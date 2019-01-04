from flask_script import Command, Option
from copr_common.enums import StatusEnum
from coprs import db
from coprs import models
from coprs.logic import coprs_logic, actions_logic, builds_logic


class RawhideToReleaseCommand(Command):

    option_list = (
        Option("rawhide_chroot", help="Rawhide chroot name, e.g. fedora-rawhide-x86_64."),
        Option("dest_chroot", help="Destination chroot, e.g. fedora-24-x86_64."),
    )

    def run(self, rawhide_chroot, dest_chroot):
        mock_chroot = coprs_logic.MockChrootsLogic.get_from_name(dest_chroot).first()
        if not mock_chroot:
            print("Given chroot does not exist. Please run:")
            print("    sudo python3 manage.py create_chroot {}".format(dest_chroot))
            return

        mock_rawhide_chroot = coprs_logic.MockChrootsLogic.get_from_name(rawhide_chroot).first()
        if not mock_rawhide_chroot:
            print("Given rawhide chroot does not exist. Didnt you mistyped?:")
            print("    {}".format(rawhide_chroot))
            return

        for copr in coprs_logic.CoprsLogic.get_all():
            if not self.has_rawhide(copr) or not copr.follow_fedora_branching:
                continue

            self.turn_on_the_chroot_for_copr(copr, rawhide_chroot, mock_chroot)

            data = {"projectname": copr.name,
                    "ownername": copr.owner_name,
                    "rawhide_chroot": rawhide_chroot,
                    "dest_chroot": dest_chroot,
                    "builds": []}

            for build in builds_logic.BuildsLogic.get_multiple_by_copr(copr):
                # rbc means rawhide_build_chroot (we needed short variable)
                rbc = builds_logic.BuildChrootsLogic.get_by_build_id_and_name(build.id, rawhide_chroot).first()
                dbc = builds_logic.BuildChrootsLogic.get_by_build_id_and_name(build.id, dest_chroot).first()

                if not rbc or rbc.status != StatusEnum("succeeded"):
                    continue

                data["builds"].append(rbc.result_dir)

                if rbc and not dbc:
                    dest_build_chroot = models.BuildChroot(**rbc.to_dict())
                    dest_build_chroot.mock_chroot_id = mock_chroot.id
                    dest_build_chroot.mock_chroot = mock_chroot
                    dest_build_chroot.status = StatusEnum("forked")
                    db.session.add(dest_build_chroot)

            if len(data["builds"]):
                actions_logic.ActionsLogic.send_rawhide_to_release(data)

        db.session.commit()

    def turn_on_the_chroot_for_copr(self, copr, rawhide_name, mock_chroot):
        rawhide_chroot = coprs_logic.CoprChrootsLogic.get_by_name_safe(copr, rawhide_name)
        dest_chroot = coprs_logic.CoprChrootsLogic.get_by_name_safe(copr, mock_chroot.name)

        if not rawhide_chroot or dest_chroot:
            return

        create_kwargs = {
            "buildroot_pkgs": rawhide_chroot.buildroot_pkgs,
            "comps": rawhide_chroot.comps,
            "comps_name": rawhide_chroot.comps_name,
        }
        coprs_logic.CoprChrootsLogic.create_chroot(copr.user, copr, mock_chroot, **create_kwargs)

    def has_rawhide(self, copr):
        return any(filter(lambda ch: ch.os_version == "rawhide", copr.mock_chroots))


