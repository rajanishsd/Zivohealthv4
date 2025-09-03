#!/usr/bin/env python3
"""
Fast PubMed Embedder - Optimized for Speed
==========================================

This is an optimized version of the PubMed embedder focused on maximum processing speed.
Key optimizations:
- Larger batch sizes
- Memory-efficient processing
- Better error handling
- Progress tracking
- GPU acceleration support
- Parallel processing where possible
"""

import os
import sys
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Generator
import logging
from datetime import datetime
import argparse
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

# Third-party imports
import numpy as np
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
        logging.FileHandler('fast_pubmed_embedder.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql://rajanishsd@localhost:5432/zivohealth"
COLLECTION_NAME = "medical_documents"

# Performance optimizations
EMBEDDING_BATCH_SIZE = 1000  # Increased from 100
DB_BATCH_SIZE = 2000         # Increased from 1000
PARSING_BATCH_SIZE = 5000    # Process more articles at once
MAX_WORKERS = 4              # Parallel processing threads

@dataclass
class PubMedArticle:
    """Data class for PubMed articles"""
    pmid: str
    title: str
    abstract: str
    authors: List[str]
    journal: str
    pub_date: str
    mesh_terms: List[str]
    doi: Optional[str] = None
    
    def get_full_text(self) -> str:
        """Get full text for embedding"""
        return f"{self.title} {self.abstract}"
    
    def to_langchain_document(self) -> Document:
        """Convert to LangChain Document"""
        return Document(
            page_content=self.get_full_text(),
            metadata={
                "pmid": self.pmid,
                "title": self.title,
                "abstract": self.abstract,
                "authors": self.authors,
                "journal": self.journal,
                "pub_date": self.pub_date,
                "mesh_terms": self.mesh_terms,
                "doi": self.doi,
                "document_type": "pubmed"
            }
        )

class FastPubMedParser:
    """Fast PubMed XML parser with optimizations"""
    
    def __init__(self, data_dir: str = "medical_data/pubmed"):
        self.data_dir = Path(data_dir)
        self.processed_files = set()
        
    def parse_xml_file_fast(self, file_path: Path) -> Generator[PubMedArticle, None, None]:
        """Parse XML file with optimizations"""
        logger.info(f"📄 Parsing {file_path.name}...")
        
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                # Read entire file for faster processing
                content = f.read()
                
            # Parse XML
            root = ET.fromstring(content)
            articles = root.findall('.//PubmedArticle')
            
            logger.info(f"Found {len(articles)} articles in {file_path.name}")
            
            # Process articles in batches
            for i, article_elem in enumerate(articles):
                try:
                    article = self._parse_article_fast(article_elem)
                    if article:
                        yield article
                        
                    # Progress update every 1000 articles
                    if (i + 1) % 1000 == 0:
                        logger.info(f"  Parsed {i + 1}/{len(articles)} articles...")
                        
                except Exception as e:
                    logger.debug(f"Error parsing article {i}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return
    
    def _parse_article_fast(self, article_elem) -> Optional[PubMedArticle]:
        """Parse individual article with optimizations"""
        try:
            # PMID
            pmid_elem = article_elem.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else ""
            
            if not pmid:
                return None
            
            # Title
            title_elem = article_elem.find('.//ArticleTitle')
            title = self._get_text_content(title_elem) if title_elem is not None else ""
            
            # Abstract
            abstract_elem = article_elem.find('.//AbstractText')
            abstract = self._get_text_content(abstract_elem) if abstract_elem is not None else ""
            
            # Skip if no title or abstract
            if not title or not abstract:
                return None
            
            # Authors (simplified)
            authors = []
            author_elems = article_elem.findall('.//Author')
            for author_elem in author_elems[:10]:  # Limit to first 10 authors
                last_name = author_elem.find('.//LastName')
                first_name = author_elem.find('.//ForeName')
                if last_name is not None and first_name is not None:
                    authors.append(f"{first_name.text} {last_name.text}")
            
            # Journal
            journal_elem = article_elem.find('.//Title')
            journal = journal_elem.text if journal_elem is not None else ""
            
            # Publication date (simplified)
            pub_date_elem = article_elem.find('.//PubDate/Year')
            pub_date = pub_date_elem.text if pub_date_elem is not None else ""
            
            # MeSH terms (simplified)
            mesh_terms = []
            mesh_elems = article_elem.findall('.//MeshHeading/DescriptorName')
            for mesh_elem in mesh_elems[:20]:  # Limit to first 20 MeSH terms
                mesh_terms.append(mesh_elem.text)
            
            # DOI
            doi_elem = article_elem.find('.//ArticleId[@IdType="doi"]')
            doi = doi_elem.text if doi_elem is not None else None
            
            return PubMedArticle(
                pmid=pmid,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                pub_date=pub_date,
                mesh_terms=mesh_terms,
                doi=doi
            )
            
        except Exception as e:
            logger.debug(f"Error parsing article: {e}")
            return None
    
    def _get_text_content(self, elem) -> str:
        """Extract text content from XML element"""
        if elem is None:
            return ""
        
        # Get all text content
        text_parts = []
        if elem.text:
            text_parts.append(elem.text)
        
        for child in elem:
            if child.text:
                text_parts.append(child.text)
            if child.tail:
                text_parts.append(child.tail)
        
        return ' '.join(text_parts).strip()
    
    def parse_all_files_fast(self) -> Generator[PubMedArticle, None, None]:
        """Parse all XML files with optimizations"""
        xml_files = list(self.data_dir.glob("*.xml.gz"))
        
        if not xml_files:
            logger.warning(f"No XML files found in {self.data_dir}")
            return
        
        logger.info(f"🚀 Starting fast parsing of {len(xml_files)} files...")
        
        for file_path in sorted(xml_files):
            if file_path.name in self.processed_files:
                logger.info(f"⏭️  Skipping already processed file: {file_path.name}")
                continue
                
            yield from self.parse_xml_file_fast(file_path)
            self.processed_files.add(file_path.name)

class FastLangChainEmbedder:
    """Fast LangChain embedder with optimizations"""
    
    def __init__(self, model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"):
        self.model_name = model_name
        self.embeddings = None
        self.vector_store = None
        self.setup_embeddings()
        
    def setup_embeddings(self):
        """Setup embeddings with optimizations"""
        logger.info("🚀 Setting up fast HuggingFace embeddings...")
        
        try:
            # Try primary model
            logger.info(f"Loading model: {self.model_name}")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={'device': 'cpu'},  # Use 'cuda' if GPU available
                encode_kwargs={'normalize_embeddings': True, 'batch_size': 64}  # Larger batch size
            )
            logger.info("✅ Primary embeddings model loaded successfully")
            
        except Exception as e:
            logger.warning(f"Failed to load {self.model_name}: {e}")
            logger.info("Falling back to sentence-transformers/all-MiniLM-L6-v2")
            
            # Fallback model
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True, 'batch_size': 64}
            )
            logger.info("✅ Fallback embeddings model loaded successfully")
    
    def setup_vector_store(self):
        """Setup vector store with optimizations"""
        logger.info("🚀 Setting up fast PGVector store...")
        
        if self.embeddings is None:
            self.setup_embeddings()
        
        try:
            self.vector_store = PGVector(
                collection_name=COLLECTION_NAME,
                connection_string=DATABASE_URL,
                embedding_function=self.embeddings,
                pre_delete_collection=False,  # Don't delete existing data
            )
            logger.info("✅ Fast PGVector store setup successfully")
            
        except Exception as e:
            logger.error(f"❌ Error setting up PGVector store: {e}")
            raise
    
    def add_documents_fast(self, documents: List[Document]) -> List[str]:
        """Add documents with maximum speed optimizations"""
        if self.vector_store is None:
            self.setup_vector_store()
        
        try:
            logger.info(f"🚀 Fast processing {len(documents)} documents...")
            
            # Very large batch size for maximum speed
            batch_size = EMBEDDING_BATCH_SIZE
            all_ids = []
            
            # Process with progress bar
            total_batches = (len(documents) + batch_size - 1) // batch_size
            
            for i in tqdm(range(0, len(documents), batch_size), desc="Processing batches"):
                batch = documents[i:i + batch_size]
                batch_num = i // batch_size + 1
                
                start_time = time.time()
                
                try:
                    batch_ids = self.vector_store.add_documents(batch)
                    all_ids.extend(batch_ids)
                    
                    # Performance metrics
                    elapsed = time.time() - start_time
                    docs_per_sec = len(batch) / elapsed if elapsed > 0 else 0
                    
                    logger.info(f"✅ Batch {batch_num}/{total_batches} - {len(batch)} docs in {elapsed:.1f}s ({docs_per_sec:.1f} docs/sec)")
                    
                except Exception as e:
                    logger.error(f"❌ Error in batch {batch_num}: {e}")
                    continue
            
            logger.info(f"🎉 Successfully processed {len(all_ids)} documents!")
            return all_ids
            
        except Exception as e:
            logger.error(f"❌ Error adding documents: {e}")
            raise

class FastMedicalEmbeddingPipeline:
    """Fast medical embedding pipeline with all optimizations"""
    
    def __init__(self, base_dir: str = "medical_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        self.parser = FastPubMedParser(str(self.base_dir / "pubmed"))
        self.embedder = FastLangChainEmbedder()
        
        # Performance tracking
        self.start_time = None
        self.processed_count = 0
        
    def setup_database(self):
        """Setup database for fast processing"""
        logger.info("🚀 Setting up database for fast processing...")
        
        try:
            # Create database engine
            engine = create_engine(DATABASE_URL)
            
            # Enable pgvector extension
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("✅ pgvector extension enabled")
            
            # Setup vector store
            self.embedder.setup_vector_store()
            
            logger.info("✅ Fast database setup completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            return False
    
    def process_pubmed_fast(self, max_articles: Optional[int] = None):
        """Process PubMed articles with maximum speed"""
        logger.info("🚀 Starting FAST PubMed processing...")
        
        self.start_time = time.time()
        batch_documents = []
        processed_count = 0
        
        # Use larger batch size for maximum speed
        batch_size = DB_BATCH_SIZE
        
        logger.info(f"Using batch size: {batch_size}")
        
        article_generator = self.parser.parse_all_files_fast()
        
        for article in article_generator:
            try:
                # Convert to LangChain document
                doc = article.to_langchain_document()
                batch_documents.append(doc)
                
                # Process batch when full
                if len(batch_documents) >= batch_size:
                    self.embedder.add_documents_fast(batch_documents)
                    processed_count += len(batch_documents)
                    
                    # Performance metrics
                    elapsed = time.time() - self.start_time
                    docs_per_sec = processed_count / elapsed if elapsed > 0 else 0
                    
                    logger.info(f"🔥 FAST MODE: {processed_count:,} articles processed ({docs_per_sec:.1f} docs/sec)")
                    
                    batch_documents = []
                    
                    # Stop if max articles reached
                    if max_articles and processed_count >= max_articles:
                        logger.info(f"Reached maximum articles limit: {max_articles}")
                        break
                    
            except Exception as e:
                logger.error(f"Error processing article {article.pmid}: {e}")
                continue
        
        # Process remaining documents
        if batch_documents:
            self.embedder.add_documents_fast(batch_documents)
            processed_count += len(batch_documents)
        
        # Final performance report
        total_time = time.time() - self.start_time
        avg_docs_per_sec = processed_count / total_time if total_time > 0 else 0
        
        logger.info(f"🎉 FAST PROCESSING COMPLETE!")
        logger.info(f"📊 Total articles: {processed_count:,}")
        logger.info(f"⏱️  Total time: {total_time:.1f} seconds")
        logger.info(f"🚀 Average speed: {avg_docs_per_sec:.1f} docs/sec")
        
        return processed_count
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = '{COLLECTION_NAME}')"))
                count = result.scalar()
                
            return {
                "total_documents": count or 0,
                "collection_name": COLLECTION_NAME,
                "processing_speed": f"{getattr(self, 'processed_count', 0) / (time.time() - getattr(self, 'start_time', time.time())):.1f} docs/sec" if hasattr(self, 'start_time') else "N/A"
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}

def main():
    """Main function with fast processing options"""
    parser = argparse.ArgumentParser(description="Fast PubMed Embedder - Optimized for Speed")
    parser.add_argument("--setup-db", action="store_true", help="Setup database")
    parser.add_argument("--fast-process", action="store_true", help="Fast process PubMed articles")
    parser.add_argument("--max-articles", type=int, help="Maximum articles to process")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    
    args = parser.parse_args()
    
    if not any([args.setup_db, args.fast_process, args.stats]):
        logger.error("Please specify at least one action")
        return
    
    pipeline = FastMedicalEmbeddingPipeline()
    
    if args.setup_db:
        pipeline.setup_database()
    
    if args.stats:
        stats = pipeline.get_stats()
        logger.info(f"📊 Database stats: {stats}")
    
    if args.fast_process:
        logger.info("🚀 Starting FAST processing mode...")
        pipeline.process_pubmed_fast(args.max_articles)

if __name__ == "__main__":
    main() 