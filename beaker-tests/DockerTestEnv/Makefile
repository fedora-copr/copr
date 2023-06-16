.PHONY : build run sh start stop del

mkfile_path:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

CONTAINER_NAME ?= test-env

build:
	docker build -t test-env-image .

bld: build

run:
	docker run \
		-dit \
		-v $(mkfile_path)/../..:/root/copr \
		--name="$(CONTAINER_NAME)" \
		-h $(CONTAINER_NAME) \
		-w /root/ \
		test-env-image

sh:
	docker exec $(CONTAINER_NAME) rm -f /run/nologin
	docker exec -u root -it $(CONTAINER_NAME) script -qc 'bash' /dev/null

start:
	docker start $(CONTAINER_NAME)

stop:
	docker stop $(CONTAINER_NAME)

del:
	docker rm -f $(CONTAINER_NAME)
