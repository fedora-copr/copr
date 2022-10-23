#! /bin/sh

set -e

dir=$(dirname "$(readlink -f "$0")")
export PYTHONPATH=$dir:$dir/../common

cd "$dir"
python3 -m pytest -s copr_messaging/tests
