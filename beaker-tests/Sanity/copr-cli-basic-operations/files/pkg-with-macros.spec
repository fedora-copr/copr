# There is probably no way to assert that a macro is defined so we need to be
# creative. Many failures because of missing macros would happen when building
# an RPM package. In order to test that macros are defined when building a SRPM,
# we can for example have a conditional preamble.

%if 0%{?copr_username:1} && 0%{?copr_projectname:1}
Name:       pkg-with-macros
Version:    1.0
Release:    1%{?dist}
Summary:    Testing spec file
License:    GPLv2
URL:        https://github.com/fedora-copr/copr
%endif


%description
Test spec file with macros

%files

%build

%check

# Make sure that macros are defined when building the actual RPM package
%if 0%{?copr_username:1} && 0%{?copr_projectname:1}
# It's okay, macros are defined
%else
exit 1
%endif


%changelog
* Thu May 12 2022 Jakub Kadlcik <jkadlcik@redhat.com> - 1.0-1
- Initial version
