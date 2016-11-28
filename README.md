# Copr

[**Project Page**](https://fedorahosted.org/copr/) | 
[**Report a Bug**](https://bugzilla.redhat.com/enter_bug.cgi?product=Copr) | 
[**Already reported bugs**](https://bugzilla.redhat.com/buglist.cgi?bug_status=NEW&bug_status=ASSIGNED&bug_status=POST&bug_status=MODIFIED&bug_status=ON_DEV&bug_status=ON_QA&bug_status=VERIFIED&bug_status=RELEASE_PENDING&classification=Community&list_id=4678560&product=Copr&query_format=advanced) |
[**Production Instance**](https://copr.fedoraproject.org) | 
[**Testing Instance**](http://copr-fe-dev.cloud.fedoraproject.org/)

Copr is a Fedora community build service in [Fedora](https://getfedora.org/) that builds your open-source project and creates your own RPM repository.

[See Copr workflow.](https://pagure.io/copr/copr/raw/master/f/doc/img/copr-workflow.png)

## Using Copr
Learn [how to use Copr](https://developer.fedoraproject.org/deployment/copr/about.html) and [how to create RPM packages](https://developer.fedoraproject.org/deployment/rpm/about.html) on the [Fedora Developer Portal](https://developer.fedoraproject.org).

## Status

Copr builds of:

* copr-backend [![build status](https://copr.fedorainfracloud.org/coprs/g/copr/copr/package/copr-backend/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/copr/copr/package/copr-backend/)
* copr-keygen [![build status](https://copr.fedorainfracloud.org/coprs/g/copr/copr/package/copr-keygen/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/copr/copr/package/copr-keygen)
* copr-frontend [![build status](https://copr.fedorainfracloud.org/coprs/g/copr/copr/package/copr-frontend/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/copr/copr/package/copr-frontend/)
* python-copr [![build status](https://copr.fedorainfracloud.org/coprs/g/copr/copr/package/python-copr/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/copr/copr/package/python-copr/)


Documentation of:

* copr-backend [![Documentation Status](https://readthedocs.org/projects/copr-backend/badge/?version=latest)](http://copr-backend.readthedocs.org/?badge=latest)
* copr-keygen [![copr-keygen documentation](https://readthedocs.org/projects/copr-keygen/badge/?version=latest)](http://copr-keygen.readthedocs.org/en/latest/?badge=latest)
* copr-frontend [![Documentation Status](https://readthedocs.org/projects/copr-rest-api/badge/?version=latest)](http://copr-rest-api.readthedocs.org/en/latest/?badge=latest)
* python-copr [![Documentation Status](https://readthedocs.org/projects/python-copr/badge/?version=latest)](http://python-copr.readthedocs.org/en/latest/?badge=latest)

## Local Testing Environment
You can use [Vagrant](https://developer.fedoraproject.org/tools/vagrant/about.html) to run your local test environment. We currently support *frontend* and *dist-git*.

```
$ git clone https://pagure.io/copr/copr.git
$ cd copr
$ vagrant up
```

Good news, everyone! From now on, you can additionally run backend in a docker container. This makes it possible to build a package by using our COPR stack but solely on your machine. Mainly useful for development. Makefile is provided for easy manipulation with the backend Dockerfile and the afterwards created docker image.

```
$ cd copr/backend/docker
$ make build && make run
```

For more information see [our wiki page](https://fedorahosted.org/copr/wiki/Contribute#LocalDevelopmentEnvironment).

[Unreported tracebacks](https://retrace.fedoraproject.org/faf/problems/?component_names=copr-cli%2Cpython-copr) of client tools.
