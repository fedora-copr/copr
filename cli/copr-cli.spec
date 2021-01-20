%if 0%{?rhel} > 7 || 0%{?fedora}
%global __python %_bindir/python3
%global with_python3 1
%else
%global __python %_bindir/python2
%global with_python2 1
%endif

%global min_python_copr_version 1.105.2.dev

Name:       copr-cli
Version:    1.92
Release:    1%{?dist}
Summary:    Command line interface for COPR

License:    GPLv2+
URL:        https://pagure.io/copr/copr

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %name-%version.tar.gz

BuildArch:  noarch

Requires:      wget

BuildRequires: asciidoc
BuildRequires: libxslt
BuildRequires: util-linux

%if %{with python3}
Requires:      python3-copr >= %min_python_copr_version
Requires:      python3-jinja2
Requires:      python3-simplejson
Requires:      python3-humanize
Requires:      python3-koji

Recommends:    python3-progress

BuildRequires: python3-copr >= %min_python_copr_version
BuildRequires: python3-devel
BuildRequires: python3-jinja2
BuildRequires: python3-humanize
BuildRequires: python3-pytest
BuildRequires: python3-setuptools
BuildRequires: python3-simplejson
BuildRequires: python3-munch
%else
Requires:      python-copr >= %min_python_copr_version
Requires:      python-jinja2
Requires:      python-simplejson
Requires:      python-humanize

BuildRequires: pytest
BuildRequires: python-copr >= %min_python_copr_version
BuildRequires: python-devel
BuildRequires: python-jinja2
BuildRequires: python-humanize
BuildRequires: python-mock
BuildRequires: python-setuptools
BuildRequires: python-simplejson
BuildRequires: python-munch
%endif

# We historically shipped empty doc package, uninstall it.
Obsoletes:     copr-cli-doc < 1.72

%if 0%{?rhel} == 6
Requires:      python-argparse

BuildRequires: python-argparse
%endif

%if 0%{?rhel} == 7
Requires:      python-progress
%endif

%description
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latests builds.

This package contains command line interface.

%prep
%setup -q


%build
version="%{version}" %py_build
mv copr_cli/README.rst ./
# convert manages
a2x -d manpage -f manpage man/copr-cli.1.asciidoc


%install
version="%{version}" %py_install
ln -sf %{_bindir}/copr-cli %{buildroot}%{_bindir}/copr
install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/copr-cli.1 %{buildroot}/%{_mandir}/man1/
install -p man/copr.1 %{buildroot}/%{_mandir}/man1/
install -d %{buildroot}%{_datadir}/cheat
cp -a man/copr-cli.cheat %{buildroot}%{_datadir}/cheat/copr-cli
ln -s %{_datadir}/cheat/copr-cli %{buildroot}%{_datadir}/cheat/copr
install -m 755 copr_cli/package_build_order.py %{buildroot}/%{_bindir}/package-build-order


%check
%{__python} -m pytest -vv tests


%files
%{!?_licensedir:%global license %doc}
%license LICENSE
%doc README.rst
%{_bindir}/copr
%{_bindir}/copr-cli
%{_mandir}/man1/copr-cli.1*
%{_mandir}/man1/copr.1*
%dir %{_datadir}/cheat
%{_datadir}/cheat/copr-cli
%{_datadir}/cheat/copr
%{python_sitelib}/*
%{_bindir}/package-build-order


%changelog
* Wed Jan 20 2021 Pavel Raiskup <praiskup@redhat.com> 1.92-1
- allow excluding chroots when submitting builds
- raise a proper exception if the module yaml file does not exist
- allow etting isolation option per chroot
- fix serializable() helper for the new python3-munch

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 1.91-1
- new --isolation option
- add --help output for build --timeout option

* Mon Nov 09 2020 Jakub Kadlcik <frostyx@email.cz> 1.90-1
- cli, frontend: custom build batches
- cli: propagate build --bootstrap value to API call
- cli: move the build --bootstrap option to a correct parser
- frontend, cli, python, rpmbuild: better bootstrap config
- beaker-tests, cli, frontend, python, rpmbuild: add option to config bootstrap
- all: run pytest with -vv in package build
- cli: fix timeout option to allow change timeout for build
- cli: fix dist-git unit tests
- common, cli, python, rpmbuild, frontend, backend: DistGit source method
- cli: support project/chroot format for getting/editting chroots
- cli: do bash-completion when argcomplete is installed
- cli: formally deprecate --memory option

* Tue Aug 11 2020 Pavel Raiskup <praiskup@redhat.com> 1.89-1
- copr get-package supports with_latest* args again
- testsuite fixes for el6
- useful error message when new client runs against old frontend

* Mon Aug 10 2020 Pavel Raiskup <praiskup@redhat.com> 1.88-1
- add command to list all builds of a project
- more effective query of packages with their latest builds
- point docs to the correct Fedora Copr instances

* Tue Jun 09 2020 Pavel Raiskup <praiskup@redhat.com> 1.87-1
- enable deleting multiple builds from cli

* Wed Mar 18 2020 Pavel Raiskup <praiskup@redhat.com> 1.86-1
- add script to list package build order in copr or koji
- fix `copr mock-config` to use `dnf.conf/yum.conf` automatically

* Wed Feb 05 2020 Pavel Raiskup <praiskup@redhat.com> 1.85-1
- new 'copr-cli build-module --distgit DISTGIT' option
- make build-package honor the --background flag

* Wed Jan 15 2020 Tomas Hrnciar <thrnciar@redhat.com> 1.84-1
- Don't spam when downloading build
- fix chroot-list command to work on both python2 and python3
- add command to list all available chroots

* Wed Dec 04 2019 Pavel Raiskup <praiskup@redhat.com> 1.83-1
- added module_hotfixes support
- nicer mock-config (build config) api output
- mock-config un-deprecated

* Thu Oct 03 2019 Pavel Raiskup <praiskup@redhat.com> 1.82-1
- manpage: update API token url
- support multilib projects
- fix traceback when lost connection during copr-cli build
- adding cheat for copr

* Tue Aug 13 2019 Pavel Raiskup <praiskup@redhat.com> 1.81-1
- cli: pypi package needs to depend on 'humanize'

* Mon Jul 29 2019 Pavel Raiskup <praiskup@redhat.com> 1.80-1
- drop pylint from BR
- use humanize instead of format_size(); fix issue#724

* Wed Apr 24 2019 Jakub Kadlčík <frostyx@email.cz> 1.79-1
- add CLI for permissions
- new --max-builds option
- rename repos 'url' attribute to 'baseurl'
- generate mock rootdir on client side
- pass a repo priority to dnf config
- Revert "[cli] fix copr mock-config"
- support temporary projects
- print helpful hints for config parsing errors
- fix tests broken by PR#547
- fix copr-cli downloading parent directory for cancelled builds

* Mon Feb 11 2019 Jakub Kadlčík <frostyx@email.cz> 1.78-1
- Don't catch exceptions inside action
- Fix storing the custom script parameters
- Properly rewrite download-build to use APIv3
- Do not require to set PyPI packagename when it is already set
- When serializing munch omit the proxy object
- Fix the APIv1 call in the aciton_new_webhook_secret function

* Tue Jan 15 2019 Miroslav Suchý <msuchy@redhat.com> 1.77-1
- fix side_effect function arguments
- fix assert_called_with params

* Thu Jan 10 2019 Miroslav Suchý <msuchy@redhat.com> 1.76-1
- rewrite description of copr dirs feature. Use "tag" instead of "suffix".
- explain copr_dir feature in man pages for build subcommand
- improve naming of copr_dir in copr-cli interface to copr_repo
- add support for copr dir to copr-cli
- we also buildrequire python-copr with APIv3 support
- add missing dependency on python-simplejson
- depend on munch because of tests
- have numbered string fields because of epel6
- fix copr mock-config

* Fri Oct 19 2018 Miroslav Suchý <msuchy@redhat.com> 1.75-1
- 1639590 - print name of package when it is deleted
- set variables for each build
- print friendlier error when trying to upload a nonexisting file
- put backend the deprecation warnings
- better errors with --config
- print just 'repos' to avoid yum/dnf confusion
- depend on python-copr-1.89
- print additional repos and blank line between projects
- rewrite unit tests to work with APIv3
- update resource properties
- fix the order of arguments
- json_dumps is not supposed to print anything
- return proper status code
- cast disable_createrepo to bool
- write to stderr instead of printing
- if ownername is not specified, use the one from config
- remove deprecated tito and mock actions
- rewrite copr-cli to use APIv3
- use git_dir_archive instead of git_dir_pack
- pg#251 Make it possible for user to select pyp2rpm template

* Thu Aug 30 2018 clime <clime@redhat.com> 1.74-1
- python-progress is not present in EL6

* Fri Aug 24 2018 clime <clime@redhat.com> 1.73-1
- pg#370 copr-cli new-webhook-secret fails
- fix input under python2

* Thu Aug 23 2018 clime <clime@redhat.com> 1.72-1
- generate new webhook secret functionality in copr-cli
- packaging: Python 2/3, RHEL/Fedora fixes

* Mon Aug 06 2018 clime <clime@redhat.com> 1.71-1
- %%{python_sitelib} → %%{python2_sitelib}

* Fri May 18 2018 clime <clime@redhat.com> 1.70-1
- deprecate mock-config command

* Mon Apr 30 2018 Dominik Turecek <dturecek@redhat.com> 1.69-1
fix non-passing unittests under f28+

* Thu Apr 26 2018 Dominik Turecek <dturecek@redhat.com> 1.68-1
- simplify bar.finish logic
- rpkg deployment into COPR - containers + releng continuation
- #280 cli upload to nonexisting project makes terminal cursor disappear
- #220 copr-cli doesn't display build progress in non-interactive terminal
- add download-build --dest description to man page
- add `copr delete-build` build into man pages

* Fri Feb 23 2018 clime <clime@redhat.com> 1.67-1
- remove Group tag

* Mon Feb 19 2018 clime <clime@redhat.com> 1.66-1
- Shebangs cleanup
- fix deps in spec
- allow running tests only for epel7
- tests also for python2 during builds
- new custom source method
- require to specify project when building module

* Thu Nov 09 2017 clime <clime@redhat.com> 1.65-1
- allow to set use_bootstrap_container via API

* Wed Oct 18 2017 clime <clime@redhat.com> 1.64-1
- add SCM api interface
- deprecate tito and mockscm methods

* Fri Sep 15 2017 clime <clime@redhat.com> 1.63-1
- fix unittests
- run tests with python3
- #130 update requirements
- #125 copr build copr pkgs [pkgs ...] builds only the first SRPM
- #112 [RFE] copr-cli whoami
- Bug 1431035 - coprs should check credentials before uploading
  source rpm
- Spelling fixes

* Fri Aug 11 2017 clime <clime@redhat.com> 1.62-1
- allow to modify copr chroots with copr modify cmd

* Fri Jul 14 2017 clime <clime@redhat.com> 1.61-1
- Bug 1399817 - copr --version does not print version info

* Fri Jun 09 2017 clime <clime@redhat.com> 1.60-1
- use global const map for on/off command line switches value translation

* Wed Apr 19 2017 clime <clime@redhat.com> 1.59-1
- when building module --url or --yaml needs to be selected
- remove make-module command
- update man for build-module command
- allow to submit optional params to mbs
- frontend act as a gateway between user and mbs
- possibility to submit yaml file to mbs
- compose auth url more prettier
- describe module actions in man
- rename method for making module to match cli naming
- split module building into two separate commands
- add possibility to build module via MBS or not
- add command for building modules
- more similar mock-config with real builder's config
- put errors/warnings on stderr
- fix trace in 'copr-cli --debug'
- replace fedorahosted links
- use 'avg' api from python-progress

* Thu Dec 01 2016 clime <clime@redhat.com> 1.58-1
- `copr-cli edit-chroot` implemented (without modulemd uploading)
- add 'mock-config' command
- added auto-prune project's option
- Bug 1390067 - Progress speed/estimates are completely incorrect
- Bug 1389265 - Using groups with copr-cli is not easily discoverable
- brought unittests into passing state
- stripped down impl of building from dist-git
- Bug 1335168 - Delete build(s) from CLI
- disable network by default when creating new copr

* Mon Sep 19 2016 Miroslav Suchý <msuchy@redhat.com> 1.57-1
- re-use PYTHONPATH in cli wrapper

* Mon Sep 12 2016 Miroslav Suchý <msuchy@redhat.com> 1.56-1
- require python-progress on Fedora
- fix for python-progress API

* Mon Aug 15 2016 clime <clime@redhat.com> 1.55-1
- Bug 1361344 - RFE: Allow denial of build deletion and resubmitting at project or group level

* Fri Jul 15 2016 Miroslav Suchý <msuchy@redhat.com> 1.54-1
- actually define use_python3 macro

* Fri Jul 01 2016 clime <clime@redhat.com> 1.53-1
- enable pylint checks only if python3 macro is enabled
- Bug 1335237 - copr create command missing --disable_createrepo
- --enable-net option added for create/modify commands of copr-cli
- added man entry about --unlisted-on-hp option of create command

* Thu Jun 16 2016 Miroslav Suchý <msuchy@redhat.com> 1.52-1
- configure more packages to run pylint
- run checks for copr-cli
- man page for --background of copr-cli
- add --background option to new build in CLI
- man entries for copr-cli package actions + tests update
- Add syntax for working with group projects to the man page.
- honor standard build options for build-package cmd + use
  package.has_source_type_set in API
- _No_ to Url & Upload package types
- man: add examples
- experimental support of building packages
  with copr-cli
- list-package-names cmd added + build-package cmd implementation thub
- added --with-all-builds, --with-latest-
  build and --with-latest-succeeded-build options for list-packages and get-
  package cmds
- support forking via CLI

* Thu May 26 2016 clime <clime@redhat.com> 1.51-1
- support for package manipulation
- added watch-build subcommand
- Bug 1333771 - Traceback from copr-cli when missing --pythonversions
- rubygems CLI support implemented
* Wed Apr 20 2016 Miroslav Suchý <msuchy@redhat.com> 1.50-1
- use python3 on Fedora24+
- better error message
- document --git-branch and --scm-branch options
- fix download-build for dist-git era file structure (RhBug: 1324847)
- implement building via mock
- document buildtito in manpage
- change build-tito command to buildtito
- implement building via tito
- buildpypi command documented in man pages + slightly improved
  --help description of the command
- add group support for modifying and deleting projects
- fix expected warning in failing unit tests
- refactor owner name parsing

* Sun Mar 20 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.49-1
- allow creating group projects
- bug 1309101 - copr-cli doesn't handle string input for 'status'

* Mon Mar 14 2016 Jakub Kadlčík <jkadlcik@redhat.com> 1.48-1
- support building from PyPI

* Fri Jan 29 2016 Miroslav Suchý <msuchy@redhat.com> 1.47-1
- gfix 1302615 - UnboundLocalError: local variable 'bar' referenced before
  assignment when building from URLs
- gman pages updated for 1292033 - copr-cli ignores multiple package
  arguments if the first is a local file
- grequire sufficiently new python-copr package
- gadd DummyBar.finish() stub
- compatibility with el6 and el7
- add --config option
- fix packaging for epel-6+ and fedora-22+
- Added MANIFEST.in for python and cli

* Mon Nov 02 2015 Miroslav Suchý <msuchy@redhat.com> 1.46-1
- Removed __version__ from cli and python
- Added version parse from specs instead of __init__
- Fixed invalid classifiers
- Fixes to allow copr-cli to be installed using setup.py
- ImportError: No module named exceptions
- Display progress bar if python-progress is available

* Mon Oct 12 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.45-1
- build action: accept any character in the username

* Fri May 15 2015 Miroslav Suchý <msuchy@redhat.com> 1.44-1
- mark license as license in spec
- 1188022 - accept dash in project name

* Wed Jan 21 2015 Miroslav Suchý <msuchy@redhat.com> 1.43-1
- regression: enable again copr-cli build username/project

* Mon Jan 05 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.42-1
- updated man page
- compatibility with Python 2.6 ( due to Epel 6)

* Mon Dec 15 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.41-1
- control auto_createrepo property of project through API
  and copr-cli; new command supported by cli: **modify**

* Fri Nov 21 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.40-1
- updated to use newer version of python-copr
- minor changes in commands output
- print debug logs only when user provides "--debug" option

* Mon Oct 20 2014 Miroslav Suchý <msuchy@redhat.com> 1.39-1
- add man page for copr(1)
- [cli] [RHBZ: #1149889]  RFE: download command in copr-cli
- A few fixes for CI

* Tue Oct 07 2014 Valentin Gologuzov <vgologuz@redhat.com> 1.38-1
- [cli] Added symlink for executable: copr -> copr-cli
- [cli] removed epydoc documentation
- [python-copr, cli] test coverage
- [python-copr, cli] updating copr-cli to use python-copr

* Thu Sep 18 2014 Miroslav Suchý <msuchy@redhat.com> 1.37-1
- [python-copr] Renamed package: python-copr-client -> python-copr
- [cli]  In case of missing config show proper message, hide traceback.
- [python-client] added a few unittest, changed package layout, updated .spec
  to run tests during %%check. [copr-cli] reflected changes in python-client
- [python-copr,copr-cli] fixing, cleanup
- [python-copr,copr-cli] Copr-cli now uses python-copr-cli package. [copr-cli]
  updated .spec to reflect usage of python-copr-client

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
