#!/usr/bin/env python3
"""
RxNorm Embedder with BioBERT model
==================================

This script processes RxNorm CONCEPT CSV and creates embeddings using the
pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb model from Hugging Face,
storing them in custom PostgreSQL tables via PGVector.

Features:
- BioBERT embeddings (768 dimensions)
- Custom table names to avoid conflicts with existing data
- Batch processing with rate limiting
- Progress tracking and resumable processing
- Comprehensive metadata extraction

Usage:
    python rxnorm_embedder.py --setup-db
    python rxnorm_embedder.py --process-rxnorm
    python rxnorm_embedder.py --search "aspirin"
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
        logging.FileHandler('rxnorm_embedder.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Remove all hardcoded config values and import from config.py
from config import (
    DATABASE_URL,
    EMBEDDING_MODEL,
    RXNORM_CSV_FILE,
    COLLECTION_NAME,
    RXNORM_COLLECTION_TABLE,
    RXNORM_EMBEDDING_TABLE,
    BATCH_SIZE,
    EMBEDDING_BATCH_SIZE,
    RATE_LIMIT_DELAY,
    # ...any other needed config values...
)

@dataclass
class RxNormRecord:
    """Data class for RxNorm records"""
    concept_id: str
    concept_name: str
    domain_id: str
    vocabulary_id: str
    concept_class_id: str
    standard_concept: str
    concept_code: str
    valid_start_date: str
    valid_end_date: str
    invalid_reason: str
    
    def get_embedding_text(self) -> str:
        """Get text for embedding (only concept_name)"""
        return self.concept_name
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata dictionary"""
        return {
            "concept_id": self.concept_id,
            "concept_name": self.concept_name,
            "domain_id": self.domain_id,
            "vocabulary_id": self.vocabulary_id,
            "concept_class_id": self.concept_class_id,
            "standard_concept": self.standard_concept,
            "concept_code": self.concept_code,
            "valid_start_date": self.valid_start_date,
            "valid_end_date": self.valid_end_date,
            "invalid_reason": self.invalid_reason,
            "document_type": "rxnorm",
            "data_source": "rxnorm_concept_table"
        }
    
    def to_langchain_document(self) -> Document:
        """Convert to LangChain Document"""
        return Document(
            page_content=self.get_embedding_text(),
            metadata=self.get_metadata()
        )

class CustomRxNormPGVector(PGVector):
    """Custom PGVector class with custom table names for RxNorm data"""
    
    def __init__(self, connection_string: str, embedding_function, collection_name: str):
        # Initialize parent class
        super().__init__(
            connection_string=connection_string,
            embedding_function=embedding_function,
            collection_name=collection_name
        )
        
        # Override table names
        self.collection_table_name = RXNORM_COLLECTION_TABLE
        self.embedding_table_name = RXNORM_EMBEDDING_TABLE
        
        # Create tables during initialization (once)
        self._create_tables_if_not_exists()
        
        # Cache collection ID to avoid repeated queries
        self._collection_id = None
    
    def _create_tables_if_not_exists(self) -> None:
        """Create custom tables with RxNorm-specific names (called once during initialization)"""
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
            """), {"name": self.collection_name})
            
            existing_collection = result.fetchone()
            
            if existing_collection:
                self._collection_id = str(existing_collection[0])
                logger.info(f"✅ Found existing collection: {self.collection_name}")
            else:
                # Create new collection
                result = session.execute(text(f"""
                    INSERT INTO {self.collection_table_name} (name, cmetadata)
                    VALUES (:name, :metadata)
                    RETURNING uuid
                """), {
                    "name": self.collection_name,
                    "metadata": json.dumps({"description": "RxNorm terminology embeddings"})
                })
                
                self._collection_id = str(result.fetchone()[0])
                logger.info(f"✅ Created new collection: {self.collection_name}")
            
            session.commit()
            return self._collection_id
    
    def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """Add documents to the vector store with custom table names"""
        collection_id = self._get_collection_id()
        
        # Get embeddings for all documents
        texts = [doc.page_content for doc in documents]
        embeddings = self.embedding_function.embed_documents(texts)
        
        # Prepare data for insertion
        ids = []
        with self._make_session() as session:
            for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
                doc_id = str(uuid.uuid4())
                ids.append(doc_id)
                
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
            
            session.commit()
        
        logger.info(f"✅ Added {len(documents)} documents to RxNorm collection")
        return ids
    
    def similarity_search_with_score(self, query: str, k: int = 10, **kwargs) -> List[Tuple[Document, float]]:
        """Search for similar documents with custom table names"""
        collection_id = self._get_collection_id()
        
        # Get query embedding
        query_embedding = self.embedding_function.embed_query(query)
        
        # Search in custom table
        with self._make_session() as session:
            result = session.execute(text(f"""
                    SELECT document, cmetadata,
                        1 - (embedding <=> (:embedding)::vector) as similarity
                    FROM {self.embedding_table_name}
                    WHERE collection_id = :collection_id
                    ORDER BY embedding <=> (:embedding)::vector
                    LIMIT :k
                """), {
                "embedding": query_embedding,
                "collection_id": collection_id,
                "k": k
            })
            
            results = []
            for row in result:
                doc = Document(
                    page_content=row[0],
                    metadata=json.loads(row[1]) if row[1] else {}
                )
                results.append((doc, row[2]))
            
            return results

class RxNormCSVProcessor:
    """Process RxNorm CONCEPT CSV file"""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
    
    def _count_lines(self) -> int:
        """Count total lines in CSV file"""
        with open(self.csv_path, 'r') as f:
            return sum(1 for _ in f)
    
    def process_csv(self, batch_size: int = BATCH_SIZE) -> Generator[List[RxNormRecord], None, None]:
        """Process CSV file in batches, filtering for RxNorm drugs"""
        logger.info(f"Processing RxNorm CSV: {self.csv_path}")
        
        batch = []
        total_processed = 0
        total_filtered = 0
        
        with open(self.csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile, delimiter='\t')
            
            for row in reader:
                total_processed += 1
                
                # Filter for standard RxNorm drugs
                if (row['vocabulary_id'] == 'RxNorm' and 
                    row['domain_id'] == 'Drug' and 
                    row['standard_concept'] == 'S'):
                    
                    rxnorm_record = RxNormRecord(
                        concept_id=row['concept_id'],
                        concept_name=row['concept_name'],
                        domain_id=row['domain_id'],
                        vocabulary_id=row['vocabulary_id'],
                        concept_class_id=row['concept_class_id'],
                        standard_concept=row['standard_concept'],
                        concept_code=row['concept_code'],
                        valid_start_date=row['valid_start_date'],
                        valid_end_date=row['valid_end_date'],
                        invalid_reason=row['invalid_reason']
                    )
                    
                    batch.append(rxnorm_record)
                    total_filtered += 1
                    
                    if len(batch) >= batch_size:
                        logger.info(f"Processing batch: {len(batch)} records (Total filtered: {total_filtered})")
                        yield batch
                        batch = []
                
                # Progress update
                if total_processed % 100000 == 0:
                    logger.info(f"Processed {total_processed} records, filtered {total_filtered}")
            
            # Yield remaining batch
            if batch:
                logger.info(f"Processing final batch: {len(batch)} records")
                yield batch
        
        logger.info(f"✅ Completed processing. Total: {total_processed}, Filtered: {total_filtered}")

class RxNormEmbeddingPipeline:
    """Main pipeline for RxNorm embedding processing"""
    
    def __init__(self):
        # Initialize HuggingFace embeddings with BioBERT model
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Initialize vector store
        self.vector_store = CustomRxNormPGVector(
            connection_string=DATABASE_URL,
            embedding_function=self.embeddings,
            collection_name=COLLECTION_NAME
        )
        
        # Initialize CSV processor
        self.csv_processor = RxNormCSVProcessor(RXNORM_CSV_FILE)
    
    def setup_database(self):
        """Setup database tables and indexes"""
        logger.info("Setting up RxNorm database tables...")
        
        # Tables are created automatically during CustomRxNormPGVector initialization
        logger.info("✅ Database setup completed")
    
    def process_rxnorm_codes(self, max_codes: Optional[int] = None):
        """Process RxNorm codes and create embeddings"""
        logger.info("Starting RxNorm embedding pipeline...")
        
        total_processed = 0
        start_time = time.time()
        
        try:
            for batch in self.csv_processor.process_csv():
                # Convert to LangChain documents
                documents = [record.to_langchain_document() for record in batch]
                
                # Add to vector store
                self.vector_store.add_documents(documents)
                
                total_processed += len(batch)
                
                # Check if we've reached the limit
                if max_codes and total_processed >= max_codes:
                    logger.info(f"Reached maximum codes limit: {max_codes}")
                    break
                
                # Progress update
                elapsed_time = time.time() - start_time
                rate = total_processed / elapsed_time if elapsed_time > 0 else 0
                logger.info(f"Processed {total_processed} RxNorm codes ({rate:.2f} codes/sec)")
                
                # Rate limiting
                time.sleep(RATE_LIMIT_DELAY)
        
        except KeyboardInterrupt:
            logger.info("Processing interrupted by user")
        except Exception as e:
            logger.error(f"Error during processing: {e}")
            raise
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Completed processing {total_processed} RxNorm codes in {elapsed_time:.2f} seconds")
    
    def search_rxnorm_codes(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        """Search for RxNorm codes"""
        logger.info(f"Searching for: {query}")
        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        for i, (doc, score) in enumerate(results):
            logger.info(f"{i+1}. Score: {score:.4f} - {doc.page_content[:100]}...")
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        with self.vector_store._make_session() as session:
            result = session.execute(text(f"""
                SELECT COUNT(*) FROM {self.vector_store.embedding_table_name}
                WHERE collection_id = (
                    SELECT uuid FROM {self.vector_store.collection_table_name} 
                    WHERE name = :collection_name
                )
            """), {"collection_name": self.vector_store.collection_name})
            total_embeddings = result.fetchone()[0]
            return {
                "total_embeddings": total_embeddings,
                "collection_name": self.vector_store.collection_name,
                "embedding_model": EMBEDDING_MODEL,
                "embedding_dimensions": 768
            }

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="RxNorm Embedder")
    parser.add_argument("--setup-db", action="store_true", help="Setup database tables")
    parser.add_argument("--process-rxnorm", action="store_true", help="Process RxNorm codes")
    parser.add_argument("--search", type=str, help="Search for RxNorm codes")
    parser.add_argument("--max-codes", type=int, help="Maximum number of codes to process")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    
    args = parser.parse_args()
    
    pipeline = RxNormEmbeddingPipeline()
    
    if args.setup_db:
        pipeline.setup_database()
    
    elif args.process_rxnorm:
        pipeline.process_rxnorm_codes(max_codes=args.max_codes)
    
    elif args.search:
        pipeline.search_rxnorm_codes(args.search)
    
    elif args.stats:
        stats = pipeline.get_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 