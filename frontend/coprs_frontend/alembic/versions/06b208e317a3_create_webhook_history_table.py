"""
create webhook history table

Revision ID: 06b208e317a3
Create Date: 2024-07-24 22:04:51.810724
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '06b208e317a3'
down_revision = 'd23f84f87130'
branch_labels = None
depends_on = None


def upgrade():
 op.create_table('webhook_history',
 sa.Column('id', sa.Integer()),
 sa.Column('timestamp', sa.Integer, nullable=False),
 sa.Column('webhook_uuid', UUID(as_uuid=True), nullable=False),
 sa.Column('user_agent',sa.String(30), default="Unknown"),
 sa.Column('build_id', sa.Integer()),
 sa.PrimaryKeyConstraint('id')                   
    )


def downgrade():
 op.drop_table("webhook_history")
