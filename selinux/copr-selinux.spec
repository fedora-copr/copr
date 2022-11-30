%if 0%{?rhel} < 7 && 0%{?rhel} > 0
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%endif

%global moduletype apps
%global modulename copr
%global selinuxbooleans httpd_enable_cgi=1 httpd_can_network_connect=1 httpd_can_sendmail=1 nis_enabled=1
# We can build 'mls' too, once this is resolved:
# https://github.com/fedora-selinux/selinux-policy-macros/pull/4
%global selinuxvariants targeted

Name:       copr-selinux
Version:    1.54
Release:    1%{?dist}
Summary:    SELinux module for COPR

License:    GPLv2+
URL:        https://github.com/fedora-copr/copr

# Source is created by:
# git clone %%url && cd copr
# tito build --tgz --tag %%name-%%version-%%release
Source0:    %name-%version.tar.gz

BuildArch:  noarch
BuildRequires: asciidoc
BuildRequires: libxslt
BuildRequires:  perl

BuildRequires: selinux-policy-devel
%{?selinux_requires}


%description
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package include SELinux targeted module for COPR

%prep
%setup -q


%build
# convert manages
a2x -d manpage -f manpage man/copr-selinux-enable.8.asciidoc
a2x -d manpage -f manpage man/copr-selinux-relabel.8.asciidoc

perl -i -pe 'BEGIN { $VER = join ".", grep /^\d+$/, split /\./, "%{version}.%{release}"; } s!\@\@VERSION\@\@!$VER!g;' %{modulename}.te
for selinuxvariant in %selinuxvariants; do
    make NAME=${selinuxvariant} -f %{_datadir}/selinux/devel/Makefile
    bzip2 -9 %{modulename}.pp
    mv %{modulename}.pp.bz2 %{modulename}.pp.bz2.${selinuxvariant}
    make NAME=${selinuxvariant} -f %{_datadir}/selinux/devel/Makefile clean
done


%install
for selinuxvariant in %selinuxvariants; do
    install -d %{buildroot}%{_datadir}/selinux/${selinuxvariant}
    install -p -m 644 %{modulename}.pp.bz2.${selinuxvariant} \
           %{buildroot}%{_datadir}/selinux/${selinuxvariant}/%{modulename}.pp.bz2
done
# Install SELinux interfaces
install -d %{buildroot}%{_datadir}/selinux/devel/include/%{moduletype}
install -p -m 644 %{modulename}.if \
  %{buildroot}%{_datadir}/selinux/devel/include/%{moduletype}/%{modulename}.if
install -d %{buildroot}%{_sbindir}
install -p -m 755 %{name}-enable %{buildroot}%{_sbindir}/%{name}-enable
install -p -m 755 %{name}-relabel %{buildroot}%{_sbindir}/%{name}-relabel
install -d %{buildroot}%{_mandir}/man8
install -p -m 644 man/%{name}-enable.8 %{buildroot}/%{_mandir}/man8/
install -p -m 644 man/%{name}-relabel.8 %{buildroot}/%{_mandir}/man8/


%pre
for selinuxvariant in %selinuxvariants; do
  %selinux_relabel_pre -s $selinuxvariant
done


%post
for selinuxvariant in %selinuxvariants; do
  %selinux_modules_install -s $selinuxvariant %{_datadir}/selinux/${selinuxvariant}/%{modulename}.pp.bz2
  %selinux_set_booleans    -s $selinuxvariant %{selinuxbooleans}
done


%postun
for selinuxvariant in %selinuxvariants; do
  %selinux_modules_uninstall -s $selinuxvariant %{modulename}
  %selinux_unset_booleans    -s $selinuxvariant %{selinuxbooleans}
done


%posttrans
for selinuxvariant in %selinuxvariants; do
  %selinux_relabel_post -s $selinuxvariant
done


%files
%license LICENSE
%{_datadir}/selinux/*/%{modulename}.pp.bz2
# empty, do not distribute it for now
%exclude %{_datadir}/selinux/devel/include/%{moduletype}/%{modulename}.if
%{_sbindir}/%{name}-enable
%{_sbindir}/%{name}-relabel
%{_mandir}/man8/%{name}-enable.8*
%{_mandir}/man8/%{name}-relabel.8*

%changelog
* Wed Nov 30 2022 Pavel Raiskup <praiskup@redhat.com> 1.54-1
- new package built with tito
- httpd_t on copr-frontend has the rights to link copr_data_t files (uploaded stuff)

* Mon Feb 11 2019 Jakub Kadlčík <frostyx@email.cz> 1.53-1
- Add more rules for keygen (follow-up to 4f689743)

* Tue Jan 15 2019 Miroslav Suchý <msuchy@redhat.com> 1.52-1
- allow signd to write to socket

* Fri Oct 19 2018 Miroslav Suchý <msuchy@redhat.com> 1.51-1
- do the relabel in %%posttrans
- use git_dir_archive instead of git_dir_pack
- allow frontend's apache to ioctl uploaded tarballs
- packaging: Python 2/3, RHEL/Fedora fixes

* Tue Aug 07 2018 clime <clime@redhat.com> 1.50-1
- fix distro condition for policycoreutils-python

* Mon Aug 06 2018 clime <clime@redhat.com> 1.49-1
- rpkg deployment into COPR

* Fri Feb 23 2018 clime <clime@redhat.com> 1.48-1
- remove Group tag

* Mon Dec 18 2017 Dominik Turecek <dturecek@redhat.com> 1.47-1
- wrap map permission in an optional block

* Wed Apr 19 2017 clime <clime@redhat.com> 1.46-1
- add perl as build dependency

* Wed Apr 19 2017 clime <clime@redhat.com> 1.45-1
- replace fedorahosted links

* Wed Aug 03 2016 Miroslav Suchý 1.44-1
- restore context of only those files, which context changed

* Fri Jul 01 2016 clime <clime@redhat.com> 1.43-1
- Revert "add selinux rule for cgit"

* Wed Jun 29 2016 Miroslav Suchý <msuchy@redhat.com> 1.42-1
- add selinux rule for cgit

* Sat Jun 04 2016 Miroslav Suchý <miroslav@suchy.cz> 1.41-1
- adjust selinux policy generation for separated log file paths

* Sun May 29 2016 Pete Travis <me@petetravis.com> - 1.40-2
- separate log file paths for backend and frontend

* Mon Mar 14 2016 Miroslav Suchý <miroslav@suchy.cz> 1.40-1
- add missing types to requires section

* Fri Feb 12 2016 Miroslav Suchý <msuchy@redhat.com> 1.39-1
- allow copr-dist-git to read dist-git

* Wed Feb 03 2016 Miroslav Suchý <msuchy@redhat.com> 1.38-1
- add rules for dist-git and keygen

* Mon Jul 27 2015 Miroslav Suchý <msuchy@redhat.com> 1.37-1
- 1246610 - depend on policycoreutils-python-utils

* Thu Mar 05 2015 Valentin Gologuzov <vgologuz@redhat.com> 1.36-1
- [selinux] allow httpd_t to write into /var/log/copr/

* Wed Oct 22 2014 Miroslav Suchý <msuchy@redhat.com> 1.35-1
- remove old changelogs

* Mon Oct 20 2014 Miroslav Suchý <msuchy@redhat.com> 1.34-1
- 1077795 - co-own /usr/share/selinux/mls

* Tue Oct 14 2014 Miroslav Suchý <msuchy@redhat.com> 1.33-1
- 1077795 - use macro for /usr/share/

* Mon Oct 13 2014 Miroslav Suchý <msuchy@redhat.com> 1.32-1
- 1077795 - spec cleanup

* Wed May 21 2014 Miroslav Suchý <msuchy@redhat.com> 1.31-1
- follow selinux packaging draft

* Tue Mar 18 2014 Miroslav Suchý <msuchy@redhat.com> 1.30-1
- finish move selinux into separate package
