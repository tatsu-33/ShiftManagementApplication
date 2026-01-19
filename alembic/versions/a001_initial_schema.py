"""Initial schema creation

Revision ID: a001
Revises: 
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema."""
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('line_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('worker', 'admin', name='userrole'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('line_id')
    )
    op.create_index('ix_users_line_id', 'users', ['line_id'])
    
    # Create requests table
    op.create_table(
        'requests',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('worker_id', sa.String(36), nullable=False),
        sa.Column('request_date', sa.Date(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='requeststatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processed_by', sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['worker_id'], ['users.id']),
        sa.ForeignKeyConstraint(['processed_by'], ['users.id']),
        sa.UniqueConstraint('worker_id', 'request_date', name='uq_worker_request_date')
    )
    op.create_index('ix_requests_worker_id', 'requests', ['worker_id'])
    op.create_index('ix_requests_request_date', 'requests', ['request_date'])
    op.create_index('ix_requests_status', 'requests', ['status'])
    
    # Create shifts table
    op.create_table(
        'shifts',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('worker_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', sa.String(36), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['worker_id'], ['users.id']),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.UniqueConstraint('shift_date', 'worker_id', name='uq_shift_date_worker')
    )
    op.create_index('ix_shifts_shift_date', 'shifts', ['shift_date'])
    op.create_index('ix_shifts_worker_id', 'shifts', ['worker_id'])
    
    # Create settings table
    op.create_table(
        'settings',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value', sa.String(1000), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', sa.String(36), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.UniqueConstraint('key')
    )
    op.create_index('ix_settings_key', 'settings', ['key'])
    
    # Create reminder_logs table
    op.create_table(
        'reminder_logs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('worker_id', sa.String(36), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('days_before_deadline', sa.Integer(), nullable=False),
        sa.Column('target_month', sa.Integer(), nullable=False),
        sa.Column('target_year', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['worker_id'], ['users.id'])
    )
    op.create_index('ix_reminder_logs_worker_id', 'reminder_logs', ['worker_id'])
    op.create_index('ix_reminder_logs_sent_at', 'reminder_logs', ['sent_at'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('reminder_logs')
    op.drop_table('settings')
    op.drop_table('shifts')
    op.drop_table('requests')
    op.drop_table('users')
