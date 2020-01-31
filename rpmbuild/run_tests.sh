#!/bin/sh

PYTHONPATH=".:$PYTHONPATH" "${PYTHON:-python3}" -m pytest -s tests "$@"
