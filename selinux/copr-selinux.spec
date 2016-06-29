%if 0%{?rhel} < 7 && 0%{?rhel} > 0
%global _pkgdocdir %{_docdir}/%{name}-%{version}
%global __python2 %{__python}
%endif

%global moduletype apps
%global modulename copr
%{!?_selinux_policy_version: %global _selinux_policy_version %(sed -e 's,.*selinux-policy-\\([^/]*\\)/.*,\\1,' %{_datadir}/selinux/devel/policyhelp 2>/dev/null)}

Name:       copr-selinux
Version:    1.42
Release:    1%{?dist}
Summary:    SELinux module for COPR

Group:      Applications/Productivity
License:    GPLv2+
URL:        https://fedorahosted.org/copr/
# Source is created by
# git clone https://git.fedorahosted.org/git/copr.git
# cd copr/selinux
# tito build --tgz
# content is same as https://git.fedorahosted.org/cgit/copr.git/snapshot/%{name}-%{version}-1.tar.gz
# but checksum does not match due different metadata
Source0: %{name}-%{version}.tar.gz

BuildArch:  noarch
BuildRequires: asciidoc
BuildRequires: libxslt
BuildRequires:  checkpolicy, selinux-policy-devel
BuildRequires:  policycoreutils
Requires(post): policycoreutils, libselinux-utils
%if 0%{?rhel} <= 7
Requires(post): policycoreutils-python
%else
Requires(post): policycoreutils-python-utils
%endif
Requires(post): selinux-policy-targeted
Requires(postun): policycoreutils
%if "%{_selinux_policy_version}" != ""
Requires:      selinux-policy >= %{_selinux_policy_version}
%endif


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
for selinuxvariant in targeted mls; do
    make NAME=${selinuxvariant} -f %{_datadir}/selinux/devel/Makefile
    bzip2 -9 %{modulename}.pp
    mv %{modulename}.pp.bz2 %{modulename}.pp.bz2.${selinuxvariant}
    make NAME=${selinuxvariant} -f %{_datadir}/selinux/devel/Makefile clean
done

%install
for selinuxvariant in targeted mls; do
    install -d %{buildroot}%{_datadir}/selinux/${selinuxvariant}
    install -p -m 644 %{modulename}.pp.bz2.${selinuxvariant} \
           %{buildroot}%{_datadir}/selinux/${selinuxvariant}/%{modulename}.pp.bz2
done
# Install SELinux interfaces
install -d %{buildroot}%{_datadir}/selinux/devel/include/%{moduletype}
install -p -m 644 %{modulename}.if \
  %{buildroot}%{_datadir}/selinux/devel/include/%{moduletype}/%{modulename}.if
# Install copr-selinux-enable which will be called in %%posttrans
install -d %{buildroot}%{_sbindir}
install -p -m 755 %{name}-enable %{buildroot}%{_sbindir}/%{name}-enable
install -p -m 755 %{name}-relabel %{buildroot}%{_sbindir}/%{name}-relabel

install -d %{buildroot}%{_mandir}/man8
install -p -m 644 man/%{name}-enable.8 %{buildroot}/%{_mandir}/man8/
install -p -m 644 man/%{name}-relabel.8 %{buildroot}/%{_mandir}/man8/

%post
if /usr/sbin/selinuxenabled ; then
   %{_sbindir}/%{name}-enable
fi

%posttrans
if /usr/sbin/selinuxenabled ; then
   %{_sbindir}/%{name}-relabel
fi

%postun
# Clean up after package removal
if [ $1 -eq 0 ]; then
  for selinuxvariant in targeted mls; do
      /usr/sbin/semodule -s ${selinuxvariant} -l > /dev/null 2>&1 \
        && /usr/sbin/semodule -s ${selinuxvariant} -r %{modulename} || :
    done
fi
%{_sbindir}/restorecon -rvvi %{_sharedstatedir}/copr

%files
%license LICENSE
%{_datadir}/selinux/*/%{modulename}.pp.bz2
# empty, do not distribute it for now
%exclude %{_datadir}/selinux/devel/include/%{moduletype}/%{modulename}.if
%{_sbindir}/%{name}-enable
%{_sbindir}/%{name}-relabel
%{_mandir}/man8/%{name}-enable.8*
%{_mandir}/man8/%{name}-relabel.8*
%dir %{_datadir}/selinux/mls

%changelog
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
