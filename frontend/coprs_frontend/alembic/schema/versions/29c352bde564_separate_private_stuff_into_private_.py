"""separate private stuff into private tables by schema

Revision ID: 29c352bde564
Revises: 6fed8655d074
Create Date: 2018-12-03 12:55:34.810037

"""

# revision identifiers, used by Alembic.
revision = '29c352bde564'
down_revision = '6fed8655d074'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('user_private',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('mail', sa.String(length=150), nullable=False),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('api_login', sa.String(length=40), nullable=False),
    sa.Column('api_token', sa.String(length=40), nullable=False),
    sa.Column('api_token_expiration', sa.Date(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_private_user_id'), 'user_private', ['user_id'], unique=True)
    op.create_table('copr_private',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('webhook_secret', sa.String(length=100), nullable=True),
    sa.Column('scm_api_auth_json', sa.Text(), nullable=True),
    sa.Column('copr_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['copr_id'], ['copr.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('copr_private_webhook_secret', 'copr_private', ['webhook_secret'], unique=False)
    op.create_index(op.f('ix_copr_private_copr_id'), 'copr_private', ['copr_id'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_copr_private_copr_id'), table_name='copr_private')
    op.drop_index('copr_private_webhook_secret', table_name='copr_private')
    op.drop_table('copr_private')
    op.drop_index(op.f('ix_user_private_user_id'), table_name='user_private')
    op.drop_table('user_private')
