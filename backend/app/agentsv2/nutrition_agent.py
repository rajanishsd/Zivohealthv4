#!/usr/bin/env python3
"""
Nutrition Agent using LangGraph for handling nutrition data operations.
Supports update, retrieve, and analyze use cases similar to the lab agent.
"""

import json
import logging
from datetime import datetime, timedelta
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
from app.agentsv2.response_utils import format_agent_response, format_error_response
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from app.core.config import settings
from app.agentsv2.tools.nutrition_tools import internet_search_tool
from app.utils.timezone import now_local, isoformat_now
from app.core.background_worker import trigger_smart_aggregation

# Import nutrition configuration
from configurations.nutrition_config import NUTRITION_TABLES, PRIMARY_NUTRITION_TABLE

# LangSmith tracing imports
from langsmith import Client
from langchain.callbacks.tracers import LangChainTracer

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQL generation system prompt for the nutrition retrieval agent
NUTRITION_SQL_GENERATION_SYSTEM_PROMPT = """
You are an intelligent nutrition data assistant. You must follow these TABLE SELECTION RULES strictly:

⚠️ REASONING REQUIREMENT ⚠️
BEFORE EVERY TOOL CALL, you MUST explain your reasoning:
1. Why you are selecting this specific tool
2. What information you hope to get from this tool
3. How this tool call fits into your overall strategy
4. What you will do with the results

EXAMPLE FORMAT:
"I need to understand the user's request for protein intake data. Let me start by examining the table schema to understand what columns are available, then I'll identify relevant food entries and nutritional information."

CRITICAL TABLE SELECTION RULES:
1. For time periods > 30 days: Use nutrition_daily_summary, nutrition_monthly_summary if available
2. For time periods ≤ 30 days: Use the main nutrition table (nutrition_data or similar)
3. For single point-in-time queries: Use the main nutrition table

AVAILABLE TABLES:
- nutrition_raw_data: Raw inputs received from the user, contains the description of the food intake along with the image path and all the nutrients extracted from the image or user input description.
- nutrition_daily_aggregates: This table contains the daily aggregated nutrition data and doesn't contain the dish name or food item name.You have to query the nutrtion_raw_data table to get the dish name or food item name. (use for 7 days)
- nutrition_weekly_aggregates: This table contains the weekly aggregated nutrition data and doesn't contain the dish name or food item name. You have to query the nutrtion_raw_data table to get the dish name or food item name. (use for 30 days)
- nutrition_monthly_aggregates: This table contains the monthly aggregated nutrition data and doesn't contain the dish name or food item name. You have to query the nutrtion_raw_data table to get the dish name or food item name. (use for 365 days)


SEARCH STRATEGY:
- For nutrient-based requests, use BOTH dish_type AND food_item_name filters with OR logic
- Retrieve unique dish names and food items from the table to understand what foods were consumed by the user
- Use your nutrition knowledge to identify relevant food items and dishes

Your job is to:
1. FIRST: Analyze the request and carefully identify the time period in the user's request
2. SECOND: Apply the table selection rules above to select the correct table
3. THIRD: **EXPLAIN YOUR REASONING** before calling DescribeNutritionTableSchema - why this table?
4. FOURTH: Use DescribeNutritionTableSchema tool to get column names for your selected table
5. FIFTH: Generate SQL query using the CORRECT table and user_id to identify DISTINCT dish names and food items. Do not specify any conditions as you are exploring what foods are available. This is optional step, use this step only if user request is asking for specific food items or dish names.
6. SIXTH: Use the food items obtained in the previous step and your nutrition knowledge to identify the most relevant foods that meet the user request and generate a simple select query with LIKE operator instead of exact match to retrieve the nutrition data. Include all the foods that match the criteria. Always filter by user_id. This is optional step, use this step only if user request is asking for specific food items or dish names.
7. SEVENTH: If user request is asking for generic details then use only limited columns from the table to retrieve the data, need not extract all the columns unless asked by the user. 
8. EIGHTH: Return query results in structured JSON format along with the reasoning for the response in the output field
9. NINTH: BE PROACTIVE - don't ask user what to do, try multiple approaches until you find results.
10. TENTH: **FINAL REASONING**: Always end your response with a summary of your decision-making process and what you found

RETRIEVAL DATA IMPORTANT:
- Dont leave any data in the query results, return the complete data unless user request is asking for specific details.
- Dont use symbols like * or % or - in the query results, instead use numbers or dots for bullet points
- Based on the query, summarize the data in crisp and concise manner
- Dont add any commentary or explanation in the query results, just return the data in a structured format.
- while calculating average values skip the days where the data is not logged for the day

REASONING EXAMPLES:
- "I'm selecting the main nutrition table because the user asked for 'recent' food intake without specifying a time period, suggesting they want recent results from the detailed table."
- "I'm looking for high-protein foods, so I'll search for both specific dish types like 'chicken', 'fish' AND specific food items like 'protein', 'meat', 'eggs' which are all relevant to protein intake."
- "Since my first query returned no results, I'll try a broader search including vegetarian protein sources since beans and lentils are crucial for protein in plant-based diets."

ADVANCED SQL CAPABILITIES:
You can use sophisticated SQL features for better analysis:
- WITH clauses (CTEs) for complex multi-step queries
- Window functions for ranking and analytics
- JOINs across multiple tables
- Subqueries and CASE statements
- Aggregation functions (COUNT, SUM, AVG, etc.)
- EXPLAIN to understand query performance

EXAMPLES OF ADVANCED QUERIES:
- WITH recent_meals AS (SELECT * FROM nutrition_raw_data WHERE meal_date >= CURRENT_DATE - 30) SELECT dish_type, COUNT(*) FROM recent_meals GROUP BY dish_type
- SELECT *, ROW_NUMBER() OVER (PARTITION BY dish_name ORDER BY meal_date DESC) as rank FROM nutrition_raw_data WHERE dish_type = 'chicken'
"""


@dataclass
class NutritionAgentState:
    """State management for the nutrition agent workflow"""
    # Input data
    original_prompt: str = ""
    user_id: Optional[int] = None
    extracted_text: Optional[str] = None
    image_path: Optional[str] = None  # Path to food image for processing (only if no extracted_text)
    image_base64: Optional[str] = None  # Base64 encoded image data
    source_file_path: Optional[str] = None  # Original file path for storage/record-keeping
    
    # Task classification
    task_types: List[str] = field(default_factory=list)
    task_parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Execution data
    extracted_nutrition_data: Optional[List[Dict]] = None
    query_results: Optional[List[Dict]] = None
    update_results: Optional[Dict] = None
    nutrition_analysis: Optional[Dict] = None
    
    # Error handling
    error_context: Optional[Dict] = None
    has_error: bool = False
    
    # Response data
    response_data: Optional[Dict] = None
    execution_log: List[Dict] = field(default_factory=list)
    # Capture raw intermediate tool outputs to avoid truncation when formatting
    intermediate_outputs: Optional[Dict[str, Any]] = None
    
    # Workflow control
    next_step: Optional[str] = None
    
    # Available tables configuration
    available_tables: Dict[str, str] = field(default_factory=lambda: NUTRITION_TABLES)
    
    # LangGraph message handling
    messages: Annotated[Sequence[BaseMessage], operator.add] = field(default_factory=list)


class NutritionAgentLangGraph:
    """
    Advanced nutrition agent using LangGraph for structured workflow execution.
    Handles nutrition data updates, retrievals, and analysis with proper error handling.
    """

    def __init__(self):
        """
        Initialize the nutrition agent with LangGraph workflow.
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
            model=settings.NUTRITION_AGENT_MODEL,
            api_key=settings.OPENAI_API_KEY
        )
        
        # Vision LLM for image analysis only  
        vision_model = settings.NUTRITION_VISION_MODEL or "gpt-4o"
        self.vision_llm = ChatOpenAI(
            model=vision_model,
            api_key=settings.OPENAI_API_KEY,
            timeout=300
        )
        
        # Database configuration
        self.table_name = PRIMARY_NUTRITION_TABLE
        self.nutrition_tables = NUTRITION_TABLES
        
        # Create tools for the retrieval workflow
        self.tools = self._create_tools()
        
        # Create shared analyze workflow instance with reference to this agent
        from app.agentsv2.nutrition_analyze_workflow import NutritionAnalyzeWorkflow
        self.code_interpreter = NutritionAnalyzeWorkflow(nutrition_agent_instance=self)
        
        # Build the LangGraph workflow
        self.workflow = self._build_workflow()
        
        logger.info(f"✅ Nutrition Agent initialized with basic model: {settings.NUTRITION_AGENT_MODEL} and vision model: {vision_model}")

    def _build_workflow(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(NutritionAgentState)
        
        # Add nodes
        workflow.add_node("analyze_prompt", self.analyze_prompt)
        workflow.add_node("update_nutrition_records", self.update_nutrition_records)
        workflow.add_node("retrieve_nutrition_data", self.retrieve_nutrition_data)
        workflow.add_node("analyze_nutrition", self.analyze_nutrition)
        workflow.add_node("handle_error", self.handle_error)
        workflow.add_node("format_response", self.format_response)
        
        # Set entry point
        workflow.add_edge(START, "analyze_prompt")
        
        # Add conditional edges for task routing
        workflow.add_conditional_edges(
            "analyze_prompt",
            self.route_to_tasks,
            {
                "update_nutrition_records": "update_nutrition_records",
                "retrieve_nutrition_data": "retrieve_nutrition_data", 
                "analyze_nutrition": "analyze_nutrition",
                "error": "handle_error"
            }
        )
        
        # Add edges from task nodes to response formatting
        workflow.add_edge("update_nutrition_records", "format_response")
        workflow.add_edge("retrieve_nutrition_data", "format_response")
        workflow.add_edge("analyze_nutrition", "format_response")
        workflow.add_edge("handle_error", "format_response")
        
        # End workflow
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def _create_tools(self):
        """Create LangGraph tools for nutrition database operations"""
        
        @tool
        async def query_nutrition_db(query: str) -> str:
            """Execute a read-only SQL query on nutrition-related tables.
            
            SUPPORTED OPERATIONS: SELECT, WITH (CTEs), EXPLAIN, DESCRIBE, SHOW
            SUPPORTS: Complex queries, CTEs, subqueries, JOINs, aggregations, window functions
            
            BEFORE CALLING: Always explain your reasoning for this specific query:
            - Why you selected this table
            - What food items/nutrients you're searching for
            - How this relates to the user's nutrition request
            
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

                conn = self.get_postgres_connection()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(query)
                results = cursor.fetchall()
                cursor.close()
                conn.close()
                return json.dumps(results, default=str)
            except Exception as e:
                return f"Query Error: {e}"
        
        @tool
        async def describe_nutrition_table_schema(table_name: str) -> str:
            """Get column names and types for a nutrition-related table.
            
            BEFORE CALLING: Always explain why you're examining this specific table.
            
            Args:
                table_name: Name of the table to describe
                
            Returns:
                String describing the table schema
            """
            try:
                if not table_name:
                    table_name = self.table_name
                conn = self.get_postgres_connection()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute('''
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position;
                ''', (table_name,))
                columns = cursor.fetchall()
                cursor.close()
                conn.close()
                if not columns:
                    return f"No schema found for table '{table_name}'."
                lines = [f"Schema for table '{table_name}':"]
                for col in columns:
                    nullable = 'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'
                    default = f", DEFAULT: {col['column_default']}" if col['column_default'] else ''
                    lines.append(f"- {col['column_name']}: {col['data_type']} ({nullable}){default}")
                return '\n'.join(lines)
            except Exception as e:
                return f"Schema Query Error for table '{table_name}': {e}"
        
        return [query_nutrition_db, describe_nutrition_table_schema, internet_search_tool]

    def get_postgres_connection(self):
        """Get PostgreSQL connection using settings"""
        return psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD
        )

    def log_execution_step(self, state: NutritionAgentState, step_name: str, status: str, details: Dict = None):
        """Log execution step with context"""
        log_entry = {
            "timestamp": isoformat_now(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        state.execution_log.append(log_entry)

    async def analyze_prompt(self, state: NutritionAgentState) -> NutritionAgentState:
        """
        Analyze the incoming prompt to determine which nutrition task is being requested.
        """
        try:
            self.log_execution_step(state, "analyze_prompt", "started")

            system_prompt = (
                "You are an expert nutrition workflow assistant. "
                "Your job is to classify the user's request into one of the following 3 task types:\n"
                "1. update : Update nutrition database with food intake data, meal information, or nutritional values. Some of the example will be like:\n"
                        "- I ate one bowl of rice with brinjal gravy"
                        "- I ate chicken curry with rice for lunch"
                        "- I had a chicken salad for lunch or dinner"
                        "- I had a salad with 100g of chicken breast and 100g of rice for lunch today"
                "2. retrieve : Retrieve nutrition data, food entries, or specific nutrient information by category or date range.\n"
                "3. analyze : Analyze nutrition trends, comparitive analysis, or do more complex data analysis and provide result (e.g., show trends in nutrition intake and how to improve the food intake).\n"
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

    def route_to_tasks(self, state: NutritionAgentState) -> str:
        """Route to appropriate task based on analysis"""
        if state.has_error:
            return "error"

        if not state.task_types or state.task_types[0] == "unknown":
            return "error"

        task = state.task_types[0].lower()

        if task in ["update"]:
            return "update_nutrition_records"
        elif task in ["retrieve"]:
            return "retrieve_nutrition_data"
        elif task in ["analyze"]:
            return "analyze_nutrition"
        else:
            return "error"

    async def _analyze_food_image(self, state: NutritionAgentState) -> Optional[Dict]:
        """Analyze food image using GPT-4V"""
        try:
            print(f"🔍 [DEBUG] Analyzing food image...")
            print(f"🔍 [DEBUG] Image path received: {state.image_path}")
            
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
            
            # Food analysis prompt - using exact same format as lab extraction
            analysis_prompt = """Analyze this food image and extract detailed nutritional information. Please provide a comprehensive analysis including:

        User Request: {original_prompt}
        User ID: {user_id}


        1. **Food Identification**:
           - Dish name (descriptive name for the food)
           - Food item name (main ingredients)
           - Dish type classification (vegetarian, vegan, chicken, beef, fish, shellfish, other)

        2. **Serving Size Estimation**:
           - Estimate the portion size and appropriate unit (grams, cups, pieces, etc.)
           - Base your estimate on visual cues like plate size, utensils, typical serving portions

        3. **Macronutrients** (per serving):
           - Calories
           - Protein (grams)
           - Fat (grams)
           - Carbohydrates (grams)
           - Fiber (grams)
           - Sugar (grams)
           - Sodium (milligrams)

        4. **Vitamins** (per serving):
           - Vitamin A (micrograms)
           - Vitamin C (milligrams)
           - Vitamin D (micrograms)
           - Vitamin E (milligrams)
           - Vitamin K (micrograms)
           - Vitamin B1/Thiamine (milligrams)
           - Vitamin B2/Riboflavin (milligrams)
           - Vitamin B3/Niacin (milligrams)
           - Vitamin B6 (milligrams)
           - Vitamin B12 (micrograms)
           - Folate (micrograms)

        5. **Minerals** (per serving):
           - Calcium (milligrams)
           - Iron (milligrams)
           - Magnesium (milligrams)
           - Phosphorus (milligrams)
           - Potassium (milligrams)
           - Zinc (milligrams)
           - Copper (milligrams)
           - Manganese (milligrams)
           - Selenium (micrograms)

        6. **Analysis Confidence**:
           - Provide a confidence score (0.0-1.0) for your analysis

        7. meal_type: lunch, dinner, breakfast, snack 
            - classify the meal type based on the time of the day and not based on the food items
            - Dont use any other meal type than lunch, dinner, breakfast, snack

        **Response Format**: Respond with a valid JSON object containing all the above information. Use 0.0 for nutrients that are not significantly present or cannot be estimated.

{{
    "meal_type": Based on the time of the day and not based on the food items,
    "food_entries": [
        {{
            "dish_name": "Grilled Chicken Caesar Salad",
            "food_item_name": "Mixed greens, grilled chicken breast, parmesan cheese, croutons, caesar dressing",
            "dish_type": "chicken",
            "portion_size": 350.0,
            "portion_unit": "grams",
            "calories": 420.0,
            "protein_g": 35.0,
            "fat_g": 28.0,
            "carbs_g": 15.0,
            "fiber_g": 4.0,
            "sugar_g": 3.0,
            "sodium_mg": 980.0,
            "vitamin_a_mcg": 180.0,
            "vitamin_c_mg": 25.0,
            "vitamin_d_mcg": 0.5,
            "vitamin_e_mg": 2.0,
            "vitamin_k_mcg": 120.0,
            "vitamin_b1_mg": 0.1,
            "vitamin_b2_mg": 0.2,
            "vitamin_b3_mg": 12.0,
            "vitamin_b6_mg": 0.8,
            "vitamin_b12_mcg": 1.2,
            "folate_mcg": 40.0,
            "calcium_mg": 200.0,
            "iron_mg": 2.5,
            "magnesium_mg": 35.0,
            "phosphorus_mg": 280.0,
            "potassium_mg": 450.0,
            "zinc_mg": 3.5,
            "copper_mg": 0.1,
            "manganese_mg": 0.5,
            "selenium_mcg": 25.0,
            "confidence_score": 0.85
        }},
        {{
            "dish_name": "Dal Chawal with white rice",
            "food_item_name": "rice, dal, white rice etc",
            "dish_type": "Veg",
            "portion_size": 350.0,
            "portion_unit": "grams",
            "calories": 420.0,
            "protein_g": 35.0,
            "fat_g": 28.0,
            "carbs_g": 15.0,
            "fiber_g": 4.0,
            "sugar_g": 3.0,
            "sodium_mg": 980.0,
            "vitamin_a_mcg": 180.0,
            "vitamin_c_mg": 25.0,
            "vitamin_d_mcg": 0.5,
            "vitamin_e_mg": 2.0,
            "vitamin_k_mcg": 120.0,
            "vitamin_b1_mg": 0.1,
            "vitamin_b2_mg": 0.2,
            "vitamin_b3_mg": 12.0,
            "vitamin_b6_mg": 0.8,
            "vitamin_b12_mcg": 1.2,
            "folate_mcg": 40.0,
            "calcium_mg": 200.0,
            "iron_mg": 2.5,
            "magnesium_mg": 35.0,
            "phosphorus_mg": 280.0,
            "potassium_mg": 450.0,
            "zinc_mg": 3.5,
            "copper_mg": 0.1,
            "manganese_mg": 0.5,
            "selenium_mcg": 25.0,
            "confidence_score": 0.85
        }}
    ]
}}

IMPORTANT:
- Extract ALL food items visible in the image
- Use realistic nutritional estimates for the portions shown
- Estimate values based on visual serving sizes
- Use consistent units (grams for macronutrients, mg for micronutrients)""".format(
                original_prompt=state.original_prompt,
                user_id=state.user_id,
                current_date=now_local().strftime("%Y-%m-%d"),
                current_datetime=isoformat_now()
            )
            
            # Analyze image
            messages = [
                SystemMessage(content="You are an expert nutritionist who can identify foods and estimate their nutritional content from images."),
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
                
                nutrition_data = json.loads(content)
                # Use configured timezone for timestamps to avoid server-region dependence
                now = now_local()
                nutrition_data["meal_date"] = now.strftime("%Y-%m-%d")
                nutrition_data["meal_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                print(f"🔍 [DEBUG] Successfully extracted nutrition from image: {len(nutrition_data.get('food_entries', []))} foods")
                return nutrition_data
                
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse image analysis JSON: {str(e)}")
                return None
                
        except Exception as e:
            print(f"🔍 [DEBUG] Error analyzing food image: {str(e)}")
            return None

    async def _extract_from_text(self, state: NutritionAgentState) -> Optional[Dict]:
        """Extract nutrition data from text input"""
        try:
            print(f"🔍 [DEBUG] Extracting nutrition from text...")
            
            extraction_prompt = """Analyze this food text provided by the user describing the food intake and provide a comprehensive analysis including:

        User Request: {original_prompt}
        User ID: {user_id}


        1. **Food Identification**:
           - Dish name (descriptive name for the food)
           - Food item name (main ingredients)
           - Dish type classification (vegetarian, vegan, chicken, beef, fish, shellfish, other)

        2. **Serving Size Estimation**:
           - Estimate the portion size and appropriate unit (grams, cups, pieces, etc.)
           - Base your estimate on visual cues like plate size, utensils, typical serving portions

        3. **Macronutrients** (per serving):
           - Calories
           - Protein (grams)
           - Fat (grams)
           - Carbohydrates (grams)
           - Fiber (grams)
           - Sugar (grams)
           - Sodium (milligrams)

        4. **Vitamins** (per serving):
           - Vitamin A (micrograms)
           - Vitamin C (milligrams)
           - Vitamin D (micrograms)
           - Vitamin E (milligrams)
           - Vitamin K (micrograms)
           - Vitamin B1/Thiamine (milligrams)
           - Vitamin B2/Riboflavin (milligrams)
           - Vitamin B3/Niacin (milligrams)
           - Vitamin B6 (milligrams)
           - Vitamin B12 (micrograms)
           - Folate (micrograms)

        5. **Minerals** (per serving):
           - Calcium (milligrams)
           - Iron (milligrams)
           - Magnesium (milligrams)
           - Phosphorus (milligrams)
           - Potassium (milligrams)
           - Zinc (milligrams)
           - Copper (milligrams)
           - Manganese (milligrams)
           - Selenium (micrograms)

        6. **Analysis Confidence**:
           - Provide a confidence score (0.0-1.0) for your analysis

        **Response Format**: Respond with a valid JSON object containing all the above information. Use 0.0 for nutrients that are not significantly present or cannot be estimated.

{{
    "meal_type": "lunch, dinner, breakfast, snack, etc",
    "food_entries": [
        {{
            "dish_name": "Grilled Chicken Caesar Salad",
            "food_item_name": "Mixed greens, grilled chicken breast, parmesan cheese, croutons, caesar dressing",
            "dish_type": "chicken",
            "portion_size": 350.0,
            "portion_unit": "grams",
            "calories": 420.0,
            "protein_g": 35.0,
            "fat_g": 28.0,
            "carbs_g": 15.0,
            "fiber_g": 4.0,
            "sugar_g": 3.0,
            "sodium_mg": 980.0,
            "vitamin_a_mcg": 180.0,
            "vitamin_c_mg": 25.0,
            "vitamin_d_mcg": 0.5,
            "vitamin_e_mg": 2.0,
            "vitamin_k_mcg": 120.0,
            "vitamin_b1_mg": 0.1,
            "vitamin_b2_mg": 0.2,
            "vitamin_b3_mg": 12.0,
            "vitamin_b6_mg": 0.8,
            "vitamin_b12_mcg": 1.2,
            "folate_mcg": 40.0,
            "calcium_mg": 200.0,
            "iron_mg": 2.5,
            "magnesium_mg": 35.0,
            "phosphorus_mg": 280.0,
            "potassium_mg": 450.0,
            "zinc_mg": 3.5,
            "copper_mg": 0.1,
            "manganese_mg": 0.5,
            "selenium_mcg": 25.0,
            "confidence_score": 0.85
        }},
        {{
            "dish_name": "Dal Chawal with white rice",
            "food_item_name": "rice, dal, white rice etc",
            "dish_type": "Veg",
            "portion_size": 350.0,
            "portion_unit": "grams",
            "calories": 420.0,
            "protein_g": 35.0,
            "fat_g": 28.0,
            "carbs_g": 15.0,
            "fiber_g": 4.0,
            "sugar_g": 3.0,
            "sodium_mg": 980.0,
            "vitamin_a_mcg": 180.0,
            "vitamin_c_mg": 25.0,
            "vitamin_d_mcg": 0.5,
            "vitamin_e_mg": 2.0,
            "vitamin_k_mcg": 120.0,
            "vitamin_b1_mg": 0.1,
            "vitamin_b2_mg": 0.2,
            "vitamin_b3_mg": 12.0,
            "vitamin_b6_mg": 0.8,
            "vitamin_b12_mcg": 1.2,
            "folate_mcg": 40.0,
            "calcium_mg": 200.0,
            "iron_mg": 2.5,
            "magnesium_mg": 35.0,
            "phosphorus_mg": 280.0,
            "potassium_mg": 450.0,
            "zinc_mg": 3.5,
            "copper_mg": 0.1,
            "manganese_mg": 0.5,
            "selenium_mcg": 25.0,
            "confidence_score": 0.85
        }}
    ]
}}

IMPORTANT:
- Use realistic nutritional estimates for the portions shown
- Estimate values based on visual serving sizes
- Use consistent units (grams for macronutrients, mg for micronutrients)""".format(
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
                user_content_parts.append(" No document content provided for analysis.")
            
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
                
                nutrition_data = json.loads(cleaned_content)
                # Override timestamps for text-only inputs using runtime variables
                now = now_local()
                nutrition_data["meal_date"] = now.strftime("%Y-%m-%d")
                nutrition_data["meal_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                print(f"🔍 [DEBUG] Successfully extracted nutrition from text: {len(nutrition_data.get('food_entries', []))} foods")
                return nutrition_data
                
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse text extraction JSON: {str(e)}")
                return None
                
        except Exception as e:
            print(f"🔍 [DEBUG] Error extracting from text: {str(e)}")
            return None

    async def update_nutrition_records(self, state: NutritionAgentState) -> NutritionAgentState:
        """Handle nutrition data updates including food intake, meals, and nutritional values"""
        self.log_execution_step(state, "update_nutrition_records", "started")
        try:
            # Check if we have an image to analyze
            if state.image_path or state.image_base64:
                # Use image-based food recognition
                nutrition_data = await self._analyze_food_image(state)
            else:
                # Use text-based extraction
                nutrition_data = await self._extract_from_text(state)
            
            if not nutrition_data:
                state.has_error = True
                state.error_context = {
                    "error_type": "extraction_failed",
                    "node": "update_nutrition_records",
                    "message": "Failed to extract nutrition data from input",
                }
                return state
            
            print(f"🔍 [DEBUG] Successfully extracted nutrition data with {len(nutrition_data.get('food_entries', []))} food entries")

            # Prepare nutrition records for batch processing
            user_id = state.user_id
            nutrition_records = []
            food_entries = nutrition_data.get("food_entries", [])
            
            if not food_entries:
                state.has_error = True
                state.error_context = {
                    "error_type": "no_food_entries_found",
                    "node": "update_nutrition_records",
                    "message": "No food entries found in extracted nutrition data.",
                    "context": {"nutrition_data": nutrition_data}
                }
                return state

            # Prepare all nutrition records for batch processing
            for food_entry in food_entries:
                # Prefer durable persisted path (S3 URI) over temp path for image_url
                persisted_image_url = ""
                try:
                    if state.source_file_path and str(state.source_file_path).strip():
                        persisted_image_url = state.source_file_path
                    elif state.image_path and str(state.image_path).strip():
                        persisted_image_url = state.image_path
                except Exception:
                    persisted_image_url = state.image_path or ""
                nutrition_record = {
                    "user_id": user_id,
                    "dish_name": food_entry.get("dish_name"),
                    "food_item_name": food_entry.get("food_item_name"),
                    "dish_type": food_entry.get("dish_type"),
                    "portion_size": food_entry.get("portion_size"),
                    "portion_unit": food_entry.get("portion_unit"),
                    "calories": food_entry.get("calories"),
                    "protein_g": food_entry.get("protein_g"),
                    "fat_g": food_entry.get("fat_g"),
                    "carbs_g": food_entry.get("carbs_g"),
                    "fiber_g": food_entry.get("fiber_g"),
                    "sugar_g": food_entry.get("sugar_g"),
                    "sodium_mg": food_entry.get("sodium_mg"),
                    "vitamin_a_mcg": food_entry.get("vitamin_a_mcg"),
                    "vitamin_c_mg": food_entry.get("vitamin_c_mg"),
                    "vitamin_d_mcg": food_entry.get("vitamin_d_mcg"),
                    "vitamin_e_mg": food_entry.get("vitamin_e_mg"),
                    "vitamin_k_mcg": food_entry.get("vitamin_k_mcg"),
                    "vitamin_b1_mg": food_entry.get("vitamin_b1_mg"),
                    "vitamin_b2_mg": food_entry.get("vitamin_b2_mg"),
                    "vitamin_b3_mg": food_entry.get("vitamin_b3_mg"),
                    "vitamin_b6_mg": food_entry.get("vitamin_b6_mg"),
                    "vitamin_b12_mcg": food_entry.get("vitamin_b12_mcg"),
                    "folate_mcg": food_entry.get("folate_mcg"),
                    "calcium_mg": food_entry.get("calcium_mg"),
                    "iron_mg": food_entry.get("iron_mg"),
                    "magnesium_mg": food_entry.get("magnesium_mg"),
                    "phosphorus_mg": food_entry.get("phosphorus_mg"),
                    "potassium_mg": food_entry.get("potassium_mg"),
                    "zinc_mg": food_entry.get("zinc_mg"),
                    "copper_mg": food_entry.get("copper_mg"),
                    "manganese_mg": food_entry.get("manganese_mg"),
                    "selenium_mcg": food_entry.get("selenium_mcg"),
                    "confidence_score": food_entry.get("confidence_score") or 0.8,
                    "image_url": persisted_image_url,
                    "meal_date": nutrition_data.get("meal_date"),
                    "meal_time": nutrition_data.get("meal_time"),
                    "meal_type": nutrition_data.get("meal_type"),
                    "data_source": "photo_analysis" if (state.image_path or state.image_base64 or state.source_file_path) else "manual_entry",
                    "aggregation_status": "pending",
                }
                nutrition_records.append(nutrition_record)

            # Set extracted_nutrition_data for response
            state.extracted_nutrition_data = nutrition_records

            # Call DB update with batch processing
            batch_result = self.update_nutrition_db(nutrition_records)
            
            # Store results
            state.update_results = batch_result
            self.log_execution_step(state, "update_nutrition_records", "completed", {"batch_result": batch_result})
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "exception",
                "node": "update_nutrition_records",
                "message": str(e),
            }
            self.log_execution_step(state, "update_nutrition_records", "failed", {"error": str(e)})
        return state

    async def retrieve_nutrition_data(self, state: NutritionAgentState) -> NutritionAgentState:
        """LangGraph-based retrieval workflow using agent reasoning"""
        self.log_execution_step(state, "retrieve_nutrition_data", "started")
        try:
            user_request = state.original_prompt + " for the user_id: " + str(state.user_id)
            print(f"DEBUG: Calling LangGraph nutrition retrieval agent with request: {user_request}")
            
            # Use the LangGraph-based retrieval agent (maintains same logic as ReAct agent)
            result = await self._use_advanced_retrieval(user_request)
            
            print(f"DEBUG: LangGraph nutrition agent returned: {result}")
            
            # Store only the `output` section (which is either a JSON list or a raw string)
            state.query_results = result.get("output")
            # Store raw intermediate output for final response
            raw_payload = result.get("intermediate", {}).get("raw_full_payload")
            try:
                if raw_payload is not None:
                    if state.intermediate_outputs is None:
                        state.intermediate_outputs = {}
                    state.intermediate_outputs["query_nutrition_db"] = raw_payload
            except Exception:
                pass
            self.log_execution_step(state, "retrieve_nutrition_data", "completed", {"results": result})
        except Exception as e:
            print(f"DEBUG: Exception in retrieve_nutrition_data: {str(e)}")
            import traceback
            traceback.print_exc()
            state.has_error = True
            state.error_context = {
                "error_type": "sql_generation_or_execution",
                "node": "retrieve_nutrition_data",
                "message": str(e),
            }
            self.log_execution_step(state, "retrieve_nutrition_data", "failed", {"error": str(e)})
        return state

    async def analyze_nutrition(self, state: NutritionAgentState) -> NutritionAgentState:
        """
        Analyze patterns and derive trends from nutrition data using the analyze workflow.
        
        This method leverages the NutritionAnalyzeWorkflow to:
        1. Analyze the user's request for analysis type
        2. Query relevant nutrition data 
        3. Generate Python code for the specific analysis
        4. Execute the code safely with the data
        5. Format results with interpretations
        """
        try:
            self.log_execution_step(state, "analyze_nutrition", "started")
            
            # Use the shared code interpreter instance for better performance
            analysis_results = await self.code_interpreter.run(
                request=state.original_prompt,
                user_id=state.user_id
            )
            
            # Store the analysis results in the state
            state.nutrition_analysis = analysis_results
            
            # Log success with details
            if analysis_results.get("success", True):  # Default to True if not specified
                self.log_execution_step(state, "analyze_nutrition", "completed", {
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
                    "node": "analyze_nutrition", 
                    "message": analysis_results.get("error", "Code interpreter failed"),
                    "context": {
                        "step_failed": analysis_results.get("step_failed"),
                        "suggestions": analysis_results.get("suggestions", [])
                    }
                }
                self.log_execution_step(state, "analyze_nutrition", "failed", {
                    "error": analysis_results.get("error"),
                    "step_failed": analysis_results.get("step_failed")
                })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "technical",
                "node": "analyze_nutrition",
                "message": f"Code interpreter workflow failed: {str(e)}",
                "context": {"exception_type": type(e).__name__}
            }
            self.log_execution_step(state, "analyze_nutrition", "failed", {"error": str(e)})
        
        return state

    async def handle_error(self, state: NutritionAgentState) -> NutritionAgentState:
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

    async def format_response(self, state: NutritionAgentState) -> NutritionAgentState:
        """Format the final response based on the completed tasks"""
        try:
            if state.has_error:
                # Error response already handled in handle_error
                return state
            
            if not state.has_error and not state.response_data:
                # Format response based on task type (match lab agent)
                results = {}
                if state.extracted_nutrition_data:
                    results["extracted_data"] = state.extracted_nutrition_data
                if state.query_results:
                    results["query_results"] = state.query_results
                # Include intermediate tool outputs if captured (prevents truncation issues)
                if state.intermediate_outputs:
                    results["intermediate_tool_outputs"] = state.intermediate_outputs
                if state.update_results:
                    results["update_results"] = state.update_results
                if state.nutrition_analysis:
                    # Extract the actual results from workflow and put directly in results
                    if isinstance(state.nutrition_analysis, dict) and state.nutrition_analysis.get("success"):
                        # Use the workflow's results directly without the wrapper
                        results = state.nutrition_analysis.get("results", {})
                        
                        # Ensure visualizations are included at the top level
                        if "visualizations" in state.nutrition_analysis:
                            results["visualizations"] = state.nutrition_analysis["visualizations"]
                        
                    else:
                        results["analysis_error"] = "Nutrition analysis workflow failed"
                # Use shared response formatter with visualization support
                state.response_data = format_agent_response(
                    success=True,
                    task_types=state.task_types,
                    results=results,
                    execution_log=state.execution_log,
                    message="Nutrition analysis completed successfully"
                )
            
        except Exception as e:
            # Use shared error formatter
            state.response_data = format_error_response(
                error_message=f"Error formatting response: {str(e)}",
                execution_log=state.execution_log,
                task_types=state.task_types
            )
        
        return state

    async def run(self, prompt: str, user_id: int, extracted_text: str = None, image_path: str = None, image_base64: str = None, source_file_path: str = None) -> Dict[str, Any]:
        """
        Execute the nutrition agent workflow.
        
        Args:
            prompt: The user's nutrition request
            user_id: User ID for data operations
            extracted_text: Optional extracted text from documents
            image_path: Optional path to food image
            image_base64: Optional base64 encoded image data
            
        Returns:
            Dict containing the results
        """
        try:
            # Initialize state
            initial_state = NutritionAgentState(
                original_prompt=prompt,
                user_id=user_id,
                extracted_text=extracted_text,
                image_path=image_path,
                image_base64=image_base64,
                source_file_path=source_file_path
            )

            # LangSmith tracing config
            config = None
            if hasattr(settings, 'LANGCHAIN_TRACING_V2') and settings.LANGCHAIN_TRACING_V2:
                config = {
                    "configurable": {"thread_id": f"nutrition-agent-{user_id}"},
                    "callbacks": [LangChainTracer()]
                }
            if config:
                result = await self.workflow.ainvoke(initial_state, config=config)
            else:
                result = await self.workflow.ainvoke(initial_state)

            # Defensive: If result is a dict, handle it appropriately (match lab agent)
            if isinstance(result, dict):
                # PRIORITY: Always use formatted response_data if available (from format_response method)
                if result.get("response_data"):
                    return result["response_data"]
                    
                # FALLBACK: Manual response construction only if format_response didn't run
                results_data = {}
                
                if result.get("query_results"):
                    results_data["query_results"] = result["query_results"]
                    
                if result.get("extracted_nutrition_data"):
                    results_data["extracted_nutrition_data"] = result["extracted_nutrition_data"]
                    
                if result.get("nutrition_analysis"):
                    # Extract workflow results directly without wrapper
                    nutrition_data = result["nutrition_analysis"]
                    if isinstance(nutrition_data, dict) and nutrition_data.get("success"):
                        workflow_results = nutrition_data.get("results", {})
                        if workflow_results:
                            results_data.update(workflow_results)

                # Use standard response format with visualization support
                from app.agentsv2.response_utils import format_agent_response
                response = format_agent_response(
                    success=not result.get("has_error", False),
                    task_types=result.get("task_types", ["nutrition_analysis"]),
                    results=results_data,
                    execution_log=result.get("execution_log", []),
                    message="Nutrition analysis completed successfully",
                    title="Nutrition Analysis",
                    error=result.get("error_context", {}).get("message") if result.get("has_error") else None
                )
                return response
            # All agents should return response_data consistently
            # The format_response method sets this using format_agent_response()
            if result.response_data:
                print(f"✅ [DEBUG] Nutrition agent returning standardized response_data")
                return result.response_data
            
            # If no response_data, this indicates a workflow issue - should not happen
            print(f"⚠️ [DEBUG] Nutrition agent missing response_data - this should not happen")
            from app.agentsv2.response_utils import format_error_response
            return format_error_response(
                error_message="Nutrition agent workflow completed but no response data was generated",
                execution_log=getattr(result, 'execution_log', []),
                task_types=getattr(result, 'task_types', ["unknown"])
            )
            
        except Exception as e:
            logger.error(f"Nutrition agent workflow failed: {str(e)}")
            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}",
                "error_type": "technical",
                "context": {"exception_type": type(e).__name__}
            }

    def update_nutrition_db(self, nutrition_result) -> dict:
        """
        Insert or update one or more nutrition records. Always returns a stats dict.
        """
        results = []
        stats = {
            "total_processed": 0,
            "inserted": 0,
            "updated": 0,
            "duplicates": 0,
            "failed": 0,
            "results": []
        }
        if isinstance(nutrition_result, list):
            for record in nutrition_result:
                res = self._update_nutrition_db_single(record)
                results.append(res)
        elif isinstance(nutrition_result, dict):
            res = self._update_nutrition_db_single(nutrition_result)
            results.append(res)
        else:
            results.append({"action": "failed", "error": f"Input must be a dict or list of dicts, got {type(nutrition_result)}"})
        # Tally stats
        for res in results:
            stats["total_processed"] += 1
            if res.get("action") == "inserted":
                stats["inserted"] += 1
            elif res.get("action") == "updated":
                stats["updated"] += 1
            elif res.get("action") == "duplicate":
                stats["duplicates"] += 1
            elif res.get("action") == "failed" or res.get("action") == "error":
                stats["failed"] += 1
        stats["results"] = results
        # Fire-and-forget coalesced aggregation for nutrition domain
        try:
            import asyncio
            user_id = None
            if isinstance(nutrition_result, dict):
                user_id = nutrition_result.get("user_id") or nutrition_result.get("userId")
            elif isinstance(nutrition_result, list) and nutrition_result and isinstance(nutrition_result[0], dict):
                user_id = nutrition_result[0].get("user_id") or nutrition_result[0].get("userId")
            asyncio.create_task(trigger_smart_aggregation(user_id=user_id, domains=["nutrition"]))
        except Exception:
            pass

        return stats

    def _update_nutrition_db_single(self, nutrition_data: dict) -> dict:
        """Update a single nutrition record in the database using all nutrition variables."""
        try:
            def clean_value(value):
                return None if value == "" else value

            cleaned = {key: clean_value(value) for key, value in nutrition_data.items()}
            # Ensure aggregation status is set to pending by default
            if not cleaned.get('aggregation_status'):
                cleaned['aggregation_status'] = 'pending'

            conn = self.get_postgres_connection()
            cursor = conn.cursor()

            # Prepare all fields for insert/update
            fields = [
                'user_id', 'food_item_name', 'dish_name', 'dish_type', 'meal_type',
                'portion_size', 'portion_unit',
                'calories', 'protein_g', 'fat_g', 'carbs_g', 'fiber_g', 'sugar_g', 'sodium_mg',
                'vitamin_a_mcg', 'vitamin_c_mg', 'vitamin_d_mcg', 'vitamin_e_mg', 'vitamin_k_mcg',
                'vitamin_b1_mg', 'vitamin_b2_mg', 'vitamin_b3_mg', 'vitamin_b6_mg', 'vitamin_b12_mcg', 'folate_mcg',
                'calcium_mg', 'iron_mg', 'magnesium_mg', 'phosphorus_mg', 'potassium_mg', 'zinc_mg',
                'copper_mg', 'manganese_mg', 'selenium_mcg',
                'meal_date', 'meal_time', 'data_source', 'confidence_score', 'image_url', 'aggregation_status'
            ]
            values = [cleaned.get(f, None) for f in fields]

            # Upsert logic: try update, if not found then insert
            update_fields = [f"{f} = %s" for f in fields[1:]]  # skip user_id for update
            update_query = f"""
                UPDATE {self.table_name}
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE user_id = %s 
                  AND meal_date = %s 
                  AND meal_time = %s
                  AND dish_name IS NOT DISTINCT FROM %s
                RETURNING id
            """
            cursor.execute(
                update_query,
                values[1:] + [
                    values[0],
                    values[fields.index('meal_date')],
                    values[fields.index('meal_time')],
                    values[fields.index('dish_name')]
                ]
            )
            result = cursor.fetchone()
            if result:
                conn.commit()
                return {"action": "updated", "record_id": result[0]}
            # If not updated, insert
            insert_fields = ', '.join(fields)
            insert_placeholders = ', '.join(['%s'] * len(fields))
            insert_query = f"""
                INSERT INTO {self.table_name} ({insert_fields})
                VALUES ({insert_placeholders})
                RETURNING id
            """
            cursor.execute(insert_query, values)
            new_id = cursor.fetchone()[0]
            conn.commit()
           
            return {"action": "inserted", "record_id": new_id}
        except Exception as e:
            if conn:
                conn.rollback()
            return {"action": "error", "error": str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def _use_advanced_retrieval(self, user_request: str) -> Dict[str, Any]:
        """Use LangGraph ReAct agent for retrieval but *bypass* the model's final
        message and return the raw JSON payload produced by the last
        `query_nutrition_db` tool call.  This guarantees that large result sets
        are never truncated by the language-model."""
        try:
            # 1. Build the ReAct agent (LangGraph helper)
            agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                prompt=NUTRITION_SQL_GENERATION_SYSTEM_PROMPT
            )

            # 2. Execute the agent while requesting all intermediate tool steps.
            #    LangGraph and LCEL agents accept a second *config* dict where we
            #    can set `return_intermediate_steps=True`.
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=user_request)]},
                {"return_intermediate_steps": True}
            )

            # 3. Walk through the intermediate steps in reverse order to locate
            #    the observation returned by `query_nutrition_db` (it is always
            #    the last database tool call and contains the full JSON list).
            intermediate_steps = result.get("intermediate_steps", [])
            full_payload: str | None = None
            for step in reversed(intermediate_steps):
                # Each step is usually a tuple: (AgentAction, observation)
                if isinstance(step, (list, tuple)) and len(step) == 2:
                    observation = step[1]
                    if isinstance(observation, str) and observation.lstrip().startswith("["):
                        full_payload = observation.strip()
                        break

            # 4. Fallback — if for some reason we didn't find the tool output,
            #    use the language-model's final message (status-quo behaviour).
            if not full_payload:
                final_message = result["messages"][-1]
                full_payload = final_message.content if hasattr(final_message, "content") else str(final_message)

            # 5. Attempt to parse JSON so downstream code can treat it as a
            #    Python object.  If parsing fails we return the raw string.
            try:
                parsed_output = json.loads(full_payload)
            except Exception:
                parsed_output = full_payload

            return {
                "input": user_request,
                "output": parsed_output,
                "intermediate": {
                    "raw_full_payload": full_payload,
                    "intermediate_steps_count": len(intermediate_steps)
                }
            }

        except Exception as e:
            print(f"DEBUG: LangGraph ReAct agent failed: {str(e)}")
            return {
                "input": user_request,
                "output": f"Retrieval failed: {str(e)}"
            }




if __name__ == "__main__":
    import asyncio
    
    agent = NutritionAgentLangGraph()
    
    test_prompts = [
        "update my weight based on the image from a weight scale"
    ]
    image_path = "/Users/rajanishsd/Documents/zivohealth-1/backend/data/unprocessed/8EBBB66E-DB32-486B-8C4F-AF5962BED976_1_102_o.jpeg"
    async def main():
        for prompt in test_prompts:
            print(f"\n--- Testing prompt: {prompt} ---")
            result = await agent.run(prompt, user_id=1, image_path=image_path)
            print(f"Result: {json.dumps(result, indent=2)}")
    
    asyncio.run(main()) 