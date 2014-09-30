#!/bin/sh

PYTHONPATH=./copr_cli:$PYTHONPATH python -B -m pytest --cov-report term-missing --cov ./copr_cli/ tests
#PYTHONPATH=./src:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./src tests
