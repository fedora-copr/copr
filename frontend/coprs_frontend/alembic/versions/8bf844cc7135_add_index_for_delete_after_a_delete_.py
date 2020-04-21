"""Add index for delete_after a delete_notify

Revision ID: 8bf844cc7135
Revises: 6fed8655d074
Create Date: 2019-01-04 10:35:26.263517

"""

# revision identifiers, used by Alembic.
revision = '8bf844cc7135'
down_revision = '6fed8655d074'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index(op.f('ix_copr_chroot_delete_after'), 'copr_chroot', ['delete_after'], unique=False)
    op.create_index(op.f('ix_copr_chroot_delete_notify'), 'copr_chroot', ['delete_notify'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_copr_chroot_delete_notify'), table_name='copr_chroot')
    op.drop_index(op.f('ix_copr_chroot_delete_after'), table_name='copr_chroot')
