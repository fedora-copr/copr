#!/bin/bash

alias RUNCMD='copr_prune_repo.py'

shopt -s expand_aliases
die() { echo "$@" 1>&2 ; exit 1; }

# repo builds:
# drwxrwxr-x. 2 copr  copr   4096 Jan  1 00:00 1-success1
# drwxrwxr-x. 2 copr  copr   4096 Jan  2 00:00 2-success2
# drwxrwxr-x. 2 clime clime  4096 Jan  3 00:00 3-fail1-baduser
# drwxrwxr-x. 2 copr  copr   4096 Jan  4 00:00 4-fail2
# drwxrwxr-x. 2 copr  copr   4096 Jan  5 00:00 5-success3
# drwxrwxr-x. 2 copr  copr   4096 Jan  6 00:00 6-success4-latestpkg

origrepo=./fedora-23-x86_64-template
testrepo=./fedora-23-x86_64-test
alias lsbuilds="ls -dr $testrepo/1-success1 $testrepo/2-success2 $testrepo/3-fail1-baduser $testrepo/4-fail2 $testrepo/5-success3 $testrepo/6-success4-latestpkg 2> /dev/null"

function setup {
	set +x
	sudo cp -aT $origrepo $testrepo
	i=1
	for b in $(lsbuilds); do
		sudo touch -t $(date "--date=-$i day" +%m%d0000) $b
		i=$((i+1))
	done;
	sudo chown copr:copr $testrepo -R
	sudo chown $(whoami):$(whoami) $testrepo/3-fail1-baduser -R
	set -x
}

# && - expect missing
# || - expect present

set +x; echo "============================ test1 ============================"; set -x;

setup
RUNCMD $testrepo
lsbuilds | grep success1           && exit 1
lsbuilds | grep success2           && exit 1
lsbuilds | grep fail1-baduser      || exit 1
lsbuilds | grep fail2              && exit 1
lsbuilds | grep success3           && exit 1
lsbuilds | grep success4-latestpkg || exit 1

set +x; echo "============================ test2 ============================"; set -x;

setup
RUNCMD --disableusercheck $testrepo
lsbuilds | grep success1           && exit 1
lsbuilds | grep success2           && exit 1
lsbuilds | grep fail1-baduser      && exit 1
lsbuilds | grep fail2              && exit 1
lsbuilds | grep success3           && exit 1
lsbuilds | grep success4-latestpkg || exit 1

set +x; echo "============================ test3 ============================"; set -x;

setup
RUNCMD --disableusercheck --days 6 $testrepo
lsbuilds | grep success1           && exit 1
lsbuilds | grep success2           || exit 1
lsbuilds | grep fail1-baduser      || exit 1
lsbuilds | grep fail2              || exit 1
lsbuilds | grep success3           || exit 1
lsbuilds | grep success4-latestpkg || exit 1

set +x; echo "============================ test4 ============================"; set -x;

setup
RUNCMD --disableusercheck --failed $testrepo
lsbuilds | grep success1           || exit 1
lsbuilds | grep success2           || exit 1
lsbuilds | grep fail1-baduser      && exit 1
lsbuilds | grep fail2              && exit 1
lsbuilds | grep success3           || exit 1
lsbuilds | grep success4-latestpkg || exit 1

set +x; echo "============================ test5 ============================"; set -x;

setup
RUNCMD --disableusercheck --obsolete $testrepo
lsbuilds | grep success1           && exit 1
lsbuilds | grep success2           && exit 1
lsbuilds | grep fail1-baduser      || exit 1
lsbuilds | grep fail2              || exit 1
lsbuilds | grep success3           && exit 1
lsbuilds | grep success4-latestpkg || exit 1

set +x; echo "============================ test6 ============================"; set -x;

setup
find $testrepo | grep success1/build.info | xargs rm
RUNCMD $testrepo
lsbuilds | grep success1           || exit 1
lsbuilds | grep success2           && exit 1
lsbuilds | grep fail1-baduser      || exit 1
lsbuilds | grep fail2              && exit 1
lsbuilds | grep success3           && exit 1
lsbuilds | grep success4-latestpkg || exit 1

exit 0
