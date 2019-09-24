# coding: utf-8
from ..util import UnicodeMixin

from .schemas import ProjectSchema, EmptySchema, ProjectChrootSchema, BuildSchema, BuildTaskSchema, MockChrootSchema, \
    ProjectCreateSchema

try:
    _ = ProjectSchema(strict=True)
    kwargs = {"strict": True}
except TypeError:
    kwargs = {}


class Link(UnicodeMixin):
    def __init__(self, role, href):
        self.role = role
        self.href = href

    def __unicode__(self):
        return u"<Link: role: {0}, href: {1}".format(self.role, self.href)

    @classmethod
    def from_dict(cls, data_dict):
        retval = {}
        for role_name, definition in data_dict.items():
            retval[role_name] = cls(role_name, definition["href"])
        return retval


# pylint: disable=E1101
class Entity(UnicodeMixin):
    _schema = EmptySchema()

    def __init__(self, **kwargs):
        for field in self._schema.fields.keys():
            setattr(self, field, kwargs.get(field))

    def to_dict(self):
        output = self._schema.dump(self)
        output = getattr(output, "data", output)
        return output

    def to_json(self):
        output = self._schema.dumps(self)
        output = getattr(output, "data", output)
        return output

    @classmethod
    def from_dict(cls, raw_dict):
        parsed = cls._schema.load(raw_dict)
        parsed = getattr(parsed, "data", parsed)
        return cls(**parsed)


class ProjectEntity(Entity):
    _schema = ProjectSchema(**kwargs)

    def __unicode__(self):
        return "<Project #{0}: {1}/{2}>".format(self.id, self.owner, self.name)


class ProjectCreateEntity(Entity):
    _schema = ProjectCreateSchema(**kwargs)

    def __unicode__(self):
        return "<New project {0}/{1}>".format(self.owner, self.name)

class ProjectChrootEntity(Entity):
    _schema = ProjectChrootSchema(**kwargs)

    def __unicode__(self):
        return "<Project chroot: {0}, additional " \
               "packages: {1}, comps size if any: {2}>"\
            .format(self.name, self.buildroot_pkgs, self.comps_len,)


class BuildEntity(Entity):
    _schema = BuildSchema(**kwargs)

    def __unicode__(self):
        return "<Build #{0} state: {1}>".format(self.id, self.state)

    def is_finished(self):
        """
        Check is the build was finished

        :rtype: bool
        """
        return self.state in [
                "failed",
                "skipped",
                "succeeded"
        ]


class BuildTaskEntity(Entity):
    _schema = BuildTaskSchema(**kwargs)

    def __unicode__(self):
        return "<Build task #{0}-{1}, state: {2}>".format(
            self.build_id, self.chroot_name, self.state
        )


class MockChrootEntity(Entity):
    _schema = MockChrootSchema(**kwargs)

    def __unicode__(self):
        return "<Mock chroot: {0} is active: {1}>".format(
            self.name, self.is_active
        )
