#!/usr/bin/env python3
"""
Diagnose Pending Status Issues
==============================

This script identifies why some lab tests are stuck in pending status and provides solutions.

Issues identified:
1. Tests without test_code are skipped during aggregation
2. Status updates only happen for records with test_code
3. Some tests may have missing or invalid data

Usage:
    python backend/aggregation/diagnose_pending_status.py
"""

import sys
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Add the backend directory to Python path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Go up two levels to backend
sys.path.insert(0, backend_dir)

# Load environment variables from .env file before importing app modules
env_file = os.path.join(backend_dir, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print(f"⚠️  No .env file found at {env_file}")

try:
    from app.core.config import settings  # noqa: E402
    from app.crud.lab_categorization import LabCategorizationCRUD  # noqa: E402
    from app.crud.lab_aggregation import LabAggregationCRUD  # noqa: E402
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running this from the project root directory:")
    print("   cd /path/to/zivohealth-1")
    print("   python backend/aggregation/diagnose_pending_status.py")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def diagnose_pending_status():
    """Diagnose why some tests are stuck in pending status"""
    logger.info("🔍 Diagnosing pending status issues...")
    
    # Setup database
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Check raw lab reports status
        logger.info("📋 Phase 1: Raw Lab Reports Status")
        raw_status = db.execute(text("""
            SELECT categorization_status, COUNT(*) as count
            FROM lab_reports
            GROUP BY categorization_status
            ORDER BY categorization_status
        """)).fetchall()
        
        for row in raw_status:
            logger.info(f"   {row.categorization_status}: {row.count} records")
        
        # 2. Check categorized lab reports status
        logger.info("\n📈 Phase 2: Categorized Lab Reports Status")
        categorized_status = db.execute(text("""
            SELECT aggregation_status, COUNT(*) as count
            FROM lab_report_categorized
            GROUP BY aggregation_status
            ORDER BY aggregation_status
        """)).fetchall()
        
        for row in categorized_status:
            logger.info(f"   {row.aggregation_status}: {row.count} records")
        
        # 3. Identify the main issue: tests without test_code
        logger.info("\n🔍 Phase 3: Identifying Tests Without test_code")
        no_test_code_result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM lab_report_categorized
            WHERE aggregation_status = 'pending' AND test_code IS NULL
        """)).fetchone()
        
        no_test_code_count = no_test_code_result.count if no_test_code_result else 0
        
        if no_test_code_count > 0:
            logger.warning(f"⚠️  Found {no_test_code_count} pending tests WITHOUT test_code")
            logger.warning("   This is the main issue - these tests are skipped during aggregation")
            
            # Show examples of tests without test_code
            examples = db.execute(text("""
                SELECT test_name, test_category, inferred_test_category, COUNT(*) as count
                FROM lab_report_categorized
                WHERE aggregation_status = 'pending' AND test_code IS NULL
                GROUP BY test_name, test_category, inferred_test_category
                ORDER BY count DESC
                LIMIT 10
            """)).fetchall()
            
            logger.info("   Examples of tests without test_code:")
            for example in examples:
                logger.info(f"      - {example.test_name} ({example.count} records)")
                logger.info(f"        Category: {example.test_category} -> {example.inferred_test_category}")
        else:
            logger.info("✅ All pending tests have test_code")
        
        # 4. Check for tests with test_code but still pending
        logger.info("\n🔍 Phase 4: Tests With test_code But Still Pending")
        with_test_code_pending_result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM lab_report_categorized
            WHERE aggregation_status = 'pending' AND test_code IS NOT NULL
        """)).fetchone()
        
        with_test_code_pending_count = with_test_code_pending_result.count if with_test_code_pending_result else 0
        
        if with_test_code_pending_count > 0:
            logger.warning(f"⚠️  Found {with_test_code_pending_count} pending tests WITH test_code")
            logger.warning("   These should be processed but aren't - possible worker issue")
            
            # Show examples
            examples = db.execute(text("""
                SELECT test_name, test_code, test_category, COUNT(*) as count
                FROM lab_report_categorized
                WHERE aggregation_status = 'pending' AND test_code IS NOT NULL
                GROUP BY test_name, test_code, test_category
                ORDER BY count DESC
                LIMIT 10
            """)).fetchall()
            
            logger.info("   Examples of tests with test_code but still pending:")
            for example in examples:
                logger.info(f"      - {example.test_name} (code: {example.test_code}) ({example.count} records)")
        else:
            logger.info("✅ No tests with test_code are pending")
        
        # 5. Check for orphaned records (in lab_reports but not in lab_report_categorized)
        logger.info("\n🔍 Phase 5: Orphaned Records")
        orphaned_result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM lab_reports lr
            LEFT JOIN lab_report_categorized lrc ON (
                lr.id = lrc.id AND lr.test_name = lrc.test_name AND 
                lr.test_date = lrc.test_date AND lr.test_value = lrc.test_value
            )
            WHERE lrc.id IS NULL AND lr.categorization_status = 'pending'
        """)).fetchone()
        
        orphaned_count = orphaned_result.count if orphaned_result else 0
        
        if orphaned_count > 0:
            logger.warning(f"⚠️  Found {orphaned_count} orphaned records in lab_reports")
            logger.warning("   These records exist in lab_reports but not in lab_report_categorized")
        else:
            logger.info("✅ No orphaned records found")
        
        # 6. Provide solutions
        logger.info("\n💡 Solutions:")
        logger.info("=" * 50)
        
        if no_test_code_count > 0:
            logger.info("1. Fix tests without test_code:")
            logger.info("   - Run the lab categorization process to generate test_codes")
            logger.info("   - Or manually update test_codes for these tests")
            logger.info("   - Command: python backend/aggregation/process_lab_categorization_and_aggregation.py")
        
        if with_test_code_pending_count > 0:
            logger.info("2. Process pending tests with test_code:")
            logger.info("   - Start the worker process to process pending aggregation")
            logger.info("   - Command: python backend/aggregation/worker_process.py")
            logger.info("   - Or run: python backend/aggregation/process_lab_categorization_and_aggregation.py")
        
        if orphaned_count > 0:
            logger.info("3. Fix orphaned records:")
            logger.info("   - Run lab categorization to process pending lab_reports")
            logger.info("   - Command: python backend/aggregation/process_lab_categorization_and_aggregation.py")
        
        logger.info("\n4. General fixes:")
        logger.info("   - Check worker process status: python backend/aggregation/reset_nutrition_aggregation.py (option 2)")
        logger.info("   - View system status: python backend/aggregation/lab_system_status.py")
        logger.info("   - Monitor aggregation: python backend/aggregation/smart_aggregation_monitor.py")
        
        return {
            "no_test_code_count": no_test_code_count,
            "with_test_code_pending_count": with_test_code_pending_count,
            "orphaned_count": orphaned_count,
            "total_pending": sum(row.count for row in categorized_status if row.aggregation_status == 'pending')
        }
        
    except Exception as e:
        logger.error(f"❌ Error in diagnosis: {e}")
        return None
    finally:
        db.close()

def fix_test_codes_for_pending():
    """Fix test_codes for pending tests that don't have them"""
    logger.info("🔧 Fixing test_codes for pending tests...")
    
    # Setup database
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Get pending tests without test_code
        pending_no_test_code = db.execute(text("""
            SELECT DISTINCT test_name, test_category, inferred_test_category, COUNT(*) as count
            FROM lab_report_categorized
            WHERE aggregation_status = 'pending' AND test_code IS NULL
            GROUP BY test_name, test_category, inferred_test_category
            ORDER BY count DESC
        """)).fetchall()
        
        if not pending_no_test_code:
            logger.info("✅ No pending tests without test_code found")
            return
        
        logger.info(f"🔧 Found {len(pending_no_test_code)} unique test types without test_code")
        
        fixed_count = 0
        for test in pending_no_test_code:
            # Generate a test_code based on the test name
            test_code = test.test_name.upper().replace(' ', '_').replace('(', '').replace(')', '')[:50]
            
            # Update all records with this test_name
            result = db.execute(text("""
                UPDATE lab_report_categorized
                SET test_code = :test_code, updated_at = :updated_at
                WHERE test_name = :test_name AND test_code IS NULL AND aggregation_status = 'pending'
            """), {
                "test_code": test_code,
                "test_name": test.test_name,
                "updated_at": datetime.utcnow()
            })
            
            updated_count = result.rowcount
            if updated_count > 0:
                logger.info(f"✅ Fixed {updated_count} records for '{test.test_name}' -> test_code: '{test_code}'")
                fixed_count += updated_count
        
        db.commit()
        logger.info(f"🎉 Fixed test_codes for {fixed_count} total records")
        
        return fixed_count
        
    except Exception as e:
        logger.error(f"❌ Error fixing test_codes: {e}")
        db.rollback()
        return 0
    finally:
        db.close()

def main():
    """Main function with menu options"""
    print("🔍 Lab Test Pending Status Diagnostic Tool")
    print("=" * 50)
    print("1. Diagnose pending status issues")
    print("2. Fix test_codes for pending tests")
    print("3. Run diagnosis and fix automatically")
    print("4. Exit")
    print("=" * 50)
    
    while True:
        try:
            choice = input("Select option (1-4): ").strip()
            
            if choice == "1":
                print("\n🔍 Running diagnosis...")
                result = diagnose_pending_status()
                if result:
                    print(f"\n📊 Summary:")
                    print(f"   Tests without test_code: {result['no_test_code_count']}")
                    print(f"   Tests with test_code but pending: {result['with_test_code_pending_count']}")
                    print(f"   Orphaned records: {result['orphaned_count']}")
                    print(f"   Total pending: {result['total_pending']}")
                print()
                
            elif choice == "2":
                print("\n🔧 Fixing test_codes...")
                fixed_count = fix_test_codes_for_pending()
                if fixed_count > 0:
                    print(f"✅ Fixed {fixed_count} records")
                    print("💡 Now run the worker process to process the fixed records:")
                    print("   python backend/aggregation/worker_process.py")
                print()
                
            elif choice == "3":
                print("\n🔍 Running diagnosis and fix...")
                result = diagnose_pending_status()
                if result and result['no_test_code_count'] > 0:
                    print("\n🔧 Auto-fixing test_codes...")
                    fixed_count = fix_test_codes_for_pending()
                    if fixed_count > 0:
                        print(f"✅ Fixed {fixed_count} records")
                        print("💡 Now run the worker process to process the fixed records:")
                        print("   python backend/aggregation/worker_process.py")
                print()
                
            elif choice == "4":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid option. Please select 1-4.\n")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    main() 