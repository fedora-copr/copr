"""
add project tags

Revision ID: fe7f7d55dde3
Create Date: 2026-08-23 12:23:00.181615
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'fe7f7d55dde3'
down_revision = 'e31b4af2468c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'project_tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_on', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_project_tag_name'), 'project_tag', ['name'], unique=True)

    op.create_table(
        'copr_project_tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('copr_id', sa.Integer(), nullable=False),
        sa.Column('project_tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['copr_id'], ['copr.id'], ),
        sa.ForeignKeyConstraint(['project_tag_id'], ['project_tag.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('copr_id', 'project_tag_id',
                            name='copr_project_tag_copr_id_project_tag_id_uniq'),
    )
    op.create_index(op.f('ix_copr_project_tag_copr_id'), 'copr_project_tag', ['copr_id'], unique=False)
    op.create_index(op.f('ix_copr_project_tag_project_tag_id'), 'copr_project_tag', ['project_tag_id'], unique=False)


def downgrade():
    op.drop_table('copr_project_tag')
    op.drop_table('project_tag')
