#!/bin/bash
# Initialize PostgreSQL database for COPR

set -e

PGDATA=${PGDATA:-/var/lib/pgsql/data}
POSTGRESQL_USER=${POSTGRESQL_USER:-copr-fe}
POSTGRESQL_PASSWORD=${POSTGRESQL_PASSWORD:-coprpass}
POSTGRESQL_DATABASE=${POSTGRESQL_DATABASE:-coprdb}

# Check if we have existing data
if [ -f "$PGDATA/PG_VERSION" ]; then
    echo "Existing PostgreSQL data found."
    EXISTING_VERSION=$(cat "$PGDATA/PG_VERSION")
    CURRENT_VERSION=$(postgres --version | grep -oP '\d+' | head -1)

    if [ "$EXISTING_VERSION" != "$CURRENT_VERSION" ]; then
        echo "WARNING: Data version ($EXISTING_VERSION) doesn't match PostgreSQL version ($CURRENT_VERSION)"
        echo "Cleaning old data and reinitializing..."
        rm -rf "$PGDATA"/*
    else
        echo "Data version matches. Starting PostgreSQL..."
        exec postgres -D "$PGDATA"
    fi
fi

# Initialize database
echo "Initializing PostgreSQL database..."
initdb -D "$PGDATA"

cat > "$PGDATA/pg_hba.conf" << 'EOF'
# COPR database access
local coprdb copr-fe md5
host  coprdb copr-fe 0.0.0.0/0 md5
host  coprdb copr-fe ::0/0 md5
local coprdb postgres ident

# Default entries
local all all peer
host  all all 127.0.0.1/32 ident
host  all all ::1/128 ident
EOF

# Configure postgresql.conf with tuning from ansible
cat >> "$PGDATA/postgresql.conf" << 'EOF'
listen_addresses = '*'
shared_buffers = 256MB
effective_cache_size = 512MB
work_mem = 4MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
log_min_duration_statement = 500
max_connections = 100
EOF

pg_ctl -D "$PGDATA" -w start

# Create user and database
psql -c "CREATE USER \"$POSTGRESQL_USER\" WITH PASSWORD '$POSTGRESQL_PASSWORD';"
psql -c "CREATE DATABASE \"$POSTGRESQL_DATABASE\" OWNER \"$POSTGRESQL_USER\" ENCODING 'UTF-8';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE \"$POSTGRESQL_DATABASE\" TO \"$POSTGRESQL_USER\";"
# Grant SUPERUSER for alembic migrations
psql -c "ALTER USER \"$POSTGRESQL_USER\" WITH SUPERUSER;"

pg_ctl -D "$PGDATA" -w stop

echo "Database initialized successfully."

exec postgres -D "$PGDATA"
