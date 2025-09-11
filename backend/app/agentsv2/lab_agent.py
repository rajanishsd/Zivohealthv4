from pathlib import Path
import sys
from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
import base64

from dotenv import load_dotenv
load_dotenv()

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from langgraph.graph import  StateGraph, END, START
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.core.database_utils import execute_query_safely_json, get_table_schema_safely, get_raw_db_connection
from app.configurations.lab_config import LAB_TABLES, PRIMARY_LAB_TABLE, ALL_LAB_TABLES, AGGREGATION_TABLES
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode, tools_condition, create_react_agent
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage, HumanMessage
from typing import Annotated, Sequence
import operator
import re

from app.agentsv2.lab_analyze_workflow import LabAnalyzeWorkflow
from app.agentsv2.response_utils import format_agent_response, format_error_response
from langchain.callbacks.tracers import LangChainTracer
import os
from app.core.background_worker import trigger_smart_aggregation

load_dotenv()



@dataclass
class LabAgentState:
    """State management for the lab agent workflow"""
    # Input data
    original_prompt: str = ""
    user_id: Optional[int] = None
    extracted_text: Optional[str] = None
    image_path: Optional[str] = None  # Path to lab image for processing (only if no extracted_text)
    image_base64: Optional[str] = None  # Base64 encoded image data
    source_file_path: Optional[str] = None  # Original file path for storage/record-keeping
    
    # Task classification
    task_types: List[str] = field(default_factory=list)
    task_parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Execution data
    extracted_lab_data: Optional[List[Dict]] = None
    query_results: Optional[List[Dict]] = None
    update_results: Optional[Dict] = None
    trend_analysis: Optional[Dict] = None
    
    # Error handling
    error_context: Optional[Dict] = None
    has_error: bool = False
    
    # Response data
    response_data: Optional[Dict] = None
    execution_log: List[Dict] = field(default_factory=list)
    
    # Workflow control
    next_step: Optional[str] = None
    
    # Available tables configuration
    available_tables: Dict[str, str] = field(default_factory=lambda: LAB_TABLES)
    
    # LangGraph message handling
    messages: Annotated[Sequence[BaseMessage], operator.add] = field(default_factory=list)

# SQL generation system prompt for the retrieval agent
SQL_GENERATION_SYSTEM_PROMPT = """
You are an intelligent medical lab data assistant. You must follow these TABLE SELECTION RULES strictly:

⚠️ REASONING REQUIREMENT FOR ALL TOOL CALLS ⚠️
BEFORE EVERY TOOL CALL, you MUST include your reasoning directly within the tool calling function itself by explaining:
1. Why you are selecting this specific tool
2. What information you hope to get from this tool
3. How this tool call fits into your overall strategy
4. What you will do with the results

CRITICAL: Include this reasoning as part of your tool call arguments or as explanatory text immediately before the tool call. Never make a tool call without first explaining your reasoning.

EXAMPLE FORMAT:
"I need to understand the user's request for heart disease tests. Let me start by examining the table schema to understand what columns are available, then I'll identify relevant cardiac tests using my medical knowledge."

CRITICAL TABLE SELECTION RULES:
1. For time periods > 30 days: Use lab_reports_monthly, lab_reports_quarterly, or lab_reports_yearly
2. For time periods ≤ 30 days: Use lab_reports_daily
3. For single point-in-time queries: Use lab_reports_daily

SPECIFIC TIME PERIOD MAPPING (FOLLOW THESE EXACT RULES):
- 1-30 days: Use lab_reports_daily
- 31 days to 6 months (inclusive): Use lab_reports_monthly
- More than 6 months to 2 years: Use lab_reports_quarterly  
- More than 2 years: Use lab_reports_yearly


AVAILABLE TABLES:
- lab_reports_daily: Daily aggregated lab results (use for ≤30 days)
- lab_reports_monthly: Monthly aggregated lab results (use for 31 days to 6 months)
- lab_reports_quarterly: Quarterly aggregated lab results (use for 6 months to 2 years)
- lab_reports_yearly: Yearly aggregated lab results (use for 2+ years)
- lab_report_categorized: Raw categorized results (use ONLY when aggregate tables don't have the data)


SEARCH STRATEGY:
- For organ-based requests, use BOTH test_category AND test_name filters with OR logic
- Retrieve unique test names and categories from the daily, monthly, quarterly, and yearly tables to understand what tests are available for the user and decide to retrieve the values, instead of searching for the test names in the tables.
- Use your medical knowledge to identify relevant test names


Your job is to:
1. FIRST: Analyze the request and Carefully identify the time period in the user's request
2. SECOND: Apply the SPECIFIC TIME PERIOD MAPPING rules above to select the correct table
3. THIRD: **EXPLAIN YOUR REASONING** before calling DescribeTableSchema - why this table?
4. FOURTH: Use DescribeTableSchema tool to get column names for your selected table
5. SIXTH: Generate SQL query using the CORRECT table using the user_id and identify DISTINCT test names and categories from the table identified in the previous step. Do not specify any conditions as you are exploring what tests are available
7. SEVENTH: Use the test names and categories obtained in the previous step and your medical knowledge to identify the most relevant test names that meets the user request and generate a simple select query with like operator instead of exact match to retrieve the test results. Include all the tests that matches the test categories  Always filter by user_id.
8. EIGTH: Return query results in structured JSON format along with the reasoning for the response in the output field
9. NINTH: BE PROACTIVE - don't ask user what to do, try multiple approaches until you find results.
10. TENTH: **FINAL REASONING**: Always end your response with a summary of your decision-making process and what you found

REASONING EXAMPLES:
- "I'm selecting lab_reports_daily because the user asked for 'latest' tests without specifying a time period, suggesting they want recent results from the daily table."
- "I'm looking for cardiac tests, so I'll search for both 'Cardiac Markers' category AND specific test names like CPK, LDH, troponin, and cholesterol which are all relevant to heart health."
- "Since my first query returned no results, I'll try a broader search including the lipid profile category since cholesterol tests are crucial for heart disease assessment."

ADVANCED SQL CAPABILITIES:
You can use sophisticated SQL features for better analysis:
- WITH clauses (CTEs) for complex multi-step queries
- Window functions for ranking and analytics
- JOINs across multiple tables
- Subqueries and CASE statements
- Aggregation functions (COUNT, SUM, AVG, etc.)
- EXPLAIN to understand query performance

EXAMPLES OF ADVANCED QUERIES:
- WITH recent_tests AS (SELECT * FROM lab_reports_daily WHERE date >= CURRENT_DATE - 30) SELECT test_category, COUNT(*) FROM recent_tests GROUP BY test_category
- SELECT *, ROW_NUMBER() OVER (PARTITION BY test_name ORDER BY date DESC) as rank FROM lab_reports_daily WHERE test_category = 'Cardiac Markers'
"""

class LabAgentLangGraph:
    """LangGraph-based lab agent with multi-step workflow"""
    
    def __init__(self):
        # Set up LangSmith tracing configuration
        if hasattr(settings, 'LANGCHAIN_TRACING_V2') and settings.LANGCHAIN_TRACING_V2:
            os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
            if hasattr(settings, 'LANGCHAIN_API_KEY') and settings.LANGCHAIN_API_KEY:
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            if hasattr(settings, 'LANGCHAIN_PROJECT') and settings.LANGCHAIN_PROJECT:
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        self.llm = ChatOpenAI(model=settings.LAB_AGENT, api_key=settings.OPENAI_API_KEY)
        self.vision_llm = ChatOpenAI(
            model="gpt-4o",
            api_key=settings.OPENAI_API_KEY,
            max_tokens=4000
        )
        
       
        self.table_name = PRIMARY_LAB_TABLE
        self.available_tables = ALL_LAB_TABLES
        
        # Create tools for the retrieval workflow
        self.tools = self._create_tools()
        self.tool_node = ToolNode(self.tools)
        
        # Create shared analyze workflow instance with reference to this agent
        self.code_interpreter = LabAnalyzeWorkflow(lab_agent_instance=self)
        
        # Build the main workflow
        self.workflow = self._build_workflow()
    
    def _create_tools(self):
        """Create LangGraph tools for database operations"""
        
        @tool
        async def query_lab_db(query: str) -> str:
            """Execute a read-only SQL query on lab-related tables.
            
            SUPPORTED OPERATIONS: SELECT, WITH (CTEs), EXPLAIN, DESCRIBE, SHOW
            SUPPORTS: Complex queries, CTEs, subqueries, JOINs, aggregations, window functions
            
            ⚠️ MANDATORY REASONING REQUIREMENT ⚠️
            BEFORE CALLING this tool, you MUST include your reasoning explaining:
            1. Why you are selecting this specific tool
            2. What information you hope to get from this tool
            3. How this tool call fits into your overall strategy
            4. What you will do with the results
            5. Why you selected this table
            6. What test categories/names you're searching for
            7. How this relates to the user's medical request
            
            Args:
                query: SQL query statement to execute (read-only operations only)
                
            Returns:
                JSON string of query results
            """
            try:
                # Clean up query string
                query = query.strip()
                if query.endswith('"\n'):
                    query = query[:-2]
                elif query.endswith('"'):
                    query = query[:-1]
                elif query.endswith("'\n"):
                    query = query[:-2]
                elif query.endswith("'"):
                    query = query[:-1]
                if query.startswith('"'):
                    query = query[1:]
                elif query.startswith("'"):
                    query = query[1:]
                query = query.replace("\\'", "'").replace('\\"', '"').strip()

                # More flexible query validation - allow read-only operations
                query_lower = query.lower().strip()
                
                # Remove comments and extra whitespace for analysis
                clean_query = re.sub(r'--.*?\n', ' ', query_lower)  # Remove -- comments
                clean_query = re.sub(r'/\*.*?\*/', ' ', clean_query, flags=re.DOTALL)  # Remove /* */ comments
                clean_query = re.sub(r'\s+', ' ', clean_query).strip()  # Normalize whitespace
                
                # Allow read-only operations
                allowed_starts = ['select', 'with', 'explain', 'describe', 'show']
                
                # Block dangerous operations
                blocked_keywords = [
                    'insert', 'update', 'delete', 'drop', 'create', 'alter', 
                    'truncate', 'grant', 'revoke', 'commit', 'rollback',
                    'set', 'reset', 'copy', 'bulk', 'exec', 'execute'
                ]
                
                if not any(clean_query.startswith(start) for start in allowed_starts):
                    return f"Only read-only queries are allowed. Supported: {', '.join(allowed_starts).upper()}"
                
                # Check for blocked keywords as complete words (not parts of column names)
                for blocked in blocked_keywords:
                    # Use word boundaries to match complete keywords only
                    pattern = r'\b' + re.escape(blocked) + r'\b'
                    if re.search(pattern, clean_query):
                        return f"Query contains blocked keyword: {blocked.upper()}"

                return execute_query_safely_json(query)
            except Exception as e:
                return f"Query Error: {e}"
        
        @tool
        async def describe_table_schema(table_name: str) -> str:
            """Get column names and types for a lab-related table.
            
            ⚠️ MANDATORY REASONING REQUIREMENT ⚠️
            BEFORE CALLING this tool, you MUST include your reasoning explaining:
            1. Why you are selecting this specific tool
            2. What information you hope to get from this tool
            3. How this tool call fits into your overall strategy
            4. What you will do with the results
            5. Why you're examining this specific table
            6. How understanding this table schema helps with the user's request
            
            Args:
                table_name: Name of the table to describe
                
            Returns:
                String describing the table schema
            """
            try:
                if not table_name:
                    table_name = self.table_name
                return get_table_schema_safely(table_name)
            except Exception as e:
                return f"Schema Query Error for table '{table_name}': {e}"
        
        return [query_lab_db, describe_table_schema]
    
    def _build_workflow(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(LabAgentState)
        
        # Add nodes
        workflow.add_node("analyze_prompt", self.analyze_prompt)
        workflow.add_node("update_lab_records", self.update_lab_records)
        workflow.add_node("retrieve_lab_data", self.retrieve_lab_data)
        workflow.add_node("analyze_trends", self.analyze_trends)
        workflow.add_node("handle_error", self.handle_error)
        workflow.add_node("format_response", self.format_response)
        
        # Set entry point
        workflow.add_edge(START, "analyze_prompt")
        
        # Add conditional edges for task routing
        workflow.add_conditional_edges(
            "analyze_prompt",
            self.route_to_tasks,
            {
                "update_lab_records": "update_lab_records",
                "retrieve_lab_data": "retrieve_lab_data", 
                "analyze_trends": "analyze_trends",
                "error": "handle_error"
            }
        )
        
        # Add edges from task nodes to response formatting
        workflow.add_edge("update_lab_records", "format_response")
        workflow.add_edge("retrieve_lab_data", "format_response")
        workflow.add_edge("analyze_trends", "format_response")
        workflow.add_edge("handle_error", "format_response")
        
        # End workflow
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    
    def get_available_tables(self) -> Dict[str, str]:
        """Get dictionary of available lab tables"""
        return LAB_TABLES
    
    def log_execution_step(self, state: LabAgentState, step_name: str, status: str, details: Dict = None):
        """Log execution step with context"""
        from app.utils.timezone import isoformat_now
        log_entry = {
            "timestamp": isoformat_now(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        state.execution_log.append(log_entry)
    
    async def analyze_prompt(self, state: LabAgentState) -> LabAgentState:
        """
        Analyze the incoming prompt to determine which task(s) are being requested.
        
        Error Scenarios:
        - Ambiguous prompts that could match multiple tasks
        - Prompts that don't match any known task patterns
        - Missing required parameters (user_id, etc.)
        """
        try:
            self.log_execution_step(state, "analyze_prompt", "started")

            # Compose the system prompt for intent classification
            system_prompt = (
                "You are an expert medical lab workflow assistant. "
                "Your job is to classify the user's request into one of the following 3 task types:\n"
                "1. update : Update my lab database with test report data (from unstructured or structured text, or update specific test values).\n"
                "2. retrieve : Retrieve a category or tests by name (e.g., get all glucose results, or all tests under Liver Function).\n"
                "3. analyze: Analyze trends or do more complex data analysis and provide result (e.g., show trends in blood pressure, or compare results over time).\n"
                "Given the user's request, return ONLY a JSON object with the following keys:\n"
                "  task_type: one of ['update', 'retrieve', 'analyze']\n"
                "  reason: a brief explanation for your classification\n"
                "If the request is ambiguous or does not match any, set task_type to 'unknown' and explain in reason."
            )

            # Prepare the user prompt
            user_prompt = (
                f"User request: {state.original_prompt}\n"
                f"User ID: {state.user_id}\n"
                "Classify this request as described above."
            )

            # Use model and temperature from settings
            

            # Run the LLM to classify the intent
            response = await self.llm.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            
            try:
                result = json.loads(response.content)
                state.task_types = [result.get("task_type", "unknown")]
                state.intent_reason = result.get("reason", "")
                if state.task_types[0] == "unknown":
                    state.has_error = True
                    state.error_context = {
                        "error_type": "intent_classification",
                        "node": "analyze_prompt",
                        "message": "Could not understand user intent.",
                        "context": {"llm_reason": state.intent_reason}
                    }
            except Exception as e:
                state.has_error = True
                state.error_context = {
                    "error_type": "intent_classification",
                    "node": "analyze_prompt",
                    "message": f"Failed to parse LLM response: {str(e)}",
                    "context": {"llm_response": getattr(response, 'content', str(response))}
                }
                state.task_types = ["unknown"]
                state.intent_reason = "LLM response parsing failed."
            
            self.log_execution_step(state, "analyze_prompt", "completed", {
                "task_types": state.task_types,
                "has_error": state.has_error
            })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "technical",
                "node": "analyze_prompt",
                "message": str(e),
                "context": {"exception_type": type(e).__name__}
            }
            self.log_execution_step(state, "analyze_prompt", "failed", {"error": str(e)})
        
        return state
    
    def route_to_tasks(self, state: LabAgentState) -> str:
        """Route to appropriate task based on analysis"""
        if state.has_error:
            return "error"
        # Route to the appropriate workflow node based on detected task_types
        # The main tasks are: update_lab_records, retrieve_lab_data, analyze_trends
        # Fallback to "error" if unknown or ambiguous

        if not state.task_types or state.task_types[0] == "unknown":
            return "error"

        task = state.task_types[0].lower()

        if task in ["update"]:
            return "update_lab_records"
        elif task in ["retrieve"]:
            return "retrieve_lab_data"
        elif task in ["analyze"]:
            return "analyze_trends"
        else:
            return "error"
        
    async def _analyze_lab_image(self, state: LabAgentState) -> Optional[Dict]:
        """Analyze lab image using GPT-4V"""
        try:
            print(f"🔍 [DEBUG] Analyzing lab image...")
            
            # Get base64 image data
            if state.image_path and not state.image_base64:
                # Read and encode image from path
                with open(state.image_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
            elif state.image_base64:
                # Use provided base64 data
                image_data = state.image_base64
            else:
                return None
            
            # Lab analysis prompt - using exact same format as text extraction
            analysis_prompt = f"""Analyze this lab report image and extract detailed laboratory test information. Please provide a comprehensive analysis including:

        User Request: {state.original_prompt}
        User ID: {state.user_id}

        Guidelines:
        - identify based on the user request, if the user is asking to update any existing test or add a new test.
        - Extract ALL tests found in the document, even if not in the mappings above
        - Use the EXACT category section name as it appears in the document
        - Use the EXACT test name as it appears in the document, dont make up any test names or modify or append anything to the test names
        
        Look for:
        - Test names and their results (extract ALL tests found in the document)
        - Reference ranges or normal values
        - Test status (Normal, High, Low, Critical, Abnormal)
        - Test dates and report dates
        - Lab facility information
        - Ordering physician name
        - Test methodology if mentioned
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
        - Extract ALL lab tests visible in the image
        - Use exact test names as they appear
        - Use exact category names as they appear
        - Include all numerical values with proper units"""
            
            # Analyze image
            messages = [
                SystemMessage(content="You are an expert medical laboratory technician who can read lab reports and extract test results from images."),
                HumanMessage(content=[
                    {"type": "text", "text": analysis_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ])
            ]
            
            response = await self.vision_llm.ainvoke(messages)
            
            if not response or not response.content:
                return None
            
            # Parse response
            try:
                content = response.content.strip()
                if content.startswith('```json'):
                    content = content[7:-3].strip()
                elif content.startswith('```'):
                    content = content[3:-3].strip()
                
                lab_data = json.loads(content)
                print(f"🔍 [DEBUG] Successfully extracted lab data from image: {len(lab_data.get('tests', []))} tests")
                return lab_data
                
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse image analysis JSON: {str(e)}")
                return None
                
        except Exception as e:
            print(f"🔍 [DEBUG] Error analyzing lab image: {str(e)}")
            return None

    async def _extract_from_text(self, state: LabAgentState) -> Optional[Dict]:
        """Extract lab data from text using LLM"""
        try:
            print(f"🔍 [DEBUG] Extracting lab data from text...")
            
            extraction_prompt = f"""
                You are an intelligent lab agent that extracts laboratory test data from the following medical text.
                
                User Request: {state.original_prompt}
                User ID: {state.user_id}

                Guidelines:
                - identify based on the user request, if the user is asking to update any existing test or add a new test.
                - Extract ALL tests found in the document, even if not in the mappings above
                - Use the EXACT category section name as it appears in the document
                - Use the EXACT test name as it appears in the document, dont make up any test names or modify or append anything to the test names
                
                Look for:
                - Test names and their results (extract ALL tests found in the document)
                - Reference ranges or normal values
                - Test status (Normal, High, Low, Critical, Abnormal)
                - Test dates and report dates
                - Lab facility information
                - Ordering physician name
                - Test methodology if mentioned
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
                
           
            """

            # Combine user request with document content
            user_content_parts = [
                f"User request: {state.original_prompt}\n"
            ]
            
            if state.extracted_text:
                user_content_parts.append(f"DOCUMENT TO ANALYZE:\n---START DOCUMENT---\n{state.extracted_text}\n---END DOCUMENT---\n")
            else:
                user_content_parts.append("ERROR: No document content provided for analysis.")
            
            user_content = "\n".join(user_content_parts)
            
            response = await self.llm.ainvoke([
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": user_content}
            ])
            
            # Extract content safely
            if hasattr(response, 'content'):
                response_content = response.content
            else:
                response_content = str(response)
            
            # Check if response is empty
            if not response_content or not response_content.strip():
                return None
            
            try:
                # Clean the response content
                cleaned_content = response_content.strip()
                if cleaned_content.startswith('```json'):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()
                
                lab_data = json.loads(cleaned_content)
                print(f"🔍 [DEBUG] Successfully extracted lab data from text: {len(lab_data.get('tests', []))} tests")
                return lab_data
                
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse text extraction JSON: {str(e)}")
                return None
                
        except Exception as e:
            print(f"🔍 [DEBUG] Error extracting from text: {str(e)}")
            return None

    async def update_lab_records(self, state: LabAgentState) -> LabAgentState:
        """Handle lab data updates including test results, reports, and lab values"""
        self.log_execution_step(state, "update_lab_records", "started")
        try:
            # Check if we have an image to analyze
            if state.image_path or state.image_base64:
                # Use image-based lab extraction
                lab_data = await self._analyze_lab_image(state)
            else:
                # Use text-based extraction
                lab_data = await self._extract_from_text(state)
            
            if not lab_data:
                state.has_error = True
                state.error_context = {
                    "error_type": "extraction_failed",
                    "node": "update_lab_records",
                    "message": "Failed to extract lab data from input",
                }
                return state
            
            print(f"🔍 [DEBUG] Successfully extracted lab data with {len(lab_data.get('tests', []))} test entries")

            # Prepare test records for batch processing
            user_id = state.user_id
            test_records = []
            tests = lab_data.get("tests", [])
            
            if not tests:
                state.has_error = True
                state.error_context = {
                    "error_type": "no_tests_found",
                    "node": "update_lab_records",
                    "message": "No tests found in extracted lab data.",
                    "context": {"lab_data": lab_data}
                }
                return state

            # Prepare all test records for batch processing
            for test in tests:
                test_record = {
                    "user_id": user_id,
                    "test_name": test.get("test_name"),
                    "test_category": test.get("test_category"),
                    "test_value": test.get("test_value"),
                    "test_unit": test.get("test_unit"),
                    "reference_range": test.get("reference_range"),
                    "test_status": test.get("test_status"),
                    "test_date": lab_data.get("test_date"),
                    "report_date": lab_data.get("report_date"),
                    "lab_name": lab_data.get("lab_name"),
                    "lab_address": lab_data.get("lab_address"),
                    "ordering_physician": lab_data.get("ordering_physician"),
                    "test_notes": test.get("test_notes"),
                    "test_methodology": test.get("test_methodology"),
                }
                test_records.append(test_record)

            # Set extracted_lab_data for response
            state.extracted_lab_data = test_records

            # 3. Call DB update with batch processing (single call for all tests)
            batch_result = self.update_lab_db(test_records)

            # 4. Store results
            state.update_results = batch_result
            self.log_execution_step(state, "update_lab_records", "completed", {"batch_result": batch_result})

            # 5. Trigger smart aggregation for labs asynchronously (delayed batch processor)
            try:
                # Fire-and-forget: schedule aggregation just for labs domain
                asyncio.create_task(trigger_smart_aggregation(user_id=user_id, domains=["labs"]))
            except Exception as agg_e:
                # Non-fatal: log but do not fail the update step
                print(f"⚠️ [LabAgent] Failed to trigger smart aggregation: {agg_e}")
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "exception",
                "node": "update_lab_records",
                "message": str(e),
            }
            self.log_execution_step(state, "update_lab_records", "failed", {"error": str(e)})
        return state
    
    async def retrieve_lab_data(self, state: LabAgentState) -> LabAgentState:
        """LangGraph-based retrieval workflow using agent reasoning"""
        self.log_execution_step(state, "retrieve_lab_data", "started")
        try:
            user_request = state.original_prompt + " for the user_id: " + str(state.user_id)
            print(f"DEBUG: Calling LangGraph retrieval agent with request: {user_request}")
            
            # Use the LangGraph-based retrieval agent (maintains same logic as ReAct agent)
            result = await self._use_advanced_retrieval(user_request)
            
            print(f"DEBUG: LangGraph agent returned: {result}")
            
            state.query_results = result
            self.log_execution_step(state, "retrieve_lab_data", "completed", {"results": result})
        except Exception as e:
            print(f"DEBUG: Exception in retrieve_lab_data: {str(e)}")
            import traceback
            traceback.print_exc()
            state.has_error = True
            state.error_context = {
                "error_type": "sql_generation_or_execution",
                "node": "retrieve_lab_data",
                "message": str(e),
            }
            self.log_execution_step(state, "retrieve_lab_data", "failed", {"error": str(e)})
        return state
    

    
    async def analyze_trends(self, state: LabAgentState) -> LabAgentState:
        """
        Analyze patterns and derive trends from lab data using the analyze workflow.
        
        This method leverages the LabAnalyzeWorkflow to:
        1. Analyze the user's request for analysis type
        2. Query relevant lab data 
        3. Generate Python code for the specific analysis
        4. Execute the code safely with the data
        5. Format results with interpretations
        """
        try:
            self.log_execution_step(state, "analyze_trends", "started")
            
            # Use the shared code interpreter instance for better performance
            analysis_results = await self.code_interpreter.run(
                request=state.original_prompt,
                user_id=state.user_id
            )
            
            # Store the analysis results in the state
            state.trend_analysis = analysis_results
            
            # Log success with details
            if analysis_results.get("success", True):  # Default to True if not specified
                self.log_execution_step(state, "analyze_trends", "completed", {
                    "analysis_type": analysis_results.get("analysis_type", "unknown"),
                    "has_visualizations": bool(analysis_results.get("visualizations")),
                    "has_interpretation": bool(analysis_results.get("interpretation")),
                    "results_keys": list(analysis_results.get("results", {}).keys())
                })
            else:
                # Code interpreter failed, but we handle it gracefully
                state.has_error = True
                state.error_context = {
                    "error_type": "analysis_execution",
                    "node": "analyze_trends", 
                    "message": analysis_results.get("error", "Analyze workflow failed"),
                    "context": {
                        "step_failed": analysis_results.get("step_failed"),
                        "suggestions": analysis_results.get("suggestions", [])
                    }
                }
                self.log_execution_step(state, "analyze_trends", "failed", {
                    "error": analysis_results.get("error"),
                    "step_failed": analysis_results.get("step_failed")
                })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "technical",
                "node": "analyze_trends",
                "message": f"Code interpreter workflow failed: {str(e)}",
                "context": {"exception_type": type(e).__name__}
            }
            self.log_execution_step(state, "analyze_trends", "failed", {"error": str(e)})
        
        return state
    
    async def handle_error(self, state: LabAgentState) -> LabAgentState:
        """
        Process and format errors with context.
        
        This function:
        - Formats error messages for user consumption
        - Determines if workflow should retry, fail, or continue
        - Provides helpful suggestions for resolution
        """
        try:
            self.log_execution_step(state, "handle_error", "started")
            
            # TODO: Implement comprehensive error handling
            # - Categorize error types
            # - Format user-friendly messages
            # - Add context and suggestions
            # - Determine retry strategies
            # - Log errors for debugging
            
            if state.error_context:
                state.response_data = {
                    "success": False,
                    "error": state.error_context.get("message", "Unknown error"),
                    "error_type": state.error_context.get("error_type", "unknown"),
                    "context": state.error_context.get("context", {}),
                    "execution_log": state.execution_log
                }
            
            self.log_execution_step(state, "handle_error", "completed")
            
        except Exception as e:
            # Handle errors in error handling
            state.response_data = {
                "success": False,
                "error": f"Critical error in error handling: {str(e)}",
                "execution_log": state.execution_log
            }
            self.log_execution_step(state, "handle_error", "critical_failure", {"error": str(e)})
        
        return state
    
    async def format_response(self, state: LabAgentState) -> LabAgentState:
        """
        Format final response for user consumption.
        
        This function:
        - Formats successful results
        - Includes relevant metadata
        - Provides execution summary
        """
        try:
            self.log_execution_step(state, "format_response", "started")
            
            # TODO: Implement response formatting
            # - Format successful results based on task type
            # - Include metadata (execution time, record counts, etc.)
            # - Provide summary of actions taken
            # - Include relevant warnings or notes
            
            if not state.has_error and not state.response_data:
                # Format response based on task type
                results = {}
                
                if state.extracted_lab_data:
                    results["extracted_data"] = state.extracted_lab_data
                
                if state.query_results:
                    results["query_results"] = state.query_results
                
                if state.update_results:
                    results["update_results"] = state.update_results
                
                if state.trend_analysis:
                    # Extract the actual results from workflow and put directly in results
                    if isinstance(state.trend_analysis, dict) and state.trend_analysis.get("success"):
                        # Use the workflow's results directly without the wrapper
                        results = state.trend_analysis.get("results", {})
                        
                        # Ensure visualizations are included at the top level
                        if "visualizations" in state.trend_analysis:
                            results["visualizations"] = state.trend_analysis["visualizations"]
                        
                    else:
                        results["analysis_error"] = "Lab analysis workflow failed"
                
                # Use shared response formatter with visualization support
                state.response_data = format_agent_response(
                    success=True,
                    task_types=state.task_types,
                    results=results,
                    execution_log=state.execution_log,
                    message="Lab analysis completed successfully",
                    title="Lab Analysis"
                )
            
            self.log_execution_step(state, "format_response", "completed")
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "technical",
                "node": "format_response",
                "message": str(e),
                "context": {"exception_type": type(e).__name__}
            }
            # Use shared error formatter
            state.response_data = format_error_response(
                error_message=f"Error formatting response: {str(e)}",
                execution_log=state.execution_log,
                task_types=state.task_types
            )
            self.log_execution_step(state, "format_response", "failed", {"error": str(e)})
        
        return state
    
    async def run(self, prompt: str, user_id: int = None, session_id: int = None, extracted_text: str = None, image_path: str = None, image_base64: str = None, source_file_path: str = None) -> Dict:
        """
        Execute the lab agent workflow.
        
        Args:
            prompt: The user's request
            user_id: Optional user ID
            extracted_text: Optional extracted text from document
            image_path: Optional path to lab image for processing (only if no extracted_text)
            image_base64: Optional base64 encoded image data
            source_file_path: Original file path for storage/record-keeping
            
        Returns:
            Dict containing the workflow results
        """
        try:
            # Initialize state
            initial_state = LabAgentState(
                original_prompt=prompt,
                user_id=user_id,
                extracted_text=extracted_text,
                image_path=image_path,
                image_base64=image_base64,
                source_file_path=source_file_path
            )

            # LangSmith tracing integration
            tracer = None
            callbacks = None
            if getattr(settings, "LANGCHAIN_TRACING_V2", False):
                tracer = LangChainTracer()
                callbacks = [tracer]

            # Execute workflow with tracing if enabled
            config = None
            if callbacks:
                config = {
                    "configurable": {"thread_id": f"lab-agent-{user_id}"},
                    "callbacks": [LangChainTracer()]
                }
            if config:
                result = await self.workflow.ainvoke(initial_state, config=config)
            else:
                result = await self.workflow.ainvoke(initial_state)

            # Defensive: If result is a dict, handle it appropriately
            if isinstance(result, dict):
                # PRIORITY: Always use formatted response_data if available (from format_response method)
                if result.get("response_data"):
                    return result["response_data"]
                    
                # FALLBACK: Manual response construction only if format_response didn't run
                results_data = {}
                
                if result.get("query_results"):
                    results_data["query_results"] = result["query_results"]
                    
                if result.get("extracted_lab_data"):
                    results_data["extracted_lab_data"] = result["extracted_lab_data"]
                    
                if result.get("trend_analysis"):
                    # Extract workflow results directly without wrapper
                    trend_data = result["trend_analysis"]
                    if isinstance(trend_data, dict) and trend_data.get("success"):
                        workflow_results = trend_data.get("results", {})
                        if workflow_results:
                            results_data.update(workflow_results)
                
                # Use standard response format
                response = format_agent_response(
                    success=not result.get("has_error", False),
                    task_types=result.get("task_types", ["lab_analysis"]),
                    results=results_data,
                    execution_log=result.get("execution_log", []),
                    error=result.get("error_context", {}).get("message") if result.get("has_error") else None
                )
                return response
                
            # All agents should return response_data consistently
            # The format_response method sets this using format_agent_response()
            if result.response_data:
                print(f"✅ [DEBUG] Lab agent returning standardized response_data")
                return result.response_data
            
            # If no response_data, this indicates a workflow issue - should not happen
            print(f"⚠️ [DEBUG] Lab agent missing response_data - this should not happen")
            return format_error_response(
                error_message="Lab agent workflow completed but no response data was generated",
                execution_log=getattr(result, "execution_log", []),
                task_types=getattr(result, "task_types", ["unknown"])
            )
            
        except Exception as e:
            print(f"DEBUG: Exception in run method: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}",
                "error_type": "technical",
                "context": {"exception_type": type(e).__name__}
            }

    def update_lab_db(self, test_result) -> dict:
        """
        Insert or update one or more lab test results. Always returns a stats dict.
        """
        import json
        results = []
        stats = {
            "total_processed": 0,
            "inserted": 0,
            "updated": 0,
            "duplicates": 0,
            "failed": 0,
            "results": []
        }
        # Handle string input (JSON parsing)
        if isinstance(test_result, str):
            test_result = test_result.strip()
            if not test_result:
                return {"action": "failed", "error": "Empty string provided - no data to process"}
            if test_result.startswith('```json'):
                test_result = test_result[7:]
            if test_result.endswith('```'):
                test_result = test_result[:-3]
            test_result = test_result.strip()
            if not test_result:
                return {"action": "failed", "error": "String became empty after cleaning markdown"}
            try:
                test_result = json.loads(test_result)
            except Exception as e:
                return {"action": "failed", "error": f"Could not parse input as JSON: {e}. Input was: {repr(test_result[:200])}"}
        # Handle batch processing
        if isinstance(test_result, list):
            for tr in test_result:
                results.append(self._update_lab_db_single(tr))
        elif isinstance(test_result, dict):
            results.append(self._update_lab_db_single(test_result))
        else:
            results.append({"action": "failed", "error": f"Input must be a dict or list of dicts, got {type(test_result)}: {repr(test_result)}"})
        # Calculate batch statistics
        for r in results:
            stats["total_processed"] += 1
            if r.get("action") == "inserted":
                stats["inserted"] += 1
            elif r.get("action") == "updated":
                stats["updated"] += 1
            elif r.get("action") == "duplicate":
                stats["duplicates"] += 1
            elif r.get("action") == "failed" or r.get("action") == "error":
                stats["failed"] += 1
        stats["results"] = results
        return stats

    def _update_lab_db_single(self, test_result: dict) -> dict:
        try:
            # Convert empty strings to None for SQL compatibility
            def clean_value(value):
                return None if value == "" else value
            
            # Normalize test name for consistent matching (but keep original for display)
            def normalize_test_name(name):
                if not name:
                    return name
                # Remove extra spaces, normalize case
                return ' '.join(name.strip().split())
            
            # Clean all values in test_result
            cleaned_result = {key: clean_value(value) for key, value in test_result.items()}
            
            # Normalize test name for consistent database operations
            if 'test_name' in cleaned_result and cleaned_result['test_name']:
                original_test_name = cleaned_result['test_name']
                cleaned_result['test_name'] = normalize_test_name(cleaned_result['test_name'])
                if original_test_name != cleaned_result['test_name']:
                    print(f"🔍 [DEBUG] Normalized test name: '{original_test_name}' -> '{cleaned_result['test_name']}'")
            
            with get_raw_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if record exists (potential duplicate detection)
                    # Use LOWER() for case-insensitive comparison
                    check_query = f"""
                        SELECT id, test_value, test_unit, reference_range, test_status, test_category, 
                               report_date, ordering_physician, test_notes, test_methodology, lab_address
                        FROM {self.table_name}
                        WHERE user_id = %s AND LOWER(test_name) = LOWER(%s) AND test_date = %s
                    """
                    cursor.execute(check_query, (
                        cleaned_result['user_id'],
                        cleaned_result['test_name'],
                        cleaned_result['test_date']
                    ))
                    existing_records = cursor.fetchall()
                    
                    if existing_records:
                        # Record exists - check for actual changes needed
                        existing_record = existing_records[0]  # Get first match
                        record_id = existing_record[0]
                        
                        # Map existing values
                        existing_values = {
                            'test_value': existing_record[1],
                            'test_unit': existing_record[2], 
                            'reference_range': existing_record[3],
                            'test_status': existing_record[4],
                            'test_category': existing_record[5],
                            'report_date': existing_record[6],
                            'ordering_physician': existing_record[7],
                            'test_notes': existing_record[8],
                            'test_methodology': existing_record[9],
                            'lab_address': existing_record[10]
                        }
                        
                        # Check what fields actually need updating
                        update_fields = []
                        update_values = []
                        changes_detected = []
                        
                        updatable_fields = ['test_value']
                        
                        for field in updatable_fields:
                            if field in cleaned_result and cleaned_result[field] is not None:
                                new_value = cleaned_result[field]
                                old_value = existing_values[field]
                                
                                # Check if value is actually different
                                if str(new_value).strip() != str(old_value or '').strip():
                                    update_fields.append(f"{field} = %s")
                                    update_values.append(new_value)
                                    changes_detected.append({
                                        'field': field,
                                        'old_value': old_value,
                                        'new_value': new_value
                                    })
                        
                        if update_fields:
                            # Add updated_at timestamp using local timezone
                            tz = settings.DEFAULT_TIMEZONE
                            update_fields.append(f"updated_at = timezone('{tz}', now())")
                            
                            update_query = f"""
                                UPDATE {self.table_name}
                                    SET {', '.join(update_fields)}
                                    WHERE user_id = %s AND LOWER(test_name) = LOWER(%s) AND test_date = %s
                                """
                            
                            # Add WHERE clause values
                            update_values.extend([
                                cleaned_result['user_id'], cleaned_result['test_name'], 
                                cleaned_result['test_date']
                            ])
                            
                            cursor.execute(update_query, update_values)
                            affected_rows = cursor.rowcount
                            
                            result = {
                                "action": "updated",
                                "test_name": cleaned_result['test_name'],
                                "test_date": cleaned_result['test_date'],
                                "record_id": record_id,
                                "affected_rows": affected_rows,
                                "fields_updated": len(changes_detected),
                                "changes": changes_detected,
                                "duplicate_records_found": len(existing_records),
                                "message": f"Successfully updated {len(changes_detected)} field(s) for {cleaned_result['test_name']} on {cleaned_result['test_date']}"
                            }
                        else:
                            # No changes needed - exact duplicate
                            result = {
                                "action": "duplicate",
                                "test_name": cleaned_result['test_name'],
                                "test_date": cleaned_result['test_date'],
                                "record_id": record_id,
                                "affected_rows": 0,
                                "fields_updated": 0,
                                "changes": [],
                                "duplicate_records_found": len(existing_records),
                                "message": f"No changes needed - identical record already exists for {cleaned_result['test_name']} on {cleaned_result['test_date']}"
                            }
                    else:
                        # Insert new record
                        insert_fields = ['user_id', 'test_name', 'test_date']
                        insert_values = [cleaned_result['user_id'], cleaned_result['test_name'], 
                                       cleaned_result['test_date']]
                        insert_placeholders = ['%s', '%s', '%s']
                        
                        # Add optional fields that have values
                        optional_fields = ['test_value', 'test_unit', 'reference_range', 'test_status',
                                         'test_category', 'report_date', 'ordering_physician', 'test_notes',
                                         'test_methodology', 'lab_address', 'lab_name']
                        
                        fields_inserted = []
                        for field in optional_fields:
                            if field in cleaned_result and cleaned_result[field] is not None:
                                insert_fields.append(field)
                                insert_values.append(cleaned_result[field])
                                insert_placeholders.append('%s')
                                fields_inserted.append({
                                    'field': field,
                                    'value': cleaned_result[field]
                                })
                        
                        # Add timestamps using local timezone
                        tz = settings.DEFAULT_TIMEZONE
                        insert_fields.extend(['created_at', 'updated_at'])
                        insert_placeholders.extend([f"timezone('{tz}', now())", f"timezone('{tz}', now())"])
                        
                        insert_query = f"""
                            INSERT INTO {self.table_name} ({', '.join(insert_fields)})
                            VALUES ({', '.join(insert_placeholders)})
                            RETURNING id
                        """
                        cursor.execute(insert_query, insert_values)
                        new_record_id = cursor.fetchone()[0]
                        
                        result = {
                            "action": "inserted",
                            "test_name": cleaned_result['test_name'],
                            "test_date": cleaned_result['test_date'],
                            "record_id": new_record_id,
                            "affected_rows": 1,
                            "fields_inserted": len(fields_inserted),
                            "data": fields_inserted,
                            "duplicate_records_found": 0,
                            "message": f"Successfully inserted new record for {cleaned_result['test_name']} on {cleaned_result['test_date']} with {len(fields_inserted)} field(s)"
                        }
                    
                    conn.commit()
            # Trigger coalesced labs aggregation (fire-and-forget)
            try:
                asyncio.create_task(trigger_smart_aggregation(user_id=cleaned_result.get('user_id'), domains=["labs"]))
            except Exception:
                pass
            return result
            
        except Exception as e:
            return {
                "action": "failed", 
                "test_name": test_result.get('test_name', 'Unknown'),
                "test_date": test_result.get('test_date', 'Unknown'),
                "affected_rows": 0,
                "error": str(e),
                "message": f"Failed to process {test_result.get('test_name', 'Unknown')}: {str(e)}"
            }

    def query_lab_db(self, query: str) -> str:
        """
        Execute a SELECT query on any lab-related table and return the results as a string.
        Cleans up the query string, executes it, fetches results, and handles errors.
        """
        try:
            original_query = query
            query = query.strip()
            # Remove trailing/leading quotes and newlines
            if query.endswith('"\n'):
                query = query[:-2]
            elif query.endswith('"'):
                query = query[:-1]
            elif query.endswith("'\n"):
                query = query[:-2]
            elif query.endswith("'"):
                query = query[:-1]
            if query.startswith('"'):
                query = query[1:]
            elif query.startswith("'"):
                query = query[1:]
            query = query.replace("\\'", "'").replace('\\"', '"')
            query = query.strip()

            # Optionally, restrict to SELECT queries only
            if not query.lower().startswith('select'):
                return "Only SELECT queries are allowed."

            return execute_query_safely_json(query)
        except Exception as e:
            return f"Query Error: {e}"

    def describe_table_schema(self, table_name: str = None) -> str:
        """
        Return the schema (column names and types) for the given table name.
        If no table_name is provided, use self.table_name (the primary lab table).
        """
        try:
            if not table_name:
                table_name = self.table_name
            return get_table_schema_safely(table_name)
        except Exception as e:
            return f"Schema Query Error for table '{table_name}': {e}"

    async def _use_advanced_retrieval(self, user_request: str) -> Dict[str, Any]:
        """Use LangGraph ReAct agent for retrieval (same logic as original ReAct agent)"""
        try:
            # Create a ReAct agent using LangGraph (replaces initialize_agent)
            agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                prompt=SQL_GENERATION_SYSTEM_PROMPT
            )
            
            # Run the agent (same as original ReAct agent logic) - use ainvoke for async tools
            result = await agent.ainvoke({"messages": [HumanMessage(content=user_request)]})
            
            # Extract the final result
            final_message = result["messages"][-1]
            
            return {
                "input": user_request,
                "output": final_message.content if hasattr(final_message, 'content') else str(final_message)
            }
            
        except Exception as e:
            print(f"DEBUG: LangGraph ReAct agent failed: {str(e)}")
            return {
                "input": user_request,
                "output": f"Retrieval failed: {str(e)}"
            }

if __name__ == "__main__":
    import asyncio
    agent = LabAgentLangGraph()
    #with open("extracted_text_1.txt", "r") as file:
    #   extracted_text = file.read()
    test_prompts = [
        "update my lab data for the test name: Creatinine, test value: 1.2, test unit: mg/dL, test date: 2023-05-13 for the user "
    ]
    async def main():
        for prompt in test_prompts:
            print(f"\n--- Testing prompt: {prompt} ---")
            result = await agent.run(prompt, user_id=1)
            print(f"Result: {json.dumps(result, indent=2)}")
    asyncio.run(main()) 

# Uncomment to run tests
# asyncio.run(test_agent()) 
