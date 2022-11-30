%global copr_common_version 0.16.4.dev

Name:       copr-dist-git
Version:    0.59
Release:    1%{?dist}
Summary:    Copr services for Dist Git server

License:    GPLv2+
URL:        https://github.com/fedora-copr/copr

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %name-%version.tar.gz

BuildArch:  noarch

BuildRequires: systemd
BuildRequires: python3-devel
BuildRequires: python3-munch
BuildRequires: python3-requests
BuildRequires: python3-rpkg
BuildRequires: python3-pytest
BuildRequires: python3-copr-common >= %copr_common_version
BuildRequires: python3-oslo-concurrency
BuildRequires: python3-redis
BuildRequires: python3-setproctitle

Recommends: logrotate
Requires: systemd
Requires: httpd
Requires: coreutils
Requires: crudini
Requires: dist-git
Requires: python3-copr-common >= %copr_common_version
Requires: python3-requests
Requires: python3-rpkg >= 1.63-5
Requires: python3-munch
Requires: python3-oslo-concurrency
Requires: python3-setproctitle
Requires: python3-daemon
Requires: python3-redis
Requires: findutils
Requires: (copr-selinux if selinux-policy-targeted)
Requires: crontabs
Requires: redis

Recommends: python3-copr

%{?fedora:Requires(post): policycoreutils-python-utils}
%{?rhel:Requires(post): policycoreutils-python}

%description
COPR is lightweight build system. It allows you to create new project in WebUI
and submit new builds and COPR will create yum repository from latest builds.

This package contains Copr services for Dist Git server.


%prep
%setup -q


%build
%py3_build


%pre
getent group packager >/dev/null || groupadd -r packager
getent group copr-dist-git >/dev/null || groupadd -r copr-dist-git
getent group apache >/dev/null || groupadd -r apache
getent passwd copr-dist-git >/dev/null || \
useradd -r -m -g copr-dist-git -G packager,apache -c "copr-dist-git user" copr-dist-git
/usr/bin/passwd -l copr-dist-git >/dev/null

%install
%py3_install

install -d %{buildroot}%{_datadir}/copr/dist_git
install -d %{buildroot}%{_sysconfdir}/copr
install -d %{buildroot}%{_sysconfdir}/logrotate.d/
install -d %{buildroot}%{_sysconfdir}/httpd/conf.d/
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}%{_var}/log/copr-dist-git
install -d %{buildroot}%{_tmpfilesdir}
install -d %{buildroot}%{_sharedstatedir}/copr-dist-git
install -d %{buildroot}%{_sysconfdir}/cron.monthly

install -p -m 755 conf/cron.monthly/copr-dist-git %{buildroot}%{_sysconfdir}/cron.monthly/copr-dist-git

cp -a conf/copr-dist-git.conf.example %{buildroot}%{_sysconfdir}/copr/copr-dist-git.conf
cp -a conf/httpd/copr-dist-git.conf %{buildroot}%{_sysconfdir}/httpd/conf.d/copr-dist-git.conf
cp -a conf/tmpfiles.d/* %{buildroot}/%{_tmpfilesdir}
cp -a copr-dist-git.service %{buildroot}%{_unitdir}/

cp -a conf/logrotate %{buildroot}%{_sysconfdir}/logrotate.d/copr-dist-git

mv %{buildroot}%{_bindir}/remove_unused_sources %{buildroot}%{_bindir}/copr-prune-dist-git-sources

# for ghost files
touch %{buildroot}%{_var}/log/copr-dist-git/main.log

%py_byte_compile %{__python3} %{buildroot}%{_datadir}/copr/dist_git


%check
./run_tests.sh -vv --no-cov

%post
%systemd_post copr-dist-git.service

%preun
%systemd_preun copr-dist-git.service

%postun
%systemd_postun_with_restart copr-dist-git.service

%files
%license LICENSE
%python3_sitelib/copr_dist_git
%python3_sitelib/copr_dist_git*egg-info

%{_bindir}/*
%dir %{_datadir}/copr
%{_datadir}/copr/*
%dir %{_sysconfdir}/copr
%config(noreplace) %attr(0640, root, copr-dist-git) %{_sysconfdir}/copr/copr-dist-git.conf
%config(noreplace) %attr(0644, root, root) %{_sysconfdir}/httpd/conf.d/copr-dist-git.conf
%config(noreplace) %attr(0755, root, root) %{_sysconfdir}/cron.monthly/copr-dist-git

%dir %attr(0755, copr-dist-git, copr-dist-git) %{_sharedstatedir}/copr-dist-git/

%{_unitdir}/copr-dist-git.service

%dir %{_sysconfdir}/logrotate.d
%config(noreplace) %{_sysconfdir}/logrotate.d/copr-dist-git
%attr(0755, copr-dist-git, copr-dist-git) %{_var}/log/copr-dist-git
%attr(0644, copr-dist-git, copr-dist-git) %{_var}/log/copr-dist-git/main.log
%ghost %{_var}/log/copr-dist-git/*.log
%{_tmpfilesdir}/copr-dist-git.conf

%changelog
* Wed Nov 30 2022 Pavel Raiskup <praiskup@redhat.com> 0.59-1
- start copr-dist-git.service after redis.service
- background workers mark themselves as done (needed by the manager logic)

* Sat Nov 26 2022 Jakub Kadlcik <frostyx@email.cz> 0.58-1
- require redis.service to be started
- move to GitHub home page
- fair processing of task from multiple sandboxes
- use dispatcher and background workers

* Tue Aug 16 2022 Jiri Kyjovsky <j1.kyjovsky@gmail.com> 0.57-1
- log the URL that got us new tasks

* Tue Jul 26 2022 Jakub Kadlcik <frostyx@email.cz> 0.56-1
- Do not hold the downloaded files in memory

* Tue Jun 21 2022 Jakub Kadlcik <frostyx@email.cz> 0.55-1
- Don't setgid(apache) while importing ("uploading")
- More obvious "locking" importer proctitle

* Mon Apr 04 2022 Pavel Raiskup <praiskup@redhat.com> 0.54-1
- do not remove the PR directories too early

* Tue Mar 08 2022 Jakub Kadlcik <frostyx@email.cz> 0.53-1
- upload sources only if there are some
- update copr-fe-dev hostname

* Wed Feb 02 2022 Silvie Chlupova <schlupov@redhat.com> 0.52-1
- dist-git: python code for removing unused tarballs on dist-git server

* Tue Jun 15 2021 Pavel Raiskup <praiskup@redhat.com> 0.51-1
- add a --foreground option for importer_runner.py
- install debugging helpers for indefinite imports (rhbz#1963954)

* Tue Apr 27 2021 Jakub Kadlcik <frostyx@email.cz> 0.50-1
- dist-git: optimize cgit cache file generator
- dist-git: move everything to Python path
- backend, frontend, keygen, distgit: keep cca 3 months of logs

* Tue Mar 16 2021 Pavel Raiskup <praiskup@redhat.com> 0.49-1
- sleep and continue when frontend is not available

* Mon Nov 09 2020 Jakub Kadlcik <frostyx@email.cz> 0.48-1
- distgit: extend the timeout limit for importing packages
- distgit: allow `import_package` function to run in parallel
- distgit: require up2date python3-rpkg
- distgit: use kojiprofile instead of deprecated kojiconfig
- all: run pytest with -vv in package build
- distgit: each log entry to contain PID
- all: add Makefile symlink to sub-dirs
- pylint: run pylint in all run*tests.sh files

* Wed Dec 04 2019 Pavel Raiskup <praiskup@redhat.com> 0.47-1
- new releases done with tito again
- avoid making more than the predetermined number of workers
- require logrotate service

* Fri Jul 12 2019 Pavel Raiskup <praiskup@redhat.com> 0.46-1
- add offline argument to upload method, to fix RPM import
- add script to clear lookaside cache of old sources

* Wed Apr 24 2019 Jakub Kadlčík <frostyx@email.cz> 0.45-1
- remove old logs from cron

* Thu Jan 10 2019 Miroslav Suchý <msuchy@redhat.com> 0.44-1
- add python3-copr Recommends:
- one-shot script script to remove data for already deleted coprs
- allow blacklisting packages from chroots

* Fri Oct 19 2018 Miroslav Suchý <msuchy@redhat.com> 0.43-1
- fix SELinux
- use FailTypeEnum from copr_common
- use EnumType from copr_common
- use git_dir_archive instead of git_dir_pack
- fix `cgit_pkg_list` script
- use git_dir_archive instead of git_dir_pack

* Mon Aug 06 2018 clime <clime@redhat.com> 0.42-1
- manual byte-code compilation
- for py3 use unittest.mock, otherwise mock from python2-mock

* Fri May 18 2018 clime <clime@redhat.com> 0.41-1
- switch to python3
- rpkg deployment into COPR - containers + releng continuation

* Fri Feb 23 2018 clime <clime@redhat.com> 0.40-1
- remove Group tag

* Mon Feb 19 2018 clime <clime@redhat.com> 0.39-1
- Shebangs cleanup
- fix spec for rhel8
- escapes in changelogs

* Sun Feb 18 2018 clime <clime@redhat.com> 0.38-1
- remove old conditional in spec
- fix python requires, also trim deps down
- add source_status field for Builds
- remove no longer needed CAP_SYS_CHROOT cap

* Thu Sep 07 2017 clime <clime@redhat.com> 0.37-1
- most of the logic moved to copr-rpmbuild

* Fri Aug 25 2017 clime <clime@redhat.com> 0.36-1
- run spec parsing in an isolated manner
- Spelling fixes

* Fri Aug 04 2017 clime <clime@redhat.com> 0.35-1
- fix cvs-data ignore regular expression

* Mon Jul 31 2017 clime <clime@redhat.com> 0.34-1
- remove --global for git config in tests so that it does not
  modify ~/.gitconfig
- fix #106 Renaming a spec file in a newer version causes the
  build to fail
- make get_package_name more robust
- add DistGitProvider with support for multiple distgits

* Wed Jul 19 2017 clime <clime@redhat.com> 0.33-1
- remove ExclusiveArch directive
- add support for SCM Subdirectory parameter
- remove docker related stuff
- fix variable name
- add missing import in providers.py
- auto-differentiate between downstream and upstream repo in
  SCMProvider
- do not include dist information in displayed version
- remove unused exceptions
- get_package_name from spec_path is now a separate method
- do not modify spec for MockScm method
- use python's tarfile instead of tar shell cmd

* Fri Jul 14 2017 clime <clime@redhat.com> 0.32-1
- srpms are now not being built on dist-git
- MockSCM and Tito methods unified into single source

* Fri Jul 07 2017 clime <clime@redhat.com> 0.31-1
- remove no longer required condition for a scm import to run
- .spec build implemented
- fedora:25 image offers the needed en_US.UTF-8 locale now
- Dockerfile with less layers

* Fri Jun 09 2017 clime <clime@redhat.com> 0.30-1
- import build task only once
- remove unsupported --depth from git svn command
- add dep on git-svn
- better exception handling in MockScmProvider
- fix 'git svn clone' and add exception handling for clone part in MockScm provider

* Thu Jun 01 2017 clime <clime@redhat.com> 0.29-1
- Bug 1457888 - Mock SCM method fails to build a package
- increase depth for git clone so that required tags that tito needs are downloaded

* Wed May 31 2017 clime <clime@redhat.com> 0.28-1
- add --depth 1 for git clone in GitProvider
- add missing 'which' for tito && git-annex builds
- arbitrary dist-git branching support
- use MockScmProvider without mock-scm to solve performance problems
- add "powerpc64le" into list of archs to allow building for

* Mon May 15 2017 clime <clime@redhat.com> 0.27-1
- Bug 1447102 - fedpkg build fail during import phase

* Wed Apr 12 2017 clime <clime@redhat.com> 0.26-1
- follow docker ExclusiveArches spec directive
- replace leftover username in lograte config
- fix README

* Mon Apr 10 2017 clime <clime@redhat.com> 0.25-1
- compatibility fixes for the latest dist-git (upstream)
- improved error logging and exception handling of external commands
- improve repo creation & srpm import logging and exception handling
- replace copr-service user by copr-dist-git and useradd the user
- Bug 1426033 - git-annex missing, cannot use tito.builder.GitAnnexBuilder
- replace fedorahosted links
- error logging of pyrpkg upload into lookaside
- update langpack hack in dist-git Dockerfile

* Thu Jan 26 2017 clime <clime@redhat.com> 0.24-1
- install mock-scm in docker image from official fedora repos
- upgrade docker image to f25
- Fixes for building COPR Backend and Dist-git on EL7
- fix copy hack for new internal pyrpkg API

* Thu Dec 01 2016 clime <clime@redhat.com> 0.23-1
- use other than epel chroot for scm building
- use newest mock
- run mock-scm inside of docker
- add README information about how docker image is built
- stripped down impl of building from dist-git
- fixed unittests
- refactor VM.run method
- remove exited containers
- add possibility to run dist-git in single thread
- refactor lookaside my_upload slightly
- Bug 1377780 - Multiple failed tasks with: Importing SRPM into Dist Git failed.

* Mon Sep 19 2016 clime <clime@redhat.com> 0.22-1
- fix Git&Tito subdirectory use-case

* Mon Sep 19 2016 clime <clime@redhat.com> 0.21-1
- Git&Tito, pyp2rpm, gem2rpm now run in docker

* Mon Aug 15 2016 clime <clime@redhat.com> 0.20-1
- try to obtain multiple tasks at once
- Add python2-psutil requirement
- inform frontend about terminated task
- log when starting and finishing workers
- log timeout value from worker
- run mock with --uniqueext
- implement timeout-based terminating
- parallelization by pool of workers

* Fri May 27 2016 clime <clime@redhat.com> 0.19-1
- strip whitespaces from the gem name

* Thu May 26 2016 clime <clime@redhat.com> 0.18-1
- implemented building from rubygems

* Fri Apr 22 2016 Miroslav Suchý <msuchy@redhat.com> 0.17-1
- support for pyrpkg-1.43
- typo in method name
- use os.listdir instead of Popen
- sort imports
- more verbose logging of exception

* Tue Apr 12 2016 Miroslav Suchý <msuchy@redhat.com> 0.16-1
- clean up after dist-git import
- assure python_versions type for pypi builds
- 1322553 - checkout specific branch

* Fri Mar 18 2016 Miroslav Suchý <msuchy@redhat.com> 0.15-1
- own /etc/logrotate.d
- own /usr/share/copr
- trailing dot in description

* Mon Mar 14 2016 Jakub Kadlčík <jkadlcik@redhat.com> 0.14-1
- per task logging for users
- don't assume the SCM repo has the same name as the package
- added policycoreutils-python-utils dependency
- do shallow git clone for mock-scm
- support building from PyPI

* Fri Jan 29 2016 Miroslav Suchý <msuchy@redhat.com> 0.13-1
- [dist-git] error handling based on subprocess return codes instead of output
  to stderr (e.g. git outputs progress to stderr) + missing catch for
  GitException in do_import (results in better error messages in frontend, see
  bz#1295540)

* Mon Jan 25 2016 Miroslav Suchý <msuchy@redhat.com> 0.12-1
- pass --scm-option spec=foo to mock-scm (msuchy@redhat.com)

* Thu Jan 21 2016 clime <clime@redhat.com> 0.11-1
- tito added to requirements

* Sat Jan 16 2016 clime <clime@redhat.com> 0.10-1
- fixed do_import test
- workaround for BZ 1283101

* Mon Nov 16 2015 Miroslav Suchý <msuchy@redhat.com> 0.9-1
- make more abstract exceptions
- implement support for multiple Mock SCMs
- split SourceDownloader to multiple SourceProvider classes
- refactor duplicate code from GIT_AND_TITO and GIT_AND_MOCK
- require mock-scm
- implement mock support in dist-git
- do not check cert when downloading srpm

* Mon Nov 02 2015 Miroslav Suchý <msuchy@redhat.com> 0.8-1
- add Git and Tito errors
- tito support
- hotfix for resubmit button

* Tue Sep 15 2015 Valentin Gologuzov <vgologuz@redhat.com> 0.7-1
- provide build failure details
- replace urllib.urlretrieve with requests.get to catch non-200 HTTP  status codes

* Fri Aug 14 2015 Valentin Gologuzov <vgologuz@redhat.com> 0.6-1
- [dist-git][rhbz: #1253335] Running rpkg in the dedicated process.

* Wed Aug 05 2015 Valentin Gologuzov <vgologuz@redhat.com> 0.5-1
- don't run tests during %%check on epel

* Wed Aug 05 2015 Valentin Gologuzov <vgologuz@redhat.com> 0.4-1
- additional BuildRequires to run tests

* Tue Aug 04 2015 Valentin Gologuzov <vgologuz@redhat.com> 0.3-1
- fixed commit message to include package name and version
- added initial tests; renamed folder with sources to use underscore instead of dash
- mark build as failed for any error during import
- don't break on the post failure to frontend
- get pkg name + version during import
- Use /var/lib/copr-dist-git/ to store pkg listing.
- refresh cgit after import

* Thu Jul 23 2015 Valentin Gologuzov <vgologuz@redhat.com> 0.2-1
- new package built with tito

* Thu Jun 25 2015 Adam Samalik <asamalik@redhat.com> 0.1
- basic package
