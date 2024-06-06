#! /bin/bash

set -e

args=()

coverage=( --cov-report term-missing --cov bin --cov dist_git_client )
for arg; do
    case $arg in
    --no-coverage) coverage=() ;;
    *) args+=( "$arg" ) ;;
    esac
done

abspath=$(readlink -f .)
export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$abspath"
export PATH=$(readlink -f bin):$PATH
"${PYTHON:-python3}" -m pytest -s tests "${coverage[@]}" "${args[@]}"
