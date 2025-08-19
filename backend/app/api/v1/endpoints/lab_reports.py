from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.sql import func

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.lab_test_mapping import LabTestMapping
from app.models.health_data import LabReportCategorized
from app.models.lab_aggregation import LabReportDaily, LabReportMonthly, LabReportQuarterly, LabReportYearly
from app.schemas.lab_reports import (
    LabReportCategoriesResponse, 
    LabTestCategoryResponse,
    LabCategoryDetailResponse,
    LabTestResultResponse,
    LabTestStatus
)

router = APIRouter()

@router.get("/categories", response_model=LabReportCategoriesResponse)
def get_lab_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all lab test categories with status counts"""
    
    # Get all active categories from lab_test_mappings
    categories = db.query(LabTestMapping.test_category).distinct().filter(
        LabTestMapping.is_active == True
    ).all()
    
    category_responses = []
    
    for category_tuple in categories:
        category = category_tuple[0]
        
        # Count total tests in this category from categorized table
        total_tests = db.query(LabReportCategorized).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.inferred_test_category == category
        ).distinct(LabReportCategorized.loinc_code).count()
        
        # Count status distribution from actual lab results
        green_count = db.query(LabReportCategorized).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.inferred_test_category == category,
            LabReportCategorized.test_status.in_(['Normal', 'normal'])
        ).distinct(LabReportCategorized.loinc_code).count()
        
        amber_count = db.query(LabReportCategorized).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.inferred_test_category == category,
            LabReportCategorized.test_status.in_(['High', 'Low', 'Elevated', 'high', 'low', 'elevated'])
        ).distinct(LabReportCategorized.loinc_code).count()
        
        red_count = db.query(LabReportCategorized).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.inferred_test_category == category,
            LabReportCategorized.test_status.in_(['Critical', 'Abnormal', 'critical', 'abnormal'])
        ).distinct(LabReportCategorized.loinc_code).count()
        
        # Ensure counts don't exceed total
        if total_tests == 0:
            continue
        
        category_responses.append(LabTestCategoryResponse(
            category=category,
            total_tests=total_tests,
            green_count=green_count,
            amber_count=amber_count,
            red_count=red_count
        ))
    
    return LabReportCategoriesResponse(categories=category_responses)

@router.get("/diabetes-panel")
def get_diabetes_panel_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get diabetes panel data from lab_report_categorized table"""
    
    # Define the diabetes panel tests
    diabetes_tests = [
        "Fasting Blood Sugar (FBS)",
        "Postprandial Blood Sugar (PPBS)", 
        "HbA1c",
        "Insulin (Fasting)",
        "Insulin (Post-meal)",
        "C-Peptide"
    ]
    
    test_results = []
    
    for test_name in diabetes_tests:
        # Get the test mapping info
        test_mapping = db.query(LabTestMapping).filter(
            LabTestMapping.test_name == test_name,
            LabTestMapping.is_active == True
        ).first()
        
        if not test_mapping:
            continue
            
        # Get the most recent lab report for this test and user from categorized table
        latest_report = db.query(LabReportCategorized).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.test_name == test_name
        ).order_by(desc(LabReportCategorized.test_date)).first()
        
        # Create test result
        test_result = {
            "name": test_name,
            "description": test_mapping.description or "",
            "value": latest_report.test_value if latest_report else "",
            "unit": test_mapping.common_units or "",
            "normalRange": test_mapping.normal_range_info or "",
            "status": latest_report.test_status.lower() if latest_report and latest_report.test_status else "unknown",
            "lastTested": latest_report.test_date.strftime("%B %d, %Y") if latest_report else ""
        }
        
        test_results.append(test_result)
    
    return {
        "tests": test_results,
        "category": "Diabetes Panel",
        "totalTests": len(test_results)
    }

@router.get("/liver-function-tests")
def get_liver_function_tests_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get liver function tests data from lab_report_categorized table"""
    
    # Define the LFT tests
    lft_tests = [
        "ALT (Alanine Aminotransferase)",
        "AST (Aspartate Aminotransferase)",
        "ALP (Alkaline Phosphatase)",
        "GGT (Gamma-glutamyl Transferase)",
        "Bilirubin (Total)",
        "Albumin",
        "Total Protein"
    ]
    
    test_results = []
    
    print(f"🔍 [LFT] Searching for user {current_user.id} with tests: {lft_tests}")
    
    for test_name in lft_tests:
        # Get the test mapping info
        test_mapping = db.query(LabTestMapping).filter(
            LabTestMapping.test_name == test_name,
            LabTestMapping.is_active == True
        ).first()
        
        if not test_mapping:
            print(f"⚠️ [LFT] No mapping found for test: {test_name}")
            continue
            
        # Try multiple approaches to find the data:
        # 1. By exact test name
        latest_report = db.query(LabReportCategorized).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.test_name == test_name
        ).order_by(desc(LabReportCategorized.test_date)).first()
        
        # 2. If not found, try by category
        if not latest_report:
            latest_report = db.query(LabReportCategorized).filter(
                LabReportCategorized.user_id == current_user.id,
                LabReportCategorized.inferred_test_category == "Liver Function Tests (LFT)",
                LabReportCategorized.test_name.ilike(f"%{test_name.split('(')[0].strip()}%")
            ).order_by(desc(LabReportCategorized.test_date)).first()
            
        # 3. If still not found, try partial matching on test names
        if not latest_report:
            # Extract the main part of the test name for partial matching
            main_name = test_name.split('(')[0].strip()
            latest_report = db.query(LabReportCategorized).filter(
                LabReportCategorized.user_id == current_user.id,
                LabReportCategorized.test_name.ilike(f"%{main_name}%")
            ).order_by(desc(LabReportCategorized.test_date)).first()
        
        if latest_report:
            print(f"✅ [LFT] Found data for {test_name}: {latest_report.test_value}")
        else:
            print(f"❌ [LFT] No data found for {test_name}")
        
        # Create test result
        test_result = {
            "name": test_name,
            "description": test_mapping.description or "",
            "value": latest_report.test_value if latest_report else "",
            "unit": test_mapping.common_units or "",
            "normalRange": test_mapping.normal_range_info or "",
            "status": latest_report.test_status.lower() if latest_report and latest_report.test_status else "unknown",
            "lastTested": latest_report.test_date.strftime("%B %d, %Y") if latest_report else ""
        }
        
        test_results.append(test_result)
    
    print(f"📊 [LFT] Returning {len(test_results)} test results")
    return {
        "tests": test_results,
        "category": "Liver Function Tests (LFT)",
        "totalTests": len(test_results)
    }

@router.get("/kidney-function-tests")
def get_kidney_function_tests_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get kidney function tests data from lab_report_categorized table"""
    
    # Define the KFT tests
    kft_tests = [
        "Urea",
        "Creatinine",
        "eGFR",
        "Uric Acid"
    ]
    
    test_results = []
    
    print(f"🔍 [KFT] Searching for user {current_user.id} with tests: {kft_tests}")
    
    for test_name in kft_tests:
        # Get the test mapping info
        test_mapping = db.query(LabTestMapping).filter(
            LabTestMapping.test_name == test_name,
            LabTestMapping.is_active == True
        ).first()
        
        if not test_mapping:
            print(f"⚠️ [KFT] No mapping found for test: {test_name}")
            continue
            
        # Try multiple approaches to find the data:
        # 1. By exact test name
        latest_report = db.query(LabReportCategorized).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.test_name == test_name
        ).order_by(desc(LabReportCategorized.test_date)).first()
        
        # 2. If not found, try by category
        if not latest_report:
            latest_report = db.query(LabReportCategorized).filter(
                LabReportCategorized.user_id == current_user.id,
                LabReportCategorized.inferred_test_category == "Kidney Function Tests (KFT)",
                LabReportCategorized.test_name.ilike(f"%{test_name}%")
            ).order_by(desc(LabReportCategorized.test_date)).first()
            
        # 3. If still not found, try partial matching on test names
        if not latest_report:
            latest_report = db.query(LabReportCategorized).filter(
                LabReportCategorized.user_id == current_user.id,
                LabReportCategorized.test_name.ilike(f"%{test_name}%")
            ).order_by(desc(LabReportCategorized.test_date)).first()
        
        # 4. Special cases for common variations
        if not latest_report and test_name == "Urea":
            # Try "Blood Urea Nitrogen" or "BUN"
            latest_report = db.query(LabReportCategorized).filter(
                LabReportCategorized.user_id == current_user.id,
                (LabReportCategorized.test_name.ilike("%Blood Urea Nitrogen%") |
                 LabReportCategorized.test_name.ilike("%BUN%"))
            ).order_by(desc(LabReportCategorized.test_date)).first()
            
        if not latest_report and test_name == "eGFR":
            # Try variations of eGFR
            latest_report = db.query(LabReportCategorized).filter(
                LabReportCategorized.user_id == current_user.id,
                (LabReportCategorized.test_name.ilike("%GFR%") |
                 LabReportCategorized.test_name.ilike("%glomerular%"))
            ).order_by(desc(LabReportCategorized.test_date)).first()
        
        if latest_report:
            print(f"✅ [KFT] Found data for {test_name}: {latest_report.test_value}")
        else:
            print(f"❌ [KFT] No data found for {test_name}")
        
        # Create test result
        test_result = {
            "name": test_name,
            "description": test_mapping.description or "",
            "value": latest_report.test_value if latest_report else "",
            "unit": test_mapping.common_units or "",
            "normalRange": test_mapping.normal_range_info or "",
            "status": latest_report.test_status.lower() if latest_report and latest_report.test_status else "unknown",
            "lastTested": latest_report.test_date.strftime("%B %d, %Y") if latest_report else ""
        }
        
        test_results.append(test_result)
    
    print(f"📊 [KFT] Returning {len(test_results)} test results")
    return {
        "tests": test_results,
        "category": "Kidney Function Tests (KFT)",
        "totalTests": len(test_results)
    }

@router.get("/category/{category_name}")
def get_category_details(
    category_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed view of a specific lab test category from categorized table"""
    
    # Get all categorized reports for this category and user
    categorized_reports = db.query(LabReportCategorized).filter(
        LabReportCategorized.user_id == current_user.id,
        LabReportCategorized.inferred_test_category == category_name
    ).order_by(desc(LabReportCategorized.test_date)).all()
    
    if not categorized_reports:
        raise HTTPException(status_code=404, detail="Category not found or no data available")
    
    # Create test responses from actual data
    test_responses = []
    
    for report in categorized_reports:
        # Convert status to enum
        status = LabTestStatus.GREEN
        if report.test_status and report.test_status.lower() in ['high', 'low', 'elevated']:
            status = LabTestStatus.AMBER
        elif report.test_status and report.test_status.lower() in ['critical', 'abnormal']:
            status = LabTestStatus.RED
        
        # Parse numeric value for range comparison
        try:
            numeric_value = float(report.test_value) if report.test_value else 0.0
        except (ValueError, TypeError):
            numeric_value = 0.0
        
        test_responses.append(LabTestResultResponse(
            id=report.id,
            test_name=report.test_name,
            test_category=report.inferred_test_category or category_name,
            value=numeric_value,
            unit=report.test_unit or "",
            normal_range_min=0.0,  # Would need to parse reference_range
            normal_range_max=100.0,  # Would need to parse reference_range
            status=status,
            date=report.test_date,
            created_at=report.created_at
        ))
    
    summary = {
        "total_tests": len(test_responses),
        "green_count": len([t for t in test_responses if t.status == LabTestStatus.GREEN]),
        "amber_count": len([t for t in test_responses if t.status == LabTestStatus.AMBER]),
        "red_count": len([t for t in test_responses if t.status == LabTestStatus.RED]),
    }
    
    return LabCategoryDetailResponse(
        category=category_name,
        tests=test_responses,
        summary=summary
    )

@router.get("/debug/categorized-data")
def get_debug_categorized_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to see all categorized lab data for current user"""
    
    # Get all categorized lab reports for this user
    all_reports = db.query(LabReportCategorized).filter(
        LabReportCategorized.user_id == current_user.id
    ).order_by(desc(LabReportCategorized.test_date)).all()
    
    print(f"🔍 [DEBUG] Found {len(all_reports)} categorized reports for user {current_user.id}")
    
    debug_data = []
    for report in all_reports:
        debug_data.append({
            "id": report.id,
            "test_name": report.test_name,
            "test_category": report.test_category,
            "inferred_test_category": report.inferred_test_category,
            "test_value": report.test_value,
            "test_unit": report.test_unit,
            "test_status": report.test_status,
            "test_date": report.test_date.isoformat() if report.test_date else None,
            "created_at": report.created_at.isoformat() if report.created_at else None
        })
        print(f"  - {report.test_name} | {report.inferred_test_category} | {report.test_value} {report.test_unit}")
    
    # Also show unique categories
    unique_categories = db.query(LabReportCategorized.inferred_test_category).filter(
        LabReportCategorized.user_id == current_user.id
    ).distinct().all()
    
    categories = [cat[0] for cat in unique_categories if cat[0]]
    print(f"🏷️ [DEBUG] Unique categories: {categories}")
    
    return {
        "user_id": current_user.id,
        "total_reports": len(all_reports),
        "categories": categories,
        "reports": debug_data
    }

@router.get("/category/{category_name}/tests")
def get_category_tests_data(
    category_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get test data for any category dynamically from lab_report_categorized table"""
    
    print(f"🔍 [CategoryTests] Searching for category '{category_name}' for user {current_user.id}")
    
    # Get all unique loinc_codes in this category for this user
    unique_tests = db.query(LabReportCategorized.loinc_code, LabReportCategorized.test_name).filter(
        LabReportCategorized.user_id == current_user.id,
        LabReportCategorized.inferred_test_category == category_name
    ).distinct().all()
    
    test_data = [(test[0], test[1]) for test in unique_tests]  # (loinc_code, test_name)
    print(f"📋 [CategoryTests] Found {len(test_data)} unique tests: {[t[1] for t in test_data]}")
    
    test_results = []
    
    for loinc_code, test_name in test_data:
        # Get the most recent lab report for this test
        latest_report = db.query(LabReportCategorized).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.loinc_code == loinc_code,
            LabReportCategorized.inferred_test_category == category_name
        ).order_by(desc(LabReportCategorized.test_date)).first()
        
        if latest_report:
            print(f"✅ [CategoryTests] Found data for {test_name}: {latest_report.test_value}")
            
            # Create test result - ensure no null values for Swift compatibility
            test_result = {
                "name": test_name or "",
                "description": f"Lab test for {test_name}",
                "value": latest_report.test_value or "",
                "unit": latest_report.test_unit or "",
                "normalRange": latest_report.reference_range or "",
                "status": latest_report.test_status.lower() if latest_report.test_status else "unknown",
                "lastTested": latest_report.test_date.strftime("%B %d, %Y") if latest_report.test_date else ""
            }
            
            test_results.append(test_result)
        else:
            print(f"❌ [CategoryTests] No recent data found for {test_name}")
    
    print(f"📊 [CategoryTests] Returning {len(test_results)} test results for category '{category_name}'")
    
    return {
        "tests": test_results,
        "category": category_name,
        "totalTests": len(test_results)
    }

@router.get("/available-categories")
def get_available_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all available test categories for the current user with test counts and status summary"""
    
    print(f"🔍 [AvailableCategories] Getting categories for user {current_user.id}")
    
    # Get all unique categories for this user
    user_categories = db.query(LabReportCategorized.inferred_test_category).filter(
        LabReportCategorized.user_id == current_user.id,
        LabReportCategorized.inferred_test_category.isnot(None)
    ).distinct().all()
    
    categories = []
    
    for category_tuple in user_categories:
        category = category_tuple[0]
        if not category:
            continue
            
        print(f"📋 [AvailableCategories] Processing category: {category}")
        
        # Count unique tests in this category
        total_tests = db.query(LabReportCategorized.loinc_code).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.inferred_test_category == category
        ).distinct().count()
        
        # Get most recent test for each unique loinc_code to determine status
        recent_tests_subquery = db.query(
            LabReportCategorized.loinc_code,
            func.max(LabReportCategorized.test_date).label('max_date')
        ).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.inferred_test_category == category
        ).group_by(LabReportCategorized.loinc_code).subquery()
        
        # Get the actual recent reports
        recent_reports = db.query(LabReportCategorized).join(
            recent_tests_subquery,
            (LabReportCategorized.loinc_code == recent_tests_subquery.c.loinc_code) &
            (LabReportCategorized.test_date == recent_tests_subquery.c.max_date)
        ).filter(
            LabReportCategorized.user_id == current_user.id,
            LabReportCategorized.inferred_test_category == category
        ).all()
        
        # Count status distribution
        green_count = 0
        amber_count = 0
        red_count = 0
        
        for report in recent_reports:
            status = (report.test_status or "").lower()
            if status in ['normal', 'green']:
                green_count += 1
            elif status in ['high', 'low', 'elevated', 'amber', 'orange']:
                amber_count += 1
            elif status in ['critical', 'abnormal', 'red']:
                red_count += 1
            else:
                # Default unknown status to normal
                green_count += 1
        
        # Determine category icon based on the category name
        icon = get_category_icon(category)
        icon_color = get_category_color(category)
        
        category_data = {
            "name": category,
            "icon": icon,
            "iconColor": icon_color,
            "totalTests": total_tests,
            "greenCount": green_count,
            "amberCount": amber_count,
            "redCount": red_count
        }
        
        categories.append(category_data)
        print(f"✅ [AvailableCategories] {category}: {total_tests} tests ({green_count}G, {amber_count}A, {red_count}R)")
    
    print(f"📊 [AvailableCategories] Returning {len(categories)} categories")
    
    return {
        "categories": categories,
        "totalCategories": len(categories)
    }

@router.get("/trends/{test_name}")
def get_test_trends(
    test_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get trends data for a specific test from aggregated tables"""
    
    print(f"🔍 [Trends] Getting trends for test: {test_name}, user: {current_user.id}")
    
    # Get the most recent value for the header
    latest_report = db.query(LabReportCategorized).filter(
        LabReportCategorized.user_id == current_user.id,
        LabReportCategorized.test_name == test_name
    ).order_by(desc(LabReportCategorized.test_date)).first()
    
    # Get daily trends (last 30 days)
    daily_data = db.query(LabReportDaily).filter(
        LabReportDaily.user_id == current_user.id,
        LabReportDaily.test_name == test_name
    ).order_by(desc(LabReportDaily.date)).limit(30).all()
    
    # Get monthly trends (last 12 months)
    monthly_data = db.query(LabReportMonthly).filter(
        LabReportMonthly.user_id == current_user.id,
        LabReportMonthly.test_name == test_name
    ).order_by(desc(LabReportMonthly.year), desc(LabReportMonthly.month)).limit(12).all()
    
    # Get quarterly trends (last 8 quarters)
    quarterly_data = db.query(LabReportQuarterly).filter(
        LabReportQuarterly.user_id == current_user.id,
        LabReportQuarterly.test_name == test_name
    ).order_by(desc(LabReportQuarterly.year), desc(LabReportQuarterly.quarter)).limit(8).all()
    
    # Get yearly trends (last 5 years)
    yearly_data = db.query(LabReportYearly).filter(
        LabReportYearly.user_id == current_user.id,
        LabReportYearly.test_name == test_name
    ).order_by(desc(LabReportYearly.year)).limit(5).all()
    
    # Helper function to convert string values to numeric when possible
    def safe_numeric_value(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # Try to convert string to float
                return float(value)
            except (ValueError, TypeError):
                # If conversion fails, return None for non-numeric values
                return None
        return None

    # Format the data for frontend
    def format_daily_data(records):
        return [{
            "date": record.date.isoformat(),
            "value": safe_numeric_value(record.avg_value),
            "status": record.status,
            "count": record.count
        } for record in reversed(records)]  # Reverse to show chronological order
    
    def format_monthly_data(records):
        return [{
            "period": f"{record.year}-{record.month:02d}",
            "year": record.year,
            "month": record.month,
            "value": safe_numeric_value(record.avg_value),
            "status": record.status,
            "count": record.count
        } for record in reversed(records)]
    
    def format_quarterly_data(records):
        return [{
            "period": f"{record.year}-Q{record.quarter}",
            "year": record.year,
            "quarter": record.quarter,
            "value": safe_numeric_value(record.avg_value),
            "status": record.status,
            "count": record.count
        } for record in reversed(records)]
    
    def format_yearly_data(records):
        return [{
            "period": str(record.year),
            "year": record.year,
            "value": safe_numeric_value(record.avg_value),
            "status": record.status,
            "count": record.count
        } for record in reversed(records)]
    
    # Get test info from mapping
    test_mapping = db.query(LabTestMapping).filter(
        LabTestMapping.test_name == test_name,
        LabTestMapping.is_active == True
    ).first()
    
    trends_data = {
        "testName": test_name,
        "currentValue": (latest_report.test_value if latest_report and latest_report.test_value else "") or "",
        "currentUnit": (test_mapping.common_units if test_mapping and test_mapping.common_units else "") or "",
        "normalRange": (test_mapping.normal_range_info if test_mapping and test_mapping.normal_range_info else "") or "",
        "lastTested": latest_report.test_date.strftime("%B %d, %Y") if latest_report else "",
        "currentStatus": latest_report.test_status.lower() if latest_report and latest_report.test_status else "unknown",
        "trends": {
            "daily": format_daily_data(daily_data),
            "monthly": format_monthly_data(monthly_data),
            "quarterly": format_quarterly_data(quarterly_data),
            "yearly": format_yearly_data(yearly_data)
        }
    }
    
    print(f"📊 [Trends] Returning trends data with {len(daily_data)} daily, {len(monthly_data)} monthly, {len(quarterly_data)} quarterly, {len(yearly_data)} yearly points")
    
    return trends_data

def get_category_icon(category_name: str) -> str:
    """Get appropriate icon for category"""
    category_lower = category_name.lower()
    
    if "diabetes" in category_lower:
        return "drop.fill"
    elif "liver" in category_lower or "lft" in category_lower:
        return "leaf.fill"
    elif "kidney" in category_lower or "kft" in category_lower:
        return "drop.triangle"
    elif "thyroid" in category_lower:
        return "bolt.fill"
    elif "lipid" in category_lower or "cholesterol" in category_lower:
        return "waveform.path.ecg"
    elif "blood" in category_lower or "cbc" in category_lower:
        return "drop.circle.fill"
    elif "electrolyte" in category_lower:
        return "atom"
    elif "cardiac" in category_lower or "heart" in category_lower:
        return "heart.fill"
    elif "vitamin" in category_lower or "mineral" in category_lower:
        return "pills"
    elif "infection" in category_lower or "inflammation" in category_lower:
        return "shield.fill"
    else:
        return "doc.text.fill"

def get_category_color(category_name: str) -> str:
    """Get appropriate color for category"""
    category_lower = category_name.lower()
    
    if "diabetes" in category_lower:
        return "green"
    elif "liver" in category_lower or "lft" in category_lower:
        return "brown"
    elif "kidney" in category_lower or "kft" in category_lower:
        return "cyan"
    elif "thyroid" in category_lower:
        return "purple"
    elif "lipid" in category_lower or "cholesterol" in category_lower:
        return "red"
    elif "blood" in category_lower or "cbc" in category_lower:
        return "red"
    elif "electrolyte" in category_lower:
        return "blue"
    elif "cardiac" in category_lower or "heart" in category_lower:
        return "pink"
    elif "vitamin" in category_lower or "mineral" in category_lower:
        return "green"
    elif "infection" in category_lower or "inflammation" in category_lower:
        return "orange"
    else:
        return "blue"
