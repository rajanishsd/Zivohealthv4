#!/usr/bin/env python3
"""
PubMed and PMC Database Embedder - LangChain + PGVector
======================================================

This script downloads, parses, and embeds PubMed and PMC databases using LangChain.
- Downloads PubMed baseline files (abstracts + metadata)
- Downloads PMC Open Access full-text articles
- Parses XML files to extract relevant text
- Generates embeddings using LangChain HuggingFace BioBERT
- Stores documents and embeddings in PostgreSQL with PGVector

Usage:
    python pubmed_pmc_embedder.py --download --parse --embed
    python pubmed_pmc_embedder.py --parse-only
    python pubmed_pmc_embedder.py --embed-only
"""

import os
import sys
import gzip
import tarfile
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Generator
import logging
from datetime import datetime
import argparse
import json
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from urllib.parse import urljoin
from ftplib import FTP
import re

# Third-party imports
import numpy as np
from tqdm import tqdm
import pandas as pd

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
        logging.FileHandler('pubmed_pmc_embedder.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql://rajanishsd@localhost:5433/zivohealth"
COLLECTION_NAME = "medical_documents"

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

@dataclass
class PMCArticle:
    """Data class for PMC articles"""
    pmc_id: str
    pmid: Optional[str]
    title: str
    abstract: str
    full_text: str
    authors: List[str]
    journal: str
    pub_date: str
    doi: Optional[str] = None
    
    def get_full_text(self) -> str:
        """Get full text for embedding"""
        return f"{self.title} {self.abstract} {self.full_text}"
    
    def to_langchain_document(self) -> Document:
        """Convert to LangChain Document"""
        return Document(
            page_content=self.get_full_text(),
            metadata={
                "pmc_id": self.pmc_id,
                "pmid": self.pmid,
                "title": self.title,
                "abstract": self.abstract,
                "full_text": self.full_text[:1000],  # Truncate for metadata
                "authors": self.authors,
                "journal": self.journal,
                "pub_date": self.pub_date,
                "doi": self.doi,
                "document_type": "pmc"
            }
        )

class PubMedDownloader:
    """Download PubMed baseline files"""
    
    def __init__(self, base_dir: str = "pubmed_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.ftp_server = "ftp.ncbi.nlm.nih.gov"
        self.baseline_path = "/pubmed/baseline/"
        self.update_path = "/pubmed/updatefiles/"
        
    def get_file_list(self, path: str) -> List[str]:
        """Get list of files from FTP server"""
        logger.info(f"Connecting to {self.ftp_server} to get file list from {path}")
        
        with FTP(self.ftp_server) as ftp:
            ftp.login()
            files = []
            ftp.cwd(path)
            file_list = ftp.nlst()
            
            for file in file_list:
                if file.endswith('.xml.gz'):
                    files.append(file)
                    
        logger.info(f"Found {len(files)} XML files")
        return sorted(files)
    
    def download_file(self, remote_path: str, filename: str) -> bool:
        """Download a single file"""
        local_path = self.base_dir / filename
        
        if local_path.exists():
            logger.info(f"File {filename} already exists, skipping")
            return True
            
        try:
            with FTP(self.ftp_server) as ftp:
                ftp.login()
                ftp.cwd(remote_path)
                
                with open(local_path, 'wb') as local_file:
                    ftp.retrbinary(f'RETR {filename}', local_file.write)
                    
            logger.info(f"Downloaded {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            return False
    
    def download_baseline_files(self, max_files: Optional[int] = None) -> List[str]:
        """Download PubMed baseline files"""
        logger.info("Starting PubMed baseline download")
        
        files = self.get_file_list(self.baseline_path)
        if max_files:
            files = files[:max_files]
            
        successful_downloads = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_file = {
                executor.submit(self.download_file, self.baseline_path, file): file 
                for file in files
            }
            
            for future in tqdm(as_completed(future_to_file), total=len(files), desc="Downloading PubMed files"):
                file = future_to_file[future]
                try:
                    if future.result():
                        successful_downloads.append(file)
                except Exception as e:
                    logger.error(f"Error downloading {file}: {e}")
                    
        logger.info(f"Successfully downloaded {len(successful_downloads)} files")
        return successful_downloads

class PMCDownloader:
    """Download PMC Open Access files"""
    
    def __init__(self, base_dir: str = "pmc_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.ftp_server = "ftp.ncbi.nlm.nih.gov"
        self.oa_path = "/pub/pmc/oa_bulk/"
        
    def get_file_list(self) -> List[str]:
        """Get list of PMC OA files"""
        logger.info(f"Connecting to {self.ftp_server} to get PMC OA file list")
        
        with FTP(self.ftp_server) as ftp:
            ftp.login()
            files = []
            ftp.cwd(self.oa_path)
            file_list = ftp.nlst()
            
            for file in file_list:
                if file.endswith('.tar.gz') and ('comm_use' in file or 'non_comm_use' in file):
                    files.append(file)
                    
        logger.info(f"Found {len(files)} PMC OA archive files")
        return sorted(files)
    
    def download_file(self, filename: str) -> bool:
        """Download a single PMC archive file"""
        local_path = self.base_dir / filename
        
        if local_path.exists():
            logger.info(f"File {filename} already exists, skipping")
            return True
            
        try:
            with FTP(self.ftp_server) as ftp:
                ftp.login()
                ftp.cwd(self.oa_path)
                
                with open(local_path, 'wb') as local_file:
                    ftp.retrbinary(f'RETR {filename}', local_file.write)
                    
            logger.info(f"Downloaded {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            return False
    
    def download_oa_files(self, max_files: Optional[int] = None) -> List[str]:
        """Download PMC Open Access files"""
        logger.info("Starting PMC OA download")
        
        files = self.get_file_list()
        if max_files:
            files = files[:max_files]
            
        successful_downloads = []
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_file = {
                executor.submit(self.download_file, file): file 
                for file in files
            }
            
            for future in tqdm(as_completed(future_to_file), total=len(files), desc="Downloading PMC files"):
                file = future_to_file[future]
                try:
                    if future.result():
                        successful_downloads.append(file)
                except Exception as e:
                    logger.error(f"Error downloading {file}: {e}")
                    
        logger.info(f"Successfully downloaded {len(successful_downloads)} PMC files")
        return successful_downloads

class PubMedParser:
    """Parse PubMed XML files"""
    
    def __init__(self, data_dir: str = "pubmed_data"):
        self.data_dir = Path(data_dir)
        
    def parse_xml_file(self, file_path: Path) -> Generator[PubMedArticle, None, None]:
        """Parse a single PubMed XML file"""
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                content = f.read()
                
            root = ET.fromstring(content)
            
            for article in root.findall('.//PubmedArticle'):
                try:
                    yield self._parse_article(article)
                except Exception as e:
                    logger.warning(f"Error parsing article in {file_path}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
    
    def _parse_article(self, article_elem) -> PubMedArticle:
        """Parse a single PubMed article element"""
        # Extract PMID
        pmid_elem = article_elem.find('.//PMID')
        pmid = pmid_elem.text if pmid_elem is not None else ""
        
        # Extract title
        title_elem = article_elem.find('.//ArticleTitle')
        title = title_elem.text if title_elem is not None else ""
        
        # Extract abstract
        abstract_parts = []
        for abstract_elem in article_elem.findall('.//AbstractText'):
            if abstract_elem.text:
                abstract_parts.append(abstract_elem.text)
        abstract = " ".join(abstract_parts)
        
        # Extract authors
        authors = []
        for author_elem in article_elem.findall('.//Author'):
            lastname = author_elem.find('.//LastName')
            firstname = author_elem.find('.//ForeName')
            if lastname is not None and firstname is not None:
                authors.append(f"{firstname.text} {lastname.text}")
        
        # Extract journal
        journal_elem = article_elem.find('.//Journal/Title')
        journal = journal_elem.text if journal_elem is not None else ""
        
        # Extract publication date
        pub_date_elem = article_elem.find('.//PubDate')
        pub_date = ""
        if pub_date_elem is not None:
            year = pub_date_elem.find('Year')
            month = pub_date_elem.find('Month')
            day = pub_date_elem.find('Day')
            date_parts = []
            if year is not None: date_parts.append(year.text)
            if month is not None: date_parts.append(month.text)
            if day is not None: date_parts.append(day.text)
            pub_date = "-".join(date_parts)
        
        # Extract MeSH terms
        mesh_terms = []
        for mesh_elem in article_elem.findall('.//MeshHeading/DescriptorName'):
            if mesh_elem.text:
                mesh_terms.append(mesh_elem.text)
        
        # Extract DOI
        doi = None
        for article_id in article_elem.findall('.//ArticleId'):
            if article_id.get('IdType') == 'doi':
                doi = article_id.text
                break
        
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
    
    def parse_all_files(self) -> Generator[PubMedArticle, None, None]:
        """Parse all PubMed XML files in the data directory"""
        xml_files = list(self.data_dir.glob("*.xml.gz"))
        logger.info(f"Found {len(xml_files)} PubMed XML files to parse")
        
        for xml_file in tqdm(xml_files, desc="Parsing PubMed files"):
            yield from self.parse_xml_file(xml_file)

class PMCParser:
    """Parse PMC XML files"""
    
    def __init__(self, data_dir: str = "pmc_data"):
        self.data_dir = Path(data_dir)
        
    def extract_and_parse_archives(self) -> Generator[PMCArticle, None, None]:
        """Extract and parse all PMC archive files"""
        archive_files = list(self.data_dir.glob("*.tar.gz"))
        logger.info(f"Found {len(archive_files)} PMC archive files to process")
        
        for archive_file in tqdm(archive_files, desc="Processing PMC archives"):
            yield from self._process_archive(archive_file)
    
    def _process_archive(self, archive_path: Path) -> Generator[PMCArticle, None, None]:
        """Process a single PMC archive file"""
        try:
            with tarfile.open(archive_path, 'r:gz') as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith('.xml'):
                        try:
                            xml_file = tar.extractfile(member)
                            if xml_file:
                                content = xml_file.read().decode('utf-8')
                                article = self._parse_pmc_xml(content)
                                if article:
                                    yield article
                        except Exception as e:
                            logger.warning(f"Error parsing {member.name}: {e}")
                            continue
        except Exception as e:
            logger.error(f"Error processing archive {archive_path}: {e}")
    
    def _parse_pmc_xml(self, xml_content: str) -> Optional[PMCArticle]:
        """Parse PMC XML content"""
        try:
            root = ET.fromstring(xml_content)
            
            # Extract PMC ID
            pmc_id_elem = root.find('.//article-id[@pub-id-type="pmc"]')
            pmc_id = pmc_id_elem.text if pmc_id_elem is not None else ""
            
            # Extract PMID
            pmid_elem = root.find('.//article-id[@pub-id-type="pmid"]')
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            # Extract title
            title_elem = root.find('.//article-title')
            title = self._extract_text_content(title_elem) if title_elem is not None else ""
            
            # Extract abstract
            abstract_elem = root.find('.//abstract')
            abstract = self._extract_text_content(abstract_elem) if abstract_elem is not None else ""
            
            # Extract full text body
            body_elem = root.find('.//body')
            full_text = self._extract_text_content(body_elem) if body_elem is not None else ""
            
            # Extract authors
            authors = []
            for contrib in root.findall('.//contrib[@contrib-type="author"]'):
                given_names = contrib.find('.//given-names')
                surname = contrib.find('.//surname')
                if given_names is not None and surname is not None:
                    authors.append(f"{given_names.text} {surname.text}")
            
            # Extract journal
            journal_elem = root.find('.//journal-title')
            journal = journal_elem.text if journal_elem is not None else ""
            
            # Extract publication date
            pub_date_elem = root.find('.//pub-date[@pub-type="epub"]') or root.find('.//pub-date')
            pub_date = ""
            if pub_date_elem is not None:
                year = pub_date_elem.find('year')
                month = pub_date_elem.find('month')
                day = pub_date_elem.find('day')
                date_parts = []
                if year is not None: date_parts.append(year.text)
                if month is not None: date_parts.append(month.text)
                if day is not None: date_parts.append(day.text)
                pub_date = "-".join(date_parts)
            
            # Extract DOI
            doi_elem = root.find('.//article-id[@pub-id-type="doi"]')
            doi = doi_elem.text if doi_elem is not None else None
            
            return PMCArticle(
                pmc_id=pmc_id,
                pmid=pmid,
                title=title,
                abstract=abstract,
                full_text=full_text,
                authors=authors,
                journal=journal,
                pub_date=pub_date,
                doi=doi
            )
            
        except Exception as e:
            logger.warning(f"Error parsing PMC XML: {e}")
            return None
    
    def _extract_text_content(self, elem) -> str:
        """Extract all text content from an XML element"""
        if elem is None:
            return ""
        
        text_parts = []
        if elem.text:
            text_parts.append(elem.text)
        
        for child in elem:
            text_parts.append(self._extract_text_content(child))
            if child.tail:
                text_parts.append(child.tail)
        
        return " ".join(text_parts).strip()

class LangChainBioBERTEmbedder:
    """LangChain-based BioBERT embedder with PGVector storage"""
    
    def __init__(self, model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"):
        self.model_name = model_name
        self.embeddings = None
        self.vector_store = None
        
    def setup_embeddings(self):
        """Setup HuggingFace embeddings"""
        logger.info(f"Setting up HuggingFace embeddings with model: {self.model_name}")
        
        try:
            # Try with trust_remote_code=True for better compatibility
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={
                    'device': 'cpu',
                    'trust_remote_code': True
                },
                encode_kwargs={'normalize_embeddings': True}
            )
            logger.info("✅ Embeddings model loaded successfully")
            
        except Exception as e:
            logger.warning(f"Failed to load {self.model_name}: {e}")
            logger.info("Falling back to sentence-transformers/all-MiniLM-L6-v2")
            
            # Fallback to a model that works with safetensors
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            logger.info("✅ Fallback embeddings model loaded successfully")
    
    def setup_vector_store(self):
        """Setup PGVector store"""
        logger.info("Setting up PGVector store...")
        
        if self.embeddings is None:
            self.setup_embeddings()
        
        try:
            self.vector_store = PGVector(
                collection_name=COLLECTION_NAME,
                connection_string=DATABASE_URL,
                embedding_function=self.embeddings,
            )
            logger.info("✅ PGVector store setup successfully")
            
        except Exception as e:
            logger.error(f"❌ Error setting up PGVector store: {e}")
            raise
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to the vector store"""
        if self.vector_store is None:
            self.setup_vector_store()
        
        try:
            logger.info(f"Adding {len(documents)} documents to vector store...")
            
            # Add documents in batches to avoid memory issues
            batch_size = 100
            all_ids = []
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                batch_ids = self.vector_store.add_documents(batch)
                all_ids.extend(batch_ids)
                
                logger.info(f"Added batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")
            
            logger.info(f"✅ Successfully added {len(documents)} documents")
            return all_ids
            
        except Exception as e:
            logger.error(f"❌ Error adding documents: {e}")
            raise
    
    def search_similar_documents(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        """Search for similar documents"""
        if self.vector_store is None:
            self.setup_vector_store()
        
        try:
            logger.info(f"Searching for similar documents to: '{query[:50]}...'")
            
            results = self.vector_store.similarity_search_with_score(query, k=k)
            
            logger.info(f"Found {len(results)} similar documents")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error searching documents: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get vector store statistics"""
        if self.vector_store is None:
            try:
                self.setup_vector_store()
            except Exception as e:
                return {"error": f"Could not initialize vector store: {e}"}
        
        try:
            # Connect to database directly to get stats
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = '{COLLECTION_NAME}')"))
                count = result.scalar()
                
            return {
                "total_documents": count or 0,
                "collection_name": COLLECTION_NAME,
                "model_name": self.model_name
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}

class MedicalEmbeddingPipeline:
    """Main pipeline for processing medical literature with LangChain"""
    
    def __init__(self, base_dir: str = "medical_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        self.pubmed_downloader = PubMedDownloader(str(self.base_dir / "pubmed"))
        self.pmc_downloader = PMCDownloader(str(self.base_dir / "pmc"))
        self.pubmed_parser = PubMedParser(str(self.base_dir / "pubmed"))
        self.pmc_parser = PMCParser(str(self.base_dir / "pmc"))
        self.embedder = LangChainBioBERTEmbedder()
        
    def setup_database(self):
        """Setup database for LangChain PGVector"""
        logger.info("Setting up database for LangChain PGVector...")
        
        try:
            # Create database engine
            engine = create_engine(DATABASE_URL)
            
            # Enable pgvector extension
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("✅ pgvector extension enabled")
            
            # Setup vector store (this will create tables)
            self.embedder.setup_vector_store()
            
            logger.info("✅ Database setup completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            return False
    
    def download_data(self, max_pubmed_files: Optional[int] = None, max_pmc_files: Optional[int] = None):
        """Download PubMed and PMC data"""
        logger.info("Starting data download phase")
        
        # Download PubMed baseline files
        pubmed_files = self.pubmed_downloader.download_baseline_files(max_pubmed_files)
        logger.info(f"Downloaded {len(pubmed_files)} PubMed files")
        
        # Download PMC Open Access files
        pmc_files = self.pmc_downloader.download_oa_files(max_pmc_files)
        logger.info(f"Downloaded {len(pmc_files)} PMC files")
        
        return pubmed_files, pmc_files
    
    def process_pubmed_to_database(self, batch_size: int = 1000):
        """Process PubMed articles and store in vector database"""
        logger.info("Starting PubMed processing to vector database")
        
        batch_documents = []
        processed_count = 0
        
        for article in self.pubmed_parser.parse_all_files():
            try:
                # Convert to LangChain document
                doc = article.to_langchain_document()
                batch_documents.append(doc)
                
                # Process batch when full
                if len(batch_documents) >= batch_size:
                    self.embedder.add_documents(batch_documents)
                    processed_count += len(batch_documents)
                    logger.info(f"Processed {processed_count} PubMed articles")
                    batch_documents = []
                    
            except Exception as e:
                logger.error(f"Error processing PubMed article {article.pmid}: {e}")
                continue
        
        # Process remaining documents
        if batch_documents:
            self.embedder.add_documents(batch_documents)
            processed_count += len(batch_documents)
        
        logger.info(f"✅ Completed PubMed processing: {processed_count} articles")
    
    def process_pmc_to_database(self, batch_size: int = 500):
        """Process PMC articles and store in vector database"""
        logger.info("Starting PMC processing to vector database")
        
        batch_documents = []
        processed_count = 0
        
        for article in self.pmc_parser.extract_and_parse_archives():
            try:
                # Convert to LangChain document
                doc = article.to_langchain_document()
                batch_documents.append(doc)
                
                # Process batch when full
                if len(batch_documents) >= batch_size:
                    self.embedder.add_documents(batch_documents)
                    processed_count += len(batch_documents)
                    logger.info(f"Processed {processed_count} PMC articles")
                    batch_documents = []
                    
            except Exception as e:
                logger.error(f"Error processing PMC article {article.pmc_id}: {e}")
                continue
        
        # Process remaining documents
        if batch_documents:
            self.embedder.add_documents(batch_documents)
            processed_count += len(batch_documents)
        
        logger.info(f"✅ Completed PMC processing: {processed_count} articles")
    
    def search_documents(self, query: str, k: int = 10):
        """Search for similar documents"""
        return self.embedder.search_similar_documents(query, k)
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        return self.embedder.get_stats()
    
    def run_full_pipeline(self, max_pubmed_files: Optional[int] = None, max_pmc_files: Optional[int] = None):
        """Run the complete pipeline"""
        logger.info("Starting full medical literature embedding pipeline with LangChain")
        
        # Setup database
        if not self.setup_database():
            logger.error("❌ Database setup failed - aborting pipeline")
            return
        
        # Download data
        self.download_data(max_pubmed_files, max_pmc_files)
        
        # Process PubMed to database
        self.process_pubmed_to_database()
        
        # Process PMC to database
        self.process_pmc_to_database()
        
        # Show final stats
        stats = self.get_database_stats()
        logger.info(f"📊 Final database stats: {stats}")
        
        logger.info("✅ Pipeline completed successfully - all documents stored in PGVector")

def main():
    parser = argparse.ArgumentParser(description="PubMed and PMC Database Embedder with LangChain")
    parser.add_argument("--download", action="store_true", help="Download databases")
    parser.add_argument("--parse", action="store_true", help="Parse XML files")
    parser.add_argument("--embed", action="store_true", help="Generate embeddings")
    parser.add_argument("--full-pipeline", action="store_true", help="Run complete pipeline")
    parser.add_argument("--setup-db", action="store_true", help="Setup database tables")
    parser.add_argument("--max-pubmed-files", type=int, help="Maximum PubMed files to download")
    parser.add_argument("--max-pmc-files", type=int, help="Maximum PMC files to download")
    parser.add_argument("--base-dir", default="medical_data", help="Base directory for data")
    parser.add_argument("--search", type=str, help="Search for similar documents")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    
    args = parser.parse_args()
    
    if not any([args.download, args.parse, args.embed, args.full_pipeline, args.setup_db, args.search, args.stats]):
        logger.error("Please specify at least one action")
        return
    
    pipeline = MedicalEmbeddingPipeline(args.base_dir)
    
    if args.setup_db:
        pipeline.setup_database()
    
    if args.stats:
        stats = pipeline.get_database_stats()
        logger.info(f"📊 Database stats: {stats}")
    
    if args.search:
        results = pipeline.search_documents(args.search, k=10)
        logger.info(f"🔍 Search results for '{args.search}':")
        for i, (doc, score) in enumerate(results, 1):
            logger.info(f"\n{i}. {doc.metadata.get('title', 'No title')} (score: {score:.4f})")
            logger.info(f"   Journal: {doc.metadata.get('journal', 'Unknown')}")
            logger.info(f"   Type: {doc.metadata.get('document_type', 'Unknown')}")
            
            # Extract and print full abstract
            abstract = doc.metadata.get('abstract', '')
            if abstract:
                logger.info(f"   Abstract: {abstract}")
            else:
                logger.info(f"   Abstract: No abstract available")
            
            # Add additional metadata for different document types
            if doc.metadata.get('document_type') == 'pubmed':
                pmid = doc.metadata.get('pmid', 'Unknown')
                logger.info(f"   PMID: {pmid}")
                authors = doc.metadata.get('authors', [])
                if authors:
                    logger.info(f"   Authors: {', '.join(authors[:3])}{'...' if len(authors) > 3 else ''}")
                mesh_terms = doc.metadata.get('mesh_terms', [])
                if mesh_terms:
                    logger.info(f"   MeSH Terms: {', '.join(mesh_terms[:5])}{'...' if len(mesh_terms) > 5 else ''}")
            elif doc.metadata.get('document_type') == 'pmc':
                pmc_id = doc.metadata.get('pmc_id', 'Unknown')
                pmid = doc.metadata.get('pmid', 'Unknown')
                logger.info(f"   PMC ID: {pmc_id}")
                if pmid:
                    logger.info(f"   PMID: {pmid}")
                authors = doc.metadata.get('authors', [])
                if authors:
                    logger.info(f"   Authors: {', '.join(authors[:3])}{'...' if len(authors) > 3 else ''}")
            
            # Add publication date and DOI if available
            pub_date = doc.metadata.get('pub_date', '')
            if pub_date:
                logger.info(f"   Publication Date: {pub_date}")
            
            doi = doc.metadata.get('doi', '')
            if doi:
                logger.info(f"   DOI: {doi}")
            
            logger.info("-" * 80)  # Separator between results
    
    if args.full_pipeline:
        pipeline.run_full_pipeline(args.max_pubmed_files, args.max_pmc_files)
    else:
        if args.download:
            pipeline.download_data(args.max_pubmed_files, args.max_pmc_files)
        
        if args.parse or args.embed:
            if args.parse:
                logger.info("Parsing enabled")
            if args.embed:
                pipeline.process_pubmed_to_database()
                pipeline.process_pmc_to_database()

if __name__ == "__main__":
    main() 