from coprs import db
from coprs.logic import coprs_logic, packages_logic, actions_logic
from commands.rawhide_to_release import RawhideToReleaseCommand


class BackendRawhideToReleaseCommand(RawhideToReleaseCommand):

    "Copy backend data of the latest successful rawhide builds into a new chroot"

    def run(self, rawhide_chroot, dest_chroot):
        for copr in coprs_logic.CoprsLogic.get_all():
            if not self.has_rawhide(copr):
                continue

            data = {"copr": copr.name,
                    "user": copr.owner_name,
                    "rawhide_chroot": rawhide_chroot,
                    "dest_chroot": dest_chroot,
                    "builds": []}

            for package in packages_logic.PackagesLogic.get_all(copr.id):
                last_build = package.last_build(successful=True)
                if last_build:
                    data["builds"].append(last_build.result_dir)

            if len(data["builds"]):
                actions_logic.ActionsLogic.send_rawhide_to_release(data)
                print("Created copy action from {}/{} to {}/{}"
                      .format(copr.full_name, rawhide_chroot, copr.full_name, dest_chroot))

        db.session.commit()
