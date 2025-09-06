#!/usr/bin/env python3

"""
Medical Doctor Agent - Provides comprehensive medical consultations and responses
with direct access to other health agents for intelligent data collection.
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.telemetry import trace_agent_operation, log_agent_interaction
from app.core.chatgpt_logger import log_chatgpt_interaction
from app.agents.guardrails_system import validate_medical_consultation_response, generate_user_friendly_violation_message
from app.crud.clinical_report import clinical_report
from app.db.session import get_db
from app.crud.clinical_report import clinical_report
from app.db.session import get_db


class MedicalDoctorAgent:
    """Medical Doctor Agent with direct access to other health agents"""
    
    def __init__(self):
        self.agent_name = "MedicalDoctorAgent"
        self.model_name = settings.MEDICAL_DOCTOR_MODEL or settings.DEFAULT_AI_MODEL
        self.llm = ChatOpenAI(
            model=settings.MEDICAL_DOCTOR_MODEL or settings.DEFAULT_AI_MODEL,
            temperature=settings.MEDICAL_DOCTOR_TEMPERATURE or 0.1,
            timeout=45
        )
        self._health_agents = None

    @property
    def health_agents(self) -> Dict[str, Any]:
        """Lazy loading of health agents"""
        if self._health_agents is None:
            # Import agent getter functions
            from app.agents.lab_agent import get_lab_agent
            from app.agents.vitals_agent import get_vitals_agent
            from app.agents.pharmacy_agent import get_pharmacy_agent
            from app.agents.prescription_agent import get_prescription_agent
            from app.agents.nutrition_agent import get_nutrition_agent
            
            self._health_agents = {
                "lab": get_lab_agent(),
                "vitals": get_vitals_agent(),
                "pharmacy": get_pharmacy_agent(),
                "prescription": get_prescription_agent(),
                "nutrition": get_nutrition_agent()
            }
        return self._health_agents

    async def handle_medical_question(
        self,
        question: str,
        user_id: int,
        session_id: Optional[int] = None,
        guardrails_validation: Optional[Dict[str, Any]] = None,  # Accept validation results from orchestrator
        document_data: Optional[Dict[str, Any]] = None  # NEW: Accept document data for document-specific questions
    ) -> Dict[str, Any]:
        """
        Handle medical question by intelligently querying relevant health agents
        and provide comprehensive medical response with pre-validated input
        
        Args:
            document_data: Optional document data for document-specific questions.
                          If provided, skips historical data collection and uses only the document.
        """
        
        with trace_agent_operation(
            self.agent_name,
            "handle_medical_question",
            user_id=user_id,
            session_id=session_id
        ):
            try:
                print(f"🩺 [DEBUG] Medical doctor handling question: {question[:50]}...")
                
                # Check if this is a document-specific question
                is_document_specific = document_data is not None
                if is_document_specific:
                    print(f"📄 [DEBUG] Document-specific question detected - skipping historical data collection")
                
                # Use pre-validated input from orchestrator (EnhancedCustomerAgent)
                if guardrails_validation and guardrails_validation.get("input_validation"):
                    validation_result = guardrails_validation["input_validation"]
                    if not validation_result.get("is_safe", True):
                        print(f"🛡️ [DEBUG] Using pre-validated unsafe input from orchestrator")
                        
                        # Generate user-friendly message for the violations
                        user_friendly_message = generate_user_friendly_violation_message(
                            validation_result.get("violations", [])
                        )
                        
                        return {
                            "success": False,
                            "error_message": "Input violates safety guidelines (pre-validated)",
                            "medical_response": user_friendly_message,  # Use helpful message instead of generic one
                            "guardrails_blocked": True,
                            "violations": validation_result.get("violations", []),
                            "violation_help": "Medical consultation blocked with specific user guidance"
                        }
                    
                    # Use the pre-filtered content
                    filtered_question = validation_result.get("filtered_content", question)
                    print(f"🛡️ [DEBUG] Using pre-validated safe input from orchestrator")
                else:
                    # Fallback: if no validation provided, use original question
                    # This shouldn't happen in normal flow, but provides safety
                    print(f"⚠️  [DEBUG] No pre-validation provided, using original question")
                    filtered_question = question
                
                # Continue with medical processing using the filtered question...
                print(f"🩺 [DEBUG] Processing filtered question: {filtered_question[:50]}...")
                
                # Step 1: Determine data strategy
                if is_document_specific:
                    # For document-specific questions, use provided document data
                    health_data = {"document": document_data}
                    agent_requirements = {"document_analysis": True}
                    print(f"📄 [DEBUG] Using provided document data only")
                else:
                    # For general questions, analyze requirements and collect health data
                    agent_requirements = await self._analyze_question_requirements(filtered_question)
                    print(f"🔍 [DEBUG] Agent requirements analysis: {agent_requirements}")
                    
                    # Step 2: Collect relevant health data from specialized agents
                    health_data = await self._collect_relevant_health_data(
                        agent_requirements, user_id, session_id
                    )
                    print(f"📊 [DEBUG] Collected health data from {len(health_data)} sources")
                
                # Step 3: Generate comprehensive medical response
                medical_response = await self._provide_medical_consultation(
                    filtered_question, health_data, agent_requirements
                )
                print(f"🩺 [DEBUG] Generated medical response: {len(medical_response)} chars")
                
                # Step 4: Save clinical report with comprehensive context (only for non-document-specific questions)
                clinical_report_id = None
                if session_id and not is_document_specific:  # Don't save clinical reports for document-only questions
                    try:
                        # Create simplified context for database storage
                        simplified_context = self._prepare_simplified_context(health_data, agent_requirements)
                        
                        # Prepare structured data for clinical report
                        vitals_data = json.dumps(health_data.get("vitals", {})) if "vitals" in health_data else None
                        nutrition_data = json.dumps(health_data.get("nutrition", {})) if "nutrition" in health_data else None
                        prescription_data = json.dumps(health_data.get("prescription", {})) if "prescription" in health_data else None
                        lab_data = json.dumps(health_data.get("lab", {})) if "lab" in health_data else None
                        pharmacy_data = json.dumps(health_data.get("pharmacy", {})) if "pharmacy" in health_data else None
                        
                        # Create data sources summary
                        data_sources_summary = {
                            "sources_used": list(health_data.keys()),
                            "agent_requirements": agent_requirements,
                            "data_collection_time": __import__('app.utils.timezone', fromlist=['isoformat_now']).isoformat_now(),
                            "total_sources": len(health_data)
                        }
                        
                        # Save clinical report to database with simplified context
                        from app.core.database_utils import get_db_session
                        with get_db_session() as db:
                            clinical_report_obj = clinical_report.create_clinical_report(
                                db=db,
                                user_id=user_id,
                                chat_session_id=session_id,
                                user_question=filtered_question,
                                ai_response=medical_response,
                                comprehensive_context=simplified_context,  # Use simplified context for storage
                                data_sources_summary=json.dumps(data_sources_summary),
                                vitals_data=vitals_data,
                                nutrition_data=nutrition_data,
                                prescription_data=prescription_data,
                                lab_data=lab_data,
                                pharmacy_data=pharmacy_data,
                                agent_requirements=json.dumps(agent_requirements)
                            )
                            clinical_report_id = clinical_report_obj.id
                            print(f"📋 [DEBUG] Saved clinical report with ID: {clinical_report_id}")
                            
                    except Exception as e:
                        print(f"⚠️  [DEBUG] Failed to save clinical report: {str(e)}")
                        # Continue without clinical report - don't fail the whole request
                elif is_document_specific:
                    print(f"📄 [DEBUG] Skipping clinical report for document-specific question")
                
                # Step 5: Validate output response
                response_validation = await validate_medical_consultation_response(
                    medical_response, user_id, session_id
                )
                
                if not response_validation.is_safe:
                    print(f"⚠️  [DEBUG] Medical response failed validation, using filtered version")
                    medical_response = response_validation.filtered_content
                
                return {
                    "success": True,
                    "medical_response": medical_response,
                    "agent_requirements": agent_requirements,
                    "health_data_sources": list(health_data.keys()),
                    "clinical_report_id": clinical_report_id,  # Include report ID in response
                    "response_validation": {
                        "is_safe": response_validation.is_safe,
                        "violations": response_validation.violations
                    },
                    "guardrails_used": "pre_validated" if guardrails_validation else "none",
                    "consultation_type": "document_specific" if is_document_specific else "comprehensive"
                }
                
            except Exception as e:
                print(f"❌ [DEBUG] Medical doctor error: {str(e)}")
                return {
                    "success": False,
                    "error_message": f"Medical consultation failed: {str(e)}",
                    "medical_response": "I apologize, but I encountered an error while processing your medical question. Please try again.",
                    "guardrails_blocked": False
                }

    async def _analyze_question_requirements(self, question: str) -> Dict[str, Any]:
        """Analyze the medical question to determine which health agents to query"""
        
        with trace_agent_operation(
            "MedicalDoctorAgent",
            "analyze_question_requirements",
            user_message=question[:100] + "..." if len(question) > 100 else question,
            analysis_step="determine_data_needs"
        ):
            analysis_prompt = f"""
            As a medical doctor, analyze this patient question to determine what health data you need to provide a comprehensive response.
            
            Patient Question: "{question}"
            
            Available health data sources:
            - lab: Laboratory results, blood tests, diagnostic tests, liver function, kidney function, etc.
            - vitals: Blood pressure, heart rate, weight, temperature, BMI measurements
            - prescription: Current medications, dosages, prescriber information, active prescriptions
            - pharmacy: Medication purchase history, drug costs, pharmacy transactions
            - nutrition: Dietary intake, calorie consumption, macronutrients, meal patterns, nutritional habits
            
            For each data source, determine:
            1. Whether it's needed for this question (true/false)
            2. What specific data to look for
            3. How far back to search (days)
            4. Priority level (high/medium/low)
            
            Respond with JSON:
            {{
                "lab": {{
                    "needed": true/false,
                    "reason": "Why this data is needed",
                    "search_criteria": "What specific tests or data to focus on",
                    "days_back": 365,
                    "priority": "high/medium/low"
                }},
                "vitals": {{
                    "needed": true/false,
                    "reason": "Why this data is needed", 
                    "search_criteria": "What vital signs to focus on",
                    "days_back": 180,
                    "priority": "high/medium/low"
                }},
                "prescription": {{
                    "needed": true/false,
                    "reason": "Why this data is needed",
                    "search_criteria": "What medication information to focus on",
                    "days_back": 365,
                    "priority": "high/medium/low"
                }},
                "pharmacy": {{
                    "needed": true/false,
                    "reason": "Why this data is needed",
                    "search_criteria": "What medications are being taken based on the pharmacy bill",
                    "days_back": 180,
                    "priority": "high/medium/low"
                }},
                "nutrition": {{
                    "needed": true/false,
                    "reason": "Why this data is needed",
                    "search_criteria": "What nutritional information to focus on",
                    "days_back": 30,
                    "priority": "high/medium/low"
                }}
            }}
            """
            
            messages = [
                SystemMessage(content="You are a medical doctor analyzing patient questions to determine what health data is needed for comprehensive consultation."),
                HumanMessage(content=analysis_prompt)
            ]
            
            # Log ChatGPT interaction
            messages_dict = [
                {"role": "system", "content": "You are a medical doctor analyzing patient questions to determine what health data is needed for comprehensive consultation."},
                {"role": "user", "content": analysis_prompt}
            ]
            
            response = self.llm.invoke(messages)
            
            # Log the interaction
            log_chatgpt_interaction(
                agent_name="MedicalDoctorAgent",
                operation="analyze_question_requirements",
                request_data=messages_dict,
                response_data=response,
                model_name=self.model_name,
                additional_metadata={"question_length": len(question)}
            )
            
            # Parse JSON response
            try:
                content = response.content.strip()
                if content.startswith('```json'):
                    content = content[7:-3].strip()
                elif content.startswith('```'):
                    content = content[3:-3].strip()
                
                requirements = json.loads(content)

                # Telemetry: log successful parsing
                log_agent_interaction(
                    "MedicalDoctorAgent",
                    "System",
                    "requirements_parsed",
                    {
                        "data_sources_count": len(requirements),
                        "data_sources": list(requirements.keys()),
                        "parsing_success": True
                    },
                    user_id=None, session_id=None, request_id=None
                )
                return requirements
            except Exception as e:
                # Telemetry: log parsing failure
                log_agent_interaction(
                    "MedicalDoctorAgent",
                    "System",
                    "requirements_parse_failed",
                    {
                        "error": str(e),
                        "raw_response_preview": response.content[:200],
                        "parsing_success": False
                    },
                    user_id=None, session_id=None, request_id=None
                )
                # Fallback to basic requirements
                return {
                    "lab": {"needed": True, "reason": "General health assessment", "search_criteria": "All recent tests", "days_back": 365, "priority": "medium"},
                    "vitals": {"needed": True, "reason": "Current health status", "search_criteria": "Recent measurements", "days_back": 180, "priority": "medium"},
                    "prescription": {"needed": True, "reason": "Current medications", "search_criteria": "Active prescriptions", "days_back": 365, "priority": "medium"},
                    "pharmacy": {"needed": False, "reason": "Not immediately relevant", "search_criteria": "", "days_back": 0, "priority": "low"},
                    "nutrition": {"needed": True, "reason": "Dietary assessment", "search_criteria": "Recent nutritional intake", "days_back": 30, "priority": "medium"}
                }

    async def _collect_relevant_health_data(
        self,
        agent_requirements: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """Collect health data from relevant agents based on requirements"""
        
        health_data = {}
        
        with trace_agent_operation(
            "MedicalDoctorAgent",
            "collect_health_data",
            user_id=user_id,
            session_id=session_id,
            orchestrator="MedicalDoctorAgent"  # NEW: Mark as orchestrator for child agents
        ):
            for agent_name, requirements in agent_requirements.items():
                if not requirements.get("needed", False):
                    continue
                    
                try:
                    print(f"🩺 [DEBUG] Querying {agent_name} agent: {requirements['reason']}")
                    
                    agent = self.health_agents[agent_name]
                    
                    # Build retrieval strategy based on requirements
                    # Increase limit for vitals to get diverse data across time range
                    limit = 500 if agent_name == "vitals" else 100
                    
                    retrieval_strategy = {
                        "days_back": requirements.get("days_back", 365),
                        "limit": limit,
                        "specific_filters": {},
                        "priority_data": ["recent_reports", "summary", "analysis"]
                    }
                    
                    # Query the agent with orchestrator context
                    result = await agent.process_request(
                        "retrieve",
                        {"retrieval_request": retrieval_strategy},
                        user_id,
                        session_id
                    )
                    
                    # Extract data from response
                    response_msg = result.get("response_message", {})
                    if response_msg.get("success"):
                        agent_data = response_msg.get("data", {})
                        
                        health_data[agent_name] = {
                            "data": agent_data,
                            "requirements": requirements,
                            "summary": self._summarize_agent_data(agent_name, agent_data)
                        }
                        print(f"✅ [DEBUG] {agent_name} agent returned data successfully")
                    else:
                        print(f"⚠️ [DEBUG] {agent_name} agent returned no data")
                        
                except Exception as e:
                    print(f"❌ [DEBUG] Failed to query {agent_name} agent: {str(e)}")
                    continue
        
        return health_data

    def _summarize_agent_data(self, agent_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize data from a health agent"""
        
        summary = {"agent": agent_name, "data_available": bool(data)}
        
        if agent_name == "lab":
            recent_reports = data.get("recent_reports", [])
            summary.update({
                "total_tests": len(recent_reports),
                "abnormal_tests": len([r for r in recent_reports if r.get("test_status", "").lower() in ["high", "low", "critical", "abnormal"]]),
                "date_range": data.get("summary", {}).get("date_range", "N/A")
            })
            
        elif agent_name == "vitals":
            recent_vitals = data.get("recent_measurements", [])
            summary.update({
                "total_measurements": len(recent_vitals),
                "abnormal_vitals": len([v for v in recent_vitals if v.get("status", "").lower() in ["high", "low", "critical", "abnormal"]])
            })
            
        elif agent_name == "prescription":
            current_meds = data.get("current_medications", [])
            summary.update({
                "active_medications": len(current_meds),
                "total_prescriptions": len(data.get("prescription_history", []))
            })
            
        elif agent_name == "pharmacy":
            recent_purchases = data.get("recent_purchases", [])
            summary.update({
                "recent_purchases": len(recent_purchases),
                "total_cost": sum(float(p.get("cost", 0)) for p in recent_purchases if p.get("cost"))
            })
            
        elif agent_name == "nutrition":
            recent_meals = data.get("recent_meals", [])
            nutritional_summary = data.get("nutritional_summary", {})
            summary.update({
                "total_meals": len(recent_meals),
                "avg_daily_calories": nutritional_summary.get("avg_daily_calories", "N/A"),
                "date_range": nutritional_summary.get("date_range", "N/A")
            })
        
        return summary

    async def _provide_medical_consultation(
        self,
        question: str,
        health_data: Dict[str, Any],
        agent_requirements: Dict[str, Any]
    ) -> str:
        """Provide medical consultation using collected health data"""
        
        with trace_agent_operation(
            "MedicalDoctorAgent",
            "provide_medical_consultation",
            user_message=question[:100] + "..." if len(question) > 100 else question,
            data_sources_used=list(health_data.keys()),
            consultation_step="generate_medical_response"
        ):
            # Prepare comprehensive medical context
            medical_context = self._prepare_comprehensive_context(health_data, agent_requirements)
            
            consultation_prompt = f"""
            You are an experienced medical doctor providing a consultation to a patient based on their question and available health data.
            
            **Patient Question:** {question}
            
            **Available Health Data:**
            {medical_context}
            
            **Medical Consultation Guidelines:**
            1. Provide a direct, medically-informed response to the patient's specific question
            2. Reference relevant findings from their health data when applicable
            3. Identify any patterns or correlations across different data types
            4. When prescription data is available, consider that he is already taking those medications and focus on the new findings and changes.
               - Assess if current medications are appropriate for the patient's condition and symptoms
               - Analyze potential drug interactions between current medications
               - Evaluate if lab results indicate medication effectiveness (e.g., cholesterol levels with statins, HbA1c with diabetes medications)
               - Check for medication-related side effects that may explain current symptoms
               - Identify if any lab abnormalities could be medication-induced (e.g., liver enzymes with certain drugs)
               - Consider if the patient's symptoms suggest medication adherence issues
               - Assess if dosage adjustments might be needed based on lab results or symptoms
               - Flag any concerning medication combinations or contraindications
            5. Highlight concerning findings that warrant medical attention
            6. Provide appropriate medical guidance while emphasizing professional consultation
            7. Be specific about what the data shows and what it might indicate
            8. Keep the response focused and avoid unnecessary analysis
            9. If the question is about a specific document, use the document data to answer the question
            10. Provide a detailed list of possible diseases accompanied by the reasoning information.
            
            **Required Response Format:**
            
            **Possible Conditions/Issues:**
            • **[Condition Name]**: Brief reasoning based on specific findings from the data
            • **[Condition Name]**: Brief reasoning based on specific findings from the data
            • **[Additional conditions as relevant]**
            
            **Analysis:**
            [Your detailed medical analysis and interpretation]
            
            **Prescription Analysis:** (Include this section when prescription data is available)
            [Detailed analysis of current medications in relation to patient's condition, lab results, and symptoms]
            
            **Recommendations:**
            [Specific recommendations and next steps]
            
            **Important Medical Disclaimers:**
            - Always emphasize this is informational guidance, not a replacement for professional medical care
            - Recommend immediate medical attention for concerning symptoms or patterns
            - Be clear about limitations when data is insufficient
            
            Provide a focused medical response that directly addresses the patient's question using their available health data. Always include the bulleted list of possible conditions with crisp reasoning based on the actual data findings.
            """
            
            messages = [
                SystemMessage(content="You are a medical doctor providing patient consultations. Always emphasize the importance of professional medical care while providing helpful insights from available health data."),
                HumanMessage(content=consultation_prompt)
            ]
            
            # Log ChatGPT interaction
            messages_dict = [
                {"role": "system", "content": "You are a medical doctor providing patient consultations. Always emphasize the importance of professional medical care while providing helpful insights from available health data."},
                {"role": "user", "content": consultation_prompt}
            ]
            
            response = self.llm.invoke(messages)
            
            # Log the interaction
            log_chatgpt_interaction(
                agent_name="MedicalDoctorAgent",
                operation="provide_medical_consultation",
                request_data=messages_dict,
                response_data=response,
                model_name=self.model_name,
                additional_metadata={
                    "question_length": len(question),
                    "data_sources": list(health_data.keys()),
                    "health_data_size": len(str(health_data))
                }
            )
            
            return response.content

    def _prepare_comprehensive_context(
        self,
        health_data: Dict[str, Any],
        agent_requirements: Dict[str, Any]
    ) -> str:
        """Prepare comprehensive medical context from collected health data"""
        
        context_parts = []
        
        # Handle document-specific case
        if "document" in health_data and agent_requirements.get("document_analysis"):
            document_data = health_data["document"]
            context_parts.append(f"\n**Uploaded Document Analysis:**")
            
            # Handle lab document
            if isinstance(document_data, dict) and document_data.get("tests"):
                lab_tests = document_data["tests"]
                context_parts.append(f"Lab Report with {len(lab_tests)} tests:")
                
                for test in lab_tests:
                    status_indicator = "🔴" if test.get("test_status", "").lower() in ["high", "critical", "abnormal"] else "🟡" if test.get("test_status", "").lower() == "low" else "🟢"
                    context_parts.append(
                        f"  {status_indicator} {test.get('test_name')}: {test.get('test_value')} {test.get('test_unit', '')} "
                        f"({test.get('test_status', 'Unknown')}) [Ref: {test.get('reference_range', 'N/A')}]"
                    )
                
                # Add lab metadata if available
                if document_data.get("test_date"):
                    context_parts.append(f"Test Date: {document_data['test_date']}")
                if document_data.get("lab_name"):
                    context_parts.append(f"Lab: {document_data['lab_name']}")
                if document_data.get("ordering_physician"):
                    context_parts.append(f"Ordering Physician: {document_data['ordering_physician']}")
            else:
                # Handle other types of documents
                context_parts.append(f"Document data: {str(document_data)[:500]}...")
            
            return "\n".join(context_parts)
        
        # Handle regular health agent data
        for agent_name, agent_info in health_data.items():
            data = agent_info["data"]
            requirements = agent_info["requirements"]
            summary = agent_info["summary"]
            
            context_parts.append(f"\n**{agent_name.title()} Data** (Priority: {requirements['priority']}):")
            context_parts.append(f"Purpose: {requirements['reason']}")
            context_parts.append(f"Focus: {requirements['search_criteria']}")
            
            if agent_name == "lab":
                reports = data.get("recent_reports", [])
                context_parts.append(f"Recent Lab Results ({len(reports)} tests):")
                
                if reports:
                    for report in reports:  # Include ALL test results for comprehensive medical analysis
                        status_indicator = "🔴" if report.get("test_status", "").lower() in ["high", "critical", "abnormal"] else "🟡" if report.get("test_status", "").lower() == "low" else "🟢"
                        context_parts.append(
                            f"  {status_indicator} {report.get('test_name')}: {report.get('test_value')} {report.get('test_unit', '')} "
                            f"({report.get('test_status', 'Unknown')}) - {report.get('test_date')}"
                        )
                else:
                    context_parts.append("  No recent lab results available")
                    
            elif agent_name == "vitals":
                vitals = data.get("recent_measurements", [])
                context_parts.append(f"Recent Vital Signs ({len(vitals)} measurements):")
                
                if vitals:
                    for vital in vitals[:15]:
                        status_indicator = "🔴" if vital.get("status", "").lower() in ["high", "critical", "abnormal"] else "🟡" if vital.get("status", "").lower() == "low" else "🟢"
                        context_parts.append(
                            f"  {status_indicator} {vital.get('measurement_type')}: {vital.get('value')} {vital.get('unit', '')} "
                            f"({vital.get('status', 'Unknown')}) - {vital.get('measurement_date')}"
                        )
                else:
                    context_parts.append("  No recent vital sign measurements available")
                    
            elif agent_name == "prescription":
                medications = data.get("current_medications", [])
                context_parts.append(f"Current Medications ({len(medications)} active):")
                
                if medications:
                    for med in medications[:15]:
                        context_parts.append(
                            f"  💊 {med.get('medication_name')} {med.get('dosage', '')} - {med.get('frequency', '')} "
                            f"(Prescribed: {med.get('prescription_date')})"
                        )
                else:
                    context_parts.append("  No current medications recorded")
                    
            elif agent_name == "pharmacy":
                purchases = data.get("recent_purchases", [])
                context_parts.append(f"Recent Medication Purchases ({len(purchases)} items):")
                
                if purchases:
                    for purchase in purchases[:10]:
                        context_parts.append(
                            f"  🏪 {purchase.get('medication_name')} - {purchase.get('purchase_date')}"
                        )
                else:
                    context_parts.append("  No recent medication purchases recorded")
                    
            elif agent_name == "nutrition":
                meals = data.get("recent_meals", [])
                context_parts.append(f"Recent Nutritional Intake ({len(meals)} meals):")
                
                if meals:
                    for meal in meals[:10]:
                        # Enhanced display with actual dish names and nutritional details
                        dish_name = meal.get('dish_name', 'Unknown dish')
                        meal_type = meal.get('meal_type', 'Meal')
                        calories = meal.get('calories', 'N/A')
                        protein = meal.get('protein_g', 0)
                        carbs = meal.get('carbs_g', 0)
                        fat = meal.get('fat_g', 0)
                        portion_info = ""
                        
                        # Add portion information if available
                        if meal.get('portion_size') and meal.get('portion_unit'):
                            portion_info = f" ({meal.get('portion_size')} {meal.get('portion_unit')})"
                        
                        context_parts.append(
                            f"  🍽️ {meal_type}: {dish_name}{portion_info} - {calories} cal "
                            f"(P:{protein:.2f}g C:{carbs:.2f}g F:{fat:.2f}g) on {meal.get('meal_date')}"
                        )
                        
                        # Add food item name if different from dish name
                        food_item = meal.get('food_item_name', '')
                        if food_item and food_item != dish_name:
                            context_parts.append(f"      Main ingredient: {food_item}")
                else:
                    context_parts.append("  No recent meals recorded")
                
                # Add nutritional summary if available
                if data.get("nutritional_summary"):
                    summary_data = data["nutritional_summary"]
                    context_parts.append("Nutritional Summary:")
                    
                    # Format values to 2 decimal places
                    avg_calories = summary_data.get('avg_daily_calories', 'N/A')
                    avg_protein = summary_data.get('avg_protein', 'N/A')
                    avg_carbs = summary_data.get('avg_carbs', 'N/A')
                    avg_fat = summary_data.get('avg_fat', 'N/A')
                    
                    # Format numeric values to 2 decimal places
                    if isinstance(avg_calories, (int, float)):
                        avg_calories = f"{avg_calories:.2f}"
                    if isinstance(avg_protein, (int, float)):
                        avg_protein = f"{avg_protein:.2f}"
                    if isinstance(avg_carbs, (int, float)):
                        avg_carbs = f"{avg_carbs:.2f}"
                    if isinstance(avg_fat, (int, float)):
                        avg_fat = f"{avg_fat:.2f}"
                    
                    context_parts.append(
                        f"  📊 Daily Avg Calories: {avg_calories}, "
                        f"Protein: {avg_protein}g, "
                        f"Carbs: {avg_carbs}g, "
                        f"Fat: {avg_fat}g"
                    )
            
            # Add summary information
            context_parts.append(f"Summary: {summary}")

        
        return "\n".join(context_parts) if context_parts else "No relevant health data available for this consultation."

    def _prepare_simplified_context(
        self,
        health_data: Dict[str, Any],
        agent_requirements: Dict[str, Any]
    ) -> str:
        """Prepare simplified medical context for storage (less detailed than comprehensive context)"""
        
        context_parts = []
        
        for agent_name, agent_info in health_data.items():
            data = agent_info["data"]
            requirements = agent_info["requirements"]
            
            context_parts.append(f"\n**{agent_name.title()} Data** (Priority: {requirements['priority']}):")
            
            if agent_name == "lab":
                reports = data.get("recent_reports", [])
                context_parts.append(f"Recent Lab Results ({len(reports)} tests):")
                
                if reports:
                    for report in reports:  # Include ALL test results for comprehensive medical analysis
                        status_indicator = "🔴" if report.get("test_status", "").lower() in ["high", "critical", "abnormal"] else "🟡" if report.get("test_status", "").lower() == "low" else "🟢"
                        context_parts.append(
                            f"  {status_indicator} {report.get('test_name')}: {report.get('test_value')} {report.get('test_unit', '')} "
                            f"({report.get('test_status', 'Unknown')}) - {report.get('test_date')}"
                        )
                else:
                    context_parts.append("  No recent lab results available")
                    
            elif agent_name == "vitals":
                vitals = data.get("recent_measurements", [])
                context_parts.append(f"Recent Vital Signs ({len(vitals)} measurements):")
                
                if vitals:
                    for vital in vitals[:10]:
                        status_indicator = "🔴" if vital.get("status", "").lower() in ["high", "critical", "abnormal"] else "🟡" if vital.get("status", "").lower() == "low" else "🟢"
                        context_parts.append(
                            f"  {status_indicator} {vital.get('measurement_type')}: {vital.get('value')} {vital.get('unit', '')} "
                            f"({vital.get('status', 'Unknown')}) - {vital.get('measurement_date')}"
                        )
                else:
                    context_parts.append("  No recent vital sign measurements available")
                    
            elif agent_name == "prescription":
                medications = data.get("current_medications", [])
                context_parts.append(f"Current Medications ({len(medications)} active):")
                
                if medications:
                    for med in medications[:15]:
                        context_parts.append(
                            f"  💊 {med.get('medication_name')} {med.get('dosage', '')} - {med.get('frequency', '')} "
                            f"(Prescribed: {med.get('prescription_date')})"
                        )
                else:
                    context_parts.append("  No current medications recorded")
                    
            elif agent_name == "pharmacy":
                purchases = data.get("recent_purchases", [])
                context_parts.append(f"Recent Medication Purchases ({len(purchases)} items):")
                
                if purchases:
                    for purchase in purchases[:10]:
                        context_parts.append(
                            f"  🏪 {purchase.get('medication_name')} - {purchase.get('purchase_date')}"
                        )
                else:
                    context_parts.append("  No recent medication purchases recorded")
                    
            elif agent_name == "nutrition":
                meals = data.get("recent_meals", [])
                context_parts.append(f"Recent Nutritional Intake ({len(meals)} meals):")
                
                if meals:
                    for meal in meals[:10]:
                        # Simplified display with just dish name and date
                        dish_name = meal.get('dish_name', 'Unknown dish')
                        meal_type = meal.get('meal_type', 'Meal')
                        
                        context_parts.append(
                            f"  🍽️ {meal_type}: {dish_name} - {meal.get('meal_date')}"
                        )
                else:
                    context_parts.append("  No recent meals recorded")
        
        return "\n".join(context_parts) if context_parts else "No relevant health data available for this consultation."


# Global instance management
_medical_doctor_agent = None

def get_medical_doctor_agent():
    """Get or create the medical doctor agent instance"""
    global _medical_doctor_agent
    if _medical_doctor_agent is None:
        _medical_doctor_agent = MedicalDoctorAgent()
    return _medical_doctor_agent 

# Global instance management
_medical_doctor_agent = None

def get_medical_doctor_agent():
    """Get or create the medical doctor agent instance"""
    global _medical_doctor_agent
    if _medical_doctor_agent is None:
        _medical_doctor_agent = MedicalDoctorAgent()
    return _medical_doctor_agent 