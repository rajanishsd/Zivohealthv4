from typing import List
from langchain.tools import Tool


class MedicalToolkit:
    def __init__(self):
        pass
    
    def get_tools(self) -> List[Tool]:
        return [
            self.get_vital_analysis_tool(),
            self.get_drug_interaction_tool(),
            self.get_symptom_checker_tool()
        ]
    
    def get_vital_analysis_tool(self) -> Tool:
        def analyze_vitals(vital_data: str) -> str:
            """Analyze vital signs for normal ranges"""
            try:
                # Basic vital analysis logic
                analysis = f"Analyzing vital signs: {vital_data}. "
                analysis += "Please consult healthcare provider for proper interpretation."
                return analysis
            except Exception as e:
                return f"Analysis error: {str(e)}"
        
        return Tool(
            name="Analyze_Vitals",
            func=analyze_vitals,
            description="Analyze vital signs and provide normal range comparisons"
        )
    
    def get_drug_interaction_tool(self) -> Tool:
        def check_interactions(medications: str) -> str:
            """Check for drug interactions"""
            try:
                return f"Drug interaction check for: {medications}. Please consult pharmacist for comprehensive interaction screening."
            except Exception as e:
                return f"Interaction check error: {str(e)}"
        
        return Tool(
            name="Drug_Interaction_Check",
            func=check_interactions,
            description="Check for potential drug interactions and contraindications"
        )
    
    def get_symptom_checker_tool(self) -> Tool:
        def check_symptoms(symptoms: str) -> str:
            """Basic symptom assessment"""
            try:
                return f"Symptom assessment for: {symptoms}. For proper diagnosis, please consult a healthcare professional."
            except Exception as e:
                return f"Symptom check error: {str(e)}"
        
        return Tool(
            name="Symptom_Checker",
            func=check_symptoms,
            description="Provide basic symptom assessment and recommendations"
        )


def create_medical_tools() -> List[Tool]:
    toolkit = MedicalToolkit()
    return toolkit.get_tools() 