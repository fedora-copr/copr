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

Errors
______
todo:


Resources
---------
.. toctree::
   :maxdepth: 1

   Resources/project


.. Indices and tables
   ==================
   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`

.. _BasicAuth: https://en.wikipedia.org/wiki/Basic_access_authentication
.. _CoprAPI: https://copr.fedoraproject.org/api
.. _HETEOAS: https://en.wikipedia.org/wiki/HATEOAS

