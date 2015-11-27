# coding: utf-8
from ..util import UnicodeMixin

from .schemas import ProjectSchema, EmptySchema, ProjectChrootSchema, BuildSchema, BuildTaskSchema, MockChrootSchema, \
    ProjectCreateSchema


class Link(UnicodeMixin):
    def __init__(self, role, href):
        self.role = role
        self.href = href

    def __unicode__(self):
        return u"<Link: role: {}, href: {}".format(self.role, self.href)

    @classmethod
    def from_dict(cls, data_dict):
        return {
            role_name:
                cls(role_name, definition["href"])
            for role_name, definition in data_dict.items()
        }


# pylint: disable=E1101
class Entity(UnicodeMixin):
    _schema = EmptySchema()

    def __init__(self, **kwargs):
        for field in self._schema.fields.keys():
            setattr(self, field, kwargs.get(field))

    def to_dict(self):
        return self._schema.dump(self).data

    def to_json(self):
        return self._schema.dumps(self).data

    @classmethod
    def from_dict(cls, raw_dict):
        parsed = cls._schema.load(raw_dict)
        return cls(**parsed.data)


class ProjectEntity(Entity):
    _schema = ProjectSchema(strict=True)

    def __unicode__(self):
        return "<Project #{}: {}/{}>".format(self.id, self.owner, self.name)


class ProjectCreateEntity(Entity):
    _schema = ProjectCreateSchema(strict=True)

    def __unicode__(self):
        return "<New project {}/{}>".format(self.owner, self.name)

class ProjectChrootEntity(Entity):
    _schema = ProjectChrootSchema(strict=True)

    def __unicode__(self):
        return "<Project chroot: {}, additional " \
               "packages: {}, comps size if any: {}>"\
            .format(self.name, self.buildroot_pkgs, self.comps_len,)


class BuildEntity(Entity):
    _schema = BuildSchema(strict=True)

    def __unicode__(self):
        return "<Build #{} state: {}>".format(self.id, self.state)

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
    _schema = BuildTaskSchema(strict=True)

    def __unicode__(self):
        return "<Build task #{}-{}, state: {}>".format(
            self.build_id, self.chroot_name, self.state
        )


class MockChrootEntity(Entity):
    _schema = MockChrootSchema(strict=True)

    def __unicode__(self):
        return "<Mock chroot: {} is active: {}>".format(
            self.name, self.is_active
        )
