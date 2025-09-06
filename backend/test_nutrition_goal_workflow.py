#!/usr/bin/env python3
"""
Test script for the Nutrition Goal Workflow
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.agentsv2.nutrition_goal_workflow import run_nutritional_goal_workflow

# Mock responses for different types of questions
MOCK_RESPONSES = {
    "age": "30",
    "gender": "male",
    "height": "175",
    "weight": "80",
    "health_status": "Generally healthy, no major issues",
    "medical_history": "None",
    "family_history": "Father has diabetes",
    "medications": "Multivitamin daily",
    "allergies": "None",
    "lab_reports": "Recent blood work shows normal levels",
    "primary_goal": "Lose weight and build muscle",
    "secondary_goals": "Improve energy levels and sleep quality",
    "timeframe": "6 months",
    "daily_routine": "Office job, 9-5, moderate stress",
    "activity_level": "Moderate - gym 3 times per week",
    "exercise_type": "Weight training and cardio",
    "exercise_frequency": "3 times per week, 1 hour each",
    "work_type": "Desk job",
    "meal_pattern": "3 meals and 2 snacks per day",
    "typical_foods": "Rice, vegetables, chicken, eggs",
    "dietary_preference": "Non-vegetarian",
    "food_likes": "Spicy food, Indian cuisine",
    "food_dislikes": "Very sweet desserts",
    "budget": "Moderate budget for healthy food",
    "cooking": "Cook at home mostly, eat out 2-3 times per week",
    "substances": "Occasional alcohol, no smoking, 2-3 cups coffee daily",
    "water_intake": "2-3 liters per day",
    "motivation": "High motivation to change",
    "emotional_eating": "Sometimes stress eat",
    "dieting_history": "Tried keto before, lost weight but gained it back",
    "support_system": "Family is supportive",
    "dietary_restrictions": "None",
    "travel": "Occasional business travel",
    "food_availability": "Good access to fresh produce",
    "health_concerns": "Want to improve overall fitness"
}

async def mock_ask_user_question(question: str, session_id: int, user_id: str) -> str:
    """Mock function to simulate user responses to questions"""
    print(f"🤖 Agent asked: {question}")
    
    # Try to match question to a response
    question_lower = question.lower()
    
    if "age" in question_lower:
        response = MOCK_RESPONSES["age"]
    elif "gender" in question_lower:
        response = MOCK_RESPONSES["gender"]
    elif "height" in question_lower:
        response = MOCK_RESPONSES["height"]
    elif "weight" in question_lower:
        response = MOCK_RESPONSES["weight"]
    elif "waist" in question_lower and "circumference" in question_lower:
        response = "85"
    elif "hip" in question_lower and "circumference" in question_lower:
        response = "95"
    elif "neck" in question_lower and "circumference" in question_lower:
        response = "38"
    elif "health status" in question_lower or "current health" in question_lower:
        response = MOCK_RESPONSES["health_status"]
    elif "medical history" in question_lower or "past medical" in question_lower:
        response = MOCK_RESPONSES["medical_history"]
    elif "family history" in question_lower:
        response = MOCK_RESPONSES["family_history"]
    elif "medication" in question_lower:
        response = MOCK_RESPONSES["medications"]
    elif "allerg" in question_lower:
        response = MOCK_RESPONSES["allergies"]
    elif "lab" in question_lower or "blood test" in question_lower:
        response = MOCK_RESPONSES["lab_reports"]
    elif "primary goal" in question_lower:
        response = MOCK_RESPONSES["primary_goal"]
    elif "secondary" in question_lower:
        response = MOCK_RESPONSES["secondary_goals"]
    elif "timeframe" in question_lower:
        response = MOCK_RESPONSES["timeframe"]
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
    elif "dietary preference" in question_lower:
        response = MOCK_RESPONSES["dietary_preference"]
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
    elif "travel" in question_lower:
        response = MOCK_RESPONSES["travel"]
    elif "availability" in question_lower:
        response = MOCK_RESPONSES["food_availability"]
    elif "concern" in question_lower:
        response = MOCK_RESPONSES["health_concerns"]
    else:
        response = "I don't have specific information about that, but I'm generally healthy and motivated to improve my nutrition."
    
    print(f"👤 User responded: {response}")
    return response

async def test_nutrition_goal_workflow():
    """Test the nutrition goal workflow with sample data"""
    
    # Sample test data
    test_request_data = {
        "original_prompt": "I want to lose weight and build muscle",
        "goal_name": "Weight Loss and Muscle Building",
        "goal_description": "Lose 10kg and gain muscle mass",
        "notes": "I'm a 30-year-old male who wants to get in shape"
    }
    
    # Test user ID and session ID
    user_id = 1
    session_id = 1
    
    print("=" * 60)
    print("TESTING NUTRITION GOAL WORKFLOW")
    print("=" * 60)
    print(f"User ID: {user_id}")
    print(f"Session ID: {session_id}")
    print(f"Request Data: {json.dumps(test_request_data, indent=2)}")
    print("=" * 60)
    
    try:
        # Mock the ask_user_question function at the module level where it's imported
        with patch('app.agentsv2.nutrition_goal_workflow.ask_user_question', side_effect=mock_ask_user_question):
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
        
        print("\n" + "=" * 60)
        print("TEST COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_nutrition_goal_workflow())
