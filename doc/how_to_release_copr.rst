.. _how_to_release_copr:

How to release Copr
===================

Go through this page well before you will do the release. Maybe you will want to do some steps in different order, and in any case, it's good to know what's ahead.

Keep amending this page if you find something not matching reality or expectations.

Tag untagged packages that have changes in them
-----------------------------------------------

Run::

    releng/show-untagged-commits

and walk the directories of packages listed. In each directory, call::

    rpkg tag
    rpkg push

Build packages
--------------

Build all packages::

    releng/build-packages @copr/copr

Upgrade -dev machines
---------------------

Check that .repo files correctly points to ``@copr/copr``. And run on batcave01.phx2.fedoraproject.org (if you do not have account there ask Mirek or somebody from fedora-infra)::

    sudo rbac-playbook -l copr-be-dev.cloud.fedoraproject.org groups/copr-backend.yml

    sudo rbac-playbook -l copr-keygen-dev.cloud.fedoraproject.org groups/copr-keygen.yml

    sudo rbac-playbook -l copr-fe-dev.cloud.fedoraproject.org groups/copr-frontend-cloud.yml

    sudo rbac-playbook -l copr-dist-git-dev.fedorainfracloud.org groups/copr-dist-git.yml


Note: if need manually run DB upgrade on frontend::

    sudo su - copr-fe

    alembic upgrade head

Note: If there is a new version of copr-rpmbuild, run this on backend::

    redis-cli
    127.0.0.1:6379> FLUSHALL
    cleanup_vm_nova.py
    systemctl restart copr-backend


Call for QA
-----------

Move MODIFIED+ bugzillas to ON_QA.

Ask people to test, verify bugs, and generally help with QA. They will ignore it but you will feel good about giving them a chance.

Test
----

Run :ref:`beaker_tests` and check the results.


Release python-copr to PyPi
---------------------------

Make sure you have `~/.pypirc` correctly set up and run::

    version=<current_pkg_version> /usr/bin/python setup.py sdist --format=gztar upload

Substitute `<current_pkg_version>` with the current package version.

If you cannot run that, tell somebody with access to run that (msuchy has access).

Build packages for production
-----------------------------

Make sure that ``releng/releasers.ini`` has up to date list of branches.

Make sure you are co-maintainer of those packages in Fedora.

Run::

    rm -r /tmp/rpkg

    git checkout <latest-python-tag>
    rpkg --path python srpm --outdir /tmp/rpkg
    releng/fedora-release git-all /tmp/rpkg/python-copr*.src.rpm

    git checkout <latest-cli-tag>
    rpkg --path cli srpm --outdir /tmp/rpkg
    releng/fedora-release git-all /tmp/rpkg/copr-cli*.src.rpm

    git checkout <latest-frontend-tag>
    rpkg --path frontend srpm --outdir /tmp/rpkg
    releng/fedora-release git /tmp/rpkg/copr-frontend*.src.rpm

    git checkout <latest-backend-tag>
    rpkg --path backend srpm --outdir /tmp/rpkg
    releng/fedora-release git /tmp/rpkg/copr-backend*.src.rpm

    git checkout <latest-distgit-tag>
    rpkg --path dist-git srpm --outdir /tmp/rpkg
    releng/fedora-release git /tmp/rpkg/copr-dist-git*.src.rpm

    git checkout <latest-keygen-tag>
    rpkg --path keygen srpm --outdir /tmp/rpkg
    releng/fedora-release git /tmp/rpkg/copr-keygen*.src.rpm

    git checkout <latest-selinux-tag>
    rpkg --path selinux srpm --outdir /tmp/rpkg
    releng/fedora-release git /tmp/rpkg/copr-selinux*.src.rpm

    git checkout <latest-prunerepo-tag>
    rpkg --path prunerepo srpm --outdir /tmp/rpkg
    releng/fedora-release git /tmp/rpkg/prunerepo*.src.rpm

    git checkout <latest-common-tag>
    rpkg --path common srpm --outdir /tmp/rpkg
    releng/fedora-release git /tmp/rpkg/python-copr-common*.src.rpm

    git checkout <latest-srpm-tag>
    rpkg --path rpmbuild srpm --outdir /tmp/rpkg
    releng/fedora-release git /tmp/rpkg/copr-rpmbuild*.src.rpm

And create erratas in `Bodhi <https://bodhi.fedoraproject.org/>`_.

Generate documentation
----------------------

Generate `Copr project documentation <https://docs.pagure.org/copr.copr/>`_

::

    cd doc
    ./update_docs.sh

Generate package specific documentation by going to:

* https://readthedocs.org/projects/copr-rest-api/

* https://readthedocs.org/projects/copr-backend/

* https://readthedocs.org/projects/copr-keygen/

* https://readthedocs.org/projects/python-copr/

And hitting "Build" button for each of those projects.

If schema was modified you should generate new Schema documentation.

Prepare release notes
---------------------

Go over bugs, which were resolved. Write some nice announce.

Schedule outage
---------------

Schedule outage even if it has to happen in the next 5 minutes!

Follow the instructions in `Outage SOP <https://docs.pagure.org/infra-docs/sysadmin-guide/sops/outage.html#id1>`_.

Upgrade production machines
---------------------------

It is advised to stop ``copr-backend.service`` before upgrading production machines to avoid failing
builds due to temporarily having installed incompatible versions of Copr packages.

Run on batcave01.phx2.fedoraproject.org (if you do not have account there ask Mirek or somebody from fedora-infra)::

    sudo rbac-playbook -l copr-be.cloud.fedoraproject.org groups/copr-backend.yml

    sudo rbac-playbook -l copr-keygen.cloud.fedoraproject.org groups/copr-keygen.yml

    sudo rbac-playbook -l copr-fe.cloud.fedoraproject.org groups/copr-frontend-cloud.yml

    sudo rbac-playbook -l copr-dist-git.fedorainfracloud.org groups/copr-dist-git.yml

Note: You shouldn't need to upgrade DB manually, playbook covers it.

Note: If there is a new version of copr-rpmbuild, throw away all builders and reprovision them.

Test production machine
-----------------------

Just run some build and check if it succeeds.

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
