.. _how_to_release_copr:

How to release Copr
===================

Go through this page well before you will do the release. Maybe you will want to do some steps in different order, and in any case, it's good to know what's ahead.

Keep amending this page if you find something not matching reality or expectations.

Tag untagged packages that have changes in them
-----------------------------------------------

Run::

    tito report --untagged-commits

and walk the directories of packages listed. In each directory, call::

    tito tag

push them::

    git push --follow-tags origin


Build packages
--------------

Build all the updated packages into ``@copr/copr`` copr project::

    copr build-package @copr/copr --name python-copr
    copr build-package @copr/copr --name copr-frontend
    ...


Upgrade -dev machines
---------------------

Check that .repo files correctly points to ``@copr/copr``. And run on batcave01.phx2.fedoraproject.org (if you do not have account there ask Mirek or somebody from fedora-infra)::

    sudo rbac-playbook -l copr-be-dev.cloud.fedoraproject.org \
                       manual/copr/copr-backend-upgrade.yml
    sudo rbac-playbook -l copr-be-dev.cloud.fedoraproject.org groups/copr-backend.yml

    sudo rbac-playbook -l copr-keygen-dev.cloud.fedoraproject.org \
                       manual/copr/copr-keygen-upgrade.yml
    sudo rbac-playbook -l copr-keygen-dev.cloud.fedoraproject.org groups/copr-keygen.yml

    sudo rbac-playbook -l copr-fe-dev.cloud.fedoraproject.org \
                       manual/copr/copr-frontend-upgrade.yml
    sudo rbac-playbook -l copr-fe-dev.cloud.fedoraproject.org groups/copr-frontend-cloud.yml

    sudo rbac-playbook -l copr-dist-git-dev.fedorainfracloud.org \
                       manual/copr/copr-dist-git-upgrade.yml
    sudo rbac-playbook -l copr-dist-git-dev.fedorainfracloud.org groups/copr-dist-git.yml


Note: If there is a new version of copr-rpmbuild, follow the
:ref:`terminate_os_vms` and :ref:`terminate_resalloc_vms` instructions.


Call for QA
-----------

Move `MODIFIED+ <https://bugzilla.redhat.com/buglist.cgi?bug_status=POST&bug_status=MODIFIED&product=Copr>`_
bugzillas to ON_QA.

Ask people to test, verify bugs, and generally help with QA. They will ignore it but you will feel good about giving them a chance.

Test
----

Run :ref:`beaker_tests` and check the results.


Release packages to PyPI
------------------------

Make sure you have `~/.pypirc` correctly set up and run::

    dnf install twine
    python3 setup.py sdist
    twine upload dist/<NAME-VERSION>.tar.gz

If you cannot run that, tell somebody with access to run that (msuchy, praiskup,
jkadlcik).

This needs to be run for `copr-common`, `python`, `copr-cli` and
`copr-messaging`.

.. _build_packages_for_production:

Build packages for production
-----------------------------

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

And submit them into `Infra tags repo <https://fedora-infra-docs.readthedocs.io/en/latest/sysadmin-guide/sops/infra-repo.html>`_.
Not even every fedora infra member can to this, ping clime or ask on ``#fedora-admin``.


Submit Bodhi updates
--------------------

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


Generate documentation
----------------------

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

Prepare release notes
---------------------

Go over bugs, which were resolved. Write some nice announce. It is useful to prepare the release notes beforehand
because developers usualy don't remember what they worked on and therefore don't know what to test once
production instances are upgraded. Sharing the prepared notes with team members before doing the actuall release
is appreciated.

Schedule outage
---------------

Schedule outage even if it has to happen in the next 5 minutes!

Follow the instructions in `Outage SOP <https://docs.pagure.org/infra-docs/sysadmin-guide/sops/outage.html#id1>`_.

Upgrade production machines
---------------------------

It is advised to stop ``copr-backend.service`` before upgrading production machines to avoid failing
builds due to temporarily having installed incompatible versions of Copr packages.

Run on batcave01.phx2.fedoraproject.org (if you do not have account there ask Mirek or somebody from fedora-infra)::

    sudo rbac-playbook -l copr-be.cloud.fedoraproject.org \
                       manual/copr/copr-backend-upgrade.yml
    sudo rbac-playbook -l copr-be.cloud.fedoraproject.org groups/copr-backend.yml

    sudo rbac-playbook -l copr-keygen.cloud.fedoraproject.org \
                       manual/copr/copr-keygen-upgrade.yml
    sudo rbac-playbook -l copr-keygen.cloud.fedoraproject.org groups/copr-keygen.yml

    sudo rbac-playbook -l copr-fe.cloud.fedoraproject.org \
                       manual/copr/copr-frontend-upgrade.yml
    sudo rbac-playbook -l copr-fe.cloud.fedoraproject.org groups/copr-frontend-cloud.yml

    sudo rbac-playbook -l copr-dist-git.fedorainfracloud.org \
                       manual/copr/copr-dist-git-upgrade.yml
    sudo rbac-playbook -l copr-dist-git.fedorainfracloud.org groups/copr-dist-git.yml

Note: You shouldn't need to upgrade DB manually, playbook covers it.


Test production machine
-----------------------

Run post-release beaker test::

    [root@test-env ~]$ cd /root/copr/beaker-tests/Sanity/copr-cli-basic-operations/
    [root@test-env ~]$ ./runtest-production.sh

or just run some build and check if it succeeds.

Announce the release
--------------------

Send email to copr-dev mailing list. If there is some important change you can send email to fedora devel mailing list too.

Post release
------------

Check if the `MODIFIED bugs <https://bugzilla.redhat.com/buglist.cgi?bug_status=POST&bug_status=MODIFIED&classification=Community&list_id=4678039&product=Copr&query_format=advanced>`_
(that are not ON_QA) are fixed in released Copr or not, move them ON_QA.


Change status of all `ON_DEV, ON_QA, VERIFIED, and RELEASE_PENDING bugs <https://bugzilla.redhat.com/buglist.cgi?bug_status=ON_QA&bug_status=VERIFIED&bug_status=RELEASE_PENDING&classification=Community&list_id=4678045&product=Copr&query_format=advanced>`_
to CLOSED/CURRENTRELEASE with comment like 'New Copr has been released.'


Fix this document to make it easy for the release nanny of the next release to use it.

.. _`Copr release directory`: https://releases.pagure.org/copr/copr
