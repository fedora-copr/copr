#!/bin/sh

PYTHONPATH=backend:run:$PYTHONPATH python -B -m pytest -s --cov-report term-missing --cov ./backend ./tests/ $@
#PYTHONPATH=../python/:./copr_cli:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./copr_cli/ $@
