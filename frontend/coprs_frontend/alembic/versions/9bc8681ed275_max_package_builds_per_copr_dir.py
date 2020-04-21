"""
max package builds per copr dir
"""

import sqlalchemy as sa
from alembic import op

revision = '9bc8681ed275'
down_revision = 'b828274ddebf'


def upgrade():
    op.add_column('package', sa.Column('max_builds', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_package_max_builds'), 'package', ['max_builds'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_package_max_builds'), table_name='package')
    op.drop_column('package', 'max_builds')
