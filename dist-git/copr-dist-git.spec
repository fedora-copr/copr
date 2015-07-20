Name:       copr-dist-git
Version:    0.1
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

BuildRequires:  systemd

Requires:   systemd
Requires:   dist-git
Requires:   python-bunch
Requires:   python-requests
Requires:   pyrpkg

%description
COPR is lightweight build system. It allows you to create new project in WebUI
and submit new builds and COPR will create yum repository from latest builds.

This package contains Copr services for Dist Git server


%prep
%setup -q


%build


%install

install -d %{buildroot}%{_datadir}/copr/dist-git
install -d %{buildroot}%{_sysconfdir}/copr
mkdir -p   %{buildroot}%{_unitdir}

cp -a dist-git/* %{buildroot}%{_datadir}/copr/dist-git
cp -a conf/copr-dist-git.conf.example %{buildroot}%{_sysconfdir}/copr/copr-dist-git.conf
cp -a copr-dist-git.service %{buildroot}%{_unitdir}/


%check


%files
%license LICENSE

%{_datadir}/copr/*
%dir %{_sysconfdir}/copr
%config(noreplace) %attr(0640, root, copr) %{_sysconfdir}/copr/copr-dist-git.conf

%{_unitdir}/copr-dist-git.service


%changelog
* Thu Jun 25 2015 Adam Samalik <asamalik@redhat.com> 0.1
- basic package
