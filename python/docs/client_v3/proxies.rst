Proxies
=======

User interface is separated among multiple proxy classes such as ``ProjectProxy``, ``BuildProxy``, etc,
which provide API operations on given resource.


General
-------

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
