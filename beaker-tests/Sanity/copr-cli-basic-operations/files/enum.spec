Name:           enum
Version:        1.1
Release:        1%{?dist}
Summary:        Seq- and jot-like enumerator

License:        BSD-3-Clause
URL:            https://fedorahosted.org/enum
# if this url stop existing, it'll sure be somewhere on the internet ^.^
Source0:        https://praiskup.fedorapeople.org/courses/packaging/%{name}-%{version}.tar.bz2

BuildRequires: gcc
BuildRequires: make
BuildRequires: asciidoc

%description
Utility enum enumerates values (numbers) between two values, possibly
further adjusted by a step and/or a count, all given on the command line.
Before printing, values are passed through a formatter. Very fine control
over input interpretation and output is possible.

%prep
%autosetup


%build
%configure
%make_build


%install
%make_install


%files
%license COPYING
%doc ChangeLog
%{_bindir}/enum
%{_mandir}/man1/enum.1*


%changelog
* Mon Sep 30 2024 Jiri Kyjovsky <j1.kyjovsky@gmail.com>
- Initial package
