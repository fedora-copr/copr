#! /bin/bash

python3 -B -m pytest --cov-report term-missing --cov ./copr_common/ $@
