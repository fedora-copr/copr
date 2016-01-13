Summary: Remove failed and obsolete succeeded builds (with the associated packages) from a copr repository.
Name: copr-prune-repo
Version: 1.2
Release: 1%{?dist} 

# Source is created by:
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/copr-prune-repo
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

License: GPLv2+
BuildArch: noarch
BuildRequires: python3-devel

# todo: remove
Requires: yum-utils

%description
Removes failed and obsolete succeeded builds (with the associated packages)
from a copr repository. The build directories should belong to `copr` user and
contain `build.info`, `success` or `fail` files, otherwise nothing gets deleted.
The repository needs to be recreated manually afterwards with createrepo.

%prep
%setup -q

%build
%py3_build

%install
%py3_install
install -d $RPM_BUILD_ROOT/%{_mandir}/man1
cp man/man1/copr_prune_repo.1 $RPM_BUILD_ROOT%{_mandir}/man1/

%files
%{python3_sitelib}/*
%{_bindir}/copr_prune_repo.py
%doc %{_mandir}/man1/copr_prune_repo.1*

%changelog
* Wed Jan 13 2016 clime <clime@redhat.com> 1.2-1
- changes in .spec according to package review
* Thu Jan 07 2016 Michal Novotny <clime@redhat.com> 1.2-1
- tests fix

* Thu Jan 07 2016 Michal Novotny <clime@redhat.com> 1.1-1
- new package built with tito

* Thu Jan 07 2016 Michal Novotny <clime@redhat.com> 1.0-1
- Package init
