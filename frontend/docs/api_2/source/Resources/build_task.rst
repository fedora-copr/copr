Build Task
==========

Build task represents information about individual build tasks. One task is responsible for one chroot.

Structure of the build task entity
----------------------------------

.. code-block:: javascript

    {
        "chroot_name": "fedora-rawhide-x86_64",
        "build_id": 12345,
        "started_on": 1440753865,
        "ended_on": 1440753919,
        "state": "succeeded",
        "result_dir_url": "http://copr-be-dev.cloud.fedoraproject.org/results/vgologuz/aeghqawgt/fedora-rawhide-x86_64/00106882-python-marshmallow",
        "git_hash": "d241064b14f9dcd5d9032d0aca3b4e78fbd1aafd"
    }

Build tasks fields
~~~~~~~~~~~~~~~~~~
==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
chroot_name         str                  chroot name
build_id            int                  unique build identifier
state               str                  current build task state
started_on          int(unixtime UTC)    time when the build chroot started
ended_on            int(unixtime UTC)    time when the build chroot ended
git_hash            str                  hash of the git commit in dist-git used for the build
result_dir_url      str(URL)             location of the build results
==================  ==================== ===============


.. note::
    Build Chroot doesn't currently support any modifications,
    so all fields are read-only.

List build tasks
----------------

.. http:get:: /api_2/builds_tasks

    Returns list of build tasks according to the given query parameters

    :query str owner: select build tasks from projects owned by this user
    :query int project_id:
        select build tasks from one project,
        when used query parameter ``owner`` is ignored
    :query int build_id:
        select build tasks from one project,
        when used query parameters ``owner`` and ``project_id`` are ignored

    :query int offset: offset number, default value is 0
    :query int limit: limit number, default value is 100
    :query str state:
        select builds in particular state, allowed values:
        ``failed``, ``succeeded``, ``canceled``, ``running``,
        ``pending``, ``starting``, ``importing``

    :statuscode 200: no error
    :statuscode 404: build not found

    **Example request**

    .. sourcecode:: http

        GET /api_2/builds_tasks?build_id=106882 HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "build_tasks": [
            {
              "build_task": {
                "chroot_name": "fedora-rawhide-x86_64",
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
                  "href": "/api_2/build_tasks/106882/fedora-rawhide-x86_64"
                }
              }
            }
          ],
          "_links": {
            "self": {
              "href": "/api_2/build_tasks?build_id=106882"
            }
          }
        }



Get build task details
----------------------

.. http:get:: /api_2/build_tasks/(int:build_id)/(str:name)

    Returns details about one build task

    :param int build_id: a unique identifier of the build
    :param str name: chroot name

    :statuscode 200: no error
    :statuscode 404: build or build task not found

    **Example request**

    .. sourcecode:: http

        GET /api_2/build_tasks/106882/fedora-rawhide-x86_64 HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "build_task": {
            "chroot_name": "fedora-rawhide-x86_64",
            "build_id": 3985,
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
              "href": "/api_2/build_tasks/106882/fedora-rawhide-x86_64"
            }
          }
        }

