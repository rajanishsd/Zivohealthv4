#!/usr/bin/env python3
"""
PMC Search Examples
===================

Simple examples of how to use the PMC search tool
"""

from pmc_search import PMCSearcher

def main():
    # Initialize searcher
    print("🚀 Initializing PMC Searcher...")
    searcher = PMCSearcher()
    
    # Example 1: Basic search
    print("\n" + "="*60)
    print("Example 1: Basic Semantic Search")
    print("="*60)
    searcher.search("diabetes treatment", k=3)
    
    # Example 2: Search with higher precision
    print("\n" + "="*60)
    print("Example 2: High-precision Search")
    print("="*60)
    searcher.search("cancer immunotherapy", k=5, min_score=0.7)
    
    # Example 3: Get database statistics
    print("\n" + "="*60)
    print("Example 3: Database Statistics")
    print("="*60)
    stats = searcher.get_database_stats()
    print(f"📊 Total chunks: {stats['total_chunks']}")
    print(f"📊 Unique documents: {stats['unique_documents']}")
    print(f"📊 Unique sources: {stats['unique_sources']}")
    
    # Example 4: Search by PMC ID (if you know one)
    print("\n" + "="*60)
    print("Example 4: Search by PMC ID")
    print("="*60)
    print("Note: Replace 'PMC123456' with an actual PMC ID from your results")
    # searcher.search_by_pmc_id("PMC123456")
    
    # Example 5: Interactive mode info
    print("\n" + "="*60)
    print("Example 5: Interactive Mode")
    print("="*60)
    print("Run: python pmc_search.py --interactive")
    print("For full interactive search experience!")

if __name__ == "__main__":
    main() 