"""Add multi-tenant organizations

Revision ID: 002
Revises: 001
Create Date: 2025-01-15 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'organizations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'])

    op.create_table(
        'organization_memberships',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(32), server_default='member'),
        sa.Column('is_default', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_org_memberships_user_id', 'organization_memberships', ['user_id'])
    op.create_index('ix_org_memberships_org_id', 'organization_memberships', ['organization_id'])
    op.create_index('ix_org_memberships_user_org', 'organization_memberships', ['user_id', 'organization_id'], unique=True)

    op.add_column('documents',
        sa.Column('organization_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('ix_documents_organization_id', 'documents', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_documents_organization_id', table_name='documents')
    op.drop_column('documents', 'organization_id')
    op.drop_table('organization_memberships')
    op.drop_table('organizations')
