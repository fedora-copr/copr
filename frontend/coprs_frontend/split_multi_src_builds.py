#!/usr/bin/python
# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import


"""
This script splits all builds which contains multiply src_packages
into the more builds, each of them containing exactly one src_pkg.
Script modifies only db records, actual rpms are not touched.
"""

import logging


logging.basicConfig(
#    filename="/var/log/copr/split_multi_src_builds.log",
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)
log = logging.getLogger(__name__)


def split_one(orig_build_id):
    from coprs import db
    from coprs import models
    from coprs.logic.builds_logic import BuildsLogic
    from coprs.models import BuildChroot

    def clone_build(build):
        other = models.Build(
            pkgs=build.pkgs,
            built_packages=build.built_packages,
            pkg_version=build.pkg_version,
            canceled=build.canceled,
            repos=build.repos,

            submitted_on=build.submitted_on,
            started_on=build.started_on,
            ended_on=build.ended_on,

            results=build.results,

            memory_reqs=build.memory_reqs,
            timeout=build.timeout,
            enable_net=build.enable_net,

            user=build.user,
            copr=build.copr,
        )
        return other

    build = BuildsLogic.get(orig_build_id).one()
    log.info("Start splitting build: {}, pkgs: {}".format(build.id, build.pkgs))

    src_pkg_list = []
    for mb_pkg in build.pkgs.strip().split(" "):
        src_pkg_list.append(mb_pkg)

    if len(src_pkg_list) == 0:
        log.error("> Got build with empty pkgs: id={}".format(build.id))
        return
    if len(src_pkg_list) == 1:
        log.debug("> Got build with one pkg in pkgs,  id={}, pkgs={}".format(build.id, build.pkgs))
        return

    new_builds = []
    new_build_chroots = []

    for src_pkg in src_pkg_list:
        log.info("> Processing {} package".format(src_pkg))
        new_build = clone_build(build)
        new_build.pkgs = src_pkg

        for bc in build.build_chroots:
            log.info("> > Copying chroot {}".format(bc.name))
            new_bc = BuildChroot(
                build=new_build,
                mock_chroot=bc.mock_chroot,
                status=bc.status
            )
            new_build_chroots.append(new_bc)

        new_builds.append(new_build)

    log.info("> Finished build split for id: {}. Doing commit".format(build.id))
    db.session.rollback()  # some dirty state in SQLalchemy, no idea how to do correctly
    db.session.add_all(new_build_chroots)
    db.session.add_all(new_builds)
    for bc in build.build_chroots:
        db.session.delete(bc)
    db.session.delete(build)
    db.session.commit()
    log.info("> New build objects were created ")
    log.info("> Build {} deleted ".format(build.id))


def main():
    from coprs import models
    query = models.Build.query.filter(models.Build.pkgs.contains(" ")).limit(3)
    for build_id in [build.id for build in query.all()]:
        split_one(build_id)


if __name__ == "__main__":
    main()
