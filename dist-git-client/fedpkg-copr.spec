Name:           fedpkg-copr
Version:        0.3
Release:        1%{?dist}
Summary:        Fedpkg modified to work with copr dist git

Group:          Applications/Productivity
License:        GPLv2+
URL:            http://nothing.example.com
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       fedpkg
Requires:       pyrpkg

%description
This is a quick and dirty solution. It's a modified version of
fedpkg that works with repos named user/project/package


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

