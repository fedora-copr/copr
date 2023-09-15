"""
Add status_reason column

Revision ID: ec3528516b0c
Create Date: 2023-09-15 21:13:43.183755
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ec3528516b0c'
down_revision = 'c6dd61c09256'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('build_chroot',
                  sa.Column('status_reason', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('build_chroot', 'status_reason')
