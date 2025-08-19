#!/usr/bin/env python3
"""
Vitals Mapping Table Creator

This script creates a vitals_mappings table with LOINC codes for common vital signs
and populates it with standard vital sign mappings.
"""

import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine, text, Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
load_dotenv()
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration - use environment variables or defaults
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://rajanishsd@localhost:5433/zivohealth')

Base = declarative_base()

class VitalsMapping(Base):
    """Vitals mapping table model"""
    __tablename__ = 'vitals_mappings'
    
    vital_sign = Column(String(255), primary_key=True)
    loinc_code = Column(String(50), nullable=True)
    property = Column(String(100), nullable=True)
    units = Column(String(100), nullable=True)
    system = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

# Vitals data to insert
VITALS_DATA = [
    {
        "vital_sign": "Body Temperature",
        "loinc_code": "8310-5",
        "property": "Temp",
        "units": "°C / °F",
        "system": "Body",
        "description": "Oral, rectal, tympanic, or axillary"
    },
    {
        "vital_sign": "Heart Rate (Pulse)",
        "loinc_code": "8867-4",
        "property": "Rate",
        "units": "beats/min",
        "system": "Heart",
        "description": "Beats per minute"
    },
    {
        "vital_sign": "Respiratory Rate",
        "loinc_code": "9279-1",
        "property": "Rate",
        "units": "breaths/min",
        "system": "Respiratory",
        "description": "Breaths per minute"
    },
    {
        "vital_sign": "Systolic Blood Pressure",
        "loinc_code": "8480-6",
        "property": "Press",
        "units": "mmHg",
        "system": "Arterial",
        "description": "Higher number in BP"
    },
    {
        "vital_sign": "Diastolic Blood Pressure",
        "loinc_code": "8462-4",
        "property": "Press",
        "units": "mmHg",
        "system": "Arterial",
        "description": "Lower number in BP"
    },
    {
        "vital_sign": "Mean Arterial Pressure",
        "loinc_code": "8478-0",
        "property": "Press",
        "units": "mmHg",
        "system": "Arterial",
        "description": "Useful in ICU or critical care"
    },
    {
        "vital_sign": "Oxygen Saturation (SpO₂)",
        "loinc_code": "59408-5",
        "property": "%",
        "units": "%",
        "system": "Blood",
        "description": "From pulse oximeter"
    },
    {
        "vital_sign": "Body Weight (measured)",
        "loinc_code": "29463-7",
        "property": "Mass",
        "units": "kg / lbs",
        "system": "Body",
        "description": "Weight of patient"
    },
    {
        "vital_sign": "Body Height (measured)",
        "loinc_code": "8302-2",
        "property": "Len",
        "units": "cm / inches",
        "system": "Body",
        "description": "Measured standing height"
    },
    {
        "vital_sign": "BMI (Body Mass Index)",
        "loinc_code": "39156-5",
        "property": "Ratio",
        "units": "kg/m²",
        "system": "Body",
        "description": "Calculated from height & weight"
    },
    {
        "vital_sign": "Head Circumference (infants)",
        "loinc_code": "8287-5",
        "property": "Len",
        "units": "cm",
        "system": "Head",
        "description": "Pediatric vital sign"
    },
    {
        "vital_sign": "Pain Score (0–10)",
        "loinc_code": "72514-3",
        "property": "Score",
        "units": "N/A",
        "system": "Self-report",
        "description": "Numeric pain rating scale"
    },
    {
        "vital_sign": "Steps Taken",
        "loinc_code": "41950-7",
        "property": "Num",
        "units": "count",
        "system": "Daily step count",
        "description": "Daily step count from wearable devices"
    },
    {
        "vital_sign": "Active Energy Burned",
        "loinc_code": "41981-2",
        "property": "Cal",
        "units": "kcal",
        "system": "Apple Watch / Fitbit",
        "description": "Active calories burned from wearable devices"
    },
    {
        "vital_sign": "Distance Walked/Run",
        "loinc_code": "41953-1",
        "property": "Len",
        "units": "meters",
        "system": "From wearable device",
        "description": "Distance tracked by wearable devices"
    },
    {
        "vital_sign": "Heart Rate (continuous)",
        "loinc_code": "8889-8",
        "property": "Rate",
        "units": "beats/min",
        "system": "Device streaming",
        "description": "Continuous heart rate monitoring from devices"
    },
    {
        "vital_sign": "Flights Climbed",
        "loinc_code": None,  # Custom - no standard LOINC code
        "property": "Num",
        "units": "floors",
        "system": "Use custom or FHIR extension",
        "description": "Floors climbed, requires custom implementation or FHIR extension"
    }
]

def create_vitals_mapping_table():
    """Create the vitals_mappings table"""
    logger.info("🚀 Creating vitals_mappings table...")
    
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        # Create table
        Base.metadata.create_all(engine, tables=[VitalsMapping.__table__])
        logger.info("✅ Vitals mappings table created successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating vitals mappings table: {e}")
        return False

def populate_vitals_mapping_table():
    """Populate the vitals_mappings table with data"""
    logger.info("📝 Populating vitals_mappings table...")
    
    try:
        # Create database engine and session
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if table exists
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'vitals_mappings'
            )
        """))
        
        if not result.scalar():
            logger.error("❌ Vitals mappings table does not exist. Run create_vitals_mapping_table() first.")
            return False
        
        # Clear existing data
        session.execute(text("DELETE FROM vitals_mappings"))
        logger.info("🧹 Cleared existing vitals mappings data")
        
        # Insert new data
        for vital_data in VITALS_DATA:
            vital_mapping = VitalsMapping(**vital_data)
            session.add(vital_mapping)
        
        session.commit()
        logger.info(f"✅ Successfully inserted {len(VITALS_DATA)} vitals mappings")
        
        # Verify insertion
        result = session.execute(text("SELECT COUNT(*) FROM vitals_mappings"))
        count = result.scalar()
        logger.info(f"📊 Total vitals mappings in table: {count}")
        
        session.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error populating vitals mappings table: {e}")
        return False

def show_vitals_mappings():
    """Display all vitals mappings"""
    logger.info("📋 Displaying vitals mappings...")
    
    try:
        # Create database engine and session
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Query all vitals mappings
        result = session.execute(text("""
            SELECT vital_sign, loinc_code, property, units, system, description
            FROM vitals_mappings
            ORDER BY vital_sign
        """))
        
        vitals = result.fetchall()
        
        if not vitals:
            logger.warning("⚠️  No vitals mappings found in table")
            return
        
        logger.info(f"📊 Found {len(vitals)} vitals mappings:")
        logger.info("-" * 100)
        logger.info(f"{'Vital Sign':<30} {'LOINC Code':<15} {'Property':<10} {'Units':<15} {'System':<20}")
        logger.info("-" * 100)
        
        for vital in vitals:
            loinc_code = vital[1] if vital[1] else "Custom"
            logger.info(f"{vital[0]:<30} {loinc_code:<15} {vital[2]:<10} {vital[3]:<15} {vital[4]:<20}")
        
        logger.info("-" * 100)
        
        session.close()
        
    except Exception as e:
        logger.error(f"❌ Error displaying vitals mappings: {e}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vitals Mapping Table Manager")
    parser.add_argument("--create-table", action="store_true", help="Create vitals_mappings table")
    parser.add_argument("--populate", action="store_true", help="Populate vitals_mappings table")
    parser.add_argument("--show", action="store_true", help="Show all vitals mappings")
    parser.add_argument("--setup", action="store_true", help="Create table and populate with data")
    
    args = parser.parse_args()
    
    if not any([args.create_table, args.populate, args.show, args.setup]):
        logger.error("Please specify at least one action")
        parser.print_help()
        return
    
    try:
        if args.create_table:
            create_vitals_mapping_table()
        
        if args.populate:
            populate_vitals_mapping_table()
        
        if args.show:
            show_vitals_mappings()
        
        if args.setup:
            if create_vitals_mapping_table():
                populate_vitals_mapping_table()
                show_vitals_mappings()
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    main() 