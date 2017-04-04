%global		confdir %_sysconfdir/%name

Name:		copr-builder
Version:	0
Release:	5%{?dist}
Summary:	Build package from copr dist-git

License:	GPLv2+
URL:		https://pagure.io/copr/copr

Source0:	copr-builder
Source1:	LICENSE
Source2:	fedora-copr.conf
Source3:	README

Requires:	crudini
Requires:	copr-cli
Requires:	mock
Requires:	rpkg
Requires:	expect
Requires:	util-linux

BuildArch:	noarch

%description
Knowing copr name, package name and dist-git git hash, build automatically the
package locally in mock.


%prep
%setup -q -c -T
cp %SOURCE1 .
cp %SOURCE3 .


%build


%install
install -d %buildroot%_bindir
install -d %buildroot%_sysconfdir/copr-builder
install -d %buildroot%_sharedstatedir/copr-builder

install -p -m 755 %SOURCE0 %buildroot%_bindir
install -p -m 644 %SOURCE2 %buildroot%confdir



%files
%doc LICENSE README
%_bindir/copr-builder
%confdir
%dir %attr(0775, root, mock) %_sharedstatedir/copr-builder


%changelog
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
