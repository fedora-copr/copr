#!/bin/bash

COVPARAMS=(--cov-report term-missing --cov ./copr_common/)

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov|--no-cov)
        COVPARAMS=()
        ;;
    *)
        KEEP_ARGS+=("$arg")
        ;;
    esac
done

python3 -B -m pytest "${COVPARAMS[@]}" "${KEEP_ARGS[@]}"
