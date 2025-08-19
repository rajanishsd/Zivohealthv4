"""Add lab test mapping table

Revision ID: 010
Revises: 009_add_vitamins_minerals_to_aggregates
Create Date: 2024-01-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = '010_add_lab_test_mapping_table'
down_revision: Union[str, None] = '009_add_vitamins_minerals_to_aggregates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create lab_test_mappings table
    op.create_table('lab_test_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('test_name', sa.String(length=255), nullable=False),
        sa.Column('test_category', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('common_units', sa.String(length=100), nullable=True),
        sa.Column('normal_range_info', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_standardized', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('test_name')
    )
    
    # Create indexes
    op.create_index('ix_lab_test_mappings_id', 'lab_test_mappings', ['id'])
    op.create_index('ix_lab_test_mappings_test_name', 'lab_test_mappings', ['test_name'])
    op.create_index('ix_lab_test_mappings_test_category', 'lab_test_mappings', ['test_category'])
    op.create_index('idx_test_category_active', 'lab_test_mappings', ['test_category', 'is_active'])
    op.create_index('idx_test_name_category', 'lab_test_mappings', ['test_name', 'test_category'])
    
    # Populate with test mappings
    current_time = datetime.utcnow()
    
    # Lab test mappings data
    test_mappings = [
        # Liver Function Tests (LFT)
        ('ALT (Alanine Aminotransferase)', 'Liver Function Tests (LFT)', 'Enzyme that indicates liver health', 'U/L', 'Normal: 7-56 U/L'),
        ('AST (Aspartate Aminotransferase)', 'Liver Function Tests (LFT)', 'Enzyme that indicates liver and heart health', 'U/L', 'Normal: 10-40 U/L'),
        ('ALP (Alkaline Phosphatase)', 'Liver Function Tests (LFT)', 'Enzyme found in liver, bones, and other tissues', 'U/L', 'Normal: 44-147 U/L'),
        ('GGT (Gamma-glutamyl Transferase)', 'Liver Function Tests (LFT)', 'Enzyme that indicates liver health', 'U/L', 'Normal: 9-48 U/L'),
        ('Bilirubin (Total)', 'Liver Function Tests (LFT)', 'Total bilirubin in blood', 'mg/dL', 'Normal: 0.3-1.2 mg/dL'),
        ('Bilirubin (Direct)', 'Liver Function Tests (LFT)', 'Direct/conjugated bilirubin', 'mg/dL', 'Normal: 0.0-0.3 mg/dL'),
        ('Bilirubin (Indirect)', 'Liver Function Tests (LFT)', 'Indirect/unconjugated bilirubin', 'mg/dL', 'Normal: 0.2-0.8 mg/dL'),
        ('Albumin', 'Liver Function Tests (LFT)', 'Main protein made by the liver', 'g/dL', 'Normal: 3.5-5.0 g/dL'),
        ('Total Protein', 'Liver Function Tests (LFT)', 'Total protein in blood', 'g/dL', 'Normal: 6.3-8.2 g/dL'),
        
        # Kidney Function Tests (KFT) / Renal Profile
        ('Urea', 'Kidney Function Tests (KFT)', 'Waste product filtered by kidneys', 'mg/dL', 'Normal: 6-20 mg/dL'),
        ('Creatinine', 'Kidney Function Tests (KFT)', 'Waste product that indicates kidney function', 'mg/dL', 'Normal: 0.6-1.2 mg/dL'),
        ('Uric Acid', 'Kidney Function Tests (KFT)', 'Waste product from purine breakdown', 'mg/dL', 'Normal: 3.4-7.0 mg/dL'),
        ('BUN (Blood Urea Nitrogen)', 'Kidney Function Tests (KFT)', 'Nitrogen component of urea in blood', 'mg/dL', 'Normal: 7-20 mg/dL'),
        ('eGFR (Estimated Glomerular Filtration Rate)', 'Kidney Function Tests (KFT)', 'Estimate of kidney function', 'mL/min/1.73m²', 'Normal: >60 mL/min/1.73m²'),
        
        # Complete Blood Count (CBC)
        ('Hemoglobin', 'Complete Blood Count (CBC)', 'Oxygen-carrying protein in red blood cells', 'g/dL', 'Normal: 12-16 g/dL (women), 14-18 g/dL (men)'),
        ('RBC', 'Complete Blood Count (CBC)', 'Red blood cell count', 'million/µL', 'Normal: 4.2-5.4 million/µL (women), 4.7-6.1 million/µL (men)'),
        ('WBC', 'Complete Blood Count (CBC)', 'White blood cell count', 'thousand/µL', 'Normal: 4.5-11.0 thousand/µL'),
        ('Platelet Count', 'Complete Blood Count (CBC)', 'Blood clotting cells', 'thousand/µL', 'Normal: 150-450 thousand/µL'),
        ('Hematocrit', 'Complete Blood Count (CBC)', 'Percentage of red blood cells in blood', '%', 'Normal: 36-46% (women), 41-50% (men)'),
        ('MCV', 'Complete Blood Count (CBC)', 'Mean corpuscular volume', 'fL', 'Normal: 80-100 fL'),
        ('MCH', 'Complete Blood Count (CBC)', 'Mean corpuscular hemoglobin', 'pg', 'Normal: 27-31 pg'),
        ('MCHC', 'Complete Blood Count (CBC)', 'Mean corpuscular hemoglobin concentration', 'g/dL', 'Normal: 32-36 g/dL'),
        ('Neutrophils', 'Complete Blood Count (CBC)', 'Type of white blood cell', '%', 'Normal: 50-70%'),
        ('Lymphocytes', 'Complete Blood Count (CBC)', 'Type of white blood cell', '%', 'Normal: 20-40%'),
        ('Monocytes', 'Complete Blood Count (CBC)', 'Type of white blood cell', '%', 'Normal: 2-8%'),
        ('Eosinophils', 'Complete Blood Count (CBC)', 'Type of white blood cell', '%', 'Normal: 1-4%'),
        ('Basophils', 'Complete Blood Count (CBC)', 'Type of white blood cell', '%', 'Normal: 0.5-1%'),
        
        # Electrolyte Panel
        ('Sodium', 'Electrolyte Panel', 'Essential electrolyte for fluid balance', 'mEq/L', 'Normal: 136-145 mEq/L'),
        ('Potassium', 'Electrolyte Panel', 'Essential electrolyte for muscle function', 'mEq/L', 'Normal: 3.5-5.0 mEq/L'),
        ('Chloride', 'Electrolyte Panel', 'Essential electrolyte for acid-base balance', 'mEq/L', 'Normal: 98-107 mEq/L'),
        ('Calcium', 'Electrolyte Panel', 'Essential mineral for bones and muscles', 'mg/dL', 'Normal: 8.5-10.5 mg/dL'),
        ('Magnesium', 'Electrolyte Panel', 'Essential mineral for enzyme function', 'mg/dL', 'Normal: 1.7-2.2 mg/dL'),
        ('Phosphorus', 'Electrolyte Panel', 'Essential mineral for bones and energy', 'mg/dL', 'Normal: 2.5-4.5 mg/dL'),
        
        # Cardiac Markers
        ('Troponin I', 'Cardiac Markers', 'Protein released during heart muscle damage', 'ng/mL', 'Normal: <0.04 ng/mL'),
        ('Troponin T', 'Cardiac Markers', 'Protein released during heart muscle damage', 'ng/mL', 'Normal: <0.01 ng/mL'),
        ('CK-MB', 'Cardiac Markers', 'Heart-specific enzyme', 'ng/mL', 'Normal: <6.3 ng/mL'),
        ('BNP', 'Cardiac Markers', 'Hormone released by heart during stress', 'pg/mL', 'Normal: <100 pg/mL'),
        ('NT-proBNP', 'Cardiac Markers', 'Hormone released by heart during stress', 'pg/mL', 'Normal: <125 pg/mL'),
        ('CRP (C-Reactive Protein)', 'Cardiac Markers', 'Inflammation marker', 'mg/L', 'Normal: <3.0 mg/L'),
        ('LDH (Lactate Dehydrogenase)', 'Cardiac Markers', 'Enzyme found in many tissues', 'U/L', 'Normal: 140-280 U/L'),
        
        # Diabetes Panel
        ('Fasting Blood Sugar (FBS)', 'Diabetes Panel', 'Blood glucose after fasting', 'mg/dL', 'Normal: 70-100 mg/dL'),
        ('Postprandial Blood Sugar (PPBS)', 'Diabetes Panel', 'Blood glucose after meal', 'mg/dL', 'Normal: <140 mg/dL'),
        ('HbA1c', 'Diabetes Panel', 'Average blood sugar over 2-3 months', '%', 'Normal: <5.7%'),
        ('Insulin (Fasting)', 'Diabetes Panel', 'Fasting insulin level', 'µU/mL', 'Normal: 2.6-24.9 µU/mL'),
        ('Insulin (Post-meal)', 'Diabetes Panel', 'Post-meal insulin level', 'µU/mL', 'Normal: varies'),
        ('C-Peptide', 'Diabetes Panel', 'Marker of insulin production', 'ng/mL', 'Normal: 0.8-3.1 ng/mL'),
        
        # Lipid Profile
        ('Total Cholesterol', 'Lipid Profile', 'Total cholesterol in blood', 'mg/dL', 'Normal: <200 mg/dL'),
        ('LDL', 'Lipid Profile', 'Low-density lipoprotein (bad cholesterol)', 'mg/dL', 'Normal: <100 mg/dL'),
        ('HDL', 'Lipid Profile', 'High-density lipoprotein (good cholesterol)', 'mg/dL', 'Normal: >40 mg/dL (men), >50 mg/dL (women)'),
        ('VLDL', 'Lipid Profile', 'Very low-density lipoprotein', 'mg/dL', 'Normal: 5-40 mg/dL'),
        ('Triglycerides', 'Lipid Profile', 'Type of fat in blood', 'mg/dL', 'Normal: <150 mg/dL'),
        
        # Thyroid Profile
        ('TSH', 'Thyroid Profile', 'Thyroid stimulating hormone', 'mIU/L', 'Normal: 0.4-4.0 mIU/L'),
        ('T3 (Triiodothyronine)', 'Thyroid Profile', 'Active thyroid hormone', 'ng/dL', 'Normal: 100-200 ng/dL'),
        ('T4 (Thyroxine)', 'Thyroid Profile', 'Main thyroid hormone', 'µg/dL', 'Normal: 5.0-12.0 µg/dL'),
        ('FT3', 'Thyroid Profile', 'Free triiodothyronine', 'pg/mL', 'Normal: 2.3-4.2 pg/mL'),
        ('FT4', 'Thyroid Profile', 'Free thyroxine', 'ng/dL', 'Normal: 0.8-1.8 ng/dL'),
        
        # Hormonal Panel
        ('Testosterone', 'Hormonal Panel', 'Male sex hormone', 'ng/dL', 'Normal: 300-1000 ng/dL (men)'),
        ('Estrogen (Estradiol)', 'Hormonal Panel', 'Female sex hormone', 'pg/mL', 'Normal: varies by cycle'),
        ('Progesterone', 'Hormonal Panel', 'Female hormone', 'ng/mL', 'Normal: varies by cycle'),
        ('LH', 'Hormonal Panel', 'Luteinizing hormone', 'mIU/mL', 'Normal: varies by gender/age'),
        ('FSH', 'Hormonal Panel', 'Follicle stimulating hormone', 'mIU/mL', 'Normal: varies by gender/age'),
        ('Prolactin', 'Hormonal Panel', 'Hormone that stimulates milk production', 'ng/mL', 'Normal: 4-23 ng/mL'),
        ('DHEA-S', 'Hormonal Panel', 'Dehydroepiandrosterone sulfate', 'µg/dL', 'Normal: varies by age/gender'),
        ('Cortisol', 'Hormonal Panel', 'Stress hormone', 'µg/dL', 'Normal: 6-23 µg/dL'),
        
        # Vitamin & Mineral Panel
        ('Vitamin D (25-OH)', 'Vitamin & Mineral Panel', '25-hydroxyvitamin D', 'ng/mL', 'Normal: 30-100 ng/mL'),
        ('Vitamin B12', 'Vitamin & Mineral Panel', 'Essential vitamin for nerve function', 'pg/mL', 'Normal: 200-900 pg/mL'),
        ('Folate', 'Vitamin & Mineral Panel', 'Essential vitamin for DNA synthesis', 'ng/mL', 'Normal: 2.7-17.0 ng/mL'),
        ('Iron', 'Vitamin & Mineral Panel', 'Essential mineral for blood', 'µg/dL', 'Normal: 60-170 µg/dL'),
        ('Ferritin', 'Vitamin & Mineral Panel', 'Iron storage protein', 'ng/mL', 'Normal: 12-150 ng/mL (women), 12-300 ng/mL (men)'),
        ('TIBC (Total Iron-Binding Capacity)', 'Vitamin & Mineral Panel', 'Total iron-binding capacity', 'µg/dL', 'Normal: 240-450 µg/dL'),
        ('Zinc', 'Vitamin & Mineral Panel', 'Essential trace mineral', 'µg/dL', 'Normal: 70-120 µg/dL'),
        
        # Infection Markers
        ('ESR (Erythrocyte Sedimentation Rate)', 'Infection Markers', 'Inflammation marker', 'mm/hr', 'Normal: <30 mm/hr (men), <20 mm/hr (women)'),
        ('CRP', 'Infection Markers', 'C-reactive protein inflammation marker', 'mg/L', 'Normal: <3.0 mg/L'),
        ('Procalcitonin', 'Infection Markers', 'Bacterial infection marker', 'ng/mL', 'Normal: <0.25 ng/mL'),
        ('Widal', 'Infection Markers', 'Typhoid fever test', 'Titer', 'Normal: <1:80'),
        ('Typhoid IgG', 'Infection Markers', 'Typhoid antibody test', 'Index', 'Normal: <1.1'),
        ('Typhoid IgM', 'Infection Markers', 'Typhoid antibody test', 'Index', 'Normal: <1.1'),
        ('Dengue NS1', 'Infection Markers', 'Dengue antigen test', 'Index', 'Normal: <1.1'),
        ('Dengue IgG', 'Infection Markers', 'Dengue antibody test', 'Index', 'Normal: <1.1'),
        ('Dengue IgM', 'Infection Markers', 'Dengue antibody test', 'Index', 'Normal: <1.1'),
        ('COVID RT-PCR', 'Infection Markers', 'COVID-19 genetic material test', 'Detected/Not Detected', 'Normal: Not Detected'),
        ('COVID Antibody', 'Infection Markers', 'COVID-19 antibody test', 'Index', 'Normal: <1.4'),
        
        # Urine & Stool Tests
        ('Routine Urine Test', 'Urine & Stool Tests', 'Complete urine analysis', 'Various', 'Normal: varies by parameter'),
        ('Urine Culture', 'Urine & Stool Tests', 'Bacterial culture of urine', 'CFU/mL', 'Normal: <10,000 CFU/mL'),
        ('Stool Routine', 'Urine & Stool Tests', 'Complete stool analysis', 'Various', 'Normal: varies by parameter'),
        ('Stool Occult Blood', 'Urine & Stool Tests', 'Hidden blood in stool', 'Positive/Negative', 'Normal: Negative'),
        
        # Tumor Markers
        ('PSA (Prostate-Specific Antigen)', 'Tumor Markers', 'Prostate cancer marker', 'ng/mL', 'Normal: <4.0 ng/mL'),
        ('CA-125', 'Tumor Markers', 'Ovarian cancer marker', 'U/mL', 'Normal: <35 U/mL'),
        ('CEA', 'Tumor Markers', 'Carcinoembryonic antigen', 'ng/mL', 'Normal: <5.0 ng/mL'),
        ('AFP (Alpha-fetoprotein)', 'Tumor Markers', 'Liver cancer marker', 'ng/mL', 'Normal: <10 ng/mL'),
    ]
    
    # Insert the data
    for test_name, test_category, description, common_units, normal_range_info in test_mappings:
        op.execute(
            sa.text(
                "INSERT INTO lab_test_mappings (test_name, test_category, description, common_units, normal_range_info, is_active, is_standardized, created_at, updated_at) "
                "VALUES (:test_name, :test_category, :description, :common_units, :normal_range_info, :is_active, :is_standardized, :created_at, :updated_at)"
            ),
            {
                'test_name': test_name,
                'test_category': test_category,
                'description': description,
                'common_units': common_units,
                'normal_range_info': normal_range_info,
                'is_active': True,
                'is_standardized': True,
                'created_at': current_time,
                'updated_at': current_time
            }
        )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_test_name_category', table_name='lab_test_mappings')
    op.drop_index('idx_test_category_active', table_name='lab_test_mappings')
    op.drop_index('ix_lab_test_mappings_test_category', table_name='lab_test_mappings')
    op.drop_index('ix_lab_test_mappings_test_name', table_name='lab_test_mappings')
    op.drop_index('ix_lab_test_mappings_id', table_name='lab_test_mappings')
    
    # Drop table
    op.drop_table('lab_test_mappings') 