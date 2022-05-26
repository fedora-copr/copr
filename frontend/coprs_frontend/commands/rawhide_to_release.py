import click
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from copr_common.enums import StatusEnum
from coprs import db
from coprs import models
from coprs.logic import coprs_logic, actions_logic, builds_logic, packages_logic


def option_retry_forked(f):
    """ Shortcut to --retry-forked option definition, to avoid C&P """
    method = click.option(
        "--retry-forked/--no-retry-forked",
        default=False,
        help=(
            "Generate actions for backend also for already forked builds, useful "
            "e.g. when previous run of this command failed."
        )
    )
    return method(f)


@click.command()
@click.argument(
    "rawhide_chroot",
    required=True
)
@click.argument(
    "dest_chroot",
    required=True
)
@option_retry_forked
def rawhide_to_release(rawhide_chroot, dest_chroot, retry_forked):
    """
    Branching
    """
    return rawhide_to_release_function(rawhide_chroot, dest_chroot,
                                       retry_forked)

def rawhide_to_release_function(rawhide_chroot, dest_chroot, retry_forked):
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

    mock_chroot.comment = mock_rawhide_chroot.comment

    for copr in coprs_query:
        print("Handling builds in copr '{}', chroot '{}'".format(
            copr.full_name, mock_rawhide_chroot.name))
        turn_on_the_chroot_for_copr(copr, rawhide_chroot, mock_chroot)

        data = {"projectname": copr.name,
                "ownername": copr.owner_name,
                "rawhide_chroot": rawhide_chroot,
                "appstream": copr.appstream,
                "dest_chroot": dest_chroot,
                "builds": []}

        latest_pkg_builds_in_rawhide = (
            db.session.query(
                func.max(models.Build.id),
            )
            .join(models.BuildChroot, models.CoprDir, models.Package)
            .filter(models.BuildChroot.mock_chroot_id == mock_rawhide_chroot.id)
            .filter(models.BuildChroot.status == StatusEnum("succeeded"))
            .filter(models.CoprDir.id == copr.main_dir.id)
            .group_by(models.Package.name)
        )

        fork_builds = (
            db.session.query(models.Build)
            .options(joinedload('build_chroots').joinedload('mock_chroot'))
            .filter(models.Build.id.in_(latest_pkg_builds_in_rawhide.subquery()))
        ).all()


        # no builds to fork in this copr
        if not len(fork_builds):
            print("Createrepo for copr '{}', chroot '{}'".format(copr.full_name, mock_chroot.name))
            actions_logic.ActionsLogic.send_createrepo(copr, chroots=[mock_chroot.name])
            continue

        new_build_chroots = 0
        for build in fork_builds:
            chroot_exists = mock_chroot in build.chroots

            if chroot_exists and not retry_forked:
                # this build should already be forked
                continue

            # rbc means rawhide_build_chroot (we needed short variable)
            rbc = None
            for rbc in build.build_chroots:
                if rbc.mock_chroot == mock_rawhide_chroot:
                    break

            if not chroot_exists:
                # forked chroot may already exists, e.g. from prevoius
                # 'rawhide-to-release-run'
                new_build_chroots += 1
                dest_build_chroot = builds_logic.BuildChrootsLogic.new(
                    build=rbc.build,
                    mock_chroot=mock_chroot,
                    **rbc.to_dict({
                        "__columns_except__": ["id"],
                    }),
                )
                dest_build_chroot.status = StatusEnum("forked")
                db.session.add(dest_build_chroot)

            if rbc.result_dir:
                data['builds'].append(rbc.result_dir)

        if data["builds"] or new_build_chroots:
            print("  Fresh new build chroots: {}, regenerate {}".format(
                new_build_chroots,
                len(data["builds"]) - new_build_chroots,
            ))

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
    coprs_logic.CoprChrootsLogic.create_chroot_from(rawhide_chroot,
                                                    mock_chroot=mock_chroot)
