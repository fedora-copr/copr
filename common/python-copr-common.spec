{{{ export srcname=copr-common }}}
%global srcname {{{ printf "$srcname" }}}

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
Source0:    {{{ git_dir_archive }}}

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
%setup -q


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
{{{ git_changelog since_tag="python-$srcname-0.3-1" }}}

* Thu Mar 22 2018 Dominik Turecek <dturecek@redhat.com> 0.2-1
- [common] fix spec file

* Mon Mar 19 2018 Dominik Turecek <dturecek@redhat.com> 0.1-1
- create python-copr-common package
