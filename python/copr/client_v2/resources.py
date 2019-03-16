# pylint: disable=R0903
# coding: utf-8

import six

if six.PY2:
    from collections import Iterable
else:
    from collections.abc import Iterable

from six import with_metaclass

from ..util import UnicodeMixin

from .entities import Link, ProjectEntity, ProjectChrootEntity, BuildEntity, MockChrootEntity, BuildTaskEntity
from .schemas import EmptySchema, BuildSchema, ProjectSchema, ProjectChrootSchema, MockChrootSchema, BuildTaskSchema


class EntityFieldDescriptor(object):
    """
    Entity Field Descriptor
    """
    def __init__(self, name):
        self.name = name

    def __get__(self, obj, objtype):
        """
        :type obj: IndividualResource
        """
        return getattr(obj._entity, self.name)

    def __set__(self, obj, val):
        """
        :type obj: IndividualResource
        """
        setattr(obj._entity, self.name, val)


class ReadOnlyFieldDescriptor(object):
    """
    Entity read-only Field Descriptor
    """
    def __init__(self, name):
        self.name = name

    def __get__(self, obj, objtype):
        """
        :type obj: IndividualResource
        """
        return getattr(obj._entity, self.name)


class EntityFieldsMetaClass(type):
    """
    Magic: we take fields info from class._schema and attach EntityFieldDescriptor
    to Resource classes
    """
    def __new__(mcs, class_name, bases, class_attrs):
        schema = class_attrs.get("_schema")
        if schema:
            for f_name, f in schema.fields.items():
                class_attrs[f_name] = EntityFieldDescriptor(f_name)

        entity_methods = []
        for base in bases:
            entity_methods.extend(getattr(base, "_entity_methods", []))
        entity_methods.extend(class_attrs.get("_entity_methods", []))

        for m_name in entity_methods:
            class_attrs[m_name] = ReadOnlyFieldDescriptor(m_name)

        return type.__new__(mcs, class_name, bases, class_attrs)


# pylint: disable=E1101
class IndividualResource(with_metaclass(EntityFieldsMetaClass, UnicodeMixin)):
    """
    :type handle: client_v2.handlers.AbstractHandle or None
    :type response: ResponseWrapper or None
    :type links: (dict of (str, Link)) or None
    """
    _schema = EmptySchema(strict=True)

    # todo:  this methods only serialize fields which can be modified by the user
    # think about an approach to override `load_only=True` fields in
    #  our schemas during the dump function
    # _entity_methods = ["to_json", "to_dict"]

    def __init__(self, entity, handle=None, response=None, links=None, embedded=None, options=None):

        self._entity = entity
        self._handle = handle
        self._response = response
        self._links = links
        self._embedded = embedded or dict()
        self._options = options or dict()

    def __dir__(self):
        res = list(set(
            dir(self.__class__) + list(self.__dict__.keys())
        ))
        if self._entity:
            res.extend(self._schema.fields.keys())
        return res

    def __unicode__(self):
        return self._entity.__unicode__()

    def get_href_by_name(self, name):
        """
        :type name: str
        """
        return self._links[name].href


class Root(IndividualResource):

    def __init__(self, response, links, root_url):
        super(Root, self).__init__(entity=None, response=response, links=links)
        self.root_url = root_url

    def get_resource_base_url(self, resource_name):
        """
        :param str resource_name:
        """
        return "{0}{1}".format(self.root_url, self.get_href_by_name(resource_name))

    @classmethod
    def from_response(cls, response, root_url):
        """
        :type response: ResponseWrapper
        :type root_url: unicode
        """
        data_dict = response.json
        links = Link.from_dict(data_dict["_links"])
        return Root(response=response, links=links, root_url=root_url)


class Build(IndividualResource):
    """
    :type entity: BuildEntity
    :type handle: copr.client_v2.handlers.BuildHandle
    """
    _schema = BuildSchema(strict=True)
    _entity_methods = ["is_finished"]

    def __init__(self, entity, handle, **kwargs):
        super(Build, self).__init__(entity=entity, handle=handle, **kwargs)
        self._entity = entity
        self._handle = handle

    @classmethod
    def from_response(cls, handle, data_dict, response=None, options=None):
        links = Link.from_dict(data_dict["_links"])
        entity = BuildEntity.from_dict(data_dict["build"])
        return cls(entity=entity, handle=handle,
                   response=response, links=links, options=options)

    def get_self(self):
        """ Retrieves fresh build object from the service

        :rtype: :py:class:`~.Build`
        """
        return self._handle.get_one(self.id)

    def cancel(self):
        """ Updates the current build

        :rtype: :py:class:`.OperationResult`
        """
        return self._handle.cancel(self._entity)

    def delete(self):
        """ Deletes the current build

        :rtype: :py:class:`.OperationResult`
        """
        return self._handle.delete(self.id)

    def get_build_tasks(self, **query_options):
        """ Get build tasks owned by this build

        :param query_options: see :py:meth:`.handlers.BuildHandle.get_list`
        :rtype: :py:class:`~.BuildTasksList`
        """
        handle = self._handle.get_build_tasks_handle()
        return handle.get_list(build_id=self.id, **query_options)


class BuildTask(IndividualResource):
    """
    :type entity: BuildTaskEntity
    :type handle: copr.client_v2.handlers.BuildTaskHandle
    """
    _schema = BuildTaskSchema(strict=True)

    def __init__(self, entity, handle, **kwargs):
        super(BuildTask, self).__init__(entity=entity, handle=handle, **kwargs)
        self._entity = entity
        self._handle = handle

    def get_self(self):
        """ Retrieves fresh build task object from the service

        :rtype: :py:class:`~.Build`
        """
        return self._handle.get_one(self.build_id, self.chroot_name)


    @classmethod
    def from_response(cls, handle, data_dict, response=None, options=None):
        links = Link.from_dict(data_dict["_links"])
        entity = BuildTaskEntity.from_dict(data_dict["build_task"])
        return cls(entity=entity, handle=handle,
                   response=response, links=links, options=options)


class Project(IndividualResource):
    """
    :type entity: ProjectEntity
    :type handle: copr.client_v2.handlers.ProjectHandle
    """
    _schema = ProjectSchema(strict=True)

    def __init__(self, entity, handle, **kwargs):
        super(Project, self).__init__(entity=entity, handle=handle, **kwargs)

        self._entity = entity
        self._handle = handle

    def update(self):
        """ Updates project using the current state.

        Shortcut for for :py:meth:`.ProjectHandle.update`

        :rtype: :py:class:`.OperationResult`
        """
        return self._handle.update(self._entity)

    def delete(self):
        """ Updates project using the current state

        :rtype: :py:class:`.OperationResult`
        """
        return self._handle.delete(self.id)

    def get_self(self):
        """ Retrieves fresh project object from the service

        :rtype: :py:class:`.Project`
        """
        return self._handle.get_one(self.id)

    def get_builds(self, **query_options):
        """ Get builds owned by this project

        :param query_options: see :py:meth:`.handlers.BuildHandle.get_list`
        :rtype: :py:class:`~.BuildsList`
        """
        handle = self._handle.get_builds_handle()
        return handle.get_list(project_id=self.id, **query_options)

    def get_build_tasks(self, **query_options):
        """ Get build tasks owned by this project

        :param query_options: see :py:meth:`.handlers.BuildHandle.get_list`
        :rtype: :py:class:`~.BuildTasksList`
        """
        handle = self._handle.get_build_tasks_handle()
        return handle.get_list(project_id=self.id, **query_options)

    def get_project_chroot(self, name):
        """ Retrieves project chroot object by the given name

        :param str name: mock chroot name
        :rtype: :py:class:`.ProjectChroot`
        """
        handle = self._handle.get_project_chroots_handle()
        return handle.get_one(self, name)

    def get_project_chroot_list(self):
        """ Retrieves project chroots list

        :rtype: :py:class:`.ProjectChrootList`
        """
        handle = self._handle.get_project_chroots_handle()
        return handle.get_list(self)

    def enable_project_chroot(self, name):
        """
        Enables given chroot for this project

        Shortcut for for :py:meth:`.ProjectChrootHandle.enable`

        :param str name: mock chroot name
        :rtype: :py:class:`.OperationResult`
        """
        handle = self._handle.get_project_chroots_handle()
        return handle.enable(self, name)

    def create_build_from_file(self, *args, **kwargs):
        """
        Shortcut for :py:meth:`.BuildHandle.create_from_file`
        (here you don't need to specify project_id)
        """
        builds = self._handle.get_builds_handle()
        return builds.create_from_file(self.id, *args, **kwargs)

    def create_build_from_url(self, *args, **kwargs):
        """
        Shortcut for :py:meth:`.BuildHandle.create_from_file`
        (here you don't need to specify project_id)
        """
        builds = self._handle.get_builds_handle()
        return builds.create_from_url(self.id, *args, **kwargs)

    @classmethod
    def from_response(cls, handle, data_dict, response=None, options=None):
        links = Link.from_dict(data_dict["_links"])
        entity = ProjectEntity.from_dict(data_dict["project"])
        return cls(entity=entity, handle=handle,
                   response=response, links=links, options=options)


class ProjectChroot(IndividualResource):
    """
    :type entity: copr.client_v2.entities.ProjectChrootEntity
    :type handle: copr.client_v2.handlers.ProjectChrootHandle
    """

    _schema = ProjectChrootSchema(strict=True)

    def __init__(self, entity, handle, project, **kwargs):
        super(ProjectChroot, self).__init__(entity=entity, handle=handle, **kwargs)
        self._entity = entity
        self._handle = handle
        self._project = project

    @classmethod
    def from_response(cls, handle, data_dict, project, response=None, options=None):
        links = Link.from_dict(data_dict["_links"])
        entity = ProjectChrootEntity.from_dict(data_dict["chroot"])
        return cls(entity=entity, handle=handle, project=project,
                   response=response, links=links, options=options)

    def disable(self):
        """ Disables chroot for the bound project

        :rtype: :py:class:`.OperationResult`
        """
        return self._handle.disable(self._project, self.name)

    def update(self):
        """ Updates chroot with the current entity state

        :rtype: :py:class:`.OperationResult`
        """
        return self._handle.update(self._project, self._entity)


class MockChroot(IndividualResource):
    """
    :type entity: copr.client_v2.entities.MockChrootEntity
    :type handle: copr.client_v2.handlers.MockChrootHandle
    """

    _schema = MockChrootSchema(strict=True)

    def __init__(self, entity, handle, **kwargs):
        super(MockChroot, self).__init__(
            entity=entity,
            handle=handle,
            **kwargs
        )

    @classmethod
    def from_response(cls, handle, data_dict, response=None, options=None):
        links = Link.from_dict(data_dict["_links"])
        entity = MockChrootEntity.from_dict(data_dict["chroot"])
        return cls(entity=entity, handle=handle,
                   response=response, links=links, options=options)


class OperationResult(IndividualResource):
    """ Fake resource to represent results of the requested operation

    """
    def __init__(self, handle, response=None, entity=None, options=None, expected_status=200):
        super(OperationResult, self).__init__(handle=handle, response=response, entity=entity, options=options)
        self._expected_status = expected_status

    @property
    def new_location(self):
        """ Contains an url to the new location produced by an operation
        If operation doesn't produce a new location would contain None

        :rtype: str
        """
        # todo: Create sub-class for results which contains `new_location`

        if self._response and \
                self._response.headers and \
                "location" in self._response.headers:
            return self._response.headers["location"]

        return None

    def is_successful(self):
        """ Performs check if status code is equal to the expected value
        of particular request.

        :rtype: bool
        """
        if self._response and self._response.status_code == self._expected_status:
            return True
        else:
            return False

    def __unicode__(self):
        out = u"<Result: "
        if self._response:
            out += u" status: {0}".format(self._response.status_code)
        out += u">"

        return out


class CollectionResource(Iterable, UnicodeMixin):
    """
    :type handle: client_v2.handlers.AbstractHandle or None
    :type response: ResponseWrapper
    :type links: (dict of (str, Link)) or None
    """

    def __init__(self, handle=None, response=None, links=None, individuals=None, options=None):
        self._handle = handle
        self._response = response
        self._links = links
        self._options = options or dict()
        self._individuals = individuals

    def get_href_by_name(self, name):
        """
        :type name: str
        """
        return self._links[name].href

    def next_page(self):
        limit = self._options.get("limit", 100)
        offset = self._options.get("offset", 0)

        offset += limit
        params = {}
        params.update(self._options)
        params["limit"] = limit
        params["offset"] = offset

        return self._handle.get_list(self, **params)

    def __iter__(self):
        """
        :rtype: Iterable[IndividualResource]
        """
        return iter(self._individuals)

    def __len__(self):
        if self._individuals is None:
            raise RuntimeError(u"Collection resource is missing self._individuals")

        return len(self._individuals)

    def __getitem__(self, item):
        if self._individuals is None:
            raise RuntimeError(u"Collection resource is missing self._individuals")

        return self._individuals[item]

    def __unicode__(self):
        out = u"<{}: [".format(self.__class__.__name__)
        out += u", ".join([str(x) for x in self])
        out += u"]>"
        return out

    @classmethod
    def from_response(cls, handle, response, options):
        raise NotImplementedError


def _construct_collection(
        resource_class, handle, response,
        individuals, options=None, **kwargs):

    """ Helper to avoid code repetition

    :type resource_class: CollectionResource
    :param handle: AbstractHandle
    :param response: ResponseWrapper
    :param options: dict with query options
    :param individuals: individuals

    :param kwargs: additional parameters for constructor

    :rtype: CollectionResource
    """
    return resource_class(
        handle,
        response=response,
        links=Link.from_dict(response.json["_links"]),
        individuals=individuals,
        options=options,
        **kwargs
    )


class ProjectList(CollectionResource):
    """
    :type handle: copr.client_v2.handlers.ProjectHandle
    """

    def __init__(self, handle, **kwargs):
        super(ProjectList, self).__init__(**kwargs)
        self._handle = handle

    def next_page(self):
        """
        Retrieves next chunk of the Project list for the same query options

        :rtype: :py:class:`.ProjectList`
        """
        return super(ProjectList, self).next_page()

    @property
    def projects(self):
        """ :rtype: list of :py:class:`~.resources.Project` """
        return self._individuals

    @classmethod
    def from_response(cls, handle, response, options):
        individuals = [
            Project.from_response(
                handle=handle,
                data_dict=dict_part,
            )
            for dict_part in response.json["projects"]
        ]
        return _construct_collection(
            cls, handle, response=response,
            individuals=individuals, options=options
        )


class BuildList(CollectionResource):
    """
    :type handle: copr.client_v2.handler.BuildHandle
    """
    def __init__(self, handle, **kwargs):
        super(BuildList, self).__init__(**kwargs)
        self._handle = handle

    def next_page(self):
        """
        Retrieves next chunk of the Build list for the same query options

        :rtype: :py:class:`.BuildList`
        """
        return super(BuildList, self).next_page()

    @property
    def builds(self):
        """
        :rtype: :py:class:`.BuildList`
        """
        return self._individuals

    @classmethod
    def from_response(cls, handle, response, options):
        individuals = [
            Build.from_response(
                handle=handle,
                data_dict=dict_part,
            )
            for dict_part in response.json["builds"]
        ]
        return _construct_collection(
            cls, handle, response=response,
            individuals=individuals, options=options
        )


class ProjectChrootList(CollectionResource):
    """
    List of the :class:`~.ProjectChroot` in the one Project.

    :type handle: copr.client_v2.handlers.ProjectChrootHandle
    """

    def __init__(self, handle, project, **kwargs):
        super(ProjectChrootList, self).__init__(**kwargs)
        self._handle = handle
        self._project = project

    @property
    def chroots(self):
        """
        :rtype: list of :py:class:`~.resources.ProjectChroot`
        """
        return self._individuals

    def enable(self, name):
        """
        Enables mock chroot for the current project

        :rtype: :py:class:`~.OperationResult`
        """
        return self._handle.enable(self._project, name)

    @classmethod
    def from_response(cls, handle, response, project):
        individuals = [
            ProjectChroot.from_response(
                handle=handle,
                data_dict=dict_part,
                project=project
            )
            for dict_part in response.json["chroots"]
        ]

        return _construct_collection(
            cls, handle, response=response,
            individuals=individuals, project=project
        )


class MockChrootList(CollectionResource):
    """
    List of the mock chroots supported by the service

    :type handle: copr.client_v2.handlers.MockChrootHandle
    """

    def __init__(self, handle, **kwargs):
        super(MockChrootList, self).__init__(**kwargs)
        self._handle = handle

    @property
    def chroots(self):
        """
        :rtype: list of :py:class:`~.resources.MockChroot`
        """
        return self._individuals

    @classmethod
    def from_response(cls, handle, response, options):
        individuals = [
            MockChroot.from_response(
                handle=handle,
                data_dict=dict_part,
            )
            for dict_part in response.json["chroots"]
        ]
        return _construct_collection(
            cls, handle, response=response,
            options=options, individuals=individuals
        )


class BuildTaskList(CollectionResource):
    """
    List of build tasks

    :type handle: copr.client_v2.handlers.BuildTaskHandle
    """

    def __init__(self, handle, **kwargs):
        super(BuildTaskList, self).__init__(**kwargs)
        self._handle = handle

    @property
    def build_tasks(self):
        """
        :rtype: list of :py:class:`~.resources.BuildTask`
        """
        return self._individuals

    @classmethod
    def from_response(cls, handle, response, options):
        individuals = [
            BuildTask.from_response(
                handle=handle,
                data_dict=dict_part
            )
            for dict_part in response.json["build_tasks"]
        ]
        return _construct_collection(
            cls, handle, response=response,
            options=options, individuals=individuals
        )
