.. Copr Api 2 documentation master file, created by
   sphinx-quickstart on Wed Sep  2 14:50:00 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Copr Api 2's documentation!
======================================

Welcome to the documentation of the new REST-like API for the Copr build service.
Almost all API calls is done using ``application/json`` ContentType.

Endpoint of the the API is ``/api_2``, public data is available without authorization.

To create new projects, submit builds and do other modification requests you will need to provide API token using
BasicAuth_ . Token can be obtained and renewed at the CoprAPI_ page.

Resources
---------
.. toctree::
   :maxdepth: 2

   Resources/project
   Resources/project_chroot
   Resources/build
   Resources/build_task
   Resources/mock_chroot


HETEOAS
-------


This API implements HETEOAS_ in the very simple form: each entity is accompanied with set of relative links
to other related entities. HETEOAS makes API self discoverable, so you shouldn't learn how to access sub-resources.
Here is a short example with the content of API root:

**GET /api_2**

.. code-block:: javascript

   {
     "_links": {
       "mock_chroots": {
         "href": "/api_2/mock_chroots"
       },
       "self": {
         "href": "/api_2/"
       },
       "projects": {
         "href": "/api_2/projects"
       },
       "builds": {
         "href": "/api_2/builds"
       }
   }

Response structure
------------------

The API operates two kinds of resources: collections and individuals.

Each entity is enveloped into json dict and accompanied with set of HETEOAS references.
GET requests would return the following structures:

**Collection structure**:

.. code-block:: javascript

    {
        "_links" {
            "self": {
                "href": "<url which was used to obtain current collection>"
            },
            "<relation name>": {
                "href": "<relation url>"
            }
        },
        "<collection name>": [
            {<individual 1>},
            {<individual 2>},
            {
                "_links": {...},
                "<entity name>": {<entity structure>}
            }
        ]
    }

**Individual structure**:

.. code-block:: javascript

    {
        "_links": {
            "self": {
                "href": "<url which was used to obtain current collection>"
            },
            "<relation name>": {
                "href": "<relation url>"
            }
        },
        "<entity name>": {<entity structure>}
    }

Errors
______

To distinguish errors we use standard HTTP codes: https://en.wikipedia.org/wiki/List_of_HTTP_status_codes.
Additional information may be contained in the response body, it SHOULD have `application/json` Content-Type.
Inside json object, there are MUST be key ``message`` with error description,
additional information MAY be present at key ``data``

    **Example**

    .. sourcecode:: http

        GET /api_2/builds?project_id=999999999 HTTP/1.1
        Host: copr.fedoraproject.org

    **Response**

    .. sourcecode:: http

        HTTP/1.1 404 NOT FOUND
        Content-Type: application/json

        {
          "message": "Project with id `999999999` not found",
          "data": {
            "project_id": 999999999
          }
        }


.. _BasicAuth: https://en.wikipedia.org/wiki/Basic_access_authentication
.. _CoprAPI: https://copr.fedoraproject.org/api
.. _HETEOAS: https://en.wikipedia.org/wiki/HATEOAS
