#!/bin/bash

absdir="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$absdir"

python3 -B -m pytest --cov-report term-missing copr/test "$@"
