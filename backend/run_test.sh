#!/bin/sh

PYTHONPATH=.:$PYTHONPATH python -B -m pytest -s --cov-report term-missing --cov ./backend/actions.py ./tests/ $@
#PYTHONPATH=../python/:./copr_cli:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./copr_cli/ $@
