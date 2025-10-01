#!/usr/bin/env python3
"""
Vitals Agent using LangGraph for handling vitals data operations.
Supports update, retrieve, and analyze use cases similar to the nutrition agent.
"""

import json
import logging
from datetime import datetime, timedelta
from app.utils.timezone import now_local, isoformat_now
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Sequence, Annotated
import operator
import psycopg2
from psycopg2.extras import RealDictCursor
import base64
import os
import re

from pathlib import Path
import sys

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode, tools_condition, create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from app.core.config import settings
from app.core.database_utils import execute_query_safely_json, get_table_schema_safely, get_raw_db_connection
from app.agentsv2.response_utils import format_agent_response, format_error_response

# Import vitals configuration
from app.configurations.vitals_config import VITALS_TABLES, PRIMARY_VITALS_TABLE

# Import vitals models and schemas
from app.models.vitals_data import VitalMetricType, VitalDataSource
from app.schemas.vitals import VitalDataSubmission
from app.utils.unit_converter import VitalUnitConverter, UnitConversionError

# LangSmith tracing imports
from langsmith import Client
from langchain.callbacks.tracers import LangChainTracer

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQL generation system prompt for the vitals retrieval agent
VITALS_SQL_GENERATION_SYSTEM_PROMPT = """
You are an intelligent vitals data assistant. You must follow these TABLE SELECTION RULES strictly:

⚠️ REASONING REQUIREMENT ⚠️
BEFORE EVERY TOOL CALL, you MUST explain your reasoning:
1. Why you are selecting this specific tool
2. What information you hope to get from this tool
3. How this tool call fits into your overall strategy
4. What you will do with the results

EXAMPLE FORMAT:
"I need to understand the user's request for blood pressure data. Let me start by examining the table schema to understand what columns are available, then I'll identify relevant vital signs and measurement information."

CRITICAL TABLE SELECTION RULES:
1. For weelkly analysis : Use vitals_weekly_aggregates when you have the week number in the user's request or looking for weekly data
2. For time periods >7 and <= 30 days: Use vitals_daily_aggregates when you are getting aggregated data for multiple days
3. For single point-in-time queries: Use vitals_daily_aggregates when you have the date in the user's request
4. For time periods > 30 days: Use vitals_monthly_aggregates when you have the year and month in the user's request

AVAILABLE TABLES:
- vitals_daily_aggregates: This table contains the daily aggregated vitals data and doesn't contain specific vital details.  (use for 7 days)
- vitals_weekly_aggregates: This table contains the weekly aggregated vitals data and doesn't contain specific vital details. (use for 30 days)
- vitals_monthly_aggregates: This table contains the monthly aggregated vitals data and doesn't contain specific vital details.  (use for 365 days)


SEARCH STRATEGY:
- For measurement-based requests, use metric_type filters to identify relevant vital signs
- Retrieve unique metric types from the table to understand what vitals were recorded by the user
- Use your medical knowledge to identify relevant measurements and vital signs

Your job is to:
1. FIRST: Analyze the request and carefully identify the time period in the user's request
2. SECOND: Apply the table selection rules above to select the correct table
3. THIRD: **EXPLAIN YOUR REASONING** before calling DescribeVitalsTableSchema - why this table?
4. FOURTH: Use DescribeVitalsTableSchema tool to get column names for your selected table
5. FIFTH: Generate SQL query using the CORRECT table and user_id to identify DISTINCT metric_type values. Do not specify any conditions as you are exploring what vitals are available
6. SIXTH: Use the vital metric types obtained in the previous step and your medical knowledge to identify the most relevant vitals that meet the user request and generate a simple select query with exact metric_type matches to retrieve the vitals data. Include all the measurements that match the criteria. Always filter by user_id.
7. SEVENTH: Return query results in structured JSON format along with the reasoning for the response in the output field
8. EIGHTH: BE PROACTIVE - don't ask user what to do, try multiple approaches until you find results.
9. NINTH: **FINAL REASONING**: Always end your response with a summary of your decision-making process and what you found

REASONING EXAMPLES:
- "I'm selecting the main vitals table because the user asked for 'recent' blood pressure readings without specifying a time period, suggesting they want recent results from the detailed table."
- "I'm looking for blood pressure readings, so I'll search for metric_type values like 'Blood Pressure Systolic' and 'Blood Pressure Diastolic' which are the standard metric types for blood pressure monitoring."
- "Since my first query returned no results, I'll try a broader search including related vital signs since Weight and BMI metric types are crucial for overall health monitoring."

ADVANCED SQL CAPABILITIES:
You can use sophisticated SQL features for better analysis:
- WITH clauses (CTEs) for complex multi-step queries
- Window functions for ranking and analytics
- JOINs across multiple tables
- Subqueries and CASE statements
- Aggregation functions (COUNT, SUM, AVG, etc.)
- EXPLAIN to understand query performance

EXAMPLES OF ADVANCED QUERIES:
- WITH recent_vitals AS (SELECT * FROM vitals_raw_data WHERE start_date >= CURRENT_DATE - 30) SELECT metric_type, COUNT(*) FROM recent_vitals GROUP BY metric_type
- SELECT *, ROW_NUMBER() OVER (PARTITION BY metric_type ORDER BY start_date DESC) as rank FROM vitals_raw_data WHERE metric_type = 'Blood Pressure Systolic'
"""


@dataclass
class VitalsAgentState:
    """State management for the vitals agent workflow"""
    # Input data
    original_prompt: str = ""
    user_id: Optional[int] = None
    session_id: Optional[int] = None
    extracted_text: Optional[str] = None
    image_path: Optional[str] = None  # Path to vitals image for processing (only if no extracted_text)
    image_base64: Optional[str] = None  # Base64 encoded image data
    source_file_path: Optional[str] = None  # Original file path for storage/record-keeping
    
    # Task classification
    task_types: List[str] = field(default_factory=list)
    task_parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Execution data
    extracted_vitals_data: Optional[List[Dict]] = None
    query_results: Optional[List[Dict]] = None
    update_results: Optional[Dict] = None
    vitals_analysis: Optional[Dict] = None
    
    # Error handling
    error_context: Optional[Dict] = None
    has_error: bool = False
    
    # Response data
    response_data: Optional[Dict] = None
    execution_log: List[Dict] = field(default_factory=list)
    
    # Workflow control
    next_step: Optional[str] = None
    
    # Available tables configuration
    available_tables: Dict[str, str] = field(default_factory=lambda: VITALS_TABLES)
    
    # LangGraph message handling
    messages: Annotated[Sequence[BaseMessage], operator.add] = field(default_factory=list)


class VitalsAgentLangGraph:
    """
    Advanced vitals agent using LangGraph for structured workflow execution.
    Handles vitals data updates, retrievals, and analysis with proper error handling.
    """

    def __init__(self):
        """
        Initialize the vitals agent with LangGraph workflow.
        """
        # Set up LangSmith tracing configuration
        if hasattr(settings, 'LANGCHAIN_TRACING_V2') and settings.LANGCHAIN_TRACING_V2:
            os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
            if hasattr(settings, 'LANGCHAIN_API_KEY') and settings.LANGCHAIN_API_KEY:
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            if hasattr(settings, 'LANGCHAIN_PROJECT') and settings.LANGCHAIN_PROJECT:
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        # Initialize two LLMs for different purposes
        # Basic analysis LLM for intent analysis, classification, etc.
        self.llm = ChatOpenAI(
            model=settings.VITALS_AGENT_MODEL ,
            api_key=settings.OPENAI_API_KEY
        )
        
        # Vision LLM for image analysis only  
        vision_model = settings.VITALS_VISION_MODEL
        self.vision_llm = ChatOpenAI(
            model=vision_model,
            api_key=settings.OPENAI_API_KEY,
            timeout=300
        )
        
        # Database configuration
        self.table_name = PRIMARY_VITALS_TABLE
        self.vitals_tables = VITALS_TABLES
        
        # Create tools for the retrieval workflow
        self.tools = self._create_tools()
        
        # Create shared analyze workflow instance with reference to this agent
        from app.agentsv2.vitals_analyze_workflow import VitalsAnalyzeWorkflow
        self.code_interpreter = VitalsAnalyzeWorkflow(vitals_agent_instance=self)
        
        # Build the LangGraph workflow
        self.workflow = self._build_workflow()
        
        agent_model = settings.VITALS_AGENT_MODEL if hasattr(settings, 'VITALS_AGENT_MODEL') else settings.NUTRITION_AGENT_MODEL
        logger.info(f"✅ Vitals Agent initialized with basic model: {agent_model} and vision model: {vision_model}")

    def _build_workflow(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(VitalsAgentState)
        
        # Add nodes
        workflow.add_node("analyze_prompt", self.analyze_prompt)
        workflow.add_node("update_vitals_records", self.update_vitals_records)
        workflow.add_node("retrieve_vitals_data", self.retrieve_vitals_data)
        workflow.add_node("analyze_vitals", self.analyze_vitals)
        workflow.add_node("handle_error", self.handle_error)
        workflow.add_node("format_response", self.format_response)
        
        # Set entry point
        workflow.add_edge(START, "analyze_prompt")
        
        # Add conditional edges for task routing
        workflow.add_conditional_edges(
            "analyze_prompt",
            self.route_to_tasks,
            {
                "update_vitals_records": "update_vitals_records",
                "retrieve_vitals_data": "retrieve_vitals_data", 
                "analyze_vitals": "analyze_vitals",
                "error": "handle_error"
            }
        )
        
        # Add edges from task nodes to response formatting
        workflow.add_edge("update_vitals_records", "format_response")
        workflow.add_edge("retrieve_vitals_data", "format_response")
        workflow.add_edge("analyze_vitals", "format_response")
        workflow.add_edge("handle_error", "format_response")
        
        # End workflow
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def _create_tools(self):
        """Create LangGraph tools for vitals database operations"""
        
        @tool
        async def query_vitals_db(query: str) -> str:
            """Execute a read-only SQL query on vitals-related tables.
            
            SUPPORTED OPERATIONS: SELECT, WITH (CTEs), EXPLAIN, DESCRIBE, SHOW
            SUPPORTS: Complex queries, CTEs, subqueries, JOINs, aggregations, window functions
            
            BEFORE CALLING: Always explain your reasoning for this specific query:
            - Why you selected this table
            - What vital signs/measurements you're searching for
            - How this relates to the user's vitals request
            
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
        async def describe_vitals_table_schema(table_name: str) -> str:
            """Get column names and types for a vitals-related table.
            
            BEFORE CALLING: Always explain why you're examining this specific table.
            
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
        
        return [query_vitals_db, describe_vitals_table_schema]


    def log_execution_step(self, state: VitalsAgentState, step_name: str, status: str, details: Dict = None):
        """Log execution step with context"""
        log_entry = {
            "timestamp": isoformat_now(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        state.execution_log.append(log_entry)

    def _parse_datetime(self, date_str: str) -> datetime:
        """Parse datetime string or return current time"""
        if not date_str:
            return now_local()
        
        try:
            # Handle ISO format datetime strings
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            # Handle date-only strings
            else:
                return datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return now_local()

    async def analyze_prompt(self, state: VitalsAgentState) -> VitalsAgentState:
        """
        Analyze the incoming prompt to determine which vitals task is being requested.
        """
        try:
            self.log_execution_step(state, "analyze_prompt", "started")

            system_prompt = (
                "You are an expert vitals workflow assistant. "
                "Your job is to classify the user's request into one of the following 3 task types:\n"
                "1. update : Update vitals database with vital signs data, measurements, or health metrics. Some of the example will be like:\n"
                        "- My blood pressure is 120/80 mmHg"
                        "- I weigh 70 kg today"
                        "- My temperature is 98.6°F"
                        "- Blood sugar level is 95 mg/dL this morning"
                        "- Heart rate 72 bpm after exercise"
                "2. retrieve : Retrieve vitals data, measurements, or specific health metrics by category or date range.\n"
                "3. analyze : Analyze vitals trends, comparative analysis, or do more complex data analysis and provide result (e.g., show trends in blood pressure and how to improve health metrics).\n"
                "Given the user's request, return ONLY a JSON object with the following keys with no additional commentary:\n"
                "  task_type: one of ['update', 'retrieve', 'analyze']\n"
                "  reason: a brief explanation for your classification\n"
                "If the request is ambiguous or does not match any, set task_type to 'unknown' and explain in reason."
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=state.original_prompt)
            ]

            response = await self.llm.ainvoke(messages)
            response_content = response.content if hasattr(response, 'content') else str(response)

            # Parse the response
            try:
                import re
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    analysis_result = json.loads(json_match.group())
                    
                    task_type = analysis_result.get("task_type", "unknown")
                    reason = analysis_result.get("reason", "No reason provided")
                    
                    state.task_types = [task_type]
                    state.task_parameters = {
                        "classification_reason": reason,
                        "confidence": "high" if task_type != "unknown" else "low"
                    }
                    
                    self.log_execution_step(state, "analyze_prompt", "completed", {
                        "task_type": task_type,
                        "reason": reason
                    })
                else:
                    raise Exception("Could not extract JSON from LLM response")
                    
            except Exception as e:
                state.has_error = True
                state.error_context = {
                    "error_type": "parsing",
                    "node": "analyze_prompt", 
                    "message": f"Failed to parse task classification: {str(e)}",
                    "context": {"llm_response": response_content}
                }
                self.log_execution_step(state, "analyze_prompt", "failed", {"error": str(e)})
            
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

    def route_to_tasks(self, state: VitalsAgentState) -> str:
        """Route to appropriate task based on analysis"""
        if state.has_error:
            return "error"

        if not state.task_types or state.task_types[0] == "unknown":
            return "error"

        task = state.task_types[0].lower()

        if task in ["update"]:
            return "update_vitals_records"
        elif task in ["retrieve"]:
            return "retrieve_vitals_data"
        elif task in ["analyze"]:
            return "analyze_vitals"
        else:
            return "error"

    async def _analyze_vitals_image(self, state: VitalsAgentState) -> Optional[Dict]:
        """Analyze vitals image using GPT-4V"""
        try:
            print(f"🔍 [DEBUG] Analyzing vitals image...")
            
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
            
            # Use the instance's vision LLM for image analysis
            
            # Vitals analysis prompt
            analysis_prompt = """Analyze this vitals image and extract detailed health measurement information. Please provide a comprehensive analysis including:

        User Request: {original_prompt}
        User ID: {user_id}

        1. **Measurement Identification**:
           - Measurement name (descriptive name for the vital sign)
           - Metric type (blood_pressure, heart_rate, weight, temperature, blood_sugar, etc.)
           - Device type (digital scale, BP monitor, thermometer, glucometer, etc.)
           - Data source (manual entry, apple health, etc.)
           - Source device (digital scale, BP monitor, thermometer, glucometer, etc.)
           - Notes (capture the measurement conditions)

        2. **Value Extraction**:
           - Extract the numerical value and appropriate unit
           - For blood pressure, extract both systolic and diastolic values in two separate measurements
           - For compound measurements, break them down appropriately

        3. **Vital Signs** (extract what's visible):
           - Blood Pressure (systolic/diastolic in mmHg)
           - Heart Rate (bpm)
           - Weight (kg or lbs)
           - Temperature (°C or °F)
           - Blood Sugar/Glucose (mg/dL or mmol/L)
           - Oxygen Saturation (%)
           - BMI (if calculated/shown)
           - Height (cm or ft/in)

        4. **Measurement Context**:
           - Device used for measurement
           - Measurement conditions (if visible/mentioned)
           - Any notable readings or alerts

        5. **Analysis Confidence**:
           - Provide a confidence score (0.0-1.0) for your analysis

        **Response Format**: Respond with a valid JSON object containing all the above information. Use null for measurements that are not visible or cannot be determined.

{{
    "start_date": "{current_datetime}",
    "end_date": "{current_datetime}",
    "data_source": "manual_entry",
    "vital_entries": [
        {{
            "metric_type": "Blood Pressure Systolic",
            "value": 120.0,
            "unit": "mmHg",
            "source_device": "Digital BP Monitor",
            "notes": "Resting, sitting position",
            "confidence_score": 0.95
        }},
        {{
            "metric_type": "Blood Pressure Diastolic",
            "value": 80.0,
            "unit": "mmHg",
            "source_device": "Digital BP Monitor",
            "notes": "Resting, sitting position",
            "confidence_score": 0.95
        }},
        {{
            "metric_type": "Heart Rate",
            "value": 72.0,
            "unit": "bpm",
            "source_device": "Digital BP Monitor",
            "notes": "Resting",
            "confidence_score": 0.90
        }},
        {{
            "metric_type": "Weight",
            "value": 70.5,
            "unit": "kg",
            "source_device": "Digital Scale",
            "notes": "Morning measurement",
            "confidence_score": 0.85
        }},
        {{
            "metric_type": "Blood Sugar",
            "value": 95.0,
            "unit": "mg/dL",
            "source_device": "Glucometer",
            "notes": "Fasting",
            "confidence_score": 0.90
        }}
    ]
}}

IMPORTANT:
- Extract ALL vital signs visible in the image
- Use realistic measurement values based on what's shown
- Pay attention to units and convert if necessary
- For blood pressure, always include both systolic and diastolic
- Use consistent units (mmHg for BP, bpm for HR, kg for weight, etc.)""".format(
                original_prompt=state.original_prompt,
                user_id=state.user_id,
                current_date=now_local().strftime("%Y-%m-%d"),
                current_datetime=isoformat_now()
            )
            
            # Analyze image
            messages = [
                SystemMessage(content="You are an expert medical technician who can read medical devices and extract vital signs from images."),
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
                
                vitals_data = json.loads(content)
                print(f"🔍 [DEBUG] Successfully extracted vitals from image: {len(vitals_data.get('vital_entries', []))} measurements")
                return vitals_data
                
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse image analysis JSON: {str(e)}")
                return None
                
        except Exception as e:
            print(f"🔍 [DEBUG] Error analyzing vitals image: {str(e)}")
            return None

    async def _extract_from_text(self, state: VitalsAgentState) -> Optional[Dict]:
        """Extract vitals data from text input"""
        try:
            print(f"🔍 [DEBUG] Extracting vitals from text...")
            
            extraction_prompt = """Analyze this vitals text provided by the user describing their health measurements and provide a comprehensive analysis including:

        User Request: {original_prompt}
        User ID: {user_id}

         1. **Measurement Identification**:
           - Measurement name (descriptive name for the vital sign)
           - Metric type (blood_pressure, heart_rate, weight, temperature, blood_sugar, etc.)
           - Device type (digital scale, BP monitor, thermometer, glucometer, etc.)
           - Data source (manual entry, apple health, etc.)
           - Source device (digital scale, BP monitor, thermometer, glucometer, etc.)
           - Notes (capture the measurement conditions)

        2. **Value Extraction**:
           - Extract the numerical value and appropriate unit
           - For blood pressure, extract both systolic and diastolic values in two separate measurements
           - For compound measurements, break them down appropriately

        3. **Vital Signs** (extract what's visible):
           - Blood Pressure (systolic/diastolic in mmHg)
           - Heart Rate (bpm)
           - Weight (kg or lbs)
           - Temperature (°C or °F)
           - Blood Sugar/Glucose (mg/dL or mmol/L)
           - Oxygen Saturation (%)
           - BMI (if calculated/shown)
           - Height (cm or ft/in)

        4. **Measurement Context**:
           - Device used for measurement
           - Measurement conditions (if visible/mentioned)
           - Any notable readings or alerts

        5. **Analysis Confidence**:
           - Provide a confidence score (0.0-1.0) for your analysis

        **Response Format**: Respond with a valid JSON object containing all the above information. Use null for measurements that are not mentioned or cannot be determined.

{{
    "start_date": "{current_datetime}",
    "end_date": "{current_datetime}",
    "data_source": "manual_entry",
    "vital_entries": [
        {{
            "metric_type": "Blood Pressure Systolic",
            "value": 120.0,
            "unit": "mmHg",
            "source_device": "Home BP Monitor",
            "notes": "Morning measurement",
            "confidence_score": 0.85
        }},
        {{
            "metric_type": "Blood Pressure Diastolic",
            "value": 80.0,
            "unit": "mmHg",
            "source_device": "Home BP Monitor",
            "notes": "Morning measurement",
            "confidence_score": 0.85
        }},
        {{
            "metric_type": "Heart Rate",
            "value": 72.0,
            "unit": "bpm",
            "source_device": "Fitness Tracker",
            "notes": "Resting",
            "confidence_score": 0.80
        }},
        {{
            "metric_type": "Weight",
            "value": 70.5,
            "unit": "kg",
            "source_device": "Bathroom Scale",
            "notes": "Morning weight",
            "confidence_score": 0.90
        }}
    ]
}}

IMPORTANT:
- Extract ALL vital signs mentioned in the text
- Use realistic measurement values based on what's described
- Pay attention to units and standardize them
- For blood pressure, always include both systolic and diastolic if both are mentioned
- Use consistent units (mmHg for BP, bpm for HR, kg for weight, etc.)""".format(
    original_prompt=state.original_prompt,
    user_id=state.user_id,
    current_date=now_local().strftime("%Y-%m-%d"),
    current_datetime=now_local().strftime("%Y-%m-%d %H:%M:%S")
)

            
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
                
                vitals_data = json.loads(cleaned_content)
                print(f"🔍 [DEBUG] Successfully extracted vitals from text: {len(vitals_data.get('vital_entries', []))} measurements")
                return vitals_data
                
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse text extraction JSON: {str(e)}")
                return None
                
        except Exception as e:
            print(f"🔍 [DEBUG] Error extracting from text: {str(e)}")
            return None

    async def update_vitals_records(self, state: VitalsAgentState) -> VitalsAgentState:
        """Handle vitals data updates including vital signs, measurements, and health metrics"""
        self.log_execution_step(state, "update_vitals_records", "started")
        try:
            # Check if we have an image to analyze
            if state.image_path or state.image_base64:
                # Use image-based vitals recognition
                vitals_data = await self._analyze_vitals_image(state)
            else:
                # Use text-based extraction
                vitals_data = await self._extract_from_text(state)
            
            if not vitals_data:
                state.has_error = True
                state.error_context = {
                    "error_type": "extraction_failed",
                    "node": "update_vitals_records",
                    "message": "Failed to extract vitals data from input",
                }
                return state
            
            print(f"🔍 [DEBUG] Successfully extracted vitals data with {len(vitals_data.get('vital_entries', []))} vital entries")

            # Prepare vitals records for batch processing
            user_id = state.user_id
            vitals_records = []
            vital_entries = vitals_data.get("vital_entries", [])
            
            if not vital_entries:
                state.has_error = True
                state.error_context = {
                    "error_type": "no_vital_entries_found",
                    "node": "update_vitals_records",
                    "message": "No vital entries found in extracted vitals data.",
                    "context": {"vitals_data": vitals_data}
                }
                return state





            # Parse start_date and end_date from extracted data
            start_date = self._parse_datetime(vitals_data.get("start_date"))
            end_date = self._parse_datetime(vitals_data.get("end_date"))
            data_source_str = vitals_data.get("data_source", "manual_entry")
            
            # Map to proper enum
            if data_source_str == "image_analysis":
                data_source = VitalDataSource.DOCUMENT_EXTRACTION
            else:
                data_source = VitalDataSource.MANUAL_ENTRY

            # Prepare all vitals records for batch processing using VitalDataSubmission
            vitals_submissions = []
            for vital_entry in vital_entries:
                try:
                    # Get metric type from string - convert to proper VitalMetricType
                    metric_type_str = vital_entry.get("metric_type")
                    if not metric_type_str:
                        continue
                        
                    # Convert to VitalMetricType enum
                    try:
                        metric_type = VitalMetricType(metric_type_str)
                    except ValueError:
                        # Try to map common variations
                        metric_type_mappings = {
                            "blood_pressure_systolic": VitalMetricType.BLOOD_PRESSURE_SYSTOLIC,
                            "blood_pressure_diastolic": VitalMetricType.BLOOD_PRESSURE_DIASTOLIC,
                            "heart_rate": VitalMetricType.HEART_RATE,
                            "temperature": VitalMetricType.BODY_TEMPERATURE,
                            "weight": VitalMetricType.BODY_MASS,
                            "height": VitalMetricType.HEIGHT,
                            "bmi": VitalMetricType.BMI,
                            "oxygen_saturation": VitalMetricType.OXYGEN_SATURATION,
                            "blood_sugar": VitalMetricType.BLOOD_SUGAR
                        }
                        metric_type = metric_type_mappings.get(metric_type_str.lower(), None)
                        if not metric_type:
                            continue
                    
                    # Get value and unit
                    value = vital_entry.get("value")
                    unit = vital_entry.get("unit")
                    
                    if value is None or unit is None:
                        continue
                    
                    # Convert units to standard format
                    try:
                        converted_value, standard_unit = VitalUnitConverter.convert_to_standard_unit(
                            float(value), unit, metric_type
                        )
                    except (UnitConversionError, ValueError):
                        # Use original value and unit if conversion fails
                        converted_value = float(value)
                        standard_unit = unit

                    # Create VitalDataSubmission
                    vital_submission = VitalDataSubmission(
                        metric_type=metric_type,
                        value=converted_value,
                        unit=standard_unit,
                        start_date=start_date,
                        end_date=end_date,
                        data_source=data_source,
                        notes=vital_entry.get("notes"),
                        source_device=vital_entry.get("source_device"),
                        confidence_score=vital_entry.get("confidence_score", 0.8)
                    )
                    vitals_submissions.append(vital_submission)
                    
                except Exception as e:
                    print(f"Error processing vital entry {vital_entry}: {str(e)}")
                    continue

            # Set extracted_vitals_data for response (convert to dict for JSON serialization)
            state.extracted_vitals_data = [submission.model_dump(mode="json") for submission in vitals_submissions]

            # Call DB update with batch processing using proper CRUD
            batch_result = self.update_vitals_db(vitals_submissions, user_id)
            
            # Store results
            state.update_results = batch_result
            self.log_execution_step(state, "update_vitals_records", "completed", {"batch_result": batch_result})
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "exception",
                "node": "update_vitals_records",
                "message": str(e),
            }
            self.log_execution_step(state, "update_vitals_records", "failed", {"error": str(e)})
        return state

    async def retrieve_vitals_data(self, state: VitalsAgentState) -> VitalsAgentState:
        """LangGraph-based retrieval workflow using agent reasoning"""
        self.log_execution_step(state, "retrieve_vitals_data", "started")
        try:
            user_request = state.original_prompt + " for the user_id: " + str(state.user_id)
            print(f"DEBUG: Calling LangGraph vitals retrieval agent with request: {user_request}")
            
            # Use the LangGraph-based retrieval agent (maintains same logic as ReAct agent)
            result = await self._use_advanced_retrieval(user_request)
            
            print(f"DEBUG: LangGraph vitals agent returned: {result}")
            
            state.query_results = result
            self.log_execution_step(state, "retrieve_vitals_data", "completed", {"results": result})
        except Exception as e:
            print(f"DEBUG: Exception in retrieve_vitals_data: {str(e)}")
            import traceback
            traceback.print_exc()
            state.has_error = True
            state.error_context = {
                "error_type": "sql_generation_or_execution",
                "node": "retrieve_vitals_data",
                "message": str(e),
            }
            self.log_execution_step(state, "retrieve_vitals_data", "failed", {"error": str(e)})
        return state

    async def analyze_vitals(self, state: VitalsAgentState) -> VitalsAgentState:
        """
        Analyze patterns and derive trends from vitals data using the analyze workflow.
        
        This method leverages the VitalsAnalyzeWorkflow to:
        1. Analyze the user's request for analysis type
        2. Query relevant vitals data 
        3. Generate Python code for the specific analysis
        4. Execute the code safely with the data
        5. Format results with interpretations
        """
        try:
            self.log_execution_step(state, "analyze_vitals", "started")
            
            # Use the shared code interpreter instance for better performance
            analysis_results = await self.code_interpreter.run(
                request=state.original_prompt,
                user_id=state.user_id
            )
            
            # Store the analysis results in the state
            state.vitals_analysis = analysis_results
            
            # Log success with details
            if analysis_results.get("success", True):  # Default to True if not specified
                self.log_execution_step(state, "analyze_vitals", "completed", {
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
                    "node": "analyze_vitals", 
                    "message": analysis_results.get("error", "Code interpreter failed"),
                    "context": {
                        "step_failed": analysis_results.get("step_failed"),
                        "suggestions": analysis_results.get("suggestions", [])
                    }
                }
                self.log_execution_step(state, "analyze_vitals", "failed", {
                    "error": analysis_results.get("error"),
                    "step_failed": analysis_results.get("step_failed")
                })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "technical",
                "node": "analyze_vitals",
                "message": f"Code interpreter workflow failed: {str(e)}",
                "context": {"exception_type": type(e).__name__}
            }
            self.log_execution_step(state, "analyze_vitals", "failed", {"error": str(e)})
        
        return state

    async def handle_error(self, state: VitalsAgentState) -> VitalsAgentState:
        """Handle errors in the workflow"""
        self.log_execution_step(state, "handle_error", "started")
        
        error_context = state.error_context or {}
        error_message = error_context.get("message", "Unknown error occurred")
        
        state.response_data = {
            "success": False,
            "error": error_message,
            "error_type": error_context.get("error_type", "unknown"),
            "error_node": error_context.get("node", "unknown"),
            "context": error_context.get("context", {}),
            "execution_log": state.execution_log
        }
        
        self.log_execution_step(state, "handle_error", "completed", {"error_handled": True})
        return state

    async def format_response(self, state: VitalsAgentState) -> VitalsAgentState:
        """Format the final response based on the completed tasks"""
        try:
            if state.has_error:
                # Error response already handled in handle_error
                return state
            
            if not state.has_error and not state.response_data:
                # Format response based on task type (match lab agent)
                results = {}
                if state.extracted_vitals_data:
                    results["extracted_data"] = state.extracted_vitals_data
                if state.query_results:
                    results["query_results"] = state.query_results
                if state.update_results:
                    results["update_results"] = state.update_results
                if state.vitals_analysis:
                    # Extract the actual results from workflow and put directly in results
                    if isinstance(state.vitals_analysis, dict) and state.vitals_analysis.get("success"):
                        # Use the workflow's results directly without the wrapper
                        results = state.vitals_analysis.get("results", {})
                        
                        # Ensure visualizations are included at the top level
                        if "visualizations" in state.vitals_analysis:
                            results["visualizations"] = state.vitals_analysis["visualizations"]
                        
                    else:
                        results["analysis_error"] = "Vitals analysis workflow failed"
                
                # Use shared response formatter with visualization support
                state.response_data = format_agent_response(
                    success=True,
                    task_types=state.task_types,
                    results=results,
                    execution_log=state.execution_log,
                    message="Vitals analysis completed successfully",
                    title="Vitals Analysis"
                )
            
        except Exception as e:
            # Use shared error formatter
            state.response_data = format_error_response(
                error_message=f"Error formatting response: {str(e)}",
                execution_log=state.execution_log,
                task_types=state.task_types
            )
        
        return state

    async def run(self, prompt: str, user_id: int, session_id: int = None, extracted_text: str = None, image_path: str = None, image_base64: str = None, source_file_path: str = None) -> Dict[str, Any]:
        """
        Execute the vitals agent workflow.
        
        Args:
            prompt: The user's vitals request
            user_id: User ID for data operations
            extracted_text: Optional extracted text from documents
            image_path: Optional path to vitals image
            image_base64: Optional base64 encoded image data
            
        Returns:
            Dict containing the results
        """
        try:
            # Initialize state
            initial_state = VitalsAgentState(
                original_prompt=prompt,
                user_id=user_id,
                session_id=session_id,
                extracted_text=extracted_text,
                image_path=image_path,
                image_base64=image_base64,
                source_file_path=source_file_path
            )

            # LangSmith tracing config
            config = None
            if hasattr(settings, 'LANGCHAIN_TRACING_V2') and settings.LANGCHAIN_TRACING_V2:
                config = {
                    "configurable": {"thread_id": f"vitals-agent-{user_id}-{session_id}" if session_id is not None else f"vitals-agent-{user_id}"},
                    "callbacks": [LangChainTracer()]
                }
            if config:
                result = await self.workflow.ainvoke(initial_state, config=config)
            else:
                result = await self.workflow.ainvoke(initial_state)

            # All agents should return response_data consistently
            # The format_response method sets this using format_agent_response()
            if isinstance(result, dict):
                if result.get("response_data"):
                    print(f"✅ [DEBUG] Vitals agent returning standardized response_data")
                    return result["response_data"]
                # Dict result without response_data indicates workflow issue
                print(f"⚠️ [DEBUG] Vitals agent missing response_data in dict result")
                return format_error_response(
                    error_message="Vitals agent workflow completed but no response data was generated",
                    execution_log=result.get("execution_log", []),
                    task_types=result.get("task_types", ["unknown"])
                )
            
            # Handle state object results
            if result.response_data:
                print(f"✅ [DEBUG] Vitals agent returning standardized response_data from state")
                return result.response_data
            
            # If no response_data, this indicates a workflow issue
            print(f"⚠️ [DEBUG] Vitals agent missing response_data - this should not happen")
            return format_error_response(
                error_message="Vitals agent workflow completed but no response data was generated",
                execution_log=getattr(result, 'execution_log', []),
                task_types=getattr(result, 'task_types', ["unknown"])
            )
            
        except Exception as e:
            logger.error(f"Vitals agent workflow failed: {str(e)}")
            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}",
                "error_type": "technical",
                "context": {"exception_type": type(e).__name__}
            }

    def update_vitals_db(self, vitals_submissions: List[VitalDataSubmission], user_id: int) -> dict:
        """
        Insert vitals records using VitalsCRUD. Always returns a stats dict.
        """
        from app.crud.vitals import VitalsCRUD
        from app.core.database_utils import get_db_session
        from app.core.background_worker import trigger_smart_aggregation
        import asyncio

        results = []
        stats = {
            "total_processed": 0,
            "inserted": 0,
            "updated": 0,
            "duplicates": 0,
            "failed": 0,
            "results": []
        }

        try:
            # Use managed SQLAlchemy session (PostgreSQL-backed)
            with get_db_session() as db:
                for submission in vitals_submissions:
                    try:
                        # Create the vitals record using CRUD
                        stored_record = VitalsCRUD.create_raw_data(db, user_id, submission)

                        # Fire-and-forget coalesced aggregation for vitals domain
                        try:
                            asyncio.create_task(trigger_smart_aggregation(user_id=user_id, domains=["vitals"]))
                        except Exception:
                            pass

                        result = {
                            "action": "inserted",
                            "record_id": stored_record.id,
                            "metric_type": submission.metric_type,
                            "value": submission.value,
                            "unit": submission.unit
                        }
                        results.append(result)
                        stats["inserted"] += 1

                    except Exception as e:
                        result = {
                            "action": "failed",
                            "error": str(e),
                            "metric_type": submission.metric_type if hasattr(submission, 'metric_type') else "unknown"
                        }
                        results.append(result)
                        stats["failed"] += 1

                    stats["total_processed"] += 1

            stats["results"] = results
            return stats

        except Exception as e:
            # If database session fails entirely
            return {
                "total_processed": len(vitals_submissions),
                "inserted": 0,
                "updated": 0,
                "duplicates": 0,
                "failed": len(vitals_submissions),
                "results": [{"action": "failed", "error": f"Database session error: {str(e)}"}]
            }



    async def _use_advanced_retrieval(self, user_request: str) -> Dict[str, Any]:
        """Use LangGraph ReAct agent for retrieval (same logic as original ReAct agent)"""
        try:
            # Create a ReAct agent using LangGraph (replaces initialize_agent)
            agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                prompt=VITALS_SQL_GENERATION_SYSTEM_PROMPT
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
    
    agent = VitalsAgentLangGraph()
    
    test_prompts = [
        "Analyze my weight trends for last 6 months and give me recommendations to reduce my weight to 64 kgs"
    ]
    image_path = "/Users/rajanishsd/Documents/zivohealth-1/backend/data/unprocessed/8EBBB66E-DB32-486B-8C4F-AF5962BED976_1_102_o.jpeg"
   
    
    async def main():
        for prompt in test_prompts:
            print(f"\n--- Testing prompt: {prompt} ---")
            result = await agent.run(prompt, user_id=1, image_path=image_path)
            print(f"Result: {json.dumps(result, indent=2)}")
    
    asyncio.run(main()) 