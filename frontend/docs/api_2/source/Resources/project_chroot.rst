Project Chroot
==============

Projects Chroots allows to view and modify project settings dedicated for different chroots.

Structure if the project chroot entity
--------------------------------------

.. code-block:: javascript

    {
        "comps": null,
        "comps_len": 0,
        "buildroot_pkgs": [
            "scl-build-utils",
            "foobar"
        ],
        "name": "fedora-22-i386",
        "comps_name": null
    }

Project Chroot fields
~~~~~~~~~~~~~~~~~~~~~
==================  ==================== ========= ===============
Field               Type                 Can edit? Description
==================  ==================== ========= ===============
name                string               no        chroot name
buildroot_pkgs      list of strings      yes       packages to be installed into the buildroot
comps               string               yes       content of the `comps.xml`_
comps_name          string               yes       name of the uploaded comps file
comps_len           int                  no        size of the uploaded comps file (bytes)
==================  ==================== ========= ===============

List project chroots
--------------------
.. http:get:: /api_2/projects/(int:project_id)/chroots

    Returns a list of project chroots

    :param int project_id: a unique identifier of the Copr project.

    :statuscode 200: no error
    :statuscode 404: project not found

    **Example request**

    .. sourcecode:: http

        GET /api_2/projects/2482/chroots HTTP/1.1
        Host: copr.fedoraproject.org
        Accept: application/json

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "chroots": [
            {
              "chroot": {
                "comps": null,
                "comps_len": 0,
                "buildroot_pkgs": [],
                "name": "fedora-21-x86_64",
                "comps_name": null
              },
              "_links": {
                "project": {
                  "href": "/api_2/projects/2482"
                },
                "self": {
                  "href": "/api_2/projects/2482/chroots/fedora-21-x86_64"
                }
              }
            },
            { }
          ],
          "_links": {
            "self": {
              "href": "/api_2/projects/2482/chroots"
            }
          }
        }

Enable chroot for project
-------------------------
.. http:post:: /api_2/projects/(int:project_id)/chroots

    **REQUIRE AUTH**

    Enables chroot for the Copr project.
    Available `chroot` names could be obtained from MockChrootResource_

    :param int project_id: a unique identifier of the Copr project.

    :resheader Location: contains URL to the enabled project chroot

    :statuscode 201: project was successfully created
    :statuscode 400: given data doesn't satisfy some requirements
    :statuscode 401: this chroot is already enabled
    :statuscode 403: authorization failed


    **Example request**:

    .. sourcecode:: http

        POST  HTTP/1.1
        Host: copr.fedoraproject.org
        Authorization: Basic base64=encoded=string
        Accept: application/json

        {
            "buildroot_pkgs": ["foo", "bar"],
            "name": "fedora-22-x86_64"
        }

    **Response**:

    .. sourcecode:: http

        HTTP/1.1 201 CREATED
        Location: /api_2/projects/2482/chroots/fedora-22-x86_64

Get project chroot details
--------------------------
.. http:get:: /api_2/projects/(int:project_id)/chroots/(str:chroot_name)

    Returns details about Copr project

    :param int project_id: a unique identifier of the Copr project.
    :param str chroot_name: name of the project chroot

    :statuscode 200: no error
    :statuscode 404: project not found or chroot isn't enabled for the project

    **Example request**

    .. sourcecode:: http

        GET /api_2/projects/2482/chroots/fedora-22-x86_64 HTTP/1.1
        Host: copr.fedoraproject.org
        Accept: application/json

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "chroot": {
            "comps": null,
            "comps_len": 0,
            "buildroot_pkgs": [
              "foo",
              "bar"
            ],
            "name": "fedora-22-x86_64",
            "comps_name": null
          },
          "_links": {
            "project": {
              "href": "/api_2/projects/2482"
            },
            "self": {
              "href": "/api_2/projects/2482/chroots/fedora-22-x86_64"
            }
          }
        }

Disable chroot for project
--------------------------
.. http:delete:: /api_2/projects/(int:project_id)/chroots/(str:chroot_name)

    **REQUIRE AUTH**

    Disables chroot for the Copr project

    :param int project_id: a unique identifier of the Copr project.
    :param str chroot_name: name of the project chroot

    :statuscode 204: project was removed
    :statuscode 403: authorization failed
    :statuscode 404: project not found or chroot isn't enabled for the project

    **Example request**:

    .. sourcecode:: http

        DELETE /api_2/projects/2482/chroots/fedora-22-x86_64  HTTP/1.1
        Host: copr.fedoraproject.org
        Authorization: Basic base64=encoded=string

    **Response**

    .. sourcecode:: http

        HTTP/1.1 204 NO CONTENT

Modify project chroot
---------------------
.. http:put:: /api_2/projects/(int:project_id)/chroots/(str:chroot_name)


    **REQUIRE AUTH**

    Updated project chroot settings

    :param int project_id: a unique identifier of the Copr project.
    :param str chroot_name: name of the project chroot

    :statuscode 201: project chroot was updated
    :statuscode 400: malformed request, see response content for details
    :statuscode 403: authorization failed
    :statuscode 404: project not found or chroot isn't enabled for the project

    **Example request**:

    .. sourcecode:: http

        PUT /api_2/projects/2482/chroots/fedora-22-x86_64  HTTP/1.1
        Host: copr.fedoraproject.org
        Authorization: Basic base64=encoded=string

        {
            "buildroot_pkgs": []
        }

    **Response**

    .. sourcecode:: http

        HTTP/1.1 204 NO CONTENT


.. _comps.xml: https://fedorahosted.org/comps/
