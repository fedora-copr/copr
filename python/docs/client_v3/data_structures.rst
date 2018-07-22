Data structures
===============

A data returned from successful API calls are transformed and presented to you as a Munch (it is a subclass of a
``dict`` with all its features, with an additional support of accessing its attributes like object properties, etc).
This page shows how to work with the results, how to access the original responses from frontend and what are the
specifics for lists of results.


First, let's just initialize an API client, and obtain some object (in this example a build) to be examined.

::

    from copr.v3 import Client
    client = Client.create_from_config_file()
    build = client.build_proxy.get(2545)
    pprint(build)


As advertised, the data is represented as a Munch.

::

    Munch({u'source_package': {u'url': u'http://backend/results//@copr/copr/srpm-builds/00002545/ed-1.14.2-3.fc26.src.rpm', u'version': u'1.14.2-3.fc26', u'name': u'ed'}, '__response__': <Response [200]>, u'projectname': u'copr', u'started_on': 1526406595, u'submitted_on': 1525635534, u'state': u'succeeded', u'ended_on': 1526408106, u'ownername': u'@copr', u'repo_url': u'http://backend/results/@copr/copr', u'submitter': u'frostyx', u'chroots': [u'fedora-27-x86_64', u'fedora-rawhide-x86_64'], u'id': 2545})


What exactly it is? It is a structure that extends ``dict`` and add more features to it.


::

    print(type(build))
    print(isinstance(build, dict))

::

    <class 'munch.Munch'>
    True


In the first example, it is quite hard to see, what attributes are available and what are their values. It is possible
to print the structure in more human-readable format.


::

    from pprint import pprint
    pprint(dict(build))

::

    {'__response__': <Response [200]>,
     u'chroots': [u'fedora-27-x86_64', u'fedora-rawhide-x86_64'],
     u'ended_on': 1526408106,
     u'id': 2545,
     u'ownername': u'@copr',
     u'projectname': u'copr',
     u'repo_url': u'http://backend/results/@copr/foo',
     u'source_package': {u'name': u'ed',
                         u'url': u'http://backend/results//@copr/copr/srpm-builds/00002545/ed-1.14.2-3.fc26.src.rpm',
                         u'version': u'1.14.2-3.fc26'},
     u'started_on': 1526406595,
     u'state': u'succeeded',
     u'submitted_on': 1525635534,
     u'submitter': u'frostyx'}


Attributes are accessible through standard dict bracket-style, but also through object like property-style.


::

    assert build.ownername == build["ownername"]
    print(build.ownername)

::

    @copr


Every data munch also stores the original response from frontend.

::

    print(build.__response__)
    print(type(build.__response__))
    print(build.__response__.status_code)

::

    <Response [200]>
    requests.models.Response
    200


Lists of objects
----------------

Now, it should be clear how a single data object is represented. Let's see how the situation looks like
when multiple objects are returned.

::

    builds = client.build_proxy.get_list("@copr", "copr")
    print(builds)


At the first sight, it is just a list of munches.

::

    [Munch({u'source_package': {u'url': u'http://backend/results//@copr/copr/srpm-builds/00002544/mksh-56c-3.fc26.src.rpm', u'version': u'56c-3.fc26', u'name': u'mksh'}, u'projectname': u'copr', u'started_on': 1519063348, u'submitted_on': 1519062565, u'state': u'succeeded', u'ended_on': 1519064069, u'ownername': u'frostyx', u'repo_url': u'http://backend/results/@copr/copr', u'submitter': u'frostyx', u'chroots': [u'fedora-rawhide-i386', u'fedora-rawhide-x86_64'], u'id': 2544}),
     Munch({u'source_package': {u'url': u'http://backend/results//@copr/copr/srpm-builds/00002545/ed-1.14.2-3.fc26.src.rpm', u'version': u'1.14.2-3.fc26', u'name': u'ed'}, u'projectname': u'copr', u'started_on': 1526406595, u'submitted_on': 1525635534, u'state': u'succeeded', u'ended_on': 1526408106, u'ownername': u'@copr', u'repo_url': u'http://backend/results/@copr/copr', u'submitter': u'frostyx', u'chroots': [u'fedora-27-x86_64', u'fedora-rawhide-x86_64'], u'id': 2545})]


Not exactly. It is a subclass of a ``list`` created in the ``copr`` package.


::

    print(type(builds))
    print(isinstance(builds, list))

::

    <class 'copr.v3.helpers.List'>
    True

Let's answer the anticipated question, why do we need a modified implementation of a list. It can provide the frontned
response in a ``__response__`` attribute the same way that single munch does.

::

    print(builds.__response__)
    <Response [200]>


It also provides a ``meta`` attribute, that has information about ordering results in the list and possibly limiting
their number. Please read more about the pagination.

::

    print(builds.meta)
    Munch({u'offset': 0, u'limit': None, u'order_type': u'ASC', u'order': u'id'})


Iterating through all objects in the response looks as expected.

::

    for build in builds:
        print("Build {} {}".format(build.id, build.state))

::

    Build 2544 succeeded
    Build 2545 succeeded


Modifying data
--------------

Previous examples show the data structures when the object was explicitly queried
(i.e. ``get`` or ``get_list`` method was used). It remains to be explained, how the responses look like when a user
tries to add, modify, or delete some object. Simply enough, the operation is executed and the object is implicitly
queried afterward.


::

    build = client.build_proxy.delete(2545)
    print(build)

::

    Munch({u'source_package': {u'url': u'http://backend/results//@copr/copr/srpm-builds/00002545/ed-1.14.2-3.fc26.src.rpm', u'version': u'1.14.2-3.fc26', u'name': u'ed'}, u'projectname': u'copr', u'started_on': 1526406595, u'submitted_on': 1525635534, u'state': u'succeeded', u'ended_on': 1526408106, u'ownername': u'@copr', u'repo_url': u'http://backend/results/@copr/copr', u'submitter': u'frostyx', u'chroots': [u'fedora-27-x86_64', u'fedora-rawhide-x86_64'], u'id': 2545})


The object was deleted, so it obviously can't be queried one more time

::

    client.build_proxy.get(build.id)

::

    CoprNoResultException: Build 2545 does not exist.
