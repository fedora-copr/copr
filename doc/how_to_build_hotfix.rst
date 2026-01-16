.. _how_to_build_hotfix:

How to build hotfix
===================

This article explains how to build a hotfix package for deployment in productions.

An hotfix is a package that is equal to latest tagged package with selected patch applied.

Preparation
-----------

This is required if you are doing the first hotfix since last regular release. If somebody already did the hotfix, you can skip this section.

Create hotfix branch ($DATE is date of last release)::

    git branch hotfix-$DATE
    git checkout hotfix-$DATE

Return in history to commit that points to latest commit tagging packages for the release. If multiple packages were tagged during the release, choose the commit related to latest package in the release::

    git reset --hard $SHA1

Push the branch to remote::

    git push origin hotfix-$DATE:hotfix-$DATE

Commit the changes::

    git commit -a -m 'set up hotfix branch'

Backport fix
------------

If you skipped previous part because the branch exists then do::

   git checkout hotfix-$DATE

Apply the fix from `main` branch. $SHA1 is commit you want to backport::

    git cherry-pick -x $SHA1

Run::

    tito report --untagged-commits

and walk the directories of packages listed. For every SPEC file make sure that `Version` tag has `.hotfix.0` at the end.
This ensure that the hotfix version is higher than any rebuild in Fedora::

    1.1-5 < 1.1.hotfix.0-1

Tag every package that was listed in the step above::

    tito tag

Push the changes::

    git push --follow-tags origin

Build packages
--------------

At this point in time, we have those files most likely patched in production. So you can take a time and follow
how to `build packages`_.

When packages are build, you should run the Ansible playbook and make sure everything runs smoothly.

.. _`build_packages`: https://docs.pagure.org/copr.copr/how_to_release_copr.html#build-packages-for-production
