"""fix stored procudure (status order)  bug

Revision ID: 4b57794e2b5
Revises: 19ca0c14096e
Create Date: 2015-11-20 11:57:25.079854

"""

# revision identifiers, used by Alembic.
revision = '4b57794e2b5'
down_revision = '19ca0c14096e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    query_functions = """
CREATE OR REPLACE FUNCTION status_to_order (x integer)
RETURNS integer AS $$ BEGIN
        RETURN CASE WHEN x = 0 THEN 0
                    WHEN x = 3 THEN 1
                    WHEN x = 6 THEN 2
                    WHEN x = 7 THEN 3
                    WHEN x = 4 THEN 4
                    WHEN x = 1 THEN 5
                    WHEN x = 5 THEN 6
                    WHEN x = 2 THEN 7
               ELSE x
        END; END;
    $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION order_to_status (x integer)
RETURNS integer AS $$ BEGIN
        RETURN CASE WHEN x = 0 THEN 0
                    WHEN x = 1 THEN 3
                    WHEN x = 2 THEN 6
                    WHEN x = 3 THEN 7
                    WHEN x = 4 THEN 4
                    WHEN x = 5 THEN 1
                    WHEN x = 6 THEN 5
                    WHEN x = 7 THEN 2
               ELSE x
        END; END;
    $$ LANGUAGE plpgsql;
"""
    op.execute(sa.text(query_functions))


def downgrade():
    query_functions = """
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
    op.execute(sa.text(query_functions))
