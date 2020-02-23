import click
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from copr_common.enums import StatusEnum
from coprs import db
from coprs import models
from coprs.logic import coprs_logic, actions_logic, builds_logic, packages_logic


@click.command()
@click.argument(
    "rawhide_chroot",
    required=True
)
@click.argument(
    "dest_chroot",
    required=True
)
def rawhide_to_release(rawhide_chroot, dest_chroot):
    """
    Branching
    """
    return rawhide_to_release_function(rawhide_chroot, dest_chroot)

def rawhide_to_release_function(rawhide_chroot, dest_chroot):
    mock_chroot = coprs_logic.MockChrootsLogic.get_from_name(dest_chroot).first()
    if not mock_chroot:
        print("Given chroot does not exist. Please run:")
        print("    sudo python3 manage.py create-chroot {}".format(dest_chroot))
        return

    mock_rawhide_chroot = coprs_logic.MockChrootsLogic.get_from_name(rawhide_chroot).first()
    if not mock_rawhide_chroot:
        print("Given rawhide chroot does not exist. Didnt you mistyped?:")
        print("    {}".format(rawhide_chroot))
        return

    coprs_query = (
        coprs_logic.CoprsLogic.get_all()
        .join(models.CoprChroot)
        .filter(models.Copr.follow_fedora_branching == True)
        .filter(models.CoprChroot.mock_chroot == mock_rawhide_chroot)
        .options(joinedload('copr_chroots').joinedload('mock_chroot'))
    )

    for copr in coprs_query:
        print("Handling builds in copr '{}', chroot '{}'".format(
            copr.full_name, mock_rawhide_chroot.name))
        turn_on_the_chroot_for_copr(copr, rawhide_chroot, mock_chroot)

        data = {"projectname": copr.name,
                "ownername": copr.owner_name,
                "rawhide_chroot": rawhide_chroot,
                "dest_chroot": dest_chroot,
                "builds": []}

        latest_pkg_builds_in_rawhide = (
            db.session.query(
                func.max(models.Build.id),
            )
            .join(models.BuildChroot)
            .join(models.Package)
            .filter(models.BuildChroot.mock_chroot_id == mock_rawhide_chroot.id)
            .filter(models.BuildChroot.status == StatusEnum("succeeded"))
            .filter(models.Package.copr_dir == copr.main_dir)
            .group_by(models.Package.name)
        )

        fork_builds = (
            db.session.query(models.Build)
            .options(joinedload('build_chroots').joinedload('mock_chroot'))
            .filter(models.Build.id.in_(latest_pkg_builds_in_rawhide.subquery()))
        ).all()


        # no builds to fork in this copr
        if not len(fork_builds):
            continue

        for build in fork_builds:
            if mock_chroot in build.chroots:
                # forked chroot already exists, from previous run?
                continue

            # rbc means rawhide_build_chroot (we needed short variable)
            rbc = None
            for rbc in build.build_chroots:
                if rbc.mock_chroot == mock_rawhide_chroot:
                    break

            dest_build_chroot = models.BuildChroot(**rbc.to_dict())
            dest_build_chroot.mock_chroot_id = mock_chroot.id
            dest_build_chroot.mock_chroot = mock_chroot
            dest_build_chroot.status = StatusEnum("forked")
            db.session.add(dest_build_chroot)

            if rbc.result_dir:
                data['builds'].append(rbc.result_dir)

        if len(data["builds"]):
            actions_logic.ActionsLogic.send_rawhide_to_release(data)

        db.session.commit()

def turn_on_the_chroot_for_copr(copr, rawhide_name, mock_chroot):
    rawhide_chroot = None
    for chroot in copr.copr_chroots:
        if chroot.name == rawhide_name:
            rawhide_chroot = chroot
        if chroot.name == mock_chroot.name:
            # already created
            return

    create_kwargs = {
        "buildroot_pkgs": rawhide_chroot.buildroot_pkgs,
        "comps": rawhide_chroot.comps,
        "comps_name": rawhide_chroot.comps_name,
    }
    coprs_logic.CoprChrootsLogic.create_chroot(copr.user, copr, mock_chroot, **create_kwargs)
