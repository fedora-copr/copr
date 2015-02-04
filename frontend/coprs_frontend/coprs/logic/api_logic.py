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
    def __init__(self, monitor_data):
        """
        :arg monitor_data: dict with fields:
            "builds": list of models.Build,
            "chroots": list of chroot names
            "packages": tuple (pkg_name, pkg_version, build_results),
            "latest_build": models.Build,
        """
        self.monitor_data = monitor_data

    def to_dict(self):
        out = {}
        chroots = self.monitor_data["chroots"]
        out["chroots"] = chroots
        out["builds"] = [
            BuildWrapper(build).to_dict()
            for build in self.monitor_data["builds"]
        ]

        packages_fixed = []
        for (pkg_name, results_by_chroot) in self.monitor_data["packages"]:
            results = {}
            for chroot_name, (build_id, status, pkg_version, _) in zip(chroots, results_by_chroot):
                if status is None or pkg_version is None:
                    results[chroot_name] = None
                else:
                    results[chroot_name] = dict(build_id=build_id,
                                                status=status,
                                                pkg_version=pkg_version)

            packages_fixed.append({
                "pkg_name": pkg_name,
                "pkg_version": None,  # legacy
                "results": results
            })

        out["packages"] = packages_fixed
        #
        # [
        #     {
        #         "pkg_name": pkg_name,
        #         "pkg_version": None,  # legacy
        #         "results": dict(zip(chroots, results_by_chroot))
        #     }
        #     for (pkg_name, results_by_chroot)
        #     in self.monitor_data["packages"]
        # ]
        return out
