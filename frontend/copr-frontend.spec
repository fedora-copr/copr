%bcond_without check
%if 0%{?fedora} < 32
%bcond_without doc
%endif

# https://fedoraproject.org/wiki/Packaging:Guidelines#Packaging_of_Additional_RPM_Macros
%global macrosdir       %(d=%{_rpmconfigdir}/macros.d; [ -d $d ] || d=%{_sysconfdir}/rpm; echo $d)

%global copr_common_version 0.15.1.dev

# Please bump the %%flavor_guard version every-time some incompatible change
# happens (since the last release) in %%flavor_files set of files.  Those files
# are basically replaced by third-party flavor providers, and any file removal,
# addition, movement or change will make the third-party flavor non-working.  By
# changing the version we make the package explicitly incompatible and
# third-party flavor providers are notified they have to update their packages,
# too.
%global flavor_guard      %name-flavor = 5
%global flavor_provides   Provides: %flavor_guard
%global flavor_files_list %_datadir/copr/copr-flavor-filelist
%global flavor_generator  %_datadir/copr/coprs_frontend/generate_colorscheme
%global staticdir         %_datadir/copr/coprs_frontend/coprs/static
%global templatedir       %_datadir/copr/coprs_frontend/coprs/templates

%global flavor_files                            \
%staticdir/header_background.png                \
%staticdir/favicon.ico                          \
%staticdir/copr_logo.png                        \
%staticdir/css/copr-flavor.css                  \
%templatedir/additional_token_info.html         \
%templatedir/project_info.html                  \
%templatedir/quick_enable.html                  \
%templatedir/user_meta.html                     \
%templatedir/homepage_header.html               \
%templatedir/documentation_cards.html               \
%templatedir/welcome.html                       \
%templatedir/contact_us.html

%global devel_files \
%flavor_generator

%define exclude_files() %{lua:
   macro = "%" .. rpm.expand("%1") .. "_files"
   x = rpm.expand(macro)
   for line in string.gmatch(x, "([^\\n]+)") do
       print("%exclude " .. line .. "\\n")
   end
}

Name:       copr-frontend
Version:    1.193
Release:    1%{?dist}
Summary:    Frontend for Copr

License:    GPLv2+
URL:        https://github.com/fedora-copr/copr

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %name-%version.tar.gz

BuildArch:  noarch

BuildRequires: systemd
BuildRequires: util-linux

%if %{with doc}
BuildRequires: epydoc
BuildRequires: graphviz
%endif

BuildRequires: python3-devel

%if %{with check}
BuildRequires: fedora-messaging
BuildRequires: python3-alembic
BuildRequires: python3-anytree
BuildRequires: python3-click
BuildRequires: python3-CommonMark
BuildRequires: python3-blinker
BuildRequires: python3-beautifulsoup4
BuildRequires: python3-copr-common >= %copr_common_version
BuildRequires: python3-email-validator
BuildRequires: python3-dateutil
BuildRequires: python3-decorator
BuildRequires: python3-flask
BuildRequires: python3-templated-dictionary
%if 0%{?fedora} >= 31
BuildRequires: python3-flask-caching
%else
BuildRequires: python3-flask-cache
%endif
BuildRequires: python3-flask-openid
BuildRequires: python3-flask-restful
BuildRequires: python3-flask-sqlalchemy
BuildRequires: python3-flask-whooshee
BuildRequires: python3-flask-wtf
BuildRequires: python3-gobject
BuildRequires: python3-html2text
BuildRequires: python3-html5-parser
BuildRequires: python3-humanize
BuildRequires: python3-libmodulemd1 >= 1.7.0
BuildRequires: python3-lxml
BuildRequires: python3-markdown
BuildRequires: python3-marshmallow >= 2.0.0
BuildRequires: python3-munch
BuildRequires: python3-netaddr
BuildRequires: python3-openid-teams
BuildRequires: python3-pygments
BuildRequires: python3-pylibravatar
BuildRequires: python3-pytest
BuildRequires: python3-pytz
BuildRequires: python3-redis
BuildRequires: python3-requests
BuildRequires: python3-sphinx
BuildRequires: python3-sphinxcontrib-httpdomain
BuildRequires: python3-whoosh
BuildRequires: python3-wtforms >= 2.2.1
BuildRequires: python3-ldap
BuildRequires: python3-yaml
BuildRequires: redis
BuildRequires: modulemd-tools >= 0.6
%endif

Requires: crontabs
Requires: curl
Requires: httpd
Recommends: logrotate
Recommends: mod_auth_gssapi
Requires: redis

Requires: %flavor_guard

Requires: (copr-selinux if selinux-policy-targeted)
Requires: fedora-messaging
Requires: js-jquery
Requires: python3-anytree
Requires: python3-click
Requires: python3-CommonMark
Requires: python3-alembic
Requires: python3-blinker
Requires: python3-copr-common >= %copr_common_version
Requires: python3-dateutil
Requires: python3-email-validator
Requires: python3-flask
%if 0%{?fedora} >= 31
Requires: python3-flask-caching
%else
Requires: python3-flask-cache
%endif
Requires: python3-flask-openid
Requires: python3-flask-restful
Requires: python3-flask-sqlalchemy
Requires: python3-flask-whooshee
Requires: python3-flask-wtf
Requires: python3-flask-wtf
Requires: python3-gobject
Requires: python3-html2text
Requires: python3-html5-parser
Requires: python3-humanize
Requires: python3-libmodulemd1 >= 1.7.0
Requires: python3-lxml
Requires: python3-markdown
Requires: python3-marshmallow
Requires: python3-mod_wsgi
Requires: python3-munch
Requires: python3-netaddr
Requires: python3-openid-teams
Requires: python3-psycopg2
Requires: python3-pygments
Requires: python3-pylibravatar
Requires: python3-pytz
Requires: python3-redis
Requires: python3-requests
Requires: python3-templated-dictionary
Requires: python3-wtforms >= 2.2.1
Requires: python3-zmq
Requires: python3-ldap
Requires: xstatic-bootstrap-scss-common
Requires: xstatic-datatables-common
Requires: js-jquery-ui
Requires: xstatic-patternfly-common
Requires: modulemd-tools >= 0.6

Provides: bundled(bootstrap-combobox) = 1.1.6
Provides: bundled(bootstrap-select) = 1.5.4
Provides: bundled(bootstrap-treeview) = 1.0.1
Provides: bundled(c3) = 0.4.10
Provides: bundled(d3) = 3.5.0
Provides: bundled(datatables-colreorder) = 1.1.3
Provides: bundled(datatables-colvis) = 1.1.2
Provides: bundled(font-awesome) = 1.0.1
Provides: bundled(google-code-prettify) = 4.3.0

%description
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package contains frontend.


%if %{with doc}
%package doc
Summary:    Code documentation for COPR
Obsoletes:  copr-doc < 1.38

%description doc
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package include documentation for COPR code. Mostly useful for developers
only.
%endif


%package fedora
Summary: Template files for %{name}
Requires: %{name} = %{version}
%flavor_provides

%description fedora
Template files for %{name} (basically colors, logo, etc.).  This package is
designed to be replaced - build your replacement package against %{name}-devel
to produce compatible {name}-flavor package, then use man dnf.conf(5) 'priority'
option to prioritize your package against the default package we provide.


%package devel
Summary: Development files to build against %{name}

%description devel
Files which allow a build against %{name}, currently it's useful to build
custom %{name}-flavor package.


%prep
%setup -q


%build
%if %{with doc}
COPR_CONFIG=../../documentation/copr-documentation.conf \
  make -C documentation %{?_smp_mflags} python
%endif


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
install -d %{buildroot}%{_sysconfdir}/cron.daily
install -d %{buildroot}/%{_bindir}
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}%{_libexecdir}

install -p -m 755 conf/cron.hourly/copr-frontend* %{buildroot}%{_sysconfdir}/cron.hourly
install -p -m 755 conf/cron.daily/copr-frontend* %{buildroot}%{_sysconfdir}/cron.daily
install -p -m 755 coprs_frontend/run/copr_dump_db.sh %{buildroot}%{_libexecdir}

cp -a coprs_frontend/* %{buildroot}%{_datadir}/copr/coprs_frontend
rm -rf %{buildroot}%{_datadir}/copr/coprs_frontend/tests
sed -i "s/__RPM_BUILD_VERSION/%{version}-%{release}/" %{buildroot}%{_datadir}/copr/coprs_frontend/coprs/templates/layout.html

mv %{buildroot}%{_datadir}/copr/coprs_frontend/coprs.conf.example ./
mv %{buildroot}%{_datadir}/copr/coprs_frontend/config/* %{buildroot}%{_sysconfdir}/copr
rm %{buildroot}%{_datadir}/copr/coprs_frontend/CONTRIBUTION_GUIDELINES
touch %{buildroot}%{_sharedstatedir}/copr/data/copr.db

install -d %{buildroot}%{_var}/log/copr-frontend
install -d %{buildroot}%{_sysconfdir}/logrotate.d
cp -a conf/logrotate %{buildroot}%{_sysconfdir}/logrotate.d/%{name}
touch %{buildroot}%{_var}/log/copr-frontend/frontend.log

ln -fs /usr/share/copr/coprs_frontend/manage.py %{buildroot}/%{_bindir}/copr-frontend

mkdir -p %buildroot/$(dirname %flavor_files_list)
cat <<EOF > %buildroot%flavor_files_list
%flavor_files
EOF

mkdir -p %buildroot%macrosdir
cat <<EOF >%buildroot%macrosdir/macros.coprfrontend
%%copr_frontend_flavor_pkg \\
%flavor_provides \\
Requires: copr-frontend
%%copr_frontend_flavor_filelist   %flavor_files_list
%%copr_frontend_flavor_generator  %flavor_generator
%%copr_frontend_staticdir         %staticdir
%%copr_frontend_templatedir       %templatedir
%%copr_frontend_chroot_logodir    %%copr_frontend_staticdir/chroot_logodir
EOF

%py_byte_compile %{__python3} %{buildroot}%{_datadir}/copr/coprs_frontend/coprs
%py_byte_compile %{__python3} %{buildroot}%{_datadir}/copr/coprs_frontend/alembic
%py_byte_compile %{__python3} %{buildroot}%{_datadir}/copr/coprs_frontend/tests

%check
%if %{with check}
./run_tests.sh -vv --no-cov
%endif

%pre
getent group copr-fe >/dev/null || groupadd -r copr-fe
getent passwd copr-fe >/dev/null || \
useradd -r -g copr-fe -G copr-fe -d %{_datadir}/copr/coprs_frontend -s /bin/bash -c "COPR frontend user" copr-fe
usermod -L copr-fe


%post
/bin/systemctl condrestart httpd.service || :
%systemd_post fm-consumer@copr_messaging.service


%preun
%systemd_preun fm-consumer@copr_messaging.service


%postun
/bin/systemctl condrestart httpd.service || :
%systemd_postun_with_restart fm-consumer@copr_messaging.service


%files
%license LICENSE
%doc coprs.conf.example
%dir %{_datadir}/copr
%dir %{_sysconfdir}/copr
%dir %{_sharedstatedir}/copr
%{_datadir}/copr/coprs_frontend
%{_bindir}/copr-frontend

%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}

%defattr(-, copr-fe, copr-fe, -)
%dir %{_sharedstatedir}/copr/data
%dir %{_sharedstatedir}/copr/data/openid_store
%dir %{_sharedstatedir}/copr/data/whooshee
%dir %{_sharedstatedir}/copr/data/whooshee/copr_user_whoosheer
%dir %{_sharedstatedir}/copr/data/srpm_storage

%ghost %{_sharedstatedir}/copr/data/copr.db

%defattr(644, copr-fe, copr-fe, 755)
%dir %{_var}/log/copr-frontend
%ghost %{_var}/log/copr-frontend/*.log

%defattr(600, copr-fe, copr-fe, 700)
%config(noreplace)  %{_sysconfdir}/copr/copr.conf
%config(noreplace)  %{_sysconfdir}/copr/copr_devel.conf
%config(noreplace)  %{_sysconfdir}/copr/copr_unit_test.conf
%config(noreplace)  %{_sysconfdir}/copr/chroots.conf

%defattr(-, root, root, -)
%config %{_sysconfdir}/cron.hourly/copr-frontend
%config %{_sysconfdir}/cron.daily/copr-frontend
%config(noreplace) %{_sysconfdir}/cron.hourly/copr-frontend-optional
%config(noreplace) %{_sysconfdir}/cron.daily/copr-frontend-optional
%{_libexecdir}/copr_dump_db.sh
%exclude_files flavor
%exclude_files devel


%files fedora
%license LICENSE
%flavor_files


%files devel
%license LICENSE
%flavor_files_list
%devel_files
%macrosdir/*



%if %{with doc}
%files doc
%license LICENSE
%doc documentation/python-doc
%endif


%changelog
* Wed Nov 30 2022 Pavel Raiskup <praiskup@redhat.com> 1.193-1
- fix get-tasks traceback when repos are not set

* Sat Nov 26 2022 Jakub Kadlcik <frostyx@email.cz> 1.192-1
- allow arbitrary creation of :pr:<ID> directories
- custom repositories with custom webhook
- move to GitHub home page
- use shlex.quote instead of pipes.quote
- add route for a new distgit dispatcher
- expand repos for custom SRPM
- process external repos for custom build
- support LDAP groups for Kerberos users
- add version to the bitbucket webhook tag name
- loosen the rules of package matching in webhook tags
- add optional argument pkg_name to webhooks API
- no delay after large SRPM upload
- name the import log "import.log" in web-UI
- show import log to everyone, not just admin
- log webhook calls
- cache the queue sizes for one minute
- log manage.py commands

* Tue Sep 20 2022 Jakub Kadlcik <frostyx@email.cz> 1.191-1
- show timeout in the build detail page
- disable Edit button in the project settings when chroot unchecked
- fix FTBFS issues for F37/Rawhide
- match OS logos by their OS family
- show the batch ID (if assigned) in the build detail
- add link to /user/repositories/ on the user detail page
- stg frontend instance should link to stg FAS instance
- add page for exploring projects
- remove APIv2 code

* Tue Aug 16 2022 Jiri Kyjovsky <j1.kyjovsky@gmail.com> 1.190-1
- Create field for packit_forge_project when creating build

* Tue Aug 16 2022 Jiri Kyjovsky <j1.kyjovsky@gmail.com> 1.189-1
- check packit_forge_project option in build_options for builds
- add packit_forge_projects_allowed for Copr projects
- remove leading and trailing whitespace from StringField

* Tue Jul 26 2022 Jakub Kadlcik <frostyx@email.cz> 1.188-1
- Add support for pyp2spec generator
- Add API support for runtime_dependencies
- Runtime_dependencies may be separated by a newline
- Pagure-events: don't submit builds for disabled projects

* Tue Jun 21 2022 Jakub Kadlcik <frostyx@email.cz> 1.187-1
- Start logging important events
- Change logging formatter to show also flask.g.user
- APIv3 support for chroot_denylist
- Restrict the CoprDir names to <copr>:custom:<suffix>
- Don't require trailing slash in APIv3 /package/list
- Don't hide CoprDir buttons in Builds web-ui
- New command 'copr-frontend chroots-template'
- More understandable Pagure badges
- Detect ClientDisconnected errors

* Mon Apr 04 2022 Pavel Raiskup <praiskup@redhat.com> 1.186-1
- support for api_3 gssapi login
- the /pending-jobs/ is now a streamed page
- a bit more optimized /pending-jobs/ route
- web-UI: make sure that background builds are more visible
- build "is_background" info in the api_3 calls
- indicate low priority builds in status overview

* Fri Mar 18 2022 Pavel Raiskup <praiskup@redhat.com> 1.185-1
- added support for resetting fields in chroots over the API
- get-chroot - return modules as a list
- add a link to comps.xml documentation into the chroot edit form
- user-friendly error for devel stack(s) when there is a database problem
- optimize the SQL for the /pending/ routes a bit
- a new route /pending/all/ giving a rough stats
- cache the number of currently processed batches to speedup the overall web-UI
- speed-up the models.Batch related routes
- don't use redis as a middleman when updating hitcounter stats
- use standard backend auth for updating stats
- hitcounter: don't return 201 when there is an exception
- add API routes for editing module list in chroot

* Wed Feb 02 2022 Silvie Chlupova <schlupov@redhat.com> 1.184-1
- sort chroot-histogram graphs by number of builds
- use dist-git method for builds by default
- fix size of graphs on status page
- limit max number of packages per request
- paginate packages list in APIv3
- don't query all packages when empty list is specified
- webhook rebuilds are background jobs now
- re-enabled chroots should reset final_prunerepo_done
- fix import order reported by pylint
- print human-readable validation errors in APIv3
- basic build tagging
- use new Fedora chroot icon
- use official EPEL log for chroot icon
- PyLint fixes for create_db.py
- fix ./run_tests.sh script for coverage args
- don't insert+commit in create_after event
- build PyPI only for python3 by default
- describe advanced searching possibilities
- limit RubyGems and PyPI package names length
- Disable coverage analysis during RPM build
- 2029379 - workaround GitHub caching proxy
- drop duplicit "group" table join
- add "My Projects" button to the homepage
- api monitor page to contain pkg_version

* Wed Nov 10 2021 Silvie Chlupova <schlupov@redhat.com> 1.183-1
- ACR toggle - handle NO_VALUE specially too
- Fixup ACR handling
- "Rebuild All" form to respect chroot denylist
- "rebuild all packages" from successful builds
- Large project modification timeout fix
- Homepage redesign
- Speedup BuildChroot removals
- Add BuildChroot(s) to Build ASAP if package is known
- APIv3 /monitor route
- Single before_request hook
- Checkpoint measurement helpers
- Assure error_handler error is 500
- Handle CoprDir.get_by_copr consistently
- Search by attributes using the input value
- Print searched string with attributes
- Add dropdown with hints for searching
- Support searching by attributes and improve searching overall
- Openid,login by email: guide user, don't do infinite loop
- Conscious language (group blacklist -> denylist)
- Conscious language (chroot blacklist -> denylist)
- Change prompt from $ to #> in Quick Enable box
- Accept admin permissions for Copr build
- Explain what fedora-review project is

* Fri Oct 01 2021 Pavel Raiskup <praiskup@redhat.com> 1.182-1
- fixup SubqueryPaginator for older sqlalchemy versions

* Thu Sep 30 2021 Silvie Chlupova 1.181-1
- frontend: better not found message for not existing chroot
- frontend: avoid additional query for main_dir.full_name
- frontend: add index for combination of build.id and build.copr_id
- frontend: move the subquery hack into paginator
- frontend: speedup for listing builds via APIv3
- frontend: add a warning about the server-side pagination
- frontend: web-ui: paginate monitor page for more than 1000 packages
- backend: don't unnecessarily split the web-ui monitor route
- frontend: web-ui: sync package list with build list
- frontend: web-ui: server-side pagination for too-many-packages
- frontend: web-ui: server-side pagination for too-many-builds
- frontend: speedup /<owner>/<project>/builds/ route
- frontend: log pending build records only when debugging
- frontend: drop LegacyApiError exception
- frontend: remove all APIv1 code
- Add API entrypoint for regenerating repos
- frontend: fix rawhide_to_release/brach_fedora commands

* Wed Aug 25 2021 Pavel Raiskup <praiskup@redhat.com> 1.180-1
- use the same repofile for all Fedora versions including Rawhide
- don't traceback for "module exists" error
- fixup logging of info messages
- don't depend on python-six, drop __future__ imports
- move package non-denylisted chroots to general information
- show more of general package information on package detail page
- update main.ini and rpkg.conf.j2 for rpkg 3.0 compatibility
- make template caching configurable
- log basic request information for each traceback
- do not cache last build badge
- drop user proxy concept, we don't use it
- generate webhook secrets using APIv3

* Tue Jun 15 2021 Pavel Raiskup <praiskup@redhat.com> 1.179-1
- add support for optional namespaces in DistGit instances
- add a "storage statistics" link to footer
- fix the copr logo so it contains updated "fedora" font
- index the CoprChroot.deleted field to speedup API/UI
- a new admin command for prolonging unnoticed chroots
- properly notify all not-deleted chroots
- storage waste - drop upload temporary directories even upon source failure
- automatically request PR CoprDirs removal using a new action type
- colorize CoprDir-buttons on builds page, notifying users which of them will be removed soon
- fix build-listing for copr-dirs, show all builds by default again
- forked source builds now have forked source_status, too
- fixed the comps file hyperlink in web-UI form
- packaging - don't install test files (not used at runtime)
- allow user to disable generating appstream metadata (admin action is no longer needed)
- provide ENVRA build results via APIv3 (for particular build ID)
- review.txt link is now shown only for proper chroots
- add a logo for the OpenMandriva chroots
- the default value for MockChroot.comment should be none
- pruner: allow pruning also the finalized chroots
- invent a new FE-BE API version constant, guarding against incompatible FE/BE installations
- a new knob for turning a profiler on (devel setup)
- newly we show two latest blog post articles

* Fri Apr 30 2021 Jakub Kadlcik <frostyx@email.cz> 1.178-1
- frontend: oops, forgot to change these two instances
- frontend: show deletion tooltip in project overview

* Fri Apr 30 2021 Pavel Raiskup <praiskup@redhat.com> 1.177-1
- fix chroot disabling in project settings
- not display EOL warning for per-project disabled chroots

* Tue Apr 27 2021 Jakub Kadlcik <frostyx@email.cz> 1.176-1
- frontend: fix tests that fail in Fedora Rawhide chroots
- frontend: create project for Fedora Review
- frontend: memory_analyzer route module
- frontend: fix unrelated pylint warnings
- frontend: use correct auto_prune default when creating via API
- frontend: better test the branch-fedora command
- frontend: print forking stats for rawhide-to-release
- frontend: rawhide-to-release fix for deactivated chroots
- frontend: clone all CoprChroot attributes when forking
- frontend: simplified Build.state logic, and better log
- frontend: avoid NULLed source_status
- frontend: don't create builds if there are no active chroots
- frontend: hide deactivated chroots in the project overview
- frontend: traceback for outdated-chroots flash message
- frontend: make the [modified] chroot clickable
- frontend: fix Jinja traceback on nulled buildroot_pkgs
- frontend: catch tracebacks when rendering invalid modules
- frontend: update FAS links to use the new site
- frontend: fix unrelated pylint warnings
- frontend: introduce ChrootDeletionStatus
- frontend: delete data for unclicked chroots after few days
- frontend: assure unique Copr name for group/user in DB
- frontend: test that we can set these options via API
- frontend: drop an unused pagure_events.py knob
- GitLab moved their webhook settings to a different page.
- frontend: fix createrepo scope for chroot enable
- frontend: fix already defined method name
- frontend: add base form for creating and modifying projects
- frontend: move tests to proper class
- frontend: explain what actions are
- frontend: use Builds instead of Tasks in stats/
- backend, frontend, keygen, distgit: keep cca 3 months of logs
- frontend: test API for 'copr modify'
- fronted: stats - sort chroots by name

* Tue Mar 16 2021 Pavel Raiskup <praiskup@redhat.com> 1.175-1
- preparations for the centos-stream-8 rename
- support per-build --enable-net
- a lot of caching implemented to support flawless build-batches
- fix: don't schedule blocked BuildChroots
- bettter preloaded /pending-jobs/ queries
- the /backend/pending-tasks/ json minimized
- better identify the build submitter from pagure events
- stop deleting unclicked CoprChroots
- exchange xstatitc-jquery-ui-common for js-jquery-ui
- rhbz#1937217, filter HTML tags from description and instructions
- allow underscore in blacklisting chroot regexp
- optionally run fedora-review after build
- respect DELETE_EOL_CHROOTS_AFTER constant
- don't show repo files expired chroots
- add --comment option for 'copr-frontend create-chroot' command
- chroot fields in forms reworked

* Thu Jan 21 2021 Pavel Raiskup <praiskup@redhat.com> 1.174-1
- fix error 500 during build resubmit in Web-UI

* Wed Jan 20 2021 Pavel Raiskup <praiskup@redhat.com> 1.173-1
- temporarily revert one patch breaking 'copr modify' command

* Wed Jan 20 2021 Pavel Raiskup <praiskup@redhat.com> 1.172-1
- reworked chroots fields in copr/build forms
- do not fork EOLed/disabled chroots
- allow disabling modules in the buildroot
- rename button from Update to Request in permission form
- allow excluding chroots when submitting builds
- delete ReviewedOutdatedChroot rows on cascade
- disable gpgcheck for external runtime dependencies
- generate build_chroots for resubmitted SRPM-upload builds
- drop dependencies on orphaned and useless javascript packages
- allow setting isolation option per chroot
- depend on python3-email-validator
- allow project admins to edit chroots
- allow overriding the api token instructions downstream
- drop delete_after tag for re-activated EOLed chroot
- sync delete_after_timestamp for all EOLed copr_chroots
- support modulemd v2
- keep showing the link to EOLed repo files in copr project
- allow enabling not-yet-deleted but only eoled chroots

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 1.171-1
- re-process killed SRPM tasks
- backward compat APIv3 build-chroot fix
- copr homepage/contact empty string converted to None
- use URL path parameter (if there is such) instead of failing
- fix custom webhook for binary payload
- added new mock --isolation option in Copr
- don't allow prolonging already expired chroots
- try-except block for github webhook without clone_url
- deduplicate APIv3 build-chroot parameters
- don't traceback when the build ID larger than integer
- allow searching builds by build ID
- fix email recipient for permissions update

* Mon Nov 09 2020 Jakub Kadlcik <frostyx@email.cz> 1.170-1
- frontend: hide buttons in repositories pages for non-admins
- frontend: fix User.copr_permission relationship
- frontend: de-dup the rendering html code for repositories
- frontend: sync flash about EOL repos with the listing indent
- frontend, python: we cannot order chroots by name
- frontend: show a warning that user should visit their EOL repositories page
- frontend: add EOL repositories page for user (in opposite to project)
- frontend: not access flask.g.user, user parameter instead
- frontend: put the "running/starting/..." text to breadcrumb
- frontend: silence cyclic-import warnings
- cli, frontend: custom build batches
- frontend: silence warnings from confused PyLint
- frontend: de-duplicate forms
- frontend: fix canceling builds
- frontend: document the attributes related to EOLed chroots
- frontend: fix APIv3 ordering
- frontend: test: adding tests for canceling builds
- frontend: don't set ended_on for canceled builds
- frontend: don't re-set Build.package value
- frontend: assign package ASAP with rebuilds
- frontend: test chroot-edit 403 and form errors
- frontend: fix-up the CoprChroot form rendering
- frontend: de-duplicate work with build form
- frontend: merge two methods which were split needlessly
- frontend: short-cut the loop in build_config chroot search
- frontend, cli, python, rpmbuild: better bootstrap config
- beaker-tests, cli, frontend, python, rpmbuild: add option to config bootstrap
- frontend: fix the monitor page
- frontend: exception handlers fix once more
- Revert "frontend: fix exception tests for F31"
- frontend: redirect to URLs with trailing slashes
- all: run pytest with -vv in package build
- cli: fix timeout option to allow change timeout for build
- frontend: reduce the timeout to 5 hours
- frontend: input field for setting timeout for builds
- frontend: remove setting memory requirements
- frontend: access chroots more safely to avoid KeyError
- frontend: don't mark ELN as fedora latest version
- frontend: use "source build" collocation, not "srpm build"
- frontend: don't duplicate enums.BuildSourceEnum
- common, cli, python, rpmbuild, frontend, backend: DistGit source method
- frontend: nicer message in package name validator
- frontend: nicer web-UI error message on missing default source method
- frontend: catch NoPackageSourceException in apiv3 on rebuild
- frontend: move error handlers to the same file
- frontend: fix exception tests for F31
- frontend: improve APIv3 exception handling for better messages
- frontend: fix custom form errors also for CoprFormFactory and
  CreateModuleForm
- frontend: make sure user cannot pin projects that he doesn't have permissions
  to
- frontend: fix PinnedCoprsForm validation
- frontend: count srpm builds in statistics
- frontend: allow . and disallow : in package name
- frontend: allow '+' symbol in package name
- frontend: enable coverage for ./commands
- frontend: silence pylint issues
- frontend: fix testsuite stderr warnings
- frontend: test branch-fedora command
- frontend: fix rawhide-to-release to inherit comment
- frontend: fix forking into an existing project

* Tue Aug 18 2020 Pavel Raiskup <praiskup@redhat.com> 1.169-1
- fix rawhide-to-release command
- simplify API and UI error handlers

* Tue Aug 11 2020 Pavel Raiskup <praiskup@redhat.com> 1.168-1
- get-package API to support with_latest* args

* Mon Aug 10 2020 Pavel Raiskup <praiskup@redhat.com> 1.167-1
- catch OSError when srpm_storage is full
- drop the duplicate jquery-ui.min.js reference from html layout
- move to jQuery 3
- drop redundant dependency on python3-flask-cache
- more understandable permissions error messages
- allow users to upvote or downvote projects
- more understandable build state descriptions in web UI
- add new overview tab showing starting builds
- fix avatars for copr groups
- validate package name input
- more effective query of packages with their latest builds
- return user-friedly error message for non-admin exceptions
- admins can now create projects for others via API
- fix up libmodulemd dependency

* Thu Jun 18 2020 Pavel Raiskup <praiskup@redhat.com> 1.166-1
- show _all_ build-delete checkboxes when javascript is on
- don't submit builds when there are no CoprChroot(s) assigned
- make pending-jobs faster again
- allow canceling also "starting" builds
- don't traceback on invalid cancel requests
- build.source_status None accepted for old builds
- don't raise 500 on misconfigured build-time repos
- print source build.log in starting state

* Tue Jun 09 2020 Pavel Raiskup <praiskup@redhat.com> 1.165-1
- enable cov by default in testsute
- more obvious links to the live logs
- return a user friendly error when modulemd is not ok
- basic build task priority implemented
- droped the reschedule-all builds idiom
- new build cancel implementation
- WorkerManager used for builds, too
- enable deleting multiple builds from cli
- drop RequestCannotBeExecuted and BuildInProgressException
- re-assign BuildChroots to re-enabled CoprChroot
- not finished build_chroots to disallow copr_chroot removal
- models: link BuildChroot(s) with corresponding CoprChroot(s)
- fix repo generation for modules with dash in their name
- added support for project runtime dependencies
- return user friendly error when build chroot was not found
- large sync of model with migrations
- require the newest version of copr-common
- fix for the new werkzeug in rawhide
- use flask caching instead of flask cache
- prioritize initial createrepo action, set lower priority for some actions
- make ActionsLogic.send_* methods to return the generated action
- minimalize the transfered amount of action information to BE
- disable group build delete checkboxes if js is not enabled
- provide status information for build chroots in APIv3
- fix application context error for add-user command
- move some constants to copr.conf so we can tweak them
- disallow creating modules without any packages
- don't show builds table when there are none of them
- fix pagure-events so it submits correct packages

* Mon Feb 24 2020 Pavel Raiskup <praiskup@redhat.com> 1.164-1
- rawhide-to-release should create the chroots deactivated
- new rawhide-to-release --retry-forked option
- allow repeated run of 'rawhide-to-release'
- bugfix rawihde to release
- raise timeout limit for builds to 24h

* Wed Feb 05 2020 Pavel Raiskup <praiskup@redhat.com> 1.163-1
- don't generate 'modules' in build-job unnecessarily

* Wed Feb 05 2020 Pavel Raiskup <praiskup@redhat.com> 1.162-1
- module enable option for chroot settings
- delete action fix for incomplete builds
- custom webhook to accept utf-8 hook data
- users can now pick against what dist-git to build module
- fix delete-chroot e-mail notification
- change panel order in 'Rebuild all packages' page

* Thu Jan 16 2020 Pavel Raiskup <praiskup@redhat.com> 1.161-1
- memory optimize /packages/ and /builds/ routes

* Wed Jan 15 2020 Tomas Hrnciar <thrnciar@redhat.com> 1.160-1
- don't cache some.repo with some.repo?arch=X
- put cost=1100 to multilib repo
- put arch into multilib repo name
- manage.py: propagate return values to cmdline
- backend: fix multi-build delete
- add migration to drop PG-only functions
- cache Build.status at runtime
- faster <project>/builds query
- faster <project>/packages query
- check alembic scripts automatically by run_tests.sh
- adds 24h and 90d graphs for actions
- sort recent tasks after caching again
- don't traceback for invalid copr:// repos
- removes unnecessary imports of flask-script
- cache repository contents
- packages does not need to be online

* Wed Dec 11 2019 Pavel Raiskup <praiskup@redhat.com> 1.159-1
- cache the recent task queries
- simplify log level configuration
- API route to list all available chroots

* Fri Dec 06 2019 Pavel Raiskup <praiskup@redhat.com> 1.158-1
- revert wrong optimization in createrepo
- don't assume all additional repos are copr://

* Wed Dec 04 2019 Pavel Raiskup <praiskup@redhat.com> 1.157-1
- createrepo action for pull-request copr-dirs
- traceback fix for copr.add form
- provide alias commands with underscores in ./manage.py

* Wed Dec 04 2019 Pavel Raiskup <praiskup@redhat.com> 1.156-1
- display chroot comments on create project page
- add info to UI that build was resubmitted from another build
- manage.py ported out from flask-script third party module
- support for module_hotfixes
- fixed non-working SRPM builder-live.log.gz link
- epydoc retired in new fedoras, build-condition added
- forking: correct builds in chroots are now forked (issues 1010 and 1012)
- `uses_devel_repo' is now part of task info
- centos chroot logo added
- correctly configure and depend on logrotate
- fix apiv2 for validation errors (issue 1061)
- pagure-events ported from fedmsg to fedora-messaging
- display project ID in UI

* Tue Oct 08 2019 Pavel Raiskup <praiskup@redhat.com> 1.155-1
- frontend: api_2: ignore validation problems mm_serialize_one
- frontend: fix one more traceback in builder-live.log link

* Thu Oct 03 2019 Pavel Raiskup <praiskup@redhat.com> 1.154-1
- api compat fixes for marshmallow 3+
- more reliable BE->FE communication (#1021)
- allow rhelbeta-X/epel-X chroot co-existence (#1035)
- new url routes for parallel handling of actions by backend (#1007)
- user can pin all projects he can build in (#1016)
- project forking fixes
- fix slow rawhide_to_release command (#989)
- support multilib projects (#938)
- status chroot build icon now links to live log (#990)
- admin: dump whooshee version when updating indexes (#946)
- admin: ability to documment chroot (#853)
- admin: add manage.py branch_fedora command (#955)

* Wed Sep 04 2019 Dominik Turecek <dturecek@redhat.com> 1.153-1
- admin permission check in 'can_build_in()' (issue#970)
- better link to builder-live.log (issue#941)
- hide unlisted projects from homepage in RSS
- build srpm first
- fixes traceback with invalid chroot name (issue#810)

* Wed Aug 28 2019 Dominik Turecek <dturecek@redhat.com> 1.152-1
- fix public dump for login to work after re-import (issue#912)
- optimize frontpage and fix recent builds page (issue#937)
- batch delete builds into a single action (issue#688)
- optimize /backend/pending-jobs/ json rendering
- monitor page should not show builds from PR (issue#839)
- unify "repos" field description for chroot/project
- add support for length of pending/running tables (issue#709)
- fix traceback on build delete (issue#822)
- remove records limit for running/pending/importing stats pages (issue#893)
- fix error with sorting pending/running table by project name (issue#901)
- fix GDPR user data deletion (issues#889,#890)
- adding better time representation for build detail (issue#860)
- un-pin projects when deleting them (issue#895)
- fix module state and show it on the module detail page (issue#607)

* Mon Jul 29 2019 Pavel Raiskup <praiskup@redhat.com> 1.151-1
- run createrepo immediately, don't wait for first build (issue#833)
- added pinned-projects feature (issue#495)
- fix/customize sorting in running/pending/importing tab (issue#808)
- removed (so far broken) group avatar from group projects (issue#806)
- added helper for daily db dumps (pr#783)
- better working with build statuses internally (issue#668)
- modular builds now respect the module platform (issue#606)
- sandbox builds not only per user, but also per submitter and project
- better submitter identification for webhook builds
- repo ID in `dnf copr enable` repo files contain frontend hostname
- hide "delete all builds" checkboxes for logged-out visitors (issue#577)
- nicer API error output for ActionInProgressException
- allow individuals to ask permissions for group projects (issue#778)
- api pagination ordering fix (rhbz#1717506)
- api /project/list now doesn't include group projects
- disallow ex-members to build in projects (issue#848)
- don't traceback when "add-group" form contains errors (issue#847)
- allow group admins to delete all projects in the group (issue#779)
- fix a lot of deprecation warning during build
- really delete builds in temporary projects, no only the DB entry
- show only forks in web-UI that are not yet deleted
- added link to RSS feed into site navigation
- admin: add command to delete orphaned builds and packages
- admin: us to create temporary aliases for chroots
- admin: allow copr admins to edit Package entries

* Tue May 21 2019 Pavel Raiskup <praiskup@redhat.com> 1.150-1
- fix the script for prolonged outdated chroots
- add RHEL 8 (rhelbeta) chroot logo
- correctly describe "Create repositories manually"
- remove unused module_md_name and module_md_zlib columns
- sort package (build)requires
- use humanize in time_ago(); fix #724
- automatize outdated chroots notifications and deletion
- notify outdated chroots with 80 days interval
- don't unselect inactive chroots in project edit; fix #712
- print soon-to-remove outdated chroots in red; see #593
- cron: call 'clean_expired_projects' correctly
- traceback when forked_from project deleted
- disable "expire now" button when chroot is already expired
- NameError: name 'unicode' is not defined
- require wtforms version with render_kw

* Wed Apr 24 2019 Jakub Kadlčík <frostyx@email.cz> 1.149-1
- fix finished status for SRPM builds, hopefully last time
- log handled 500 errors
- fix a failing test
- expect the correct status code for project deletion failure
- webhook triggers expect int:copr_id
- fix shebang in daily cron job
- remove a redundant condition for outdated chroots
- allow user to remove outdated chroot; fix #624
- sort outdated chroots by name; fix #593
- pagure-events: send keep-alive tcp packets
- replace cron configuration automatically
- respect module buildorder by setting dependencies among batches
- add mechanism to block build batch until other one finishes
- build is not finished when not even SRPM is finished
- fix WTForms deprecation warning
- fix Flask invalid cookie warning
- fix YAMLLoadWarning deprecation warning
- fix FlaskWTForms deprecation warning
- pagure-events: each commit in push/PR should trigger build
- webhooks: each commit in push should trigger build
- make clean_old_builds query join() explicit
- link to correct API documentation
- fixup test fixtures for Rawhide
- add CLI for permissions
- new --max-builds option
- move "Other options" to separate panel
- support temporary projects
- print friendly error on http when https is enforced
- Merge #647 `[frontend] make 'alembic revision --autogenerate' pylint-clean`
- *_private migration is irreversible
- don't ignore constraints when moving data to *_private
- simplify *_private tables
- de-duplicate *_private ids
- add CoprPrivate to join
- fix migration sequence by putting private table migrations on top
- remove private columns from user and copr
- private tables for user and copr
- make 'alembic revision --autogenerate' pylint-clean
- pagure-events: accept [copr-build] key in PR message
- pagure-events: allow duplicate builds
- better parse Pagure's PR messages
- fix Pagure-triggered Package builds
- linter for alembic revisions
- repaired import in builds_logic Closes #644
- increase the build timeout limit because of chromium
- reset config changes after each test method
- UI: say "SRPM log" instead of "Import log"
- disallow root to execute ./manage.py
- don't display url to dist-git logs for non-admin users
- fix batch build delete in group projects; see #575
- fix exception when multiple sources are generating graph data
- support ?priority=x for non copr:// repo
- Redis.setex swapped arguments in v3+
- go to builds page after submitting a custom method build
- fix module builds table
- test real-world module buildorder, see #599
- enforce https for outdated chroots emails
- pass queue_sizes also to the graph page
- display badges in task queue tabs, see #552
-[python] avoid 'collections.abc' warnings

* Fri Mar 15 2019 Jakub Kadlčík <frostyx@email.cz> 1.148-1
- [frontend] add missing spaces
- [frontend] set reply-to header to our emails
- [frontend] sort chroots in email by project name
- [frontend] don't get chroots from deleted projects
- [frontend][python] handle timeout errors
- [frontend] return the correct status for SRPM fail (fix #513)
- Added rss feed from all copr's projects to /rss/
- [frontend] show packages with no builds as 'not built yet'
- [cli][frontend] fix copr-cli downloading parent directory for cancelled builds
- [frontend][backend] make copr_prune_results skip already pruned outdated
chroots

* Mon Mar 11 2019 Jakub Kadlčík <frostyx@email.cz> 1.147-1
- [frontend] don't forget to commit in 'manage.py alter_chroot'
- [frontend] new 'db_session_scope' idiom
- [frontend] remove leftover old_status after PR#562
- [frontend] rework error handlers to fix #531
- [frontend] remove migration-report page
- [frontend] remove old_status column from package table
- [frontend] mention Copr in mail subject
- [frontend][backend] require libmodulemd in at least 1.7.0
- [frontend] build batch deletion by xhr

* Thu Feb 14 2019 Jakub Kadlčík <frostyx@email.cz> 1.146-1
- [frontend] require copr-common greater than 0.4 version

* Mon Feb 11 2019 Jakub Kadlčík <frostyx@email.cz> 1.145-1
- Don't let dev instance notify all users
- Don't allow to send notification for empty chroots
- Move splitFilename function to the copr-common package
- Fix storing the custom script parameters
- Set webhook_rebuild even in APIv3
- Set the disable_createrepo when creating the project via APIv3
- Stick with the old repo_id format until F28 is supported
- Add index build(canceled, is_background, source_status, id)
- Couple of bugfixes for wrong variables and properties

* Tue Jan 15 2019 Miroslav Suchý <msuchy@redhat.com> 1.144-1
- add db indexes

* Mon Jan 14 2019 Miroslav Suchý <msuchy@redhat.com> 1.143-1
- add build_copr_id index and build_chroot(status, started_on)
- fix path to bash
- removing executable bit from api_general.py

* Fri Jan 11 2019 Miroslav Suchý <msuchy@redhat.com> 1.142-1
- remove data from outdated chroots
- fix modulemd import on F29

* Thu Jan 10 2019 Miroslav Suchý <msuchy@redhat.com> 1.141-1
- order builds already by SQL
- add support for copr dir to copr-cli
- Show markdown code for status badge
- add pending action count
- add get_admins command to manage.py
- notifications for outdated chroots
- show project forks
- don't include port in repofile ID
- Remove spaces around slash in owner/project header
- Make pagure-events service load-balanceable
- Fix `copr-cli mock-config` after switching to APIv3 by preprocessing repos on
frontend
- add data migration to remove build.results column
- add try-except block to rollback session properly if an error ocurrs
- move inline style to css
- let mock rootdir generation on clients
- rename repos 'url' attribute to 'baseurl'
- provide repo_id in project chroot build config
- refactor repo_id property
- dont remove additional_repos list
- add possibility to query all projects (RhBug: 1130166)
- don't show empty copr dirs (see #447)
- warn maintainer when working in foreign project
- Allow per-package chroot-blacklisting by wildcard patterns
- add possibility to notify just selected users
- send only one email per user
- preprocess repo URLs on frontend
- move 'Build only for' down into 'Default Build Source'
- list chroots the package is built for
- render "Generic form"
- drop "downloading" state
- allow blacklisting packages from chroots

* Fri Oct 19 2018 Miroslav Suchý <msuchy@redhat.com> 1.140-1
- /usr/bin/env python3 -> /usr/bin/python3
- fix SELinux
- use cached data for small graph of usage
- add quick_enable.html flavor template
- sync style-overwrite.css with generate_colorscheme
- new config REPO_NO_SSL
- split style-overwrite.css into two parts
- change repo ID format
- Start using a code from copr_common
- refactor mailing code
- use git_dir_archive instead of git_dir_pack
- 1628399 - che/llvm and che/mesa do not show up when searching
  for the search terms
- migrate from deprecated python3-modulemd to libmodulemd
- do not allow other users to edit your packages
- fix operation of alembic-3 commands (e.g. alembic-3 history)
- pg#251 Make it possible for user to select pyp2rpm template
- don't hardcode OpenID provider (#374)
- 1622513 - require python3-requests
- pg#251 Make it possible for user to select pyp2rpm template
- change repo ID format to copr:<hub>:<user>:<project>

* Fri Aug 24 2018 clime <clime@redhat.com> 1.139-1
- add proper access check for integrations page

* Thu Aug 23 2018 clime <clime@redhat.com> 1.138-1
- fix bug that project non-owner can generate new webhook secret

* Thu Aug 23 2018 clime <clime@redhat.com> 1.137-1
- generate new webhook secret functionality in copr-cli
- fix forking not to duplicate information that should not be
duplicated
- apiv3: construct dict with project data before deleting it
- don't set source_build_method for unset packages
- Change of the default setting of follow_fedora_branching
- #349 Do not fork package auto-rebuild information
- fix rawhide_to_release after b15e4504c
- packaging: Python 2/3, RHEL/Fedora fixes
- fix custom package webhooks

* Mon Aug 06 2018 clime <clime@redhat.com> 1.136-1
- None task protection
- apiv3
- pagure integration
- manual byte-code compilation

* Fri Jul 20 2018 clime <clime@redhat.com> 1.135-1
- fix tests under ppc64le

* Fri Jul 20 2018 clime <clime@redhat.com> 1.134-1
- fix #320 copr frontend check: remove arch specific condition
- drop initscripts Require
- fix #322 frontend: scriptlet stderr pollution
- contact_us column added into footer
- graphs optimizied
- note contact info for GDPR data dump
- remove logstash configuration from .spec

* Tue Jun 19 2018 clime <clime@redhat.com> 1.133-1
- separate version of the copr-frontend-flavor provide
- ignore errors on "condrestart" foreign services
- rename user_info flavor template file to user_meta
- GDPR compliance
- drop 'passwd' dependency

* Fri May 18 2018 clime <clime@redhat.com> 1.132-1
- add --with/--without rpmbuild options for build chroot
- use "$releasever" in repo base URL for opensuse-leap and mageia chroots
- openSUSE chroot support
- fix #291 forks are incomplete
- fix rpm download counters for group projects
- #290 auto-rebuilds are being spawned on commits to some other projects
- preparation for opensuse-leap-15.0-x86_64

* Mon Apr 30 2018 clime <clime@redhat.com> 1.131-1
- fix build on pagure commit script to listen only to pagure fedmsgs
- use rsplit for chroot splitting to get os, version, arch triplet

* Thu Apr 26 2018 Dominik Turecek <dturecek@redhat.com> 1.130-1
- add pending tasks to graphs
- rpkg deployment into COPR - containers + releng continuation
- fix flash messages not disappearing after page reload
- change flash messages for deleted/cancelled builds
- remove dangling symlinks after 00b6073
- unbundle static files
- some javascript assets are not placed under component folder
- remove redundatant stuff in complex tests
- remove unneeded basenames
- fix #269, #273, #221 and #268
- fix  #275 web-ui: last build name shows "None"
- api /build_status/ to not require login
- add status_icon for build_id
- change login welcome message to success message
- redirect to builds table after rebuild
- custom method: move the script filter into form
- fix graphics issues after adding xstatic-patternfly-common
- give project names more space

* Wed Feb 28 2018 clime <clime@redhat.com> 1.129-1
- several tweaks for graphs of utilization
- fix copr_update after user and group routes merge
- custom build: single-line textarea placeholder
- vanish '\r\n' in custom script
- fix filter has no len() error
- make the news box optional
- fix group listing
- remove workaround from copr_url macro
- merge regular and group views

* Fri Feb 23 2018 clime <clime@redhat.com> 1.128-1
- fix counting stat logic
- use end_commit when building by copr-fedmsg-listener
- update service file for copr-fedmsg-listener to use python3
- add forked description
- fix init_db
- fix unittests (zlib.compress expects bytes, not str)
- task queue info cleanup
- fix initial build.source_status and chroot statuses for auto-
  rebuilds
- remove some old python scripts
- enable chroot for every project that follows branching
- fix copr_url() template macro for custom method
- remove Group tag

* Mon Feb 19 2018 clime <clime@redhat.com> 1.127-1
- Shebangs cleanup
- new custom source method
- fix search page error due to missing graph data

* Sun Feb 18 2018 clime <clime@redhat.com> 1.126-1
- add fetch_sources_only: True into build task defintion
- add graphs of utilization
- option to give COPR repository bigger priority (see #97)
- grammar: s/duplicate a backend data/duplicate backend data/
- Trailing ".git" is ignored when matching clone URL, so is unnecessary.
- fix frontend by disabling doc generation
- Accept webhooks from bitbucket.org.
- Expand docs on how to find the correct Pagure hook setting.
- fix typos
- fixed status_to_order, order_to_status functions, added waiting
  icon
- add indeces for faster build selection
- add source_status field for Builds
- implement the module buildorder logic
- krb5: last iteritems()->items()
- have .repo on the end of module repofile URL
- set the gpg properties for module repo
- Byecompile files in %%{_datadir} with python3
- pg#191 When auto-rebuilding from push event, use a head commit
  hash
- move run3_tests.sh into run_tests.sh, polish .spec a bit
- fix run scripts under python3
- frontend now presents the whole job queue state to
  backend
- opt rename SRPM_STORAGE_DIR to STORAGE_DIR
- new generic web-hook
- when passing URL with path, expect it in result; see ad9c3b4cc
- remove outdated tests, see 3f62873
- add index to build module_id
- copy only module builds into the repo directory
- generate the module NSV rather than asking for it
- fix condition that all module packages were successfully built
- remove outdated modularity code
- fix baseurl for module repofile
- build modules in all enabled chroots
- implement submitting modules via URL
- set default values for optional modulemd params
- change module version to bigint
- always have a known state of a module
- have unique module nsv per project
- build a module without using MBS
- require to specify project when building module
- add build to module relation
- limit spec to python3 deps and switch application and scripts to
  python3
- pg#188 COPR webhook doesn't work with branches
- python3 conversion

* Mon Dec 18 2017 Dominik Turecek <dturecek@redhat.com> 1.125-1
- add support for src.fp.o in build_on_pagure_commit.py
- fix source type description
- fix make-srpm anchor link
- provide default for source_json_dict in scm migration
- fix committish filter condition for auto-rebuilds
- fix SCM migrations not to use models that might be newer than db
- always use ref from the push/tag event for package auto-rebuild
- rather suggest dnf-modularity-stable repo
- update the info how to install a module
- fix code block spacing
- fix scm unification migrations for mock-scm
- show most recent post from our blog

* Thu Nov 09 2017 clime <clime@redhat.com> 1.124-1
- fix build_on_pagure_commit.py
- optimize check_for_anitya_version_updates
- Bug 1508888 - Webhook triggered from GitHub does not start the
  build
- allow to set use_bootstrap_container via API
- fix job stucking provisionally
- add PoC scripts for fedora-ci

* Wed Oct 18 2017 clime <clime@redhat.com> 1.123-1
- also set srpm_url when --initial-pkgs is used when creating new
  project
- for tag webhook events, rebuild the package on the specified tag
- check for pagure hostname in pagure auto-rebuilding script
- fix for fatal error when accessing old upload builds that do not
  contain 'url' key in source_json
- unify SCM source types
- deprecate tito and mock-scm methods
- add index on package(webhook_rebuild, source_type) and
  copr(copr_webhook_secret)
- update docs for requests/flask interaction

* Wed Sep 27 2017 clime <clime@redhat.com> 1.122-1
- remove unneeded yum dep

* Tue Sep 26 2017 clime <clime@redhat.com> 1.121-1
- fix generate_repo_url method not to edit mock_chroot object
  attributes
- spec cleanup in regard to python-flask-whooshee
- fix rpm download stats collection
- fix 'Repo Downloads' counter

* Fri Sep 15 2017 clime <clime@redhat.com> 1.120-1
- fix build stucking with srpm url/upload resubmitted builds
- .spec cleanup
- move DEFER_BUILD_SECONDS to config values and set default to 80
- show backend log for srpm builds
- fix url to import log
- Bug 1431035 - coprs should check credentials before uploading
  source rpm

* Thu Sep 07 2017 clime <clime@redhat.com> 1.119-1
- add dist_git_clone_url property of package and use it on /backend
- #68 Building SRPMs on builder
- append / to result_dir_url
- #119 python-copr client_v2 BuildHandler limits builds to the 100 most
  recent builds
- Fix tab vs spaces errors
- [*] Spelling fixes
- Invalid escape sequence fixes
- Bug 1471285 - Webhook triggers all changed specs even without new
  tito tag
- api for obtaining queue information

* Fri Aug 11 2017 clime <clime@redhat.com> 1.118-1
- fork all succeeded buildchroot in RawhideToRelease
- follow Fedora branching project's option added
- allow to modify copr chroots
- syntax highlight in project description and instructions
- fix 500 on /api/coprs/build/ for auto-rebuilds
- Bug 1409894 - COPR invalidly renders markdown
- basic rebuild all packages feature added

* Mon Jul 31 2017 clime <clime@redhat.com> 1.117-1
- Bug 1473361 - New SCM 2 build does not recall the 'Subdirectory'
  setting
- Deprecation warnings on F25
- hotfix for monitor page with jinja 2.9
- bug 1460399 - Build breadcrumb incorrect for group project

* Wed Jul 19 2017 clime <clime@redhat.com> 1.116-1
- in UI, rename Tito to SCM-1 and MockSCM to SCM-2
- add support for SCM Subdirectory parameter

* Fri Jul 14 2017 clime <clime@redhat.com> 1.115-1
- small updates

* Fri Jul 07 2017 clime <clime@redhat.com> 1.114-1
- .spec build implemented
- just return repo_url as it is in helpers.pre_process_repo_url

* Fri Jun 23 2017 clime <clime@redhat.com> 1.113-1
- fix for a case when build task is pending for chroot no longer enabled in the project
- address Bug 1455249 - github webhook fires unnecessary builds
- Bug 1461371 - Counterintuitive user link

* Wed Jun 14 2017 clime <clime@redhat.com> 1.112-1
- use_bootstrap_container frontend support

* Fri Jun 09 2017 clime <clime@redhat.com> 1.111-1
- build_on_pagure_commit script refactoring
- support for importing build task only once
- modularity UI tweaks
- #67 copr edit-package-tito nulls out fields not edited
- fix Bug 1455249 - github webhook fires unnecessary builds
- support for copr-rpmbuild
- arbitrary dist-git branching

* Thu May 25 2017 clime <clime@redhat.com> 1.110-1
- gitlab webhooks support
- make pagure repo auto-rebuilding more error-prone

* Mon May 15 2017 clime <clime@redhat.com> 1.109-1
- debugging infos in build_on_pagure_commit.py
- error handling in build_on_pagure_commit.py
- Bug 1448333 - Unable to edit someone's else project settings
- do not require .git suffix in Git repo URL for webhook rebuilds of Tito and MockSCM packages
- use MBS for building modules via UI
- add class for communicating with MBS
- add NSV property for modulemd generator
- #55 Builds triggered by GitHub WebHook (tag event) do not enable Internet during build
- use ModulemdGenerator for construnting the yaml file

* Wed Apr 19 2017 clime <clime@redhat.com> 1.108-1
- use custom chroot for modules instead of F24
- send the original filename to MBS
- get rid of 'unknown key username' warning
- fix modularity unit test
- validate uploaded yaml file
- dont print how to use a module when it is not succeeded
- move MBS_URL to config
- allow to submit optional params to mbs
- frontend act as a gateway between user and mbs
- allow to create module and it's action separately
- make new-lines work in <code> blocks
- Bug 1442047 - Regenerate action is not restricted to an owner of the project.
- redirect output of update_indexes_quick in cron into /dev/null
- validate fork name characters (RhBug: 1435123)
- Bug 1433508 - Half-cancelled builds are not deleted correctly.
- Add extra step for setting up GitHub Webhook
- add "buildroot" repository into generated build-config
- python3 compatibility fixes in frontend core
- correctly set repo and ref to point to our dist-git
- replace fedorahosted links
- replace no-longer working fedorahosted links with the pagure ones

* Tue Feb 28 2017 clime <clime@redhat.com> 1.107-1
- [frontend] fix for python-flask-whooshee-0.4.1-2

* Mon Feb 27 2017 clime <clime@redhat.com> 1.106-1
- added alembic fedora revision to enable rawhide
- rename add_debug_user command to add_user
- show info about auto-createrepo only when disabled
- only require python2-flask-whooshee on f25+, require python-flask- whooshee otherwise
- proxyuser feature (RhBug: 1381574)
- allow setting proxy/no-proxy when altering user
- rewrite broken add_debug_user command
- add boolean proxy column to user table
- care only about packages in filter
- specify module components buildorder
- fill module rpm components

* Sat Jan 28 2017 clime <clime@redhat.com> 1.105-1
- separate schema and data (fedora) migrations
- update option descriptions in project settings page
- always show "Regenerate" button for recreating backend repodata
- ensure mock triplets are unique
- show a quick guide how to install 'dnf module' command
- add info what to do with modulemd
- allow to have multiple info lines per form field
- print info when there are no packages in a module
- suggest dnf to enable module
- make repo filter support group coprs for copr:// scheme
- move creation of copr-frontend-devel macro definition file from %%check to %%install
- handle GitHub tag event webhooks
- change dependency from python-flask-whooshee to python2-flask-whooshee
- fix package icon for group projects (RhBug: 1403348)
- return proper error when module not found
- hide FAS groups for non-FAS deployments
- provide functional API url to renew token
- krb5 login
- new replaceable welcome.html template
- make FAS opt-out
- fix traceback when forking

* Thu Dec 01 2016 clime <clime@redhat.com> 1.104-1
- set default build timeout to 18 hours
- allow hiding "quick enable" helper
- login should not be required for viewing modules
- (cli) inform user about build links
- create backend_rawhide_to_release command
- adding chroot repos implemented
- group_add: make group in breadcrumb menu clickable - create status/order functions by 'create_db'
- modularize design files
- spec: allow 'rpmbuild --without check'
- use "Suggests" tag only in Fedora
- add api method for translating module NVR to DNF repo url
- promptly generate mock profiles
- added auto-prune project's option
- Bug 1393361 - get_project_details returns incorrect yum_repos
- Bug 1086139 - [RFE] provide UI to cancel a build
- group support for modules
- modularity 1.0.2 support
- create proper module table
- by pagure fedmsgs induced auto-rebuilds
- Bug 1384923 - Ignore push events to other branches when one is
  selected
- stripped down impl of building from dist-git
- fix unit tests
- Bug 1377854 - provide functional URL when asking to renew token
- Bug 1382243 - Multiple rows were found for one()
- add link to all BZs to footer
- Bug 1335168 - Delete build(s) from CLI
- Bug 1380810 - [RFE] Show original repo when forking
- Bug 1368458 - Resubmit does not work on forked projects.
- FAS groups need re-login, inform user
- Bug 1381790 - rename Rawhide to F26 in Copr and create F27 when Fedora branches instead
- use 'debug' level for krb debug message
- fix krb auth for services
- fork only successful builds
- check user permissions when building module
- implement methods for querying multiple modules
- Bug 1361641 - Status in build table shows wrong values
- show html code for build badge
- speed up querying for recent builds
- modularity UI improvements
- do not fork created_on from previous project
- fix Bug 1376703 - Cannot cancel build and now explain

* Wed Sep 21 2016 clime <clime@redhat.com> 1.103-1
- add migration to enable mageia chroots
- fix Bug 1369763 - Cannot delete repo due to a canceled build
- Fix a typo

* Mon Sep 19 2016 clime <clime@redhat.com> 1.102-1
- support for mageia chroots
- add a note about Copr not being supported by Fedora Infra
- Bug 1374906 - Login redirection for raising legal flag doesn't work
- Modularity integration
- Bug 1370704 - Internal Server Error (too many values to unpack)

* Mon Sep 12 2016 clime <clime@redhat.com> 1.101-1
- package query fix

* Wed Sep 07 2016 clime <clime@redhat.com> 1.100-1
- alembic revision to enable F25 chroots
- script to deactivate fedora-22-* chroots
- stream api call package/list
- Add 'repo_gpgcheck=0' to .repo file template
- Add 'type=rpm-md' to .repo file template
- fixed the remaining unittest and reenabled tests during package build in .spec
- fix for DetachedInstanceError in unittests
- Bug 1369392 - package not listed in project page
- Bug 1368259 - Deleting a build from a group project doesn't delete backend files

* Mon Aug 15 2016 clime <clime@redhat.com> 1.99-1
- disable unittests during package builds

* Mon Aug 15 2016 clime <clime@redhat.com> 1.98-1
- Bug 1365882 - on create group copr, gpg key is generated for user and not for group
- Bug 1361344 - RFE: Allow denial of build deletion and resubmitting at project or group level
- do not use _mock_chroots_error property
- added unlisted_on_hp field into copr detail output
- do not care about generation of gpg keys on frontend while forking, delegate work to backend
- stream content of long pages
- monitor memory/speed optimization
- sort packages from a to z
- batch search indexing
- out of memory fixes
- module_md.yaml uploading for a chroot
- executable copr-frontend as symlink to manage.py
- fix incorrect build link from package tab when builder != owner (RhBug: 1354442)
- Bug 1337171 - creating group projects doesn't work
- fix multiple appearance of 'toggle all' button in build forms
- more error output from api entry-points
- generate again -doc subpackage
- Bug 1335237 - copr create command missing --disable_createrepo
- introduced parallel distgit
- simplified build and action task workflow

* Thu Jun 23 2016 Miroslav Suchý <msuchy@redhat.com> 1.97-1
- New Package view UI refresh
- empty state in the Builds and Packages views
- setting of WHOOSHEE_WRITER_TIMEOUT removed from code so that it is
  configurable from the main frontend config file
- remove unused methods from whoosheer so that flask_whooshee can
  avoid locking on these
- UI fix - project overview
- Requires: python-requests -> python2-requests
- Monitor - UI fix
- --enable-net option added for create/modify commands
  of copr-cli

* Thu Jun 23 2016 Miroslav Suchý <msuchy@redhat.com> 1.96-1
- package status image for CI
- Revert "[frontend] try again if whoosh does not get lock"
- add missing imports
- unlisted_on_hp attribute added to Copr model

* Thu Jun 16 2016 Miroslav Suchý <msuchy@redhat.com> 1.95-1
- fix logic of dist-git import queue
- typo

* Thu Jun 16 2016 Miroslav Suchý <msuchy@redhat.com> 1.94-1
- add mageia logo
- mask traceback which can be waived out
- only display normal tasks in status/importing
- timeout value for whoosh search index update increased to address
  LockError
- deserialize in python-marshmallow 2.1+ need 4 params
- lower priority for background task for dist-git import
- only display normal tasks in status/waiting + bg tasks cnt
- configure more packages to run pylint
- send confirm only when it is True
- add --background option to new build in CLI
- only publish first 10 background jobs so that backend queue
  doesn't get jammed
- only publish background jobs on /backend/waiting if no normal jobs
  are available
- add is_background column for builds
- send latest 1000 jobs to backend
- just issue a warning msg when unknown form key was received
  when creating new build or new copr
- if source_json is None for Package or Build, then return {} from
  source_json_dict prop
- more of log file migration
- Change log file paths in spec files
- no script label
- Editing a Table View for package, delete column Package name
- honor standard build options for build-package cmd + use
  package.has_source_type_set in API
- _No_ to Url & Upload package types
- removing need for source_type in package post data
- experimental support of building packages
  with copr-cli
- rename of method for creating new builds
- add with_chroot_states option for build.to_dict. Use this when
  serializing builds through API.
- added --with-all-builds, --with-latest-
  build and --with-latest-succeeded-build options for list-packages and get-
  package cmds
- label no javascript (#8)
- support forking via CLI
- more reliable condition whether forking into existing project

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
- move package views to separate file
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
  `succeeded` states; added some logs
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
- [frontend] provide info about last successful build
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
- [cli] UX changes - explicitly state that pkgs is URL
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
- [cron] manually clean /var/tmp after createrepo

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
