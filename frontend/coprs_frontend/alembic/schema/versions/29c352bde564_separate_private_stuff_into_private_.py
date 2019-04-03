"""separate private stuff into private tables by schema

Revision ID: 29c352bde564
Revises: b64659389c54
Create Date: 2018-12-03 12:55:34.810037

"""

# revision identifiers, used by Alembic.
revision = '29c352bde564'
down_revision = 'b64659389c54'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('user_private',
    sa.Column('mail', sa.String(length=150), nullable=False),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('api_login', sa.String(length=40), nullable=False),
    sa.Column('api_token', sa.String(length=40), nullable=False),
    sa.Column('api_token_expiration', sa.Date(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('copr_private',
    sa.Column('webhook_secret', sa.String(length=100), nullable=True),
    sa.Column('scm_api_auth_json', sa.Text(), nullable=True),
    sa.Column('copr_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['copr_id'], ['copr.id'], ),
    sa.PrimaryKeyConstraint('copr_id')
    )
    op.create_index('copr_private_webhook_secret', 'copr_private', ['webhook_secret'], unique=False)


def downgrade():
    op.drop_index('copr_private_webhook_secret', table_name='copr_private')
    op.drop_table('copr_private')
    op.drop_table('user_private')
