.PHONY: check test lint unittests

# we keep this serialized to avoid messed standard output
check:
	$(MAKE) unittests
	$(MAKE) lint

test: check

unittests:
	./run_tests.sh -vv -s

lint:
	vcs-diff-lint
