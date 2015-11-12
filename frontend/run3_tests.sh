#!/bin/sh

REDIS_PORT=7777

redis-server --port $REDIS_PORT &> _redis.log &


cd coprs_frontend
COPR_CONFIG="$(pwd)/config/copr_unit_test.conf" python3 -m pytest tests -s $@ # \
     #--cov-report term-missing --cov coprs $@

kill %1
