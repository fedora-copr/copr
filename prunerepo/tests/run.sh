#!/bin/bash

export scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

for dir in `ls -d $scriptdir/*/`; do
	$dir/test.sh || exit 1;
done;
