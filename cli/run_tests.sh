#!/bin/bash

COVPARAMS=(--cov-report term-missing --cov ./copr_cli/)

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

PYTHONPATH="../python/:./copr_cli${PYTHONPATH:+:$PYTHONPATH}" python3 -B -m pytest "${COVPARAMS[@]}" "${KEEP_ARGS[@]}"
