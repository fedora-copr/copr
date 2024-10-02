%global __python        %__python3
%global python          python3
%global python_pfx      python3
%global rpm_python      python3-rpm
%global sitelib         %python3_sitelib

%global copr_common_version 0.21.1.dev

# do not build debuginfo sub-packages
%define debug_package %nil

%define latest_requires() \
Requires: %1 \
%{expand: %%global latest_requires_packages %1 %%{?latest_requires_packages}}

Name:    copr-rpmbuild
Version: 1.0
Summary: Run COPR build tasks
Release: 1%{?dist}
URL: https://github.com/fedora-copr/copr
License: GPL-2.0-or-later

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %name-%version.tar.gz

BuildRequires: %{python}-copr-common >= %copr_common_version
BuildRequires: %{python}-devel
BuildRequires: %{python}-distro
BuildRequires: %{python}-httmock
BuildRequires: %{rpm_python}
BuildRequires: asciidoc
BuildRequires: dist-git-client
BuildRequires: git
BuildRequires: %{python}-setuptools
BuildRequires: %{python}-pytest
BuildRequires: %{python_pfx}-munch
BuildRequires: %{python}-requests
BuildRequires: %{python_pfx}-jinja2
BuildRequires: %{python_pfx}-specfile >= 0.21.0
BuildRequires: python3-backoff >= 1.9.0
BuildRequires: python3-pyyaml

BuildRequires: /usr/bin/argparse-manpage
BuildRequires: python-rpm-macros

%if "%{?python}" == "python2"
BuildRequires: python2-configparser
BuildRequires: python2-mock
Requires: python2-configparser
%endif

Requires: %python
Requires: %{python}-copr-common >= %copr_common_version
Requires: %{python_pfx}-jinja2
Requires: %{python_pfx}-munch
Requires: %{python}-requests
Requires: %{python_pfx}-specfile >= 0.21.0
Requires: python3-backoff >= 1.9.0
Requires: python3-pyyaml

Requires: mock >= 5.0
Requires: git
Requires: git-svn
# for the /bin/unbuffer binary
Requires: expect
%if 0%{?openEuler} > 0 || 0%{?rhel} > 0
# qemu-user-static is not supported
%else
Requires: qemu-user-static
%endif
Requires: sed

%if 0%{?fedora} || 0%{?rhel} > 7
Recommends: rpkg
Recommends: python-srpm-macros
Recommends: dist-git-client
Suggests: tito
Suggests: rubygem-gem2rpm
Suggests: pyp2rpm
Suggests: pyp2spec
%endif

%description
Provides command capable of running COPR build-tasks.
Example: copr-rpmbuild 12345-epel-7-x86_64 will locally
build build-id 12345 for chroot epel-7-x86_64.


%package -n copr-builder
Summary: copr-rpmbuild with all weak dependencies
Requires: %{name} = %{version}-%{release}
Requires: dist-git-client

%if 0%{?fedora} && 0%{?fedora} < 41
# replacement for yum/yum-utils, to be able to work with el* chroots
# bootstrap_container.
Requires: dnf-yum
Requires: dnf-utils
%endif
# selinux toolset to allow running ansible against the builder
Requires: python3-libselinux
Requires: python3-libsemanage
%if 0%{?openEuler}
# for mock to allow: config_opts['nosync'] = True
Requires: nosync
%endif
Requires: openssh-clients
Requires: podman
%if 0%{?openEuler} > 0 || 0%{?rhel} > 0
# not supported
%else
Requires: pyp2rpm
Requires: pyp2spec
Requires: rubygem-gem2rpm
Requires: scl-utils-build
Requires: fedora-review >= 0.8
Requires: fedora-review-plugin-java
%endif
# We need %%pypi_source defined, which is in 3-29+
Requires: python-srpm-macros >= 3-29
Requires: rpkg
Requires: rsync
Requires: tito
# yum* to allow mock to build against el* chroots without bootstrap_container
%if 0%{?rhel}
Requires: yum
Requires: yum-utils
%endif

# We want those to be always up-2-date
%latest_requires ca-certificates
%latest_requires distribution-gpg-keys
%if 0%{?fedora} >= 38
%latest_requires dnf5
%latest_requires dnf5-plugins
%endif

%latest_requires python3-dnf
%latest_requires dnf-plugins-core
%latest_requires libdnf
%latest_requires librepo
%latest_requires libsolv
%latest_requires mock
%latest_requires mock-core-configs
%latest_requires system-rpm-config
%latest_requires rpm


%description -n copr-builder
Provides command capable of running COPR build-tasks.
Example: copr-rpmbuild 12345-epel-7-x86_64 will locally
build build-id 12345 for chroot epel-7-x86_64.

This package contains all optional modules for building SRPM.


%prep
%setup -q
for script in bin/copr-rpmbuild*; do
    sed -i '1 s|#.*python.*|#! /usr/bin/%python|' "$script"
done


%check
PYTHON=%{python} ./run_tests.sh -vv --no-coverage


%build
name="%{name}" version="%{version}" summary="%{summary}" %py_build
a2x -d manpage -f manpage man/copr-rpmbuild.1.asciidoc

%global mock_config_overrides %_sysconfdir/copr-rpmbuild/mock-config-overrides

cat > copr-update-builder <<'EOF'
#! /bin/sh

# Update the Copr builder machine, can be called anytime Copr build system
# decides to do so (please keep the script idempotent).

# install the latest versions of those packages
dnf update -y %latest_requires_packages *rpm-macros

# The mock-core-configs package was potentially updated above, and it provides
# "noreplace" %%config files.  It means that - if the builder cloud image had
# baked-in locally _changed_ configuration files - the updated official
# configuration files from mock-core-configs package wouldn't be used.  So now
# make sure that they _are_ used (those, if any, would reside in .rpmnew files).
find /etc/mock -name '*.rpmnew' | while read -r rpmnew_file; do
    config=${rpmnew_file%%.rpmnew}
    mv -f "$config" "$config.copr-builder-backup" && \
    mv "$rpmnew_file" "$config"
done

# And now use the overrides from %%mock_config_overrides directory
(
  cd %mock_config_overrides
  find . -name '*.tpl' -o -name '*.cfg' | while read -r file; do
    base=$(basename "$file")
    dir=%_sysconfdir/mock/$(dirname "$file")
    mkdir -p "$dir"
    cp "$file" "$dir"
  done
)
EOF


%install
install -d %{buildroot}%mock_config_overrides
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild/results
install -d %{buildroot}%{_sharedstatedir}/copr-rpmbuild/workspace

install -d %{buildroot}%{_bindir}
install -m 755 main.py %{buildroot}%{_bindir}/copr-rpmbuild
install -m 644 main.ini %{buildroot}%{_sysconfdir}/copr-rpmbuild/main.ini
install -m 644 mock.cfg.j2 %{buildroot}%{_sysconfdir}/copr-rpmbuild/mock.cfg.j2
install -m 644 rpkg.conf.j2 %{buildroot}%{_sysconfdir}/copr-rpmbuild/rpkg.conf.j2
install -m 644 mock-source-build.cfg.j2 %{buildroot}%{_sysconfdir}/copr-rpmbuild/
install -m 644 mock-custom-build.cfg.j2 %{buildroot}%{_sysconfdir}/copr-rpmbuild/
install -m 644 copr-rpmbuild.yml %{buildroot}%{_sysconfdir}/copr-rpmbuild/copr-rpmbuild.yml

cat <<EOF > %buildroot%mock_config_overrides/README
Contents of this directory is used by %_bindir/copr-update-builder script.
When the script is executed, all files and directories (recursively) from here
are automatically copied to /etc/mock directory.  The files in /etc/mock are
overwritten if they already exist.
EOF

install -d %{buildroot}%{_mandir}/man1
install -p -m 644 man/copr-rpmbuild.1 %{buildroot}/%{_mandir}/man1/
install -p -m 755 bin/copr-builder %buildroot%_bindir
install -p -m 755 bin/copr-builder-cleanup %buildroot%_bindir
install -p -m 755 bin/copr-sources-custom %buildroot%_bindir
install -p -m 755 bin/copr-rpmbuild-cancel %buildroot%_bindir
install -p -m 755 bin/copr-rpmbuild-log %buildroot%_bindir
install -p -m 755 bin/copr-rpmbuild-loggify %buildroot%_bindir

name="%{name}" version="%{version}" summary="%{summary}" %py_install

install -p -m 755 copr-update-builder %buildroot%_bindir

(
  cd builder-hooks
  find -name README | while read line; do
    dir=%buildroot%_sysconfdir"/copr-builder/hooks/$(dirname "$line")"
    mkdir -p "$dir"
    install -p -m 644 "$line" "$dir"
  done
)


%files
%{!?_licensedir:%global license %doc}
%license LICENSE

%sitelib/copr_rpmbuild*

%{_bindir}/copr-rpmbuild*
%{_bindir}/copr-sources-custom
%{_mandir}/man1/copr-rpmbuild.1*

%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild
%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild/results
%dir %attr(0775, root, mock) %{_sharedstatedir}/copr-rpmbuild/workspace

%dir %{_sysconfdir}/copr-rpmbuild
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/main.ini
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/mock.cfg.j2
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/rpkg.conf.j2
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/mock-source-build.cfg.j2
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/mock-custom-build.cfg.j2
%config(noreplace) %{_sysconfdir}/copr-rpmbuild/copr-rpmbuild.yml

%files -n copr-builder
%license LICENSE
%_bindir/copr-builder
%_bindir/copr-update-builder
%_bindir/copr-builder-cleanup
%_sysconfdir/copr-builder
%dir %mock_config_overrides
%doc %mock_config_overrides/README


%changelog
* Wed Oct 02 2024 Jiri Kyjovsky <j1.kyjovsky@gmail.com> 1.0-1
- Specify snippets to mock config via copr-rpmbuild config file
- Increase the custom method timeout to 90 minutes
- Use new dist-git-client instead of copr one
- Add diff.txt file for fedora review
- When `copr-builder release` set timestamp 0

* Tue May 21 2024 Jakub Kadlcik <frostyx@email.cz> 0.73-1
- Remove static methods from tests

* Sat Mar 16 2024 Pavel Raiskup <praiskup@redhat.com> 0.72-1
- don't clean after builds with user ssh access

* Fri Mar 01 2024 Pavel Raiskup <praiskup@redhat.com> 0.71-1
- don't set bootstrap_image_ready for rawhide
- no Jinja-vars in config_opts keys (mock-core-configs 40.2 compat)
- allow user SSH to builders
- fix copr-rpmbuild --dump-configs
- install copr-distgit-client with copr-rpmbuild

* Thu Nov 23 2023 Pavel Raiskup <praiskup@redhat.com> 0.70-1
- collect and compress fedora-review logs after run
- use Copr custom macros when parsing the specfile

* Tue Aug 15 2023 Pavel Raiskup <praiskup@redhat.com> 0.69-1
- require python-specfile (in new enough) version, and use it for specfile
  parsing instead of parsing the metadata from SRPMs
- make sure we have (also) the latest DNF5 on builders
- override disttag macro to None
- make sure detected epoch is int() or None
- build RPMs in one Mock step, instead of two (SRPM and then RPM)
- use Mock's bootstrap_image_ready for the custom build (Mock 5.0+ required)
- store review.json generated by fedora-review into the result directory
- better/more verbose logging in the results.json generator
- drop dependency on simplejson
- repeatedly try to download files from lookaside cache
- moving the package NEVRA parsing to from backend here into copr-rpmbuild
- priority=X support added for the Copr repository itself
- query exclusivearch and excludearch from the specfile, and store into results.json

* Tue May 23 2023 Jakub Kadlcik <frostyx@email.cz> 0.68-1
- Fix python3-backoff dependency

* Mon May 22 2023 Jakub Kadlcik <frostyx@email.cz> 0.67-1
- Add loggs to python-backoff decorator
- Set git.safe_directory as repo rootdir
- Explain how to reproduce the build locally
- Retry only git clone without checkouting
- Use git checkout instead of switch but ignore files

* Tue Apr 04 2023 Jiri Kyjovsky <j1.kyjovsky@gmail.com> 0.66-1
- Ise 'git switch', not 'git checkout'

* Wed Mar 22 2023 Jiri Kyjovsky <j1.kyjovsky@gmail.com> 0.65-1
- Add basic "clone" method
- Define some copr-specific environment variables

* Wed Jan 25 2023 Jakub Kadlcik <frostyx@email.cz> 0.64-1
- Add runtime dependency for python-backoff

* Tue Jan 24 2023 Jakub Kadlcik <frostyx@email.cz> 0.63-1
- Retry when copr-distgit is temporarily down
- Don't print traceback for 404 errors on SRPM download
- Decode URL encoded characters such as %%5E into caret
- Use SPDX license

* Sat Nov 26 2022 Jakub Kadlcik <frostyx@email.cz> 0.62-1
- migrate from pipes to shlex
- move to GitHub home page
- use repos from task for custom method
- switch to template for custom method
- strip trailing / from clone url

* Tue Aug 09 2022 Jakub Kadlcik <frostyx@email.cz> 0.61-1
- rpmbuild: specify some optional parameters for pyp2spec

* Wed Jul 27 2022 Pavel Raiskup <praiskup@redhat.com> 0.60-1
- fix source build detection needed for %%dist hacks

* Tue Jul 26 2022 Jakub Kadlcik <frostyx@email.cz> 0.59-1
- Add support for pyp2spec generator
- Define copr-specific macros for make_srpm method
- Define copr-specific macros for custom builds
- Determine SRPM builds by having source_type
- Undefine %%dist for SRPM builds
- Build SRPM from DistGit even with missing sources
- Drop an unused extract_srpm method

* Tue Jun 21 2022 Jakub Kadlcik <frostyx@email.cz> 0.58-1
- Fix make_srpm with new git
- Define copr-specific macros also for SRPM builds
- SCM method to clone recursively

* Mon Apr 11 2022 Jakub Kadlcik <frostyx@email.cz> 0.57-1
- Don't fail a build because of fedora-review
- Require a new version of fedora-review tool

* Fri Mar 18 2022 Pavel Raiskup <praiskup@redhat.com> 0.56-1
- copr-distgit-client: document the configuration for the dist-git subpackage
- copr-distgit-client: add the centos-stream configuration
- copr-distgit-client: new --forked-from option that allows builds from (any) forks
- rpmbuild: support for remote refs in committish (PR#2049 and PR#2081)

* Wed Feb 02 2022 Silvie Chlupova <schlupov@redhat.com> 0.55.2-1
- don't depend on autospec in EL9
- use config file in *-cancel and *-log scripts
- better PID for copr-rpmbuild-log
- keep the required common version on one place

* Wed Nov 10 2021 Silvie Chlupova <schlupov@redhat.com> 0.55.1-1
- Fixing copr-common version

* Wed Nov 10 2021 Silvie Chlupova <schlupov@redhat.com> 0.54.2.dev-1
- Fixup ACR handling
- Always set 'requests.get()' timeout
- Drop ANSI escape sequences from logs again
- Install fedora-review-plugin-java

* Mon Oct 11 2021 Pavel Raiskup <praiskup@redhat.com> 0.54-1
- %%auto{spec,changelog} support for DistGit method

* Thu Sep 30 2021 Silvie Chlupova 0.53-1
- rpmbuild: require the latest version of gem2rpm
- rpmbuild: update main.ini and rpkg.conf.j2 for rpkg 3.0 compatibility

* Tue Jun 15 2021 Pavel Raiskup <praiskup@redhat.com> 0.52-1
- provide the build results as results.json
- ensure the latest *rpm macros packages on builder

* Thu May 20 2021 Pavel Raiskup <praiskup@redhat.com> 0.51-1
- don't cleanup resultdir itself, only contents

* Tue Apr 27 2021 Jakub Kadlcik <frostyx@email.cz> 0.50-1
- rpmbuild: properly cleanup mock bootstrap
- rpmbuild: document the options in main.ini file
- rpmbuild: clarify and encapsulate Provider's directories
- rpmbuild: cleanup the Provider class API
- rpmbuild: better error for cleanup issue#1258

* Tue Mar 16 2021 Pavel Raiskup <praiskup@redhat.com> 0.49-1
- don't require fedora_review tag in task json

* Tue Mar 16 2021 Pavel Raiskup <praiskup@redhat.com> 0.48-1
- support running the fedora-review tool

* Tue Feb 09 2021 Pavel Raiskup <praiskup@redhat.com> 0.47-1
- scm method to not enforce 'master'

* Tue Feb 09 2021 Pavel Raiskup <praiskup@redhat.com> 0.46-1
- rpmbuild: don't checkout master when not requested

* Wed Jan 20 2021 Pavel Raiskup <praiskup@redhat.com> 0.45-1
- allow disabling modules in the buildroot
- fix background process (group) cancellation

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 0.44-1
- don't override isolation config by default
- require appropriate common version
- repeatedly send requests to frontend until they succeed

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 0.43-1
- new --isolation copr option in Copr
- require up2date copr-common

* Thu Nov 12 2020 Pavel Raiskup <praiskup@redhat.com> 0.42-1
- require podman on all builders
- move the whole copr-distgit-client below copr-builder
- git module name to define the lookaside download url

* Wed Nov 11 2020 Pavel Raiskup <praiskup@redhat.com> 0.41-1
- non-dev version and release

* Mon Nov 09 2020 Jakub Kadlcik <frostyx@email.cz> 0.40.2.dev-1
- rpmbuild: fix chroot_scan copying
- rpmbuild: fix mock --buildsrpm option
- rpmbuild: set Vendor metadata for builds
- rpmbuild: use mock --srpmbuild for spec file uploads
- frontend, cli, python, rpmbuild: better bootstrap config
- beaker-tests, cli, frontend, python, rpmbuild: add option to config bootstrap
- all: run pytest with -vv in package build
- rpmbuild: disable source fetch for the dist-git method
- rpmbuild: catch FileNotFound on el6 correctly
- rpmbuild: drop SourceType and rely on BuildSourceEnum
- common, cli, python, rpmbuild, frontend, backend: DistGit source method
- rpmbuild: fix Provider class design
- rpmbuild: inform about testsuite coverage

* Mon Aug 10 2020 Pavel Raiskup <praiskup@redhat.com> 0.40-1
- provide the "dynamic" %%buildtag
- define config_opts['root'] mock config for make srpm method

* Tue Jun 09 2020 Pavel Raiskup <praiskup@redhat.com> 0.39-1
- more work delegate to builder scripts from backend
- don't delete the "old" .rpmnew files
- fix macro in comment (rpmlint)

* Fri Apr 03 2020 Pavel Raiskup <praiskup@redhat.com> 0.38-1
- do not scrub mock caches, to re-use dnf/yum caches
- scrub chroot and bootstrap chroot when build is done
- invent /etc/copr-rpmbuild/mock-config-overrides config dir
- print human friendly error for nonexisting subdirectory
- less verbose error output

* Wed Feb 19 2020 Pavel Raiskup <praiskup@redhat.com> 0.37-1
- add tests that we properly cleanup tmp directories
- mock 2.0: config s/use_bootstrap_container/use_bootstrap/
- mock 2.0: disable bootstrap chroot for make_srpm method
- put complete set of mock configs to resultdir, in tarball
- mock 2.0: use dnf.conf/yum.conf automatically
- make sure builders have the latest libsolv

* Thu Feb 06 2020 Pavel Raiskup <praiskup@redhat.com> 0.36-1
- do not fail if we can not remove temporary we created

* Wed Feb 05 2020 Pavel Raiskup <praiskup@redhat.com> 0.35-1
- mock config - module_enable needs to be an array
- catch FileExistsError in python2 compatible manner

* Wed Feb 05 2020 Pavel Raiskup <praiskup@redhat.com> 0.34-1
- don't create unnecessary tmp directory
- prefix the name of all copr-rpmbuild temporary directory
- properly cleanup after obtaining sources, and build failure
- add support for mock's module_enable

* Fri Dec 06 2019 Pavel Raiskup <praiskup@redhat.com> 0.33-1
- rpmbuild: skip_if_unavailable=1 for non-ACR projects

* Wed Dec 04 2019 Pavel Raiskup <praiskup@redhat.com> 0.32-1
- fix custom method for F31's nspawn (--console=pipe is not default)
- buildrequires: add qemu-user-static for building armhfp
- module_hotfixes support
- define %%copr_username again on copr builders
- skip_if_unavailable=False for copr_base

* Wed Jul 31 2019 Pavel Raiskup <praiskup@redhat.com> 0.31-1
- rpmbuild: make sure librepo/libdnf is always up2date

* Mon Jul 29 2019 Pavel Raiskup <praiskup@redhat.com> 0.30-1
- drop SCM parameters from copr-rpmbuild
- implement --task-file and --task-url parameters (issue#517)

* Fri Jun 07 2019 Pavel Raiskup <praiskup@redhat.com> 0.29-1
- clean /var/cache/mock automatically

* Mon May 27 2019 Pavel Raiskup <praiskup@redhat.com> 0.28-1
- don't use --private-users=pick

* Mon May 20 2019 Pavel Raiskup <praiskup@redhat.com> 0.27-1
- enforce use_host_resolv
- require even nosync.i686

* Tue May 14 2019 Pavel Raiskup <praiskup@redhat.com> 0.26-1
- [rpmbuild] ansible_python_interpreter: /usr/bin/python3
- [rpmbuild] install dnf-utils instead of yum-utils on Fedora
- [rpmbuild] builder: document some of the requires
- [rpmbuild] builder: merge dependencies from playbooks
- [rpmbuild] don't define %%_disable_source_fetch
- [rpmbuild] use six.moves.urllib.parse
- [rpmbuild] download srpm/spec if url contains query string

* Wed Apr 24 2019 Jakub Kadlčík <frostyx@email.cz> 0.25-1
- remove dependency on python3-configparser

* Thu Jan 10 2019 Miroslav Suchý <msuchy@redhat.com> 0.24-1
- create copr-rpmbuild-all subpackage
- Fix `copr-cli mock-config` after switching to APIv3 by preprocessing repos on
frontend
- add python-srpm-macros
- print nice error when suggested package is not installed
- tito and rpkg should be required only by copr-builder
- create copr-builder
- let mock rootdir generation on clients
- rename repos 'url' attribute to 'baseurl'
- provide repo_id in project chroot build config
- Allow per-package chroot-blacklisting by wildcard patterns
- preprocess repo URLs on frontend
- revert back Suggests
- drop "downloading" state
- allow blacklisting packages from chroots

* Fri Oct 19 2018 Miroslav Suchý <msuchy@redhat.com> 0.23-1
- /usr/bin/env python3 -> /usr/bin/python3
- nicer live logs

* Tue Sep 18 2018 clime <clime@redhat.com> 0.22-1
- make spec_template for pypi in build config optional
- EPEL6 fixes
- EPEL7 fixes
- Merge #393 `use git_dir_archive instead of git_dir_pack`
- handle non-existent chroot for given build-id
- fix requests exception
- add support for copr://
- generate some sane mock root param when --copr arg is used
- add --copr arg to build/dump-configs against copr+chroot build defs
- pg#251 Make it possible for user to select pyp2rpm template
- --dump-configs option

* Wed Aug 29 2018 clime <clime@redhat.com> 0.21-1
- [rpmbuild] add possibility to supply rpkg.conf in top-level scm dir
- packaging: Python 2/3, RHEL/Fedora fixes

* Mon Aug 06 2018 clime <clime@redhat.com> 0.20-1
- for py3 use unittest.mock, otherwise mock from python2-mock
- avoid subprocess.communicate(timeout=..)
- BlockingIOError, IOError -> OSError
- hack for optional argparse subparser
- fix shebang for epel7
- use fcntl.lockf (works with python 2.7, too)
- make copr-rpmbuild installable/buildable on el7

* Fri May 18 2018 clime <clime@redhat.com> 0.19-1
- add --with/--without rpmbuild options for build chroot

* Thu Apr 26 2018 Dominik Turecek <dturecek@redhat.com> 0.18-1
- rpkg deployment into COPR - containers + releng continuation
- updates for latest upstream rpkg
- update rpkg.conf.j2 to the latest rpkg version
- s|/bin/env|/usr/bin/env| in shebang

* Fri Feb 23 2018 clime <clime@redhat.com> 0.17-1
- remove unused requires and rename rpm-python3 to python3-rpm
- switch copr-sources-custom to python3 shebang
- keep tmpfs data mounted acros mock invocations for custom method

* Mon Feb 19 2018 clime <clime@redhat.com> 0.16-1
- new custom source method

* Sun Feb 18 2018 clime <clime@redhat.com> 0.15-1
- add support for fetch_sources_only in task defition
- allow building rpms from srpms fetched by providers, 
- extend cmdline with scm submode
- optionally set a priority for a repo
- add test for create_rpmmacros + refactoring
- allow only https and ftps protocols for source fetch

* Thu Jan 11 2018 clime <clime@redhat.com> 0.14-1
- copy out dnf and yum logs when using mock
- introspection and --version argument

* Mon Dec 11 2017 clime <clime@redhat.com> 0.13-1
- update man pages
- update help
- exclude 'tests' in package auto-discovery
- don't install additional stuff into bootstrap of custom buildroot
- Bug 1514221 - Copr fails to clone the repository. Build fails.

* Thu Nov 09 2017 clime <clime@redhat.com> 0.12-1
- fix get_mock_uniqueext call
- fortify make_srpm
- add '--private-users=pick' to make_srpm container to improve
  security
- compatibility with rpkg-client-0.11
- add config for src.stg.fedoraproject.org into default rpmbuild
  config
- fix download url for new rpkg-client version

* Wed Oct 18 2017 clime <clime@redhat.com> 0.11-1
- provide option to root spec file path in SCM with '/'
- fix exception raising in scm provider
- make command debug info nicer
- print task structure in the beginning even without -v
- add listdir after srpm production
- some Git backends do not support --depth
- remove unused run method
- checkout master by default
- with limited depth, we need to clone with --no-single-branch
- remove original perl script and mock config for it
- remove no longer needed options from rpkg.conf.j2
- SCM source types unification
- apply continuing line filtering from f4561c149893
- increase clone depth to address pag#129 SCM source type error

* Tue Sep 26 2017 clime <clime@redhat.com> 0.10-1
- use https for copr frontend in default config
- Make error message when the build task does not exist more user-
  friendly
- add --build-id switch instead of positional argument
- do not fail when lockfile does not exist
- change arguments to build_id and chroot
- remove lockfile import
- remove unused requires:
- remove unused variables in try-excepts
- #138 FileExistsError: [Errno 17] File exists: '/var/lib/copr-
  rpmbuild/lockfile.lock'

* Fri Sep 15 2017 clime <clime@redhat.com> 0.9-1
- copy spec file to the result dir to have a quick overview on the
  package

* Thu Sep 14 2017 clime <clime@redhat.com> 0.8-1
- provide more verbose exception logging
- take timeout into account
- fix downstream/upstream condition
- set also use_host_resolv to False if enable_net is False
- when building rpms, prebuild srpm in mock chroot

* Thu Sep 07 2017 clime <clime@redhat.com> 0.7-1
- rewrite to python
- build-srpm from upstream ability added
* Fri Jul 07 2017 clime <clime@redhat.com> 0.6-1
- support for source downloading

* Tue Jun 27 2017 clime <clime@redhat.com> 0.5-1
- use Perl Virtual naming for Requires

* Fri Jun 23 2017 clime <clime@redhat.com> 0.4-1
- use dnf.conf for custom-1 chroots
- also copy .spec to the build result directory
- raise curl timeout for downloading sources to be built
- changes according to review bz#1460630
- rpmbuild_networking option is now used to enable/disable net

* Wed Jun 14 2017 clime <clime@redhat.com> 0.3-1
- support for mock's bootstrap container
- check each line of sources file separately
- allow multiple sources and use current dir for mock as source dir
- also check for value of repos first before array referencing in mockcfg.tmpl
- handle null for buildroot_pkgs in mockcfg.tmpl

* Fri Jun 09 2017 clime <clime@redhat.com> 0.2-1
- new package built with tito

* Fri Jun 02 2017 clime <clime@redhat.com> 0.1-1
- Initial version
