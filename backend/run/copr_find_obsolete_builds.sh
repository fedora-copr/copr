#!/bin/bash

CHROOT_PATH=$1
DAYS=$2

echo "# looking for obsolete files in: " $CHROOT_PATH
if [ -d $CHROOT_PATH ]
then
    cd $CHROOT_PATH

    # query latest (successful) packages
    LATEST_PKGS=$(mktemp)
    ERR_LOG=$(mktemp)
    # "yum clean metadata" does not work on this custom repos
    rm -rf $(find /var/tmp -name query &> /dev/null) &> /dev/null
    rm -rf /var/tmp/createrepo* &> /dev/null
    rm -rf /var/cache/yum/* &> /dev/null

    repoquery --repofrompath=query,$CHROOT_PATH --repoid=query -a --location 2>$ERR_LOG \
        | cut -c8- > $LATEST_PKGS

    # Remove builds older then $DAYS days and which have newer builds available
    for SUCCESS in $(find -name success -mtime +$DAYS); do
        DIR=$(basename $(dirname $SUCCESS))
        echo "# checking dir: " $DIR
        for PACKAGE in $(ls $DIR); do
            grep $PACKAGE $LATEST_PKGS >/dev/null && continue 2
        done
        # package was not found in $LATEST_PKGS
        #rm -rf $DIR
        #echo -n .
        echo $DIR
    done

    rm -f $LATEST_PKGS $ERR_LOG
fi
