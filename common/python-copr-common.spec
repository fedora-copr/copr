{{{ export srcname=copr-common }}}
%global srcname {{{ printf "$srcname" }}}

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

Name:       {{{ git_name name="python-$srcname" }}}
Version:    {{{ git_version }}}
Release:    1%{?dist}
Summary:    Python code used by Copr

License:    GPLv2+
URL:        https://pagure.io/copr/copr
# Source is created by
# git clone https://pagure.io/copr/copr.git
# git checkout {{{ cached_git_name_version }}}
# cd copr/common
# rpkg spec --sources
Source0:    {{{ git_dir_pack }}}

BuildArch: noarch

%if 0%{?with_python2}
BuildRequires: python2-devel
%endif # with_python2

%if 0%{?with_python3}
BuildRequires: python3-devel
%endif # with_python3

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
version="%{version}" %py3_build
%endif # with_python3

%if 0%{?with_python2}
version="%{version}" %py2_build
%endif # with_python2

%install
%if 0%{?with_python2}
version="%{version}" %py2_install
%endif # with_python2

%if 0%{?with_python3}
version="%{version}" %py3_install
%endif # with_python3

%if 0%{?with_python3}
%files -n python3-%{srcname}
%license LICENSE
%{python3_sitelib}/*
%endif # with_python3

%if 0%{?with_python2}
%files -n python2-%{srcname}
%license LICENSE
%{python2_sitelib}/*
%endif # with_python2

%changelog
{{{ git_changelog since_tag="python-$srcname-0.3-1" }}}

* Thu Mar 22 2018 Dominik Turecek <dturecek@redhat.com> 0.2-1
- [common] fix spec file

* Mon Mar 19 2018 Dominik Turecek <dturecek@redhat.com> 0.1-1
- create python-copr-common package
