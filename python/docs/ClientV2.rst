.. warning::
    Client version 2 is obsolete, please use Client version 3 instead.


Client version 2
================

New package copr.ClientV2 supports APIv2 and should  eventually replace older one.
New API and Client_v2 provides more simple and uniform approach for communication with the Copr service.




Client mostly reflects resource based API nature. Client object offers range of methods to query from service.
Response objects contains requested information and also provides helper methods to execute new requests in the context
of retrieved objects.


.. toctree::
    :maxdepth: 1

    client_v2/initialization.rst
    client_v2/resources_usage.rst
    client_v2/errors.rst

Resources info
--------------

.. toctree::
    :maxdepth: 1

    client_v2/resource_info/project.rst
    client_v2/resource_info/project_chroot.rst
    client_v2/resource_info/build.rst
    client_v2/resource_info/build_task.rst
    client_v2/resource_info/mock_chroot.rst

Autodoc
-------

.. toctree::

    client_v2/general.rst
    client_v2/handlers.rst
    client_v2/resources.rst
    client_v2/entities.rst
