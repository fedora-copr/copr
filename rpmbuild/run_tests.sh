#!/bin/sh

set -e

test -f ../build_aux/linter && {
    echo >&2 "running linter"
    ../build_aux/linter
}

PYTHONPATH=".:$PYTHONPATH" "${PYTHON:-python3}" -m pytest -s tests "$@"
