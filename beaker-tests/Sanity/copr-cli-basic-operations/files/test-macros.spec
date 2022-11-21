Name:		test-macros
Version:	1.0
Release:	1%{?dist}
Summary:	This is to test user-defined macros in buildroot
License:	GPLv2
URL:		https://github.com/fedora-copr/copr

%description
Lets print some macros here
MACRO: %{my_module_macro}
MACRO: %{my_second_macro}

%files

%changelog
* Thu Jun 22 2017 Jakub Kadlcik <jkadlcik@redhat.com> 1.0-1
- Initial version
