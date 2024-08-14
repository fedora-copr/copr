"""
create webhook history table

Revision ID: 06b208e317a3
Create Date: 2024-07-24 22:04:51.810724
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '06b208e317a3'
down_revision = 'd23f84f87130'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("webhook_history",
                   sa.Column("id", sa.Integer()),
                   sa.Column("timestamp", sa.DateTime(timezone=True),
                             nullable=False, server_default=sa.func.now()),
                   sa.Column("webhook_uuid", sa.Text(), nullable=True),
                   sa.Column("user_agent",sa.Text(), nullable=True),
                   sa.PrimaryKeyConstraint("id")
    )

    op.add_column("build",
                  sa.Column("webhook_history_id",
                  sa.Integer,
                  sa.ForeignKey("webhook_history.id"), nullable=True))

def downgrade():
    op.drop_table("webhook_history")
    op.drop_column("build","webhook_history_id")
