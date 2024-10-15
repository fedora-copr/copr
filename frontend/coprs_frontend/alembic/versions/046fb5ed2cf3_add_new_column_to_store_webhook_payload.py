"""
add new column to store Webhook payload

Revision ID: 046fb5ed2cf3
Create Date: 2024-10-07 05:53:50.891339
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '046fb5ed2cf3'
down_revision = 'bb52d9f878f5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('webhook_history', sa.Column('payload', sa.Text())) 


def downgrade():
    op.drop_column('webhook_history', 'payload')
