#! /bin/bash

set -e

coverage=( --cov-report term-missing --cov bin --cov copr_rpmbuild --cov copr_distgit_client )

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov|--no-cov|--no-coverage) coverage=() ;;
    *) KEEP_ARGS+=( "$arg" ) ;;
    esac
done

abspath=$(readlink -f .)
common_path=$(readlink -f "$abspath"/../common)
export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$common_path:$abspath"
export PATH=$(readlink -f bin):$PATH
"${PYTHON:-python3}" -m pytest -s tests "${coverage[@]}" "${KEEP_ARGS[@]}"
