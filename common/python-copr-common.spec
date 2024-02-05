%global srcname copr-common

%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?_licensedir:%global license %%doc}
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%endif

%if 0%{?fedora} || 0%{?rhel} > 7 || 0%{?openEuler}
%global with_python3 1
%global __python %_bindir/python3
%endif

%if 0%{?fedora} && 0%{?fedora} < 28 || 0%{?rhel} && 0%{?rhel} <= 7
%global with_python2 1
%global __python %_bindir/python2
%endif

Name:       python-copr-common
Version:    0.21.1.dev1
Release:    1%{?dist}
Summary:    Python code used by Copr

License:    GPL-2.0-or-later
URL:        https://github.com/fedora-copr/copr

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %name-%version.tar.gz

BuildArch: noarch

%if %{with python2}
BuildRequires: python2-devel
BuildRequires: python-setuptools
BuildRequires: python-pytest
BuildRequires: python-mock
BuildRequires: python-requests
BuildRequires: python-six
%endif

%if %{with python3}
BuildRequires: python3-devel
BuildRequires: python3-setuptools
BuildRequires: python3-pytest
BuildRequires: python3-requests
BuildRequires: python3-six
%endif

%global _description\
COPR is lightweight build system. It allows you to create new project in WebUI,\
and submit new builds and COPR will create yum repository from latest builds.\
\
This package contains python code used by other Copr packages. Mostly\
useful for developers only.\


%description %_description


%if %{with python2}
%package -n python2-%{srcname}
Summary: %{summary}
%{?python_provide:%python_provide python2-%{srcname}}
%description -n python2-%{srcname} %_description
%endif


%if %{with python3}
%package -n python3-%{srcname}
Summary: %{summary}
%{?python_provide:%python_provide python3-%{srcname}}
%description -n python3-%{srcname} %_description
%endif


%prep
%setup -q
# Check that setup.py version matches our version
grep '"%version"' setup.py


%build
%if %{with python3}
version="%version" %py3_build
%endif

%if %{with python2}
version="%version" %py2_build
%endif


%install
%if %{with python3}
version=%version %py3_install
%endif

%if %{with python2}
version=%version %py2_install
%endif


%check
%{__python} -m pytest -vv tests


%if %{with python3}
%files -n python3-%{srcname}
%license LICENSE
%{python3_sitelib}/*
%endif


%if %{with python2}
%files -n python2-%{srcname}
%license LICENSE
%{python2_sitelib}/*
%endif


%changelog
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
