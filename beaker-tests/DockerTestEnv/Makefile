.PHONY : build run sh start stop del

mkfile_path:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

build:
	docker build -t test-env-image .

bld: build

run:
	docker run \
		-dit \
		-v $(mkfile_path)/../../../copr:/root/copr \
		--name="test-env" \
		-h test-env \
		-w /root/ \
		test-env-image

sh:
	docker exec test-env rm -f /run/nologin
	docker exec -u root -it test-env script -qc 'bash' /dev/null

start:
	docker start test-env

stop:
	docker stop test-env

del:
	docker rm -f test-env
