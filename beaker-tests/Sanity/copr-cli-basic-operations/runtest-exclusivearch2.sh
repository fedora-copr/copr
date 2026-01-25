#! /bin/bash

# Test the ExcludeArch + ExclusiveArch selection using python3-norpm (behave
# wrapper)

HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

export FRONTEND_URL BACKEND_URL DISTGIT_URL

set -x
cd "$HERE/../../../behave" || exit 1
behave --tags architecture_selection
