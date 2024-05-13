"""
create timeout per copr dir

Revision ID: 9fec2c962fcd
Create Date: 2024-05-13 14:46:06.406773
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9fec2c962fcd'
down_revision = '41763f7a5185'


def upgrade():
    op.add_column('package', sa.Column('timeout', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_package_timeout'), 'package', ['timeout'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_package_timeout'), table_name='package')
    op.drop_column('package', 'timeout')
