AP := ansible-playbook -vv -c local -i localhost,

deploy:
	$(AP) deploy.yml

images:
	podman login quay.io
	podman build -t quay.io/copr/frontend:test ../docker/frontend/
	podman push quay.io/copr/frontend:test
	podman build -t quay.io/copr/backend:test ../docker/backend/
	podman push quay.io/copr/backend:test
	podman build -t quay.io/copr/backend-httpd:test ../docker/backend_httpd/
	podman push quay.io/copr/backend-httpd:test
	podman build -t quay.io/copr/distgit:test ../docker/distgit/
	podman push quay.io/copr/distgit:test
	podman build -t quay.io/copr/keygen:test ../docker/keygen/
	podman push quay.io/copr/keygen:test
	podman build -t quay.io/copr/resalloc:test ../docker/resalloc/
	podman push quay.io/copr/resalloc:test
