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

unittest-in-container:
	podman build -f ../build_aux/Containerfile.unittest . -t copr_test_image
	podman run --rm -it copr_test_image /bin/sh -c "./run_tests.sh -vv -s"
	podman image rm copr_test_image
