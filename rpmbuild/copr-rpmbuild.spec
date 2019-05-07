%if 0%{?fedora} || 0%{?rhel} > 7
%global __python        %__python3
%global python          python3
%global python_pfx      python3
%global rpm_python      python3-rpm
%else
%global __python        %__python2
%global python          python2
%global python_pfx      python
%global rpm_python      rpm-python
%endif

%define latest_requires() \
Requires: %1 \
%{expand: %%global latest_requires_packages %1 %%{?latest_requires_packages}}

Name:    {{{ git_dir_name }}}
Version: {{{ git_dir_version }}}
Summary: Run COPR build tasks
Release: 1%{?dist}
URL: https://pagure.io/copr/copr
License: GPLv2+
BuildArch: noarch

# Source is created by:
# git clone https://pagure.io/copr/copr.git
# git checkout {{{ cached_git_name_version }}}
# cd copr/rpmbuild
# rpkg spec --sources
Source0: {{{ git_dir_archive }}}

BuildRequires: %{python}-devel
BuildRequires: %{python}-distro
%if 0%{?rhel} == 0 || 0%{?rhel} != 6
BuildRequires: %{python}-httmock
%endif
BuildRequires: %{rpm_python}
BuildRequires: asciidoc
BuildRequires: %{python}-setuptools
BuildRequires: %{python}-pytest
BuildRequires: %{python_pfx}-munch
BuildRequires: %{python}-requests
BuildRequires: %{python_pfx}-jinja2

BuildRequires: python-rpm-macros

%if %{?python} == "python2"
BuildRequires: python2-configparser
BuildRequires: python2-mock
Requires: python2-configparser
%endif

Requires: %python
Requires: %{python_pfx}-jinja2
Requires: %{python_pfx}-munch
Requires: %{python}-requests
Requires: %{python_pfx}-simplejson

Requires: mock
Requires: git
Requires: git-svn
# for the /bin/unbuffer binary
Requires: expect

%if 0%{?fedora} || 0%{?rhel} > 7
Recommends: rpkg
Recommends: python-srpm-macros
Suggests: tito
Suggests: rubygem-gem2rpm
Suggests: pyp2rpm
%endif

%description
Provides command capable of running COPR build-tasks.
Example: copr-rpmbuild 12345-epel-7-x86_64 will locally
build build-id 12345 for chroot epel-7-x86_64.


%package -n copr-builder
Summary: copr-rpmbuild with all weak dependencies
Requires: %{name} = %{version}-%{release}

# selinux toolset to allow running ansible against the builder
Requires: libselinux-python
Requires: libsemanage-python
# for mock to allow 'nosync = True'
Requires: nosync
Requires: openssh-clients
Requires: pyp2rpm
# We need %%pypi_source defined, which is in 3-29+
Requires: python-srpm-macros >= 3-29
Requires: rpkg
Requires: rsync
Requires: rubygem-gem2rpm
Requires: scl-utils-build
Requires: tito
# yum* to allow mock to build against el* chroots
Requires: yum
Requires: yum-utils


# We want those to be always up-2-date
%latest_requires ca-certificates
%latest_requires distribution-gpg-keys
%latest_requires dnf
%latest_requires dnf-plugins-core
%latest_requires mock
%latest_requires mock-core-configs
%latest_requires rpm


%description -n copr-builder
Provides command capable of running COPR build-tasks.
Example: copr-rpmbuild 12345-epel-7-x86_64 will locally
build build-id 12345 for chroot epel-7-x86_64.

This package contains all optional modules for building SRPM.


%prep
%setup -q


%check
PYTHON=%{python} ./run_tests.sh


%build
name="%{name}" version="%{version}" summary="%{summary}" %py_build
a2x -d manpage -f manpage man/copr-rpmbuild.1.asciidoc

cat > copr-update-builder <<EOF
#! /bin/sh

# Update the Copr builder machine, can be called anytime Copr build system
# decides to do so (please keep the output idempotent).

# install the latest versions of those packages
dnf update -y %latest_requires_packages
EOF


%install
install -d %{buildroot}%{_sysconfdir}/copr-rpmbuild
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild/results

install -d %{buildroot}%{_bindir}
install -m 755 main.py %{buildroot}%{_bindir}/copr-rpmbuild
sed -i '1 s|#.*|#! /usr/bin/%python|' %{buildroot}%{_bindir}/copr-rpmbuild
install -m 644 main.ini %{buildroot}%{_sysconfdir}/copr-rpmbuild/main.ini
install -m 644 mock.cfg.j2 %{buildroot}%{_sysconfdir}/copr-rpmbuild/mock.cfg.j2
install -m 644 rpkg.conf.j2 %{buildroot}%{_sysconfdir}/copr-rpmbuild/rpkg.conf.j2
install -m 644 make_srpm_mock.cfg %{buildroot}%{_sysconfdir}/copr-rpmbuild/make_srpm_mock.cfg

install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/copr-rpmbuild.1 %{buildroot}/%{_mandir}/man1/
install -p -m 755 bin/copr-sources-custom %buildroot%_bindir

name="%{name}" version="%{version}" summary="%{summary}" %py_install

install -p -m 755 copr-update-builder %buildroot%_bindir


%files
%{!?_licensedir:%global license %doc}
%license LICENSE

%{expand:%%%{python}_sitelib}/*

%{_bindir}/copr-rpmbuild
%{_bindir}/copr-sources-custom
%{_mandir}/man1/copr-rpmbuild.1*

%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild
%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild/results

%dir %{_sysconfdir}/copr-rpmbuild
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/main.ini
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/mock.cfg.j2
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/rpkg.conf.j2
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/make_srpm_mock.cfg

%files -n copr-builder
%license LICENSE
%_bindir/copr-update-builder


%changelog
{{{ git_dir_changelog since_tag=copr-rpmbuild-0.18-1 }}}

* Fri Feb 23 2018 clime <clime@redhat.com> 0.17-1
- remove unused requires and rename rpm-python3 to python3-rpm
- switch copr-sources-custom to python3 shebang
- keep tmpfs data mounted acros mock invocations for custom method

* Mon Feb 19 2018 clime <clime@redhat.com> 0.16-1
- new custom source method

* Sun Feb 18 2018 clime <clime@redhat.com> 0.15-1
- add support for fetch_sources_only in task defition
- allow building rpms from srpms fetched by providers, 
- extend cmdline with scm submode
- optionally set a priority for a repo
- add test for create_rpmmacros + refactoring
- allow only https and ftps protocols for source fetch

* Thu Jan 11 2018 clime <clime@redhat.com> 0.14-1
- copy out dnf and yum logs when using mock
- introspection and --version argument

* Mon Dec 11 2017 clime <clime@redhat.com> 0.13-1
- update man pages
- update help
- exclude 'tests' in package auto-discovery
- don't install additional stuff into bootstrap of custom buildroot
- Bug 1514221 - Copr fails to clone the repository. Build fails.

* Thu Nov 09 2017 clime <clime@redhat.com> 0.12-1
- fix get_mock_uniqueext call
- fortify make_srpm
- add '--private-users=pick' to make_srpm container to improve
  security
- compatibility with rpkg-client-0.11
- add config for src.stg.fedoraproject.org into default rpmbuild
  config
- fix download url for new rpkg-client version

* Wed Oct 18 2017 clime <clime@redhat.com> 0.11-1
- provide option to root spec file path in SCM with '/'
- fix exception raising in scm provider
- make command debug info nicer
- print task structure in the beginning even without -v
- add listdir after srpm production
- some Git backends do not support --depth
- remove unused run method
- checkout master by default
- with limited depth, we need to clone with --no-single-branch
- remove original perl script and mock config for it
- remove no longer needed options from rpkg.conf.j2
- SCM source types unification
- apply continuing line filtering from f4561c149893
- increase clone depth to address pag#129 SCM source type error

* Tue Sep 26 2017 clime <clime@redhat.com> 0.10-1
- use https for copr frontend in default config
- Make error message when the build task does not exist more user-
  friendly
- add --build-id switch instead of positional argument
- do not fail when lockfile does not exist
- change arguments to build_id and chroot
- remove lockfile import
- remove unused requires:
- remove unused variables in try-excepts
- #138 FileExistsError: [Errno 17] File exists: '/var/lib/copr-
  rpmbuild/lockfile.lock'

* Fri Sep 15 2017 clime <clime@redhat.com> 0.9-1
- copy spec file to the result dir to have a quick overview on the
  package

* Thu Sep 14 2017 clime <clime@redhat.com> 0.8-1
- provide more verbose exception logging
- take timeout into account
- fix downstream/upstream condition
- set also use_host_resolv to False if enable_net is False
- when building rpms, prebuild srpm in mock chroot

* Thu Sep 07 2017 clime <clime@redhat.com> 0.7-1
- rewrite to python
- build-srpm from upstream ability added
* Fri Jul 07 2017 clime <clime@redhat.com> 0.6-1
- support for source downloading

* Tue Jun 27 2017 clime <clime@redhat.com> 0.5-1
- use Perl Virtual naming for Requires

* Fri Jun 23 2017 clime <clime@redhat.com> 0.4-1
- use dnf.conf for custom-1 chroots
- also copy .spec to the build result directory
- raise curl timeout for downloading sources to be built
- changes according to review bz#1460630
- rpmbuild_networking option is now used to enable/disable net

* Wed Jun 14 2017 clime <clime@redhat.com> 0.3-1
- support for mock's bootstrap container
- check each line of sources file separately
- allow multiple sources and use current dir for mock as source dir
- also check for value of repos first before array referencing in mockcfg.tmpl
- handle null for buildroot_pkgs in mockcfg.tmpl

* Fri Jun 09 2017 clime <clime@redhat.com> 0.2-1
- new package built with tito

* Fri Jun 02 2017 clime <clime@redhat.com> 0.1-1
- Initial version
