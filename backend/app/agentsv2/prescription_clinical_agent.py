from pathlib import Path
import sys
from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import base64
import uuid

from dotenv import load_dotenv
load_dotenv()

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI
from app.core.config import settings
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode, tools_condition, create_react_agent
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage, HumanMessage
from typing import Annotated, Sequence
import operator
import re
import os

# Import models
from app.models.chat_session import Prescription
from app.models.clinical_notes import ClinicalNotes
from app.db.session import SessionLocal

# Import vitals and lab agents
from app.agentsv2.vitals_agent import VitalsAgentLangGraph
from app.agentsv2.lab_agent import LabAgentLangGraph

load_dotenv()

SQL_GENERATION_SYSTEM_PROMPT = """
You are an intelligent medical prescription and clinical data assistant. You must follow these TABLE SELECTION RULES strictly:

⚠️ REASONING REQUIREMENT ⚠️
BEFORE EVERY TOOL CALL, you MUST explain your reasoning:
1. Why you are selecting this specific tool
2. What information you hope to get from this tool
3. How this tool call fits into your overall strategy
4. What you will do with the results

EXAMPLE FORMAT:
"I need to understand the user's request for diabetes medications. Let me start by examining the prescriptions table schema to understand what columns are available, then I'll search for diabetes-related medications using my medical knowledge."

CRITICAL TABLE SELECTION RULES:
1. For prescribed medications: Use prescriptions table (main source)
2. For pharmacy purchases: Use pharmacy_bills and pharmacy_medications tables
3. For clinical notes and diagnoses: Use clinical_notes table
4. For comprehensive clinical reports: Use clinical_reports table
5. For recent medication history: Use prescriptions with date filters

AVAILABLE TABLES:
- prescriptions: Main prescription records (medication_name, dosage, frequency, instructions, duration, prescribed_by, prescribed_at)
- clinical_notes: Clinical notes and diagnoses (diagnosis, symptoms_presented, doctor_observations, treatment_plan, follow_up_recommendations)
- pharmacy_medications: Medication details, costs, and prescription details that were purchased at the pharmacy. This includes medication that were not prescribed by a doctor or taken over the counter. There will overlap with prescriptions table.

SEARCH STRATEGY:
- For medication-based requests, use BOTH medication_name AND generic_name filters with OR logic
- Retrieve unique medication names from prescriptions table to understand what medications are available for the user
- Use your medical knowledge to identify relevant medication names and therapeutic categories
- For clinical conditions, search clinical_notes for diagnosis and symptoms_presented fields
- For prescription analysis, use the prescriptions table to understand the medication history and trends

Your job is to:
1. FIRST: Analyze the request and identify whether it's about prescriptions, clinical notes, or pharmacy data
2. SECOND: **EXPLAIN YOUR REASONING** before calling DescribeTableSchema - why this table?
3. THIRD: Use DescribeTableSchema tool to get column names for your selected table(s)
4. FOURTH: Generate SQL query using the CORRECT table(s) using the user_id and identify DISTINCT medication names and categories from the relevant tables. Do not specify conditions initially as you are exploring what medications/data are available
5. FIFTH: Use the medication names and your medical knowledge to identify the most relevant medications/clinical data that meets the user request and generate a targeted select query with LIKE operator instead of exact match to retrieve the results. Always filter by user_id.
6. SIXTH: Return query results in structured JSON format along with the reasoning for the response in the output field
7. SEVENTH: BE PROACTIVE - don't ask user what to do, try multiple approaches until you find results.
8. EIGHTH: **FINAL REASONING**: Always end your response with a summary of your decision-making process and what you found

REASONING EXAMPLES:
- "I'm selecting the prescriptions table because the user asked for 'diabetes medications' and this table contains all prescribed medications with their therapeutic details."
- "I'm looking for heart medications, so I'll search for both 'cardiac' conditions in clinical_notes AND specific medication names like metoprolol, lisinopril, atorvastatin which are commonly prescribed for cardiovascular conditions."
- "Since my first query in prescriptions returned limited results, I'll also check pharmacy_medications to see if the user purchased any heart medications from pharmacies."

ADVANCED SQL CAPABILITIES:
You can use sophisticated SQL features for better analysis:
- WITH clauses (CTEs) for complex multi-step queries
- Window functions for ranking and analytics
- JOINs across multiple tables (e.g., prescriptions JOIN clinical_notes)
- Subqueries and CASE statements
- Aggregation functions (COUNT, SUM, AVG, etc.)
- EXPLAIN to understand query performance

EXAMPLES OF ADVANCED QUERIES:
- WITH recent_prescriptions AS (SELECT * FROM prescriptions WHERE prescribed_at >= CURRENT_DATE - INTERVAL '6 months') SELECT medication_name, COUNT(*) FROM recent_prescriptions GROUP BY medication_name
- SELECT p.*, cn.diagnosis FROM prescriptions p LEFT JOIN clinical_notes cn ON p.user_id = cn.user_id WHERE p.medication_name ILIKE '%diabetes%'
- SELECT *, ROW_NUMBER() OVER (PARTITION BY medication_name ORDER BY prescribed_at DESC) as rank FROM prescriptions WHERE user_id = ? ORDER BY prescribed_at DESC

TIME-BASED QUERIES:
- Recent prescriptions: prescribed_at >= CURRENT_DATE - INTERVAL '30 days'
- Long-term medications: duration ILIKE '%chronic%' OR duration ILIKE '%ongoing%'
- Historical analysis: GROUP BY DATE_TRUNC('month', prescribed_at)
"""

@dataclass
class PrescriptionClinicalAgentState:
    """State for the prescription clinical agent workflow"""
    # Input parameters
    original_prompt: str
    user_id: int
    session_id: int = 1
    image_path: Optional[str] = None  # Path for processing (only if no extracted_text)
    image_base64: Optional[str] = None
    extracted_text: Optional[str] = None
    source_file_path: Optional[str] = None  # Original file path for storage/record-keeping
    
    # Workflow control
    task_types: List[str] = field(default_factory=list)
    intent_reason: str = ""
    component_analysis: Optional[Dict] = None
    
    # Data storage
    extracted_prescription_data: Optional[Dict] = None
    extracted_clinical_data: Optional[Dict] = None
    extracted_vitals_data: Optional[Dict] = None
    extracted_lab_data: Optional[Dict] = None
    storage_results: Optional[List[Dict]] = None
    query_results: Optional[Any] = None
    
    # Error handling
    has_error: bool = False
    error_context: Optional[Dict] = None
    
    # Response
    response_data: Optional[Dict] = None
    
    # Execution tracking
    execution_log: List[Dict] = field(default_factory=list)


class PrescriptionClinicalAgentLangGraph:
    """LangGraph agent for prescription and clinical data processing (same approach as lab agent)"""
    
    def __init__(self):
        # Configure LangSmith if available
        if settings.LANGCHAIN_TRACING_V2:
            os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
            if settings.LANGCHAIN_ENDPOINT:
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
            if settings.LANGCHAIN_PROJECT:
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

        # Use global configs with fallbacks
        self.llm = ChatOpenAI(
            model=settings.PRESCRIPTION_CLINICAL_AGENT_MODEL or settings.DEFAULT_AI_MODEL,
            api_key=settings.OPENAI_API_KEY
        )
        self.vision_llm = ChatOpenAI(
            model=settings.PRESCRIPTION_CLINICAL_VISION_MODEL or "gpt-4o",
            api_key=settings.OPENAI_API_KEY,
            max_tokens=settings.PRESCRIPTION_CLINICAL_VISION_MAX_TOKENS or 4000
        )
        
        # Initialize vitals and lab agents for processing respective data
        self.vitals_agent = VitalsAgentLangGraph()
        self.lab_agent = LabAgentLangGraph()
        
        # Create tools and workflow
        self.tools = self._create_tools()
        self.workflow = self._build_workflow()

    def _create_tools(self):
        """Create LangGraph tools for database operations (same as lab agent)"""
        
        @tool
        async def query_prescription_clinical_db(query: str) -> str:
            """Execute a read-only SQL query on prescription and clinical notes tables.
            
            SUPPORTED OPERATIONS: SELECT, WITH (CTEs), EXPLAIN, DESCRIBE, SHOW
            SUPPORTS: Complex queries, CTEs, subqueries, JOINs, aggregations, window functions
            
            BEFORE CALLING: Always explain your reasoning for this specific query:
            - Why you selected this table (prescriptions vs clinical_notes)
            - What medical information you're searching for
            - How this relates to the user's medical request
            
            Args:
                query: SQL query statement to execute (read-only operations only)
                
            Returns:
                JSON string of query results
            """
            try:
                # Clean up query string (same as lab agent)
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
        async def describe_table_schema(table_name: str) -> str:
            """Get column names and types for prescription and clinical data tables.
            
            BEFORE CALLING: Always explain why you're examining this specific table.
            
            Available tables:
            - prescriptions: Main prescription records (medication_name, dosage, frequency, instructions, duration, prescribed_by, prescribed_at)
            - clinical_notes: Clinical notes and diagnoses (diagnosis, symptoms_presented, doctor_observations, treatment_plan, follow_up_recommendations)
          
            Args:
                table_name: Name of the table to describe
                
            Returns:
                String describing the table schema
            """
            try:
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
                
                result = f"Schema for table '{table_name}':\n"
                for col in columns:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                    result += f"  {col['column_name']}: {col['data_type']} {nullable}{default}\n"
                return result
            except Exception as e:
                return f"Schema Error: {e}"
        
        return [query_prescription_clinical_db, describe_table_schema]

    def _build_workflow(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(PrescriptionClinicalAgentState)
        
        # Add nodes for component-based processing
        workflow.add_node("analyze_prompt", self.analyze_prompt)
        workflow.add_node("process_components", self.process_components)
        workflow.add_node("store_data", self.store_data)
        workflow.add_node("retrieve_data", self.retrieve_data)
        workflow.add_node("handle_error", self.handle_error)
        workflow.add_node("format_response", self.format_response)
        
        # Set entry point
        workflow.add_edge(START, "analyze_prompt")
        
        # Add conditional edges for component routing
        workflow.add_conditional_edges(
            "analyze_prompt",
            self.route_to_tasks,
            {
                "process_components": "process_components",
                "retrieve": "retrieve_data",
                "error": "handle_error"
            }
        )
        
        # Add edges for component processing workflows
        workflow.add_edge("process_components", "store_data")
        
        # Add edges to response formatting
        workflow.add_edge("store_data", "format_response")
        workflow.add_edge("retrieve_data", "format_response")
        workflow.add_edge("handle_error", "format_response")
        
        # End workflow
        workflow.add_edge("format_response", END)
        
        return workflow.compile()

    def get_postgres_connection(self):
        """Get PostgreSQL connection (same as lab agent)"""
        return psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD or ""
        )

    def log_execution_step(self, state: PrescriptionClinicalAgentState, step_name: str, status: str, details: Dict = None):
        """Log execution step with context"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        state.execution_log.append(log_entry)

    async def analyze_prompt(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """Analyze the incoming prompt to determine which task(s) are being requested"""
        try:
            self.log_execution_step(state, "analyze_prompt", "started")

            # Compose the system prompt for component classification
            system_prompt = (
                "You are an expert medical document processing assistant. "
                "Your job is to analyze the provided prescription document (from extracted text or image) "
                "and identify which of the following components are present and need to be updated:\n\n"
                
                "🩺 1. VITALS - Physical measurements and vital signs:\n"
                "   • Blood Pressure: systolic/diastolic (e.g., 120/80, BP: 140/90 mmHg)\n"
                "   • Heart Rate: pulse, HR, beats per minute (e.g., HR: 72 bpm, Pulse: 88)\n"
                "   • Temperature: body temp, fever (e.g., Temp: 98.6°F, 37.2°C)\n"
                "   • Weight: body weight, mass (e.g., Wt: 150 lbs, Weight: 68 kg)\n"
                "   • Height: stature (e.g., Ht: 5'8\", Height: 173 cm)\n"
                "   • BMI: body mass index (e.g., BMI: 24.5, BMI: 22.1 kg/m²)\n"
                "   • Respiratory Rate: breathing rate, RR (e.g., RR: 16/min)\n"
                "   • Oxygen Saturation: SpO2, O2 sat (e.g., O2 sat: 98%, SpO2: 95%)\n"
                "   • Pain Scale: pain level (e.g., Pain: 3/10, Pain scale: 5)\n\n"
                
                "🧪 2. BIOMARKERS - Laboratory test results and blood work:\n"
                "   • Blood Tests: CBC, CMP, lipid panel, liver function\n"
                "   • Glucose/Sugar: blood glucose, A1C, HbA1c, fasting glucose (e.g., Glucose: 95 mg/dL, A1C: 6.2%)\n"
                "   • Cholesterol: total cholesterol, LDL, HDL, triglycerides (e.g., Total Chol: 180 mg/dL, LDL: 120)\n"
                "   • Kidney Function: creatinine, BUN, eGFR (e.g., Creatinine: 1.0 mg/dL, eGFR: 85)\n"
                "   • Liver Enzymes: ALT, AST, bilirubin (e.g., ALT: 25 U/L, AST: 30 U/L)\n"
                "   • Thyroid: TSH, T3, T4 (e.g., TSH: 2.5 mIU/L, Free T4: 1.2)\n"
                "   • Electrolytes: sodium, potassium, chloride (e.g., Na: 140 mEq/L, K: 4.0)\n"
                "   • Blood Count: WBC, RBC, hemoglobin, hematocrit, platelets\n"
                "   • Inflammatory Markers: ESR, CRP (e.g., CRP: <1.0 mg/L)\n"
                "   • Cardiac Markers: troponin, BNP, CK-MB\n"
                "   • Vitamins: Vitamin D, B12, folate (e.g., Vit D: 32 ng/mL)\n\n"
                
                "💊 3. PRESCRIPTIONS - Medications and pharmaceutical instructions:\n"
                "   • Medication Names: brand names, generic names, drug names\n"
                "   • Dosages: strength, amount (e.g., 10mg, 500mg, 0.5mg)\n"
                "   • Frequency: how often (e.g., twice daily, BID, QID, every 6 hours, PRN)\n"
                "   • Instructions: take with food, on empty stomach, at bedtime\n"
                "   • Duration: length of treatment (e.g., for 7 days, x30 days)\n"
                "   • Quantity: number of pills/units (e.g., #30, Qty: 90)\n"
                "   • Refills: number of refills allowed (e.g., Refills: 2, No refills)\n"
                "   • Route: oral, topical, injection, inhaled\n"
                "   • Drug Forms: tablets, capsules, liquid, cream, patches\n\n"
                
                "📋 4. CLINICAL_NOTES - Medical observations and assessments:\n"
                "   • Diagnoses: ICD codes, medical conditions (e.g., Type 2 Diabetes, Hypertension)\n"
                "   • Symptoms: patient complaints, chief complaint (e.g., chest pain, fatigue, SOB)\n"
                "   • Physical Exam: doctor's findings, examination results\n"
                "   • Assessment: medical opinion, clinical impression\n"
                "   • Treatment Plans: recommended treatments, follow-up care\n"
                "   • Medical History: past medical history, family history\n"
                "   • Allergies: drug allergies, food allergies (e.g., NKDA, Allergy to penicillin)\n"
                "   • Social History: smoking, alcohol, occupation\n"
                "   • Review of Systems: ROS, system-specific symptoms\n"
                "   • Follow-up Instructions: return visit, monitoring recommendations\n\n"
                
                "📊 ANALYSIS INSTRUCTIONS:\n"
                "1. Look for NUMERICAL VALUES with units for vitals/biomarkers\n"
                "2. Look for DRUG NAMES and dosing information for prescriptions\n"
                "3. Look for MEDICAL TERMINOLOGY and diagnoses for clinical notes\n"
                "4. Consider CONTEXT - numbers near 'BP', 'glucose', etc. are likely biomarkers/vitals\n"
                "5. Multiple components can exist in the same document\n\n"
                
                "Return ONLY a JSON object with ALL components explicitly listed:\n"
                "{\n"
                "  \"components\": {\n"
                "    \"vitals\": {\"present\": true/false, \"details\": \"specific findings or 'not found'\", \"reason\": \"explanation for presence/absence\"},\n"
                "    \"biomarkers\": {\"present\": true/false, \"details\": \"specific findings or 'not found'\", \"reason\": \"explanation for presence/absence\"},\n"
                "    \"prescriptions\": {\"present\": true/false, \"details\": \"specific findings or 'not found'\", \"reason\": \"explanation for presence/absence\"},\n"
                "    \"clinical_notes\": {\"present\": true/false, \"details\": \"specific findings or 'not found'\", \"reason\": \"explanation for presence/absence\"}\n"
                "  }\n"
                "}\n\n"
                
                "EXAMPLES:\n"
                "• Document: 'BP: 140/90, Metformin 500mg BID, Type 2 DM'\n"
                "  → {\"components\": {\"vitals\": {\"present\": true, \"details\": \"BP reading: 140/90\", \"reason\": \"Found blood pressure measurement with systolic/diastolic values\"}, \"biomarkers\": {\"present\": false, \"details\": \"not found\", \"reason\": \"No laboratory test results or blood work values present\"}, \"prescriptions\": {\"present\": true, \"details\": \"Metformin 500mg BID\", \"reason\": \"Identified medication name with specific dosage and frequency\"}, \"clinical_notes\": {\"present\": true, \"details\": \"Type 2 DM diagnosis\", \"reason\": \"Contains medical diagnosis terminology\"}}}\n\n"
                "• Document: 'Glucose: 180 mg/dL, A1C: 8.2%, Cholesterol: 220 mg/dL'\n"
                "  → {\"components\": {\"vitals\": {\"present\": false, \"details\": \"not found\", \"reason\": \"No vital signs like BP, heart rate, weight, or temperature\"}, \"biomarkers\": {\"present\": true, \"details\": \"Glucose: 180 mg/dL, A1C: 8.2%, Cholesterol: 220 mg/dL\", \"reason\": \"Multiple laboratory values with units indicating blood test results\"}, \"prescriptions\": {\"present\": false, \"details\": \"not found\", \"reason\": \"No medication names, dosages, or pharmaceutical instructions\"}, \"clinical_notes\": {\"present\": false, \"details\": \"not found\", \"reason\": \"No diagnoses, symptoms, or clinical observations mentioned\"}}}\n\n"
                "• Document: 'Weight: 85 kg, Height: 175 cm, BMI: 27.8, complains of fatigue'\n"
                "  → {\"components\": {\"vitals\": {\"present\": true, \"details\": \"Weight: 85 kg, Height: 175 cm, BMI: 27.8\", \"reason\": \"Contains anthropometric measurements and calculated BMI\"}, \"biomarkers\": {\"present\": false, \"details\": \"not found\", \"reason\": \"No blood test results or laboratory values present\"}, \"prescriptions\": {\"present\": false, \"details\": \"not found\", \"reason\": \"No medications or pharmaceutical instructions mentioned\"}, \"clinical_notes\": {\"present\": true, \"details\": \"Patient complaint: fatigue\", \"reason\": \"Contains subjective symptom reported by patient\"}}}"
            )

            # Prepare the user prompt with document content
            user_prompt_parts = [
                f"User request: {state.original_prompt}\n"
                f"User ID: {state.user_id}\n"
            ]
            
            # Add document content based on what's available
            if state.image_base64 or state.image_path:
                user_prompt_parts.append("DOCUMENT TO ANALYZE: Medical document image (see attached image)")
                user_prompt_parts.append("Please analyze the medical document image and identify which components are present.")
            elif state.extracted_text:
                user_prompt_parts.append(f"DOCUMENT TO ANALYZE:\n---START DOCUMENT---\n{state.extracted_text}\n---END DOCUMENT---\n")
                user_prompt_parts.append("Please analyze the document text above and identify which components are present.")
            else:
                user_prompt_parts.append("ERROR: No document content provided for analysis.")
            
            user_prompt = "\n".join(user_prompt_parts)

            # Simple rule: prioritize extracted_text over image processing
            if state.extracted_text:
                # Use regular LLM for pre-extracted text
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                response = await self.llm.ainvoke(messages)
            elif state.image_base64 or state.image_path:
                # Convert image_path to base64 if needed
                if state.image_path and not state.image_base64:
                    try:
                        import base64
                        with open(state.image_path, "rb") as image_file:
                            state.image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
                    except Exception as e:
                        state.has_error = True
                        state.error_context = {
                            "error_type": "image_processing",
                            "node": "analyze_prompt",
                            "message": f"Failed to load image: {str(e)}",
                            "context": {"image_path": state.image_path}
                        }
                        return state
                
                # Use vision model for image analysis only if no extracted text
                messages = [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{state.image_base64}"}
                            }
                        ]
                    }
                ]
                response = await self.vision_llm.ainvoke(messages)
            else:
                # Use regular LLM for text analysis
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                response = await self.llm.ainvoke(messages)

            try:
                result = json.loads(response.content)
                components_data = result.get("components", {})
                state.intent_reason = "Component-specific analysis completed"
                
                # Process explicit component status
                valid_components = ["vitals", "biomarkers", "prescriptions", "clinical_notes"]
                detected_components = []
                component_details = {}
                
                for component in valid_components:
                    component_info = components_data.get(component, {})
                    is_present = component_info.get("present", False)
                    details = component_info.get("details", "not found")
                    reason = component_info.get("reason", "no explanation provided")
                    
                    component_details[component] = {
                        "present": is_present,
                        "details": details,
                        "reason": reason
                    }
                    
                    if is_present:
                        detected_components.append(component)
                
                # Store detailed component information for potential use
                state.component_analysis = component_details
                
                if not detected_components:
                    state.task_types = ["unknown"]
                    state.has_error = True
                    state.error_context = {
                        "error_type": "component_classification",
                        "node": "analyze_prompt",
                        "message": "No valid components detected in document.",
                        "context": {"llm_reason": state.intent_reason, "component_details": component_details}
                    }
                else:
                    state.task_types = detected_components
                    
            except Exception as e:
                state.has_error = True
                state.error_context = {
                    "error_type": "component_classification",
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

    def route_to_tasks(self, state: PrescriptionClinicalAgentState) -> str:
        """Route to appropriate task based on detected components"""
        if state.has_error:
            return "error"
        
        if not state.task_types or "unknown" in state.task_types:
            return "error"

        # Process all detected components
        return "process_components"

    async def process_components(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """Process document based on detected components and route to appropriate agents"""
        try:
            self.log_execution_step(state, "process_components", "started", {
                "detected_components": state.task_types
            })
            
            # Process vitals if detected
            if "vitals" in state.task_types:
                self.log_execution_step(state, "process_components", "processing_vitals")
                vitals_data = await self._extract_vitals_data(state)
                state.extracted_vitals_data = vitals_data
            
            # Process biomarkers if detected
            if "biomarkers" in state.task_types:
                self.log_execution_step(state, "process_components", "processing_biomarkers")
                biomarkers_data = await self._extract_biomarkers_data(state)
                state.extracted_lab_data = biomarkers_data
            
            # Process prescriptions if detected
            if "prescriptions" in state.task_types:
                self.log_execution_step(state, "process_components", "processing_prescriptions")
                prescription_data = await self._extract_prescription_data_internal(state)
                state.extracted_prescription_data = prescription_data
            
            # Process clinical notes if detected
            if "clinical_notes" in state.task_types:
                self.log_execution_step(state, "process_components", "processing_clinical_notes")
                clinical_data = await self._extract_clinical_data_internal(state)
                state.extracted_clinical_data = clinical_data
            
            self.log_execution_step(state, "process_components", "completed", {
                "processed_components": len(state.task_types)
            })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "component_processing",
                "node": "process_components",
                "message": f"Failed to process components: {str(e)}",
                "context": {"components": state.task_types}
            }
            self.log_execution_step(state, "process_components", "failed", {"error": str(e)})
        
        return state

    async def extract_prescription_data(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """Extract prescription data from image or text"""
        self.log_execution_step(state, "extract_prescription_data", "started")
        try:
            # Check if we have an image to analyze
            if state.image_path or state.image_base64:
                prescription_data = await self._analyze_prescription_image(state)
            else:
                prescription_data = await self._extract_prescription_from_text(state)
            
            if not prescription_data:
                state.has_error = True
                state.error_context = {
                    "error_type": "extraction_failed",
                    "node": "extract_prescription_data",
                    "message": "Failed to extract prescription data from input",
                }
                return state
            
            state.extracted_prescription_data = prescription_data
            
            self.log_execution_step(state, "extract_prescription_data", "completed", {
                "medications_extracted": len(prescription_data.get("medications", []))
            })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "exception",
                "node": "extract_prescription_data",
                "message": str(e),
            }
            self.log_execution_step(state, "extract_prescription_data", "failed", {"error": str(e)})
        
        return state

    async def extract_clinical_data(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """Extract clinical notes data from image or text"""
        self.log_execution_step(state, "extract_clinical_data", "started")
        try:
            # Check if we have an image to analyze
            if state.image_path or state.image_base64:
                clinical_data = await self._analyze_clinical_image(state)
            else:
                clinical_data = await self._extract_clinical_from_text(state)
            
            if not clinical_data:
                state.has_error = True
                state.error_context = {
                    "error_type": "extraction_failed",
                    "node": "extract_clinical_data",
                    "message": "Failed to extract clinical data from input",
                }
                return state
            
            state.extracted_clinical_data = clinical_data
            
            self.log_execution_step(state, "extract_clinical_data", "completed", {
                "diagnosis_extracted": bool(clinical_data.get("diagnosis"))
            })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "exception",
                "node": "extract_clinical_data",
                "message": str(e),
            }
            self.log_execution_step(state, "extract_clinical_data", "failed", {"error": str(e)})
        
        return state

    async def update_data(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """Extract prescription, clinical, and vitals data from the same document"""
        self.log_execution_step(state, "extract_both_data", "started")
        
        
        
        
        
        
        
        
        
        try:
            # Extract prescription data first
            if state.image_path or state.image_base64:
                prescription_data = await self._analyze_prescription_image(state)
                clinical_data = await self._analyze_clinical_image(state)
            else:
                prescription_data = await self._extract_prescription_from_text(state)
                clinical_data = await self._extract_clinical_from_text(state)
            
            # Extract vitals data using the vitals agent
            vitals_data = await self._extract_vitals_data(state)
            
            # Store all results
            state.extracted_prescription_data = prescription_data
            state.extracted_clinical_data = clinical_data
            state.extracted_vitals_data = vitals_data
            
            self.log_execution_step(state, "extract_both_data", "completed", {
                "prescription_extracted": bool(prescription_data),
                "clinical_extracted": bool(clinical_data),
                "vitals_extracted": bool(vitals_data)
            })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "exception",
                "node": "extract_both_data",
                "message": str(e),
            }
            self.log_execution_step(state, "extract_both_data", "failed", {"error": str(e)})
        
        return state

    async def _extract_vitals_data(self, state: PrescriptionClinicalAgentState) -> Optional[Dict]:
        """Extract vitals data using the vitals agent"""
        try:
            # Prepare prompt for vitals extraction
            vitals_prompt = f"Extract vitals data from this document: {state.original_prompt}"
            
            # Call the vitals agent with the same data
            vitals_result = await self.vitals_agent.run(
                prompt=vitals_prompt,
                user_id=state.user_id,
                extracted_text=state.extracted_text,
                image_path=state.image_path,
                image_base64=state.image_base64
            )
            
            # Check if vitals were successfully extracted
            if vitals_result and vitals_result.get("success"):
                return vitals_result
            else:
                # No vitals found or error occurred, but don't fail the whole process
                return None
                
        except Exception as e:
            # Log the error but don't fail the whole process since vitals are optional
            self.log_execution_step(state, "_extract_vitals_data", "failed", {"error": str(e)})
            return None

    async def _extract_biomarkers_data(self, state: PrescriptionClinicalAgentState) -> Optional[Dict]:
        """Extract biomarkers/lab data using the lab agent"""
        try:
            # Prepare prompt for lab data extraction
            lab_prompt = f"Extract lab/biomarker data from this document: {state.original_prompt}"
            
            # Call the lab agent with the same data
            lab_result = await self.lab_agent.run(
                prompt=lab_prompt,
                user_id=state.user_id,
                extracted_text=state.extracted_text,
                image_path=state.image_path,
                image_base64=state.image_base64
            )
            
            # Check if lab data were successfully extracted
            if lab_result and lab_result.get("success"):
                return lab_result
            else:
                # No lab data found or error occurred, but don't fail the whole process
                return None
                
        except Exception as e:
            # Log the error but don't fail the whole process since lab data are optional
            self.log_execution_step(state, "_extract_biomarkers_data", "failed", {"error": str(e)})
            return None

    async def _extract_prescription_data_internal(self, state: PrescriptionClinicalAgentState) -> Optional[Dict]:
        """Internal method to extract prescription data"""
        try:
            if state.image_path or state.image_base64:
                return await self._analyze_prescription_image(state)
            else:
                return await self._extract_prescription_from_text(state)
        except Exception as e:
            self.log_execution_step(state, "_extract_prescription_data_internal", "failed", {"error": str(e)})
            return None

    async def _extract_clinical_data_internal(self, state: PrescriptionClinicalAgentState) -> Optional[Dict]:
        """Internal method to extract clinical notes data"""
        try:
            if state.image_path or state.image_base64:
                return await self._analyze_clinical_image(state)
            else:
                return await self._extract_clinical_from_text(state)
        except Exception as e:
            self.log_execution_step(state, "_extract_clinical_data_internal", "failed", {"error": str(e)})
            return None

    async def store_data(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """Store extracted data using direct database operations"""
        self.log_execution_step(state, "store_data", "started")
        try:
            storage_results = []
            
            # Store prescription data if available
            if state.extracted_prescription_data:
                prescription_result = self._store_prescription_data_direct(state.extracted_prescription_data, state.user_id, state.session_id, state.image_path)
                storage_results.append({"type": "prescription", "result": prescription_result})
            
            # Store clinical data if available
            if state.extracted_clinical_data:
                clinical_result = self._store_clinical_data_direct(state.extracted_clinical_data, state.user_id, state.session_id, state.source_file_path or state.image_path)
                storage_results.append({"type": "clinical", "result": clinical_result})
            
            # Store vitals data if available (vitals agent handles its own storage)
            if state.extracted_vitals_data:
                vitals_result = {"success": True, "message": "Vitals processed by vitals agent", "data": state.extracted_vitals_data}
                storage_results.append({"type": "vitals", "result": vitals_result})
            
            # Store lab/biomarkers data if available (lab agent handles its own storage)
            if state.extracted_lab_data:
                lab_result = {"success": True, "message": "Lab data processed by lab agent", "data": state.extracted_lab_data}
                storage_results.append({"type": "biomarkers", "result": lab_result})
            
            state.storage_results = storage_results
            
            self.log_execution_step(state, "store_data", "completed", {
                "stored_types": [r["type"] for r in storage_results]
            })
            
        except Exception as e:
            state.has_error = True
            state.error_context = {
                "error_type": "exception",
                "node": "store_data",
                "message": str(e),
            }
            self.log_execution_step(state, "store_data", "failed", {"error": str(e)})
        
        return state

    async def retrieve_data(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """LangGraph-based retrieval workflow using agent reasoning (same as lab agent)"""
        self.log_execution_step(state, "retrieve_data", "started")
        try:
            user_request = state.original_prompt + " for the user_id: " + str(state.user_id)
            print(f"DEBUG: Calling LangGraph retrieval agent with request: {user_request}")
            
            # Use the LangGraph-based retrieval agent (same approach as lab agent)
            result = await self._use_advanced_retrieval(user_request)
            
            print(f"DEBUG: LangGraph agent returned: {result}")
            
            state.query_results = result
            self.log_execution_step(state, "retrieve_data", "completed", {"results": result})
        except Exception as e:
            print(f"DEBUG: Exception in retrieve_data: {str(e)}")
            import traceback
            traceback.print_exc()
            state.has_error = True
            state.error_context = {
                "error_type": "retrieval_execution",
                "node": "retrieve_data",
                "message": str(e),
            }
            self.log_execution_step(state, "retrieve_data", "failed", {"error": str(e)})
        return state

    async def _use_advanced_retrieval(self, user_request: str) -> Dict[str, Any]:
        """Use LangGraph ReAct agent for retrieval (same approach as lab agent)"""
        try:
            # Use the comprehensive SQL generation system prompt
            retrieval_system_prompt = SQL_GENERATION_SYSTEM_PROMPT
            
            # Create a ReAct agent using LangGraph (same as lab agent approach)
            agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                prompt=retrieval_system_prompt
            )
            
            # Run the agent - use ainvoke for async tools
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

    async def handle_error(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """Handle errors and prepare error response"""
        self.log_execution_step(state, "handle_error", "started")
        
        error_context = state.error_context or {}
        error_response = {
            "success": False,
            "error": error_context.get("message", "Unknown error occurred"),
            "error_type": error_context.get("error_type", "unknown"),
            "node": error_context.get("node", "unknown"),
            "context": error_context.get("context", {})
        }
        
        state.response_data = error_response
        
        self.log_execution_step(state, "handle_error", "completed", error_response)
        return state

    async def format_response(self, state: PrescriptionClinicalAgentState) -> PrescriptionClinicalAgentState:
        """Format the final response"""
        self.log_execution_step(state, "format_response", "started")
        
        if state.has_error:
            # Error response already formatted in handle_error
            pass
        elif state.storage_results:
            # Check for any failed component extractions in execution log
            failed_extractions = [
                log for log in state.execution_log 
                if log.get("status") == "failed" and log.get("step", "").startswith("_extract_")
            ]
            
            # Check for errors in storage results
            failed_storage = [
                result for result in state.storage_results 
                if result.get("result", {}).get("error") or not result.get("result", {}).get("success", True)
            ]
            
            # Determine overall success - partial success if some components failed
            overall_success = len(failed_extractions) == 0 and len(failed_storage) == 0
            
            # Format storage results
            response = {
                "success": overall_success,
                "operation": "store",
                "results": state.storage_results,
                "execution_log": state.execution_log
            }
            
            # Add warnings about partial failures
            if failed_extractions or failed_storage:
                warnings = []
                if failed_extractions:
                    failed_components = [log.get("step", "").replace("_extract_", "").replace("_data", "") for log in failed_extractions]
                    warnings.append(f"Failed to extract: {', '.join(failed_components)}")
                if failed_storage:
                    failed_types = [result.get("type", "unknown") for result in failed_storage]
                    warnings.append(f"Failed to store: {', '.join(failed_types)}")
                response["warnings"] = warnings
                response["partial_success"] = True
            
            state.response_data = response
        elif state.query_results:
            # Format retrieval results
            response = {
                "success": True,
                "operation": "retrieve",
                "results": state.query_results,
                "execution_log": state.execution_log
            }
            state.response_data = response
        else:
            # Unknown state
            response = {
                "success": False,
                "error": "No results generated",
                "execution_log": state.execution_log
            }
            state.response_data = response
        
        self.log_execution_step(state, "format_response", "completed")
        return state

    def _store_prescription_data_direct(self, prescription_data: Dict, user_id: int, session_id: int, image_path: str = None) -> Dict:
        """Store prescription data directly to database"""
        try:
            db = SessionLocal()
            
            if not prescription_data or not prescription_data.get("medications"):
                return {"error": "No prescription data to store"}
            
            stored_records = []
            
            # Store each medication as a separate prescription record
            for idx, med_data in enumerate(prescription_data.get("medications", [])):
                # Generate unique ID
                prescription_id = f"rx_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{idx}"
                
                # Build instructions including additional details
                instruction_parts = []
                if med_data.get("instructions"):
                    instruction_parts.append(med_data.get("instructions"))
                if med_data.get("warnings"):
                    instruction_parts.append(f"Warning: {med_data.get('warnings')}")
                if med_data.get("indication"):
                    instruction_parts.append(f"For: {med_data.get('indication')}")
                
                combined_instructions = ". ".join(instruction_parts) if instruction_parts else None
                
                # Parse prescription date
                prescribed_at = datetime.utcnow()
                if prescription_data.get("prescription_date"):
                    try:
                        prescribed_at = datetime.fromisoformat(prescription_data.get("prescription_date"))
                    except:
                        pass
                
                prescription = Prescription(
                    id=prescription_id,
                    session_id=session_id,
                    user_id=user_id,
                    medication_name=med_data.get("medication_name", "Unknown Medication"),
                    dosage=med_data.get("dosage") or med_data.get("strength"),
                    frequency=med_data.get("frequency"),
                    instructions=combined_instructions,
                    duration=med_data.get("duration") if med_data.get("duration") != "" else None,
                    prescribed_by=prescription_data.get("prescribing_doctor", "Document Upload"),
                    prescribed_at=prescribed_at,
                    prescription_image_link=image_path
                )
                
                db.add(prescription)
                db.flush()
                
                stored_records.append({
                    "table": "prescriptions",
                    "id": prescription.id,
                    "medication": med_data.get("medication_name")
                })
            
            db.commit()
            db.close()
            
            return {
                "success": True,
                "stored_records": stored_records,
                "total_medications": len(stored_records)
            }
            
        except Exception as e:
            return {"error": f"Failed to store prescription data: {str(e)}"}

    def _store_clinical_data_direct(self, clinical_data: Dict, user_id: int, session_id: int, image_path: str = None) -> Dict:
        """Store clinical data directly to database"""
        try:
            db = SessionLocal()
            
            if not clinical_data:
                return {"error": "No clinical data to store"}
            
            # Generate unique ID
            clinical_id = f"cn_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            # Parse visit date
            visit_date = datetime.utcnow()
            if clinical_data.get("visit_date"):
                try:
                    visit_date = datetime.fromisoformat(clinical_data.get("visit_date"))
                except:
                    pass
            
            clinical_note = ClinicalNotes(
                id=clinical_id,
                session_id=session_id,
                user_id=user_id,
                diagnosis=clinical_data.get("diagnosis"),
                symptoms_presented=clinical_data.get("symptoms_presented"),
                doctor_observations=clinical_data.get("doctor_observations"),
                clinical_findings=clinical_data.get("clinical_findings"),
                treatment_plan=clinical_data.get("treatment_plan"),
                follow_up_recommendations=clinical_data.get("follow_up_recommendations"),
                vital_signs_mentioned=clinical_data.get("vital_signs_mentioned"),
                medical_history_noted=clinical_data.get("medical_history_noted"),
                visit_date=visit_date,
                clinic_or_hospital=clinical_data.get("clinic_or_hospital"),
                attending_physician=clinical_data.get("attending_physician"),
                specialty=clinical_data.get("specialty"),
                document_type=clinical_data.get("document_type", "document_upload"),
                document_image_link=image_path  # This should be source_file_path
            )
            
            db.add(clinical_note)
            db.commit()
            db.close()
            
            return {
                "success": True,
                "stored_record": {
                    "table": "clinical_notes",
                    "id": clinical_note.id,
                    "diagnosis": clinical_data.get("diagnosis")
                }
            }
            
        except Exception as e:
            return {"error": f"Failed to store clinical data: {str(e)}"}

    # Image and text analysis methods (simplified versions)
    async def _analyze_prescription_image(self, state: PrescriptionClinicalAgentState) -> Optional[Dict]:
        """Analyze prescription image using GPT-4V"""
        try:
            # Get base64 image data
            if state.image_path and not state.image_base64:
                with open(state.image_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
            elif state.image_base64:
                image_data = state.image_base64
            else:
                return None
            
            # Prescription analysis prompt
            analysis_prompt = f"""Analyze this prescription document image and extract detailed prescription information only, if there are clinical notes in the image, ignore them.

            User Request: {state.original_prompt}
            User ID: {state.user_id}

            Look for:
            - Medication names (brand and generic)
            - Dosage and strength
            - Frequency and timing
            - Duration of treatment
            - Instructions for use
            - Prescribing doctor information
            - Prescription date
            - Refill information
            - Special instructions or warnings

            Return a JSON object with prescription details:
            {{
                "prescribing_doctor": "Dr. Smith",
                "doctor_license": "12345",
                "prescription_date": "2024-01-15",
                "patient_name": "John Doe",
                "clinic_or_hospital": "City Medical Center",
                "medications": [
                    {{
                        "medication_name": "Lisinopril",
                        "generic_name": "Lisinopril", 
                        "strength": "10mg",
                        "dosage_form": "Tablet",
                        "quantity": 30,
                        "frequency": "Once daily",
                        "instructions": "Take with food in the morning",
                        "duration": "30 days",
                        "refills": 2,
                        "indication": "High blood pressure",
                        "warnings": "Monitor blood pressure regularly"
                    }}
                ]
            }}
            """
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        }
                    ]
                }
            ]
            
            response = await self.vision_llm.ainvoke(messages)
            
            # Parse JSON response
            try:
                response_content = response.content
                cleaned_content = response_content.strip()
                if cleaned_content.startswith('```json'):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()
                
                prescription_data = json.loads(cleaned_content)
                return prescription_data
                
            except json.JSONDecodeError as e:
                return None
                
        except Exception as e:
            return None

    async def _extract_prescription_from_text(self, state: PrescriptionClinicalAgentState) -> Optional[Dict]:
        """Extract prescription data from text"""
        try:
            if not state.extracted_text:
                return None
            
            extraction_prompt = f"""Analyze this prescription document image and extract detailed prescription information only, if there are clinical notes in the image, ignore them.

            User Request: {state.original_prompt}
            User ID: {state.user_id}

            Text: {state.extracted_text}

            Look for:
            - Medication names (brand and generic)
            - Dosage and strength
            - Frequency and timing
            - Duration of treatment
            - Instructions for use
            - Prescribing doctor information
            - Prescription date
            - Refill information
            - Special instructions or warnings

            Return a JSON object with prescription details:
            {{
                "prescribing_doctor": "Dr. Smith",
                "doctor_license": "12345",
                "prescription_date": "2024-01-15",
                "patient_name": "John Doe",
                "clinic_or_hospital": "City Medical Center",
                "medications": [
                    {{
                        "medication_name": "Lisinopril",
                        "generic_name": "Lisinopril", 
                        "strength": "10mg",
                        "dosage_form": "Tablet",
                        "quantity": 30,
                        "frequency": "Once daily",
                        "instructions": "Take with food in the morning",
                        "duration": "30 days",
                        "refills": 2,
                        "indication": "High blood pressure",
                        "warnings": "Monitor blood pressure regularly"
                    }}
                ]
            }}"""
            
            response = await self.llm.ainvoke([
                {"role": "system", "content": "You are a medical prescription extraction specialist."},
                {"role": "user", "content": extraction_prompt}
            ])
            
            try:
                response_content = response.content
                cleaned_content = response_content.strip()
                if cleaned_content.startswith('```json'):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()
                
                prescription_data = json.loads(cleaned_content)
                return prescription_data
                
            except json.JSONDecodeError as e:
                return None
                
        except Exception as e:
            return None

    async def _analyze_clinical_image(self, state: PrescriptionClinicalAgentState) -> Optional[Dict]:
        """Analyze clinical notes image using GPT-4V"""
        try:
            # Get base64 image data
            if state.image_path and not state.image_base64:
                with open(state.image_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
            elif state.image_base64:
                image_data = state.image_base64
            else:
                return None
            
            # Clinical notes analysis prompt
            analysis_prompt = f"""Analyze this clinical document image and extract detailed clinical information like diagnosis, symptoms, treatment plan, follow-up recommendations, vital signs, medical history, visit date, attending physician, clinic/hospital information
         . leave the prescription data if there is any, dont extract it.

            User Request: {state.original_prompt}
            User ID: {state.user_id}

            Look for:
            - Primary diagnosis/condition
            - Symptoms presented by patient
            - Doctor's clinical observations
            - Physical examination findings
            - Treatment plan prescribed
            - Follow-up recommendations
            - Vital signs mentioned
            - Medical history noted
            - Visit date and attending physician
            - Clinic/hospital information

            Return a JSON object with clinical details:
            {{
                "diagnosis": "Primary diagnosis or condition",
                "symptoms_presented": "Patient's reported symptoms",
                "doctor_observations": "Doctor's clinical observations",
                "clinical_findings": "Physical exam findings, test results",
                "treatment_plan": "Prescribed treatment plan",
                "follow_up_recommendations": "Follow-up care instructions",
                "vital_signs_mentioned": "Any vital signs noted",
                "medical_history_noted": "Patient medical history mentioned",
                "visit_date": "2024-01-15",
                "attending_physician": "Dr. Smith",
                "clinic_or_hospital": "City Medical Center",
                "specialty": "Internal Medicine",
                "document_type": "consultation_note"
            }}
            """
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        }
                    ]
                }
            ]
            
            response = await self.vision_llm.ainvoke(messages)
            
            # Parse JSON response
            try:
                response_content = response.content
                cleaned_content = response_content.strip()
                if cleaned_content.startswith('```json'):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()
                
                clinical_data = json.loads(cleaned_content)
                return clinical_data
                
            except json.JSONDecodeError as e:
                return None
                
        except Exception as e:
            return None

    async def _extract_clinical_from_text(self, state: PrescriptionClinicalAgentState) -> Optional[Dict]:
        """Extract clinical notes data from text"""
        try:
            if not state.extracted_text:
                return None
            
            extraction_prompt = f"""AAnalyze this clinical document image and extract detailed clinical information like diagnosis, symptoms, treatment plan, follow-up recommendations, vital signs, medical history, visit date, attending physician, clinic/hospital information
             . leave the prescription data if there is any, dont extract it.

            User Request: {state.original_prompt}
            User ID: {state.user_id}

            Text: {state.extracted_text}

            Look for:
            - Primary diagnosis/condition
            - Symptoms presented by patient
            - Doctor's clinical observations
            - Physical examination findings
            - Treatment plan prescribed
            - Follow-up recommendations
            - Vital signs mentioned
            - Medical history noted
            - Visit date and attending physician
            - Clinic/hospital information

            Return a JSON object with clinical details:
            {{
                "diagnosis": "Primary diagnosis or condition",
                "symptoms_presented": "Patient's reported symptoms",
                "doctor_observations": "Doctor's clinical observations",
                "clinical_findings": "Physical exam findings, test results",
                "treatment_plan": "Prescribed treatment plan",
                "follow_up_recommendations": "Follow-up care instructions",
                "vital_signs_mentioned": "Any vital signs noted",
                "medical_history_noted": "Patient medical history mentioned",
                "visit_date": "2024-01-15",
                "attending_physician": "Dr. Smith",
                "clinic_or_hospital": "City Medical Center",
                "specialty": "Internal Medicine",
                "document_type": "consultation_note"
            }}"""
            
            response = await self.llm.ainvoke([
                {"role": "system", "content": "You are a medical clinical notes extraction specialist."},
                {"role": "user", "content": extraction_prompt}
            ])
            
            try:
                response_content = response.content
                cleaned_content = response_content.strip()
                if cleaned_content.startswith('```json'):
                    cleaned_content = cleaned_content[7:]
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]
                cleaned_content = cleaned_content.strip()
                
                clinical_data = json.loads(cleaned_content)
                return clinical_data
                
            except json.JSONDecodeError as e:
                return None
                
        except Exception as e:
            return None

    async def process_request(self, prompt: str, user_id: int, session_id: int = 1, image_path: str = None, image_base64: str = None, extracted_text: str = None, source_file_path: str = None) -> Dict:
        """Process a request through the agent workflow"""
        initial_state = PrescriptionClinicalAgentState(
            original_prompt=prompt,
            user_id=user_id,
            session_id=session_id,
            image_path=image_path,
            image_base64=image_base64,
            extracted_text=extracted_text,
            source_file_path=source_file_path
        )
        
        try:
            final_state = await self.workflow.ainvoke(initial_state)
            
            # Handle both dictionary and object returns from LangGraph
            if isinstance(final_state, dict):
                return final_state.get("response_data", final_state)
            else:
                return final_state.response_data
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Workflow execution error: {str(e)}",
                "error_type": "workflow_execution"
            }


# Convenience functions for external usage
def get_prescription_clinical_agent() -> PrescriptionClinicalAgentLangGraph:
    """Get a prescription clinical agent instance"""
    return PrescriptionClinicalAgentLangGraph()

async def extract_prescription_and_clinical_data(prompt: str, user_id: int, session_id: int = 1, image_path: str = None, image_base64: str = None, extracted_text: str = None) -> Dict:
    """Extract prescription and/or clinical data from document"""
    agent = get_prescription_clinical_agent()
    return await agent.process_request(prompt, user_id, session_id, image_path, image_base64, extracted_text)

async def retrieve_prescription_and_clinical_data(prompt: str, user_id: int, session_id: int = 1) -> Dict:
    """Retrieve stored prescription and clinical data"""
    agent = get_prescription_clinical_agent()
    return await agent.process_request(prompt, user_id, session_id) 

if __name__ == "__main__":
    import asyncio
    agent = get_prescription_clinical_agent()
    image_path = "/Users/rajanishsd/Documents/zivohealth-1/backend/data/uploads/chat/5eb324be-354a-4f12-9355-2f9c1ef4b954_1_20250715_185147.jpg"
    
    print("Testing prescription clinical agent...")
    print(f"Image path: {image_path}")
    print(f"Image exists: {Path(image_path).exists()}")
    
    result = asyncio.run(agent.process_request("I have a prescription, update the same", session_id=1, user_id=1, image_path=image_path))
    print(f"Result: {result}")
    print(f"Result type: {type(result)}")

    