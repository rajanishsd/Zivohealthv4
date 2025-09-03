#!/usr/bin/env python3
"""
PMC Document Search Tool
========================

Search through chunked PMC documents with various modes:
- Semantic search across all documents
- Search by PMC ID
- Document reconstruction from chunks
- Context expansion around relevant chunks
- Advanced filtering and sorting

Usage:
    python pmc_search.py "diabetes treatment"
    python pmc_search.py --interactive
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Database and embeddings
from sqlalchemy import create_engine, text
from langchain_community.embeddings import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores.pgvector import PGVector
from langchain.docstore.document import Document
import torch
from transformers import AutoModel, AutoTokenizer
from transformers.modeling_utils import load_state_dict
from safetensors.torch import save_file
import os
# Configuration
DATABASE_URL = "postgresql://rajanishsd@localhost:5432/zivohealth"
COLLECTION_NAME = "pmc_tracked_docs"


def downloadembedding():
    

    MODEL_NAME = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
    LOCAL_DIR = "./converted_model"

    # Step 1: Download model config and tokenizer
    print("🔄 Downloading config and tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME, trust_remote_code=True)

    # Step 2: Get state_dict and convert
    print("💾 Converting to safetensors format...")
    state_dict = model.state_dict()

    # Step 3: Save model using safetensors
    os.makedirs(LOCAL_DIR, exist_ok=True)
    save_file(state_dict, f"{LOCAL_DIR}/model.safetensors")

    # Save config and tokenizer
    model.config.save_pretrained(LOCAL_DIR)
    tokenizer.save_pretrained(LOCAL_DIR)

    print(f"✅ Model saved to {LOCAL_DIR} in safetensors format.")


class PMCSearcher:
    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = database_url
        self.embeddings = None
        self.vector_store = None
        self.engine = None
        self.setup()
    
    
    def setup(self):
        """Initialize embeddings and database connection"""
        print("🧠 Setting up embeddings...")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        
        self.embeddings = SentenceTransformer("./converted_model", trust_remote_code=True)
        #self.embeddings = self.load_biobert_model()
        print("💾 Connecting to database...")
        self.engine = create_engine(self.database_url)
        
        self.vector_store = PGVector(
            collection_name=COLLECTION_NAME,
            connection_string=self.database_url,
            embedding_function=self.embeddings,
        )
        print("✅ Search ready!")
    
    def search(self, query: str, k: int = 5, min_score: float = 0.0) -> List[Tuple[Document, float]]:
        """Basic semantic search"""
        print(f"\n🔍 Searching: '{query}'")
        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)
            # Filter by minimum score if specified
            if min_score > 0:
                results = [(doc, score) for doc, score in results if score >= min_score]
            
            self.print_results(results)
            return results
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []
    
    def search_by_pmc_id(self, pmc_id: str) -> List[Document]:
        """Find all chunks for a specific PMC ID"""
        print(f"\n🔍 Finding all chunks for PMC: {pmc_id}")
        try:
            # Use similarity search with filter
            results = self.vector_store.similarity_search(
                query="",  # Empty query, rely on filter
                k=100,     # Get many results
                filter={"pmc_id": pmc_id}
            )
            
            if not results:
                print(f"❌ No documents found for PMC ID: {pmc_id}")
                return []
            
            # Sort by chunk index
            results.sort(key=lambda x: x.metadata.get("chunk_index", 0))
            
            print(f"✅ Found {len(results)} chunks for {pmc_id}")
            for i, doc in enumerate(results):
                chunk_idx = doc.metadata.get("chunk_index", "?")
                total_chunks = doc.metadata.get("total_chunks", "?")
                title = doc.metadata.get("title", "No title")
                print(f"   Chunk {chunk_idx + 1}/{total_chunks}: {title}")
            
            return results
        except Exception as e:
            print(f"❌ PMC search error: {e}")
            return []
    
    def reconstruct_document(self, pmc_id: str) -> Optional[str]:
        """Reconstruct full document from chunks"""
        chunks = self.search_by_pmc_id(pmc_id)
        if not chunks:
            return None
        
        print(f"\n📄 Reconstructing document: {pmc_id}")
        
        # Sort chunks by index
        chunks.sort(key=lambda x: x.metadata.get("chunk_index", 0))
        
        # Combine chunks (removing overlap)
        full_content = ""
        for i, chunk in enumerate(chunks):
            content = chunk.page_content
            
            if i == 0:
                # First chunk - use all content
                full_content = content
            else:
                # Subsequent chunks - try to remove overlap
                overlap_size = 1000  # CHUNK_OVERLAP from original config
                
                # Simple overlap removal - take content after overlap
                if len(content) > overlap_size:
                    full_content += content[overlap_size:]
                else:
                    full_content += content
        
        print(f"✅ Reconstructed document: {len(full_content)} characters")
        return full_content
    
    def search_with_context(self, query: str, k: int = 5, context_chunks: int = 1) -> List[Dict]:
        """Search and return results with surrounding context chunks"""
        print(f"\n🔍 Searching with context: '{query}'")
        
        basic_results = self.search(query, k, min_score=0.0)
        enhanced_results = []
        
        for doc, score in basic_results:
            pmc_id = doc.metadata.get("pmc_id")
            chunk_index = doc.metadata.get("chunk_index", 0)
            
            # Get all chunks for this document
            all_chunks = self.search_by_pmc_id(pmc_id)
            
            # Find context chunks
            start_idx = max(0, chunk_index - context_chunks)
            end_idx = min(len(all_chunks), chunk_index + context_chunks + 1)
            
            context_chunks_list = all_chunks[start_idx:end_idx]
            
            enhanced_results.append({
                "main_chunk": doc,
                "score": score,
                "context_chunks": context_chunks_list,
                "pmc_id": pmc_id,
                "chunk_index": chunk_index
            })
        
        return enhanced_results
    
    def search_by_source(self, source_archive: str, query: str = "", k: int = 10) -> List[Document]:
        """Search within a specific source archive"""
        print(f"\n🔍 Searching in source: {source_archive}")
        try:
            if query:
                results = self.vector_store.similarity_search(
                    query=query,
                    k=k,
                    filter={"source_archive": source_archive}
                )
            else:
                # Get all documents from this source
                results = self.vector_store.similarity_search(
                    query="",
                    k=k,
                    filter={"source_archive": source_archive}
                )
            
            print(f"✅ Found {len(results)} results in {source_archive}")
            return results
        except Exception as e:
            print(f"❌ Source search error: {e}")
            return []
    
    def get_database_stats(self) -> Dict:
        """Get statistics about the database"""
        try:
            with self.engine.connect() as conn:
                # Get total documents
                result = conn.execute(text(f"""
                    SELECT COUNT(*) as total_chunks,
                           COUNT(DISTINCT (cmetadata->>'pmc_id')) as unique_documents,
                           COUNT(DISTINCT (cmetadata->>'source_archive')) as unique_sources
                    FROM langchain_pg_embedding 
                    WHERE cmetadata->>'document_type' = 'pmc_tracked'
                """))
                
                stats = result.fetchone()
                
                return {
                    "total_chunks": stats[0] if stats else 0,
                    "unique_documents": stats[1] if stats else 0,
                    "unique_sources": stats[2] if stats else 0
                }
        except Exception as e:
            print(f"❌ Stats error: {e}")
            return {"total_chunks": 0, "unique_documents": 0, "unique_sources": 0}
    
    def print_results(self, results: List[Tuple[Document, float]]):
        """Pretty print search results"""
        if not results:
            print("❌ No results found")
            return
        
        print(f"📊 Found {len(results)} results:")
        print("-" * 80)
        
        for i, (doc, score) in enumerate(results, 1):
            title = doc.metadata.get('title', 'No title')
            pmc_id = doc.metadata.get('pmc_id', 'Unknown')
            chunk_info = f"{doc.metadata.get('chunk_index', 0) + 1}/{doc.metadata.get('total_chunks', 1)}"
            source = doc.metadata.get('source_archive', 'Unknown')
            
            print(f"{i}. {title}")
            print(f"   PMC: {pmc_id} | Chunk: {chunk_info} | Score: {score:.3f}")
            print(f"   Source: {source}")
            print(f"   Preview: {doc.page_content[:200]}...")
            print()
    
    def interactive_search(self):
        """Interactive search mode"""
        print("\n🎯 Interactive PMC Search")
        print("=" * 50)
        
        # Show stats
        stats = self.get_database_stats()
        print(f"📊 Database: {stats['total_chunks']} chunks, {stats['unique_documents']} documents, {stats['unique_sources']} sources")
        
        while True:
            print("\nCommands:")
            print("  search <query>           - Semantic search")
            print("  pmc <PMC_ID>            - Get all chunks for PMC ID")
            print("  reconstruct <PMC_ID>    - Reconstruct full document")
            print("  context <query>         - Search with context")
            print("  source <archive> [query] - Search in specific source")
            print("  stats                   - Show database statistics")
            print("  quit                    - Exit")
            
            try:
                command = input("\n> ").strip()
                
                if not command:
                    continue
                
                if command.lower() == 'quit':
                    break
                
                if command.lower() == 'stats':
                    stats = self.get_database_stats()
                    print(f"📊 Total chunks: {stats['total_chunks']}")
                    print(f"📊 Unique documents: {stats['unique_documents']}")
                    print(f"📊 Unique sources: {stats['unique_sources']}")
                    continue
                
                parts = command.split(' ', 1)
                cmd = parts[0].lower()
                
                if cmd == 'search' and len(parts) > 1:
                    self.search(parts[1])
                
                elif cmd == 'pmc' and len(parts) > 1:
                    self.search_by_pmc_id(parts[1])
                
                elif cmd == 'reconstruct' and len(parts) > 1:
                    content = self.reconstruct_document(parts[1])
                    if content:
                        print(f"\n📄 Full document content:")
                        print("-" * 80)
                        print(content[:2000] + "..." if len(content) > 2000 else content)
                
                elif cmd == 'context' and len(parts) > 1:
                    results = self.search_with_context(parts[1])
                    for result in results:
                        print(f"\n📄 Context for: {result['pmc_id']}")
                        for chunk in result['context_chunks']:
                            idx = chunk.metadata.get('chunk_index', 0)
                            print(f"   Chunk {idx + 1}: {chunk.page_content[:100]}...")
                
                elif cmd == 'source':
                    if len(parts) > 1:
                        source_parts = parts[1].split(' ', 1)
                        source = source_parts[0]
                        query = source_parts[1] if len(source_parts) > 1 else ""
                        self.search_by_source(source, query)
                    else:
                        print("❌ Please specify source archive")
                
                else:
                    print("❌ Unknown command or missing arguments")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

def main():
    downloadembedding()
    parser = argparse.ArgumentParser(description="Search PMC documents")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--pmc", help="Search by PMC ID")
    parser.add_argument("--reconstruct", help="Reconstruct document by PMC ID")
    parser.add_argument("--context", type=int, default=1, help="Context chunks around results")
    parser.add_argument("--count", "-k", type=int, default=5, help="Number of results")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum similarity score")
    
    args = parser.parse_args()
    
    # Initialize searcher
    searcher = PMCSearcher()
    
    if args.interactive:
        searcher.interactive_search()
    
    elif args.pmc:
        searcher.search_by_pmc_id(args.pmc)
    
    elif args.reconstruct:
        content = searcher.reconstruct_document(args.reconstruct)
        if content:
            print(content)
    
    elif args.query:
        searcher.search(args.query, k=args.count, min_score=args.min_score)
    
    else:
        print("❌ Please provide a query or use --interactive mode")
        print("Examples:")
        print("  python pmc_search.py 'diabetes treatment'")
        print("  python pmc_search.py --interactive")
        print("  python pmc_search.py --pmc PMC123456")

if __name__ == "__main__":
    main() 