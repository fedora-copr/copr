.. _how_to_release_copr:

How to release Copr
===================

Go through this page well before you will do the release. Maybe you
will want to do some steps in different order, and in any case, it's
good to know what's ahead.

Keep amending this page if you find something not matching reality or expectations.


Pre-release
-----------

The goal is to do as much work pre-release as possible while focusing
only on important things and not creating a work overload with tasks,
that can be done post-release.


Tag untagged packages that have changes in them
...............................................

Make sure you are on the ``main`` branch and that it is up-to-date::

  git checkout main
  git pull --rebase

Run::

    tito report --untagged-commits

and walk the directories of packages listed, and tag them. During development,
we sometimes put `.dev` suffix into our packages versions. See what packages has
such version::

    cat ./.tito/packages/* |grep ".dev"

If a package has `.dev` suffix, manually increment its version::

    tito tag --use-version X.Y

For others, new version can be bumped automatically::

    tito tag

Make sure that the %changelog is nice and meaningful, i.e. remove the
`frontend:`, `rpmbuild:`, etc. prefixes and filter-out entries which are not
interesting for the package end-users (git-log != %changelog).  Later on, if
properly polished, the %changelogs' contents may be used for filling the Bodhi
update text.

Push all new tags at once::

    git push --follow-tags origin


Build packages
..............

Build all the updated packages into ``@copr/copr`` copr project::

    copr build-package @copr/copr --nowait --name python-copr
    copr build-package @copr/copr --nowait --name copr-frontend
    ...


Upgrade -dev machines
.....................

Check that .repo files correctly points to ``@copr/copr``. And run on batcave01.iad2.fedoraproject.org (if you do not have account there ask Mirek or somebody from fedora-infra)::

    sudo rbac-playbook -l copr-be-dev.aws.fedoraproject.org \
                       manual/copr/copr-backend-upgrade.yml
    sudo rbac-playbook -l copr-be-dev.aws.fedoraproject.org groups/copr-backend.yml

    sudo rbac-playbook -l copr-keygen-dev.aws.fedoraproject.org \
                       manual/copr/copr-keygen-upgrade.yml
    sudo rbac-playbook -l copr-keygen-dev.aws.fedoraproject.org groups/copr-keygen.yml

    sudo rbac-playbook -l copr-fe-dev.aws.fedoraproject.org \
                       manual/copr/copr-frontend-upgrade.yml
    sudo rbac-playbook -l copr-fe-dev.aws.fedoraproject.org groups/copr-frontend.yml

    sudo rbac-playbook -l copr-dist-git-dev.aws.fedoraproject.org \
                       manual/copr/copr-dist-git-upgrade.yml
    sudo rbac-playbook -l copr-dist-git-dev.aws.fedoraproject.org groups/copr-dist-git.yml

.. note::

    If there is a new version of copr-rpmbuild, follow the
    :ref:`terminate_os_vms` and :ref:`terminate_resalloc_vms` instructions.

Make sure expected versions of Copr packages are installed on the dev
instances::

    ./releng/run-on-all-infra --devel 'rpm -qa | grep copr'


Call for QA
...........

Move `MODIFIED+ <https://bugzilla.redhat.com/buglist.cgi?bug_status=POST&bug_status=MODIFIED&product=Copr>`_
bugzillas to ON_QA.

Ask people to test, verify bugs, and generally help with QA. They will ignore it but you will feel good about giving them a chance.


Test
....

Run the :ref:`sanity tests<sanity_tests>` from a Podman container (alternatively
this can be run also from :ref:`Beaker directly <beaker_tests>`).


.. _build_packages_for_production:

Build packages for production
.............................

Make sure that ``.tito/releasers.conf`` has up to date list of branches.

Make sure you are co-maintainer of those packages in Fedora::

    copr-backend
    copr-cli
    copr-dist-git
    copr-frontend
    copr-keygen
    copr-messaging
    copr-mocks
    copr-rpmbuild
    copr-selinux
    python-copr
    python-copr-common

For each package do::

    cd <package subdir>
    # run this for python-copr and copr-cli
    tito release fedora-git-clients
    # run this for copr-messaging package
    tito release fedora-git-messaging
    # run this for other (server) packages (copr-frontend, copr-backend, ...)
    tito release fedora-git

.. note::

    Koji doesn't automatically put successfully built packages into the buildroot
    for the following builds and therefore you can easily encounter failures of
    ``copr-cli`` or copr server pacakges because of a missing dependency to
    ``python3-copr`` or ``python3-copr-common`` that you have just built in Koji. To
    fix this, you need to create a
    `Bodhi override for those dependencies <https://fedoraproject.org/wiki/Bodhi/BuildRootOverrides>`_.
    It takes up to 30 minutes to for the override to be available in the buildroot::

        koji wait-repo f34-build --build=python-copr-common-0.13-1.fc34

.. warning::

   Tito doesn't work properly with more than one source, and when releasing
   backend, it removes ``test-data-copr-backend-2.tar.gz`` from the DistGit
   ``sources`` file. Until it gets resolved,
   `fix this way <https://src.fedoraproject.org/rpms/copr-backend/c/65e663d23e5caaac01123bf8c0fc0e636fd08ee3>`_.


Submit packages into stg infra tags
...................................

Submit the pacakges into `Infra tags repo <https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/infra-repo/>`_.
If you don't have permissions to do this, try `@praiskup` or `@frostyx`, or someone on ``#fedora-admin`` libera.chat channel.

.. warning::

    There's a long-term `race in Koji <https://pagure.io/fedora-infrastructure/issue/9504>`_.
    If you plan to submit more packages (and likely you do), submit all **but
    one** at once.  Keep one package to be submitted later, when other tasks are
    already processed to "poke through" potencially broken repository.

We have wrappers around the ``koji`` tool for this.  First we "tag" the packages
into the infra staging repo like (`example stg infra repo`_)::

    ./releng/koji-infratag-staging  copr-rpmbuild-0.53-1.fc34

Now give the Koji automation some time to process the request above (package
signing, and preparing a new repository).  Wait until the package is available
in the repo::

    ./releng/koji-infratag-available --stg --wait copr-rpmbuild-0.53-1.fc34.x86_64.rpm

When the packages are ready, you can install the packages on the devel copr
stack (staging infra repository is enabled there by default).  Now for example
you can re-run te tests against the soon-to-be production packages.

Besides the obvious server packages, don't forget to submit also
`python-copr` and `copr-cli` (we use it on the backend).

Prepare release notes
.....................

Go over bugs, which were resolved. Write some nice announce. It is useful to prepare the release notes beforehand
because developers usualy don't remember what they worked on and therefore don't know what to test once
production instances are upgraded. Sharing the prepared notes with team members before doing the actuall release
is appreciated.

See :ref:`previous release notes <release_notes>` and try to format
them in the same way. Then create a pull request with this release
notes against Copr git repository.


Schedule and announce the outage
................................

.. warning::

    Schedule outage even if it has to happen in the next 5 minutes!

Get faimiliar with the `Fedora Outage SOP <https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/outage/>`_.
In general, please follow these steps:

1. Prepare the infrastructure ticket similar to `this old one <https://pagure.io/fedora-infrastructure/issue/10854>`_.

2. Send email to `copr-devel`_ mailing list informing about an upcomming
   release. We usually copy-paste text of the infrastructure ticket created in a
   previous step. Don't forget to put a link to the ticket at the end of the
   email.  See the `example <https://lists.fedoraproject.org/archives/list/copr-devel@lists.fedorahosted.org/message/FVVX3Y7IVRTFW3NYVBTWX3AK3BHNRATX/>`_.

3. Send ``op #fedora-buildsys MyIrcNick`` message to ``ChanServ`` on
   libera.chat to get the OP rights, and then adjust the channel title so it
   starts with message similar to::

        Planned outage 2022-08-17 20:00 UTC - https://pagure.io/fedora-infrastructure/issue/10854

4. Create a new "planned" `Fedora Status SOP`_ entry.


Release window
--------------

If all the pre-release preparations were done meticulously and everything
was tested properly, the release window shouldn't take more than ten
minutes. That is, if nothing goes terribly sideways...


Let users know
--------------

1. Change the "planned" `Fedora Status SOP`_ entry into an "ongoing" entry.

2. Announce on ``#fedora-buildsys``, change title like
   ``s/Planned outage ../OUTAGE NOW .../`` and send some message like
   ``WARNING: The scheduled outage just begings!``.


Production infra tags
---------------------

.. warning::

    The Koji race mentioned above is here, too.  Delay moving one of the NVRs a
    bit!

You can now move the packages to production infra repo.  Note that the
production builder machines install/update the ``copr-rpmbuild`` package from
the production infra repo *automatically*;  so you probably want to wait with
tagging (at least for some of the packages) till it is 100% safe action (during
outage window, as old copr infra stack might be incompatible with updated
rpmbuild, e.g.). ::

    ./releng/koji-infratag-move-prod copr-rpmbuild-0.53-1.fc34 ...

This takes some time. Wait until the packages are available in the infra repo::

    ./releng/koji-infratag-available --prod --wait copr-rpmbuild-0.53-1.fc34.x86_64.rpm ...

Or you can check the repository manually, e.g.
https://kojipkgs.fedoraproject.org/repos-dist/f35-infra/latest/x86_64/


Upgrade production machines
...........................

It is advised to stop ``copr-backend.target`` before upgrading production machines to avoid failing
builds due to temporarily having installed incompatible versions of Copr packages.

Run on batcave01.iad2.fedoraproject.org (if you do not have account there ask Mirek or somebody from fedora-infra)::

    sudo rbac-playbook -l copr-be.aws.fedoraproject.org \
                       manual/copr/copr-backend-upgrade.yml
    sudo rbac-playbook -l copr-be.aws.fedoraproject.org groups/copr-backend.yml

    sudo rbac-playbook -l copr-keygen.aws.fedoraproject.org \
                       manual/copr/copr-keygen-upgrade.yml
    sudo rbac-playbook -l copr-keygen.aws.fedoraproject.org groups/copr-keygen.yml

    sudo rbac-playbook -l copr-fe.aws.fedoraproject.org \
                       manual/copr/copr-frontend-upgrade.yml
    sudo rbac-playbook -l copr-fe.aws.fedoraproject.org groups/copr-frontend.yml

    sudo rbac-playbook -l copr-dist-git.aws.fedoraproject.org \
                       manual/copr/copr-dist-git-upgrade.yml
    sudo rbac-playbook -l copr-dist-git.aws.fedoraproject.org groups/copr-dist-git.yml

.. note::

    You shouldn't need to upgrade DB manually, playbook covers it.

Make sure expected versions of Copr packages are installed on the
production instances::

    ./releng/run-on-all-infra 'rpm -qa | grep copr'

And make sure there is no unexpected update available::

    ./releng/run-on-all-infra 'dnf copr list'


Test production machine
.......................

Run post-release beaker test::

    [root@test-env ~]$ cd /root/copr/beaker-tests/Sanity/copr-cli-basic-operations/
    [root@test-env ~]$ ./runtest-production.sh

or just run some build and check if it succeeds.


Post-release
------------

At this moment, every Copr service should be up and running.


Generate documentation
......................

Generate `Copr project documentation <https://docs.pagure.org/copr.copr/>`_

::

    cd doc
    ./update_docs.sh

Generate package specific documentation by going to:

* https://readthedocs.org/projects/copr-backend/

* https://readthedocs.org/projects/copr-keygen/

* https://readthedocs.org/projects/copr-messaging/

* https://readthedocs.org/projects/copr-rest-api/

* https://readthedocs.org/projects/python-copr/

And hitting "Build" button for each of those projects.

If schema was modified you should generate new Schema documentation.


Announce the end of the release
...............................

1. Remove the "Outage" note from the ``#fedora-buildsys`` title.

2. Send a message on ``fedora-buildsys`` that the outage is over!

3. Send email to `copr-devel`_ mailing list.  If there is some important change
   you can send email to fedora devel mailing list too.  Mention the link to the
   "Highlights from XXXX-XX-XX release" documentation page.

4. Propose a new "highlights" post for the `Fedora Copr Blog`_,
   see `the example
   <https://github.com/fedora-copr/fedora-copr.github.io/pull/55/files>`_.

5. Close the Fedora Infra ticket.

6. Change the "ongoing" `Fedora Status SOP`_ entry into a "resolved" one.


Release packages to PyPI
........................

Make sure you have `~/.pypirc` correctly set up and run::

    dnf install twine
    python3 setup.py sdist
    twine upload dist/<NAME-VERSION>.tar.gz

If you cannot run that, tell somebody with access to run that (msuchy, praiskup,
jkadlcik).

This needs to be run for `copr-common`, `python`, `copr-cli` and
`copr-messaging`.


Submit Bodhi updates
....................

Create updates in `Bodhi <https://bodhi.fedoraproject.org/>`_ for
:ref:`every package built in Koji <build_packages_for_production>`.

It is useful to do updates in batches, e.g. to group several packages into one
update.  You can do this by ``fedpkg update``, with the following template::

    [ copr-backend-1.127-1.fc31, copr-frontend-1.154-1.fc31]
    type=enhancement
    notes=copr-frontend

        - change 1 in frontend
        - change 2 in frontend

        copr-backend

        - change 1 in backend
        - change 2 in backend

It is often good idea to put new (filtered) ``%changelogs`` entries there.


Final steps
...........

Check if the `MODIFIED bugs <https://bugzilla.redhat.com/buglist.cgi?bug_status=POST&bug_status=MODIFIED&classification=Community&list_id=4678039&product=Copr&query_format=advanced>`_
(that are not ON_QA) are fixed in released Copr or not, move them ON_QA.


Change status of all `ON_DEV, ON_QA, VERIFIED, and RELEASE_PENDING bugs <https://bugzilla.redhat.com/buglist.cgi?bug_status=ON_QA&bug_status=VERIFIED&bug_status=RELEASE_PENDING&classification=Community&list_id=4678045&product=Copr&query_format=advanced>`_
to CLOSED/CURRENTRELEASE with comment like 'New Copr has been released.'


Fix this document to make it easy for the release nanny of the next release to use it.

.. _`Copr release directory`: https://releases.pagure.org/copr/copr
.. _`copr-devel`: https://lists.fedoraproject.org/archives/list/copr-devel@lists.fedorahosted.org/
.. _`Fedora Status SOP`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/status-fedora/
.. _`example stg infra repo`: https://kojipkgs.fedoraproject.org/repos-dist/f36-infra-stg/
.. _`Fedora Copr Blog`: https://fedora-copr.github.io/
