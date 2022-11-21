Name:		copr-java
Version:	0.2
Release:	1%{?dist}
Summary:	COPR Java client
License:	ASL 2.0
URL:		https://github.com/fedora-copr/copr

# Source is created by
# git clone https://pagure.io/copr/copr.git
# cd copr/java
# tito build --tgz
Source0:        %{name}-%{version}.tar.gz

BuildRequires:	maven-local

%description
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package contains Java client library.

%package javadoc
Summary:        API documentation for %{name}

%description javadoc
This package provides %{summary}.

%prep
%setup -q

%build
%mvn_build

%install
%mvn_install

%files -f .mfiles
%license LICENSE
%doc NOTICE

%files javadoc -f .mfiles-javadoc
%license LICENSE
%doc NOTICE

%changelog
* Tue Sep 16 2014 Mikolaj Izdebski <mizdebsk@redhat.com>
- Initial packaging
