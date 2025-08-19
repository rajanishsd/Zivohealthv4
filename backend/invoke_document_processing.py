#!/usr/bin/env python3
"""
Simple script to invoke document processing workflow.

This script demonstrates how to use the document processing workflow
to analyze and process various types of medical documents.
"""

import sys
import os
from pathlib import Path
import asyncio
import json
from typing import Dict, Any

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

# Import the document processing functions
from app.agentsv2.document_workflow import process_file, process_file_async


def print_results(result: Dict[str, Any], file_path: str) -> None:
    """Print processing results in a formatted way."""
    print(f"\n{'='*60}")
    print(f"DOCUMENT PROCESSING RESULTS")
    print(f"{'='*60}")
    print(f"File: {file_path}")
    print(f"File Name: {result.get('file_name', 'N/A')}")
    print(f"Document Type: {result.get('file_type', 'Unknown')}")
    print(f"Processing Success: {result.get('processing_success', False)}")
    print(f"Processing Message: {result.get('processing_message', 'N/A')}")
    
    # Show analysis result details if available
    analysis_result = result.get('analysis_result')
    if analysis_result:
        print(f"\nANALYSIS DETAILS:")
        print(f"  Document Type: {analysis_result.get('document_type', 'Unknown')}")
        print(f"  Confidence: {analysis_result.get('confidence', 0):.2f}")
        print(f"  Sub-category: {analysis_result.get('sub_category') or 'N/A'}")
        print(f"  Key Indicators: {', '.join(analysis_result.get('key_indicators', [])) if analysis_result.get('key_indicators') else 'None'}")
        print(f"  Description: {analysis_result.get('description', 'No description')}")
    
    # Show processing statistics if available (for lab reports)
    stats = result.get('processing_statistics')
    if stats and stats.get('total_records_processed', 0) > 0:
        print(f"\nPROCESSING STATISTICS:")
        print(f"  Total Records: {stats.get('total_records_processed', 0)}")
        print(f"  Inserted: {stats.get('records_inserted', 0)}")
        print(f"  Updated: {stats.get('records_updated', 0)}")
        print(f"  Duplicates: {stats.get('duplicate_records', 0)}")
        print(f"  Failed: {stats.get('failed_records', 0)}")
    
    # Show any errors
    if result.get('error'):
        print(f"\nERROR: {result['error']}")
    
    print(f"{'='*60}\n")


def process_document_sync(user_id: str, file_path: str) -> Dict[str, Any]:
    """Process a document using the synchronous method."""
    print(f"Processing document synchronously...")
    print(f"User ID: {user_id}")
    print(f"File Path: {file_path}")
    
    try:
        result = process_file(user_id, file_path)
        print_results(result, file_path)
        return result
    except Exception as e:
        print(f"Error processing document: {str(e)}")
        return {"error": str(e), "success": False}


async def process_document_async(user_id: str, file_path: str) -> Dict[str, Any]:
    """Process a document using the asynchronous method."""
    print(f"Processing document asynchronously...")
    print(f"User ID: {user_id}")
    print(f"File Path: {file_path}")
    
    try:
        result = await process_file_async(user_id, file_path)
        print_results(result, file_path)
        return result
    except Exception as e:
        print(f"Error processing document: {str(e)}")
        return {"error": str(e), "success": False}


async def process_multiple_documents_async(user_id: str, file_paths: list) -> None:
    """Process multiple documents concurrently."""
    print(f"Processing {len(file_paths)} documents concurrently...")
    
    tasks = []
    for file_path in file_paths:
        task = process_document_async(user_id, file_path)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"\nCompleted processing {len(file_paths)} documents.")
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Document {i+1} failed: {str(result)}")
        else:
            print(f"Document {i+1} processed successfully")


def main():
    """Main function with usage examples."""
    print("Document Processing Workflow Invoker")
    print("=" * 40)
    
    # Example usage - you can modify these paths
    user_id = 1  # Replace with actual user ID (must be string)
    
    # Example file paths - replace with actual file paths
    example_files = [
        "data/uploads/pharmacy/78aa86c2-adc4-4594-8ef0-e258f0bdbd46.pdf"
    ]
    
    # Check if files exist and filter to existing ones
    existing_files = []
    for file_path in example_files:
        if os.path.exists(file_path):
            existing_files.append(file_path)
        else:
            print(f"Warning: File not found: {file_path}")
    
    if not existing_files:
        print("No example files found. Please update the file paths in the script.")
        print("\nExample usage:")
        print("1. Synchronous processing:")
        print("   result = process_file('1', 'path/to/your/document.pdf')")
        print("\n2. Asynchronous processing:")
        print("   result = await process_file_async('1', 'path/to/your/document.pdf')")
        return
    
    # Process first file synchronously
    if existing_files:
        print("\n1. SYNCHRONOUS PROCESSING EXAMPLE:")
        result_sync = process_document_sync(user_id, existing_files[0])
        print(f"Result: {json.dumps(result_sync, indent=2)}")
   

if __name__ == "__main__":
    main() 