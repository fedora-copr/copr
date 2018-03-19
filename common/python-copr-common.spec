%global srcname copr-common

%if 0%{?rhel} < 7 && 0%{?rhel} > 0
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%global __python2 %{__python}
%endif

%if 0%{?fedora} || 0%{?rhel} >= 8
%global with_python3 1
%else
%global with_python3 0
%endif

%if 0%{?fedora} >= 28 || 0%{?rhel} >= 8
%global with_python2 0
%else
%global with_python2 1
%endif

Name:       python-%{srcname}
Version:    0.1
Release:    1%{?dist}
Summary:    Python code used by Copr

License:    GPLv2+
URL:        https://pagure.io/copr/copr
# Source is created by
# git clone https://pagure.io/copr/copr.git
# cd copr/common
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

BuildArch: noarch
BuildRequires: python2-devel
BuildRequires: python3-devel

%global _description\
COPR is lightweight build system. It allows you to create new project in WebUI,\
and submit new builds and COPR will create yum repository from latest builds.\
\
This package contains python code used by other Copr packages. Mostly\
useful for developers only.\


%description %_description

%if 0%{?with_python2}
%package -n python2-%{srcname}
Summary: %{summary}
%{?python_provide:%python_provide python2-%{srcname}}
%description -n python2-%{srcname} %_description
%endif # with_python2

%if 0%{?with_python3}
%package -n python3-%{srcname}
Summary: %{summary}
%{?python_provide:%python_provide python3-%{srcname}}
%description -n python3-%{srcname} %_description
%endif # with_python3

%prep
rm -rf *.pyc *.pyo

%setup -q
%build
%if 0%{?with_python3}
%py3_build
%endif # with_python3

%if 0%{?with_python2}
%py2_build
%endif # with_python2

%install
%if 0%{?with_python2}
%py2_install
%endif # with_python2

%if 0%{?with_python3}
%py3_install
%endif # with_python3

%check

%if 0%{?with_python3}
%files -n python3-%{srcname}
%license LICENSE
%{python3_sitelib}/*
%endif # with_python3

%if 0%{?with_python2}
%files -n python2-%{srcname}
%license LICENSE
%{python_sitelib}/*
%endif # with_python2

%changelog
* Mon Mar 19 2018 Dominik Turecek <dturecek@redhat.com> 0.1-1
- create python-copr-common package

