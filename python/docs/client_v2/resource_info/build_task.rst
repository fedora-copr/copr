.. warning::
    Client version 2 is obsolete, please use Client version 3 instead.


.. _build-task-info:

Build task
==========

Build task represents information about individual build tasks. One task is responsible for one chroot.

Access to the build tasks is done through :py:meth:`~copr.client_v2.client.CoprClient.build_tasks`.
property of initialized :py:class:`~copr.client_v2.client.CoprClient`. That property is an instance of
:py:class:`~copr.client_v2.handlers.BuildTaskHandle`.


It may be more convenient to access build tasks in context of a build
using method :py:meth:`~copr.client_v2.resources.Build.get_build_tasks`
of  access build tasks in context of a project
using method :py:meth:`~copr.client_v2.resources.Project.get_build_tasks`

Build tasks are represented by
:py:class:`~copr.client_v2.resources.BuildTask` class.

.. _build-task-attributes:

Build task entity attributes
----------------------------

.. copied from frontend docs, don't forget to update

==================  ==================== ===============
Field               Type                 Description
==================  ==================== ===============
chroot_name         str                  chroot name
build_id            int                  unique build identifier
state               str                  current build task state
started_on          int(unixtime UTC)    time when the build chroot started
ended_on            int(unixtime UTC)    time when the build chroot ended
git_hash            str                  hash of the git commit in dist-git used for the build
result_dir_url      str(URL)             location of the build results
==================  ==================== ===============


.. note::
    Build Task doesn't currently support any modifications,
    so all fields are read-only.


.. note::
    all following examples assume that we use ``cl``
    as an instance of :py:class:`.client_v2.client.CoprClient`,
    ``p`` as an instance of  :py:class:`~copr.client_v2.resources.Project`,
    ``b`` as an instance of  :py:class:`~copr.client_v2.resources.Build`,


Get build tasks list
--------------------

.. sourcecode:: python

    >>> bt_list_1 = cl.build_tasks.get_list(state=BuildStateValues.FAILED, limit=5)
    >>> map(str, bt_list_1)
    ['<Build task #17-fedora-18-x86_64, state: failed>',
     '<Build task #17-fedora-18-i386, state: failed>',
     '<Build task #17-fedora-19-x86_64, state: failed>',
     '<Build task #17-fedora-19-i386, state: failed>',
     '<Build task #107850-fedora-23-x86_64, state: failed>']

    # using project object
    >>> bt_list_2 = p.get_build_tasks(limit=5)
    >>> map(str, bt_list_2)
    ['<Build task #86705-epel-6-i386, state: succeeded>',
     '<Build task #86705-epel-6-x86_64, state: failed>',
     '<Build task #86705-fedora-rawhide-x86_64, state: succeeded>',
     '<Build task #86705-fedora-rawhide-i386, state: failed>',
     '<Build task #86705-fedora-20-x86_64, state: succeeded>']

    # using build object
    >>> bt_list_3 = b.get_build_tasks(limit=5)
    >>> map(str, bt_list_3)
    ['<Build task #87165-epel-6-i386, state: failed>',
     '<Build task #87165-epel-6-x86_64, state: failed>',
     '<Build task #87165-fedora-rawhide-x86_64, state: succeeded>',
     '<Build task #87165-fedora-rawhide-i386, state: succeeded>',
     '<Build task #87165-fedora-20-x86_64, state: succeeded>']

Get single build task
---------------------


.. sourcecode:: python

    >>> bt = cl.build_tasks.get_one(106897, "epel-6-i386")
    >>> print(bt.state, bt.result_dir_url)
    (u'succeeded', u'http://copr-be-dev.cloud.fedoraproject.org/results/rineau/libQGLViewer-qt5/epel-6-i386/libQGLViewer-2.5.1-5.fc21')
