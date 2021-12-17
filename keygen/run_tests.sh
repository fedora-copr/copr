#!/bin/bash

COVPARAMS=( --cov-report term-missing --cov ./src )

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

PYTHONPATH=./src:$PYTHONPATH python3 -B -m pytest "${COVPARAMS[@]}" tests "${KEEP_ARGS[@]}"
