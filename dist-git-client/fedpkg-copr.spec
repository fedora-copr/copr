Name:           fedpkg-copr
Version:        0.10
Release:        1%{?dist}
Summary:        Fedpkg modified to work with copr dist git

License:        GPLv2+
URL:            https://fedorahosted.org/copr/
# Source is created by
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/dist-git-client
# tito build --tgz
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  asciidoc
Requires:       fedpkg

%description
Script and configuration built on top of fedpkg to work
with Copr dist-git and repos named user/project/package.


%prep
%setup -q


%build
a2x -d manpage -f manpage man/fedpkg-copr.1.asciidoc


%install
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_sysconfdir}/rpkg
cp -a fedpkg-copr         %{buildroot}%{_bindir}/
cp -a fedpkg-copr.conf    %{buildroot}%{_sysconfdir}/rpkg/

install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/fedpkg-copr.1 %{buildroot}/%{_mandir}/man1/


%files
%license LICENSE
%doc README
%config(noreplace)  %{_sysconfdir}/rpkg/fedpkg-copr.conf
%{_bindir}/fedpkg-copr
%{_mandir}/man1/fedpkg-copr.1*



%changelog
* Thu Dec 01 2016 clime <clime@redhat.com> 0.10-1
- Automatic commit of package [fedpkg-copr] release [0.9-1].

* Thu Dec 01 2016 clime <clime@redhat.com> 0.9-1
- Bug 1393460 - Copr chokes on %%mageia conditional in spec files for rebuilding SRPM
- Add Mageia branches to the regex

* Thu Sep 29 2016 clime <clime@redhat.com> 0.8-1
- missing BuildRequires: asciidoc added

* Thu Sep 29 2016 clime <clime@redhat.com> 0.7-1
- support for mageia-specific macros added

* Wed Sep 21 2016 clime <clime@redhat.com> 0.6-1
- basic man page

* Mon Sep 19 2016 clime <clime@redhat.com> 0.5-1
- support for mageia chroots
- do not override module_name, override lookasidecache method instead

* Wed May 18 2016 Miroslav Suchý <msuchy@redhat.com> 0.4-1
- sort imports
- fedpkg-copr: workaround till this get into propper fedora
- clean it up for inclusion in Fedora
- remove left over from import

* Thu Apr 21 2016 Miroslav Suchý <msuchy@redhat.com> 0.3-1
- rebuild from new location

* Thu Jun 11 2015 Adam Samalik <asamalik@redhat.com> 0
- initial pacakge

