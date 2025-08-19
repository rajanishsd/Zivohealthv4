#!/usr/bin/env python3
"""
Medical Mappings Table Creator
==============================

This script creates and populates:
1. vitals_mappings - Vital signs with LOINC codes
2. prescription_mappings - Prescriptions with RxNorm and SNOMED CT codes
3. medical_images_mappings - Medical images with RadLex and SNOMED CT codes

Usage:
    python create_medical_mappings.py --setup-all
    python create_medical_mappings.py --setup-vitals
    python create_medical_mappings.py --setup-prescriptions
    python create_medical_mappings.py --setup-images
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import argparse

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Third-party imports
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, DateTime, Text, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('create_medical_mappings.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql://rajanishsd@localhost:5433/zivohealth"
Base = declarative_base()

# Vital Signs Data with LOINC Codes
VITAL_SIGNS_DATA = [
    {
        'vital_name': 'Body Temperature',
        'loinc_code': '8310-5',
        'description': 'Body temperature measurement',
        'common_units': '°C, °F',
        'normal_range': '36.1-37.2°C (97.0-99.0°F)',
        'category': 'Temperature'
    },
    {
        'vital_name': 'Heart Rate',
        'loinc_code': '8867-4',
        'description': 'Heart rate measurement',
        'common_units': 'bpm',
        'normal_range': '60-100 bpm',
        'category': 'Cardiovascular'
    },
    {
        'vital_name': 'Respiratory Rate',
        'loinc_code': '9279-1',
        'description': 'Respiratory rate measurement',
        'common_units': 'breaths/min',
        'normal_range': '12-20 breaths/min',
        'category': 'Respiratory'
    },
    {
        'vital_name': 'Blood Pressure Systolic',
        'loinc_code': '8480-6',
        'description': 'Systolic blood pressure',
        'common_units': 'mmHg',
        'normal_range': '<120 mmHg',
        'category': 'Cardiovascular'
    },
    {
        'vital_name': 'Blood Pressure Diastolic',
        'loinc_code': '8462-4',
        'description': 'Diastolic blood pressure',
        'common_units': 'mmHg',
        'normal_range': '<80 mmHg',
        'category': 'Cardiovascular'
    },
    {
        'vital_name': 'Oxygen Saturation (SpO2)',
        'loinc_code': '59408-5',
        'description': 'Oxygen saturation in arterial blood',
        'common_units': '%',
        'normal_range': '95-100%',
        'category': 'Respiratory'
    },
    {
        'vital_name': 'Height',
        'loinc_code': '8302-2',
        'description': 'Body height measurement',
        'common_units': 'cm, in',
        'normal_range': 'Varies by age/gender',
        'category': 'Anthropometric'
    },
    {
        'vital_name': 'Weight',
        'loinc_code': '29463-7',
        'description': 'Body weight measurement',
        'common_units': 'kg, lbs',
        'normal_range': 'Varies by age/gender',
        'category': 'Anthropometric'
    },
    {
        'vital_name': 'BMI',
        'loinc_code': '39156-5',
        'description': 'Body mass index',
        'common_units': 'kg/m²',
        'normal_range': '18.5-24.9 kg/m²',
        'category': 'Anthropometric'
    },
    {
        'vital_name': 'Blood Glucose',
        'loinc_code': '2339-0',
        'description': 'Blood glucose measurement',
        'common_units': 'mg/dL',
        'normal_range': '70-100 mg/dL (fasting)',
        'category': 'Metabolic'
    }
]

# Prescription Data with RxNorm and SNOMED CT codes
PRESCRIPTION_DATA = [
    {
        'medication_name': 'Aspirin',
        'generic_name': 'Acetylsalicylic acid',
        'rxnorm_code': '1191',
        'snomedct_code': '372665008',
        'medication_type': 'NSAID',
        'dosage_form': 'Tablet',
        'strength': '81mg, 325mg',
        'description': 'Non-steroidal anti-inflammatory drug for pain and blood thinning'
    },
    {
        'medication_name': 'Lisinopril',
        'generic_name': 'Lisinopril',
        'rxnorm_code': '29046',
        'snomedct_code': '430193006',
        'medication_type': 'ACE Inhibitor',
        'dosage_form': 'Tablet',
        'strength': '5mg, 10mg, 20mg, 40mg',
        'description': 'Angiotensin-converting enzyme inhibitor for hypertension'
    },
    {
        'medication_name': 'Metformin',
        'generic_name': 'Metformin',
        'rxnorm_code': '6809',
        'snomedct_code': '430193006',
        'medication_type': 'Biguanide',
        'dosage_form': 'Tablet',
        'strength': '500mg, 850mg, 1000mg',
        'description': 'Oral diabetes medication for type 2 diabetes'
    },
    {
        'medication_name': 'Atorvastatin',
        'generic_name': 'Atorvastatin',
        'rxnorm_code': '83367',
        'snomedct_code': '430193006',
        'medication_type': 'Statin',
        'dosage_form': 'Tablet',
        'strength': '10mg, 20mg, 40mg, 80mg',
        'description': 'HMG-CoA reductase inhibitor for cholesterol management'
    },
    {
        'medication_name': 'Omeprazole',
        'generic_name': 'Omeprazole',
        'rxnorm_code': '7646',
        'snomedct_code': '430193006',
        'medication_type': 'Proton Pump Inhibitor',
        'dosage_form': 'Capsule, Tablet',
        'strength': '10mg, 20mg, 40mg',
        'description': 'Proton pump inhibitor for acid reflux and ulcers'
    }
]

# Medical Images Data with RadLex and SNOMED CT codes
MEDICAL_IMAGES_DATA = [
    {
        'image_type': 'Chest X-Ray',
        'radlex_code': 'RID10300',
        'snomedct_code': '399208008',
        'body_part': 'Chest',
        'modality': 'X-Ray',
        'description': 'Radiographic examination of the chest'
    },
    {
        'image_type': 'CT Scan - Head',
        'radlex_code': 'RID10301',
        'snomedct_code': '71651007',
        'body_part': 'Head',
        'modality': 'CT',
        'description': 'Computed tomography of the head'
    },
    {
        'image_type': 'MRI - Brain',
        'radlex_code': 'RID10302',
        'snomedct_code': '71651007',
        'body_part': 'Brain',
        'modality': 'MRI',
        'description': 'Magnetic resonance imaging of the brain'
    },
    {
        'image_type': 'Ultrasound - Abdominal',
        'radlex_code': 'RID10303',
        'snomedct_code': '71651007',
        'body_part': 'Abdomen',
        'modality': 'Ultrasound',
        'description': 'Ultrasonography of the abdomen'
    },
    {
        'image_type': 'Mammography',
        'radlex_code': 'RID10304',
        'snomedct_code': '71651007',
        'body_part': 'Breast',
        'modality': 'X-Ray',
        'description': 'Radiographic examination of the breast'
    },
    {
        'image_type': 'Echocardiogram',
        'radlex_code': 'RID10305',
        'snomedct_code': '71651007',
        'body_part': 'Heart',
        'modality': 'Ultrasound',
        'description': 'Ultrasonography of the heart'
    }
]

class VitalSignMapping(Base):
    """Vital signs mapping table"""
    __tablename__ = "vitals_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    vital_name = Column(String(255), nullable=False, unique=True, index=True)
    loinc_code = Column(String(20), nullable=True, index=True)
    description = Column(Text)
    common_units = Column(String(100))
    normal_range = Column(String(255))
    category = Column(String(100), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_vital_category_active', 'category', 'is_active'),
        Index('idx_vital_name_category', 'vital_name', 'category'),
    )

class PrescriptionMapping(Base):
    """Prescription mapping table"""
    __tablename__ = "prescription_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    medication_name = Column(String(255), nullable=False, unique=True, index=True)
    generic_name = Column(String(255), nullable=True, index=True)
    rxnorm_code = Column(String(20), nullable=True, index=True)
    snomedct_code = Column(String(20), nullable=True, index=True)
    medication_type = Column(String(100), nullable=True, index=True)
    dosage_form = Column(String(100))
    strength = Column(String(255))
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_prescription_type_active', 'medication_type', 'is_active'),
        Index('idx_prescription_name_type', 'medication_name', 'medication_type'),
    )

class MedicalImageMapping(Base):
    """Medical images mapping table"""
    __tablename__ = "medical_images_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    image_type = Column(String(255), nullable=False, unique=True, index=True)
    radlex_code = Column(String(20), nullable=True, index=True)
    snomedct_code = Column(String(20), nullable=True, index=True)
    body_part = Column(String(100), nullable=True, index=True)
    modality = Column(String(50), nullable=True, index=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_image_modality_active', 'modality', 'is_active'),
        Index('idx_image_type_modality', 'image_type', 'modality'),
    )

class MedicalMappingsCreator:
    """Main class for creating medical mappings tables"""
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Create all mapping tables"""
        logger.info("🚀 Creating medical mapping tables...")
        
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ All tables created successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Error creating tables: {e}")
            return False
    
    def setup_vitals_mappings(self):
        """Setup vitals_mappings table with data"""
        logger.info("📊 Setting up vitals_mappings table...")
        
        try:
            session = self.Session()
            
            # Check if data already exists
            existing_count = session.query(VitalSignMapping).count()
            if existing_count > 0:
                logger.info(f"⏭️  Vitals mappings already has {existing_count} records. Skipping.")
                return True
            
            # Insert vital signs data
            created_count = 0
            for vital_data in VITAL_SIGNS_DATA:
                try:
                    vital = VitalSignMapping(**vital_data)
                    session.add(vital)
                    created_count += 1
                    logger.info(f"✅ Added: {vital_data['vital_name']} ({vital_data['loinc_code']})")
                except Exception as e:
                    logger.error(f"❌ Error adding {vital_data['vital_name']}: {e}")
                    continue
            
            session.commit()
            logger.info(f"✅ Successfully created {created_count} vital signs mappings")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up vitals mappings: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def setup_prescription_mappings(self):
        """Setup prescription_mappings table with data"""
        logger.info("💊 Setting up prescription_mappings table...")
        
        try:
            session = self.Session()
            
            # Check if data already exists
            existing_count = session.query(PrescriptionMapping).count()
            if existing_count > 0:
                logger.info(f"⏭️  Prescription mappings already has {existing_count} records. Skipping.")
                return True
            
            # Insert prescription data
            created_count = 0
            for prescription_data in PRESCRIPTION_DATA:
                try:
                    prescription = PrescriptionMapping(**prescription_data)
                    session.add(prescription)
                    created_count += 1
                    logger.info(f"✅ Added: {prescription_data['medication_name']} (RxNorm: {prescription_data['rxnorm_code']})")
                except Exception as e:
                    logger.error(f"❌ Error adding {prescription_data['medication_name']}: {e}")
                    continue
            
            session.commit()
            logger.info(f"✅ Successfully created {created_count} prescription mappings")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up prescription mappings: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def setup_medical_images_mappings(self):
        """Setup medical_images_mappings table with data"""
        logger.info("🖼️  Setting up medical_images_mappings table...")
        
        try:
            session = self.Session()
            
            # Check if data already exists
            existing_count = session.query(MedicalImageMapping).count()
            if existing_count > 0:
                logger.info(f"⏭️  Medical images mappings already has {existing_count} records. Skipping.")
                return True
            
            # Insert medical images data
            created_count = 0
            for image_data in MEDICAL_IMAGES_DATA:
                try:
                    image = MedicalImageMapping(**image_data)
                    session.add(image)
                    created_count += 1
                    logger.info(f"✅ Added: {image_data['image_type']} (RadLex: {image_data['radlex_code']})")
                except Exception as e:
                    logger.error(f"❌ Error adding {image_data['image_type']}: {e}")
                    continue
            
            session.commit()
            logger.info(f"✅ Successfully created {created_count} medical images mappings")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up medical images mappings: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_mapping_stats(self) -> Dict[str, Any]:
        """Get statistics about all mapping tables"""
        logger.info("📊 Getting mapping statistics...")
        
        try:
            session = self.Session()
            
            stats = {}
            
            # Vitals mappings stats
            vitals_count = session.query(VitalSignMapping).count()
            vitals_with_loinc = session.query(VitalSignMapping).filter(
                VitalSignMapping.loinc_code.isnot(None)
            ).count()
            
            stats['vitals'] = {
                'total': vitals_count,
                'with_loinc': vitals_with_loinc,
                'percentage': round((vitals_with_loinc / vitals_count) * 100, 1) if vitals_count > 0 else 0
            }
            
            # Prescription mappings stats
            prescription_count = session.query(PrescriptionMapping).count()
            prescription_with_rxnorm = session.query(PrescriptionMapping).filter(
                PrescriptionMapping.rxnorm_code.isnot(None)
            ).count()
            prescription_with_snomed = session.query(PrescriptionMapping).filter(
                PrescriptionMapping.snomedct_code.isnot(None)
            ).count()
            
            stats['prescriptions'] = {
                'total': prescription_count,
                'with_rxnorm': prescription_with_rxnorm,
                'with_snomed': prescription_with_snomed,
                'rxnorm_percentage': round((prescription_with_rxnorm / prescription_count) * 100, 1) if prescription_count > 0 else 0,
                'snomed_percentage': round((prescription_with_snomed / prescription_count) * 100, 1) if prescription_count > 0 else 0
            }
            
            # Medical images mappings stats
            images_count = session.query(MedicalImageMapping).count()
            images_with_radlex = session.query(MedicalImageMapping).filter(
                MedicalImageMapping.radlex_code.isnot(None)
            ).count()
            images_with_snomed = session.query(MedicalImageMapping).filter(
                MedicalImageMapping.snomedct_code.isnot(None)
            ).count()
            
            stats['medical_images'] = {
                'total': images_count,
                'with_radlex': images_with_radlex,
                'with_snomed': images_with_snomed,
                'radlex_percentage': round((images_with_radlex / images_count) * 100, 1) if images_count > 0 else 0,
                'snomed_percentage': round((images_with_snomed / images_count) * 100, 1) if images_count > 0 else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting mapping stats: {e}")
            return {"error": str(e)}
        finally:
            session.close()

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="Medical Mappings Table Creator")
    parser.add_argument("--setup-all", action="store_true", help="Setup all mapping tables")
    parser.add_argument("--setup-vitals", action="store_true", help="Setup vitals_mappings table")
    parser.add_argument("--setup-prescriptions", action="store_true", help="Setup prescription_mappings table")
    parser.add_argument("--setup-images", action="store_true", help="Setup medical_images_mappings table")
    parser.add_argument("--stats", action="store_true", help="Show mapping statistics")
    
    args = parser.parse_args()
    
    if not any([args.setup_all, args.setup_vitals, args.setup_prescriptions, args.setup_images, args.stats]):
        logger.error("Please specify at least one action")
        parser.print_help()
        return
    
    try:
        creator = MedicalMappingsCreator()
        
        if args.setup_all or args.setup_vitals or args.setup_prescriptions or args.setup_images:
            # Create tables first
            if not creator.create_tables():
                return
        
        if args.setup_all or args.setup_vitals:
            creator.setup_vitals_mappings()
        
        if args.setup_all or args.setup_prescriptions:
            creator.setup_prescription_mappings()
        
        if args.setup_all or args.setup_images:
            creator.setup_medical_images_mappings()
        
        if args.stats:
            stats = creator.get_mapping_stats()
            logger.info(f"📊 Mapping Statistics: {stats}")
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 