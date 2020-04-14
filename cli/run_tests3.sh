#!/bin/sh

set -e

test -f ../build_aux/linter && {
    echo >&2 "running linter"
    ../build_aux/linter
}

PYTHONPATH=../python/:./copr_cli:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./copr_cli/ $@
