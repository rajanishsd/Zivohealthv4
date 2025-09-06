#!/usr/bin/env python3

"""
Nutrition Agent - Analyzes food images to extract nutritional information
and manages nutrition data with daily/weekly summaries for medical consultations.
"""

import json
import time
import base64
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.nutrition_data import (
    NutritionRawData, NutritionDailyAggregate, NutritionWeeklyAggregate,
    NutritionDataSource, MealType, DishType
)
from app.crud import nutrition as crud_nutrition
from app.core.telemetry_simple import trace_agent_operation, log_agent_interaction
from app.agents.guardrails_system import validate_agent_response, generate_user_friendly_violation_message


class NutritionAgent:
    """Nutrition Agent for food image analysis and nutrition data management"""
    
    def __init__(self):
        self.agent_name = "NutritionAgent"
        self.model_name = settings.NUTRITION_AGENT_MODEL or settings.DEFAULT_AI_MODEL
        self.vision_model = "gpt-4o"  # Updated to use gpt-4o instead of deprecated gpt-4-vision-preview
        
        self.llm = ChatOpenAI(
            model=self.model_name,
            timeout=45
        )
        
        self.vision_llm = ChatOpenAI(
            model=self.vision_model,
            timeout=60
        )

    async def process_request(
        self,
        operation: str,
        request_data: Dict[str, Any],
        user_id: int,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Main entry point for nutrition agent operations"""
        
        with trace_agent_operation(
            self.agent_name,
            f"process_request_{operation}",
            user_id=user_id,
            session_id=session_id,
            operation_type=operation
        ):
            try:
                if operation == "extract":
                    return await self._extract_nutrition_from_image(request_data, user_id, session_id)
                elif operation == "store":
                    return await self._store_nutrition_data(request_data, user_id, session_id)
                elif operation == "retrieve":
                    return await self._retrieve_nutrition_data(request_data, user_id, session_id)
                elif operation == "assess":
                    return await self._assess_question_relevance(request_data, user_id, session_id)
                else:
                    return {
                        "success": False,
                        "error": f"Unknown operation: {operation}",
                        "response_message": {
                            "success": False,
                            "error": f"Nutrition agent does not support operation: {operation}"
                        }
                    }
                    
            except Exception as e:
                print(f"❌ [DEBUG] NutritionAgent operation {operation} failed: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "response_message": {
                        "success": False,
                        "error": f"Nutrition analysis failed: {str(e)}"
                    }
                }

    async def _extract_nutrition_from_image(
        self,
        request_data: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """Extract nutritional information from food image using GPT-4V"""
        
        with trace_agent_operation(
            self.agent_name,
            "extract_nutrition_from_image",
            user_id=user_id,
            session_id=session_id,
            extraction_step="nutrition_analysis"
        ):
            try:
                image_path = request_data.get("image_path")
                if not image_path or not Path(image_path).exists():
                    return {
                        "success": False,
                        "error": "Image file not found",
                        "response_message": {
                            "success": False,
                            "error": "Image file not found for nutrition analysis"
                        }
                    }

                # Read and encode image
                with open(image_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')

                # Create prompt for nutrition extraction
                nutrition_prompt = self._create_nutrition_extraction_prompt()

                # Analyze image with GPT-4V
                messages = [
                    SystemMessage(content="You are a nutrition expert analyzing food images to extract detailed nutritional information."),
                    HumanMessage(content=[
                        {"type": "text", "text": nutrition_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ])
                ]

                response = self.vision_llm.invoke(messages)
                
                if not response or not response.content:
                    return {
                        "success": False,
                        "error": "Empty response from vision model",
                        "response_message": {
                            "success": False,
                            "error": "Failed to analyze food image"
                        }
                    }

                # Parse nutrition data from response
                nutrition_data = self._parse_nutrition_response(response.content)
                
                if not nutrition_data:
                    return {
                        "success": False,
                        "error": "Failed to parse nutrition data",
                        "response_message": {
                            "success": False,
                            "error": "Could not extract nutritional information from image"
                        }
                    }

                # Add metadata
                nutrition_data["image_path"] = image_path
                nutrition_data["confidence_score"] = nutrition_data.get("confidence_score", 0.8)
                nutrition_data["data_source"] = NutritionDataSource.PHOTO_ANALYSIS.value

                return {
                    "success": True,
                    "response_message": {
                        "success": True,
                        "data": nutrition_data,
                        "message": f"Successfully extracted nutrition data for {nutrition_data.get('dish_name', 'food item')}"
                    }
                }

            except Exception as e:
                print(f"❌ [DEBUG] Nutrition extraction failed: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "response_message": {
                        "success": False,
                        "error": f"Nutrition extraction failed: {str(e)}"
                    }
                }

    def _create_nutrition_extraction_prompt(self) -> str:
        """Create prompt for nutrition extraction from food images"""
        
        return """
        Analyze this food image and extract detailed nutritional information. Please provide a comprehensive analysis including:

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

        **Example Response Structure**:
        ```json
        {
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
        }
        ```

        Please analyze the image and provide the nutritional information in this exact JSON format.
        """

    def _parse_nutrition_response(self, response_content: str) -> Optional[Dict[str, Any]]:
        """Parse nutrition data from AI response, robustly extracting JSON."""
        try:
            # Log the raw response for debugging
            print(f"[DEBUG] Raw AI nutrition response: {response_content[:500]}")
            content = response_content.strip()
            if not content:
                print("⚠️ [DEBUG] Nutrition response is empty.")
                return None
            # Try to extract JSON block using regex
            json_match = re.search(r'\{[\s\S]*?\}', content)
            if json_match:
                content = json_match.group(0)
            # Parse JSON
            nutrition_data = json.loads(content)
            # Validate required fields
            required_fields = ["dish_name", "food_item_name", "portion_size", "portion_unit", "calories"]
            missing_fields = []
            for field in required_fields:
                if field not in nutrition_data or nutrition_data[field] is None:
                    missing_fields.append(field)
                    print(f"⚠️ [DEBUG] Missing required field: {field}")
            if missing_fields:
                print(f"❌ [DEBUG] Missing required fields: {missing_fields}")
                return None
            # Ensure numeric fields are floats
            numeric_fields = [
                "portion_size", "calories", "protein_g", "fat_g", "carbs_g", "fiber_g", "sugar_g", "sodium_mg",
                "vitamin_a_mcg", "vitamin_c_mg", "vitamin_d_mcg", "vitamin_e_mg", "vitamin_k_mcg",
                "vitamin_b1_mg", "vitamin_b2_mg", "vitamin_b3_mg", "vitamin_b6_mg", "vitamin_b12_mcg", "folate_mcg",
                "calcium_mg", "iron_mg", "magnesium_mg", "phosphorus_mg", "potassium_mg", "zinc_mg",
                "copper_mg", "manganese_mg", "selenium_mcg", "confidence_score"
            ]
            for field in numeric_fields:
                if field in nutrition_data and nutrition_data[field] is not None:
                    try:
                        nutrition_data[field] = float(nutrition_data[field])
                    except (ValueError, TypeError):
                        nutrition_data[field] = 0.0
                        print(f"⚠️ [DEBUG] Invalid numeric value for {field}, setting to 0.0")
            # Set default values for missing optional fields
            optional_defaults = {
                "dish_type": "other",
                "meal_type": "snack",
                "confidence_score": 0.8,
                "notes": "Estimated values based on typical preparation"
            }
            for field, default_value in optional_defaults.items():
                if field not in nutrition_data or nutrition_data[field] is None:
                    nutrition_data[field] = default_value
            print(f"✅ [DEBUG] Successfully parsed nutrition data with {len(nutrition_data)} fields")
            return nutrition_data
        except json.JSONDecodeError as e:
            print(f"⚠️ [DEBUG] Failed to parse nutrition JSON: {e}")
            print(f"⚠️ [DEBUG] Raw response: {response_content[:200]}...")
            return None
        except Exception as e:
            print(f"⚠️ [DEBUG] Error parsing nutrition response: {e}")
            return None

    async def _store_nutrition_data(
        self,
        request_data: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """Store extracted nutrition data to database"""
        
        with trace_agent_operation(
            self.agent_name,
            "store_nutrition_data",
            user_id=user_id,
            session_id=session_id,
            storage_step="database_insert"
        ):
            try:
                nutrition_data = request_data.get("nutrition_data", {})
                from app.utils.timezone import now_local
                meal_time = request_data.get("meal_time", now_local())
                meal_type = request_data.get("meal_type", MealType.OTHER.value)

                # Create nutrition record
                db_nutrition = NutritionRawData(
                    user_id=user_id,
                    food_item_name=nutrition_data.get("food_item_name", ""),
                    dish_name=nutrition_data.get("dish_name", ""),
                    dish_type=nutrition_data.get("dish_type", DishType.OTHER.value),
                    meal_type=meal_type,
                    portion_size=nutrition_data.get("portion_size", 0.0),
                    portion_unit=nutrition_data.get("portion_unit", "grams"),
                    
                    # Macronutrients
                    calories=nutrition_data.get("calories", 0.0),
                    protein_g=nutrition_data.get("protein_g", 0.0),
                    fat_g=nutrition_data.get("fat_g", 0.0),
                    carbs_g=nutrition_data.get("carbs_g", 0.0),
                    fiber_g=nutrition_data.get("fiber_g", 0.0),
                    sugar_g=nutrition_data.get("sugar_g", 0.0),
                    sodium_mg=nutrition_data.get("sodium_mg", 0.0),
                    
                    # Vitamins
                    vitamin_a_mcg=nutrition_data.get("vitamin_a_mcg", 0.0),
                    vitamin_c_mg=nutrition_data.get("vitamin_c_mg", 0.0),
                    vitamin_d_mcg=nutrition_data.get("vitamin_d_mcg", 0.0),
                    vitamin_e_mg=nutrition_data.get("vitamin_e_mg", 0.0),
                    vitamin_k_mcg=nutrition_data.get("vitamin_k_mcg", 0.0),
                    vitamin_b1_mg=nutrition_data.get("vitamin_b1_mg", 0.0),
                    vitamin_b2_mg=nutrition_data.get("vitamin_b2_mg", 0.0),
                    vitamin_b3_mg=nutrition_data.get("vitamin_b3_mg", 0.0),
                    vitamin_b6_mg=nutrition_data.get("vitamin_b6_mg", 0.0),
                    vitamin_b12_mcg=nutrition_data.get("vitamin_b12_mcg", 0.0),
                    folate_mcg=nutrition_data.get("folate_mcg", 0.0),
                    
                    # Minerals
                    calcium_mg=nutrition_data.get("calcium_mg", 0.0),
                    iron_mg=nutrition_data.get("iron_mg", 0.0),
                    magnesium_mg=nutrition_data.get("magnesium_mg", 0.0),
                    phosphorus_mg=nutrition_data.get("phosphorus_mg", 0.0),
                    potassium_mg=nutrition_data.get("potassium_mg", 0.0),
                    zinc_mg=nutrition_data.get("zinc_mg", 0.0),
                    copper_mg=nutrition_data.get("copper_mg", 0.0),
                    manganese_mg=nutrition_data.get("manganese_mg", 0.0),
                    selenium_mcg=nutrition_data.get("selenium_mcg", 0.0),
                    
                    # Metadata
                    meal_date=meal_time.date() if isinstance(meal_time, datetime) else meal_time,
                    meal_time=meal_time if isinstance(meal_time, datetime) else datetime.combine(meal_time, datetime.min.time()),
                    data_source=nutrition_data.get("data_source", NutritionDataSource.PHOTO_ANALYSIS.value),
                    confidence_score=nutrition_data.get("confidence_score", 0.8),
                    image_url=nutrition_data.get("image_path", ""),
                    aggregation_status="pending"
                )

                # Save to database
                with SessionLocal() as db:
                    db.add(db_nutrition)
                    db.commit()
                    db.refresh(db_nutrition)

                    # Create storage summary
                    storage_summary = {
                        "records_stored": 1,
                        "nutrition_id": db_nutrition.id,
                        "dish_name": db_nutrition.dish_name,
                        "calories": db_nutrition.calories,
                        "meal_type": db_nutrition.meal_type,
                        "meal_date": str(db_nutrition.meal_date)
                    }

                # Trigger aggregation for nutrition data
                print(f"🚀 [DEBUG] Triggering nutrition aggregation worker for meal on {db_nutrition.meal_date}")
                import subprocess
                import os
                
                try:
                    worker_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "aggregation", "worker_process.py")
                    subprocess.Popen(
                        ["python", worker_script],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=os.path.dirname(worker_script)
                    )
                    print(f"✅ [DEBUG] Nutrition aggregation worker triggered successfully")
                except Exception as e:
                    print(f"❌ [DEBUG] Failed to trigger nutrition aggregation worker: {e}")

                return {
                    "success": True,
                    "response_message": {
                        "success": True,
                        "data": storage_summary,
                        "message": f"Successfully stored nutrition data for {db_nutrition.dish_name}"
                    }
                }

            except Exception as e:
                print(f"❌ [DEBUG] Nutrition storage failed: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "response_message": {
                        "success": False,
                        "error": f"Failed to store nutrition data: {str(e)}"
                    }
                }

    async def _retrieve_nutrition_data(
        self,
        request_data: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """Retrieve nutrition data based on request parameters"""
        
        with trace_agent_operation(
            self.agent_name,
            "retrieve_nutrition_data",
            user_id=user_id,
            session_id=session_id,
            retrieval_step="database_query"
        ):
            try:
                retrieval_request = request_data.get("retrieval_request", {})
                days_back = retrieval_request.get("days_back", 30)
                limit = retrieval_request.get("limit", 50)
                summary_type = retrieval_request.get("summary_type", "combined")  # combined, daily, weekly

                end_date = date.today()
                
                # For medical doctor agent: get daily data for last week + monthly data for last 30 days
                if summary_type == "combined" or days_back >= 30:
                    return await self._get_combined_nutrition_data(user_id, session_id)
                else:
                    start_date = end_date - timedelta(days=days_back)

                with SessionLocal() as db:
                    if summary_type == "daily":
                        # Get daily aggregates
                        daily_aggregates = crud_nutrition.nutrition_daily_aggregate.get_by_user_date_range(
                            db=db,
                            user_id=user_id,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        # Convert daily aggregates to recent_meals format for medical doctor agent compatibility
                        recent_meals = []
                        for agg in daily_aggregates:
                            # Create meal entries for each meal type with calories > 0
                            meal_types = [
                                ("breakfast", agg.breakfast_calories),
                                ("lunch", agg.lunch_calories), 
                                ("dinner", agg.dinner_calories),
                                ("snack", agg.snack_calories)
                            ]
                            
                            for meal_type, calories in meal_types:
                                if calories and calories > 0:
                                    recent_meals.append({
                                        "meal_type": meal_type.title(),
                                        "meal_date": str(agg.date),
                                        "calories": calories,
                                        "protein_g": agg.total_protein_g / agg.meal_count if agg.meal_count > 0 else 0,
                                        "carbs_g": agg.total_carbs_g / agg.meal_count if agg.meal_count > 0 else 0,
                                        "fat_g": agg.total_fat_g / agg.meal_count if agg.meal_count > 0 else 0,
                                        "notes": f"Daily aggregate: {agg.meal_count} total meals, {agg.total_calories} total cal"
                                    })
                        
                        # Calculate nutritional summary
                        if daily_aggregates:
                            total_days = len(daily_aggregates)
                            avg_calories = sum(agg.total_calories for agg in daily_aggregates) / total_days
                            avg_protein = sum(agg.total_protein_g for agg in daily_aggregates) / total_days
                            avg_carbs = sum(agg.total_carbs_g for agg in daily_aggregates) / total_days
                            avg_fat = sum(agg.total_fat_g for agg in daily_aggregates) / total_days
                            
                            nutritional_summary = {
                                "avg_daily_calories": round(avg_calories, 1),
                                "avg_protein": round(avg_protein, 1),
                                "avg_carbs": round(avg_carbs, 1),
                                "avg_fat": round(avg_fat, 1),
                                "date_range": f"{start_date} to {end_date}",
                                "total_days": total_days
                            }
                        else:
                            nutritional_summary = {}
                        
                        summary_data = {
                            "summary_type": "daily",
                            "date_range": {"start": str(start_date), "end": str(end_date)},
                            "daily_summaries": [
                                {
                                    "date": str(agg.date),
                                    "total_calories": agg.total_calories,
                                    "total_protein_g": agg.total_protein_g,
                                    "total_fat_g": agg.total_fat_g,
                                    "total_carbs_g": agg.total_carbs_g,
                                    "total_fiber_g": agg.total_fiber_g,
                                    "meal_count": agg.meal_count,
                                    "breakfast_calories": agg.breakfast_calories,
                                    "lunch_calories": agg.lunch_calories,
                                    "dinner_calories": agg.dinner_calories,
                                    "snack_calories": agg.snack_calories
                                }
                                for agg in daily_aggregates
                            ],
                            "recent_meals": recent_meals,  # For medical doctor agent compatibility
                            "nutritional_summary": nutritional_summary  # For medical doctor agent compatibility
                        }
                        
                    elif summary_type == "weekly":
                        # Get weekly aggregates
                        weekly_aggregates = crud_nutrition.nutrition_weekly_aggregate.get_by_user_date_range(
                            db=db,
                            user_id=user_id,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        summary_data = {
                            "summary_type": "weekly",
                            "date_range": {"start": str(start_date), "end": str(end_date)},
                            "weekly_summaries": [
                                {
                                    "week_start": str(agg.week_start_date),
                                    "week_end": str(agg.week_end_date),
                                    "avg_daily_calories": agg.avg_daily_calories,
                                    "avg_daily_protein_g": agg.avg_daily_protein_g,
                                    "avg_daily_fat_g": agg.avg_daily_fat_g,
                                    "avg_daily_carbs_g": agg.avg_daily_carbs_g,
                                    "total_weekly_calories": agg.total_weekly_calories,
                                    "days_with_data": agg.days_with_data
                                }
                                for agg in weekly_aggregates
                            ]
                        }
                    
                    else:
                        # Get raw nutrition data
                        raw_data = crud_nutrition.nutrition_data.get_multi_by_user(
                            db=db,
                            user_id=user_id,
                            params=crud_nutrition.NutritionQueryParams(
                                start_date=start_date,
                                end_date=end_date,
                                limit=limit
                            )
                        )
                        
                        summary_data = {
                            "summary_type": "raw",
                            "date_range": {"start": str(start_date), "end": str(end_date)},
                            "nutrition_records": [
                                {
                                    "id": record.id,
                                    "dish_name": record.dish_name,
                                    "meal_type": record.meal_type,
                                    "meal_date": str(record.meal_date),
                                    "calories": record.calories,
                                    "protein_g": record.protein_g,
                                    "fat_g": record.fat_g,
                                    "carbs_g": record.carbs_g,
                                    "dish_type": record.dish_type
                                }
                                for record in raw_data
                            ]
                        }

                return {
                    "success": True,
                    "response_message": {
                        "success": True,
                        "data": summary_data,
                        "message": f"Retrieved {summary_type} nutrition data for {days_back} days"
                    }
                }

            except Exception as e:
                print(f"❌ [DEBUG] Nutrition retrieval failed: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "response_message": {
                        "success": False,
                        "error": f"Failed to retrieve nutrition data: {str(e)}"
                    }
                }

    async def _get_combined_nutrition_data(
        self,
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """Get combined nutrition data: daily for last week + monthly summary for last 30 days"""
        
        with trace_agent_operation(
            self.agent_name,
            "get_combined_nutrition_data",
            user_id=user_id,
            session_id=session_id,
            retrieval_step="combined_aggregates"
        ):
            try:
                end_date = date.today()
                
                with SessionLocal() as db:
                    # Get daily data for last 7 days
                    week_start = end_date - timedelta(days=7)
                    daily_aggregates = crud_nutrition.nutrition_daily_aggregate.get_by_user_date_range(
                        db=db,
                        user_id=user_id,
                        start_date=week_start,
                        end_date=end_date
                    )
                    
                    # Get monthly data for context (last 30 days worth)
                    month_start = end_date - timedelta(days=30)
                    monthly_aggregates = crud_nutrition.nutrition_daily_aggregate.get_by_user_date_range(
                        db=db,
                        user_id=user_id,
                        start_date=month_start,
                        end_date=end_date
                    )
                    
                    # Get raw nutrition data for last 10 days to include actual food descriptions
                    raw_start = end_date - timedelta(days=10)
                    raw_nutrition_data = crud_nutrition.nutrition_data.get_multi_by_user(
                        db=db,
                        user_id=user_id,
                        params=crud_nutrition.NutritionQueryParams(
                            start_date=raw_start,
                            end_date=end_date,
                            limit=100  # Get up to 100 recent meals
                        )
                    )
                    
                    # Convert raw nutrition data to recent_meals format with actual food descriptions
                    recent_meals = []
                    for record in raw_nutrition_data:
                        recent_meals.append({
                            "meal_type": record.meal_type.title() if record.meal_type else "Unknown",
                            "meal_date": str(record.meal_date),
                            "dish_name": record.dish_name or "Unknown dish",
                            "food_item_name": record.food_item_name or "",
                            "calories": record.calories or 0,
                            "protein_g": round(record.protein_g or 0, 1),
                            "carbs_g": round(record.carbs_g or 0, 1),
                            "fat_g": round(record.fat_g or 0, 1),
                            "fiber_g": round(record.fiber_g or 0, 1),
                            "portion_size": record.portion_size or "",
                            "portion_unit": record.portion_unit or "",
                            "notes": record.notes or f"Real food item: {record.dish_name}",
                            "data_source": getattr(record, 'data_source', 'photo_analysis')
                        })
                    
                    # Sort recent meals by date (newest first)
                    recent_meals.sort(key=lambda x: x["meal_date"], reverse=True)
                    
                    # Calculate comprehensive nutritional summary from 30-day data
                    if monthly_aggregates:
                        total_days = len(monthly_aggregates)
                        total_calories = sum(agg.total_calories for agg in monthly_aggregates)
                        total_protein = sum(agg.total_protein_g for agg in monthly_aggregates)
                        total_carbs = sum(agg.total_carbs_g for agg in monthly_aggregates)
                        total_fat = sum(agg.total_fat_g for agg in monthly_aggregates)
                        total_fiber = sum(agg.total_fiber_g or 0 for agg in monthly_aggregates)
                        
                        nutritional_summary = {
                            "avg_daily_calories": round(total_calories / total_days, 1),
                            "avg_protein": round(total_protein / total_days, 1),
                            "avg_carbs": round(total_carbs / total_days, 1),
                            "avg_fat": round(total_fat / total_days, 1),
                            "avg_fiber": round(total_fiber / total_days, 1),
                            "total_calories_30days": total_calories,
                            "date_range": f"{month_start} to {end_date}",
                            "total_days": total_days,
                            "recent_week_days": len(daily_aggregates)
                        }
                    else:
                        nutritional_summary = {
                            "avg_daily_calories": "N/A",
                            "avg_protein": "N/A", 
                            "avg_carbs": "N/A",
                            "avg_fat": "N/A",
                            "date_range": f"{month_start} to {end_date}",
                            "total_days": 0
                        }
                    
                    combined_data = {
                        "summary_type": "combined",
                        "date_range": {"start": str(week_start), "end": str(end_date)},
                        "recent_meals": recent_meals,  # For medical doctor agent
                        "nutritional_summary": nutritional_summary,  # For medical doctor agent
                        "daily_data_week": [
                            {
                                "date": str(agg.date),
                                "total_calories": agg.total_calories,
                                "total_protein_g": agg.total_protein_g,
                                "total_fat_g": agg.total_fat_g,
                                "total_carbs_g": agg.total_carbs_g,
                                "total_fiber_g": agg.total_fiber_g,
                                "meal_count": agg.meal_count
                            }
                            for agg in daily_aggregates
                        ],
                        "monthly_summary": {
                            "days_with_data": len(monthly_aggregates),
                            "avg_daily_calories": nutritional_summary["avg_daily_calories"],
                            "avg_macros": {
                                "protein_g": nutritional_summary["avg_protein"],
                                "carbs_g": nutritional_summary["avg_carbs"], 
                                "fat_g": nutritional_summary["avg_fat"]
                            }
                        }
                    }
                    
                    return {
                        "success": True,
                        "response_message": {
                            "success": True,
                            "data": combined_data,
                            "message": f"Retrieved combined nutrition data: {len(daily_aggregates)} daily records (last week) + 30-day summary"
                        }
                    }

            except Exception as e:
                print(f"❌ [DEBUG] Combined nutrition retrieval failed: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "response_message": {
                        "success": False,
                        "error": f"Failed to retrieve combined nutrition data: {str(e)}"
                    }
                }

    async def _assess_question_relevance(
        self,
        request_data: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """Assess if a question is relevant to nutrition data"""
        
        with trace_agent_operation(
            self.agent_name,
            "assess_question_relevance",
            user_id=user_id,
            session_id=session_id,
            assessment_step="relevance_analysis"
        ):
            try:
                question = request_data.get("question", "")
                
                assessment_prompt = f"""
                Analyze this health question to determine if it's relevant to nutrition data and what nutrition information would be helpful.

                Question: "{question}"

                Determine:
                1. Is this question relevant to nutrition/diet data? (true/false)
                2. What specific nutrition data would help answer this question?
                3. How far back should we look for nutrition data? (days)
                4. What type of summary would be most helpful? (daily/weekly/raw)
                5. Relevance score (0.0-1.0)

                Examples of nutrition-relevant questions:
                - "What did I eat yesterday?"
                - "How many calories am I consuming daily?"
                - "Am I getting enough protein?"
                - "Show me my meal patterns"
                - "What's my average daily fiber intake?"
                - "How is my diet affecting my health?"

                Respond with JSON:
                {{
                    "is_relevant": true/false,
                    "relevance_score": 0.0-1.0,
                    "reasoning": "Why this question is/isn't relevant to nutrition",
                    "retrieval_strategy": {{
                        "days_back": 7,
                        "summary_type": "daily",
                        "priority_data": ["calories", "macronutrients", "meal_patterns"]
                    }}
                }}
                """

                messages = [
                    SystemMessage(content="You are a nutrition expert assessing question relevance to nutrition data."),
                    HumanMessage(content=assessment_prompt)
                ]

                response = self.llm.invoke(messages)
                
                # Parse assessment
                try:
                    content = response.content.strip()
                    if content.startswith('```json'):
                        content = content[7:-3].strip()
                    elif content.startswith('```'):
                        content = content[3:-3].strip()
                    
                    assessment = json.loads(content)
                    
                    return {
                        "success": True,
                        "is_relevant": assessment.get("is_relevant", False),
                        "relevance_score": assessment.get("relevance_score", 0.0),
                        "reasoning": assessment.get("reasoning", ""),
                        "retrieval_strategy": assessment.get("retrieval_strategy", {})
                    }
                    
                except json.JSONDecodeError:
                    # Fallback assessment
                    nutrition_keywords = ["food", "eat", "meal", "diet", "nutrition", "calories", "protein", "carbs", "fat", "vitamin", "mineral"]
                    is_relevant = any(keyword in question.lower() for keyword in nutrition_keywords)
                    
                    return {
                        "success": True,
                        "is_relevant": is_relevant,
                        "relevance_score": 0.7 if is_relevant else 0.1,
                        "reasoning": "Keyword-based assessment",
                        "retrieval_strategy": {
                            "days_back": 7,
                            "summary_type": "daily",
                            "priority_data": ["calories", "macronutrients"]
                        }
                    }

            except Exception as e:
                print(f"❌ [DEBUG] Nutrition assessment failed: {str(e)}")
                return {
                    "success": False,
                    "is_relevant": False,
                    "relevance_score": 0.0,
                    "reasoning": f"Assessment failed: {str(e)}",
                    "retrieval_strategy": {}
                }

    async def assess_question_relevance(
        self,
        question: str,
        user_id: int,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Public method for question relevance assessment"""
        
        return await self._assess_question_relevance(
            {"question": question},
            user_id,
            session_id
        )

    async def extract_data(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract nutrition data from text message (not image)"""
        
        with trace_agent_operation(
            self.agent_name,
            "extract_nutrition_from_text",
            user_id=state["user_id"],
            session_id=state["session_id"],
            request_id=state.get("request_id")
        ):
            try:
                user_message = state.get("ocr_text", "")  # Use ocr_text field as expected by enhanced customer agent
                if not user_message:
                    return {
                        "error_message": "No user message provided for nutrition extraction",
                        "extracted_data": None
                    }

                # Create prompt for nutrition extraction from text
                nutrition_prompt = self._create_text_nutrition_extraction_prompt(user_message)

                # Analyze text with GPT
                messages = [
                    SystemMessage(content="You are a nutrition expert analyzing food descriptions to extract detailed nutritional information."),
                    HumanMessage(content=nutrition_prompt)
                ]

                response = self.llm.invoke(messages)
                
                if not response or not response.content:
                    return {
                        "error_message": "Empty response from AI model",
                        "extracted_data": None
                    }

                # Parse nutrition data from response
                nutrition_data = self._parse_nutrition_response(response.content)
                
                if not nutrition_data:
                    return {
                        "error_message": "Failed to parse nutrition data",
                        "extracted_data": None
                    }

                # Add metadata
                nutrition_data["data_source"] = NutritionDataSource.MANUAL_ENTRY.value
                nutrition_data["confidence_score"] = nutrition_data.get("confidence_score", 0.8)

                return {
                    "extracted_data": nutrition_data,
                    "error_message": None
                }

            except Exception as e:
                print(f"❌ [DEBUG] Nutrition extraction from text failed: {str(e)}")
                return {
                    "error_message": f"Nutrition extraction failed: {str(e)}",
                    "extracted_data": None
                }

    def _create_text_nutrition_extraction_prompt(self, user_message: str) -> str:
        """Use the same prompt as image extraction, but append the user message for context."""
        base_prompt = self._create_nutrition_extraction_prompt()
        return f"{base_prompt}\n\nUser Message: {user_message}\n"

    

    async def store_data(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Store nutrition data to database"""
        
        try:
            # Get data to store
            data = state.get("extracted_data") or state.get("extraction_request", {})
            
            if not data:
                return {
                    "error_message": "No nutrition data to store",
                    "stored_records": []
                }
            
            # Extract user_id and session_id from the state
            # The state might be the extract_result, so we need to handle this
            user_id = state.get("user_id")
            session_id = state.get("session_id")
            
            # If user_id is not in the state, we can't proceed
            if user_id is None:
                return {
                    "error_message": "Missing user_id for nutrition storage",
                    "stored_records": []
                }
            
            with trace_agent_operation(
                self.agent_name,
                "store_nutrition",
                user_id=user_id,
                session_id=session_id,
                request_id=state.get("request_id")
            ):
                # Use the existing store method
                request_data = {
                    "nutrition_data": data,
                    "meal_type": data.get("meal_type", "snack"),
                    "dish_type": data.get("dish_type", "other"),
                    "data_source": data.get("data_source", NutritionDataSource.MANUAL_ENTRY.value)
                }
                
                result = await self._store_nutrition_data(request_data, user_id, session_id)
                
                if result.get("success"):
                    return {
                        "error_message": None,
                        "stored_records": [result.get("nutrition_data", {})]  # Return as list to match expected format
                    }
                else:
                    return {
                        "error_message": result.get("error", "Storage failed"),
                        "stored_records": []
                    }

        except Exception as e:
            print(f"❌ [DEBUG] Nutrition storage failed: {str(e)}")
            return {
                "error_message": f"Nutrition storage failed: {str(e)}",
                "stored_records": []
            }


# Global instance management
_nutrition_agent = None

def get_nutrition_agent():
    """Get or create the nutrition agent instance"""
    global _nutrition_agent
    if _nutrition_agent is None:
        _nutrition_agent = NutritionAgent()
    return _nutrition_agent

def nutrition_agent():
    """Alias for get_nutrition_agent"""
    return get_nutrition_agent()

# For backward compatibility and integration
async def process_nutrition_request(
    operation: str,
    request_data: Dict[str, Any],
    user_id: int,
    session_id: Optional[int] = None
) -> Dict[str, Any]:
    """Process nutrition request using the agent"""
    
    agent = get_nutrition_agent()
    return await agent.process_request(operation, request_data, user_id, session_id) 