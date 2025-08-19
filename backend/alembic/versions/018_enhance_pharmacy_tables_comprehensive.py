"""enhance_pharmacy_tables_comprehensive

Revision ID: 018
Revises: 017
Create Date: 2025-01-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add comprehensive fields to pharmacy_bills table
    
    # Pharmacy details enhancements
    op.add_column('pharmacy_bills', sa.Column('pharmacy_gstin', sa.String(20), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('pharmacy_fssai_license', sa.String(20), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('pharmacy_dl_numbers', postgresql.JSON(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('pharmacy_registration_address', sa.Text(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('pharmacy_premise_address', sa.Text(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('pos_location', sa.String(100), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('pharmacist_name', sa.String(255), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('pharmacist_registration_number', sa.String(50), nullable=True))
    
    # Bill information enhancements
    op.add_column('pharmacy_bills', sa.Column('bill_type', sa.String(50), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('invoice_number', sa.String(100), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('order_id', sa.String(100), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('order_date', sa.Date(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('invoice_date', sa.Date(), nullable=True))
    
    # Financial breakdown enhancements
    op.add_column('pharmacy_bills', sa.Column('gross_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('taxable_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('cgst_rate', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('cgst_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('sgst_rate', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('sgst_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('igst_rate', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('igst_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('total_gst_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('shipping_charges', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('vas_charges', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('credits_applied', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('payable_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('amount_in_words', sa.Text(), nullable=True))
    
    # Customer information
    op.add_column('pharmacy_bills', sa.Column('patient_name', sa.String(255), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('patient_address', sa.Text(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('patient_contact', sa.String(20), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('place_of_supply', sa.String(100), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('doctor_address', sa.Text(), nullable=True))
    
    # Transaction details
    op.add_column('pharmacy_bills', sa.Column('transaction_id', sa.String(100), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('payment_method', sa.String(50), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('transaction_timestamp', sa.DateTime(), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('transaction_amount', sa.Float(), nullable=True))
    
    # Additional information
    op.add_column('pharmacy_bills', sa.Column('support_contact', sa.String(100), nullable=True))
    op.add_column('pharmacy_bills', sa.Column('compliance_codes', postgresql.JSON(), nullable=True))
    
    # Add comprehensive fields to pharmacy_medications table
    
    # Medication details enhancements
    op.add_column('pharmacy_medications', sa.Column('brand_name', sa.String(255), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('unit_of_measurement', sa.String(20), nullable=True))
    
    # Manufacturer and regulatory information
    op.add_column('pharmacy_medications', sa.Column('manufacturer_name', sa.String(255), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('hsn_code', sa.String(20), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('batch_number', sa.String(50), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('expiry_date', sa.Date(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('ndc_number', sa.String(20), nullable=True))
    
    # Pricing details enhancements
    op.add_column('pharmacy_medications', sa.Column('mrp', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('discount_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('taxable_amount', sa.Float(), nullable=True))
    
    # Tax breakdown
    op.add_column('pharmacy_medications', sa.Column('gst_rate', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('gst_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('cgst_rate', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('cgst_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('sgst_rate', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('sgst_amount', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('igst_rate', sa.Float(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('igst_amount', sa.Float(), nullable=True))
    
    # Regulatory information
    op.add_column('pharmacy_medications', sa.Column('prescription_validity_date', sa.Date(), nullable=True))
    op.add_column('pharmacy_medications', sa.Column('dispensing_dl_number', sa.String(50), nullable=True))


def downgrade() -> None:
    # Remove all added columns from pharmacy_medications table
    op.drop_column('pharmacy_medications', 'dispensing_dl_number')
    op.drop_column('pharmacy_medications', 'prescription_validity_date')
    op.drop_column('pharmacy_medications', 'igst_amount')
    op.drop_column('pharmacy_medications', 'igst_rate')
    op.drop_column('pharmacy_medications', 'sgst_amount')
    op.drop_column('pharmacy_medications', 'sgst_rate')
    op.drop_column('pharmacy_medications', 'cgst_amount')
    op.drop_column('pharmacy_medications', 'cgst_rate')
    op.drop_column('pharmacy_medications', 'gst_amount')
    op.drop_column('pharmacy_medications', 'gst_rate')
    op.drop_column('pharmacy_medications', 'taxable_amount')
    op.drop_column('pharmacy_medications', 'discount_amount')
    op.drop_column('pharmacy_medications', 'mrp')
    op.drop_column('pharmacy_medications', 'ndc_number')
    op.drop_column('pharmacy_medications', 'expiry_date')
    op.drop_column('pharmacy_medications', 'batch_number')
    op.drop_column('pharmacy_medications', 'hsn_code')
    op.drop_column('pharmacy_medications', 'manufacturer_name')
    op.drop_column('pharmacy_medications', 'unit_of_measurement')
    op.drop_column('pharmacy_medications', 'brand_name')
    
    # Remove all added columns from pharmacy_bills table
    op.drop_column('pharmacy_bills', 'compliance_codes')
    op.drop_column('pharmacy_bills', 'support_contact')
    op.drop_column('pharmacy_bills', 'transaction_amount')
    op.drop_column('pharmacy_bills', 'transaction_timestamp')
    op.drop_column('pharmacy_bills', 'payment_method')
    op.drop_column('pharmacy_bills', 'transaction_id')
    op.drop_column('pharmacy_bills', 'doctor_address')
    op.drop_column('pharmacy_bills', 'place_of_supply')
    op.drop_column('pharmacy_bills', 'patient_contact')
    op.drop_column('pharmacy_bills', 'patient_address')
    op.drop_column('pharmacy_bills', 'patient_name')
    op.drop_column('pharmacy_bills', 'amount_in_words')
    op.drop_column('pharmacy_bills', 'payable_amount')
    op.drop_column('pharmacy_bills', 'credits_applied')
    op.drop_column('pharmacy_bills', 'vas_charges')
    op.drop_column('pharmacy_bills', 'shipping_charges')
    op.drop_column('pharmacy_bills', 'total_gst_amount')
    op.drop_column('pharmacy_bills', 'igst_amount')
    op.drop_column('pharmacy_bills', 'igst_rate')
    op.drop_column('pharmacy_bills', 'sgst_amount')
    op.drop_column('pharmacy_bills', 'sgst_rate')
    op.drop_column('pharmacy_bills', 'cgst_amount')
    op.drop_column('pharmacy_bills', 'cgst_rate')
    op.drop_column('pharmacy_bills', 'taxable_amount')
    op.drop_column('pharmacy_bills', 'gross_amount')
    op.drop_column('pharmacy_bills', 'invoice_date')
    op.drop_column('pharmacy_bills', 'order_date')
    op.drop_column('pharmacy_bills', 'order_id')
    op.drop_column('pharmacy_bills', 'invoice_number')
    op.drop_column('pharmacy_bills', 'bill_type')
    op.drop_column('pharmacy_bills', 'pharmacist_registration_number')
    op.drop_column('pharmacy_bills', 'pharmacist_name')
    op.drop_column('pharmacy_bills', 'pos_location')
    op.drop_column('pharmacy_bills', 'pharmacy_premise_address')
    op.drop_column('pharmacy_bills', 'pharmacy_registration_address')
    op.drop_column('pharmacy_bills', 'pharmacy_dl_numbers')
    op.drop_column('pharmacy_bills', 'pharmacy_fssai_license')
    op.drop_column('pharmacy_bills', 'pharmacy_gstin') 