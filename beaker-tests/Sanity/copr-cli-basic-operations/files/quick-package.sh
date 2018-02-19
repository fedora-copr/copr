#! /bin/sh -x

set -e

generate_specfile()
{
    test -n "$DESTDIR" && mkdir -p "$DESTDIR"

    test -n "$BUILDDEPS" && {
        for i in $BUILDDEPS; do
            rpm -q $i
        done
    }

    if ${HOOK_PAYLOAD-false}; then
        test -f hook_payload
        test "$(cat hook_payload)" = "{\"a\": \"b\"}"
    else
        ! test -f hook_payload
    fi

cat > "${DESTDIR-.}"/quick-package.spec <<\EOF
Name:           quick-package
Version:        0
Release:        0%{?dist}
Summary:        dummy package
License:        GPL
URL:            http://example.com/

%{!?_pkgdocdir: %global _pkgdocdir %{_docdir}/%{name}-%{version}}

%description
nothing


%install
mkdir -p $RPM_BUILD_ROOT/%{_pkgdocdir}
echo "this does nothing" > $RPM_BUILD_ROOT/%{_pkgdocdir}/README


%files
%doc %{_pkgdocdir}/README


%changelog
* Thu Jun 05 2014 Pavel Raiskup <praiskup@redhat.com> - 0-1
- does nothing!
EOF
}
