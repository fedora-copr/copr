import os
import whoosh
import time

from subprocess import Popen, PIPE
from flask_whooshee import AbstractWhoosheer

from coprs import app
from coprs import models
from coprs import whooshee
from coprs import db


@whooshee.register_whoosheer
class CoprWhoosheer(AbstractWhoosheer):
    schema = whoosh.fields.Schema(
        copr_id=whoosh.fields.NUMERIC(stored=True, unique=True),
        user_id=whoosh.fields.NUMERIC(stored=True),
        group_id=whoosh.fields.NUMERIC(stored=True),
        # treat dash as a normal character - so searching for example
        # "copr-dev" will really search for "copr-dev"
        ownername=whoosh.fields.TEXT(
            analyzer=whoosh.analysis.StandardAnalyzer(
                expression=r"@?\w+(-\.?\w+)*"), field_boost=2),
        coprname=whoosh.fields.TEXT(
            analyzer=whoosh.analysis.StandardAnalyzer(
                expression=r"\w+(-\.?\w+)*"), field_boost=3),
        chroots=whoosh.fields.TEXT(field_boost=2),
        packages=whoosh.fields.TEXT(
            analyzer=whoosh.analysis.StandardAnalyzer(
                expression=r"\s+", gaps=True), field_boost=2),
        description=whoosh.fields.TEXT(),
        instructions=whoosh.fields.TEXT())

    models = [models.Copr, models.Package] # copr-specific: must inherit from CoprSearchRelatedData class

    auto_update = False

    @classmethod
    def update_copr(cls, writer, copr):
        writer.update_document(copr_id=copr.id,
                               user_id=copr.user.id,
                               group_id=copr.group.id if copr.group else None,
                               ownername=copr.owner_name,
                               coprname=copr.name,
                               chroots=cls.get_chroot_info(copr),
                               packages=cls.get_package_names(copr),
                               description=copr.description,
                               instructions=copr.instructions)

    @classmethod
    def update_package(cls, writer, package):
        writer.update_document(copr_id=package.copr.id, packages=cls.get_package_names(package.copr))

    @classmethod
    def insert_copr(cls, writer, copr):
        writer.add_document(copr_id=copr.id,
                            user_id=copr.user.id,
                            group_id=copr.group.id if copr.group else None,
                            ownername=copr.owner_name,
                            coprname=copr.name,
                            chroots=cls.get_chroot_info(copr),
                            packages=cls.get_package_names(copr),
                            description=copr.description,
                            instructions=copr.instructions)

    @classmethod
    def insert_package(cls, writer, package):
        writer.update_document(copr_id=package.copr.id, packages=cls.get_package_names(package.copr))

    @classmethod
    def delete_copr(cls, writer, copr):
        writer.delete_by_term("copr_id", copr.id)

    @classmethod
    def delete_package(cls, writer, package):
        writer.update_document(copr_id=package.copr.id, packages=cls.get_package_names(package.copr))

    @classmethod
    def get_chroot_info(cls, copr):
        # NOTE: orm db session for Copr model is already committed at the point insert_*/update_* methods are called.
        # Hence we use db.engine directly (for a new session).
        result = db.engine.execute(
            """
            SELECT os_release, os_version, arch
            FROM mock_chroot
            JOIN copr_chroot ON copr_chroot.mock_chroot_id=mock_chroot.id
            WHERE copr_chroot.copr_id={0}
            """.format(copr.id)
        )
        return ["{}-{}-{}".format(t[0], t[1], t[2]) for t in result.fetchall()]

    @classmethod
    def get_package_names(cls, copr):
        result = db.engine.execute(
            """
            SELECT name
            FROM package
            WHERE copr_id={0}
            """.format(copr.id)
        )
        return [row[0] for row in result.fetchall()]

    @classmethod
    def on_commit(cls, app, changes):
        """Should be registered with flask.ext.sqlalchemy.models_committed."""
        for change in changes:
            if change[0].__class__ in cls.models:
                copr_id = change[0].get_search_related_copr_id()
                db.engine.execute(
                    """
                    UPDATE copr SET latest_indexed_data_update = {0}
                    WHERE copr.id = {1}
                    """.format(int(time.time()), copr_id)
                )


class WhoosheeStamp(object):
    """
    When a whooshee package is updated, it is often needed to rebuild
    indexes. This class manages a stamp file containing whooshee packages
    versions and decides whether they are still up-to-date or not.
    """

    PATH = os.path.join(app.config["WHOOSHEE_DIR"], "whooshee-version")

    @classmethod
    def current(cls):
        packages = ["python3-flask-whooshee", "python3-whoosh"]
        cmd = ["rpm", "-q", "--qf", "%{NAME}-%{VERSION}\n"] + packages
        process = Popen(cmd, stdout=PIPE, stderr=PIPE)
        out, err = process.communicate()
        return out.decode("utf-8").rstrip()

    @classmethod
    def store(cls):
        with open(cls.PATH, "w") as f:
            f.write(cls.current())

    @classmethod
    def read(cls):
        try:
            with open(cls.PATH, "r") as f:
                return f.read().rstrip()
        except OSError:
            return None

    @classmethod
    def is_valid(cls):
        return cls.read() == cls.current()
