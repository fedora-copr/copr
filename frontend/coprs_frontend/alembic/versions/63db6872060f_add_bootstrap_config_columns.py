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
    op.add_column('copr', sa.Column('bootstrap', sa.Text()))
    op.add_column('copr_chroot', sa.Column('bootstrap', sa.Text()))
    op.add_column('copr_chroot', sa.Column('bootstrap_image', sa.Text()))
    op.add_column('build', sa.Column('bootstrap', sa.Text()))


    op.execute("""
    UPDATE
        copr
    SET
        bootstrap = 'on'
    WHERE
        use_bootstrap_container = true
    """)

    op.execute("""
    UPDATE
        copr
    SET
        bootstrap = 'off'
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
        bootstrap = 'on'
    """)

    op.execute("""
    UPDATE
        copr
    SET
        use_bootstrap_container = false
    WHERE
        bootstrap = 'off'
    """)

    op.drop_column('copr', 'bootstrap')
    op.drop_column('copr_chroot', 'bootstrap')
    op.drop_column('copr_chroot', 'bootstrap_image')
    op.drop_column('build', 'bootstrap')
