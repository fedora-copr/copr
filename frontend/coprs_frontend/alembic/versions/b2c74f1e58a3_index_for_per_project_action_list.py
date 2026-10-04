"""
Add composite index for the per-project action list

Revision ID: b2c74f1e58a3
Revises: 43f9339a9e9a
Create Date: 2026-09-30 09:12:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'b2c74f1e58a3'
down_revision = '43f9339a9e9a'
branch_labels = None
depends_on = None


INDEX_NAME = "action_copr_id_id"
TABLE_NAME = "action"


def upgrade():
    # The Actions tab lists actions of a single project ordered by ID.  With
    # the plain ix_action_copr_id index Postgres has to sort all the matching
    # rows, which hurts for projects with many thousands of actions.
    op.create_index(INDEX_NAME, TABLE_NAME, ["copr_id", "id"], unique=False)


def downgrade():
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
