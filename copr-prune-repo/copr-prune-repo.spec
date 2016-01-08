Summary: Remove failed and obsolete succeeded builds (with the associated packages) from a copr repository.
Name: copr-prune-repo
Version: 1.2
Release: 1%{?dist} 
Source0: %{name}-%{version}.tar.gz
License: GPLv2+
Group: Applications/Productivity
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: clime <micnovot@redhat.com>
Url: http://github.com/clime/copr-prune-repo
Requires: python3
Requires: yum-utils

%description
Removes failed and obsolete succeeded builds (with the associated packages) 
from a copr repository. The build directories should belong to `copr` user and 
contain `build.info`, `success` or `fail` files, otherwise nothing gets deleted.
The repository needs to be recreated manually afterwards with createrepo.

%prep
%setup -n %{name}-%{version}

%build
python3 setup.py build

%install
python3 setup.py install -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
install -d $RPM_BUILD_ROOT/%{_mandir}/man1
cp man/man1/copr_prune_repo.1 $RPM_BUILD_ROOT%{_mandir}/man1/

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)
%doc %{_mandir}/man1/copr_prune_repo.1*

%changelog
* Thu Jan 07 2016 clime <clime@redhat.com> 1.2-1
- tests fix (clime@redhat.com)

* Thu Jan 07 2016 clime <clime@redhat.com> 1.1-1
- new package built with tito

* Thu Jan 07 2016 Michal Novotny <micnovot@redhat.com> 1.0-1
- Package init
