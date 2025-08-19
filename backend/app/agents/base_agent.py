import uuid
import json
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.tools import Tool

from app.db.session import SessionLocal
from app.core.config import settings
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction, log_document_processing_step
from app.core.chatgpt_logger import log_chatgpt_interaction

# Shared LLM instance to avoid multiple slow initializations
_shared_llm = None

def get_shared_llm():
    """Get or create the shared ChatOpenAI instance"""
    global _shared_llm
    if _shared_llm is None:
        _shared_llm = ChatOpenAI(
            model=settings.BASE_AGENT_MODEL or settings.DEFAULT_AI_MODEL, 
            temperature=settings.BASE_AGENT_TEMPERATURE or 0.1
        )
    return _shared_llm

class AgentState(TypedDict):
    """Base state for all specialized agents"""
    # Request context
    request_id: str
    user_id: int
    session_id: Optional[int]
    agent_name: str
    
    # Input data
    ocr_text: Optional[str]
    document_type: Optional[str]
    file_path: Optional[str]  # Path to the uploaded file
    file_type: Optional[str]  # Type of the uploaded file
    extraction_request: Optional[Dict[str, Any]]
    retrieval_request: Optional[Dict[str, Any]]
    
    # Processing results
    extracted_data: Optional[Dict[str, Any]]
    stored_records: Optional[List[Dict[str, Any]]]
    retrieved_data: Optional[Dict[str, Any]]
    
    # Workflow control
    operation_type: str  # "extract", "store", "retrieve"
    processing_complete: bool
    error_message: Optional[str]
    
    # Agent communication
    response_message: Optional[Dict[str, Any]]
    
    # Processing status information (for cases where processing succeeds but no data changes)
    processing_status_message: Optional[str]  # Generic message for any processing outcome
    processing_summary: Optional[Dict[str, Any]]  # Detailed summary of processing results

class BaseHealthAgent(ABC):
    """Base class for all specialized health data agents"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.llm = get_shared_llm()  # Use shared instance
        self.memory_saver = MemorySaver()
        self.workflow = self._build_workflow()
        
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for this agent"""
        
        workflow = StateGraph(AgentState)

        # Add common nodes
        workflow.add_node("initialize_agent", self.initialize_agent)
        workflow.add_node("route_operation", self.route_operation)
        workflow.add_node("extract_data", self.extract_data)
        workflow.add_node("store_data", self.store_data)
        workflow.add_node("retrieve_data", self.retrieve_data)
        workflow.add_node("finalize_response", self.finalize_response)
        workflow.add_node("handle_error", self.handle_error)
        
        # Set entry point by adding an edge from the START node
        workflow.add_edge(START, "initialize_agent")
        
        # Add edges
        workflow.add_edge("initialize_agent", "route_operation")
        workflow.add_conditional_edges(
            "route_operation",
            self.determine_operation_path,
            {
                "extract": "extract_data",
                "store": "store_data",
                "retrieve": "retrieve_data",
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("extract_data", "finalize_response")
        workflow.add_edge("store_data", "finalize_response")
        workflow.add_edge("retrieve_data", "finalize_response")
        workflow.add_edge("finalize_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile(checkpointer=self.memory_saver)
    
    async def process_request(
        self,
        operation_type: str,
        request_data: Dict[str, Any],
        user_id: int,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Main entry point for agent processing"""
        
        request_id = str(uuid.uuid4())
        
        with trace_agent_operation(
            self.agent_name,
            f"process_{operation_type}",
            user_id=user_id,
            session_id=session_id,
            request_id=request_id
        ):
            # Initialize state
            initial_state = AgentState(
                request_id=request_id,
                user_id=user_id,
                session_id=session_id,
                agent_name=self.agent_name,
                ocr_text=request_data.get("ocr_text"),
                document_type=request_data.get("document_type"),
                file_path=request_data.get("file_path"),  # Pass file path to agent state
                file_type=request_data.get("file_type"),  # Pass file type to agent state
                extraction_request=request_data.get("extraction_request"),
                retrieval_request=request_data.get("retrieval_request"),
                extracted_data=None,
                stored_records=None,
                retrieved_data=None,
                operation_type=operation_type,
                processing_complete=False,
                error_message=None,
                response_message=None,
                processing_status_message=None,
                processing_summary=None
            )
            
            # Run the workflow
            result = await self.workflow.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": request_id}}
            )
            
            return result
    
    async def initialize_agent(self, state: AgentState) -> AgentState:
        """Initialize the agent processing"""
        
        with trace_agent_operation(
            self.agent_name,
            "initialize",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            log_agent_interaction(
                self.agent_name,
                "System",
                "agent_initialized",
                {
                    "operation_type": state["operation_type"],
                    "has_ocr_text": bool(state.get("ocr_text")),
                    "document_type": state.get("document_type"),
                    "file_path": state.get("file_path"),
                    "file_type": state.get("file_type")
                },
                user_id=state["user_id"],
                session_id=state["session_id"],
                request_id=state["request_id"]
            )
            
            return state
    
    def determine_operation_path(self, state: AgentState) -> str:
        """Determine which operation path to take"""
        
        operation = state.get("operation_type")
        if operation in ["extract", "store", "retrieve"]:
            return operation
        else:
            return "error"
    
    async def route_operation(self, state: AgentState) -> AgentState:
        """Route to the appropriate operation"""
        return state
    
    @abstractmethod
    async def extract_data(self, state: AgentState) -> AgentState:
        """Extract data from OCR text - to be implemented by each agent"""
        pass
    
    @abstractmethod
    async def store_data(self, state: AgentState) -> AgentState:
        """Store extracted data to database - to be implemented by each agent"""
        pass
    
    @abstractmethod
    async def retrieve_data(self, state: AgentState) -> AgentState:
        """Retrieve data from database - to be implemented by each agent"""
        pass
    
    @abstractmethod
    async def assess_question_relevance(self, question: str, user_id: int, session_id: int = None) -> Dict[str, Any]:
        """
        Assess if a question is relevant to this agent's domain and determine what data to retrieve.
        
        Returns:
        {
            "is_relevant": bool,
            "relevance_score": float (0.0-1.0),
            "retrieval_strategy": {
                "days_back": int,
                "limit": int,
                "specific_filters": dict,
                "priority_data": list
            },
            "reasoning": str
        }
        """
        pass
    
    async def finalize_response(self, state: AgentState) -> AgentState:
        """Finalize the agent response"""
        
        with trace_agent_operation(
            self.agent_name,
            "finalize_response",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            # Create response message
            response = {
                "agent_name": self.agent_name,
                "operation_type": state["operation_type"],
                "success": not bool(state.get("error_message")),
                "data": {}
            }
            
            if state["operation_type"] == "extract":
                response["data"] = state.get("extracted_data", {})
            elif state["operation_type"] == "store":
                response["data"] = {
                    "records_stored": len(state.get("stored_records", [])),
                    "records": state.get("stored_records", [])
                }
                
                # Preserve processing status information if present
                if state.get("processing_status_message"):
                    response["processing_status_message"] = state["processing_status_message"]
                if state.get("processing_summary"):
                    response["processing_summary"] = state["processing_summary"]
                    
            elif state["operation_type"] == "retrieve":
                response["data"] = state.get("retrieved_data", {})
            
            if state.get("error_message"):
                response["error"] = state["error_message"]
            
            state["response_message"] = response
            state["processing_complete"] = True
            
            log_agent_interaction(
                self.agent_name,
                "System",
                "response_finalized",
                response,
                user_id=state["user_id"],
                session_id=state["session_id"],
                request_id=state["request_id"]
            )
            
            return state
    
    async def handle_error(self, state: AgentState) -> AgentState:
        """Handle errors in processing"""
        
        with trace_agent_operation(
            self.agent_name,
            "handle_error",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            error_response = {
                "agent_name": self.agent_name,
                "operation_type": state["operation_type"],
                "success": False,
                "error": state.get("error_message", "Unknown error"),
                "data": {}
            }
            
            state["response_message"] = error_response
            state["processing_complete"] = True
            
            return state
    
    # Common tools that all agents can use
    def get_extraction_tool(self) -> Tool:
        """Get LLM-based extraction tool"""
        
        def extract_with_llm(text: str, extraction_prompt: str) -> Dict[str, Any]:
            """Extract data using LLM with robust JSON parsing"""
            try:
                messages = [
                    SystemMessage(content=f"You are a medical data extraction specialist for {self.agent_name}. ALWAYS return valid JSON only, no additional text. Do not wrap the JSON in markdown code blocks."),
                    HumanMessage(content=f"{extraction_prompt}\n\nText: {text}")
                ]
                
                # Log ChatGPT interaction
                messages_dict = [
                    {"role": "system", "content": f"You are a medical data extraction specialist for {self.agent_name}. ALWAYS return valid JSON only, no additional text. Do not wrap the JSON in markdown code blocks."},
                    {"role": "user", "content": f"{extraction_prompt}\n\nText: {text}"}
                ]
                
                response = self.llm.invoke(messages)
                
                # Log the interaction
                log_chatgpt_interaction(
                    agent_name=self.agent_name,
                    operation="extract_with_llm",
                    request_data=messages_dict,
                    response_data=response,
                    model_name=settings.BASE_AGENT_MODEL or settings.DEFAULT_AI_MODEL,
                    additional_metadata={"extraction_type": "generic", "text_length": len(text)}
                )
                
                # Log the raw response for debugging
                print(f"🔍 [DEBUG] LLM raw response: {response.content[:500]}...")
                
                # Try to extract JSON from the response with multiple strategies
                response_text = response.content.strip()
                
                # Strategy 1: Direct JSON parsing
                try:
                    result = json.loads(response_text)
                    print(f"✅ [DEBUG] Strategy 1 success: Direct JSON parsing")
                    return result
                except json.JSONDecodeError:
                    print(f"⚠️ [DEBUG] Strategy 1 failed: Direct JSON parsing")
                
                # Strategy 2: Remove markdown code blocks
                if response_text.startswith("```json"):
                    response_text = response_text[7:]  # Remove ```json
                if response_text.startswith("```"):
                    response_text = response_text[3:]  # Remove ```
                if response_text.endswith("```"):
                    response_text = response_text[:-3]  # Remove ```
                
                try:
                    result = json.loads(response_text.strip())
                    print(f"✅ [DEBUG] Strategy 2 success: Removed markdown blocks")
                    return result
                except json.JSONDecodeError:
                    print(f"⚠️ [DEBUG] Strategy 2 failed: Removed markdown blocks")
                
                # Strategy 3: Find JSON boundaries
                json_start = response_text.find('{')
                json_end = response_text.rfind('}')
                
                if json_start != -1 and json_end != -1 and json_end >= json_start:
                    json_text = response_text[json_start:json_end+1]
                    try:
                        result = json.loads(json_text)
                        print(f"✅ [DEBUG] Strategy 3 success: Found JSON boundaries")
                        return result
                    except json.JSONDecodeError:
                        print(f"⚠️ [DEBUG] Strategy 3 failed: Found JSON boundaries")
                
                # Strategy 4: Try to find JSON array boundaries
                array_start = response_text.find('[')
                array_end = response_text.rfind(']')
                
                if array_start != -1 and array_end != -1 and array_end >= array_start:
                    json_text = response_text[array_start:array_end+1]
                    try:
                        result = json.loads(json_text)
                        print(f"✅ [DEBUG] Strategy 4 success: Found JSON array boundaries")
                        return result
                    except json.JSONDecodeError:
                        print(f"⚠️ [DEBUG] Strategy 4 failed: Found JSON array boundaries")
                
                # Strategy 5: Clean up common issues and retry
                # Remove common prefixes/suffixes
                clean_text = response_text
                for prefix in ["Here is the JSON:", "JSON:", "Result:", "```json", "```"]:
                    if clean_text.startswith(prefix):
                        clean_text = clean_text[len(prefix):].strip()
                
                for suffix in ["```", "That's the extracted data."]:
                    if clean_text.endswith(suffix):
                        clean_text = clean_text[:-len(suffix)].strip()
                
                try:
                    result = json.loads(clean_text)
                    print(f"✅ [DEBUG] Strategy 5 success: Cleaned common issues")
                    return result
                except json.JSONDecodeError:
                    print(f"⚠️ [DEBUG] Strategy 5 failed: Cleaned common issues")
                
                # All strategies failed
                print(f"❌ [DEBUG] All JSON parsing strategies failed")
                print(f"🔍 [DEBUG] Response text (first 300 chars): {response_text[:300]}...")
                return {"error": f"Could not parse JSON from LLM response. Response: {response_text[:200]}..."}
                    
            except Exception as e:
                error_msg = f"LLM extraction failed: {str(e)}"
                print(f"❌ [DEBUG] {error_msg}")
                return {"error": error_msg}
        
        return Tool(
            name=f"{self.agent_name}_extract",
            description=f"Extract {self.agent_name} data from medical text",
            func=extract_with_llm
        )
    
    def get_database_session(self) -> Session:
        """Get database session"""
        return SessionLocal()
    
    def log_operation(self, operation: str, data: Dict[str, Any], state: AgentState):
        """Log agent operation"""
        log_document_processing_step(
            f"{self.agent_name}_{operation}",
            0,  # Document ID if available
            data,
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ) 