Name:       example
Version:	1.0.1
Release:	1%{?dist}
Summary:	This is a simple example to test copr
BuildArch:  noarch

Group:		Applications/File
License:	GPLv2+
URL:		http://github.com
Source0:	%{name}-%{version}.tar.gz

# simulated dependencies
BuildRequires:  desktop-file-utils
BuildRequires:  gtk2-devel gettext

%description
Simple example to demonstrate copr's abilites.


%prep
%setup -q


%build
%configure
make %{?_smp_mflags}


%install
%make_install


%files
%doc

%changelog
* Sat Dec 19 2015 Unknown name 1.0.1-1
- new package built with tito

* Mon Nov 16 2015 Miroslav Suchý <miroslav@suchy.cz> 1.78-1
- handle_generate_gpg_key skips key creation when signing is disabled
