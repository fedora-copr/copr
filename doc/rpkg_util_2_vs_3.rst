:orphan:

.. _rpkg_util_v3:

The rpkg-util v2 vs v3 differences
==================================

The major difference is that the ``auto_pack =`` configuration option was
dropped in the ``rpkg`` utility, and namely that even the default behavior
(``auto_pack = True``) was changed entirely (after a long period of feature
deprecation).

So, while for quite some time you've probably seen builds succeeding, and output
similar to the following one (in source RPM ``builder-live.log`` files)::

    ...
    Running: rpkg srpm --outdir /var/lib/copr-rpmbuild/results --spec /var/lib/copr-rpmbuild/workspace/workdir-p7s1qop1/copr-hello
    ...
    stdout: Wrote: /var/lib/copr-rpmbuild/results/example.spec
    Wrote: /var/lib/copr-rpmbuild/results/example-1.0.13.tar.gz
    setting SOURCE_DATE_EPOCH=1518912000
    Wrote: /var/lib/copr-rpmbuild/results/example-1.0.13-1.fc34.src.rpm
    stderr: auto-packing: This function is deprecated and will be removed in a future release.

Note the **deprecation error** output!  But newly you see build failures, and output
like::

    ...
    Running: rpkg srpm --outdir /var/lib/copr-rpmbuild/results --spec /var/lib/copr-rpmbuild/workspace/workdir-49_sbnvg/copr-hello
    ...
    rc: 0
    stdout: Wrote: /var/lib/copr-rpmbuild/results/example.spec
    stderr: error: Bad source: /var/lib/copr-rpmbuild/results/example-1.0.13.tar.gz: No such file or directory
    Failed to execute command.

    Output: ['example.spec']

Or even something like::

    Running: rpkg srpm --outdir /var/lib/copr-rpmbuild/results --spec /var/lib/copr-rpmbuild/workspace/workdir-ffz7kky4/copr-hello
    ...
    rc: 1
    stdout: Wrote: /var/lib/copr-rpmbuild/results/example.spec
    stderr: error: Bad source: /var/lib/copr-rpmbuild/results/example-1.0.13.tar.gz: No such file or directory

    Copr build error: error: Bad source: /var/lib/copr-rpmbuild/results/example-1.0.13.tar.gz: No such file or directory

The utility in ``v3`` version also stopped automatically loading the
``rpkg.macros`` file stored in git repository.   Newly, one must tell the
utility `where the rpkg.macros file resides`_.  That's done using the git-root
``rpkg.conf`` file::

    [rpkg]
    user_macros = "${git_props:root}/rpkg.macros"


How am I supposed to fix the ``auto_pack`` issue
------------------------------------------------

First, if you build your package from a DistGit instance (e.g. from
``src.fedoraproject.org``, ``git.centos.org``, etc.), you are encouraged to use
the :ref:`Copr DistGit build method <dist-git method>`.

If you build from a git forge (GitHub, GitLab, ...) and you see build failures
like those above, the problem is most likely that your spec file is not using
the ``{{{ ... }}}`` templates, and you rely on the already removed ``auto_pack =
True`` feature.

Please take a look at the `rpkg-util documentation`_, and perhaps get an
inspiration from the `example commit`_ which makes the package compatible with
both rpkg-util **v2** and **v3**.

If for any reason you can not use the new `rpkg-util` syntax, take a look at the
:ref:`other source methods<scm_ref>` Copr supports.


.. _`rpkg-util documentation`: https://pagure.io/rpkg-util
.. _`example commit`: https://pagure.io/copr/copr-hello/c/739ff9910ee8a9c76d7e97de2f6176106dc19a09?branch=rpkg-util
.. _`DistGit`: https://github.com/release-engineering/dist-git
.. _`where the rpkg.macros file resides`: https://docs.pagure.org/rpkg-util/v3/macro_reference.html#user-defined-macros
