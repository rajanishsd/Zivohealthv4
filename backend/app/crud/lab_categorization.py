"""
Lab Categorization CRUD Operations
Handles categorization and processing of lab reports before aggregation
"""

from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, text, func
from datetime import datetime, date
import logging
import sys
import os

# Add the 3PData/loinc directory to the path for LOINC mapper
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '3PData', 'loinc'))

from app.models.health_data import LabReport
from app.models.lab_test_mapping import LabTestMapping
from app.utils.lab_test_mapper import LabTestMapper
from app.health_scoring.services import HealthScoringService

# Import LOINC mapper components with proper error handling
LabTestLOINCMapper = None
LabTest = None
LOINC_MAPPER_AVAILABLE = False

logger = logging.getLogger(__name__)

try:
    # Allow disabling LOINC mapper in ML worker via env
    if os.getenv("LOINC_ENABLED", "0") == "1":
        from lab_test_loinc_mapper import LabTestLOINCMapper, LabTest
        LOINC_MAPPER_AVAILABLE = True
        logger.info("✅ LOINC mapper imported successfully")
    else:
        logger.info("ℹ️  LOINC mapper disabled via LOINC_ENABLED env var")
except ImportError as e:
    logger.error(f"❌ CRITICAL: LOINC mapper not available - install dependencies: {e}")
    # This is a critical error in production - LOINC codes won't be assigned

class LabCategorizationRecord:
    """Model for lab_report_categorized table records"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

class LabCategorizationCRUD:
    """CRUD operations for lab categorization and processing"""
    
    @staticmethod
    def get_loinc_code_for_test(test_name: str, test_category: str, test_unit: str = None, reference_range: str = None, loinc_mapper: Optional[Any] = None) -> tuple[Optional[str], Optional[str]]:
        """Get LOINC code for a lab test using the LOINC mapper"""
        try:
            # Check if LOINC mapper is available
            if not loinc_mapper:
                logger.debug("LOINC mapper not available - skipping LOINC code assignment")
                return None, None
            
            # Create a LabTest object for the LOINC mapper
            lab_test = LabTest(
                id=0,  # Not used for LOINC lookup
                test_name=test_name,
                test_code=None,  # Will be determined by the mapper
                test_category=test_category,
                description=f"Lab test: {test_name}",
                common_units=test_unit,
                normal_range_info=reference_range,
                loinc_code=None
            )
            
            # Search for similar LOINC codes
            similar_codes = loinc_mapper.search_similar_loinc_codes(lab_test, k=50)
            
            if not similar_codes:
                logger.debug(f"🔍 No similar LOINC codes found for '{test_name}'")
                return None, None
            
            # Get LOINC code using ChatGPT
            loinc_code, source = loinc_mapper.get_chatgpt_loinc_code(lab_test, similar_codes)
            
            if loinc_code:
                logger.info(f"✅ Found LOINC code '{loinc_code}' for test '{test_name}' (Source: {source})")
                return loinc_code, source
            else:
                logger.debug(f"❌ No LOINC code found for test '{test_name}'")
                return None, None
                
        except Exception as e:
            logger.error(f"❌ Error getting LOINC code for '{test_name}': {e}")
            return None, None
    
    @staticmethod
    def get_pending_categorization_entries(db: Session, limit: int = 1000) -> List[LabReport]:
        """Get lab reports that need categorization processing using status column"""
        try:
            # Get lab reports with categorization_status = 'pending' and exclude 'insufficient' records
            lab_reports = db.query(LabReport).filter(
                LabReport.categorization_status == 'pending'
            ).order_by(LabReport.created_at.asc()).limit(limit).all()
            
            logger.debug(f"📋 [LabCategorization] Found {len(lab_reports)} pending lab reports for categorization")
            return lab_reports
            
        except Exception as e:
            logger.error(f"❌ [LabCategorization] Error getting pending categorization entries: {e}")
            return []
    
    @staticmethod
    def _validate_lab_report_data(lab_report: LabReport) -> tuple[bool, str]:
        """Validate if lab report has sufficient data for categorization"""
        if not lab_report.test_value:
            return False, "Missing test_value"
        if not lab_report.test_name:
            return False, "Missing test_name"
        if not lab_report.test_date:
            return False, "Missing test_date"
        return True, ""
    
    @staticmethod
    def _mark_lab_report_insufficient(db: Session, lab_report_id: int, failure_reason: str):
        """Mark lab report as insufficient with failure reason"""
        try:
            db.execute(text("""
                UPDATE lab_reports 
                SET categorization_status = 'insufficient', 
                    failure_reason = :failure_reason,
                    updated_at = :updated_at 
                WHERE id = :id
            """), {
                "id": lab_report_id,
                "failure_reason": failure_reason,
                "updated_at": datetime.utcnow()
            })
            logger.info(f"🚫 [LabCategorization] Marked lab report {lab_report_id} as insufficient: {failure_reason}")
        except Exception as e:
            logger.error(f"❌ [LabCategorization] Failed to mark lab report {lab_report_id} as insufficient: {e}")
    
    @staticmethod
    def _insert_categorized_lab_report(db: Session, lab_report: LabReport, standardized_test_name: str, 
                                     test_code: str, loinc_code: str, inferred_category: str) -> bool:
        """Insert lab report into lab_report_categorized table"""
        try:
            insert_query = text("""
                INSERT INTO lab_report_categorized (
                    id, user_id, test_name, test_code, loinc_code, test_category, test_value, test_unit,
                    reference_range, test_status, lab_name, lab_address, ordering_physician,
                    test_date, report_date, test_notes, test_methodology,
                    extracted_from_document_id, confidence_score, raw_text,
                    inferred_test_category, aggregation_status, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :test_name, :test_code, :loinc_code, :test_category, :test_value, :test_unit,
                    :reference_range, :test_status, :lab_name, :lab_address, :ordering_physician,
                    :test_date, :report_date, :test_notes, :test_methodology,
                    :extracted_from_document_id, :confidence_score, :raw_text,
                    :inferred_test_category, :aggregation_status, :created_at, :updated_at
                )
            """)
            
            db.execute(insert_query, {
                "id": lab_report.id,
                "user_id": lab_report.user_id,
                "test_name": standardized_test_name,
                "test_code": test_code,
                "loinc_code": loinc_code,
                "test_category": lab_report.test_category,
                "test_value": lab_report.test_value,
                "test_unit": lab_report.test_unit,
                "reference_range": lab_report.reference_range,
                "test_status": lab_report.test_status,
                "lab_name": lab_report.lab_name,
                "lab_address": lab_report.lab_address,
                "ordering_physician": lab_report.ordering_physician,
                "test_date": lab_report.test_date,
                "report_date": lab_report.report_date,
                "test_notes": lab_report.test_notes,
                "test_methodology": lab_report.test_methodology,
                "extracted_from_document_id": lab_report.extracted_from_document_id,
                "confidence_score": lab_report.confidence_score,
                "raw_text": lab_report.raw_text,
                "inferred_test_category": inferred_category,
                "aggregation_status": "pending",
                "created_at": lab_report.created_at,
                "updated_at": datetime.utcnow()
            })
            
            # Update the original lab_report categorization_status to 'categorized'
            db.execute(text("""
                UPDATE lab_reports 
                SET categorization_status = 'categorized', updated_at = :updated_at 
                WHERE id = :id
            """), {
                "id": lab_report.id,
                "updated_at": datetime.utcnow()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [LabCategorization] Failed to insert categorized lab report {lab_report.id}: {e}")
            return False
    
    @staticmethod
    def categorize_and_transfer_lab_reports(db: Session, lab_reports: List[LabReport]) -> int:
        """Categorize lab reports and transfer to lab_report_categorized table"""
        processed_count = 0
        mapper = LabTestMapper(db)
        
        # Initialize LOINC mapper once for all tests
        loinc_mapper = None
        if LOINC_MAPPER_AVAILABLE and LabTestLOINCMapper is not None:
            try:
                loinc_mapper = LabTestLOINCMapper()
                logger.info("🔧 [LabCategorization] LOINC mapper initialized for batch processing")
            except Exception as e:
                logger.error(f"❌ [LabCategorization] Failed to initialize LOINC mapper: {e}")
        else:
            logger.warning("⚠️ [LabCategorization] LOINC mapper not available - will use 'UNKNOWN' for LOINC codes")
        
        for lab_report in lab_reports:
            try:
                # Validate lab report data
                is_valid, failure_reason = LabCategorizationCRUD._validate_lab_report_data(lab_report)
                if not is_valid:
                    LabCategorizationCRUD._mark_lab_report_insufficient(db, lab_report.id, failure_reason)
                    continue
                
                # Get or create test category, test_code, and standardized test name using fuzzy matching
                # Pass GPT's original category from lab_report.test_category
                inferred_category, test_code, standardized_test_name, existing_mapping = LabCategorizationCRUD._get_or_create_test_category(
                    db, mapper, lab_report.test_name, lab_report.test_category, loinc_mapper
                )
                
                # Get LOINC code from the mapping (lookup was done in _get_or_create_test_category)
                loinc_code = existing_mapping.loinc_code if existing_mapping else None
                if not loinc_code:
                    loinc_code = 'UNKNOWN'  # Ensure we always have a loinc_code for the primary key
                
                # Insert lab report using modular function
                if LabCategorizationCRUD._insert_categorized_lab_report(
                    db, lab_report, standardized_test_name, test_code, loinc_code, inferred_category
                ):
                    processed_count += 1
                    loinc_info = f" with LOINC '{loinc_code}'" if loinc_code else ""
                    logger.debug(f"✅ [LabCategorization] Categorized test '{lab_report.test_name}' -> '{standardized_test_name}' with code '{test_code}' as '{inferred_category}'{loinc_info}")
                
            except Exception as e:
                logger.error(f"❌ [LabCategorization] Failed to categorize lab report {lab_report.id}: {e}")
                continue
        
        db.commit()
        # After mapping updates and categorization, sync metric anchors from LOINC mappings
        try:
            svc = HealthScoringService(db)
            upserts = svc.sync_metric_anchors_from_lab_mapping()
            logger.info(f"🔄 [LabCategorization] Synced metric anchors from LOINC mappings (upserts={upserts})")
        except Exception as e:
            logger.error(f"❌ [LabCategorization] Anchor sync failed: {e}")
        return processed_count
    
    @staticmethod
    def _get_or_create_test_category(db: Session, mapper: LabTestMapper, test_name: str, gpt_category: str = None, loinc_mapper: Optional[Any] = None) -> tuple[str, str, str, Optional[LabTestMapping]]:
        """Get existing category, test_code, and standardized test name or create new mapping with 'Others' category"""
        try:
            # First check if exact mapping exists for this test name (case-insensitive)
            existing_mapping = db.query(LabTestMapping).filter(
                func.lower(LabTestMapping.test_name) == test_name.lower()
            ).first()
            
            if existing_mapping:
                # Exact mapping exists, update with GPT suggestion if missing or different
                needs_update = False
                
                if gpt_category:
                    # Case-insensitive comparison for GPT suggestions
                    current_gpt = existing_mapping.gpt_suggested_category or ""
                    if current_gpt.lower() != gpt_category.lower():
                        existing_mapping.gpt_suggested_category = gpt_category
                        needs_update = True
                        logger.info(f"📝 [LabCategorization] Updated existing mapping '{test_name}' with GPT suggestion: '{current_gpt}' -> '{gpt_category}'")
                    else:
                        logger.debug(f"📋 [LabCategorization] GPT suggestion unchanged for '{test_name}': '{gpt_category}'")
                
                # Check if we need to get LOINC code for existing mapping
                if not existing_mapping.loinc_code and loinc_mapper:
                    loinc_code, loinc_source = LabCategorizationCRUD.get_loinc_code_for_test(
                        test_name=test_name,
                        test_category=existing_mapping.test_category,
                        test_unit=None,
                        reference_range=None,
                        loinc_mapper=loinc_mapper
                    )
                    if loinc_code:
                        existing_mapping.loinc_code = loinc_code
                        existing_mapping.loinc_source = loinc_source
                        needs_update = True
                        logger.info(f"📝 [LabCategorization] Updated existing mapping '{test_name}' with LOINC code: '{loinc_code}'")
                
                if needs_update:
                    existing_mapping.updated_at = datetime.utcnow()
                    db.flush()
                
                # Get standardized test name - use standardized name if available, otherwise fall back to test_name
                standardized_name = existing_mapping.test_name_standardized or existing_mapping.test_name
                
                logger.debug(f"📋 [LabCategorization] Found exact mapping '{existing_mapping.test_category}' for test '{test_name}' -> standardized: '{standardized_name}' with code '{existing_mapping.test_code}'")
                return existing_mapping.test_category, existing_mapping.test_code, standardized_name, existing_mapping
            
            # No exact mapping, try fuzzy matching
            category = mapper.get_test_category(test_name)
            
            if category:
                # Fuzzy match found, create new mapping with the fuzzy-matched category
                # Generate a test code based on the normalized test name
                test_code = test_name.upper().replace(' ', '_').replace('(', '').replace(')', '')[:50]
                
                # For new mappings, use the original test_name as both test_name and test_name_standardized
                # This can be manually updated later for better standardization
                standardized_name = test_name
                
                logger.info(f"🔍 [LabCategorization] Fuzzy match found for '{test_name}' -> '{category}' (GPT suggested: '{gpt_category}')")
                
                new_mapping = LabTestMapping(
                    test_name=test_name.lower(),
                    test_name_standardized=standardized_name,  # Set standardized name
                    test_code=test_code,
                    test_category=category,  # Use the fuzzy-matched category
                    gpt_suggested_category=gpt_category,
                    description=f"Auto-generated from fuzzy match for '{test_name}' (GPT suggested: {gpt_category})",
                    is_active=True,
                    is_standardized=False,  # Mark as non-standardized since it's fuzzy matched
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                # Get LOINC code for new mapping
                loinc_code, loinc_source = LabCategorizationCRUD.get_loinc_code_for_test(
                    test_name=standardized_name,
                    test_category=category,
                    test_unit=None,  # Not available at this stage
                    reference_range=None,  # Not available at this stage
                    loinc_mapper=loinc_mapper # Pass loinc_mapper here
                )
                
                if loinc_code:
                    new_mapping.loinc_code = loinc_code
                    new_mapping.loinc_source = loinc_source
                    logger.info(f"🔍 [LabCategorization] Found LOINC code '{loinc_code}' for new fuzzy mapping '{test_name}'")
                
                print(f"🔍 [LabCategorization] New mapping: {new_mapping}")
                db.add(new_mapping)
                db.flush()
                
                logger.info(f"✅ [LabCategorization] Created fuzzy mapping: '{test_name}' -> '{category}' with standardized name '{standardized_name}' and code '{test_code}' (GPT: '{gpt_category}')")
                return category, test_code, standardized_name, new_mapping
            
            # No fuzzy match found, create new mapping with "Others" category
            # Generate a test code based on the normalized test name
            test_code = test_name.upper().replace(' ', '_').replace('(', '').replace(')', '')[:50]
            
            # For new mappings, use the original test_name as both test_name and test_name_standardized
            standardized_name = test_name
            
            logger.info(f"🆕 [LabCategorization] Creating new mapping for unknown test: '{test_name}' (GPT suggested: '{gpt_category}')")
            
            new_mapping = LabTestMapping(
                test_name=test_name.lower(),
                test_name_standardized=standardized_name,  # Set standardized name
                test_code=test_code,
                test_category="Others",
                gpt_suggested_category=gpt_category,
                description=f"Auto-generated mapping for '{test_name}' (GPT suggested: {gpt_category})",
                is_active=True,
                is_standardized=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Get LOINC code for new mapping
            loinc_code, loinc_source = LabCategorizationCRUD.get_loinc_code_for_test(
                test_name=standardized_name,
                test_category="Others",
                test_unit=None,  # Not available at this stage
                reference_range=None,  # Not available at this stage
                loinc_mapper=loinc_mapper # Pass loinc_mapper here
            )
            
            if loinc_code:
                new_mapping.loinc_code = loinc_code
                new_mapping.loinc_source = loinc_source
                logger.info(f"🔍 [LabCategorization] Found LOINC code '{loinc_code}' for new 'Others' mapping '{test_name}'")
            
            db.add(new_mapping)
            db.flush()
            
            logger.info(f"✅ [LabCategorization] Created new mapping: '{test_name}' -> 'Others' with standardized name '{standardized_name}' and code '{test_code}' (GPT: '{gpt_category}')")
            return "Others", test_code, standardized_name, new_mapping
            
        except Exception as e:
            logger.error(f"❌ [LabCategorization] Error processing test '{test_name}': {e}")
            return "Others", test_name.upper().replace(' ', '_')[:50], test_name, None  # Default fallback
    
    @staticmethod
    def get_categorized_lab_reports(
        db: Session, 
        user_id: int, 
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get categorized lab reports for aggregation"""
        query = text("""
            SELECT * FROM lab_report_categorized
            WHERE user_id = :user_id
            AND (:start_date IS NULL OR test_date >= :start_date)
            AND (:end_date IS NULL OR test_date <= :end_date)
            ORDER BY test_date DESC, created_at DESC
            LIMIT :limit
        """)
        
        result = db.execute(query, {
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit
        })
        
        reports = []
        for row in result:
            report_dict = dict(row._mapping)
            reports.append(report_dict)
        
        return reports
    
    @staticmethod
    def get_processing_status(db: Session) -> Dict[str, Any]:
        """Get status of lab categorization processing"""
        try:
            # Count pending categorization
            # Join via mapping to get loinc_code for comparison
            pending_query = text("""
                SELECT COUNT(*) as pending_count FROM lab_reports lr
                LEFT JOIN lab_test_mappings ltm ON LOWER(lr.test_name) = LOWER(ltm.test_name)
                LEFT JOIN lab_report_categorized lrc ON (
                    lr.user_id = lrc.user_id AND
                    COALESCE(ltm.loinc_code, 'UNKNOWN') = lrc.loinc_code AND
                    lr.test_value = lrc.test_value AND
                    lr.test_date = lrc.test_date
                )
                WHERE lrc.user_id IS NULL
            """)
            
            pending_result = db.execute(pending_query).fetchone()
            pending_count = pending_result.pending_count if pending_result else 0
            
            # Count total in lab_reports
            total_result = db.execute(text("SELECT COUNT(*) as total FROM lab_reports")).fetchone()
            total_count = total_result.total if total_result else 0
            
            # Count categorized
            categorized_result = db.execute(text("SELECT COUNT(*) as categorized FROM lab_report_categorized")).fetchone()
            categorized_count = categorized_result.categorized if categorized_result else 0
            
            return {
                "total_lab_reports": total_count,
                "categorized_reports": categorized_count,
                "pending_categorization": pending_count,
                "completion_percentage": (categorized_count / total_count * 100) if total_count > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ [LabCategorization] Error getting status: {e}")
            return {
                "total_lab_reports": 0,
                "categorized_reports": 0,
                "pending_categorization": 0,
                "completion_percentage": 0,
                "error": str(e)
            }

# Instance for external use
lab_categorization = LabCategorizationCRUD()
