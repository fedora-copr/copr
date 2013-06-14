Name:		copr
Version:	1.0
Release:	1%{?dist}
Summary:	Cool Other Package Repo

Group:		Applications/Productivity
License:	GPLv2+
URL:		https://fedorahosted.org/copr/
Source0:	%{name}-%{version}.tar.gz

BuildRequires: asciidoc
BuildRequires: libxslt
BuildRequires: util-linux

%description
COPR is lightway Koji. It allows you to create new project in WebUI, and
submit new builds and COPR will create yum repository from latests builds.

%package backend
Summary:	Backend for COPR
Requires:   ansible >= 0.9
Requires:   lighttpd
Requires:   euca2ools
Requires:   rsync
Requires:   openssh-clients
Requires:   mock
Requires:   yum-utils
Requires:   createrepo
Requires:   python-bunch
Requires:   python-requests

%description backend
COPR is lightway Koji. It allows you to create new project in WebUI, and
submit new builds and COPR will create yum repository from latests builds.

This package contains backend.

%package frontend
Summary:    Frontend for COPR
Requires:   httpd
Requires:	mod_wsgi
Requires:	postgresql-server
Requires:   postgresql-devel
Requires:	gcc
Requires:   python-flask
Requires:   python-flask-openid
Requires:   python-flask-wtf
Requires:   python-flask-sqlalchemy
#Requires:	python-virtualenv
Requires:   python-blinker
Requires:	python-whoosh
# for tests:
Requires:	pytest

%description frontend
COPR is lightway Koji. It allows you to create new project in WebUI, and
submit new builds and COPR will create yum repository from latests builds.

This package contains frontend.

%package cli
Summary:	Command line interface for COPR
Requires:	python-requests
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
Requires:   python-argparse
%endif

%description cli
COPR is lightway Koji. It allows you to create new project in WebUI, and
submit new builds and COPR will create yum repository from latests builds.

This package contains command line interface.

%prep
%setup -q


%build
mv copr_cli/README.rst ./

# convert manages
a2x -d manpage -f manpage man/copr-cli.1.asciidoc

%install
%{__python} coprcli-setup.py install --root %{buildroot}

install -d %{buildroot}%{_mandir}/man1
install -m 644 man/copr-cli.1 %{buildroot}/%{_mandir}/man1/

%pre backend
getent group copr >/dev/null || groupadd -r copr
getent passwd copr >/dev/null || \
useradd -r -g copr -G apache -d %{_var}/lib/copr -s /bin/bash -c "COPR user" copr
/usr/bin/passwd -l copr >/dev/null

%files backend
%doc LICENSE README

%files frontend
%doc LICENSE

%files cli
%doc LICENSE README.rst
%{_bindir}/copr-cli
%{python_sitelib}/*
%doc %{_mandir}/man1/copr-cli.1*

%changelog

