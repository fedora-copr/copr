#! /bin/sh

exec runuser -u copr-signer -- /usr/bin/gpg-copr "$@"
