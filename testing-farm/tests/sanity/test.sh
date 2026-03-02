#!/bin/sh -eux

cd "$(git rev-parse --show-toplevel)"
rpm -qa | grep copr
rpm -qa | grep dnf

lscpu || :
lsmem || :
swapon || :
dnf copr list
cat /etc/yum.repos.d/*.repo

for i in /etc/yum.repos.d/*.repo; do echo "=== $i ==="; cat "$i" ; done

./testing-farm/all-on-single-host.sh
