"""
add cancel_requests table

Revision ID: 484a1d4dd424
Revises: b0fd99505e37
Create Date: 2020-05-14 18:39:06.284361
"""

import sqlalchemy as sa
from alembic import op


revision = '484a1d4dd424'
down_revision = 'b0fd99505e37'

def upgrade():
    op.create_table(
        'cancel_request',
        sa.Column('what', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('what')
    )

def downgrade():
    op.drop_table('cancel_request')
