Name:       example
Version:	1.0.9
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
%(find-debuginfo.sh)

%changelog

