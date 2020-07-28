.. warning::
    Client version 2 is obsolete, please use Client version 3 instead.


.. _project-chroot-info:

Project chroot
==============

Projects Chroots allows to enable and disable target chroots and
modify project settings dedicated for specific chroots.

Access to the project chroots is done through :py:meth:`~copr.client_v2.client.CoprClient.project_chroots`.
property of initialized :py:class:`~copr.client_v2.client.CoprClient`. That property is an instance of
:py:class:`~copr.client_v2.handlers.ProjectChrootHandle`.

However it's usually more convenient to access project chroots
from an instance of :py:class:`~copr.client_v2.resources.Project`
using methods :py:meth:`~copr.client_v2.resources.Project.get_project_chroot_list` or
:py:meth:`~copr.client_v2.resources.Project.get_project_chroot`.

Chroot are represented by
:py:class:`~copr.client_v2.resources.ProjectChroot` class.

.. _project-chroot-attributes:

Project chroot entity attributes
--------------------------------

.. copied from frontend docs, don't forget to update

==================  ==================== ========= ===============
Field               Type                 Can edit? Description
==================  ==================== ========= ===============
name                string               no        chroot name
buildroot_pkgs      list of strings      yes       packages to be installed into the buildroot
comps               string               yes       content of the `comps.xml`_
comps_name          string               yes       name of the uploaded comps file
comps_len           int                  no        size of the uploaded comps file (bytes)
==================  ==================== ========= ===============

.. note::
    all following examples assume that we use ``cl``
    as an instance of :py:class:`.client_v2.client.CoprClient`
    and ``p`` as an instance of :py:class:`~copr.client_v2.resources.Project`

Get project chroots list
------------------------

.. sourcecode:: python

    >>> pc_list = cl.project_chroots.get_list(project=p)
    # or more simple
    >>> pc_list = p.get_project_chroot_list()
    >>>  map(str, pc_list)
    ['<Project chroot: fedora-21-x86_64, additional packages: [], comps size if any: 0>',
     '<Project chroot: epel-7-x86_64, additional packages: [], comps size if any: 0>']


Get one project chroot
----------------------

.. sourcecode:: python


    >>> pc = cl.project_chroots.get_one(project=p, name="fedora-23-x86_64")
    # or
    >>> pc = p.get_project_chroot("fedora-23-x86_64")
    >>> print(pc)
    <Project chroot: fedora-23-x86_64, additional packages: [], comps size if any: 0>

Modify project chroot
---------------------

.. sourcecode:: python

    >>> pc.buildroot_pkgs = ["scl-utils",]
    >>> pc.update()

Disable project chroot
----------------------
.. sourcecode:: python

    >>> pc.disable()


.. _comps.xml: https://fedorahosted.org/comps/
