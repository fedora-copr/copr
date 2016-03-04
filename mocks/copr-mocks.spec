Summary: COPR system components mocks
Name: copr-mocks
Version: 1.1
Release: 1%{?dist}

# Source is created by:
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/mocks/frontend
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

License: GPLv2+
BuildArch: noarch
BuildRequires: python3-devel
BuildRequires: systemd-units
Requires: python3
Requires: python3-flask
Requires: python3-flask-script

%description
This package provides mocks for individual copr system components
to enable regression testing of the real components independently.

%prep
%setup -q

%build

%install
install -d %{buildroot}%{_datadir}/copr/mocks/frontend
install -d %{buildroot}%{_datadir}/copr/mocks/backend
install -d %{buildroot}%{_unitdir}

cp -a frontend/* %{buildroot}%{_datadir}/copr/mocks/frontend/
cp -a backend/* %{buildroot}%{_datadir}/copr/mocks/backend/
cp -a copr-mocks-frontend.service %{buildroot}%{_unitdir}/

%pre
getent group copr-mocks >/dev/null || groupadd -r copr-mocks
getent passwd copr-mocks >/dev/null || \
useradd -r -g copr-mocks -G copr-mocks -d %{_datadir}/copr/mocks -s /bin/bash -c "COPR mocks user" copr-mocks
/usr/bin/passwd -l copr-mocks >/dev/null

%files
%license LICENSE

%{_datadir}/copr/mocks/frontend
%{_datadir}/copr/mocks/backend
%{_unitdir}/copr-mocks-frontend.service

%changelog
* Fri Mar 04 2016 clime <clime@redhat.com> 1.1-1
- new package built with tito

* Thu Feb 25 2016 clime <clime@redhat.com> 1.0-1
- Initial package version
