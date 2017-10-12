build:
	docker build -t copr-database-image --build-arg=RELEASETEST="${RELEASETEST}" -f Dockerfile ../../

run:
	docker run --privileged --name="copr-database" -dit --net="host" copr-database-image

sh:
	docker exec -it copr-database bash

start:
	docker start copr-database

stop:
	docker stop copr-database

del:
	docker rm -f copr-database

update: del build run
