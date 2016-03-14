Summary: Remove old packages from rpm-md repository
Name: prunerepo
Version: 1.6
Release: 1%{?dist}

# Source is created by:
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/prunerepo
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

License: GPLv2+
BuildArch: noarch
BuildRequires: python3-devel
BuildRequires: asciidoc
Requires: createrepo_c
Requires: dnf-plugins-core
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

%build
%py3_build
a2x -d manpage -f manpage man/prunerepo.1.asciidoc

%install
%py3_install

install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/prunerepo.1 %{buildroot}/%{_mandir}/man1/

%files
%license LICENSE

%{python3_sitelib}/*
%{_bindir}/prunerepo
%{_mandir}/man1/prunerepo.1*

%changelog
* Mon Mar 14 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.6-1
- removed obsolete dependency on rpm-python
- doc update

* Fri Feb 26 2016 clime <clime@redhat.com> 1.5-1
- srpm deletion logic changed

* Mon Feb 22 2016 clime <clime@redhat.com> 1.4-1
- deletion of srpms when the same rpm is present in muliple dirs and --days is used fixed

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
