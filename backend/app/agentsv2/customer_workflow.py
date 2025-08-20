import sys

from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.ERROR)

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio
import threading
import uuid
import re

from contextvars import ContextVar
from app.core.config import settings

# LangSmith tracing imports

from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager


from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from app.agentsv2.response_utils import format_agent_response, format_error_response

# Context variables for passing state to tools  
current_session_id: ContextVar[Optional[int]] = ContextVar('current_session_id', default=None)
current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)

# Global state for managing user responses
user_response_events: Dict[str, asyncio.Event] = {}
user_responses: Dict[str, str] = {}
_lock = threading.Lock()

def get_or_create_event_loop():
    """Get the current event loop or create a new one"""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def extract_chat_title_and_content(response_content: str) -> tuple[Optional[str], str, Optional[str], Optional[List[dict]]]:
    """
    Extract the chat title, content, reasoning, and visualizations from the LLM JSON response.
    Expected format: {"title": "Brief title", "reasoning": "Tool selection reasoning", "content": "Response content", "visualizations": [...]}
    
    Args:
        response_content (str): The full LLM response content
        
    Returns:
        tuple[Optional[str], str, Optional[str], Optional[List[dict]]]: The extracted title, content, reasoning, and visualizations, or (None, original_content, None, None) if parsing fails
    """
    try:
        # Try to parse as JSON
        response_json = json.loads(response_content.strip())
        
        if isinstance(response_json, dict):
            title = response_json.get("title")
            content = response_json.get("content", response_content)
            reasoning = response_json.get("reasoning")
            visualizations = response_json.get("visualizations")
            
            # Clean up title if it exists
            if title:
                title = str(title).strip()
                # Remove any surrounding brackets or quotes
                title = re.sub(r'^[\[\(\"\']*|[\]\)\"\']*$', '', title).strip()
                title = title if title else None
            
            # Clean up reasoning if it exists
            if reasoning:
                reasoning = str(reasoning).strip()
                reasoning = reasoning if reasoning else None
            
            # Process visualizations if they exist
            processed_visualizations = None
            if visualizations and isinstance(visualizations, list):
                processed_visualizations = []
                for viz in visualizations:
                    if isinstance(viz, dict):
                        # Ensure all required fields are present
                        filename = viz.get("filename", "")
                        viz_data = {
                            "id": f"viz_{uuid.uuid4().hex[:8]}",
                            "type": "chart",
                            "title": viz.get("title", "Visualization"),
                            "description": viz.get("description", "Generated visualization"),
                            "filename": filename,
                            "file_path": viz.get("path", ""),
                            "relative_url": f"/files/plots/{filename}" if filename else "",
                            "key_findings": viz.get("key_findings", "")
                        }
                        processed_visualizations.append(viz_data)
                        print(f"🔍 [DEBUG] Extracted visualization from response: {viz_data['title']} -> {viz_data['relative_url']}")
                
                if processed_visualizations:
                    print(f"🔍 [DEBUG] Total visualizations extracted from response: {len(processed_visualizations)}")
            
            # Ensure content is always a string
            if isinstance(content, dict):
                # Convert dictionary to a formatted string
                try:
                    content = json.dumps(content, indent=2)
                except Exception as e:
                    print(f"Warning: Could not serialize content dictionary to JSON: {e}")
                    content = str(content)
            elif content is not None:
                content = str(content)
            else:
                content = response_content
            
            return title, content, reasoning, processed_visualizations
            
    except json.JSONDecodeError as e:
        print(f"Warning: Response is not valid JSON, using fallback extraction: {str(e)}")
        # Fallback to original regex-based extraction for backward compatibility
        title_match = re.search(r'^TITLE:\s*(.+?)(?:\n|$)', response_content, re.MULTILINE | re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'^[\[\(\"\']*|[\]\)\"\']*$', '', title).strip()
            # Remove the title line from content
            content = re.sub(r'^TITLE:\s*.+?(?:\n|$)', '', response_content, flags=re.MULTILINE | re.IGNORECASE).strip()
            return title if title else None, content, None, None
            
    except Exception as e:
        print(f"Error extracting chat title and content: {str(e)}")
    
    # Return original content if all parsing fails
    return None, response_content, None, None

# Import available workflows (agents will be called via their workflow functions)
# from app.agentsv2.document_workflow import process_file_async
# Note: Other agents will be imported dynamically as needed to avoid circular imports

# Database imports for chat message storage
from app.db.session import SessionLocal
from app import crud
from app.schemas.chat_session import ChatMessageCreate
import re
import json


class IntentClassification(BaseModel):
    """Result of user intent classification"""
    intent_type: str = Field(description="Primary intent category (upload_document, update_data, query_data, analysis_request, symptom_diagnosis)")
    sub_category: Optional[str] = Field(default=None, description="Specific sub-category (vitals, nutrition, lab_report, prescription, etc.)")
    confidence: float = Field(description="Confidence score for the classification (0.0 to 1.0)")
    requires_document: bool = Field(description="Whether this intent requires document processing")
    target_agents: List[str] = Field(description="List of agents that may be needed for this intent")
    description: str = Field(description="Brief description of what the user wants to accomplish")


class ExecutionPlan(BaseModel):
    """Execution plan for fulfilling user intent"""
    steps: List[Dict[str, Any]] = Field(description="Ordered list of execution steps")
    estimated_duration: str = Field(description="Estimated time to complete")
    required_agents: List[str] = Field(description="Agents that will be used")
    success_criteria: str = Field(description="How to determine if execution was successful")


class CustomerState(TypedDict):
    user_input: str
    user_id: str
    extracted_text: str
    document_type: Optional[str]  # Document type from document workflow
    source_file_path: Optional[str]  # Source file path for document processing
    session_id: Optional[int]  # Add session_id to track chat session
    conversation_history: List[Dict[str, Any]]
    intent_classification: Optional[IntentClassification]
    missing_information: List[str]
    clarification_questions: List[str]
    execution_plan: Optional[ExecutionPlan]
    agent_results: Dict[str, Any]
    final_response: str
    generated_title: Optional[str]  # Add chat_title to store extracted title
    tool_reasoning: Optional[str]  # Add tool reasoning to store explanation
    error: str
    processing_complete: bool
    requires_user_input: bool
    is_diagnosis_request: bool
    uploaded_file: Optional[Dict[str, Any]]
    # Add standardized response fields like other agents
    response_data: Optional[Dict[str, Any]]  # Standardized response format
    task_types: List[str]  # Track what types of tasks were performed
    execution_log: List[Dict[str, Any]]  # Execution log for debugging



async def ask_user_question(question: str, session_id: Optional[int], user_id: str) -> str:
    """Ask a clarifying question to the user and wait for their response (with DB + WS updates)."""
    if not session_id or not user_id:
        return f"I need more context to ask this question: {question}"

    try:
        # Persist and notify via centralized chat session helper (single writer)
        try:
            from app.api.v1.endpoints.chat_sessions import ask_user_question_and_wait
            # Delegate storing the question and waiting for reply to chat sessions module
            reply = await ask_user_question_and_wait(session_id, user_id, question, timeout_sec=300.0)
            return reply
        except Exception:
            pass
    finally:
        pass

def set_user_response(response_key: str, response: str):
    """Set the user response for a pending question"""
    with _lock:
        if response_key in user_responses:
            user_responses[response_key] = response
            print(f"✅ [set_user_response] Response set for key {response_key}: {response}")
            if response_key in user_response_events:
                user_response_events[response_key].set()
                print(f"🔔 [set_user_response] Event triggered for key {response_key}")
            else:
                print(f"⚠️  [set_user_response] No event found for key {response_key}")
        else:
            print(f"❌ [set_user_response] Response key not found: {response_key}")


def get_pending_response_keys() -> List[str]:
    """Get all pending response keys"""
    with _lock:
        return list(user_response_events.keys())


async def assess_user_intent(state: CustomerState) -> CustomerState:
    """
    The objective is to understand the user's intent completeness and classify the intent.
    Actively asks clarifying questions to get complete information and returns the fully qualified request.
    """
    try:
        original_input = state["user_input"]
        enhanced_input = original_input
        
        # Create the ask_user_question tool with access to state
        @tool
        async def ask_clarifying_question(question: str) -> str:
            """Ask a clarifying question to the user and get their response.
            
            Args:
                question: The clarifying question to ask the user
                
            Returns:
                String containing the user's response
            """
            session_id = state.get("session_id")
            user_id = state.get("user_id")
            return await ask_user_question(question, session_id, user_id)
        
        # Create a ReAct agent with the tool
        
        llm = ChatOpenAI(model=settings.CUSTOMER_AGENT_MODEL, openai_api_key=settings.OPENAI_API_KEY)
        
            # Get conversation history for context
        conversation_history = state.get("conversation_history", [])
        context_info = ""
        if conversation_history:
            # Format recent conversation history (last 5 messages for context)
            recent_history = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            context_info = "\n\nCONVERSATION CONTEXT:\n"
            for msg in recent_history:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                context_info += f"- {role.upper()}: {content[:200]}{'...' if len(content) > 200 else ''}\n"
            context_info += "\nUse this context to better understand the current request.\n"
        
        # Get file information if available
        uploaded_file = state.get("uploaded_file")
        print(f"🔍 [DEBUG] assess_user_intent - uploaded_file from state: {uploaded_file}")
        file_info = ""
        if uploaded_file:
            file_info = f"""
        FILE PROVIDED:
        - File name: {uploaded_file.get('original_name', 'Unknown')}
        - File type: {uploaded_file.get('file_type', 'Unknown')}
        - File path: {uploaded_file.get('file_path', 'Unknown')}
        """
            
        # Add time context for meal-related requests
        from datetime import datetime
        current_time = datetime.now()
  
        
       
                    
        # Build the JSON template separately to avoid f-string formatting issues
        json_template = """{
            "final_user_input": "",
            "is_complete": boolean,
            "is_diagnosis_request": boolean,
            "missing_elements": ["list of missing elements if incomplete"]
        }"""
        
        assessment_prompt = f"""You are a healthcare app assistant that evaluates user request completeness.
        
        Conversation history: 
        {context_info}

        Current time: {current_time.strftime('%I:%M %p')}

        HEALTHCARE APP SCOPE:
        The app handles these specific areas with dedicated agents:
        1. VITALS: Heart rate, blood pressure, weight, temperature, oxygen saturation
        - Agents can: update database, retrieve data, analyze trends
        2. NUTRITION: Food intake, calorie tracking, meal logging, dietary analysis
        - Agents can: update database, retrieve data, analyze trends
        3. BIOMARKERS/LAB RESULTS: Blood tests, LFT, kidney function, cholesterol, etc.
        - Agents can: update database, retrieve data, analyze trends
        4. PHARMACY: Medication inventory, drug information, prescription management
        - Agents can: update database, retrieve data, analyze trends
        5. PRESCRIPTION: Prescription analysis, medication tracking, clinical notes
        - Agents can: update database, retrieve data, analyze trends
        6. CLINICAL NOTES: Medical observations, doctor notes, health records
        - Agents can: update database, retrieve data, analyze trends
        7. MEDICAL DOCTOR: Symptom analysis, diagnosis assistance, medical recommendations
        - Agents can: analyze symptoms, provide medical insights, health recommendations

        NON-HEALTH REQUESTS (NOT SUPPORTED):
        This is a healthcare app ONLY. The following types of requests are NOT supported:
        - Travel bookings, flight tickets, hotel reservations
        - Shopping, purchasing products, e-commerce transactions
        - Financial services, banking, investment advice
        - Entertainment, music, movies, gaming
        - General web search, news, weather updates
        - Transportation, ride booking, car purchases
        - Social media, messaging, communication services
        - Education, courses, tutoring (unless health-related)
        - Job search, career advice, business services
        - Real estate, property searches
        - Any other non-health related requests

        IMPORTANT: 
        DONOT ASK ANY FURTHER QUESTIONS:
        - if file is provided without any request then complete the assessment as "final_user_input": "user want to upload the file to update health records" and dont ask any further questions.
        - if user request message is there along with file then dont ask any further questions.

        CONTEXT AWARENESS:
        - Consider the conversation history provided above to understand references to previous topics
        - If the user refers to "my data", "that meal", "those results", etc., use context to understand what they mean
        - Previous context can help determine completeness - if user previously discussed specific health areas, use that info
        - Example: If user previously asked about blood pressure and now says "update my data", they likely mean blood pressure
        
        
        SPECIAL HANDLING FOR DIAGNOSIS QUESTIONS:
        - If the request is about symptoms, diagnosis, medical advice, or health concerns
        - These are considered COMPLETE by default and should proceed to medical doctor agent
        - Do NOT ask for completeness of symptoms - medical professionals will handle evaluation
        - Examples: "I have a headache", "What could cause chest pain?", "I'm feeling dizzy"

        EXAMPLES OF INCOMPLETE REQUESTS (Non-diagnosis):
        - "Get me my LFT values" → Missing: When? (latest or trends over time?)
        - "Show my nutrition data" → Missing: When? What specific nutrients?
        - "My blood pressure" → Missing: When? Just latest or trends?
        - "Analyze my health" → Missing: Which area? What time period?
        - "Upload my lab report" → Missing: File not provided
        - "Analyze this document" → Missing: File not provided

        EXAMPLES OF COMPLETE REQUESTS:
        - "Show me my latest LFT values"
        - "Get my blood pressure trends over the last 6 months"
        - "I want to log my lunch - chicken salad with rice"
        - "Analyze my cholesterol trends over the past year"
        - "I have a headache and nausea" (diagnosis - complete by default)
        - "What could cause shortness of breath?" (medical advice - complete by default)
        - "Analyze my lab report" (with relevant health-related PDF file attached)

        EXAMPLES OF NON-HEALTH REQUESTS (NOT SUPPORTED):
        - "Book me a flight to New York"
        - "Buy me a car"
        - "What's the weather today?"
        - "Play some music"
        - "Find me a restaurant"
        - "Help me with my homework"
        - "Book a taxi"

        TOOL CALLING REASONING REQUIREMENTS:
        When using ANY tool (especially ask_clarifying_question), you MUST provide clear reasoning including:
        1. WHY you are calling this specific tool
        2. WHAT information you are seeking or what problem you are solving
        3. HOW this tool call relates to the user's request assessment
        4. WHAT specific gap or issue in the request prompted this tool call
        
        Example reasoning for ask_clarifying_question:
        - "Calling ask_clarifying_question because the user mentioned 'my lab results' but didn't specify which type of lab test or time period, making the request incomplete for proper routing to the biomarkers agent"
        - "Using ask_clarifying_question to redirect user from non-health request about flight booking to valid healthcare input, as this is outside our healthcare app scope"
        - "Calling ask_clarifying_question because user wants to 'analyze document' but no file was provided, which is required for document processing workflow"

        RULES:
        1. If request is COMPLETELY UNRELATED TO HEALTH → Use ask_clarifying_question tool to correct the user and ask for valid health input
        2. If request mentions file operations but NO FILE provided → Mark as incomplete, ask for file
        3. If request is DIAGNOSIS/SYMPTOM related → Mark as COMPLETE and route to medical doctor
        4. If request is COMPLETE and within health scope → Return empty questions list
        5. If request is INCOMPLETE but health-related → Use ask_clarifying_question tool to ask EXACTLY ONE question
        6. Focus on the most critical missing piece first
        7. NEVER ask multiple questions at once - only use the ask_clarifying_question tool ONCE per assessment
        8. For meal/nutrition requests with files, use time context intelligently - don't ask unnecessary timing questions
        9. ALWAYS provide clear reasoning when making any tool call as specified in the TOOL CALLING REASONING REQUIREMENTS section above

        INVALID INPUT HANDLING:
        For non-health requests, use the ask_clarifying_question tool to correct the user:
        - Example: "I understand you're asking about booking flights, but I'm a healthcare assistant. Could you please ask me about your health data instead? For example, you can ask about your vitals, lab results, nutrition, medications, or symptoms."
        - Wait for their corrected health-related input
        - Then process their valid health request normally


        Original user input: "{original_input}"
        Current enhanced input: "{enhanced_input}"
        FILE INFORMATION: {file_info}

        OUTPUT VALUES REQUIRED:
        "final_user_input": This should be based on the user's input and the conversation history,
        - If user input is empty, then consider this as a file upload request for health record update.
        - if user input is not empty then there 2 cases
           1. use conversation history to understand the user's intent if user input is in continuation of the conversation history then use the user input along with conversation history.
           2. if user input is not in continuation of the conversation history then use the user input alone as it is.
       
        "is_complete": boolean,
        "is_diagnosis_request": boolean,
        "missing_elements": [list of missing elements if incomplete]


        After asking necessary clarifying questions ONLY IF USER REQUEST IS INCOMPLETE, analyze the final request and return a JSON object with ONLY these essential fields:
        {json_template}

        """
                    
        # Create agent for assessment
        agent = create_react_agent(
            model=llm,
            tools=[ask_clarifying_question]
        )
        
        # Create messages with system prompt
        messages = [
            SystemMessage(content=assessment_prompt),
            HumanMessage(content=enhanced_input)
        ]
        
        # Run the agent asynchronously to properly support async tools
        result = await agent.ainvoke({"messages": messages})
        
        # Extract the response
        final_message = result["messages"][-1]
        response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
        
        # Parse the final assessment
        try:
            import json
            # Extract JSON from the response if it's mixed with other text
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_content[json_start:json_end]
                assessment_result = json.loads(json_str)
                
                # Validate required fields
                required_fields = ["final_user_input", "is_complete", "is_diagnosis_request", "missing_elements"]
                if not all(field in assessment_result for field in required_fields):
                    raise ValueError(f"Missing required fields in assessment result: {assessment_result}")
                    
            else:
                raise json.JSONDecodeError("No JSON found", response_content, 0)
                
        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️  Assessment parsing failed: {str(e)}")
            print(f"Response content: {response_content[:500]}")
            
            # Intelligent fallback based on conversation context and content analysis
            is_diagnosis_related = any(keyword in enhanced_input.lower() for keyword in [
                'symptom', 'pain', 'hurt', 'sick', 'feel', 'ache', 'dizzy', 'nausea', 'fever', 'cough'
            ])
            
            has_context_reference = any(ref in enhanced_input.lower() for ref in [
                'my data', 'that', 'those', 'update', 'show me', 'get me'
            ])
            
            # Check for meal logging with file upload (should be considered complete)
            is_meal_with_file = (
                uploaded_file and
                any(meal_word in enhanced_input.lower() for meal_word in [
                    'log my lunch', 'log my breakfast', 'log my dinner', 'log my meal', 
                    'add my lunch', 'add my breakfast', 'add my dinner', 'add my meal',
                    'lunch', 'breakfast', 'dinner', 'meal', 'food', 'ate', 'eating'
                ]) and
                any(action_word in enhanced_input.lower() for action_word in [
                    'log', 'add', 'record', 'track', 'analyze', 'save'
                ])
            )
            
            # If we have conversation context and user is making a reference, try to be more complete
            is_contextually_complete = has_context_reference and len(conversation_history) > 0
            
            # Determine if request is complete
            is_complete = is_diagnosis_related or is_contextually_complete or is_meal_with_file
            
            assessment_result = {
                "final_user_input": enhanced_input,
                "is_complete": is_complete,
                "is_diagnosis_request": is_diagnosis_related,
                "missing_elements": [] if is_complete else ["time_period", "specificity"]
            }
            
        
        # Extract the final constructed user input from the assessment
        final_user_input = assessment_result.get("final_user_input", enhanced_input)
        
        # Update state with final results
        state["user_input"] = final_user_input  # Update with the complete constructed request
        state["clarification_questions"] = []  # Clear questions since we've processed them
        state["missing_information"] = assessment_result.get("missing_elements", []) if not assessment_result.get("is_complete", False) else []
        state["requires_user_input"] = False  # We've gathered the information needed
        state["is_diagnosis_request"] = assessment_result.get("is_diagnosis_request", False)  # Store diagnosis fl
        
        print(f"🎯 Final user request (transformed if needed): {final_user_input}")
        state["error"] = ""
        
    except Exception as e:
        state["error"] = f"Error in intent assessment: {str(e)}"
        state["clarification_questions"] = []
        state["missing_information"] = []
        state["requires_user_input"] = False
        state["is_diagnosis_request"] = False
        print(f"❌ Intent assessment error: {str(e)}")
    
    return state


def _get_recommended_agent_for_document_type(document_type: str) -> str:
    """Get the recommended agent tool name based on document type."""
    document_type_lower = document_type.lower()
    
    if "lab" in document_type_lower or "blood test" in document_type_lower or "pathology" in document_type_lower:
        return "lab_agent_tool"
    elif "vitals" in document_type_lower or "blood pressure" in document_type_lower or "heart rate" in document_type_lower:
        return "vitals_agent_tool"
    elif "nutrition" in document_type_lower or "food" in document_type_lower or "meal" in document_type_lower:
        return "nutrition_agent_tool"
    elif "pharmacy" in document_type_lower or "medication" in document_type_lower or "drug" in document_type_lower:
        return "pharmacy_agent_tool"
    elif "prescription" in document_type_lower or "clinical" in document_type_lower:
        return "prescription_clinical_agent_tool"
    else:
        return "prescription_clinical_agent_tool"  # Default fallback


async def execute_user_request(state: CustomerState) -> CustomerState:
    """
    Execute the user request by coordinating with appropriate agents.
    """
    
    # Extract user input and context from state
    user_input = state["user_input"]
    user_id = state["user_id"]
    session_id = state.get("session_id")
    uploaded_file = state.get("uploaded_file")
    
    # Create agent tool functions
    @tool
    async def ask_clarifying_question(question: str, reasoning: str) -> str:
        """Ask a clarifying question to the user and get their response.
        
        Args:
            question: The clarifying question to ask the user
            reasoning: Clear explanation of why this clarifying question is needed
            
        Returns:
            String containing the user's response
        """
        return await ask_user_question(question, session_id, user_id)
    
    @tool
    async def vitals_agent_tool(prompt_with_user_input: str) -> dict:
        """Handle vitals data operations (heart rate, blood pressure, weight, temperature, oxygen saturation).
        
        SUPPORTED OPERATIONS:
        1. UPDATE: "update my vitals data: [user input]" - Add new vital measurements to health records
        2. RETRIEVE: "retrieve my vitals: [user input]" - Get historical vitals data and current values
        3. ANALYZE & RECOMMENDATIONS: "analyze my vitals: [user input]" - Analyze trends, patterns, and provide health recommendations
        
        Use this tool when:
        - User wants to update vital signs measurements (blood pressure, heart rate, weight, temperature, oxygen saturation)
        - User wants to retrieve historical vitals data and view past measurements
        - User wants analysis of vitals trends, patterns, and health recommendations
        - User uploads images of medical devices (scale, BP monitor, thermometer, pulse oximeter)
        - User mentions specific vital signs like "blood pressure", "weight", "heart rate", "temperature", "SpO2"
        - User asks for health insights based on their vital signs
        
        Examples:
        - "update my vitals data: I just measured my blood pressure and it was 120/80"
        - "retrieve my vitals: show me my weight trends from last month"
        - "analyze my vitals: what does my blood pressure pattern suggest?"
        
        Args:
            prompt_with_user_input: Combined prompt that includes the operation type AND the user's actual words/input
                                   Must preserve the user's original words and context
            
        Returns:
            Dict containing vitals processing results
        """
        # Get all required values from state
        final_extracted_text = state.get("extracted_text", "")
        final_source_file_path = state.get("source_file_path", "")
        final_image_base64 = state.get("image_base64", None)
        
        # Get image path from uploaded file if available
        final_image_path = None
        uploaded_file = state.get("uploaded_file")
        if uploaded_file is not None:
            final_image_path = uploaded_file.get("file_path")
        
        from app.agentsv2.vitals_agent import VitalsAgentLangGraph
        agent = VitalsAgentLangGraph()
        return await agent.run(prompt_with_user_input, user_id, final_extracted_text, final_image_path, final_image_base64, final_source_file_path)
    
    @tool
    async def nutrition_agent_tool(prompt_with_user_input: str) -> dict:
        """Handle nutrition data operations (food intake, calorie tracking, meal logging, dietary analysis).
        
        SUPPORTED OPERATIONS:
        1. UPDATE: "update my nutrition data: [user input]" - Log meals, food intake, and nutrition information
        2. RETRIEVE: "retrieve my nutrition data: [user input]" - Get historical nutrition data, meal logs, and calorie tracking
        3. ANALYZE & RECOMMENDATIONS: "analyze my nutrition: [user input]" - Analyze dietary patterns, nutritional balance, and provide dietary recommendations. dont split the user request into multiple tool calls for analysis and recommendations
        
        Use this tool when:
        - User wants to log meals, food intake, or nutrition information
        - User wants to track calories, macronutrients, or dietary habits
        - User wants dietary analysis, nutritional insights, and personalized recommendations
        - User uploads food images, nutrition labels, or meal photos
        - User mentions food, meals, calories, nutrition, diet, eating habits, supplements
        - User asks for dietary advice or nutritional guidance
        
        
        Examples:
        - "update my nutrition data: I had a chicken salad with olive oil dressing for lunch"
        - "retrieve my nutrition data: show me my calorie intake for this week"
        - "analyze my nutrition: am I getting enough protein in my diet? and recommend me a meal plan"
        
        Args:
            prompt_with_user_input: Combined prompt that includes the operation type AND the user's actual words/input
                                   Must preserve the user's original words and context
            
        Returns:
            Dict containing nutrition processing results
        """
        # Get all required values from state
        final_extracted_text = state.get("extracted_text", "")
        final_source_file_path = state.get("source_file_path", "")
        final_image_base64 = state.get("image_base64", None)
        
        # Get image path from uploaded file if available
        final_image_path = None
        uploaded_file = state.get("uploaded_file")
        if uploaded_file is not None:
            final_image_path = uploaded_file.get("file_path")
        
        from app.agentsv2.nutrition_agent import NutritionAgentLangGraph
        agent = NutritionAgentLangGraph()
        return await agent.run(prompt_with_user_input, user_id, final_extracted_text, final_image_path, final_image_base64, final_source_file_path)
    
    @tool
    async def pharmacy_agent_tool(prompt_with_user_input: str) -> dict:
        """Handle pharmacy and medication inventory operations.
        
        SUPPORTED OPERATIONS:
        1. UPDATE: "update my pharmacy bills along with medication data: [user input]" - Add pharmacy purchases, medications, and billing information
        2. RETRIEVE: "retrieve my pharmacy bills along with medication data: [user input]" - Get medication history, pharmacy expenses, and inventory
        3. ANALYZE & RECOMMENDATIONS: "analyze my pharmacy bills data: [user input]" - Analyze spending patterns, medication usage, and provide cost-saving recommendations. dont split the user request into multiple tool calls for analysis and recommendations
        
        Use this tool when:
        - User wants to track medication inventory and pharmacy purchases
        - User wants drug information, interactions, and medication details
        - User mentions pharmacy purchases, over-the-counter medications, or prescriptions
        - User wants to track medication costs, pharmacy bills, and healthcare expenses
        - User uploads pharmacy receipts, medication packaging, or pill bottles
        - User asks for medication management advice or cost optimization
        
        Examples:
        - "update my pharmacy bills along with medication data: I bought Tylenol and vitamins from CVS for $25"
        - "retrieve my pharmacy bills along with medication data: show me my medication expenses this month"
        - "analyze my pharmacy bills data: how can I save money on my medications?"
        
        Args:
            prompt_with_user_input: Combined prompt that includes the operation type AND the user's actual words/input
                                   Must preserve the user's original words and context
            
        Returns:
            Dict containing pharmacy processing results
        """
        # Get all required values from state
        final_extracted_text = state.get("extracted_text", "")
        final_source_file_path = state.get("source_file_path", "")
        final_image_base64 = state.get("image_base64", None)
        
        # Get image path from uploaded file if available
        final_image_path = None
        uploaded_file = state.get("uploaded_file")
        if uploaded_file is not None:
            final_image_path = uploaded_file.get("file_path")
        
        from app.agentsv2.pharmacy_agent import PharmacyAgentLangGraph
        agent = PharmacyAgentLangGraph()
        return await agent.run(prompt_with_user_input, user_id, final_extracted_text, final_image_path, final_image_base64, final_source_file_path)
    
    @tool
    async def lab_agent_tool(prompt_with_user_input: str) -> dict:
        """Handle biomarkers and lab results operations (blood tests, LFT, kidney function, cholesterol).
        
        SUPPORTED OPERATIONS:
        1. UPDATE: "update my lab or biomarker data: [user input]" - Add new lab results, blood test values, and biomarker measurements
        2. RETRIEVE: "retrieve my lab or biomarker data: [user input]" - Get historical lab results, test values, and biomarker trends
        3. ANALYZE & RECOMMENDATIONS: "analyze my lab or biomarker data: [user input]" - Analyze lab trends, identify patterns, and provide health recommendations.dont split the user request into multiple tool calls for analysis and recommendations
        
        Use this tool when:
        - User uploads lab reports, blood test results, or medical test documents
        - User wants to track biomarkers, lab values, and test results over time
        - User wants analysis of lab trends, patterns, and health insights
        - User mentions specific lab tests (cholesterol, glucose, liver function, kidney function, CBC, metabolic panel)
        - User wants to understand lab report findings and their health implications
        - User asks for interpretation of blood work or biomarker results
        
        Examples:
        - "update my lab or biomarker data: My recent blood test showed cholesterol at 200 mg/dL"
        - "retrieve my lab or biomarker data: show me my glucose levels from the past 6 months"
        - "analyze my lab or biomarker data: what do my liver function tests indicate?"
        
        Args:
            prompt_with_user_input: Combined prompt that includes the operation type AND the user's actual words/input
                                   Must preserve the user's original words and context
            
        Returns:
            Dict containing lab processing results
        """
        # Get all required values from state
        final_extracted_text = state.get("extracted_text", "")
        final_source_file_path = state.get("source_file_path", "")
        final_image_base64 = state.get("image_base64", None)
        
        # Get image path from uploaded file if available
        final_image_path = None
        uploaded_file = state.get("uploaded_file")
        if uploaded_file is not None:
            final_image_path = uploaded_file.get("file_path")
        
        from app.agentsv2.lab_agent import LabAgentLangGraph
        agent = LabAgentLangGraph()
        result = await agent.run(prompt_with_user_input, user_id, final_extracted_text, final_image_path, final_image_base64, final_source_file_path)
        
        # Debug: Log what the lab agent returns to the LangChain agent
        print(f"🔍 [DEBUG] lab_agent_tool returning to LangChain agent:")
        print(f"🔍 [DEBUG] - success: {result.get('success')}")
        print(f"🔍 [DEBUG] - visualizations count: {len(result.get('visualizations', []))}")
        if result.get('visualizations'):
            for i, viz in enumerate(result['visualizations']):
                print(f"🔍 [DEBUG] - viz {i}: {viz.get('title')} -> {viz.get('filename')}")
        
        return result
    
    @tool
    async def prescription_clinical_agent_tool(prompt_with_user_input: str) -> dict:
        """Handle prescription analysis and clinical notes operations.
        
        SUPPORTED OPERATIONS:
        1. UPDATE: "update my prescription or clinical data: [user input]" - Add new prescriptions, clinical notes, and medical observations
        2. RETRIEVE: "retrieve my prescription or clinical data: [user input]" - Get prescription history, clinical notes, and medication records
        
        IMPORTANT: Do NOT use this tool for lab reports, vitals, nutrition, or pharmacy data - use the respective specialized agents instead.
        
        Use this tool when:
        - User uploads prescription documents from doctors or healthcare providers
        - User wants prescription analysis, medication tracking, and adherence monitoring
        - User wants to manage clinical notes, medical observations, and doctor's recommendations
        - User mentions prescribed medications from doctors (not over-the-counter purchases)
        - User wants to track prescription history, dosages, and medication changes
        - User needs help with prescription medication management and clinical documentation
        
        Examples:
        - "update my prescription or clinical data: My doctor prescribed Lisinopril 10mg daily for blood pressure"
        - "retrieve my prescription or clinical data: show me all my current prescriptions"
        - "update my prescription or clinical data: Doctor noted I should monitor blood sugar twice daily"
        
        Args:
            prompt_with_user_input: Combined prompt that includes the operation type AND the user's actual words/input
                                   Must preserve the user's original words and context
            
        Returns:
            Dict containing prescription/clinical processing results
        """
        # Get all required values from state
        final_extracted_text = state.get("extracted_text", "")
        final_source_file_path = state.get("source_file_path", "")
        final_image_base64 = state.get("image_base64", None)
        
        # Get image path from uploaded file if available
        final_image_path = None
        uploaded_file = state.get("uploaded_file")
        if uploaded_file is not None:
            final_image_path = uploaded_file.get("file_path")
        
        from app.agentsv2.prescription_clinical_agent import PrescriptionClinicalAgentLangGraph
        agent = PrescriptionClinicalAgentLangGraph()
        return await agent.process_request(prompt_with_user_input, user_id, session_id, final_image_path, final_image_base64, final_extracted_text, final_source_file_path)
    
    @tool
    async def medical_doctor_agent_tool(patient_case: str, budget_limit: float = None) -> dict:
        """Provide medical analysis, symptom evaluation, and health recommendations.
        
        Use this tool when:
        - User describes symptoms and wants medical analysis
        - User wants diagnosis assistance or second opinion
        - User wants health recommendations based on their data
        - User asks medical questions about conditions or treatments
        - User wants comprehensive health assessment
        - NOT for simple data updates or retrieval - use specific agents for those
        
        Args:
            patient_case: The user's medical case description or symptoms
            budget_limit: Optional budget limit for medical recommendations
            
        Returns:
            Dict containing medical analysis and recommendations
        """
        # Use the dedicated LangGraph medical doctor workflow
        from app.agentsv2.medical_doctor_workflow import process_medical_request_async
        try:
            result = await process_medical_request_async(
                user_id=user_id,
                patient_case=patient_case,
                session_id=session_id,
                conversation_history=state.get("conversation_history", []),
                budget_limit=budget_limit,
            )
            return result
        except Exception as mdw_e:
            print(f"⚠️ [medical_doctor_agent_tool] Workflow error: {mdw_e}")
            # Minimal fallback using panel directly if workflow fails
            from app.agentsv2.medical_doctor_panels import MedicalDoctorPanel
            try:
                panel = MedicalDoctorPanel(api_key=settings.OPENAI_API_KEY, budget_limit=budget_limit)
                return panel.process_patient_case(patient_case, budget_limit)
            except Exception as inner_e:
                return {"action": "error", "details": str(inner_e)}
    
    @tool
    async def document_workflow_tool(file_path: str, analysis_only: bool = False) -> dict:
        """Process uploaded documents and optionally update health records.
        
        Use this tool when:
        - User uploads a document that needs processing (PDF, image of medical document)
        - User wants to extract information from medical documents
        - If analysis_only=True: Only analyze the document, don't update health records. 
        - Use this tool to analyze the document and then use the agents to process the document.
    
        
        IMPORTANT: 
        - Always set analysis_only=True
        
        Args:
            file_path: Path to the uploaded document file
            analysis_only: If True, only analyze without updating records
            
        Returns:
            Dict containing document processing results with clear guidance for next steps
        """
        from app.agentsv2.document_workflow import process_file_async
        result = await process_file_async(user_id, file_path, analysis_only)
        
        # Extract key information from the result
        analysis_result = result.get("analysis_result", {})
        document_type = analysis_result.get("document_type", "Unknown") if isinstance(analysis_result, dict) else getattr(analysis_result, 'document_type', "Unknown")
        extracted_text = result.get("ocr_result", "")
        confidence = analysis_result.get("confidence", 0.0) if isinstance(analysis_result, dict) else getattr(analysis_result, 'confidence', 0.0)
        
        # Store extracted text in state for other tools to use
        state["extracted_text"] = extracted_text
        state["document_type"] = document_type
        state["source_file_path"] = file_path
        
        # Create enhanced result with clear next steps guidance
        enhanced_result = result.copy()
        enhanced_result["next_steps_guidance"] = {
            "document_type": document_type,
            "confidence": confidence,
            "extracted_text": extracted_text,
            "source_file_path": file_path,
            "recommended_agent": _get_recommended_agent_for_document_type(document_type),
            "agent_prompt": f"Process this {document_type} document for user {user_id}. The extracted text and file information are provided."
        }
        
        # Store agent-specific results in the state for later synthesis
        agent_results = {}
        if result.get("lab_agent_result"):
            agent_results["lab_agent"] = result.get("lab_agent_result")
        if result.get("vitals_agent_result"):
            agent_results["vitals_agent"] = result.get("vitals_agent_result")
        if result.get("nutrition_agent_result"):
            agent_results["nutrition_agent"] = result.get("nutrition_agent_result")
        if result.get("pharmacy_agent_result"):
            agent_results["pharmacy_agent"] = result.get("pharmacy_agent_result")
        if result.get("clinical_agent_result"):
            agent_results["clinical_agent"] = result.get("clinical_agent_result")
        
        # Store agent results in state for synthesis
        if agent_results:
            state["agent_results"] = agent_results
            print(f"🔍 [DEBUG] Stored agent results in state: {list(agent_results.keys())}")
        
        return enhanced_result

    # Create ReAct agent with all tools
    llm = ChatOpenAI(model=settings.CUSTOMER_AGENT_MODEL, openai_api_key=settings.OPENAI_API_KEY)
    
    # Get file information if available
    file_info = ""
    if uploaded_file:
        file_info = f"""
    UPLOADED FILE AVAILABLE:
    - File name: {uploaded_file.get('original_name', 'Unknown')}
    - File type: {uploaded_file.get('file_type', 'Unknown')}
    - File path: {uploaded_file.get('file_path', 'Unknown')}
    """

    system_prompt = f"""You are a healthcare app assistant that coordinates with specialized agents to fulfill user requests.

            HEALTHCARE APP SCOPE:
            The app handles these specific areas with dedicated agents:

            🩺 VITALS AGENT - Use for: vitals_agent_tool
            - Heart rate, blood pressure, weight, temperature, oxygen saturation
            - Vital signs from medical device images (scales, BP monitors, thermometers)
            - Vitals trend analysis and historical data
            - Keywords: "blood pressure", "weight", "heart rate", "temperature", "vitals"
            - agent has update, retrieve, and analysis capabilities. use the agent to achieve the user request.

            🍎 NUTRITION AGENT - Use for: nutrition_agent_tool  
            - Food intake logging, calorie tracking, meal planning
            - Food images and nutrition label analysis
            - Dietary recommendations and nutrition trends
            - Keywords: "food", "meal", "calories", "nutrition", "diet", "eating"
            - agent has update, retrieve, and analysis capabilities. use the agent to achieve the user request.

            💊 PHARMACY AGENT - Use for: pharmacy_agent_tool
            - Medication inventory and over-the-counter purchases
            - Pharmacy bills and medication costs
            - Drug information and interactions
            - Keywords: "pharmacy", "medication inventory", "drug costs", "OTC medications"
            - agent has update, retrieve, and analysis capabilities. use the agent to achieve the user request.

            🧪 LAB AGENT - Use for: lab_agent_tool
            - Blood tests, biomarkers, lab reports
            - LFT, kidney function, cholesterol, glucose levels
            - Lab trends and interpretation
            - Keywords: "lab results", "blood test", "cholesterol", "biomarkers"
            - agent has update, retrieve, and analysis capabilities. use the agent to achieve the user request.

            📋 PRESCRIPTION & CLINICAL AGENT - Use for: prescription_clinical_agent_tool
            - Prescription documents from doctors
            - Clinical notes and medical observations
            - Prescription history and adherence tracking
            - Keywords: "prescription", "clinical notes", "prescribed medication"
            - agent has update and retrieve. use the agent to achieve the user request.

            👨‍⚕️ MEDICAL DOCTOR AGENT - Use for: medical_doctor_agent_tool
            - Symptom analysis and medical recommendations
            - Health assessments and second opinions
            - Medical questions and condition guidance
            - Keywords: "symptoms", "diagnosis", "medical advice", "health recommendations"

            📄 DOCUMENT WORKFLOW - Use for: document_workflow_tool
            - Use analysis_only=True to just analyze the document type and content 
            - Once you understand the image then you can use the agents to process the document.
            
            TOOL SELECTION STRATEGY:
            1. **Document uploads**: ALWAYS start with document_workflow_tool(analysis_only=True) if there's an uploaded file
            2. **Read tool results carefully**: After document_workflow_tool, examine the "next_steps_guidance" in the result
            3. **Sequential workflow**: Use the "recommended_agent" from document_workflow_tool result to select the next tool
            4. **Specific data types**: Use the appropriate specialized agent (vitals, nutrition, lab, pharmacy, clinical)
            5. **Medical questions/symptoms**: Use medical_doctor_agent_tool
            6. **Missing information**: Use ask_clarifying_question for ONE piece of missing info

            SEQUENTIAL WORKFLOW FOR DOCUMENTS:
            Step 1: Call document_workflow_tool(analysis_only=True) 
            Step 2: Read the result and extract:
               - document_type (e.g., "Lab Report", "Clinical Notes", "Prescription")
               - recommended_agent (e.g., "lab_agent_tool", "prescription_clinical_agent_tool")
               - extracted_text and source_file_path
            Step 3: Call the recommended agent tool with appropriate parameters
            Step 4: The agent tools will automatically use the extracted_text and source_file_path from the previous step

            EXECUTION APPROACH:
            - Be proactive and use multiple tools if needed to fully address the request
            - Dont use the same tool multiple times for the same request like nutrition_agent_tool analyze trends supports both analysis and recommendations. so dont split the user request into multiple tool calls
            - For documents: First analyze with document_workflow_tool, then process with the appropriate specialized agent
            - If one tool doesn't fully satisfy the request, try additional relevant tools
            - Always provide a comprehensive response combining results from all tools used
            
            REASONING REQUIREMENTS:
            In your reasoning field, explain:
            - Which specific tools you selected (e.g., "vitals_agent_tool", "lab_agent_tool")
            - Why you chose these tools based on the user's request content
            - How the keywords or context in the request guided your tool selection
            - If you used multiple tools, explain the sequence and rationale
            - For document workflows: Explain how document_type guided your agent selection
            - If you read tool results to inform next steps, mention what you learned from the results
            - If you asked clarifying questions, explain why they were necessary

            RESPONSE FORMAT:
            You must respond with a valid JSON object in this exact structure:
            {{
                "title": "Brief descriptive title for the chat",
                "reasoning": "Explain which tools you selected and why you chose them for this specific request",
                "content": "DONT USE JSON WITHIN THIS BLOCK. Based on the response from the tools, you need to synthesize the response in a way that is easy to understand for the user and dont capture the plot path in the response, format the response with proper whitespace and without star symbols or hyphens or any other symbols, use numbers or dots for bullet points",
                "visualizations": [
                    {{
                        "title": "Chart Title",
                        "filename": "chart_file.png", 
                        "path": "data/plots/chart_file.png",
                        "description": "Description of what this visualization shows"
                    }}
                ]
            }}

            CRITICAL VISUALIZATION EXTRACTION:
            - If ANY tool returns visualization data, plots, charts, or downloaded files, you MUST extract this information
            - Look for "downloaded_plots", "visualizations", "plots", or "files" in tool results
            - Each visualization entry should include: title, filename, path, and description
            - If no visualizations are present, omit the "visualizations" field entirely
            - Pay special attention to lab analysis, vitals trends, nutrition charts that generate visualizations
            - Extract ALL visualization files mentioned in tool responses - don't miss any charts or plots

            TITLE GENERATION RULES:
            - For document_upload: Use "Health Record Update"
            - For data_question: Generate a specific title based on what they're asking about (e.g., "Blood Pressure Trends", "Lab Results Review", "Medication History")
            - For document_only_question: Generate a specific title based on the document topic (e.g., "Lab Report Explanation", "Document Analysis", "Test Results Review")
            - For document_upload_with_question: Generate a specific title based on the health topic (e.g., "Lab Report Comparison", "Results Analysis", "Medical Review")

            USER REQUEST: "{user_input}"
            {file_info}

            Use the appropriate tools to fulfill the user request completely, then respond with the JSON format above. If you need clarification on any aspect, ask the user first."""

    # Create agent with all tools
    tools = [
        ask_clarifying_question,
        vitals_agent_tool,
        nutrition_agent_tool,
        pharmacy_agent_tool,
        lab_agent_tool,
        prescription_clinical_agent_tool,
        medical_doctor_agent_tool,
        document_workflow_tool
    ]
    

    agent = create_react_agent(
        model=llm,
        tools=tools
    )
    
    # Create messages with system prompt
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ]
    
    # Run the agent
    try:
        result = await agent.ainvoke({"messages": messages})
        
        # Extract the response
        final_message = result["messages"][-1]
        response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
        
        # Debug: Log what the LangChain agent generated
        print(f"🔍 [DEBUG] LangChain agent response content:")
        print(f"🔍 [DEBUG] Response length: {len(response_content)}")
        if "visualizations" in response_content.lower():
            print(f"🔍 [DEBUG] Response contains 'visualizations' keyword")
        else:
            print(f"🔍 [DEBUG] Response does NOT contain 'visualizations' keyword")
        
        # Extract chat title, content, reasoning, and visualizations from the JSON response
        generated_title, cleaned_content, tool_reasoning, extracted_visualizations = extract_chat_title_and_content(response_content)
        
        # Store the response, title, and reasoning in state
        state["final_response"] = cleaned_content
        state["generated_title"] = generated_title
        state["tool_reasoning"] = tool_reasoning
        state["processing_complete"] = True
        
        # Preserve existing agent_results and add execution result
        # This ensures visualization data from individual agents is not lost
        existing_agent_results = state.get("agent_results", {})
        existing_agent_results["execution_result"] = cleaned_content
        
        # Store extracted visualizations if any
        if extracted_visualizations:
            existing_agent_results["visualizations"] = extracted_visualizations
            print(f"🔍 [DEBUG] Stored {len(extracted_visualizations)} visualizations in agent_results")
        
        state["agent_results"] = existing_agent_results
        
        print(f"🔍 [DEBUG] Final agent_results keys: {list(existing_agent_results.keys())}")
        
        print(f"✅ Successfully executed user request with response: {response_content[:200]}...")
        if generated_title:
            print(f"📝 Extracted chat title: {generated_title}")
        if tool_reasoning:
            print(f"🧠 Tool selection reasoning: {tool_reasoning[:100]}...")
        
    except Exception as e:
        state["error"] = f"Error executing user request: {str(e)}"
        state["final_response"] = f"I'm sorry, but I encountered an issue while processing your request: {str(e)}. Please try rephrasing your request or contact support if the problem persists."
        state["generated_title"] = None
        state["processing_complete"] = True
        
        print(f"❌ Error in execute_user_request: {str(e)}")
    
    return state


def synthesize_final_response(state: CustomerState) -> CustomerState:
    """
    Synthesize the final response from all agent results using standardized format.
    """
    try:
        # If we already have a final response and it's complete, format it properly
        if state.get("final_response") and state.get("processing_complete"):
            # Create standardized response format like other agents
            results = {}
            
            # Include agent results if available
            agent_results = state.get("agent_results", {})
            if agent_results:
                results["agent_results"] = agent_results
            
            # Include other relevant data - title is now handled by format_agent_response
            # if state.get("generated_title"):
            #     results["chat_title"] = state["generated_title"]
            if state.get("tool_reasoning"):
                results["tool_reasoning"] = state["tool_reasoning"]
            if state.get("intent_classification"):
                results["intent_classification"] = state["intent_classification"]
            if state.get("execution_plan"):
                results["execution_plan"] = state["execution_plan"]
            

            # Extract visualizations from agent_results for debugging
            agent_visualizations = agent_results.get('visualizations', []) if agent_results else []
            print(f"🔍 [DEBUG] Customer workflow - Visualizations: {len(agent_visualizations)} found in agent_results")
            
            # Determine task types from agent results
            task_types = list(agent_results.keys()) if agent_results else ["customer_request"]
            
            # Use standardized response formatter with consistent title field
            state["response_data"] = format_agent_response(
                success=not bool(state.get("error")),
                task_types=task_types,
                results=results,
                execution_log=state.get("execution_log", []),
                message=state["final_response"],
                title=state.get("generated_title", "Chat"),
                error=state.get("error") if state.get("error") else None
            )
            
            print(f"✅ [DEBUG] Customer workflow created standardized response_data")
            return state
        
        # Handle case where no final response was generated
        agent_results = state.get("agent_results", {})
        if not agent_results:
            error_msg = "I'm sorry, but I wasn't able to process your request successfully. Please try again or contact support if the issue persists."
            state["final_response"] = error_msg
            state["generated_title"] = "Processing Error"
            state["processing_complete"] = True
            state["response_data"] = format_error_response(
                error_message=error_msg,
                execution_log=state.get("execution_log", []),
                task_types=["customer_request"]
            )
            return state
        
        
    except Exception as e:
        print(f"❌ Error in synthesize_final_response: {str(e)}")
        error_msg = "I successfully processed your document, but encountered an issue formatting the response. The data has been saved to your health records."
        state["final_response"] = error_msg
        state["generated_title"] = "Document Processed"
        state["processing_complete"] = True
        state["response_data"] = format_error_response(
            error_message=f"Response formatting error: {str(e)}",
            execution_log=state.get("execution_log", []),
            task_types=state.get("task_types", ["customer_request"])
        )
    
    return state


def handle_error(state: CustomerState) -> CustomerState:
    """
    Handle errors gracefully with helpful user messaging.
    """
    error = state.get("error", "Unknown error occurred")
    
    state["final_response"] = f"I'm sorry, but I encountered an issue while processing your request: {error}. Please try rephrasing your request or contact support if the problem persists."
    state["processing_complete"] = True
    
    print(f"❌ Handling error: {error}")
    
    return state


def should_handle_error(state: CustomerState) -> str:
    """
    Condition function to determine if we should handle error or synthesize response.
    """
    if state.get("error"):
        return "handle_error"
    else:
        return "synthesize_response"


# Create the workflow graph
async def create_customer_workflow():
    """Create and return the customer workflow graph."""
     # Set up LangSmith tracing
    tracer = LangChainTracer()
    callback_manager = CallbackManager([tracer])
    
    # Create the workflow
    workflow = StateGraph(CustomerState)
    

    workflow.add_node("assess_user_intent", assess_user_intent)
    workflow.add_node("execute_user_request", execute_user_request)
    workflow.add_node("synthesize_response", synthesize_final_response)
    workflow.add_node("handle_error", handle_error)
    
    # Set entry point
    workflow.add_edge(START, "assess_user_intent")

    workflow.add_edge("assess_user_intent", "execute_user_request")

    # Add conditional edges from execute_user_request
    workflow.add_conditional_edges(
        "execute_user_request",
        should_handle_error,
        {
            "handle_error": "handle_error",
            "synthesize_response": "synthesize_response"
        }
    )
    
    # Add edges to END
    workflow.add_edge("synthesize_response", END)
    workflow.add_edge("handle_error", END)
    
    # Compile the workflow
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app


async def process_customer_request_async(user_id: str, user_input: str, conversation_history: List[Dict] = None, uploaded_file: Optional[Dict[str, Any]] = None, session_id: Optional[int] = None) -> dict:
    """
    Process a customer request asynchronously.
    
    Args:
        user_id (str): The user ID
        user_input (str): The user's input/request
        conversation_history (List[Dict]): Previous conversation context
        uploaded_file (Optional[Dict[str, Any]]): File information if user uploaded a file
        session_id (Optional[int]): Chat session ID for storing messages
        
    Returns:
        dict: Processing results including final response
    """
    
    # Create initial state
    print(f"🔍 [DEBUG] Customer workflow received uploaded_file: {uploaded_file}")
    initial_state = {
        "user_input": user_input,
        "user_id": user_id,
        "session_id": session_id,  # Add session_id to initial state
        "conversation_history": conversation_history or [],
        "intent_classification": None,
        "missing_information": [],
        "clarification_questions": [],
        "execution_plan": None,
        "agent_results": {},
        "final_response": "",
        "generated_title": None,
        "tool_reasoning": None,
        "error": "",
        "processing_complete": False,
        "requires_user_input": False,
        "is_diagnosis_request": False,
        "uploaded_file": uploaded_file,
        # Initialize standardized response fields
        "response_data": None,
        "task_types": [],
        "execution_log": []
    }
    
    # Set context variables for the workflow run
    current_session_id.set(session_id)
    current_user_id.set(user_id)
    
    # Create and run workflow
    app = await create_customer_workflow()
    
    result = await app.ainvoke(
        initial_state,
        config={
            "configurable": {"thread_id": f"customer-{user_id}"},
            "callbacks": [LangChainTracer()]
        }
    )
    
    # Convert any Pydantic models to dicts for JSON serialization
    intent_result = result.get("intent_classification")
    if intent_result and hasattr(intent_result, 'model_dump'):
        intent_result = intent_result.model_dump()
    
    plan_result = result.get("execution_plan")
    if plan_result and hasattr(plan_result, 'model_dump'):
        plan_result = plan_result.model_dump()
    
    # Return standardized response_data if available (like other agents)
    if result.get("response_data"):
        print(f"✅ [DEBUG] Customer workflow returning standardized response_data")
        return result["response_data"]
    
    # Fallback to legacy format for backward compatibility
    print(f"⚠️ [DEBUG] Customer workflow falling back to legacy response format")
    return {
        "user_input": result["user_input"],
        "intent_classification": intent_result,
        "execution_plan": plan_result,
        "agent_results": result.get("agent_results", {}),
        "final_response": result["final_response"],
        "chat_title": result.get("generated_title"),  # Use generated_title instead of chat_title
        "tool_reasoning": result.get("tool_reasoning"),
        "error": result["error"],
        "processing_complete": result["processing_complete"],
        "requires_user_input": result["requires_user_input"],
        "clarification_questions": result.get("clarification_questions", []),
        "is_diagnosis_request": result.get("is_diagnosis_request", False),
        "uploaded_file": result.get("uploaded_file")
    }


def process_customer_request(user_id: str, user_input: str, conversation_history: List[Dict] = None, uploaded_file: Optional[Dict[str, Any]] = None, session_id: Optional[int] = None) -> dict:
    """
    Process a customer request (sync wrapper).
    
    Args:
        user_id (str): The user ID  
        user_input (str): The user's input/request
        conversation_history (List[Dict]): Previous conversation context
        uploaded_file (Optional[Dict[str, Any]]): File information if user uploaded a file
        session_id (Optional[int]): Chat session ID for storing messages
        
    Returns:
        dict: Processing results including final response
    """
    import asyncio
    
    # Check if there's already an event loop running
    try:
        loop = asyncio.get_running_loop()
        # If we're in an async context, run in a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, process_customer_request_async(user_id, user_input, conversation_history, uploaded_file, session_id))
            return future.result()
    except RuntimeError:
        # No event loop running, use asyncio.run directly
        return asyncio.run(process_customer_request_async(user_id, user_input, conversation_history, uploaded_file, session_id))


# Test function
if __name__ == "__main__":
    # Test the JSON-based title extraction function
    print("🧪 Testing JSON Chat Title Extraction:")
    test_responses = [
        '{"title": "Blood Pressure Analysis", "reasoning": "Selected vitals_agent_tool because user mentioned blood pressure readings", "content": "I\'ve analyzed your blood pressure readings and here are the results..."}',
        '{"title": "Lab Report Review", "reasoning": "Used lab_agent_tool to process blood test results", "content": "Your recent lab results show the following patterns..."}',
        '{"title": "[Medication History]", "reasoning": "Chose pharmacy_agent_tool for medication tracking", "content": "Based on your prescription history, I can see..."}',
        'No valid JSON in this response, should return None and original content',
        '{"title": "Health Record Update", "reasoning": "Started with document_workflow_tool for file processing", "content": "I\'ve successfully processed your uploaded document..."}',
        # Test fallback to old format
        "TITLE: Legacy Format Title\n\nThis should work with fallback extraction...",
    ]
    
    for i, response in enumerate(test_responses, 1):
        title, content, reasoning, visualizations = extract_chat_title_and_content(response)
        viz_count = len(visualizations) if visualizations else 0
        print(f"   Test {i}: Title='{title}', Reasoning='{reasoning}', Content='{content[:50]}...', Visualizations={viz_count}")
    
    print("\n🧪 Testing Workflow:")
    # Test the workflow
    test_requests = [
        "I want to upload my lab report and ask a question about it",
        "Can you update my blood pressure to 120/80?",
        "Show me my nutrition data from last week",
        "I have a headache and feel tired, what could be wrong?",
        "Give me nutrition recommendations based on my recent meals"
    ]
    
    for request in test_requests:
        print(f"\n🧪 Testing: {request}")
        result = process_customer_request("test_user", request)
        print(f"   Intent: {result.get('intent_classification', {}).get('intent_type', 'unknown')}")
        print(f"   Chat Title: {result.get('chat_title', 'None')}")
        print(f"   Tool Reasoning: {result.get('tool_reasoning', 'None')}")
        print(f"   Response: {result['final_response'][:100]}...") 