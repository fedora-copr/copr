%global srcname copr

%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?_licensedir:%global license %%doc}
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%global sphinxbuild SPHINXBUILD=%_bindir/sphinx-1.0-build
%endif

%if 0%{?fedora} || 0%{?rhel} > 7
%global with_python3 1
%endif

%if 0%{?fedora} < 28 || 0%{?rhel} && 0%{?rhel} <= 7
%global with_python2 1
%endif

Name:       python-copr
Version:    1.108
Release:    1%{?dist}
Summary:    Python interface for Copr

License:    GPLv2+
URL:        https://pagure.io/copr/copr

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %name-%version.tar.gz

BuildArch:  noarch

BuildRequires: libxslt
BuildRequires: util-linux

%if %{with python2}
%if 0%{?rhel} && 0%{?rhel} <= 7
BuildRequires: python-setuptools
BuildRequires: python-requests
BuildRequires: python-requests-toolbelt
BuildRequires: python-marshmallow
BuildRequires: python-six >= 1.9.0
BuildRequires: python-mock
BuildRequires: python-munch
BuildRequires: python-configparser
BuildRequires: pytest
BuildRequires: python2-devel
# for doc package
%if 0%{?rhel} && 0%{?rhel} == 6
BuildRequires: python-sphinx10
%else
BuildRequires: python-sphinx
%endif
BuildRequires: python-docutils
%else
BuildRequires: python2-setuptools
BuildRequires: python2-requests
BuildRequires: python2-requests-toolbelt
BuildRequires: python2-marshmallow
BuildRequires: python2-six >= 1.9.0
BuildRequires: python2-mock
BuildRequires: python2-pytest
BuildRequires: python2-devel
BuildRequires: python-munch
BuildRequires: python2-configparser
# for doc package
BuildRequires: python2-sphinx
BuildRequires: python2-docutils
%endif
%endif
#doc
BuildRequires: make

%global _description\
COPR is lightweight build system. It allows you to create new project in WebUI,\
and submit new builds and COPR will create yum repository from latest builds.\
\
This package contains python interface to access Copr service. Mostly useful\
for developers only.\


%description %_description

%if %{with python2}
%package -n python2-copr
Summary: %summary

%if 0%{?rhel} < 8 && 0%{?rhel} > 0
Requires: python-configparser
Requires: python-marshmallow
Requires: python-munch
Requires: python-requests
Requires: python-requests-toolbelt
Requires: python-setuptools
Requires: python-six >= 1.9.0
%else
Requires: python2-configparser
Requires: python2-marshmallow
Requires: python2-munch
Requires: python2-requests
Requires: python2-requests-toolbelt
Requires: python2-setuptools
Requires: python2-six >= 1.9.0
%endif

%{?python_provide:%python_provide python2-copr}

%description -n python2-copr %_description
%endif
# with python2

%if %{with python3}
%package -n python3-copr
Summary:        Python interface for Copr

# for recent fedoras the requires are generated dynamicaly
%if 0%{?fedora} && 0%{?fedora} < 31 || 0%{?rhel} && 0%{?rhel} <= 8

BuildRequires: python3-devel
BuildRequires: python3-docutils
BuildRequires: python3-mock
BuildRequires: python3-munch
BuildRequires: python3-marshmallow
BuildRequires: python3-pytest
BuildRequires: python3-setuptools
BuildRequires: python3-requests
BuildRequires: python3-requests-toolbelt
BuildRequires: python3-six
BuildRequires: python3-sphinx

Requires: python3-marshmallow
Requires: python3-munch
Requires: python3-requests
Requires: python3-requests-toolbelt
Requires: python3-setuptools
Requires: python3-six
%endif

%{?python_provide:%python_provide python3-copr}

%if 0%{?fedora} > 30
BuildRequires: pyproject-rpm-macros
BuildRequires: python3-sphinx
BuildRequires: python3-pytest
BuildRequires: python3-mock

%generate_buildrequires
%pyproject_buildrequires -r
%endif

%description -n python3-copr
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package contains python interface to access Copr service. Mostly useful
for developers only.

%endif
# with python3


%package -n python-copr-doc
Summary:    Code documentation for python-copr package

%description doc
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package includes documentation for python-copr. Mostly useful for
developers only.


%prep
%setup -q


%build
%if %{with python3}
version=%version %py3_build
%endif

%if %{with python2}
version=%version %py2_build
%endif

mv copr/README.rst ./

# build documentation
make -C docs %{?_smp_mflags} html %{?sphinxbuild}


%install
%if %{with python3}
version=%version %py3_install
%endif

%if %{with python2}
version=%version %py2_install
%endif

find %{buildroot} -name '*.exe' -delete

install -d %{buildroot}%{_pkgdocdir}
cp -a docs/_build/html %{buildroot}%{_pkgdocdir}/

%check
%if %{with python3}
%{__python3} -m pytest -vv copr/test
%endif

%if %{with python2}
%{__python2} -m pytest -vv copr/test
%endif


%if %{with python3}
%files -n python3-copr
%license LICENSE
%doc README.rst
%{python3_sitelib}/*
%endif
# with python3

%if %{with python2}
%files -n python2-copr
%license LICENSE
%doc README.rst
%{python2_sitelib}/*
%endif
# with python2

%files -n python-copr-doc
%license LICENSE
%doc %{_pkgdocdir}

%changelog
* Wed Jan 20 2021 Pavel Raiskup <praiskup@redhat.com> 1.108-1
- allow setting isolation option per chroot

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 1.107-1
- new mock --isolation option
- deduplicate APIv3 build-chroot parameters

* Wed Nov 11 2020 Pavel Raiskup <praiskup@redhat.com> 1.106-1
- bump to non-devel version

* Mon Nov 09 2020 Jakub Kadlcik <frostyx@email.cz> 1.105.3.dev-1
- frontend, python: we cannot order chroots by name
- python: synchronize the docs for build options
- frontend, cli, python, rpmbuild: better bootstrap config
- beaker-tests, cli, frontend, python, rpmbuild: add option to config bootstrap
- all: run pytest with -vv in package build
- common, cli, python, rpmbuild, frontend, backend: DistGit source method
- python: Don't apply bind_proxy in BaseProxy __init__()

* Tue Aug 11 2020 Pavel Raiskup <praiskup@redhat.com> 1.105-1
- drop a redundant %%py3dir use

* Tue Aug 11 2020 Pavel Raiskup <praiskup@redhat.com> 1.104-1
- copr-cli API for get-package to support with_latest* args again

* Mon Aug 10 2020 Pavel Raiskup <praiskup@redhat.com> 1.103-1
- fix APIv3 build deletion
- warn about deprecated APIv1
- fix v2 client is_a_group_project usage
- show obsolete warning on all APIv1 and APIv2 pages
- more effective query of packages with their latest builds

* Tue Jun 09 2020 Pavel Raiskup <praiskup@redhat.com> 1.102-1
- fix large recursion problem
- enable deleting multiple builds from cli

* Wed Feb 05 2020 Pavel Raiskup <praiskup@redhat.com> 1.101-1
- allow to pick dist-git instance when building modules
- fix traceback when wrong url to frontend is specified

* Wed Jan 15 2020 Tomas Hrnciar <thrnciar@redhat.com> 1.100-1
- add command to list all available chroots

* Wed Dec 04 2019 Pavel Raiskup <praiskup@redhat.com> 1.99-1
- add api support for module_hotfixes
- nicer mock-config command output

* Thu Oct 03 2019 Pavel Raiskup <praiskup@redhat.com> 1.98-1
- enable dynamic buildrequires on F31+
- drop comments after %%endif

* Thu Sep 26 2019 Pavel Raiskup <praiskup@redhat.com> 1.97-1
- python: fix API for marshmallow 3+ (#934)
- frontend, cli, python: support multilib projects (#1)

* Mon Jul 29 2019 Pavel Raiskup <praiskup@redhat.com> 1.96-1
- use plain %%setup to fix FTBFS

* Mon Jul 29 2019 Pavel Raiskup <praiskup@redhat.com> 1.95-1
- drop pylint from BR

* Wed Apr 24 2019 Jakub Kadlčík <frostyx@email.cz> 1.94-1
- add CLI for permissions
- support temporary projects
- print friendly error on http when https is enforced
- print helpful hints for config parsing errors
- remove unnecessary PY3 condition
- re-order spec {Build,}Requires
- BuildRequires python3-mock
- avoid 'collections.abc' warnings
- handle timeout errors
- remove old_status column from package table
- fix wait function for custom List
- remove dependency on python3-configparser

* Tue Jan 15 2019 Miroslav Suchý <msuchy@redhat.com> 1.93-1
- there is no dict comprehension for python2.6 which is in epel6

* Thu Jan 10 2019 Miroslav Suchý <msuchy@redhat.com> 1.92-1
- add support for copr dir to copr-cli
- provide a way to wait until builds finish
- don't pass proxy object to the wait method
- don't fail when no callback
- provide a way to wait until builds finish
- store a reference to the proxy object
- add possibility to query all projects (RhBug: 1130166)

* Fri Oct 19 2018 Miroslav Suchý <msuchy@redhat.com> 1.91-1
- better errors with --config
- use git_dir_archive instead of git_dir_pack
- document status codes from frontend
- pg#251 Make it possible for user to select pyp2rpm template

* Thu Aug 23 2018 clime <clime@redhat.com> 1.90-1
- generate new webhook secret functionality in copr-cli
- allow to edit devel_mode on a project
- update copyright for the documentation
- packaging: Python 2/3, RHEL/Fedora fixes
- fix "File 'setup.py' not found" error in readthedocs.org
- use readthedocs theme if it is installed

* Mon Aug 06 2018 clime <clime@redhat.com> 1.89-1
- apiv3
- change %%{python_sitelib} to %%{python2_sitelib}
- for py3 use unittest.mock, otherwise mock from python2-mock

* Thu Apr 26 2018 Dominik Turecek <dturecek@redhat.com> 1.88-1
- rpkg deployment into COPR - containers + releng continuation

* Wed Feb 28 2018 clime <clime@redhat.com> 1.87-1
- add missing frontend states to clientv2

* Fri Feb 23 2018 clime <clime@redhat.com> 1.86-1
- remove Group tag

* Mon Feb 19 2018 clime <clime@redhat.com> 1.85-1
- build python2-copr package conditionally
- Remove unnecessary shebang sed in copr-cli.spec and python-copr.spec
- fix deps in spec
- new custom source method
- use username from config if nothing is explicitly specified
- remove outdated modularity code
- require to specify project when building module

* Fri Nov 10 2017 clime <clime@redhat.com> 1.84-1
- update clients to use https://copr.fedorainfracloud.org as default
  API endpoint

* Thu Nov 09 2017 clime <clime@redhat.com> 1.83-1
- Remove duplicated Python packagtes, using "." in requirements.txt
- Add classifiers to support Python3.
- allow to set use_bootstrap_container via API

* Wed Oct 18 2017 clime <clime@redhat.com> 1.82-1
- add SCM api
- add deprecation warnings for tito and mockscm methods

* Fri Sep 15 2017 clime <clime@redhat.com> 1.81-1
- Bug 1431035 - coprs should check credentials before uploading
  source rpm Remove unnecesary condition
- Spelling fixes

* Mon Aug 21 2017 Miroslav Suchý <msuchy@redhat.com> 1.80-1
- rename python-copr to python2-copr

* Fri Aug 11 2017 clime <clime@redhat.com> 1.79-1
- allow to modify copr chroots
- always send name of the user

* Fri Jun 09 2017 clime <clime@redhat.com> 1.78-1
- pag#67 copr edit-package-tito nulls out fields not edited

* Wed Apr 19 2017 clime <clime@redhat.com> 1.77-1
- allow to submit optional params to mbs
- frontend act as a gateway between user and mbs
- allow to create module and it's action separately
- possibility to submit yaml file to mbs
- update auth for current MBS package
- rename method for making module to match cli naming
- add command for building modules
- files can be uploaded via simple MultipartEncoder (RhBug: 1440480)
- fix proxyuser when creating modules
- replace fedorahosted links
- fix setting username on multipart data
- proxyuser feature (RhBug: 1381574)

* Thu Jan 26 2017 clime <clime@redhat.com> 1.76-1
- fix python 2.6 incompatibility

* Thu Dec 01 2016 clime <clime@redhat.com> 1.75-1
- edit_chroot implemented
- modulemd 1.0.2 compatibility
- add method for fetching /api/module/repo
- add 'mock-config' command to CLI
- added auto-prune project's option
- stripped down impl of building from dist-git
- Bug 1335168 - Delete build(s) from CLI

* Mon Sep 19 2016 clime <clime@redhat.com> 1.74-1
- dummy api for submitting module builds

* Mon Aug 15 2016 clime <clime@redhat.com> 1.73-1
- Bug 1361344 - RFE: Allow denial of build deletion and resubmitting at project or group level
- fix creating group projects
- fix search for projects within group (RhBug: 1337247)

* Fri Jul 01 2016 clime <clime@redhat.com> 1.72-1
- run pylint check during build only if python3 is defined
- Bug 1335237 - copr create command missing --disable_createrepo
- --enable-net option added for create/modify commands of copr-cli
- --unlisted-on-hp option add for create/modify commands of copr-cli
* Thu Jun 16 2016 Miroslav Suchý <msuchy@redhat.com> 1.71-1
- configure more packages to run pylint
- send confirm only when it is True
- add --background option to new build in CLI
- honor standard build options for build-package cmd + use
  package.has_source_type_set in API
- _No_ to Url & Upload package types
- removing need for source_type in package post data
- fix non-existent attribute access for PackageWrapper
- experimental support of building packages
  with copr-cli
- added --with-all-builds, --with-latest-
  build and --with-latest-succeeded-build options for list-packages and get-
  package cmds

* Mon May 30 2016 clime <clime@redhat.com> 1.70-1
- [cli][python][frontend] support forking via CLI
- [python-copr] added missing source_type specification for upload & url builds

* Thu May 26 2016 clime <clime@redhat.com> 1.69-1
- package manip implemented in Client
- refactored building via url and pypi; see df6ad16
- connection error message simplified
- print user-friendly error for broken config
- implemented rubygems CLI support

* Fri Apr 22 2016 Miroslav Suchý <msuchy@redhat.com> 1.68-1
- Add unicode representation for collections (RhBug: 1327597)
- handlers: use list() after map() for chroots
- fix download-build for dist-git era file structure (RhBug:
  1324847)
- implement building via mock
- refactor building via tito
- implement building via tito
- assure python_versions type for pypi builds

* Sun Mar 20 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.67-1
- allow creating group projects

* Mon Mar 14 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.66-1
- support building from PyPI

* Wed Feb 03 2016 Miroslav Suchý <msuchy@redhat.com> 1.65-1
- convert bytes to utf-8 in Py3

* Fri Jan 29 2016 Miroslav Suchý <msuchy@redhat.com> 1.64-1
- fix wrong check for list instance

* Wed Dec 23 2015 Miroslav Suchý <msuchy@redhat.com> 1.63-1
- fixes for epel-6+ and fedora-22+
- Added MANIFEST.in for python and cli
- updated docs to include project creation method
- create new projects now returns newly created project on success
- added method to create new projects through ClientV2
- we need six >= 1.9.0
- added support for BuildTask and update docs
- W: 67, 8: Unused variable 's' (unused-variable)
- W: 70,12: Unused variable 'x' (unused-variable)
- Too few public methods (0/1) (too-few-public-methods)
- Use %% formatting in logging functions but pass the %% parameters as
  arguments
- Instance of '...Entity' has no '...' member (no-member)
- add Entity tests
- initial documentation for ClientV2

* Mon Nov 16 2015 Miroslav Suchý <msuchy@redhat.com> 1.62-1
- pylint cleaning

* Mon Nov 09 2015 Miroslav Suchý <msuchy@redhat.com> 1.61-1
- W:  9, 0: Unused import json (unused-import)
- Added marshmallow as dep
- since APIv2 we require python-marshmallow

* Mon Nov 02 2015 Miroslav Suchý <msuchy@redhat.com> 1.60-1
- python3 compatibility
- Removed __version__ from cli and python
- Added version parse from specs instead of __init__
- Fixes to allow copr lib to be installed using setup.py
- Fixed invalid classifiers
- put client_v2 into package
- Display progress bar if python-progress is available
- support APIv2

* Tue Oct 13 2015 Miroslav Suchý <msuchy@redhat.com> 1.59-1
- version_info is not namedtuple on epel6 interpreter
- fix missing urllib.parse on el7
- use requests-toolbelt to stream SRPM files (RhBug:1261125)
- add run_tests.sh script
- fix unicode representation of CoprResponse (RhBug:1258915)

* Tue Aug 11 2015 Miroslav Suchý <msuchy@redhat.com> 1.58-1
- implement srpm upload functionality
- better error handling (RhBug:1245105)
- define %%license macro for el6
- el6 needs field numbers

* Thu Jul 02 2015 Miroslav Suchý <msuchy@redhat.com> 1.57-1
- [cli] wrap requests exception (RhBug:1194522)
- [python] Bug 1188874 - better unicode handling
- [cli] test unicode representation of ProjectWrapper (RhBug:1188874)
- [cli] fix unicode representation of ProjectWrapper (RhBug:1188874)
- mark license as license in spec

* Mon Dec 15 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.56-1
- control auto_createrepo property of project through API

* Thu Nov 20 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.55-1
- [python] support python 2.6

* Thu Nov 20 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.54-1
- fixed poor decision abou CoprClient constructor, now it accepts
  kwargs arguments instead of config dict

* Mon Nov 03 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.53-1
- [python-copr] syntax bugfix

* Mon Nov 03 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.52-1
- [python-copr] removed log config from client

* Tue Oct 07 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.51-1
- [python-copr, cli] test coverage 
- [python-copr, cli] updating copr-cli to use python-copr
- [python-copr] minor fixes, added usage examples to docs

* Mon Sep 08 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.50-1
- [python-copr] fix: we need to support python 2.6 due to epel-6

* Fri Sep 05 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.49-1
- [python-copr] 
- bugfix in cancel_build - more docsrtings
- using sphinx documentation for rpm build
- added instruction to build documentation
- re-implemented Response handling  
- started transition to sphinx documentation  
- added optional argument `username` to most client methods
- removed method  `get_build_status`

* Wed Aug 27 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.48-1
- [python-copr] small fix due to the old version of python-six in RHEL-7

* Wed Aug 27 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.47-1
- [python-copr] Build python3 package only for fedora
- [python-copr] minor description fix in .spec

* Fri Aug 22 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.46-1
- [python-copr] packaging fixes to satisfy Fedora package guidelines.

* Thu Aug 21 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.45-1
- change package name: python-copr-client -> python-copr

* Tue Aug 19 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.44-1
- [python-client] fixed BuildRequires

* Tue Aug 19 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.43-1
- [python-client] Added new package
- [cli] cli now  access api through  python-client

* Tue Jul 22 2014 Miroslav Suchý <msuchy@redhat.com> 1.36-1
- use correct name of variable

* Fri Jul 04 2014 Miroslav Suchý <msuchy@redhat.com> 1.35-1
- [cli] stop waiting when the status is unknown

* Fri Jul 04 2014 Miroslav Suchý <msuchy@redhat.com> 1.34-1
- [cli] skipped state support

* Thu Jun 19 2014 Miroslav Suchý <msuchy@redhat.com> 1.33-1
- cancel added to the man page
- exit code 4 for failed build and man pages updated
- error and shell return code 1 when build fails
- delete a project
- shell return codes with errors
- copr-cli cancel fix

* Thu Apr 10 2014 Miroslav Suchý <msuchy@redhat.com> 1.32-1
- be less strict in parsing fas/copr-name

* Thu Apr 10 2014 Miroslav Suchý <msuchy@redhat.com> 1.31-1
- We can choose chroots for new builds
- copr-cli waiting fix
- building pkgs separately

* Wed Mar 19 2014 Miroslav Suchý <msuchy@redhat.com> 1.30-1
- BR make is not needed
- build -doc subpackage only for fedoras
- add LICENSE to -doc
- replace 'copr' with 'project'

* Tue Mar 18 2014 Miroslav Suchý <msuchy@redhat.com> 1.29-1
- move copr-cli in standalone package

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
