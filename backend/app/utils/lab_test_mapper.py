"""
Utility functions for lab test mapping operations
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.lab_test_mapping import LabTestMapping
import difflib
import re
from sqlalchemy import func

class LabTestMapper:
    """Utility class for mapping lab test names to categories and standardized names"""
    
    def __init__(self, db: Session):
        self.db = db
        self._mappings_cache = {}
        self._cache_loaded = False
    
    def _load_mappings(self) -> Dict[str, LabTestMapping]:
        """Load mappings from database into cache"""
        if self._cache_loaded:
            return self._mappings_cache
        
        mappings = self.db.query(LabTestMapping).filter(
            LabTestMapping.is_active == True
        ).all()
        
        # Create a dictionary for fast lookup using lowercase test names
        self._mappings_cache = {
            mapping.test_name.lower().strip(): mapping 
            for mapping in mappings
        }
        
        self._cache_loaded = True
        return self._mappings_cache
    
    def _generate_name_variations(self, test_name: str) -> List[str]:
        """Generate common variations of a test name"""
        variations = [test_name]
        
        # Remove parentheses content for shorter versions
        if '(' in test_name:
            short_name = re.sub(r'\s*\([^)]*\)', '', test_name).strip()
            if short_name:
                variations.append(short_name)
        
        # Extract abbreviations from parentheses
        abbreviations = re.findall(r'\(([^)]*)\)', test_name)
        for abbr in abbreviations:
            variations.append(abbr.strip())
        
        # Common variations
        variations_map = {
            'Total Cholesterol': ['Cholesterol', 'TC', 'CHOL'],
            'Fasting Blood Sugar (FBS)': ['FBS', 'Glucose', 'Blood Sugar', 'Fasting Glucose'],
            'HbA1c': ['A1C', 'Hemoglobin A1C', 'Glycated Hemoglobin'],
            'Creatinine': ['CREA', 'Cr'],
            'Blood Urea Nitrogen': ['BUN'],
            'Alanine Aminotransferase': ['ALT', 'SGPT'],
            'Aspartate Aminotransferase': ['AST', 'SGOT'],
            'Alkaline Phosphatase': ['ALP', 'ALKP'],
            'Gamma-glutamyl Transferase': ['GGT', 'GGTP'],
            'Thyroid Stimulating Hormone': ['TSH'],
            'Triiodothyronine': ['T3'],
            'Thyroxine': ['T4'],
            'Free T4': ['FT4', 'Free Thyroxine'],
            'Free T3': ['FT3', 'Free Triiodothyronine'],
        }
        
        for standard_name, alt_names in variations_map.items():
            if standard_name.lower() in test_name.lower():
                variations.extend(alt_names)
        
        return list(set(variations))  # Remove duplicates
    
    def get_test_category(self, test_name: str) -> Optional[str]:
        """Get the category for a given test name"""
        mappings = self._load_mappings()
        
        # Direct lookup
        test_name_lower = test_name.lower().strip()
        if test_name_lower in mappings:
            return mappings[test_name_lower].test_category
        
        # Fuzzy matching for partial matches
        best_match = self._find_best_match(test_name, list(mappings.keys()))
        if best_match:
            return mappings[best_match].test_category
        
        return None
    
    def get_standardized_test_name(self, test_name: str) -> Optional[str]:
        """Get the standardized test name for a given test name"""
        mappings = self._load_mappings()
        
        # Direct lookup
        test_name_lower = test_name.lower().strip()
        if test_name_lower in mappings:
            mapping = mappings[test_name_lower]
            # Return standardized name if available, otherwise original test_name
            return mapping.test_name_standardized or mapping.test_name
        
        # Fuzzy matching
        best_match = self._find_best_match(test_name, list(mappings.keys()))
        if best_match:
            mapping = mappings[best_match]
            return mapping.test_name_standardized or mapping.test_name
        
        return None
    
    def get_test_mapping(self, test_name: str) -> Optional[LabTestMapping]:
        """Get the full mapping object for a given test name"""
        mappings = self._load_mappings()
        
        # Direct lookup
        test_name_lower = test_name.lower().strip()
        if test_name_lower in mappings:
            return mappings[test_name_lower]
        
        # Fuzzy matching
        best_match = self._find_best_match(test_name, list(mappings.keys()))
        if best_match:
            return mappings[best_match]
        
        return None
    
    def get_test_mapping_details(self, test_name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive mapping details including standardized name"""
        mapping = self.get_test_mapping(test_name)
        if not mapping:
            return None
        
        return {
            'test_name': mapping.test_name,
            'test_name_standardized': mapping.test_name_standardized,
            'test_code': mapping.test_code,
            'test_category': mapping.test_category,
            'gpt_suggested_category': mapping.gpt_suggested_category,
            'description': mapping.description,
            'common_units': mapping.common_units,
            'normal_range_info': mapping.normal_range_info,
            'is_active': mapping.is_active,
            'is_standardized': mapping.is_standardized
        }
    
    def _find_best_match(self, test_name: str, available_names: List[str], threshold: float = 0.6) -> Optional[str]:
        """Find the best matching test name using fuzzy matching"""
        test_name_lower = test_name.lower().strip()
        
        # First try exact substring matching
        for name in available_names:
            if test_name_lower in name or name in test_name_lower:
                return name
        
        # Then try fuzzy matching
        matches = difflib.get_close_matches(
            test_name_lower, 
            available_names, 
            n=1, 
            cutoff=threshold
        )
        
        return matches[0] if matches else None
    
    def get_tests_by_category(self, category: str) -> List[LabTestMapping]:
        """Get all tests for a specific category"""
        return self.db.query(LabTestMapping).filter(
            LabTestMapping.test_category == category,
            LabTestMapping.is_active == True
        ).all()
    
    def get_all_categories(self) -> List[str]:
        """Get all available test categories"""
        categories = self.db.query(LabTestMapping.test_category).filter(
            LabTestMapping.is_active == True
        ).distinct().all()
        
        return [cat[0] for cat in categories]
    
    def search_tests(self, query: str, limit: int = 10) -> List[LabTestMapping]:
        """Search for tests by name, standardized name, or category"""
        query_lower = f"%{query.lower()}%"
        
        return self.db.query(LabTestMapping).filter(
            (LabTestMapping.test_name.ilike(query_lower)) | 
            (LabTestMapping.test_name_standardized.ilike(query_lower)) |
            (LabTestMapping.test_category.ilike(query_lower)) |
            (LabTestMapping.description.ilike(query_lower)),
            LabTestMapping.is_active == True
        ).limit(limit).all()
    
    def normalize_test_name(self, test_name: str) -> str:
        """Normalize a test name to match our standard format"""
        standardized = self.get_standardized_test_name(test_name)
        if standardized:
            return standardized
        return test_name  # Return original if no mapping found
    
    def get_test_info(self, test_name: str) -> Dict[str, Any]:
        """Get comprehensive information about a test"""
        mapping = self.get_test_mapping(test_name)
        
        if not mapping:
            return {
                'found': False,
                'original_name': test_name,
                'message': 'Test not found in mapping database'
            }
        
        return {
            'found': True,
            'original_name': test_name,
            'mapped_name': mapping.test_name,
            'standardized_name': mapping.test_name_standardized or mapping.test_name,
            'test_code': mapping.test_code,
            'category': mapping.test_category,
            'gpt_suggested_category': mapping.gpt_suggested_category,
            'description': mapping.description,
            'common_units': mapping.common_units,
            'normal_range': mapping.normal_range_info,
            'is_standardized': mapping.is_standardized
        }
    
    def update_standardized_name(self, test_name: str, standardized_name: str) -> bool:
        """Update the standardized name for a test mapping"""
        try:
            mapping = self.get_test_mapping(test_name)
            if not mapping:
                return False
            
            mapping.test_name_standardized = standardized_name
            mapping.updated_at = func.now()
            self.db.commit()
            
            # Clear cache to force reload
            self._cache_loaded = False
            self._mappings_cache = {}
            
            return True
        except Exception:
            self.db.rollback()
            return False
    
    def get_standardization_status(self) -> Dict[str, Any]:
        """Get statistics about test name standardization"""
        total_query = self.db.query(LabTestMapping).filter(LabTestMapping.is_active == True)
        total_count = total_query.count()
        
        standardized_count = total_query.filter(
            LabTestMapping.test_name_standardized.isnot(None)
        ).count()
        
        manually_standardized_count = total_query.filter(
            LabTestMapping.test_name_standardized.isnot(None),
            LabTestMapping.test_name_standardized != LabTestMapping.test_name
        ).count()
        
        return {
            'total_tests': total_count,
            'tests_with_standardized_names': standardized_count,
            'manually_standardized_tests': manually_standardized_count,
            'standardization_percentage': (standardized_count / total_count * 100) if total_count > 0 else 0,
            'manual_standardization_percentage': (manually_standardized_count / total_count * 100) if total_count > 0 else 0
        }


# Convenience functions for direct use
def get_test_category(db: Session, test_name: str) -> Optional[str]:
    """Get the category for a test name"""
    mapper = LabTestMapper(db)
    return mapper.get_test_category(test_name)

def normalize_test_name(db: Session, test_name: str) -> str:
    """Normalize a test name to standard format"""
    mapper = LabTestMapper(db)
    return mapper.normalize_test_name(test_name)

def get_test_info(db: Session, test_name: str) -> Dict[str, Any]:
    """Get comprehensive test information"""
    mapper = LabTestMapper(db)
    return mapper.get_test_info(test_name) 