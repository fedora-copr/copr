#!/bin/sh

set -e

PYTHONPATH=".:$PYTHONPATH" "${PYTHON:-python3}" -m pytest -s tests "$@"
