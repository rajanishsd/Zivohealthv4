#!/usr/bin/env python3
"""
Web Search Tool
Simple web search tool for health and fitness information.
"""

import logging
from typing import Dict, Any
from langchain_core.tools import tool

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@tool
async def web_search_tool(query: str) -> Dict[str, Any]:
    """
    Search the web for health and fitness information.
    
    This tool simulates web search results for health-related queries including:
    - Exercise recommendations and workout videos
    - Health research and medical studies
    - Cardiovascular health guidelines
    - Fitness programs and exercise routines
    - Blood pressure management techniques
    - Weight loss and health improvement plans
    
    Args:
        query: Search query for health and fitness information
        
    Returns:
        Dict containing structured search results with exercises, workout plans, and health tips
    """
    try:
        # Simulate structured web search results for health queries
        # In a real implementation, this would use actual web search APIs
        
        # Basic health and exercise information based on common queries
        if any(keyword in query.lower() for keyword in ['blood pressure', 'hypertension', 'cardiovascular']):
            return {
                "query": query,
                "results_count": 5,
                "exercises": [
                    {
                        "name": "Brisk Walking",
                        "type": "cardio",
                        "duration": "30-45 minutes",
                        "frequency": "5 days per week",
                        "instructions": "Walk at a pace where you can talk but feel slightly breathless. Start slow and gradually increase pace.",
                        "benefits": "Improves cardiovascular health, helps lower blood pressure, strengthens heart muscle"
                    },
                    {
                        "name": "Swimming",
                        "type": "cardio",
                        "duration": "20-30 minutes",
                        "frequency": "3-4 days per week",
                        "instructions": "Start with gentle strokes, focus on breathing rhythm. Build up endurance gradually.",
                        "benefits": "Low-impact exercise, excellent for heart health, reduces blood pressure"
                    },
                    {
                        "name": "Cycling",
                        "type": "cardio",
                        "duration": "30-60 minutes",
                        "frequency": "3-5 days per week",
                        "instructions": "Maintain steady pace, use proper bike setup, start with flat terrain.",
                        "benefits": "Strengthens heart and lungs, improves circulation, helps manage blood pressure"
                    }
                ],
                "workout_plans": [
                    {
                        "name": "Beginner Cardio Plan",
                        "duration": "4 weeks",
                        "schedule": {
                            "week_1": "15-20 minutes walking, 3 days",
                            "week_2": "20-25 minutes walking, 4 days",
                            "week_3": "25-30 minutes walking + 5 min light jogging, 4 days",
                            "week_4": "30-35 minutes mixed walking/jogging, 5 days"
                        },
                        "target": "Build cardiovascular endurance and lower blood pressure"
                    }
                ],
                "health_tips": [
                    "Monitor blood pressure before and after exercise",
                    "Stay hydrated during workouts",
                    "Start slowly and progress gradually",
                    "Avoid holding your breath during exercise",
                    "Stop if you feel dizzy or chest pain"
                ],
                "benefits": [
                    "Regular cardio exercise can reduce systolic blood pressure by 5-10 mmHg",
                    "Exercise improves heart efficiency and reduces resting heart rate",
                    "Physical activity helps manage stress, a key factor in blood pressure"
                ]
            }
        
        elif any(keyword in query.lower() for keyword in ['weight loss', 'weight management', 'obesity']):
            return {
                "query": query,
                "results_count": 5,
                "exercises": [
                    {
                        "name": "High-Intensity Interval Training (HIIT)",
                        "type": "cardio/strength",
                        "duration": "20-30 minutes",
                        "frequency": "3 days per week",
                        "instructions": "Alternate between high-intensity bursts (30 seconds) and recovery periods (60 seconds)",
                        "benefits": "Burns calories efficiently, boosts metabolism, builds lean muscle"
                    },
                    {
                        "name": "Strength Training",
                        "type": "resistance",
                        "duration": "45-60 minutes",
                        "frequency": "2-3 days per week",
                        "instructions": "Focus on compound movements like squats, deadlifts, push-ups. Use progressive overload.",
                        "benefits": "Builds muscle mass, increases metabolic rate, improves body composition"
                    },
                    {
                        "name": "Circuit Training",
                        "type": "mixed",
                        "duration": "30-45 minutes",
                        "frequency": "3-4 days per week",
                        "instructions": "Combine cardio and strength exercises with minimal rest between stations",
                        "benefits": "Maximizes calorie burn, improves both strength and cardio fitness"
                    }
                ],
                "workout_plans": [
                    {
                        "name": "Weight Loss Circuit",
                        "duration": "6 weeks",
                        "schedule": {
                            "week_1-2": "3 circuits, 30 seconds work, 60 seconds rest",
                            "week_3-4": "4 circuits, 45 seconds work, 45 seconds rest",
                            "week_5-6": "5 circuits, 60 seconds work, 30 seconds rest"
                        },
                        "target": "Burn calories and build lean muscle for weight loss"
                    }
                ],
                "health_tips": [
                    "Create a caloric deficit through diet and exercise",
                    "Focus on whole foods and proper portion sizes",
                    "Track progress with body measurements, not just weight",
                    "Get adequate sleep for hormone regulation",
                    "Stay consistent with both diet and exercise"
                ]
            }
        
        elif any(keyword in query.lower() for keyword in ['strength', 'muscle', 'resistance']):
            return {
                "query": query,
                "results_count": 5,
                "exercises": [
                    {
                        "name": "Push-ups",
                        "type": "upper body strength",
                        "duration": "3 sets of 8-15 reps",
                        "frequency": "3 days per week",
                        "instructions": "Keep body in straight line, lower chest to floor, push back up with control",
                        "benefits": "Builds chest, shoulders, triceps, and core strength"
                    },
                    {
                        "name": "Squats",
                        "type": "lower body strength",
                        "duration": "3 sets of 10-20 reps",
                        "frequency": "3 days per week",
                        "instructions": "Feet shoulder-width apart, lower as if sitting in chair, keep knees behind toes",
                        "benefits": "Strengthens legs, glutes, and core muscles"
                    },
                    {
                        "name": "Planks",
                        "type": "core strength",
                        "duration": "3 sets of 30-60 seconds",
                        "frequency": "daily",
                        "instructions": "Hold body in straight line from head to heels, engage core muscles",
                        "benefits": "Builds core stability, improves posture, strengthens entire torso"
                    }
                ],
                "workout_plans": [
                    {
                        "name": "Bodyweight Strength Program",
                        "duration": "8 weeks",
                        "schedule": {
                            "monday": "Upper body: Push-ups, planks, pike push-ups",
                            "wednesday": "Lower body: Squats, lunges, calf raises",
                            "friday": "Full body: Burpees, mountain climbers, jumping jacks"
                        },
                        "progression": "Increase reps by 2-3 each week or add more challenging variations"
                    }
                ]
            }
        
        else:
            # General fitness information
            return {
                "query": query,
                "results_count": 3,
                "exercises": [
                    {
                        "name": "Walking",
                        "type": "cardio",
                        "duration": "30 minutes",
                        "frequency": "daily",
                        "instructions": "Maintain steady pace, focus on good posture",
                        "benefits": "Improves cardiovascular health, easy on joints"
                    }
                ],
                "health_tips": [
                    "Start with activities you enjoy",
                    "Set realistic and achievable goals",
                    "Listen to your body and rest when needed",
                    "Consult healthcare provider before starting new exercise program"
                ]
            }
    
    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
        return {
            "query": query,
            "error": f"Search failed: {str(e)}",
            "results_count": 0,
            "exercises": [],
            "health_tips": ["Unable to retrieve search results. Please try a different query."]
        }

# Export the tool
__all__ = ['web_search_tool'] 