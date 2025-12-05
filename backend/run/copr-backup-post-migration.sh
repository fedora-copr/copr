#! /bin/bash

set -ex
shopt -s nullglob

SRCDIR=/var/lib/copr/public_html/results
DESTDIR=/pulp-move-safetybelt/results

BASE_DIR_NAME="$1"  # e.g. @copr/copr-pull-requests

cd "$SRCDIR"

# source_file is like: @copr/copr-pull-requests:pr:123/fedora-rawhide-x86_64/0000001-foo/bar.rpm
find "$BASE_DIR_NAME" "$BASE_DIR_NAME":* -type f -name "*.rpm" | while IFS= read -r source_file; do
    # getting relative directory name of the found file
    # example found: @copr/copr-pull-requests:pr:123/fedora-rawhide-x86_64/0000001-foo
    reldir=$(dirname "$source_file")
    # absolute TARGET directory, create it
    destdir=$DESTDIR/$reldir
    mkdir -p "$destdir"
    cp -a "$source_file" "$destdir"
done
