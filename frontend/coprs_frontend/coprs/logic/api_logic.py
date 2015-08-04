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
        :arg monitor_data: dict with fields:
            "builds": list of models.Build,
            "chroots": list of chroot names
            "packages": tuple (pkg_name, pkg_version, build_results),
            "latest_build": models.Build,
        """
        self.copr = copr
        self.monitor_data = monitor_data

    def to_dict(self):
        out = {}
        out["chroots"] = map(lambda x: x.name, self.copr.active_chroots_sorted)
        out["builds"] = [
            BuildWrapper(build).to_dict()
            for build in self.copr.builds
        ]


        packages = []

        for pkg in self.monitor_data:
            package = pkg["package"]
            chroots = pkg["build_chroots"]

            results = {}
            for ch in self.copr.active_chroots:
                if chroots[ch.name]:
                    results[ch.name] = {"build_id": chroots[ch.name].build.id,
                                        "status": chroots[ch.name].state,
                                        "pkg_version": chroots[ch.name].build.pkg_version}
                else:
                    results[ch.name] = None

            packages.append({"pkg_name": package.name,
                             "pkg_version": None,
                             "results": results})

        out["packages"] = packages
        return out
