#!/bin/bash

set -e

if test "$#" -ne 1; then
    echo "Specify dump directory"
    exit 1
fi

dump_dir=$1

runuser -c 'pg_dump --exclude-table-data "*_private" coprdb' - postgres \
    | runuser -c "gzip > $dump_dir/copr_db-$(date '+%Y-%m-%d_%H-%M').gz" - copr-fe \

find "$dump_dir" -name 'copr_db-*.gz' -mtime +1 -delete
