#!/bin/sh

path="${1:-tests}"

PYTHONPATH=.:$PYTHONPATH ${PYTHON:-python3} -m pytest -s $path
