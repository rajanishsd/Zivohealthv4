#!/usr/bin/env python3
"""
Lab Test to LOINC Code Mapper
==============================

This script:
1. Extracts all lab tests from lab_test_mappings table
2. Uses LOINC embeddings to find similar LOINC codes
3. Queries ChatGPT to get the exact LOINC code based on test details
4. Updates the lab_test_mappings table with LOINC codes

Usage:
    python lab_test_loinc_mapper.py --setup-db
    python lab_test_loinc_mapper.py --map-tests
    python lab_test_loinc_mapper.py --update-loinc-column
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import argparse

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Third-party imports
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import openai
from langchain_openai import ChatOpenAI
from tqdm import tqdm
from dotenv import load_dotenv
load_dotenv()
# Local imports
from loinc_embedder import LOINCEmbeddingPipeline, DATABASE_URL
from config import (
    LAB_AGGREGATION_AGENT_MODEL, LAB_AGGREGATION_AGENT_TEMPERATURE, 
    LAB_TEST_MAPPINGS_TABLE, LAB_MAPPER_BATCH_SIZE, LAB_MAPPER_RATE_LIMIT_DELAY,
    OPENAI_API_KEY
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lab_test_loinc_mapper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration - all imported from config.py

@dataclass
class LabTest:
    """Data class for lab test records"""
    id: int
    test_name: str
    test_code: Optional[str]  # Standardized test code for grouping similar tests
    test_category: str
    description: Optional[str]
    common_units: Optional[str]
    normal_range_info: Optional[str]
    loinc_code: Optional[str] = None
    
    def get_search_text(self) -> str:
        """Get text for LOINC search"""
        parts = [self.test_name]
        
        if self.description:
            parts.append(self.description)
        
        if self.common_units:
            parts.append(f"Units: {self.common_units}")
        
        if self.normal_range_info:
            parts.append(f"Range: {self.normal_range_info}")
        
        return " ".join(parts)
    
    def get_chatgpt_prompt(self, similar_loinc_codes: List[Dict]) -> str:
        """Generate ChatGPT prompt for LOINC code determination"""
        
        # Check if the similar codes are relevant to the test
        relevant_codes = []
        test_keywords = self.test_name.lower().split()
        
        for loinc in similar_loinc_codes[:10]:  # Check more codes for relevance
            loinc_name = loinc['long_common_name'].lower()
            # Check if any test keywords appear in the LOINC name
            if any(keyword in loinc_name for keyword in test_keywords if len(keyword) > 2):
                relevant_codes.append(loinc)
        
        # Format LOINC codes for the prompt
        if relevant_codes:
            loinc_examples = ""
            for i, loinc in enumerate(relevant_codes[:5], 1):
                loinc_examples += f"{i}. LOINC: {loinc['loinc_num']} - {loinc['long_common_name']}\n"
            search_context = f"SIMILAR LOINC CODES FOUND:\n{loinc_examples}"
        else:
            search_context = "SIMILAR LOINC CODES FOUND:\n(No relevant LOINC codes found in search results)"
        
        prompt = f"""You are a medical coding expert specializing in LOINC codes. I need you to determine the most appropriate LOINC code for a lab test.

LAB TEST DETAILS:
- Test Name: {self.test_name}
- Category: {self.test_category}
- Description: {self.description or 'Not provided'}
- Units: {self.common_units or 'Not provided'}
- Normal Range: {self.normal_range_info or 'Not provided'}

{search_context}

INSTRUCTIONS:
1. Analyze the lab test details above
2. If relevant LOINC codes are provided, review them first and select the best match
3. If no relevant codes are provided or the search results are unrelated, use your medical knowledge to determine the appropriate LOINC code
4. For common lab tests, you should know the standard LOINC codes (e.g., Vitamin D 25-OH is typically 1989-3)
5. Determine the most appropriate LOINC code for this test
6. If no suitable code exists, respond with "NO_MATCH"

IMPORTANT: If the search results are not relevant to the test (e.g., searching for "vitamin d" but getting "DPYD gene" results), rely on your medical knowledge to provide the correct LOINC code.

RESPONSE FORMAT:
Return in this exact format:
LOINC_CODE: [the LOINC code]
SOURCE: [LOINC or CHATGPT]

Example:
LOINC_CODE: 1989-3
SOURCE: CHATGPT

Or if no match:
LOINC_CODE: NO_MATCH
SOURCE: NONE

LOINC CODE:"""

        return prompt

class LabTestLOINCMapper:
    """Main class for mapping lab tests to LOINC codes"""
    
    def __init__(self):
        self.openai_client = ChatOpenAI(
            model=LAB_AGGREGATION_AGENT_MODEL,
            api_key=OPENAI_API_KEY
        )
        self.loinc_pipeline = LOINCEmbeddingPipeline()
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
        
        # Statistics
        self.processed_count = 0
        self.matched_count = 0
        self.no_match_count = 0
        self.error_count = 0
    
    def setup_database(self):
        """Add LOINC code column to lab_test_mappings table"""
        logger.info("🚀 Setting up database for LOINC code mapping...")
        
        try:
            with self.engine.begin() as conn:
                # Check if loinc_code column already exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = :table_name AND column_name = 'loinc_code'
                """), {"table_name": LAB_TEST_MAPPINGS_TABLE})
                
                if result.fetchone():
                    logger.info("✅ LOINC code column already exists")
                else:
                    # Add loinc_code column
                    conn.execute(text(f"""
                        ALTER TABLE {LAB_TEST_MAPPINGS_TABLE} 
                        ADD COLUMN loinc_code VARCHAR(20)
                    """))
                    
                    # Create index for the new column
                    conn.execute(text(f"""
                        CREATE INDEX idx_lab_test_mappings_loinc_code 
                        ON {LAB_TEST_MAPPINGS_TABLE}(loinc_code)
                    """))
                    
                    logger.info("✅ Added loinc_code column to lab_test_mappings table")
                
                # Check if loinc_source column already exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = :table_name AND column_name = 'loinc_source'
                """), {"table_name": LAB_TEST_MAPPINGS_TABLE})
                
                if result.fetchone():
                    logger.info("✅ LOINC source column already exists")
                else:
                    # Add loinc_source column
                    conn.execute(text(f"""
                        ALTER TABLE {LAB_TEST_MAPPINGS_TABLE} 
                        ADD COLUMN loinc_source VARCHAR(20)
                    """))
                    
                    # Create index for the new column
                    conn.execute(text(f"""
                        CREATE INDEX idx_lab_test_mappings_loinc_source 
                        ON {LAB_TEST_MAPPINGS_TABLE}(loinc_source)
                    """))
                    
                    logger.info("✅ Added loinc_source column to lab_test_mappings table")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            return False
    
    def get_lab_tests(self) -> List[LabTest]:
        """Get all lab tests from the database, grouped by test_code to avoid duplicates"""
        logger.info("📊 Fetching lab tests from database...")
        
        try:
            with self.Session() as session:
                # Get unique test codes with their details, fallback to test_name if test_code is null
                result = session.execute(text(f"""
                    SELECT DISTINCT 
                        COALESCE(test_code, test_name) as grouping_key,
                        test_name, 
                        test_code,
                        test_category, 
                        description, 
                        common_units, 
                        normal_range_info, 
                        loinc_code
                    FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true
                    ORDER BY test_category, COALESCE(test_code, test_name)
                """))
                
                tests = []
                for row in result:
                    test = LabTest(
                        id=0,  # We'll use test_code as the identifier
                        test_name=row[1],
                        test_code=row[2],
                        test_category=row[3],
                        description=row[4],
                        common_units=row[5],
                        normal_range_info=row[6],
                        loinc_code=row[7]
                    )
                    tests.append(test)
                
                logger.info(f"✅ Found {len(tests)} unique lab tests (grouped by test_code)")
                return tests
                
        except Exception as e:
            logger.error(f"❌ Error fetching lab tests: {e}")
            return []
    
    def search_similar_loinc_codes(self, test: LabTest, k: int =300) -> List[Dict]:
        """Search for similar LOINC codes using embeddings"""
        try:
            search_text = test.get_search_text()
            results = self.loinc_pipeline.search_loinc_codes(search_text, k=k)
            
            similar_codes = []
            for doc, score in results:
                metadata = doc.metadata
                similar_codes.append({
                    'loinc_num': metadata.get('loinc_num', ''),
                    'long_common_name': metadata.get('long_common_name', ''),
                    'component': metadata.get('component', ''),
                    'property': metadata.get('property', ''),
                    'system': metadata.get('system', ''),
                    'score': score
                })
            
            return similar_codes
            
        except Exception as e:
            logger.error(f"❌ Error searching LOINC codes for {test.test_name}: {e}")
            return []
    
    def get_chatgpt_loinc_code(self, test: LabTest, similar_codes: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
        """Query ChatGPT to determine the exact LOINC code"""
        try:
            # Check if search results are relevant
            test_keywords = test.test_name.lower().split()
            relevant_codes = []
            
            for loinc in similar_codes[:10]:
                loinc_name = loinc['long_common_name'].lower()
                if any(keyword in loinc_name for keyword in test_keywords if len(keyword) > 2):
                    relevant_codes.append(loinc)
            
            if not relevant_codes and similar_codes:
                logger.warning(f"⚠️  Search results for '{test.test_name}' appear unrelated. Using ChatGPT's medical knowledge.")
                logger.warning(f"   Search returned: {similar_codes[0]['long_common_name'][:50]}...")
            
            prompt = test.get_chatgpt_prompt(similar_codes)
            
            # Use ChatOpenAI pattern instead of openai.OpenAI
            response = self.openai_client.invoke([
                    {"role": "system", "content": "You are a medical coding expert specializing in LOINC codes."},
                    {"role": "user", "content": prompt}
            ])
            
            response_text = response.content.strip()
            
            # Parse the response to extract LOINC code and source
            loinc_code = None
            source = None
            
            for line in response_text.split('\n'):
                line = line.strip()
                if line.startswith('LOINC_CODE:'):
                    loinc_code = line.replace('LOINC_CODE:', '').strip()
                elif line.startswith('SOURCE:'):
                    source = line.replace('SOURCE:', '').strip()
            
            # Validate LOINC code format
            if loinc_code == "NO_MATCH":
                return None, None
            
            # Basic LOINC code validation - LOINC codes can have various formats:
            # - Standard format: XXXXX-X (e.g., 751-8, 8480-6)
            # - Extended format: XXXXX-X-X (e.g., 12345-6-7)
            # - Some codes might not have dashes but are still valid
            
            # Check if it looks like a LOINC code (contains numbers and possibly dashes)
            if loinc_code and any(c.isdigit() for c in loinc_code):
                # Additional validation: should not contain spaces or special characters except dashes
                if all(c.isalnum() or c == '-' for c in loinc_code):
                    return loinc_code, source
                else:
                    logger.warning(f"⚠️  LOINC code contains invalid characters: {loinc_code}")
                    return None, None
            else:
                logger.warning(f"⚠️  Invalid LOINC code format (no digits): {loinc_code}")
                return None, None
                
        except Exception as e:
            logger.error(f"❌ Error querying ChatGPT for {test.test_name}: {e}")
            return None, None

    def update_loinc_code(self, test_code: str, test_name: str, loinc_code: str, source: str) -> bool:
        """Update the LOINC code for all records with the same test_code"""
        try:
            with self.engine.begin() as conn:
                # Update all records with the same test_code, fallback to test_name if test_code is null
                if test_code:
                    result = conn.execute(text(f"""
                        UPDATE {LAB_TEST_MAPPINGS_TABLE}
                        SET loinc_code = :loinc_code, loinc_source = :source, updated_at = CURRENT_TIMESTAMP
                        WHERE (test_code = :test_code OR (test_code IS NULL AND test_name = :test_name)) 
                        AND is_active = true
                    """), {
                        "loinc_code": loinc_code,
                        "source": source,
                        "test_code": test_code,
                        "test_name": test_name
                    })
                else:
                    # Fallback to test_name if test_code is not available
                    result = conn.execute(text(f"""
                        UPDATE {LAB_TEST_MAPPINGS_TABLE}
                        SET loinc_code = :loinc_code, loinc_source = :source, updated_at = CURRENT_TIMESTAMP
                        WHERE test_name = :test_name AND is_active = true
                    """), {
                        "loinc_code": loinc_code,
                        "source": source,
                        "test_name": test_name
                    })
                
                updated_count = result.rowcount
                grouping_key = test_code if test_code else test_name
                logger.info(f"✅ Updated {updated_count} records for test_code '{grouping_key}' with LOINC code '{loinc_code}' (Source: {source})")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating LOINC code for test_code '{test_code}': {e}")
            return False
    
    def _show_duplicate_tests(self):
        """Show duplicate test codes in the database"""
        try:
            with self.engine.connect() as conn:
                # Show duplicates by test_code
                result = conn.execute(text(f"""
                    SELECT test_code, COUNT(*) as count
                    FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true AND test_code IS NOT NULL
                    GROUP BY test_code
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                """))
                
                test_code_duplicates = []
                for row in result:
                    test_code_duplicates.append({
                        'test_code': row[0],
                        'count': row[1]
                    })
                
                # Show duplicates by test_name (for records without test_code)
                result = conn.execute(text(f"""
                    SELECT test_name, COUNT(*) as count
                    FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true AND test_code IS NULL
                    GROUP BY test_name
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                """))
                
                test_name_duplicates = []
                for row in result:
                    test_name_duplicates.append({
                        'test_name': row[0],
                        'count': row[1]
                    })
                
                if test_code_duplicates:
                    logger.info(f"📋 Found {len(test_code_duplicates)} test codes with duplicates:")
                    for dup in test_code_duplicates[:5]:  # Show first 5
                        logger.info(f"   - test_code '{dup['test_code']}': {dup['count']} records")
                    if len(test_code_duplicates) > 5:
                        logger.info(f"   ... and {len(test_code_duplicates) - 5} more")
                
                if test_name_duplicates:
                    logger.info(f"📋 Found {len(test_name_duplicates)} test names with duplicates (no test_code):")
                    for dup in test_name_duplicates[:5]:  # Show first 5
                        logger.info(f"   - test_name '{dup['test_name']}': {dup['count']} records")
                    if len(test_name_duplicates) > 5:
                        logger.info(f"   ... and {len(test_name_duplicates) - 5} more")
                
                if not test_code_duplicates and not test_name_duplicates:
                    logger.info("✅ No duplicate test codes or names found")
                else:
                    logger.info("   (All duplicates will be updated together when LOINC code is found)")
                    
        except Exception as e:
            logger.error(f"❌ Error checking for duplicates: {e}")

    def map_tests_to_loinc(self, max_tests: Optional[int] = None):
        """Map lab tests to LOINC codes"""
        logger.info("🚀 Starting lab test to LOINC mapping...")
        
        # Get all lab tests
        tests = self.get_lab_tests()
        
        if max_tests:
            tests = tests[:max_tests]
        
        logger.info(f"📊 Processing {len(tests)} unique lab tests...")
        
        # Show duplicate test names if any
        self._show_duplicate_tests()
        
        # Process tests in batches
        for i in tqdm(range(0, len(tests), LAB_MAPPER_BATCH_SIZE), desc="Processing batches"):
            batch = tests[i:i + LAB_MAPPER_BATCH_SIZE]
            
            for test in batch:
                try:
                    # Skip if already has LOINC code
                    if test.loinc_code:
                        logger.info(f"⏭️  Skipping {test.test_name} (already has LOINC code: {test.loinc_code})")
                        continue
                    
                    logger.info(f"🔍 Processing: {test.test_name}")
                    
                    # Search for similar LOINC codes
                    similar_codes = self.search_similar_loinc_codes(test)
                    
                    if not similar_codes:
                        logger.warning(f"⚠️  No similar LOINC codes found for {test.test_name}")
                        self.no_match_count += 1
                        continue
                    
                    # Query ChatGPT for exact LOINC code
                    loinc_code, source = self.get_chatgpt_loinc_code(test, similar_codes)
                    
                    if loinc_code:
                        # Update database for all records with the same test_code
                        if self.update_loinc_code(test.test_code, test.test_name, loinc_code, source):
                            grouping_key = test.test_code if test.test_code else test.test_name
                            logger.info(f"✅ Mapped {grouping_key} -> {loinc_code} (Source: {source})")
                            self.matched_count += 1
                        else:
                            logger.error(f"❌ Failed to update LOINC code for {test.test_name}")
                            self.error_count += 1
                    else:
                        logger.warning(f"⚠️  No LOINC code determined for {test.test_name}")
                        self.no_match_count += 1
                    
                    self.processed_count += 1
                    
                    # Rate limiting
                    time.sleep(LAB_MAPPER_RATE_LIMIT_DELAY)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing {test.test_name}: {e}")
                    self.error_count += 1
                    continue
        
        # Final summary
        logger.info(f"\n🎉 LOINC Mapping Complete!")
        logger.info(f"📊 Total processed: {self.processed_count}")
        logger.info(f"✅ Successfully mapped: {self.matched_count}")
        logger.info(f"⚠️  No match found: {self.no_match_count}")
        logger.info(f"❌ Errors: {self.error_count}")
    
    def get_mapping_stats(self) -> Dict[str, Any]:
        """Get statistics about LOINC code mapping"""
        try:
            with self.engine.connect() as conn:
                # Total tests
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true
                """))
                total_tests = result.scalar()
                
                # Tests with LOINC codes
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true AND loinc_code IS NOT NULL
                """))
                mapped_tests = result.scalar()
                
                # Tests without LOINC codes
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true AND loinc_code IS NULL
                """))
                unmapped_tests = result.scalar()
                
                # Unique test codes and names
                result = conn.execute(text(f"""
                    SELECT COUNT(DISTINCT test_code) FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true AND test_code IS NOT NULL
                """))
                unique_test_codes = result.scalar()
                
                result = conn.execute(text(f"""
                    SELECT COUNT(DISTINCT test_name) FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true
                """))
                unique_test_names = result.scalar()
                
                # Duplicate test codes analysis
                result = conn.execute(text(f"""
                    SELECT test_code, COUNT(*) as count
                    FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true AND test_code IS NOT NULL
                    GROUP BY test_code
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                """))
                duplicate_test_codes = []
                for row in result:
                    duplicate_test_codes.append({
                        'test_code': row[0],
                        'count': row[1]
                    })
                
                # Duplicate test names analysis (for records without test_code)
                result = conn.execute(text(f"""
                    SELECT test_name, COUNT(*) as count
                    FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true AND test_code IS NULL
                    GROUP BY test_name
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                """))
                duplicate_test_names = []
                for row in result:
                    duplicate_test_names.append({
                        'test_name': row[0],
                        'count': row[1]
                    })
                
                # Category breakdown
                result = conn.execute(text(f"""
                    SELECT test_category, COUNT(*) as total, 
                           COUNT(loinc_code) as mapped
                    FROM {LAB_TEST_MAPPINGS_TABLE}
                    WHERE is_active = true
                    GROUP BY test_category
                    ORDER BY test_category
                """))
                category_stats = []
                for row in result:
                    category_stats.append({
                        'category': row[0],
                        'total': row[1],
                        'mapped': row[2],
                        'percentage': round((row[2] / row[1]) * 100, 1) if row[1] > 0 else 0
                    })
                
                return {
                    'total_tests': total_tests,
                    'unique_test_codes': unique_test_codes,
                    'unique_test_names': unique_test_names,
                    'mapped_tests': mapped_tests,
                    'unmapped_tests': unmapped_tests,
                    'mapping_percentage': round((mapped_tests / total_tests) * 100, 1) if total_tests > 0 else 0,
                    'duplicate_test_codes': duplicate_test_codes,
                    'duplicate_test_names': duplicate_test_names,
                    'category_stats': category_stats
                }
                
        except Exception as e:
            logger.error(f"Error getting mapping stats: {e}")
            return {"error": str(e)}

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="Lab Test to LOINC Code Mapper")
    parser.add_argument("--setup-db", action="store_true", help="Setup database (add LOINC column)")
    parser.add_argument("--map-tests", action="store_true", help="Map lab tests to LOINC codes")
    parser.add_argument("--max-tests", type=int, help="Maximum number of tests to process")
    parser.add_argument("--stats", action="store_true", help="Show mapping statistics")
    
    args = parser.parse_args()
    
    if not any([args.setup_db, args.map_tests, args.stats]):
        logger.error("Please specify at least one action")
        parser.print_help()
        return
    
    if not OPENAI_API_KEY:
        logger.error("❌ OPENAI_API_KEY environment variable not set")
        return
    
    try:
        mapper = LabTestLOINCMapper()
        
        if args.setup_db:
            mapper.setup_database()
        
        if args.map_tests:
            mapper.map_tests_to_loinc(max_tests=args.max_tests)
        
        if args.stats:
            stats = mapper.get_mapping_stats()
            logger.info(f"📊 Mapping Statistics: {json.dumps(stats, indent=2)}")
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 