#!/bin/bash
#python -B -m pytest --cov-report term-missing --cov ./copr_cli/ tests $@

PYTHONPATH=.:$PYTHONPATH python -B -m pytest --cov-report term-missing --cov ./copr/client_v2/ -s $@
