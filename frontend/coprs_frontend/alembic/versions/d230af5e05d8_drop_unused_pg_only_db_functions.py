"""
drop unused PG-only DB functions

Revision ID: d230af5e05d8
Revises: 4ed794df3bbb
Create Date: 2020-01-07 20:42:39.467075
"""

import sqlalchemy as sa
from alembic import op


revision = 'd230af5e05d8'
down_revision = 'a8ef299dcac8'

def upgrade():
    query_functions = """
    DROP FUNCTION status_to_order;
    DROP FUNCTION order_to_status;
    """
    op.execute(sa.text(query_functions))

def downgrade():
    # copy from 465202bfb9ce_update_db_functions.py
    query_functions = """
CREATE OR REPLACE FUNCTION status_to_order (x integer)
RETURNS integer AS $$ BEGIN
        RETURN CASE WHEN x = 3 THEN 1
                    WHEN x = 6 THEN 2
                    WHEN x = 7 THEN 3
                    WHEN x = 4 THEN 4
                    WHEN x = 0 THEN 5
                    WHEN x = 1 THEN 6
                    WHEN x = 5 THEN 7
                    WHEN x = 2 THEN 8
                    WHEN x = 8 THEN 9
                    WHEN x = 9 THEN 10
               ELSE x
        END; END;
    $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION order_to_status (x integer)
RETURNS integer AS $$ BEGIN
        RETURN CASE WHEN x = 1 THEN 3
                    WHEN x = 2 THEN 6
                    WHEN x = 3 THEN 7
                    WHEN x = 4 THEN 4
                    WHEN x = 5 THEN 0
                    WHEN x = 6 THEN 1
                    WHEN x = 7 THEN 5
                    WHEN x = 8 THEN 2
                    WHEN x = 9 THEN 8
                    WHEN x = 10 THEN 9
               ELSE x
        END; END;
    $$ LANGUAGE plpgsql;
    """
    op.execute(sa.text(query_functions))
