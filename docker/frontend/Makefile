build:
	docker build -t copr-frontend-image --build-arg=RELEASETEST="${RELEASETEST}" -f Dockerfile ../../

run:
	docker run --privileged --name="copr-frontend" -dit --net="host" copr-frontend-image

sh:
	docker exec -it copr-frontend bash

start:
	docker start copr-frontend

stop:
	docker stop copr-frontend

del:
	docker rm -f copr-frontend

update: del build run
