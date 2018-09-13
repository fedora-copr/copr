Name:    {{{ git_name name=prunerepo }}}
Version: {{{ git_version lead=1 }}}
Summary: Remove old packages from rpm-md repository
Release: 1%{?dist}

# Source is created by:
# git clone https://pagure.io/copr/copr.git
# git checkout {{{ cached_git_name_version }}}
# cd copr/prunerepo
# rpkg spec --sources
Source0: {{{ git_dir_archive }}}

License: GPLv2+
BuildArch: noarch
BuildRequires: bash
BuildRequires: python3-devel
BuildRequires: rpm-python3
BuildRequires: createrepo_c
BuildRequires: asciidoc
BuildRequires: findutils
BuildRequires: dnf
BuildRequires: dnf-plugins-core
BuildRequires: coreutils
Requires: createrepo_c
Requires: dnf-plugins-core
Requires: rpm-python3
Requires: python3

%description
RPM packages that have newer version available in that same
repository are deleted from filesystem and the rpm-md metadata are
recreated afterwards. If there is a source rpm for a deleted rpm
(and they both share the same directory path), then the source rpm
will be deleted as well.

Support for specific repository structure (e.g. COPR) is also available
making it possible to additionally remove build logs and whole build
directories associated with a package.

After deletion of obsoleted packages, the command
"createrepo_c --database --update" is called
to recreate the repository metadata.

%prep
%setup -q

%check
tests/run.sh

%build
name="%{name}" version="%{version}" summary="%{summary}" %py3_build
a2x -d manpage -f manpage man/prunerepo.1.asciidoc

%install
name="%{name}" version="%{version}" summary="%{summary}" %py3_install

install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/prunerepo.1 %{buildroot}/%{_mandir}/man1/

%files
%license LICENSE

%{python3_sitelib}/*
%{_bindir}/prunerepo
%{_mandir}/man1/prunerepo.1*

%changelog
{{{ git_changelog since_tag=prunerepo-1.12-1 }}}

* Wed Jan 24 2018 clime <clime@redhat.com> 1.11-1
- do not recreate repo if there was no change in data unless
  --alwayscreaterepo is specified
- add builddep on createrepo_c as well
- add Builddep on dnf that is no longer present in Builddep chain
- optimize createrepo_c
- run tests during build
- use just --repo instead of --disablerepo= --enablerepo=
- Spelling fixes

* Wed Apr 19 2017 clime <clime@redhat.com> 1.10-1
- replace fedorahosted links

* Thu May 26 2016 clime <clime@redhat.com> 1.9-1
- --days now also influences --cleancopr

* Mon May 23 2016 Miroslav Suchý <msuchy@redhat.com> 1.8-1
- just skip the missing srpm
- first remove srpm and then the rpm

* Mon Mar 14 2016 clime <clime@redhat.com> 1.7-1
- rpm-python3 dependency added back

* Mon Mar 14 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.6-1
- removed obsolete dependency on rpm-python
- doc update

* Fri Feb 26 2016 clime <clime@redhat.com> 1.5-1
- srpm deletion logic changed

* Mon Feb 22 2016 clime <clime@redhat.com> 1.4-1
- deletion of srpms when the same rpm is present in multiple dirs and --days is used fixed

* Fri Jan 29 2016 Miroslav Suchý <msuchy@redhat.com> 1.3-1
- rebuild for release

* Tue Jan 26 2016 clime <clime@redhat.com> 1.2-1
- bugfix for --cleancopr when a log for the respective dir does not
  exist (e.g. copr repos with old dir naming)

* Mon Jan 25 2016 clime <clime@redhat.com> 1.1-1
- test suite finished
- --quiet, --cleancopr and --days options implemented

* Tue Jan 19 2016 clime <clime@redhat.com> 1.0-1
- Initial package version
