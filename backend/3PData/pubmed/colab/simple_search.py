#!/usr/bin/env python3
"""
Simple PMC Document Search Tool
===============================

A basic search tool that uses SQL queries to search through your PMC documents
without requiring PyTorch or embeddings.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import create_engine, text

# Configuration
DATABASE_URL = "postgresql://rajanishsd@localhost:5433/zivohealth"
COLLECTION_NAME = "pmc_tracked_docs"

class SimplePMCSearcher:
    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        print("✅ Database connection ready!")
    
    def search_text(self, query: str, limit: int = 10) -> List[Dict]:
        """Search using basic text matching"""
        print(f"\n🔍 Text search: '{query}'")
        
        try:
            with self.engine.connect() as conn:
                # Use PostgreSQL's text search
                sql = text("""
                    SELECT document as content, 
                           cmetadata->>'pmc_id' as pmc_id,
                           cmetadata->>'title' as title,
                           cmetadata->>'chunk_index' as chunk_index,
                           cmetadata->>'total_chunks' as total_chunks,
                           cmetadata->>'source_archive' as source_archive,
                           cmetadata->>'filename' as filename
                    FROM langchain_pg_embedding 
                    WHERE cmetadata->>'document_type' = 'pmc_tracked'
                    AND (document ILIKE :query OR 
                         cmetadata->>'title' ILIKE :query OR
                         cmetadata->>'pmc_id' ILIKE :query)
                    ORDER BY LENGTH(document) DESC
                    LIMIT :limit
                """)
                
                result = conn.execute(sql, {"query": f"%{query}%", "limit": limit})
                rows = result.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        "content": row[0],
                        "pmc_id": row[1],
                        "title": row[2] or "No title",
                        "chunk_index": int(row[3]) if row[3] else 0,
                        "total_chunks": int(row[4]) if row[4] else 1,
                        "source_archive": row[5] or "Unknown",
                        "filename": row[6] or "Unknown"
                    })
                
                self.print_results(results)
                return results
                
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []
    
    def search_by_pmc_id(self, pmc_id: str) -> List[Dict]:
        """Find all chunks for a specific PMC ID"""
        print(f"\n🔍 Finding chunks for PMC: {pmc_id}")
        
        try:
            with self.engine.connect() as conn:
                sql = text("""
                    SELECT document as content, 
                           cmetadata->>'pmc_id' as pmc_id,
                           cmetadata->>'title' as title,
                           cmetadata->>'chunk_index' as chunk_index,
                           cmetadata->>'total_chunks' as total_chunks,
                           cmetadata->>'source_archive' as source_archive,
                           cmetadata->>'filename' as filename
                    FROM langchain_pg_embedding 
                    WHERE cmetadata->>'document_type' = 'pmc_tracked'
                    AND cmetadata->>'pmc_id' = :pmc_id
                    ORDER BY CAST(cmetadata->>'chunk_index' AS INTEGER)
                """)
                
                result = conn.execute(sql, {"pmc_id": pmc_id})
                rows = result.fetchall()
                
                if not rows:
                    print(f"❌ No chunks found for PMC: {pmc_id}")
                    return []
                
                results = []
                for row in rows:
                    results.append({
                        "content": row[0],
                        "pmc_id": row[1],
                        "title": row[2] or "No title",
                        "chunk_index": int(row[3]) if row[3] else 0,
                        "total_chunks": int(row[4]) if row[4] else 1,
                        "source_archive": row[5] or "Unknown",
                        "filename": row[6] or "Unknown"
                    })
                
                print(f"✅ Found {len(results)} chunks for {pmc_id}")
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
        chunks.sort(key=lambda x: x["chunk_index"])
        
        # Combine chunks (simple concatenation)
        full_content = ""
        for i, chunk in enumerate(chunks):
            content = chunk["content"]
            if i == 0:
                full_content = content
            else:
                # Simple overlap removal
                overlap_size = 1000
                if len(content) > overlap_size:
                    full_content += content[overlap_size:]
                else:
                    full_content += content
        
        print(f"✅ Reconstructed document: {len(full_content)} characters")
        return full_content
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        try:
            with self.engine.connect() as conn:
                sql = text("""
                    SELECT COUNT(*) as total_chunks,
                           COUNT(DISTINCT (cmetadata->>'pmc_id')) as unique_documents,
                           COUNT(DISTINCT (cmetadata->>'source_archive')) as unique_sources
                    FROM langchain_pg_embedding 
                    WHERE cmetadata->>'document_type' = 'pmc_tracked'
                """)
                
                result = conn.execute(sql)
                row = result.fetchone()
                
                return {
                    "total_chunks": row[0] if row else 0,
                    "unique_documents": row[1] if row else 0,
                    "unique_sources": row[2] if row else 0
                }
        except Exception as e:
            print(f"❌ Stats error: {e}")
            return {"total_chunks": 0, "unique_documents": 0, "unique_sources": 0}
    
    def list_pmc_ids(self, limit: int = 20) -> List[str]:
        """List available PMC IDs"""
        try:
            with self.engine.connect() as conn:
                sql = text("""
                    SELECT DISTINCT cmetadata->>'pmc_id' as pmc_id,
                           cmetadata->>'title' as title
                    FROM langchain_pg_embedding 
                    WHERE cmetadata->>'document_type' = 'pmc_tracked'
                    ORDER BY pmc_id
                    LIMIT :limit
                """)
                
                result = conn.execute(sql, {"limit": limit})
                rows = result.fetchall()
                
                print(f"\n📋 Available PMC IDs (showing first {limit}):")
                for row in rows:
                    pmc_id = row[0]
                    title = row[1] or "No title"
                    print(f"   {pmc_id}: {title[:60]}...")
                
                return [row[0] for row in rows if row[0]]
                
        except Exception as e:
            print(f"❌ List error: {e}")
            return []
    
    def print_results(self, results: List[Dict]):
        """Pretty print search results"""
        if not results:
            print("❌ No results found")
            return
        
        print(f"📊 Found {len(results)} results:")
        print("-" * 80)
        
        for i, result in enumerate(results, 1):
            title = result["title"]
            pmc_id = result["pmc_id"]
            chunk_info = f"{result['chunk_index'] + 1}/{result['total_chunks']}"
            source = result["source_archive"]
            
            print(f"{i}. {title}")
            print(f"   PMC: {pmc_id} | Chunk: {chunk_info}")
            print(f"   Source: {source}")
            print(f"   Preview: {result['content'][:200]}...")
            print()
    
    def interactive_search(self):
        """Interactive search mode"""
        print("\n🎯 Simple PMC Search (Text-based)")
        print("=" * 50)
        
        # Show stats
        stats = self.get_stats()
        print(f"📊 Database: {stats['total_chunks']} chunks, {stats['unique_documents']} documents")
        
        while True:
            print("\nCommands:")
            print("  search <text>     - Text search")
            print("  pmc <PMC_ID>      - Get chunks for PMC ID")
            print("  reconstruct <PMC_ID> - Reconstruct document")
            print("  list              - List available PMC IDs")
            print("  stats             - Database statistics")
            print("  quit              - Exit")
            
            try:
                command = input("\n> ").strip()
                
                if not command:
                    continue
                
                if command.lower() == 'quit':
                    break
                
                if command.lower() == 'stats':
                    stats = self.get_stats()
                    print(f"📊 Total chunks: {stats['total_chunks']}")
                    print(f"📊 Unique documents: {stats['unique_documents']}")
                    print(f"📊 Unique sources: {stats['unique_sources']}")
                    continue
                
                if command.lower() == 'list':
                    self.list_pmc_ids()
                    continue
                
                parts = command.split(' ', 1)
                cmd = parts[0].lower()
                
                if cmd == 'search' and len(parts) > 1:
                    self.search_text(parts[1])
                
                elif cmd == 'pmc' and len(parts) > 1:
                    self.search_by_pmc_id(parts[1])
                
                elif cmd == 'reconstruct' and len(parts) > 1:
                    content = self.reconstruct_document(parts[1])
                    if content:
                        print(f"\n📄 Full document:")
                        print("-" * 80)
                        print(content[:2000] + "..." if len(content) > 2000 else content)
                
                else:
                    print("❌ Unknown command or missing arguments")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

def main():
    if len(sys.argv) > 1:
        searcher = SimplePMCSearcher()
        if sys.argv[1] == "--interactive":
            searcher.interactive_search()
        else:
            query = " ".join(sys.argv[1:])
            searcher.search_text(query)
    else:
        searcher = SimplePMCSearcher()
        searcher.interactive_search()

if __name__ == "__main__":
    main() 