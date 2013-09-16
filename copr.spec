%if 0%{?rhel} < 7 && 0%{?rhel} > 0
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%endif

Name:		copr
Version:	1.1
Release:	1%{?dist}
Summary:	Cool Other Package Repo

Group:		Applications/Productivity
License:	GPLv2+
URL:		https://fedorahosted.org/copr/
Source0:	https://git.fedorahosted.org/cgit/copr.git/snapshot/%{name}-%{version}-1.tar.gz

BuildArch:  noarch
BuildRequires: asciidoc
BuildRequires: libxslt
BuildRequires: util-linux
BuildRequires: python-setuptools
BuildRequires: python-requests
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
BuildRequires: python-argparse
%endif
#for doc package
BuildRequires: epydoc
BuildRequires: graphviz
BuildRequires: make

%description
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

%package backend
Summary:	Backend for COPR
Requires:   ansible >= 1.2
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
COPR is lightweight buildsystem. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package contains backend.

%package frontend
Summary:    Frontend for COPR
Requires:   httpd
Requires:	mod_wsgi
Requires:	python-alembic
Requires:   python-flask
Requires:   python-flask-openid
Requires:   python-flask-wtf
Requires:   python-flask-sqlalchemy
Requires:   python-flask-script
Requires:   python-flask-whooshee
#Requires:	python-virtualenv
Requires:   python-blinker
Requires:	python-psycopg2
Requires:   python-pylibravatar
Requires:	python-whoosh >= 2.5.3
# for tests:
Requires:	pytest
Requires:   python-flexmock
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
BuildRequires: python-argparse
%endif

%description frontend
COPR is lightweight buildsystem. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package contains frontend.

%package cli
Summary:	Command line interface for COPR
Requires:	python-requests
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
Requires:   python-argparse
%endif

%description cli
COPR is lightweight buildsystem. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package contains command line interface.

%package doc
Summary:    Code documentation for COPR

%description doc
COPR is lightweight buildsystem. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package include documentation for COPR code. Mostly useful for developers
only.

%prep
%setup -q


%build
mv copr_cli/README.rst ./

# convert manages
a2x -d manpage -f manpage man/copr-cli.1.asciidoc

# build documentation
pushd documentation
make python
popd

%install

#backend
install -d %{buildroot}%{_sharedstatedir}/copr
install -d %{buildroot}%{_sharedstatedir}/copr/public_html/results
install -d %{buildroot}%{_var}/log/copr
install -d %{buildroot}%{_var}/log/copr/workers/
install -d %{buildroot}%{_pkgdocdir}/lighttpd/
install -d %{buildroot}%{_datadir}/copr/backend
install -d %{buildroot}%{_sysconfdir}/copr

cp -a backend/* %{buildroot}%{_datadir}/copr/backend
cp -a copr-be.py %{buildroot}%{_datadir}/copr/
cp -a copr-be.conf.example %{buildroot}%{_sysconfdir}/copr/copr-be.conf

cp -a backend-dist/lighttpd/* %{buildroot}%{_pkgdocdir}/lighttpd/
# for ghost files
touch %{buildroot}%{_var}/log/copr/copr.log
for i in `seq 7`; do
	touch %{buildroot}%{_var}/log/copr/workers/worker-$i.log
done

#frontend
install -d %{buildroot}%{_sysconfdir}
install -d %{buildroot}%{_datadir}/copr/coprs_frontend
install -d %{buildroot}%{_sharedstatedir}/copr/data/openid_store
install -d %{buildroot}%{_sharedstatedir}/copr/data/openid_store/associations
install -d %{buildroot}%{_sharedstatedir}/copr/data/openid_store/nonces
install -d %{buildroot}%{_sharedstatedir}/copr/data/openid_store/temp
install -d %{buildroot}%{_sharedstatedir}/copr/data/whooshee
install -d %{buildroot}%{_sharedstatedir}/copr/data/whooshee/copr_user_whoosheer

cp -a coprs_frontend/* %{buildroot}%{_datadir}/copr/coprs_frontend
mv %{buildroot}%{_datadir}/copr/coprs_frontend/coprs.conf.example ./
mv %{buildroot}%{_datadir}/copr/coprs_frontend/config/* %{buildroot}%{_sysconfdir}/copr
rm %{buildroot}%{_datadir}/copr/coprs_frontend/CONTRIBUTION_GUIDELINES
touch %{buildroot}%{_sharedstatedir}/copr/data/copr.db

#copr-cli
%{__python} coprcli-setup.py install --root %{buildroot}
install -d %{buildroot}%{_mandir}/man1
install -m 644 man/copr-cli.1 %{buildroot}/%{_mandir}/man1/

#doc
cp -a documentation/python-doc %{buildroot}%{_pkgdocdir}/
cp -a playbooks %{buildroot}%{_pkgdocdir}/

%pre backend
getent group copr >/dev/null || groupadd -r copr
getent passwd copr >/dev/null || \
useradd -r -g copr -G lighttpd -d %{_datadir}/copr -s /bin/bash -c "COPR user" copr
/usr/bin/passwd -l copr >/dev/null

%pre frontend
getent group copr-fe >/dev/null || groupadd -r copr-fe
getent passwd copr-fe >/dev/null || \
useradd -r -g copr-fe -G copr-fe -d %{_datadir}/copr/coprs_frontend -s /bin/bash -c "COPR frontend user" copr-fe
/usr/bin/passwd -l copr-fe >/dev/null

%post frontend
service httpd condrestart

%files backend
%doc LICENSE README
%dir %{_datadir}/copr
%dir %{_sharedstatedir}/copr
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/public_html/
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/public_html/results
%dir %attr(0755, copr, copr) %{_var}/log/copr
%dir %attr(0755, copr, copr) %{_var}/log/copr/workers
%ghost %{_var}/log/copr/copr.log
%ghost %{_var}/log/copr/workers/worker-*.log
%doc %{_pkgdocdir}/lighttpd
%doc %{_pkgdocdir}/playbooks
%config(noreplace) %{_sysconfdir}/copr/copr-be.conf

%{_datadir}/copr/backend
%{_datadir}/copr/copr-be.py*

%files frontend
%doc LICENSE coprs.conf.example copr-setup.txt
%dir %{_datadir}/copr
%dir %{_sharedstatedir}/copr
%{_datadir}/copr/coprs_frontend

%defattr(-, copr-fe, copr-fe, -)
%dir %{_sharedstatedir}/copr/data
%dir %{_sharedstatedir}/copr/data/openid_store
%dir %{_sharedstatedir}/copr/data/whooshee
%dir %{_sharedstatedir}/copr/data/whooshee/copr_user_whoosheer

%ghost %{_sharedstatedir}/copr/data/copr.db

%defattr(600, copr-fe, copr-fe, 700)
%dir %{_sysconfdir}/copr
%config(noreplace)  %{_sysconfdir}/copr/copr.conf
%config(noreplace)  %{_sysconfdir}/copr/copr_devel.conf
%config(noreplace)  %{_sysconfdir}/copr/copr_unit_test.conf


%files cli
%doc LICENSE README.rst
%{_bindir}/copr-cli
%{python_sitelib}/*
%doc %{_mandir}/man1/copr-cli.1*

%files doc
%doc %{_pkgdocdir}/python-doc

%changelog
* Mon Jun 17 2013 Miroslav Suchý <msuchy@redhat.com> 1.1-1
- new package built with tito


