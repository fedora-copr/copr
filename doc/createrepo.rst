.. _createrepo:

When do we run createrepo
=========================

There are several situations when we need to update repository metadata in copr
repository.

We need to run createrepo when some build finishes so the built RPMs are
distributed to the repository end-users.  Similarly we need to update repodata
when some build is removed.

Also, there's no sophisticated "gating" mechanism in copr similar to Fedora's
Bodhi (aka ``updates`` vs ``updates-testing`` repositories).  The alternative
approach in Copr is to temporarily disable the "Auto Create Repo" feature (or
*ACR*).  With such configuration, copr instead creates the repodata in a
separate directory named ``devel`` -- so the subsequent builds still can be
built against previously finished builds.  With such configuration though, copr
doesn't re-generate the "production" repodata after each build automatically
(even though there freshly built RPMs, they are not visible in repos) so project
maintainers are fully responsible for recreating the "production" metadata
manually when it is appropriate (in the web-UI - in project overview, hit the
``Regenerate Repositories`` button).

The following table describes situations when we execute ``/bin/createrepo_c``.

+----------------------------------+------------------------------+--------------------------+--------------------------+
| situation                        | what copr dirs               | what chroots             | devel/normal repo        |
+==================================+==============================+==========================+==========================+
| new Project created              | main                         | all enabled              | ACR reflected            |
+----------------------------------+------------------------------+--------------------------+--------------------------+
| new chroot(s) enabled            | all                          | only related chroots     | ACR reflected            |
+----------------------------------+------------------------------+--------------------------+--------------------------+
| new (PR) copr dir                | the one just created         | all enabled              | ACR reflected            |
+----------------------------------+------------------------------+--------------------------+--------------------------+
| ACR disabled                     | all                          | all enabled              | devel                    |
+----------------------------------+------------------------------+--------------------------+--------------------------+
| ACR enable                       | all                          | all enabled              | normal                   |
+----------------------------------+------------------------------+--------------------------+--------------------------+
| post-build                       | affected                     | only related chroots     | ACR reflected            |
+----------------------------------+------------------------------+--------------------------+--------------------------+
| manual createrepo event          | all                          | all enabled              | non-devel only           |
+----------------------------------+------------------------------+--------------------------+--------------------------+
| delete build event               | affected                     | only related chroots     | both for prod packages   |
+----------------------------------+------------------------------+--------------------------+--------------------------+
| prunerepo script                 | affected                     | affected                 | normal                   |
+----------------------------------+------------------------------+--------------------------+--------------------------+

The ``copr dirs`` can be either the default project directory (e.g.
``jsmith/coolproject``), or pull-request directories (e.g.
``jsmith/coolproject:pr:100``).
