Error handling
==============

All methods from proxy classes return Munch with data only when the API call succeeds. Otherwise, an exception is raised.

This example code tries to cancel a build. Such thing is possible only when the build is not already finished.

.. code-block:: python

    from copr.v3 import Client
    client = Client.create_from_config_file()

    try:
        build = client.build_proxy.cancel(123)
        print("Build {} is {}".format(build.id, build.state))
    except CoprRequestException as ex:
        print(ex)


In case that the build can be canceled, we get this output.

::

    Build 123 is canceled


Otherwise, an exception is raised and handled.

::

    Cannot cancel build 123


Exception hierarchy
-------------------

.. automodule:: copr.v3.exceptions
    :members:
    :show-inheritance:
