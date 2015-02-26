#!/bin/sh

# PYTHONPATH=backend:run:$PYTHONPATH python -B -m pytest -s ./tests/ $@
PYTHONPATH=backend:run:$PYTHONPATH python -B -m pytest -s --cov-report term-missing --cov ./backend --cov ./run ./tests/ $@
# PYTHONPATH=../python/:./copr_cli:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./copr_cli/ $@
