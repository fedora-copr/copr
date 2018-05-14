.. _pagination:

Pagination
==========

Pagination is not enforced, so users don't need to care about it if they don't want to. In this code sample,
all packages from given project are returned, regardless their number.

.. code-block:: python

    from copr.client_v3 import Client
    client = Client(config)

    packages = client.package_proxy.get_list("@copr", "foo")
    print(packages)


In some cases, it may be useful to obtain just a limited number of objects.

.. code-block:: python

    pagination = {"limit": 3, "order": "name"}
    packages = client.package_proxy.get_list("@copr", "foo", pagination=pagination)
    print(packages)
    print(packages.meta)


And finally, in some cases, it may be useful to iterate through all objects, but not obtaining them all at once
(e.g. when projects are so large, that requesting everything timeouts).

.. code-block:: python

    from copr.client_v3 import next_page

    packages = packagep.get_list("@copr", "foo", pagination={"limit": 3})
    while packages:
        print(packages)
        packages = next_page(packages)


Pagination parameters
---------------------

==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
limit               int                  number of objects to obtain
offset              int                  number of objects from beginning to skip
order               str                  sort objects by this property
order_type          str                  "ASC" or "DESC"
==================  ==================== ===============

