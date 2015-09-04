Mock Chroot
===========

Mock chroot resources represents available chroots for builds. API provides only read-only access,
since configuration of the build chroots is done by the service administrator.

Structure of the mock chroot entity
-----------------------------------

.. code-block:: javascript

    {
        "name": "epel-6-i386",
        "os_release": "epel",
        "os_version": "6",
        "arch": "i386",
        "is_active": true
    }

Mock Chroot fields
~~~~~~~~~~~~~~~~~~
==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
name                str                  chroot name
os_release          str                  name of distribution system, e.g.: epel, fedora
os_version          str                  version of distribution system, e.g.: 7, 22
arch                str                  architecture of distribution, e.g.: i386, x86_64, ppc64le
is_active           bool                 defines if this chroot is available for builds
==================  ==================== ===============

List mock chroots
-----------------
.. http:get:: /api_2/mock_chroots

    Returns a list of mock chroots

    :query param active_only: when set to True shows only active mock chroots

    :statuscode 200: no error

    **Example request**:

    .. sourcecode:: http

        GET /api_2/mock_chroots?active_only=True HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**:

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "chroots": [
            {
              "chroot": {
                "name": "epel-6-i386",
                "os_release": "epel",
                "os_version": "6",
                "arch": "i386",
                "is_active": true
              },
              "_links": {
                "self": {
                  "href": "/api_2/mock_chroots/epel-6-i386"
                }
              }
            },
            {  },
          ],
          "_links": {
            "self": {
              "href": "/api_2/mock_chroots?active_only=True"
            }
          }
        }

Get mock chroot details
-----------------------
.. http:get:: /api_2/mock_chroots/(str:chroot_name)

    Returns mock chroot details

    :param str chroot_name: Uniquer mock chroot name


    :statuscode 200: no error
    :statuscode 404: mock chroot not found by the given name

    **Example request**

    .. sourcecode:: http

        GET /api_2/mock_chroots/fedora-rawhide-i386 HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

        {
          "chroot": {
            "name": "fedora-rawhide-i386",
            "os_release": "fedora",
            "os_version": "rawhide",
            "arch": "i386",
            "is_active": true
          },
          "_links": {
            "self": {
              "href": "/api_2/mock_chroots/fedora-rawhide-i386"
            }
          }
        }

