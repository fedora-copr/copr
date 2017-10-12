build:
	docker build -t copr-distgit-image --build-arg=RELEASETEST="${RELEASETEST}" -f Dockerfile ../../

run:
	docker run --privileged --name="copr-distgit" -dit --net="host" copr-distgit-image

sh:
	docker exec -it copr-distgit bash

start:
	docker start copr-distgit

stop:
	docker stop copr-distgit

del:
	docker rm -f copr-distgit

update: del build run
