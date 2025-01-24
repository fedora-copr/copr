#!/usr/bin/python3


"""
We encountered an issue, that a chroot contained RPM packages for multiple
chroots. Please see https://pagure.io/copr/copr/issue/1501

This is an one-shot script, trying to figure out whether it happened just once
or repeatedly.

This scipt may print false-positives - in case of a packaging error when the
package didn't set `Release:` field properly. That is a minor inconvenience, but
we store also `.spec` files, so we can verify whether it is false-positive or
not.
"""

import os
import sys
from copr_common.rpm import splitFilename
from copr_backend.helpers import BackendConfigReader


config_file = "/etc/copr/copr-be.conf"
config = BackendConfigReader(config_file).read()


def get_chroot_map():
    """
    Return a dict mapping chroot names to their dist values, e.g.

        fedora-32-x86_64  -->  fc32
        epel-7-x86_64  -->  el7

    Only active chroots are returned, so we save some time when running the
    script. Also `fedora-rawhide-*`, `mageia-cauldron-*`, and `centos-stream-*`,
    `fedora-eln-*`, are ommitted because it is not trivial to map them (they
    don't have one static value but rather a number chaning in time)
    """

    chroots = {}
    archs = ["x86_64", "i386", "aarch64", "armhfp", "s390x", "i586", "ppc64le"]

    # fedora
    for version in list(range(31, 33)):
        for arch in archs:
            nva = "fedora-{}-{}".format(version, arch)
            dist = "fc{}".format(version)
            chroots[nva] = dist

    # epel
    for version in [6, 7, 8]:
        for arch in archs:
            nva = "epel-{}-{}".format(version, arch)
            dist = "el{}".format(version)
            chroots[nva] = dist

    # mageia
    chroots["mageia-7-x86_64"] = "mga7"
    chroots["mageia-7-i586"] = "mga7"

    # opensuse
    chroots["opensuse-leap-15.1-x86_64"] = "suse.lp151"
    chroots["opensuse-leap-15.2-x86_64"] = "suse.lp152"
    chroots["opensuse-tumbleweed-i586"] = "suse.tw"
    chroots["opensuse-tumbleweed-x86_64"] = "suse.tw"

    return chroots


def check_rpm_results(path, known_dists):
    """
    Check whether a directory contains only one set of RPM packages (e.g. not
    fc30 and fc31 at the same time)
    """

    releases = []
    for artifact_entry in os.scandir(path):
        artifact = artifact_entry.name
        if not artifact.endswith(".rpm"):
            continue
        (_, _, release, _, _) = splitFilename(artifact)
        releases.append(release)

    dists = {x.rsplit(".", 1)[-1] for x in releases}
    dists = {x for x in dists if x in known_dists}
    if len(dists) > 1:
        sys.stderr.write("{0}   ({1})\n".format(path, " ".join(dists)))


def main():
    """
    Recursively go through all `results -> owner -> project -> chroot -> build`
    directories and make sure they contain only acceptable RPM packages for
    those chroots.
    """
    chroot_map = get_chroot_map()
    destdir_path = config["destdir"]
    for owner_entry in os.scandir(destdir_path):
        if not owner_entry.is_dir():
            continue
        owner = owner_entry.name
        owner_path = os.path.join(destdir_path, owner)

        for project_entry in os.scandir(owner_path):
            if not project_entry.is_dir():
                continue
            project_path = os.path.join(owner_path, project_entry.name)

            for chroot_entry in os.scandir(project_path):
                if not chroot_entry.is_dir():
                    continue
                chroot = chroot_entry.name
                chroot_path = os.path.join(project_path, chroot)

                if chroot not in chroot_map:
                    continue

                for build_entry in os.scandir(chroot_path):
                    if not build_entry.is_dir():
                        continue
                    build_path = os.path.join(chroot_path, build_entry.name)

                    check_rpm_results(build_path, chroot_map.values())


if __name__ == '__main__':
    main()
