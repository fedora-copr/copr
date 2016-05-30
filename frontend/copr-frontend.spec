%global with_test 1
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%global __python2 %{__python}
%endif

Name:       copr-frontend
Version:    1.93
Release:    1%{?dist}
Summary:    Frontend for Copr

Group:      Applications/Productivity
License:    GPLv2+
URL:        https://fedorahosted.org/copr/
# Source is created by
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/frontend
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

BuildArch:  noarch
#BuildRequires: asciidoc
#BuildRequires: libxslt
BuildRequires: util-linux
BuildRequires: python-setuptools
BuildRequires: python-requests
BuildRequires: python2-devel
BuildRequires: systemd
%if 0%{?rhel} < 7 && 0%{?rhel} > 0
BuildRequires: python-argparse
%endif
#for doc package
#BuildRequires: epydoc
#BuildRequires: graphviz

Requires:   httpd
Requires:   mod_wsgi
Requires:   passwd
Requires:   curl
Requires:   python-alembic
Requires:   python-flask
Requires:   python-flask-openid
Requires:   python-openid-teams
Requires:   python-flask-wtf
Requires:   python-flask-sqlalchemy
Requires:   python-flask-script
Requires:   python-flask-whooshee
#Requires:   python-virtualenv
Requires:   python-blinker
Requires:   python-markdown
Requires:   python-psycopg2
Requires:   python-pylibravatar
Requires:   python-requests
Requires:   python-whoosh >= 2.5.3
Requires:   pytz
Requires:   python-six
Requires:   python-netaddr
Requires:   python-flask-restful
Requires:   python-marshmallow >= 2.0.0
# for tests:
Requires:   pytest
Requires:   python-flexmock
Requires:   python-mock
Requires:   python-decorator
Requires:   yum
Suggests:   logstash
Requires:   redis
Requires:   python-redis
Requires:   python-dateutil
Requires:   crontabs

%if 0%{?fedora} >= 23
Requires: python-dnf
BuildRequires: python-dnf
%else
Requires: dnf
BuildRequires: dnf
%endif

%if 0%{?rhel} < 7 && 0%{?rhel} > 0
BuildRequires: python-argparse
%endif
# check
BuildRequires: python-six
BuildRequires: python-flask
BuildRequires: python-flask-script
BuildRequires: python-flask-sqlalchemy
BuildRequires: python-flask-openid
BuildRequires: python-openid-teams
BuildRequires: python-flask-whooshee
BuildRequires: python-pylibravatar
BuildRequires: python-flask-wtf
BuildRequires: python-netaddr
BuildRequires: python-redis
BuildRequires: redis
BuildRequires: python-dateutil
BuildRequires: pytest
BuildRequires: yum
BuildRequires: python-mock
BuildRequires: python-decorator
BuildRequires: python-markdown
BuildRequires: pytz
BuildRequires: python-flask-restful
BuildRequires: python-marshmallow >= 2.0.0
BuildRequires: python-sphinx
BuildRequires: python-sphinxcontrib-httpdomain
BuildRequires: python-whoosh
BuildRequires: python-blinker

%if 0%{?with_python3}
Requires:   dnf
Requires:   python3-flask
Requires:   python3-flask-wtf
Requires:   python3-flask-sqlalchemy
Requires:   python3-flask-script
Requires:   python3-flask-whooshee
Requires:   python3-pytz
Requires:   python3-markdown
Requires:   python3-netaddr
Requires:   python3-redis
Requires:   python3-pylibravatar
Requires:   python3-wtforms
Requires:   python3-flask-wtf
Requires:   python3-flask-restful
Requires:   python3-marshmallow
Requires:   python3-blinker
Requires:   python3-flask-openid
Requires:   python3-openid-teams

%if 0%{?fedora} >= 23
Requires: python3-dnf
BuildRequires: python3-dnf
%else
Requires: dnf
BuildRequires: dnf
%endif

%endif # with_python3

Provides: bundled(bootstrap) = 3.3.4
Provides: bundled(bootstrap-combobox) = 1.1.6
Provides: bundled(bootstrap-select) = 1.5.4
Provides: bundled(bootstrap-treeview) = 1.0.1
Provides: bundled(c3) = 0.4.10
Provides: bundled(d3) = 3.5.0
Provides: bundled(datatables) = 1.10.7
Provides: bundled(datatables-colreorder) = 1.1.3
Provides: bundled(datatables-colvis) = 1.1.2
Provides: bundled(font-awesome) = 1.0.1
Provides: bundled(google-code-prettify) = 4.3.0
Provides: bundled(html5shiv) = 3.7.2
Provides: bundled(jquery) = 1.11.3
Provides: bundled(jquery-ui) = 1.11.4
Provides: bundled(Respond.js) = 1.4.2

%description
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package contains frontend.

%package doc
Summary:    Code documentation for COPR
Obsoletes:  copr-doc < 1.38

%description doc
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package include documentation for COPR code. Mostly useful for developers
only.

%prep
%setup -q


%build
# build documentation
#pushd documentation
#make %{?_smp_mflags} python
#popd

%install



install -d %{buildroot}%{_sysconfdir}/copr
install -d %{buildroot}%{_datadir}/copr/coprs_frontend
install -d %{buildroot}%{_sharedstatedir}/copr/data/openid_store
install -d %{buildroot}%{_sharedstatedir}/copr/data/openid_store/associations
install -d %{buildroot}%{_sharedstatedir}/copr/data/openid_store/nonces
install -d %{buildroot}%{_sharedstatedir}/copr/data/openid_store/temp
install -d %{buildroot}%{_sharedstatedir}/copr/data/whooshee
install -d %{buildroot}%{_sharedstatedir}/copr/data/whooshee/copr_user_whoosheer
install -d %{buildroot}%{_sharedstatedir}/copr/data/srpm_storage
install -d %{buildroot}%{_sysconfdir}/cron.hourly

install -p -m 755 conf/cron.hourly/copr-frontend %{buildroot}%{_sysconfdir}/cron.hourly/copr-frontend

cp -a coprs_frontend/* %{buildroot}%{_datadir}/copr/coprs_frontend
sed -i "s/__RPM_BUILD_VERSION/%{version}-%{release}/" %{buildroot}%{_datadir}/copr/coprs_frontend/coprs/templates/layout.html

mv %{buildroot}%{_datadir}/copr/coprs_frontend/coprs.conf.example ./
mv %{buildroot}%{_datadir}/copr/coprs_frontend/config/* %{buildroot}%{_sysconfdir}/copr
rm %{buildroot}%{_datadir}/copr/coprs_frontend/CONTRIBUTION_GUIDELINES
touch %{buildroot}%{_sharedstatedir}/copr/data/copr.db

install -d %{buildroot}%{_var}/log/copr
install -d %{buildroot}%{_sysconfdir}/logrotate.d
install -d %{buildroot}%{_sysconfdir}/logstash.d
cp -a conf/logrotate %{buildroot}%{_sysconfdir}/logrotate.d/%{name}
cp -a conf/logstash.conf %{buildroot}%{_sysconfdir}/logstash.d/copr_frontend.conf
touch %{buildroot}%{_var}/log/copr/frontend.log

%check
%if %{with_test} && "%{_arch}" == "x86_64"
    pushd coprs_frontend
    REDIS_PORT=7777
    redis-server --port $REDIS_PORT & #&> _redis.log &
    rm -rf /tmp/copr.db /tmp/whooshee || :
    COPR_CONFIG="$(pwd)/config/copr_unit_test.conf" ./manage.py test
    redis-cli -p $REDIS_PORT shutdown
    popd
%endif

%pre
getent group copr-fe >/dev/null || groupadd -r copr-fe
getent passwd copr-fe >/dev/null || \
useradd -r -g copr-fe -G copr-fe -d %{_datadir}/copr/coprs_frontend -s /bin/bash -c "COPR frontend user" copr-fe
/usr/bin/passwd -l copr-fe >/dev/null

%post
service httpd condrestart
service logstash condrestart

%files
%license LICENSE
%doc coprs.conf.example
%dir %{_datadir}/copr
%dir %{_sysconfdir}/copr
%dir %{_sharedstatedir}/copr
%{_datadir}/copr/coprs_frontend

%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%config(noreplace) %{_sysconfdir}/logstash.d/copr_frontend.conf

%defattr(-, copr-fe, copr-fe, -)
%dir %{_sharedstatedir}/copr/data
%dir %{_sharedstatedir}/copr/data/openid_store
%dir %{_sharedstatedir}/copr/data/whooshee
%dir %{_sharedstatedir}/copr/data/whooshee/copr_user_whoosheer
%dir %{_sharedstatedir}/copr/data/srpm_storage

%ghost %{_sharedstatedir}/copr/data/copr.db

%defattr(644, copr-fe, copr-fe, 755)
%dir %{_var}/log/copr
%ghost %{_var}/log/copr/*.log

%defattr(600, copr-fe, copr-fe, 700)
%config(noreplace)  %{_sysconfdir}/copr/copr.conf
%config(noreplace)  %{_sysconfdir}/copr/copr_devel.conf
%config(noreplace)  %{_sysconfdir}/copr/copr_unit_test.conf

%config(noreplace) %attr(0755, root, root) %{_sysconfdir}/cron.hourly/copr-frontend

%files doc
%license LICENSE
#%doc documentation/python-doc

%changelog
* Thu May 26 2016 clime <clime@redhat.com> 1.93-1
- added source_type to URL and Upload UI build forms
- support for creating/editing/deleting/listing packages implemented
- Bug 1337446 - Broken links to builds in package tab
- action to create gpg key is now always sent
- added tests for projects forking
- building via url and pypi refactoring; see df6ad16
- Bug 1336360 - reverse naming for custom and mageia chroots
- Rubygems building support with Anitya autorebuilds
- ./manage.py mark_as_failed command added
- build timeout increased to 24 hours
- added missing group insert/update hooks into CoprWhoosheer
- added package names into search index + field boosts tweaking
- fixed search for just a group name
- Bug 1333792 - do not count group projects
- Bug 1334625 - Search for coprs owned by a group does not work
- Bug 1334575 - Missing package name in "Recent builds" tab for
  upload/url builds
- Bug 1334390 - Bad link in Recent Builds for group project
- reset button also sets source_json to {}
- speeding up of Packages view
- enable other group users to edit the project settings
- Bug 1333082 - Disable createrepo does not work on group project

* Wed May 04 2016 Miroslav Suchý <msuchy@redhat.com> 1.92-1
- load group.id before we commit the session

* Fri Apr 29 2016 Miroslav Suchý <msuchy@redhat.com> 1.91-1
- check for duplicities during creating
- toggle-all button for chroot selection

* Thu Apr 28 2016 Miroslav Suchý <msuchy@redhat.com> 1.90-1
- comment in unittests after some _serious_ investigation
- monitor unittest removed (output of get_monitor_data changed),
  expected response for delete_fail_unfinished_build test changed to 204

* Fri Apr 22 2016 Miroslav Suchý <msuchy@redhat.com> 1.89-1
- requires python3* packages which are finally packaged
- add BR python-blinker

* Fri Apr 22 2016 Miroslav Suchý <msuchy@redhat.com> 1.88-1
- add BR python-whoosh

* Fri Apr 22 2016 Miroslav Suchý <msuchy@redhat.com> 1.87-1
- run createrepo on forked project (RhBug: 1329076)
- search-bar placeholder update to reflect search improvements
- changed build deletion check for unfinished builds
- builds monitor (performance) optimization (both frontend and API)
- fix error when editing group project
- search only for non-group projects (RhBug: 1328122) (RhBug:
  1328129)
- Bug 1327598 - RFE: Deleting project should be faster
- code clarifications, simplications & fixes related to copr.owner
  to copr.user rename
- tabs on the monitor page are more visible
- owner renamed to user in Copr model
- when reference /api page, use current hostname
- search improvements
- change order of ordering on status page
- indicate if we reached limit on status page
- implement building via mock
- Bug 1325515 - rebuild repository on group project does not work

* Fri Apr 08 2016 Miroslav Suchý <msuchy@redhat.com> 1.86-1
- temporary disable this test
- tests: base url is now in config not taken from results
- Bug 1323796 - incorrect centos7 repodata - deleted build present
- [python][cli] refactor building via tito
- [python][cli] implement building via tito
- Bug 1324378 - Wrong .repo file in forked project.
- fix removing packages from group projects (RhBug: 1322293)
- create database records for duplicated builds
- package default source is automatically set upon creation from its
  build data
- do not print whitespace around urls in href
- do not print whitespace around urls in href
- fix rawhide_to_release for old directory naming
- copr can actually work even without logstash
- set correctly name of page for group projects
- [api] return error when group does not exist
- Bug 1196826 - RFE: A build is marked as failed even though one
  chroot is still running

* Sun Mar 20 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.85-1
- allow creating group projects via API
- do not build tito based packages, if the commit did not affect it
- bug 1305754 - incorrect dates are displayed on the build page
- bug 1318229 - fix package deletion issue

* Mon Mar 14 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.84-1
- support building from PyPI
- support project forking
- add button to reset package default source (RhBug: 1314917)
- support for import (copr-dist-git per-task) logs
- implement migration report table
- add possibility to run only particular migration stage
- fix 1311777 - failure to delete project (and cancelled build)
- fix 1314369 - Exception raised when resubmitting Git&Tito build
- fix resubmiting as reported in RHBZ 1313270
- fix default package source validation for group projects (RhBug: 1314918)
- fix chroot states in monitor (RhBug: 1306182)

* Mon Feb 22 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.83-1
- [frontend] select as user_name; see e492bb

* Mon Feb 22 2016 clime <clime@redhat.com> 1.82-1
- patch for webhook invoked rebuilds

* Fri Jan 29 2016 Miroslav Suchý <msuchy@redhat.com> 1.81-1
- minor css fix
- report a bug link
- fix 1286334 - resubmit should offer other buildroots
- admin section UI
- fix 1296805 also for building from "other builds"
- fix 1296805 - cannot enable internet network access for builds
  without enabling it in project settings
- fix for two special cases: 1) no build exists for a package (might
  happen if srpm import failed or all builds were deleted), 2) there is no
  chroot for a build and hence build.status cannot be derived from chroot's
  statuses (also case for failes srpm imports)
- fix 1297907 - Information about packages is not correct
- fix 1300849 
- fix 1299159 - "Git & Tito" new build includes even deselected
  chroots
- remove trailing and leading whitespaces in links (at least for
  build links, other links might still contain some)
- fix bug 1299163 - Clicking on a build in list of builds for a
  package gives 500 if the owner is a group
- [frontend][backend] implement rawhide to release feature First create new
  chroots:     python manage.py create_chroot fedora-24-i386 fedora-24-x86_64
- don't show rebuild button to all
- Packages and Builds css polishing
- button icon
- two sections on the Edit Poject Details view
- edit chroot buttons
- fix cancel button on the Edit Chroot view
- disable internet connection by default
- get_copr_safe() should always return only personal projects

* Tue Jan 05 2016 Miroslav Suchý <miroslav@suchy.cz> 1.80-1
- 1295930 - leftover after b7c5a76848587629cc9358fe45258a2f1af884e7
- 1295915 - leftover after 4b1ec255 refactoring

* Tue Jan 05 2016 Miroslav Suchý <miroslav@suchy.cz> 1.79-1
- Fix API uploads after frontend refactoring
- manage.py requires python-requests
- dependency on dnf package removed by providing own impl of
  SplitFilename function in coprs/helpers.py
- versioned (by current f23 package versions) requirements file
  added and also cleanup in non-versioned requirements.txt file
- split creating of SQL functions to two separate commands
- adjust python path to fix 'alembic history'
- do not require package_name on build forms
- show both request and manage permissions forms for admin (RhBug:
  1268261)

* Wed Dec 23 2015 Miroslav Suchý <msuchy@redhat.com> 1.78-1
- do not validate package forms twice
- enhance the packages and webhooks UI
- re-design source options for packages to tabs
- show active menu tab when inner tab is selected
- display link to webhooks settings
- merge group/user views for package routes
- fix checkboxes in package adding
- 1286797 - failing validation on project edit
- be able to print packages without builds
- implement packages adding
- show flash messages when editing packages

* Wed Dec 09 2015 Miroslav Suchý <msuchy@redhat.com> 1.77-1
- do not assume logged user
- use same naming convention as for builds (i.e.
  coprs_ns.copr_edit_package instead of coprs_ns.copr_package_edit)
- make cleaner URL for detailed monitor
- complete missing breadcrumbs
- add Packages page
- use copr_url macro (see 2473efc)
- move package views to seperate file
- make a settings tab from permissions page
- clarify settings tab names
- move 'New Build' button to 'Builds' page
- use copr_url macro to generate proper URLs for user/group projects
- remove duplicates from build forms
- don't use create_form_cls for package forms
- explain webhooks
- unite edit, webhooks and delete under settings page
- add checkbox for 'package.webhook_rebuild'
- removed old api documentation, added link to the rest api
  documentation at the ReadTheDocs.
- automatic builds from GitHub - initial implementation
- show which default source type is selected
- show icon instead of [edit] tag
- show all information about default source
- improve package default source navigation
- fix default source for group projects
- fix error handling on 'new build' page for url and tito
- fix broken 'new build' page for tito and mock on group projects
- provide link to rebuild package
- add Provides for bundled components
- do not use jquery from remote URL (RhBug: 1268215)
- possibility to set default source for the package
- add function only for Pg
- fix bug in the psql stored procedure (status order)
- use the same variable as defined in route

* Mon Nov 16 2015 Miroslav Suchý <msuchy@redhat.com> 1.76-1
- move status_to_order() definition to alembic

* Mon Nov 16 2015 Miroslav Suchý <miroslav@suchy.cz> 1.75-1
- Sending action to create gpg key right after the project creation
- Permission -> Permissions
- Make the New Build forms more organized
- fix breadcrumb
- using raw SQL for builds view
- [rhbz:#1273738] "dnf copr enable" fails with old projects because
  old projects are not redirect well
- [rhbz:#1279199] Internet access always enabled when building from
  CLI
- 1280416 - do not use @ in repo id
- Validate group name and access right during the group activation.
- make more abstract exceptions
- fix showing active tab for tito and mock
- implement support for multiple Mock SCMs
- implement mock support in dist-git
- implement mock support in frontend
- fix dnf dependency for F23

* Mon Nov 02 2015 Miroslav Suchý <msuchy@redhat.com> 1.74-1
- [frontend] require dnf because of 6ab5306

* Mon Nov 02 2015 Miroslav Suchý <msuchy@redhat.com> 1.73-1
- fix permission tab on project page
- support APIv2
- still run on python2 until we get all py3 dependencies
- use integers division
- run on python3 from apache
- specify python3 dependencies
- use print function instead of statement
- run tests in python3 interpreter
- [api 2] don't assert url parameters in fixed order Flask's url_for
  can generate them randomly
- sort by argument 'key' instead of 'cmp'
- explicitly cast map results to list On python3, the result of a
  map function is an iterator, not list
- do the str/bytes/unicode py2/3 compatibility magic
- use dict items() instead of iteritems()
- use python2/3 compatible metaclasses
- fix import path of rest_api
- use rpmutils provided by DNF
- use six.moves.urllib instead of py2 only urllib
- properly set repo rpm configuration
- use absolute path
- implement logging for generating repo packages
- use new api format
- add Git and Tito errors
- sort colums with time ago natural way (not alphabetical)
- 1272184 - sort builds numericaly
- tito support in frontend

* Wed Oct 14 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.72-1
- [frontend] typo
- [frontend][docs] minor

* Wed Oct 14 2015 Miroslav Suchý <msuchy@redhat.com> 1.71-1
- more api2 improvements
- proper check for group membership in the copr creation method
- run redis server during %%check

* Tue Oct 13 2015 Miroslav Suchý <msuchy@redhat.com> 1.70-1
- support for groups projects
- api2 improvements
- [rhbz: #1266750]  Unable to view second, third, … page of search
  results: " Search string must have at least 3 characters "

* Tue Sep 22 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.69-1
- hotfix for resubmit button

* Tue Sep 15 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.68-1
- fix tests to create tmp directory for srpm upload
- don't depend on python-copr

* Tue Sep 15 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.67-1
- new REST-like api
- fixed resubmitting build
- validate uploaded file to .src.rpm extension
- warn user if he use rpmfusion repository for building.
- give user hint how to give permission to somebody else
- [frontend][old API] backported `result_dir_url` of BuildChroot to the build
  details: new field `results_by_chroot`
- [frontend] [dist-git] provide build failure details
- fix missing copr names in yum_repos (RhBug:1258943) URL build.results may or
  may not end with slash, so when not, the urljoin cuts off it's last part
  (which is copr name)
- UI updates: 403, 404 errors, notification texts, footer, alerts are dismissable
- comps.xml support
- unify printing of form errors (RhBug:1252559)
- sort chroots alphabetically (RhBug:1253588)
- add command generate_repo_packages for manage.py
- build deletion fix (taiga #32)
- change columns in status (taiga #28)

* Tue Aug 11 2015 Miroslav Suchý <msuchy@redhat.com> 1.66-1
- correctly join url fragments
- create json for each package (RhBug:1252432)
- add route providing repo RPM packages
- show contact and homepage bubble only when its set
- generate one package for all fedora releases
- add experimental support for repo RPM packages (RhBug:1227696)

* Tue Aug 04 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.65-1
- Dist-git support
- Transition to Patternfly UI
- and lot of fixes
* Wed Jul 01 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.64-1
- [frontend] fix help text on builds pages

* Wed Jul 01 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.63-1
- fix tests for old f20
- assign owner by user id instead of the whole object When assigning
  the whole object which is already in the session, the actual object will be
  implicitly added too. This led to DuplicateException on F22.
- add "uploading" status
- update statistics look
- clearer links to results (RhBug:1221519)
- logstash config ignore requests generated by search engine
  crawlers

* Fri Jun 05 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.62-1
- [frontend] remove exessive log in logstash.conf

* Fri Jun 05 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.61-1
- added enabled_metadata=1 to .repo files
  metadata
- decorator intranet_required should always accept requests from
  localhost
- showing download stats

* Wed Jun 03 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.60-1
- [rhbz:#1227190] hotfix: restore old route to the repo_file handler
- Fix default networking option (RhBug:1215157)

* Sat May 30 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.59-1
- Front page rendering takes too much time due to a long sql query.
  Simplified until issue is resolved.
- fix regression: show again additional buildroot packages for
  modified chroots at overview page
- reject build_chroot status update for `failed`, `cancelled` and
  `succeded` states; added some logs
- new logo

* Wed May 20 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.58-1
- backend api: handle to mark all running/starting builds as pending
- add to example url to Fedora instance of FedMenu

* Fri May 15 2015 Miroslav Suchý <msuchy@redhat.com> 1.57-1
- Add optional fedmenu resources to every page.
- more specific error message in UrlListValidator
- /backend/waiting: filter out cancelled builds
- make option gpgcheck in copr.repo configurable
- show at most 200 builds at /status pages
- /backend/waiting returns at most 200 builds
- tests fix
- [backend] repaired unittests
- 1206562 - Cannot delete Copr because it incorrectly thinks
  there are unfinished builds. Solution: `failed` but unfinished (ended_on is
  null) builds should be rescheduled.
- [backend][frontend] Send for delete action only `src_pkg_name` instead of
  original URL.
- [api] Bug 1194592 - User is able to submit directory
- [rhbz:#1188784] RFE: Include a "last build" item on the overview
  page
- New python dependencies
- run tmp redis-server for tests
- Dedicated and more complex management for builder machines.
  Now builds failed due to VM errors reschedulted faster.

* Fri Mar 06 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.56-1
- hotfix:#1199258]  Link to Source RPM on build detail page points to a wrong URL

* Mon Mar 02 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.55-1
- [frontend] fix tests to be runnable without redis-server.

* Mon Mar 02 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.54-1
- [backend] [rhbz:#1091640] RFE: Release specific additional repos
- [frontend][backend] [rhbz:#1119300]  [RFE] allow easy add copr repos in using
  repository lis
- [frontend] enabled `gpgcheck=1` in .repo template
- [copr] monitor page redone: show version for each chroot
- [frontend] [rhbz:#1160370, #1173165] sub-page on resubmit action, where user
  could change preselected build chroots.
- [frontend] added filelog for frontend
- [frontend] Added "-%%{release}" to the build version on the copr pages.
- mark license as license in spec
- [rhbz:#1171796] copr sometimes doesn't delete build from repository
- [backend] [rhbz:#1073333] Record consecutive builds fails to redis. Added
  script to produce warnings for nagios check from failures recorded to redis.

* Thu Feb 05 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.53-1
- [frontend] enabled `gpgcheck=1` in .repo template
- [frontend] correct url for pubkey in .repo

* Fri Jan 23 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.52-1
- add url to gpg pubkey in .repo files
- [rhbz:#1183702]  Interrupted builds aren't re-added to the
  builder queue, and stuck forever in RUNNING state.
- [rhbz:#1133650] RFE: copr frontend on page of build details,
  results section should show multiple links that link directly for every
  chroot directory
- UI to control `enable_net` option, DB schema changes
- new command AddDebugUser for manage script
- [RHBZ:#1176364] Wrong value for the build timeout.
- [RHBZ:#1177179] Display the timezone with a format more similar to
  ISO 8601

* Mon Dec 15 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.51-1
- bugfix: send correct chroots in on_auto_createrepo_change()
- control auto_createrepo property of project through API

* Thu Dec 11 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.50-1
- fix unittest

* Thu Dec 11 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.49-1
- api workaround: removed auto_createrepo option
- show copr-frontend version;
- re-enabling of auto_createrepo should produce createrepo action
- 1169366 - Files installed in both copr-frontend and copr-frontend-doc
- Fix mismatch between documentation and actual API in new build
- disabled debug prints, fixed PEP8 violations

* Mon Nov 24 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.48-1
- [frontend] fixed paramater validation for API hanlde `create_new_copr`
- [frontend] show "createrepo" action only when user disable auto_createrepo
- [frontend] removed hardcoded frontend url from /api page.

* Fri Oct 24 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.47-1
- [frontend] sending createrepo action
- [frontend] [html]  new option to configure copr->auto_creatrepo
- [fronted] adding option to disable auto invokation of createrepo
- [frontent] [WIP]fixing unittest, better isolation during test run
- [frontend] [RHBZ: #1149091] bugfix:  'Repeat' does not respect chroot
  selection of original build
- Added script to automate tests execution inside virtualenv
- [frontend] [RHBZ:#1146825] Reorder chroots for monitor widget

* Wed Sep 24 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.46-1
- [frontend] added helper function and flask filter which allows to ensure that
  url starts with either http or https, see config

* Thu Sep 18 2014 Miroslav Suchý <msuchy@redhat.com> 1.45-1
- revert f0e5c211f86cc3691fda8d4412c21ef6338a339f
- [frontend] including project name
- [frontend] recent builds on the home page
- [frontend] project search update after patch
- support for kerberos authentication
- do not strictly resist on Fedora's OpenID
- [frontend] recent builds sorting fix
- [frontend] user's recent builds on their home page

* Wed Aug 27 2014 Miroslav Suchý <msuchy@redhat.com> 1.44-1
- fix spec parsing on arm
-  'manage.py update_indexes' and search fix
- [RHBZ:1131286] RFE: API endpoint for a project's "monitor" status

* Mon Aug 25 2014 Adam Samalik <asamalik@redhat.com> 1.43-1
- [frontend] bugfix: context_processor shouldn't return None
- [frontend] task queue sorting fix

* Fri Aug 22 2014 Adam Samalik <asamalik@redhat.com> 1.42-1
- [frontend] make all html tags to have the same left-padding
- [frontend][RHBZ:1128602] RFE: define banner for local instance
- [frontend][RHBZ:1131186] Use https URLs to install copr repo file
- [frontend] [RHBZ:1128231] Show list of recent builds owned by user ( for
  logged in users).
- [API] friendly notification about invalid/expired token
- [frontend] project name can not be just number
- [frontend] starting builds highlighted on the waiting list
- [frontend] [BZ:1128231] RFE: frontend user interface like koji: added
  `/recent` page which list of ended builds.
- [frontend] fixed SQLa ordering queries.
- [frontend] paginator fix
- [frontend] build states list
- [frontend] minor bugfix: fixed api method `cancel build`.

* Wed Aug 13 2014 Miroslav Suchý <msuchy@redhat.com> 1.41-1
- [frontend] bugifx: for some projects API doesn't return last-modified time in
  detail resource.
- new queue for backend
- [frontend] new waiting queue
- [frontend] sorting packages on the Monitor view

* Tue Jul 22 2014 Miroslav Suchý <msuchy@redhat.com> 1.40-1
- [frontend] status page fix
- [frontend] How to enable a repo on a Overview page
- [frontend] build listing fix
- [frontend] status page extension - running tasks
- [frontend] modified chroots in overview
- FrontendCallback prettified
- Starting state implemented, cancelling fixed
- [frontend] new build status: Starting
- [frontend] db migration

* Tue Jul 15 2014 Miroslav Suchý <msuchy@redhat.com> 1.39-1
- frontend: add f21 chroot
- 1118829 - suggest owners to entry link to reporting web
- small changes after review
- better and safer deleting of builds
- [frontend] build's ended_on time fix
- [frontend] built pkgs info - include subpackages
- deleting of failed builds fixed
- [frontend] api build details extended
- pkg name on the build page
- [frontend] pkg version on the Monitor page
- [frontend] pkg name and version on the build page
- [frontend] pkg name and version support
- [frontend] skipped state support
- Ansible playbok to generate frontend db documentation
- obsolete copr-doc
- [frontend] repeat build button in all states of build except pending
- [frontend] project update by admin fix
- get rid of multi assigment
- [frontend] repofiles without specifying architecture
- api search fix
- WSGIPassAuthorization needs to be on

* Fri May 30 2014 Miroslav Suchý <msuchy@redhat.com> 1.38-1
- [frontend] running build can not be deleted
- [frontend] cancel status set to all chroots

* Fri May 30 2014 Miroslav Suchý <msuchy@redhat.com> 1.37-1
- [frontend] monitor table design unified
- [frontend] skipping bad package urls
- builders can delete their builds
- css fix

* Wed May 21 2014 Miroslav Suchý <msuchy@redhat.com> 1.36-1
- 1077794 - add LICENSE to -doc subpackage
- 1077794 - own /usr/share/doc/copr-frontend
- 1077794 - remove BR make
- 1077794 - require passwd

* Wed May 21 2014 Miroslav Suchý <msuchy@redhat.com> 1.35-1
- build detail and new builds table
- admin/playground page
- Use "https" in API template
- Use flask_openid safe_roots to mitigate Covert Redirect.
- add newline at the end of repo file
- [cli & api] delete a project

* Thu Apr 24 2014 Miroslav Suchý <msuchy@redhat.com> 1.34-1
- add indexes
- 1086729 - make build tab friendly for users without JS
- copr-cli cancel fix
- correctly print chroots
- [frontend] SEND_EMAILS config correction

* Tue Apr 15 2014 Miroslav Suchý <msuchy@redhat.com> 1.33-1
- api: add chroots to playground api call
- check if chroot exist for specified project
- better explain additional yum repos

* Thu Apr 10 2014 Miroslav Suchý <msuchy@redhat.com> 1.32-1
- send permissions request to admin not to requestee

* Wed Apr 09 2014 Miroslav Suchý <msuchy@redhat.com> 1.31-1
- validate chroots in POST requests with API
- add /playground/list/ api call
- add playground column to copr table
- Make repo urls nicer so that last part matches filename
- fixes and documentation for 66287cc8
- use https for gravatar urls
- We can choose chroots for new builds
- [frontend] delete all builds with their project
- [frontend] config comments
- [frontend] sending emails when perms change
- [frontend] typo s/Coper/Copr/
- api: fix coprs.models.User usage in search
- status page fix: long time
- status page fix: project's owner
- building pkgs separately
- [frontend] let apache log in default location
- api: fix KeyError in search

* Wed Mar 19 2014 Miroslav Suchý <msuchy@redhat.com> 1.30-1
- Fix typo in API doc HTML
- white background
- status page
- create _pkgdocdir

* Tue Mar 18 2014 Miroslav Suchý <msuchy@redhat.com> 1.29-1
- move frontend to standalone package

* Thu Feb 27 2014 Miroslav Suchý <msuchy@redhat.com> 1.28-1
- [backend] - pass lock to Actions

* Wed Feb 26 2014 Miroslav Suchý <msuchy@redhat.com> 1.27-1
- [frontend] update to jquery 1.11.0
- [fronted] link username to fas
- [cli] allow to build into projects of other users
- [backend] do not create repo in destdir
- [backend] ensure that only one createrepo is running at the same time
- [cli] allow to get data from sent build
- temporary workaround for BZ 1065251
- Chroot details API now uses GET instead of POST
- when deleting/canceling task, go to same page
- add copr modification to web api
- 1063311 - admin should be able to delete task
- [frontend] Stray end tag h4.
- [frontend] another s/coprs/projects/ rename
- [frontend] provide info about last successfull build
- [spec] rhel5 needs group definition even in subpackage
- [frontend] move 'you agree' text to dd
- [frontend] add margin to chroots-set
- [frontend] add margin to field label
- [frontend] put disclaimer to paragraph tags
- [frontend] use black font color
- [frontend] use default filter instead of *_not_filled
- [frontend] use markdown template filter
- [frontend] use isdigit instead of is_int
- [frontend] move Serializer to helpers
- [frontend] fix coding style and py3 compatibility
- [cli] fix coding style and py3 compatibility
- [backend] fix coding style and py3 compatibility

* Tue Jan 28 2014 Miroslav Suchý <miroslav@suchy.cz> 1.26-1
- lower testing date
- move localized_time into filters
- [frontend] update user data after login
- [frontend] use iso-8601 date

* Mon Jan 27 2014 Miroslav Suchý <msuchy@redhat.com> 1.25-1
- 1044085 - move timezone modification out of template and make it actually
  work
- clean up temp data if any
- [db] timezone can be nullable
- [frontend] actually save the timezone to model
- fix colision of revision id
- 1044085 - frontend: display time in user timezone
- [frontend] rebuild stuck task
- disable test on i386
- use experimental createrepo_c to get rid of lock on temp files
- [frontend] - do not throw ISE when build_id is malformed
- [tests] add test for BuildLogic.add
- [tests] add test for build resubmission
- [frontend] permission checking is done in BuildLogic.add
- [frontend] remove BuildLogic.new, use BL.add only
- [api] fix validation error handling
- [cli] fix initial_pkgs and repos not sent to backend
- [frontend] fix BuildsLogic.new not assigning copr to build
- [frontend] allow resubmitting builds from monitor
- [frontend] allow GET on repeat_build
- [frontend] 1050904 - monitor shows not submitted chroots
- [frontend] rename active_mock_chroots to active_chroots
- [frontend] rename MockChroot.chroot_name to .name
- [frontend] 1054474 - drop Copr.build_count nonsense
- [tests] fix https and repo generation
- [tests] return exit code from manage.py test
- 1054472 - Fix deleting multiple SRPMs
- [spec] tighten acl on copr-be.conf
- [backend] - add missing import
- 1054082 - general: encode to utf8 if err in mimetext
- [backend] lock log file before writing
- 1055594 - mockremote: always unquote pkg url
- 1054086 - change vendor tag
- mockremote: rawhide instead of $releasever in repos when in rawhide chroot
- 1055499 - do not replace version with $releasever on rawhide
- 1055119 - do not propagate https until it is properly signed
- fix spellings on chroot edit page
- 1054341 - be more verbose about allowed licenses
- 1054594 - temporary disable https in repo file

* Thu Jan 16 2014 Miroslav Suchý <msuchy@redhat.com> 1.24-1
- add BR python-markdown
- [fronted] don't add description to .repo files
- [spec] fix with_tests conditional
- add build deletion
- 1044158 - do not require fas username prior to login
- replace http with https in copr-cli and in generated repo file
- [cli] UX changes - explicitely state that pkgs is URL
- 1053142 - only build copr-cli on el6
- [frontend] correctly handle mangled chroot
- [frontend] do not traceback when user malform url
- [frontend] change default description and instructions to sound more
  dangerously
- 1052075 - do not set chroots on repeated build
- 1052071 - do not throw ISE when copr does not exist

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


