#!/bin/sh

PYTHONPATH=./src:$PYTHONPATH python -B -m pytest --cov-report term-missing --cov ./src
