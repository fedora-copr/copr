#!/bin/bash

pushd `dirname $0`/.. >/dev/null
PROJECT=$1
if [ -z "$PROJECT" ]; then
	echo "usage: build-missing-builds.sh TARGET"
    echo "       where TARGET is either @copr or @copr-dev"
    exit 1
fi

for package in $(cat .tito/packages/*| cut -d' ' -f2); do
	pushd $package
    tito release $PROJECT
done

popd >/dev/null
