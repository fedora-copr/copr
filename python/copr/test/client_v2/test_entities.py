# coding: utf-8
# pylint: disable=E1101, C0102
import pytest
from copr.client_v2.schemas import Schema, fields
from copr.client_v2.entities import Entity


class FooSchema(Schema):
    foo = fields.Str()
    bar = fields.Int()


class FooEntity(Entity):
    _schema = FooSchema()


class TestEntities(object):

    entity = None

    # pylint: disable=W0613
    def setup_method(self, method):
        self.entity = FooEntity.from_dict({"foo": "baz", "bar": 123})

    def test_from_dict(self):
        assert self.entity.foo == "baz"
        assert self.entity.bar == 123
        assert not hasattr(self.entity, "non_existing_attribute")

        with pytest.raises(AttributeError):
            assert self.entity.non_existing_attribute

    def test_to_dict(self):
        assert set(self.entity.to_dict().items()) == \
               set([("foo", "baz"), ("bar", 123)])

    def test_to_json(self):
        assert self.entity.to_json() == '{"foo": "baz", "bar": 123}' \
            or self.entity.to_json() == '{"bar": 123, "foo": "baz"}'

