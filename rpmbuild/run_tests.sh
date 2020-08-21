#! /bin/bash

set -e

args=()

coverage=( --cov-report term-missing --cov bin --cov copr_rpmbuild --cov copr_distgit_client )
for arg; do
    case $arg in
    --no-coverage) coverage=() ;;
    *) args+=( "$arg" ) ;;
    esac
done

abspath=$(readlink -f .)
common_path=$(readlink -f "$abspath"/../common)
export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$common_path:$abspath"
export PATH=$(readlink -f bin):$PATH
"${PYTHON:-python3}" -m pytest -s tests "${coverage[@]}" "${args[@]}"
