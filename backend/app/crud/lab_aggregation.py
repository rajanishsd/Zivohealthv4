#!/usr/bin/env python3
"""
Lab Aggregation CRUD Operations

This module handles the aggregation of lab report data into daily, monthly,
quarterly, and yearly summaries for efficient querying and analysis.
"""

import re
import logging
from datetime import datetime, date
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.health_data import LabReportCategorized
from app.models.lab_aggregation import LabReportDaily

logger = logging.getLogger(__name__)


class LabAggregationCRUD:
    """CRUD operations for lab data aggregation"""

    @staticmethod
    def aggregate_daily_data(db: Session, user_id: int = None, target_date: date = None, 
                           categorized_reports: List[LabReportCategorized] = None) -> int:
        """
        Unified function to aggregate lab data for daily summaries.
        
        Can be used in two modes:
        1. Real-time mode: Provide user_id and target_date for specific user/date aggregation
        2. Batch mode: Provide categorized_reports list for batch processing of pending reports
        
        Args:
            db: Database session
            user_id: User ID (for real-time mode)
            target_date: Target date (for real-time mode) 
            categorized_reports: List of categorized reports (for batch mode)
            
        Returns:
            Number of records processed
        """
        try:
            processed_count = 0
            
            if categorized_reports:
                # Batch mode: Process provided categorized reports
                logger.info(f"📊 [LabAggregation] Processing {len(categorized_reports)} categorized reports in batch mode")
                
                # Group by (user_id, loinc_code, test_date) and aggregate
                daily_groups = {}
                for report in categorized_reports:
                    # Skip records without loinc_code (should not happen after migration)
                    if not report.loinc_code:
                        logger.warning(f"⚠️ [LabAggregation] Skipping report without loinc_code: {report.test_name}")
                        continue

                    # Use loinc_code as primary key
                    group_key = report.loinc_code
                    key = (report.user_id, group_key, report.test_date)
                    if key not in daily_groups:
                        daily_groups[key] = []
                    daily_groups[key].append(report)

                # Process each group
                for (user_id, group_key, test_date), reports in daily_groups.items():
                    try:
                        # Get all values for aggregation
                        numeric_values = []
                        all_values = []
                        latest_report = None

                        for report in reports:
                            all_values.append(report.test_value)
                            # Use _parse_numeric_value helper method
                            try:
                                numeric_value = LabAggregationCRUD._parse_numeric_value(report.test_value)
                                if numeric_value is not None:
                                    numeric_values.append(numeric_value)
                            except Exception as e:
                                logger.error(f"❌ [LabAggregation] Error parsing numeric value '{report.test_value}' for {group_key}: {e}")
                                continue

                            # Keep track of the most recent report for metadata
                            if latest_report is None or report.created_at > latest_report.created_at:
                                latest_report = report

                        # Calculate aggregations based on value type
                        if numeric_values and len(numeric_values) == len(all_values):
                            # All values are numeric - calculate standard aggregations
                            avg_value = str(sum(numeric_values) / len(numeric_values))
                            min_value = str(min(numeric_values))
                            max_value = str(max(numeric_values))
                        elif len(all_values) == 1:
                            # Single value (numeric or non-numeric) - preserve as string
                            single_val = str(all_values[0])
                            avg_value = single_val
                            min_value = single_val
                            max_value = single_val
                        else:
                            # Multiple values with mix of numeric/non-numeric - store all values
                            unique_values = list(set(str(v) for v in all_values))
                            if len(unique_values) == 1:
                                # All values are the same
                                single_val = unique_values[0]
                                avg_value = single_val
                                min_value = single_val
                                max_value = single_val
                            else:
                                # Different values - store them in the fields
                                values_str = ", ".join(unique_values)
                                avg_value = values_str[:100]  # Limit length for database
                                min_value = min(unique_values, key=len)[:100]  # Shortest value
                                max_value = max(unique_values, key=len)[:100]  # Longest value

                        # Ensure we have a latest report to work with
                        if not latest_report:
                            logger.warning(f"⚠️ [LabAggregation] No valid reports found for group {group_key}")
                            continue

                        # Check if already exists (for deduplication) - use loinc_code in the query
                        existing = db.query(LabReportDaily).filter(
                            LabReportDaily.user_id == user_id,
                            LabReportDaily.loinc_code == latest_report.loinc_code,
                            LabReportDaily.date == test_date
                        ).first()

                        if existing:
                            # Update existing record
                            existing.count = len(reports)
                            existing.avg_value = avg_value
                            existing.min_value = min_value
                            existing.max_value = max_value
                            existing.unit = latest_report.test_unit
                            existing.status = latest_report.test_status
                            existing.updated_at = datetime.utcnow()
                        else:
                            # Create new daily aggregation record
                            daily_report = LabReportDaily(
                                user_id=user_id,
                                test_code=latest_report.test_code,
                                loinc_code=latest_report.loinc_code,
                                test_name=latest_report.test_name,
                                test_category=latest_report.inferred_test_category,
                                count=len(reports),
                                avg_value=avg_value,
                                min_value=min_value,
                                max_value=max_value,
                                unit=latest_report.test_unit,
                                status=latest_report.test_status,
                                date=test_date
                            )
                            db.add(daily_report)

                        processed_count += len(reports)

                    except Exception as e:
                        logger.error(f"❌ [LabAggregation] Error aggregating daily for {group_key}: {e}")
                        continue

                # Update aggregation status for all processed records
                for report in categorized_reports:
                    if report.loinc_code:  # Only update those with loinc_code (primary key)
                        db.execute(text("""
                            UPDATE lab_report_categorized
                            SET aggregation_status = 'complete', updated_at = :updated_at
                            WHERE user_id = :user_id AND loinc_code = :loinc_code
                            AND test_value = :test_value AND test_date = :test_date
                        """), {
                            "user_id": report.user_id,
                            "loinc_code": report.loinc_code,
                            "test_value": report.test_value,
                            "test_date": report.test_date,
                            "updated_at": datetime.utcnow()
                        })

                logger.info(f"✅ [LabAggregation] Aggregated {processed_count} categorized reports into daily summaries")
                
            else:
                # Real-time mode: Get data for specific user and date
                if not user_id or not target_date:
                    logger.error("❌ [LabAggregation] user_id and target_date required for real-time mode")
                    return 0
                    
                logger.info(f"📊 [LabAggregation] Processing real-time aggregation for user {user_id}, date {target_date}")
                
            # Get categorized lab data for the specific date
            lab_data_query = text("""
                SELECT
                    user_id,
                    test_date,
                    inferred_test_category,
                    test_name,
                        loinc_code,
                    test_code,
                    test_value,
                    test_unit,
                    reference_range,
                    test_status
                FROM lab_report_categorized
                WHERE user_id = :user_id
                AND test_date = :target_date
                    ORDER BY loinc_code, test_code, test_name, test_date
            """)

            result = db.execute(lab_data_query, {
                "user_id": user_id,
                "target_date": target_date
            })

            lab_records = list(result)
            if not lab_records:
                logger.info(f"ℹ️ [LabAggregation] No lab data found for user {user_id}, date {target_date}")
                return 0

                # Group by test category and loinc_code (fallback to test_code, then test_name)
            test_groups = {}
            for record in lab_records:
                category = record.inferred_test_category or "Others"
                loinc_code = record.loinc_code or None
                test_code = record.test_code or None
                test_name = record.test_name
                group_key = loinc_code or test_code or test_name.upper().replace(' ', '_')[:50]
                key = f"{category}:{group_key}"

                if key not in test_groups:
                    test_groups[key] = {
                        'category': category,
                            'loinc_code': loinc_code,
                        'test_code': test_code,
                        'test_name': test_name,
                        'values': [],
                        'units': set(),
                        'reference_ranges': set(),
                        'statuses': set()
                    }

                # Store all values and try to parse numeric value
                test_groups[key]['values'].append(record.test_value)
                numeric_value = LabAggregationCRUD._parse_numeric_value(record.test_value)
                if numeric_value is not None:
                    if 'numeric_values' not in test_groups[key]:
                        test_groups[key]['numeric_values'] = []
                    test_groups[key]['numeric_values'].append(numeric_value)

                if record.test_unit:
                    test_groups[key]['units'].add(record.test_unit)
                if record.reference_range:
                    test_groups[key]['reference_ranges'].add(record.reference_range)
                if record.test_status:
                    test_groups[key]['statuses'].add(record.test_status)

            # Create aggregated records
            for key, group in test_groups.items():
                try:
                    # Calculate statistics based on value type
                    all_values = group['values']
                    numeric_values = group.get('numeric_values', [])
                    
                    if numeric_values and len(numeric_values) == len(all_values):
                        # All values are numeric - calculate standard aggregations
                        avg_value = sum(numeric_values) / len(numeric_values)
                        min_value = min(numeric_values)
                        max_value = max(numeric_values)
                    elif len(all_values) == 1:
                        # Single value (numeric or non-numeric) - preserve as string
                        single_val = str(all_values[0])
                        avg_value = single_val
                        min_value = single_val
                        max_value = single_val
                    elif all_values:
                        # Multiple values with mix of numeric/non-numeric - store all values
                        unique_values = list(set(str(v) for v in all_values))
                        if len(unique_values) == 1:
                            # All values are the same
                            single_val = unique_values[0]
                            avg_value = single_val
                            min_value = single_val
                            max_value = single_val
                        else:
                            # Different values - store them in the fields
                            values_str = ", ".join(unique_values)
                            avg_value = values_str[:255]  # Limit length for database
                            min_value = min(unique_values, key=len)[:255]  # Shortest value
                            max_value = max(unique_values, key=len)[:255]  # Longest value
                    else:
                        avg_value = min_value = max_value = None

                    # Determine the most common unit and status
                    unit = next(iter(group['units'])) if group['units'] else None
                    status = LabAggregationCRUD._determine_status(group['statuses'])

                    # Parse normal range
                    normal_range_min, normal_range_max = LabAggregationCRUD._parse_reference_ranges(
                        group["reference_ranges"])

                    # Insert or update aggregated record
                    upsert_query = text("""
                        INSERT INTO lab_reports_daily (
                                user_id, date, test_category, loinc_code, test_code, test_name,
                            avg_value, min_value, max_value, count,
                            unit, normal_range_min, normal_range_max, status,
                            created_at, updated_at
                        ) VALUES (
                                :user_id, :date, :test_category, :loinc_code, :test_code, :test_name,
                            :avg_value, :min_value, :max_value, :count,
                            :unit, :normal_range_min, :normal_range_max, :status,
                            :created_at, :updated_at
                        )
                            ON CONFLICT (user_id, date, test_category, loinc_code)
                        DO UPDATE SET
                                test_code = EXCLUDED.test_code,
                            test_name = EXCLUDED.test_name,
                            avg_value = EXCLUDED.avg_value,
                            min_value = EXCLUDED.min_value,
                            max_value = EXCLUDED.max_value,
                            count = EXCLUDED.count,
                            unit = EXCLUDED.unit,
                            normal_range_min = EXCLUDED.normal_range_min,
                            normal_range_max = EXCLUDED.normal_range_max,
                            status = EXCLUDED.status,
                            updated_at = EXCLUDED.updated_at
                    """)

                    db.execute(upsert_query, {
                        "user_id": user_id,
                        "date": target_date,
                        "test_category": group['category'],
                            "loinc_code": group['loinc_code'],
                        "test_code": group['test_code'],
                        "test_name": group['test_name'],
                        "avg_value": avg_value,
                        "min_value": min_value,
                        "max_value": max_value,
                        "count": len(all_values) if all_values else 1,
                        "unit": unit,
                        "normal_range_min": normal_range_min,
                        "normal_range_max": normal_range_max,
                        "status": status,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    })

                    processed_count += 1

                except Exception as e:
                    logger.error(f"❌ [LabAggregation] Error aggregating daily for {group['loinc_code'] or group['test_code']}: {e}")
                    continue

                logger.info(f"✅ [LabAggregation] Created {processed_count} daily aggregates for user {user_id}, date {target_date}")

            db.commit()
            return processed_count

        except Exception as e:
            logger.error(f"❌ [LabAggregation] Error in daily aggregation: {e}")
            db.rollback()
            return 0

    @staticmethod
    def aggregate_monthly_data(db: Session, user_id: int, year: int, month: int) -> int:
        """Aggregate lab data for a specific month"""
        try:
            # Get daily records for the month
            daily_query = text("""
                SELECT
                    test_category,
                    loinc_code,
                    test_code,
                    test_name,
                    avg_value,
                    min_value,
                    max_value,
                    count,
                    unit,
                    normal_range_min,
                    normal_range_max
                FROM lab_reports_daily
                WHERE user_id = :user_id
                AND EXTRACT(YEAR FROM date) = :year
                AND EXTRACT(MONTH FROM date) = :month
                ORDER BY test_category, loinc_code, test_code, test_name
            """)

            result = db.execute(daily_query, {
                "user_id": user_id,
                "year": year,
                "month": month
            })

            daily_records = list(result)
            if not daily_records:
                return 0

            # Group by test category and loinc_code
            monthly_groups = {}
            for record in daily_records:
                key = (record.test_category, record.loinc_code, record.test_code, record.test_name, record.unit)
                if key not in monthly_groups:
                    monthly_groups[key] = []
                monthly_groups[key].append(record)

            aggregated_count = 0
            for key, records in monthly_groups.items():
                test_category, loinc_code, test_code, test_name, unit = key
                
                try:
                    # Collect all values for aggregation
                    all_avg_values = []
                    all_min_values = []
                    all_max_values = []
                    total_count = 0
                    normal_ranges = []

                    for record in records:
                        all_avg_values.append(record.avg_value)
                        all_min_values.append(record.min_value)
                        all_max_values.append(record.max_value)
                        total_count += record.count
                        if record.normal_range_min is not None and record.normal_range_max is not None:
                            normal_ranges.append((record.normal_range_min, record.normal_range_max))

                    # Determine if all values are numeric
                    numeric_avg_values = []
                    numeric_min_values = []
                    numeric_max_values = []
                    
                    for val in all_avg_values:
                        try:
                            numeric_avg_values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                    
                    for val in all_min_values:
                        try:
                            numeric_min_values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                    
                    for val in all_max_values:
                        try:
                            numeric_max_values.append(float(val))
                        except (ValueError, TypeError):
                            pass

                    # Calculate aggregated values
                    if (len(numeric_avg_values) == len(all_avg_values) and 
                        len(numeric_min_values) == len(all_min_values) and 
                        len(numeric_max_values) == len(all_max_values)):
                        # All values are numeric - calculate proper aggregations
                        avg_value = str(sum(numeric_avg_values) / len(numeric_avg_values))
                        min_value = str(min(numeric_min_values))
                        max_value = str(max(numeric_max_values))
                    else:
                        # Mixed or non-numeric values - store all unique values
                        unique_avg = list(set(str(v) for v in all_avg_values))
                        unique_min = list(set(str(v) for v in all_min_values))
                        unique_max = list(set(str(v) for v in all_max_values))
                        
                        avg_value = ", ".join(unique_avg)[:100]
                        min_value = ", ".join(unique_min)[:100]
                        max_value = ", ".join(unique_max)[:100]

                    # Calculate average normal ranges
                    avg_normal_range_min = None
                    avg_normal_range_max = None
                    if normal_ranges:
                        avg_normal_range_min = sum(r[0] for r in normal_ranges) / len(normal_ranges)
                        avg_normal_range_max = sum(r[1] for r in normal_ranges) / len(normal_ranges)

                    # Determine status
                    status = LabAggregationCRUD._calculate_aggregated_status(
                        avg_value, avg_normal_range_min, avg_normal_range_max
                    )

                    # Insert or update monthly record
                    upsert_query = text("""
                        INSERT INTO lab_reports_monthly (
                            user_id, year, month, test_category, loinc_code, test_code, test_name,
                            avg_value, min_value, max_value, count,
                            unit, normal_range_min, normal_range_max, status,
                            created_at, updated_at
                        ) VALUES (
                            :user_id, :year, :month, :test_category, :loinc_code, :test_code, :test_name,
                            :avg_value, :min_value, :max_value, :count,
                            :unit, :normal_range_min, :normal_range_max, :status,
                            :created_at, :updated_at
                        )
                        ON CONFLICT (user_id, year, month, test_category, loinc_code)
                        DO UPDATE SET
                            test_code = EXCLUDED.test_code,
                            test_name = EXCLUDED.test_name,
                            avg_value = EXCLUDED.avg_value,
                            min_value = EXCLUDED.min_value,
                            max_value = EXCLUDED.max_value,
                            count = EXCLUDED.count,
                            unit = EXCLUDED.unit,
                            normal_range_min = EXCLUDED.normal_range_min,
                            normal_range_max = EXCLUDED.normal_range_max,
                            status = EXCLUDED.status,
                            updated_at = EXCLUDED.updated_at
                    """)

                    db.execute(upsert_query, {
                        "user_id": user_id,
                        "year": year,
                        "month": month,
                        "test_category": test_category,
                        "loinc_code": loinc_code,
                        "test_code": test_code,
                        "test_name": test_name,
                        "avg_value": avg_value,
                        "min_value": min_value,
                        "max_value": max_value,
                        "count": total_count,
                        "unit": unit,
                        "normal_range_min": avg_normal_range_min,
                        "normal_range_max": avg_normal_range_max,
                        "status": status,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    })

                    aggregated_count += 1

                except Exception as e:
                    logger.error(f"❌ [LabAggregation] Error aggregating monthly for {test_code}: {e}")
                    continue

            db.commit()
            return aggregated_count

        except Exception as e:
            logger.error(f"❌ [LabAggregation] Error in monthly aggregation: {e}")
            return 0

    @staticmethod
    def aggregate_quarterly_data(db: Session, user_id: int, year: int, quarter: int) -> int:
        """Aggregate lab data for a specific quarter"""
        try:
            # Calculate month range for quarter
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3

            # Get monthly records for the quarter
            monthly_query = text("""
                SELECT
                    test_category,
                    loinc_code,
                    test_code,
                    test_name,
                    avg_value,
                    min_value,
                    max_value,
                    count,
                    unit,
                    normal_range_min,
                    normal_range_max
                FROM lab_reports_monthly
                WHERE user_id = :user_id
                AND year = :year
                AND month >= :start_month
                AND month <= :end_month
                ORDER BY test_category, loinc_code, test_code, test_name
            """)

            result = db.execute(monthly_query, {
                "user_id": user_id,
                "year": year,
                "start_month": start_month,
                "end_month": end_month
            })

            monthly_records = list(result)
            if not monthly_records:
                return 0

            # Group by test category and loinc_code
            quarterly_groups = {}
            for record in monthly_records:
                key = (record.test_category, record.loinc_code, record.test_code, record.test_name, record.unit)
                if key not in quarterly_groups:
                    quarterly_groups[key] = []
                quarterly_groups[key].append(record)

            aggregated_count = 0
            for key, records in quarterly_groups.items():
                test_category, loinc_code, test_code, test_name, unit = key
                
                try:
                    # Collect all values for aggregation
                    all_avg_values = []
                    all_min_values = []
                    all_max_values = []
                    total_count = 0
                    normal_ranges = []

                    for record in records:
                        all_avg_values.append(record.avg_value)
                        all_min_values.append(record.min_value)
                        all_max_values.append(record.max_value)
                        total_count += record.count
                        if record.normal_range_min is not None and record.normal_range_max is not None:
                            normal_ranges.append((record.normal_range_min, record.normal_range_max))

                    # Determine if all values are numeric
                    numeric_avg_values = []
                    numeric_min_values = []
                    numeric_max_values = []
                    
                    for val in all_avg_values:
                        try:
                            numeric_avg_values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                    
                    for val in all_min_values:
                        try:
                            numeric_min_values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                    
                    for val in all_max_values:
                        try:
                            numeric_max_values.append(float(val))
                        except (ValueError, TypeError):
                            pass

                    # Calculate aggregated values
                    if (len(numeric_avg_values) == len(all_avg_values) and 
                        len(numeric_min_values) == len(all_min_values) and 
                        len(numeric_max_values) == len(all_max_values)):
                        # All values are numeric - calculate proper aggregations
                        avg_value = str(sum(numeric_avg_values) / len(numeric_avg_values))
                        min_value = str(min(numeric_min_values))
                        max_value = str(max(numeric_max_values))
                    else:
                        # Mixed or non-numeric values - store all unique values
                        unique_avg = list(set(str(v) for v in all_avg_values))
                        unique_min = list(set(str(v) for v in all_min_values))
                        unique_max = list(set(str(v) for v in all_max_values))
                        
                        avg_value = ", ".join(unique_avg)[:100]
                        min_value = ", ".join(unique_min)[:100]
                        max_value = ", ".join(unique_max)[:100]

                    # Calculate average normal ranges
                    avg_normal_range_min = None
                    avg_normal_range_max = None
                    if normal_ranges:
                        avg_normal_range_min = sum(r[0] for r in normal_ranges) / len(normal_ranges)
                        avg_normal_range_max = sum(r[1] for r in normal_ranges) / len(normal_ranges)

                    # Determine status
                    status = LabAggregationCRUD._calculate_aggregated_status(
                        avg_value, avg_normal_range_min, avg_normal_range_max
                    )

                    # Insert or update quarterly record
                    upsert_query = text("""
                        INSERT INTO lab_reports_quarterly (
                            user_id, year, quarter, test_category, loinc_code, test_code, test_name,
                            avg_value, min_value, max_value, count,
                            unit, normal_range_min, normal_range_max, status,
                            created_at, updated_at
                        ) VALUES (
                            :user_id, :year, :quarter, :test_category, :loinc_code, :test_code, :test_name,
                            :avg_value, :min_value, :max_value, :count,
                            :unit, :normal_range_min, :normal_range_max, :status,
                            :created_at, :updated_at
                        )
                        ON CONFLICT (user_id, year, quarter, test_category, loinc_code)
                        DO UPDATE SET
                            test_code = EXCLUDED.test_code,
                            test_name = EXCLUDED.test_name,
                            avg_value = EXCLUDED.avg_value,
                            min_value = EXCLUDED.min_value,
                            max_value = EXCLUDED.max_value,
                            count = EXCLUDED.count,
                            unit = EXCLUDED.unit,
                            normal_range_min = EXCLUDED.normal_range_min,
                            normal_range_max = EXCLUDED.normal_range_max,
                            status = EXCLUDED.status,
                            updated_at = EXCLUDED.updated_at
                    """)

                    db.execute(upsert_query, {
                        "user_id": user_id,
                        "year": year,
                        "quarter": quarter,
                        "test_category": test_category,
                        "loinc_code": loinc_code,
                        "test_code": test_code,
                        "test_name": test_name,
                        "avg_value": avg_value,
                        "min_value": min_value,
                        "max_value": max_value,
                        "count": total_count,
                        "unit": unit,
                        "normal_range_min": avg_normal_range_min,
                        "normal_range_max": avg_normal_range_max,
                        "status": status,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    })

                    aggregated_count += 1

                except Exception as e:
                    logger.error(f"❌ [LabAggregation] Error aggregating quarterly for {test_code}: {e}")
                    continue

            db.commit()
            return aggregated_count

        except Exception as e:
            logger.error(f"❌ [LabAggregation] Error in quarterly aggregation: {e}")
            return 0

    @staticmethod
    def aggregate_yearly_data(db: Session, user_id: int, year: int) -> int:
        """Aggregate lab data for a specific year"""
        try:
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)

            # Get daily records for the year
            daily_query = text("""
                SELECT
                    test_category,
                    loinc_code,
                    test_code,
                    test_name,
                    avg_value,
                    min_value,
                    max_value,
                    count,
                    unit,
                    normal_range_min,
                    normal_range_max
                FROM lab_reports_daily
                WHERE user_id = :user_id
                AND date >= :year_start
                AND date <= :year_end
                ORDER BY test_category, loinc_code, test_code, test_name
            """)

            result = db.execute(daily_query, {
                "user_id": user_id,
                "year_start": year_start,
                "year_end": year_end
            })

            daily_records = list(result)
            if not daily_records:
                return 0

            # Group by test category and loinc_code
            yearly_groups = {}
            for record in daily_records:
                key = (record.test_category, record.loinc_code, record.test_code, record.test_name, record.unit)
                if key not in yearly_groups:
                    yearly_groups[key] = []
                yearly_groups[key].append(record)

            aggregated_count = 0
            for key, records in yearly_groups.items():
                test_category, loinc_code, test_code, test_name, unit = key
                
                try:
                    # Collect all values for aggregation
                    all_avg_values = []
                    all_min_values = []
                    all_max_values = []
                    total_count = 0
                    normal_ranges = []

                    for record in records:
                        all_avg_values.append(record.avg_value)
                        all_min_values.append(record.min_value)
                        all_max_values.append(record.max_value)
                        total_count += record.count
                        if record.normal_range_min is not None and record.normal_range_max is not None:
                            normal_ranges.append((record.normal_range_min, record.normal_range_max))

                    # Determine if all values are numeric
                    numeric_avg_values = []
                    numeric_min_values = []
                    numeric_max_values = []
                    
                    for val in all_avg_values:
                        try:
                            numeric_avg_values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                    
                    for val in all_min_values:
                        try:
                            numeric_min_values.append(float(val))
                        except (ValueError, TypeError):
                            pass
                    
                    for val in all_max_values:
                        try:
                            numeric_max_values.append(float(val))
                        except (ValueError, TypeError):
                            pass

                    # Calculate aggregated values
                    if (len(numeric_avg_values) == len(all_avg_values) and 
                        len(numeric_min_values) == len(all_min_values) and 
                        len(numeric_max_values) == len(all_max_values)):
                        # All values are numeric - calculate proper aggregations
                        avg_value = str(sum(numeric_avg_values) / len(numeric_avg_values))
                        min_value = str(min(numeric_min_values))
                        max_value = str(max(numeric_max_values))
                    else:
                        # Mixed or non-numeric values - store all unique values
                        unique_avg = list(set(str(v) for v in all_avg_values))
                        unique_min = list(set(str(v) for v in all_min_values))
                        unique_max = list(set(str(v) for v in all_max_values))
                        
                        avg_value = ", ".join(unique_avg)[:100]
                        min_value = ", ".join(unique_min)[:100]
                        max_value = ", ".join(unique_max)[:100]

                    # Calculate average normal ranges
                    avg_normal_range_min = None
                    avg_normal_range_max = None
                    if normal_ranges:
                        avg_normal_range_min = sum(r[0] for r in normal_ranges) / len(normal_ranges)
                        avg_normal_range_max = sum(r[1] for r in normal_ranges) / len(normal_ranges)

                    # Determine status
                    status = LabAggregationCRUD._calculate_aggregated_status(
                        avg_value, avg_normal_range_min, avg_normal_range_max
                    )

                    # Insert or update yearly record
                    upsert_query = text("""
                        INSERT INTO lab_reports_yearly (
                            user_id, year, test_category, loinc_code, test_code, test_name,
                            avg_value, min_value, max_value, count,
                            unit, normal_range_min, normal_range_max, status,
                            created_at, updated_at
                        ) VALUES (
                            :user_id, :year, :test_category, :loinc_code, :test_code, :test_name,
                            :avg_value, :min_value, :max_value, :count,
                            :unit, :normal_range_min, :normal_range_max, :status,
                            :created_at, :updated_at
                        )
                        ON CONFLICT (user_id, year, test_category, loinc_code)
                        DO UPDATE SET
                            test_code = EXCLUDED.test_code,
                            test_name = EXCLUDED.test_name,
                            avg_value = EXCLUDED.avg_value,
                            min_value = EXCLUDED.min_value,
                            max_value = EXCLUDED.max_value,
                            count = EXCLUDED.count,
                            unit = EXCLUDED.unit,
                            normal_range_min = EXCLUDED.normal_range_min,
                            normal_range_max = EXCLUDED.normal_range_max,
                            status = EXCLUDED.status,
                            updated_at = EXCLUDED.updated_at
                    """)

                    db.execute(upsert_query, {
                        "user_id": user_id,
                        "year": year,
                        "test_category": test_category,
                        "loinc_code": loinc_code,
                        "test_code": test_code,
                        "test_name": test_name,
                        "avg_value": avg_value,
                        "min_value": min_value,
                        "max_value": max_value,
                        "count": total_count,
                        "unit": unit,
                        "normal_range_min": avg_normal_range_min,
                        "normal_range_max": avg_normal_range_max,
                        "status": status,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    })

                    aggregated_count += 1

                except Exception as e:
                    logger.error(f"❌ [LabAggregation] Error aggregating yearly for {test_code}: {e}")
                    continue

            db.commit()
            return aggregated_count

        except Exception as e:
            logger.error(f"❌ [LabAggregation] Error in yearly aggregation: {e}")
            return 0

    @staticmethod
    def _parse_reference_ranges(reference_ranges: set) -> Tuple[Optional[float], Optional[float]]:
        """Parse reference ranges to extract min and max values"""
        if not reference_ranges:
            return None, None

        for ref_range in reference_ranges:
            if not ref_range:
                continue

            try:
                # Parse reference range patterns like "10-20", ">10", "<20", "10.5-15.2"
                if '-' in ref_range and not ref_range.startswith('<') and not ref_range.startswith('>'):
                    # Range format: "10-20"
                    parts = ref_range.split('-')
                    if len(parts) == 2:
                        min_val = float(re.sub(r'[^\d\.\-]', '', parts[0]))
                        max_val = float(re.sub(r'[^\d\.\-]', '', parts[1]))
                        return min_val, max_val

                elif ref_range.startswith('>'):
                    # Greater than format: ">10"
                    threshold = float(re.sub(r'[^\d\.\-]', '', ref_range[1:]))
                    return threshold, None

                elif ref_range.startswith('<'):
                    # Less than format: "<20"
                    threshold = float(re.sub(r'[^\d\.\-]', '', ref_range[1:]))
                    return None, threshold

            except (ValueError, IndexError):
                continue

        return None, None

    @staticmethod
    def _parse_numeric_value(value_str: str) -> Optional[float]:
        """Parse numeric value from string, handling various formats including mixed text-number patterns"""
        if not value_str:
            return None

        try:
            value_str = str(value_str).strip()
            
            # First try direct conversion for simple numeric values
            try:
                return float(value_str)
            except ValueError:
                pass
            
            # Use regex to find floating point numbers in the string
            # Pattern matches: optional minus, digits, optional decimal point and more digits
            # Examples: "123", "123.45", "-45.67", "0.123"
            float_pattern = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
            matches = re.findall(float_pattern, value_str)
            
            if matches:
                # Take the first numeric value found
                for match in matches:
                    try:
                        # Additional validation - ensure it's a reasonable number
                        num_value = float(match)
                        # Skip extremely large or small values that might be artifacts
                        if abs(num_value) < 1e15:  # Reasonable upper bound
                            return num_value
                    except ValueError:
                        continue
            
            # Fallback: try to extract just digits and decimal points
            cleaned = re.sub(r'[^\d\.\-\+]', '', value_str)
            if cleaned and cleaned not in ['.', '-', '+', '-.', '+.']:
                # Ensure we don't have multiple decimal points
                if cleaned.count('.') <= 1:
                    return float(cleaned)
                        
        except (ValueError, TypeError):
            pass

        return None

    @staticmethod
    def _determine_status(statuses: set) -> str:
        """Determine test status based on statuses"""
        if not statuses:
            return "amber"  # No status available

        status = "amber"  # Default
        for s in statuses:
            if s == "green":
                status = "green"
                break
            elif s == "red":
                status = "red"

        return status

    @staticmethod
    def _calculate_aggregated_status(avg_value, normal_range_min: float, normal_range_max: float) -> str:
        """Calculate aggregated status based on average value and normal ranges"""
        # Handle string values - return amber status for non-numeric values
        if isinstance(avg_value, str):
            return "amber"  # Non-numeric values get amber status
            
        # Handle numeric values
        if normal_range_min is not None and normal_range_max is not None:
            if normal_range_min <= avg_value <= normal_range_max:
                return "green"
            else:
                return "red"
        else:
            return "amber"  # No normal range available

    @staticmethod
    def get_pending_aggregation_entries(db: Session, limit: int = 5000) -> List[LabReportCategorized]:
        """Get categorized lab reports that need aggregation processing using status column"""
        try:
            # Get categorized lab reports with aggregation_status = 'pending'
            categorized_reports = db.query(LabReportCategorized).filter(
                LabReportCategorized.aggregation_status == 'pending'
            ).order_by(LabReportCategorized.created_at.asc()).limit(limit).all()

            logger.debug(f"📋 [LabAggregation] Found {len(categorized_reports)} "
                         f"pending categorized reports for aggregation")
            return categorized_reports

        except Exception as e:
            logger.error(f"❌ [LabAggregation] Error getting pending aggregation entries: {e}")
            return []

    @staticmethod
    def aggregate_daily_records(db: Session, categorized_reports: List[LabReportCategorized]) -> int:
        """Alias for aggregate_daily_data in batch mode for backward compatibility"""
        return LabAggregationCRUD.aggregate_daily_data(db, categorized_reports=categorized_reports)


# Instance for external use
lab_aggregation = LabAggregationCRUD()

