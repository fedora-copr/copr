build:
	docker build -t copr-backend-image .

run:
	docker run --privileged --name="copr-backend" -dit --net="host" copr-backend-image

sh:
	docker exec -it copr-backend bash

start:
	docker start copr-backend

stop:
	docker stop copr-backend

del:
	docker rm -f copr-backend

update: del build run
