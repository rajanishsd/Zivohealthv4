"""
Document Processing Workflow using LangGraph

This module orchestrates the complete document processing pipeline using specialized agents.
"""

import asyncio
import json
import uuid
import time
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from pathlib import Path
import tempfile
import os

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.health_data import (
    DocumentProcessingLog, LabReport, PharmacyBill, PharmacyMedication, AgentMemory
)
from app.agents.tools.ocr_tools import OCRToolkit
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction, log_document_processing_step
from app.agents.guardrails_system import validate_agent_response, validate_user_input, generate_user_friendly_violation_message
# Agent imports will be done lazily to avoid startup hanging

class DocumentProcessingState(TypedDict):
    """State for document processing workflow"""
    # Request context
    request_id: str
    user_id: int
    session_id: Optional[int]
    
    # Input
    file_path: str
    file_type: str
    file_size: int
    
    # Processing steps
    ocr_text: Optional[str]
    ocr_confidence: Optional[float]
    document_type: Optional[str]
    classification_confidence: Optional[float]
    routing_decision: Optional[str]
    user_question: Optional[str]
    
    # Agent processing results
    agent_results: Dict[str, Any]
    
    # Output
    processed_data: Dict[str, Any]
    processing_complete: bool
    error_message: Optional[str]
    
    # Debug timing data
    timing_data: Dict[str, float]
    step_start_times: Dict[str, float]

class DocumentProcessingOrchestrator:
    """Orchestrator for document processing workflow with agent routing"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.DOCUMENT_WORKFLOW_MODEL or settings.DEFAULT_AI_MODEL, 
            temperature=settings.DOCUMENT_WORKFLOW_TEMPERATURE or 0.1
        )
        self.ocr_toolkit = OCRToolkit()
        self.memory_saver = MemorySaver()
        self.workflow = self._build_workflow()
        
        # Agent mapping - will be populated lazily
        self._processing_agents = None
    
    @property
    def processing_agents(self) -> Dict[str, Any]:
        """Lazy-loaded processing agents"""
        if self._processing_agents is None:
            # Import agents only when needed to avoid circular imports
            from app.agents.vitals_agent import vitals_agent
            from app.agents.pharmacy_agent import pharmacy_agent
            from app.agents.lab_agent import lab_agent
            from app.agents.prescription_agent import prescription_agent
            
            self._processing_agents = {
                "vitals": vitals_agent(),
                "pharmacy": pharmacy_agent(),
                "lab": lab_agent(),
                "prescription": prescription_agent()
            }
        return self._processing_agents
    
    def _build_workflow(self) -> StateGraph:
        """Build the document processing workflow"""
        
        workflow = StateGraph(DocumentProcessingState)

        # Add nodes
        workflow.add_node("extract_text", self.extract_text)
        workflow.add_node("classify_document", self.classify_document)
        workflow.add_node("process_with_agents", self.process_with_agents)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("handle_error", self.handle_error)
        
        # Set entry point by adding an edge from the START node
        workflow.add_edge(START, "extract_text")
        
        # Add edges
        workflow.add_edge("extract_text", "classify_document")
        workflow.add_conditional_edges(
            "classify_document",
            self.determine_processing_path,
            {
                "process": "process_with_agents",
                "error": "handle_error"
            }
        )
        workflow.add_edge("process_with_agents", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile(checkpointer=self.memory_saver)
    
    async def process_document(
        self,
        file_path: str,
        file_type: str,
        user_id: int,
        session_id: Optional[int] = None,
        user_question: Optional[str] = None,
        cached_ocr_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main entry point for document processing"""
        
        overall_start = time.time()
        request_id = str(uuid.uuid4())
        
        print(f"📊 [DEBUG] Starting document processing at {datetime.now().isoformat()}")
        print(f"📊 [DEBUG] File: {file_path}")
        print(f"📊 [DEBUG] Type: {file_type}")
        print(f"📊 [DEBUG] User ID: {user_id}")
        print(f"📊 [DEBUG] Session ID: {session_id}")
        
        # Check if we have cached OCR data
        if cached_ocr_data:
            print(f"📊 [DEBUG] Using cached OCR data (length: {cached_ocr_data.get('text_length', 0)} chars)")
        
        with trace_agent_operation(
            "DocumentProcessingOrchestrator",
            "process_document",
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            # Add file upload context for dashboard visibility
            user_message=f"File upload: {Path(file_path).name}" + (f" - {user_question}" if user_question else ""),
            file_path=file_path,
            file_type=file_type,
            has_user_question=bool(user_question),
            processing_type="file_upload_workflow"
        ):
            # Initialize state with cached OCR data if available
            initial_state = DocumentProcessingState(
                request_id=request_id,
                user_id=user_id,
                session_id=session_id,
                file_path=file_path,
                file_type=file_type,
                file_size=0,
                ocr_text=cached_ocr_data.get("text") if cached_ocr_data else None,
                ocr_confidence=cached_ocr_data.get("confidence", 0.8) if cached_ocr_data else None,
                document_type=None,
                classification_confidence=None,
                routing_decision=None,
                user_question=user_question,
                agent_results={},
                processed_data=None,
                processing_complete=False,
                error_message=None,
                timing_data={},
                step_start_times={}
            )
            
            # Add cached OCR timing data if available
            if cached_ocr_data:
                initial_state["timing_data"]["cached_ocr_reuse"] = 0.001  # Minimal time for reuse
            
            print(f"📊 [DEBUG] About to run workflow...")
            workflow_start = time.time()
            
            # Run the workflow
            result = await self.workflow.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": request_id}}
            )
            
            workflow_duration = time.time() - workflow_start
            overall_duration = time.time() - overall_start
            
            print(f"📊 [DEBUG] Workflow completed in {workflow_duration:.2f}s")
            print(f"📊 [DEBUG] Total document processing time: {overall_duration:.2f}s")
            print(f"📊 [DEBUG] Processing status: {result.get('processing_complete', False)}")
            if result.get('error_message'):
                print(f"📊 [DEBUG] Error: {result['error_message']}")
            
            # Add timing data to result
            if not result.get("timing_data"):
                result["timing_data"] = {}
            result["timing_data"]["workflow_execution"] = workflow_duration
            result["timing_data"]["total_processing"] = overall_duration
            
            # Return the processed_data if available, otherwise return the full result
            if result.get("processed_data"):
                processed_data = result["processed_data"]
                # Add timing data to the processed response
                processed_data["timing_data"] = result["timing_data"]
                processed_data["processing_complete"] = result.get("processing_complete", False)
                
                print(f"📊 [DEBUG] Returning processed_data with status: {processed_data.get('processing_status')}")
                return processed_data
            else:
                print(f"📊 [DEBUG] No processed_data found, returning full result")
                return result
    
    async def extract_text(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """Extract text from uploaded document using OCR or use cached data"""
        
        step_start = time.time()
        state["step_start_times"]["extract_text"] = step_start
        print(f"🔤 [DEBUG] Starting text extraction at {datetime.now().isoformat()}")
        
        with trace_agent_operation(
            "DocumentProcessingOrchestrator",
            "extract_text",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"],
            # Add file context for dashboard visibility
            user_message=f"File upload: {Path(state['file_path']).name}" + (f" - {state['user_question']}" if state.get('user_question') else ""),
            file_type=state["file_type"],
            has_cached_ocr=bool(state.get("ocr_text")),
            processing_step="text_extraction"
        ):
            try:
                # Check if we already have cached OCR data
                if state.get("ocr_text"):
                    print(f"🔤 [DEBUG] ✅ Using cached OCR data from validation")
                    print(f"🔤 [DEBUG] Cached text length: {len(state['ocr_text'])} characters")
                    
                    # Ensure we have a confidence value
                    if state.get("ocr_confidence") is None:
                        state["ocr_confidence"] = 0.8  # Default confidence
                        print(f"🔤 [DEBUG] Set default confidence: 0.8")
                    else:
                        print(f"🔤 [DEBUG] Cached confidence: {state['ocr_confidence']}")
                    
                    print(f"🔤 [DEBUG] Text preview: {state['ocr_text'][:200]}...")
                    
                    step_duration = time.time() - step_start
                    state["timing_data"]["extract_text"] = step_duration
                    state["timing_data"]["ocr_cache_reuse"] = step_duration  # Track cache reuse time
                    
                    log_document_processing_step(
                        "ocr_cache_reuse",
                        0,  # Document ID
                        {
                            "text_length": len(state["ocr_text"]),
                            "confidence": state["ocr_confidence"],
                            "cache_reuse_duration": step_duration,
                            "total_duration": step_duration
                        },
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        request_id=state["request_id"]
                    )
                    
                    print(f"✅ [DEBUG] extract_text completed using cache in {step_duration:.2f}s")
                    return state
                
                # No cached data - perform OCR extraction
                print(f"🔤 [DEBUG] No cached OCR data, performing extraction")
                print(f"🔤 [DEBUG] File type: {state['file_type']}")
                print(f"🔤 [DEBUG] About to run OCR...")
                ocr_start = time.time()
                
                # Use OCRToolkit to extract text
                if state["file_type"].lower() == "pdf":
                    ocr_text = self.ocr_toolkit._extract_text_from_pdf(Path(state["file_path"]))
                else:
                    ocr_text = self.ocr_toolkit._extract_text_from_image(Path(state["file_path"]))
                
                ocr_duration = time.time() - ocr_start
                print(f"🔤 [DEBUG] OCR completed in {ocr_duration:.2f}s")
                
                # Step: Validate OCR-extracted content with guardrails (REQUIRED - different from user input)
                try:
                    print(f"🛡️ [DEBUG] Validating OCR-extracted content...")
                    validation_start = time.time()
                    
                    ocr_validation = await validate_user_input(
                        user_input=ocr_text,
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        context={
                            "agent": "document_processing_workflow",
                            "content_type": "ocr_extracted_text",
                            "document_type": state["file_type"],
                            "request_id": state["request_id"],
                            "validation_reason": "OCR content safety check"
                        }
                    )
                    
                    validation_duration = time.time() - validation_start
                    state["timing_data"]["ocr_validation"] = validation_duration
                    
                    # Log validation results
                    log_document_processing_step(
                        "ocr_content_validation",
                        0,  # Document ID
                        {
                            "is_safe": ocr_validation.is_safe,
                            "violations_count": len(ocr_validation.violations),
                            "confidence_score": ocr_validation.confidence_score,
                            "original_length": len(ocr_text),
                            "filtered_length": len(ocr_validation.filtered_content),
                            "validation_duration": validation_duration,
                            "violation_types": [v.get("type") for v in ocr_validation.violations],
                            "validation_reason": "OCR extracted content requires separate safety validation"
                        },
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        request_id=state["request_id"]
                    )
                    
                    # Use filtered OCR content for further processing
                    if ocr_validation.violations:
                        print(f"🛡️ [DEBUG] OCR content had {len(ocr_validation.violations)} violations, using filtered version")
                        state["ocr_text"] = ocr_validation.filtered_content
                        
                        # Store validation info for transparency
                        state["ocr_validation"] = {
                            "original_length": len(ocr_text),
                            "filtered_length": len(ocr_validation.filtered_content),
                            "violations_filtered": len(ocr_validation.violations),
                            "safety_score": ocr_validation.confidence_score
                        }
                    else:
                        print(f"✅ [DEBUG] OCR content passed all safety checks")
                        state["ocr_text"] = ocr_text
                        state["ocr_validation"] = {
                            "original_length": len(ocr_text), 
                            "filtered_length": len(ocr_text),
                            "violations_filtered": 0,
                            "safety_score": ocr_validation.confidence_score
                        }
                
                except Exception as validation_error:
                    print(f"⚠️ [DEBUG] OCR validation failed: {validation_error}")
                    # If validation fails, use original text but log the issue
                    state["ocr_text"] = ocr_text
                    state["ocr_validation"] = {
                        "validation_failed": True,
                        "error": str(validation_error),
                        "safety_score": 0.5  # Unknown safety
                    }
                
                # Log extraction completion
                log_document_processing_step(
                    "ocr_extraction_completed",
                    0,  # Document ID
                    {
                        "text_length": len(state["ocr_text"]),
                        "extraction_source": "OCR",
                        "extraction_time": ocr_duration,
                        "confidence_score": 0.8,  # Assuming default confidence
                        "pages_processed": 1,  # Assuming single page
                        "validation_applied": True,
                        "safety_validated": state.get("ocr_validation", {}).get("safety_score", 0.5)
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                step_duration = time.time() - step_start
                state["timing_data"]["extract_text"] = step_duration
                state["timing_data"]["ocr_only"] = ocr_duration
                
                log_document_processing_step(
                    "ocr_extraction",
                    0,  # Document ID
                    {
                        "text_length": len(state.get("ocr_text", "")),
                        "confidence": state["ocr_confidence"],
                        "ocr_duration": ocr_duration,
                        "total_duration": step_duration
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                print(f"✅ [DEBUG] extract_text completed with OCR in {step_duration:.2f}s")
                return state
                
            except Exception as e:
                step_duration = time.time() - step_start
                state["timing_data"]["extract_text"] = step_duration
                print(f"❌ [DEBUG] extract_text failed in {step_duration:.2f}s: {str(e)}")
                state["error_message"] = f"OCR extraction failed: {str(e)}"
                return state
    
    async def classify_document(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """Classify the document type using LLM"""
        
        with trace_agent_operation(
            "DocumentProcessingOrchestrator",
            "classify_document",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"],
            # Add file context for dashboard visibility
            user_message=f"File upload: {Path(state['file_path']).name}" + (f" - {state['user_question']}" if state.get('user_question') else ""),
            file_type=state["file_type"],
            ocr_text_length=len(state.get("ocr_text", "")),
            processing_step="document_classification"
        ):
            try:
                classification_prompt = f"""
                Analyze the following medical document text and classify it into one of these categories:
                - vitals: Vital signs, blood pressure readings, weight measurements
                - pharmacy: Pharmacy bills, medication receipts, drug purchase records
                - lab: Laboratory reports, blood tests, urine tests, diagnostic results
                - prescription: Medical prescriptions, medication orders from doctors. one of way to identify is if it has a doctor's name and a patient's name and if it handwritten or if it mentions OUT-PATIENT RECORD
                
                Text to classify:
                {(state.get("ocr_text", "") or "")[:1000]}...
                
                Respond with ONLY the category name (vitals, pharmacy, lab, or prescription).
                If unclear, respond with the most likely category.
                """
                
                messages = [
                    SystemMessage(content="You are a medical document classifier."),
                    HumanMessage(content=classification_prompt)
                ]
                
                response = self.llm.invoke(messages)
                
                # Check if response is None or if content is None
                if response is None or response.content is None:
                    print("⚠️ [DocumentProcessingOrchestrator] LLM response or content is None, defaulting to vitals")
                    classified_type = "vitals"
                else:
                    classified_type = response.content.strip().lower()
                
                # Validate classification
                if classified_type not in ["vitals", "pharmacy", "lab", "prescription"]:
                    # Default to vitals if classification is unclear
                    print(f"⚠️ [DocumentProcessingOrchestrator] Invalid classification '{classified_type}', defaulting to vitals")
                    classified_type = "vitals"
                
                state["document_type"] = classified_type
                state["classification_confidence"] = 0.8  # Default confidence
                
                log_document_processing_step(
                    "document_classification",
                    0,
                    {
                        "classified_type": classified_type,
                        "confidence": state["classification_confidence"]
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Document classification failed: {str(e)}"
                return state
    
    def determine_processing_path(self, state: DocumentProcessingState) -> str:
        """Determine whether to proceed with processing or handle error"""
        if state.get("error_message"):
            return "error"
        return "process"
    
    async def process_with_agents(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """Process document using specialized agents"""
        
        with trace_agent_operation(
            "DocumentProcessingOrchestrator",
            "process_with_agents",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"],
            # Add file context for dashboard visibility
            user_message=f"File upload: {Path(state['file_path']).name}" + (f" - {state['user_question']}" if state.get('user_question') else ""),
            file_type=state["file_type"],
            document_type=state.get("document_type"),
            processing_step="agent_processing"
        ):
            try:
                classified_type = state.get("document_type")
                if not classified_type:
                    state["error_message"] = "Document type not found in state"
                    return state
                    
                agent = self.processing_agents.get(classified_type)
                
                if not agent:
                    state["error_message"] = f"No agent found for document type: {classified_type}"
                    return state
                
                # Ensure state has required fields with defaults
                ocr_text = state.get("ocr_text", "")
                user_id = state.get("user_id")
                session_id = state.get("session_id")
                
                if not user_id:
                    state["error_message"] = "User ID not found in state"
                    return state
                
                # Extract data using specialized agent
                extraction_result = await agent.process_request(
                    "extract",
                    {
                        "ocr_text": ocr_text,
                        "document_type": classified_type,
                        "file_path": state.get("file_path"),  # Pass file path to agent
                        "file_type": state.get("file_type")   # Pass file type to agent
                    },
                    user_id,
                    session_id
                )
                
                # Ensure agent_results is initialized
                if "agent_results" not in state:
                    state["agent_results"] = {}
                
                # Store extraction result
                state["agent_results"][f"{classified_type}_extraction"] = extraction_result or {}
                
                # Store data if extraction was successful AND no user question
                storage_result = {}
                extraction_response = extraction_result.get("response_message", {})
                
                # Only store to database if there's no user question (file-only upload)
                if extraction_response.get("success") and extraction_response.get("data") and not state.get("user_question"):
                    print(f"📊 [DEBUG] File-only upload: storing data to database")
                    storage_result = await agent.process_request(
                        "store",
                        {
                            "extraction_request": extraction_response.get("data"),
                            "file_path": state.get("file_path"),  # Pass file path to storage
                            "file_type": state.get("file_type")   # Pass file type to storage
                        },
                        user_id,
                        session_id
                    )
                elif state.get("user_question"):
                    print(f"📊 [DEBUG] File+question upload: skipping database storage, data available for analysis only")
                    # Create a mock successful storage result for consistency
                    storage_result = {
                        "response_message": {
                            "success": True,
                            "data": {"records_stored": 0},
                            "message": "Data extracted for analysis only - not stored to database"
                        }
                    }
                
                # Store storage result separately
                state["agent_results"][f"{classified_type}_storage"] = storage_result
                
                log_agent_interaction(
                    "DocumentProcessingOrchestrator",
                    agent.agent_name,
                    "agent_processing_complete",
                    {
                        "extraction_success": extraction_response.get("success", False),
                        "storage_success": storage_result.get("response_message", {}).get("success", False)
                    },
                    user_id=user_id,
                    session_id=session_id,
                    request_id=state["request_id"]
                )
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Agent processing failed: {str(e)}"
                return state
    
    async def generate_response(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """Generate final response with processed data"""
        
        with trace_agent_operation(
            "DocumentProcessingOrchestrator",
            "generate_response",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"],
            # Add file context for dashboard visibility
            user_message=f"File upload: {Path(state['file_path']).name}" + (f" - {state['user_question']}" if state.get('user_question') else ""),
            file_type=state["file_type"],
            document_type=state.get("document_type"),
            processing_step="response_generation"
        ):
            try:
                classified_type = state["document_type"]
                extraction_result = state["agent_results"].get(f"{classified_type}_extraction", {})
                storage_result = state["agent_results"].get(f"{classified_type}_storage", {})
                
                # Access the response_message correctly
                extraction_response = extraction_result.get("response_message", {})
                storage_response = storage_result.get("response_message", {})
                
                # Handle duplicate detection case - lab agent returns state directly
                storage_state = storage_result if isinstance(storage_result, dict) else {}
                processing_msg = storage_state.get("processing_status_message")
                processing_summary_direct = storage_state.get("processing_summary", {})
                
                # Also check in response_message structure (after finalize_response)
                if not processing_msg:
                    processing_msg = storage_response.get("processing_status_message")
                if not processing_summary_direct:
                    processing_summary_direct = storage_response.get("processing_summary", {})
                
                # DEBUG: Print what we're receiving
                print(f"🔍 [DEBUG] storage_result keys: {list(storage_result.keys()) if isinstance(storage_result, dict) else 'Not a dict'}")
                print(f"🔍 [DEBUG] processing_msg: {processing_msg}")
                print(f"🔍 [DEBUG] processing_summary_direct: {processing_summary_direct}")
                print(f"🔍 [DEBUG] storage_response: {storage_response}")
                
                # Determine overall processing success
                extraction_success = extraction_result.get("response_message", {}).get("success", False)
                
                # Handle both normal storage success and special processing scenarios (duplicates, etc.)
                storage_success = (
                    storage_response.get("success", False) or  # Normal success
                    processing_summary_direct.get("success", False) or  # Special scenario success
                    bool(processing_msg)  # Has processing status message
                )
                
                overall_success = extraction_success and storage_success
                
                # Prepare storage summary data
                if state.get("user_question"):
                    # File+question scenario - data extracted but not stored
                    print(f"🔍 [DEBUG] File+question scenario: data extracted for analysis only")
                    storage_summary = {
                        "records_stored": 0,
                        "success": True,
                        "message": "Data extracted for analysis only - not stored to database",
                        "scenario": "analysis_only"
                    }
                elif processing_msg and processing_summary_direct:
                    # Special processing scenario (duplicates, validation issues, etc.)
                    scenario = processing_summary_direct.get("scenario", "unknown")
                    print(f"🔍 [DEBUG] Using special processing scenario: {scenario}")
                    storage_summary = {
                        "records_stored": processing_summary_direct.get("new_records", 0),
                        "duplicates_skipped": processing_summary_direct.get("duplicates_skipped", 0), 
                        "success": True,
                        "message": processing_summary_direct.get("message", "Special processing completed"),
                        "scenario": scenario
                    }
                else:
                    # Normal file-only case
                    print(f"🔍 [DEBUG] Using normal file-only case")
                    storage_summary = {
                        "records_stored": storage_response.get("data", {}).get("records_stored", 0),
                        "success": storage_response.get("success", False)
                    }
                
                # Create response data
                response_data = {
                    "document_type": classified_type,
                    "processing_status": "success" if overall_success else "failed",
                    "ocr_confidence": state["ocr_confidence"],
                    "classification_confidence": state["classification_confidence"],
                    "extracted_data": extraction_response.get("data", {}),
                    "storage_summary": storage_summary,
                    "processing_details": {
                        "extraction_success": extraction_success,
                        "storage_success": storage_success,
                        "extraction_error": extraction_response.get("error") if not extraction_success else None,
                        "storage_error": storage_response.get("error") if not storage_success else None
                    }
                }
                
                # Add processing status message if present
                if processing_msg:
                    response_data["processing_status_message"] = processing_msg
                
                # Add user question response if provided
                if state["user_question"]:
                    # Use the extracted data to answer the user's question
                    answer = await self._answer_user_question(
                        state["user_question"],
                        extraction_response.get("data", {}),
                        classified_type,
                        state
                    )
                    response_data["question_answer"] = answer
                
                state["processed_data"] = response_data
                state["processing_complete"] = True
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Response generation failed: {str(e)}"
                return state
    
    async def _answer_user_question(
        self,
        question: str,
        extracted_data: Dict[str, Any],
        document_type: str,
        state: DocumentProcessingState
    ) -> str:
        """Answer user question using extracted data"""
        
        try:
            # Get recent data from the same agent for context
            agent = self.processing_agents.get(document_type)
            if agent:
                context_data = await agent.process_request(
                    "retrieve",
                    {"retrieval_request": {"days_back": 30, "limit": 10}},
                    state["user_id"],
                    state["session_id"]
                )
                context = context_data.get("data", {})
            else:
                context = {}
            
            answer_prompt = f"""
            Based on the following medical document data and historical context, answer the user's question.
            
            Document Type: {document_type}
            
            Current Document Data:
            {extracted_data}
            
            Historical Context (last 30 days):
            {context}
            
            User Question: {question}
            
            Provide a helpful, accurate response based on the available data. If the data doesn't contain 
            enough information to fully answer the question, say so and explain what information is available.
            """
            
            messages = [
                SystemMessage(content="You are a medical data assistant helping interpret health documents."),
                HumanMessage(content=answer_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            # Check if response is None or if content is None
            if response is None or response.content is None:
                return "I couldn't process your question due to an empty response from the AI system."
            
            # Validate response with guardrails
            try:
                response_validation = await validate_agent_response(
                    response_content=response.content,
                    agent_name="document_processing_workflow",
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    is_medical_response=True  # Document processing often involves medical data
                )
                
                # Use filtered content and log any violations
                if response_validation.violations:
                    print(f"📄 [DEBUG] Document response had {len(response_validation.violations)} guardrail violations")
                
                # Use the filtered/enhanced content (may include medical disclaimers)
                validated_response = response_validation.filtered_content
                
                # If response is not safe, replace with safe fallback
                if not response_validation.is_safe:
                    validated_response = "I cannot provide that response as it may not meet our safety guidelines. The document has been processed and stored, but I recommend consulting with your healthcare provider for interpretation of the medical data."
                
                return validated_response
                
            except Exception as e:
                # If guardrails fail, log error but continue with original response
                print(f"⚠️ [DEBUG] Document response validation failed: {e}")
                return response.content
            
        except Exception as e:
            return f"I couldn't process your question due to an error: {str(e)}"
    
    async def handle_error(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """Handle errors in processing"""
        
        with trace_agent_operation(
            "DocumentProcessingOrchestrator",
            "handle_error",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"],
            # Add file context for dashboard visibility
            user_message=f"File upload: {Path(state['file_path']).name}" + (f" - {state['user_question']}" if state.get('user_question') else ""),
            file_type=state["file_type"],
            error_message=state.get("error_message"),
            processing_step="error_handling"
        ):
            error_response = {
                "document_type": state.get("document_type", "unknown"),
                "processing_status": "error",
                "error_message": state.get("error_message", "Unknown error occurred"),
                "ocr_confidence": state.get("ocr_confidence"),
                "partial_data": {
                    "ocr_text": state.get("ocr_text", "")[:200] + "..." if state.get("ocr_text") else None,
                    "document_type": state.get("document_type")
                }
            }
            
            state["processed_data"] = error_response
            state["processing_complete"] = True
            
            return state

async def process_health_document(
    file_path: str,
    file_type: str,
    user_id: int,
    session_id: Optional[int] = None,
    user_question: Optional[str] = None,
    cached_ocr_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process a health document using the orchestrator"""
    
    orchestrator = DocumentProcessingOrchestrator()
    return await orchestrator.process_document(
        file_path=file_path,
        file_type=file_type,
        user_id=user_id,
        session_id=session_id,
        user_question=user_question,
        cached_ocr_data=cached_ocr_data
    )

async def process_document_with_workflow(
    file_path: str,
    file_type: str,
    user_id: int,
    session_id: Optional[int] = None,
    user_question: Optional[str] = None,
    cached_ocr_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process a document using the workflow - alias for process_health_document"""
    
    return await process_health_document(
        file_path=file_path,
        file_type=file_type,
        user_id=user_id,
        session_id=session_id,
        user_question=user_question,
        cached_ocr_data=cached_ocr_data
    )

# Global orchestrator instance
# document_orchestrator = DocumentProcessingOrchestrator()  # Commented to prevent startup hanging

# Lazy-loaded document orchestrator
_document_orchestrator = None

def get_document_orchestrator():
    """Get or create the document orchestrator instance"""
    global _document_orchestrator
    if _document_orchestrator is None:
        _document_orchestrator = DocumentProcessingOrchestrator()
    return _document_orchestrator

# For backward compatibility
def document_orchestrator():
    return get_document_orchestrator() 