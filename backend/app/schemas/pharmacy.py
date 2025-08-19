from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum

from app.models.pharmacy_data import PharmacyDataSource, MedicationType, PharmacyType


# Base schemas
class PharmacyDataBase(BaseModel):
    """Base schema for pharmacy data"""
    medication_name: str = Field(..., description="Name of the medication")
    medication_type: MedicationType = Field(..., description="Type of medication")
    quantity: float = Field(..., gt=0, description="Quantity purchased")
    quantity_unit: str = Field(..., description="Unit of quantity (tablets, capsules, bottles, etc.)")
    
    # Optional medication details
    brand_name: Optional[str] = Field(None, description="Brand name of medication")
    generic_name: Optional[str] = Field(None, description="Generic name of medication")
    dosage_form: Optional[str] = Field(None, description="Form of medication (tablet, capsule, liquid, etc.)")
    strength: Optional[str] = Field(None, description="Strength of medication (e.g., 500mg, 10ml)")
    days_supply: Optional[int] = Field(None, ge=0, description="Number of days medication should last")
    refills_remaining: Optional[int] = Field(None, ge=0, description="Number of refills remaining")
    
    # Pharmacy information
    pharmacy_name: Optional[str] = Field(None, description="Name of the pharmacy")
    pharmacy_type: Optional[PharmacyType] = Field(None, description="Type of pharmacy")
    pharmacy_address: Optional[str] = Field(None, description="Address of pharmacy")
    pharmacy_phone: Optional[str] = Field(None, description="Phone number of pharmacy")
    pharmacist_name: Optional[str] = Field(None, description="Name of pharmacist")
    
    # Prescriber information
    prescriber_name: Optional[str] = Field(None, description="Name of prescriber")
    prescriber_npi: Optional[str] = Field(None, description="NPI number of prescriber")
    prescriber_dea: Optional[str] = Field(None, description="DEA number of prescriber")
    
    # Financial information
    total_cost: float = Field(..., ge=0, description="Total cost of medication")
    insurance_coverage: Optional[float] = Field(0.0, ge=0, description="Insurance coverage amount")
    copay_amount: Optional[float] = Field(0.0, ge=0, description="Copay amount")
    deductible_amount: Optional[float] = Field(0.0, ge=0, description="Deductible amount")
    
    # Timing
    purchase_date: date = Field(..., description="Date of purchase")
    purchase_time: datetime = Field(..., description="Time of purchase")
    prescription_date: Optional[date] = Field(None, description="Date prescription was written")
    expiration_date: Optional[date] = Field(None, description="Expiration date of medication")
    
    # Source and metadata
    data_source: PharmacyDataSource = Field(..., description="Source of the data")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="AI confidence score")
    image_url: Optional[str] = Field(None, description="URL to uploaded image")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Prescription details
    prescription_number: Optional[str] = Field(None, description="Prescription number")
    ndc_number: Optional[str] = Field(None, description="National Drug Code")
    lot_number: Optional[str] = Field(None, description="Lot number")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")


class PharmacyDataCreate(PharmacyDataBase):
    """Schema for creating pharmacy data"""
    user_id: int = Field(..., description="User ID")


class PharmacyDataUpdate(BaseModel):
    """Schema for updating pharmacy data"""
    medication_name: Optional[str] = None
    medication_type: Optional[MedicationType] = None
    quantity: Optional[float] = None
    quantity_unit: Optional[str] = None
    brand_name: Optional[str] = None
    generic_name: Optional[str] = None
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    days_supply: Optional[int] = None
    refills_remaining: Optional[int] = None
    pharmacy_name: Optional[str] = None
    pharmacy_type: Optional[PharmacyType] = None
    pharmacy_address: Optional[str] = None
    pharmacy_phone: Optional[str] = None
    pharmacist_name: Optional[str] = None
    prescriber_name: Optional[str] = None
    prescriber_npi: Optional[str] = None
    prescriber_dea: Optional[str] = None
    total_cost: Optional[float] = None
    insurance_coverage: Optional[float] = None
    copay_amount: Optional[float] = None
    deductible_amount: Optional[float] = None
    purchase_date: Optional[date] = None
    purchase_time: Optional[datetime] = None
    prescription_date: Optional[date] = None
    expiration_date: Optional[date] = None
    data_source: Optional[PharmacyDataSource] = None
    confidence_score: Optional[float] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None
    prescription_number: Optional[str] = None
    ndc_number: Optional[str] = None
    lot_number: Optional[str] = None
    manufacturer: Optional[str] = None


class PharmacyDataResponse(PharmacyDataBase):
    """Schema for pharmacy data response"""
    id: int
    user_id: int
    aggregation_status: str
    aggregated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Aggregate schemas
class PharmacyDailyAggregateBase(BaseModel):
    """Base schema for daily pharmacy aggregates"""
    aggregation_date: date = Field(..., alias="date", description="Date of aggregation")
    total_spent: float = Field(0.0, ge=0, description="Total amount spent")
    total_insurance_coverage: float = Field(0.0, ge=0, description="Total insurance coverage")
    total_copay: float = Field(0.0, ge=0, description="Total copay amount")
    total_deductible: float = Field(0.0, ge=0, description="Total deductible amount")
    total_medications: int = Field(0, ge=0, description="Total number of medications")
    prescription_count: int = Field(0, ge=0, description="Number of prescription medications")
    otc_count: int = Field(0, ge=0, description="Number of OTC medications")
    supplement_count: int = Field(0, ge=0, description="Number of supplements")
    unique_pharmacies: int = Field(0, ge=0, description="Number of unique pharmacies visited")
    total_visits: int = Field(0, ge=0, description="Total number of pharmacy visits")

    class Config:
        from_attributes = True
        validate_by_name = True


class PharmacyDailyAggregateResponse(PharmacyDailyAggregateBase):
    """Schema for daily pharmacy aggregate response"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


# Bulk operation schemas
class PharmacyDataBulkCreate(BaseModel):
    """Schema for bulk creating pharmacy data"""
    items: List[PharmacyDataCreate] = Field(..., description="List of pharmacy data items to create")


class PharmacyDataBulkResponse(BaseModel):
    """Schema for bulk operation response"""
    created_count: int = Field(..., description="Number of items successfully created")
    failed_count: int = Field(..., description="Number of items that failed to create")
    created_items: List[PharmacyDataResponse] = Field(..., description="Successfully created items")
    errors: List[str] = Field(..., description="List of error messages for failed items")