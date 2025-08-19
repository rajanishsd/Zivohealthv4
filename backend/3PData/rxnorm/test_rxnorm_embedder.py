#!/usr/bin/env python3
"""
Test RxNorm Embedder
===================

This script tests the RxNorm embedder functionality including:
- Database setup
- CSV processing
- Embedding generation
- Search functionality
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from rxnorm_embedder import RxNormEmbeddingPipeline, RxNormCSVProcessor
from config import validate_config, get_config_summary

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config():
    """Test configuration validation"""
    logger.info("Testing configuration...")
    
    try:
        validate_config()
        logger.info("✅ Configuration validation passed")
        
        config_summary = get_config_summary()
        logger.info(f"Configuration summary: {json.dumps(config_summary, indent=2)}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        return False

def test_csv_processing():
    """Test CSV processing functionality"""
    logger.info("Testing CSV processing...")
    
    try:
        from config import RXNORM_CSV_FILE
        
        if not RXNORM_CSV_FILE.exists():
            logger.error(f"❌ RxNorm CSV file not found: {RXNORM_CSV_FILE}")
            return False
        
        processor = RxNormCSVProcessor(str(RXNORM_CSV_FILE))
        
        # Test processing a small batch
        batch_count = 0
        total_filtered = 0
        
        for batch in processor.process_csv(batch_size=100):
            batch_count += 1
            total_filtered += len(batch)
            
            logger.info(f"Batch {batch_count}: {len(batch)} records")
            
            # Test first record structure
            if batch:
                first_record = batch[0]
                logger.info(f"Sample record: {first_record.concept_name} ({first_record.concept_code})")
            
            # Only process first few batches for testing
            if batch_count >= 3:
                break
        
        logger.info(f"✅ CSV processing test passed. Processed {batch_count} batches, {total_filtered} total records")
        return True
        
    except Exception as e:
        logger.error(f"❌ CSV processing test failed: {e}")
        return False

def test_database_setup():
    """Test database setup"""
    logger.info("Testing database setup...")
    
    try:
        pipeline = RxNormEmbeddingPipeline()
        pipeline.setup_database()
        logger.info("✅ Database setup test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Database setup test failed: {e}")
        return False

def test_embedding_generation():
    """Test embedding generation with a small sample"""
    logger.info("Testing embedding generation...")
    
    try:
        pipeline = RxNormEmbeddingPipeline()
        
        # Create a test document
        from rxnorm_embedder import RxNormRecord
        from langchain.docstore.document import Document
        
        test_record = RxNormRecord(
            concept_id="12345",
            concept_name="Test Drug",
            domain_id="Drug",
            vocabulary_id="RxNorm",
            concept_class_id="Clinical Drug",
            standard_concept="S",
            concept_code="TEST123",
            valid_start_date="20200101",
            valid_end_date="20991231",
            invalid_reason=""
        )
        
        # Test embedding generation
        test_doc = test_record.to_langchain_document()
        logger.info(f"Test document: {test_doc.page_content[:100]}...")
        
        # Test embedding
        embedding = pipeline.embeddings.embed_query(test_doc.page_content)
        logger.info(f"✅ Embedding generated successfully. Dimensions: {len(embedding)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Embedding generation test failed: {e}")
        return False

def test_search_functionality():
    """Test search functionality"""
    logger.info("Testing search functionality...")
    
    try:
        pipeline = RxNormEmbeddingPipeline()
        
        # Test search (this will work even if no data is loaded)
        results = pipeline.search_rxnorm_codes("aspirin", k=5)
        logger.info(f"✅ Search test completed. Found {len(results)} results")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Search functionality test failed: {e}")
        return False

def test_stats():
    """Test statistics functionality"""
    logger.info("Testing statistics...")
    
    try:
        pipeline = RxNormEmbeddingPipeline()
        stats = pipeline.get_stats()
        logger.info(f"✅ Statistics test passed: {json.dumps(stats, indent=2)}")
        return True
    except Exception as e:
        logger.error(f"❌ Statistics test failed: {e}")
        return False

def main():
    """Run all tests"""
    logger.info("Starting RxNorm embedder tests...")
    
    tests = [
        ("Configuration", test_config),
        ("CSV Processing", test_csv_processing),
        ("Database Setup", test_database_setup),
        ("Embedding Generation", test_embedding_generation),
        ("Search Functionality", test_search_functionality),
        ("Statistics", test_stats)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Test Results: {passed}/{total} tests passed")
    logger.info(f"{'='*50}")
    
    if passed == total:
        logger.info("🎉 All tests passed! RxNorm embedder is ready to use.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    exit(main()) 