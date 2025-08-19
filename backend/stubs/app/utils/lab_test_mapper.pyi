# Type stub for lab test mapper
from typing import Any, Optional

class LabTestLOINCMapper:
    def __init__(self) -> None: ...
    
    @staticmethod
    def get_loinc_code_for_test(test_name: str, reference_range: Optional[str] = None) -> Optional[str]: ... 