#!/bin/bash
#python -B -m pytest --cov-report term-missing --cov ./copr_cli/ tests $@

python -B -m pytest --cov-report term-missing --cov ./copr/test -s $@
