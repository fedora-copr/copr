# COPR

[**Project Page**](https://pagure.io/copr/copr) |
[**Documentation**](https://docs.pagure.org/copr.copr/) |
[**Report a Bug**](https://bugzilla.redhat.com/enter_bug.cgi?product=Copr) |
[**Already reported bugs**](https://bugzilla.redhat.com/buglist.cgi?bug_status=NEW&bug_status=ASSIGNED&bug_status=POST&bug_status=MODIFIED&bug_status=ON_DEV&bug_status=ON_QA&bug_status=VERIFIED&bug_status=RELEASE_PENDING&classification=Community&list_id=4678560&product=Copr&query_format=advanced) |
[**Fedora COPR**](https://copr.fedoraproject.org)

COPR is a community projects build service that builds your open-source project and creates your own RPM repository. See it in action [here](https://copr.fedoraproject.org).

![See COPR workflow](/copr/copr/raw/master/f/doc/img/copr-workflow.png)

## Using COPR
Learn [how to use COPR](https://developer.fedoraproject.org/deployment/copr/about.html) and [how to create RPM packages](https://developer.fedoraproject.org/deployment/rpm/about.html) on the [Fedora Developer Portal](https://developer.fedoraproject.org).

## Status

Fedora COPR builds of:

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
You can use [Docker](https://docs.docker.com/) to run your local test environment. You need to install `docker-compose` tool for this to work.

```
$ git clone https://pagure.io/copr/copr.git
$ cd copr
$ docker-compose up -d
```

For more information see [our wiki page](https://docs.pagure.org/copr.copr/contribute.html?highlight=contribute).

[Unreported tracebacks](https://retrace.fedoraproject.org/faf/problems/?component_names=copr-cli%2Cpython-copr) of client tools.
