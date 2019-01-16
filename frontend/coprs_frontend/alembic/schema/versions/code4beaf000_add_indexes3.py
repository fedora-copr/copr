"""add indexes3

Revision ID: code4beaf000_add_indexes3.py
Revises: deadbeafc0de
Create Date: 2019-01-16 14:43:00.000000

"""
# revision identifiers, used by Alembic.
revision = 'code4beaf000'
down_revision = 'deadbeafc0de'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index('build_canceled_is_background_source_status_id_idx', 'build', ['canceled', 'is_background', 'source_status', 'id'], unique=False)


def downgrade():
    op.drop_index('build_canceled_is_background_source_status_id_idx', table_name='build')
