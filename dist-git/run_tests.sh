#! /bin/sh

set -x
set -e

common_path=$(readlink -f ../common)
export PYTHONPATH="${PYTHONPATH+$PYTHONPATH:}$common_path"
python3 -m pytest --cov-report term-missing --cov ./dist_git tests "$@"
