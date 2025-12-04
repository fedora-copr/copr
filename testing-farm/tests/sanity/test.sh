#!/bin/sh -eux

cd "$(git rev-parse --show-toplevel)"
rpm -qa | grep copr
