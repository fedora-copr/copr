#! /bin/bash

set -e

test -f ../build_aux/linter && {
    echo >&2 "running linter"
    ../build_aux/linter
}
