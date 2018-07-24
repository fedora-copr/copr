#! /bin/sh

PYTHONPATH=.:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./dist_git tests "$@"
