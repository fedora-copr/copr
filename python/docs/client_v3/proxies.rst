Proxies
=======

User interface is separated among multiple proxy classes such as ``ProjectProxy``, ``BuildProxy``, etc,
which provide API operations on given resource.

There are several methods available across majority (there are some corner cases where it wouldn't make sense)
of proxies. Naturally, all methods (e.g. ``auth_check``) from ``BaseProxy`` are available everywhere. Moreover,
proxies implement ``get`` method to get one specific object and ``get_list`` to get multiple objects that meet some
criteria (e.g. all successful builds from a project). When it makes sense, proxies also implement an ``edit`` method
that modifies an object. Exception for this is for example, a ``BuildProxy`` because it shouldn't be possible to
change a build. Similarly, most of the proxies have a ``delete`` method except for e.g. ``BuildChrootProxy``.


Base
----

.. autoclass:: copr.v3.proxies.BaseProxy
   :members:


Project
-------

.. autoclass:: copr.v3.proxies.project.ProjectProxy
   :members:


Build
-----

.. autoclass:: copr.v3.proxies.build.BuildProxy
   :members:


Package
-------

.. autoclass:: copr.v3.proxies.package.PackageProxy
   :members:


Module
------

.. autoclass:: copr.v3.proxies.module.ModuleProxy
   :members:


Project Chroot
--------------

.. autoclass:: copr.v3.proxies.project_chroot.ProjectChrootProxy
   :members:


Build Chroot
------------

.. autoclass:: copr.v3.proxies.build_chroot.BuildChrootProxy
   :members:
