%if 0%{?rhel} <= 7 && 0%{?rhel} > 0
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%endif

%global prunerepo_version 1.20
%global tests_version 2
%global tests_tar test-data-copr-backend

%global copr_common_version 0.16.4.dev

Name:       copr-backend
Version:    1.163
Release:    1%{?dist}
Summary:    Backend for Copr

License:    GPLv2+
URL:        https://github.com/fedora-copr/copr

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %{name}-%{version}.tar.gz
Source1:    https://github.com/fedora-copr/%{tests_tar}/archive/v%{tests_version}/%{tests_tar}-%{tests_version}.tar.gz

BuildArch:  noarch
BuildRequires: asciidoc
BuildRequires: createrepo_c >= 0.16.1
BuildRequires: libappstream-glib-builder
BuildRequires: libxslt
BuildRequires: make
BuildRequires: redis
BuildRequires: rsync
BuildRequires: systemd
BuildRequires: util-linux

BuildRequires: python3-devel
BuildRequires: python3-setuptools

BuildRequires: python3-copr
BuildRequires: python3-copr-common >= %copr_common_version
BuildRequires: python3-copr-messaging
BuildRequires: python3-daemon
BuildRequires: python3-dateutil
BuildRequires: python3-distro
BuildRequires: python3-fedmsg
BuildRequires: python3-filelock
BuildRequires: python3-gobject
BuildRequires: python3-httpretty
BuildRequires: python3-humanize
BuildRequires: python3-libmodulemd1 >= 1.7.0
BuildRequires: python3-munch
BuildRequires: python3-netaddr
BuildRequires: python3-packaging
BuildRequires: python3-pytest
BuildRequires: python3-pytz
BuildRequires: python3-requests
BuildRequires: python3-resalloc
BuildRequires: python3-retask
BuildRequires: python3-setproctitle
BuildRequires: python3-sphinx
BuildRequires: python3-tabulate
BuildRequires: modulemd-tools >= 0.6
BuildRequires: prunerepo >= %prunerepo_version
BuildRequires: dnf

Requires:   (copr-selinux if selinux-policy-targeted)
Requires:   ansible
Suggests:   awscli
Requires:   createrepo_c >= 0.16.1
Requires:   crontabs
Requires:   gawk
Requires:   libappstream-glib-builder
Requires:   lighttpd
Recommends: logrotate
Requires:   mock
Requires:   obs-signd
Requires:   openssh-clients
Requires:   prunerepo >= %prunerepo_version
Requires:   python3-copr
Requires:   python3-copr-common >= %copr_common_version
Requires:   python3-copr-messaging
Requires:   python3-daemon
Requires:   python3-dateutil
Requires:   python3-fedmsg
Requires:   python3-filelock
Requires:   python3-gobject
Requires:   python3-humanize
Requires:   python3-jinja2
Requires:   python3-libmodulemd1 >= 1.7.0
Requires:   python3-munch
Requires:   python3-netaddr
Requires:   python3-novaclient
Requires:   python3-packaging
Requires:   python3-pytz
Requires:   python3-requests
Requires:   python3-resalloc >= 3.0
Requires:   python3-retask
Requires:   python3-setproctitle
Requires:   python3-tabulate
Requires:   python3-boto3
Requires:   redis
Requires:   rpm-sign
Requires:   rsync
Requires:   modulemd-tools >= 0.6
Recommends: util-linux-core
Requires:   zstd

Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd

%description
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package contains backend.

%package doc
Summary:    Code documentation for COPR backend

%description doc
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package include documentation for COPR code. Mostly useful for developers
only.


%prep
%setup -q -a 1


%build
make -C docs %{?_smp_mflags} html
%py3_build


%install
%py3_install


install -d %{buildroot}%{_sharedstatedir}/copr/public_html/results
install -d %{buildroot}%{_pkgdocdir}/lighttpd/
install -d %{buildroot}%{_sysconfdir}/copr
install -d %{buildroot}%{_sysconfdir}/logrotate.d/
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}/%{_var}/log/copr-backend
install -d %{buildroot}/%{_var}/run/copr-backend/
install -d %{buildroot}/%{_tmpfilesdir}
install -d %{buildroot}/%{_sbindir}
install -d %{buildroot}%{_sysconfdir}/cron.daily
install -d %{buildroot}%{_sysconfdir}/cron.weekly
install -d %{buildroot}%{_sysconfdir}/sudoers.d
install -d %{buildroot}%{_bindir}/

cp -a copr-backend-service %{buildroot}/%{_sbindir}/
cp -a run/* %{buildroot}%{_bindir}/
cp -a conf/copr-be.conf.example %{buildroot}%{_sysconfdir}/copr/copr-be.conf

install -p -m 755 conf/crontab/daily %{buildroot}%{_sysconfdir}/cron.daily/copr-backend
install -p -m 755 conf/crontab/weekly  %{buildroot}%{_sysconfdir}/cron.weekly/copr-backend

cp -a conf/lighttpd/* %{buildroot}%{_pkgdocdir}/lighttpd/
cp -a conf/logrotate/* %{buildroot}%{_sysconfdir}/logrotate.d/
cp -a conf/tmpfiles.d/* %{buildroot}/%{_tmpfilesdir}

# for ghost files
touch %{buildroot}%{_var}/log/copr-backend/copr.log
touch %{buildroot}%{_var}/log/copr-backend/prune_old.log

cp -a units/*.{target,service} %{buildroot}/%{_unitdir}/
install -m 0644 conf/copr.sudoers.d %{buildroot}%{_sysconfdir}/sudoers.d/copr


install -d %{buildroot}%{_sysconfdir}/logstash.d

install -d %{buildroot}%{_datadir}/logstash/patterns/
cp -a conf/logstash/lighttpd.pattern %{buildroot}%{_datadir}/logstash/patterns/lighttpd.pattern

cp -a conf/playbooks %{buildroot}%{_pkgdocdir}/

install -d %{buildroot}%{_pkgdocdir}/examples/%{_sysconfdir}/logstash.d
cp -a conf/logstash/copr_backend.conf %{buildroot}%{_pkgdocdir}/examples/%{_sysconfdir}/logstash.d/copr_backend.conf

cp -a docs/build/html %{buildroot}%{_pkgdocdir}/


%check
./run_tests.sh -vv --no-cov

%pre
getent group copr >/dev/null || groupadd -r copr
getent passwd copr >/dev/null || \
useradd -r -g copr -G lighttpd -s /bin/bash -c "COPR user" copr
/usr/bin/passwd -l copr >/dev/null

%post
%systemd_post copr-backend.target

%preun
%systemd_preun copr-backend.target

%postun
%systemd_postun_with_restart copr-backend-log.service
%systemd_postun_with_restart copr-backend-build.service
%systemd_postun_with_restart copr-backend-action.service

%files
%license LICENSE
%python3_sitelib/copr_backend
%python3_sitelib/copr_backend*egg-info

%dir %{_sharedstatedir}/copr
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/public_html/
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/public_html/results
%dir %attr(0755, copr, copr) %{_var}/run/copr-backend
%dir %attr(0755, copr, copr) %{_var}/log/copr-backend

%ghost %{_var}/log/copr-backend/*.log

%config(noreplace) %{_sysconfdir}/logrotate.d/copr-backend
%dir %{_pkgdocdir}
%doc %{_pkgdocdir}/lighttpd
%doc %{_pkgdocdir}/playbooks
%dir %{_sysconfdir}/copr
%config(noreplace) %attr(0640, root, copr) %{_sysconfdir}/copr/copr-be.conf
%{_unitdir}/*.service
%{_unitdir}/*.target
%{_tmpfilesdir}/copr-backend.conf
%{_bindir}/*
%{_sbindir}/*

%config(noreplace) %{_sysconfdir}/cron.daily/copr-backend
%config(noreplace) %{_sysconfdir}/cron.weekly/copr-backend
%{_datadir}/logstash/patterns/lighttpd.pattern


%config(noreplace) %attr(0600, root, root)  %{_sysconfdir}/sudoers.d/copr

%files doc
%license LICENSE
%doc
%{_pkgdocdir}/
%exclude %{_pkgdocdir}/lighttpd
%exclude %{_pkgdocdir}/playbooks

%changelog
* Wed Nov 30 2022 Pavel Raiskup <praiskup@redhat.com> 1.163-1
- start systemd services after the redis.service
- build worker - list the built RPMs with rpm --nosignature

* Sat Nov 26 2022 Jakub Kadlcik <frostyx@email.cz> 1.162-1
- use OpenPGP v4 signatures
- migrate from pipes to shlex
- require redis.service to be started
- move to GitHub home page
- add resultdir cleaner
- move dispatcher and background workers to copr-common
- de-prio IO for the analyze-results script
- don't traceback when there are no files in the S3 storage
- allow devel instance to remove access files
- send non-CDN hitcounter hits in chunks
- copr-backend-unknown-resalloc-tickets script
- work with multiple CDN hostnames per instance
- move setup_script_logger to copr-common

* Mon Sep 26 2022 Pavel Raiskup <praiskup@redhat.com> 1.161-1
- sign everything EPEL-5+ with sha256 hashalgo

* Tue Sep 20 2022 Jakub Kadlcik <frostyx@email.cz> 1.160-1
- aws-hitcounter: remove temporary files as soon as possible
- aws-hitcounter: ignore downloaded SRPM files
- aws-hitcounter: decode special characters from URLs

* Tue Aug 16 2022 Pavel Raiskup <praiskup@redhat.com> 1.159-1
- count only hits from an appropriate CDN hostname
- add option for infinite number of attempts to the hitcounter script
- print more reasonable output from AWS hitcounter script

* Tue Aug 16 2022 Jiri Kyjovsky <j1.kyjovsky@gmail.com> 1.158-1
- log every request that is sent to frontend

* Tue Jul 26 2022 Jakub Kadlcik <frostyx@email.cz> 1.157-1
- Don't use --keep-all-metadata
- Search for comps.xml in chroot dir

* Tue Jun 21 2022 Jakub Kadlcik <frostyx@email.cz> 1.156-1
- Consolidate the two hitcounter scripts
- Dump Resalloc ticket ID and hostname to backend.log
- Automatically restart services in %%post
- Don't count RPMs downloaded from Mock
- Attempt to sign multiple times
- Try multiple attempts of creating GPG keys

* Mon Apr 04 2022 Pavel Raiskup <praiskup@redhat.com> 1.155-1
- fix slow priority queue filling
- speedup the background-process spawner

* Fri Mar 18 2022 Pavel Raiskup <praiskup@redhat.com> 1.154-1
- copr_fix_gpg: automatically refresh CDN cache
- copr_fix_gpg: don't use --skip-stat for copr-repo when RPMs are re-signed
- action processor: properly return failures of the fork action
- sign EL8+ with sha256 hash algorithm
- copr_fix_gpg: add a new --chroot option
- copr_fix_gpg: skip non-chroot directories
- add hitcounter script for AWS CDN
- backend: tasks in concurrent sandboxes reprioritized to be more fair

* Wed Feb 02 2022 Silvie Chlupova <schlupov@redhat.com> 1.153-1
- less aggressive final_prunerepo setting
- analyze-results: dump data for projects' chroots
- basic build tagging
- better "regenerate repo" instructions
- limit RubyGems and PyPI package names length
- Disable coverage analysis during RPM build
- python code for removing unused tarballs on dist-git server

* Wed Nov 10 2021 Silvie Chlupova <schlupov@redhat.com> 1.152-1
- Fixup ACR handling
- Drop the unused pid file from the specfile
* Thu Sep 30 2021 Silvie Chlupova 1.151-1
- backend: use lock(timeout=5) to work-around fair-locks

* Wed Aug 25 2021 Pavel Raiskup <praiskup@redhat.com> 1.150-1
- request arch_noarch resalloc tag for source RPM builds
- re-try /bin/sign call upon connection timeout
- drop 'check_consecutive_build_fails' script

* Tue Jun 15 2021 Pavel Raiskup <praiskup@redhat.com> 1.149-1
- new weekly cron-job for analyzing storage use (graphs, statistics)
- added some convenience globals into copr_backend.setup module
- keep the max batch size really on the MAX_IN_BATCH limit
- require up2date rpmbuild version
- new action for removing CoprDirs (triggered by cron on frontend)
- fix the CompsUpdate action
- users now can disable appstream metadata generation themselves (without admins asistance)
- handle results.json given by builder, and provide it to frontend (served as APIv3 later)
- pruner: allow pruning also the finalized chroots on demand
- invent FE-BE API version, so backend politely waits for an updated copr-frontend version

* Thu May 13 2021 Pavel Raiskup <praiskup@redhat.com> 1.148-1
- work with builders also over ipv6

* Sun May 02 2021 Pavel Raiskup <praiskup@redhat.com> 1.147-1
- fix logging traceback for module builds
- call creatrepo_c with --update if possible
- don't do full createrpeo with --rpms-to-remove

* Fri Apr 30 2021 Pavel Raiskup <praiskup@redhat.com> 1.146-1
- better fixes for the appstream-builder generated files
- new helper script named /bin/copr-assure-permissions
- do not rsync-copy permissions from the builder
- log the partial "prunerepo" effects into resultdir
- better, more verbose call_copr_repo logging

* Tue Apr 27 2021 Jakub Kadlcik <frostyx@email.cz> 1.145-1
- backend: make the walk_limited test not dependend on its output order, pt2

* Tue Apr 27 2021 Jakub Kadlcik <frostyx@email.cz> 1.144-1
- backend: make the walk_limited test not dependend on its output order

* Tue Apr 27 2021 Jakub Kadlcik <frostyx@email.cz> 1.143-1
- backend: fix copr_prune_results logging once more
- backend: better logging in prunerepo
- backend: prunerepo: don't re-createrepo when no rpm is removed
- backend: catch correct client exceptions in copr_prune_results
- test: backend: change prunerepo logic, use get_rpms_to_remove from prunerepo
- backend: new fixture for testing prunerepo
- backend: use safe defaults if APIv3 result doesn't contain what it should
- backend: migrate to APIv3
- backend: better how-to-redirect logs comment
- backend, frontend, keygen, distgit: keep cca 3 months of logs
- backend: don't createrepo in srpm-builds on delete
- backend: test walk_limited function from helpers

* Tue Mar 16 2021 Pavel Raiskup <praiskup@redhat.com> 1.142-1
- prepare for the centos-stream-8 rename
- add script to prune srpm-build directories
- pruner: correctly deliver the final prunerepo stamp to frontend
- pruner: logging through RedisLogHandler
- pruner: better parallelization
- pruner: re-try be-fe communication upon failures
- require up2date modulemd-tools

* Wed Jan 20 2021 Pavel Raiskup <praiskup@redhat.com> 1.141-1
- run prunerepo in parallel
- add one-shot copr_find_wrong_chroot_artifacts.py script
- support modulemd v2

* Tue Dec 01 2020 Pavel Raiskup <praiskup@redhat.com> 1.140-1
- fix frontend-client post arguments

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 1.139-1
- require appropriate common version
- use common for repeatedly sends requests to frontend

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 1.138-1
- get back to using standard createrepo_c command from createrepo_mod
- drop call to stomp's conn.start() (it was dropped)

* Mon Nov 09 2020 Jakub Kadlcik <frostyx@email.cz> 1.137-1
- backend: test action for deleting chroot
- backend: fix testsuite for the new createrepo_c
- frontend: don't set ended_on for canceled builds
- all: run pytest with -vv in package build
- common, cli, python, rpmbuild, frontend, backend: DistGit source method
- backend: use createrepo_mod tool for generating module repodata

* Wed Aug 12 2020 Pavel Raiskup <praiskup@redhat.com> 1.136-1
- testsuite: give more time to the slow Koji builders

* Mon Aug 10 2020 Pavel Raiskup <praiskup@redhat.com> 1.135-1
- prioritize all non-background jobs
- fix up libmodulemd dependency

* Fri Jun 19 2020 Pavel Raiskup <praiskup@redhat.com> 1.134-1
- fix copr-repo to work with absolute paths
- automatically batch the createrepo requests
- scheduler is now fair, and ordered
- indefinitely retry workers' talk to frontend
- allow canceling also "starting" builds
- more verbose delete action in logs
- cleanup the example configuration
- use FileHandler for backend.log, fixes traceback

* Tue Jun 09 2020 Pavel Raiskup <praiskup@redhat.com> 1.133-1
- better build task priority processing
- dump attempt to send message to backend.log
- drop the VMM concept, replaced with resalloc
- delegate more work to the builder code
- external blob tarball for unittests
- buggy error handler in pkg_name_evr()
- basic build task priority
- the reschedule-all builds idiom removed
- fix the build cancelation
- drop duplicate BuildRequire on python-requests
- require the newest version of copr-common
- minimalize the transfered amount of information about actions from FE
- process actions in regard to their priority
- move backend's code to standard PYTHONPATH
- move ActionResult to copr_common.enums
- actions/builds use the same WorkerManager logic
- more verbose rawhide to release action processing

* Wed Feb 05 2020 Pavel Raiskup <praiskup@redhat.com> 1.132-1
- better handle invalid options in copr-repo --add/--delete
- copr-repo: optimize-out useless createrepo_c runs
- move initial createrepo check from dispatcher to worker
- don't send messages on bus N-times
- /bin/copr-repo now respects .disable-appstream files
- drop unused build_deleting_without_createrepo option

* Wed Jan 15 2020 Tomas Hrnciar <thrnciar@redhat.com> 1.131-1
- put build-ID.log file to resultdir
- call call_copr_repo if initial createrepo failed
- Build Dispatcher does not wait forever till repo is created,
  it creates it manually
- properly delete logs for old builds
- delete build-ID.log files again
- edit repositories only by new 'copr-repo' tool
- fix multi-build delete
- fix for not saving end time of actions
- lower traffic in build_dispatcher log
- more resilient redis logging
- attempt to publish on msgbus N-times
- log service: move RequiredBy to [Install]
- keep worker ID in proc title

* Fri Dec 06 2019 Pavel Raiskup <praiskup@redhat.com> 1.130-1
- backend: execute actions with sane umask=0022

* Wed Dec 04 2019 Pavel Raiskup <praiskup@redhat.com> 1.129-1
- do not start a build if copr_base is not available yet
- systemd services' restart re-ordering
- de-duplicate frontend_.update() call when reattaching to existing build
- allow specifying timeout for spawn/terminate playbooks
- removing dependecy on euca2ools in spec
- send `uses_devel_repo' as a part of task info
- correctly configure logrotate
- get_redis_logger: skip log entries bellow log_level
- delete leftover action workers from redis

* Fri Oct 11 2019 Pavel Raiskup <praiskup@redhat.com> 1.128-1
- restart copr-backend sub-services on failure
- don't kill action processors by 'systemctl restart'
- lower the log traffic in build_dispatcher.log

* Thu Oct 03 2019 Pavel Raiskup <praiskup@redhat.com> 1.127-1
- fix testsuite for slow Koji builders

* Thu Oct 03 2019 Pavel Raiskup <praiskup@redhat.com> 1.126-1
- more reliable communication with frontend (#1021)
- only ask for auto_createrepo once per project
- parallel handling of actions (#1007)
- don't provide builder-live.log once the build ended, and
  add 'copr-compress-live-logs' helper (#985)
- less exceptions in logs
- project forking fixes
- depend on copr-messaging, not fedora-messaging
- fixes for copr_print_results_to_delete.py script

* Wed Aug 28 2019 Dominik Turecek <dturecek@redhat.com> 1.125-1
- minimize redis traffic for looping over pending-jobs (issue#902)
- batch delete builds into a single action (issue#688)
- admin opt-out createrepo after build-deleting
- fix wrong message validation class
- refine cleanup_vm_nova.py
- depend on copr-messaging

* Mon Jul 29 2019 Pavel Raiskup <praiskup@redhat.com> 1.124-1
- run createrepo immediately, don't wait for build (issue#833)
- compress backend-live.log by calling gzip (issue#86)
- use copr-messaging module for validating outgoing messages
- don't run appstream-builder for PR dirs
- don't run createrepo for srpm directories
- skip VMs with failing live-check in scheduler
- sandbox builds per user/submitter/project
- drop unused compat code for droped /bin/copr-builder
- do not call appstream builder with --max-threads (issue#717)
- added copr_print_results_to_delete.py script, should help
  us with removal of orphaned resources on backend storage (issue#712)
- allow disabling appstream builder per project (issue#738)
- tabular output from copr_get_vm_info.py

* Wed Apr 24 2019 Jakub Kadlčík <frostyx@email.cz> 1.123-1
- clean data for failed builds; fix #619
- replace runnecessary regex with str.endswith
- move clean_copr from prunerepo to our codebase
- cleanup_vm_nova.py: use yaml.safe_load
- don't rely on createrepo from prunerepo
- simplify logging through redis
- run sign command without sudo to fix #636
- encode 'msg' in LogRecord sooner
- fix charset warnings on redis-py v3
- fix default arguments in redis scripts
- don't prunerepo too old directories
- LogHandler: don't drop exc_info from LogRecord
- use the correct data for rawhide_to_release createrepo
- make copr_prune_results skip already pruned outdated chroots
- require libmodulemd in at least 1.7.0
- remove dependency on python3-configparser

* Mon Feb 11 2019 Jakub Kadlčík <frostyx@email.cz> 1.122-1
- Add requires python3-novaclient
- Set the architecture for which the module has been built
- Generate module artifacts in the correct format
- Compress the modules.yaml file

* Fri Jan 11 2019 Miroslav Suchý <msuchy@redhat.com> 1.121-1
- remove data from outdated chroots

* Thu Jan 10 2019 Miroslav Suchý <msuchy@redhat.com> 1.120-1
- update list of copr services
- Use oslo_concurrency for craeterepo locking
- use run_cmd() in pkg_name_evr()
- drop "downloading" state
- allow blacklisting packages from chroots

* Fri Oct 19 2018 Miroslav Suchý <msuchy@redhat.com> 1.119-1
- optimize copr_log_hitcounter.py for speed a bit
- move selinux rules to copr-selinux
- fix traceback for non-serializable log message
- fix tracebacks in copr-backend-log
- more robust run_tests.sh
- remove unused imports
- py3 compat for msgbus support
- use git_dir_archive instead of git_dir_pack
- migrate from deprecated python3-modulemd to libmodulemd
- doc: remove warning that _static directory does not exists
- doc: the undeline need to be at least as long as the title

* Thu Aug 23 2018 clime <clime@redhat.com> 1.118-1
- fix logging exception
- send proper arguments for rawhide_to_release
- packaging: Python 2/3, RHEL/Fedora fixes

* Mon Aug 06 2018 clime <clime@redhat.com> 1.117-1
- None task protection
- pagure integration
- use manual .pyc file generation
- remove unused imports, ad. pr#327
- resolving pylint warnings
- for py3 use unittest.mock
- fix msgbus ContentType to application/json

* Fri May 18 2018 clime <clime@redhat.com> 1.116-1
- fix #291 forks are incomplete
- log more information about incoming actions
- preparation for opensuse-leap-15.0-x86_64

* Thu Apr 26 2018 Dominik Turecek <dturecek@redhat.com> 1.115-1
- rpkg deployment into COPR - containers + releng continuation
- fix pagure bugs #269, #273, #221 and #268
- cleanup in test_helpers, one test added
- change order of args in StrictRedis call
- add comment about expected usage of the copr_log_hitcounter script
- try to send hit data to frontend several times from
copr_log_hitcounter

* Mon Feb 26 2018 clime <clime@redhat.com> 1.114-1
- add possibility for copr_log_hitcounter to ignore multiple subnets

* Fri Feb 23 2018 clime <clime@redhat.com> 1.113-1
- original builder deprecation
- remove Group tag

* Mon Feb 19 2018 clime <clime@redhat.com> 1.112-1
- Shebangs cleanup
- escapes in changelogs

* Sun Feb 18 2018 clime <clime@redhat.com> 1.111-1
- use netaddr instead of IPy module
- sleep after each load_jobs iteration
- python3 conversion
- UMB: adding content type
- add source_status field for Builds
- generate module artifacts rpms
- the rsync log is actually renderred directly into result dir now
- mockchain.log renamed to backend.log
- pg#192 missing records in mockchain.log
- enable running tests in spec file
- enable and update vmmamanger tests, fix three minor bugs in the
  manager
- frontend now presents the whole job queue state to
  backend
- copy only module builds into the repo directory

* Wed Dec 20 2017 clime <clime@redhat.com> 1.110-1
- exception handling for hit counting when IP address cannot be parsed

* Mon Dec 18 2017 Dominik Turecek <dturecek@redhat.com> 1.109-1
- terminate also 'in_use' builders if health checks have failed
- make --detached the last arg for copr-rpmbuild
- update copr_log_hitcounter to check ip against ignored pattern
- new msg bus options 
- disable DNF makecache timer/service
- fix message duplication for multi-bus scenario

* Thu Nov 16 2017 Miroslav Suchý <msuchy@redhat.com> 1.108-1
- optimize createrepo_c
- Revert "[backend] remove --ignore-lock from createrepo_c"

* Thu Nov 09 2017 clime <clime@redhat.com> 1.107-1
- kill all processes in copr-rpmbuild's process group
- add --drop-resultdir switch to copr-rpmbuild call
- release_vm immediately after VM is no longer needed
- remove --ignore-lock from createrepo_c

* Wed Oct 18 2017 clime <clime@redhat.com> 1.106-1
- run copr-rpmbuild with --verbose option

* Wed Sep 27 2017 clime <clime@redhat.com> 1.105-1
- remove uneeded yum dep

* Tue Sep 26 2017 clime <clime@redhat.com> 1.104-1
- update copr-rpmbuild command for the new options
- change arguments to build_id and chroot
- #128 AppStream data collection vetoes addons
- fix rpm download stats collection
- module-stuff update

* Fri Sep 15 2017 clime <clime@redhat.com> 1.103-1
- update fedora image version to 26
- fixes for recent code

* Thu Sep 07 2017 clime <clime@redhat.com> 1.102-1
- srpms are now being built from upstream on builders

* Wed Jun 14 2017 clime <clime@redhat.com> 1.101-1
- remove unused helpers.run_ssh + function spacing fixup
- cancel-build action fix

* Fri Jun 09 2017 clime <clime@redhat.com> 1.100-1
- extend check for a builder package present on a builder machine
- arbitrary dist-git branching
- remove --add-cache-id from appstream-builder call, see Bug 1426166
- change to using a standalone builder package

* Wed May 03 2017 clime <clime@redhat.com> 1.99-1
- missing on_success_build call added back to sign packages and recreate repo after each build

* Mon Apr 24 2017 clime <clime@redhat.com> 1.98-1
- Bug 1444804 - Logs are not present for failed builds

* Wed Apr 19 2017 clime <clime@redhat.com> 1.97-1
- do not condrestart optional logstash service
- standalone builder option
- build reattaching after copr-backend(-build) service restart
- live mockchain log
- use openssh instead of paramiko
- update cleanup_vm_nova script
- remove buggy logging
- removed Sphinx as a dependency...
- verbose log everything we have about failed playbook
- replace fedorahosted links
- make systemd services out of ActionDispatcher and BuildDispatcher

* Thu Jan 26 2017 clime <clime@redhat.com> 1.96-1
- Fixes for building COPR Backend and Dist-git on EL7
- simplified/improved logging of exceptions mainly
- don't use sha256 checksum for rhel-5* repos, too
- drop mentions of the max_builds_per_vm optoin
- switched usage of deprecated ansible Runner for python-paramiko module
- os_nova filter plugin fixed for python-novaclient 3
- support for STOMP msg buses
- fix Bug 1402689 regarding job cancellation
- jobgrab service is no more
- respect 'do_sign' option when forking
- fix buildroot_cmd for rhel mock profiles

* Thu Dec 01 2016 clime <clime@redhat.com> 1.95-1
- use buildroot_pkgs substitution type according to job.chroot
- use timeout command to respect timeout param coming from frontend
- don't ship unitfiles in %%bindir
- move createrepo to the end of the rawhide_to_release handler
- modulemd 1.0.2 compatibility
- Bug 1397119 - Error reading SSH protocol banner
- added auto-prune project's option
- Bug 1086139 - [RFE] provide UI to cancel a build
- Fix misleading debug statement
- fix exception logging in ensure_dir_exists helper
- Fix chroot_setup_cmd regex for custom chroot

* Mon Sep 19 2016 clime <clime@redhat.com> 1.94-1
- also provide default version and release for generated modules.json

* Mon Sep 19 2016 clime <clime@redhat.com> 1.93-1
- fix NameError: global name 'result' is not defined
- fix exception logging
- Modularity support
- Bug 1357564 - RFE: allow downloading of mock profiles (reproducible builds)
- "safer" exception handling for actions

* Mon Aug 15 2016 clime <clime@redhat.com> 1.92-1
- wrap feedback about actions to frontend into try-except
- log even the traceback from forking
- use makedirs instead of mkpath in fork action
- if anything bad happens, log exception in generate_gpg_key action
- also restart copr-backend-vmm and copr-backend-log when (re)installing
- Bug 1361344 - RFE: Allow denial of build deletion and resubmitting at project or group level
- catch errors in fork action
- set action result for comps.xml and module_md.yaml file deletion
- backend fork action now takes care of new gpg-key generation instead of frontend
- removed no longer supported --api-version=0.8 arg from appstream-builder command line
- specify module_md as module type
- fix saving comps.xml and module_md.yaml into empty copr (with no build)
- module_md.yaml is added to repodata now similarly to appstream.xml
- support for generation of module dist tags
- module_md.yaml uploading for a chroot
- simplified build and action task workflow
- use copy of the mock (chroot) config, not the original in /etc/mock/

* Wed Jun 22 2016 Miroslav Suchý <msuchy@redhat.com> 1.91-1
- configure more packages to run pylint
- terminate machine which was only partially spawned
- [copr-prune-results] do not sys.exit if prunerepo returns non-zero status,
  just raise an exception
- more of log file migration
- claim /var/log/copr-backend in %%files
- adjust log path in runtime files
- update conf file log path directives
- change logdir to /var/log/copr-backend/

* Fri May 27 2016 Miroslav Suchý <msuchy@redhat.com> 1.90-1
- do not use --log-dir in appstream-builder

* Tue May 24 2016 Miroslav Suchý <miroslav@suchy.cz> 1.89-1
- use correct conditional in requires

* Mon May 23 2016 Miroslav Suchý <msuchy@redhat.com> 1.88-1
- backend: change logstash requires to soft requires
- 1336360 - allow custom chroots

* Fri May 13 2016 Miroslav Suchý <msuchy@redhat.com> 1.87-1
- workaround for BZ 1334200
- more info in logs by default
- print seconds just as int
- unsign gpg from forked packages before signing them with new key
- sign forked packages @TODO We need to delsign them first

* Fri May 06 2016 Miroslav Suchý <msuchy@redhat.com> 1.86-1
- more info in logs by default
- unsign gpg from forked packages before signing them with new key

* Thu May 05 2016 Miroslav Suchý <msuchy@redhat.com> 1.85-1
- also be tolerant about sign/unsign failures on particular rpm
- just log errors (exception) during particular copr fixing, do not
  interrupt the whole process
- added additional check on copr path existence into copr_fix_gpg.py
- allow sudo /usr/bin/rpm for `copr` user
- look into build dirs (subdirs of a chroot) for rpms to be re-signed
- on F24+ use just ansible
- Run rpm-sign with sudo when unsigning
- script to fix gpg keys & rpm signatures
- define functions for deleting gpg signatures from packages
- removed temporary mock workaround from Dockerfile (no
  longer needed)

* Thu Apr 28 2016 Miroslav Suchý <msuchy@redhat.com> 1.84-1
- Bug 1327996 - config_opts['use_host_resolv'] is not set back to
  True if it was False before

* Fri Apr 22 2016 Miroslav Suchý <msuchy@redhat.com> 1.83-1
- run createrepo on forked project (RhBug: 1329076)
- Bug 1327852 - /usr/bin/check_consecutive_build_fails.py errors
- we need to stick to ansible1.9
- more escaping
- prunning down testresults :)
- a few unittests for copr_prune_results.py script
- unit test "fixes"
- fix error when forking into existing project
- (mockremote): improve chroot_setup_cmd replacement for EL-5
- copr_prune_results.py - python path fix
- Bug 1324514 - copr createrepo error messages - fix for errors of
  type one
- Bug 1324514 - copr createrepo error messages - fix for errors of
  type 2

* Thu Mar 24 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.82-1
- use timeout variable from config

* Mon Mar 14 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.81-1
- support project forking
- support building from PyPI
- support for redis_host, redis_port, redis_db config options
- dockerized-backend project moved under backend/docker
- run createrepo in rawhide_to_release
- specify rawhide name when calling rawhide_to_release

* Fri Jan 29 2016 Miroslav Suchý <msuchy@redhat.com> 1.80-1
- do not fail when when you receive job with architecture which does not have
  queue
- fix 1260780 - Build fails after successful package generation -
  just add a log error message pointing to an rsync log
- jobgrabcontrol.py/retask misuse fix
- "localhost-targeted" spawn and terminate playbooks added for testing
- [frontend]implement rawhide to release feature First create new
  chroots:     python manage.py create_chroot fedora-24-i386 fedora-24-x86_64
- abstraction above [BE <-> JG <-> Builders] channels
- don't traceback backend if frontend is not yet up&running
- do not preserve user and group when rsyncing

* Wed Dec 23 2015 Miroslav Suchý <msuchy@redhat.com> 1.79-1
- fix packaging issues in epel-7+

* Mon Nov 16 2015 Miroslav Suchý <miroslav@suchy.cz> 1.78-1
- handle_generate_gpg_key skips key creation when signing is disabled
- Added test_handle_generate_gpg_key
- fixed failing tests
- show when createrepo is waiting for lock
- do not block builds when processing too much actions

* Fri Nov 06 2015 Miroslav Suchý <msuchy@redhat.com> 1.77-1
- we need to have recent python-copr
- create copr-backend-service script to handle all copr services
- [backend] fix not starting job_grab

* Tue Oct 13 2015 Miroslav Suchý <msuchy@redhat.com> 1.76-1
- createrepo action run infinitely when applied to
  deleted project

* Mon Sep 21 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.75-1
- [backend] run copr-backend-log service before other components

* Mon Sep 21 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.74-1
- [backend] add executable bit to run/copr_run_job_grab.py

* Mon Sep 21 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.73-1
- added context manager `local_file_logger`
- eliminated global multiprocessing.Lock
- split backend daemon: extracted RedisLogHandler, JobGrab, VMM
- replace python-bunch with python-munch
- added comps.xml support

* Tue Aug 04 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.72-1
- support new results naming in the build deletion action
- fix BuildJob.results_dir; eliminated MockRemote.pkg_dest_path
- using package name and versiong given in the build task; cleanup;
- handle error's caused by failure to obtain srpm from dist-git
- repairing test for newest changes
- rsync update + several fixes
- building from dist git
- fix vm spawn check: spawner count child processes per build group;

* Wed Jul 01 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.71-1
- add small script to print queues
- AppData supproted
- copy mockchain and rsync logs to resdir (RhBug:1221519)
- note which modules still stops us from migrating to python3

* Mon Jun 15 2015 Miroslav Suchý <msuchy@redhat.com> 1.70-1
- alter vm_name= regexp
- polishing Bug 1195867 - Move or delete logs when rebuilding failed
  build.
- backup only info and log files
- have just one backup directory per results directory
- clean results from previous build
- alter IP= regexp
- disabled appdata until fixed
- unable appdata in createrepo
- more safe VmMaster.check_one_vm_for_dead_builder function
- adding support for AppData
- new requirement form AppData support
- createrepo_unsafe now returns only STDOUT and raise exception on
  errors

* Mon Jun 01 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.69-1
- removed creation of symlinks for log.gz
- catch exception during Worker.can_start_job
- config cleanup

* Thu May 28 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.68-1
- [backend] add config option for VM health check timeout
- [backend] moved config parameters from Threshold class into the backend
  config file

* Thu May 21 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.67-1
- [backend] Handle unexpected exception VmMaster::check_one_vm_for_dead_builder

* Thu May 21 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.66-1
- [backend] fix race condition in check for dead worker

* Wed May 20 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.65-1
- [backend] Rescheduling unfinished builds before stop
- fix indentation
- [backend] request frontend to reschedule old unfinished builds at startup
- [backend] update sytemd unit: removed obsolete
  EnviromentFile=/home/copr/cloud/ec2rc.variable directive

* Tue May 19 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.64-1
- [backend] check for aux process state and restart if needed

* Fri May 15 2015 Miroslav Suchý <msuchy@redhat.com> 1.63-1
- BR python-sphinx

* Fri May 15 2015 Miroslav Suchý <msuchy@redhat.com> 1.62-1
- [backend] small cleanup, need more tests

* Fri May 15 2015 Miroslav Suchý <msuchy@redhat.com> 1.61-1
- [backend] notify job_grab to remove job from added when start_job failed
- [backend] [vmm] terminate VM with state IN_USE only when builder process is
  missed
- [backend] bugfix VMM.get_all_vm_in_group : VM could be removed before load
  occures
- [backend] job_grab: postpone build is we already serving more builds
  than`max_vm_per_user` option
- [backend] fix build logging
- [backend] defer sending job to worker if job owner acquired too much VMs
- [backend] replaced Thresholds.dirty_vm_terminating_timeout with config option
  vm_dirty_terminating_timeout
- [backend] Thread's doesn't have a pid
- [backend] vm manage: user threading instead of multiprocessing
- [backend] VMM aware cleunup_vm_nova
- [backend] moving to nginx to serve results. lighttpd couldnt server pre-
  compressed properly
- [backend] script to clean up erred and forgotten VM's using python-novaclient
- [backend] new documentation
- [backend] repaired unittests
- [backend] updated builder playbooks
- [backend] updated example spawn playbook
- [backend] don't provide logstash config directly, add only example to
  documentation
- [backend] do logging from multiply processes through redis pubsub; some fixes
  to VM-management
- [image_builder] initial release, due to OS bug, we cannot create snapshot
  after provision through API, need to do it manually in the WebUI.
- [backend] tests cleanup
- [backend] ensure that prune script running under the copr user; simpler
  `copr_find_obsolete_builds`
- [backend] safer copr_prune_results script,  unittests
- [backend][frontend] Send for delete action only `src_pkg_name` instead of
  original URL.
- [backend] returned script to call createrepo from cli
- [copr] don't allow acquire VMs that was last checked before server restart.
- [backend] Added limit to acquire_vm based on VMs used by the same username at
  the current moment.
- New python dependencies
- [backend] run tmp redis-server for tests
- [backend] Dedicated and more complex management for builder machines.
  [frontend] Now builds failed due to VM errors reschedulted faster.

* Fri Mar 20 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.60-1
- [backend][spec] start/stop redis server during package build tests

* Fri Mar 20 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.59-1
- [backend][hotfix] 1203753 : don't process delete action if src_pkg is
  mallformed

* Mon Mar 02 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.58-1
- [rhbz:#1185959] - RFE: Present statistics about project
  popularity. A few more counters for downloads from backend's result
  directory.
- [backend] [rhbz:#1191037] RFE: Include package name and version in fedmsg
  notification
- [rhbz:#1091640] RFE: Release specific additional repos
- [rhbz:#1119300]  [RFE] allow easy add copr repos in using
  repository lis
- [backend][frontend] removing code related to multiply source rpms in build.
  Build.pkgs now expected to have exactly one src.rpm.
- [copr] backend: script fixes, dropped create_repo cli script
- more file descriptors on builder
- [rhbz:#1171796] copr sometimes doesn't delete build from repository
- [rhbz:#1073333] Record consecutive builds fails to redis. Added
  script to produce warnings for nagios check from failures recorded to redis.
- correctly print job representation

* Fri Jan 23 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.57-1
- call correct Worker method on backend termination
- put gpg pubkey to the project results root dir (one level up from
  the chroot dir)
- don't kill Worker from errors during job build
- [rhbz:#1169782] RFE - Show package "version-release" instead of
  just "version"
- [rhbz:#1117446] add a build id tagfile into the package directory
- Updated unittests to reflect latest changes.
- builder: use only one log file for rsync per build
- dispatcher: run terminate_instance safely
- cleanup example config
- cleanup mockremote.builder
- Builder.download don't use Popen+PIPE.communicate with rsync,
  output redirected to the files.
- disable networking only when required; python style exception
  handling in mockremote*; removed run/copr_mockremote
- test build with disabled networking
- simplified  mockremote.builder.Builder.check_for_ans_error; new
  method mockremote.builder.Builder.run_ansible_with_check
- daemons.dispatched.Worker: don't fail when wrong group_id was
  provided
- add vm_ip to worker process title (rhbz: 1182637)

* Wed Jan 14 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.56-1
- [backend] [.spec] fix %%files section

* Wed Jan 14 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.55-1
- [backend] [bugfix] set pythonpath in systemd unit to run /usr/bin/copr_be.py
- [backend] [RHBZ:#1182106] JobGrabber dies when action raises an exception.
- [backend] Moved scripts into /usr/bin/ Renamed copr{-,_}be.py.

* Wed Jan 07 2015 Miroslav Suchý <msuchy@redhat.com> 1.54-1
- 1179713 - workaround for 1179806
- run script unbufferred otherwise log is written after full block
- express that it is n-th projects
- fix permissions on prune script

* Mon Jan 05 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.53-1
- [backend, frontend] [RHBZ:#1176364] Wrong value for the build timeout.

* Mon Dec 15 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.52-1
- fixed config option `results_baseurl` usage, in mockremote

* Fri Dec 12 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.51-1
- updated BuildRequires; cleanup imports
- package sign: generate gpg usermail with special symbol
- bugfix: when dispatcher has vm_ip it shouldn't start new VM;
- run tests during rpm build
- minor docstring fix

* Wed Dec 10 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.50-1
- [backend] added option to control ansible ssh transport, changed by default
  to `paramiko` [frontend] bugfix api create new
- [backend] removed spawn_vars options, to be able to spawn VMs in advance
- [backend] unittest for backend.daemons.log
- [backend] massive refactoring and unittest coverage
- [backend] backend.sign: discover `keygen_host` from backend config file

* Tue Nov 25 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.49-1
- [backend] small bug in dispatcher

* Tue Nov 25 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.48-1
- bugfixes, disabled debug prints, fixed PEP8 violations

* Thu Nov 20 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.47-1
- refactored mockremote, added  explicit BuildJob class
- allow to spawn builder in advance
- copr-prune-repo respects auto_createrepo option
- bugfix: repeated config reads produced constantly growing lists

* Fri Oct 24 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.46-1
- [backend] added handling of new action type: "createrepo"
- [backend] added dependency on `python-copr`
- [backend] added to mockchroot -a /devel/repodata subfolder
- [backend] new config option to define the public frontend api endpoint
- [backend] conditional execution of createrepo_c
- [backend] unittest for Action and minor refactoring
- [backend] rotate backend.log as well

* Thu Sep 18 2014 Miroslav Suchý <msuchy@redhat.com> 1.45-1
- [backend][keygen] minor fixes/typos

* Thu Sep 18 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.44-1
- [backend] type fix

* Thu Sep 18 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.43-1
- [backend] config parsing: convert fields to proper data type.
- [backend] added option to disable package signing.
- [keygen] new component for copr: gpg key generation for package sign
- [backend] broadcast both submitter and owner to fedmsg
- [backend] example backend config: changes url protocol to HTTPS.

* Mon Aug 25 2014 Adam Samalik <asamalik@redhat.com> 1.42-1
- [backend] [RHBZ:1128606 ] For rhel-5 builds pass "--checksum md5" to
  `createrepo_c` command.
- [backend] fix of builder test
- [backend] test builder instance after spawning
- [backend] never give up while spawning an OpenStack VM
- [backend] worker's log filename correction
- [backend] task id in worker process' name
- [backend] async build playbooks

* Thu Aug 14 2014 Miroslav Suchý <miroslav@suchy.cz> 1.41-1
- [backend] fix of fix
- [backend] couple of fixes

* Wed Aug 13 2014 Miroslav Suchý <msuchy@redhat.com> 1.40-1
- [backend] queue cleaning
- [backend] experimental build groups for more architectures
- [backend] fix of a strange beaviour of retask
- [backend] fedmsg shows submitter instead of project owner
- [backend] new task queue for workers using retask
- epel-7 comps workaround is need no more, since CENTOS7 have been released

* Tue Jul 22 2014 Miroslav Suchý <msuchy@redhat.com> 1.39-1
- FrontendCallback prettified
- Starting state implemented, cancelling fixed
- [backend] faster skipping

* Tue Jul 15 2014 Miroslav Suchý <msuchy@redhat.com> 1.38-1
- [backend] built pkgs fix

* Tue Jul 15 2014 Miroslav Suchý <msuchy@redhat.com> 1.37-1
- [backend] shell command uses pipes.quote
- Return the chroot that finished when sending build.end
- better and safer deleting of builds
- [backend] separate playbooks for each architecture
- [backend] built pkgs - include subpackages
- [backend] skipped status and package details implemented
- document vm_name option

* Thu Jun 19 2014 Miroslav Suchý <msuchy@redhat.com> 1.36-1
- backend: migrate to nova ansible module
- backend: make sure that exit() exit whole script not just sub-shell
- backend: allow passing additional info to playbooks
- handle {spawn,terminate}_instance equally
- backend: stop if you could not change to directory
- W:310, 8: Attribute 'abort' defined outside __init__ (attribute-defined-
  outside-init)
- W:139, 0: Dangerous default value [] as argument (dangerous-default-value)
  W:139, 0: Dangerous default value [0] as argument (dangerous-default-value)
  W:139, 0: Dangerous default value ['stdout', 'stderr'] as argument
  (dangerous-default-value)
- W:543, 4: Dangerous default value DEF_MACROS ({}) as argument (dangerous-
  default-value)
- W:543, 4: Dangerous default value DEF_REPOS ([]) as argument (dangerous-
  default-value)
- W:677,24: Unused variable 'out' (unused-variable) W:677,20: Unused variable
  'rc' (unused-variable)
- W:297,12: Unused variable 'hn' (unused-variable)
- C:116, 0: Unnecessary parens after 'print' keyword (superfluous-parens)
- W: 72,28: Unused variable 'out' (unused-variable) W: 72,24: Unused variable
  'rc' (unused-variable)
- fix typo in exception message printing
- 1102788 - Increase number of file descriptors on the build machine

* Fri May 30 2014 Miroslav Suchý <msuchy@redhat.com> 1.35-1
- follow selinux packaging draft
- [backend] epel 5 repo fix (sha256 -> sha)

* Thu Apr 24 2014 Miroslav Suchý <msuchy@redhat.com> 1.34-1
- if directory does not exist, do not try to delete it

* Tue Apr 15 2014 Miroslav Suchý <miroslav@suchy.cz> 1.33-1
- do not publish copr.worker messages
- better count workers

* Thu Apr 10 2014 Miroslav Suchý <msuchy@redhat.com> 1.32-1
- include ec2rc in service unit file

* Wed Apr 09 2014 Miroslav Suchý <msuchy@redhat.com> 1.31-1
- 1077791 - set perm of cronfile to 755
- 1077791 - add LICENSE to -doc subpackage
- 1077791 - remove make as BR

* Tue Mar 18 2014 Miroslav Suchý <msuchy@redhat.com> 1.30-1
- [backend] exclude files which are part of main package
- copr-backend.src:113: W: mixed-use-of-spaces-and-tabs (spaces: line 5, tab:
  line 113)

* Tue Mar 18 2014 Miroslav Suchý <msuchy@redhat.com> 1.29-1
- move backend into separate package

* Thu Feb 27 2014 Miroslav Suchý <msuchy@redhat.com> 1.28-1
- [backend] - pass lock to Actions

* Wed Feb 26 2014 Miroslav Suchý <msuchy@redhat.com> 1.27-1
- [frontend] update to jquery 1.11.0
- [fronted] link username to fas
- [cli] allow to build into projects of other users
- [backend] do not create repo in destdir
- [backend] ensure that only one createrepo is running at the same time
- [cli] allow to get data from sent build
- temporary workaround for BZ 1065251
- Chroot details API now uses GET instead of POST
- when deleting/canceling task, go to same page
- add copr modification to web api
- 1063311 - admin should be able to delete task
- [frontend] Stray end tag h4.
- [frontend] another s/coprs/projects/ rename
- [frontend] provide info about last successful build
- [spec] rhel5 needs group definition even in subpackage
- [frontend] move 'you agree' text to dd
- [frontend] add margin to chroots-set
- [frontend] add margin to field label
- [frontend] put disclaimer to paragraph tags
- [frontend] use black font color
- [frontend] use default filter instead of *_not_filled
- [frontend] use markdown template filter
- [frontend] use isdigit instead of is_int
- [frontend] move Serializer to helpers
- [frontend] fix coding style and py3 compatibility
- [cli] fix coding style and py3 compatibility
- [backend] fix coding style and py3 compatibility

* Tue Jan 28 2014 Miroslav Suchý <miroslav@suchy.cz> 1.26-1
- lower testing date
- move localized_time into filters
- [frontend] update user data after login
- [frontend] use iso-8601 date

* Mon Jan 27 2014 Miroslav Suchý <msuchy@redhat.com> 1.25-1
- 1044085 - move timezone modification out of template and make it actually
  work
- clean up temp data if any
- [db] timezone can be nullable
- [frontend] actually save the timezone to model
- fix colision of revision id
- 1044085 - frontend: display time in user timezone
- [frontend] rebuild stuck task
- disable test on i386
- use experimental createrepo_c to get rid of lock on temp files
- [frontend] - do not throw ISE when build_id is malformed
- [tests] add test for BuildLogic.add
- [tests] add test for build resubmission
- [frontend] permission checking is done in BuildLogic.add
- [frontend] remove BuildLogic.new, use BL.add only
- [api] fix validation error handling
- [cli] fix initial_pkgs and repos not sent to backend
- [frontend] fix BuildsLogic.new not assigning copr to build
- [frontend] allow resubmitting builds from monitor
- [frontend] allow GET on repeat_build
- [frontend] 1050904 - monitor shows not submitted chroots
- [frontend] rename active_mock_chroots to active_chroots
- [frontend] rename MockChroot.chroot_name to .name
- [frontend] 1054474 - drop Copr.build_count nonsense
- [tests] fix https and repo generation
- [tests] return exit code from manage.py test
- 1054472 - Fix deleting multiple SRPMs
- [spec] tighten acl on copr-be.conf
- [backend] - add missing import
- 1054082 - general: encode to utf8 if err in mimetext
- [backend] lock log file before writing
- 1055594 - mockremote: always unquote pkg url
- 1054086 - change vendor tag
- mockremote: rawhide instead of $releasever in repos when in rawhide chroot
- 1055499 - do not replace version with $releasever on rawhide
- 1055119 - do not propagate https until it is properly signed
- fix spellings on chroot edit page
- 1054341 - be more verbose about allowed licenses
- 1054594 - temporary disable https in repo file

* Thu Jan 16 2014 Miroslav Suchý <msuchy@redhat.com> 1.24-1
- add BR python-markdown
- [fronted] don't add description to .repo files
- [spec] fix with_tests conditional
- add build deletion
- 1044158 - do not require fas username prior to login
- replace http with https in copr-cli and in generated repo file
- [cli] UX changes - explicitly state that pkgs is URL
- 1053142 - only build copr-cli on el6
- [frontend] correctly handle mangled chroot
- [frontend] do not traceback when user malform url
- [frontend] change default description and instructions to sound more
  dangerously
- 1052075 - do not set chroots on repeated build
- 1052071 - do not throw ISE when copr does not exist

* Mon Jan 13 2014 Miroslav Suchý <msuchy@redhat.com> 1.23-1
- [backend] rhel7-beta do not have comps
- 1052073 - correctly parse malformed chroot

* Fri Jan 10 2014 Miroslav Suchý <msuchy@redhat.com> 1.22-1
- [backend] if we could not spawn VM, wait a moment and try again
- [backend] use createrepo_c instead of createrepo
- 1050952 - check if copr_url exist in config
- [frontend] replace newlines in description by space in repo file

* Wed Jan 08 2014 Miroslav Suchý <msuchy@redhat.com> 1.21-1
- 1049460 - correct error message
- [cron] manually clean /var/tmp after createrepo

* Wed Jan 08 2014 Miroslav Suchý <msuchy@redhat.com> 1.20-1
- [cli] no need to set const with action=store_true
- [cli] code cleanup
- 1049460 - print nice error when projects does not exist
- 1049392 - require python-setuptools
- [backend] add --verbose to log to stderr
- [backend] handle KeyboardInterrupt without tons of tracebacks
- 1048508 - fix links at projects lists
- [backend] in case of error the output is in e.output
- [selinux] allow httpd to search
- [backend] set number of worker in name of process
- [logrotate] rotate every week unconditionally
- [backend] do not traceback if jobfile is mangled
- [backend] print error messages to stderr
- [cli] do not require additional arguments for --nowait
- [backend] replace procname with setproctitle
- [cli] use copr.fedoraproject.org as default url
- [frontend] show monitor even if last build have been canceled
- [backend] call correct function
- [cli] print errors to stderr
- 1044136 - do not print TB if config in mangled
- 1044165 - Provide login and token information in the same form as entered to
  ~/.config-copr
- [frontend] code cleanup
- [frontend] move rendering of .repo file to helpers
- 1043649 - in case of Fedora use $releasever in repo file
- [frontend] condition should be in reverse

* Mon Dec 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.19-1
- [backend] log real cause if ansible crash
- [frontend] try again if whoosh does not get lock
- [backend] if frontend does not respond, repeat
- print yum repos nicely
- Bump the copr-cli release to 0.2.0 with all the changes made
- Refer to the man page for more information about the configuration file for
  copr-cli
- Rework the layout of the list command
- Fix parsing the copr_url from the configuration file
- [backend] run createrepo as copr user
- 1040615 - wrap lines with long URL

* Wed Dec 11 2013 Miroslav Suchý <msuchy@redhat.com> 1.18-1
- [frontend] inicialize variable

* Wed Dec 11 2013 Miroslav Suchý <msuchy@redhat.com> 1.17-1
- [frontend] fix latest build variable overwrite

* Wed Dec 11 2013 Miroslav Suchý <msuchy@redhat.com> 1.16-1
- [backend] store jobs in id-chroot.json file
- [frontend] handle unknown build/chroot status
- use newstyle ansible variables

* Tue Dec 10 2013 Miroslav Suchý <msuchy@redhat.com> 1.15-1
- [frontend] smarter package name parsing
- [frontend] extend range to allow 0
- handle default timeout on backend
- initial support for SCL
- [backend] create word readable files in result directory
- [backend] print tracebacks
- [frontend] monitor: display only pkg name w/o version
- [doc] update api docs
- [doc] update copr-cli manpage
- [cli] list only name, description and instructions
- [cli] add support for build status & build monitor
- [frontend] add build status to API
- [playbook] do not overwrite mockchain
- [backend] add spece between options
- [backend] pass mock options correctly
- [frontend] support markdown in description and instructions
- [backend] Add macros to mockchain define arguments
- [backend] Pass copr username and project name to MockRemote
- [backend] Handle additional macro specification in MockRemote
- [frontend] monitor: show results per package
- [frontend] add favicon
- [backend] quote strings before passing to mockchain
- send chroots with via callback to frontend
- [cli] change cli to new api call
- enhance API documentation
- add yum_repos to coprs/user API call
- [frontend] provide link to description of allowed content
- [backend] we pass just one chroot
- [backend] - variable play is not defined
- if createrepo fail, run it again
- [cron] fix syntax error
- [man] state that --chroot for create command is required
- [spec] enable tests
- [howto] add note about upgrading db schema
- [frontend]: add copr monitor
- [tests]: replace test_allowed_one
- [tests]: fix for BuildChroots & new backend view
- [frontend] rewrite backend view to use Build <-> Chroot relation
- [frontend] add Build <-> Chroot relation
- 1030493 - [cli] check that at least one chroot is entered
- [frontend] typo
- fixup! [tests]: fix test_build_logic to handle BuildChroot
- fixup! [frontend] add ActionsLogic
- [tests]: fix test_build_logic to handle BuildChroot
- [spec] enable/disable test using variable
- add migration script - add table build_chroot
- [frontend] skip legal-flag actions when dumping waiting actions
- [frontend] rewrite backend view to use Build <-> Chroot relation
- [frontend] add ActionsLogic
- [frontend] create BuildChroot objects on new build
- [frontend] add Build <-> Chroot relation
- [frontend] add StatusEnum
- [frontend] fix name -> coprname typo
- [frontend] remove unused imports
- [frontend] add missing json import
- [backend] rework ip address extraction
- ownership of /etc/copr should be just normal
- [backend] - wrap up returning action in "action" blok
- [backend] rename backend api url
- [backend] handle "rename" action
- [backend] handle "delete" action
- base handling of actions
- move callback to frontend to separate object
- secure waiting_actions with password
- pick only individual builds
- make address, where we send legal flags, configurable
- send email to root after legal flag have been raised

* Fri Nov 08 2013 Miroslav Suchý <msuchy@redhat.com> 1.14-1
- 1028235 - add disclaimer about repos
- fix pagination
- fix one failing test

* Wed Nov 06 2013 Miroslav Suchý <msuchy@redhat.com> 1.13-1
- suggest correct name of repo file
- we could not use releasever macro
- no need to capitalize Projects
- another s/copr/project
- add link to header for sign-in
- fix failing tests
- UX - let textarea will full widht of box
- UX - make background of hovered builds darker
- generate yum repo for each chroot of copr
- align table header same way as ordinary rows
- enable resulting repo and disable gpgchecks

* Mon Nov 04 2013 Miroslav Suchý <msuchy@redhat.com> 1.12-1
- do not send parameters when we neither need them nor use them
- authenticate using api login, not using username
- disable editing name of project
- Add commented out WTF_CSRF_ENABLED = True to configs
- Use new session for each test
- fix test_coprs_general failures
- fix test_coprs_builds failures
- Add WTF_CSRF_ENABLED = False to unit test config
- PEP8 fixes
- Fix compatibility with wtforms 0.9
- typo s/submited/submitted/
- UX - show details of build only after click
- add link to FAQ to footer
- UX - add placeholders
- UX - add asterisk to required fields
- dynamicly generate url for home
- add footer

* Sat Oct 26 2013 Miroslav Suchý <msuchy@redhat.com> 1.11-1
- catch IOError from libravatar if there is no network

* Fri Oct 25 2013 Miroslav Suchý <msuchy@redhat.com> 1.10-1
- do not normalize url
- specify full prefix of http
- execute playbook using /usr/bin/ansible-playbook
- use ssh transport
- check after connection is made
- add notes about debuging mockremote
- clean up instance even when worker fails
- normalize paths before using
- do not use exception variable
- operator should be preceded and followed by space
- remove trailing whitespace
- convert comment to docstring
- use ssh transport
- do not create new ansible connection, reuse self.conn
- run copr-be.py as copr
- s/Copr/Project/ where we use copr in meaning of projects
- number will link to those coprs, to which it refers
- run log and jobgrab as copr user
- log event to log file
- convert comment into docstring
- use unbufferred output for copr-be.py
- hint how to set ec2 variables
- document sleeptime
- document copr_url for copr-cli
- document how to set api key for copr-cli
- do not create list of list
- document SECRET_KEY variable
- make note how to become admin
- instruct people to install selinux with frontend

* Thu Oct 03 2013 Miroslav Suchý <msuchy@redhat.com> 1.9-1
- prune old builds
- require python-decorator
- remove requirements.txt
- move TODO-backend to our wiki
- create pid file in /var/run/copr-backend
- add backend service file for systemd
- remove daemonize option in config
- use python logging
- create pid file in /var/run by default
- do not create destdir
- use daemon module instead of home brew function
- fix default location of copr-be.conf
- 2 tests fixed, one still failing
- fix failing test test_fail_on_missing_dash
- fixing test_fail_on_nonexistent_copr test
- run frontend unit tests when building package
- Adjust URLs in the unit-tests to their new structure
- Adjust the CLI to call the adjuste endpoint of the API
- Adjust API endpoint to reflects the UI endpoints in their url structure
- First pass at adding fedmsg hooks.

* Tue Sep 24 2013 Miroslav Suchý <msuchy@redhat.com> 1.8-1
- 1008532 - require python2-devel
- add note about ssh keys to copr-setup.txt
- set home of copr user to system default

* Mon Sep 23 2013 Miroslav Suchý <msuchy@redhat.com> 1.7-1
- 1008532 - backend should own _pkgdocdir
- 1008532 - backend should owns /etc/copr as well
- 1008532 - require logrotate
- 1008532 - do not distribute empty copr.if
- 1008532 - use %%{?_smp_mflags} macro with make
- move jobsdir to /var/lib/copr/jobs
- correct playbooks path
- selinux with enforce can be used for frontend

* Wed Sep 18 2013 Miroslav Suchý <msuchy@redhat.com> 1.6-1
- add BR python-devel
- generate selinux type for /var/lib/copr and /var/log/copr
- clean up backend setup instructions
- initial selinux subpackage

* Mon Sep 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.5-1
- 1008532 - use __python2 instead of __python
- 1008532 - do not mark man page as doc
- 1008532 - preserve timestamp

* Mon Sep 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.4-1
- add logrotate file

* Mon Sep 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.3-1
- be clear how we create tgz

* Mon Sep 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.2-1
- fix typo
- move frontend data into /var/lib/copr
- no need to own /usr/share/copr by copr-fe
- mark application as executable
- coprs_frontend does not need to be owned by copr-fe
- add executable attribute to copr-be.py
- remove shebang from dispatcher.py
- squeeze description into 80 chars
- fix typo
- frontend need argparse too
- move results into /var/lib/copr/public_html
- name of dir is just copr-%%version
- Remove un-necessary quote that breaks the tests
- Adjust unit-tests to the new urls
- Update the URL to be based upon a /user/copr/<action> structure
- comment config copr-be.conf and add defaults
- put examples of builderpb.yml and terminatepb.yml into doc dir
- more detailed description of copr-be.conf
- move files in config directory not directory itself
- include copr-be.conf
- include copr-be.py
- create copr with lighttpd group
- edit backend part of copr-setup.txt
- remove fedora16 and add 19 and 20
- create -doc subpackage with python documentation
- add generated documentation on gitignore list
- add script to generate python documentation
- copr-setup.txt change to for mock
- rhel6 do not know _pkgdocdir macro
- make instruction clear
- require recent whoosh
- add support for libravatar
- include backend in rpm
- add notes about lighttpd config files and how to deploy them
- do not list file twice
- move log file to /var/log
- change destdir in copr-be.conf.example
- lightweight is the word and buildsystem has more meaning than 'koji'.
- restart apache after upgrade of frontend
- own directory where backend put results
- removal of hidden-file-or-dir
  /usr/share/copr/coprs_frontend/coprs/logic/.coprs_logic.py.swo
- copr-backend.noarch: W: spelling-error %%description -l en_US latests ->
  latest, latest's, la tests
- simplify configuration - introduce /etc/copr/copr*.conf
- Replace "with" statements with @TransactionDecorator decorator
- add python-flexmock to deps of frontend
- remove sentence which does not have meaning
- change api token expiration to 120 days and make it configurable
- create_chroot must be run as copr-fe user
- add note that you have to add chroots to db
- mark config.py as config so it is not overwritten during upgrade
- own directory data/whooshee/copr_user_whoosheer
- gcc is not needed
- sqlite db must be owned by copr-fe user
- copr does not work with selinux
- create subdirs under data/openid_store
- suggest to install frontend as package from copr repository
- on el6 add python-argparse to BR
- add python-requests to BR
- add python-setuptools to BR
- maintain apache configuration on one place only
- apache 2.4 changed access control
- require python-psycopg2
- postgresql server is not needed
- document how to create db
- add to HOWTO how to create db
- require python-alembic
- add python-flask-script and python-flask-whooshee to requirements
- change user in coprs.conf.example to copr-fe
- fix paths in coprs.conf.example
- copr is noarch package
- add note where to configure frontend
- move frontend to /usr/share/copr/coprs_frontend
- put production placeholders in coprs_frontend/coprs/config.py
- put frontend into copr.spec
- web application should be put in /usr/share/%%{name}

* Mon Jun 17 2013 Miroslav Suchý <msuchy@redhat.com> 1.1-1
- new package built with tito


