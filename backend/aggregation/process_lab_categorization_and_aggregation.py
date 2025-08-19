#!/usr/bin/env python3
"""
Lab Categorization and Aggregation Processing Script

This script processes lab reports by:
1. Processing pending lab reports based on categorization_status column
2. Using fuzzy matching to categorize test names with lab_test_mappings
3. Creating new mappings with 'Others' category for unknown tests
4. Processing aggregation based on aggregation_status column
5. Triggering aggregation functions for daily, monthly, quarterly, and yearly data

Run this script after lab report uploads to process the data for aggregation.
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
    print("   python backend/aggregation/process_lab_categorization_and_aggregation.py")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_lab_categorization_and_aggregation():
    """Main function to process lab categorization and aggregation with status tracking"""
    logger.info("🔬 Starting lab categorization and aggregation processing with status tracking...")

    # Setup database
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    categorization_processed = 0
    daily_aggregation_processed = 0

    try:
        # Step 1: Process Lab Categorization using status column
        logger.info("📊 Phase 1: Processing Lab Report Categorization...")
        pending_reports = LabCategorizationCRUD.get_pending_categorization_entries(db, limit=1000)

        if pending_reports:
            logger.info(f"Found {len(pending_reports)} lab reports pending categorization")
            categorization_processed = LabCategorizationCRUD.categorize_and_transfer_lab_reports(db, pending_reports)
            logger.info(f"✅ Categorized {categorization_processed} lab reports")
        else:
            logger.info("✅ No lab reports pending categorization")

        # Step 2: Process Daily Aggregations using status column
        logger.info("📈 Phase 2: Processing Daily Aggregations...")
        pending_categorized_reports = LabAggregationCRUD.get_pending_aggregation_entries(db, limit=5000)

        if pending_categorized_reports:
            logger.info(f"Found {len(pending_categorized_reports)} categorized reports pending aggregation")
            daily_aggregation_processed = LabAggregationCRUD.aggregate_daily_records(db, pending_categorized_reports)
            logger.info(f"✅ Aggregated {daily_aggregation_processed} reports into daily summaries")
        else:
            logger.info("✅ No categorized reports pending aggregation")

        # Step 3: Process Monthly, Quarterly, and Yearly Aggregations
        logger.info("📅 Phase 3: Processing Higher-Level Aggregations...")
        monthly_processed = 0
        quarterly_processed = 0
        yearly_processed = 0

        # Get unique user IDs and date ranges from daily aggregations to process higher-level aggregations
        if daily_aggregation_processed > 0 or True:  # Always try to process existing daily data
            # Get unique users and date ranges from daily data for monthly aggregation
            user_date_ranges = db.execute(text("""
                SELECT DISTINCT
                    user_id,
                    EXTRACT(YEAR FROM date) as year,
                    EXTRACT(MONTH FROM date) as month,
                    EXTRACT(QUARTER FROM date) as quarter
                FROM lab_reports_daily
                ORDER BY user_id, year, month
            """)).fetchall()

            if user_date_ranges:
                logger.info(f"Found {len(user_date_ranges)} daily date combinations for higher-level aggregation")

                # Track processed combinations to avoid duplicates
                processed_monthly = set()
                processed_quarterly = set()
                processed_yearly = set()

                # Process monthly aggregations from daily data
                for row in user_date_ranges:
                    user_id = int(row.user_id)
                    year = int(row.year)
                    month = int(row.month)

                    try:
                        # Process Monthly Aggregation
                        monthly_key = (user_id, year, month)
                        if monthly_key not in processed_monthly:
                            monthly_count = LabAggregationCRUD.aggregate_monthly_data(db, user_id, year, month)
                            if monthly_count > 0:
                                monthly_processed += monthly_count
                                logger.debug(f"📅 Monthly: Processed {monthly_count} records for "
                                             f"user {user_id}, {year}-{month:02d}")
                            processed_monthly.add(monthly_key)

                        # Process Yearly Aggregation
                        yearly_key = (user_id, year)
                        if yearly_key not in processed_yearly:
                            yearly_count = LabAggregationCRUD.aggregate_yearly_data(db, user_id, year)
                            if yearly_count > 0:
                                yearly_processed += yearly_count
                                logger.debug(f"📅 Yearly: Processed {yearly_count} records for "
                                             f"user {user_id}, {year}")
                            processed_yearly.add(yearly_key)

                    except Exception as e:
                        logger.error(f"❌ Error processing monthly/yearly aggregations for "
                                     f"user {user_id}, {year}-{month:02d}: {e}")
                        continue

                # Now process quarterly aggregations from ALL monthly data (after monthly processing is complete)
                # This query runs after monthly inserts, so it can see all monthly data including newly inserted records
                quarterly_ranges = db.execute(text("""
                    SELECT DISTINCT
                        user_id,
                        year,
                        CASE 
                            WHEN month IN (1,2,3) THEN 1
                            WHEN month IN (4,5,6) THEN 2
                            WHEN month IN (7,8,9) THEN 3
                            WHEN month IN (10,11,12) THEN 4
                        END as quarter
                    FROM lab_reports_monthly
                    ORDER BY user_id, year, quarter
                """)).fetchall()
                
                logger.info(f"Found {len(quarterly_ranges)} quarterly combinations from monthly data")

                # Process quarterly aggregations from monthly data (ensures complete coverage)
                for row in quarterly_ranges:
                    user_id = int(row.user_id)
                    year = int(row.year)
                    quarter = int(row.quarter)

                    try:
                        # Process Quarterly Aggregation
                        quarterly_key = (user_id, year, quarter)
                        if quarterly_key not in processed_quarterly:
                            # Always re-run quarterly aggregation to ensure it includes all monthly data
                            # This handles cases where quarterly was run before all monthly data was complete
                            quarterly_count = LabAggregationCRUD.aggregate_quarterly_data(db, user_id, year, quarter)
                            if quarterly_count > 0:
                                quarterly_processed += quarterly_count
                                logger.debug(f"📅 Quarterly: Processed {quarterly_count} records for "
                                             f"user {user_id}, {year}-Q{quarter}")
                            processed_quarterly.add(quarterly_key)

                    except Exception as e:
                        logger.error(f"❌ Error processing quarterly aggregation for "
                                     f"user {user_id}, {year}-Q{quarter}: {e}")
                        continue

                logger.info("✅ Higher-level aggregations complete:")
                logger.info(f"   📅 Monthly: {monthly_processed} records")
                logger.info(f"   📅 Quarterly: {quarterly_processed} records")
                logger.info(f"   📅 Yearly: {yearly_processed} records")
            else:
                logger.info("ℹ️ No daily data found for higher-level aggregation")
        else:
            logger.info("⏭️ Skipping higher-level aggregations (no daily data processed)")

        # Final summary
        total_processed = (categorization_processed + daily_aggregation_processed +
                           monthly_processed + quarterly_processed + yearly_processed)

        logger.info("🎉 Lab Processing Complete!")
        logger.info("=" * 50)
        logger.info(f"📊 Categorization: {categorization_processed} lab reports")
        logger.info(f"📈 Daily Aggregation: {daily_aggregation_processed} records")
        logger.info(f"📅 Monthly Aggregation: {monthly_processed} records")
        logger.info(f"📅 Quarterly Aggregation: {quarterly_processed} records")
        logger.info(f"📅 Yearly Aggregation: {yearly_processed} records")
        logger.info(f"🏆 Total Records Processed: {total_processed}")
        logger.info("=" * 50)

        # Show status summary
        show_processing_status(db)

        return {
            "categorization_processed": categorization_processed,
            "daily_aggregation_processed": daily_aggregation_processed,
            "monthly_processed": monthly_processed,
            "quarterly_processed": quarterly_processed,
            "yearly_processed": yearly_processed,
            "total_processed": total_processed
        }

    except Exception as e:
        logger.error(f"❌ Error in lab processing: {e}")
        return None
    finally:
        db.close()


def show_processing_status(db: Session):
    """Show current processing status using status columns"""
    try:
        # Lab Reports Status
        categorization_status = db.execute(text("""
            SELECT categorization_status, COUNT(*) as count
            FROM lab_reports
            GROUP BY categorization_status
            ORDER BY categorization_status
        """)).fetchall()

        logger.info("📋 Lab Reports Categorization Status:")
        for row in categorization_status:
            logger.info(f"   {row.categorization_status}: {row.count} records")

        # Lab Report Categorized Status
        aggregation_status = db.execute(text("""
            SELECT aggregation_status, COUNT(*) as count
            FROM lab_report_categorized
            GROUP BY aggregation_status
            ORDER BY aggregation_status
        """)).fetchall()

        logger.info("📈 Lab Reports Aggregation Status:")
        for row in aggregation_status:
            logger.info(f"   {row.aggregation_status}: {row.count} records")

    except Exception as e:
        logger.error(f"❌ Error showing processing status: {e}")


def main():
    """Main entry point"""
    try:
        logger.info("🏥 ZivoHealth Lab Categorization and Aggregation Processor")
        logger.info(f"⏰ Started at: {datetime.now()}")

        # Run the processing function
        result = process_lab_categorization_and_aggregation()

        if result:
            logger.info("✅ Processing completed successfully")
        else:
            logger.error("❌ Processing failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("🛑 Processing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Lab processing terminated")


if __name__ == "__main__":
    main()
