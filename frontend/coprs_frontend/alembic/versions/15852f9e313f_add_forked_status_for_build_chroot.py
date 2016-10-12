"""add forked status for build_chroot

Revision ID: 15852f9e313f
Revises: 149da7c4ac2f
Create Date: 2016-10-06 09:07:06.487213

"""

# revision identifiers, used by Alembic.
revision = '15852f9e313f'
down_revision = '149da7c4ac2f'

from alembic import op
import sqlalchemy as sa


def upgrade():
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
               ELSE x
        END; END;
    $$ LANGUAGE plpgsql;
"""
    op.execute(sa.text(query_functions))


def downgrade():
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
               ELSE x
        END; END;
    $$ LANGUAGE plpgsql;
"""
    op.execute(sa.text(query_functions))
