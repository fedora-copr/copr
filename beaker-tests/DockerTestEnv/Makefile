.PHONY: build run run-local sh start stop del help

mkfile_path:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

CONTAINER_NAME ?= test-env
CONTAINER_ENGINE ?= $(shell command -v podman 2> /dev/null || echo docker)

help:
	@echo "COPR Test Environment"
	@echo ""
	@echo "Targets:"
	@echo "  build       Build test container image"
	@echo "  run         Run container (for staging/remote testing)"
	@echo "  run-local   Run container with host network (for local podman-kube)"
	@echo "  sh          Open shell in container"
	@echo "  start/stop  Start/stop container"
	@echo "  del         Delete container"
	@echo ""
	@echo "For local podman-kube testing:"
	@echo "  1. make build"
	@echo "  2. make run-local"
	@echo "  3. make sh"
	@echo "  4. Inside container: setup-local-copr"
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

# Run with host network - for local podman-kube testing
# This allows the container to access localhost:5000 etc.
run-local:
	$(CONTAINER_ENGINE) run \
		-dit \
		-v $(mkfile_path)/../..:/root/copr:z \
		--name="$(CONTAINER_NAME)" \
		-h $(CONTAINER_NAME) \
		-w /root/ \
		--network=host \
		--add-host=frontend:127.0.0.1 \
		--add-host=backend-httpd:127.0.0.1 \
		--add-host=distgit:127.0.0.1 \
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
