%global with_test 1
%global with_server 1
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%global __python2 %{__python}
%global with_server 0
%endif
%global moduletype apps
%global modulename copr

Name:       copr
Version:    1.23
Release:    1%{?dist}
Summary:    Cool Other Package Repo

Group:      Applications/Productivity
License:    GPLv2+
URL:        https://fedorahosted.org/copr/
# Source is created by
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr
# tito build --tgz
# content is same as https://git.fedorahosted.org/cgit/copr.git/snapshot/%{name}-%{version}-1.tar.gz
# but checksum does not match due different metadata
Source0: %{name}-%{version}.tar.gz

BuildArch:  noarch
BuildRequires: asciidoc
BuildRequires: libxslt
BuildRequires: util-linux
BuildRequires: python-setuptools
BuildRequires: python-requests
BuildRequires: python2-devel
%if %{with_server}
BuildRequires: systemd
%endif
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
BuildRequires: python-argparse
%endif
#for doc package
BuildRequires: epydoc
BuildRequires: graphviz
BuildRequires: make
%if %{with_server}
#for selinux
BuildRequires:  checkpolicy, selinux-policy-devel
BuildRequires:  policycoreutils >= %{POLICYCOREUTILSVER}
%endif

%description
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

%if %{with_server}
%package backend
Summary:    Backend for COPR
Requires:   ansible >= 1.2
Requires:   lighttpd
Requires:   euca2ools
Requires:   rsync
Requires:   openssh-clients
Requires:   mock
Requires:   yum-utils
Requires:   createrepo_c
Requires:   python-bunch
Requires:   python-daemon
Requires:   python-lockfile
Requires:   python-requests
Requires:   python-setproctitle
Requires:   logrotate
Requires:   fedmsg
Requires:   gawk
Requires:   crontabs
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd

%description backend
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package contains backend.

%package frontend
Summary:    Frontend for COPR
Requires:   httpd
Requires:   mod_wsgi
Requires:   python-alembic
Requires:   python-flask
Requires:   python-flask-openid
Requires:   python-flask-wtf
Requires:   python-flask-sqlalchemy
Requires:   python-flask-script
Requires:   python-flask-whooshee
#Requires:   python-virtualenv
Requires:   python-blinker
Requires:   python-markdown
Requires:   python-psycopg2
Requires:   python-pylibravatar
Requires:   python-whoosh >= 2.5.3
# for tests:
Requires:   pytest
Requires:   python-flexmock
Requires:   python-decorator
Requires:   yum
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
BuildRequires: python-argparse
%endif
# check
BuildRequires: python-flask
BuildRequires: python-flask-script
BuildRequires: python-flask-sqlalchemy
BuildRequires: python-flask-openid
BuildRequires: python-flask-whooshee
BuildRequires: python-pylibravatar
BuildRequires: python-flask-wtf
BuildRequires: pytest
BuildRequires: yum
BuildRequires: python-flexmock
BuildRequires: python-decorator
BuildRequires: python-markdown

%description frontend
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package contains frontend.
%endif # with_server

%package cli
Summary:    Command line interface for COPR
Requires:   python-requests
Requires:   python-setuptools
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
Requires:   python-argparse
%endif

%description cli
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package contains command line interface.

%if %{with_server}
%package doc
Summary:    Code documentation for COPR

%description doc
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package include documentation for COPR code. Mostly useful for developers
only.

%package selinux
Summary:        SELinux module for COPR
Requires(post): policycoreutils, libselinux-utils
Requires(post): policycoreutils-python
Requires(post): selinux-policy-targeted
Requires(postun): policycoreutils

%description selinux
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package include SELinux targeted module for COPR
%endif

%prep
%setup -q


%build
mv copr_cli/README.rst ./

# convert manages
a2x -d manpage -f manpage man/copr-cli.1.asciidoc
a2x -d manpage -f manpage man/copr-selinux-enable.8.asciidoc
a2x -d manpage -f manpage man/copr-selinux-relabel.8.asciidoc

# build documentation
pushd documentation
make %{?_smp_mflags} python
popd

%if %{with_server}
#selinux
pushd selinux
perl -i -pe 'BEGIN { $VER = join ".", grep /^\d+$/, split /\./, "%{version}.%{release}"; } s!\@\@VERSION\@\@!$VER!g;' %{modulename}.te
for selinuxvariant in targeted; do
    make NAME=${selinuxvariant} -f /usr/share/selinux/devel/Makefile
    bzip2 -9 %{modulename}.pp
    mv %{modulename}.pp.bz2 %{modulename}.pp.bz2.${selinuxvariant}
    make NAME=${selinuxvariant} -f /usr/share/selinux/devel/Makefile clean
done
popd
%endif

%install

%if %{with_server}
#backend
install -d %{buildroot}%{_sharedstatedir}/copr
install -d %{buildroot}%{_sharedstatedir}/copr/jobs
install -d %{buildroot}%{_sharedstatedir}/copr/public_html/results
install -d %{buildroot}%{_var}/log/copr
install -d %{buildroot}%{_var}/log/copr/workers/
install -d %{buildroot}%{_pkgdocdir}/lighttpd/
install -d %{buildroot}%{_datadir}/copr/backend
install -d %{buildroot}%{_sysconfdir}/copr
install -d %{buildroot}%{_sysconfdir}/logrotate.d/
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}/%{_var}/log/copr-backend
install -d %{buildroot}/%{_var}/run/copr-backend/
install -d %{buildroot}/%{_tmpfilesdir}
install -d %{buildroot}/%{_sbindir}
install -d %{buildroot}%{_sysconfdir}/cron.daily

cp -a backend/* %{buildroot}%{_datadir}/copr/backend
cp -a copr-be.py %{buildroot}%{_datadir}/copr/
cp -a copr-be.conf.example %{buildroot}%{_sysconfdir}/copr/copr-be.conf
install -p -m 755 copr-prune-repo %{buildroot}%{_sbindir}/copr-prune-repo
install -p -m 750 crontab/copr-backend %{buildroot}%{_sysconfdir}/cron.daily/copr-backend

cp -a backend-dist/lighttpd/* %{buildroot}%{_pkgdocdir}/lighttpd/
cp -a logrotate/* %{buildroot}%{_sysconfdir}/logrotate.d/
cp -a tmpfiles.d/* %{buildroot}/%{_tmpfilesdir}

# for ghost files
touch %{buildroot}%{_var}/log/copr/copr.log
for i in `seq 7`; do
	touch %{buildroot}%{_var}/log/copr/workers/worker-$i.log
done
touch %{buildroot}%{_var}/run/copr-backend/copr-be.pid

install -m 0644 copr-backend.service %{buildroot}/%{_unitdir}/

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
%endif # with_server

#copr-cli
%{__python2} coprcli-setup.py install --root %{buildroot}
install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/copr-cli.1 %{buildroot}/%{_mandir}/man1/

%if %{with_server}
#doc
cp -a documentation/python-doc %{buildroot}%{_pkgdocdir}/
cp -a playbooks %{buildroot}%{_pkgdocdir}/

#selinux
for selinuxvariant in targeted; do
    install -d %{buildroot}%{_datadir}/selinux/${selinuxvariant}
    install -p -m 644 selinux/%{modulename}.pp.bz2.${selinuxvariant} \
           %{buildroot}%{_datadir}/selinux/${selinuxvariant}/%{modulename}.pp.bz2
done
# Install SELinux interfaces
install -d %{buildroot}%{_datadir}/selinux/devel/include/%{moduletype}
install -p -m 644 selinux/%{modulename}.if \
  %{buildroot}%{_datadir}/selinux/devel/include/%{moduletype}/%{modulename}.if
# Install copr-selinux-enable which will be called in %posttrans
install -d %{buildroot}%{_sbindir}
install -p -m 755 selinux/%{name}-selinux-enable %{buildroot}%{_sbindir}/%{name}-selinux-enable
install -p -m 755 selinux/%{name}-selinux-relabel %{buildroot}%{_sbindir}/%{name}-selinux-relabel

install -d %{buildroot}%{_mandir}/man8
install -p -m 644 man/%{name}-selinux-enable.8 %{buildroot}/%{_mandir}/man8/
install -p -m 644 man/%{name}-selinux-relabel.8 %{buildroot}/%{_mandir}/man8/
%endif

%check
%if %{with_test} && %{with_server}
    pushd coprs_frontend
    COPR_CONFIG="$(pwd)/config/copr_unit_test.conf" ./manage.py test
    popd
%endif

%if %{with_server}
%pre backend
getent group copr >/dev/null || groupadd -r copr
getent passwd copr >/dev/null || \
useradd -r -g copr -G lighttpd -s /bin/bash -c "COPR user" copr
/usr/bin/passwd -l copr >/dev/null

%post backend
%systemd_post copr-backend.service

%preun backend
%systemd_preun copr-backend.service

%postun backend
%systemd_postun_with_restart copr-backend.service

%pre frontend
getent group copr-fe >/dev/null || groupadd -r copr-fe
getent passwd copr-fe >/dev/null || \
useradd -r -g copr-fe -G copr-fe -d %{_datadir}/copr/coprs_frontend -s /bin/bash -c "COPR frontend user" copr-fe
/usr/bin/passwd -l copr-fe >/dev/null

%post frontend
service httpd condrestart

%post selinux
if /usr/sbin/selinuxenabled ; then
   %{_sbindir}/%{name}-selinux-enable
fi

%posttrans selinux
if /usr/sbin/selinuxenabled ; then
   %{_sbindir}/%{name}-selinux-relabel
fi

%postun
# Clean up after package removal
if [ $1 -eq 0 ]; then
  for selinuxvariant in targeted; do
      /usr/sbin/semodule -s ${selinuxvariant} -l > /dev/null 2>&1 \
        && /usr/sbin/semodule -s ${selinuxvariant} -r %{modulename} || :
    done
fi
%{sbinpath}/restorecon -rvvi %{_sharedstatedir}/copr

%files backend
%doc LICENSE README
%dir %{_datadir}/copr
%dir %{_sharedstatedir}/copr
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/jobs/
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/public_html/
%dir %attr(0755, copr, copr) %{_sharedstatedir}/copr/public_html/results
%dir %attr(0755, copr, copr) %{_var}/log/copr
%dir %attr(0755, copr, copr) %{_var}/log/copr/workers
%dir %attr(0755, copr, copr) %{_var}/run/copr-backend

%ghost %{_var}/log/copr/copr.log
%ghost %{_var}/log/copr/workers/worker-*.log
%ghost %{_var}/run/copr-backend/copr-be.pid

%config(noreplace) %{_sysconfdir}/logrotate.d/copr-backend
%dir %{_pkgdocdir}
%doc %{_pkgdocdir}/lighttpd
%doc %{_pkgdocdir}/playbooks
%dir %{_sysconfdir}/copr
%config(noreplace) %{_sysconfdir}/copr/copr-be.conf
%{_unitdir}/copr-backend.service
%{_tmpfilesdir}/copr-backend.conf
%{_sbindir}/copr-prune-repo
%config(noreplace) %{_sysconfdir}/cron.daily/copr-backend

%{_datadir}/copr/backend
%{_datadir}/copr/copr-be.py*

%files frontend
%doc LICENSE coprs.conf.example copr-setup.txt
%dir %{_datadir}/copr
%dir %{_sysconfdir}/copr
%dir %{_sharedstatedir}/copr
%{_datadir}/copr/coprs_frontend

%defattr(-, copr-fe, copr-fe, -)
%dir %{_sharedstatedir}/copr/data
%dir %{_sharedstatedir}/copr/data/openid_store
%dir %{_sharedstatedir}/copr/data/whooshee
%dir %{_sharedstatedir}/copr/data/whooshee/copr_user_whoosheer

%ghost %{_sharedstatedir}/copr/data/copr.db

%defattr(600, copr-fe, copr-fe, 700)
%config(noreplace)  %{_sysconfdir}/copr/copr.conf
%config(noreplace)  %{_sysconfdir}/copr/copr_devel.conf
%config(noreplace)  %{_sysconfdir}/copr/copr_unit_test.conf
%endif # with_server

%files cli
%doc LICENSE README.rst
%{_bindir}/copr-cli
%{python_sitelib}/*
%{_mandir}/man1/copr-cli.1*

%if %{with_server}
%files doc
%doc %{_pkgdocdir}/python-doc

%files selinux
%{_datadir}/selinux/*/%{modulename}.pp.bz2
# empty, do not distribute it for now
%exclude %{_datadir}/selinux/devel/include/%{moduletype}/%{modulename}.if
%{_sbindir}/%{name}-selinux-enable
%{_sbindir}/%{name}-selinux-relabel
%{_mandir}/man8/%{name}-selinux-enable.8*
%{_mandir}/man8/%{name}-selinux-relabel.8*
%endif # with_server

%changelog
* Mon Jan 13 2014 Miroslav Suchý <msuchy@redhat.com> 1.23-1
- [backend] rhel7-beta do not have comps
- 1052073 - correctly parse malformed chroot

* Fri Jan 10 2014 Miroslav Suchý <msuchy@redhat.com> 1.22-1
- [backend] if we could not spawn VM, wait a moment and try again
- [backend] use createrepo_c instead of createrepo
- 1050952 - check if copr_url exist in config
- [frontend] replace newlines in description by space in repo file

* Wed Jan 08 2014 Miroslav Suchý <msuchy@redhat.com> 1.21-1
- 1049460 - correct error message
- [cron] manualy clean /var/tmp after createrepo

* Wed Jan 08 2014 Miroslav Suchý <msuchy@redhat.com> 1.20-1
- [cli] no need to set const with action=store_true
- [cli] code cleanup
- 1049460 - print nice error when projects does not exist
- 1049392 - require python-setuptools
- [backend] add --verbose to log to stderr
- [backend] handle KeyboardInterrupt without tons of tracebacks
- 1048508 - fix links at projects lists
- [backend] in case of error the output is in e.output
- [selinux] allow httpd to search
- [backend] set number of worker in name of process
- [logrotate] rotate every week unconditionally
- [backend] do not traceback if jobfile is mangled
- [backend] print error messages to stderr
- [cli] do not require additional arguments for --nowait
- [backend] replace procname with setproctitle
- [cli] use copr.fedoraproject.org as default url
- [frontend] show monitor even if last build have been canceled
- [backend] call correct function
- [cli] print errors to stderr
- 1044136 - do not print TB if config in mangled
- 1044165 - Provide login and token information in the same form as entered to
  ~/.config-copr
- [frontend] code cleanup
- [frontend] move rendering of .repo file to helpers
- 1043649 - in case of Fedora use $releasever in repo file
- [frontend] condition should be in reverse

* Mon Dec 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.19-1
- [backend] log real cause if ansible crash
- [frontend] try again if whoosh does not get lock
- [backend] if frontend does not respond, repeat
- print yum repos nicely
- Bump the copr-cli release to 0.2.0 with all the changes made
- Refer to the man page for more information about the configuration file for
  copr-cli
- Rework the layout of the list command
- Fix parsing the copr_url from the configuration file
- [backend] run createrepo as copr user
- 1040615 - wrap lines with long URL

* Wed Dec 11 2013 Miroslav Suchý <msuchy@redhat.com> 1.18-1
- [frontend] inicialize variable

* Wed Dec 11 2013 Miroslav Suchý <msuchy@redhat.com> 1.17-1
- [frontend] fix latest build variable overwrite

* Wed Dec 11 2013 Miroslav Suchý <msuchy@redhat.com> 1.16-1
- [backend] store jobs in id-chroot.json file
- [frontend] handle unknown build/chroot status
- use newstyle ansible variables

* Tue Dec 10 2013 Miroslav Suchý <msuchy@redhat.com> 1.15-1
- [frontend] smarter package name parsing
- [frontend] extend range to allow 0
- handle default timeout on backend
- initial support for SCL
- [backend] create word readable files in result directory
- [backend] print tracebacks
- [frontend] monitor: display only pkg name w/o version
- [doc] update api docs
- [doc] update copr-cli manpage
- [cli] list only name, description and instructions
- [cli] add support for build status & build monitor
- [frontend] add build status to API
- [playbook] do not overwrite mockchain
- [backend] add spece between options
- [backend] pass mock options correctly
- [frontend] support markdown in description and instructions
- [backend] Add macros to mockchain define arguments
- [backend] Pass copr username and project name to MockRemote
- [backend] Handle additional macro specification in MockRemote
- [frontend] monitor: show results per package
- [frontend] add favicon
- [backend] quote strings before passing to mockchain
- send chroots with via callback to frontend
- [cli] change cli to new api call
- enhance API documentation
- add yum_repos to coprs/user API call
- [frontend] provide link to description of allowed content
- [backend] we pass just one chroot
- [backend] - variable play is not defined
- if createrepo fail, run it again
- [cron] fix syntax error
- [man] state that --chroot for create command is required
- [spec] enable tests
- [howto] add note about upgrading db schema
- [frontend]: add copr monitor
- [tests]: replace test_allowed_one
- [tests]: fix for BuildChroots & new backend view
- [frontend] rewrite backend view to use Build <-> Chroot relation
- [frontend] add Build <-> Chroot relation
- 1030493 - [cli] check that at least one chroot is entered
- [frontend] typo
- fixup! [tests]: fix test_build_logic to handle BuildChroot
- fixup! [frontend] add ActionsLogic
- [tests]: fix test_build_logic to handle BuildChroot
- [spec] enable/disable test using variable
- add migration script - add table build_chroot
- [frontend] skip legal-flag actions when dumping waiting actions
- [frontend] rewrite backend view to use Build <-> Chroot relation
- [frontend] add ActionsLogic
- [frontend] create BuildChroot objects on new build
- [frontend] add Build <-> Chroot relation
- [frontend] add StatusEnum
- [frontend] fix name -> coprname typo
- [frontend] remove unused imports
- [frontend] add missing json import
- [backend] rework ip address extraction
- ownership of /etc/copr should be just normal
- [backend] - wrap up returning action in "action" blok
- [backend] rename backend api url
- [backend] handle "rename" action
- [backend] handle "delete" action
- base handling of actions
- move callback to frontend to separate object
- secure waiting_actions with password
- pick only individual builds
- make address, where we send legal flags, configurable
- send email to root after legal flag have been raised

* Fri Nov 08 2013 Miroslav Suchý <msuchy@redhat.com> 1.14-1
- 1028235 - add disclaimer about repos
- fix pagination
- fix one failing test

* Wed Nov 06 2013 Miroslav Suchý <msuchy@redhat.com> 1.13-1
- suggest correct name of repo file
- we could not use releasever macro
- no need to capitalize Projects
- another s/copr/project
- add link to header for sign-in
- fix failing tests
- UX - let textarea will full widht of box
- UX - make background of hovered builds darker
- generate yum repo for each chroot of copr
- align table header same way as ordinary rows
- enable resulting repo and disable gpgchecks

* Mon Nov 04 2013 Miroslav Suchý <msuchy@redhat.com> 1.12-1
- do not send parameters when we neither need them nor use them
- authenticate using api login, not using username
- disable editing name of project
- Add commented out WTF_CSRF_ENABLED = True to configs
- Use new session for each test
- fix test_coprs_general failures
- fix test_coprs_builds failures
- Add WTF_CSRF_ENABLED = False to unit test config
- PEP8 fixes
- Fix compatibility with wtforms 0.9
- typo s/submited/submitted/
- UX - show details of build only after click
- add link to FAQ to footer
- UX - add placeholders
- UX - add asterisk to required fields
- dynamicly generate url for home
- add footer

* Sat Oct 26 2013 Miroslav Suchý <msuchy@redhat.com> 1.11-1
- catch IOError from libravatar if there is no network

* Fri Oct 25 2013 Miroslav Suchý <msuchy@redhat.com> 1.10-1
- do not normalize url
- specify full prefix of http
- execute playbook using /usr/bin/ansible-playbook
- use ssh transport
- check after connection is made
- add notes about debuging mockremote
- clean up instance even when worker fails
- normalize paths before using
- do not use exception variable
- operator should be preceded and followed by space
- remove trailing whitespace
- convert comment to docstring
- use ssh transport
- do not create new ansible connection, reuse self.conn
- run copr-be.py as copr
- s/Copr/Project/ where we use copr in meaning of projects
- number will link to those coprs, to which it refers
- run log and jobgrab as copr user
- log event to log file
- convert comment into docstring
- use unbufferred output for copr-be.py
- hint how to set ec2 variables
- document sleeptime
- document copr_url for copr-cli
- document how to set api key for copr-cli
- do not create list of list
- document SECRET_KEY variable
- make note how to become admin
- instruct people to install selinux with frontend

* Thu Oct 03 2013 Miroslav Suchý <msuchy@redhat.com> 1.9-1
- prune old builds
- require python-decorator
- remove requirements.txt
- move TODO-backend to our wiki
- create pid file in /var/run/copr-backend
- add backend service file for systemd
- remove daemonize option in config
- use python logging
- create pid file in /var/run by default
- do not create destdir
- use daemon module instead of home brew function
- fix default location of copr-be.conf
- 2 tests fixed, one still failing
- fix failing test test_fail_on_missing_dash
- fixing test_fail_on_nonexistent_copr test
- run frontend unit tests when building package
- Adjust URLs in the unit-tests to their new structure
- Adjust the CLI to call the adjuste endpoint of the API
- Adjust API endpoint to reflects the UI endpoints in their url structure
- First pass at adding fedmsg hooks.

* Tue Sep 24 2013 Miroslav Suchý <msuchy@redhat.com> 1.8-1
- 1008532 - require python2-devel
- add note about ssh keys to copr-setup.txt
- set home of copr user to system default

* Mon Sep 23 2013 Miroslav Suchý <msuchy@redhat.com> 1.7-1
- 1008532 - backend should own _pkgdocdir
- 1008532 - backend should owns /etc/copr as well
- 1008532 - require logrotate
- 1008532 - do not distribute empty copr.if
- 1008532 - use %%{?_smp_mflags} macro with make
- move jobsdir to /var/lib/copr/jobs
- correct playbooks path
- selinux with enforce can be used for frontend

* Wed Sep 18 2013 Miroslav Suchý <msuchy@redhat.com> 1.6-1
- add BR python-devel
- generate selinux type for /var/lib/copr and /var/log/copr
- clean up backend setup instructions
- initial selinux subpackage

* Mon Sep 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.5-1
- 1008532 - use __python2 instead of __python
- 1008532 - do not mark man page as doc
- 1008532 - preserve timestamp

* Mon Sep 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.4-1
- add logrotate file

* Mon Sep 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.3-1
- be clear how we create tgz

* Mon Sep 16 2013 Miroslav Suchý <msuchy@redhat.com> 1.2-1
- fix typo
- move frontend data into /var/lib/copr
- no need to own /usr/share/copr by copr-fe
- mark application as executable
- coprs_frontend does not need to be owned by copr-fe
- add executable attribute to copr-be.py
- remove shebang from dispatcher.py
- squeeze description into 80 chars
- fix typo
- frontend need argparse too
- move results into /var/lib/copr/public_html
- name of dir is just copr-%%version
- Remove un-necessary quote that breaks the tests
- Adjust unit-tests to the new urls
- Update the URL to be based upon a /user/copr/<action> structure
- comment config copr-be.conf and add defaults
- put examples of builderpb.yml and terminatepb.yml into doc dir
- more detailed description of copr-be.conf
- move files in config directory not directory itself
- include copr-be.conf
- include copr-be.py
- create copr with lighttpd group
- edit backend part of copr-setup.txt
- remove fedora16 and add 19 and 20
- create -doc subpackage with python documentation
- add generated documentation on gitignore list
- add script to generate python documentation
- copr-setup.txt change to for mock
- rhel6 do not know _pkgdocdir macro
- make instruction clear
- require recent whoosh
- add support for libravatar
- include backend in rpm
- add notes about lighttpd config files and how to deploy them
- do not list file twice
- move log file to /var/log
- change destdir in copr-be.conf.example
- lightweight is the word and buildsystem has more meaning than 'koji'.
- restart apache after upgrade of frontend
- own directory where backend put results
- removal of hidden-file-or-dir
  /usr/share/copr/coprs_frontend/coprs/logic/.coprs_logic.py.swo
- copr-backend.noarch: W: spelling-error %%description -l en_US latests ->
  latest, latest's, la tests
- simplify configuration - introduce /etc/copr/copr*.conf
- Replace "with" statements with @TransactionDecorator decorator
- add python-flexmock to deps of frontend
- remove sentence which does not have meaning
- change api token expiration to 120 days and make it configurable
- create_chroot must be run as copr-fe user
- add note that you have to add chroots to db
- mark config.py as config so it is not overwritten during upgrade
- own directory data/whooshee/copr_user_whoosheer
- gcc is not needed
- sqlite db must be owned by copr-fe user
- copr does not work with selinux
- create subdirs under data/openid_store
- suggest to install frontend as package from copr repository
- on el6 add python-argparse to BR
- add python-requests to BR
- add python-setuptools to BR
- maintain apache configuration on one place only
- apache 2.4 changed access control
- require python-psycopg2
- postgresql server is not needed
- document how to create db
- add to HOWTO how to create db
- require python-alembic
- add python-flask-script and python-flask-whooshee to requirements
- change user in coprs.conf.example to copr-fe
- fix paths in coprs.conf.example
- copr is noarch package
- add note where to configure frontend
- move frontend to /usr/share/copr/coprs_frontend
- put production placeholders in coprs_frontend/coprs/config.py
- put frontend into copr.spec
- web application should be put in /usr/share/%%{name}

* Mon Jun 17 2013 Miroslav Suchý <msuchy@redhat.com> 1.1-1
- new package built with tito


