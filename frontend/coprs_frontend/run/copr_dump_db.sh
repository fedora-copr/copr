#!/bin/bash

set -e

if test "$#" -ne 1; then
    echo "Specify dump directory"
    exit 1
fi

dump_dir=$1

(
    runuser -c 'pg_dump --exclude-table-data "*_private" coprdb' - postgres
    cat <<'EOF'
INSERT INTO public.user_private (mail, api_login, api_token, api_token_expiration, user_id)
SELECT '', '', '', '2000-01-01', id FROM public."user";

INSERT INTO public.copr_private (copr_id)
SELECT id FROM public.copr;
EOF
) | runuser -c "gzip > $dump_dir/copr_db-$(date '+%Y-%m-%d_%H-%M').gz" - copr-fe

find "$dump_dir" -name 'copr_db-*.gz' -mtime +1 -delete
