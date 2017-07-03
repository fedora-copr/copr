#! /bin/sh

PYTHONPATH=./src: python2 -B -m pytest --cov-report term-missing --cov ./dist_git tests "$@"
#PYTHONPATH=./src: python2 -B -m pytest --capture=no --cov-report term-missing --cov ./dist_git tests "$@"
