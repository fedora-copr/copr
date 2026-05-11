#!/bin/bash

set -e

absdir="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$absdir"

coverage=(
    --cov-report term-missing
    --cov copr/v3
)

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov|--no-cov)
        coverage=()
        ;;
    *)
        KEEP_ARGS+=("$arg")
        ;;
    esac
done

python3 -B -m pytest "${coverage[@]}" copr/test "${KEEP_ARGS[@]}"
