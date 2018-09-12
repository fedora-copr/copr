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


Debugging
---------

Sometimes it is useful to dig deeper and examine the failure. Exceptions contain a ``result`` attribute
returning a Munch with additional information.

::

    except CoprRequestException as ex:
        print(ex)
        print(ex.result)

::

    Cannot cancel build 123
    Munch({'__response__': <Response [500]>, 'error': u'Cannot cancel build 123'})


The stored response is a standard ``requests.Reponse`` so every possible detail like
status code or headers can be examined.

::

    except CoprRequestException as ex:
        print(type(ex.result.__response__))
        print(ex.result.__response__)
        print(ex.result.__response__.status_code)
        print(ex.result.__response__.headers)


::

    <class 'requests.models.Response'>
    <Response [500]>
    500
    {'Date': 'Wed, 25 Jul 2018 21:40:48 GMT', 'Content-Length': '42', 'Content-Type': 'application/json', 'Server': 'Werkzeug/0.12.2 Python/3.6.4'}


Status codes
------------

An apropriate status codes are used for specific situations.

==================  ====================
Status code         Reason
==================  ====================
200                 Successful request
401                 Unauthorized request when login is required
403                 Insufficient permissions, e.g. modifying a project of someone else
404                 API endpoint or requested object was not found
500                 General frontend error
==================  ====================


Exception hierarchy
-------------------

.. automodule:: copr.v3.exceptions
    :members:
    :show-inheritance:
