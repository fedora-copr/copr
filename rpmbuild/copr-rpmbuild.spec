Name: copr-rpmbuild
Summary: Run COPR build tasks
Version: 0.15
Release: 1%{?dist}
URL: https://pagure.io/copr/copr

# Source is created by:
# git clone https://pagure.io/copr/copr.git
# cd copr/rpmbuild
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

License: GPLv2+
BuildArch: noarch
BuildRequires: python3-devel
BuildRequires: rpm-python3
BuildRequires: asciidoc
Requires: createrepo_c
Requires: dnf-plugins-core
Requires: rpm-python3
Requires: python3
Requires: python3-jinja2
Requires: python3-munch
Requires: python3-configparser
Requires: python3-simplejson

Requires: mock
Requires: git
Requires: git-svn
Requires: expect
Requires: rubygem-gem2rpm
Requires: pyp2rpm
Requires: rpkg
Requires: tito

%description
Provides command capable of running COPR build-tasks.
Example: copr-rpmbuild 12345-epel-7-x86_64 will locally
build build-id 12345 for chroot epel-7-x86_64.

%prep
%setup -q

%build
%py3_build
a2x -d manpage -f manpage man/copr-rpmbuild.1.asciidoc

%install
install -d %{buildroot}%{_sysconfdir}/copr-rpmbuild
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild/results

install -d %{buildroot}%{_bindir}
install -m 755 main.py %{buildroot}%{_bindir}/copr-rpmbuild
install -m 644 main.ini %{buildroot}%{_sysconfdir}/copr-rpmbuild/main.ini
install -m 644 mock.cfg.j2 %{buildroot}%{_sysconfdir}/copr-rpmbuild/mock.cfg.j2
install -m 644 rpkg.conf.j2 %{buildroot}%{_sysconfdir}/copr-rpmbuild/rpkg.conf.j2
install -m 644 make_srpm_mock.cfg %{buildroot}%{_sysconfdir}/copr-rpmbuild/make_srpm_mock.cfg

install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/copr-rpmbuild.1 %{buildroot}/%{_mandir}/man1/

%py3_install

%files
%license LICENSE

%{python3_sitelib}/*

%{_bindir}/copr-rpmbuild
%{_mandir}/man1/copr-rpmbuild.1*

%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild
%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild/results

%dir %{_sysconfdir}/copr-rpmbuild
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/main.ini
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/mock.cfg.j2
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/rpkg.conf.j2
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/make_srpm_mock.cfg

%changelog
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
