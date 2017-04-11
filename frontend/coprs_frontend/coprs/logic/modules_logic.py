import time
import base64
import modulemd
from sqlalchemy import and_
from coprs import models
from coprs import db
from coprs import exceptions
from wtforms import ValidationError


class ModulesLogic(object):
    @classmethod
    def get(cls, module_id):
        """
        Return single module identified by `module_id`
        """
        return models.Module.query.filter(models.Module.id == module_id)

    @classmethod
    def get_by_nsv(cls, copr, name, stream, version):
        return models.Module.query.filter(
            and_(models.Module.name == name,
                 models.Module.stream == stream,
                 models.Module.version == version,
                 models.Module.copr_id == copr.id))

    @classmethod
    def get_multiple(cls):
        return models.Module.query.order_by(models.Module.id.desc())

    @classmethod
    def get_multiple_by_copr(cls, copr):
        return cls.get_multiple().filter(models.Module.copr_id == copr.id)

    @classmethod
    def yaml2modulemd(cls, yaml):
        mmd = modulemd.ModuleMetadata()
        mmd.loads(yaml)
        return mmd

    @classmethod
    def from_modulemd(cls, yaml):
        mmd = cls.yaml2modulemd(yaml)
        return models.Module(name=mmd.name, stream=mmd.stream, version=mmd.version, summary=mmd.summary,
                             description=mmd.description, yaml_b64=base64.b64encode(yaml))

    @classmethod
    def validate(cls, yaml):
        mmd = cls.yaml2modulemd(yaml)
        if not all([mmd.name, mmd.stream, mmd.version]):
            raise ValidationError("Module should contain name, stream and version")

    @classmethod
    def add(cls, user, copr, module):
        if not user.can_build_in(copr):
            raise exceptions.InsufficientRightsException("You don't have permissions to build in this copr.")

        module.copr_id = copr.id
        module.copr = copr
        module.created_on = time.time()

        db.session.add(module)
        return module
