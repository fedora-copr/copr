Project
=======

Access to project resources is done through :py:meth:`~copr.client_v2.client.CoprClient.projects`.
property of initialized :py:class:`~copr.client_v2.client.CoprClient`.

Individual Attributes
---------------------

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
build_enable_net    bool                 yes       set default value for new builds option `enable_net`
repos               list of string       yes       list of additional repositories to be enabled during the build
==================  ==================== ========= =================================================================================


.. note:: all following examples assume that we use `cl` as an instance of :py:class:`.client_v2.client.CoprClient`

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

    .. todo:: Not Implemented yet


Fetch projects
--------------

    .. sourcecode:: python

        >>> plist_1 = cl.project.get_list(limit=10)
        # filter by name
        >>> plist_2 = cl.project.get_list(name="copr")
        # search by string
        >>> plist_2 = cl.project.get_list(name="copr")


