Name:       copr-dist-git
Version:    0.2
Release:    1%{?dist}
Summary:    Copr services for Dist Git server

Group:      Applications/Productivity
License:    GPLv2+
URL:        https://fedorahosted.org/copr/
# Source is created by
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/dist-git
# tito build --tgz
Source0: %{name}-%{version}.tar.gz

BuildArch:  noarch

BuildRequires:  systemd

Requires:   systemd
Requires:   dist-git
Requires:   python-bunch
Requires:   python-requests
Requires:   pyrpkg

%description
COPR is lightweight build system. It allows you to create new project in WebUI
and submit new builds and COPR will create yum repository from latest builds.

This package contains Copr services for Dist Git server


%prep
%setup -q


%build


%install

install -d %{buildroot}%{_datadir}/copr/dist-git
install -d %{buildroot}%{_sysconfdir}/copr
install -d %{buildroot}%{_sysconfdir}/logrotate.d/
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}%{_var}/log/copr-dist-git
install -d %{buildroot}%{_sharedstatedir}/copr-dist-git

cp -a dist-git/* %{buildroot}%{_datadir}/copr/dist-git
cp -a conf/copr-dist-git.conf.example %{buildroot}%{_sysconfdir}/copr/copr-dist-git.conf
cp -a copr-dist-git.service %{buildroot}%{_unitdir}/

cp -a conf/logrotate %{buildroot}%{_sysconfdir}/logrotate.d/copr-dist-git

# for ghost files
touch %{buildroot}%{_var}/log/copr-dist-git/main.log

%check

%post
# change context to be readable by cgit
semanage fcontext -a -t httpd_sys_content_t '/var/lib/copr-dist-git(/.*)?'
restorecon -rv /var/lib/copr-dist-git

%files
%license LICENSE

%{_datadir}/copr/*
%dir %{_sysconfdir}/copr
%config(noreplace) %attr(0640, root, copr-service) %{_sysconfdir}/copr/copr-dist-git.conf

%dir %attr(0755, copr-service, copr-service) %{_sharedstatedir}/copr-dist-git/

%{_unitdir}/copr-dist-git.service

%config(noreplace) %{_sysconfdir}/logrotate.d/copr-dist-git
%attr(0755, copr-service, copr-service) %{_var}/log/copr-dist-git
%attr(0644, copr-service, copr-service) %{_var}/log/copr-dist-git/main.log
%ghost %{_var}/log/copr-dist-git/*.log

%changelog
* Thu Jul 23 2015 Valentin Gologuzov <vgologuz@redhat.com> 0.2-1
- new package built with tito

* Thu Jun 25 2015 Adam Samalik <asamalik@redhat.com> 0.1
- basic package
