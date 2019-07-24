%global srcname copr-common

%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?_licensedir:%global license %%doc}
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%endif

%if 0%{?fedora} || 0%{?rhel} > 7
%global with_python3 1
%endif

%if 0%{?fedora} < 28 || 0%{?rhel} && 0%{?rhel} <= 7
%global with_python2 1
%endif

Name:       python-copr-common
Version:    0.5
Release:    1%{?dist}
Summary:    Python code used by Copr

License:    GPLv2+
URL:        https://pagure.io/copr/copr
Source0:    %pypi_source

BuildArch: noarch

%if %{with python2}
BuildRequires: python2-devel
BuildRequires: python-setuptools
%endif

%if %{with python3}
BuildRequires: python3-devel
BuildRequires: python3-setuptools
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
%setup -q -n %srcname-%version


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
