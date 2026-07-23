#! /bin/sh

set -x
set -e

common_path=$(readlink -f ../common)
export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$common_path"

REDIS_PORT=7777
redis-server --port $REDIS_PORT &> _redis.log &

cleanup ()
{
    redis-cli -p "$REDIS_PORT" shutdown
    wait
}
trap cleanup EXIT

COVPARAMS=( --cov-report term-missing --cov ./dist_git )

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

python3 -m pytest "${COVPARAMS[@]}" tests "${KEEP_ARGS[@]}"
