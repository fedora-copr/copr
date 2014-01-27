"""Add token information to the user table

Revision ID: 32ba137a3d56
Revises: 595a31c145fb
Create Date: 2013-01-07 20:56:14.698735

"""

# revision identifiers, used by Alembic.
revision = "32ba137a3d56"
down_revision = "595a31c145fb"

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Add the coluns api_token and api_token_expiration to the user table.
    """
    op.add_column("user", sa.Column("api_token", sa.String(40),
                                    nullable=False,
                                    server_default="default_token"))

    op.add_column("user", sa.Column("api_token_expiration", sa.Date,
                                    nullable=False,
                                    server_default="2000-1-1"))


def downgrade():
    """ Drop the coluns api_token and api_token_expiration to the user table.
    """
    op.drop_column("user", "api_token")
    op.drop_column("user", "api_token_expiration")
