COPR_TEST_IMAGE ?= copr_test_image
CONTAINER_ENGINE ?= $(shell command -v podman 2> /dev/null || echo docker)

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

build-test-image:
	$(CONTAINER_ENGINE) build -f ../build_aux/Containerfile.unittest . -t $(COPR_TEST_IMAGE)

enter-test-image:
	$(CONTAINER_ENGINE) run -v .:/home/copr_user/copr_bind:Z -ti $(COPR_TEST_IMAGE) /bin/bash

unittest-in-container:
	$(CONTAINER_ENGINE) run --rm -v .:/home/copr_user/copr_bind:Z \
		-it $(COPR_TEST_IMAGE) /bin/sh -c "./run_tests.sh -vvv -s --no-coverage"
