#!/usr/bin/env python3
"""
LOINC Embedder with OpenAI text-embedding-3-large
================================================

This script processes LOINC Core Table CSV and creates embeddings using OpenAI's
text-embedding-3-large model, storing them in custom PostgreSQL tables via PGVector.

Features:
- OpenAI text-embedding-3-large embeddings (3072 dimensions)
- Custom table names to avoid conflicts with existing PubMed data
- Batch processing with rate limiting
- Progress tracking and resumable processing
- Comprehensive metadata extraction

Usage:
    python loinc_embedder.py --setup-db
    python loinc_embedder.py --process-loinc
    python loinc_embedder.py --search "blood glucose"
"""

import os
import sys
import csv
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Generator
import logging
from datetime import datetime
import argparse
from dataclasses import dataclass

# Third-party imports
import pandas as pd
from tqdm import tqdm

# Local imports
from config import (
    EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, MAX_RETRIES, LOINC_CSV_FILE, COLLECTION_NAME, 
    LOINC_COLLECTION_TABLE, LOINC_EMBEDDING_TABLE, DATABASE_URL, LOINC_CSV_PATH,
    LOINC_EMBEDDER_BATCH_SIZE, EMBEDDING_BATCH_SIZE, LOINC_EMBEDDER_RATE_LIMIT_DELAY
)

# LangChain imports
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain.docstore.document import Document
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('loinc_embedder.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Processing settings - all imported from config.py

@dataclass
class LOINCRecord:
    """Data class for LOINC records"""
    loinc_num: str
    component: str
    property: str
    time_aspect: str
    system: str
    scale_type: str
    method_type: str
    loinc_class: str
    long_common_name: str
    short_name: str
    status: str
    version_first_released: str
    version_last_changed: str
    
    def get_embedding_text(self) -> str:
        """Get combined text for embedding"""
        return f"""LOINC: {self.loinc_num}
Name: {self.long_common_name}
Short Name: {self.short_name}
Component: {self.component}
Property: {self.property}
System: {self.system}
Class: {self.loinc_class}
Status: {self.status}"""
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata dictionary"""
        return {
            "loinc_num": self.loinc_num,
            "component": self.component,
            "property": self.property,
            "time_aspect": self.time_aspect,
            "system": self.system,
            "scale_type": self.scale_type,
            "method_type": self.method_type,
            "loinc_class": self.loinc_class,
            "long_common_name": self.long_common_name,
            "short_name": self.short_name,
            "status": self.status,
            "version_first_released": self.version_first_released,
            "version_last_changed": self.version_last_changed,
            "document_type": "loinc",
            "data_source": "loinc_core_table"
        }
    
    def to_langchain_document(self) -> Document:
        """Convert to LangChain Document"""
        return Document(
            page_content=self.get_embedding_text(),
            metadata=self.get_metadata()
        )

class CustomLOINCPGVector(PGVector):
    """Custom PGVector class with custom table names for LOINC data"""
    
    def __init__(self, connection_string: str, embedding_function, collection_name: str):
        # Initialize parent class
        super().__init__(
            connection_string=connection_string,
            embedding_function=embedding_function,
            collection_name=collection_name
        )
        
        # Override table names
        self.collection_table_name = LOINC_COLLECTION_TABLE
        self.embedding_table_name = LOINC_EMBEDDING_TABLE
        
        # Create tables during initialization (once)
        self._create_tables_if_not_exists()
        
        # Cache collection ID to avoid repeated queries
        self._collection_id = None
    
    def _create_tables_if_not_exists(self) -> None:
        """Create custom tables with LOINC-specific names (called once during initialization)"""
        with self._make_session() as session:
            # Create custom collection table
            session.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {self.collection_table_name} (
                    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    cmetadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create custom embedding table
            session.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {self.embedding_table_name} (
                    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    collection_id UUID REFERENCES {self.collection_table_name}(uuid),
                    embedding VECTOR(768),
                    document TEXT,
                    cmetadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create indexes
            session.execute(text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.embedding_table_name}_collection 
                ON {self.embedding_table_name}(collection_id)
            """))
            
            # Create embedding index for BioBERT (768 dimensions < 2000 limit)
            session.execute(text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.embedding_table_name}_embedding 
                ON {self.embedding_table_name} USING hnsw (embedding vector_cosine_ops)
            """))
            
            logger.info(f"✅ Created embedding index for BioBERT (768 dimensions)")
            
            session.commit()
            logger.info(f"✅ Created custom tables: {self.collection_table_name}, {self.embedding_table_name}")
    
    def _get_collection_id(self) -> str:
        """Get or create collection ID using custom table (with caching)"""
        # Return cached collection ID if available
        if self._collection_id:
            return self._collection_id
            
        with self._make_session() as session:
            # Check if collection exists
            result = session.execute(text(f"""
                SELECT uuid FROM {self.collection_table_name} 
                WHERE name = :name
            """), {"name": self.collection_name}).fetchone()
            
            if result:
                self._collection_id = str(result[0])
                return self._collection_id
            
            # Create new collection
            collection_id = str(uuid.uuid4())
            session.execute(text(f"""
                INSERT INTO {self.collection_table_name} (uuid, name, cmetadata)
                VALUES (:uuid, :name, :metadata)
            """), {
                "uuid": collection_id,
                "name": self.collection_name,
                "metadata": json.dumps({"embedding_model": EMBEDDING_MODEL})
            })
            session.commit()
            
            # Cache the collection ID
            self._collection_id = collection_id
            logger.info(f"✅ Created collection '{self.collection_name}' with ID: {collection_id}")
            return collection_id
    
    def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """Add documents to custom embedding table"""
        if not documents:
            return []
        
        # Tables are already created during initialization
        collection_id = self._get_collection_id()
        
        # Generate embeddings
        texts = [doc.page_content for doc in documents]
        embeddings = self.embeddings.embed_documents(texts)
        
        # Insert into custom table
        document_ids = []
        with self._make_session() as session:
            for doc, embedding in zip(documents, embeddings):
                doc_id = str(uuid.uuid4())
                session.execute(text(f"""
                    INSERT INTO {self.embedding_table_name} 
                    (uuid, collection_id, embedding, document, cmetadata)
                    VALUES (:uuid, :collection_id, :embedding, :document, :metadata)
                """), {
                    "uuid": doc_id,
                    "collection_id": collection_id,
                    "embedding": embedding,
                    "document": doc.page_content,
                    "metadata": json.dumps(doc.metadata)
                })
                document_ids.append(doc_id)
            
            session.commit()
        
        logger.info(f"✅ Added {len(documents)} documents to {self.embedding_table_name}")
        return document_ids
    
    def similarity_search_with_score(self, query: str, k: int = 10, **kwargs) -> List[Tuple[Document, float]]:
        """Search using custom embedding table"""
        # Use cached collection ID for better performance
        collection_id = self._get_collection_id()
        query_embedding = self.embeddings.embed_query(query)
        
        with self._make_session() as session:
            # Convert embedding list to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            result = session.execute(text(f"""
                SELECT document, cmetadata, embedding <=> '{embedding_str}'::vector as distance
                FROM {self.embedding_table_name}
                WHERE collection_id = :collection_id
                AND (cmetadata->>'status' IS NULL OR cmetadata->>'status' != 'DISCOURAGED')
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT :k
            """), {
                "collection_id": collection_id,
                "k": k
            }).fetchall()
            
            documents = []
            for row in result:
                # Handle metadata - it might be a dict or JSON string
                if isinstance(row[1], dict):
                    metadata = row[1]
                elif isinstance(row[1], str):
                    metadata = json.loads(row[1]) if row[1] else {}
                else:
                    metadata = {}
                
                doc = Document(page_content=row[0], metadata=metadata)
                score = float(row[2])
                documents.append((doc, score))
            
            return documents

class LOINCCSVProcessor:
    """Process LOINC CSV file and extract records"""
    
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        if not self.csv_path.exists():
            raise FileNotFoundError(f"LOINC CSV file not found: {csv_path}")
        
        # Get total lines for progress tracking
        self.total_lines = self._count_lines()
        logger.info(f"📊 Found {self.total_lines:,} lines in LOINC CSV")
    
    def _count_lines(self) -> int:
        """Count total lines in CSV file"""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f) - 1  # Subtract header
    
    def process_csv(self, batch_size: int = LOINC_EMBEDDER_BATCH_SIZE) -> Generator[List[LOINCRecord], None, None]:
        """Process CSV file and yield LOINC records in batches"""
        logger.info(f"📄 Processing LOINC CSV: {self.csv_path}")
        
        records = []
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Skip empty rows
                    if not row.get('LOINC_NUM'):
                        continue
                    
                    # Create LOINC record
                    record = LOINCRecord(
                        loinc_num=row.get('LOINC_NUM', '').strip(),
                        component=row.get('COMPONENT', '').strip(),
                        property=row.get('PROPERTY', '').strip(),
                        time_aspect=row.get('TIME_ASPCT', '').strip(),
                        system=row.get('SYSTEM', '').strip(),
                        scale_type=row.get('SCALE_TYP', '').strip(),
                        method_type=row.get('METHOD_TYP', '').strip(),
                        loinc_class=row.get('CLASS', '').strip(),
                        long_common_name=row.get('LONG_COMMON_NAME', '').strip(),
                        short_name=row.get('SHORTNAME', '').strip(),
                        status=row.get('STATUS', '').strip(),
                        version_first_released=row.get('VersionFirstReleased', '').strip(),
                        version_last_changed=row.get('VersionLastChanged', '').strip()
                    )
                    
                    # Only include records with essential fields and not DISCOURAGED
                    if record.loinc_num and record.long_common_name and record.status != 'DISCOURAGED':
                        records.append(record)
                    
                    # Yield batch when ready
                    if len(records) >= batch_size:
                        yield records
                        records = []
                        
                        # Progress update
                        if row_num % 1000 == 0:
                            logger.info(f"  📈 Processed {row_num:,}/{self.total_lines:,} rows...")
                
                except Exception as e:
                    logger.warning(f"Error processing row {row_num}: {e}")
                    continue
        
        # Yield remaining records
        if records:
            yield records
        
        logger.info(f"✅ Completed processing LOINC CSV")

class LOINCEmbeddingPipeline:
    """Main pipeline for LOINC embedding processing"""
    
    def __init__(self, openai_api_key: str = None):
        # Initialize HuggingFace embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},  # Use 'cuda' if GPU available
            encode_kwargs={'normalize_embeddings': True, 'batch_size': EMBEDDING_BATCH_SIZE}
        )
        
        self.vector_store = CustomLOINCPGVector(
            connection_string=DATABASE_URL,
            embedding_function=self.embeddings,
            collection_name=COLLECTION_NAME
        )
        
        self.processor = LOINCCSVProcessor(LOINC_CSV_PATH)
        
        # Progress tracking
        self.processed_count = 0
        self.total_cost = 0.0
        self.start_time = None
    
    def setup_database(self):
        """Setup database and create tables"""
        logger.info("🚀 Setting up database for LOINC embeddings...")
        
        try:
            # Create database engine
            engine = create_engine(DATABASE_URL)
            
            # Enable pgvector extension
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("✅ pgvector extension enabled")
            
            # Tables are automatically created during vector store initialization
            # Just verify they exist
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN (:collection_table, :embedding_table)
                """), {
                    "collection_table": LOINC_COLLECTION_TABLE,
                    "embedding_table": LOINC_EMBEDDING_TABLE
                })
                tables = [row[0] for row in result.fetchall()]
                
                if len(tables) == 2:
                    logger.info(f"✅ Custom tables verified: {tables}")
                else:
                    logger.warning(f"⚠️  Expected 2 tables, found {len(tables)}: {tables}")
            
            logger.info("✅ Database setup completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            return False
    
    def process_loinc_codes(self, max_codes: Optional[int] = None):
        """Process LOINC codes and generate embeddings"""
        logger.info("🚀 Starting LOINC code processing...")
        
        self.start_time = time.time()
        processed_batches = 0
        
        try:
            for batch_records in self.processor.process_csv(batch_size=LOINC_EMBEDDER_BATCH_SIZE):
                if max_codes and self.processed_count >= max_codes:
                    logger.info(f"Reached maximum codes limit: {max_codes}")
                    break
                
                # Convert to LangChain documents
                documents = [record.to_langchain_document() for record in batch_records]
                
                # Add to vector store with rate limiting
                try:
                    start_batch_time = time.time()
                    self.vector_store.add_documents(documents)
                    batch_time = time.time() - start_batch_time
                    
                    # Update progress
                    self.processed_count += len(documents)
                    processed_batches += 1
                    
                    # No cost for local HuggingFace embeddings
                    batch_cost = 0.0
                    self.total_cost += batch_cost
                    
                    logger.info(f"✅ Batch {processed_batches}: {len(documents)} codes in {batch_time:.1f}s "
                              f"(Total: {self.processed_count:,})")
                    
                    # Minimal rate limiting for local processing
                    if LOINC_EMBEDDER_RATE_LIMIT_DELAY > 0:
                        time.sleep(LOINC_EMBEDDER_RATE_LIMIT_DELAY)
                
                except Exception as e:
                    logger.error(f"❌ Error processing batch {processed_batches}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"❌ Error in LOINC processing: {e}")
            raise
        
        # Final summary
        total_time = time.time() - self.start_time
        codes_per_minute = (self.processed_count / total_time) * 60 if total_time > 0 else 0
        
        logger.info(f"🎉 LOINC Processing Complete!")
        logger.info(f"📊 Total codes processed: {self.processed_count:,}")
        logger.info(f"⏱️  Total time: {total_time:.1f} seconds")
        logger.info(f"🚀 Processing rate: {codes_per_minute:.1f} codes/minute")
        logger.info(f"💰 Cost: $0.00 (local HuggingFace embeddings)")
    
    def search_loinc_codes(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        """Search LOINC codes using semantic similarity"""
        logger.info(f"🔍 Searching LOINC codes for: '{query}'")
        
        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        logger.info(f"Found {len(results)} results:")
        for i, (doc, score) in enumerate(results, 1):
            metadata = doc.metadata
            logger.info(f"  {i}. LOINC: {metadata.get('loinc_num', 'N/A')} "
                       f"(Score: {score:.4f})")
            logger.info(f"     Name: {metadata.get('long_common_name', 'N/A')}")
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {LOINC_EMBEDDING_TABLE} e
                    JOIN {LOINC_COLLECTION_TABLE} c ON e.collection_id = c.uuid
                    WHERE c.name = :collection_name
                """), {"collection_name": COLLECTION_NAME})
                count = result.scalar()
                
                return {
                    "total_loinc_codes": count or 0,
                    "collection_name": COLLECTION_NAME,
                    "embedding_model": EMBEDDING_MODEL,
                    "embedding_dimensions": EMBEDDING_DIMENSIONS,
                    "custom_tables": {
                        "collection_table": LOINC_COLLECTION_TABLE,
                        "embedding_table": LOINC_EMBEDDING_TABLE
                    }
                }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="LOINC Embedder with OpenAI")
    parser.add_argument("--setup-db", action="store_true", help="Setup database")
    parser.add_argument("--process-loinc", action="store_true", help="Process LOINC codes")
    parser.add_argument("--max-codes", type=int, help="Maximum codes to process")
    parser.add_argument("--search", type=str, help="Search LOINC codes")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    
    args = parser.parse_args()
    
    if not any([args.setup_db, args.process_loinc, args.search, args.stats]):
        logger.error("Please specify at least one action")
        parser.print_help()
        return
    
    try:
        pipeline = LOINCEmbeddingPipeline()
        
        if args.setup_db:
            pipeline.setup_database()
        
        if args.process_loinc:
            pipeline.process_loinc_codes(max_codes=args.max_codes)
        
        if args.search:
            pipeline.search_loinc_codes(args.search)
        
        if args.stats:
            stats = pipeline.get_stats()
            logger.info(f"📊 Database stats: {stats}")
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 