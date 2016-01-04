"""status_to_order function

Revision ID: 19ca0c14096e
Revises: 3ec22e1db75a
Create Date: 2015-11-16 21:20:46.498155

"""

# revision identifiers, used by Alembic.
revision = '19ca0c14096e'
down_revision = '3ec22e1db75a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    status_to_order = """
CREATE OR REPLACE FUNCTION status_to_order (x integer)
RETURNS integer AS $$ BEGIN
        RETURN CASE WHEN x = 0 THEN 0
                    WHEN x = 3 THEN 1
                    WHEN x = 6 THEN 2
                    WHEN x = 7 THEN 3
                    WHEN x = 4 THEN 4
                    WHEN x = 1 THEN 5
                    WHEN x = 5 THEN 6
               ELSE 1000
        END; END;
    $$ LANGUAGE plpgsql;
"""

    order_to_status = """
CREATE OR REPLACE FUNCTION order_to_status (x integer)
RETURNS integer AS $$ BEGIN
        RETURN CASE WHEN x = 0 THEN 0
                    WHEN x = 1 THEN 3
                    WHEN x = 2 THEN 6
                    WHEN x = 3 THEN 7
                    WHEN x = 4 THEN 4
                    WHEN x = 5 THEN 1
                    WHEN x = 6 THEN 5
               ELSE 1000
        END; END;
    $$ LANGUAGE plpgsql;
"""

    if op.get_bind().dialect.name == "postgresql":
        op.execute(status_to_order)
        op.execute(order_to_status)


def downgrade():
    query = """DROP FUNCTION status_to_order (x integer);
		DROP FUNCTION order_to_status (x integer);
		"""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text(query))
