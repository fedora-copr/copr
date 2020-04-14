#!/bin/bash

set -e

test -f ../build_aux/linter && {
    echo >&2 "running linter"
    ../build_aux/linter
}

absdir="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$absdir"

python3 -B -m pytest --cov-report term-missing copr/test "$@"
