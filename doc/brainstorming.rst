.. _brainstorming:

Brainbox
========

This is just a page to collect brainwaves/ideas/evil-thoughts for Copr. 

Proposal of change
------------------

* move srpm-from-upstream generation (i.e. all build methods like URL, Tito, MockSCM, PyPI, Rubygems) to builders
* basically meaning, getting rid of copr-dist-git importer
* instead the builder would push built srpm into copr-dist-git through https with a client certificate
* the copr-dist-git would now have only one purpose - serve as a build history
* optionally setup another public dist-git where people can push and pull from freely as they are used to

Frontend
--------

* make link to /api page (Done)
* Extend APIs
* localize frontend (use Transifex)
* Meet Docstring standards for the code.
* Allow a repo author to optionally provide a url to the upstream source repo (visible to viewers)
* Allow a repo author to optionally provide a url to the spec file (visible to viewers)

Backend
-------

* change instance type by build request for more mem/procs/extend timeouts
   - use extra-vars?
   - need ansible 0.9?
* auto-timer/cleanup script for old instances that may have been orphaned
* prune out builders when we drop the number of them active
* LOADS of fixme and catching weird conditions
* make logging from mockremote more sane and consistent
* mock configs should be pushed to instances at creation time
   - single url to repos, not mirrorlists
* consider making each worker return job to a completed queue so the primary
  process can do other kinds of notification
* email notifications from backend?
* work on a way to find and cancel a specific build that's happening other than just killing the instance
* determine if it is properly checking the timeout from a dead instance
* maybe dump out the PID of the worker that is running so we know which one to kill?

(Done)
* have jobs as static records in redis, drop workers for each build and only have process checking build status and downloading results in the end
  - advantage is that you don't lose the already done work on builds that were running when copr-be is restarted (which happens on upgrades or a component failure)
  - disadvantage is that it includes quite some changes: keeping and maintaing jobs and their states + process with infinite loop that checkes status of the running jobs
  - you also need to run the mockchain job on background with stdin and stoud disattached so that it does not halt on SIGHUP
  - includes implementation of a nice way to check whether build is finished or not (e.g. check running processes for mockbuilder user could be ok)
  - looks like all of this requires some `copr-builder` script to be run on builder?  Then `copr-builder` and `copr-backend` can have pre-defined API
        - $ copr-builder --config /some/config.conf build <coprID>/<package> --chroot <chroot>
        - the config.conf identifies where 'dist-git' and 'frontend' can be found to do `git clone PKG` and `copr-cli mock-config`
        - outputs could look like /copr-builder/live-log (stdout + stderr), /copr-builder/results/, /copr-builder/build.running (status)

  - clime: it can be done without `copr-builder` script ;)

* alternative to the prev approach:
  - run the builds remotely in background or in a terminal multiplexer
  - try to reconnect based on builder records on copr-be restart (involves setting up a new worker)

Command line interface
----------------------

* integrate with fedpkg

Other
-----

* Create CoprReleaser for `Tito <https://github.com/dgoodwin/tito>`_ (Done)
* provide .repo file (not sure if backend or frontend). (Done)
* Logo. We desperatly :) need logo. I was thinking about simplified picture of [http://en.wikipedia.org/wiki/Dill Dill] which is pronaunced in Czech (my native language) exactly same as Copr.
