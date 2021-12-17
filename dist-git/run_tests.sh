#! /bin/sh

set -x
set -e

common_path=$(readlink -f ../common)
export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$common_path"

COVPARAMS=( --cov-report term-missing --cov ./dist_git )

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov|--no-cov)
        COVPARAMS=()
        ;;
    *)
        KEEP_ARGS+=( "$arg" )
        ;;
    esac
done

python3 -m pytest "${COVPARAMS[@]}" tests "${KEEP_ARGS[@]}"
