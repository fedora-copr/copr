# update
Name:       example
Version:	1.0.8
Release:	1%{?dist}
Summary:	This is a simple example to test copr

Group:		Applications/File
License:	GPLv2+
URL:		http://github.com/example
Source0:	%{name}-%{version}.tar.gz

# simulated dependencies
#BuildRequires:  desktop-file-utils
#BuildRequires:  gtk2-devel gettext

%description
Simple example to demonstrate copr's abilites.


%prep
%setup -q


%build
make %{?_smp_mflags}


%install
install -d %{buildroot}%{_sbindir}
cp -a main %{buildroot}%{_sbindir}/main


%files
%doc

%{_sbindir}/main

%changelog
* Mon Oct 16 2017 clime <clime@redhat.com> 1.0.8-1
- update (clime@redhat.com)
- update (clime@redhat.com)
- update (clime@redhat.com)
- update (clime@redhat.com)
- update (clime@redhat.com)

* Tue Jun 20 2017 clime <clime@redhat.com> 1.0.7-1
- update (clime@redhat.com)
- UPdate (clime@redhat.com)

* Tue May 30 2017 clime <clime@redhat.com> 1.0.6-1
- update (clime@redhat.com)
- update (clime@redhat.com)
- test (clime@redhat.com)
- update (clime@redhat.com)
- update (clime@redhat.com)
- update (clime@redhat.com)
- update (clime@redhat.com)
- update (clime@redhat.com)
- update (clime@redhat.com)
- Remove BuildArch requirement (clime7@gmail.com)
- and yet another (clime@redhat.com)
- another webhook push try (clime@redhat.com)
- another try (clime@redhat.com)
- test change (clime@redhat.com)
- Trying to reproduce Bug 1334102. (clime@redhat.com)

* Wed Feb 24 2016 clime <clime@redhat.com> 1.0.5-1
- subpkg removed (clime@redhat.com)

* Thu Jan 21 2016 clime <clime@redhat.com> 1.0.4-1
- some comment

* Thu Jan 21 2016 clime <clime@redhat.com> 1.0.3-1
- subpkg added (experimental thing to play with COPR building system)

* Sun Dec 20 2015 clime <clime@redhat.com> 1.0.2-1
- spec file change 

* Sat Dec 19 2015 clime <clime@redhat.com> 1.0.1-1
- new package built with tito

* Sat Dec 15 2015 clime <clime@redhat.com> 1.0.0-1
- Initial version
