.PHONY: build run run-local sh start stop del help

mkfile_path:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

CONTAINER_NAME ?= test-env
CONTAINER_ENGINE ?= $(shell command -v podman 2> /dev/null || echo docker)
COPR_NETWORK ?= copr

help:
	@echo "COPR Test Environment"
	@echo ""
	@echo "Targets:"
	@echo "  build       Build test container image"
	@echo "  run         Run container (for staging/remote testing)"
	@echo "  run-local   Run container on copr network (for local deployment testing)"
	@echo "  sh          Open shell in container"
	@echo "  start/stop  Start/stop container"
	@echo "  del         Delete container"
	@echo ""
	@echo "For local deployment testing:"
	@echo "  1. cd ../../deployment && just up"
	@echo "  2. cd ../beaker-tests/DockerTestEnv"
	@echo "  3. make build && make run-local"
	@echo "  4. make sh"
	@echo "  5. Inside container: setup-local-copr"
	@echo ""

build:
	$(CONTAINER_ENGINE) build -t test-env-image .

bld: build

# Standard run - for staging/remote instances
run:
	$(CONTAINER_ENGINE) run \
		-dit \
		-v $(mkfile_path)/../..:/root/copr:z \
		--name="$(CONTAINER_NAME)" \
		-h $(CONTAINER_NAME) \
		-w /root/ \
		test-env-image

# Run on the copr network - for local deployment testing
# Aardvark-dns resolves all service hostnames (frontend, backend-httpd, etc.)
run-local:
	$(CONTAINER_ENGINE) run \
		-dit \
		-v $(mkfile_path)/../..:/root/copr:z \
		--name="$(CONTAINER_NAME)" \
		-h $(CONTAINER_NAME) \
		-w /root/ \
		--network=$(COPR_NETWORK) \
		--no-hosts \
		-e FRONTEND_URL=http://frontend:5000 \
		-e FRONTEND_PUBLIC_HOST=frontend \
		-e BACKEND_URL=http://backend-httpd:5002 \
		-e DISTGIT_URL=http://distgit:5001 \
		-e DNF_COPR_ID=tested-copr \
		test-env-image

sh:
	$(CONTAINER_ENGINE) exec $(CONTAINER_NAME) rm -f /run/nologin
	$(CONTAINER_ENGINE) exec -u root -it $(CONTAINER_NAME) script -qc 'bash' /dev/null

start:
	$(CONTAINER_ENGINE) start $(CONTAINER_NAME)

stop:
	$(CONTAINER_ENGINE) stop $(CONTAINER_NAME)

del:
	$(CONTAINER_ENGINE) rm -f $(CONTAINER_NAME)
