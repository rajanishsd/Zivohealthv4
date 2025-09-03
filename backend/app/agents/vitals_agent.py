import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseHealthAgent, AgentState
from app.models.vitals_data import VitalsRawData, VitalMetricType, VitalDataSource
from app.crud.vitals import VitalsCRUD
from app.schemas.vitals import VitalDataSubmission
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction
from langchain.schema import SystemMessage, HumanMessage
from app.utils.unit_converter import VitalUnitConverter, UnitConversionError

class VitalsAgent(BaseHealthAgent):
    """Specialized agent for processing vital signs data"""
    
    def __init__(self):
        super().__init__("VitalsAgent")
        # Agent swarm metadata
        self.specialization = "vital_signs"
        self.capabilities = ["extract", "store", "retrieve", "assess"]
        self.data_types = ["blood_pressure", "heart_rate", "temperature", "weight", "bmi"]
    
    async def extract_data(self, state: AgentState) -> AgentState:
        """Extract vital signs data from OCR text with enhanced telemetry"""
        
        with trace_agent_operation(
            self.agent_name,
            "extract_vitals",
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
                        "operation": "extract_vitals_data",
                        "ocr_text_length": len(state.get("ocr_text", "")),
                        "document_type": state.get("document_type", "unknown")
                    },
                    user_id=state["user_id"],
                    session_id=state["session_id"],
                    request_id=state["request_id"]
                )
                
                extraction_prompt = f"""
                Extract vital signs data from the following medical text. Look for:
                - Blood pressure (systolic/diastolic) in mmHg
                - Heart rate in BPM
                - Temperature in Celsius or Fahrenheit
                - Weight in kg or lbs
                - Height in cm or feet+inches
                - Blood sugar/glucose levels in mg/dL
                - Oxygen saturation (SpO2) in %
                - BMI if mentioned
                
                Return a JSON object with extracted values. Use null for missing values.
                Convert units to standard format (kg for weight, cm for height, Celsius for temperature).
                
                For measurement_date:
                - If text mentions "today", "as of today", or similar, use: "{__import__('app.utils.timezone', fromlist=['isoformat_now']).isoformat_now()}"
                - If a specific date is mentioned, parse and use that date
                - If no date is mentioned, use: "{__import__('app.utils.timezone', fromlist=['isoformat_now']).isoformat_now()}"
                
                Example format:
                {{
                    "blood_pressure_systolic": 120,
                    "blood_pressure_diastolic": 80,
                    "heart_rate": 72,
                    "temperature": 36.5,
                    "weight": 70.5,
                    "height": 175.0,
                    "blood_sugar": 95.0,
                    "oxygen_saturation": 98.0,
                    "bmi": 23.1,
                    "measurement_date": "{__import__('app.utils.timezone', fromlist=['isoformat_now']).isoformat_now()}",
                    "device_used": "Digital BP Monitor",
                    "notes": "Patient resting, no medication taken"
                }}
                """
                
                extraction_tool = self.get_extraction_tool()
                result = extraction_tool.func(state["ocr_text"], extraction_prompt)
                
                if "error" in result:
                    state["error_message"] = f"Vitals extraction failed: {result['error']}"
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
                    vitals_count = sum(1 for key in ["blood_pressure_systolic", "heart_rate", "temperature", "weight"] 
                                     if result.get(key) is not None)
                    log_agent_interaction(
                        self.agent_name,
                        "System",
                        "extraction_completed",
                        {
                            "vitals_extracted": vitals_count,
                            "has_blood_pressure": bool(result.get("blood_pressure_systolic")),
                            "has_heart_rate": bool(result.get("heart_rate")),
                            "has_temperature": bool(result.get("temperature")),
                            "has_weight": bool(result.get("weight")),
                            "data_quality_score": self._assess_extraction_quality(result)
                        },
                        user_id=state["user_id"],
                        session_id=state["session_id"],
                        request_id=state["request_id"]
                    )
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Vitals extraction error: {str(e)}"
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
        """Assess the quality of extracted vitals data"""
        key_vitals = ["blood_pressure_systolic", "blood_pressure_diastolic", "heart_rate", "temperature"]
        optional_vitals = ["weight", "height", "bmi", "oxygen_saturation", "blood_sugar"]
        
        quality_score = 0.0
        
        # Check key vitals (70% of score)
        key_present = sum(1 for vital in key_vitals if extracted_data.get(vital) is not None)
        quality_score += (key_present / len(key_vitals)) * 0.7
        
        # Check optional vitals (20% of score)
        optional_present = sum(1 for vital in optional_vitals if extracted_data.get(vital) is not None)
        quality_score += (optional_present / len(optional_vitals)) * 0.2
        
        # Check data validity (10% of score)
        if self._validate_vital_ranges(extracted_data):
            quality_score += 0.1
        
        return round(quality_score, 3)
    
    def _validate_vital_ranges(self, data: Dict[str, Any]) -> bool:
        """Validate that vital signs are within reasonable ranges"""
        try:
            if data.get("blood_pressure_systolic") and not (60 <= float(data["blood_pressure_systolic"]) <= 250):
                return False
            if data.get("heart_rate") and not (30 <= float(data["heart_rate"]) <= 250):
                return False
            if data.get("temperature") and not (30 <= float(data["temperature"]) <= 45):
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    async def store_data(self, state: AgentState) -> AgentState:
        """Store vital signs data to database"""
        
        with trace_agent_operation(
            self.agent_name,
            "store_vitals",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            db = self.get_database_session()
            try:
                # Get data to store
                data = state.get("extracted_data") or state.get("extraction_request", {})
                
                if not data:
                    state["error_message"] = "No vital signs data to store"
                    return state
                
                # Create vital signs records for each metric
                measurement_date = self._parse_date(data.get("measurement_date"))
                stored_records = []
                
                # Map extracted data to individual vital submissions
                vital_mappings = [
                    ("blood_pressure_systolic", VitalMetricType.BLOOD_PRESSURE_SYSTOLIC, "mmHg"),
                    ("blood_pressure_diastolic", VitalMetricType.BLOOD_PRESSURE_DIASTOLIC, "mmHg"),
                    ("heart_rate", VitalMetricType.HEART_RATE, "bpm"),
                    ("temperature", VitalMetricType.BODY_TEMPERATURE, "°C"),
                    ("weight", VitalMetricType.BODY_MASS, "kg"),
                    ("height", VitalMetricType.HEIGHT, "cm"),
                    ("bmi", VitalMetricType.BMI, "kg/m²"),
                    ("oxygen_saturation", VitalMetricType.OXYGEN_SATURATION, "%"),
                    ("blood_sugar", VitalMetricType.BLOOD_SUGAR, "mg/dL")
                ]
                
                for field_name, metric_type, unit in vital_mappings:
                    value = data.get(field_name)
                    if value is not None:
                        try:
                            # Convert units to standard format
                            input_unit = data.get(f"{field_name}_unit", unit)  # Use provided unit or default
                            converted_value, standard_unit = VitalUnitConverter.convert_to_standard_unit(
                                float(value), input_unit, metric_type
                            )
                            
                            vital_submission = VitalDataSubmission(
                                metric_type=metric_type,
                                value=converted_value,
                                unit=standard_unit,
                                start_date=measurement_date,
                                end_date=measurement_date,
                                data_source=VitalDataSource.MANUAL_ENTRY,
                                notes=data.get("notes"),
                                source_device=data.get("device_used"),
                                confidence_score=state.get("confidence_score", 0.8)
                            )
                        except UnitConversionError as e:
                            # Log conversion error but continue with original value and unit
                            print(f"Unit conversion error for {field_name}: {e}")
                            vital_submission = VitalDataSubmission(
                                metric_type=metric_type,
                                value=float(value),
                                unit=unit,
                                start_date=measurement_date,
                                end_date=measurement_date,
                                data_source=VitalDataSource.MANUAL_ENTRY,
                                notes=data.get("notes", f"Unit conversion failed: {e}"),
                                source_device=data.get("device_used"),
                                confidence_score=state.get("confidence_score", 0.8)
                            )
                        
                        # Store the vital data
                        stored_record = VitalsCRUD.create_raw_data(db, state["user_id"], vital_submission)
                        stored_records.append(stored_record)
                
                # Trigger aggregation for the measurement date
                if stored_records:
                    VitalsCRUD.aggregate_hourly_data(db, state["user_id"], measurement_date.date())
                    VitalsCRUD.aggregate_daily_data(db, state["user_id"], measurement_date.date())
                
                # Prepare response
                stored_records_summary = []
                for record in stored_records:
                    stored_records_summary.append({
                        "table": "vitals_raw_data",
                        "id": record.id,
                        "metric_type": record.metric_type,
                        "value": record.value,
                        "unit": record.unit,
                        "created_at": record.created_at.isoformat()
                    })
                
                state["stored_records"] = stored_records_summary
                self.log_operation("store", {"records_count": len(stored_records)}, state)
                
                return state
                
            except Exception as e:
                db.rollback()
                state["error_message"] = f"Vitals storage error: {str(e)}"
                return state
            finally:
                db.close()
    
    async def retrieve_data(self, state: AgentState) -> AgentState:
        """Retrieve vital signs data from database using aggregated data"""
        
        with trace_agent_operation(
            self.agent_name,
            "retrieve_vitals",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state["request_id"]
        ):
            db = self.get_database_session()
            try:
                retrieval_request = state.get("retrieval_request", {})
                
                # Get aggregated vitals data instead of overwhelming raw data
                # Daily data for recent week + Monthly data for longer trends
                vitals_data = self._get_aggregated_vitals_data(
                    db=db,
                    user_id=state["user_id"]
                )
                
                # Convert aggregated data to flat recent_measurements format for medical doctor agent compatibility
                recent_measurements = []
                
                # Add daily measurements (last 7 days)
                for daily_data in vitals_data.get("daily_data", []):
                    recent_measurements.append({
                        "measurement_type": daily_data["metric_type"],
                        "value": daily_data.get("average_value") or daily_data.get("total_value", 0),
                        "unit": daily_data["unit"],
                        "measurement_date": daily_data["date"],
                        "status": self._assess_vital_status(daily_data["metric_type"], daily_data.get("average_value") or daily_data.get("total_value", 0)),
                        "aggregation_type": "daily_average",
                        "data_source": "aggregated",
                        "count": daily_data.get("count", 1),
                        "min_value": daily_data.get("min_value"),
                        "max_value": daily_data.get("max_value")
                    })
                
                # Calculate trends from daily and monthly data
                trends = self._calculate_trends_from_aggregates(vitals_data)
                
                # Get latest values from most recent daily data
                latest_vitals = self._get_latest_vitals_from_aggregates(vitals_data)
                
                retrieved_data = {
                    "latest_vitals": latest_vitals,
                    "daily_aggregates": vitals_data.get("daily_data", []),
                    "monthly_aggregates": vitals_data.get("monthly_data", []),
                    "recent_measurements": recent_measurements,  # For medical doctor agent compatibility
                    "trends": trends,
                    "summary": {
                        "total_daily_records": len(vitals_data.get("daily_data", [])),
                        "total_monthly_records": len(vitals_data.get("monthly_data", [])),
                        "total_measurements": len(recent_measurements),
                        "date_range": "Daily: last 7 days, Monthly: last 3 months",
                        "has_recent_data": len(recent_measurements) > 0,
                        "unique_metrics": len(set(m["measurement_type"] for m in recent_measurements))
                    }
                }
                
                state["retrieved_data"] = retrieved_data
                self.log_operation("retrieve", {"daily_count": len(vitals_data.get("daily_data", [])), "monthly_count": len(vitals_data.get("monthly_data", []))}, state)
                
                return state
                
            except Exception as e:
                state["error_message"] = f"Vitals retrieval error: {str(e)}"
                return state
            finally:
                db.close()
    
    def _get_aggregated_vitals_data(self, db: Session, user_id: int) -> Dict[str, Any]:
        """Get aggregated vitals data: daily for last week, monthly for last 3 months"""
        today = date.today()
        
        # Get daily data for last 7 days
        week_start = today - timedelta(days=7)
        daily_data = []
        
        # Get all available metric types for this user
        available_metrics = db.query(VitalsRawData.metric_type).filter(
            VitalsRawData.user_id == user_id
        ).distinct().all()
        
        for metric_tuple in available_metrics:
            metric_type = metric_tuple[0]
            
            # Get daily aggregates for this metric
            daily_aggregates = VitalsCRUD.get_daily_aggregates(
                db=db,
                user_id=user_id,
                metric_type=metric_type,
                start_date=week_start,
                end_date=today
            )
            
            for aggregate in daily_aggregates:
                daily_data.append({
                    "metric_type": aggregate.metric_type,
                    "date": aggregate.date.isoformat(),
                    "average_value": aggregate.average_value,
                    "total_value": aggregate.total_value,
                    "min_value": aggregate.min_value,
                    "max_value": aggregate.max_value,
                    "count": aggregate.count,
                    "unit": aggregate.unit,
                    "duration_minutes": aggregate.duration_minutes
                })
        
        # Get monthly data for last 3 months
        monthly_data = []
        current_date = today
        
        for i in range(3):
            target_date = current_date - relativedelta(months=i)
            target_year = target_date.year
            target_month = target_date.month
            
            for metric_tuple in available_metrics:
                metric_type = metric_tuple[0]
                
                monthly_aggregates = VitalsCRUD.get_monthly_aggregates(
                    db=db,
                    user_id=user_id,
                    metric_type=metric_type,
                    start_year=target_year,
                    end_year=target_year
                )
                
                for aggregate in monthly_aggregates:
                    if aggregate.month == target_month:
                        monthly_data.append({
                            "metric_type": aggregate.metric_type,
                            "year": aggregate.year,
                            "month": aggregate.month,
                            "date": f"{aggregate.year}-{aggregate.month}",
                            "average_value": aggregate.average_value,
                            "total_value": aggregate.total_value,
                            "min_value": aggregate.min_value,
                            "max_value": aggregate.max_value,
                            "days_with_data": aggregate.days_with_data,
                            "unit": aggregate.unit,
                            "total_duration_minutes": aggregate.total_duration_minutes
                        })
        
        return {
            "daily_data": sorted(daily_data, key=lambda x: x["date"], reverse=True),
            "monthly_data": sorted(monthly_data, key=lambda x: x["date"], reverse=True)
        }
    
    def _assess_vital_status(self, metric_type: str, value: float) -> str:
        """Assess if a vital sign value is normal, high, or low"""
        if not value:
            return "Unknown"
            
        # Basic ranges for common vitals (could be enhanced with user-specific ranges)
        ranges = {
            "Heart Rate": (60, 100),
            "Blood Pressure Systolic": (90, 140),
            "Blood Pressure Diastolic": (60, 90),
            "Temperature": (36.1, 37.2),  # Celsius
            "Weight": (None, None),  # No standard range
            "BMI": (18.5, 25),
            "Oxygen Saturation": (95, 100),
            "Blood Sugar": (70, 140)  # mg/dL fasting
        }
        
        if metric_type not in ranges:
            return "Normal"  # Default for metrics without defined ranges
            
        min_val, max_val = ranges[metric_type]
        
        if min_val is None or max_val is None:
            return "Normal"
            
        if value < min_val:
            return "Low"
        elif value > max_val:
            return "High"
        else:
            return "Normal"
    
    def _calculate_trends_from_aggregates(self, vitals_data: Dict[str, Any]) -> Dict[str, str]:
        """Calculate trends from aggregated data"""
        trends = {}
        daily_data = vitals_data.get("daily_data", [])
        
        if len(daily_data) < 2:
            return trends
        
        # Group by metric type
        metrics_by_type = {}
        for item in daily_data:
            metric_type = item["metric_type"]
            if metric_type not in metrics_by_type:
                metrics_by_type[metric_type] = []
            metrics_by_type[metric_type].append(item)
        
        # Calculate trends for each metric
        for metric_type, metric_data in metrics_by_type.items():
            if len(metric_data) >= 2:
                # Sort by date
                sorted_data = sorted(metric_data, key=lambda x: x["date"])
                latest = sorted_data[-1]
                previous = sorted_data[-2]
                
                latest_val = latest.get("average_value") or latest.get("total_value", 0)
                previous_val = previous.get("average_value") or previous.get("total_value", 0)
                
                if latest_val and previous_val:
                    percent_change = ((latest_val - previous_val) / previous_val) * 100
                    
                    if abs(percent_change) < 5:  # Less than 5% change
                        trends[metric_type.lower().replace(" ", "_")] = "stable"
                    elif percent_change > 0:
                        trends[metric_type.lower().replace(" ", "_")] = "increasing"
                    else:
                        trends[metric_type.lower().replace(" ", "_")] = "decreasing"
        
        return trends
    
    def _get_latest_vitals_from_aggregates(self, vitals_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get latest vital values from aggregated data"""
        daily_data = vitals_data.get("daily_data", [])
        
        if not daily_data:
            return None
        
        # Get most recent day's data
        latest_date = max(item["date"] for item in daily_data)
        latest_day_data = [item for item in daily_data if item["date"] == latest_date]
        
        latest_vitals = {
            "measurement_date": latest_date,
            "data_source": "daily_aggregates",
            "metrics": {}
        }
        
        for item in latest_day_data:
            latest_vitals["metrics"][item["metric_type"]] = {
                "value": item.get("average_value") or item.get("total_value", 0),
                "unit": item["unit"],
                "count": item.get("count", 1),
                "min_value": item.get("min_value"),
                "max_value": item.get("max_value")
            }
        
        return latest_vitals

    def _get_diverse_vitals_data(
        self,
        db: Session,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        limit: int
    ) -> List[VitalsRawData]:
        """Get diverse vitals data with better coverage across metric types and time"""
        
        # Priority vitals for medical consultation (especially important but potentially less frequent)
        priority_metrics = [
            "Blood Pressure Systolic", "Blood Pressure Diastolic", "Weight", 
            "Temperature", "Blood Sugar", "BMI", "Oxygen Saturation"
        ]
        
        # Common vitals (more frequent)
        common_metrics = [
            "Heart Rate", "Steps", "Active Energy", "Sleep", "Stand Hours",
            "Flights Climbed", "Workout Duration", "Workout Calories"
        ]
        
        all_vitals = []
        
        # Strategy 1: Get ALL priority vitals within date range (these are rare but important)
        for metric in priority_metrics:
            priority_vitals = VitalsCRUD.get_raw_data(
                db=db,
                user_id=user_id,
                metric_types=[metric],
                start_date=start_date,
                end_date=end_date,
                limit=50  # Get more of these important ones
            )
            all_vitals.extend(priority_vitals)
        
        # Strategy 2: Get recent + historical samples of common metrics
        remaining_limit = max(0, limit - len(all_vitals))
        if remaining_limit > 0:
            # Get recent common vitals (last 7 days for latest values)
            recent_end = end_date
            recent_start = max(start_date, end_date - timedelta(days=7))
            
            recent_common = VitalsCRUD.get_raw_data(
                db=db,
                user_id=user_id,
                metric_types=common_metrics,
                start_date=recent_start,
                end_date=recent_end,
                limit=remaining_limit // 2
            )
            all_vitals.extend(recent_common)
            
            # Get historical samples spread across the time range
            remaining_limit = max(0, limit - len(all_vitals))
            if remaining_limit > 0:
                historical_common = VitalsCRUD.get_raw_data(
                    db=db,
                    user_id=user_id,
                    metric_types=common_metrics,
                    start_date=start_date,
                    end_date=recent_start,
                    limit=remaining_limit
                )
                all_vitals.extend(historical_common)
        
        # Remove duplicates and sort by date (most recent first)
        seen_ids = set()
        unique_vitals = []
        for vital in all_vitals:
            if vital.id not in seen_ids:
                seen_ids.add(vital.id)
                unique_vitals.append(vital)
        
        # Sort by date (most recent first) and apply final limit
        unique_vitals.sort(key=lambda x: x.start_date, reverse=True)
        
        return unique_vitals[:limit]
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string or return current time"""
        if not date_str:
            return datetime.utcnow()
        
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return datetime.utcnow()
    
    async def assess_question_relevance(self, question: str, user_id: int, session_id: int = None) -> Dict[str, Any]:
        """Assess if question is relevant to vitals data and determine retrieval strategy"""
        
        with trace_agent_operation(
            self.agent_name,
            "assess_question_relevance",
            user_id=user_id,
            session_id=session_id
        ):
            try:
                # Use LLM to assess relevance to vitals
                assessment_prompt = f"""
                Analyze this health question to determine if it's relevant to vital signs data.
                
                Vital signs include: blood pressure, heart rate, temperature, weight, height, BMI, 
                blood sugar/glucose, oxygen saturation, breathing rate.
                
                Question: {question}
                
                Respond with a JSON object:
                {{
                    "is_relevant": true/false,
                    "relevance_score": 0.0-1.0,
                    "specific_vitals": ["blood_pressure", "heart_rate", etc.],
                    "time_sensitivity": "recent_only" | "trends_needed" | "historical",
                    "reasoning": "Why this is/isn't relevant to vitals"
                }}
                
                Examples:
                - "What's my blood pressure?" → highly relevant, recent_only
                - "Am I losing weight?" → highly relevant, trends_needed  
                - "What medications do I take?" → not relevant to vitals
                - "How is my health overall?" → moderately relevant, trends_needed
                """
                
                messages = [
                    SystemMessage(content="You are a medical vitals specialist assessing question relevance."),
                    HumanMessage(content=assessment_prompt)
                ]
                
                response = self.llm.invoke(messages)
                assessment = json.loads(response.content)
                
                # Determine retrieval strategy based on assessment
                if assessment.get("is_relevant", False):
                    time_sensitivity = assessment.get("time_sensitivity", "recent_only")
                    
                    if time_sensitivity == "recent_only":
                        retrieval_strategy = {
                            "days_back": 7,
                            "limit": 5,
                            "specific_filters": {},
                            "priority_data": ["latest_vitals", "summary"]
                        }
                    elif time_sensitivity == "trends_needed":
                        retrieval_strategy = {
                            "days_back": 90,
                            "limit": 20,
                            "specific_filters": {},
                            "priority_data": ["history", "trends", "latest_vitals"]
                        }
                    else:  # historical
                        retrieval_strategy = {
                            "days_back": 365,
                            "limit": 50,
                            "specific_filters": {},
                            "priority_data": ["history", "trends", "summary"]
                        }
                    
                    # Add specific vital filters if mentioned
                    specific_vitals = assessment.get("specific_vitals", [])
                    if specific_vitals:
                        retrieval_strategy["specific_filters"]["focus_vitals"] = specific_vitals
                    
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
                # Default to low relevance if assessment fails
                return {
                    "is_relevant": False,
                    "relevance_score": 0.0,
                    "retrieval_strategy": {"days_back": 0, "limit": 0, "specific_filters": {}, "priority_data": []},
                    "reasoning": f"Assessment failed: {str(e)}"
                }

# Lazy-loaded global instance
_vitals_agent = None

def get_vitals_agent():
    """Get or create the vitals agent instance"""
    global _vitals_agent
    if _vitals_agent is None:
        _vitals_agent = VitalsAgent()
    return _vitals_agent

# For backward compatibility, create a module-level property-like access
def vitals_agent():
    return get_vitals_agent()

# Convenience functions for orchestrator
async def extract_vitals_data(ocr_text: str, user_id: int, session_id: int = None) -> Dict[str, Any]:
    """Extract vitals data from OCR text"""
    agent = get_vitals_agent()
    return await agent.process_request(
        "extract",
        {"ocr_text": ocr_text},
        user_id,
        session_id
    )

async def store_vitals_data(vitals_data: Dict[str, Any], user_id: int, session_id: int = None) -> Dict[str, Any]:
    """Store vitals data to database"""
    agent = get_vitals_agent()
    return await agent.process_request(
        "store",
        {"extraction_request": vitals_data},
        user_id,
        session_id
    )

async def retrieve_vitals_data(user_id: int, session_id: int = None, days_back: int = 30) -> Dict[str, Any]:
    """Retrieve vitals data from database"""
    agent = get_vitals_agent()
    return await agent.process_request(
        "retrieve",
        {"retrieval_request": {"days_back": days_back}},
        user_id,
        session_id
    ) 