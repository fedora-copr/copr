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

./build_aux/check-alembic-revisions

COVPARAMS=(--cov-report term-missing --cov run --cov coprs --cov commands)

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov|--no-cov)
        COVPARAMS=()
        ;;
    *)
        KEEP_ARGS+=( "$arg" )
        ;;
    esac
done

common_path=$(readlink -f ../common)
export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$common_path"
export COPR_CONFIG="$(pwd)/coprs_frontend/config/copr_unit_test.conf"

cd coprs_frontend
./manage.py test "${COVPARAMS[@]}" "${KEEP_ARGS[@]}"
