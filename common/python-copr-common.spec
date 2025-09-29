%global srcname copr-common

Name:       python-copr-common
Version:    1.4
Release:    1%{?dist}
Summary:    Python code used by Copr

License:    GPL-2.0-or-later
URL:        https://github.com/fedora-copr/copr

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %name-%version.tar.gz

BuildArch: noarch

%if 0%{?rhel} > 10 || 0%{?fedora} > 42
BuildRequires: python3-devel
%else
BuildRequires: python3-devel
BuildRequires: python3-setuptools
%endif
BuildRequires: python3-pytest
BuildRequires: python3-requests
BuildRequires: python3-filelock
BuildRequires: python3-setproctitle

%global _description\
COPR is lightweight build system. It allows you to create new project in WebUI,\
and submit new builds and COPR will create yum repository from latest builds.\
\
This package contains python code used by other Copr packages. Mostly\
useful for developers only.\


%description %_description


%package -n python3-%{srcname}
Summary: %{summary}
%{?python_provide:%python_provide python3-%{srcname}}
%description -n python3-%{srcname} %_description


%if 0%{?rhel} > 10 || 0%{?fedora} > 42
%generate_buildrequires
%pyproject_buildrequires
%endif


%prep
%setup -q


%build
%if 0%{?rhel} > 10 || 0%{?fedora} > 42
version="%version" %pyproject_wheel
%else
version="%version" %py3_build
%endif


%install
%if 0%{?rhel} > 10 || 0%{?fedora} > 42
version=%version %pyproject_install
%else
version=%version %py3_install
%endif

%check
%{_bindir}/python3 -m pytest -vv tests


%files -n python3-%{srcname}
%license LICENSE
%{python3_sitelib}/*



%changelog
* Mon Sep 29 2025 Jakub Kadlcik <frostyx@email.cz> 1.4-1
- Increase the user SSH builder max expiration to 3 days

* Tue Sep 16 2025 Jakub Kadlcik <frostyx@email.cz> 1.3-1
- SafeRequest to retry upon error 408
- Handle unsuccessful Pulp requests

* Tue Aug 26 2025 Jakub Kadlcik <frostyx@email.cz> 1.2-1
- Specify reason for running createrepo
- Improve robustness and cooperation between backend and rpmbuild
- Remove license classifier
- Modernize specfile using pyproject macro

* Tue Mar 25 2025 Pavel Raiskup <praiskup@redhat.com> 1.1-1
- lock the pulp-redirect.txt file

* Wed Oct 02 2024 Jiri Kyjovsky <j1.kyjovsky@gmail.com> 1.0-1
- Drop support for rhel7 and rhel6

* Thu Aug 01 2024 Miroslav Suchý <msuchy@redhat.com> 0.25-1
- frontend, backend, common: don't limit the storage to pulp only

* Tue May 21 2024 Jakub Kadlcik <frostyx@email.cz> 0.24-1
- Fix chroot_to_branch default

* Fri Mar 15 2024 Pavel Raiskup <praiskup@redhat.com> 0.23-1
- make get_redis_connection to accept dict-like 'opts' argument

* Fri Mar 01 2024 Pavel Raiskup <praiskup@redhat.com> 0.22-1
- fix misleading warning for non-copr library consumers
- add `contextlib.nullcontext` function as EL8 compat
- limit stdout/stderr of ssh.run_expensive() commands
- use 'copr-common/<version>' as http user agent identifier
- changes needed to allow user SSH to builders

* Thu Nov 23 2023 Pavel Raiskup <praiskup@redhat.com> 0.21-1
- rename GroupWorkerLimit to HashWorkerLimit
- explicitly build-depend on python-six

* Tue Aug 15 2023 Pavel Raiskup <praiskup@redhat.com> 0.20-1
- move chroot_to_branch from frontend to copr-common
- redis authentication support added

* Tue May 23 2023 Jakub Kadlcik <frostyx@email.cz> 0.19-1
- Specfile compatibility with OpenEuler

* Tue Jan 24 2023 Jakub Kadlcik <frostyx@email.cz> 0.18-1
- Periodically dump the priority queue to a JSON file
- Use SPDX license

* Sat Nov 26 2022 Jakub Kadlcik <frostyx@email.cz> 0.17-1
- move to GitHub home page
- logging shouldn't affect stdout
- move dispatcher and background workers to copr-common
- scripts should log also timestamps etc when logging into file
- move setup_script_logger to copr-common

* Thu Oct 27 2022 Jakub Kadlcik <frostyx@email.cz> - 0.16.2.dev-1
- Add background_worker.py from backend
- Add get_redis_connection function
- Add Dispatcher, WorkerManager, and QueueTask classes
- Add WorkerLimit, PredicateWorkerLimit, and GroupWorkerLimit classes

* Sun Oct 02 2022 Jakub Kadlcik <frostyx@email.cz> - 0.16-1
- Add setup_script_logger function

* Tue Jun 21 2022 Jakub Kadlcik <frostyx@email.cz> 0.15-1
- Allow SafeRequest's timeout to be specified

* Wed Feb 02 2022 Silvie Chlupova <schlupov@redhat.com> 0.14-1
- Fixing copr-common version

* Wed Feb 02 2022 Silvie Chlupova <schlupov@redhat.com> 0.13.2.dev-1
- dist-git: python code for removing unused tarballs on dist-git server

* Wed Nov 10 2021 Silvie Chlupova <schlupov@redhat.com> 0.13.1-1
- Fixing copr-common version

* Wed Nov 10 2021 Silvie Chlupova <schlupov@redhat.com> 0.12.2.dev-1
- Always set 'requests.get()' timeout

* Tue Jun 15 2021 Pavel Raiskup <praiskup@redhat.com> 0.12-1
- new action type for automatically deleting pull-request CoprDirs

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 0.11-1
- add first tests for copr-common package
- repeatedly send requests to frontend until they succeed

* Mon Nov 30 2020 Pavel Raiskup <praiskup@redhat.com> 0.10-1
- ship LICENSE file in PyPI tarball

* Wed Nov 11 2020 Pavel Raiskup <praiskup@redhat.com> 0.9-1
- bump to non-devel version

* Mon Nov 09 2020 Jakub Kadlcik <frostyx@email.cz> 0.8.2.dev-1
- common, cli, python, rpmbuild, frontend, backend: DistGit source method
- common: RHEL6 fix for ModuleStatusEnum

* Tue Jun 09 2020 Pavel Raiskup <praiskup@redhat.com> 0.8-1
- non-devel version 0.8

* Tue May 05 2020 Jakub Kadlcik <frostyx@email.cz> 0.7-1
- add ActionResult (moved from backend package)
- add DefaultActionPriorityEnum
- add ActionPriorityEnum
- add run_tests.sh script and run pylint in it

* Wed Aug 28 2019 Pavel Raiskup <praiskup@redhat.com> 0.6-1
- enhanced ModuleStatusEnum (issue#607)

* Fri Jul 26 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Mon Feb 11 2019 Jakub Kadlčík <frostyx@email.cz> 0.5-1
- Add splitFilename function

* Fri Oct 19 2018 Miroslav Suchý <msuchy@redhat.com> 0.4-1
- sync common.BuildSourceEnum with helpers.BuildSourceEnum
- use git_dir_archive instead of git_dir_pack
- packaging: Python 2/3, RHEL/Fedora fixes

* Mon Aug 06 2018 clime <clime@redhat.com> 0.3-1
- %%{python_sitelib} → %%{python2_sitelib}
- fix git packing for python-copr, copr-common
- fix reading spec file values from setup.py
- rpkg deployment into COPR

* Thu Mar 22 2018 Dominik Turecek <dturecek@redhat.com> 0.2-1
- [common] fix spec file

* Mon Mar 19 2018 Dominik Turecek <dturecek@redhat.com> 0.1-1
- create python-copr-common package
