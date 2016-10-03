from coprs import models
from coprs import helpers


ACTION_TYPE = helpers.ActionTypeEnum("build_module")


class ModulesLogic(object):
    """
    @FIXME ?
    Module builds are currently stored as Actions, so we are querying subset of Action objects
    """

    @classmethod
    def get(cls, module_id):
        """
        Return single module identified by `module_id`
        """
        return models.Module.query.filter(models.Action.id == module_id)

    @classmethod
    def get_multiple(cls):
        return models.Module.query.filter(models.Module.action_type == ACTION_TYPE).order_by(models.Module.id.desc())

    @classmethod
    def get_multiple_by_copr(cls, copr):
        return filter(lambda m: m.ownername == copr.owner_name and m.projectname == copr.name,
                      cls.get_multiple())
