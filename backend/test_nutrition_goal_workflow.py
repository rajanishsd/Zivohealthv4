#!/usr/bin/env python3
"""
Test script for the Nutrition Goal Workflow
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    print("Warning: python-dotenv not installed, using system environment variables only")

# Mock database connection before importing
class MockDBConnection:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def cursor(self, **kwargs):
        return MockCursor()

class MockCursor:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, query, params=None):
        pass
    def fetchall(self):
        # Return mock nutrient catalog data
        return [
            {"id": 1, "key": "calories", "display_name": "Calories", "unit": "kcal", "category": "energy"},
            {"id": 2, "key": "protein_g", "display_name": "Protein", "unit": "g", "category": "macronutrient"},
            {"id": 3, "key": "carbs_g", "display_name": "Carbohydrates", "unit": "g", "category": "macronutrient"},
            {"id": 4, "key": "fat_g", "display_name": "Fat", "unit": "g", "category": "macronutrient"},
            {"id": 5, "key": "fiber_g", "display_name": "Fiber", "unit": "g", "category": "macronutrient"},
            {"id": 6, "key": "calcium_mg", "display_name": "Calcium", "unit": "mg", "category": "mineral"},
            {"id": 7, "key": "iron_mg", "display_name": "Iron", "unit": "mg", "category": "mineral"},
            {"id": 8, "key": "vitamin_c_mg", "display_name": "Vitamin C", "unit": "mg", "category": "vitamin"},
        ]
    def fetchone(self):
        return {"id": 999}
    def executemany(self, sql, values):
        pass
    @property
    def rowcount(self):
        return 1

def mock_get_raw_db_connection():
    return MockDBConnection()

# Mock settings
class MockSettings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-test-key")
    CUSTOMER_AGENT_MODEL = "gpt-4o-mini"
    DEFAULT_AI_MODEL = "gpt-4o-mini"
    NUTRITION_AGENT_MODEL = "gpt-4o-mini"
    NUTRITION_VISION_MODEL = "gpt-4o"
    ALGORITHM = "HS256"
    SECRET_KEY = "test-secret-key"
    PROJECT_NAME = "Test Project"
    VERSION = "1.0.0"
    PROJECT_VERSION = "1.0.0"
    API_V1_STR = "/api/v1"
    SERVER_HOST = "localhost"
    SERVER_PORT = 8000
    POSTGRES_SERVER = "localhost"
    POSTGRES_PORT = 5432
    POSTGRES_USER = "test"
    POSTGRES_PASSWORD = "test"
    POSTGRES_DB = "test"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REDIS_HOST = "localhost"
    REDIS_PORT = 6379
    REDIS_DB = 0
    AWS_DEFAULT_REGION = "us-east-1"
    AWS_REGION = "us-east-1"
    AWS_S3_BUCKET = "test-bucket"
    OCR_PROVIDER = "test"
    OCR_TIMEOUT = 30
    OCR_MAX_FILE_SIZE = 10485760
    CORS_ORIGINS = ["*"]
    WS_MESSAGE_QUEUE = "test-queue"

# Mock the specific models that cause mapper initialization errors
class MockNutritionGoal:
    pass

class MockNutritionMealPlan:
    pass

class MockNutritionGoalTarget:
    pass

class MockUserNutrientFocus:
    pass

# Mock responses for different types of questions
MOCK_RESPONSES = {
    "age": "30",
    "gender": "male",
    "height": "175",
    "weight": "80",
    "activity_level": "Moderate - gym 3 times per week",
    "timeframe": "6 months",
    "dietary_preference": "Non-vegetarian",
    "allergies": "None",
    "lab_reports": "No recent lab reports",
    "primary_goal": "Lose 10kg and gain muscle mass",
    "secondary_goals": "Improve energy levels and sleep quality",
    "daily_routine": "Office job, 9-5, gym after work",
    "exercise_type": "Weight training and cardio",
    "exercise_frequency": "3 times per week, 1 hour each",
    "work_type": "Software engineer, mostly sedentary",
    "meal_pattern": "3 meals and 2 snacks per day",
    "typical_foods": "Rice, chicken, vegetables, eggs",
    "food_likes": "Chicken, fish, vegetables, fruits",
    "food_dislikes": "Spicy food, very sweet desserts",
    "budget": "Moderate budget for groceries",
    "cooking": "Cook at home most days, eat out on weekends",
    "substances": "Occasional alcohol, no smoking, moderate caffeine",
    "water_intake": "2-3 liters per day",
    "motivation": "High motivation to make changes",
    "emotional_eating": "Sometimes eat when stressed",
    "dieting_history": "Tried keto before, lost weight but gained it back",
    "support_system": "Family is supportive",
    "dietary_restrictions": "No specific restrictions"
}

# Mock function for ask_user_question
def mock_ask_user_question(question: str, session_id: int, user_id: str) -> str:
    """Mock function that returns predefined responses based on question content."""
    question_lower = question.lower()
    
    # Check for confirmation-related questions first
    if "accept" in question_lower or ("plan" in question_lower and ("review" in question_lower or "summary" in question_lower)):
        # This is the confirmation question - simulate user requesting changes first, then accepting
        if not hasattr(mock_ask_user_question, 'first_confirm'):
            mock_ask_user_question.first_confirm = True
            print(f"🔄 [CONFIRMATION] User is being asked to confirm the nutrition plan")
            print(f"🤖 Agent asked: {question}")
            response = "I want to reduce calories to 1800 and increase protein to 150g per day"
            print(f"👤 User responded: {response}")
            return response
        else:
            response = "Yes, this revised plan looks perfect! I accept it."
            print(f"👤 User responded: {response}")
            return response
    
    # Handle other question types
    if "age" in question_lower:
        response = MOCK_RESPONSES["age"]
    elif "gender" in question_lower:
        response = MOCK_RESPONSES["gender"]
    elif "height" in question_lower:
        response = MOCK_RESPONSES["height"]
    elif "weight" in question_lower:
        response = MOCK_RESPONSES["weight"]
    elif "activity" in question_lower:
        response = MOCK_RESPONSES["activity_level"]
    elif "timeframe" in question_lower:
        response = MOCK_RESPONSES["timeframe"]
    elif "dietary preference" in question_lower:
        response = MOCK_RESPONSES["dietary_preference"]
    elif "allerg" in question_lower:
        response = MOCK_RESPONSES["allergies"]
    elif "lab" in question_lower or "blood test" in question_lower:
        response = MOCK_RESPONSES["lab_reports"]
    elif "primary goal" in question_lower:
        response = MOCK_RESPONSES["primary_goal"]
    elif "secondary" in question_lower:
        response = MOCK_RESPONSES["secondary_goals"]
    elif "start" in question_lower and ("plan" in question_lower or "nutrition" in question_lower):
        response = "I want to start immediately"
    elif "target completion" in question_lower or "completion date" in question_lower:
        response = "6 months from now"
    elif "daily routine" in question_lower:
        response = MOCK_RESPONSES["daily_routine"]
    elif "activity level" in question_lower:
        response = MOCK_RESPONSES["activity_level"]
    elif "exercise" in question_lower and "type" in question_lower:
        response = MOCK_RESPONSES["exercise_type"]
    elif "exercise" in question_lower and ("frequency" in question_lower or "often" in question_lower):
        response = MOCK_RESPONSES["exercise_frequency"]
    elif "work" in question_lower and "type" in question_lower:
        response = MOCK_RESPONSES["work_type"]
    elif "meal" in question_lower and "pattern" in question_lower:
        response = MOCK_RESPONSES["meal_pattern"]
    elif "typical food" in question_lower:
        response = MOCK_RESPONSES["typical_foods"]
    elif "like" in question_lower and "dislike" in question_lower:
        response = f"Likes: {MOCK_RESPONSES['food_likes']}, Dislikes: {MOCK_RESPONSES['food_dislikes']}"
    elif "budget" in question_lower:
        response = MOCK_RESPONSES["budget"]
    elif "cook" in question_lower:
        response = MOCK_RESPONSES["cooking"]
    elif "alcohol" in question_lower or "smoke" in question_lower or "caffeine" in question_lower:
        response = MOCK_RESPONSES["substances"]
    elif "water" in question_lower:
        response = MOCK_RESPONSES["water_intake"]
    elif "motivat" in question_lower:
        response = MOCK_RESPONSES["motivation"]
    elif "emotional eating" in question_lower:
        response = MOCK_RESPONSES["emotional_eating"]
    elif "dieting" in question_lower or "tried" in question_lower:
        response = MOCK_RESPONSES["dieting_history"]
    elif "support" in question_lower:
        response = MOCK_RESPONSES["support_system"]
    elif "restriction" in question_lower:
        response = MOCK_RESPONSES["dietary_restrictions"]
    else:
        response = "I don't have specific information about that"
    
    print(f"🤖 Agent asked: {question}")
    print(f"👤 User responded: {response}")
    return response

# Wrapper to adapt chat_sessions.ask_user_question_and_wait signature
def mock_ask_user_question_and_wait(session_id: int, user_id: str, question: str, timeout_sec: float = 300.0) -> str:
    return mock_ask_user_question(question, session_id, user_id)

# Create a global mock function that can be imported
import app.agentsv2.customer_workflow
app.agentsv2.customer_workflow.ask_user_question = mock_ask_user_question

# Apply mocks before importing - this is critical for the confirmation agent
with patch('app.core.database_utils.get_raw_db_connection', mock_get_raw_db_connection), \
     patch('app.core.config.settings', MockSettings()), \
     patch('app.models.nutrition_goals.NutritionGoal', MockNutritionGoal), \
     patch('app.models.nutrition_goals.NutritionGoalTarget', MockNutritionGoalTarget), \
     patch('app.models.nutrition_data.NutritionMealPlan', MockNutritionMealPlan), \
     patch('app.agentsv2.nutrition_goal_workflow.ask_user_question', side_effect=mock_ask_user_question), \
     patch('app.agentsv2.customer_workflow.ask_user_question', side_effect=mock_ask_user_question), \
     patch('app.api.v1.endpoints.chat_sessions.ask_user_question_and_wait', side_effect=mock_ask_user_question_and_wait):
    from app.agentsv2.nutrition_goal_workflow import run_nutritional_goal_workflow

async def test_nutrition_goal_workflow():
    """Test the complete nutrition goal workflow"""
    
    # Test data
    user_id = 1
    session_id = 1
    test_request_data = {
        "objective": "I want to lose weight and build muscle",
        "use_stub_answers": True,
        "stub_answers": []
    }
    
    print("=" * 60)
    print("NUTRITION GOAL WORKFLOW TEST")
    print("=" * 60)
    print("This test will simulate the complete workflow:")
    print("   1. Data collection and user survey")
    print("   2. Nutrition plan preparation")
    print("   3. Plan confirmation with user")
    print("   4. Plan revision (if requested)")
    print("   5. Final acceptance and goal creation")
    print("=" * 60)
    
    try:
        # Mock the ask_user_question function at the module level where it's imported
        with patch('app.agentsv2.nutrition_goal_workflow.ask_user_question', side_effect=mock_ask_user_question), \
             patch('app.agentsv2.customer_workflow.ask_user_question', side_effect=mock_ask_user_question), \
             patch('app.api.v1.endpoints.chat_sessions.ask_user_question_and_wait', side_effect=mock_ask_user_question_and_wait), \
             patch('app.core.database_utils.get_raw_db_connection', mock_get_raw_db_connection):
            # Run the workflow
            print("Starting nutrition goal workflow...")
            result = await run_nutritional_goal_workflow(
                user_id=user_id,
                session_id=session_id,
                request_data=test_request_data
            )
        
        print("\n" + "=" * 60)
        print("WORKFLOW RESULT")
        print("=" * 60)
        print(f"Success: {result['success']}")
        print(f"Response Message: {json.dumps(result['response_message'], indent=2, default=str)}")
        
        # Extract and display key information
        if result['success'] and 'data' in result['response_message']:
            data = result['response_message']['data']
            
            print("\n" + "-" * 40)
            print("COLLECTED CONTEXT")
            print("-" * 40)
            collected = data.get('collected_context', {})
            print(f"Goal Name: {collected.get('goal_name', 'N/A')}")
            print(f"Goal Description: {collected.get('goal_description', 'N/A')}")
            print(f"Requested Objective: {collected.get('requested_objective', 'N/A')}")
            
            survey_responses = collected.get('survey_responses', {})
            if 'structured' in survey_responses:
                print("\nStructured Survey Data:")
                print(json.dumps(survey_responses['structured'], indent=2, default=str))
            elif 'raw' in survey_responses:
                print("\nRaw Survey Data:")
                print(survey_responses['raw'])
            
            print("\n" + "-" * 40)
            print("PROPOSED GOAL")
            print("-" * 40)
            proposed = data.get('proposed_goal', {})
            if proposed:
                print(json.dumps(proposed, indent=2, default=str))
            
            print("\n" + "-" * 40)
            print("SET GOAL RESULT")
            print("-" * 40)
            set_result = data.get('set_goal_result', {})
            if set_result:
                print(json.dumps(set_result, indent=2, default=str))
            
            # Check if confirmation loop was triggered
            print("\n" + "-" * 40)
            print("CONFIRMATION LOOP ANALYSIS")
            print("-" * 40)
            if hasattr(mock_ask_user_question, 'first_confirm'):
                print("✅ Confirmation loop was triggered")
                print("   - User was asked to confirm the nutrition plan")
                print("   - User requested changes first, then accepted")
            else:
                print("❌ Confirmation loop was NOT triggered")
                print("   This might indicate the agent didn't ask for confirmation")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Reset the first_confirm flag for clean test runs
    if hasattr(mock_ask_user_question, 'first_confirm'):
        delattr(mock_ask_user_question, 'first_confirm')
    
    asyncio.run(test_nutrition_goal_workflow())
