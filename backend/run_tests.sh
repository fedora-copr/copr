#! /bin/bash

set -x
set -e

REDIS_PORT=7777
redis-server --port $REDIS_PORT &> _redis.log &

cleanup ()
{
    redis-cli -p "$REDIS_PORT" shutdown
    wait
}
trap cleanup EXIT

COVPARAMS='--cov-report term-missing --cov ./backend --cov ./run'

while [[ $# > 1 ]]
do
	key="$1"
	case $key in
		--nocov)
		COVPARAMS=""
		;;
		*) # unknown option
		;;
	esac
shift # past argument or value
done

#TESTS=./tests

# Quick hack to disable tests/daemons/test_backend.py tests/mockremote/test_builder.py
# tests/mockremote/test_mockremote.py that are currently failing due to complete code rewrite
# TODO: prune tests (case-by-case) that are no longer relevant. We mostly rely on
# integration & regression tests now.
TESTS="tests/test_createrepo.py tests/test_frontend.py tests/test_helpers.py tests/test_sign.py tests/vm_manager/test_manager.py tests/test_action.py"

if [[ -n $@ ]]; then
	TESTS=$@
fi

common_path=$(readlink -f ../common)
export PYTHONPATH="$common_path:backend:run${PYTHONPATH+:$PYTHONPATH}$common_path"
python3 -m pytest -s $COVPARAMS $TESTS
