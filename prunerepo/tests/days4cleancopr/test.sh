#!/bin/bash

shopt -s expand_aliases

# repo build dirs:
# 1-norpmsinside

export testdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export origrepo=$testdir/repo-template
export testrepo=$testdir/repo-test

source $testdir/../testlib.sh

echo "============================ test --cleancopr --days ============================";

setup

touch -d "2 days ago" 1-norpmsinside
runcmd --cleancopr --days 3 .
run "ls -d 1-norpmsinside" || die
runcmd --cleancopr --days 1 .
run "ls -d 1-norpmsinside" && die

echo success.

exit 0
