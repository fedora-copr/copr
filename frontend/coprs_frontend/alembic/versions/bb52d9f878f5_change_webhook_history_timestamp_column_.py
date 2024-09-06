"""
Change Webhook History timestamp column type from DateTime to Integer UNIX timestamp

Revision ID: bb52d9f878f5
Create Date: 2024-09-19 18:07:28.504280
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision = 'bb52d9f878f5'
down_revision = '06b208e317a3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('webhook_history', sa.Column('created_on', sa.Integer(), nullable=True))
    op.drop_column('webhook_history', 'timestamp')

def downgrade():
    op.add_column('webhook_history', sa.Column('timestamp', sa.DateTime(timezone=True), server_default=func.now()))
    op.drop_column('webhook_history', 'created_on')
