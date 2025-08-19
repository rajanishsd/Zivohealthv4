"""
Health Data Processing Agents

This module contains specialized agents for processing different types of health documents
and data using LangGraph workflows. Each agent has its own mini-workflow for extraction,
storage, and retrieval operations.

Architecture:
- BaseHealthAgent: Common functionality for all agents
- VitalsAgent: Processes vital signs and health measurements
- PharmacyAgent: Processes pharmacy bills and medication purchases  
- LabAgent: Processes laboratory reports and test results
- PrescriptionAgent: Processes medical prescriptions
- DocumentProcessingOrchestrator: Coordinates document processing workflow
- EnhancedCustomerAgent: Main customer-facing agent with comprehensive capabilities

Message Flow:
Customer Agent → Document Orchestrator → Specialized Agents → Database Storage
Customer Agent → Specialized Agents (for data retrieval) → LLM Response Generation

Each agent maintains its own memory and can operate independently while supporting
inter-agent communication through LangGraph state management.
"""

# Load environment variables before importing agents
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file to ensure OpenAI API key is available
# Look for .env file in the backend directory
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from .base_agent import BaseHealthAgent, AgentState

# Import classes but not instances to avoid startup hanging
from .vitals_agent import VitalsAgent
from .lab_agent import LabAgent
from .prescription_agent import PrescriptionAgent
from .document_processing_workflow import DocumentProcessingOrchestrator, DocumentProcessingState
from .enhanced_customer_agent import EnhancedCustomerAgent, CustomerAgentState

# Lazy-loaded agent instances
_agent_instances = {}

def get_vitals_agent():
    """Get or create vitals agent instance"""
    if 'vitals' not in _agent_instances:
        from .vitals_agent import vitals_agent
        _agent_instances['vitals'] = vitals_agent()
    return _agent_instances['vitals']

def get_lab_agent():
    """Get or create lab agent instance"""
    if 'lab' not in _agent_instances:
        from .lab_agent import lab_agent
        _agent_instances['lab'] = lab_agent()
    return _agent_instances['lab']

def get_prescription_agent():
    """Get or create prescription agent instance"""
    if 'prescription' not in _agent_instances:
        from .prescription_agent import prescription_agent
        _agent_instances['prescription'] = prescription_agent()
    return _agent_instances['prescription']

def get_document_orchestrator():
    """Get or create document orchestrator instance"""
    if 'document_orchestrator' not in _agent_instances:
        from .document_processing_workflow import document_orchestrator
        _agent_instances['document_orchestrator'] = document_orchestrator
    return _agent_instances['document_orchestrator']

def get_enhanced_customer_agent():
    """Get or create enhanced customer agent instance"""
    if 'customer_agent' not in _agent_instances:
        from .enhanced_customer_agent import enhanced_customer_agent
        _agent_instances['customer_agent'] = enhanced_customer_agent
    return _agent_instances['customer_agent']

# Lazy-loaded function imports
def get_extract_vitals_data():
    """Get extract vitals data function"""
    from .vitals_agent import extract_vitals_data
    return extract_vitals_data

def get_store_vitals_data():
    """Get store vitals data function"""
    from .vitals_agent import store_vitals_data
    return store_vitals_data

def get_retrieve_vitals_data():
    """Get retrieve vitals data function"""
    from .vitals_agent import retrieve_vitals_data
    return retrieve_vitals_data

def get_extract_lab_data():
    """Get extract lab data function"""
    from .lab_agent import extract_lab_data
    return extract_lab_data

def get_store_lab_data():
    """Get store lab data function"""
    from .lab_agent import store_lab_data
    return store_lab_data

def get_retrieve_lab_data():
    """Get retrieve lab data function"""
    from .lab_agent import retrieve_lab_data
    return retrieve_lab_data

def get_extract_prescription_data():
    """Get extract prescription data function"""
    from .prescription_agent import extract_prescription_data
    return extract_prescription_data

def get_store_prescription_data():
    """Get store prescription data function"""
    from .prescription_agent import store_prescription_data
    return store_prescription_data

def get_retrieve_prescription_data():
    """Get retrieve prescription data function"""
    from .prescription_agent import retrieve_prescription_data
    return retrieve_prescription_data

def get_process_health_document():
    """Get process health document function"""
    from .document_processing_workflow import process_health_document
    return process_health_document

def get_process_customer_request():
    """Get process customer request function"""
    from .enhanced_customer_agent import process_customer_request
    return process_customer_request

# Agent registry for easy access - populated lazily
def get_agents():
    """Get agent registry with lazy loading"""
    return {
        "vitals": get_vitals_agent(),
        "lab": get_lab_agent(),
        "prescription": get_prescription_agent(),
        "document_orchestrator": get_document_orchestrator(),
        "customer_agent": get_enhanced_customer_agent()
    }

# Convenience functions for common operations
async def extract_health_data(document_type: str, ocr_text: str, user_id: int, session_id: int = None):
    """Extract health data using appropriate specialized agent"""
    
    agent_map = {
        "vitals": get_extract_vitals_data(),
        "lab": get_extract_lab_data(),
        "prescription": get_extract_prescription_data()
    }
    
    extract_func = agent_map.get(document_type)
    if extract_func:
        return await extract_func(ocr_text, user_id, session_id)
    else:
        raise ValueError(f"Unsupported document type: {document_type}")

async def store_health_data(document_type: str, data: dict, user_id: int, session_id: int = None):
    """Store health data using appropriate specialized agent"""
    
    agent_map = {
        "vitals": get_store_vitals_data(),
        "lab": get_store_lab_data(),
        "prescription": get_store_prescription_data()
    }
    
    store_func = agent_map.get(document_type)
    if store_func:
        return await store_func(data, user_id, session_id)
    else:
        raise ValueError(f"Unsupported document type: {document_type}")

async def retrieve_health_data(document_type: str, user_id: int, session_id: int = None, **kwargs):
    """Retrieve health data using appropriate specialized agent"""
    
    agent_map = {
        "vitals": get_retrieve_vitals_data(),
        "lab": get_retrieve_lab_data(),
        "prescription": get_retrieve_prescription_data()
    }
    
    retrieve_func = agent_map.get(document_type)
    if retrieve_func:
        return await retrieve_func(user_id, session_id, **kwargs)
    else:
        raise ValueError(f"Unsupported document type: {document_type}")



__all__ = [
    # Base classes
    "BaseHealthAgent",
    "AgentState",
    
    # Agent classes
    "VitalsAgent",
    "LabAgent",
    "PrescriptionAgent",
    "EnhancedCustomerAgent",
    "DocumentProcessingOrchestrator",
    
    # State classes
    "CustomerAgentState",
    "DocumentProcessingState",
    
    # Lazy-loaded agent getters
    "get_vitals_agent",
    "get_lab_agent", 
    "get_prescription_agent",
    "get_enhanced_customer_agent",
    "get_document_orchestrator",
    
    # Function getters
    "get_extract_vitals_data",
    "get_store_vitals_data",
    "get_retrieve_vitals_data",
    "get_extract_lab_data",
    "get_store_lab_data",
    "get_retrieve_lab_data",
    "get_extract_prescription_data",
    "get_store_prescription_data",
    "get_retrieve_prescription_data",
    "get_process_health_document",
    "get_process_customer_request",
    
    # Convenience functions
    "extract_health_data",
    "store_health_data", 
    "retrieve_health_data",
    
    # Agent registry
    "get_agents"
] 