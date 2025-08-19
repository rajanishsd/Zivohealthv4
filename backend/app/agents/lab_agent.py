import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
import time
import os

from app.agents.base_agent import BaseHealthAgent, AgentState
from app.models.health_data import LabReport
from app.models.lab_test_mapping import LabTestMapping
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction
from langchain.schema import SystemMessage, HumanMessage

class LabAgent(BaseHealthAgent):
    """Specialized agent for processing laboratory reports and test results"""
    
    def __init__(self):
        super().__init__("LabAgent")
        # Agent swarm metadata
        self.specialization = "lab_reports"
        self.capabilities = ["extract", "store", "retrieve", "assess"]
        self.data_types = ["test_results", "reference_ranges", "lab_categories"]
        
        # Cache for lab test mappings context
        self._mappings_context = None
    
    def _build_lab_mappings_context(self) -> str:
        """Build standardized lab test mappings context for ChatGPT"""
        
        if self._mappings_context is not None:
            return self._mappings_context
        
        try:
            db = self.get_database_session()
            mappings = db.query(LabTestMapping).filter(
                LabTestMapping.is_active == True
            ).order_by(LabTestMapping.test_category, LabTestMapping.test_name).all()
            
            if not mappings:
                print("⚠️ [DEBUG] No lab test mappings found in database")
                return ""
            
            # Group mappings by category
            categories = {}
            for mapping in mappings:
                category = mapping.test_category
                if category not in categories:
                    categories[category] = []
                categories[category].append(mapping)
            
            # Build context string - RULES FIRST, then mappings
            context_lines = [
                "CRITICAL EXTRACTION RULES - FOLLOW EXACTLY:",
                "",
                "STEP 1 - FIND ALL TESTS:",
                "• Extract EVERY single test result from the document - DO NOT skip any",
                "• Look for test names followed by values, ranges, or status",
                "• Include tests even if they seem unclear or abbreviated",
                "",
                "STEP 2 - MATCH TEST NAMES:",
                "• First try to match test name to standardized names below (exact or close match)",
                "• For variations (ALT/SGPT/Alanine aminotransferase), use standardized name",
                "• If no match found, keep the EXACT original test name from document",
                "",
                "STEP 3 - ASSIGN CATEGORIES:",
                "• Use the EXACT category section name as it appears in the document",
                "• Look for category headers/sections in the document (e.g., 'LIVER FUNCTION', 'Complete Blood Count', 'LIPID PROFILE')",
                "• Use the category name directly from the document without modification",
                "• If no clear document category section, use 'Other'",
                "",
                "EXAMPLES OF CATEGORY USAGE:",
                "• Document section header 'LIVER FUNCTION' → Use 'LIVER FUNCTION'",
                "• Document section header 'Complete Blood Count' → Use 'Complete Blood Count'",
                "• Document section header 'LIPID PROFILE' → Use 'LIPID PROFILE'",
                "• Document section header 'KIDNEY FUNCTION' → Use 'KIDNEY FUNCTION'",
                "• Document section header 'CARDIAC MARKERS' → Use 'CARDIAC MARKERS'",
                "",
                "MANDATORY: Extract ALL tests - missing tests is unacceptable",
                "",
                "=== STANDARDIZED LAB TEST MAPPINGS ===",
                "USE THE FOLLOWING EXACT TEST NAMES AND CATEGORIES FOR MATCHING:",
                ""
            ]
            
            for category, tests in categories.items():
                context_lines.append(f"=== {category.upper()} ===")
                for test in tests:
                    context_lines.append(f"• {test.test_name}")
                    context_lines.append(f"  Category: {test.test_category}")
                    context_lines.append(f"  Units: {test.common_units}")
                    context_lines.append(f"  Normal Range: {test.normal_range_info}")
                    context_lines.append(f"  Description: {test.description}")
                    context_lines.append("")
                context_lines.append("")
            
            self._mappings_context = "\n".join(context_lines)
            db.close()
            
            print(f"✅ [DEBUG] Built lab mappings context with {len(mappings)} tests across {len(categories)} categories")
            return self._mappings_context
            
        except Exception as e:
            print(f"❌ [DEBUG] Error building lab mappings context: {e}")
            return ""
    
    async def extract_data(self, state: AgentState) -> AgentState:
        """Extract lab report data from OCR text with enhanced telemetry"""
        
        with trace_agent_operation(
            self.agent_name,
            "extract_lab",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            try:
                log_agent_interaction(
                    self.agent_name,
                    "System",
                    "extraction_started",
                    {
                        "operation": "extract_lab_data",
                        "ocr_text_length": len(state.get("ocr_text", "")),
                        "document_type": state.get("document_type", "unknown")
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                extraction_prompt = f"""
                Extract laboratory test data from the following medical text.
                
                Look for:
                - Test names and their results (extract ALL tests found in the document)
                - Reference ranges or normal values
                - Test status (Normal, High, Low, Critical, Abnormal)
                - Test dates and report dates
                - Lab facility information
                - Ordering physician name
                - Test methodology if mentioned
                - Test value cannot be more than 100 characters, if it is more than 100 characters, then discard the test
                - Category section headers in the document
                
                Return a JSON object with lab information and an array of test results:
                {{
                    "lab_name": "Laboratory facility name",
                    "lab_address": "Lab address if available",
                    "test_date": "2024-01-15",
                    "report_date": "2024-01-16",
                    "ordering_physician": "Dr. Smith",
                    "tests": [
                        {{
                            "test_name": "ALT",
                            "test_category": "LIVER FUNCTION",
                            "test_value": "45",
                            "test_unit": "U/L",
                            "reference_range": "M: 10-40; F: 7-35",
                            "test_status": "High",
                            "test_notes": "Slightly elevated",
                            "test_methodology": "Enzymatic"
                        }},
                        {{
                            "test_name": "Glucose",
                            "test_category": "Complete Blood Count",
                            "test_value": "92",
                            "test_unit": "mg/dL",
                            "reference_range": "70-99",
                            "test_status": "Normal",
                            "test_notes": "Within normal limits",
                            "test_methodology": "Enzymatic"
                        }}
                    ]
                }}
                
                IMPORTANT: 
                - Extract ALL tests found in the document, even if not in the mappings above
                - Use the EXACT category section name as it appears in the document
                - Use the EXACT test name as it appears in the document
                """
                
                extraction_tool = self.get_extraction_tool()
                
                # Store the input (OCR text + prompt) 
                self._store_chatgpt_interaction(
                    state.get("request_id", "unknown"),
                    state["ocr_text"], 
                    extraction_prompt
                )
                
                result = extraction_tool.func(state["ocr_text"], extraction_prompt)
                
                # Store the response
                self._store_chatgpt_interaction(
                    state.get("request_id", "unknown"),
                    state["ocr_text"], 
                    extraction_prompt,
                    result
                )
                
                if "error" in result:
                    state["error_message"] = f"Lab extraction failed: {result['error']}"
                    log_agent_interaction(
                        self.agent_name,
                        "System",
                        "extraction_failed",
                        {"error": result['error']},
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        request_id=state["request_id"]
                    )
                else:
                    state["extracted_data"] = result
                    self.log_operation("extract", result, state)
                    
                    # Enhanced logging for agent swarm coordination
                    tests_count = len(result.get("tests", []))
                    abnormal_tests = sum(1 for test in result.get("tests", []) 
                                       if test.get("test_status", "").lower() in ["high", "low", "critical", "abnormal"])
                    
                    log_agent_interaction(
                        self.agent_name,
                        "System",
                        "extraction_completed",
                        {
                            "tests_extracted": tests_count,
                            "abnormal_tests": abnormal_tests,
                            "has_lab_info": bool(result.get("lab_name")),
                            "has_physician": bool(result.get("ordering_physician")),
                            "test_categories": list(set(test.get("test_category", "Unknown") 
                                                      for test in result.get("tests", []))),
                            "data_quality_score": self._assess_extraction_quality(result)
                        },
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        request_id=state["request_id"]
                    )
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Lab extraction error: {str(e)}"
                log_agent_interaction(
                    self.agent_name,
                    "System",
                    "extraction_error",
                    {"error": str(e)},
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                return state
    
    def _assess_extraction_quality(self, extracted_data: Dict[str, Any]) -> float:
        """Assess the quality of extracted lab data"""
        if not extracted_data:
            return 0.0
            
        required_fields = ["tests"]
        optional_fields = ["lab_name", "test_date", "ordering_physician"]
        
        quality_score = 0.0
        
        # Check if we have tests (50% of score)
        tests = extracted_data.get("tests", [])
        if tests and isinstance(tests, list) and len(tests) > 0:
            quality_score += 0.5
            
            # Check test completeness (30% of score)
            complete_tests = sum(1 for test in tests 
                               if test and isinstance(test, dict) and test.get("test_name") and test.get("test_value"))
            quality_score += (complete_tests / len(tests)) * 0.3
        
        # Check optional fields (20% of score)
        optional_present = sum(1 for field in optional_fields if extracted_data.get(field))
        quality_score += (optional_present / len(optional_fields)) * 0.2
        
        return round(quality_score, 3)
    
    def _store_chatgpt_interaction(self, request_id: str, ocr_text: str, prompt: str, response: Dict[str, Any] = None) -> None:
        """Store ChatGPT interaction (input and output) as files in data folder"""
        import json
        import os
        from datetime import datetime
        
        try:
            # Create chatgpt_interactions directory
            interactions_dir = "data/chatgpt_interactions"
            os.makedirs(interactions_dir, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"lab_extraction_{request_id}_{timestamp}"
            
            # Store input (OCR text + prompt)
            input_data = {
                "request_id": request_id,
                "agent": "LabAgent",
                "timestamp": datetime.now().isoformat(),
                "ocr_text_length": len(ocr_text),
                "ocr_text": ocr_text,
                "extraction_prompt": prompt
            }
            
            input_file_path = os.path.join(interactions_dir, f"{base_filename}_input.json")
            with open(input_file_path, 'w', encoding='utf-8') as f:
                json.dump(input_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 [DEBUG] Stored ChatGPT input to: {input_file_path}")
            
            # Store output (ChatGPT response) if provided
            if response is not None:
                output_data = {
                    "request_id": request_id,
                    "agent": "LabAgent", 
                    "timestamp": datetime.now().isoformat(),
                    "response": response,
                    "response_type": type(response).__name__,
                    "tests_extracted": len(response.get("tests", [])) if isinstance(response, dict) else 0
                }
                
                output_file_path = os.path.join(interactions_dir, f"{base_filename}_output.json")
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
                
                print(f"💾 [DEBUG] Stored ChatGPT output to: {output_file_path}")
            
        except Exception as e:
            print(f"❌ [DEBUG] Failed to store ChatGPT interaction: {e}")
            # Don't fail the main process if storage fails
    
    def _check_for_duplicate_test(self, db, user_id: int, test_name: str, test_date, lab_name: str = None, 
                                 test_value: str = None, test_unit: str = None, reference_range: str = None) -> bool:
        """Check if a lab test with the same criteria already exists"""
        
        try:
            # Convert test_name and lab_name to lowercase for comparison
            test_name_lower = test_name.lower() if test_name else None
            lab_name_lower = lab_name.lower() if lab_name else None
            
            # First check: test_name + lab_name + date
            query1 = db.query(LabReport).filter(
                LabReport.user_id == user_id,
                LabReport.test_name == test_name_lower,
                LabReport.test_date == test_date
            )
            
            # Add lab_name to uniqueness check if available
            if lab_name_lower:
                query1 = query1.filter(LabReport.lab_name == lab_name_lower)
            else:
                # If no lab_name provided, only check for records without lab_name
                query1 = query1.filter(LabReport.lab_name.is_(None))
            
            existing_record = query1.first()
            
            if existing_record:
                print(f"🔍 [DEBUG] Duplicate found (test_name + lab_name + date): test '{test_name}' on {test_date} from lab '{lab_name}' (ID: {existing_record.id})")
                return True
            
            # Second check: test_value + test_unit + reference_range + lab_name + date (if first check failed)
            if test_value is not None and test_unit is not None and reference_range is not None:
                query2 = db.query(LabReport).filter(
                    LabReport.user_id == user_id,
                    LabReport.test_value == test_value,
                    LabReport.test_unit == test_unit,
                    LabReport.reference_range == reference_range,
                    LabReport.test_date == test_date
                )
                
                # Add lab_name to second check if available
                if lab_name_lower:
                    query2 = query2.filter(LabReport.lab_name == lab_name_lower)
                else:
                    query2 = query2.filter(LabReport.lab_name.is_(None))
                
                existing_record_2 = query2.first()
                
                if existing_record_2:
                    print(f"🔍 [DEBUG] Duplicate found (test_value + test_unit + reference_range + lab_name + date): value '{test_value}' {test_unit} range '{reference_range}' on {test_date} from lab '{lab_name}' (ID: {existing_record_2.id})")
                    return True
            
            print(f"✅ [DEBUG] No duplicate found for test '{test_name}' on {test_date} from lab '{lab_name}'")
            return False
                
        except Exception as e:
            print(f"❌ [DEBUG] Error checking for duplicates: {str(e)}")
            # If there's an error checking, assume not duplicate to avoid blocking storage
            return False

    async def store_data(self, state: AgentState) -> AgentState:
        """Store lab report data to database"""
        
        step_start = time.time()
        print(f"💾 [DEBUG] Starting store_data at {datetime.now().isoformat()}")
        
        with trace_agent_operation(
            self.agent_name,
            "store_lab",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            db = self.get_database_session()
            try:
                # Get data to store - handle different possible data structures
                data = None
                
                print(f"🔍 [DEBUG] LabAgent store_data - raw state keys: {list(state.keys())}")
                print(f"🔍 [DEBUG] LabAgent store_data - extraction_request type: {type(state.get('extraction_request'))}")
                print(f"🔍 [DEBUG] LabAgent store_data - extraction_request content: {state.get('extraction_request')}")
                
                # Try to get data from different possible sources
                if state.get("extracted_data"):
                    data = state.get("extracted_data")
                    print(f"🔍 [DEBUG] Using extracted_data: {type(data)}")
                elif state.get("extraction_request"):
                    # Data might be nested in extraction_request
                    extraction_req = state.get("extraction_request")
                    if isinstance(extraction_req, dict) and extraction_req.get("tests"):
                        data = extraction_req
                        print(f"🔍 [DEBUG] Using extraction_request directly: {type(data)}")
                    else:
                        # Data might be further nested
                        data = extraction_req
                        print(f"🔍 [DEBUG] Using extraction_request as is: {type(data)}")
                
                print(f"🔍 [DEBUG] LabAgent store_data - final data: {data}")
                
                # Enhanced null checking to prevent NoneType errors
                if data is None:
                    error_msg = "No lab data provided - data is None"
                    print(f"❌ [DEBUG] {error_msg}")
                    state["error_message"] = error_msg
                    return state
                
                if not isinstance(data, dict):
                    error_msg = f"Lab data is not a dictionary - got {type(data)}: {data}"
                    print(f"❌ [DEBUG] {error_msg}")
                    state["error_message"] = error_msg
                    return state
                
                # Check for tests array safely
                tests = data.get("tests")
                if tests is None:
                    error_msg = f"No 'tests' key in lab data. Available keys: {list(data.keys())}"
                    print(f"❌ [DEBUG] {error_msg}")
                    state["error_message"] = error_msg
                    return state
                
                if not isinstance(tests, list):
                    error_msg = f"Tests data is not a list - got {type(tests)}: {tests}"
                    print(f"❌ [DEBUG] {error_msg}")
                    state["error_message"] = error_msg
                    return state
                
                if len(tests) == 0:
                    error_msg = "Tests array is empty - no test data to store"
                    print(f"❌ [DEBUG] {error_msg}")
                    state["error_message"] = error_msg
                    return state
                
                print(f"✅ [DEBUG] Valid lab data found with {len(tests)} tests")
                
                stored_records = []
                skipped_duplicates = []
                
                # Store each test as a separate lab report record
                for i, test_data in enumerate(tests):
                    print(f"💾 [DEBUG] Processing test {i+1}/{len(tests)}: {test_data.get('test_name', 'Unknown')}")
                    
                    if not isinstance(test_data, dict):
                        print(f"⚠️ [DEBUG] Skipping invalid test data (not dict): {test_data}")
                        continue
                    
                    try:
                        # Parse dates once for this test
                        parsed_test_date = self._parse_date(data.get("test_date"))
                        parsed_report_date = self._parse_date(data.get("report_date"))
                        
                        # Skip this test if we can't determine the test date
                        if parsed_test_date is None:
                            print(f"⚠️ [DEBUG] Skipping test '{test_data.get('test_name')}' - cannot determine test date from '{data.get('test_date')}'")
                            continue
                        
                        # Check for duplicate before creating the record
                        is_duplicate = self._check_for_duplicate_test(
                            db=db,
                            user_id=state["user_id"],
                            test_name=test_data.get("test_name", "Unknown Test"),
                            test_date=parsed_test_date,
                            lab_name=data.get("lab_name"),
                            test_value=test_data.get("test_value"),
                            test_unit=test_data.get("test_unit"),
                            reference_range=test_data.get("reference_range")
                        )
                        
                        if is_duplicate:
                            print(f"⏭️ [DEBUG] Skipping duplicate test: {test_data.get('test_name')} on {parsed_test_date}")
                            skipped_duplicates.append(test_data)
                            continue
                        
                        # Convert test_name and lab_name to lowercase for storage
                        test_name_lower = test_data.get("test_name", "Unknown Test").lower() if test_data.get("test_name") else "unknown test"
                        lab_name_lower = data.get("lab_name").lower() if data.get("lab_name") else None
                        
                        lab_report = LabReport(
                            user_id=state["user_id"],
                            test_name=test_name_lower,
                            test_category=test_data.get("test_category"),
                            test_value=test_data.get("test_value"),
                            test_unit=test_data.get("test_unit"),
                            reference_range=test_data.get("reference_range"),
                            test_status=test_data.get("test_status"),
                            lab_name=lab_name_lower,
                            lab_address=data.get("lab_address"),
                            ordering_physician=data.get("ordering_physician"),
                            test_date=parsed_test_date,
                            report_date=parsed_report_date,
                            test_notes=test_data.get("test_notes"),
                            test_methodology=test_data.get("test_methodology"),
                            confidence_score=data.get("confidence_score", 0.9),
                            raw_text=state.get("ocr_text", "")[:1000] if state.get("ocr_text") else ""  # Store first 1000 chars
                        )
                        
                        db.add(lab_report)
                        db.flush()  # Get ID without committing
                        
                        stored_records.append({
                            "table": "lab_reports",
                            "id": lab_report.id,
                            "data": test_data
                        })
                        
                        print(f"✅ [DEBUG] Stored test: {test_data.get('test_name')} with ID {lab_report.id}")
                        
                    except Exception as test_error:
                        error_str = str(test_error)
                        print(f"❌ [DEBUG] Failed to store test {i+1}: {error_str}")
                        
                        # Handle specific database constraint errors
                        if "violates foreign key constraint" in error_str and "user_id" in error_str:
                            print(f"❌ [DEBUG] User {state['user_id']} does not exist in database")
                            state["error_message"] = f"User account not found. Please ensure you are properly logged in."
                            db.rollback()
                            return state
                        elif "duplicate key" in error_str:
                            print(f"⚠️ [DEBUG] Duplicate test detected by database constraint")
                            skipped_duplicates.append(test_data)
                        else:
                            # For other errors, continue processing other tests
                            continue
                
                if not stored_records:
                    if skipped_duplicates:
                        # All tests were duplicates - this is informational, not an error
                        duplicate_msg = f"All {len(skipped_duplicates)} lab tests from this report were already in your records (duplicates detected)"
                        print(f"ℹ️ [DEBUG] {duplicate_msg}")
                        
                        # Set as success with informational message instead of error
                        state["processing_status_message"] = duplicate_msg
                        state["processing_complete"] = True
                        state["processing_summary"] = {
                            "success": True,
                            "new_records": 0,
                            "duplicates_skipped": len(skipped_duplicates),
                            "message": "Duplicate lab report detected - no new data stored",
                            "scenario": "duplicate_detection"  # Add scenario type for future extensibility
                        }
                        
                        # Set stored_records as empty list so finalize_response works properly
                        state["stored_records"] = []
                        
                        # Don't rollback - duplicates are successful detection, not failure
                        db.commit()
                        
                        # Continue to normal completion - DO NOT return early to let finalize_response run
                        completion_msg = f"Detected and skipped {len(skipped_duplicates)} duplicate lab tests"
                        print(f"✅ [DEBUG] {completion_msg}")
                        
                        self.log_operation("store", {
                            "records_count": 0,
                            "duplicates_skipped": len(skipped_duplicates),
                            "total_processed": len(tests)
                        }, state)
                        
                        step_duration = time.time() - step_start
                        print(f"💾 [DEBUG] store_data completed in {step_duration:.2f}s")
                        
                        return state
                    else:
                        error_msg = "No tests were successfully stored"
                        print(f"❌ [DEBUG] {error_msg}")
                        state["error_message"] = error_msg
                        db.rollback()
                        return state
                
                db.commit()
                
                # Enhanced completion message with duplicate statistics
                completion_msg = f"Successfully committed {len(stored_records)} lab reports to database"
                if skipped_duplicates:
                    completion_msg += f" (skipped {len(skipped_duplicates)} duplicates)"
                print(f"✅ [DEBUG] {completion_msg}")
                
                state["stored_records"] = stored_records
                self.log_operation("store", {
                    "records_count": len(stored_records),
                    "duplicates_skipped": len(skipped_duplicates),
                    "total_processed": len(tests)
                }, state)
                
                step_duration = time.time() - step_start
                print(f"💾 [DEBUG] store_data completed in {step_duration:.2f}s")
                
                return state
                
            except Exception as e:
                step_duration = time.time() - step_start
                error_msg = f"Lab storage error: {str(e)}"
                print(f"❌ [DEBUG] {error_msg} (after {step_duration:.2f}s)")
                db.rollback()
                state["error_message"] = error_msg
                return state
            finally:
                db.close()
    
    async def retrieve_data(self, state: AgentState) -> AgentState:
        """Retrieve lab report data from database"""
        
        with trace_agent_operation(
            self.agent_name,
            "retrieve_lab",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            db = self.get_database_session()
            try:
                retrieval_request = state.get("retrieval_request", {})
                days_back = retrieval_request.get("days_back", 180)  # 6 months default
                limit = retrieval_request.get("limit", 100)
                test_category = retrieval_request.get("test_category")
                test_status = retrieval_request.get("test_status")
                
                # Calculate date range
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=days_back)
                
                # Build query
                query = db.query(LabReport).filter(
                    LabReport.user_id == state["user_id"],
                    LabReport.test_date >= start_date.date()
                )
                
                if test_category:
                    query = query.filter(LabReport.test_category == test_category)
                
                if test_status:
                    query = query.filter(LabReport.test_status == test_status)
                
                lab_reports = query.order_by(LabReport.test_date.desc()).limit(limit).all()
                
                # Format data
                reports_data = []
                for report in lab_reports:
                    report_dict = {
                        "id": report.id,
                        "test_name": report.test_name,
                        "test_category": report.test_category,
                        "test_value": report.test_value,
                        "test_unit": report.test_unit,
                        "reference_range": report.reference_range,
                        "test_status": report.test_status,
                        "test_date": report.test_date.isoformat(),
                        "report_date": report.report_date.isoformat() if report.report_date else None,
                        "lab_name": report.lab_name,
                        "ordering_physician": report.ordering_physician,
                        "test_notes": report.test_notes,
                        "test_methodology": report.test_methodology
                    }
                    reports_data.append(report_dict)
                
                # Generate analysis
                analysis = self._analyze_lab_results(lab_reports)
                
                # Group by test name for trends
                test_trends = self._calculate_test_trends(lab_reports)
                
                retrieved_data = {
                    "recent_reports": reports_data,
                    "summary": {
                        "total_tests": len(reports_data),
                        "date_range": f"{start_date.date()} to {end_date.date()}",
                        "unique_tests": len(set(report.test_name for report in lab_reports)),
                        "labs_used": len(set(report.lab_name for report in lab_reports if report.lab_name))
                    },
                    "analysis": analysis,
                    "trends": test_trends
                }
                
                state["retrieved_data"] = retrieved_data
                self.log_operation("retrieve", {"reports_count": len(reports_data)}, state)
                
                return state
                
            except Exception as e:
                error_msg = f"Lab retrieval error: {str(e)}"
                state["error_message"] = error_msg
                return state
            finally:
                db.close()
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Enhanced date parsing with proper handling of time-only strings and various date formats.
        Returns None for unparseable dates instead of today's date to avoid data corruption.
        """
        if not date_str:
            print(f"⚠️ [DEBUG] No date string provided - returning None")
            return None
        
        # Clean and normalize the input
        date_str = str(date_str).strip()
        
        # Detect time-only patterns (AM/PM indicators without dates)
        time_only_patterns = [
            r'^\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)$',  # 09:25AM, 04:04PM, 10:30:15 AM
            r'^\d{1,2}:\d{2}(:\d{2})?$',            # 14:30, 09:25:00 (24-hour format)
            r'^(AM|PM)$',                           # Just AM or PM
            r'^\d{1,2}\s*(AM|PM)$'                  # 9 AM, 4PM
        ]
        
        import re
        for pattern in time_only_patterns:
            if re.match(pattern, date_str, re.IGNORECASE):
                print(f"⚠️ [DEBUG] Detected time-only string '{date_str}' - cannot determine date. Returning None to avoid using today's date")
                return None
        
        try:
            if isinstance(date_str, str):
                # Handle ISO datetime strings like "2025-05-03T08:56:00"
                if 'T' in date_str:
                    print(f"🔍 [DEBUG] Parsing ISO datetime: {date_str}")
                    date_part = date_str.split('T')[0]
                    parsed_date = datetime.fromisoformat(date_part).date()
                    print(f"✅ [DEBUG] Parsed date: {parsed_date}")
                    return parsed_date
                
                # Try multiple date formats commonly found in lab reports
                date_formats = [
                    "%Y-%m-%d",           # 2024-01-15
                    "%d-%b-%Y",           # 20-Dec-2022
                    "%d/%m/%Y",           # 20/12/2022
                    "%m/%d/%Y",           # 12/20/2022
                    "%d-%m-%Y",           # 20-12-2022
                    "%Y/%m/%d",           # 2022/12/20
                    "%b %d, %Y",          # Dec 20, 2022
                    "%B %d, %Y",          # December 20, 2022
                    "%d %b %Y",           # 20 Dec 2022
                    "%d %B %Y",           # 20 December 2022
                ]
                
                # Try each format
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt).date()
                        print(f"✅ [DEBUG] Parsed date using format '{fmt}': {parsed_date}")
                        return parsed_date
                    except ValueError:
                        continue
                
                # Handle dates with times (not just ISO format)
                # Example: "20-Dec-2022 09:25AM"
                if any(indicator in date_str.upper() for indicator in ['AM', 'PM']):
                    # Split on space and try to parse the date part
                    parts = date_str.split()
                    if len(parts) >= 2:
                        date_part = parts[0]
                        time_part = ' '.join(parts[1:])
                        
                        # Check if time_part is actually just a time
                        if re.match(r'^\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)$', time_part, re.IGNORECASE):
                            print(f"🔍 [DEBUG] Found date with time: date='{date_part}', time='{time_part}'")
                            
                            # Try to parse just the date part
                            for fmt in date_formats:
                                try:
                                    parsed_date = datetime.strptime(date_part, fmt).date()
                                    print(f"✅ [DEBUG] Parsed date part using format '{fmt}': {parsed_date}")
                                    return parsed_date
                                except ValueError:
                                    continue
                
                # Last attempt with general ISO parsing
                try:
                    parsed_date = datetime.fromisoformat(date_str).date()
                    print(f"✅ [DEBUG] Parsed date with ISO format: {parsed_date}")
                    return parsed_date
                except ValueError:
                    pass
                
            # If we reach here, couldn't parse the date string
            print(f"❌ [DEBUG] Could not parse date string '{date_str}' - returning None")
            return None
            
        except Exception as e:
            print(f"❌ [DEBUG] All date parsing attempts failed for '{date_str}': {e}")
            print(f"⚠️ [DEBUG] Returning None instead of today's date to prevent data corruption")
            return None
    
    def _analyze_lab_results(self, reports: List[LabReport]) -> Dict[str, Any]:
        """Analyze lab results for patterns and concerns"""
        if not reports:
            return {}
        
        # Count test statuses
        status_counts = {}
        category_counts = {}
        
        for report in reports:
            status = report.test_status or "Unknown"
            category = report.test_category or "Unknown"
            
            status_counts[status] = status_counts.get(status, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Find abnormal results
        abnormal_tests = [
            {
                "test_name": report.test_name,
                "test_value": report.test_value,
                "reference_range": report.reference_range,
                "status": report.test_status,
                "test_date": report.test_date.isoformat()
            }
            for report in reports 
            if report.test_status and report.test_status.lower() in ['high', 'low', 'critical', 'abnormal']
        ]
        
        return {
            "status_distribution": status_counts,
            "category_distribution": category_counts,
            "abnormal_results": abnormal_tests[:10],  # Limit to 10 most recent
            "total_abnormal": len(abnormal_tests),
            "normal_percentage": round(
                (status_counts.get("Normal", 0) / len(reports)) * 100, 1
            ) if reports else 0
        }
    
    def _calculate_test_trends(self, reports: List[LabReport]) -> Dict[str, Any]:
        """Calculate trends for recurring tests"""
        if not reports or len(reports) < 2:
            return {}
        
        # Group by test name
        test_groups = {}
        for report in reports:
            test_name = report.test_name
            if test_name not in test_groups:
                test_groups[test_name] = []
            test_groups[test_name].append(report)
        
        trends = {}
        for test_name, test_reports in test_groups.items():
            if len(test_reports) >= 2:
                # Sort by date
                test_reports.sort(key=lambda x: x.test_date, reverse=True)
                
                # Try to calculate numeric trend
                try:
                    latest_value = float(test_reports[0].test_value or 0)
                    previous_value = float(test_reports[1].test_value or 0)
                    
                    if latest_value > previous_value:
                        trend = "increasing"
                    elif latest_value < previous_value:
                        trend = "decreasing"
                    else:
                        trend = "stable"
                    
                    trends[test_name] = {
                        "trend": trend,
                        "latest_value": test_reports[0].test_value,
                        "previous_value": test_reports[1].test_value,
                        "latest_date": test_reports[0].test_date.isoformat(),
                        "previous_date": test_reports[1].test_date.isoformat(),
                        "test_count": len(test_reports)
                    }
                except (ValueError, TypeError):
                    # Non-numeric values, just track status changes
                    trends[test_name] = {
                        "trend": "non_numeric",
                        "latest_status": test_reports[0].test_status,
                        "previous_status": test_reports[1].test_status,
                        "latest_date": test_reports[0].test_date.isoformat(),
                        "test_count": len(test_reports)
                    }
        
        return trends

    async def assess_question_relevance(self, question: str, user_id: int, session_id: int = None) -> Dict[str, Any]:
        """Assess if question is relevant to lab data and determine retrieval strategy"""
        
        with trace_agent_operation(
            self.agent_name,
            "assess_question_relevance",
            user_id=user_id,
            session_id=session_id
        ):
            try:
                assessment_prompt = f"""
                Analyze this health question to determine if it's relevant to laboratory/diagnostic test data.
                
                Lab data includes: blood tests, urine tests, diagnostic results, lab values, reference ranges,
                test status (normal/abnormal/high/low), test trends, specific tests like CBC, lipid panels,
                liver function, kidney function, thyroid, glucose, cholesterol, etc.
                
                Question: {question}
                
                Respond with a JSON object:
                {{
                    "is_relevant": true/false,
                    "relevance_score": 0.0-1.0,
                    "test_categories": ["blood", "urine", "chemistry", "specific_test_name"],
                    "time_sensitivity": "recent_only" | "trend_analysis" | "historical",
                    "reasoning": "Why this is/isn't relevant to lab data"
                }}
                
                Examples:
                - "What are my latest lab results?" → highly relevant, recent_only
                - "Is my cholesterol improving?" → highly relevant, trend_analysis
                - "What medications do I take?" → not relevant to lab data
                - "How is my kidney function?" → highly relevant, trend_analysis
                """
                
                messages = [
                    SystemMessage(content="You are a laboratory data specialist assessing question relevance."),
                    HumanMessage(content=assessment_prompt)
                ]
                
                response = self.llm.invoke(messages)
                
                # Handle JSON wrapped in markdown code blocks
                content = response.content.strip()
                if content.startswith('```json'):
                    # Extract JSON from markdown code block
                    content = content[7:]  # Remove ```json
                    if content.endswith('```'):
                        content = content[:-3]  # Remove closing ```
                    content = content.strip()
                elif content.startswith('```'):
                    # Handle generic code block
                    content = content[3:]  # Remove opening ```
                    if content.endswith('```'):
                        content = content[:-3]  # Remove closing ```
                    content = content.strip()
                
                assessment = json.loads(content)
                
                # Determine retrieval strategy
                if assessment.get("is_relevant", False):
                    time_sensitivity = assessment.get("time_sensitivity", "recent_only")
                    
                    if time_sensitivity == "recent_only":
                        retrieval_strategy = {
                            "days_back": 520,  # Extended to include historical test data (Jan 2024)
                            "limit": 50,       # Increased limit
                            "specific_filters": {},
                            "priority_data": ["recent_reports", "summary"]
                        }
                    elif time_sensitivity == "trend_analysis":
                        retrieval_strategy = {
                            "days_back": 730,  # 2 years for trend analysis
                            "limit": 100,
                            "specific_filters": {},
                            "priority_data": ["recent_reports", "analysis", "trends"]
                        }
                    else:  # historical
                        retrieval_strategy = {
                            "days_back": 1095,  # 3 years for historical
                            "limit": 200,
                            "specific_filters": {},
                            "priority_data": ["recent_reports", "analysis", "trends", "summary"]
                        }
                    
                    # Add test category filters
                    test_categories = assessment.get("test_categories", [])
                    if test_categories:
                        retrieval_strategy["specific_filters"]["test_categories"] = test_categories
                
                else:
                    retrieval_strategy = {
                        "days_back": 0,
                        "limit": 0,
                        "specific_filters": {},
                        "priority_data": []
                    }
                
                return {
                    "is_relevant": assessment.get("is_relevant", False),
                    "relevance_score": assessment.get("relevance_score", 0.0),
                    "retrieval_strategy": retrieval_strategy,
                    "reasoning": assessment.get("reasoning", "Assessment completed")
                }
                
            except Exception as e:
                return {
                    "is_relevant": False,
                    "relevance_score": 0.0,
                    "retrieval_strategy": {"days_back": 0, "limit": 0, "specific_filters": {}, "priority_data": []},
                    "reasoning": f"Assessment failed: {str(e)}"
                }

# Global instance
# lab_agent = LabAgent()  # Commented to prevent startup hanging

# Lazy-loaded global instance
_lab_agent = None

def get_lab_agent():
    """Get or create the lab agent instance"""
    global _lab_agent
    if _lab_agent is None:
        _lab_agent = LabAgent()
    return _lab_agent

# For backward compatibility
def lab_agent():
    return get_lab_agent()

# Convenience functions for orchestrator
async def extract_lab_data(ocr_text: str, user_id: int, session_id: int = None) -> Dict[str, Any]:
    """Extract lab data from OCR text"""
    agent = get_lab_agent()
    return await agent.process_request(
        "extract",
        {"ocr_text": ocr_text},
        user_id,
        session_id
    )

async def store_lab_data(lab_data: Dict[str, Any], user_id: int, session_id: int = None) -> Dict[str, Any]:
    """Store lab data to database"""
    agent = get_lab_agent()
    return await agent.process_request(
        "store",
        {"extraction_request": lab_data},
        user_id,
        session_id
    )

async def retrieve_lab_data(user_id: int, session_id: int = None, days_back: int = 180, test_category: str = None) -> Dict[str, Any]:
    """Retrieve lab data from database"""
    agent = get_lab_agent()
    return await agent.process_request(
        "retrieve",
        {"retrieval_request": {"days_back": days_back, "test_category": test_category}},
        user_id,
        session_id
    ) 