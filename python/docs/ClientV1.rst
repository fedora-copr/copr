.. warning::
    Legacy client is obsolete, please use Client version 3 instead. :ref:`This document <migration>` describes the migration process.


Legacy client
=============

All interaction are done through copr.CoprClient.
It can be created directly or using config file :file:`/etc/copr.conf`

*CoprClient* offers methods that directly reflect Copr api. Received data
are wrapped into the Response object.
Depending on used methods Responses will have different set of
provided attributes and methods.

.. toctree::
    client_v1/Examples

See method signatures and response objects in
the auto generated documentation:


.. toctree::
    client_v1/CoprClient
    client_v1/Responses
