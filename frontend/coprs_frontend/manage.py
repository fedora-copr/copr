#!/usr/bin/python3

import argparse
import os
import subprocess
import datetime
import sqlalchemy
import time

import flask
from flask_script import Manager, Command, Option, Group
from flask_whooshee import Whooshee

from copr_common.enums import StatusEnum
from coprs import app
from coprs import db
from coprs import exceptions
from coprs import models
from coprs.logic import coprs_logic, packages_logic, actions_logic, builds_logic, users_logic
from coprs.views.misc import create_user_wrapper
from coprs.whoosheers import CoprWhoosheer
from sqlalchemy import and_, or_
from coprs.helpers import chroot_to_branch


class TestCommand(Command):

    def run(self, coverage, test_args):
        os.environ["COPRS_ENVIRON_UNITTEST"] = "1"
        if not (("COPR_CONFIG" in os.environ) and os.environ["COPR_CONFIG"]):
            os.environ["COPR_CONFIG"] = "/etc/copr/copr_unit_test.conf"

        if 'PYTHONPATH' in os.environ:
            os.environ['PYTHONPATH'] = os.environ['PYTHONPATH'] + ':.'
        else:
            os.environ['PYTHONPATH'] = '.'

        additional_args = []

        if coverage:
            additional_args.extend([
                '--cov-report', 'term-missing', '--cov', 'coprs'
            ])

        return subprocess.call(["/usr/bin/python3", "-m", "pytest"] + additional_args)

    option_list = (
        Option("-a",
               dest="test_args",
               nargs=argparse.REMAINDER),
        Option("--coverage",
               dest="coverage",
               required=False,
               action='store_true',
               default=False),
    )


class CreateSqliteFileCommand(Command):

    """
    Create the sqlite DB file (not the tables).
    Used for alembic, "create_db" does this automatically.
    """

    def run(self):
        if flask.current_app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            # strip sqlite:///
            datadir_name = os.path.dirname(
                flask.current_app.config["SQLALCHEMY_DATABASE_URI"][10:])
            if not os.path.exists(datadir_name):
                os.makedirs(datadir_name)


class CreateDBCommand(Command):

    """
    Create the DB schema
    """

    def run(self, alembic_ini=None):
        CreateSqliteFileCommand().run()
        db.create_all()

        # load the Alembic configuration and generate the
        # version table, "stamping" it with the most recent rev:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(alembic_ini)
        command.stamp(alembic_cfg, "head")

        # Functions are not covered by models.py, and no migrations are run
        # by command.stamp() above.  Create functions explicitly:
        builds_logic.BuildsLogic.init_db()

    option_list = (
        Option("--alembic",
               "-f",
               dest="alembic_ini",
               help="Path to the alembic configuration file (alembic.ini)",
               required=True),
    )


class DropDBCommand(Command):

    """
    Delete DB
    """

    def run(self):
        db.drop_all()


class ChrootCommand(Command):

    def print_invalid_format(self, chroot_name):
        print(
            "{0} - invalid chroot format, must be '{release}-{version}-{arch}'."
            .format(chroot_name))

    def print_already_exists(self, chroot_name):
        print("{0} - already exists.".format(chroot_name))

    def print_doesnt_exist(self, chroot_name):
        print("{0} - chroot doesn\"t exist.".format(chroot_name))

    option_list = (
        Option("chroot_names",
               help="Chroot name, e.g. fedora-18-x86_64.",
               nargs="+"),
    )


class CreateChrootCommand(ChrootCommand):

    "Creates a mock chroot in DB"

    def __init__(self):
        self.option_list += Option(
               "--dist-git-branch",
               "-b",
               dest="branch",
               help="Branch name for this set of new chroots"),

    def run(self, chroot_names, branch=None):
        for chroot_name in chroot_names:
            if not branch:
                branch = chroot_to_branch(chroot_name)
            branch_object = coprs_logic.BranchesLogic.get_or_create(branch)
            try:
                chroot = coprs_logic.MockChrootsLogic.add(chroot_name)
                chroot.distgit_branch = branch_object
                db.session.commit()
            except exceptions.MalformedArgumentException:
                self.print_invalid_format(chroot_name)
            except exceptions.DuplicateException:
                self.print_already_exists(chroot_name)


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


class AlterChrootCommand(ChrootCommand):

    "Activates or deactivates a chroot"

    def run(self, chroot_names, action):
        activate = (action == "activate")
        for chroot_name in chroot_names:
            try:
                coprs_logic.MockChrootsLogic.edit_by_name(
                    chroot_name, activate)
                db.session.commit()
            except exceptions.MalformedArgumentException:
                self.print_invalid_format(chroot_name)
            except exceptions.NotFoundException:
                self.print_doesnt_exist(chroot_name)

    option_list = ChrootCommand.option_list + (
        Option("--action",
               "-a",
               dest="action",
               help="Action to take - currently activate or deactivate",
               choices=["activate", "deactivate"],
               required=True),
    )


class DropChrootCommand(ChrootCommand):

    "Activates or deactivates a chroot"

    def run(self, chroot_names):
        for chroot_name in chroot_names:
            try:
                coprs_logic.MockChrootsLogic.delete_by_name(chroot_name)
                db.session.commit()
            except exceptions.MalformedArgumentException:
                self.print_invalid_format(chroot_name)
            except exceptions.NotFoundException:
                self.print_doesnt_exist(chroot_name)


class DisplayChrootsCommand(Command):

    "Displays current mock chroots"

    def run(self, active_only):
        for ch in coprs_logic.MockChrootsLogic.get_multiple(
                active_only=active_only).all():

            print(ch.name)

    option_list = (
        Option("--active-only",
               "-a",
               dest="active_only",
               help="Display only active chroots",
               required=False,
               action="store_true",
               default=False),
    )


class AddUserCommand(Command):

    """
    You should not use regularly as that user will not be related to FAS account.
    This should be used only for testing or adding special accounts e.g. proxy user.
    """

    def run(self, name, mail, **kwargs):
        user = models.User.query.filter(models.User.username == name).first()
        if user:
            print("User named {0} already exists.".format(name))
            return

        user = create_user_wrapper(name, mail)
        if kwargs["api_token"]:
            user.api_token = kwargs["api_token"]
        if kwargs["api_login"]:
            user.api_token = kwargs["api_login"]

        db.session.add(user)
        db.session.commit()

    option_list = (
        Option("name"),
        Option("mail"),
        Option("--api_token", default=None, required=False),
        Option("--api_login", default=None, required=False),
    )


class DumpUserCommand(Command):

    def run(self, username):
        user = models.User.query.filter(models.User.username == username).first()
        if not user:
            print("There is no user named {0}.".format(username))
            return 1
        dumper = users_logic.UserDataDumper(user)
        print(dumper.dumps(pretty=True))

    option_list = (
        Option("username"),
    )


class AlterUserCommand(Command):

    def run(self, name, **kwargs):
        user = models.User.query.filter(
            models.User.username == name).first()
        if not user:
            print("No user named {0}.".format(name))
            return

        if kwargs["admin"]:
            user.admin = True
        if kwargs["no_admin"]:
            user.admin = False
        if kwargs["proven"]:
            user.proven = True
        if kwargs["no_proven"]:
            user.proven = False
        if kwargs["proxy"]:
            user.proxy = True
        if kwargs["no_proxy"]:
            user.proxy = False

        db.session.add(user)
        db.session.commit()

    option_list = (
        Option("name"),
        Group(
            Option("--admin",
                   action="store_true"),
            Option("--no-admin",
                   action="store_true"),
            exclusive=True
        ),
        Group(
            Option("--proven",
                   action="store_true"),
            Option("--no-proven",
                   action="store_true"),
            exclusive=True
        ),
        Group(
            Option("--proxy",
                   action="store_true"),
            Option("--no-proxy",
                   action="store_true"),
            exclusive=True
        )
    )


class FailBuildCommand(Command):

    """
    Marks build as failed on all its non-finished chroots
    """

    option_list = [Option("build_id")]

    def run(self, build_id, **kwargs):
        try:
            builds_logic.BuildsLogic.mark_as_failed(build_id)
            print("Marking non-finished chroots of build {} as failed".format(build_id))
            db.session.commit()

        except (sqlalchemy.exc.DataError, sqlalchemy.orm.exc.NoResultFound) as e:
            print("Error: No such build {}".format(build_id))
            return 1


class UpdateIndexesCommand(Command):
    """
    recreates whoosh indexes for all projects
    """

    def run(self):
        index = Whooshee.get_or_create_index(app, CoprWhoosheer)

        writer = index.writer()
        for copr in coprs_logic.CoprsLogic.get_all():
            CoprWhoosheer.delete_copr(writer, copr)
        writer.commit(optimize=True)

        writer = index.writer()
        writer.schema = CoprWhoosheer.schema
        writer.commit(optimize=True)

        writer = index.writer()
        for copr in coprs_logic.CoprsLogic.get_all():
            CoprWhoosheer.insert_copr(writer, copr)
        writer.commit(optimize=True)


class UpdateIndexesQuickCommand(Command):
    """
    Recreates whoosh indexes for projects for which
    indexed data were updated in last n minutes.
    Doesn't update schema.
    """

    option_list = [Option("minutes_passed")]

    def run(self, minutes_passed):
        index = Whooshee.get_or_create_index(app, CoprWhoosheer)

        writer = index.writer()
        query = db.session.query(models.Copr).filter(
            models.Copr.latest_indexed_data_update >= time.time()-int(minutes_passed)*60
        )
        for copr in query.all():
            CoprWhoosheer.update_copr(writer, copr)
        writer.commit()


class UpdateGraphsDataCommand(Command):
    """
    Generates newest graph data.
    """

    def run(self):
        builds_logic.BuildsLogic.get_tasks_histogram('10min')
        builds_logic.BuildsLogic.get_tasks_histogram('30min')
        builds_logic.BuildsLogic.get_tasks_histogram('24h')


class RemoveGraphsDataCommand(Command):
    """
    Removes old cached graph data that is no longer used.
    """

    def run(self):
        curr_time = int(time.time())
        models.BuildsStatistics.query.filter(or_(
            and_(models.BuildsStatistics.time < curr_time - 91 * 86400,
                 models.BuildsStatistics.stat_type == '24h'),
            and_(models.BuildsStatistics.time < curr_time - 87000,
                 models.BuildsStatistics.stat_type == '30min'),
            and_(models.BuildsStatistics.time < curr_time - 87000,
                 models.BuildsStatistics.stat_type == '10min')
        )).delete()
        db.session.commit()


manager = Manager(app)
manager.add_command("test", TestCommand())
manager.add_command("create_sqlite_file", CreateSqliteFileCommand())
manager.add_command("create_db", CreateDBCommand())
manager.add_command("drop_db", DropDBCommand())
manager.add_command("create_chroot", CreateChrootCommand())
manager.add_command("alter_chroot", AlterChrootCommand())
manager.add_command("display_chroots", DisplayChrootsCommand())
manager.add_command("drop_chroot", DropChrootCommand())
manager.add_command("alter_user", AlterUserCommand())
manager.add_command("add_user", AddUserCommand())
manager.add_command("dump_user", DumpUserCommand())
manager.add_command("fail_build", FailBuildCommand())
manager.add_command("update_indexes", UpdateIndexesCommand())
manager.add_command("update_indexes_quick", UpdateIndexesQuickCommand())
manager.add_command("rawhide_to_release", RawhideToReleaseCommand())
manager.add_command("backend_rawhide_to_release", BackendRawhideToReleaseCommand())
manager.add_command("update_graphs", UpdateGraphsDataCommand())
manager.add_command("vacuum_graphs", RemoveGraphsDataCommand())

if __name__ == "__main__":
    manager.run()
