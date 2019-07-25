%global _description\
Schemas for messages sent by Copr project, as described on \
fedora-messaging documentation page \
https://fedora-messaging.readthedocs.io/en/latest/messages.html#schema \
\
Package also provides several convenience methods for working with \
copr messages.

Name:       copr-messaging
Version:    0.3
Release:    1%{?dist}
Summary:    Abstraction for Copr messaging listeners/publishers

License:    GPLv2+
URL:        https://pagure.io/copr/copr

# Source is created by:
# git clone %url && cd copr
# tito build --tgz --tag %name-%version-%release
Source0:    %name-%version.tar.gz

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
* Thu Jul 25 2019 Pavel Raiskup <praiskup@redhat.com> 0.3-1
- mention how to create Source0 tarball

* Wed Jul 24 2019 Pavel Raiskup <praiskup@redhat.com> 0.2-1
- apply review fixes (by Silvie)

* Wed Jul 17 2019 Pavel Raiskup <praiskup@redhat.com> 0.1-1
- copr_messaging: new package for working with copr messages
