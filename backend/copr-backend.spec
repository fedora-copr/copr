%if 0%{?rhel} < 7 && 0%{?rhel} > 0
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%endif

Name:       copr-backend
Version:    1.58
Release:    1%{?dist}
Summary:    Backend for Copr

Group:      Applications/Productivity
License:    GPLv2+
URL:        https://fedorahosted.org/copr/
# Source is created by
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/backend
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

BuildArch:  noarch
BuildRequires: asciidoc
BuildRequires: libxslt
BuildRequires: util-linux
BuildRequires: python-setuptools
BuildRequires: python-requests
BuildRequires: python2-devel
BuildRequires: python-copr
BuildRequires: systemd
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
BuildRequires: python-argparse
%endif
#for doc package
BuildRequires: epydoc
BuildRequires: graphviz
BuildRequires: pytest
BuildRequires: python-pytest-cov
BuildRequires: python-mock
BuildRequires: python-six
BuildRequires: python-bunch
BuildRequires: python-daemon
BuildRequires: python-lockfile
BuildRequires: python-requests
BuildRequires: python-setproctitle
BuildRequires: python-retask
BuildRequires: python-copr
BuildRequires: python-six
BuildRequires: ansible >= 1.2
BuildRequires: python-IPy
BuildRequires: python-paramiko
BuildRequires: python-psutil
BuildRequires: wget

Requires:   obs-signd
Requires:   ansible >= 1.2
Requires:   lighttpd
Requires:   euca2ools
Requires:   rsync
Requires:   openssh-clients
Requires:   mock
Requires:   yum-utils
Requires:   createrepo_c >= 0.2.1-3
Requires:   python-bunch
Requires:   python-daemon
Requires:   python-lockfile
Requires:   python-requests
Requires:   python-setproctitle
Requires:   python-retask
Requires:   python-copr
Requires:   python-six
Requires:   python-IPy
Requires:   python-psutil
Requires:   redis
Requires:   logrotate
Requires:   fedmsg
Requires:   gawk
Requires:   crontabs
Requires:   python-paramiko
# Requires:   logstash

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
%setup -q


%build
# build documentation
pushd documentation
make %{?_smp_mflags} python
popd

%install

install -d %{buildroot}%{_sharedstatedir}/copr
install -d %{buildroot}%{_sharedstatedir}/copr/jobs
install -d %{buildroot}%{_sharedstatedir}/copr/public_html/results
install -d %{buildroot}%{_var}/log/copr
install -d %{buildroot}%{_var}/log/copr/workers/
install -d %{buildroot}%{_pkgdocdir}/lighttpd/
install -d %{buildroot}%{_datadir}/copr/backend
install -d %{buildroot}%{_sysconfdir}/copr
install -d %{buildroot}%{_sysconfdir}/logrotate.d/
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}/%{_var}/log/copr-backend
install -d %{buildroot}/%{_var}/run/copr-backend/
install -d %{buildroot}/%{_tmpfilesdir}
install -d %{buildroot}/%{_sbindir}
install -d %{buildroot}%{_sysconfdir}/cron.daily
install -d %{buildroot}%{_sysconfdir}/sudoers.d
install -d %{buildroot}%{_bindir}/

cp -a backend/* %{buildroot}%{_datadir}/copr/backend
cp -a run/* %{buildroot}%{_bindir}/
cp -a conf/copr-be.conf.example %{buildroot}%{_sysconfdir}/copr/copr-be.conf

install -p -m 755 conf/crontab/copr-backend %{buildroot}%{_sysconfdir}/cron.daily/copr-backend

cp -a conf/lighttpd/* %{buildroot}%{_pkgdocdir}/lighttpd/
cp -a conf/logrotate/* %{buildroot}%{_sysconfdir}/logrotate.d/
cp -a conf/tmpfiles.d/* %{buildroot}/%{_tmpfilesdir}

# for ghost files
touch %{buildroot}%{_var}/log/copr/copr.log
touch %{buildroot}%{_var}/log/copr/prune_old.log

for i in `seq 7`; do
    touch %{buildroot}%{_var}/log/copr/workers/worker-$i.log
done
touch %{buildroot}%{_var}/run/copr-backend/copr-be.pid

install -m 0644 copr-backend.service %{buildroot}/%{_unitdir}/
install -m 0644 conf/copr.sudoers.d %{buildroot}%{_sysconfdir}/sudoers.d/copr


install -d %{buildroot}%{_sysconfdir}/logstash.d
cp -a conf/logstash/copr_backend.conf %{buildroot}%{_sysconfdir}/logstash.d/copr_backend.conf
install -d %{buildroot}%{_datadir}/logstash/patterns/
cp -a conf/logstash/lighttpd.pattern %{buildroot}%{_datadir}/logstash/patterns/lighttpd.pattern
cp -a conf/logstash/frontend.hostname %{buildroot}%{_sysconfdir}/copr/


#doc
cp -a documentation/python-doc %{buildroot}%{_pkgdocdir}/
cp -a conf/playbooks %{buildroot}%{_pkgdocdir}/

%check

#PYTHONPATH=backend:run:$PYTHONPATH python -B -m pytest \
#  -s --cov-report term-missing --cov ./backend --cov ./run ./tests/


%pre
getent group copr >/dev/null || groupadd -r copr
getent passwd copr >/dev/null || \
useradd -r -g copr -G lighttpd -s /bin/bash -c "COPR user" copr
/usr/bin/passwd -l copr >/dev/null

%post
%systemd_post copr-backend.service
%systemd_post logstash.service

%preun
%systemd_preun copr-backend.service

%postun
%systemd_postun_with_restart copr-backend.service

%files
%license LICENSE

%{_datadir}/copr/*
%dir %{_sharedstatedir}/copr
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/jobs/
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/public_html/
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/public_html/results
%dir %attr(0755, copr, copr) %{_var}/log/copr
%dir %attr(0755, copr, copr) %{_var}/log/copr/workers
%dir %attr(0755, copr, copr) %{_var}/run/copr-backend

%ghost %{_var}/log/copr/*.log
%ghost %{_var}/log/copr/workers/worker-*.log
%ghost %{_var}/run/copr-backend/copr-be.pid

%config(noreplace) %{_sysconfdir}/logrotate.d/copr-backend
%dir %{_pkgdocdir}
%doc %{_pkgdocdir}/lighttpd
%doc %{_pkgdocdir}/playbooks
%dir %{_sysconfdir}/copr
%config(noreplace) %attr(0640, root, copr) %{_sysconfdir}/copr/copr-be.conf
%config(noreplace) %attr(0640, root, copr) %{_sysconfdir}/copr/frontend.hostname
%{_unitdir}/copr-backend.service
%{_tmpfilesdir}/copr-backend.conf
%{_bindir}/*

%config(noreplace) %{_sysconfdir}/cron.daily/copr-backend
%config(noreplace) %{_sysconfdir}/logstash.d/copr_backend.conf
%{_datadir}/logstash/patterns/lighttpd.pattern


%config(noreplace) %attr(0600, root, root)  %{_sysconfdir}/sudoers.d/copr

%files doc
%license LICENSE
%doc %{_pkgdocdir}/python-doc
%exclude %{_pkgdocdir}/lighttpd
%exclude %{_pkgdocdir}/playbooks

%changelog
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
- [backend] [.spec] fix %files section

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
- [frontend] provide info about last successfull build
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
- [cli] UX changes - explicitely state that pkgs is URL
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
- [cron] manualy clean /var/tmp after createrepo

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


