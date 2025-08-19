#!/usr/bin/env python3
"""
RxNorm Search Utility
=====================

A simple utility for searching RxNorm drug terminology using the embedded vectors.
This can be used independently or integrated into other applications.
"""

import sys
import json
import argparse
from typing import List, Tuple, Dict, Any
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from rxnorm_embedder import RxNormEmbeddingPipeline
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

class RxNormSearch:
    """Simple RxNorm search utility"""
    
    def __init__(self):
        """Initialize the search utility"""
        try:
            self.pipeline = RxNormEmbeddingPipeline()
            print(f"✅ RxNorm search utility initialized")
        except Exception as e:
            print(f"❌ Failed to initialize RxNorm search: {e}")
            sys.exit(1)
    
    def search(self, query: str, k: int = 10, show_metadata: bool = False) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for RxNorm codes
        
        Args:
            query: Search query
            k: Number of results to return
            show_metadata: Whether to include full metadata in results
            
        Returns:
            List of (result_dict, score) tuples
        """
        try:
            results = self.pipeline.search_rxnorm_codes(query, k=k)
            
            formatted_results = []
            for doc, score in results:
                result_dict = {
                    "score": score,
                    "content": doc.page_content,
                    "concept_name": doc.metadata.get("concept_name", ""),
                    "concept_code": doc.metadata.get("concept_code", ""),
                    "concept_class": doc.metadata.get("concept_class_id", ""),
                    "domain": doc.metadata.get("domain_id", ""),
                    "vocabulary": doc.metadata.get("vocabulary_id", ""),
                    "standard": doc.metadata.get("standard_concept", "")
                }
                
                if show_metadata:
                    result_dict["full_metadata"] = doc.metadata
                
                formatted_results.append((result_dict, score))
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get search statistics"""
        try:
            return self.pipeline.get_stats()
        except Exception as e:
            print(f"❌ Failed to get stats: {e}")
            return {}

def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(description="RxNorm Search Utility")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("-k", "--num-results", type=int, default=10, help="Number of results to return")
    parser.add_argument("--metadata", action="store_true", help="Show full metadata")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    # Initialize search utility
    search_util = RxNormSearch()
    
    if args.stats:
        # Show statistics
        stats = search_util.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("RxNorm Search Statistics:")
            print(f"  Total embeddings: {stats.get('total_embeddings', 0)}")
            print(f"  Collection: {stats.get('collection_name', 'N/A')}")
            print(f"  Model: {stats.get('embedding_model', 'N/A')}")
            print(f"  Dimensions: {stats.get('embedding_dimensions', 'N/A')}")
        return
    
    if not args.query:
        print("Error: Search query is required")
        parser.print_help()
        return
    
    # Perform search
    print(f"Searching for: '{args.query}'")
    results = search_util.search(args.query, k=args.num_results, show_metadata=args.metadata)
    
    if not results:
        print("No results found")
        return
    
    if args.json:
        # Output as JSON
        output = {
            "query": args.query,
            "num_results": len(results),
            "results": [{"result": result[0], "score": result[1]} for result in results]
        }
        print(json.dumps(output, indent=2))
    else:
        # Output as formatted text
        print(f"\nFound {len(results)} results:")
        print("=" * 80)
        
        for i, (result, score) in enumerate(results, 1):
            print(f"{i}. Score: {score:.4f}")
            print(f"   Name: {result['concept_name']}")
            print(f"   Code: {result['concept_code']}")
            print(f"   Class: {result['concept_class']}")
            print(f"   Domain: {result['domain']}")
            print(f"   Standard: {result['standard']}")
            
            if args.metadata:
                print(f"   Full Metadata: {json.dumps(result['full_metadata'], indent=2)}")
            
            print("-" * 40)

if __name__ == "__main__":
    main() 