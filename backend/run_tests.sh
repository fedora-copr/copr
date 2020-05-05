#! /bin/bash

set -x
set -e

REDIS_PORT=7777
redis-server --port $REDIS_PORT &> _redis.log &

cleanup ()
{
    redis-cli -p "$REDIS_PORT" shutdown
    wait
}
trap cleanup EXIT

common_path=$(readlink -f ../common)
export PYTHONPATH="$common_path:tests:run${PYTHONPATH+:$PYTHONPATH}"

COVPARAMS='--cov-report term-missing --cov ./copr_backend --cov ./run'

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov)
        COVPARAMS=""
        ;;
    *)
        KEEP_ARGS+=( "$arg" )
        ;;
    esac
done

python3 -m pytest -s tests $COVPARAMS "${KEEP_ARGS[@]}"
