#!/bin/sh

cd coprs_frontend
COPR_CONFIG="$(pwd)/config/copr_unit_test.conf" python -m pytest tests -s $@ # \
     #--cov-report term-missing --cov coprs $@

