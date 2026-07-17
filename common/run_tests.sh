#!/bin/bash

set -x
set -e

REDIS_PORT=7777
valkey-server --port $REDIS_PORT &> _valkey.log &

cleanup ()
{
    valkey-cli -p "$REDIS_PORT" shutdown
    wait
}
trap cleanup EXIT

COVPARAMS=(--cov-report term-missing --cov ./copr_common/)

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov|--no-cov)
        COVPARAMS=()
        ;;
    *)
        KEEP_ARGS+=("$arg")
        ;;
    esac
done

python3 -B -m pytest "${COVPARAMS[@]}" "${KEEP_ARGS[@]}"
