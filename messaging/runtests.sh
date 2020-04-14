#! /bin/sh

set -e

test -f ../build_aux/linter && {
    echo >&2 "running linter"
    ../build_aux/linter
}

dir=$(dirname "$(readlink -f "$0")")
export PYTHONPATH=$dir:$dir/../common

cd "$dir"
python3 -m pytest -s copr_messaging/tests
