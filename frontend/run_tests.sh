#!/bin/sh

REDIS_PORT=7777

redis-server --port $REDIS_PORT &> _redis.log &

path="${1:-tests}"

cd coprs_frontend
COPR_CONFIG="$(pwd)/config/copr_unit_test.conf" python3 -B -m pytest -s $path # \
     #--cov-report term-missing --cov coprs $@

kill %1
