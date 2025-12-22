.. _how_to_build_hotfix:

How to build hotfix
===================

This article explains how to build a hotfix package for deployment in productions.

An hotfix is a package that is equal to latest tagged package with selected patch applied.

Preparation
-----------

This is required if you are doing the first hotfix since last regular release. If somebody already did the hotfix, you can skip this section.

Create hotfix branch ($DATE is date of last release):

    git branch hotfix-$DATE

Return in history to commit that points to latest commit tagging packages for the release:

    git reset --hard $SHA1

Push the branch to remote:

    git push origin hotfix-$DATE:hotfix-$DATE

Edit `tito.props` to:

    tagger = tito.tagger.ReleaseTagger

optionally you can change even:

    builder = tito.builder.UpstreamBuilder

Backport fix
------------

If you skipped previous part because the branch exists then do:

   git checkout hotfix-$DATE

Apply the fix from `main` branch. $SHA1 is commit you want to backport.

    git cherry-pick -x $SHA1

Run:

    tito report --untagged-commits

and walk the directories of packages listed. For every SPEC file make sure that `Version` tag has `^hotfix` at the end.
This ensure that the hotfix version is higher than any rebuild in Fedora.

    1.1-5 < 1.1^hotfix-1

Tag every package that was listed in the step above:

    tito tag

Push the changes:

    git push --follow-tags origin

Build packages
--------------

FIXME

Now we can either follow
https://docs.pagure.org/copr.copr/how_to_release_copr.html#build-packages-for-production
(Work always, but is painfully long)

or

Create hotfix project in Copr itself. Enable this repo in production. Build there the hotfix and install from Copr.

