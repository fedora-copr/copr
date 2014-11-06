#!/bin/bash

REPOPATH=$1
DAYS=$2


pushd $REPOPATH >/dev/null


for CHROOT in $(ls $REPOPATH); do
    pushd $CHROOT >/dev/null

    # remove old failed builds
    for FAILED in $(find -name 'fail' -mtime +$DAYS); do
        rm -rf $(dirname $FAILED)
        echo -n .
    done

    # query latest (sucessfull) packages
    LATEST_PKGS=$(mktemp)
    ERR_LOG=$(mktemp)
    # "yum clean metadata" does not work on this custom repos
    rm -rf $(find /var/tmp -name query &> /dev/null) &> /dev/null
    rm -rf /var/tmp/createrepo* &> /dev/null
    rm -rf /var/cache/yum/* &> /dev/null

    repoquery --repofrompath=query,$REPOPATH/$CHROOT --repoid=query -a --location 2>$ERR_LOG \
        | cut -c8- > $LATEST_PKGS

    # remove directory if it does not have repodata at all
    if  $(grep --quiet 'Cannot retrieve repository metadata' $ERR_LOG) || $(grep --quiet "Can't download or revert repomd.xml" $ERR_LOG) ; then
        # don't remove when /devel presents
        if [ ! -d $REPOPATH/$CHROOT/devel ]; then
            rm -rf $REPOPATH/$CHROOT/
        fi
    else
        # Remove builds older then $DAYS days and which have newer builds available
        for SUCCESS in $(find -name success -mtime +$DAYS); do
            DIR=$(basename $(dirname $SUCCESS))
            for PACKAGE in $(ls $DIR); do
                grep $PACKAGE $LATEST_PKGS >/dev/null && continue 2
            done
            # package was not found in $LATEST_PKGS
            rm -rf $DIR
            echo -n .
        done
    fi

    rm -f $LATEST_PKGS $ERR_LOG
    popd >/dev/null
done
popd >/dev/null
