%global _description\
Schemas for messages sent by Copr project, as described on \
fedora-messaging documentation page \
https://fedora-messaging.readthedocs.io/en/latest/messages.html#schema \
\
Package also provides several convenience methods for working with \
copr messages.

Name:       {{{ git_dir_name }}}
Version:    {{{ git_dir_version }}}
Release:    1%{?dist}
Summary:    Abstraction for Copr messaging listeners/publishers

License:    GPLv2+
URL:        https://pagure.io/copr/copr
# Source is created by:
# git clone https://pagure.io/copr/copr.git
# git checkout {{{ cached_git_name_version }}}
# cd copr/fedora-messaging
# rpkg spec --sources
Source0:    {{{ git_dir_archive }}}

BuildArch:  noarch

Requires:      wget


BuildRequires: asciidoc
BuildRequires: libxslt
BuildRequires: util-linux

BuildRequires: python3-copr-common
BuildRequires: python3-devel
BuildRequires: python3-fedora-messaging
BuildRequires: python3-pytest
BuildRequires: python3-sphinx

%description %_description


%package -n python3-%name
Summary: %summary
Provides: %name = %version
%{?python_provide:%python_provide python3-%{name}}

Requires: python3-copr-common
Requires: python3-fedora-messaging

%description -n python3-%name %_description

%package -n python3-%name-doc
Summary: Code documentation for copr messaging

%description -n python3-%name-doc %_description

This package contains documentation for copr-messaging.


%prep
%setup -q


%build
%py3_build
PYTHONPATH=${PWD} sphinx-build-3 docs html
rm -rf html/.{doctrees,buildinfo}


%install
%py3_install


%check
./runtests.sh


%files -n python3-%name
%license LICENSE
%doc README.md
%python3_sitelib/copr_messaging
%python3_sitelib/copr_messaging*egg-info

%files -n python3-%name-doc
%license LICENSE
%doc html


%changelog
{{{ git_dir_changelog }}}
