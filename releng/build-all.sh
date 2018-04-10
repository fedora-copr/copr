#!/bin/bash

pushd `dirname $0`/.. >/dev/null

PROJECT=$1
if [ -z "$PROJECT" ]; then
	echo "usage: build-missing-builds.sh project"
    echo "       where TARGET is either @copr/copr or @copr/copr-dev"
    exit 1
fi

packages="$(find -maxdepth 2 -path '*spec' -exec dirname {} \;)"
for package in $packages; do
    echo "##############################"
    echo "Building $(basename $package):"
    echo "##############################"
	pushd $package > /dev/null
    rpkg build $PROJECT
    popd > /dev/null
done

popd >/dev/null
