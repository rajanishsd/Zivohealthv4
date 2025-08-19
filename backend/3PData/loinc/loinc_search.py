#!/usr/bin/env python3
"""
LOINC Search Tool
================

Command-line search tool for LOINC embeddings using OpenAI text-embedding-3-large.
Provides semantic search capabilities for LOINC codes and terminology.

Usage:
    python loinc_search.py "blood glucose"
    python loinc_search.py --interactive
    python loinc_search.py --code "33747-0"
    python loinc_search.py --batch-search queries.txt
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from loinc_embedder import LOINCEmbeddingPipeline
from config import *

class LOINCSearchTool:
    """Interactive search tool for LOINC embeddings"""
    
    def __init__(self):
        try:
            self.pipeline = LOINCEmbeddingPipeline()
            print("✅ LOINC Search Tool initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing search tool: {e}")
            sys.exit(1)
    
    def search(self, query: str, k: int = 10, verbose: bool = True) -> List[Tuple[Dict, float]]:
        """
        Search LOINC codes using semantic similarity
        
        Args:
            query: Search query string
            k: Number of results to return
            verbose: Whether to print results
            
        Returns:
            List of (metadata, score) tuples
        """
        if verbose:
            print(f"\n🔍 Searching for: '{query}'")
            print(f"📊 Requesting {k} results...")
        
        try:
            results = self.pipeline.search_loinc_codes(query, k=k)
            
            if not results:
                if verbose:
                    print("❌ No results found")
                return []
            
            formatted_results = []
            for i, (doc, score) in enumerate(results, 1):
                metadata = doc.metadata
                formatted_results.append((metadata, score))
                
                if verbose:
                    self._print_result(i, metadata, score)
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []
    
    def search_by_code(self, loinc_code: str, verbose: bool = True) -> Optional[Dict]:
        """
        Search for a specific LOINC code
        
        Args:
            loinc_code: LOINC code (e.g., "33747-0")
            verbose: Whether to print results
            
        Returns:
            LOINC code metadata if found, None otherwise
        """
        if verbose:
            print(f"\n🔍 Searching for LOINC code: '{loinc_code}'")
        
        # Search using the LOINC code as query
        results = self.search(f"LOINC: {loinc_code}", k=50, verbose=False)
        
        # Find exact match
        for metadata, score in results:
            if metadata.get('loinc_num') == loinc_code:
                if verbose:
                    print("✅ Found exact match:")
                    self._print_result(1, metadata, score)
                return metadata
        
        if verbose:
            print("❌ LOINC code not found")
        return None
    
    def batch_search(self, queries: List[str], k: int = 5) -> Dict[str, List[Dict]]:
        """
        Perform batch search for multiple queries
        
        Args:
            queries: List of search queries
            k: Number of results per query
            
        Returns:
            Dictionary mapping queries to results
        """
        print(f"\n🔍 Performing batch search for {len(queries)} queries...")
        
        results = {}
        for i, query in enumerate(queries, 1):
            print(f"  📊 Processing query {i}/{len(queries)}: '{query}'")
            query_results = self.search(query, k=k, verbose=False)
            results[query] = [metadata for metadata, score in query_results]
        
        return results
    
    def interactive_search(self):
        """Interactive search mode"""
        print("\n🔍 LOINC Interactive Search Mode")
        print("Commands:")
        print("  Type search query to search")
        print("  'code <LOINC_CODE>' to search by code")
        print("  'stats' to show database statistics")
        print("  'help' to show this help")
        print("  'exit' or 'quit' to exit")
        print()
        
        while True:
            try:
                user_input = input("loinc_search> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 Goodbye!")
                    break
                
                elif user_input.lower() == 'help':
                    print("\n🔍 LOINC Search Help:")
                    print("  - Enter any medical term to search")
                    print("  - Use 'code <LOINC_CODE>' for exact code lookup")
                    print("  - Use 'stats' to view database statistics")
                    print("  - Use 'exit' to quit")
                    print()
                
                elif user_input.lower() == 'stats':
                    stats = self.pipeline.get_stats()
                    print(f"\n📊 Database Statistics:")
                    for key, value in stats.items():
                        print(f"  {key}: {value}")
                    print()
                
                elif user_input.lower().startswith('code '):
                    loinc_code = user_input[5:].strip()
                    self.search_by_code(loinc_code)
                
                else:
                    # Regular search
                    self.search(user_input)
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def _print_result(self, rank: int, metadata: Dict, score: float):
        """Print a single search result"""
        print(f"\n  {rank}. LOINC: {metadata.get('loinc_num', 'N/A')} (Score: {score:.4f})")
        print(f"     Name: {metadata.get('long_common_name', 'N/A')}")
        print(f"     Short Name: {metadata.get('short_name', 'N/A')}")
        print(f"     Component: {metadata.get('component', 'N/A')}")
        print(f"     System: {metadata.get('system', 'N/A')}")
        print(f"     Class: {metadata.get('loinc_class', 'N/A')}")
        print(f"     Status: {metadata.get('status', 'N/A')}")
    
    def export_results(self, query: str, results: List[Tuple[Dict, float]], 
                      filename: str = None) -> str:
        """
        Export search results to JSON file
        
        Args:
            query: Original search query
            results: Search results
            filename: Output filename (optional)
            
        Returns:
            Path to exported file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"loinc_search_results_{timestamp}.json"
        
        export_data = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "num_results": len(results),
            "results": []
        }
        
        for metadata, score in results:
            export_data["results"].append({
                "score": score,
                "loinc_code": metadata.get('loinc_num'),
                "name": metadata.get('long_common_name'),
                "short_name": metadata.get('short_name'),
                "component": metadata.get('component'),
                "system": metadata.get('system'),
                "class": metadata.get('loinc_class'),
                "status": metadata.get('status'),
                "metadata": metadata
            })
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"📁 Results exported to: {filename}")
        return filename

def load_queries_from_file(filename: str) -> List[str]:
    """Load search queries from text file"""
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="LOINC Search Tool")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("-k", "--results", type=int, default=10, 
                       help="Number of results to return")
    parser.add_argument("-i", "--interactive", action="store_true",
                       help="Interactive search mode")
    parser.add_argument("-c", "--code", type=str,
                       help="Search by specific LOINC code")
    parser.add_argument("-b", "--batch-search", type=str,
                       help="File containing search queries (one per line)")
    parser.add_argument("-e", "--export", type=str,
                       help="Export results to JSON file")
    parser.add_argument("--stats", action="store_true",
                       help="Show database statistics")
    
    args = parser.parse_args()
    
    # Initialize search tool
    search_tool = LOINCSearchTool()
    
    # Handle different modes
    if args.stats:
        stats = search_tool.pipeline.get_stats()
        print(f"\n📊 Database Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    elif args.interactive:
        search_tool.interactive_search()
    
    elif args.code:
        search_tool.search_by_code(args.code)
    
    elif args.batch_search:
        try:
            queries = load_queries_from_file(args.batch_search)
            results = search_tool.batch_search(queries, k=args.results)
            
            # Print summary
            print(f"\n📊 Batch Search Results:")
            for query, query_results in results.items():
                print(f"  '{query}': {len(query_results)} results")
            
            # Export if requested
            if args.export:
                with open(args.export, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"📁 Results exported to: {args.export}")
            
        except FileNotFoundError:
            print(f"❌ File not found: {args.batch_search}")
        except Exception as e:
            print(f"❌ Error in batch search: {e}")
    
    elif args.query:
        results = search_tool.search(args.query, k=args.results)
        
        # Export if requested
        if args.export:
            search_tool.export_results(args.query, results, args.export)
    
    else:
        print("❌ Please specify a search query, use --interactive mode, or see --help")
        parser.print_help()

if __name__ == "__main__":
    main() 