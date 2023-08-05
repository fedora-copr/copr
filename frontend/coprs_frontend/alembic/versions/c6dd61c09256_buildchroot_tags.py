"""
BuildChroot Tags

Revision ID: c6dd61c09256
Create Date: 2023-08-04 12:37:23.509594
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6dd61c09256'
down_revision = '08dd42f4c304'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('build_chroot', sa.Column('tags_raw', sa.String(length=50),
                                            nullable=True))


def downgrade():
    op.drop_column('build_chroot', 'tags_raw')
