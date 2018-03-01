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

Name:       python-copr-common
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

BuildArch:  noarch

%global _description\
COPR is lightweight build system. It allows you to create new project in WebUI,\
and submit new builds and COPR will create yum repository from latest builds.\
\
This package contains python code used by other Copr packages. Mostly\
useful for developers only.\


%description %_description

%if 0%{?with_python2}
%package -n python2-copr-common
Summary: Python code used by Copr
%{?python_provide:%python_provide python2-copr-common}
%description -n python2-copr-common %_description
%endif # with_python2

%if 0%{?with_python3}
%package -n python3-copr-common
Summary: Python code used by Copr
%{?python_provide:%python_provide python3-copr-common}
%description -n python3-copr-common %_description
%endif # with_python3

%prep
%setup -q
%if 0%{?with_python3}
rm -rf %{py3dir}
cp -a . %{py3dir}
%endif # with_python3

%build
%if 0%{?with_python3}
pushd %{py3dir}
CFLAGS="%{optflags}" %{__python3} setup.py build
popd
%endif # with_python3

%if 0%{?with_python2}
CFLAGS="%{optflags}" %{__python2} setup.py build
%endif # with_python2

%install

%if 0%{?with_python3}
pushd %{py3dir}
%{__python3} setup.py install --skip-build --root %{buildroot}
find %{buildroot}%{python3_sitelib} -name '*.exe' | xargs rm -f
popd
%endif # with_python3

%if 0%{?with_python2}
%{__python2} setup.py install --skip-build --root %{buildroot}
find %{buildroot}%{python2_sitelib} -name '*.exe' | xargs rm -f
%endif # with_python2

%check
%if 0%{?with_python3}
%files -n python3-copr-common
%license LICENSE
%{python3_sitelib}/*
%endif # with_python3

%if 0%{?with_python2}
%files -n python2-copr-common
%license LICENSE
%{python_sitelib}/*
%endif # with_python2

%changelog
* Tue Mar 13 2018 Dominik Turecek <dturecek@redhat.com>
- created python-copr-common
