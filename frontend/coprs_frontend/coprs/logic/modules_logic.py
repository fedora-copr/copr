from coprs import models


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
