Name:           fedpkg-copr
Version:        0.3
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
Requires:       fedpkg

%description
Script and configuration built on top of fedpkg to work
with Copr dist-git and repos named user/project/package.


%prep
%setup -q


%build


%install
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_sysconfdir}/rpkg
cp -a fedpkg-copr         %{buildroot}%{_bindir}/
cp -a fedpkg-copr.conf    %{buildroot}%{_sysconfdir}/rpkg/


%files
%license LICENSE
%doc README
%config(noreplace)  %{_sysconfdir}/rpkg/fedpkg-copr.conf
%{_bindir}/fedpkg-copr



%changelog
* Thu Apr 21 2016 Miroslav Suchý <msuchy@redhat.com> 0.3-1
- rebuild from new location

* Thu Jun 11 2015 Adam Samalik <asamalik@redhat.com> 0
- initial pacakge

