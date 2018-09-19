"""
    This module contains logic for Copr API.

    xWrapper classes add helper methods
    to [de]serialize model instances for API views.
"""

from copr_common.enums import StatusEnum

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

    def render_packages(self):
        """
        NOTE: individual records for the same package must be "grouped" together in self.monitor_data
        """
        packages = []
        results = {}
        current_package_id = None

        for row in self.monitor_data:
            if row["package_id"] != current_package_id:
                if current_package_id:
                    packages.append({ "pkg_name": row["package_name"], "pkg_version": None, "results": results })
                current_package_id = row["package_id"]
                results = {}

            build_chroot_name = "{}-{}-{}".format(row["mock_chroot_os_release"], row["mock_chroot_os_version"], row["mock_chroot_arch"])
            if build_chroot_name in [chroot.name for chroot in self.copr.active_chroots]:
                results[build_chroot_name] = { "build_id": row["build_id"], "status": StatusEnum(row["build_chroot_status"]), "pkg_version": row["build_pkg_version"] }

        packages.append({ "pkg_name": row["package_name"], "pkg_version": None, "results": results })
        return packages

    def to_dict(self):
        return {
            "chroots": list(map(lambda x: x.name, self.copr.active_chroots_sorted)),
            "builds":  [BuildWrapper(build).to_dict() for build in self.copr.builds],
            "packages": self.render_packages()
        }
