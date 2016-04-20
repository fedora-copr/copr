"""
    This module contains logic for Copr API.

    xWrapper classes add helper methods
    to [de]serialize model instances for API views.
"""


class BuildWrapper(object):
    def __init__(self, build):
        """
        :arg build: copr.models.Build
        """
        self.build = build

    def to_dict(self):
        out = {}
        for field in ["id", "pkg_version", "status", "state",
                      "canceled", "repos", "submitted_on", "started_on",
                      "ended_on", "results", "memory_reqs", "timeout"]:
            out[field] = getattr(self.build, field, None)

        out["src_pkg"] = self.build.pkgs
        build_packages = self.build.built_packages
        if build_packages:
            out["built_packages"] = build_packages.split("\n")
        else:
            out["built_packages"] = []

        return out


class MonitorWrapper(object):
    def __init__(self, copr, monitor_data):
        """
        Params
        ------
        copr : copr for which we want to get monitor data
        monitor_data : list(tuple(package, build, build_chroot, mock_chroot))
            the list must be ordered by package (!)
        """
        self.copr = copr
        self.monitor_data = monitor_data

    def wrap_package(self, package, builds_data):
        """Converts single package to the API format.

        Params
        ------
        package : Package instance
        builds_data : dict(build_chroot.name : dict(build, build_chroot, mock_chroot))

        Returns
        -------
        dict(pkg_name, pkg_version, results)
            pkg_name : name of package
            pkg_version : None
            results : dict(build_id, status, pkg_version)
        """
        results = {}

        for chroot in self.copr.active_chroots:
            if chroot.name in builds_data:
                results[chroot.name] = {
                    "build_id": builds_data[chroot.name]['build'].id,
                    "status": builds_data[chroot.name]['build_chroot'].state,
                    "pkg_version": builds_data[chroot.name]['build'].pkg_version
                }
            else:
                results[chroot.name] = None

        return {"pkg_name": package.name, "pkg_version": None, "results": results}

    def render_packages(self):
        """
        NOTE: individual records for the same package in must be "grouped" together in self.monitor_data
        """
        packages = []
        builds_data = {}
        current_package = None

        for package, build, build_chroot, mock_chroot in self.monitor_data:
            if package != current_package:
                if current_package:
                    packages.append(self.wrap_package(current_package, builds_data))
                current_package = package
                builds_data = {}
            builds_data[build_chroot.name] = {"build": build, "build_chroot": build_chroot, "mock_chroot": mock_chroot}
        packages.append(self.wrap_package(current_package, builds_data))

        return packages

    def to_dict(self):
        return {
            "chroots": map(lambda x: x.name, self.copr.active_chroots_sorted),
            "builds":  [BuildWrapper(build).to_dict() for build in self.copr.builds],
            "packages": self.render_packages()
        }
