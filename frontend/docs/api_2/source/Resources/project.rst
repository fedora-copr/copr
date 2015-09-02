Project
=======

Project resource represents copr projects and operations with them.

Structure of the project entity
-------------------------------

**An example**:

.. code-block:: javascript

    {
        "description": "A recent stable release of Ruby with Rails 3.2.8 and ... ",
        "disable_createrepo": false,
        "repos": [
          "http://copr-be.cloud.fedoraproject.org/results/msuchy/scl-utils/epel-6-$basearch/",
          "http://copr-be.cloud.fedoraproject.org/results/rhscl/httpd24/epel-6-$basearch/",
        ],
        "contact": null,
        "owner": "rhscl",
        "build_enable_net": true,
        "instructions": "",
        "homepage": null,
        "id": 479,
        "name": "ruby193"
    }


Project fields
~~~~~~~~~~~~~~
==================  ==================== ========= ===============
Field               Type                 Can edit? Description
==================  ==================== ========= ===============
id                  number               no        unique identifier
owner               string               no        login of the project owner
name                string               no        name of the project, MUST be specified during a project creation
description         string               yes       project description
instructions        string               yes       installation instructions
homepage            string(URL)          yes       project homepage
contact             string(URL or email) yes       contact with the project maintainer
disable_createrepo  bool                 yes       disables automatic repository metadata generation
build_enable_net    bool                 yes       set default value for new builds option `enable_net`
==================  ==================== ========= ===============

List projects collection
------------------------
.. http:get:: /api_2/projects

    Returns a list of Copr projects according to the given query parameters

    **Example request**:

    .. sourcecode:: http

        GET /api_2/projects HTTP/1.1
        Host: copr.fedoraproject.org
        Accept: application/json

    **Response**:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "_links": {
            "self": {
              "href": "/api_2/projects"
            }
          },
          "projects": [
            {
              "project": {
                "description": "Lightweight buildsystem - upstream releases. Usually build few days before it land in Fedora.",
                "disable_createrepo": false,
                "repos": [],
                "contact": null,
                "owner": "msuchy",
                "build_enable_net": false,
                "instructions": "See https://fedorahosted.org/copr/ for more details.",
                "homepage": null,
                "id": 1,
                "name": "copr"
              },
              "_links": {   }
            },
          ]
        }

    :query search_query: filter project using full-text search
    :query owner: select only projects owned by this user
    :query name: select only projects with this name
    :query offset: offset number, default value is 0
    :query limit: limit number, default value is 100

    :statuscode 200: no error

Create new project
------------------
.. http:post:: /api_2/projects

    **REQUIRE AUTH**

    Creates new Copr project.

    Additionally to described before `Project fields`_ the user could specify field `chroots` which contains list of chroots to be enabled.
    Available `chroot` names could be obtained from MockChrootResource_

    **Example request**:

    .. sourcecode:: http

        POST /api_2/projects HTTP/1.1
        Host: copr.fedoraproject.org
        Authorization: Basic base64=encoded=string
        Accept: application/json

        {
            "disable_createrepo": false,
            "build_enable_net": true,
            "name": "foobar",
            "chroots": [
                "fedora-22-x86_64",
                "fedora-22-i386",
            ]
        }


    **Response**:

    .. sourcecode:: http

        HTTP/1.1 201 CREATED
        Location: /api_2/projects/<new project id>

    :resheader Location: contains URL to the newly created project entity

    :statuscode 201: project was successfully created
    :statuscode 400: given data for project creation doesn't satisfy some requirements
    :statuscode 401: the user already has project with the same name
    :statuscode 403: authorization failed

Get project details
-------------------
.. http:get:: /api_2/projects/(int:project_id)

    Returns details about Copr project

    :param project_id: a unique identifier of the Copr project.

    :query bool show_builds: embed Build_ entities owned by this project into the result, default is False
    :query bool show_chroots: embed ProjectChroot_ sub-resources into the result, default is False

    :statuscode 200: no error
    :statuscode 404: project not found

    **Example request**

    .. sourcecode:: http

        GET /api_2/projects/2482 HTTP/1.1
        Host: copr.fedoraproject.org
        Accept: application/json

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
            "project": {
                "description": "A simple KDE respin",
                "disable_createrepo": false,
                "repos": [],
                "contact": null,
                "owner": "jmiahman",
                "build_enable_net": true,
                "instructions": "",
                "homepage": null,
                "id": 2482,
                "name": "Synergy-Linux"
            },
            "project_chroots": [
                {
                    "chroot": {
                        "comps": null,
                        "comps_len": 0,
                        "buildroot_pkgs": [],
                        "name": "fedora-19-x86_64",
                        "comps_name": null
                    }
                    "_links": {}
                },
                { }
            ],
            "project_builds": [
                {
                    "_links": { },
                    "build": {
                        "enable_net": true,
                        "submitted_on": 1422379448,
                        "repos": [],
                        "results": "https://copr-be.cloud.fedoraproject.org/results/jmiahman/Synergy-Linux/",
                        "started_on": 1422379466,
                        "source_type": 1,
                        "state": "succeeded",
                        "source_json": "{\"url\": \"http://dl.kororaproject.org/pub/korora/releases/21/source/korora-welcome-21.6-1.fc21.src.rpm\"}",
                        "ended_on": 1422379584,
                        "timeout": 21600,
                        "pkg_version": "21.6-1.fc21",
                        "id": 69493
                    }
                },
                {  }
            ],
            "_links": {
                "self": {
                  "href": "/api_2/projects/2482?show_builds=True&show_chroots=True"
                },
                "chroots": {
                  "href": "/api_2/projects/2482/chroots"
                },
                "builds": {
                  "href": "/api_2/builds?project_id=2482"
                }
            }
        }

Delete project
--------------

Modify project
--------------
