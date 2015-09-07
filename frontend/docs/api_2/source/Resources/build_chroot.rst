Build Chroot
============

Build chroot represents information about individual build tasks for each chroot.

Structure of the build chroot entity
------------------------------------

.. code-block:: javascript

    {
        "name": "fedora-rawhide-x86_64",
        "started_on": 1440753865,
        "ended_on": 1440753919,
        "state": "succeeded",
        "result_dir_url": "http://copr-be-dev.cloud.fedoraproject.org/results/vgologuz/aeghqawgt/fedora-rawhide-x86_64/00106882-python-marshmallow",
        "git_hash": "d241064b14f9dcd5d9032d0aca3b4e78fbd1aafd"
    }

Build chroot fields
~~~~~~~~~~~~~~~~~~~
==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
name                str                  chroot name
state               str                  current build state
started_on          int(unixtime UTC)    time when the build chroot started
ended_on            int(unixtime UTC)    time when the build chroot ended
git_hash            str                  hash of the git commit in dist-git used for the build
result_dir_url      str(URL)             location of the build results
==================  ==================== ===============


.. note::
    Build Chroot doesn't currently support any modifications,
    so all fields are read-only.

List build chroots
------------------

.. http:get:: /api_2/builds/(int:build_id)/chroots

    Returns list of build chroots contained in the one build

    :param int build_id: a unique identifier of the build

    :statuscode 200: no error
    :statuscode 404: build not found

    **Example request**

    .. sourcecode:: http

        GET /api_2/builds/106882/chroots HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "chroots": [
            {
              "chroot": {
                "name": "fedora-rawhide-x86_64",
                "started_on": 1440753865,
                "state": "succeeded",
                "ended_on": 1440753919,
                "result_dir_url": "http://copr-be-dev.cloud.fedoraproject.org/results/vgologuz/aeghqawgt/fedora-rawhide-x86_64/00106882-python-marshmallow",
                "git_hash": "d241064b14f9dcd5d9032d0aca3b4e78fbd1aafd"
              },
              "_links": {
                "project": {
                  "href": "/api_2/projects/3985"
                },
                "self": {
                  "href": "/api_2/builds/106882/chroots/fedora-rawhide-x86_64"
                }
              }
            }
          ],
          "_links": {
            "self": {
              "href": "/api_2/builds/106882/chroots"
            }
          }
        }



Get build chroot details
------------------------

.. http:get:: /api_2/builds/(int:build_id)/chroots/(str:name)

    Returns details about one build chroot

    :param int build_id: a unique identifier of the build
    :param str name: chroot name

    :statuscode 200: no error
    :statuscode 404: build or build chroot not found

    **Example request**

    .. sourcecode:: http

        GET /api_2/builds/106882/chroots/fedora-rawhide-x86_64 HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "chroot": {
            "name": "fedora-rawhide-x86_64",
            "started_on": 1440753865,
            "state": "succeeded",
            "ended_on": 1440753919,
            "result_dir_url": "http://copr-be-dev.cloud.fedoraproject.org/results/vgologuz/aeghqawgt/fedora-rawhide-x86_64/00106882-python-marshmallow",
            "git_hash": "d241064b14f9dcd5d9032d0aca3b4e78fbd1aafd"
          },
          "_links": {
            "project": {
              "href": "/api_2/projects/3985"
            },
            "self": {
              "href": "/api_2/builds/106882/chroots/fedora-rawhide-x86_64"
            }
          }
        }

