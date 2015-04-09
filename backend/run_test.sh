#!/usr/bin/bash

REDIS_PORT=7777

redis-server --port $REDIS_PORT &> _redis.log &


# PYTHONPATH=backend:run:$PYTHONPATH python -B -m pytest -s ./tests/ $@
PYTHONPATH=backend:run:$PYTHONPATH python -B -m pytest -s --cov-report term-missing --cov ./backend --cov ./run ./tests/ $@
# PYTHONPATH=../python/:./copr_cli:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./copr_cli/ $@

kill %1
