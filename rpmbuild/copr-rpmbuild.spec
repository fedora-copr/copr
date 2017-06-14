Summary: Run COPR build tasks
Name: copr-rpmbuild
Version: 0.3
Release: 1%{?dist}

# Source is created by:
# git clone https://pagure.io/copr/copr.git
# cd copr/rpmbuild
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

License: GPLv2+
BuildArch: noarch

BuildRequires: asciidoc

Requires: perl
Requires: perl-Getopt-Long-Descriptive
Requires: perl-Config-IniFiles
Requires: perl-Text-Template-Simple
Requires: perl-JSON-Tiny
Requires: perl-Data-Types
Requires: perl-HTTP-Tiny
Requires: perl-IPC-Run
Requires: perl-IPC-System-Simple
Requires: perl-Time-Out
Requires: perl-File-Tee
Requires: perl-Proc-Fork
Requires: mock
Requires: git
Requires: expect
Requires: curl

%description
Provides command capable of running COPR build-task definitions.

%prep
%setup -q

%build
a2x -d manpage -f manpage man/copr-rpmbuild.1.asciidoc

%install
install -d %{buildroot}%{_sysconfdir}/copr-rpmbuild
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild/results

install -d %{buildroot}%{_bindir}
install -m 755 main.pl %{buildroot}%{_bindir}/copr-rpmbuild
install -m 644 main.ini %{buildroot}%{_sysconfdir}/copr-rpmbuild/main.ini
install -m 644 mockcfg.tmpl %{buildroot}%{_sysconfdir}/copr-rpmbuild/mockcfg.tmpl

install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/copr-rpmbuild.1 %{buildroot}/%{_mandir}/man1/

%files
%license LICENSE

%{_bindir}/copr-rpmbuild
%{_mandir}/man1/copr-rpmbuild.1*

%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild
%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild/results

%config(noreplace) %{_sysconfdir}/copr-rpmbuild/main.ini
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/mockcfg.tmpl

#%{perl_vendorlib}/*

%changelog
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
