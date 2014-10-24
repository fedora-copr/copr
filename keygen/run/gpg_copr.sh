#!/bin/bash

runuser -u copr-signer  /usr/bin/gpg2 -- --homedir /var/lib/copr-keygen/gnupg --no-auto-check-trustdb  $@
