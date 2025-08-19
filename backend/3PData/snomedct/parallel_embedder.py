#!/usr/bin/env python3
"""
Parallel SNOMED CT Embedder
==========================

This script processes SNOMED CT concepts in parallel using Python's ProcessPoolExecutor.
It batches the data, computes embeddings, and writes to the database in parallel processes.

Usage:
    python parallel_embedder.py
"""
import os
import sys
import time
import json
import logging
from pathlib import Path
from typing import List, Any, Tuple
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from sqlalchemy import create_engine, text
import uuid

# Import config and model
from config import (
    DATABASE_URL,
    EMBEDDING_MODEL,
    SNOMED_CONCEPTS_FILE,
    COLLECTION_NAME,
    SNOMED_COLLECTION_TABLE,
    SNOMED_EMBEDDING_TABLE,
    BATCH_SIZE,
    EMBEDDING_BATCH_SIZE,
    LOG_FILE
)

# LangChain imports
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain.docstore.document import Document

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

class SNOMEDRecord:
    def __init__(self, concept_id: str, term: str):
        self.concept_id = concept_id
        self.term = term
    def get_embedding_text(self) -> str:
        return self.term
    def get_metadata(self) -> dict:
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

def create_tables_once():
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {SNOMED_COLLECTION_TABLE} (
                uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                cmetadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {SNOMED_EMBEDDING_TABLE} (
                uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                collection_id UUID REFERENCES {SNOMED_COLLECTION_TABLE}(uuid),
                embedding VECTOR(768),
                document TEXT,
                cmetadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Add this block to create the HNSW index
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_{SNOMED_EMBEDDING_TABLE}_embedding
            ON {SNOMED_EMBEDDING_TABLE} USING hnsw (embedding vector_cosine_ops)
        """))

def embed_and_write(batch: List[dict]) -> int:
    """
    Embeds a batch of SNOMED records and writes them to the DB.
    This function is run in a separate process.
    """
    import torch
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    embeddings = HuggingFaceEmbeddings(
    model_name="/Users/rajanishsd/Documents/zivohealth-1/backend/model/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
    model_kwargs={'device': device},
    encode_kwargs={'normalize_embeddings': True}
)
    class CustomSNOMEDPGVector(PGVector):
        def __init__(self, connection_string, embedding_function, collection_name):
            super().__init__(
                connection_string=connection_string,
                embedding_function=embedding_function,
                collection_name=collection_name
            )
            self.collection_table_name = SNOMED_COLLECTION_TABLE
            self.embedding_table_name = SNOMED_EMBEDDING_TABLE
            self._collection_id = None

        def _create_tables_if_not_exists(self):
            # Only create if not exists
            from sqlalchemy import text
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
                session.commit()

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
    vector_store = CustomSNOMEDPGVector(
        connection_string=DATABASE_URL,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )
    records = [SNOMEDRecord(concept_id=row["concept_id"], term=row["concept_name"]) for row in batch]
    documents = [rec.to_langchain_document() for rec in records]
    vector_store.add_documents(documents)
    return len(documents)

def main():
    logger.info("Starting parallel SNOMED CT embedding pipeline...")
    start_time = time.time()
    # Create tables/types ONCE before starting pool
    create_tables_once()
    # Read CSV with pandas
    df = pd.read_csv(SNOMED_CONCEPTS_FILE, sep='\t')
    # Filter for SNOMED vocabulary and allowed domains
    df = df[(df["concept_id"].notnull()) &
            (df["concept_name"].notnull()) &
            (df["vocabulary_id"] == "SNOMED") &
            (df["domain_id"].isin([
                "Condition", "Procedure", "Observation", "Measurement", "Device", "Specimen", "Episode"
            ]))]
    logger.info(f"Total SNOMED CT records after filter: {len(df)}")
    # Batch the data
    batches = [df.iloc[i:i+BATCH_SIZE].to_dict(orient='records') for i in range(0, len(df), BATCH_SIZE)]
    logger.info(f"Processing {len(batches)} batches of size {BATCH_SIZE}")
    processed = 0
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(embed_and_write, batch) for batch in batches]
        for i, future in enumerate(tqdm(as_completed(futures), total=len(futures))):
            n = future.result()
            processed += n
            logger.info(f"✅ Batch {i+1}: Added {n} documents (Total processed: {processed})")
    elapsed_time = time.time() - start_time
    logger.info(f"✅ Completed processing {processed} SNOMED CT codes in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main() 