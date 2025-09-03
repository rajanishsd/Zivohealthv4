import asyncio
import json
import uuid
import time
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.utils.timezone import now_local, isoformat_now

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from app.db.session import SessionLocal
from app.models.health_data import AgentMemory, LabReport, PharmacyBill, MedicalImage
from app.models.chat_session import Prescription
from app.agents.document_processing_workflow import process_document_with_workflow
# Agent imports will be done lazily to avoid startup hanging
from app.core.config import settings
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction
from app.core.chatgpt_logger import log_chatgpt_interaction
from app.agents.lab_agent import get_lab_agent
from app.agents.vitals_agent import get_vitals_agent  
from app.agents.pharmacy_agent import get_pharmacy_agent
from app.agents.prescription_agent import get_prescription_agent
from app.agents.medical_doctor_agent import get_medical_doctor_agent
from app.agents.nutrition_agent import get_nutrition_agent
from app.agents.guardrails_system import validate_user_input, validate_agent_response

class CustomerAgentState(TypedDict):
    """State for customer agent processing"""
    # Request context
    request_id: str
    user_id: int
    session_id: Optional[int]
    
    # Input
    user_message: str
    original_user_message: Optional[str]  # Keep original for reference
    uploaded_file: Optional[Dict[str, Any]]
    
    # NEW: Guardrails validation results (centralized)
    guardrails_validation: Optional[Dict[str, Any]]
    
    # Analysis
    request_type: str  # "file_only", "question_only", "file_and_question"
    requires_file_processing: bool
    requires_data_retrieval: bool
    routing_decision: Optional[Dict[str, Any]]  # Intelligent router decision
    generated_title: Optional[str]  # AI-generated title for the session
    
    # Agent swarm coordination
    active_agents: List[str]
    agent_responses: Dict[str, Dict[str, Any]]
    parallel_processing: bool
    coordination_mode: str  # "sequential", "parallel", "hybrid"
    
    # Processing results
    file_processing_result: Optional[Dict[str, Any]]
    retrieved_data: Dict[str, Any]
    
    # Response
    response_message: str
    processing_complete: bool
    error_message: Optional[str]
    
    # Debug timing data
    timing_data: Dict[str, float]
    step_start_times: Dict[str, float]

class EnhancedCustomerAgent:
    """Enhanced customer agent with specialized health data capabilities and agent swarm coordination"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.CUSTOMER_AGENT_MODEL or settings.DEFAULT_AI_MODEL, 
            temperature=settings.CUSTOMER_AGENT_TEMPERATURE or 0.3
        )
        self.memory_saver = MemorySaver()
        self.workflow = self._build_workflow()
        
        # Agent mapping for data retrieval - will be populated lazily
        self._data_agents = None
        
        # Agent swarm configuration
        self.agent_coordination_config = {
            "parallel_threshold": 2,  # Number of agents to trigger parallel processing
            "timeout_seconds": 120,   # Timeout for agent operations (increased for OCR processing)
            "retry_attempts": 2,      # Retry attempts for failed agent operations
            "relevance_threshold": 0.3  # Minimum relevance score for agent inclusion
        }
    
    @property
    def data_agents(self) -> Dict[str, Any]:
        """Lazy loading of specialized agents to avoid startup hanging"""
        return {
            "lab": get_lab_agent(),
            "vitals": get_vitals_agent(), 
            "pharmacy": get_pharmacy_agent(),
            "prescription": get_prescription_agent(),
            "medical_doctor": get_medical_doctor_agent(),
            "nutrition": get_nutrition_agent()
        }
    
    def _build_workflow(self) -> StateGraph:
        """Build the enhanced customer agent workflow with intelligent routing"""
        
        workflow = StateGraph(CustomerAgentState)
        
        # Add nodes
        workflow.add_node("analyze_request", self.analyze_request)
        workflow.add_node("smart_file_question_router", self.smart_file_question_router)  # New smart router
        workflow.add_node("process_file", self.process_file)
        workflow.add_node("execute_medical_doctor", self.execute_medical_doctor)  # Direct medical doctor route
        workflow.add_node("intelligent_router", self.intelligent_router)  # New smart router
        workflow.add_node("execute_lab_agent", self.execute_lab_agent)
        workflow.add_node("execute_vitals_agent", self.execute_vitals_agent)
        workflow.add_node("execute_pharmacy_agent", self.execute_pharmacy_agent)
        workflow.add_node("execute_prescription_agent", self.execute_prescription_agent)
        workflow.add_node("execute_nutrition_agent", self.execute_nutrition_agent)
        workflow.add_node("execute_multi_agent", self.execute_multi_agent)  # For complex queries
        workflow.add_node("execute_medical_consultation", self.execute_medical_consultation)  # Medical doctor agent
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("handle_error", self.handle_error)
        
        # Set entry point by adding an edge from the START node
        workflow.add_edge(START, "analyze_request")
        
        # Add edges
        workflow.add_conditional_edges(
            "analyze_request",
            self.determine_processing_path,
            {
                "smart_file_question_router": "smart_file_question_router",  # New smart router path
                "file_processing": "process_file",
                "medical_doctor": "execute_medical_doctor",  # Direct route to medical doctor
                "data_retrieval": "intelligent_router",  # Route through intelligent router
                "error": "handle_error"
            }
        )
        
        # Smart router for file+question scenarios
        workflow.add_conditional_edges(
            "smart_file_question_router",
            self.determine_smart_router_path,
            {
                "file_processing": "process_file",  # Process file if document-specific question
                "medical_consultation": "execute_medical_consultation",  # Skip file processing for general questions
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "process_file",
            self.after_file_processing,
            {
                "respond": "generate_response",
                "coordinate_agents": "intelligent_router",  # Use smart routing for follow-up questions
                "error": "handle_error"
            }
        )
        
        # Smart routing based on intent classification
        workflow.add_conditional_edges(
            "intelligent_router",
            self.route_to_specific_agent,
            {
                "lab_data": "execute_lab_agent",
                "vitals": "execute_vitals_agent", 
                "pharmacy": "execute_pharmacy_agent",
                "prescription": "execute_prescription_agent",
                "nutrition": "execute_nutrition_agent",
                "multi_domain": "execute_multi_agent",
                "medical_consultation": "execute_medical_consultation",  # Medical consultation path
                "unclear": "execute_multi_agent",  # Fallback to assessment approach
                "error": "handle_error"
            }
        )
        
        # All agent execution nodes lead to response generation
        workflow.add_edge("execute_medical_doctor", "generate_response")  # Medical doctor to response
        workflow.add_edge("execute_lab_agent", "generate_response")
        workflow.add_edge("execute_vitals_agent", "generate_response")
        workflow.add_edge("execute_pharmacy_agent", "generate_response")
        workflow.add_edge("execute_prescription_agent", "generate_response")
        workflow.add_edge("execute_nutrition_agent", "generate_response")
        workflow.add_edge("execute_multi_agent", "generate_response")
        workflow.add_edge("execute_medical_consultation", "generate_response")  # Medical consultation to response
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile(checkpointer=self.memory_saver)
    
    async def process_request(
        self,
        user_message: str,
        user_id: int,
        session_id: Optional[int] = None,
        uploaded_file: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main entry point for customer agent processing with enhanced telemetry and guardrails"""
        
        request_id = f"customer_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Step 1: Validate user input with guardrails (ONLY for actual user messages, not file uploads)
        try:
            # Determine if this is a file-only upload or has an actual user message
            has_file = bool(uploaded_file)
            has_meaningful_message = user_message and user_message.strip() and len(user_message.strip()) > 3
            
            # Skip guardrails validation for file-only uploads or when message is just a filename
            if has_file and not has_meaningful_message:
                print(f"🛡️ [DEBUG] Skipping input validation for file-only upload")
                log_agent_interaction(
                    "EnhancedCustomerAgent",
                    "GuardrailsSystem", 
                    "validation_skipped",
                    {
                        "reason": "file_only_upload",
                        "has_file": True,
                        "message_length": len(user_message) if user_message else 0,
                        "user_message": user_message[:50] if user_message else "None"
                    },
                    user_id=user_id,
                    session_id=session_id
                )
                
                filtered_message = user_message or ""
                # Create a pass-through validation result
                input_validation = type('GuardrailResult', (), {
                    'is_safe': True, 
                    'filtered_content': filtered_message, 
                    'violations': [], 
                    'confidence_score': 1.0
                })()
            elif has_file and self._is_likely_filename(user_message):
                print(f"🛡️ [DEBUG] Skipping input validation for filename-like input: {user_message}")
                log_agent_interaction(
                    "EnhancedCustomerAgent",
                    "GuardrailsSystem", 
                    "validation_skipped",
                    {
                        "reason": "filename_detected",
                        "has_file": True,
                        "detected_filename": user_message,
                        "message_length": len(user_message)
                    },
                    user_id=user_id,
                    session_id=session_id
                )
                
                filtered_message = user_message
                input_validation = type('GuardrailResult', (), {
                    'is_safe': True, 
                    'filtered_content': filtered_message, 
                    'violations': [], 
                    'confidence_score': 1.0
                })()
            else:
                # Validate actual user messages normally
                print(f"🛡️ [DEBUG] Validating user message: {user_message[:50]}...")
                log_agent_interaction(
                    "EnhancedCustomerAgent",
                    "GuardrailsSystem", 
                    "validation_initiated",
                    {
                        "reason": "actual_user_message",
                        "has_file": has_file,
                        "message_length": len(user_message),
                        "message_preview": user_message[:100]
                    },
                    user_id=user_id,
                    session_id=session_id
                )
                input_validation = await validate_user_input(
                    user_input=user_message,
                    user_id=user_id,
                    session_id=session_id,
                    context={
                        "agent": "enhanced_customer_agent",
                        "has_file": bool(uploaded_file),
                        "file_type": uploaded_file.get("file_type") if uploaded_file else None,
                        "request_id": request_id,
                        "validation_reason": "User message validation (not filename)"
                    }
                )
            
            # If input is not safe, return filtered response
            if not input_validation.is_safe:
                # Generate user-friendly violation message
                from app.agents.guardrails_system import healthcare_guardrails
                user_friendly_message = healthcare_guardrails._generate_user_friendly_violation_message(
                    input_validation.violations
                )
                
                log_agent_interaction(
                    "EnhancedCustomerAgent",
                    "GuardrailsViolation",
                    "input_blocked",
                    {
                        "violations": input_validation.violations,
                        "confidence_score": input_validation.confidence_score,
                        "original_message_length": len(user_message),
                        "filtered_message_length": len(input_validation.filtered_content),
                        "user_friendly_message_provided": True,
                        "had_file": has_file,
                        "validation_skipped": False
                    },
                    user_id=user_id,
                    session_id=session_id
                )
                
                return {
                    "success": False,
                    "response": user_friendly_message,  # Use detailed, helpful message
                    "guardrails_blocked": True,
                    "violations": input_validation.violations,
                    "processing_time": 0.1,
                    "violation_help": "User received specific guidance on how to fix their request"
                }
            
            # Use filtered content for processing
            filtered_message = input_validation.filtered_content
            
        except Exception as e:
            # If guardrails fail, log error but continue with original message
            log_agent_interaction(
                "EnhancedCustomerAgent",
                "GuardrailsError",
                "validation_failed",
                {"error": str(e)},
                user_id=user_id,
                session_id=session_id
            )
            filtered_message = user_message
            # Create a default validation result for consistency
            input_validation = type('GuardrailResult', (), {
                'is_safe': True, 
                'filtered_content': user_message, 
                'violations': [], 
                'confidence_score': 1.0
            })()

        # Initialize state with enhanced telemetry and guardrails results
        state = CustomerAgentState(
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            user_message=filtered_message,  # Use filtered message
            original_user_message=user_message,  # Keep original for reference
            uploaded_file=uploaded_file,
            
            # NEW: Pass guardrails validation results to all agents
            guardrails_validation={
                "input_validation": {
                    "is_safe": input_validation.is_safe,
                    "filtered_content": input_validation.filtered_content,
                    "violations": input_validation.violations,
                    "confidence_score": input_validation.confidence_score,
                    "validated_at": datetime.utcnow().isoformat(),
                    "validated_by": "EnhancedCustomerAgent"
                }
            },
            
            # Initialize other required fields
            request_type="",
            requires_file_processing=False,
            requires_data_retrieval=False,
            routing_decision=None,
            active_agents=[],
            agent_responses={},
            parallel_processing=False,
            coordination_mode="sequential",
            file_processing_result=None,
            retrieved_data={},
            response_message="",
            processing_complete=False,
            error_message=None,
            timing_data={},
            step_start_times={}
        )
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "process_request",
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            # Add initial request details to metadata
            user_message=filtered_message[:200] + "..." if len(filtered_message) > 200 else filtered_message,
            has_uploaded_file=bool(uploaded_file),
            file_type=uploaded_file.get("file_type") if uploaded_file else None,
            file_name=uploaded_file.get("original_name") if uploaded_file else None,
            file_path=uploaded_file.get("file_path") if uploaded_file else None
        ):
            # Run the workflow with telemetry tracking
            result = await self.workflow.ainvoke(
                state,
                config={"configurable": {"thread_id": request_id}}
            )
            
            # Log final workflow metrics
            log_agent_interaction(
                "EnhancedCustomerAgent",
                "System",
                "workflow_completed",
                {
                    "total_agents_used": len(result.get("active_agents", [])),
                    "coordination_mode": result.get("coordination_mode"),
                    "parallel_processing": result.get("parallel_processing"),
                    "processing_complete": result.get("processing_complete"),
                    "has_error": bool(result.get("error_message"))
                },
                user_id=user_id,
                session_id=session_id,
                request_id=request_id
            )
            
            return {
                "response": result.get("response_message"),
                "processing_complete": result.get("processing_complete"),
                "error": result.get("error_message"),
                "generated_title": result.get("generated_title"),  # Add the generated title
                "agent_swarm_metrics": {
                    "active_agents": result.get("active_agents", []),
                    "coordination_mode": result.get("coordination_mode"),
                    "parallel_processing": result.get("parallel_processing")
                },
                "data": {
                    "file_processing": result.get("file_processing_result"),
                    "retrieved_data": result.get("retrieved_data"),
                    "agent_responses": result.get("agent_responses", {})
                },
                "timing_data": result.get("timing_data", {}),
                "step_start_times": result.get("step_start_times", {})
            }
    
    async def analyze_request(self, state: CustomerAgentState) -> CustomerAgentState:
        """Analyze the user request to determine processing path with enhanced telemetry"""
        
        step_start = time.time()
        state["step_start_times"]["analyze_request"] = step_start
        print(f"🔍 [DEBUG] Starting analyze_request at {isoformat_now()}")
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "analyze_request",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            try:
                has_file = bool(state["uploaded_file"])
                user_message = state["user_message"].strip()
                
                # Use AI to classify intent when there's both file and message
                if has_file and user_message:
                    intent_result = await self._classify_user_intent(user_message, has_file)
                    intent = intent_result["intent"]
                    title = intent_result["title"]
                    print(f"🧠 [DEBUG] AI Intent Classification: {intent}, Title: {title}")
                    
                    # Store the generated title in state
                    state["generated_title"] = title
                    
                    if intent == "document_upload":
                        state["request_type"] = "file_only"
                        state["requires_file_processing"] = True
                        state["requires_data_retrieval"] = False
                        print(f"📄 [DEBUG] Classified as document upload (file_only)")
                    elif intent == "data_question":
                        state["request_type"] = "file_and_question"
                        state["requires_file_processing"] = True
                        state["requires_data_retrieval"] = True
                        print(f"❓ [DEBUG] Classified as file with data question (file_and_question)")
                    elif intent == "document_only_question":
                        state["request_type"] = "file_and_question"
                        state["requires_file_processing"] = True
                        state["requires_data_retrieval"] = False  # No historical data retrieval needed
                        print(f"📄❓ [DEBUG] Classified as document-only question (file_and_question, no historical data)")
                    else:  # document_upload_with_question
                        state["request_type"] = "file_and_question"
                        state["requires_file_processing"] = True
                        state["requires_data_retrieval"] = False
                        print(f"📄❓ [DEBUG] Classified as file with question requiring historical data (file_and_question)")
                    
                    # CRITICAL DEBUG: Print the final classification
                    print(f"🚨 [CRITICAL DEBUG] Final classification for '{user_message[:50]}...': request_type='{state['request_type']}', requires_file_processing={state['requires_file_processing']}, requires_data_retrieval={state['requires_data_retrieval']}")
                        
                elif has_file and not user_message:
                    state["request_type"] = "file_only"
                    state["requires_file_processing"] = True
                    state["requires_data_retrieval"] = False
                    state["generated_title"] = "Health Record Update"
                    print(f"📄 [DEBUG] File only, no message")
                    
                elif not has_file and user_message:
                    # Use AI to classify question-only intent
                    question_result = await self._classify_question_intent(user_message)
                    question_intent = question_result["intent"]
                    title = question_result["title"]
                    print(f"🧠 [DEBUG] Question Intent Classification: {question_intent}, Title: {title}")
                    
                    # Store the generated title in state
                    state["generated_title"] = title
                    
                    if question_intent == "data_update":
                        state["request_type"] = "data_update"
                        state["requires_file_processing"] = True  # Process as structured data extraction
                        state["requires_data_retrieval"] = False
                        print(f"📝 [DEBUG] Classified as data update (treating as file processing)")
                    else:  # medical_question
                        state["request_type"] = "question_only"
                        state["requires_file_processing"] = False
                        state["requires_data_retrieval"] = True
                        print(f"❓ [DEBUG] Classified as medical question (question_only)")
                    
                else:
                    state["error_message"] = "No valid input provided"
                    state["generated_title"] = "Health Consultation"
                    print(f"❌ [DEBUG] No valid input")
                
                log_agent_interaction(
                    "EnhancedCustomerAgent",
                    "System",
                    "request_analyzed",
                    {
                        "request_type": state["request_type"],
                        "has_file": has_file,
                        "requires_file_processing": state.get("requires_file_processing", False),
                        "requires_data_retrieval": state.get("requires_data_retrieval", False),
                        "message_length": len(user_message),
                        "user_message": user_message[:200] + "..." if len(user_message) > 200 else user_message,
                        "file_type": state["uploaded_file"].get("file_type") if has_file else None,
                        "generated_title": state.get("generated_title", ""),
                        "ai_intent": intent if has_file and user_message else question_intent if not has_file and user_message else "rule_based"
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                step_duration = time.time() - step_start
                state["timing_data"]["analyze_request"] = step_duration
                print(f"✅ [DEBUG] analyze_request completed in {step_duration:.2f}s")
                
                return state
                
            except Exception as e:
                step_duration = time.time() - step_start
                state["timing_data"]["analyze_request"] = step_duration
                print(f"❌ [DEBUG] analyze_request failed in {step_duration:.2f}s: {str(e)}")
                state["error_message"] = f"Request analysis failed: {str(e)}"
                state["generated_title"] = "Health Consultation"
                return state
    
    async def _classify_user_intent(self, user_message: str, has_file: bool) -> Dict[str, str]:
        """Use AI to classify user intent for file + message scenarios and generate appropriate title"""
        
        classification_prompt = f"""
        Analyze this user message to determine their intent when uploading a health document and generate an appropriate title:

        User Message: "{user_message}"

        First, classify into ONE of these categories:

        1. "document_upload" - User wants to upload/process a document (store data) without asking questions
           Examples: "Please process this lab report", "Upload my test results", "Process this document"
        
        2. "data_question" - User is asking questions about their historical health data (may also upload)
           Examples: "What are my latest lab results?", "Show me my blood pressure trends", "Compare with last month"
        
        3. "document_only_question" - User uploads document and asks questions ONLY about the uploaded document
           Examples: "What does this lab report show?", "Explain this prescription", "What are the values in this document?", "Interpret these test results"
        
        4. "document_upload_with_question" - User uploads document AND asks questions comparing it with historical context
           Examples: "Process this lab report and compare with my previous results", "How do these results compare to normal?", "Are my values improving?"

        Then, generate a brief, descriptive title (3-6 words) based on the intent and content:

        For document_upload: Use "Health Record Update"
        For data_question: Generate a specific title based on what they're asking about (e.g., "Blood Pressure Trends", "Lab Results Review", "Medication History")
        For document_only_question: Generate a specific title based on the document topic (e.g., "Lab Report Explanation", "Document Analysis", "Test Results Review")
        For document_upload_with_question: Generate a specific title based on the health topic (e.g., "Lab Report Comparison", "Results Analysis", "Medical Review")

        Respond in this exact format:
        INTENT: [category_name]
        TITLE: [brief_title]
        """
        
        try:
            from langchain_openai import ChatOpenAI
            from langchain.schema import HumanMessage, SystemMessage
            
            llm = ChatOpenAI(
                model=settings.CUSTOMER_AGENT_MODEL or settings.DEFAULT_AI_MODEL, 
                temperature=0.1  # Lower temperature for classification tasks
            )
            
            messages = [
                SystemMessage(content="You are an intent classifier and title generator for health document processing."),
                HumanMessage(content=classification_prompt)
            ]
            
            # Log ChatGPT interaction
            messages_dict = [
                {"role": "system", "content": "You are an intent classifier and title generator for health document processing."},
                {"role": "user", "content": classification_prompt}
            ]
            
            response = llm.invoke(messages)
            
            # Log the interaction
            log_chatgpt_interaction(
                agent_name="EnhancedCustomerAgent",
                operation="classify_user_intent",
                request_data=messages_dict,
                response_data=response,
                model_name=settings.CUSTOMER_AGENT_MODEL or settings.DEFAULT_AI_MODEL,
                additional_metadata={"has_file": has_file, "user_message_length": len(user_message)}
            )
            
            if response and response.content:
                content = response.content.strip()
                
                # Parse the response to extract intent and title
                intent_match = None
                title_match = None
                
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('INTENT:'):
                        intent_match = line.replace('INTENT:', '').strip().lower()
                    elif line.startswith('TITLE:'):
                        title_match = line.replace('TITLE:', '').strip()
                
                if intent_match and intent_match in ["document_upload", "data_question", "document_only_question", "document_upload_with_question"]:
                    return {
                        "intent": intent_match,
                        "title": title_match or "Health Consultation"
                    }
                
        except Exception as e:
            print(f"⚠️ [DEBUG] AI classification failed: {str(e)}, falling back to simple upload")
            
        # Fallback: assume document upload if classification fails
        return {
            "intent": "document_upload",
            "title": "Health Record Update"
        }
    
    async def _classify_question_intent(self, user_message: str) -> Dict[str, str]:
        """Use AI to classify question-only intent to distinguish data updates from medical questions and generate appropriate title"""
        
        classification_prompt = f"""
        Analyze this user message to determine their intent when asking a question or making a statement and generate an appropriate title:

        User Message: "{user_message}"

        First, classify into ONE of these categories:

        1. "data_update" - User wants to update/record their health data (like file upload but in message format)
           Examples: 
           - "Update my weight to 71.2 kg"
           - "My blood pressure today is 120/80"
           - "Record my temperature as 98.6 F"
           - "Add my blood sugar reading: 110 mg/dL"
           - "My heart rate this morning was 65 bpm"
           - "Set my height to 5'8""
           - "I took my medication at 8 AM"
           - "My cholesterol test result is 180"
           - "I had one bowl of rice with brinjal gravy"
           - "I ate chicken curry with rice for lunch"
           - "I took my blood pressure medication"
           - "My lab test shows glucose level of 95"
           - "I bought aspirin from the pharmacy"
           - "My doctor prescribed amoxicillin"
        
        2. "medical_question" - User is asking questions about health, seeking medical consultation, or requesting data retrieval
           Examples:
           - "What do my recent liver function tests show?"
           - "How is my blood pressure trending?"
           - "I'm experiencing pain in my abdomen, what could be causing this?"
           - "What medications am I currently taking?"
           - "Can you analyze my recent lab results?"
           - "I have a headache, should I be concerned?"
           - "Compare my current weight with last month"
           - "Can you pull my health records from lab reports"
           - "Show me my recent lab results"
           - "What are my latest test results?"
           - "Get my medical history"
           - "Retrieve my lab reports"

        **Key distinction:**
        - data_update = Recording/updating specific health values or measurements
        - medical_question = Asking questions, seeking analysis, requesting information retrieval, or asking about existing data

        **Important:**
        - If the user is asking to see, get, pull, retrieve, or show any health data, classify as "medical_question"
        - If the user is providing specific measurements or values to record, classify as "data_update"
        - Any request to view, access, or retrieve existing health records should be classified as "medical_question"

        Then, generate a brief, descriptive title (3-6 words) based on the intent and content:

        For data_update: Use "Health Data Update"
        For medical_question: Generate a specific title based on what they're asking about or their health concern (e.g., "Blood Pressure Inquiry", "Lab Results Review", "Abdominal Pain Consultation", "Medication History", "Health Data Query")

        Respond in this exact format:
        INTENT: [category_name]
        TITLE: [brief_title]
        """
        
        try:
            from langchain_openai import ChatOpenAI
            from langchain.schema import HumanMessage, SystemMessage
            
            llm = ChatOpenAI(
                model=settings.CUSTOMER_AGENT_MODEL or settings.DEFAULT_AI_MODEL, 
                temperature=0.1  # Lower temperature for classification tasks
            )
            
            messages = [
                SystemMessage(content="You are an intent classifier and title generator for health-related messages. Distinguish between data recording requests and medical consultation/data retrieval requests."),
                HumanMessage(content=classification_prompt)
            ]
            
            # Log ChatGPT interaction
            messages_dict = [
                {"role": "system", "content": "You are an intent classifier and title generator for health-related messages. Distinguish between data recording requests and medical consultation/data retrieval requests."},
                {"role": "user", "content": classification_prompt}
            ]
            
            response = llm.invoke(messages)
            
            # Log the interaction
            log_chatgpt_interaction(
                agent_name="EnhancedCustomerAgent",
                operation="classify_question_intent",
                request_data=messages_dict,
                response_data=response,
                model_name=settings.CUSTOMER_AGENT_MODEL or settings.DEFAULT_AI_MODEL,
                additional_metadata={"user_message_length": len(user_message)}
            )
            
            if response and response.content:
                content = response.content.strip()
                
                # Parse the response to extract intent and title
                intent_match = None
                title_match = None
                
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('INTENT:'):
                        intent_match = line.replace('INTENT:', '').strip().lower()
                    elif line.startswith('TITLE:'):
                        title_match = line.replace('TITLE:', '').strip()
                
                if intent_match and intent_match in ["data_update", "medical_question"]:
                    return {
                        "intent": intent_match,
                        "title": title_match or "Health Consultation"
                    }
                
        except Exception as e:
            print(f"⚠️ [DEBUG] Question intent classification failed: {str(e)}, falling back to medical_question")
            
        # Fallback: assume medical question if classification fails
        return {
            "intent": "medical_question",
            "title": "Health Consultation"
        }

    async def _classify_data_update_agent(self, user_message: str) -> str:
        """Classify which agent should handle the data update based on the message content"""
        
        classification_prompt = f"""
        Analyze this user message to determine which specialized health agent should handle this data update:

        User Message: "{user_message}"

        Classify into ONE of these agent categories based on the type of health data being updated:

        1. "vitals" - Vital signs, measurements, and basic health metrics
           Examples:
           - "My blood pressure is 120/80"
           - "Update my weight to 71.2 kg"
           - "Record my temperature as 98.6 F"
           - "My heart rate is 65 bpm"
           - "Set my height to 5'8""
           - "My blood sugar is 110 mg/dL"
           - "My oxygen saturation is 98%"
           - "I took my blood pressure reading: 118/75"

        2. "nutrition" - Food intake, meals, dietary information, and nutritional data
           Examples:
           - "I had one bowl of rice with brinjal gravy"
           - "I ate chicken curry with rice for lunch"
           - "I had oatmeal with berries for breakfast"
           - "I drank a protein shake"
           - "I ate a salad with grilled chicken"
           - "I had pasta with tomato sauce"
           - "I consumed 2000 calories today"
           - "I ate an apple and a banana"

        3. "prescription" - Medication prescriptions, dosage information, and prescription data
           Examples:
           - "My doctor prescribed amoxicillin"
           - "I got a prescription for blood pressure medication"
           - "My doctor wrote me a prescription for insulin"
           - "I have a prescription for pain medication"
           - "My doctor prescribed antibiotics"
           - "I got a new prescription for diabetes medication"

        4. "pharmacy" - Pharmacy purchases, over-the-counter medications, and pharmacy transactions
           Examples:
           - "I bought aspirin from the pharmacy"
           - "I purchased vitamins from CVS"
           - "I got cough syrup from Walgreens"
           - "I bought allergy medication"
           - "I purchased pain relievers"
           - "I got cold medicine from the drugstore"

        5. "lab" - Laboratory test results, medical test data, and diagnostic information
           Examples:
           - "My lab test shows glucose level of 95"
           - "My blood test results show cholesterol at 180"
           - "My liver function test results are normal"
           - "My lab work shows hemoglobin of 14"
           - "My kidney function test results"
           - "My thyroid test results came back"

        **Classification Guidelines:**
        - Look for specific keywords and context clues
        - Focus on the primary type of data being recorded
        - If multiple types are mentioned, choose the most prominent one
        - For medication-related updates, distinguish between prescriptions (doctor-ordered) and pharmacy purchases (self-purchased)

        Respond with ONLY the agent name (vitals, nutrition, prescription, pharmacy, or lab):
        """
        
        try:
            from langchain_openai import ChatOpenAI
            from langchain.schema import HumanMessage, SystemMessage
            
            llm = ChatOpenAI(
                model=settings.CUSTOMER_AGENT_MODEL or settings.DEFAULT_AI_MODEL, 
                temperature=0.1  # Lower temperature for classification tasks
            )
            
            messages = [
                SystemMessage(content="You are an agent classifier for health data updates. Determine which specialized agent should handle the data update based on the content."),
                HumanMessage(content=classification_prompt)
            ]
            
            # Log ChatGPT interaction
            messages_dict = [
                {"role": "system", "content": "You are an agent classifier for health data updates. Determine which specialized agent should handle the data update based on the content."},
                {"role": "user", "content": classification_prompt}
            ]
            
            response = llm.invoke(messages)
            
            # Log the interaction
            log_chatgpt_interaction(
                agent_name="EnhancedCustomerAgent",
                operation="classify_data_update_agent",
                request_data=messages_dict,
                response_data=response,
                model_name=settings.CUSTOMER_AGENT_MODEL or settings.DEFAULT_AI_MODEL,
                additional_metadata={"user_message_length": len(user_message)}
            )
            
            if response and response.content:
                agent_name = response.content.strip().lower()
                
                # Validate the agent name
                valid_agents = ["vitals", "nutrition", "prescription", "pharmacy", "lab"]
                if agent_name in valid_agents:
                    return agent_name
                
        except Exception as e:
            print(f"⚠️ [DEBUG] Data update agent classification failed: {str(e)}")
            
        # Fallback: default to vitals agent if classification fails
        return "vitals"
    
    def determine_processing_path(self, state: CustomerAgentState) -> str:
        """Determine the processing path based on request analysis"""
        
        # CRITICAL DEBUG logging
        print(f"🚨🚨🚨 [CRITICAL] determine_processing_path called with:")
        print(f"🚨🚨🚨 [CRITICAL] request_type: {state.get('request_type')}")
        print(f"🚨🚨🚨 [CRITICAL] requires_file_processing: {state.get('requires_file_processing')}")
        print(f"🚨🚨🚨 [CRITICAL] requires_data_retrieval: {state.get('requires_data_retrieval')}")
        print(f"🚨🚨🚨 [CRITICAL] user_message: {state.get('user_message', '')[:100]}...")
        
        # Add debug logging
        print(f"🔀 [DEBUG] determine_processing_path - request_type: {state.get('request_type')}")
        print(f"🔀 [DEBUG] determine_processing_path - requires_file_processing: {state.get('requires_file_processing')}")
        print(f"🔀 [DEBUG] determine_processing_path - requires_data_retrieval: {state.get('requires_data_retrieval')}")
        
        if state.get("error_message"):
            print(f"🔀 [DEBUG] Routing to error due to: {state.get('error_message')}")
            return "error"
        
        # Special handling for file+question: check if question actually needs the file
        if state["request_type"] == "file_and_question":
            print(f"🚨🚨🚨 [CRITICAL] Routing to smart_file_question_router for file+question scenario!")
            print(f"🔀 [DEBUG] Routing to smart_file_question_router for file+question scenario")
            return "smart_file_question_router"
        
        elif state["requires_file_processing"] and state["requires_data_retrieval"]:
            print(f"🔀 [DEBUG] Routing to file_processing (file + data retrieval)")
            return "file_processing"  # Process file first, then coordinate agents
        elif state["requires_file_processing"]:
            print(f"🔀 [DEBUG] Routing to file_processing (file only)")
            return "file_processing"  # File only processing or data_update (treated as file processing)
        elif state["requires_data_retrieval"]:
            print(f"🔀 [DEBUG] Routing to medical_doctor (data retrieval only)")
            # For question-only workflows, route directly to medical doctor agent
            return "medical_doctor"  # Direct to medical doctor agent
        else:
            print(f"🔀 [DEBUG] No valid routing path found - defaulting to error")
            return "error"
    
    async def smart_file_question_router(self, state: CustomerAgentState) -> CustomerAgentState:
        """Smart router for file+question scenarios - determines if file processing is actually needed"""
        
        step_start = time.time()
        state["step_start_times"]["smart_file_question_router"] = step_start
        print(f"🤖 [DEBUG] Starting smart_file_question_router at {isoformat_now()}")
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "smart_file_question_router",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            try:
                user_question = state["user_message"]
                file_name = state["uploaded_file"]["original_name"] if state.get("uploaded_file") else "document"
                
                # Use AI to determine if the question is about the uploaded document
                intent_prompt = f"""
                Analyze this question to determine if it refers to an uploaded document or is a general medical question:
                
                Question: "{user_question}"
                Uploaded file: {file_name}
                
                Document-referencing indicators:
                - Uses words like "this", "the document", "this report", "these results", "what does this show"
                - Asks about specific values, numbers, or data that would be in a document
                - Asks for interpretation or explanation of document content
                - References "my lab results", "my test", "this prescription"
                
                General medical question indicators:
                - Describes symptoms (pain, headache, fever, etc.)
                - Asks about general medical advice
                - Doesn't reference the document content
                - Could be answered without seeing any document
                
                Examples:
                - "What does this lab report show?" → DOCUMENT_SPECIFIC
                - "What are my cholesterol levels?" → DOCUMENT_SPECIFIC  
                - "Explain these test results" → DOCUMENT_SPECIFIC
                - "Analyze this and let know your prognosis" → DOCUMENT_SPECIFIC
                - "I have a headache, what should I do?" → GENERAL_MEDICAL
                - "I'm feeling tired lately" → GENERAL_MEDICAL
                - "What medications should I take for pain?" → GENERAL_MEDICAL
                
                Respond with ONLY:
                - "DOCUMENT_SPECIFIC" if the question refers to the uploaded document
                - "GENERAL_MEDICAL" if it's a general medical question unrelated to the document
                """
                
                messages = [
                    SystemMessage(content="You are an AI that determines if a question refers to an uploaded document or is a general medical question."),
                    HumanMessage(content=intent_prompt)
                ]
                
                response = self.llm.invoke(messages)
                intent = response.content.strip().upper()
                
                print(f"🤖 [DEBUG] Smart router in intelligent_router classified intent: {intent}")
                
                if intent == "GENERAL_MEDICAL":
                    # General medical question - ignore the uploaded file and just answer the medical question
                    print(f"🩺 [DEBUG] General medical question detected - ignoring uploaded file, routing to medical consultation")
                    
                    # Clear the file processing result so it doesn't get used in medical consultation
                    state["file_processing_result"] = None
                    
                    classified_domain = "medical_consultation"
                    state["routing_decision"] = {
                        "domain": classified_domain,
                        "question": user_question,
                        "confidence": 0.95,  # High confidence for general medical questions
                        "reasoning": f"General medical question detected, ignoring uploaded file: '{user_question[:50]}...'"
                    }
                    
                    step_duration = time.time() - step_start
                    state["timing_data"]["intelligent_router"] = step_duration
                    print(f"🧠 [DEBUG] Classified as: {classified_domain} (general medical, ignoring file)")
                    print(f"✅ [DEBUG] intelligent_router completed in {step_duration:.2f}s")
                    return state
                
                # If document-specific, continue with normal document interpretation flow
                print(f"🧠 [DEBUG] Document-specific question detected, routing to medical_consultation with file data")
                classified_domain = "medical_consultation"
                state["routing_decision"] = {
                    "domain": classified_domain,
                    "question": user_question,
                    "confidence": 0.95,  # High confidence for document questions
                    "reasoning": f"Document-specific question detected: '{user_question[:50]}...'"
                }
                
                step_duration = time.time() - step_start
                state["timing_data"]["intelligent_router"] = step_duration
                print(f"🧠 [DEBUG] Classified as: {classified_domain} (document-specific)")
                print(f"✅ [DEBUG] intelligent_router completed in {step_duration:.2f}s")
                return state
                
            except Exception as e:
                step_duration = time.time() - step_start
                state["timing_data"]["smart_file_question_router"] = step_duration
                print(f"❌ [DEBUG] Smart router failed in {step_duration:.2f}s: {str(e)}")
                
                # Fallback: if classification fails, assume it's document-specific to be safe
                print(f"⚠️ [DEBUG] Smart router failed, defaulting to file processing")
                state["routing_decision"] = {
                    "requires_file": True,
                    "reasoning": f"Classification failed, defaulting to file processing: {str(e)}"
                }
                state["requires_file_processing"] = True
                return state
    
    def determine_smart_router_path(self, state: CustomerAgentState) -> str:
        """Determine the path after smart routing analysis"""
        
        routing_decision = state.get("routing_decision", {})
        requires_file = routing_decision.get("requires_file", True)
        
        if requires_file:
            print(f"🔀 [DEBUG] Smart router directing to file processing")
            return "file_processing"
        else:
            print(f"🔀 [DEBUG] Smart router directing to medical consultation (skipping file)")
            return "medical_consultation"
    
    async def process_file(self, state: CustomerAgentState) -> CustomerAgentState:
        """Process uploaded file using document orchestrator OR extract data from user message for data_update"""
        
        step_start = time.time()
        state["step_start_times"]["process_file"] = step_start
        print(f"📄 [DEBUG] Starting process_file at {isoformat_now()}")
        
        # Handle data_update scenario (no file, just message with structured data)
        if state["request_type"] == "data_update":
            print(f"📝 [DEBUG] Processing data update from message: {state['user_message'][:100]}...")
            
            with trace_agent_operation(
                "EnhancedCustomerAgent",
                "process_data_update",
                user_id=state["user_id"],
                session_id=state["session_id"],
                request_id=state["request_id"]
            ):
                try:
                    # Classify which agent should handle this data update
                    agent_type = await self._classify_data_update_agent(state["user_message"])
                    print(f"🤖 [DEBUG] Classified data update for agent: {agent_type}")
                    
                    # Get the appropriate agent
                    if agent_type not in self.data_agents:
                        raise Exception(f"Unsupported agent type: {agent_type}")
                    
                    selected_agent = self.data_agents[agent_type]
                    
                    # Prepare state for the selected agent
                    agent_state = {
                        "ocr_text": state["user_message"],
                        "user_id": state["user_id"],
                        "session_id": state["session_id"],
                        "request_id": state["request_id"]
                    }
                    
                    # Extract data from the message using the selected agent
                    extract_result = await selected_agent.extract_data(agent_state)
                    
                    if extract_result.get("extracted_data") and not extract_result.get("error_message"):
                        # Merge the extracted data into the agent_state for storage
                        agent_state["extracted_data"] = extract_result.get("extracted_data")
                        
                        # Store the extracted data using the selected agent
                        store_result = await selected_agent.store_data(agent_state)
                        
                        if not store_result.get("error_message"):
                            processing_duration = time.time() - step_start
                            print(f"📝 [DEBUG] Data update processing completed in {processing_duration:.2f}s")
                            
                            # Create a processing result similar to document processing
                            state["file_processing_result"] = {
                                "processing_status": "success",
                                "success": True,
                                "processing_complete": True,
                                "document_type": agent_type,
                                "extracted_data": extract_result.get("extracted_data"),
                                "stored_records": store_result.get("stored_records", []),
                                "storage_summary": {
                                    "success": True,
                                    "records_stored": len(store_result.get("stored_records", [])),
                                    "table": f"{agent_type}_data"
                                },
                                "processing_details": {
                                    "storage_success": True,
                                    "extraction_success": True,
                                    "agent_used": agent_type
                                }
                            }
                            
                            log_agent_interaction(
                                "EnhancedCustomerAgent",
                                f"{agent_type.capitalize()}Agent",
                                "data_update_processed",
                                {
                                    "success": True,
                                    "message": state["user_message"],
                                    "processing_status": "success",
                                    "records_extracted": len(store_result.get("stored_records", [])),
                                    "agent_type": agent_type
                                },
                                user_id=state["user_id"],
                                session_id=state["session_id"],
                                request_id=state["request_id"]
                            )
                            
                            state["timing_data"]["process_file"] = processing_duration
                            print(f"✅ [DEBUG] Data update completed in {processing_duration:.2f}s total using {agent_type} agent")
                            
                            return state
                        else:
                            raise Exception(f"Storage failed: {store_result.get('error_message')}")
                    else:
                        raise Exception(f"Data extraction failed: {extract_result.get('error_message', 'No data extracted')}")
                    
                except Exception as e:
                    step_duration = time.time() - step_start
                    state["timing_data"]["process_file"] = step_duration
                    print(f"❌ [DEBUG] Data update failed in {step_duration:.2f}s: {str(e)}")
                    state["error_message"] = f"Data update processing failed: {str(e)}"
                    return state
        
        # Original file processing logic for actual file uploads
        print(f"📄 [DEBUG] File path: {state['uploaded_file']['file_path']}")
        print(f"📄 [DEBUG] File type: {state['uploaded_file']['file_type']}")
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "process_file",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            try:
                uploaded_file = state["uploaded_file"]
                # Always pass user_question for file+question scenarios to prevent storage
                user_question = state["user_message"] if state["request_type"] == "file_and_question" else None
                print(f"🚨 [DEBUG] process_file - request_type: {state['request_type']}, user_question: {'SET' if user_question else 'NONE'}")
                
                # First, validate if the document is of a supported type
                print(f"📄 [DEBUG] Validating document type...")
                
                # Check file type - only use GPT-4V for image files, not PDFs
                file_extension = uploaded_file["file_path"].lower().split('.')[-1]
                image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
                
                if file_extension in image_extensions:
                    # Enhanced image classification with GPT-4V for image files
                    print(f"🔍 [DEBUG] Starting enhanced image classification for: {uploaded_file['file_path']}")
                    classification_result = await self._classify_image_with_gpt4v(uploaded_file["file_path"])
                else:
                    # For PDFs and other document types, skip vision classification
                    print(f"📄 [DEBUG] PDF/Document file detected, skipping image classification")
                    classification_result = {
                        "success": True,
                        "image_type": "document",
                        "description": "Document file - using text-based validation",
                        "details": {},
                        "confidence": 1.0
                    }
                
                if not classification_result.get("success"):
                    state["error_message"] = f"Image classification failed: {classification_result.get('error', 'Unknown error')}"
                    return state
                
                image_type = classification_result.get("image_type", "unknown")
                print(f"🔍 [DEBUG] Image classified as: {image_type}")
                
                # Route based on image type
                if image_type == "food":
                    print(f"🍽️ [DEBUG] Processing food image with nutrition agent")
                    nutrition_result = await self._process_nutrition_image(
                        uploaded_file["file_path"], 
                        state["user_id"], 
                        state.get("session_id")
                    )
                    # Convert to validation result format
                    if nutrition_result.get("success"):
                        validation_result = {
                            "is_valid": True,
                            "document_type": nutrition_result.get("document_type", "food_image"),
                            "suggestions": "",
                            "cached_ocr_data": None,
                            "food_processing_result": nutrition_result  # Store the original result
                        }
                        # For successful food processing, set file_processing_result directly
                        state["file_processing_result"] = {
                            "processing_status": "success",
                            "document_type": "food_image",
                            "extracted_data": nutrition_result.get("extracted_data", {}),
                            "message": nutrition_result.get("message", "Successfully processed food image")
                        }
                    else:
                        # For food processing failures, provide specific nutrition error
                        error_msg = nutrition_result.get("error", "Nutrition analysis failed")
                        state["error_message"] = f"nutrition_processing_failed:{error_msg}"
                        step_duration = time.time() - step_start
                        state["timing_data"]["process_file"] = step_duration
                        print(f"❌ [DEBUG] Nutrition processing failed in {step_duration:.2f}s: {error_msg}")
                        return state
                        
                elif image_type == "medical":
                    print(f"🏥 [DEBUG] Processing medical image")
                    medical_result = await self._process_medical_image(
                        uploaded_file["file_path"], 
                        classification_result, 
                        state["user_id"], 
                        state.get("session_id")
                    )
                    # Convert to validation result format
                    if medical_result.get("success"):
                        validation_result = {
                            "is_valid": True,
                            "document_type": medical_result.get("document_type", "medical_image"),
                            "suggestions": "",
                            "cached_ocr_data": None,
                            "medical_processing_result": medical_result  # Store the original result
                        }
                        # For successful medical processing, set file_processing_result directly
                        state["file_processing_result"] = {
                            "processing_status": "success",
                            "document_type": "medical_image",
                            "extracted_data": medical_result.get("extracted_data", {}),
                            "message": medical_result.get("message", "Successfully processed medical image")
                        }
                    else:
                        # For medical processing failures, provide specific medical error
                        error_msg = medical_result.get("error", "Medical image analysis failed")
                        state["error_message"] = f"medical_processing_failed:{error_msg}"
                        step_duration = time.time() - step_start
                        state["timing_data"]["process_file"] = step_duration
                        print(f"❌ [DEBUG] Medical processing failed in {step_duration:.2f}s: {error_msg}")
                        return state
                        
                elif image_type == "document":
                    print(f"📄 [DEBUG] Processing document image with existing validation")
                    validation_result = await self._validate_document_type(uploaded_file["file_path"])
                else:
                    print(f"❓ [DEBUG] Unknown image type: {image_type}, using standard validation")
                    validation_result = await self._validate_document_type(uploaded_file["file_path"])
                
                # Only proceed with document processing if this is a traditional document
                if image_type in ["food", "medical"] and state.get("file_processing_result"):
                    # Food/medical processing already completed successfully
                    step_duration = time.time() - step_start
                    state["timing_data"]["process_file"] = step_duration
                    print(f"✅ [DEBUG] {image_type} processing completed in {step_duration:.2f}s")
                    return state
                
                if not validation_result["is_valid"]:
                    # Document is not supported - set error and return
                    state["error_message"] = f"unsupported_document_type:{validation_result['document_type']}:{validation_result['suggestions']}"
                    
                    log_agent_interaction(
                        "EnhancedCustomerAgent",
                        "DocumentValidator",
                        "document_rejected",
                        {
                            "file_path": uploaded_file["file_path"],
                            "file_type": uploaded_file["file_type"],
                            "detected_type": validation_result["document_type"],
                            "suggestions": validation_result["suggestions"]
                        },
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        request_id=state["request_id"]
                    )
                    
                    step_duration = time.time() - step_start
                    state["timing_data"]["process_file"] = step_duration
                    print(f"❌ [DEBUG] Document validation failed in {step_duration:.2f}s")
                    return state
                
                print(f"📄 [DEBUG] Document validation passed - detected type: {validation_result['document_type']}")
                
                # Cache OCR data from validation to avoid duplicate OCR calls
                cached_ocr_data = validation_result.get("cached_ocr_data")
                if cached_ocr_data:
                    print(f"📄 [DEBUG] Using cached OCR data from validation (length: {len(cached_ocr_data.get('text', ''))} chars)")
                
                print(f"📄 [DEBUG] About to call process_document_with_workflow...")
                processing_start = time.time()
                
                # Process document using orchestrator with cached OCR data
                processing_result = await process_document_with_workflow(
                    file_path=uploaded_file["file_path"],
                    file_type=uploaded_file["file_type"],
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    user_question=user_question,
                    cached_ocr_data=cached_ocr_data  # Pass cached OCR data to avoid duplicate calls
                )
                
                processing_duration = time.time() - processing_start
                print(f"📄 [DEBUG] process_document_with_workflow completed in {processing_duration:.2f}s")
                
                state["file_processing_result"] = processing_result
                
                log_agent_interaction(
                    "EnhancedCustomerAgent",
                    "DocumentProcessingOrchestrator",
                    "file_processed",
                    {
                        "success": processing_result.get("processing_status") == "success",
                        "document_type": processing_result.get("document_type"),
                        "file_path": uploaded_file["file_path"],
                        "file_type": uploaded_file["file_type"],
                        "processing_status": processing_result.get("processing_status"),
                        "error_message": processing_result.get("error_message") if processing_result.get("processing_status") != "success" else None,
                        "records_extracted": processing_result.get("storage_summary", {}).get("records_stored", 0)
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                step_duration = time.time() - step_start
                state["timing_data"]["process_file"] = step_duration
                state["timing_data"]["document_workflow"] = processing_duration
                print(f"✅ [DEBUG] process_file completed in {step_duration:.2f}s total")
                
                return state
                
            except Exception as e:
                step_duration = time.time() - step_start
                state["timing_data"]["process_file"] = step_duration
                print(f"❌ [DEBUG] process_file failed in {step_duration:.2f}s: {str(e)}")
                state["error_message"] = f"File processing failed: {str(e)}"
                return state
    
    def after_file_processing(self, state: CustomerAgentState) -> str:
        """Determine next step after file processing"""
        
        if state.get("error_message"):
            return "error"
        
        # For file_only uploads and data_update, go directly to response (no agent coordination needed)
        if state["request_type"] in ["file_only", "data_update"]:
            return "respond"
        
        # Check if smart router determined we should use medical consultation for enhanced analysis
        routing_decision = state.get("routing_decision", {})
        should_use_medical_consultation = routing_decision.get("domain") == "medical_consultation"
        
        # If we have a question and file processing included question answering, we can respond
        # UNLESS the smart router determined we should use medical consultation for enhanced analysis
        if (state["request_type"] == "file_and_question" and 
            state["file_processing_result"] and 
            "question_answer" in state["file_processing_result"] and
            not should_use_medical_consultation):
            print(f"💬 [DEBUG] Basic document analysis complete, routing to response (no enhanced medical analysis needed)")
            return "respond"
        
        # If smart router determined medical consultation is needed, route to coordination even if we have basic analysis
        if should_use_medical_consultation:
            print(f"🩺 [DEBUG] Smart router determined medical consultation needed - routing to coordinate_agents for enhanced analysis")
            return "coordinate_agents"
        
        # For file_and_question requests, we need to answer the question regardless of data retrieval needs
        if state["request_type"] == "file_and_question":
            # Route to intelligent router to handle the medical question about the uploaded document
            return "coordinate_agents"
        
        # If we need to retrieve additional data for questions, use intelligent routing
        if state["requires_data_retrieval"]:
            return "coordinate_agents"
        
        return "respond"
    
    async def intelligent_router(self, state: CustomerAgentState) -> CustomerAgentState:
        """Intelligent router that classifies intent and determines which agent(s) to engage"""
        
        step_start = time.time()
        state["step_start_times"]["intelligent_router"] = step_start
        print(f"🧠 [DEBUG] Starting intelligent_router at {isoformat_now()}")
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "intelligent_router",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            try:
                user_question = state["user_message"]
                print(f"🧠 [DEBUG] Routing question: {user_question[:100]}...")
                
                # Check if this is a file_and_question scenario with document-specific questions
                has_file = bool(state.get("uploaded_file"))
                file_processing_result = state.get("file_processing_result", {})
                
                # If we have a file and the question is about the uploaded document content, 
                # route to medical consultation for interpretation
                if has_file and file_processing_result:
                    # Use AI to determine if the question is about the uploaded document or general medical
                    intent_prompt = f"""
                    Analyze this question to determine if it refers to an uploaded document or is a general medical question:
                    
                    Question: "{user_question}"
                    
                    Document-referencing indicators:
                    - Uses words like "this", "the document", "this report", "these results", "what does this show"
                    - Asks about specific values, numbers, or data that would be in a document
                    - Asks for interpretation or explanation of document content
                    - References "my lab results", "my test", "this prescription"
                    
                    General medical question indicators:
                    - Describes symptoms (pain, headache, fever, etc.)
                    - Asks about general medical advice
                    - Doesn't reference the document content
                    - Could be answered without seeing any document
                    
                    Examples:
                    - "What does this lab report show?" → DOCUMENT_SPECIFIC
                    - "What are my cholesterol levels?" → DOCUMENT_SPECIFIC  
                    - "Explain these test results" → DOCUMENT_SPECIFIC
                    - "Analyze this and let know your prognosis" → DOCUMENT_SPECIFIC
                    - "I have a headache, what should I do?" → GENERAL_MEDICAL
                    - "I'm feeling tired lately" → GENERAL_MEDICAL
                    - "What medications should I take for pain?" → GENERAL_MEDICAL
                    
                    Respond with ONLY:
                    - "DOCUMENT_SPECIFIC" if the question refers to the uploaded document
                    - "GENERAL_MEDICAL" if it's a general medical question unrelated to the document
                    """
                    
                    messages = [
                        SystemMessage(content="You are an AI that determines if a question refers to an uploaded document or is a general medical question."),
                        HumanMessage(content=intent_prompt)
                    ]
                    
                    response = self.llm.invoke(messages)
                    intent = response.content.strip().upper()
                    
                    print(f"🤖 [DEBUG] Smart router in intelligent_router classified intent: {intent}")
                    
                    if intent == "GENERAL_MEDICAL":
                        # General medical question - ignore the uploaded file and just answer the medical question
                        print(f"🩺 [DEBUG] General medical question detected - ignoring uploaded file, routing to medical consultation")
                        
                        # Clear the file processing result so it doesn't get used in medical consultation
                        state["file_processing_result"] = None
                        
                        classified_domain = "medical_consultation"
                        state["routing_decision"] = {
                            "domain": classified_domain,
                            "question": user_question,
                            "confidence": 0.95,  # High confidence for general medical questions
                            "reasoning": f"General medical question detected, ignoring uploaded file: '{user_question[:50]}...'"
                        }
                        
                        step_duration = time.time() - step_start
                        state["timing_data"]["intelligent_router"] = step_duration
                        print(f"🧠 [DEBUG] Classified as: {classified_domain} (general medical, ignoring file)")
                        print(f"✅ [DEBUG] intelligent_router completed in {step_duration:.2f}s")
                        return state
                    
                    # If document-specific, continue with normal document interpretation flow
                    print(f"🧠 [DEBUG] Document-specific question detected, routing to medical_consultation with file data")
                    classified_domain = "medical_consultation"
                    state["routing_decision"] = {
                        "domain": classified_domain,
                        "question": user_question,
                        "confidence": 0.95,  # High confidence for document questions
                        "reasoning": f"Document-specific question detected: '{user_question[:50]}...'"
                    }
                    
                    step_duration = time.time() - step_start
                    state["timing_data"]["intelligent_router"] = step_duration
                    print(f"🧠 [DEBUG] Classified as: {classified_domain} (document-specific)")
                    print(f"✅ [DEBUG] intelligent_router completed in {step_duration:.2f}s")
                    return state
                
                # Single LLM call to classify intent and route for non-document-specific questions
                intent_prompt = f"""
                Analyze this health-related question and determine which health data domain it belongs to:
                
                Question: "{user_question}"
                
                Available domains:
                - lab_data: Lab reports, blood tests, diagnostic results, test values, lab trends
                - vitals: Vital signs, blood pressure, heart rate, weight, temperature measurements
                - pharmacy: Medication costs, pharmacy bills, drug purchases, prescription costs
                - prescription: Medical prescriptions, medication orders from doctors. one of way to identify is if it has a doctor's name and a patient's name and if it handwritten or if it mentions OUT-PATIENT RECORD
                - medical_consultation: Health symptoms, medical concerns, pain, illness, medical advice requests
                - multi_domain: Questions that span multiple domains or require data from multiple sources
                
                Examples:
                - "Show me my lab reports" → lab_data
                - "What's my latest blood pressure?" → vitals
                - "How much did I spend on medications?" → pharmacy
                - "What medications am I prescribed?" → prescription
                - "I'm experiencing pain in my liver" → medical_consultation
                - "I have chest pain, what could it be?" → medical_consultation
                - "My stomach hurts after eating" → medical_consultation
                - "Compare my blood pressure with my lab results" → multi_domain
                
                **Important:** Choose "medical_consultation" for any question about:
                - Physical symptoms (pain, discomfort, illness)
                - Medical concerns or worries
                - Requests for medical advice or interpretation
                - Questions about what health data might indicate medically
                
                Respond with ONLY the domain name (lab_data, vitals, pharmacy, prescription, nutrition, medical_consultation, or multi_domain).
                If unclear, respond with "medical_consultation" for symptom-related questions or "multi_domain" for data questions.
                """
                
                messages = [
                    SystemMessage(content="You are a health query classifier that routes questions to the appropriate health data domain."),
                    HumanMessage(content=intent_prompt)
                ]
                
                response = self.llm.invoke(messages)
                classified_domain = response.content.strip().lower()
                
                # Validate classification
                valid_domains = ["lab_data", "vitals", "pharmacy", "prescription", "nutrition", "medical_consultation", "multi_domain"]
                if classified_domain not in valid_domains:
                    print(f"⚠️ [DEBUG] Invalid classification '{classified_domain}', defaulting to multi_domain")
                    classified_domain = "multi_domain"
                
                state["routing_decision"] = {
                    "domain": classified_domain,
                    "question": user_question,
                    "confidence": 0.9,  # High confidence for single-domain routing
                    "reasoning": f"Question classified as {classified_domain}"
                }
                
                step_duration = time.time() - step_start
                state["timing_data"]["intelligent_router"] = step_duration
                
                print(f"🧠 [DEBUG] Classified as: {classified_domain}")
                print(f"✅ [DEBUG] intelligent_router completed in {step_duration:.2f}s")
                
                log_agent_interaction(
                    "EnhancedCustomerAgent",
                    "IntelligentRouter",
                    "intent_classified",
                    {
                        "question": user_question[:200] + "..." if len(user_question) > 200 else user_question,
                        "classified_domain": classified_domain,
                        "routing_time": step_duration
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                return state
                
            except Exception as e:
                step_duration = time.time() - step_start
                state["timing_data"]["intelligent_router"] = step_duration
                print(f"❌ [DEBUG] intelligent_router failed in {step_duration:.2f}s: {str(e)}")
                # Fallback to multi_domain for assessment-based routing
                state["routing_decision"] = {
                    "domain": "multi_domain",
                    "question": state["user_message"],
                    "confidence": 0.0,
                    "reasoning": f"Classification failed: {str(e)}"
                }
                return state
    
    def route_to_specific_agent(self, state: CustomerAgentState) -> str:
        """Route to specific agent based on intent classification"""
        
        routing_decision = state.get("routing_decision", {})
        domain = routing_decision.get("domain", "multi_domain")
        
        print(f"🎯 [DEBUG] Routing to domain: {domain}")
        
        # Route based on classified domain - must match workflow edge keys exactly
        routing_map = {
            "lab_data": "lab_data",  # Routes to execute_lab_agent
            "vitals": "vitals",      # Routes to execute_vitals_agent
            "pharmacy": "pharmacy",  # Routes to execute_pharmacy_agent
            "prescription": "prescription",  # Routes to execute_prescription_agent
            "nutrition": "nutrition",      # Routes to execute_nutrition_agent
            "medical_consultation": "medical_consultation",  # Routes to execute_medical_consultation
            "multi_domain": "multi_domain",  # Routes to execute_multi_agent
            "unclear": "multi_domain"
        }
        
        result = routing_map.get(domain, "multi_domain")
        print(f"🎯 [DEBUG] Final routing decision: {result}")
        return result
    
    async def retrieve_data(self, state: CustomerAgentState) -> CustomerAgentState:
        """Retrieve relevant health data by delegating to specialized agents"""
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "retrieve_data",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            try:
                user_question = state["user_message"]
                
                # Ask each specialized agent to assess question relevance
                agent_assessments = {}
                
                for agent_name, agent in self.data_agents.items():
                    assessment = await agent.assess_question_relevance(
                        user_question,
                        state["user_id"],
                        state["session_id"]
                    )
                    agent_assessments[agent_name] = assessment
                
                # Retrieve data from relevant agents based on their assessments
                retrieved_data = {}
                agent_errors = {}
                
                for agent_name, assessment in agent_assessments.items():
                    if assessment.get("is_relevant", False):
                        retrieval_strategy = assessment.get("retrieval_strategy", {})
                        
                        if retrieval_strategy.get("days_back", 0) > 0:
                            agent = self.data_agents[agent_name]
                            
                            try:
                                # Use the agent's own retrieval strategy
                                result = await agent.process_request(
                                    "retrieve",
                                    {"retrieval_request": retrieval_strategy},
                                    state["user_id"],
                                    state["session_id"]
                                )
                                
                                if result.get("success"):
                                    retrieved_data[agent_name] = {
                                        "data": result.get("data", {}),
                                        "relevance_score": assessment.get("relevance_score", 0.0),
                                        "reasoning": assessment.get("reasoning", ""),
                                        "priority_data": retrieval_strategy.get("priority_data", [])
                                    }
                                else:
                                    agent_errors[agent_name] = {
                                        "error": result.get("error_message", "Unknown error"),
                                        "relevance_score": assessment.get("relevance_score", 0.0)
                                    }
                            except Exception as e:
                                agent_errors[agent_name] = {
                                    "error": f"Agent execution failed: {str(e)}",
                                    "relevance_score": assessment.get("relevance_score", 0.0)
                                }
                
                state["retrieved_data"] = retrieved_data
                
                log_agent_interaction(
                    "EnhancedCustomerAgent",
                    "SpecializedAgents",  
                    "intelligent_data_retrieval",
                    {
                        "question": user_question[:100] + "..." if len(user_question) > 100 else user_question,
                        "assessments": {k: {"relevant": v.get("is_relevant"), "score": v.get("relevance_score")} 
                                       for k, v in agent_assessments.items()},
                        "successful_retrievals": list(retrieved_data.keys()),
                        "failed_agents": agent_errors if agent_errors else None,
                        "total_relevant_agents": len([a for a in agent_assessments.values() if a.get("is_relevant", False)]),
                        "total_successful_agents": len(retrieved_data)
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Intelligent data retrieval failed: {str(e)}"
                return state
    
    async def generate_response(self, state: CustomerAgentState) -> CustomerAgentState:
        """Generate comprehensive response based on all available data"""
        
        step_start = time.time()
        print(f"💬 [DEBUG] Starting generate_response at {isoformat_now()}")
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "generate_response",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            try:
                response_parts = []
                
                print(f"💬 [DEBUG] State keys: {list(state.keys())}")
                print(f"💬 [DEBUG] file_processing_result: {state.get('file_processing_result')}")
                print(f"💬 [DEBUG] request_type: {state.get('request_type')}")
                print(f"💬 [DEBUG] user_message: {state.get('user_message', '')[:50]}...")
                
                # If we processed a file, include that information
                if state.get("file_processing_result"):
                    file_result = state["file_processing_result"]
                    print(f"💬 [DEBUG] file_result type: {type(file_result)}")
                    print(f"💬 [DEBUG] file_result keys: {list(file_result.keys()) if isinstance(file_result, dict) else 'Not a dict'}")
                    
                    processing_status = file_result.get("processing_status", "unknown")
                    print(f"💬 [DEBUG] processing_status: {processing_status}")
                    
                    # Check for multiple possible success indicators
                    is_successful = False
                    
                    # Special handling for nutrition and medical images
                    if file_result.get("document_type") in ["food_image", "medical_image"]:
                        # For nutrition/medical images, success is simpler
                        is_successful = (
                            processing_status == "success" and
                            file_result.get("message")  # Has a success message
                        )
                        print(f"💬 [DEBUG] Special handling for {file_result.get('document_type')}: is_successful = {is_successful}")
                    else:
                        # Traditional document processing success criteria
                        is_successful = (
                            processing_status == "success" and
                            file_result.get("success") != False and
                            file_result.get("processing_complete") == True and
                            # Check storage was actually successful
                            file_result.get("storage_summary", {}).get("success") != False and
                            file_result.get("processing_details", {}).get("storage_success") != False
                        )
                    
                    print(f"💬 [DEBUG] is_successful: {is_successful}")
                    
                    if is_successful:
                        doc_type = file_result.get("document_type", "document")
                        
                        # Check for processing status message (duplicates, validation issues, etc.)
                        processing_msg = file_result.get("processing_status_message")
                        storage_summary = file_result.get("storage_summary", {})
                        scenario = storage_summary.get("scenario", "unknown")
                            
                        if scenario == "analysis_only":
                            # File+question scenario - data extracted for analysis only
                            response_parts.append(
                                f"📄 I've analyzed your {doc_type} document and extracted the data for answering your question. The data was not stored to your health records since you asked a specific question about this document."
                            )
                            
                            # Include the medical analysis from the document processing workflow
                            question_answer = file_result.get("question_answer")
                            if question_answer:
                                response_parts.append(f"\n🩺 **Medical Analysis:**\n{question_answer}")
                            else:
                                print(f"💬 [DEBUG] No question_answer found in file_result for analysis_only scenario")
                        elif processing_msg or (storage_summary.get("duplicates_skipped", 0) > 0 and storage_summary.get("new_records", 0) == 0):
                            # Handle special processing scenarios
                            if scenario == "duplicate_detection":
                                # All tests were duplicates
                                duplicates_count = storage_summary.get("duplicates_skipped", 0)
                                response_parts.append(
                                    f"🔄 I've already processed this {doc_type} before. All {duplicates_count} lab tests from this report are already stored in your health records. No duplicate data was added."
                                )
                            else:
                                # Other processing scenarios - use the generic message
                                response_parts.append(
                                    f"ℹ️ {processing_msg or storage_summary.get('message', 'Processing completed with special handling.')}"
                                )
                        else:
                            # Normal processing - new data was stored
                            records_stored = 0
                            if "storage_summary" in file_result and isinstance(file_result["storage_summary"], dict):
                                records_stored = file_result["storage_summary"].get("records_stored", 0)
                            elif "extracted_data" in file_result and isinstance(file_result["extracted_data"], dict):
                                # Count from extracted data if available
                                extracted_data = file_result["extracted_data"]
                                if "tests" in extracted_data and isinstance(extracted_data["tests"], list):
                                    records_stored = len(extracted_data["tests"])
                            elif "data" in file_result and isinstance(file_result["data"], dict):
                                # Check if data has test results
                                data = file_result["data"]
                                if "tests" in data and isinstance(data["tests"], list):
                                    records_stored = len(data["tests"])
                            
                            print(f"💬 [DEBUG] Calculated records_stored: {records_stored}")
                            
                            if records_stored > 0:
                                # Use appropriate record type based on document type
                                record_type = "lab test records" if doc_type == "lab report" else f"{doc_type} records"
                                if doc_type == "vitals":
                                    record_type = "vital signs records"
                                elif doc_type == "pharmacy":
                                    record_type = "medication records"
                                elif doc_type == "prescription":
                                    record_type = "prescription records"
                                    
                                response_parts.append(
                                    f"✅ Successfully processed your {doc_type} document and stored {records_stored} {record_type} in your health profile."
                                )
                            else:
                                # Special messages for nutrition and medical images
                                if doc_type == "food_image":
                                    response_parts.append(
                                        f"🍽️ Successfully analyzed your food image! I've extracted nutritional information and stored it in your nutrition log. You can now track your meals and nutritional intake."
                                    )
                                elif doc_type == "medical_image":
                                    response_parts.append(
                                        f"🏥 Successfully processed your medical image! I've analyzed the image content and stored it with an AI-generated summary in your medical records."
                                )
                                else:
                                    response_parts.append(
                                        f"✅ Successfully processed your {doc_type} document. The data has been analyzed and stored in your health profile."
                                    )
                    else:
                        error_msg = file_result.get("error_message")
                        print(f"💬 [DEBUG] Processing failed with error: {error_msg}")
                        
                        if error_msg:
                            response_parts.append(f"❌ Had trouble processing your document: {error_msg}")
                        else:
                            # No specific error message, but processing didn't clearly succeed
                            response_parts.append(
                                    f"⚠️ I processed your document but couldn't determine the final status. Please check your health profile to see if the data was stored successfully."
                            )
                else:
                    print(f"💬 [DEBUG] No file_processing_result found")
                
                # If we have a question and retrieved data, generate comprehensive answer
                if state.get("user_message") and state.get("retrieved_data"):
                    # Check if this is a direct medical doctor response
                    if "medical_doctor" in state.get("retrieved_data", {}) and state.get("coordination_mode") == "medical_doctor_direct":
                        print(f"💬 [DEBUG] Using direct medical doctor response")
                        doctor_data = state["retrieved_data"]["medical_doctor"]["data"]
                        medical_response = doctor_data.get("medical_response", "")
                        
                        if medical_response:
                            response_parts.append(f"\n🩺 **Medical Consultation:**\n{medical_response}")
                        else:
                            # Fallback if medical response failed
                            print(f"💬 [DEBUG] Medical doctor response empty, using default")
                            response_parts.append("I'd be happy to help with your health-related question, but I'm having trouble generating a comprehensive medical response right now. Please consult with your healthcare provider for medical guidance.")
                    # Check if this is a medical consultation response
                    elif "medical_consultation" in state.get("retrieved_data", {}):
                        print(f"💬 [DEBUG] Using medical consultation response")
                        consultation_data = state["retrieved_data"]["medical_consultation"]["data"]
                        consultation_response = consultation_data.get("consultation_response", "")
                        
                        if consultation_response:
                            response_parts.append(f"\n🩺 **Medical Consultation:**\n{consultation_response}")
                        else:
                            # Fallback to comprehensive answer if consultation failed
                            print(f"💬 [DEBUG] Medical consultation response empty, using comprehensive answer")
                            answer = await self._generate_comprehensive_answer(
                                state["user_message"],
                                state["retrieved_data"],
                                state.get("file_processing_result")
                            )
                            response_parts.append(f"\n📊 **Based on your health data:**\n{answer}")
                    else:
                        print(f"💬 [DEBUG] Generating comprehensive answer for question")
                        answer = await self._generate_comprehensive_answer(
                            state["user_message"],
                            state["retrieved_data"],
                            state.get("file_processing_result")
                        )
                        
                        if not any("Answer to your question" in part for part in response_parts):
                            response_parts.append(f"\n📊 **Based on your health data:**\n{answer}")
                
                # If no other content, provide a default response
                if not response_parts:
                    print(f"💬 [DEBUG] No response parts found, using default response")
                    if state.get("user_message"):
                        response_parts.append("I'd be happy to help with your health-related question, but I don't have enough recent data to provide a comprehensive answer. Try uploading a recent medical document or asking about specific health metrics.")
                    else:
                        response_parts.append("Hello! I'm your health assistant. Upload a medical document or ask me about your health data, and I'll help you understand and track your health information.")
                
                final_response = "\n".join(response_parts)
                
                # Step 2: Validate output with guardrails
                try:
                    output_validation = await validate_agent_response(
                        response_content=final_response,
                        agent_name="enhanced_customer_agent",
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        is_medical_response=False  # This is general customer service, not medical advice
                    )
                    
                    # Use filtered content and log any violations
                    if output_validation.violations:
                        log_agent_interaction(
                            "EnhancedCustomerAgent",
                            "GuardrailsValidation",
                            "output_filtered",
                            {
                                "violations": output_validation.violations,
                                "confidence_score": output_validation.confidence_score,
                                "original_length": len(final_response),
                                "filtered_length": len(output_validation.filtered_content),
                                "is_safe": output_validation.is_safe
                            },
                            user_id=state["user_id"],
                            session_id=state["session_id"]
                        )
                    
                    # Use the filtered content
                    final_response = output_validation.filtered_content
                    
                    # If response is not safe, replace with safe fallback
                    if not output_validation.is_safe:
                        final_response = "I apologize, but I cannot provide that response as it may not meet our safety guidelines. Please rephrase your question, and I'll be happy to help you with your healthcare needs in a safe and appropriate manner."
                        
                        log_agent_interaction(
                            "EnhancedCustomerAgent",
                            "GuardrailsViolation",
                            "output_blocked",
                            {
                                "violations": output_validation.violations,
                                "confidence_score": output_validation.confidence_score
                            },
                            user_id=state["user_id"],
                            session_id=state["session_id"]
                        )
                
                except Exception as e:
                    # If guardrails fail, log error but continue with original response
                    log_agent_interaction(
                        "EnhancedCustomerAgent",
                        "GuardrailsError",
                        "output_validation_failed",
                        {"error": str(e)},
                        user_id=state["user_id"],
                        session_id=state["session_id"]
                    )
                
                state["response_message"] = final_response
                state["processing_complete"] = True
                
                step_duration = time.time() - step_start
                state["timing_data"]["generate_response"] = step_duration
                print(f"💬 [DEBUG] generate_response completed in {step_duration:.2f}s")
                print(f"💬 [DEBUG] Final response: {final_response[:100]}...")
                
                return state
                
            except Exception as e:
                step_duration = time.time() - step_start
                state["timing_data"]["generate_response"] = step_duration
                error_msg = f"Response generation failed: {str(e)}"
                print(f"💬 [DEBUG] generate_response failed in {step_duration:.2f}s: {error_msg}")
                state["error_message"] = error_msg
                return state
    
    async def _generate_comprehensive_answer(
        self,
        question: str,
        retrieved_data: Dict[str, Any],
        file_processing_result: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate comprehensive answer using all available data"""
        
        # Prepare context from retrieved data with agent-specific intelligence
        context_parts = []
        
        for agent_name, agent_data in retrieved_data.items():
            data = agent_data.get("data", {})
            relevance_score = agent_data.get("relevance_score", 0.0)
            reasoning = agent_data.get("reasoning", "")
            priority_data = agent_data.get("priority_data", [])
            
            if relevance_score > 0.5:  # Only include highly relevant data
                context_parts.append(f"\n--- {agent_name.title()} Data (Relevance: {relevance_score:.1f}) ---")
                context_parts.append(f"Agent Assessment: {reasoning}")
                
                # Include priority data first
                for priority_key in priority_data:
                    if priority_key in data:
                        context_parts.append(f"{priority_key.title()}: {data[priority_key]}")
                
                # Also include all available data keys for comprehensive context
                for key, value in data.items():
                    if key not in priority_data:  # Don't duplicate priority data
                        if key == "recent_reports" and isinstance(value, list):
                            context_parts.append(f"{key.title()}: {len(value)} lab reports found")
                            # Include some sample data for context
                            if value:
                                context_parts.append("Sample Lab Reports:")
                                for i, report in enumerate(value[:5]):  # Show first 5 reports
                                    context_parts.append(f"  {i+1}. {report.get('test_name', 'Unknown')} - {report.get('test_value', 'N/A')} {report.get('test_unit', '')} ({report.get('test_status', 'Unknown')})")
                        else:
                            context_parts.append(f"{key.title()}: {value}")
        
        # Include file processing result if available
        if file_processing_result and file_processing_result.get("extracted_data"):
            context_parts.append(f"\n--- Recently Processed Document ---")
            context_parts.append(f"Document Type: {file_processing_result.get('document_type')}")
            context_parts.append(f"Extracted Data: {file_processing_result['extracted_data']}")
        
        # Generate answer using LLM with intelligent context
        answer_prompt = f"""
        Based on the following health data, provide a direct and concise answer to the user's question.
        
        User Question: {question}
        
        Health Data Context:
        {chr(10).join(context_parts)}
        
        Instructions:
        1. Answer the specific question asked - nothing more, nothing less
        2. Present relevant data clearly and concisely 
        3. Use bullet points or structured format for lab results
        4. Include test values, units, and status when available
        5. Keep the response focused and avoid unnecessary analysis or recommendations
        6. Only mention concerning findings if directly relevant to the question
        
        Provide a direct, focused answer that specifically addresses what the user asked for.
        """
        
        try:
            messages = [
                SystemMessage(content="You are an intelligent health assistant that interprets medical data for patients, using agent-assessed relevance to focus on the most important information."),
                HumanMessage(content=answer_prompt)
            ]
            
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            return f"I have your health data available and multiple specialized agents assessed its relevance to your question, but I'm having trouble generating a comprehensive response right now. Please try rephrasing your question. Error: {str(e)}"
    
    async def handle_error(self, state: CustomerAgentState) -> CustomerAgentState:
        """Handle errors in processing"""
        
        error_message = state.get("error_message", "An unknown error occurred")
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "handle_error",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"],
            error_message=error_message,
            request_type=state.get("request_type"),
            user_message=state.get("user_message", "")[:100] + "..." if len(state.get("user_message", "")) > 100 else state.get("user_message", ""),
            has_file=bool(state.get("uploaded_file")),
            file_processing_status=state.get("file_processing_result", {}).get("processing_status") if state.get("file_processing_result") else None
        ):
            log_agent_interaction(
                "EnhancedCustomerAgent",
                "System",
                "error_handled",
                {
                    "error_message": error_message,
                    "request_type": state.get("request_type"),
                    "processing_stage": "error_handling",
                    "file_processing_attempted": bool(state.get("file_processing_result")),
                    "data_retrieval_attempted": bool(state.get("retrieved_data"))
                },
                user_id=state["user_id"],
                session_id=state["session_id"],
                request_id=state["request_id"]
            )
            
            # Handle different types of errors with appropriate user messages
            if error_message.startswith("nutrition_processing_failed:"):
                # Extract the nutrition error details
                nutrition_error = error_message.replace("nutrition_processing_failed:", "")
                state["response_message"] = f"""🍽️ **Food Image Processing Issue**

I detected that you uploaded a food image, but I'm currently experiencing technical difficulties processing nutrition data.

**What I was trying to do:**
• Analyze the nutritional content of your food
• Extract calories, proteins, carbs, and other nutrients
• Store the meal information in your nutrition log

**Technical Issue:**
{nutrition_error}

**What you can try:**
• Please restart the backend server to apply recent updates
• Try uploading the food image again in a few minutes
• Contact support if the issue persists

I apologize for the inconvenience! The nutrition analysis feature is being updated to provide better food recognition and detailed nutritional information."""
                state["processing_complete"] = True
                return state

            elif error_message.startswith("medical_processing_failed:"):
                # Extract the medical error details
                medical_error = error_message.replace("medical_processing_failed:", "")
                state["response_message"] = f"""🏥 **Medical Image Processing Issue**

I detected that you uploaded a medical image (X-ray, MRI, CT scan, etc.), but I'm currently experiencing technical difficulties processing medical images.

**What I was trying to do:**
• Analyze the medical image content
• Extract relevant medical information
• Store the image with AI-generated summary

**Technical Issue:**
{medical_error}

**What you can try:**
• Please restart the backend server to apply recent updates
• Try uploading the medical image again in a few minutes
• Contact support if the issue persists

I apologize for the inconvenience! The medical image analysis feature is being updated to provide better image recognition and detailed analysis."""
                state["processing_complete"] = True
                return state
            
            # Handle unsupported document type error specifically
            elif error_message.startswith("unsupported_document_type:"):
                try:
                    # Parse the error message: "unsupported_document_type:{type}:{suggestions}"
                    parts = error_message.split(":", 2)
                    if len(parts) >= 3:
                        document_type = parts[1]
                        suggestions = parts[2]
                        
                        state["response_message"] = f"""❌ **Document Not Supported**

I can't process this document because it appears to be a **{document_type}** document, which is not one of the medical document types I support.

**What I can process:**
• 📋 **Lab Reports** - Blood tests, diagnostic results, laboratory findings
• 💊 **Prescription Documents** - Medication prescriptions, drug information
• 🏥 **Pharmacy Bills** - Medication purchase receipts, pharmacy invoices  
• 💓 **Vitals Records** - Blood pressure, heart rate, weight measurements

**What I detected in your document:**
{suggestions}

**Please try uploading:**
• A recent lab report from your healthcare provider
• A prescription document from your doctor
• A pharmacy receipt or bill
• A vitals measurement record

If you believe this document should be supported, please contact support for assistance."""
                    else:
                        # Fallback if parsing fails
                        state["response_message"] = """❌ **Document Not Supported**

I can't process this document because it doesn't appear to be a supported medical document type.

**What I can process:**
• 📋 **Lab Reports** - Blood tests, diagnostic results
• 💊 **Prescription Documents** - Medication prescriptions  
• 🏥 **Pharmacy Bills** - Medication purchase receipts
• 💓 **Vitals Records** - Blood pressure, heart rate, weight measurements

Please try uploading one of these supported document types."""
                except Exception as e:
                    # Fallback if any error in parsing
                    state["response_message"] = f"❌ I'm sorry, but I can't process this document. It doesn't appear to be a supported medical document type. Please try uploading a lab report, prescription, pharmacy bill, or vitals record."
            else:
                # Handle all other errors with the default message
                state["response_message"] = f"I'm sorry, but I encountered an issue while processing your request: {error_message}. Please try again or contact support if the problem persists."
            
            state["processing_complete"] = True
            return state
    
    async def execute_lab_agent(self, state: CustomerAgentState) -> CustomerAgentState:
        """Execute lab agent directly for lab-related queries"""
        
        step_start = time.time()
        print(f"🧪 [DEBUG] Starting execute_lab_agent at {isoformat_now()}")
        
        try:
            user_question = state["user_message"]
            lab_agent = self.data_agents["lab"]
            
            print(f"🧪 [DEBUG] Calling lab agent for: {user_question[:50]}...")
            
            # Use lab agent's intelligent assessment for proper retrieval strategy
            assessment = await lab_agent.assess_question_relevance(
                user_question,
                state["user_id"],
                state["session_id"]
            )
            
            # Get the intelligent retrieval strategy
            retrieval_strategy = assessment.get("retrieval_strategy", {
                "days_back": 365,  # Default to 1 year for lab data
                "limit": 50
            })
            
            print(f"🧪 [DEBUG] Using intelligent retrieval strategy: {retrieval_strategy}")
            
            # Direct call to lab agent with intelligent strategy
            result = await lab_agent.process_request(
                "retrieve",
                {"retrieval_request": retrieval_strategy},
                state["user_id"],
                state["session_id"]
            )
            
            # Check success in response_message (not top level)
            response_msg = result.get("response_message", {})
            if response_msg.get("success"):
                state["retrieved_data"]["lab"] = {
                    "data": response_msg.get("data", {}),  # Data is in response_message
                    "relevance_score": 1.0,  # High confidence since routed directly
                    "reasoning": "Direct route to lab agent for lab data query"
                }
                state["active_agents"] = ["lab"]
                print(f"✅ [DEBUG] Lab agent returned data successfully")
            else:
                print(f"⚠️ [DEBUG] Lab agent returned no data")
                state["retrieved_data"]["lab"] = {"data": {}, "error": result.get("error_message")}
            
            step_duration = time.time() - step_start
            state["timing_data"]["execute_lab_agent"] = step_duration
            print(f"✅ [DEBUG] execute_lab_agent completed in {step_duration:.2f}s")
            
            return state
            
        except Exception as e:
            step_duration = time.time() - step_start
            state["timing_data"]["execute_lab_agent"] = step_duration
            print(f"❌ [DEBUG] execute_lab_agent failed in {step_duration:.2f}s: {str(e)}")
            state["error_message"] = f"Lab agent execution failed: {str(e)}"
            return state
    
    async def execute_vitals_agent(self, state: CustomerAgentState) -> CustomerAgentState:
        """Execute vitals agent directly for vitals-related queries"""
        
        step_start = time.time()
        print(f"💓 [DEBUG] Starting execute_vitals_agent at {isoformat_now()}")
        
        try:
            user_question = state["user_message"]
            vitals_agent = self.data_agents["vitals"]
            
            print(f"💓 [DEBUG] Calling vitals agent for: {user_question[:50]}...")
            
            # Use vitals agent's intelligent assessment
            assessment = await vitals_agent.assess_question_relevance(
                user_question,
                state["user_id"],
                state["session_id"]
            )
            
            retrieval_strategy = assessment.get("retrieval_strategy", {
                "days_back": 180,  # Default to 6 months for vitals
                "limit": 30
            })
            
            print(f"💓 [DEBUG] Using intelligent retrieval strategy: {retrieval_strategy}")
            
            result = await vitals_agent.process_request(
                "retrieve",
                {"retrieval_request": retrieval_strategy},
                state["user_id"],
                state["session_id"]
            )
            
            if result.get("success"):
                state["retrieved_data"]["vitals"] = {
                    "data": result.get("data", {}),
                    "relevance_score": 1.0,
                    "reasoning": "Direct route to vitals agent for vitals data query"
                }
                state["active_agents"] = ["vitals"]
            else:
                state["retrieved_data"]["vitals"] = {"data": {}, "error": result.get("error_message")}
            
            step_duration = time.time() - step_start
            state["timing_data"]["execute_vitals_agent"] = step_duration
            print(f"✅ [DEBUG] execute_vitals_agent completed in {step_duration:.2f}s")
            
            return state
            
        except Exception as e:
            step_duration = time.time() - step_start
            state["timing_data"]["execute_vitals_agent"] = step_duration
            print(f"❌ [DEBUG] execute_vitals_agent failed in {step_duration:.2f}s: {str(e)}")
            state["error_message"] = f"Vitals agent execution failed: {str(e)}"
            return state
    
    async def execute_pharmacy_agent(self, state: CustomerAgentState) -> CustomerAgentState:
        """Execute pharmacy agent directly for pharmacy-related queries"""
        
        step_start = time.time()
        print(f"💊 [DEBUG] Starting execute_pharmacy_agent at {isoformat_now()}")
        
        try:
            user_question = state["user_message"]
            pharmacy_agent = self.data_agents["pharmacy"]
            
            print(f"💊 [DEBUG] Calling pharmacy agent for: {user_question[:50]}...")
            
            # Use pharmacy agent's intelligent assessment
            assessment = await pharmacy_agent.assess_question_relevance(
                user_question,
                state["user_id"],
                state["session_id"]
            )
            
            retrieval_strategy = assessment.get("retrieval_strategy", {
                "days_back": 365,  # Default to 1 year for pharmacy data
                "limit": 50
            })
            
            print(f"💊 [DEBUG] Using intelligent retrieval strategy: {retrieval_strategy}")
            
            result = await pharmacy_agent.process_request(
                "retrieve",
                {"retrieval_request": retrieval_strategy},
                state["user_id"],
                state["session_id"]
            )
            
            if result.get("success"):
                state["retrieved_data"]["pharmacy"] = {
                    "data": result.get("data", {}),
                    "relevance_score": 1.0,
                    "reasoning": "Direct route to pharmacy agent for pharmacy data query"
                }
                state["active_agents"] = ["pharmacy"]
            else:
                state["retrieved_data"]["pharmacy"] = {"data": {}, "error": result.get("error_message")}
            
            step_duration = time.time() - step_start
            state["timing_data"]["execute_pharmacy_agent"] = step_duration
            print(f"✅ [DEBUG] execute_pharmacy_agent completed in {step_duration:.2f}s")
            
            return state
            
        except Exception as e:
            step_duration = time.time() - step_start
            state["timing_data"]["execute_pharmacy_agent"] = step_duration
            print(f"❌ [DEBUG] execute_pharmacy_agent failed in {step_duration:.2f}s: {str(e)}")
            state["error_message"] = f"Pharmacy agent execution failed: {str(e)}"
            return state
    
    async def execute_prescription_agent(self, state: CustomerAgentState) -> CustomerAgentState:
        """Execute prescription agent directly for prescription-related queries"""
        
        step_start = time.time()
        print(f"📋 [DEBUG] Starting execute_prescription_agent at {isoformat_now()}")
        
        try:
            user_question = state["user_message"]
            prescription_agent = self.data_agents["prescription"]
            
            print(f"📋 [DEBUG] Calling prescription agent for: {user_question[:50]}...")
            
            # Use prescription agent's intelligent assessment
            assessment = await prescription_agent.assess_question_relevance(
                user_question,
                state["user_id"],
                state["session_id"]
            )
            
            retrieval_strategy = assessment.get("retrieval_strategy", {
                "days_back": 365,  # Default to 1 year for prescription data
                "limit": 30
            })
            
            print(f"📋 [DEBUG] Using intelligent retrieval strategy: {retrieval_strategy}")
            
            result = await prescription_agent.process_request(
                "retrieve",
                {"retrieval_request": retrieval_strategy},
                state["user_id"],
                state["session_id"]
            )
            
            if result.get("success"):
                state["retrieved_data"]["prescription"] = {
                    "data": result.get("data", {}),
                    "relevance_score": 1.0,
                    "reasoning": "Direct route to prescription agent for prescription data query"
                }
                state["active_agents"] = ["prescription"]
            else:
                state["retrieved_data"]["prescription"] = {"data": {}, "error": result.get("error_message")}
            
            step_duration = time.time() - step_start
            state["timing_data"]["execute_prescription_agent"] = step_duration
            print(f"✅ [DEBUG] execute_prescription_agent completed in {step_duration:.2f}s")
            
            return state
            
        except Exception as e:
            step_duration = time.time() - step_start
            state["timing_data"]["execute_prescription_agent"] = step_duration
            print(f"❌ [DEBUG] execute_prescription_agent failed in {step_duration:.2f}s: {str(e)}")
            state["error_message"] = f"Prescription agent execution failed: {str(e)}"
        return state

    async def execute_nutrition_agent(self, state: CustomerAgentState) -> CustomerAgentState:
        """Execute nutrition agent for food-related queries"""
        
        step_start = time.time()
        try:
            print(f"🍽️ [DEBUG] Starting execute_nutrition_agent at {isoformat_now()}")
            
            user_question = state.get("user_message", "")
            retrieval_strategy = state.get("retrieval_strategy", {})
            
            # Get nutrition agent and assess relevance
            nutrition_agent = self.data_agents["nutrition"]
            assessment = await nutrition_agent.assess_question_relevance(
                user_question, 
                state["user_id"], 
                state.get("session_id")
            )
            
            if assessment.get("is_relevant", False):
                print(f"🍽️ [DEBUG] Using intelligent retrieval strategy: {retrieval_strategy}")
                
                # Retrieve nutrition data
                retrieval_request = {
                    "days_back": retrieval_strategy.get("days_back", 7),
                    "summary_type": retrieval_strategy.get("summary_type", "daily"),
                    "limit": 50
                }
                
                result = await nutrition_agent.process_request(
                    "retrieve",
                    {"retrieval_request": retrieval_request},
                    state["user_id"],
                    state.get("session_id")
                )
                
                if result.get("success"):
                    state["data_retrieval_result"] = result["response_message"]
                    state["reasoning"] = f"Retrieved nutrition data: {assessment.get('reasoning', 'nutrition analysis')}"
                    print(f"✅ [DEBUG] Nutrition data retrieved successfully")
                else:
                    state["error_message"] = f"Nutrition data retrieval failed: {result.get('error', 'Unknown error')}"
            else:
                state["data_retrieval_result"] = {
                    "success": False,
                    "message": "Question not relevant to nutrition data"
                }
                state["reasoning"] = assessment.get("reasoning", "Not nutrition-related")
                print(f"ℹ️ [DEBUG] Question not relevant to nutrition data")
            
            step_duration = time.time() - step_start
            state["timing_data"]["execute_nutrition_agent"] = step_duration
            print(f"✅ [DEBUG] execute_nutrition_agent completed in {step_duration:.2f}s")
            
            return state
        
        except Exception as e:
            step_duration = time.time() - step_start
            state["timing_data"]["execute_nutrition_agent"] = step_duration
            print(f"❌ [DEBUG] execute_nutrition_agent failed in {step_duration:.2f}s: {str(e)}")
            state["error_message"] = f"Nutrition agent execution failed: {str(e)}"
            return state
    
    async def execute_multi_agent(self, state: CustomerAgentState) -> CustomerAgentState:
        """Execute multiple agents for complex queries (fallback to assessment approach)"""
        
        step_start = time.time()
        print(f"🔄 [DEBUG] Starting execute_multi_agent at {isoformat_now()}")
        print(f"🔄 [DEBUG] Using assessment approach for complex/unclear query")
        
        # For complex queries, fall back to the original assessment-based approach
        result = await self.retrieve_data(state)
        
        step_duration = time.time() - step_start
        state["timing_data"]["execute_multi_agent"] = step_duration
        print(f"✅ [DEBUG] execute_multi_agent completed in {step_duration:.2f}s")
        
        return result

    async def _validate_document_type(self, file_path: str) -> Dict[str, Any]:
        """Validate if the uploaded document is of a supported medical document type"""
        
        try:
            # Import OCR toolkit for text extraction
            from app.agents.tools.ocr_tools import OCRToolkit
            from pathlib import Path
            
            # Extract text from document for classification
            ocr_toolkit = OCRToolkit()
            
            # Use the correct synchronous OCR methods based on file type
            file_path_obj = Path(file_path)
            file_extension = file_path_obj.suffix.lower()
            
            if file_extension == '.pdf':
                ocr_text = ocr_toolkit._extract_text_from_pdf(file_path_obj)
            else:
                ocr_text = ocr_toolkit._extract_text_from_image(file_path_obj)
            
            # Check if OCR failed or returned error
            if not ocr_text or ocr_text.startswith("[OCR ERROR]") or ocr_text.startswith("[OCR FALLBACK]"):
                return {
                    "is_valid": False,
                    "document_type": "unreadable",
                    "suggestions": "Please ensure the document is clear and readable. Try scanning at higher resolution or using a different file format.",
                    "cached_ocr_data": None
                }
            
            # Use first 2000 characters for classification
            ocr_text_for_classification = ocr_text[:2000]
            
            # Cache the full OCR data for later use
            cached_ocr_data = {
                "text": ocr_text,
                "confidence": 0.8,  # Default confidence
                "extraction_method": "pdf" if file_extension == '.pdf' else "image",
                "text_length": len(ocr_text)
            }
            
            # Use LLM to classify and validate document type
            validation_prompt = f"""
            Analyze the following document text and determine if it's a valid medical document that falls into one of these supported categories:

            SUPPORTED TYPES:
            - lab_report: Laboratory test results, blood tests, urine tests, diagnostic lab reports
            - prescription: Medical prescriptions, medication orders from doctors. one of way to identify is if it has a doctor's name and a patient's name and if it handwritten or if it mentions OUT-PATIENT RECORD
            - pharmacy_bill: Pharmacy receipts, medication purchase bills, drug store receipts
            - vitals_report: Vital signs measurements, blood pressure readings, weight charts, health monitoring reports

            Document text to analyze:
            {ocr_text_for_classification}

            If the document matches one of the supported types, respond with:
            VALID:<type>

            If the document is NOT a medical document or doesn't match any supported type, respond with:
            INVALID:<detected_type>:<suggestions>

            Where:
            - <detected_type> should be what you think the document actually is (e.g., "invoice", "letter", "form", "insurance_claim", etc.)
            - <suggestions> should be specific suggestions for what type of medical document the user should upload instead

            Examples:
            - For a lab report: "VALID:lab_report"
            - For a car repair invoice: "INVALID:automotive_invoice:Please upload a medical document such as lab test results, prescription from your doctor, pharmacy receipt, or vital signs report."
            - For an insurance form: "INVALID:insurance_form:This appears to be an insurance document. Please upload a medical document like lab reports, prescriptions, pharmacy bills, or vital signs measurements."
            """
            
            messages = [
                SystemMessage(content="You are a medical document validator that determines if documents are supported medical document types."),
                HumanMessage(content=validation_prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            print(f"📄 [DEBUG] Document validation response: {response_text}")
            
            if response_text.startswith("VALID:"):
                document_type = response_text.split(":", 1)[1]
                return {
                    "is_valid": True,
                    "document_type": document_type,
                    "suggestions": "",
                    "cached_ocr_data": cached_ocr_data  # Include cached OCR data for valid documents
                }
            elif response_text.startswith("INVALID:"):
                parts = response_text.split(":", 2)
                detected_type = parts[1] if len(parts) > 1 else "unknown"
                suggestions = parts[2] if len(parts) > 2 else "Please upload a valid medical document such as lab reports, prescriptions, pharmacy bills, or vital signs measurements."
                return {
                    "is_valid": False,
                    "document_type": detected_type,
                    "suggestions": suggestions,
                    "cached_ocr_data": None  # Don't cache OCR data for invalid documents
                }
            else:
                # Fallback in case of unexpected response format
                return {
                    "is_valid": False,
                    "document_type": "unknown",
                    "suggestions": "Unable to determine document type. Please upload a clear medical document such as lab test results, prescription from your doctor, pharmacy receipt, or vital signs report.",
                    "cached_ocr_data": None
                }
                
        except Exception as e:
            print(f"❌ [DEBUG] Document validation error: {str(e)}")
            # On error, assume document might be valid to avoid blocking legitimate documents
            return {
                "is_valid": True,
                "document_type": "unknown",
                "suggestions": "",
                "cached_ocr_data": None  # No cached data on error
            }

    async def execute_medical_consultation(self, state: CustomerAgentState) -> CustomerAgentState:
        """Execute medical consultation by collecting data from multiple agents and using medical doctor agent"""
        
        step_start = time.time()
        print(f"🩺 [DEBUG] Starting execute_medical_consultation at {isoformat_now()}")
        
        try:
            user_question = state["user_message"]
            print(f"🩺 [DEBUG] Medical consultation for: {user_question[:50]}...")
            
            # Collect data from all relevant health agents
            retrieved_data = {}
            agent_names = ["lab", "vitals", "pharmacy", "prescription", "nutrition"]
            
            print(f"🩺 [DEBUG] Collecting data from {len(agent_names)} health agents...")
            
            for agent_name in agent_names:
                try:
                    agent = self.data_agents[agent_name]
                    
                    # Use broad retrieval strategy for medical consultations
                    retrieval_strategy = {
                        "days_back": 365,  # 1 year of data for comprehensive medical review
                        "limit": 100,
                        "specific_filters": {},
                        "priority_data": ["recent_reports", "summary", "analysis"]
                    }
                    
                    print(f"🩺 [DEBUG] Retrieving data from {agent_name} agent...")
                    
                    result = await agent.process_request(
                        "retrieve",
                        {"retrieval_request": retrieval_strategy},
                        state["user_id"],
                        state["session_id"]
                    )
                    
                    # Check success in response_message (consistent with other agents)
                    response_msg = result.get("response_message", {})
                    if response_msg.get("success"):
                        retrieved_data[agent_name] = {
                            "data": response_msg.get("data", {}),
                            "relevance_score": 1.0,  # High relevance for medical consultation
                            "reasoning": f"Medical consultation data from {agent_name} agent"
                        }
                        print(f"✅ [DEBUG] {agent_name} agent returned data successfully")
                    else:
                        print(f"⚠️ [DEBUG] {agent_name} agent returned no data")
                        
                except Exception as e:
                    print(f"❌ [DEBUG] {agent_name} agent failed: {str(e)}")
                    continue
            
            print(f"🩺 [DEBUG] Collected data from {len(retrieved_data)} agents")
            
            # Include file processing result if available (for document-specific questions)
            file_processing_result = state.get("file_processing_result")
            if file_processing_result:
                print(f"🩺 [DEBUG] Including uploaded document data in medical consultation")
                retrieved_data["uploaded_document"] = {
                    "data": {
                        "document_type": file_processing_result.get("document_type", "unknown"),
                        "extracted_data": file_processing_result.get("extracted_data", {}),
                        "processing_status": file_processing_result.get("processing_status", "unknown"),
                        "question_answer": file_processing_result.get("question_answer"),  # May be None
                        "storage_summary": file_processing_result.get("storage_summary", {})
                    },
                    "relevance_score": 1.0,  # High relevance for uploaded document
                    "reasoning": "Recently uploaded document for analysis"
                }
            
            # Use medical doctor agent for comprehensive consultation
            medical_doctor = self.data_agents["medical_doctor"]
            
            # Check if this is a document-specific question
            file_processing_result = state.get("file_processing_result")
            document_data = None
            if file_processing_result and state["request_type"] == "file_and_question":
                # For document-specific questions, pass the document data directly
                document_data = file_processing_result.get("extracted_data")
                print(f"📄 [DEBUG] Passing document data directly to medical doctor (skipping historical data collection)")
            
            consultation_result = await medical_doctor.handle_medical_question(
                user_question,
                state["user_id"],
                state["session_id"],
                guardrails_validation=state.get("guardrails_validation"),
                document_data=document_data  # Pass document data for optimization
            )
            
            if consultation_result.get("success"):
                # Store the medical consultation response
                state["retrieved_data"]["medical_consultation"] = {
                    "data": {
                        "consultation_response": consultation_result.get("medical_response"),  # Fixed: medical_response -> consultation_response
                        "data_sources_used": consultation_result.get("data_sources_used", []),
                        "medical_context_summary": consultation_result.get("agent_requirements", {})  # Fixed: use agent_requirements
                    },
                    "relevance_score": 1.0,
                    "reasoning": "Comprehensive medical consultation using multi-agent data"
                }
                
                # Also store the collected health data
                for agent_name, agent_data in retrieved_data.items():
                    state["retrieved_data"][agent_name] = agent_data
                
                state["active_agents"] = list(retrieved_data.keys()) + ["medical_doctor"]
                state["coordination_mode"] = "medical_consultation"
                
                print(f"✅ [DEBUG] Medical consultation completed successfully")
            else:
                error_msg = consultation_result.get("error_message", "Medical consultation failed")
                print(f"❌ [DEBUG] Medical consultation failed: {error_msg}")
                state["error_message"] = error_msg
            
            step_duration = time.time() - step_start
            state["timing_data"]["execute_medical_consultation"] = step_duration
            print(f"✅ [DEBUG] execute_medical_consultation completed in {step_duration:.2f}s")
            
            return state
            
        except Exception as e:
            step_duration = time.time() - step_start
            state["timing_data"]["execute_medical_consultation"] = step_duration
            print(f"❌ [DEBUG] execute_medical_consultation failed in {step_duration:.2f}s: {str(e)}")
            state["error_message"] = f"Medical consultation execution failed: {str(e)}"
            return state

    async def execute_medical_doctor(self, state: CustomerAgentState) -> CustomerAgentState:
        """Execute medical doctor agent directly for question-only workflows"""
        
        step_start = time.time()
        print(f"🩺 [DEBUG] Starting execute_medical_doctor at {isoformat_now()}")
        
        with trace_agent_operation(
            "EnhancedCustomerAgent",
            "execute_medical_doctor",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"],
            orchestrator="EnhancedCustomerAgent"  # NEW: Mark as orchestrator
        ):
            try:
                user_question = state["user_message"]
                print(f"🩺 [DEBUG] Medical doctor handling question: {user_question[:50]}...")
                
                # Get medical doctor agent and let it handle the question
                medical_doctor = self.data_agents["medical_doctor"]
                
                # Medical doctor will analyze the question and query relevant agents itself
                consultation_result = await medical_doctor.handle_medical_question(
                    user_question,
                    state["user_id"],
                    state["session_id"],
                    guardrails_validation=state.get("guardrails_validation")  # NEW: Pass validation results
                )
                
                if consultation_result.get("success"):
                    # Store the medical response
                    state["retrieved_data"]["medical_doctor"] = {
                        "data": {
                            "medical_response": consultation_result.get("medical_response"),
                            "data_sources_used": consultation_result.get("data_sources_used", []),
                            "agent_requirements": consultation_result.get("agent_requirements", {})
                        },
                        "relevance_score": 1.0,
                        "reasoning": "Direct medical consultation for question-only workflow"
                    }
                    
                    state["active_agents"] = ["medical_doctor"] + consultation_result.get("data_sources_used", [])
                    state["coordination_mode"] = "medical_doctor_direct"
                    
                    print(f"✅ [DEBUG] Medical doctor consultation completed successfully")
                else:
                    error_msg = consultation_result.get("error_message", "Medical consultation failed")
                    print(f"❌ [DEBUG] Medical doctor consultation failed: {error_msg}")
                    state["error_message"] = error_msg
                
                step_duration = time.time() - step_start
                state["timing_data"]["execute_medical_doctor"] = step_duration
                print(f"✅ [DEBUG] execute_medical_doctor completed in {step_duration:.2f}s")
                
                return state
                
            except Exception as e:
                step_duration = time.time() - step_start
                state["timing_data"]["execute_medical_doctor"] = step_duration
                print(f"❌ [DEBUG] execute_medical_doctor failed in {step_duration:.2f}s: {str(e)}")
                state["error_message"] = f"Medical doctor execution failed: {str(e)}"
                return state

    def _is_likely_filename(self, message: str) -> bool:
        """Check if a message is likely just a filename rather than a healthcare question"""
        if not message:
            return False
        
        message = message.strip()
        
        # Check for common file extensions
        file_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.txt', '.csv', '.xls', '.xlsx']
        if any(message.lower().endswith(ext) for ext in file_extensions):
            return True
        
        # Check if it's very short and contains no question words
        if len(message) < 20:
            question_words = ['what', 'how', 'why', 'when', 'where', 'is', 'are', 'can', 'should', 'do', 'does', '?']
            if not any(word in message.lower() for word in question_words):
                return True
        
        # Check if it looks like a filename pattern (no spaces, underscores/dashes)
        if len(message.split()) == 1 and ('_' in message or '-' in message):
            return True
        
        # Check if it's just numbers and letters (might be a file ID)
        if message.replace('_', '').replace('-', '').replace('.', '').isalnum() and len(message) < 50:
            return True
        
        return False

    async def _classify_image_with_gpt4v(self, file_path: str) -> Dict[str, Any]:
        """Enhanced image classification using GPT-4V to detect food, medical, or document images"""
        
        try:
            import base64
            from pathlib import Path
            from langchain_core.messages import SystemMessage, HumanMessage
            from langchain_openai import ChatOpenAI
            
            # Check if file exists
            if not Path(file_path).exists():
                return {
                    "success": False,
                    "error": "Image file not found",
                    "image_type": "unknown"
                }
            
            # Read and encode image
            with open(file_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Create GPT-4V client
            vision_llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.1,
                timeout=30
            )
            
            # Classification prompt
            classification_prompt = """
            Analyze this image and classify it into one of these categories:

            1. **FOOD/DISH** - Images of food, meals, dishes, beverages, or any edible items
               - Examples: restaurant meals, home-cooked food, fruits, vegetables, drinks, snacks
               - Return: "food"

            2. **MEDICAL** - Medical images like X-rays, MRIs, CT scans, ultrasounds, or other medical imaging
               - Examples: chest X-rays, brain MRIs, ultrasound images, CT scans, medical charts with images
               - Return: "medical"

            3. **DOCUMENT** - Text-based documents like lab reports, prescriptions, pharmacy bills, medical records
               - Examples: lab test results, prescription forms, medical bills, health reports with text
               - Return: "document"

            4. **OTHER** - Any other type of image that doesn't fit the above categories
               - Return: "other"

            Respond with ONLY the category name: "food", "medical", "document", or "other"

            If the image contains food, also provide:
            - A brief description of the food items visible
            - Estimated meal type (breakfast, lunch, dinner, snack)
            - Confidence level (0.0-1.0)

            If the image is medical, also provide:
            - Type of medical image (x-ray, mri, ct-scan, ultrasound, etc.)
            - Body part or area shown
            - Confidence level (0.0-1.0)

            Response format:
            {
                "image_type": "food/medical/document/other",
                "description": "brief description",
                "details": {
                    "meal_type": "breakfast/lunch/dinner/snack" // for food only
                    "medical_type": "x-ray/mri/ct-scan/ultrasound" // for medical only
                    "body_part": "chest/abdomen/head/etc" // for medical only
                },
                "confidence": 0.8
            }
            """
            
            # Analyze image
            messages = [
                SystemMessage(content="You are an expert at classifying images into food, medical, document, or other categories."),
                HumanMessage(content=[
                    {"type": "text", "text": classification_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ])
            ]
            
            # Log ChatGPT interaction (GPT-4V)
            messages_dict = [
                {"role": "system", "content": "You are an expert at classifying images into food, medical, document, or other categories."},
                {"role": "user", "content": f"[IMAGE DATA] {classification_prompt}"}  # Simplified for logging
            ]
            
            response = vision_llm.invoke(messages)
            
            # Log the interaction
            log_chatgpt_interaction(
                agent_name="EnhancedCustomerAgent",
                operation="classify_image_with_gpt4v",
                request_data=messages_dict,
                response_data=response,
                model_name="gpt-4o",
                additional_metadata={"image_path": file_path, "image_size": len(image_data)}
            )
            
            if not response or not response.content:
                return {
                    "success": False,
                    "error": "Empty response from vision model",
                    "image_type": "unknown"
                }
            
            # Parse response
            import json
            try:
                content = response.content.strip()
                if content.startswith('```json'):
                    content = content[7:-3].strip()
                elif content.startswith('```'):
                    content = content[3:-3].strip()
                
                result = json.loads(content)
                
                return {
                    "success": True,
                    "image_type": result.get("image_type", "other"),
                    "description": result.get("description", ""),
                    "details": result.get("details", {}),
                    "confidence": result.get("confidence", 0.5)
                }
                
            except json.JSONDecodeError:
                # Fallback - simple keyword extraction
                content_lower = response.content.lower()
                if any(word in content_lower for word in ["food", "meal", "dish", "eat"]):
                    return {
                        "success": True,
                        "image_type": "food",
                        "description": "Food image detected",
                        "details": {"meal_type": "other"},
                        "confidence": 0.6
                    }
                elif any(word in content_lower for word in ["x-ray", "mri", "ct", "scan", "medical"]):
                    return {
                        "success": True,
                        "image_type": "medical",
                        "description": "Medical image detected",
                        "details": {"medical_type": "unknown", "body_part": "unknown"},
                        "confidence": 0.6
                    }
                else:
                    return {
                        "success": True,
                        "image_type": "document",
                        "description": "Document image detected",
                        "details": {},
                        "confidence": 0.5
                    }
            
        except Exception as e:
            print(f"❌ [DEBUG] Image classification failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "image_type": "unknown"
            }

    async def _process_nutrition_image(self, file_path: str, user_id: int, session_id: Optional[int]) -> Dict[str, Any]:
        """Process food images using nutrition agent"""
        
        try:
            print(f"🍽️ [DEBUG] Processing nutrition image: {file_path}")
            
            # Get nutrition agent
            nutrition_agent = self.data_agents["nutrition"]
            
            # Extract nutrition data from image
            extract_result = await nutrition_agent.process_request(
                "extract",
                {"image_path": file_path},
                user_id,
                session_id
            )
            
            if not extract_result.get("success"):
                return {
                    "success": False,
                    "error": f"Nutrition extraction failed: {extract_result.get('error', 'Unknown error')}",
                    "document_type": "food_image"
                }
            
            # Get extracted nutrition data
            nutrition_data = extract_result["response_message"]["data"]
            
            # Determine meal time (default to current time)
            from datetime import datetime
            meal_time = now_local()
            
            # Determine meal type based on time of day
            hour = meal_time.hour
            if 5 <= hour < 11:
                meal_type = "breakfast"
            elif 11 <= hour < 16:
                meal_type = "lunch"
            elif 16 <= hour < 21:
                meal_type = "dinner"
            else:
                meal_type = "snack"
            
            # Store nutrition data
            store_result = await nutrition_agent.process_request(
                "store",
                {
                    "nutrition_data": nutrition_data,
                    "meal_time": meal_time,
                    "meal_type": meal_type
                },
                user_id,
                session_id
            )
            
            if store_result.get("success"):
                return {
                    "success": True,
                    "document_type": "food_image",
                    "extracted_data": {
                        "dish_name": nutrition_data.get("dish_name", "Unknown dish"),
                        "calories": nutrition_data.get("calories", 0),
                        "meal_type": meal_type,
                        "confidence": nutrition_data.get("confidence_score", 0.8),
                        "nutrition_id": store_result["response_message"]["data"]["nutrition_id"]
                    },
                    "processing_status": "completed",
                    "message": f"Successfully processed {nutrition_data.get('dish_name', 'food image')} with {nutrition_data.get('calories', 0)} calories"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to store nutrition data: {store_result.get('error', 'Unknown error')}",
                    "document_type": "food_image"
                }
                
        except Exception as e:
            print(f"❌ [DEBUG] Nutrition image processing failed: {str(e)}")
            return {
                "success": False,
                "error": f"Nutrition processing failed: {str(e)}",
                "document_type": "food_image"
            }

    async def _process_medical_image(self, file_path: str, classification_result: Dict[str, Any], user_id: int, session_id: Optional[int]) -> Dict[str, Any]:
        """Process medical images (X-ray, MRI, CT, ultrasound) and store them"""
        
        try:
            print(f"🏥 [DEBUG] Processing medical image: {file_path}")
            
            from app.models.health_data import MedicalImage
            from app.db.session import SessionLocal
            from pathlib import Path
            from datetime import datetime
            import os
            
            # Create medical images directory if it doesn't exist
            medical_images_dir = Path("backend/data/uploads/medical_images")
            medical_images_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy image to medical images directory
            original_path = Path(file_path)
            new_filename = f"medical_{user_id}_{now_local().strftime('%Y%m%d_%H%M%S')}_{original_path.name}"
            new_path = medical_images_dir / new_filename
            
            import shutil
            shutil.copy2(file_path, new_path)
            
            # Use GPT-4V to generate summary of medical image
            summary_result = await self._generate_medical_image_summary(str(new_path), classification_result)
            
            # Store medical image record in database
            with SessionLocal() as db:
                medical_image = MedicalImage(
                    user_id=user_id,
                    image_type=classification_result["details"].get("medical_type", "unknown"),
                    body_part=classification_result["details"].get("body_part", "unknown"),
                    image_path=str(new_path),
                    original_filename=original_path.name,
                    file_size=original_path.stat().st_size,
                    image_format=original_path.suffix.lower().replace(".", ""),
                    ai_summary=summary_result.get("summary", "Medical image analysis"),
                    ai_findings=summary_result.get("findings", ""),
                    confidence_score=classification_result.get("confidence", 0.8),
                    exam_date=now_local().date(),
                    processing_status="processed",
                    processed_at=now_local()
                )
                
                db.add(medical_image)
                db.commit()
                db.refresh(medical_image)
                
                return {
                    "success": True,
                    "document_type": "medical_image",
                    "extracted_data": {
                        "image_type": medical_image.image_type,
                        "body_part": medical_image.body_part,
                        "summary": medical_image.ai_summary,
                        "findings": medical_image.ai_findings,
                        "confidence": medical_image.confidence_score,
                        "medical_image_id": medical_image.id,
                        "image_path": str(new_path)
                    },
                    "processing_status": "completed",
                    "message": f"Successfully processed {medical_image.image_type} image of {medical_image.body_part}"
                }
                
        except Exception as e:
            print(f"❌ [DEBUG] Medical image processing failed: {str(e)}")
            return {
                "success": False,
                "error": f"Medical image processing failed: {str(e)}",
                "document_type": "medical_image"
            }

    async def _generate_medical_image_summary(self, image_path: str, classification_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI summary for medical images"""
        
        try:
            import base64
            from langchain_core.messages import SystemMessage, HumanMessage
            from langchain_openai import ChatOpenAI
            
            # Read and encode image
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Create GPT-4V client
            vision_llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.1,
                timeout=45
            )
            
            medical_type = classification_result["details"].get("medical_type", "medical image")
            body_part = classification_result["details"].get("body_part", "unknown area")
            
            # Medical analysis prompt
            analysis_prompt = f"""
            Analyze this {medical_type} image of the {body_part} and provide:

            1. **Image Quality Assessment**: Clarity, positioning, technical quality
            2. **Anatomical Structures**: What structures are visible
            3. **Notable Observations**: Any visible findings, abnormalities, or notable features
            4. **Technical Details**: Image type, view/projection if applicable

            IMPORTANT: 
            - Do NOT provide medical diagnoses or clinical interpretations
            - Focus on objective, descriptive observations only
            - Mention if image quality affects analysis
            - State limitations of AI analysis

            Response format:
            {{
                "summary": "Brief overall description of the image",
                "findings": "Objective observations of visible structures and features",
                "image_quality": "Assessment of technical quality",
                "limitations": "Limitations of AI analysis"
            }}
            """
            
            messages = [
                SystemMessage(content="You are an AI assistant analyzing medical images for documentation purposes. Provide objective, descriptive observations only. Do not provide medical diagnoses."),
                HumanMessage(content=[
                    {"type": "text", "text": analysis_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ])
            ]
            
            response = vision_llm.invoke(messages)
            
            if response and response.content:
                try:
                    import json
                    content = response.content.strip()
                    if content.startswith('```json'):
                        content = content[7:-3].strip()
                    elif content.startswith('```'):
                        content = content[3:-3].strip()
                    
                    result = json.loads(content)
                    return result
                    
                except json.JSONDecodeError:
                    # Fallback to text summary
                    return {
                        "summary": f"{medical_type} image analysis completed",
                        "findings": response.content[:500] + "..." if len(response.content) > 500 else response.content,
                        "image_quality": "Analysis completed",
                        "limitations": "AI analysis provides descriptive observations only"
                    }
            else:
                return {
                    "summary": f"{medical_type} image processed",
                    "findings": "Image analysis could not be completed automatically",
                    "image_quality": "Unable to assess",
                    "limitations": "Analysis limited due to processing constraints"
                }
                
        except Exception as e:
            print(f"❌ [DEBUG] Medical image summary generation failed: {str(e)}")
            return {
                "summary": f"Medical image processed with limitations",
                "findings": f"Analysis error: {str(e)}",
                "image_quality": "Unable to assess",
                "limitations": "Technical error during analysis"
            }

    # Now update the validation logic to use enhanced image processing
    async def _enhanced_image_validation(self, file_path: str, user_id: int, session_id: Optional[int]) -> Dict[str, Any]:
        """Enhanced image validation and processing using GPT-4V classification"""
        
        try:
            print(f"🔍 [DEBUG] Starting enhanced image classification for: {file_path}")
            
            # Classify image with GPT-4V
            classification_result = await self._classify_image_with_gpt4v(file_path)
            
            if not classification_result.get("success"):
                return {
                    "success": False,
                    "error": f"Image classification failed: {classification_result.get('error', 'Unknown error')}",
                    "document_type": "unknown"
                }
            
            image_type = classification_result.get("image_type", "unknown")
            print(f"🔍 [DEBUG] Image classified as: {image_type}")
            
            # Route based on image type
            if image_type == "food":
                print(f"🍽️ [DEBUG] Processing food image with nutrition agent")
                return await self._process_nutrition_image(file_path, user_id, session_id)
                
            elif image_type == "medical":
                print(f"🏥 [DEBUG] Processing medical image")
                return await self._process_medical_image(file_path, classification_result, user_id, session_id)
                
            elif image_type == "document":
                print(f"📄 [DEBUG] Processing document image with existing validation")
                return await self._validate_document_type(file_path)
                
            else:
                print(f"❓ [DEBUG] Unknown image type: {image_type}, using standard validation")
                return await self._validate_document_type(file_path)
                
        except Exception as e:
            print(f"❌ [DEBUG] Enhanced image validation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Enhanced image validation failed: {str(e)}",
                "document_type": "unknown"
            }

# Global agent instance
# enhanced_customer_agent = EnhancedCustomerAgent()  # Commented to prevent startup hanging

# Lazy-loaded global instance
_enhanced_customer_agent = None

def get_enhanced_customer_agent():
    """Get or create the enhanced customer agent instance"""
    global _enhanced_customer_agent
    if _enhanced_customer_agent is None:
        _enhanced_customer_agent = EnhancedCustomerAgent()
    return _enhanced_customer_agent

# For backward compatibility
def enhanced_customer_agent():
    return get_enhanced_customer_agent()

# Convenience function for API
async def process_customer_request(
    user_message: str,
    user_id: int,
    session_id: Optional[int] = None,
    uploaded_file: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Process customer request using enhanced agent"""
    
    agent = get_enhanced_customer_agent()
    return await agent.process_request(
        user_message=user_message,
        user_id=user_id,
        session_id=session_id,
        uploaded_file=uploaded_file
    ) 