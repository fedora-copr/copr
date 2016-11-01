import time
import base64
import modulemd
from sqlalchemy import and_
from coprs import models
from coprs import db


class ModulesLogic(object):
    @classmethod
    def get(cls, module_id):
        """
        Return single module identified by `module_id`
        """
        return models.Module.query.filter(models.Module.id == module_id)

    @classmethod
    def get_by_nvr(cls, owner, name, version, release):
        return cls.filter_by_owner(models.Module.query, owner).filter(
            and_(models.Module.name == name,
                 models.Module.version == version,
                 models.Module.release == release))

    @classmethod
    def filter_by_owner(cls, query, owner):
        if isinstance(owner, models.Group):
            return query.filter(models.Module.group_id == owner.id)
        return query.filter(models.Module.user_id == owner.id)

    @classmethod
    def get_multiple(cls):
        return models.Module.query.order_by(models.Module.id.desc())

    @classmethod
    def get_multiple_by_copr(cls, copr):
        return cls.get_multiple().filter(models.Module.copr_id == copr.id)

    @classmethod
    def from_modulemd(cls, yaml):
        mmd = modulemd.ModuleMetadata()
        mmd.loads(yaml)
        return models.Module(name=mmd.name, version=mmd.version, release=mmd.release, summary=mmd.summary,
                             description=mmd.description, yaml_b64=base64.b64encode(yaml))

    @classmethod
    def add(cls, user, copr, module):
        module.copr_id = copr.id
        module.user_id = user.id
        module.user = user
        module.copr = copr
        if copr.group:
            module.group_id = copr.group.id
            module.group = copr.group
        module.created_on = time.time()

        db.session.add(module)
        return module
