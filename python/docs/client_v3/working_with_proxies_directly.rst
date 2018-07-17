Working with proxies directly
=============================

In all sample codes, it is used Client to provide proxy objects (``project_proxy``, ``build_proxy``, etc). However, that
is not the only way how to do it. Proxy classes can be also initialized directly.


Following code samples are equal.

.. code-block:: python

    from copr.v3 import Client
    client = Client.create_from_config_file()
    build = client.build_proxy.get(123)


Same thing without using Client.

.. code-block:: python

    from copr.v3 import BuildProxy
    config = {"username": "frostyx", , "copr_url": "https://copr.fedorainfracloud.org/",
              "login": "somehash", "token": "someotherhash"}
    build_proxy = BuildProxy(config)
    build = build_proxy.get(123)
