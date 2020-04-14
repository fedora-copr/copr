#! /bin/sh

set -x
set -e

test -f ../build_aux/linter && {
    echo >&2 "running linter"
    ../build_aux/linter
}

common_path=$(readlink -f ../common)
export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$common_path"
python3 -m pytest --cov-report term-missing --cov ./dist_git tests "$@"
