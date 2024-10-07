.PHONY : build run sh start stop del

mkfile_path:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

CONTAINER_NAME ?= test-env
CONTAINER_ENGINE ?= $(shell command -v podman 2> /dev/null || echo docker)

build:
	$(CONTAINER_ENGINE) build -t test-env-image .

bld: build

run:
	$(CONTAINER_ENGINE) run \
		-dit \
		-v $(mkfile_path)/../..:/root/copr:z \
		--name="$(CONTAINER_NAME)" \
		-h $(CONTAINER_NAME) \
		-w /root/ \
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
