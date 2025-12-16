#!/bin/sh -eux

cd "$(git rev-parse --show-toplevel)"
rpm -qa | grep copr

lscpu || :
lsmem || :
swapon || :
dnf copr list
cat /etc/yum.repos.d/*.repo

./testing-farm/all-on-single-host.sh
