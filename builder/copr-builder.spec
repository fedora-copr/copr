%global confdir %_sysconfdir/%name

Name:		copr-builder
Version:	1
Release:	1%{?dist}
Summary:	Build package from Copr dist-git

License:	GPLv2+
URL:		https://pagure.io/copr/copr

Source0:	copr-builder
Source1:	LICENSE
Source3:	README

# Those could be dropped, but still we keep them at least for reference (those
# files are not aimed to be used by production builders).  The real
# configuration will be copied on builder via backend's VM spin-up playbook.
Source2:	fedora-copr.conf
Source4:	fedora-copr-dev.conf
Source5:	rhcopr.conf
Source6:	rhcopr-stg.conf
Source7:	rhcopr-dev.conf
Source8:	rpkg

# Ensure that 'mock' group is available for our installed files
Requires(pre):	mock

Requires:	crudini
Requires:	copr-cli
Requires:	mock
Requires:	expect
Requires:	util-linux
Requires:	sed

BuildArch:	noarch

%description
Knowing copr name, package name and dist-git git hash, build automatically the
package locally in mock.


%prep
%setup -q -c -T
install -p -m 644 %SOURCE1 .
install -p -m 644 %SOURCE3 .


%build


%install
install -d %buildroot%_bindir
install -d %buildroot%_sysconfdir/copr-builder
install -d %buildroot%_sharedstatedir/copr-builder

install -d %buildroot%_sharedstatedir/copr-builder/results
touch %buildroot%_sharedstatedir/copr-builder/pid
touch %buildroot%_sharedstatedir/copr-builder/lock
touch %buildroot%_sharedstatedir/copr-builder/live-log

install -p -m 755 %SOURCE0 %buildroot%_bindir

# Ideally we would 'Require: rpkg' only, but 'rpkg' package has been
# (temprorarily?) dropped from Fedora (rhbz#1452202).
install -p -m 755 %SOURCE8 %buildroot%_bindir/copr-rpkg
install -p -m 644 %SOURCE2 %buildroot%confdir
install -p -m 644 %SOURCE4 %buildroot%confdir
install -p -m 644 %SOURCE5 %buildroot%confdir
install -p -m 644 %SOURCE6 %buildroot%confdir
install -p -m 644 %SOURCE7 %buildroot%confdir


%files
%license LICENSE
%doc README
%_bindir/copr-builder
%_bindir/copr-rpkg
%confdir
%dir %attr(0775, root, mock) %_sharedstatedir/copr-builder
%ghost %dir %verify(not mode mtime) %_sharedstatedir/copr-builder/results
%ghost %verify(not md5 size mode mtime) %_sharedstatedir/copr-builder/pid
%ghost %verify(not md5 size mode mtime) %_sharedstatedir/copr-builder/lock
%ghost %verify(not md5 size mode mtime) %_sharedstatedir/copr-builder/live-log


%changelog
* Sat May 27 2017 Pavel Raiskup <praiskup@redhat.com> - 1-1
- package 'rpkg' script

* Thu Apr 27 2017 Pavel Raiskup <praiskup@redhat.com> - 0-13
- package review changes
- use copr vs. Copr consistently; capitalize when we talk about Copr "service",
  and don't for particular coprs (projects) maintained _in_ Copr service
- use %%license properly
- Requires(pre) mock
- own some %%ghost files
- ensure doc files have 644 mode

* Tue Apr 18 2017 Pavel Raiskup <praiskup@redhat.com> - 0-12
- dump command-line arguments to log (easier reproducibility)

* Thu Apr 13 2017 Pavel Raiskup <praiskup@redhat.com> - 0-10
- add --mock-opts option

* Tue Apr 04 2017 Pavel Raiskup <praiskup@redhat.com> - 0-9
- more lively logs with sed filtering

* Tue Apr 04 2017 Pavel Raiskup <praiskup@redhat.com> - 0-8
- touch 'success' file

* Tue Apr 04 2017 Pavel Raiskup <praiskup@redhat.com> - 0-7
- distribute non-default configuration
- fix --chroot option

* Tue Apr 04 2017 Pavel Raiskup <praiskup@redhat.com> - 0-6
- add timeout option

* Tue Apr 04 2017 Pavel Raiskup <praiskup@redhat.com> - 0-5
- changes needed after copr PR 44

* Mon Mar 27 2017 Pavel Raiskup <praiskup@redhat.com> - 0-4
- several TODOs implemented

* Mon Mar 20 2017 Pavel Raiskup <praiskup@redhat.com> - 0-3
- filter both stderr and stdout through 'col -b' for sub-commands

* Mon Mar 20 2017 Pavel Raiskup <praiskup@redhat.com> - 0-2
- a bit nicer live logs in copr

* Sun Mar 19 2017 Pavel Raiskup <praiskup@redhat.com> - 0-1
- package also README

* Sun Mar 19 2017 Pavel Raiskup <praiskup@redhat.com> - 0-0
- Initial commit
