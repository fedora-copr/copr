Name:           vera
Version:        1.3
Release:        0%{?dist}
Summary:        A programmable tool for verification, analysis and transformation of C++ source code

License:        Boost
%global commit0 cf13c413f641b5816a4fc9cd4b2fb248c81bf2bd
URL:            https://github.com/verateam/%{name}

Source0:        https://github.com/verateam/%{name}/archive/%{commit0}.tar.gz

BuildRequires:  cmake
BuildRequires:  luabind-devel
BuildRequires:  tcl-devel
BuildRequires:  tk-devel

BuildRequires:  lua-devel
BuildRequires:  python2-devel

BuildRequires:  gcc-c++


%description
Vera++ is a programmable tool for verification, analysis and transformation of
C++ source code. Vera++ is mainly an engine that parses C++ source files and
presents the result of this parsing to scripts in the form of various
collections - the scripts are actually performing the requested tasks.

%prep
%autosetup -n %{name}-%{commit0}

sed -i 's|URL http://${SOURCEFORGE}/project/boost/boost/1.60.0/boost_1_60_0.tar.bz2|URL http://sourceforge.net/projects/boost/files/boost/1.60.0/boost_1_60_0.tar.bz2|' src/boost.cmake

%build
%cmake .
%cmake_build

%install
%cmake_install

%files
   %{_bindir}/vera++
   %{_libdir}/vera++/profiles/boost
   %{_libdir}/vera++/profiles/default
   %{_libdir}/vera++/profiles/full
   %{_libdir}/vera++/rules/DUMP.tcl
   %{_libdir}/vera++/rules/F001.tcl
   %{_libdir}/vera++/rules/F002.tcl
   %{_libdir}/vera++/rules/L001.tcl
   %{_libdir}/vera++/rules/L002.tcl
   %{_libdir}/vera++/rules/L003.tcl
   %{_libdir}/vera++/rules/L004.tcl
   %{_libdir}/vera++/rules/L005.tcl
   %{_libdir}/vera++/rules/L006.tcl
   %{_libdir}/vera++/rules/M001.tcl
   %{_libdir}/vera++/rules/M002.tcl
   %{_libdir}/vera++/rules/M003.tcl
   %{_libdir}/vera++/rules/T001.tcl
   %{_libdir}/vera++/rules/T002.tcl
   %{_libdir}/vera++/rules/T003.tcl
   %{_libdir}/vera++/rules/T004.tcl
   %{_libdir}/vera++/rules/T005.tcl
   %{_libdir}/vera++/rules/T006.tcl
   %{_libdir}/vera++/rules/T007.tcl
   %{_libdir}/vera++/rules/T008.tcl
   %{_libdir}/vera++/rules/T008A.tcl
   %{_libdir}/vera++/rules/T008B.tcl
   %{_libdir}/vera++/rules/T009.tcl
   %{_libdir}/vera++/rules/T010.tcl
   %{_libdir}/vera++/rules/T011.tcl
   %{_libdir}/vera++/rules/T012.tcl
   %{_libdir}/vera++/rules/T013.tcl
   %{_libdir}/vera++/rules/T014.tcl
   %{_libdir}/vera++/rules/T015.tcl
   %{_libdir}/vera++/rules/T016.tcl
   %{_libdir}/vera++/rules/T017.tcl
   %{_libdir}/vera++/rules/T018.tcl
   %{_libdir}/vera++/rules/T019.tcl
   %{_libdir}/vera++/test_wrapper.cmake.in
   %{_libdir}/vera++/transformations/move_includes.tcl
   %{_libdir}/vera++/transformations/move_macros.tcl
   %{_libdir}/vera++/transformations/move_namespace.tcl
   %{_libdir}/vera++/transformations/to_lower.tcl
   %{_libdir}/vera++/transformations/to_xml.tcl
   %{_libdir}/vera++/transformations/to_xml2.tcl
   %{_libdir}/vera++/transformations/trim_right.tcl
   %{_libdir}/vera++/use_vera++.cmake
   %{_libdir}/vera++/vera++-config-version.cmake
   %{_libdir}/vera++/vera++-config.cmake

%changelog

* Wed May 31 2017 Alexis Jeandet <alexis.jeandet@member.fsf.org> - 1.3-0
- Initial packaging.
