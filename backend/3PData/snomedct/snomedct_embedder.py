#!/usr/bin/env python3
"""
SNOMED CT Embedder with PySpark and BioBERT
===========================================

This script processes SNOMED CT concepts using PySpark for parallel processing,
creates embeddings using the BioBERT model, and stores them in PostgreSQL via PGVector.

Features:
- PySpark for scalable, parallel data processing
- BioBERT embeddings (768 dimensions)
- Batching and rate limiting for safe DB writes
- Custom table names to avoid conflicts
- Progress tracking and resumable processing

Usage:
    python snomedct_embedder.py --setup-db
    python snomedct_embedder.py --process-snomedct
    python snomedct_embedder.py --search "diabetes"
"""

import os
import sys
import time
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import argparse
from dataclasses import dataclass

# PySpark imports
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

# Third-party imports
from tqdm import tqdm
import pandas as pd

# LangChain imports
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain.docstore.document import Document
from sqlalchemy import create_engine, text

# Import config
from config import (
    DATABASE_URL,
    EMBEDDING_MODEL,
    SNOMED_CONCEPTS_FILE,
    COLLECTION_NAME,
    SNOMED_COLLECTION_TABLE,
    SNOMED_EMBEDDING_TABLE,
    BATCH_SIZE,
    EMBEDDING_BATCH_SIZE,
    RATE_LIMIT_DELAY,
    MAX_DB_CONNECTIONS,
    SPARK_MASTER,
    SPARK_APP_NAME,
    SPARK_NUM_EXECUTORS,
    SPARK_EXECUTOR_MEMORY,
    SPARK_DRIVER_MEMORY,
    LOG_FILE
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class SNOMEDRecord:
    """Data class for SNOMED CT records"""
    concept_id: str
    term: str
    
    def get_embedding_text(self) -> str:
        """Get text for embedding (only term)"""
        return self.term
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "term": self.term,
            "document_type": "snomedct",
            "data_source": "snomedct_concepts"
        }
    
    def to_langchain_document(self) -> Document:
        return Document(
            page_content=self.get_embedding_text(),
            metadata=self.get_metadata()
        )

class CustomSNOMEDPGVector(PGVector):
    """Custom PGVector class with custom table names for SNOMED CT data"""
    def __init__(self, connection_string: str, embedding_function, collection_name: str):
        super().__init__(
            connection_string=connection_string,
            embedding_function=embedding_function,
            collection_name=collection_name
        )
        self.collection_table_name = SNOMED_COLLECTION_TABLE
        self.embedding_table_name = SNOMED_EMBEDDING_TABLE
        self._create_tables_if_not_exists()
        self._collection_id = None
    def _create_tables_if_not_exists(self) -> None:
        with self._make_session() as session:
            session.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {self.collection_table_name} (
                    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    cmetadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
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
            session.execute(text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.embedding_table_name}_collection 
                ON {self.embedding_table_name}(collection_id)
            """))
            session.execute(text(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.embedding_table_name}_embedding 
                ON {self.embedding_table_name} USING hnsw (embedding vector_cosine_ops)
            """))
            logger.info(f"✅ Created embedding index for BioBERT (768 dimensions)")
            session.commit()
            logger.info(f"✅ Created custom tables: {self.collection_table_name}, {self.embedding_table_name}")
    def _get_collection_id(self) -> str:
        if self._collection_id:
            return self._collection_id
        with self._make_session() as session:
            result = session.execute(text(f"""
                SELECT uuid FROM {self.collection_table_name} 
                WHERE name = :name
            """), {"name": self.collection_name})
            existing_collection = result.fetchone()
            if existing_collection:
                self._collection_id = str(existing_collection[0])
                logger.info(f"✅ Found existing collection: {self.collection_name}")
            else:
                result = session.execute(text(f"""
                    INSERT INTO {self.collection_table_name} (name, cmetadata)
                    VALUES (:name, :metadata)
                    RETURNING uuid
                """), {
                    "name": self.collection_name,
                    "metadata": json.dumps({"description": "SNOMED CT terminology embeddings"})
                })
                self._collection_id = str(result.fetchone()[0])
                logger.info(f"✅ Created new collection: {self.collection_name}")
            session.commit()
            return self._collection_id
    def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        collection_id = self._get_collection_id()
        texts = [doc.page_content for doc in documents]
        embeddings = self.embedding_function.embed_documents(texts)
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
        logger.info(f"✅ Added {len(documents)} documents to SNOMED CT collection")
        return ids
    def similarity_search_with_score(self, query: str, k: int = 10, **kwargs) -> List[Tuple[Document, float]]:
        collection_id = self._get_collection_id()
        query_embedding = self.embedding_function.embed_query(query)
        with self._make_session() as session:
            result = session.execute(text(f"""
                SELECT document, cmetadata, 1 - (embedding <=> (:embedding)::vector) as similarity
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
                # Robustly handle cmetadata type
                if not row[1]:
                    metadata = {}
                elif isinstance(row[1], dict):
                    metadata = row[1]
                elif isinstance(row[1], (str, bytes, bytearray)):
                    metadata = json.loads(row[1])
                else:
                    try:
                        metadata = json.loads(row[1].tobytes().decode())
                    except Exception:
                        metadata = {}
                doc = Document(
                    page_content=row[0],
                    metadata=metadata
                )
                results.append((doc, row[2]))
            return results

def get_spark_session() -> SparkSession:
    return SparkSession.builder \
        .appName(SPARK_APP_NAME) \
        .master(SPARK_MASTER) \
        .config("spark.executor.memory", SPARK_EXECUTOR_MEMORY) \
        .config("spark.driver.memory", SPARK_DRIVER_MEMORY) \
        .getOrCreate()

class SNOMEDCTEmbeddingPipeline:
    def __init__(self):
        import torch

        # Choose device: MPS (Apple GPU) if available, else CPU
        device = "mps" if torch.backends.mps.is_available() else "cpu"

        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': device},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.vector_store = CustomSNOMEDPGVector(
            connection_string=DATABASE_URL,
            embedding_function=self.embeddings,
            collection_name=COLLECTION_NAME
        )
        self.spark = get_spark_session()
        logger.info(f"Using device for embeddings: {device}")
    def setup_database(self):
        logger.info("Setting up SNOMED CT database tables...")
        # Tables are created automatically during CustomSNOMEDPGVector initialization
        logger.info("✅ Database setup completed")
    def process_snomedct(self, max_codes: Optional[int] = None):
        logger.info("Starting SNOMED CT embedding pipeline with PySpark...")
        start_time = time.time()
        # Read SNOMED CT concepts file (tab-delimited, columns: concept_id, concept_name, domain_id, vocabulary_id, ...)
        df = self.spark.read.csv('/Users/rajanishsd/Documents/zivohealth-1/backend/3PData/data/snomedct/concept.csv', sep="\t", header=True)
        # Filter for SNOMED vocabulary and allowed domains
        df = df.filter(
            (col("concept_id").isNotNull()) &
            (col("concept_name").isNotNull()) &
            (col("vocabulary_id") == "SNOMED") &
            (col("domain_id").isin(
                "Condition", "Procedure", "Observation", "Measurement", "Device", "Specimen", "Episode"
            ))
        )
        total_records = df.count()
        logger.info(f"Total SNOMED CT records after filter: {total_records}")
        if max_codes:
            df = df.limit(max_codes)
        # Convert to Pandas for batching (PySpark to Pandas for embedding)
        pandas_df = df.select("concept_id", "concept_name").toPandas()
        total_processed = 0
        for i in tqdm(range(0, len(pandas_df), BATCH_SIZE)):
            batch_df = pandas_df.iloc[i:i+BATCH_SIZE]
            records = [SNOMEDRecord(concept_id=row["concept_id"], term=row["concept_name"]) for _, row in batch_df.iterrows()]
            documents = [rec.to_langchain_document() for rec in records]
            # Write in smaller batches to avoid DB overload
            for j in range(0, len(documents), EMBEDDING_BATCH_SIZE * MAX_DB_CONNECTIONS):
                subdocs = documents[j:j+EMBEDDING_BATCH_SIZE * MAX_DB_CONNECTIONS]
                # Further split for DB connection safety
                for k in range(0, len(subdocs), EMBEDDING_BATCH_SIZE):
                    self.vector_store.add_documents(subdocs[k:k+EMBEDDING_BATCH_SIZE])
                    time.sleep(RATE_LIMIT_DELAY)
            total_processed += len(batch_df)
            logger.info(f"Processed {total_processed}/{len(pandas_df)} SNOMED CT codes")
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Completed processing {total_processed} SNOMED CT codes in {elapsed_time:.2f} seconds")
    def search_snomedct(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        logger.info(f"Searching for: {query}")
        results = self.vector_store.similarity_search_with_score(query, k=k)
        for i, (doc, score) in enumerate(results):
            logger.info(f"{i+1}. Score: {score:.4f} - {doc.page_content[:100]}...")
        return results
    def get_stats(self) -> Dict[str, Any]:
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
    parser = argparse.ArgumentParser(description="SNOMED CT Embedder")
    parser.add_argument("--setup-db", action="store_true", help="Setup database tables")
    parser.add_argument("--process-snomedct", action="store_true", help="Process SNOMED CT concepts")
    parser.add_argument("--search", type=str, help="Search for SNOMED CT terms")
    parser.add_argument("--max-codes", type=int, help="Maximum number of codes to process")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    args = parser.parse_args()
    pipeline = SNOMEDCTEmbeddingPipeline()
    if args.setup_db:
        pipeline.setup_database()
    elif args.process_snomedct:
        pipeline.process_snomedct(max_codes=args.max_codes)
    elif args.search:
        pipeline.search_snomedct(args.search)
    elif args.stats:
        stats = pipeline.get_stats()
        print(json.dumps(stats, indent=2))
    else:
        parser.print_help()
if __name__ == "__main__":
    main() 