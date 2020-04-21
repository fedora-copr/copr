"""map mock croots to dits-git branch

Revision ID: bf4b5dc74740
Revises: 38ea34def9a
Create Date: 2017-05-19 07:55:05.743045

"""

# revision identifiers, used by Alembic.
revision = 'bf4b5dc74740'
down_revision = '38ea34def9a'

from alembic import op
import sqlalchemy as sa

from sqlalchemy.orm import sessionmaker

import sys, os
sys.path.append(os.getcwd())
from coprs.models import MockChroot
from coprs.helpers import chroot_to_branch
from coprs.logic.coprs_logic import BranchesLogic

def upgrade():
    bind = op.get_bind()
    Session = sessionmaker()
    session = Session(bind=bind)

    op.create_table('dist_git_branch',
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('name')
    )

    # Nullable at this point.
    op.add_column(u'mock_chroot', sa.Column('distgit_branch_name', sa.String(length=50), nullable=True))
    op.create_foreign_key(None, 'mock_chroot', 'dist_git_branch', ['distgit_branch_name'], ['name'])

    for chroot in session.query(MockChroot).all():
        # Pick the predefined default.
        branch = chroot_to_branch(chroot.name)
        chroot.distgit_branch = BranchesLogic.get_or_create(branch, session)
        session.add(chroot.distgit_branch)
        session.add(chroot)

    session.commit()

    # not nulllable since now..
    op.alter_column('mock_chroot', 'distgit_branch_name',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)


def downgrade():
    op.drop_column(u'mock_chroot', 'distgit_branch_name')
    op.drop_table('dist_git_branch')
