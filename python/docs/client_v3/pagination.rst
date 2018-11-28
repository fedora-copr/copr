.. _pagination:

Pagination
==========

Pagination is not enforced, so users don't need to care about it if they don't want to. In this code sample,
all packages from given project are returned, regardless their number.

.. code-block:: python

    from copr.v3 import Client
    client = Client(config)

    packages = client.package_proxy.get_list("@copr", "copr")
    print(packages)

::

    [Munch({'id': 1, 'ownername': '@copr', 'projectname': 'copr', 'state': 'pending', ...}),
     Munch({'id': 2, 'ownername': '@copr', 'projectname': 'copr', 'state': 'pending', ...}),
     Munch({'id': 3, 'ownername': '@copr', 'projectname': 'copr', 'state': 'importing', ...}),
     Munch({'id': 4, 'ownername': '@copr', 'projectname': 'copr', 'state': 'importing', ...}),
     Munch({'id': 5, 'ownername': '@copr', 'projectname': 'copr', 'state': 'canceled', ...})]


However, in some cases, it may be useful to obtain just a limited number of objects. Querying all builds from a project
with hundreds of thousands of them may be painfully slow or even timeout. And if all of them are not even needed, it is
a huge waste of resources. It all depends on the specific use-case. When it is useful, you can query limited
and/or ordered number of objects.

.. code-block:: python

    pagination = {"limit": 3, "order": "name"}
    packages = client.package_proxy.get_list("@copr", "copr", pagination=pagination)
    print(packages)
    print(packages.meta)

::

    [Munch({'id': 1, 'ownername': '@copr', 'projectname': 'copr', 'state': 'pending', ...}),
     Munch({'id': 2, 'ownername': '@copr', 'projectname': 'copr', 'state': 'pending', ...}),
     Munch({'id': 3, 'ownername': '@copr', 'projectname': 'copr', 'state': 'importing', ...})]
    Munch({u'offset': 0, u'limit': 3, u'order_type': u'ASC', u'order': u'id'})


And finally, in some cases, it may be useful to iterate through all objects, but not obtaining them all at once
(e.g. when projects are so large, that requesting everything timeouts).

.. code-block:: python

    from copr.v3 import next_page

    package_page = client.package_proxy.get_list("@copr", "copr", pagination={"limit": 3})
    while package_page:
        for package in package_page:
            print(package)
        print("---")
        package_page = next_page(package_page)

::

    Munch({'id': 1, 'ownername': '@copr', 'projectname': 'copr', 'state': 'pending', ...})
    Munch({'id': 2, 'ownername': '@copr', 'projectname': 'copr', 'state': 'pending', ...})
    Munch({'id': 3, 'ownername': '@copr', 'projectname': 'copr', 'state': 'importing', ...})
    ---
    Munch({'id': 4, 'ownername': '@copr', 'projectname': 'copr', 'state': 'importing', ...})
    Munch({'id': 5, 'ownername': '@copr', 'projectname': 'copr', 'state': 'canceled', ...})


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

