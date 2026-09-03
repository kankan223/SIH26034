"""create initial schema

Revision ID: 001
Revises: 
Create Date: 2026-09-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum types
    op.execute("CREATE TYPE role AS ENUM ('inspector', 'senior_officer', 'admin')")
    op.execute("CREATE TYPE inspectionstatus AS ENUM ('draft', 'analyzing', 'review', 'reviewed', 'reported')")
    op.execute("CREATE TYPE overallstatus AS ENUM ('compliant', 'non_compliant', 'partially_compliant', 'needs_human_review', 'insufficient_evidence')")
    op.execute("CREATE TYPE verdict AS ENUM ('pass', 'fail', 'needs_review', 'not_applicable')")
    op.execute("CREATE TYPE severity AS ENUM ('critical', 'major', 'minor')")
    op.execute("CREATE TYPE source AS ENUM ('physical', 'ecommerce')")

    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # categories
    op.create_table(
        'categories',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parent_id', sa.Uuid(), sa.ForeignKey('categories.id'), nullable=True),
    )

    # products
    op.create_table(
        'products',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('barcode', sa.String(255), nullable=True, index=True),
        sa.Column('product_name', sa.String(500), nullable=False),
        sa.Column('category_id', sa.Uuid(), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('manufacturer_name', sa.String(500), nullable=True),
        sa.Column('previous_inspection_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # inspections
    op.create_table(
        'inspections',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('inspector_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('source', sa.String(50), nullable=False, server_default='physical'),
        sa.Column('overall_status', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    )

    # images
    op.create_table(
        'images',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('inspection_id', sa.Uuid(), sa.ForeignKey('inspections.id'), nullable=False),
        sa.Column('storage_url', sa.String(1000), nullable=False),
        sa.Column('content_hash', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('quality_issues', postgresql.JSONB(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ocr_results
    op.create_table(
        'ocr_results',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('image_id', sa.Uuid(), sa.ForeignKey('images.id'), nullable=False),
        sa.Column('raw_text', sa.String(5000), nullable=False),
        sa.Column('bbox', postgresql.JSONB(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # declarations
    op.create_table(
        'declarations',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('inspection_id', sa.Uuid(), sa.ForeignKey('inspections.id'), nullable=False),
        sa.Column('field_type', sa.String(100), nullable=False),
        sa.Column('value', postgresql.JSONB(), nullable=True),
        sa.Column('bbox', postgresql.JSONB(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('source_ocr_result_id', sa.Uuid(), sa.ForeignKey('ocr_results.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # rules
    op.create_table(
        'rules',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('rule_key', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('title', sa.String(500), nullable=False),
    )

    # rule_versions
    op.create_table(
        'rule_versions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('rule_id', sa.Uuid(), sa.ForeignKey('rules.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', postgresql.JSONB(), nullable=True),
        sa.Column('legal_reference', sa.String(1000), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('published_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )

    # compliance_checks
    op.create_table(
        'compliance_checks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('inspection_id', sa.Uuid(), sa.ForeignKey('inspections.id'), nullable=False),
        sa.Column('rule_version_id', sa.Uuid(), sa.ForeignKey('rule_versions.id'), nullable=False),
        sa.Column('declaration_id', sa.Uuid(), sa.ForeignKey('declarations.id'), nullable=True),
        sa.Column('verdict', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # violations
    op.create_table(
        'violations',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('inspection_id', sa.Uuid(), sa.ForeignKey('inspections.id'), nullable=False),
        sa.Column('compliance_check_id', sa.Uuid(), sa.ForeignKey('compliance_checks.id'), nullable=False),
        sa.Column('field', sa.String(100), nullable=False),
        sa.Column('severity', sa.String(50), nullable=False),
        sa.Column('issue_description', sa.Text(), nullable=True),
        sa.Column('detected_value', sa.String(500), nullable=True),
        sa.Column('expected_condition', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # evidence
    op.create_table(
        'evidence',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('violation_id', sa.Uuid(), sa.ForeignKey('violations.id'), nullable=False),
        sa.Column('image_id', sa.Uuid(), sa.ForeignKey('images.id'), nullable=False),
        sa.Column('bbox', postgresql.JSONB(), nullable=True),
        sa.Column('crop_storage_url', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # corrections
    op.create_table(
        'corrections',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('declaration_id', sa.Uuid(), sa.ForeignKey('declarations.id'), nullable=True),
        sa.Column('compliance_check_id', sa.Uuid(), sa.ForeignKey('compliance_checks.id'), nullable=True),
        sa.Column('corrected_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('original_value', postgresql.JSONB(), nullable=True),
        sa.Column('corrected_value', postgresql.JSONB(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # reports
    op.create_table(
        'reports',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('inspection_id', sa.Uuid(), sa.ForeignKey('inspections.id'), nullable=False),
        sa.Column('pdf_storage_url', sa.String(1000), nullable=True),
        sa.Column('editable_export_url', sa.String(1000), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('generated_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
    )

    # audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(255), nullable=False),
        sa.Column('before_value', postgresql.JSONB(), nullable=True),
        sa.Column('after_value', postgresql.JSONB(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Indexes per prd.md §20.2
    op.create_index('idx_inspections_status_region_created', 'inspections', ['status', 'region', 'created_at'])
    op.create_index('idx_rule_versions_rule_id_effective', 'rule_versions', ['rule_id', 'effective_date'])
    op.create_index('idx_audit_logs_entity', 'audit_logs', ['entity_type', 'entity_id'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('reports')
    op.drop_table('corrections')
    op.drop_table('evidence')
    op.drop_table('violations')
    op.drop_table('compliance_checks')
    op.drop_table('rule_versions')
    op.drop_table('rules')
    op.drop_table('declarations')
    op.drop_table('ocr_results')
    op.drop_table('images')
    op.drop_table('inspections')
    op.drop_table('products')
    op.drop_table('categories')
    op.drop_table('users')

    op.execute("DROP TYPE IF EXISTS source")
    op.execute("DROP TYPE IF EXISTS severity")
    op.execute("DROP TYPE IF EXISTS verdict")
    op.execute("DROP TYPE IF EXISTS overallstatus")
    op.execute("DROP TYPE IF EXISTS inspectionstatus")
    op.execute("DROP TYPE IF EXISTS role")
