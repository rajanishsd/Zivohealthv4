#!/usr/bin/env python3
"""
Pharmacy Agent using LangGraph for handling pharmacy data operations.
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
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from app.core.config import settings
from app.core.database_utils import execute_query_safely_json, get_table_schema_safely, get_raw_db_connection
from app.utils.timezone import now_local, isoformat_now
from app.agentsv2.response_utils import format_agent_response, format_error_response

# Import pharmacy configuration
from app.configurations.pharmacy_config import PHARMACY_TABLES, PRIMARY_PHARMACY_TABLE

# LangSmith tracing imports
from langsmith import Client
from langchain.callbacks.tracers import LangChainTracer

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQL generation system prompt for the pharmacy retrieval agent
PHARMACY_SQL_GENERATION_SYSTEM_PROMPT = """
You are an intelligent pharmacy data assistant. You must follow these TABLE SELECTION RULES strictly:

⚠️ REASONING REQUIREMENT ⚠️
BEFORE EVERY TOOL CALL, you MUST explain your reasoning:
1. Why you are selecting this specific tool
2. What information you hope to get from this tool
3. How this tool call fits into your overall strategy
4. What you will do with the results

EXAMPLE FORMAT:
"I want to know the pharmacy bill for the last 30 days or extract medication intake for the last 30 days"

CRITICAL TABLE SELECTION RULES:
1. for pharmacy related queries, use the pharmacy_bills table for all time periods. this contain raw data when the medication were purchased from the pharmacy.
2. for medication related queries, use the pharmacy_medications table for all time periods. this contain raw data when the medication were purchased from the pharmacy.


AVAILABLE TABLES:
- pharmacy_bills: Main table for pharmacy bills, that contains the pharmacy bill, pharmacy name, address, cost, gst(total tax), total amount, date, etc.
- pharmacy_medications: this table contains the medication items that are purchased from the pharmacy along with individual cost, quantity, date of purchase, total taxt, discount, etc.


SEARCH STRATEGY:
- For pharmacy related queries, use the pharmacy_bills table for all time periods. this contain raw data when the medication were purchased from the pharmacy.
- For medication related queries, use the pharmacy_medications table for all time periods. for individual medication items, you can join with pharmacy_bills table to get the pharmacy name, address, cost, gst(total tax), total amount, date, etc.

Your job is to:
1. FIRST: Analyze the request and carefully identify the time period in the user's request
2. SECOND: Apply the table selection rules above to select the correct table
3. THIRD: **EXPLAIN YOUR REASONING** before calling DescribePharmacyTableSchema - why this table?
4. FOURTH: Use DescribePharmacyTableSchema tool to get column names for your selected table
5. FIFTH: Generate SQL query using the CORRECT table and user_id to identify DISTINCT pharmacy names and medication items. Do not specify any conditions as you are exploring what medications are available
6. SIXTH: Use the medication items obtained in the previous step and your pharmacy knowledge to identify the most relevant medications or pharmacy related data that meet the user request and generate a simple select query with LIKE operator instead of exact match to retrieve the pharmacy data. Include all the medications that match the criteria. Always filter by user_id.
7. SEVENTH: Return query results in structured JSON format along with the reasoning for the response in the output field
8. EIGHTH: BE PROACTIVE - don't ask user what to do, try multiple approaches until you find results.
9. NINTH: **FINAL REASONING**: Always end your response with a summary of your decision-making process and what you found

REASONING EXAMPLES:
- "I'm selecting the main pharmacy table because the user asked for 'recent' bills intake without specifying a time period, suggesting they want recent results from the detailed table."
- "I'm looking for high-protein medications, so I'll search for both specific dish types like 'chicken', 'fish' AND specific medication items like 'protein', 'meat', 'eggs' which are all relevant to protein intake."
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
- WITH recent_bills AS (SELECT * FROM pharmacy_bills WHERE date >= CURRENT_DATE - 30) SELECT pharmacy_name, COUNT(*) FROM recent_bills GROUP BY pharmacy_name
- SELECT *, ROW_NUMBER() OVER (PARTITION BY pharmacy_name ORDER BY date DESC) as rank FROM pharmacy_bills WHERE pharmacy_name = 'pharmacy_name'
"""


@dataclass
class PharmacyAgentState:
    """State management for the pharmacy agent workflow"""
    # Input data
    original_prompt: str = ""
    user_id: Optional[int] = None
    extracted_text: Optional[str] = None
    image_path: Optional[str] = None  # Path to medication image for processing (only if no extracted_text)
    image_base64: Optional[str] = None  # Base64 encoded image data
    source_file_path: Optional[str] = None  # Original file path for storage/record-keeping
    
    # Task classification
    task_types: List[str] = field(default_factory=list)
    task_parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Execution data
    extracted_pharmacy_data: Optional[List[Dict]] = None
    query_results: Optional[List[Dict]] = None
    update_results: Optional[Dict] = None
    pharmacy_analysis: Optional[Dict] = None
    
    # Error handling
    error_context: Optional[Dict] = None
    has_error: bool = False
    
    # Response data
    response_data: Optional[Dict] = None
    execution_log: List[Dict] = field(default_factory=list)
    
    # Workflow control
    next_step: Optional[str] = None
    
    # Available tables configuration
    available_tables: Dict[str, str] = field(default_factory=lambda: PHARMACY_TABLES)
    
    # LangGraph message handling
    messages: Annotated[Sequence[BaseMessage], operator.add] = field(default_factory=list)


class PharmacyAgentLangGraph:
    """
    Advanced pharmacy agent using LangGraph for structured workflow execution.
    Handles pharmacy data updates, retrievals, and analysis with proper error handling.
    """

    def __init__(self):
        """
        Initialize the pharmacy agent with LangGraph workflow.
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
            model=settings.PHARMACY_AGENT_MODEL,
            api_key=settings.OPENAI_API_KEY
        )
        
        # Vision LLM for image analysis only  
        vision_model = settings.PHARMACY_VISION_MODEL 
        self.vision_llm = ChatOpenAI(
            model=vision_model,
            api_key=settings.OPENAI_API_KEY,
            timeout=300
        )
        
        # Database configuration
        self.table_name = PRIMARY_PHARMACY_TABLE
        self.pharmacy_tables = PHARMACY_TABLES
        
        # Create tools for the retrieval workflow
        self.tools = self._create_tools()
        
        # Create shared analyze workflow instance with reference to this agent
        from app.agentsv2.pharmacy_analyze_workflow import PharmacyAnalyzeWorkflow
        self.code_interpreter = PharmacyAnalyzeWorkflow(pharmacy_agent_instance=self)
        
        # Build the LangGraph workflow
        self.workflow = self._build_workflow()
        
        logger.info(f"✅ Pharmacy Agent initialized with basic model: {settings.PHARMACY_AGENT_MODEL} and vision model: {vision_model}")

    def _build_workflow(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(PharmacyAgentState)
        
        # Add nodes
        workflow.add_node("analyze_prompt", self.analyze_prompt)
        workflow.add_node("update_pharmacy_records", self.update_pharmacy_records)
        workflow.add_node("retrieve_pharmacy_data", self.retrieve_pharmacy_data)
        workflow.add_node("analyze_pharmacy", self.analyze_pharmacy)
        workflow.add_node("handle_error", self.handle_error)
        workflow.add_node("format_response", self.format_response)
        
        # Set entry point
        workflow.add_edge(START, "analyze_prompt")
        
        # Add conditional edges for task routing
        workflow.add_conditional_edges(
            "analyze_prompt",
            self.route_to_tasks,
            {
                "update_pharmacy_records": "update_pharmacy_records",
                "retrieve_pharmacy_data": "retrieve_pharmacy_data", 
                "analyze_pharmacy": "analyze_pharmacy",
                "error": "handle_error"
            }
        )
        
        # Add edges from task nodes to response formatting
        workflow.add_edge("update_pharmacy_records", "format_response")
        workflow.add_edge("retrieve_pharmacy_data", "format_response")
        workflow.add_edge("analyze_pharmacy", "format_response")
        workflow.add_edge("handle_error", "format_response")
        
        # End workflow
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def _create_tools(self):
        """Create LangGraph tools for pharmacy database operations"""
        
        @tool
        async def query_pharmacy_db(query: str) -> str:
            """Execute a read-only SQL query on pharmacy-related tables.
            
            SUPPORTED OPERATIONS: SELECT, WITH (CTEs), EXPLAIN, DESCRIBE, SHOW
            SUPPORTS: Complex queries, CTEs, subqueries, JOINs, aggregations, window functions
            
            BEFORE CALLING: Always explain your reasoning for this specific query:
            - Why you selected this table
            - What medication items/nutrients you're searching for
            - How this relates to the user's pharmacy request
            
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
        async def describe_pharmacy_table_schema(table_name: str) -> str:
            """Get column names and types for a pharmacy-related table.
            
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
        
        return [query_pharmacy_db, describe_pharmacy_table_schema]


    def log_execution_step(self, state: PharmacyAgentState, step_name: str, status: str, details: Dict = None):
        """Log execution step with context"""
        log_entry = {
            "timestamp": isoformat_now(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        state.execution_log.append(log_entry)

    async def analyze_prompt(self, state: PharmacyAgentState) -> PharmacyAgentState:
        """
        Analyze the incoming prompt to determine which pharmacy task is being requested.
        """
        try:
            self.log_execution_step(state, "analyze_prompt", "started")

            system_prompt = (
                "You are an expert pharmacy workflow assistant. "
                "Your job is to classify the user's request into one of the following 3 task types:\n"
                "1. update : Update pharmacy database with medication intake data, prescription information, or pharmacyal values. Some of the example will be like:\n"
                        "- I bought 100mg of paracetamol"
                        "- I bought 100mg of paracetamol from the pharmacy"
                "2. retrieve : Retrieve pharmacy data, medication entries, or specific nutrient information by category or date range.\n"
                "3. analyze : Analyze pharmacy trends, comparitive analysis, or do more complex data analysis and provide result (e.g., show trends in pharmacy intake and how to improve the medication intake).\n"
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

    def route_to_tasks(self, state: PharmacyAgentState) -> str:
        """Route to appropriate task based on analysis"""
        if state.has_error:
            return "error"

        if not state.task_types or state.task_types[0] == "unknown":
            return "error"

        task = state.task_types[0].lower()

        if task in ["update"]:
            return "update_pharmacy_records"
        elif task in ["retrieve"]:
            return "retrieve_pharmacy_data"
        elif task in ["analyze"]:
            return "analyze_pharmacy"
        else:
            return "error"

    async def _analyze_medication_image(self, state: PharmacyAgentState) -> Optional[Dict]:
        """Analyze medication image using GPT-4V"""
        try:
            print(f"🔍 [DEBUG] Analyzing medication image...")
            
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
            
            # Medication analysis prompt - using exact same format as lab extraction
            analysis_prompt = """Analyze this pharmacy bill image and extract detailed pharmacy and medication information. Please provide a comprehensive analysis following the EXACT JSON structure provided below.

        User Request: {original_prompt}
        User ID: {user_id}

        IMPORTANT: You MUST respond with the EXACT JSON structure shown below. Do not modify field names or structure.

        **FIELD EXPLANATIONS & EXTRACTION GUIDELINES:**

        **Pharmacy Information** (Company/Store Details):
        - pharmacy_name: Full registered business name of the pharmacy
        - pharmacy_address: Complete physical address where pharmacy is located
        - pharmacy_phone: Contact phone number (format: numbers only or with country code)
        - pharmacy_gstin: GST Identification Number (15-character alphanumeric code)
        - pharmacy_fssai_license: Food Safety and Standards Authority license number
        - pharmacy_dl_numbers: Drug License numbers (array of strings, can be multiple)
        - pharmacy_registration_address: Registered business address (may differ from premise)
        - pharmacy_premise_address: Physical premise address where business operates
        - pos_location: Point of Sale location/state for tax purposes
        - pharmacist_name: Licensed pharmacist's name
        - pharmacist_registration_number: Pharmacist's registration/license number

        **Bill Information** (Document Details):
        - bill_number: Unique bill/receipt number
        - bill_date: Date when bill was generated (YYYY-MM-DD format)
        - bill_type: Type of document (Tax Invoice, Cash Memo, Bill of Supply, etc.)
        - invoice_number: Invoice number (may be same as bill_number)
        - order_id: Online order ID if applicable
        - order_date: Date when order was placed
        - invoice_date: Date when invoice was generated

        **Financial Information** (Amounts and Calculations):
        - total_amount: Final amount to be paid by customer (= gross_amount + taxes + charges - discounts)
        - gross_amount: Sum of all item prices before taxes and discounts
        - taxable_amount: Amount on which tax is calculated (after discounts)
        - tax_amount: Total tax amount (= cgst_amount + sgst_amount + igst_amount)
        - discount_amount: Total discount given to customer
        - cgst_rate: Central GST rate (percentage, e.g., 9.0 for 9%)
        - cgst_amount: Central GST amount in rupees (= taxable_amount × cgst_rate / 100)
        - sgst_rate: State GST rate (percentage, e.g., 9.0 for 9%)
        - sgst_amount: State GST amount in rupees (= taxable_amount × sgst_rate / 100)
        - igst_rate: Integrated GST rate (percentage, used for interstate transactions)
        - igst_amount: Integrated GST amount in rupees
        - total_gst_amount: Total GST (= cgst_amount + sgst_amount + igst_amount)
        - shipping_charges: Delivery/shipping charges
        - vas_charges: Value Added Services charges
        - credits_applied: Store credits or cashback applied
        - payable_amount: Final amount to pay (usually same as total_amount)
        - amount_in_words: Amount written in words (e.g., "Five Hundred Rupees Only")

        **Patient Information** (Customer Details):
        - patient_name: Name of the patient/customer
        - patient_address: Patient's address
        - patient_contact: Patient's phone number or contact info

        **Prescription Information** (Medical Details):
        - prescription_number: Prescription reference number
        - prescribing_doctor: Name of the doctor who prescribed
        - doctor_address: Doctor's clinic/hospital address
        - place_of_supply: State/location for tax calculation purposes

        **Transaction Information** (Payment Details):
        - transaction_id: Payment transaction reference
        - payment_method: How payment was made (Cash, Card, UPI, etc.)
        - transaction_timestamp: When payment was processed
        - transaction_amount: Amount processed in transaction

        **Medication Details** (For Each Medicine):
        - medication_name: Complete product name as shown on bill
        - generic_name: Generic/scientific name of medicine
        - brand_name: Brand/commercial name
        - strength: Dosage strength (e.g., "500mg", "100ml")
        - quantity: Number of units purchased
        - unit_of_measurement: Unit type (tablets, ml, grams, etc.)
        - unit_price: Price per individual unit
        - total_price: Total cost for this medication (quantity × unit_price - discount + tax)
        - dosage_instructions: How to take the medicine
        - frequency: How often to take (e.g., "twice daily")
        - duration: For how long to take
        - manufacturer_name: Company that manufactured the medicine
        - hsn_code: Harmonized System of Nomenclature code for taxation
        - batch_number: Manufacturing batch identifier
        - expiry_date: When medicine expires (MM/YY format)
        - ndc_number: National Drug Code number
        - mrp: Maximum Retail Price
        - discount_amount: Discount applied to this item
        - taxable_amount: Amount on which tax is calculated for this item
        - gst_rate: GST rate applicable to this item (percentage)
        - gst_amount: Total GST for this item
        - cgst_rate: Central GST rate for this item
        - cgst_amount: Central GST amount for this item
        - sgst_rate: State GST rate for this item
        - sgst_amount: State GST amount for this item
        - igst_rate: Integrated GST rate for this item
        - igst_amount: Integrated GST amount for this item
        - prescription_validity_date: Until when prescription is valid
        - dispensing_dl_number: Drug license under which medicine was dispensed

        **MANDATORY JSON RESPONSE FORMAT** (You MUST use this exact structure):

        {{
            "user_id": "{user_id}",
            "pharmacy": {{
                "pharmacy_name": "TATA 1MG Healthcare Solutions Private Limited",
                "pharmacy_address": "Complete address from bill",
                "pharmacy_phone": "9900080830",
                "pharmacy_gstin": "29ABCDE1234F1Z5",
                "pharmacy_fssai_license": "12345678901234",
                "pharmacy_dl_numbers": ["DL-KA-20B-12345", "DL-KA-21B-67890"],
                "pharmacy_registration_address": "Registered address",
                "pharmacy_premise_address": "Premise address",
                "pos_location": "Karnataka",
                "pharmacist_name": "Dr. John Doe",
                "pharmacist_registration_number": "PHARM123456"
            }},
            "bill": {{
                "bill_number": "BILL001234",
                "bill_date": "{current_date}",
                "bill_type": "Tax Invoice",
                "invoice_number": "INV001234",
                "order_id": "ORD001234",
                "order_date": "{current_date}",
                "invoice_date": "{current_date}"
            }},
            "financial": {{
                "total_amount": 615.00,
                "gross_amount": 65.00,
                "taxable_amount": 549.11,
                "tax_amount": 65.90,
                "discount_amount": 59.00,
                "cgst_rate": 6.0,
                "cgst_amount": 32.95,
                "sgst_rate": 6.0,
                "sgst_amount": 32.95,
                "igst_rate": 0.0,
                "igst_amount": 0.0,
                "total_gst_amount": 65.90,
                "shipping_charges": 9.00,
                "vas_charges": 0.0,
                "credits_applied": 0.0,
                "payable_amount": 615.00,
                "amount_in_words": "Rupees six hundred and fifteen only"
            }},
            "patient": {{
                "patient_name": "rajanish",
                "patient_address": null,
                "patient_contact": null
            }},
            "prescription": {{
                "prescription_number": null,
                "prescribing_doctor": "Dr. Pulim Thulasi",
                "doctor_address": "Doctor's complete address",
                "place_of_supply": "Karnataka"
            }},
            "transaction": {{
                "transaction_id": null,
                "payment_method": null,
                "transaction_timestamp": null,
                "transaction_amount": null
            }},
            "additional": {{
                "support_contact": "care@1mg.com",
                "compliance_codes": null,
                "confidence_score": 0.95,
                "raw_text": "Complete bill text...",
                "file_name": "bill_filename.pdf"
            }},
            "medications": [
                {{
                    "medication_name": "Emolene Cream - 100gm",
                    "generic_name": null,
                    "brand_name": null,
                    "strength": "100gm",
                    "quantity": 1,
                    "unit_of_measurement": "unit",
                    "unit_price": null,
                    "total_price": 345.99,
                    "dosage_instructions": null,
                    "frequency": null,
                    "duration": null,
                    "manufacturer_name": "Fulford India Ltd",
                    "hsn_code": "30049099",
                    "batch_number": "D651224",
                    "expiry_date": "11/26",
                    "ndc_number": null,
                    "mrp": 380.0,
                    "discount_amount": 34.01,
                    "taxable_amount": 308.92,
                    "gst_rate": 12.0,
                    "gst_amount": 37.07,
                    "cgst_rate": 6.0,
                    "cgst_amount": 18.54,
                    "sgst_rate": 6.0,
                    "sgst_amount": 18.53,
                    "igst_rate": 0.0,
                    "igst_amount": 0.0,
                    "prescription_validity_date": null,
                    "dispensing_dl_number": null
                }}
            ]
        }}

        **CRITICAL INSTRUCTIONS:**
        1. Use the EXACT JSON structure above - do not change field names or nesting
        2. Calculate tax_amount as: cgst_amount + sgst_amount + igst_amount
        3. For intrastate: use CGST + SGST rates (e.g., 9% + 9% = 18% total)
        4. For interstate: use IGST rate (e.g., 18% IGST, CGST and SGST = 0)
        5. total_gst_amount should equal tax_amount
        6. Extract ALL medications from the bill
        7. Use null for missing values, not empty strings
        8. Ensure financial calculations are mathematically correct
        9. Extract exact text values as they appear on the bill""".format(
                original_prompt=state.original_prompt,
                user_id=state.user_id,
                current_date=now_local().strftime("%Y-%m-%d"),
                current_datetime=isoformat_now()
            )
            
            # Analyze image
            messages = [
                SystemMessage(content="You are an expert pharmacy bill analyzer who can extract detailed pharmacy, billing, and medication information from pharmacy bills and invoices."),
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
                
                pharmacy_data = json.loads(content)
                print(f"🔍 [DEBUG] Successfully extracted pharmacy from image: {len(pharmacy_data.get('medications', []))} medications")
                return pharmacy_data
                
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse image analysis JSON: {str(e)}")
                return None
                
        except Exception as e:
            print(f"🔍 [DEBUG] Error analyzing medication image: {str(e)}")
            return None

    async def _extract_from_text(self, state: PharmacyAgentState) -> Optional[Dict]:
        """Extract pharmacy data from text input"""
        try:
            print(f"🔍 [DEBUG] Extracting pharmacy from text...")
            
            extraction_prompt = """Analyze this pharmacy bill text and extract detailed pharmacy and medication information. Please provide a comprehensive analysis following the EXACT JSON structure provided below.

        User Request: {original_prompt}
        User ID: {user_id}

        IMPORTANT: You MUST respond with the EXACT JSON structure shown below. Do not modify field names or structure.

        **FIELD EXPLANATIONS & EXTRACTION GUIDELINES:**

        **Pharmacy Information** (Company/Store Details):
        - pharmacy_name: Full registered business name of the pharmacy
        - pharmacy_address: Complete physical address where pharmacy is located
        - pharmacy_phone: Contact phone number (format: numbers only or with country code)
        - pharmacy_gstin: GST Identification Number (15-character alphanumeric code)
        - pharmacy_fssai_license: Food Safety and Standards Authority license number
        - pharmacy_dl_numbers: Drug License numbers (array of strings, can be multiple)
        - pharmacy_registration_address: Registered business address (may differ from premise)
        - pharmacy_premise_address: Physical premise address where business operates
        - pos_location: Point of Sale location/state for tax purposes
        - pharmacist_name: Licensed pharmacist's name
        - pharmacist_registration_number: Pharmacist's registration/license number

        **Bill Information** (Document Details):
        - bill_number: Unique bill/receipt number
        - bill_date: Date when bill was generated (YYYY-MM-DD format)
        - bill_type: Type of document (Tax Invoice, Cash Memo, Bill of Supply, etc.)
        - invoice_number: Invoice number (may be same as bill_number)
        - order_id: Online order ID if applicable
        - order_date: Date when order was placed
        - invoice_date: Date when invoice was generated

        **Financial Information** (Amounts and Calculations):
        - total_amount: Final amount to be paid by customer (= gross_amount + taxes + charges - discounts)
        - gross_amount: Sum of all item prices before taxes and discounts
        - taxable_amount: Amount on which tax is calculated (after discounts)
        - tax_amount: Total tax amount (= cgst_amount + sgst_amount + igst_amount)
        - discount_amount: Total discount given to customer
        - cgst_rate: Central GST rate (percentage, e.g., 9.0 for 9%)
        - cgst_amount: Central GST amount in rupees (= taxable_amount × cgst_rate / 100)
        - sgst_rate: State GST rate (percentage, e.g., 9.0 for 9%)
        - sgst_amount: State GST amount in rupees (= taxable_amount × sgst_rate / 100)
        - igst_rate: Integrated GST rate (percentage, used for interstate transactions)
        - igst_amount: Integrated GST amount in rupees
        - total_gst_amount: Total GST (= cgst_amount + sgst_amount + igst_amount)
        - shipping_charges: Delivery/shipping charges
        - vas_charges: Value Added Services charges
        - credits_applied: Store credits or cashback applied
        - payable_amount: Final amount to pay (usually same as total_amount)
        - amount_in_words: Amount written in words (e.g., "Five Hundred Rupees Only")

        **Patient Information** (Customer Details):
        - patient_name: Name of the patient/customer
        - patient_address: Patient's address
        - patient_contact: Patient's phone number or contact info

        **Prescription Information** (Medical Details):
        - prescription_number: Prescription reference number
        - prescribing_doctor: Name of the doctor who prescribed
        - doctor_address: Doctor's clinic/hospital address
        - place_of_supply: State/location for tax calculation purposes

        **Transaction Information** (Payment Details):
        - transaction_id: Payment transaction reference
        - payment_method: How payment was made (Cash, Card, UPI, etc.)
        - transaction_timestamp: When payment was processed
        - transaction_amount: Amount processed in transaction

        **Medication Details** (For Each Medicine):
        - medication_name: Complete product name as shown on bill
        - generic_name: Generic/scientific name of medicine
        - brand_name: Brand/commercial name
        - strength: Dosage strength (e.g., "500mg", "100ml")
        - quantity: Number of units purchased
        - unit_of_measurement: Unit type (tablets, ml, grams, etc.)
        - unit_price: Price per individual unit
        - total_price: Total cost for this medication (quantity × unit_price - discount + tax)
        - dosage_instructions: How to take the medicine
        - frequency: How often to take (e.g., "twice daily")
        - duration: For how long to take
        - manufacturer_name: Company that manufactured the medicine
        - hsn_code: Harmonized System of Nomenclature code for taxation
        - batch_number: Manufacturing batch identifier
        - expiry_date: When medicine expires (MM/YY format)
        - ndc_number: National Drug Code number
        - mrp: Maximum Retail Price
        - discount_amount: Discount applied to this item
        - taxable_amount: Amount on which tax is calculated for this item
        - gst_rate: GST rate applicable to this item (percentage)
        - gst_amount: Total GST for this item
        - cgst_rate: Central GST rate for this item
        - cgst_amount: Central GST amount for this item
        - sgst_rate: State GST rate for this item
        - sgst_amount: State GST amount for this item
        - igst_rate: Integrated GST rate for this item
        - igst_amount: Integrated GST amount for this item
        - prescription_validity_date: Until when prescription is valid
        - dispensing_dl_number: Drug license under which medicine was dispensed

        **MANDATORY JSON RESPONSE FORMAT** (You MUST use this exact structure):

        {{
            "user_id": "{user_id}",
            "pharmacy": {{
                "pharmacy_name": "TATA 1MG Healthcare Solutions Private Limited",
                "pharmacy_address": "Complete address from bill",
                "pharmacy_phone": "9900080830",
                "pharmacy_gstin": "29ABCDE1234F1Z5",
                "pharmacy_fssai_license": "12345678901234",
                "pharmacy_dl_numbers": ["DL-KA-20B-12345", "DL-KA-21B-67890"],
                "pharmacy_registration_address": "Registered address",
                "pharmacy_premise_address": "Premise address",
                "pos_location": "Karnataka",
                "pharmacist_name": "Dr. John Doe",
                "pharmacist_registration_number": "PHARM123456"
            }},
            "bill": {{
                "bill_number": "BILL001234",
                "bill_date": "{current_date}",
                "bill_type": "Tax Invoice",
                "invoice_number": "INV001234",
                "order_id": "ORD001234",
                "order_date": "{current_date}",
                "invoice_date": "{current_date}"
            }},
            "financial": {{
                "total_amount": 615.00,
                "gross_amount": 65.00,
                "taxable_amount": 549.11,
                "tax_amount": 65.90,
                "discount_amount": 59.00,
                "cgst_rate": 6.0,
                "cgst_amount": 32.95,
                "sgst_rate": 6.0,
                "sgst_amount": 32.95,
                "igst_rate": 0.0,
                "igst_amount": 0.0,
                "total_gst_amount": 65.90,
                "shipping_charges": 9.00,
                "vas_charges": 0.0,
                "credits_applied": 0.0,
                "payable_amount": 615.00,
                "amount_in_words": "Rupees six hundred and fifteen only"
            }},
            "patient": {{
                "patient_name": "rajanish",
                "patient_address": null,
                "patient_contact": null
            }},
            "prescription": {{
                "prescription_number": null,
                "prescribing_doctor": "Dr. Pulim Thulasi",
                "doctor_address": "Doctor's complete address",
                "place_of_supply": "Karnataka"
            }},
            "transaction": {{
                "transaction_id": null,
                "payment_method": null,
                "transaction_timestamp": null,
                "transaction_amount": null
            }},
            "additional": {{
                "support_contact": "care@1mg.com",
                "compliance_codes": null,
                "confidence_score": 0.95,
                "raw_text": "Complete bill text...",
                "file_name": "bill_filename.pdf"
            }},
            "medications": [
                {{
                    "medication_name": "Emolene Cream - 100gm",
                    "generic_name": null,
                    "brand_name": null,
                    "strength": "100gm",
                    "quantity": 1,
                    "unit_of_measurement": "unit",
                    "unit_price": null,
                    "total_price": 345.99,
                    "dosage_instructions": null,
                    "frequency": null,
                    "duration": null,
                    "manufacturer_name": "Fulford India Ltd",
                    "hsn_code": "30049099",
                    "batch_number": "D651224",
                    "expiry_date": "11/26",
                    "ndc_number": null,
                    "mrp": 380.0,
                    "discount_amount": 34.01,
                    "taxable_amount": 308.92,
                    "gst_rate": 12.0,
                    "gst_amount": 37.07,
                    "cgst_rate": 6.0,
                    "cgst_amount": 18.54,
                    "sgst_rate": 6.0,
                    "sgst_amount": 18.53,
                    "igst_rate": 0.0,
                    "igst_amount": 0.0,
                    "prescription_validity_date": null,
                    "dispensing_dl_number": null
                }}
            ]
        }}

        **CRITICAL INSTRUCTIONS:**
        1. Use the EXACT JSON structure above - do not change field names or nesting
        2. Calculate tax_amount as: cgst_amount + sgst_amount + igst_amount
        3. For intrastate: use CGST + SGST rates (e.g., 9% + 9% = 18% total)
        4. For interstate: use IGST rate (e.g., 18% IGST, CGST and SGST = 0)
        5. total_gst_amount should equal tax_amount
        6. Extract ALL medications from the bill
        7. Use null for missing values, not empty strings
        8. Ensure financial calculations are mathematically correct
        9. Extract exact text values as they appear on the bill""".format(
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
                
                pharmacy_data = json.loads(cleaned_content)
                print(f"🔍 [DEBUG] Successfully extracted pharmacy from text: {len(pharmacy_data.get('medications', []))} medications")
                return pharmacy_data
                
            except json.JSONDecodeError as e:
                print(f"🔍 [DEBUG] Failed to parse text extraction JSON: {str(e)}")
                return None
                
        except Exception as e:
            print(f"🔍 [DEBUG] Error extracting from text: {str(e)}")
            return None

    async def update_pharmacy_records(self, state: PharmacyAgentState) -> PharmacyAgentState:
        """Handle pharmacy bill data updates including bill information and medications"""
        self.log_execution_step(state, "update_pharmacy_records", "started")
        try:
            # Check if we have an image to analyze
            if state.image_path or state.image_base64:
                # Use image-based pharmacy bill recognition
                pharmacy_data = await self._analyze_medication_image(state)
            else:
                # Use text-based extraction
                pharmacy_data = await self._extract_from_text(state)
            
            if not pharmacy_data:
                state.has_error = True
                state.error_context = {
                    "error_type": "extraction_failed",
                    "node": "update_pharmacy_records",
                    "message": "Failed to extract pharmacy bill data from input",
                }
                return state
            
            print(f"🔍 [DEBUG] Successfully extracted pharmacy data with {len(pharmacy_data.get('medications', []))} medication entries")

            # Prepare pharmacy bill record - handle nested JSON structure
            user_id = state.user_id
            # Use server-side local timezone in inserts; keep current_time for client-side mirrors if needed
            current_time = isoformat_now()
            
            pharmacy_info = pharmacy_data.get("pharmacy", {})
            bill_info = pharmacy_data.get("bill", {})
            financial_info = pharmacy_data.get("financial", {})
            patient_info = pharmacy_data.get("patient", {})
            prescription_info = pharmacy_data.get("prescription", {})
            transaction_info = pharmacy_data.get("transaction", {})
            additional_info = pharmacy_data.get("additional", {})
            
            pharmacy_bill_record = {
                "user_id": user_id,
                # Pharmacy information
                "pharmacy_name": pharmacy_info.get("pharmacy_name") or "Unknown Pharmacy",  # Default value to prevent null constraint
                "pharmacy_address": pharmacy_info.get("pharmacy_address"),
                "pharmacy_phone": pharmacy_info.get("pharmacy_phone"),
                "pharmacy_gstin": pharmacy_info.get("pharmacy_gstin"),
                "pharmacy_fssai_license": pharmacy_info.get("pharmacy_fssai_license"),
                "pharmacy_dl_numbers": pharmacy_info.get("pharmacy_dl_numbers"),
                "pharmacy_registration_address": pharmacy_info.get("pharmacy_registration_address"),
                "pharmacy_premise_address": pharmacy_info.get("pharmacy_premise_address"),
                "pos_location": pharmacy_info.get("pos_location"),
                "pharmacist_name": pharmacy_info.get("pharmacist_name"),
                "pharmacist_registration_number": pharmacy_info.get("pharmacist_registration_number"),
                # Bill information
                "bill_number": bill_info.get("bill_number"),
                "bill_date": bill_info.get("bill_date"),
                "bill_type": bill_info.get("bill_type"),
                "invoice_number": bill_info.get("invoice_number"),
                "order_id": bill_info.get("order_id"),
                "order_date": bill_info.get("order_date"),
                "invoice_date": bill_info.get("invoice_date"),
                # Financial information
                "total_amount": financial_info.get("total_amount"),
                "gross_amount": financial_info.get("gross_amount"),
                "taxable_amount": financial_info.get("taxable_amount"),
                "tax_amount": financial_info.get("tax_amount"),
                "discount_amount": financial_info.get("discount_amount"),
                "cgst_rate": financial_info.get("cgst_rate"),
                "cgst_amount": financial_info.get("cgst_amount"),
                "sgst_rate": financial_info.get("sgst_rate"),
                "sgst_amount": financial_info.get("sgst_amount"),
                "igst_rate": financial_info.get("igst_rate"),
                "igst_amount": financial_info.get("igst_amount"),
                "total_gst_amount": financial_info.get("total_gst_amount"),
                "shipping_charges": financial_info.get("shipping_charges"),
                "vas_charges": financial_info.get("vas_charges"),
                "credits_applied": financial_info.get("credits_applied"),
                "payable_amount": financial_info.get("payable_amount"),
                "amount_in_words": financial_info.get("amount_in_words"),
                # Patient information
                "patient_name": patient_info.get("patient_name"),
                "patient_address": patient_info.get("patient_address"),
                "patient_contact": patient_info.get("patient_contact"),
                # Prescription information
                "prescription_number": prescription_info.get("prescription_number"),
                "prescribing_doctor": prescription_info.get("prescribing_doctor"),
                "doctor_address": prescription_info.get("doctor_address"),
                "place_of_supply": prescription_info.get("place_of_supply"),
                # Transaction information
                "transaction_id": transaction_info.get("transaction_id"),
                "payment_method": transaction_info.get("payment_method"),
                "transaction_timestamp": transaction_info.get("transaction_timestamp"),
                "transaction_amount": transaction_info.get("transaction_amount"),
                # Additional information
                "support_contact": additional_info.get("support_contact"),
                "compliance_codes": additional_info.get("compliance_codes"),
                "confidence_score": additional_info.get("confidence_score", 0.8),
                "raw_text": additional_info.get("raw_text"),
                "pharmacybill_filepath": state.source_file_path,  # Updated field name to match database schema
                "created_at": current_time,
                "updated_at": current_time
            }

            # Debug logging to see what we're trying to insert
            print(f"🔍 [DEBUG] Pharmacy bill record to insert: {json.dumps(pharmacy_bill_record, indent=2)}")

            # Insert pharmacy bill and get the bill_id
            bill_result = self._insert_pharmacy_bill(pharmacy_bill_record)
            
            if not bill_result.get("success"):
                state.has_error = True
                state.error_context = {
                    "error_type": "bill_insertion_failed",
                    "node": "update_pharmacy_records",
                    "message": f"Failed to insert pharmacy bill: {bill_result.get('error')}",
                }
                return state

            bill_id = bill_result.get("bill_id")
            print(f"🔍 [DEBUG] Successfully inserted pharmacy bill with ID: {bill_id}")

            # Prepare medication records
            medication_entries = pharmacy_data.get("medications", [])
            medication_records = []
            
            if not medication_entries:
                state.has_error = True
                state.error_context = {
                    "error_type": "no_medication_entries_found",
                    "node": "update_pharmacy_records",
                    "message": "No medication entries found in extracted pharmacy data.",
                    "context": {"pharmacy_data": pharmacy_data}
                }
                return state

            # Create medication records with bill_id reference
            for medication_entry in medication_entries:
                medication_record = {
                    "bill_id": bill_id,
                    "user_id": user_id,
                    "medication_name": medication_entry.get("medication_name"),
                    "generic_name": medication_entry.get("generic_name"),
                    "brand_name": medication_entry.get("brand_name"),
                    "strength": medication_entry.get("strength"),
                    "quantity": medication_entry.get("quantity"),
                    "unit_of_measurement": medication_entry.get("unit_of_measurement"),
                    "unit_price": medication_entry.get("unit_price"),
                    "total_price": medication_entry.get("total_price"),
                    "dosage_instructions": medication_entry.get("dosage_instructions"),
                    "frequency": medication_entry.get("frequency"),
                    "duration": medication_entry.get("duration"),
                    "manufacturer_name": medication_entry.get("manufacturer_name"),
                    "hsn_code": medication_entry.get("hsn_code"),
                    "batch_number": medication_entry.get("batch_number"),
                    "expiry_date": medication_entry.get("expiry_date"),
                    "ndc_number": medication_entry.get("ndc_number"),
                    "mrp": medication_entry.get("mrp"),
                    "discount_amount": medication_entry.get("discount_amount"),
                    "taxable_amount": medication_entry.get("taxable_amount"),
                    "gst_rate": medication_entry.get("gst_rate"),
                    "gst_amount": medication_entry.get("gst_amount"),
                    "cgst_rate": medication_entry.get("cgst_rate"),
                    "cgst_amount": medication_entry.get("cgst_amount"),
                    "sgst_rate": medication_entry.get("sgst_rate"),
                    "sgst_amount": medication_entry.get("sgst_amount"),
                    "igst_rate": medication_entry.get("igst_rate"),
                    "igst_amount": medication_entry.get("igst_amount"),
                    "prescription_validity_date": medication_entry.get("prescription_validity_date"),
                    "dispensing_dl_number": medication_entry.get("dispensing_dl_number"),
                    "created_at": current_time,
                    "updated_at": current_time
                }
                medication_records.append(medication_record)

            # Insert medications
            medications_result = self._insert_pharmacy_medications(medication_records)
            
            if not medications_result.get("success"):
                state.has_error = True
                state.error_context = {
                    "error_type": "medications_insertion_failed",
                    "node": "update_pharmacy_records",
                    "message": f"Failed to insert medications: {medications_result.get('error')}",
                }
                return state

            print(f"🔍 [DEBUG] Successfully inserted {len(medication_records)} medications")

            # Set extracted data for response
            state.extracted_pharmacy_data = {
                "pharmacy_bill": pharmacy_bill_record,
                "medications": medication_records,
                "bill_id": bill_id
            }

            # Combine results
            combined_result = {
                "pharmacy_bill": bill_result,
                "medications": medications_result,
                "total_medications": len(medication_records),
                "bill_id": bill_id
            }
            
            # Store results
            state.update_results = combined_result
            self.log_execution_step(state, "update_pharmacy_records", "completed", {"combined_result": combined_result})
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "exception",
                "node": "update_pharmacy_records",
                "message": str(e),
            }
            self.log_execution_step(state, "update_pharmacy_records", "failed", {"error": str(e)})
        return state

    async def retrieve_pharmacy_data(self, state: PharmacyAgentState) -> PharmacyAgentState:
        """LangGraph-based retrieval workflow using agent reasoning"""
        self.log_execution_step(state, "retrieve_pharmacy_data", "started")
        try:
            user_request = state.original_prompt + " for the user_id: " + str(state.user_id)
            print(f"DEBUG: Calling LangGraph pharmacy retrieval agent with request: {user_request}")
            
            # Use the LangGraph-based retrieval agent (maintains same logic as ReAct agent)
            result = await self._use_advanced_retrieval(user_request)
            
            print(f"DEBUG: LangGraph pharmacy agent returned: {result}")
            
            state.query_results = result
            self.log_execution_step(state, "retrieve_pharmacy_data", "completed", {"results": result})
        except Exception as e:
            print(f"DEBUG: Exception in retrieve_pharmacy_data: {str(e)}")
            import traceback
            traceback.print_exc()
            state.has_error = True
            state.error_context = {
                "error_type": "sql_generation_or_execution",
                "node": "retrieve_pharmacy_data",
                "message": str(e),
            }
            self.log_execution_step(state, "retrieve_pharmacy_data", "failed", {"error": str(e)})
        return state

    async def analyze_pharmacy(self, state: PharmacyAgentState) -> PharmacyAgentState:
        """
        Analyze patterns and derive trends from pharmacy data using the analyze workflow.
        
        This method leverages the PharmacyAnalyzeWorkflow to:
        1. Analyze the user's request for analysis type
        2. Query relevant pharmacy data 
        3. Generate Python code for the specific analysis
        4. Execute the code safely with the data
        5. Format results with interpretations
        """
        try:
            self.log_execution_step(state, "analyze_pharmacy", "started")
            
            # Use the shared code interpreter instance for better performance
            analysis_results = await self.code_interpreter.run(
                request=state.original_prompt,
                user_id=state.user_id
            )
            
            # Store the analysis results in the state
            state.pharmacy_analysis = analysis_results
            
            # Log success with details
            if analysis_results.get("success", True):  # Default to True if not specified
                self.log_execution_step(state, "analyze_pharmacy", "completed", {
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
                    "node": "analyze_pharmacy", 
                    "message": analysis_results.get("error", "Code interpreter failed"),
                    "context": {
                        "step_failed": analysis_results.get("step_failed"),
                        "suggestions": analysis_results.get("suggestions", [])
                    }
                }
                self.log_execution_step(state, "analyze_pharmacy", "failed", {
                    "error": analysis_results.get("error"),
                    "step_failed": analysis_results.get("step_failed")
                })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "technical",
                "node": "analyze_pharmacy",
                "message": f"Code interpreter workflow failed: {str(e)}",
                "context": {"exception_type": type(e).__name__}
            }
            self.log_execution_step(state, "analyze_pharmacy", "failed", {"error": str(e)})
        
        return state

    async def handle_error(self, state: PharmacyAgentState) -> PharmacyAgentState:
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

    async def format_response(self, state: PharmacyAgentState) -> PharmacyAgentState:
        """Format the final response based on the completed tasks"""
        try:
            if state.has_error:
                # Error response already handled in handle_error
                return state
            
            if not state.has_error and not state.response_data:
                # Format response based on task type (match lab agent)
                results = {}
                if state.extracted_pharmacy_data:
                    results["extracted_data"] = state.extracted_pharmacy_data
                if state.query_results:
                    results["query_results"] = state.query_results
                if state.update_results:
                    results["update_results"] = state.update_results
                if state.pharmacy_analysis:
                    # Extract the actual results from workflow and put directly in results
                    if isinstance(state.pharmacy_analysis, dict) and state.pharmacy_analysis.get("success"):
                        # Use the workflow's results directly without the wrapper
                        results = state.pharmacy_analysis.get("results", {})
                        
                        # Ensure visualizations are included at the top level
                        if "visualizations" in state.pharmacy_analysis:
                            results["visualizations"] = state.pharmacy_analysis["visualizations"]
                        
                    else:
                        results["analysis_error"] = "Pharmacy analysis workflow failed"
                
                # Use shared response formatter with visualization support
                state.response_data = format_agent_response(
                    success=True,
                    task_types=state.task_types,
                    results=results,
                    execution_log=state.execution_log,
                    message="Pharmacy analysis completed successfully"
                )
            
        except Exception as e:
            # Use shared error formatter
            state.response_data = format_error_response(
                error_message=f"Error formatting response: {str(e)}",
                execution_log=state.execution_log,
                task_types=state.task_types
            )
        
        return state

    async def process_request(self, prompt: str, user_id: int, session_id: int = 1, image_path: str = None, image_base64: str = None, extracted_text: str = None, source_file_path: str = None) -> Dict:
        """Process a request through the agent workflow - compatibility wrapper for run method"""
        return await self.run(
            prompt=prompt,
            user_id=user_id,
            extracted_text=extracted_text,
            image_path=image_path,
            image_base64=image_base64,
            source_file_path=source_file_path
        )

    async def run(self, prompt: str, user_id: int, extracted_text: str = None, image_path: str = None, image_base64: str = None, source_file_path: str = None) -> Dict[str, Any]:
        """
        Execute the pharmacy agent workflow.
        
        Args:
            prompt: The user's pharmacy request
            user_id: User ID for data operations
            extracted_text: Optional extracted text from documents
            image_path: Optional path to medication image
            image_base64: Optional base64 encoded image data
            
        Returns:
            Dict containing the results
        """
        try:
            # Initialize state
            initial_state = PharmacyAgentState(
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
                    "configurable": {"thread_id": f"pharmacy-agent-{user_id}"},
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
                    
                if result.get("extracted_pharmacy_data"):
                    results_data["extracted_pharmacy_data"] = result["extracted_pharmacy_data"]
                    
                if result.get("pharmacy_analysis"):
                    results_data["pharmacy_analysis"] = result["pharmacy_analysis"]

                # Use standard response format with visualization support
                from app.agentsv2.response_utils import format_agent_response
                response = format_agent_response(
                    success=not result.get("has_error", False),
                    task_types=result.get("task_types", ["pharmacy_analysis"]),
                    results=results_data,
                    execution_log=result.get("execution_log", []),
                    message="Pharmacy analysis completed successfully",
                    title="Pharmacy Analysis",
                    error=result.get("error_context", {}).get("message") if result.get("has_error") else None
                )
                return response
            # All agents should return response_data consistently
            # The format_response method sets this using format_agent_response()
            if result.response_data:
                print(f"✅ [DEBUG] Pharmacy agent returning standardized response_data")
                return result.response_data
            
            # If no response_data, this indicates a workflow issue - should not happen
            print(f"⚠️ [DEBUG] Pharmacy agent missing response_data - this should not happen")
            from app.agentsv2.response_utils import format_error_response
            return format_error_response(
                error_message="Pharmacy agent workflow completed but no response data was generated",
                execution_log=getattr(result, 'execution_log', []),
                task_types=getattr(result, 'task_types', ["unknown"])
            )
            
        except Exception as e:
            logger.error(f"Pharmacy agent workflow failed: {str(e)}")
            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}",
                "error_type": "technical",
                "context": {"exception_type": type(e).__name__}
            }

    def _parse_expiry_date(self, date_str):
        """Parse expiry date from MM/YY format to proper date format"""
        if not date_str or date_str in ["", "null", None]:
            return None
            
        try:
            # Handle MM/YY format (e.g., "11/26" -> "2026-11-01")
            if '/' in date_str and len(date_str.split('/')) == 2:
                month, year = date_str.split('/')
                
                # Convert 2-digit year to 4-digit year
                if len(year) == 2:
                    current_year = now_local().year
                    current_century = current_year // 100
                    year_int = int(year)
                    
                    # If year is less than current year's last 2 digits, assume next century
                    if year_int < (current_year % 100):
                        full_year = (current_century + 1) * 100 + year_int
                    else:
                        full_year = current_century * 100 + year_int
                else:
                    full_year = int(year)
                
                # Create date string in YYYY-MM-DD format (use first day of month)
                month_int = int(month)
                if 1 <= month_int <= 12:
                    return f"{full_year:04d}-{month_int:02d}-01"
                    
            # Handle other date formats if needed
            # For now, return None if format is not recognized
            return None
            
        except (ValueError, IndexError):
            # If parsing fails, return None
            return None

    def _insert_pharmacy_bill(self, bill_data: dict) -> dict:
        """Insert a pharmacy bill record and return the bill_id"""
        try:
            def clean_value(value):
                return None if value == "" else value

            cleaned = {key: clean_value(value) for key, value in bill_data.items()}

            with get_raw_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Prepare all fields for pharmacy_bills table
                    fields = [
                'user_id', 'pharmacy_name', 'pharmacy_address', 'pharmacy_phone',
                'pharmacy_gstin', 'pharmacy_fssai_license', 'pharmacy_dl_numbers',
                'pharmacy_registration_address', 'pharmacy_premise_address', 'pos_location',
                'pharmacist_name', 'pharmacist_registration_number', 'bill_number',
                'bill_date', 'bill_type', 'invoice_number', 'order_id', 'order_date',
                'invoice_date', 'total_amount', 'gross_amount', 'taxable_amount',
                'tax_amount', 'discount_amount', 'cgst_rate', 'cgst_amount',
                'sgst_rate', 'sgst_amount', 'igst_rate', 'igst_amount',
                'total_gst_amount', 'shipping_charges', 'vas_charges', 'credits_applied',
                'payable_amount', 'amount_in_words', 'patient_name', 'patient_address',
                'patient_contact', 'prescription_number', 'prescribing_doctor',
                'doctor_address', 'place_of_supply', 'transaction_id', 'payment_method',
                'transaction_timestamp', 'transaction_amount', 'support_contact',
                'compliance_codes', 'confidence_score', 'raw_text',
                'pharmacybill_filepath', 'created_at', 'updated_at'
            ]
            
                    values = [cleaned.get(f, None) for f in fields]

            # Convert lists to JSON strings for PostgreSQL
                    for i, field in enumerate(fields):
                        if field in ['pharmacy_dl_numbers', 'compliance_codes'] and values[i] is not None:
                            if isinstance(values[i], list):
                                values[i] = json.dumps(values[i])

            # Insert pharmacy bill
                    insert_fields = ', '.join(fields)
                    insert_placeholders = ', '.join(['%s'] * len(fields))
                    tz = settings.DEFAULT_TIMEZONE
                    insert_query = f"""
                        INSERT INTO pharmacy_bills ({insert_fields})
                        VALUES ({insert_placeholders})
                        RETURNING id
                    """
            
                    cursor.execute(insert_query, values)
                    bill_id = cursor.fetchone()[0]
                    
                    return {"success": True, "action": "inserted", "bill_id": bill_id}
            
        except Exception as e:
            return {"success": False, "action": "error", "error": str(e)}

    def _insert_pharmacy_medications(self, medications_data: list) -> dict:
        """Insert multiple medication records for a pharmacy bill"""
        try:
            if not medications_data:
                return {"success": True, "action": "no_medications", "inserted_count": 0}

            with get_raw_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Prepare all fields for pharmacy_medications table
                    fields = [
                'bill_id', 'user_id', 'medication_name', 'generic_name', 'brand_name',
                'strength', 'quantity', 'unit_of_measurement', 'unit_price', 'total_price',
                'dosage_instructions', 'frequency', 'duration', 'manufacturer_name',
                'hsn_code', 'batch_number', 'expiry_date', 'ndc_number', 'mrp',
                'discount_amount', 'taxable_amount', 'gst_rate', 'gst_amount',
                'cgst_rate', 'cgst_amount', 'sgst_rate', 'sgst_amount',
                'igst_rate', 'igst_amount', 'prescription_validity_date',
                'dispensing_dl_number', 'created_at', 'updated_at'
                    ]
            
                    # Prepare batch insert
                    insert_fields = ', '.join(fields)
                    insert_placeholders = ', '.join(['%s'] * len(fields))
                    tz = settings.DEFAULT_TIMEZONE
                    insert_query = f"""
                        INSERT INTO pharmacy_medications ({insert_fields})
                        VALUES ({insert_placeholders})
                        RETURNING id
                    """
            
                    inserted_ids = []
                    
                    for medication_data in medications_data:
                        def clean_value(value):
                            return None if value == "" else value

                        # Clean the data and handle special date parsing
                        cleaned = {key: clean_value(value) for key, value in medication_data.items()}
                        
                        # Special handling for expiry_date
                        if 'expiry_date' in cleaned:
                            cleaned['expiry_date'] = self._parse_expiry_date(cleaned['expiry_date'])
                        
                        # Special handling for prescription_validity_date if needed
                        if 'prescription_validity_date' in cleaned:
                            cleaned['prescription_validity_date'] = self._parse_expiry_date(cleaned['prescription_validity_date'])
                        
                        values = [cleaned.get(f, None) for f in fields]
                        
                        cursor.execute(insert_query, values)
                        medication_id = cursor.fetchone()[0]
                        inserted_ids.append(medication_id)
                    
                    conn.commit()
            
            return {
                "success": True, 
                "action": "inserted", 
                "inserted_count": len(inserted_ids),
                "medication_ids": inserted_ids
            }
            
        except Exception as e:
            return {"success": False, "action": "error", "error": str(e)}

    async def _use_advanced_retrieval(self, user_request: str) -> Dict[str, Any]:
        """Use LangGraph ReAct agent for retrieval (same logic as original ReAct agent)"""
        try:
            # Create a ReAct agent using LangGraph (replaces initialize_agent)
            agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                prompt=PHARMACY_SQL_GENERATION_SYSTEM_PROMPT
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
    
    agent = PharmacyAgentLangGraph()
    
    test_prompts = [
        "update my pharmacy data for the user"
    ]
    file_path = "/Users/rajanishsd/Documents/zivohealth-1/backend/data/uploads/pharmacy/78aa86c2-adc4-4594-8ef0-e258f0bdbd46.pdf"
    async def main():
        for prompt in test_prompts:
            print(f"\n--- Testing prompt: {prompt} ---")
            result = await agent.run(prompt, user_id=1, file_path=file_path)
            print(f"Result: {json.dumps(result, indent=2)}")
    
    asyncio.run(main()) 