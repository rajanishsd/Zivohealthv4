import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseHealthAgent, AgentState
from app.models.chat_session import Prescription
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction
from app.core.chatgpt_logger import log_chatgpt_interaction
from langchain.schema import SystemMessage, HumanMessage

class PrescriptionAgent(BaseHealthAgent):
    """Specialized agent for processing prescription data"""
    
    def __init__(self):
        super().__init__("PrescriptionAgent")
        # Agent swarm metadata
        self.specialization = "prescriptions"
        self.capabilities = ["extract", "store", "retrieve", "assess"]
        self.data_types = ["medications", "dosages", "prescriptions", "instructions"]
    
    async def extract_data(self, state: AgentState) -> AgentState:
        """Extract prescription data from OCR text with enhanced telemetry"""
        
        with trace_agent_operation(
            self.agent_name,
            "extract_prescription",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            try:
                log_agent_interaction(
                    self.agent_name,
                    "System",
                    "extraction_started",
                    {
                        "operation": "extract_prescription_data",
                        "ocr_text_length": len(state.get("ocr_text", "")),
                        "document_type": state.get("document_type", "unknown")
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                extraction_prompt = """
                Extract prescription information from the following medical text. Look for:
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
                {
                    "prescribing_doctor": "Dr. Smith",
                    "doctor_license": "12345",
                    "prescription_date": "2024-01-15",
                    "patient_name": "John Doe",
                    "medications": [
                        {
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
                        }
                    ]
                }
                """
                
                extraction_tool = self.get_extraction_tool()
                result = extraction_tool.func(state["ocr_text"], extraction_prompt)
                
                if "error" in result:
                    state["error_message"] = f"Prescription extraction failed: {result['error']}"
                    log_agent_interaction(
                        self.agent_name,
                        "System",
                        "extraction_failed",
                        {"error": result['error']},
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        request_id=state["request_id"]
                    )
                else:
                    state["extracted_data"] = result
                    self.log_operation("extract", result, state)
                    
                    # Enhanced logging for agent swarm coordination
                    medications_count = len(result.get("medications", []))
                    has_dosage_info = sum(1 for med in result.get("medications", []) 
                                        if med.get("strength") and med.get("frequency"))
                    
                    log_agent_interaction(
                        self.agent_name,
                        "System",
                        "extraction_completed",
                        {
                            "medications_extracted": medications_count,
                            "medications_with_dosage": has_dosage_info,
                            "has_doctor_info": bool(result.get("prescribing_doctor")),
                            "has_prescription_date": bool(result.get("prescription_date")),
                            "medication_names": [med.get("medication_name", "Unknown") 
                                               for med in result.get("medications", [])],
                            "data_quality_score": self._assess_extraction_quality(result)
                        },
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        request_id=state["request_id"]
                    )
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Prescription extraction error: {str(e)}"
                log_agent_interaction(
                    self.agent_name,
                    "System",
                    "extraction_error",
                    {"error": str(e)},
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                return state
    
    def _assess_extraction_quality(self, extracted_data: Dict[str, Any]) -> float:
        """Assess the quality of extracted prescription data"""
        required_fields = ["medications"]
        optional_fields = ["prescribing_doctor", "prescription_date"]
        
        quality_score = 0.0
        
        # Check if we have medications (60% of score)
        medications = extracted_data.get("medications", [])
        if medications:
            quality_score += 0.6
            
            # Check medication completeness (20% of score)
            complete_meds = sum(1 for med in medications 
                              if med.get("medication_name") and med.get("strength") and med.get("frequency"))
            if medications:
                quality_score += (complete_meds / len(medications)) * 0.2
        
        # Check optional fields (20% of score)
        optional_present = sum(1 for field in optional_fields if extracted_data.get(field))
        quality_score += (optional_present / len(optional_fields)) * 0.2
        
        return round(quality_score, 3)
    
    async def store_data(self, state: AgentState) -> AgentState:
        """Store prescription data to database"""
        
        with trace_agent_operation(
            self.agent_name,
            "store_prescription",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            db = self.get_database_session()
            try:
                # Get data to store
                data = state.get("extracted_data") or state.get("extraction_request", {})
                
                if not data or not data.get("medications"):
                    state["error_message"] = "No prescription data to store"
                    return state
                
                # Get file path for prescription image link
                file_path = state.get("file_path")
                print(f"🔍 [DEBUG] File path from state: {file_path}")
                
                stored_records = []
                
                # Store each medication as a separate prescription record
                for med_data in data.get("medications", []):
                    # Build instructions including additional details
                    instruction_parts = []
                    if med_data.get("instructions"):
                        instruction_parts.append(med_data.get("instructions"))
                    if med_data.get("warnings"):
                        instruction_parts.append(f"Warning: {med_data.get('warnings')}")
                    if med_data.get("indication"):
                        instruction_parts.append(f"For: {med_data.get('indication')}")
                    if data.get('prescription_number'):
                        instruction_parts.append(f"Prescription #{data.get('prescription_number')}")
                    
                    combined_instructions = ". ".join(instruction_parts) if instruction_parts else None
                    
                    # Get duration - handle empty strings as None
                    duration = med_data.get("duration")
                    if duration == "":
                        duration = None
                    
                    print(f"🔍 [DEBUG] Medication: {med_data.get('medication_name')}, Duration: '{duration}', File path: {file_path}")
                    
                    prescription = Prescription(
                        id=f"rx_{state['user_id']}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{len(stored_records)}",
                        session_id=state.get("session_id"),
                        user_id=state.get("user_id"),  # Add user_id if the field exists
                        medication_name=med_data.get("medication_name", "Unknown Medication"),
                        dosage=med_data.get("dosage") or med_data.get("strength"),
                        frequency=med_data.get("frequency"),
                        instructions=combined_instructions,
                        duration=duration,
                        prescribed_by=data.get("prescribing_doctor", "Document Upload"),
                        prescribed_at=self._parse_datetime(data.get("prescription_date")),
                        prescription_image_link=file_path  # Use file_path from state
                    )
                    
                    db.add(prescription)
                    db.flush()  # Get ID without committing
                    
                    stored_records.append({
                        "table": "prescriptions",
                        "id": prescription.id,
                        "data": med_data
                    })
                
                db.commit()
                
                state["stored_records"] = stored_records
                self.log_operation("store", {"records_count": len(stored_records)}, state)
                
                return state
                
            except Exception as e:
                db.rollback()
                state["error_message"] = f"Prescription storage error: {str(e)}"
                return state
            finally:
                db.close()
    
    async def retrieve_data(self, state: AgentState) -> AgentState:
        """Retrieve prescription data from database"""
        
        with trace_agent_operation(
            self.agent_name,
            "retrieve_prescription",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            db = self.get_database_session()
            try:
                retrieval_request = state.get("retrieval_request", {})
                days_back = retrieval_request.get("days_back", 365)  # 1 year default
                limit = retrieval_request.get("limit", 50)
                active_only = retrieval_request.get("active_only", False)
                
                # Calculate date range - use timezone-naive datetime to match database
                from datetime import timezone
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days_back)
                
                # Query prescriptions - need to join with chat_sessions to get user_id
                from app.models.chat_session import ChatSession
                
                query = db.query(Prescription).join(ChatSession).filter(
                    ChatSession.user_id == state["user_id"],
                    Prescription.prescribed_at >= start_date
                )
                
                if active_only:
                    # Filter for potentially active prescriptions (prescribed within last 90 days)
                    recent_date = end_date - timedelta(days=90)
                    query = query.filter(Prescription.prescribed_at >= recent_date)
                
                prescriptions = query.order_by(Prescription.prescribed_at.desc()).limit(limit).all()
                
                # Format data
                prescriptions_data = []
                for prescription in prescriptions:
                    prescription_dict = {
                        "id": prescription.id,
                        "medication_name": prescription.medication_name,
                        "dosage": prescription.dosage,
                        "frequency": prescription.frequency,
                        "instructions": prescription.instructions,
                        "duration": prescription.duration,
                        "prescribed_by": prescription.prescribed_by,
                        "prescribed_at": prescription.prescribed_at.isoformat() if prescription.prescribed_at else None,
                        "session_id": prescription.session_id
                    }
                    
                    # Add optional fields if they exist
                    if hasattr(prescription, 'user_id') and prescription.user_id:
                        prescription_dict["user_id"] = prescription.user_id
                    if hasattr(prescription, 'prescription_image_link') and prescription.prescription_image_link:
                        prescription_dict["prescription_image_link"] = prescription.prescription_image_link
                    
                    prescriptions_data.append(prescription_dict)
                
                # Generate analysis
                analysis = self._analyze_prescriptions(prescriptions)
                
                # Group by medication for tracking
                medication_history = self._track_medication_history(prescriptions)
                
                # Convert to format expected by medical doctor agent
                current_medications = []
                for prescription in prescriptions:
                    # Check if prescription is likely still active (within last 90 days)
                    if prescription.prescribed_at:
                        days_since_prescribed = (end_date - prescription.prescribed_at.replace(tzinfo=None)).days
                        is_recent = days_since_prescribed <= 90
                        
                        current_medications.append({
                            "medication_name": prescription.medication_name,
                            "dosage": prescription.dosage,
                            "frequency": prescription.frequency,
                            "instructions": prescription.instructions,
                            "prescribed_by": prescription.prescribed_by,
                            "prescription_date": prescription.prescribed_at.strftime("%Y-%m-%d") if prescription.prescribed_at else "Unknown",
                            "duration": prescription.duration,
                            "status": "Active" if is_recent else "Historical"
                        })
                
                retrieved_data = {
                    "recent_prescriptions": prescriptions_data,
                    "current_medications": current_medications,  # For medical doctor agent compatibility
                    "summary": {
                        "total_prescriptions": len(prescriptions_data),
                        "date_range": f"{start_date.date()} to {end_date.date()}",
                        "unique_medications": len(set(p.medication_name for p in prescriptions)),
                        "prescribing_doctors": len(set(p.prescribed_by for p in prescriptions if p.prescribed_by)),
                        "active_medications": len([med for med in current_medications if med["status"] == "Active"])
                    },
                    "analysis": analysis,
                    "medication_history": medication_history
                }
                
                state["retrieved_data"] = retrieved_data
                self.log_operation("retrieve", {"prescriptions_count": len(prescriptions_data)}, state)
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Prescription retrieval error: {str(e)}"
                return state
            finally:
                db.close()
    
    def _parse_datetime(self, date_str: str) -> datetime:
        """Parse date string or return current datetime"""
        if not date_str:
            return datetime.utcnow()
        
        try:
            if isinstance(date_str, str):
                # Try different date formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_str
        except:
            return datetime.utcnow()
    
    def _analyze_prescriptions(self, prescriptions: List[Prescription]) -> Dict[str, Any]:
        """Analyze prescription patterns"""
        if not prescriptions:
            return {}
        
        # Count medications by type/class
        medication_counts = {}
        prescriber_counts = {}
        frequency_patterns = {}
        
        for prescription in prescriptions:
            med_name = prescription.medication_name or "Unknown"
            prescriber = prescription.prescribed_by or "Unknown"
            frequency = prescription.frequency or "Unknown"
            
            medication_counts[med_name] = medication_counts.get(med_name, 0) + 1
            prescriber_counts[prescriber] = prescriber_counts.get(prescriber, 0) + 1
            frequency_patterns[frequency] = frequency_patterns.get(frequency, 0) + 1
        
        # Find most prescribed medications
        most_prescribed = sorted(medication_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Find most frequent prescribers
        top_prescribers = sorted(prescriber_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Identify potentially active prescriptions (last 30 days)
        recent_date = datetime.now() - timedelta(days=30)
        recent_prescriptions = [
            p for p in prescriptions 
            if p.prescribed_at and p.prescribed_at.replace(tzinfo=None) >= recent_date
        ]
        
        return {
            "most_prescribed_medications": [
                {"medication": med, "count": count} 
                for med, count in most_prescribed
            ],
            "top_prescribers": [
                {"prescriber": doc, "prescriptions": count}
                for doc, count in top_prescribers
            ],
            "frequency_patterns": frequency_patterns,
            "recent_prescriptions_count": len(recent_prescriptions),
            "total_unique_medications": len(medication_counts),
            "prescription_trend": self._calculate_prescription_trend(prescriptions)
        }
    
    def _track_medication_history(self, prescriptions: List[Prescription]) -> Dict[str, Any]:
        """Track medication history and changes"""
        if not prescriptions:
            return {}
        
        # Group by medication name
        med_groups = {}
        for prescription in prescriptions:
            med_name = prescription.medication_name
            if med_name not in med_groups:
                med_groups[med_name] = []
            med_groups[med_name].append(prescription)
        
        medication_history = {}
        for med_name, med_prescriptions in med_groups.items():
            # Sort by date
            med_prescriptions.sort(key=lambda x: x.prescribed_at, reverse=True)
            
            # Track dosage changes
            dosage_changes = []
            for i in range(len(med_prescriptions) - 1):
                current = med_prescriptions[i]
                previous = med_prescriptions[i + 1]
                
                if current.dosage != previous.dosage:
                    dosage_changes.append({
                        "from_dosage": previous.dosage,
                        "to_dosage": current.dosage,
                        "change_date": current.prescribed_at.isoformat(),
                        "prescribed_by": current.prescribed_by
                    })
            
            medication_history[med_name] = {
                "total_prescriptions": len(med_prescriptions),
                "first_prescribed": med_prescriptions[-1].prescribed_at.isoformat(),
                "last_prescribed": med_prescriptions[0].prescribed_at.isoformat(),
                "current_dosage": med_prescriptions[0].dosage,
                "dosage_changes": dosage_changes,
                "prescribing_doctors": list(set(p.prescribed_by for p in med_prescriptions if p.prescribed_by))
            }
        
        return medication_history
    
    def _calculate_prescription_trend(self, prescriptions: List[Prescription]) -> str:
        """Calculate overall prescription trend"""
        if len(prescriptions) < 4:
            return "insufficient_data"
        
        # Sort by date
        prescriptions.sort(key=lambda x: x.prescribed_at)
        
        # Compare first half vs second half
        mid_point = len(prescriptions) // 2
        first_half = prescriptions[:mid_point]
        second_half = prescriptions[mid_point:]
        
        first_half_rate = len(first_half) / max(1, (first_half[-1].prescribed_at - first_half[0].prescribed_at).days)
        second_half_rate = len(second_half) / max(1, (second_half[-1].prescribed_at - second_half[0].prescribed_at).days)
        
        if second_half_rate > first_half_rate * 1.2:
            return "increasing"
        elif second_half_rate < first_half_rate * 0.8:
            return "decreasing"
        else:
            return "stable"

    async def assess_question_relevance(self, question: str, user_id: int, session_id: int = None) -> Dict[str, Any]:
        """Assess if question is relevant to prescription data and determine retrieval strategy"""
        
        with trace_agent_operation(
            self.agent_name,
            "assess_question_relevance",
            user_id=user_id,
            session_id=session_id
        ):
            try:
                assessment_prompt = f"""
                Analyze this health question to determine if it's relevant to prescription/medication data.
                
                Prescription data includes: prescribed medications, dosages, frequencies, prescribing doctors,
                medication changes over time, adherence patterns, refill schedules, drug interactions,
                medication history, generic vs brand preferences.
                
                Question: {question}
                
                Respond with a JSON object:
                {{
                    "is_relevant": true/false,
                    "relevance_score": 0.0-1.0,
                    "focus_areas": ["current_medications", "medication_history", "dosage_changes", "prescribers"],
                    "time_sensitivity": "current_only" | "medication_trends" | "historical",
                    "reasoning": "Why this is/isn't relevant to prescription data"
                }}
                
                Examples:
                - "What medications am I currently taking?" → highly relevant, current_only
                - "Has my dosage changed recently?" → highly relevant, medication_trends
                - "What's my blood pressure?" → not relevant to prescriptions
                - "Who prescribed my medications?" → highly relevant, historical
                """
                
                messages = [
                    SystemMessage(content="You are a prescription data specialist assessing question relevance."),
                    HumanMessage(content=assessment_prompt)
                ]
                
                # Log ChatGPT interaction
                messages_dict = [
                    {"role": "system", "content": "You are a prescription data specialist assessing question relevance."},
                    {"role": "user", "content": assessment_prompt}
                ]
                
                response = self.llm.invoke(messages)
                
                # Log the interaction
                log_chatgpt_interaction(
                    agent_name="PrescriptionAgent",
                    operation="assess_question_relevance",
                    request_data=messages_dict,
                    response_data=response,
                    user_id=user_id,
                    session_id=session_id,
                    model_name=self.llm.model_name if hasattr(self.llm, 'model_name') else "unknown",
                    additional_metadata={"question": question[:100]}
                )
                
                assessment = json.loads(response.content)
                
                # Determine retrieval strategy
                if assessment.get("is_relevant", False):
                    time_sensitivity = assessment.get("time_sensitivity", "current_only")
                    
                    if time_sensitivity == "current_only":
                        retrieval_strategy = {
                            "days_back": 90,  # Last 3 months for current meds
                            "limit": 20,
                            "specific_filters": {"active_only": True},
                            "priority_data": ["recent_prescriptions", "summary"]
                        }
                    elif time_sensitivity == "medication_trends":
                        retrieval_strategy = {
                            "days_back": 365,  # Full year for trends
                            "limit": 50,
                            "specific_filters": {},
                            "priority_data": ["recent_prescriptions", "analysis", "medication_history"]
                        }
                    else:  # historical
                        retrieval_strategy = {
                            "days_back": 1095,  # 3 years for full history
                            "limit": 100,
                            "specific_filters": {},
                            "priority_data": ["recent_prescriptions", "analysis", "medication_history", "summary"]
                        }
                    
                    # Add focus area filters
                    focus_areas = assessment.get("focus_areas", [])
                    if focus_areas:
                        retrieval_strategy["specific_filters"]["focus_areas"] = focus_areas
                
                else:
                    retrieval_strategy = {
                        "days_back": 0,
                        "limit": 0,
                        "specific_filters": {},
                        "priority_data": []
                    }
                
                return {
                    "is_relevant": assessment.get("is_relevant", False),
                    "relevance_score": assessment.get("relevance_score", 0.0),
                    "retrieval_strategy": retrieval_strategy,
                    "reasoning": assessment.get("reasoning", "Assessment completed")
                }
                
            except Exception as e:
                return {
                    "is_relevant": False,
                    "relevance_score": 0.0,
                    "retrieval_strategy": {"days_back": 0, "limit": 0, "specific_filters": {}, "priority_data": []},
                    "reasoning": f"Assessment failed: {str(e)}"
                }

# Global instance
# prescription_agent = PrescriptionAgent()  # Commented to prevent startup hanging

# Lazy-loaded global instance
_prescription_agent = None

def get_prescription_agent():
    """Get or create the prescription agent instance"""
    global _prescription_agent
    if _prescription_agent is None:
        _prescription_agent = PrescriptionAgent()
    return _prescription_agent

# For backward compatibility
def prescription_agent():
    return get_prescription_agent()

# Convenience functions for orchestrator
async def extract_prescription_data(ocr_text: str, user_id: int, session_id: int = None) -> Dict[str, Any]:
    """Extract prescription data from OCR text"""
    agent = get_prescription_agent()
    return await agent.process_request(
        "extract",
        {"ocr_text": ocr_text},
        user_id,
        session_id
    )

async def store_prescription_data(prescription_data: Dict[str, Any], user_id: int, session_id: int = None) -> Dict[str, Any]:
    """Store prescription data to database"""
    agent = get_prescription_agent()
    return await agent.process_request(
        "store",
        {"extraction_request": prescription_data},
        user_id,
        session_id
    )

async def retrieve_prescription_data(user_id: int, session_id: int = None, days_back: int = 365, active_only: bool = False) -> Dict[str, Any]:
    """Retrieve prescription data from database"""
    agent = get_prescription_agent()
    return await agent.process_request(
        "retrieve",
        {"retrieval_request": {"days_back": days_back, "active_only": active_only}},
        user_id,
        session_id
    ) 