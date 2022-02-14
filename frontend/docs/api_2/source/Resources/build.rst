Build
=====

Build resource allows to submit new builds and access current build progress.

In fact, build consists of a few tasks, one per chroot, and detailed information
is available through resource :doc:`./build_task`.



Structure of the build entity
-----------------------------

.. code-block:: javascript

    {
        "enable_net": true,
        "source_metadata": {
            "tmp": "tmpUNPJWO",
            "pkg": "python-marshmallow-2.0.0b5-1.fc22.src.rpm"
        },
        "submitted_on": 1440753750,
        "repos": [],
        "built_packages": [
            {
                "version": "2.0.0b5",
                "name": "python3-marshmallow"
            },
            {
                "version": "2.0.0b5",
                "name": "python-marshmallow"
            }
        ],
        "started_on": null,
        "source_type": "srpm_upload",
        "state": "succeeded",
        "ended_on": 1440754058,
        "package_version": "2.0.0b5-1.fc22",
        "package_name": "python-marshmallow",
        "id": 106882,
        "submitter": "asamalik"
    }


Build fields
~~~~~~~~~~~~
==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
id                  int                  unique build identifier
state               string               current state of the build, value is aggregated from build tasks
submitted_on        int(unixtime UTC)    time of the build submission
started_on          int(unixtime UTC)    time when the first build task started, otherwise ``null``
ended_on            int(unixtime UTC)    time when the last build task ended, otherwise ``null``
source_type         string               method used for build creation
source_metadata     json object          build source information
package_version     string               version of the source package
package_name        string               name of the source package
enable_net          bool                 defines if network is available during the build
repos               list of string       list of additional repositories enabled during the build
built_packages      list of hash maps    list of the built packages, each hash map has two keys: ``name`` and ``version``
submitter           string               name of the user who submitted the build
==================  ==================== ===============

.. note::
    Only the ``state`` field is editable by the PUT method.
    All other fields are read-only.
    There is a different structure used for build creation, see details at `Submit new build`_.


List builds
-----------
.. http:post:: /api_2/builds

    Returns a list of builds according to the given query parameters.

    :query str owner: select only builds from projects owned by this user
    :query str project_id: select only projects owned by this project
    :query int offset: offset number, default value is 0
    :query int limit: limit number between 1 and 100, default value is 100

    :statuscode 200: no error

    **Example request**:

    .. sourcecode:: http

        GET /api_2/builds?project_id=3985&limit=1 HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "_links": {
            "self": {
              "href": "/api_2/builds?project_id=3985&limit=1"
            }
          },
          "builds": [
            {
              "_links": {
                "project": {
                  "href": "/api_2/projects/3985"
                },
                "self": {
                  "href": "/api_2/builds/106897"
                },
                "build_tasks": {
                  "href": "/api_2/build_tasks?build_id=106897"
                }
              },
              "build": {
                "enable_net": true,
                "source_metadata": {
                  "url": "http://miroslav.suchy.cz/copr/copr-ping-1-1.fc20.src.rpm"
                },
                "package_name": "copr-ping",
                "submitted_on": 1441366834,
                "package_version": "1-1.fc20",
                "built_packages": [
                  {
                    "version": "1",
                    "name": "copr-ping"
                  }
                ],
                "started_on": null,
                "source_type": "srpm_link",
                "state": "succeeded",
                "ended_on": 1441366969,
                "id": 106897,
                "repos": [],
                "submitter": "asamalik"
              }
            }
          ]
        }


Submit new build
----------------
**REQUIRES AUTH**

There are more ways to submit new build. Copr services currently provides the following options for build submission:

From SRPM URL
~~~~~~~~~~~~~
    .. code-block:: javascript

        {
            "project_id": 3985,
            "chroots": ["fedora-22-i386", "fedora-21-i386"],
            "srpm_url": "http://miroslav.suchy.cz/copr/copr-ping-1-1.fc20.src.rpm"
        }


    ==================  ==================== ===============
    Field               Type                 Description
    ==================  ==================== ===============
    project_id          int                  identifier of the parent project
    chroots             list of strings      which chroots should be used for build
    srpm_url            string(URL)          URL to the publicly available source package
    enable_net          bool                 allows to disable network access during the build, default: True
    ==================  ==================== ===============

.. http:post:: /api_2/builds

    :reqheader Content-Type: MUST be a ``application/json``

    :resheader Location: contains URL to the submitted build

    :statuscode 201: build was successfully submitted
    :statuscode 400: user data doesn't satisfy some requirements
    :statuscode 403: authorization failed


    **Example request**:

    .. sourcecode:: http

        POST /api_2/builds HTTP/1.1
        Host: copr.fedoraproject.org
        Authorization: Basic base64=encoded=string
        Content-Type: application/json

        {
            "project_id": 3985,
            "chroots": ["fedora-22-i386", "fedora-21-i386"],
            "srpm_url": "http://miroslav.suchy.cz/copr/copr-ping-1-1.fc20.src.rpm"
        }

    **Response**:

    .. sourcecode:: http

        HTTP/1.1 201 CREATED
        Location: /api_2/builds/106897

Using SRPM file upload
~~~~~~~~~~~~~~~~~~~~~~
To upload source package you MUST use ``multipart/form-data`` content type.
An additional build information MUST be present in ``metadata`` part in JSON format. Source package
MUST be uploaded as binary  ``srpm`` file.


    ****

    .. code-block:: javascript

        {
            "project_id": 3985,
            "chroots": ["fedora-22-i386", "fedora-21-i386"],
            "enable_net": false
        }

    ==================  ==================== ===============
    Field               Type                 Description
    ==================  ==================== ===============
    project_id          int                  identifier of the parent project
    chroots             list of strings      which chroots should be used for build
    enable_net          bool                 allows to disable network access during the build, default: True
    ==================  ==================== ===============


.. http:post:: /api_2/builds

    :reqheader Content-Type: MUST be a ``multipart/form-data``
    :formparam metadata: JSON with the build info, MUST have a content type ``application/json``
    :formparam srpm: file with source package, MUST have a content type ``application/x-rpm``

    :resheader Location: contains URL to the created build

    :statuscode 201: build was successfully submitted
    :statuscode 400: user data doesn't satisfy some requirements
    :statuscode 403: authorization failed

    .. note::  Using a ``multipart/form-data`` might not be nice to read. To make your life a bit brighter, a Python example is included below.

    **Example request**:

    .. sourcecode:: http

        POST /api_2/builds HTTP/1.1
        Host: copr.fedoraproject.org
        Authorization: Basic base64=encoded=string
        Content-Length: xxxx
        Content-Type: multipart/form-data; boundary=--------------------31063722920652

        ------------------------------31063722920652
        Content-Disposition: form-data; name="metadata"
        Content-Type: application/json

        {
            "project_id": 3985,
            "chroots": ["fedora-22-i386", "fedora-21-i386"],
            "enable_net": false
        }

        ------------------------------31063722920652
        Content-Disposition: form-data; name="srpm"; filename="package-2.6-fc21.src.rpm"
        Content-Type: application/x-rpm

        << SRPM BINARY CONTENT HERE >>

        -----------------------------31063722920652--


    **Response**:

    .. sourcecode:: http

        HTTP/1.1 201 CREATED
        Location: /api_2/builds/106897
        

    **Python Example**:

    Here we use python-requests_ lib:

    .. code-block:: python

        >>> import json
        >>> from requests import post
        >>> api_url = "http://copr.stg.fedoraproject.org/api_2/builds"
        >>> api_login = "my api login"
        >>> api_token = "my api token"
        >>> metadata = {
        >>>     'chroots': ['fedora-22-i386', 'fedora-21-i386'],
        >>>     'project_id': 3985,
        >>> }
        >>> files = {
        >>>     "srpm": ('pkg.src.rpm', open('/path/to/pkg.src.rpm'), 'application/x-rpm'),
        >>> }
        >>> data = {
        >>>     "metadata": (json.dumps(metadata), 'application/json'),
        >>> }
        >>> r = post(api_url, auth=(api_login, api_token), files=files, data=data)
        >>> r.status_code
        201
        >>> r.headers["Location"]
        http://copr.stg.fedoraproject.org/api_2/builds/106899

Get build details
-----------------

.. http:get:: /api_2/builds/(int:build_id)

    Returns details about build

    :param int build_id: a unique identifier of the build
    :query bool show_build_tasks: embed :doc:`./build_task` sub-resources into the result, default is False

    :statuscode 200: no error
    :statuscode 404: build not found

    **Example request**

    .. sourcecode:: http

        GET /api_2/builds/106897?show_build_tasks=True HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "build_tasks": [
            {
              "tasks": {
                "build_id": 3985,
                "chroot_name": "fedora-21-i386",
                "started_on": 1441366860,
                "state": "succeeded",
                "ended_on": 1441366969,
                "result_dir_url": "http://copr-be-dev.cloud.fedoraproject.org/results/vgologuz/aeghqawgt/fedora-21-i386/00106897-copr-ping",
                "git_hash": "8daed2e23140243d8beaafb0fee436c1bca3fdf7"
              },
              "_links": {
                "project": {
                  "href": "/api_2/projects/3985"
                },
                "self": {
                  "href": "/api_2/build_tasks/106897/fedora-21-i386"
                }
              }
            }
          ],
          "_links": {
            "project": {
              "href": "/api_2/projects/3985"
            },
            "self": {
              "href": "/api_2/builds/106897?show_chroots=True"
            },
            "build_tasks": {
              "href": "/api_2/build_tasks/?build_id=3985"
            }
          },
          "build": {
            "enable_net": true,
            "source_metadata": {
              "url": "http://miroslav.suchy.cz/copr/copr-ping-1-1.fc20.src.rpm"
            },
            "package_name": "copr-ping",
            "submitted_on": 1441366834,
            "package_version": "1-1.fc20",
            "built_packages": [
              {
                "version": "1",
                "name": "copr-ping"
              }
            ],
            "started_on": null,
            "source_type": "srpm_link",
            "state": "succeeded",
            "ended_on": 1441366969,
            "id": 106897,
            "repos": [],
            "submitter": "asamalik"
          }
        }

Cancel build
------------

Build cancellation is done be setting build state to ``cancelled``.

.. http:put:: /api_2/builds/(int:build_id)

    **REQUIRE AUTH**

    :param int build_id: a unique identifier of the build

    :statuscode 204: build was updated
    :statuscode 400: malformed request, most probably build can't be canceled at the moment
    :statuscode 404: build not found

    **Example request**:

    .. sourcecode:: http

        PUT /api_2/builds/1 HTTP/1.1
        Host: copr.fedoraproject.org
        Authorization: Basic base64=encoded=string
        Content-Type: application/json

        {
            "state": "cancelled"
        }

    **Response**

    .. sourcecode:: http

        HTTP/1.1 204 NO CONTENT

Delete build
------------
.. http:delete:: /api_2/builds/(int:build_id)

    **REQUIRE AUTH**

    Deletes build and schedules deletion of build result from the Copr backend

    :param int build_id: a unique identifier of the build

    :statuscode 204: build was removed
    :statuscode 400: could not delete build right now, most probably due to unfinished build
    :statuscode 403: authorization failed
    :statuscode 404: build not found

    **Example request**:

    .. sourcecode:: http

        DELETE /api_2/builds/1 HTTP/1.1
        Host: copr.fedoraproject.org
        Authorization: Basic base64=encoded=string

    **Response**

    .. sourcecode:: http

        HTTP/1.1 204 NO CONTENT


.. _python-requests: http://docs.python-requests.org/
