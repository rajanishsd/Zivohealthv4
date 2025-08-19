"""
Unit Converter for Vitals Data
Standardizes units across different data sources to ensure consistent storage
"""
from typing import Dict, Tuple, Optional
from enum import Enum
from app.models.vitals_data import VitalMetricType

class UnitConversionError(Exception):
    """Exception raised when unit conversion fails"""
    pass

class VitalUnitConverter:
    """Handles unit conversion and standardization for vital signs data"""
    
    # Define standard units for each metric type
    STANDARD_UNITS: Dict[VitalMetricType, str] = {
        VitalMetricType.HEIGHT: "cm",
        VitalMetricType.BODY_MASS: "kg", 
        VitalMetricType.BODY_TEMPERATURE: "°C",
        VitalMetricType.HEART_RATE: "bpm",
        VitalMetricType.BLOOD_PRESSURE_SYSTOLIC: "mmHg",
        VitalMetricType.BLOOD_PRESSURE_DIASTOLIC: "mmHg",
        VitalMetricType.BLOOD_SUGAR: "mg/dL",
        VitalMetricType.BMI: "kg/m²",
        VitalMetricType.OXYGEN_SATURATION: "%",
        VitalMetricType.STEP_COUNT: "steps",
        VitalMetricType.STAND_TIME: "hours",
        VitalMetricType.ACTIVE_ENERGY: "kcal",
        VitalMetricType.FLIGHTS_CLIMBED: "flights",
        VitalMetricType.WORKOUTS: "minutes",
        VitalMetricType.WORKOUT_DURATION: "minutes",
        VitalMetricType.WORKOUT_CALORIES: "kcal",
        VitalMetricType.WORKOUT_DISTANCE: "meters",
        VitalMetricType.SLEEP: "hours",
        VitalMetricType.DISTANCE_WALKING: "km"
    }
    
    # Unit conversion mappings - each metric type maps to a dict of {input_unit: conversion_factor}
    # Conversion factor converts to standard unit
    UNIT_CONVERSIONS: Dict[VitalMetricType, Dict[str, float]] = {
        VitalMetricType.HEIGHT: {
            "cm": 1.0,  # standard
            "centimeters": 1.0,
            "in": 2.54,
            "inches": 2.54,
            "inch": 2.54,
            "ft": 30.48,
            "feet": 30.48,
            "foot": 30.48,
            "m": 100.0,
            "meters": 100.0,
            "meter": 100.0
        },
        VitalMetricType.BODY_MASS: {
            "kg": 1.0,  # standard
            "kilograms": 1.0,
            "kilogram": 1.0,
            "lb": 0.453592,
            "lbs": 0.453592,
            "pounds": 0.453592,
            "pound": 0.453592,
            "g": 0.001,
            "grams": 0.001,
            "gram": 0.001,
            "oz": 0.0283495,
            "ounces": 0.0283495,
            "ounce": 0.0283495
        },
        VitalMetricType.BODY_TEMPERATURE: {
            "°C": 1.0,  # standard
            "celsius": 1.0,
            "c": 1.0,
            "°F": "fahrenheit_conversion",  # Special conversion
            "fahrenheit": "fahrenheit_conversion",
            "f": "fahrenheit_conversion",
            "degF": "fahrenheit_conversion"
        },
        VitalMetricType.BLOOD_SUGAR: {
            "mg/dL": 1.0,  # standard
            "mg/dl": 1.0,
            "milligrams per deciliter": 1.0,
            "mmol/L": 18.0182,  # multiply by this to get mg/dL
            "mmol/l": 18.0182,
            "millimoles per liter": 18.0182
        },
        VitalMetricType.HEART_RATE: {
            "bpm": 1.0,  # standard
            "beats/min": 1.0,
            "beats per minute": 1.0,
            "count/min": 1.0,
            "/min": 1.0
        },
        VitalMetricType.BLOOD_PRESSURE_SYSTOLIC: {
            "mmHg": 1.0,  # standard
            "mm Hg": 1.0,
            "millimeters of mercury": 1.0,
            "torr": 1.0,  # same as mmHg
            "kPa": 7.50062  # multiply by this to convert kPa to mmHg
        },
        VitalMetricType.BLOOD_PRESSURE_DIASTOLIC: {
            "mmHg": 1.0,  # standard
            "mm Hg": 1.0,
            "millimeters of mercury": 1.0,
            "torr": 1.0,  # same as mmHg
            "kPa": 7.50062  # multiply by this to convert kPa to mmHg
        },
        VitalMetricType.BMI: {
            "kg/m²": 1.0,  # standard
            "kg/m2": 1.0,
            "kilograms per square meter": 1.0
        },
        VitalMetricType.OXYGEN_SATURATION: {
            "%": 1.0,  # standard
            "percent": 1.0,
            "percentage": 1.0,
            "fraction": 100.0  # multiply by 100 to convert fraction to percentage
        },
        VitalMetricType.STEP_COUNT: {
            "steps": 1.0,  # standard
            "step": 1.0,
            "count": 1.0,
            "counts": 1.0
        },
        VitalMetricType.ACTIVE_ENERGY: {
            "kcal": 1.0,  # standard
            "kilocalories": 1.0,
            "kilocalorie": 1.0,
            "cal": 0.001,  # divide by 1000 to convert calories to kcal
            "calories": 0.001,
            "calorie": 0.001,
            "kJ": 0.239006,  # multiply by this to convert kJ to kcal
            "kilojoules": 0.239006,
            "kilojoule": 0.239006,
            "J": 0.000239006,  # multiply by this to convert J to kcal
            "joules": 0.000239006,
            "joule": 0.000239006
        },
        VitalMetricType.FLIGHTS_CLIMBED: {
            "flights": 1.0,  # standard
            "flight": 1.0,
            "floors": 1.0,
            "floor": 1.0,
            "levels": 1.0,
            "level": 1.0,
            "stories": 1.0,
            "story": 1.0
        },
        VitalMetricType.DISTANCE_WALKING: {
            "km": 1.0,  # standard
            "kilometers": 1.0,
            "kilometer": 1.0,
            "mi": 1.60934,
            "miles": 1.60934,
            "mile": 1.60934,
            "m": 0.001,
            "meters": 0.001,
            "meter": 0.001,
            "ft": 0.0003048,
            "feet": 0.0003048,
            "foot": 0.0003048
        },
        VitalMetricType.WORKOUTS: {
            "minutes": 1.0,  # standard (changed to minutes as it's more practical)
            "minute": 1.0,
            "min": 1.0,
            "hours": 60.0,  # multiply by 60 to convert hours to minutes
            "hour": 60.0,
            "hr": 60.0,
            "h": 60.0,
            "seconds": 0.0166667,  # divide by 60 to convert seconds to minutes
            "second": 0.0166667,
            "sec": 0.0166667,
            "s": 0.0166667
        },
        VitalMetricType.WORKOUT_DURATION: {
            "minutes": 1.0,  # standard
            "minute": 1.0,
            "min": 1.0,
            "hours": 60.0,  # multiply by 60 to convert hours to minutes
            "hour": 60.0,
            "hr": 60.0,
            "h": 60.0,
            "seconds": 0.0166667,  # divide by 60 to convert seconds to minutes
            "second": 0.0166667,
            "sec": 0.0166667,
            "s": 0.0166667
        },
        VitalMetricType.WORKOUT_CALORIES: {
            "kcal": 1.0,  # standard
            "kilocalories": 1.0,
            "kilocalorie": 1.0,
            "cal": 0.001,  # divide by 1000 to convert calories to kcal
            "calories": 0.001,
            "calorie": 0.001,
            "kJ": 0.239006,  # multiply by this to convert kJ to kcal
            "kilojoules": 0.239006,
            "kilojoule": 0.239006,
            "J": 0.000239006,  # multiply by this to convert J to kcal
            "joules": 0.000239006,
            "joule": 0.000239006
        },
        VitalMetricType.WORKOUT_DISTANCE: {
            "meters": 1.0,  # standard
            "meter": 1.0,
            "m": 1.0,
            "km": 1000.0,  # multiply by 1000 to convert km to meters
            "kilometers": 1000.0,
            "kilometer": 1000.0,
            "mi": 1609.34,  # multiply by this to convert miles to meters
            "miles": 1609.34,
            "mile": 1609.34,
            "ft": 0.3048,  # multiply by this to convert feet to meters
            "feet": 0.3048,
            "foot": 0.3048,
            "yd": 0.9144,  # multiply by this to convert yards to meters
            "yards": 0.9144,
            "yard": 0.9144
        },
        VitalMetricType.SLEEP: {
            "hours": 1.0,  # standard
            "hour": 1.0,
            "hr": 1.0,
            "h": 1.0,
            "minutes": 0.0166667,  # divide by 60 to convert minutes to hours
            "minute": 0.0166667,
            "min": 0.0166667,
            "seconds": 0.000277778,  # divide by 3600 to convert seconds to hours
            "second": 0.000277778,
            "sec": 0.000277778,
            "s": 0.000277778
        },
        VitalMetricType.STAND_TIME: {
            "hours": 1.0,  # standard
            "hour": 1.0,
            "hr": 1.0,
            "h": 1.0,
            "minutes": 0.0166667,  # divide by 60 to convert minutes to hours
            "minute": 0.0166667,
            "min": 0.0166667,
            "seconds": 0.000277778,  # divide by 3600 to convert seconds to hours
            "second": 0.000277778,
            "sec": 0.000277778,
            "s": 0.000277778
        }
    }
    
    # Valid ranges for each metric (min, max) to validate converted values
    VALID_RANGES: Dict[VitalMetricType, Tuple[float, float]] = {
        VitalMetricType.HEIGHT: (30.0, 300.0),  # cm
        VitalMetricType.BODY_MASS: (1.0, 500.0),  # kg
        VitalMetricType.BODY_TEMPERATURE: (30.0, 45.0),  # °C
        VitalMetricType.HEART_RATE: (30, 220),  # bpm
        VitalMetricType.BLOOD_PRESSURE_SYSTOLIC: (50, 300),  # mmHg
        VitalMetricType.BLOOD_PRESSURE_DIASTOLIC: (30, 200),  # mmHg
        VitalMetricType.BLOOD_SUGAR: (20, 800),  # mg/dL
        VitalMetricType.BMI: (10.0, 80.0),  # kg/m²
        VitalMetricType.OXYGEN_SATURATION: (50.0, 100.0),  # %
        VitalMetricType.STEP_COUNT: (0, 100000),  # steps
        VitalMetricType.STAND_TIME: (0, 24),  # hours
        VitalMetricType.ACTIVE_ENERGY: (0, 10000),  # kcal
        VitalMetricType.FLIGHTS_CLIMBED: (0, 500),  # flights
        VitalMetricType.WORKOUTS: (0, 600),  # minutes
        VitalMetricType.WORKOUT_DURATION: (0, 600),  # minutes
        VitalMetricType.WORKOUT_CALORIES: (0, 5000),  # kcal
        VitalMetricType.WORKOUT_DISTANCE: (0, 100000),  # meters (100km max)
        VitalMetricType.SLEEP: (0, 24),  # hours
        VitalMetricType.DISTANCE_WALKING: (0, 200)  # km
    }
    
    @classmethod
    def get_standard_unit(cls, metric_type: VitalMetricType) -> str:
        """Get the standard unit for a given metric type"""
        return cls.STANDARD_UNITS.get(metric_type, "unknown")
    
    @classmethod
    def convert_to_standard_unit(cls, value: float, input_unit: str, metric_type: VitalMetricType) -> Tuple[float, str]:
        """
        Convert a value from input unit to standard unit for the given metric type
        
        Args:
            value: The numeric value to convert
            input_unit: The unit of the input value
            metric_type: The type of metric being converted
            
        Returns:
            Tuple of (converted_value, standard_unit)
            
        Raises:
            UnitConversionError: If conversion fails or units are incompatible
        """
        # Get standard unit
        standard_unit = cls.get_standard_unit(metric_type)
        
        # If input unit is already standard, just validate and return
        if input_unit.lower().strip() == standard_unit.lower():
            converted_value = value
        else:
            # Get conversion mappings for this metric type
            conversions = cls.UNIT_CONVERSIONS.get(metric_type, {})
            
            # Find matching conversion (case-insensitive)
            conversion_factor = None
            normalized_input = input_unit.lower().strip()
            
            for unit_key, factor in conversions.items():
                if unit_key.lower() == normalized_input:
                    conversion_factor = factor
                    break
            
            if conversion_factor is None:
                raise UnitConversionError(
                    f"Cannot convert from '{input_unit}' to '{standard_unit}' for {metric_type.value}. "
                    f"Supported units: {list(conversions.keys())}"
                )
            
            # Handle special conversions
            if conversion_factor == "fahrenheit_conversion":
                converted_value = cls._convert_fahrenheit_to_celsius(value)
            else:
                converted_value = value * conversion_factor
        
        # Validate the converted value is within reasonable range
        cls._validate_value_range(converted_value, metric_type)
        
        return converted_value, standard_unit
    
    @classmethod
    def _convert_fahrenheit_to_celsius(cls, fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius"""
        return (fahrenheit - 32) * 5/9
    
    @classmethod
    def _validate_value_range(cls, value: float, metric_type: VitalMetricType) -> None:
        """Validate that a converted value is within acceptable range"""
        valid_range = cls.VALID_RANGES.get(metric_type)
        if valid_range:
            min_val, max_val = valid_range
            if value < min_val or value > max_val:
                raise UnitConversionError(
                    f"Converted value {value} for {metric_type.value} is outside valid range "
                    f"({min_val} - {max_val} {cls.get_standard_unit(metric_type)})"
                )
    
    @classmethod
    def normalize_unit_string(cls, unit: str) -> str:
        """Normalize unit string by removing extra spaces and standardizing case"""
        if not unit:
            return unit
        
        # Common unit normalizations
        normalizations = {
            "count/min": "bpm",
            "beats/min": "bpm",
            "beats per minute": "bpm",
            "deg f": "°F",
            "deg c": "°C",
            "degree f": "°F",
            "degree c": "°C",
            "degrees f": "°F", 
            "degrees c": "°C"
        }
        
        normalized = unit.lower().strip()
        return normalizations.get(normalized, unit.strip())
    
    @classmethod
    def is_unit_compatible(cls, unit: str, metric_type: VitalMetricType) -> bool:
        """Check if a unit is compatible with a given metric type"""
        conversions = cls.UNIT_CONVERSIONS.get(metric_type, {})
        normalized_unit = unit.lower().strip()
        
        # Check direct matches
        for supported_unit in conversions.keys():
            if supported_unit.lower() == normalized_unit:
                return True
        
        # Check if it's already the standard unit
        standard_unit = cls.get_standard_unit(metric_type)
        if standard_unit.lower() == normalized_unit:
            return True
        
        return False


def convert_vital_unit(value: float, input_unit: str, metric_type: VitalMetricType) -> Tuple[float, str]:
    """
    Convenience function to convert vital units
    
    Args:
        value: The numeric value to convert
        input_unit: The unit of the input value  
        metric_type: The type of metric being converted
        
    Returns:
        Tuple of (converted_value, standard_unit)
    """
    return VitalUnitConverter.convert_to_standard_unit(value, input_unit, metric_type)


def get_standard_unit_for_metric(metric_type: VitalMetricType) -> str:
    """
    Get the standard unit for a metric type
    
    Args:
        metric_type: The metric type
        
    Returns:
        Standard unit string
    """
    return VitalUnitConverter.get_standard_unit(metric_type) 