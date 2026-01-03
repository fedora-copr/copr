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

# Configure PostgreSQL to accept connections
echo "host all all 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"
echo "listen_addresses = '*'" >> "$PGDATA/postgresql.conf"

# Start PostgreSQL temporarily to create user and database
pg_ctl -D "$PGDATA" -w start

# Create user and database
psql -c "CREATE USER \"$POSTGRESQL_USER\" WITH PASSWORD '$POSTGRESQL_PASSWORD';"
psql -c "CREATE DATABASE \"$POSTGRESQL_DATABASE\" OWNER \"$POSTGRESQL_USER\";"
psql -c "GRANT ALL PRIVILEGES ON DATABASE \"$POSTGRESQL_DATABASE\" TO \"$POSTGRESQL_USER\";"

# Stop temporary instance
pg_ctl -D "$PGDATA" -w stop

echo "Database initialized successfully."

# Start PostgreSQL
echo "Starting PostgreSQL..."
exec postgres -D "$PGDATA"
