#! /bin/bash

set -x
set -e

srcdir=$(dirname "$0")

test_tarball_version=$(grep -E '%global[[:space:]]*tests_version' < "$srcdir"/copr-backend.spec | awk '{ print $3 }')
test_tarball_name=$(grep -E '%global[[:space:]]*tests_tar' < "$srcdir"/copr-backend.spec | awk '{ print $3 }')
test_tarball_extracted=$test_tarball_name-$test_tarball_version
test_tarball=$test_tarball_extracted.tar.gz

test -d "$test_tarball_extracted" || (
    cd "$srcdir" || exit 1
    spectool -S copr-backend.spec --get-files
    tar -xf "$test_tarball"
)
export TEST_DATA_DIRECTORY
TEST_DATA_DIRECTORY=$(readlink -f "$test_tarball_extracted")

REDIS_PORT=7777
redis-server --port $REDIS_PORT &> _redis.log &

cleanup ()
{
    redis-cli -p "$REDIS_PORT" shutdown
    wait
}
trap cleanup EXIT

common_path=$(readlink -f ../common)
messaging_path=$(readlink -f ../messaging)
export PYTHONPATH="$common_path:$messaging_path:$PWD:$PWD/tests:$PWD/run${PYTHONPATH+:$PYTHONPATH}"
export PATH="$PWD/run${PATH+:$PATH}"

COVPARAMS=( --cov-report term-missing --cov ./copr_backend --cov ./run )

KEEP_ARGS=()
for arg; do
    case $arg in
    --nocov|--no-cov)
        COVPARAMS=()
        ;;
    *)
        KEEP_ARGS+=( "$arg" )
        ;;
    esac
done

python3 -m pytest -s tests "${COVPARAMS[@]}" "${KEEP_ARGS[@]}"
