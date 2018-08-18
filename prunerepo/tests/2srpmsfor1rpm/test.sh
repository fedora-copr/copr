#!/bin/bash

shopt -s expand_aliases

# repo build dirs:
# 00000003-motionpaint-1.3
# 00000005-motionpaint-1.3
# 00000007-motionpaint-1.4 <- content should stay

export testdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export origrepo=$testdir/repo-template
export testrepo=$testdir/repo-test

source $testdir/../testlib.sh

echo "============================ Test that all srpms get deleted when the same package is present in multiple directories and --days is used ============================";

setup
runcmd --days=1 .

run 'ls 00000003-motionpaint-1.3/*.rpm' && die
run 'ls 00000005-motionpaint-1.3/*.rpm' && die
run 'ls 00000007-motionpaint-1.4/*.rpm' || die
run 'ls 00000007-motionpaint-1.4/*.src.rpm' || die

echo success.

exit 0
