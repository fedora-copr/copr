#!/bin/sh

set -e

test -f ../build_aux/linter && {
    echo >&2 "running linter"
    ../build_aux/linter
}

PYTHONPATH=./src:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./src tests
