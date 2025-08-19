#!/usr/bin/env python3
"""
Test SNOMED CT Embedder
======================

This script tests the SNOMED CT embedder functionality including:
- Database setup
- CSV processing
- Embedding generation
- Search functionality
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from snomedct_embedder import SNOMEDCTEmbeddingPipeline
from config import validate_config, get_config_summary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config():
    """Test configuration validation"""
    logger.info("Testing configuration...")
    try:
        validate_config()
        logger.info("✅ Configuration validation passed")
        config_summary = get_config_summary()
        logger.info(f"Configuration summary: {json.dumps(config_summary, indent=2)}")
        return True
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        return False

def test_csv_processing():
    """Test CSV processing functionality"""
    logger.info("Testing CSV processing...")
    try:
        from config import SNOMED_CONCEPTS_FILE
        if not SNOMED_CONCEPTS_FILE.exists():
            logger.error(f"❌ SNOMED CT CSV file not found: {SNOMED_CONCEPTS_FILE}")
            return False
        import pandas as pd
        df = pd.read_csv(SNOMED_CONCEPTS_FILE, sep='\t')
        logger.info(f"Read {len(df)} records from SNOMED CT CSV file")
        # Filter for SNOMED and allowed domains
        filtered = df[(df['vocabulary_id'] == 'SNOMED') & df['domain_id'].isin([
            'Condition', 'Procedure', 'Observation', 'Measurement', 'Device', 'Specimen', 'Episode'])]
        logger.info(f"Filtered to {len(filtered)} records for SNOMED and allowed domains")
        logger.info(f"Sample record: {filtered.iloc[0].to_dict() if not filtered.empty else 'No records'}")
        return True
    except Exception as e:
        logger.error(f"❌ CSV processing test failed: {e}")
        return False

def test_database_setup():
    """Test database setup"""
    logger.info("Testing database setup...")
    try:
        pipeline = SNOMEDCTEmbeddingPipeline()
        pipeline.setup_database()
        logger.info("✅ Database setup test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Database setup test failed: {e}")
        return False

def test_embedding_generation():
    """Test embedding generation with a small sample"""
    logger.info("Testing embedding generation...")
    try:
        pipeline = SNOMEDCTEmbeddingPipeline()
        from snomedct_embedder import SNOMEDRecord
        test_record = SNOMEDRecord(
            concept_id="123456",
            term="Test SNOMED Concept"
        )
        test_doc = test_record.to_langchain_document()
        logger.info(f"Test document: {test_doc.page_content[:100]}...")
        embedding = pipeline.embeddings.embed_query(test_doc.page_content)
        logger.info(f"✅ Embedding generated successfully. Dimensions: {len(embedding)}")
        return True
    except Exception as e:
        logger.error(f"❌ Embedding generation test failed: {e}")
        return False

def test_search_functionality():
    """Test search functionality"""
    logger.info("Testing search functionality...")
    try:
        pipeline = SNOMEDCTEmbeddingPipeline()
        results = pipeline.search_snomedct("diabetes", k=5)
        logger.info(f"✅ Search test completed. Found {len(results)} results")
        return True
    except Exception as e:
        logger.error(f"❌ Search functionality test failed: {e}")
        return False

def test_stats():
    """Test statistics functionality"""
    logger.info("Testing statistics...")
    try:
        pipeline = SNOMEDCTEmbeddingPipeline()
        stats = pipeline.get_stats()
        logger.info(f"✅ Statistics test passed: {json.dumps(stats, indent=2)}")
        return True
    except Exception as e:
        logger.error(f"❌ Statistics test failed: {e}")
        return False

def main():
    """Run all tests"""
    logger.info("Starting SNOMED CT embedder tests...")
    tests = [
        ("Configuration", test_config),
        ("CSV Processing", test_csv_processing),
        ("Database Setup", test_database_setup),
        ("Embedding Generation", test_embedding_generation),
        ("Search Functionality", test_search_functionality),
        ("Statistics", test_stats)
    ]
    passed = 0
    total = len(tests)
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*50}")
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
    logger.info(f"\n{'='*50}")
    logger.info(f"Test Results: {passed}/{total} tests passed")
    logger.info(f"{'='*50}")
    if passed == total:
        logger.info("🎉 All tests passed! SNOMED CT embedder is ready to use.")

if __name__ == "__main__":
    main() 