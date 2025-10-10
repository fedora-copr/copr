#!/bin/sh -eux

cd "$(git rev-parse --show-toplevel)"

# Note:
# https://gitlab.com/testing-farm/tests/-/issues/2
packages=$(PYTHON_PKG_SUFFIX=3 ./releng/detect-changed-packages "$PACKIT_TARGET_SHA")
./releng/install-copr-packages "@copr/copr-pull-requests:pr:$PACKIT_PR_ID" "$PACKIT_COMMIT_SHA" $packages
