Name:       pkg-with-macros
Version:    1.0
Release:    1%{?dist}
Summary:    Testing spec file
License:    GPLv2
URL:        https://github.com/fedora-copr/copr
ExcludeArch: aarch64 %{power64} s390x


%description
Test spec file with macros

%files

%build

%check

%changelog
* Thu May 12 2022 Jakub Kadlcik <jkadlcik@redhat.com> - 1.0-1
- Initial version
