Name:           %{pkg_name}
Version:        %{pkg_version}
Release:        %{pkg_release}
Summary:        COPR %{user}/%{copr} Repository Configuration

License:        GPLv2+
URL:            https://copr.fedoraproject.org/coprs/%{user}/%{copr}/
Source0:        https://copr.fedoraproject.org/coprs/frostyx/tracer/repo/%{chroot}/%{user}-%{copr}-%{chroot}.repo
BuildArch:      noarch


%description
This is configuration package for COPR repository %{user}/%{copr}

%prep
echo "Nothing to prep"

%build
echo "Nothing to build"

%install
mkdir -p %{buildroot}%{_sysconfdir}/yum.repos.d
%{__install} -p -m644 %{SOURCE0} \
    $RPM_BUILD_ROOT%{_sysconfdir}/yum.repos.d/%{repofile}

%files
%config(noreplace) %{_sysconfdir}/yum.repos.d/%{repofile}


%changelog
# @TODO
# - Initial package
