import re
import os

import whoosh
import whoosh.fields
import whoosh.index
import whoosh.qparser

from flask.ext.sqlalchemy import models_committed
from flask.ext.whooshee import AbstractWhoosheer

from coprs import app
from coprs import db
from coprs import models
from coprs import whooshee

@whooshee.register_whoosheer
class CoprUserWhoosheer(AbstractWhoosheer):
    schema = whoosh.fields.Schema(
        copr_id = whoosh.fields.NUMERIC(stored=True, unique=True),
        user_id = whoosh.fields.NUMERIC(stored=True),
        username = whoosh.fields.TEXT(),
        coprname = whoosh.fields.TEXT(),
        description = whoosh.fields.TEXT(),
        instructions = whoosh.fields.TEXT())

    models = [models.Copr, models.User]

    @classmethod
    def update_user(cls, writer, user):
        # TODO: this is not needed now, as users can't change names, but may be needed later
        pass

    @classmethod
    def update_copr(cls, writer, copr):
        writer.update_document(copr_id=copr.id,
                               user_id=copr.owner.id,
                               username=copr.owner.name,
                               coprname=copr.name,
                               description=copr.description,
                               instructions=copr.instructions)

    @classmethod
    def insert_user(cls, writer, user):
        # nothing, user doesn't have coprs yet
        pass

    @classmethod
    def insert_copr(cls, writer, copr):
        writer.add_document(copr_id=copr.id,
                            user_id=copr.owner.id,
                            username=copr.owner.name,
                            coprname=copr.name,
                            description=copr.description,
                            instructions=copr.instructions)

    @classmethod
    def delete_copr(cls, writer, copr):
        writer.delete_by_term('copr_id', copr.id)
