.. warning::
    Client version 2 is obsolete, please use Client version 3 instead.


Resources
~~~~~~~~~

Client represents API with two kinds of resources: Individuals and Collections. For example when we request
all projects with name `copr` we would receive collection :py:class:`~copr.client_v2.resources.ProjectList` resource:

    .. sourcecode:: python

        >>> from copr import create_client2_from_params
        # using dev server for test
        >>> cl = create_client2_from_params(root_url="http://copr-fe-dev.cloud.fedoraproject.org/")

        >>> projects = cl.projects.get_list(name="copr", limit=3)
        >>> for p in projects:
        >>>    print(p)
        <Project #1: msuchy/copr>
        <Project #1503: vgologuz/copr>
        <Project #2796: mosquito/copr>


Access to elements in collection is done through iterator interface. Since API limits number of elements
retrieved in the one request, collections has method `next_page()` to retrieve more objects:

    .. sourcecode:: python

        >>> more_projects = projects.next_page()
        >>> for p in more_projects:
        >>>    print(p)
        <Project #2805: esmil/copr>
        <Project #4266: frostyx/copr>



If we already knew project id we could get an individual :py:class:`~copr.client_v2.resources.Project` resource:

    .. sourcecode:: python

        >>> p = cl.projects.get_one(1835)

Individual resource allows to directly access entity properties and also provides some helper functions:

    .. sourcecode:: python

        >>> print(p.owner, p.name)
        (u'saltstack', u'salt')
        # obtain active build chroots
        >>> print("\n".join(map(str, p.get_project_chroot_list())))
        <Project chroot: fedora-22-x86_64, additional packages: [], comps size if any: 0>
        <Project chroot: fedora-22-i386, additional packages: [], comps size if any: 0>
        # change project description (require auth)
        >>> p.description = u"Hello world!"
        >>> p.update()
        # instead of cl.projects.update(p._entity)
