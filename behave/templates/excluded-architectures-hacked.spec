Name:		excluded-architectures-hacked
Version:	1
Release:	1%{?dist}
Summary:	A dummy package
License:	GPLv3+
URL:		http://example.com/

Source0:	https://raw.githubusercontent.com/praiskup/quick-package/master/README.xz

# Only one build per distro, namely
#       fedora-rawhide-x86_64
#       fedora-latest-aarch64
#       epel-10-ppc64le

%if 0%{?rhel} >= 9
ExclusiveArch: x86_64 ppc64le
%else
ExclusiveArch: x86_64 aarch64
%endif

%if 0%{?fedora} > @FEDORA_LATEST@
ExcludeArch: aarch64
%endif
%if 0%{?fedora} && 0%{?fedora} <= @FEDORA_LATEST@
ExcludeArch: x86_64
%endif
%if 0%{?rhel} && 0%{?rhel} <= 100
ExcludeArch: x86_64
%endif


%description
Description for the %name package that is used for various testing tasks.


%prep


%build


%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/%{_pkgdocdir}
xz -d %{SOURCE0} --stdout > $RPM_BUILD_ROOT/%{_pkgdocdir}/README


%files
%doc %{_pkgdocdir}/README

%changelog
* Thu Jun 05 2014 Pavel Raiskup <praiskup@redhat.com> - 0-1
- does nothing!
