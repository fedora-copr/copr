#!/bin/bash

set -e

absdir="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$absdir"

coverage=(
    --cov-report term-missing
    --cov copr/v3
)
python3 -B -m pytest "${coverage[@]}" copr/test "$@"
