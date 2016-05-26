Summary: COPR system components mocks
Name: copr-mocks
Version: 1.3
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
* Thu May 26 2016 clime <clime@redhat.com> 1.3-1
- task files are now directly under batch (data) dir, no in/out subdirs
- action result storing fixed + code improvements
- make dump files with .json extension for syntax highlightning to kick in
- pretty-print dist-git/backend responses
* Fri Apr 22 2016 Miroslav Suchý <msuchy@redhat.com> 1.2-1
- support for feeding actions to backend
- added debug output
- file names update + do not dump empty files
- possiblity to omit import-tasks.json (or waiting-
  task.json) from datadir
- added possibility to specify static dir on command line
- only finished (failed/succeeded) builds are dumped in
  the end
- simplify output
- create outputdir if does not exists + sample test data
  update
- small fix in error handlers
- fixes & debug infos & better error/input/output handling
- interfaces for backend - initial impl

* Fri Mar 04 2016 clime <clime@redhat.com> 1.1-1
- new package built with tito

* Thu Feb 25 2016 clime <clime@redhat.com> 1.0-1
- Initial package version
