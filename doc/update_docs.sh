#!/bin/bash

make html

git clone "ssh://git@pagure.io/docs/copr-docs.git"
cp -r _build/html/* copr-docs/
(
    cd copr-docs
    git add .
    git commit -av
    git push
)

rm -rf _build
rm -rf copr-docs
