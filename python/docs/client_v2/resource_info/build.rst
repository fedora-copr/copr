.. warning::
    Client version 2 is obsolete, please use Client version 3 instead.


.. _build-info:

Build
=====

Build resource allows to submit new builds and access current build progress.
In fact, build consists of a few tasks, one per chroot, and detailed information is available through
:ref:`build-task-info`.

Access to the builds is done through :py:meth:`~copr.client_v2.client.CoprClient.builds`.
property of initialized :py:class:`~copr.client_v2.client.CoprClient`. That property is an instance of
:py:class:`~copr.client_v2.handlers.BuildHandle`.

It may be more convenient to access builds in context of a project
using method :py:meth:`~copr.client_v2.resources.Project.get_builds`.

Builds are represented by
:py:class:`~copr.client_v2.resources.Build` class.

.. _build-attributes:

Build entity attributes
-----------------------

.. copied from frontend docs, don't forget to update

==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
id                  int                  unique build identifier
state               string               current state of the build, value is aggregated from build tasks
submitted_on        int(unixtime UTC)    time of the build submission
started_on          int(unixtime UTC)    time when the first build task started, otherwise ``null``
ended_on            int(unixtime UTC)    time when the last build task ended, otherwise ``null``
source_type         string               method used for build creation
source_metadata     json object          build source information
package_version     string               version of the source package
package_name        string               name of the source package
enable_net          bool                 defines if network is available during the build
repos               list of string       list of additional repositories enabled during the build
built_packages      list of hash maps    list of the built packages, each hash map has two keys: ``name`` and ``version``
submitter           string               name of the user who submitted the build
==================  ==================== ===============

.. note::
    Only the ``state`` field is editable by the PUT method.
    All other fields are read-only.

Get builds list
---------------

.. sourcecode:: python

    >>> blist_1 = cl.builds.get_list(limit=2)
    >>> print(map(str, blist_1))
    ['<Build #138426 state: succeeded>', '<Build #138425 state: succeeded>']
    # using the project object
    >>> blist_2 = p.get_builds(limit=2)
    >>> print(map(str, blist_2))
    ['<Build #138423 state: failed>', '<Build #138421 state: failed>']


Get one build
-------------

.. sourcecode:: python

    >>> b = cl.builds.get_one(138421)
    >>> print(b)
    <Build #138421 state: failed>


Create new build
----------------

.. sourcecode:: python

    # using the url to sprm
    >>> b1 = cl.builds.create_from_url(project_id=3806, srpm_url="http://example.com/my.src.rpm")
    # or using project object
    >>> b2 = p.create_build_from_url("http://example.com/my.src.rpm")
    >>> print(map(str, [b1, b2]))
    ['<Build #138431 state: importing>', '<Build #138430 state: importing>']

    # and using the file upload
    >>> b3 = cl.builds.create_from_file(project_id=3806, file_path="/tmp/hello-2.8-1.fc20.src.rpm")
    >>> b4 = p.create_build_from_file("/tmp/hello-2.8-1.fc20.src.rpm")



Cancel build
------------

.. sourcecode:: python

    >>> b1.cancel()

Delete build
------------


.. sourcecode:: python

    >>> b1.delete()
