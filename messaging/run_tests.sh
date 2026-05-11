#!/bin/bash

set -e

dir=$(dirname "$(readlink -f "$0")")
export PYTHONPATH=$dir:$dir/../common

cd "$dir"

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov|--no-cov) ;;
    *) KEEP_ARGS+=("$arg") ;;
    esac
done

python3 -m pytest -s copr_messaging/tests "${KEEP_ARGS[@]}"
