#!/bin/bash

shopt -s expand_aliases

# repo build dirs:
# 0-oldestbuild
# 1-norpmsinside
# 2-secondlatestpkg
# 3-latestpkg

export testdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export origrepo=$testdir/repo-template
export testrepo=$testdir/repo-test

source $testdir/../testlib.sh

echo "============================ test basic functionality ============================";

setup
runcmd .

run 'ls 0-oldestbuild/*.rpm' && die
run 'ls 1-norpmsinside/*.rpm' && die
run 'ls 2-secondlatestpkg/*.rpm' && die
run '[[ `ls 3-latestpkg/*.rpm | wc -l` == 3 ]]' || die
run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die

echo success.

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

echo "============================ test --days ============================";

setup

oldestbuilddate=`rpm -qp --queryformat '%{BUILDTIME:date}' $testrepo/0-oldestbuild/example-1.0.1-1.fc23.x86_64.rpm 2> /dev/null`
oldestbuilddayback=$(( (`date +'%s'` - `date -d "$oldestbuilddate" +'%s'`)/60/60/24 ))

runcmd --days $oldestbuilddayback .

run 'ls 0-oldestbuild/*.rpm' && die
run '[[ `ls 2-secondlatestpkg/*.rpm | wc -l` == 3 ]]' || die
run '[[ `ls 3-latestpkg/*.rpm | wc -l` == 3 ]]' || die

echo success.

echo "============================ test --nocreaterepo ============================";

setup

repomdlastmodtime1=`stat -c '%Y' $testrepo/repodata/repomd.xml`
run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die

run 'sleep 1'
runcmd --nocreaterepo .

run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' && die
run '[[ $repomdlastmodtime1 == `stat -c '%Y' $testrepo/repodata/repomd.xml` ]]' || die

echo success.

echo "============================ test repo is not recreatered if there was not a change ============================";

setup

repomdlastmodtime1=`stat -c '%Y' $testrepo/repodata/repomd.xml`
run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die

run 'sleep 1'
runcmd --days 999999999 .

run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die
run '[[ $repomdlastmodtime1 == `stat -c '%Y' $testrepo/repodata/repomd.xml` ]]' || die

echo success.

echo "============================ test --alwayscreaterepo ============================";

setup

repomdlastmodtime1=`stat -c '%Y' $testrepo/repodata/repomd.xml`
run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die

run 'sleep 1'
runcmd --alwayscreaterepo --days 999999999 .

run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die
run '[[ $repomdlastmodtime1 < `stat -c '%Y' $testrepo/repodata/repomd.xml` ]]' || die

echo success.

echo "============================ test --nocreaterepo takes precedence over --alwayscreaterepo ============================";

setup

repomdlastmodtime1=`stat -c '%Y' $testrepo/repodata/repomd.xml`
run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die

run 'sleep 1'
runcmd --alwayscreaterepo --nocreaterepo --days 999999999 .

run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' || die
run '[[ $repomdlastmodtime1 < `stat -c '%Y' $testrepo/repodata/repomd.xml` ]]' && die

run 'sleep 1'
runcmd --alwayscreaterepo --nocreaterepo .

run '[[ `listpkgsbyfs` == `listpkgsbyrepo` ]]' && die
run '[[ $repomdlastmodtime1 < `stat -c '%Y' $testrepo/repodata/repomd.xml` ]]' && die

echo success.

echo "============================ test repo data always fresh (no dnf cache used) ============================";

setup

runcmd .

run 'ls 2-secondlatestpkg/*.rpm' && die
run '[[ `ls 3-latestpkg/*.rpm | wc -l` == 3 ]]' || die

setup

run 'rm -r $testrepo/3-latestpkg'
run 'createrepo_c $testrepo'

runcmd .
run '[[ `ls 2-secondlatestpkg/*.rpm | wc -l` == 3 ]]' || die

echo success.

exit 0
