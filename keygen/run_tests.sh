#!/bin/sh

PYTHONPATH=./src:$PYTHONPATH python3 -B -m pytest --cov-report term-missing --cov ./src tests
