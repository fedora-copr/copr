.. warning::
    Client version 2 is obsolete, please use Client version 3 instead.


.. _`mock-chroot-info`:

Mock chroot
===========

Mock chroot resources represents available chroots for builds. API provides only read-only access,
since configuration of the build chroots is done by the service administrator.

Access to the mock chroots is done through :py:meth:`~copr.client_v2.client.CoprClient.mock_chroots`.
property of initialized :py:class:`~copr.client_v2.client.CoprClient`. That property is an instance of
:py:class:`~copr.client_v2.handlers.MockChrootHandle`. Mock chroots are represented by
:py:class:`~copr.client_v2.resources.MockChroot` class.

.. _mock-chroot-attributes:

Mock chroot entity attributes
-----------------------------


.. copied from frontend docs, don't forget to update

==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
name                str                  chroot name
os_release          str                  name of distribution system, e.g.: epel, fedora
os_version          str                  version of distribution system, e.g.: 7, 22
arch                str                  architecture of distribution, e.g.: i386, x86_64, ppc64le
is_active           bool                 defines if this chroot is available for builds
==================  ==================== ===============

.. note::
    all following examples assume that we use ``cl``
    as an instance of :py:class:`.client_v2.client.CoprClient`

Get mock chroot list
--------------------

.. sourcecode:: python

    >>> mlist = map(str, cl.mock_chroots.get_list(active_only=True))
    >>> print("\n".join(map(str, mlist)))
    <Mock chroot: epel-6-i386 is active: True>
    <Mock chroot: epel-6-x86_64 is active: True>
    <Mock chroot: epel-5-i386 is active: True>
    ...

Get single mock chroot
----------------------

.. sourcecode:: python

    >>> mc = cl.mock_chroots.get_one("fedora-22-i386")
    >>> print(mc)
    <Mock chroot: fedora-22-i386 is active: True>
    >>> print(mc.name,  mc.os_release, mc.os_version, mc.arch)
    (u'fedora-22-i386', u'fedora', u'22', u'i386')
