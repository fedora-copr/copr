#! /bin/sh

dir=$(dirname "$(readlink -f "$0")")
export PYTHONPATH=$dir:$dir/../common
cd "$dir"
python3 setup.py bdist_egg
pytest-3
