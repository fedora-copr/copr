# SPEC file overview:
# https://docs.fedoraproject.org/en-US/quick-docs/creating-rpm-packages/#con_rpm-spec-file-overview
# Fedora packaging guidelines:
# https://docs.fedoraproject.org/en-US/packaging-guidelines/


Name:      dist-git-client
Version:   1.1
Release:   0%{?dist}
Summary:   Get sources for RPM builds from DistGit repositories
BuildArch: noarch

License: GPL-2.0-or-later
URL:     https://github.com/release-engineering/dist-git.git
Source0: %name-%version.tar.gz

Requires: curl
Requires: /usr/bin/git

BuildRequires: python3-pytest
BuildRequires: python3-rpm-macros
BuildRequires: /usr/bin/argparse-manpage
BuildRequires: /usr/bin/git

%if 0%{?fedora} || 0%{?rhel} > 9
Requires: python3-rpmautospec
BuildRequires: python3-rpmautospec
%endif

%description
A simple, configurable python utility that is able to clone package sources from
a DistGit repository, download sources from the corresponding lookaside cache
locations, and generate source RPMs.

The utility is able to automatically map the .git/config clone URL into the
corresponding DistGit instance configuration.


%prep
%setup -q


%build



%install
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_mandir}/man1
install -d %{buildroot}%{_sysconfdir}/dist-git-client
install -d %{buildroot}%{python3_sitelib}
install -p -m 755 bin/dist-git-client %buildroot%_bindir
argparse-manpage --pyfile dist_git_client.py \
    --function _get_argparser \
    --author "Copr Team" \
    --author-email "copr-team@redhat.com" \
    --url %url --project-name Copr \
> %{buildroot}%{_mandir}/man1/dist-git-client.1
install -p -m 644 etc/default.ini \
    %{buildroot}%{_sysconfdir}/dist-git-client
install -p -m 644 dist_git_client.py %{buildroot}%{python3_sitelib}


%check
PYTHON=python3 ./run_tests.sh -vv --no-coverage


%files
%license LICENSE
%_bindir/dist-git-client
%_mandir/man1/dist-git-client.1*
%dir %_sysconfdir/dist-git-client
%config %_sysconfdir/dist-git-client/default.ini
%python3_sitelib/dist_git_client.*
%python3_sitelib/__pycache__/dist_git_client*


%changelog
* Thu Jun 06 2024 Pavel Raiskup <praiskup@redhat.com> 1.1-0
- new package built with tito
