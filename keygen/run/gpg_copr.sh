#!/bin/bash

# TODO: implement this in python, and use app.config for --homedir, etc.
runuser -u copr-signer \
    /usr/bin/gpg2 -- --homedir /var/lib/copr-keygen/gnupg --no-auto-check-trustdb "$@"
