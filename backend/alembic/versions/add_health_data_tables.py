"""Add health data and document processing tables

Revision ID: add_health_data_tables
Revises: b2204deb1260
Create Date: 2025-06-09 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_health_data_tables'
down_revision = 'b2204deb1260'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create vital_signs table
    op.create_table('vital_signs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('blood_pressure_systolic', sa.Integer(), nullable=True),
        sa.Column('blood_pressure_diastolic', sa.Integer(), nullable=True),
        sa.Column('heart_rate', sa.Integer(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('bmi', sa.Float(), nullable=True),
        sa.Column('oxygen_saturation', sa.Float(), nullable=True),
        sa.Column('blood_sugar', sa.Float(), nullable=True),
        sa.Column('measurement_date', sa.DateTime(), nullable=False),
        sa.Column('device_used', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('extracted_from_document_id', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vital_signs_id'), 'vital_signs', ['id'], unique=False)

    # Create lab_reports table
    op.create_table('lab_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('test_name', sa.String(length=255), nullable=False),
        sa.Column('test_category', sa.String(length=100), nullable=True),
        sa.Column('test_value', sa.String(length=100), nullable=True),
        sa.Column('test_unit', sa.String(length=50), nullable=True),
        sa.Column('reference_range', sa.String(length=100), nullable=True),
        sa.Column('test_status', sa.String(length=20), nullable=True),
        sa.Column('lab_name', sa.String(length=255), nullable=True),
        sa.Column('lab_address', sa.Text(), nullable=True),
        sa.Column('ordering_physician', sa.String(length=255), nullable=True),
        sa.Column('test_date', sa.Date(), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=True),
        sa.Column('test_notes', sa.Text(), nullable=True),
        sa.Column('test_methodology', sa.String(length=255), nullable=True),
        sa.Column('extracted_from_document_id', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lab_reports_id'), 'lab_reports', ['id'], unique=False)

    # Create pharmacy_bills table
    op.create_table('pharmacy_bills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('pharmacy_name', sa.String(length=255), nullable=False),
        sa.Column('pharmacy_address', sa.Text(), nullable=True),
        sa.Column('pharmacy_phone', sa.String(length=20), nullable=True),
        sa.Column('bill_number', sa.String(length=100), nullable=True),
        sa.Column('bill_date', sa.Date(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('tax_amount', sa.Float(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=True),
        sa.Column('prescription_number', sa.String(length=100), nullable=True),
        sa.Column('prescribing_doctor', sa.String(length=255), nullable=True),
        sa.Column('extracted_from_document_id', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pharmacy_bills_id'), 'pharmacy_bills', ['id'], unique=False)

    # Create pharmacy_medications table
    op.create_table('pharmacy_medications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bill_id', sa.Integer(), nullable=False),
        sa.Column('medication_name', sa.String(length=255), nullable=False),
        sa.Column('generic_name', sa.String(length=255), nullable=True),
        sa.Column('strength', sa.String(length=100), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('unit_price', sa.Float(), nullable=True),
        sa.Column('total_price', sa.Float(), nullable=True),
        sa.Column('dosage_instructions', sa.Text(), nullable=True),
        sa.Column('frequency', sa.String(length=100), nullable=True),
        sa.Column('duration', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['bill_id'], ['pharmacy_bills.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pharmacy_medications_id'), 'pharmacy_medications', ['id'], unique=False)

    # Create document_processing_logs table
    op.create_table('document_processing_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_type', sa.String(length=20), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('document_type', sa.String(length=50), nullable=True),
        sa.Column('classification_confidence', sa.Float(), nullable=True),
        sa.Column('processing_status', sa.String(length=20), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('ocr_confidence', sa.Float(), nullable=True),
        sa.Column('ocr_engine', sa.String(length=50), nullable=True),
        sa.Column('extracted_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('structured_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_errors', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('records_created', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('records_updated', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('workflow_steps', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('agent_interactions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_processing_logs_id'), 'document_processing_logs', ['id'], unique=False)
    op.create_index(op.f('ix_document_processing_logs_request_id'), 'document_processing_logs', ['request_id'], unique=False)

    # Create opentelemetry_traces table
    op.create_table('opentelemetry_traces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trace_id', sa.String(length=32), nullable=False),
        sa.Column('span_id', sa.String(length=16), nullable=False),
        sa.Column('parent_span_id', sa.String(length=16), nullable=True),
        sa.Column('span_name', sa.String(length=255), nullable=False),
        sa.Column('span_kind', sa.String(length=20), nullable=True),
        sa.Column('status_code', sa.String(length=20), nullable=True),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('service_name', sa.String(length=100), nullable=True),
        sa.Column('operation_name', sa.String(length=100), nullable=True),
        sa.Column('resource_attributes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('span_attributes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('span_events', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('agent_type', sa.String(length=50), nullable=True),
        sa.Column('workflow_step', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_opentelemetry_traces_id'), 'opentelemetry_traces', ['id'], unique=False)
    op.create_index(op.f('ix_opentelemetry_traces_span_id'), 'opentelemetry_traces', ['span_id'], unique=False)
    op.create_index(op.f('ix_opentelemetry_traces_trace_id'), 'opentelemetry_traces', ['trace_id'], unique=False)
    op.create_index(op.f('ix_opentelemetry_traces_request_id'), 'opentelemetry_traces', ['request_id'], unique=False)

    # Create agent_memory table
    op.create_table('agent_memory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('memory_type', sa.String(length=50), nullable=True),
        sa.Column('memory_key', sa.String(length=255), nullable=True),
        sa.Column('memory_value', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('expiry_date', sa.DateTime(), nullable=True),
        sa.Column('last_accessed', sa.DateTime(), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_memory_id'), 'agent_memory', ['id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_agent_memory_id'), table_name='agent_memory')
    op.drop_table('agent_memory')
    
    op.drop_index(op.f('ix_opentelemetry_traces_request_id'), table_name='opentelemetry_traces')
    op.drop_index(op.f('ix_opentelemetry_traces_trace_id'), table_name='opentelemetry_traces')
    op.drop_index(op.f('ix_opentelemetry_traces_span_id'), table_name='opentelemetry_traces')
    op.drop_index(op.f('ix_opentelemetry_traces_id'), table_name='opentelemetry_traces')
    op.drop_table('opentelemetry_traces')
    
    op.drop_index(op.f('ix_document_processing_logs_request_id'), table_name='document_processing_logs')
    op.drop_index(op.f('ix_document_processing_logs_id'), table_name='document_processing_logs')
    op.drop_table('document_processing_logs')
    
    op.drop_index(op.f('ix_pharmacy_medications_id'), table_name='pharmacy_medications')
    op.drop_table('pharmacy_medications')
    
    op.drop_index(op.f('ix_pharmacy_bills_id'), table_name='pharmacy_bills')
    op.drop_table('pharmacy_bills')
    
    op.drop_index(op.f('ix_lab_reports_id'), table_name='lab_reports')
    op.drop_table('lab_reports')
    
    op.drop_index(op.f('ix_vital_signs_id'), table_name='vital_signs')
    op.drop_table('vital_signs') 