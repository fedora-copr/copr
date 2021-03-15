"""
disallow dash in os_release

Revision ID: 6b48324e9264
Revises: 6866cd91c3c6
Create Date: 2021-03-15 15:54:24.870411
"""

from alembic import op

revision = '6b48324e9264'
down_revision = '6866cd91c3c6'

def upgrade():
    op.execute("""
        ALTER TABLE "mock_chroot"
        ADD CONSTRAINT "no_dash_in_version_check"
        CHECK ("os_version" NOT LIKE '%-%')
    """)

def downgrade():
    op.execute("""
        ALTER TABLE mock_chroot DROP CONSTRAINT "no_dash_in_version_check"
    """)
