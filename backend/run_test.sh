#!/usr/bin/bash

REDIS_PORT=7777

redis-server --port $REDIS_PORT &> _redis.log &

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

TESTS=./tests
if [[ -n $@ ]]; then
	TESTS=$@
fi

PYTHONPATH=backend:run:$PYTHONPATH python -B -m pytest -s $COVPARAMS $TESTS

kill %1
