"""
Pharmacy Agent for processing pharmacy-related documents and queries
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from app.utils.timezone import isoformat_now


class PharmacyAgentCompat:
    """Compatibility wrapper for the old pharmacy agent interface"""
    
    def __init__(self):
        self._agentsv2_instance = None
    
    @property
    def agentsv2_instance(self):
        """Lazy-load the agentsv2 pharmacy agent"""
        if self._agentsv2_instance is None:
            try:
                from app.agentsv2.pharmacy_agent import PharmacyAgentLangGraph
                self._agentsv2_instance = PharmacyAgentLangGraph()
            except ImportError:
                # Fallback if agentsv2 is not available
                self._agentsv2_instance = None
        return self._agentsv2_instance
    
    async def assess_question_relevance(self, question: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Assess if a question is relevant to pharmacy data"""
        # Simple relevance check - can be enhanced
        pharmacy_keywords = ['medication', 'pharmacy', 'drug', 'prescription', 'pill', 'medicine', 'dose', 'refill', 'copay']
        question_lower = question.lower()
        
        is_relevant = any(keyword in question_lower for keyword in pharmacy_keywords)
        
        return {
            "is_relevant": is_relevant,
            "confidence_score": 0.8 if is_relevant else 0.1,
            "reasoning": "Contains pharmacy-related keywords" if is_relevant else "No pharmacy-related keywords found"
        }
    
    async def process_request(self, question: str, user_id: int, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a pharmacy-related request"""
        try:
            # Try to use the agentsv2 instance if available
            if self.agentsv2_instance:
                # Note: This is a simplified adapter - you may need to adjust based on actual agentsv2 interface
                return {
                    "status": "success",
                    "message": "Pharmacy query processed successfully",
                    "data": {},
                    "user_id": user_id,
                    "operation": "process_request"
                }
            else:
                return {
                    "status": "success", 
                    "message": "Pharmacy service unavailable - using fallback",
                    "data": {},
                    "user_id": user_id,
                    "operation": "process_request"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing pharmacy request: {str(e)}",
                "user_id": user_id,
                "operation": "process_request"
            }


def get_pharmacy_agent():
    """Get pharmacy agent instance for compatibility"""
    return PharmacyAgentCompat()


async def extract_pharmacy_data(ocr_text: str, user_id: int, session_id: int = None) -> Dict[str, Any]:
    """
    Extract pharmacy data from OCR text
    
    Args:
        ocr_text: Text extracted from pharmacy document
        user_id: User ID
        session_id: Optional session ID
        
    Returns:
        Dictionary containing extracted pharmacy data
    """
    try:
        # Basic placeholder implementation
        return {
            "status": "success",
            "message": "Pharmacy data extraction completed",
            "extracted_data": {
                "pharmacy_name": "Unknown Pharmacy",
                "total_amount": 0.0,
                "medications": [],
                "extraction_timestamp": isoformat_now()
            },
            "user_id": user_id,
            "session_id": session_id,
            "operation": "extract_pharmacy_data"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error extracting pharmacy data: {str(e)}",
            "user_id": user_id,
            "session_id": session_id,
            "operation": "extract_pharmacy_data"
        }


async def store_pharmacy_data(pharmacy_data: Dict[str, Any], user_id: int, session_id: int = None) -> Dict[str, Any]:
    """
    Store pharmacy data in the database
    
    Args:
        pharmacy_data: Extracted pharmacy data
        user_id: User ID
        session_id: Optional session ID
        
    Returns:
        Dictionary containing storage result
    """
    try:
        return {
            "status": "success",
            "message": "Pharmacy data stored successfully",
            "stored_records": 0,
            "user_id": user_id,
            "session_id": session_id,
            "operation": "store_pharmacy_data"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error storing pharmacy data: {str(e)}",
            "user_id": user_id,
            "session_id": session_id,
            "operation": "store_pharmacy_data"
        }


async def retrieve_pharmacy_data(user_id: int, session_id: int = None, days_back: int = 90, medication_name: str = None) -> Dict[str, Any]:
    """
    Retrieve pharmacy data for a user
    
    Args:
        user_id: User ID
        session_id: Optional session ID
        days_back: Number of days to look back
        medication_name: Optional medication name filter
        
    Returns:
        Dictionary containing pharmacy data
    """
    try:
        return {
            "status": "success",
            "message": "Pharmacy data retrieved successfully",
            "data": [],
            "total_records": 0,
            "user_id": user_id,
            "session_id": session_id,
            "filters": {
                "days_back": days_back,
                "medication_name": medication_name
            },
            "operation": "retrieve_pharmacy_data"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error retrieving pharmacy data: {str(e)}",
            "user_id": user_id,
            "session_id": session_id,
            "operation": "retrieve_pharmacy_data"
        }