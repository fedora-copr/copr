%global debug_package %{nil}
Name:       example
Version:	1.0.13
Release:	1%{?dist}
Summary:	This is a simple example to test copr

Group:		Applications/File
License:	GPLv2+
URL:		http://github.com/example
Source0:	%{name}-%{version}.tar.gz

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
* Sun Feb 18 2018 clime <clime@redhat.com> 1.0.13-1
- disable debuginfo generation (clime@redhat.com)
- add find debuginfo (clime@redhat.com)
- add -g switch (clime@redhat.com)
- empty changelog (clime@redhat.com)
- update (clime@redhat.com)

* Sun Feb 18 2018 clime <clime@redhat.com>
- disable debuginfo generation (clime@redhat.com)
- add find debuginfo (clime@redhat.com)
- add -g switch (clime@redhat.com)
- empty changelog (clime@redhat.com)
- update (clime@redhat.com)

* Sun Feb 18 2018 clime <clime@redhat.com>
- disable debuginfo generation (clime@redhat.com)
- add find debuginfo (clime@redhat.com)
- add -g switch (clime@redhat.com)
- empty changelog (clime@redhat.com)
- update (clime@redhat.com)

* Sun Feb 18 2018 clime <clime@redhat.com>
- disable debuginfo generation (clime@redhat.com)
- add find debuginfo (clime@redhat.com)
- add -g switch (clime@redhat.com)
- empty changelog (clime@redhat.com)
- update (clime@redhat.com)


