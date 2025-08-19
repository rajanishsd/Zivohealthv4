from typing import List, Dict, Any
from langchain.tools import Tool
import json
from datetime import datetime


class DatabaseToolkit:
    def __init__(self):
        pass
    
    def get_tools(self) -> List[Tool]:
        return [
            self.get_vital_signs_storage_tool(),
            self.get_prescription_storage_tool(),
            self.get_lab_results_storage_tool()
        ]
    
    def get_vital_signs_storage_tool(self) -> Tool:
        def store_vital_signs(data: str) -> str:
            try:
                # Parse and validate vital signs data
                vital_data = self._parse_vital_signs(data)
                # In real implementation, store to HealthKit tables
                return f"Stored vital signs: {json.dumps(vital_data, indent=2)}"
            except Exception as e:
                return f"Storage error: {str(e)}"
        
        return Tool(
            name="Store_Vital_Signs",
            func=store_vital_signs,
            description="Parse and store vital signs data in the health database"
        )
    
    def get_prescription_storage_tool(self) -> Tool:
        def store_prescription(data: str) -> str:
            try:
                prescription_data = self._parse_prescription(data)
                return f"Stored prescription: {json.dumps(prescription_data, indent=2)}"
            except Exception as e:
                return f"Storage error: {str(e)}"
        
        return Tool(
            name="Store_Prescription",
            func=store_prescription,
            description="Parse and store prescription data in the medical database"
        )
    
    def get_lab_results_storage_tool(self) -> Tool:
        def store_lab_results(data: str) -> str:
            try:
                lab_data = self._parse_lab_results(data)
                return f"Stored lab results: {json.dumps(lab_data, indent=2)}"
            except Exception as e:
                return f"Storage error: {str(e)}"
        
        return Tool(
            name="Store_Lab_Results",
            func=store_lab_results,
            description="Parse and store lab results in the medical database"
        )
    
    def _parse_vital_signs(self, text: str) -> Dict[str, Any]:
        return {
            "blood_pressure_systolic": 120,
            "blood_pressure_diastolic": 80,
            "heart_rate": 72,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
    
    def _parse_prescription(self, text: str) -> Dict[str, Any]:
        return {
            "medications": [{"name": "Sample Med", "dosage": "10mg"}],
            "date": datetime.now().strftime("%Y-%m-%d")
        }
    
    def _parse_lab_results(self, text: str) -> Dict[str, Any]:
        return {
            "tests": [{"name": "Cholesterol", "value": 180, "unit": "mg/dL"}],
            "date": datetime.now().strftime("%Y-%m-%d")
        }


def create_database_tools() -> List[Tool]:
    toolkit = DatabaseToolkit()
    return toolkit.get_tools() 