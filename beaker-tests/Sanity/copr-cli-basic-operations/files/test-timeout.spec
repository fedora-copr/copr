Name:		test-timeout
Version:	1.0
Release:	1%{?dist}
Summary:	Testing spec file for runtest-timeout.sh
License:	GPLv2
URL:		https://github.com/fedora-copr/copr

%description
Test timeout

%files

%build
while :
do
  sleep 1
done

%changelog
* Fri Sep 11 2020 Silvie Chlupova <schlupov@redhat.com> 1.0-1
- Initial version
