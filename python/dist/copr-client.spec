%define name copr-client
%define version 0.0.1
%define unmangled_version 0.0.1
%define unmangled_version 0.0.1
%define release 1

Summary: Python client for copr service
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{unmangled_version}.tar.gz
License: GPLv2+
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Valentin Gologuzov <vgologuz@redhat.com>
Url: http://fedorahosted.org/copr/

%description
Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories.

This part is a python client to the copr service.

%prep
%setup -n %{name}-%{unmangled_version} -n %{name}-%{unmangled_version}

%build
python setup.py build

%install
python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)
