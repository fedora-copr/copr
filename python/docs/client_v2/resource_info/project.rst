.. warning::
    Client version 2 is obsolete, please use Client version 3 instead.


.. _project-info:

Project
=======

Project resource represents copr projects and operations with them.

Access to the projects is done through :py:meth:`~copr.client_v2.client.CoprClient.projects`.
property of initialized :py:class:`~copr.client_v2.client.CoprClient`. That property is an instance of
:py:class:`~copr.client_v2.handlers.ProjectHandle`. Projects are represented by
:py:class:`~copr.client_v2.resources.Project` class.

.. _project-attributes:

Project entity attributes
-------------------------

.. copied from frontend docs, don't forget to update

==================  ==================== ========= =================================================================================
Field               Type                 Can edit? Description
==================  ==================== ========= =================================================================================
id                  number               no        unique identifier
owner               string               no        username of the project owner
group               string               no        name of the group which owns the project, value is null for non-group projects
                                                    - MAY be specified during a project creation to create a group managed project
name                string               no        name of the project
                                                    - MUST be specified during a project creation
description         string               yes       project description
instructions        string               yes       installation instructions
homepage            string(URL)          yes       project homepage URL
contact             string(URL or email) yes       contact with the project maintainer
disable_createrepo  bool                 yes       disables automatic repository metadata generation
build_enable_net    bool                 yes       set default value for new builds option ``enable_net``
repos               list of string       yes       list of additional repositories to be enabled during the build
==================  ==================== ========= =================================================================================


.. note::
    all following examples assume that we use ``cl``
    as an instance of :py:class:`.client_v2.client.CoprClient`


Get projects list
-----------------

.. sourcecode:: python

    >>> plist_1 = cl.project.get_list(limit=10)
    # filter by name
    >>> plist_2 = cl.project.get_list(name="copr")
    # search by string
    >>> plist_2 = cl.project.get_list(search_query="copr")


Get one project
---------------

.. sourcecode:: python

    >>> p = cl.projects.get_one(1835)

Modify project parameters
-------------------------

.. sourcecode:: python

    >>> p.description = "Nothing"
    >>> p.update()

Delete project
--------------

.. sourcecode:: python

    >>> p.delete()

Create new project
------------------

.. note::
    Here you could also provide list of chroots, which should be activated. Use key ``chroots``.

.. sourcecode:: python

    >>> res = cl.projects.create(name="my_cool_project",
                                 owner="vgologuz",
                                 instructions="don't touch me!",
                                 chroots=["fedora-22-x86_64"])
    >>>  print(res)
    <Project #5384: vgologuz/my_cool_project>



Access project chroots
----------------------
.. note::
    see also :ref:`project-chroot-info`


.. sourcecode:: python

    # get all lists
    >>> chroots = p.get_project_chroot_list()
    >>> print("\n".join(map(str, chroots)))
    <Project chroot: fedora-21-x86_64, additional packages: [], comps size if any: 0>
    <Project chroot: fedora-21-i386, additional packages: [], comps size if any: 0>
    # get one chroot
    >>> chroot_1 = p.get_project_chroot("fedora-22-i386")
    # enable chroot for project
    >>> p.enable_project_chroot("fedora-22-x86_64)

Access project builds
---------------------
.. note::
    see also :ref:`build-info`

.. sourcecode:: python

    >>> p.get_builds(limit=5)
    >>> pbuilds = p.get_builds(limit=5)
    >>> print(pbuilds[3])
    <Build #138414 state: failed>

    # submit new builds
    >>> p.create_build_from_url(srpm_url="http://example.com/my.src.rpm")
    >>> p.create_build_from_file(file_path="/tmp/my.src.rpm")
