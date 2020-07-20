"""
add bootstrap-config columns

Revision ID: 63db6872060f
Revises: de903581465c
Create Date: 2020-06-29 08:59:07.525039
"""

import sqlalchemy as sa
from alembic import op


revision = '63db6872060f'
down_revision = 'de903581465c'

def upgrade():
    op.add_column('copr', sa.Column('bootstrap_config', sa.Text()))
    op.add_column('copr', sa.Column('bootstrap_image', sa.Text()))
    op.add_column('copr_chroot', sa.Column('bootstrap_config', sa.Text()))
    op.add_column('copr_chroot', sa.Column('bootstrap_image', sa.Text()))
    op.add_column('build', sa.Column('bootstrap_config', sa.Text()))
    op.add_column('build', sa.Column('bootstrap_image', sa.Text()))


    op.execute("""
    UPDATE
        copr
    SET
        bootstrap_config = 'enabled'
    WHERE
        use_bootstrap_container = true
    """)

    op.execute("""
    UPDATE
        copr
    SET
        bootstrap_config = 'disabled'
    WHERE
        use_bootstrap_container = false
    """)

    op.drop_column('copr', 'use_bootstrap_container')

def downgrade():
    op.add_column('copr', sa.Column('use_bootstrap_container', sa.Boolean(),
                  nullable=False, server_default='f'))

    op.execute("""
    UPDATE
        copr
    SET
        use_bootstrap_container = true
    WHERE
        bootstrap_config = 'enabled'
    """)

    op.execute("""
    UPDATE
        copr
    SET
        use_bootstrap_container = false
    WHERE
        bootstrap_config = 'disabled'
    """)

    op.drop_column('copr', 'bootstrap_config')
    op.drop_column('copr', 'bootstrap_image')
    op.drop_column('copr_chroot', 'bootstrap_config')
    op.drop_column('copr_chroot', 'bootstrap_image')
    op.drop_column('build', 'bootstrap_config')
    op.drop_column('build', 'bootstrap_image')
