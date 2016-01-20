#!/bin/bash

shopt -s expand_aliases

# repo build dirs:
# 1-oldestbuild
# 2-norpmsinside
# 3-secondlatestpkg
# 4-latestpkg

export testdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export origrepo=$testdir/fedora-23-x86_64-template
export testrepo=$testdir/fedora-23-x86_64-test

die() { echo "fail."; exit 1; }

function runcmd {
	bash -c "set -x; ../../prunerepo --quiet $*;"
}

function listpkgsbyrepo {
	dnf --disablerepo="*" repoquery --repofrompath=test_prunerepo,$testrepo --repoid=test_prunerepo --enablerepo=test_prunerepo --refresh --quiet --queryformat '%{location}' | sort
}

function listpkgsbyfs {
	find . -name '*.rpm' | cut -c 3- | sort
}

function run {
	echo '>' $@;
	eval $@;
}

function setup {
	cp -aT $origrepo $testrepo
	cd $testrepo
}

echo "============================ test basic functionality ============================";

setup
runcmd .

run 'ls 0-oldestbuild/*.rpm' && die
run 'ls 1-norpmsinside/*.rpm' && die
run 'ls 2-secondlatestpkg/*.rpm' && die
run '[[ `ls 3-latestpkg/*.rpm | wc -l` == 3 ]]' || die
run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die


echo "============================ test --cleancopr ============================";

setup
runcmd --cleancopr .

run "ls -d 0-oldestbuild" && die
run "ls -d 1-norpmsinside" && die
run "ls -d 2-secondlatestpkg" && die
run "ls -d 3-latestpkg" || die

run "ls build-0.log" && die
run "ls build-1.log" && die
run "ls build-2.log" && die
run "ls build-3.log" || die

echo success.

echo "============================ test --nocreaterepo ============================"; #TODO

setup
runcmd --days 7 .
echo success.

echo "============================ test --days ============================"; #TODO

setup
runcmd --days 7 .
echo success.

echo "============================ test no dnf caching ============================"; #TODO

setup
runcmd .
echo success.

exit 0
