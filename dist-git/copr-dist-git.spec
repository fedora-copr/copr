Name:       copr-dist-git
Version:    0.23
Release:    1%{?dist}
Summary:    Copr services for Dist Git server

Group:      Applications/Productivity
License:    GPLv2+
URL:        https://fedorahosted.org/copr/
# Source is created by
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/dist-git
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

BuildArch:  noarch

BuildRequires: systemd
BuildRequires: dist-git
BuildRequires: python-bunch
BuildRequires: python-requests
BuildRequires: pyrpkg >= 1.47
# check
BuildRequires: python-six
BuildRequires: python-netaddr
BuildRequires: python-dateutil
BuildRequires: pytest
BuildRequires: python-pytest-cov
BuildRequires: python-mock
%if 0%{?el7}
BuildRequires: python-psutil
%else
BuildRequires: python2-psutil
%endif
BuildRequires: pytz

%if 0%{?fedora} > 23
# BuildRequires also because of build-time tests
BuildRequires: python2-jinja2
Requires: python2-jinja2
%else
BuildRequires: python-jinja2
Requires: python-jinja2
%endif

Requires: systemd
Requires: dist-git
Requires: python-bunch
Requires: python-requests
%if 0%{?el7}
Requires: python-psutil
%else
Requires: python2-psutil
%endif
Requires: python-jinja2
Requires: pyrpkg >= 1.47
Requires: mock-scm
%ifarch x86_64 i386 i486 i586 i686
Requires: docker
%endif
Requires: httpd
%{?fedora:Requires(post): policycoreutils-python-utils}
%{?rhel:Requires(post): policycoreutils-python}

%description
COPR is lightweight build system. It allows you to create new project in WebUI
and submit new builds and COPR will create yum repository from latest builds.

This package contains Copr services for Dist Git server.


%prep
%setup -q


%build


%install

install -d %{buildroot}%{_datadir}/copr/dist_git
install -d %{buildroot}%{_sysconfdir}/copr
install -d %{buildroot}%{_sysconfdir}/logrotate.d/
install -d %{buildroot}%{_sysconfdir}/httpd/conf.d/
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}%{_var}/log/copr-dist-git
install -d %{buildroot}%{_sharedstatedir}/copr-dist-git
install -d %{buildroot}%{_bindir}/

cp -a dist_git/* %{buildroot}%{_datadir}/copr/dist_git
cp -a conf/copr-dist-git.conf.example %{buildroot}%{_sysconfdir}/copr/copr-dist-git.conf
cp -a conf/httpd/copr-dist-git.conf %{buildroot}%{_sysconfdir}/httpd/conf.d/copr-dist-git.conf
cp -a copr-dist-git.service %{buildroot}%{_unitdir}/
cp -a run/* %{buildroot}%{_bindir}/

cp -a conf/logrotate %{buildroot}%{_sysconfdir}/logrotate.d/copr-dist-git

# for ghost files
touch %{buildroot}%{_var}/log/copr-dist-git/main.log

%check

%if 0%{?fedora} >= 21
# too old `pytest` in epel repo
PYTHONPATH=.:$PYTHONPATH python -B -m pytest \
  -v --cov-report term-missing --cov ./dist_git ./tests/
%endif

%post
# change context to be readable by cgit
semanage fcontext -a -t httpd_sys_content_t '/var/lib/copr-dist-git(/.*)?'
restorecon -rv /var/lib/copr-dist-git
groupadd docker
usermod -aG docker copr-service
%systemd_post copr-dist-git.service

%preun
%systemd_preun copr-dist-git.service

%postun
%systemd_postun_with_restart copr-dist-git.service

%files
%license LICENSE

%{_bindir}/*
%dir %{_datadir}/copr 
%{_datadir}/copr/*
%dir %{_sysconfdir}/copr
%config(noreplace) %attr(0640, root, copr-service) %{_sysconfdir}/copr/copr-dist-git.conf
%config(noreplace) %attr(0644, root, root) %{_sysconfdir}/httpd/conf.d/copr-dist-git.conf

%dir %attr(0755, copr-service, copr-service) %{_sharedstatedir}/copr-dist-git/

%{_unitdir}/copr-dist-git.service

%dir %{_sysconfdir}/logrotate.d
%config(noreplace) %{_sysconfdir}/logrotate.d/copr-dist-git
%attr(0755, copr-service, copr-service) %{_var}/log/copr-dist-git
%attr(0644, copr-service, copr-service) %{_var}/log/copr-dist-git/main.log
%ghost %{_var}/log/copr-dist-git/*.log

%changelog
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
- don't run tests during %check on epel

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
