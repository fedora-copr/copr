.PHONY: build run run-local-kube run-local-openshift sh start stop del help

mkfile_path:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

CONTAINER_NAME ?= test-env
CONTAINER_ENGINE ?= $(shell command -v podman 2> /dev/null || echo docker)
COPR_NETWORK ?= copr

help:
	@echo "COPR Test Environment"
	@echo ""
	@echo "Targets:"
	@echo "  build              Build test container image"
	@echo "  run                Run container (for staging/remote testing)"
	@echo "  run-local-kube     Run container for podman kube play testing"
	@echo "  run-local-openshift  Run container for local OpenShift/CRC testing"
	@echo "  sh                 Open shell in container"
	@echo "  start/stop         Start/stop container"
	@echo "  del                Delete container"
	@echo ""
	@echo "For podman kube play testing:"
	@echo "  1. cd ../../kube-deploy && just up"
	@echo "  2. cd ../beaker-tests/DockerTestEnv"
	@echo "  3. make build && make run-local-kube"
	@echo "  4. make sh"
	@echo "  5. Inside container: setup-local-copr local-kube --auto-token"
	@echo ""

build:
	$(CONTAINER_ENGINE) build -t test-env-image .

bld: build

_run:
	$(CONTAINER_ENGINE) run \
		-dit \
		-v $(mkfile_path)/../..:/root/copr:z \
		--name="$(CONTAINER_NAME)" \
		-h $(CONTAINER_NAME) \
		-w /root/ \
		$(RUN_ARGS) \
		test-env-image

# Standard run - for staging/remote instances
run: RUN_ARGS=
run: _run

# Run on the copr podman network - for podman kube play testing
# Aardvark-dns resolves all service hostnames (frontend, backend-httpd, etc.)
run-local-kube: RUN_ARGS=\
	--network=$(COPR_NETWORK) \
	--no-hosts \
	-e FRONTEND_URL=http://frontend:5000 \
	-e FRONTEND_PUBLIC_HOST=frontend \
	-e BACKEND_URL=http://backend-httpd:5002 \
	-e DISTGIT_URL=http://distgit:5001 \
	-e DNF_COPR_ID=tested-copr
run-local-kube: _run

# Run for local OpenShift/CRC testing - uses host network to reach *.apps.crc.testing
run-local-openshift: RUN_ARGS=\
	--network=host \
	-e FRONTEND_URL=http://copr-frontend-copr.apps.crc.testing \
	-e FRONTEND_PUBLIC_HOST=copr-frontend-copr.apps.crc.testing \
	-e BACKEND_URL=http://copr-backend-copr.apps.crc.testing \
	-e DISTGIT_URL=http://copr-distgit-copr.apps.crc.testing \
	-e DNF_COPR_ID=tested-copr \
	-e PULP_CONTENT_URL= \
	-e OWNER=jdoe \
	-e "VENDOR=Fedora Copr (devel) - user jdoe"
run-local-openshift: _run

sh:
	$(CONTAINER_ENGINE) exec $(CONTAINER_NAME) rm -f /run/nologin
	$(CONTAINER_ENGINE) exec -u root -it $(CONTAINER_NAME) script -qc 'bash' /dev/null

start:
	$(CONTAINER_ENGINE) start $(CONTAINER_NAME)

stop:
	$(CONTAINER_ENGINE) stop $(CONTAINER_NAME)

del:
	$(CONTAINER_ENGINE) rm -f $(CONTAINER_NAME)
