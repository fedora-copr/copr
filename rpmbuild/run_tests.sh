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

PYTHONPATH=".:$PYTHONPATH" "${PYTHON:-python3}" -m pytest -s tests "${coverage[@]}" "${args[@]}"
