# pylint: disable=R0903
# coding: utf-8
from collections import Iterable
from six import with_metaclass

from ..util import UnicodeMixin

from .entities import Link, ProjectEntity, ProjectChrootEntity, BuildEntity, MockChrootEntity
from .schemas import EmptySchema, BuildSchema, ProjectSchema, ProjectChrootSchema, MockChrootSchema


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
        return type.__new__(mcs, class_name, bases, class_attrs)


# pylint: disable=E1101
class IndividualResource(with_metaclass(EntityFieldsMetaClass, UnicodeMixin)):
    """
    :type handle: client_v2.handlers.AbstractHandle or None
    :type response: ResponseWrapper or None
    :type links: (dict of (str, Link)) or None
    """
    _schema = EmptySchema(strict=True)

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
            # res.extend([x for x in dir(self._entity) if not x.startswith("_")])
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
        return "{}{}".format(self.root_url, self.get_href_by_name(resource_name))

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
        return self._handle.get_one(self.id)

    def cancel(self):
        return self._handle.cancel(self._entity)

    def delete(self):
        return self._handle.delete(self.id)


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

        :rtype: :py:class:`~copr.client_v2.resources.OperationResult`
        """
        return self._handle.update(self._entity)

    def delete(self):
        """ Updates project using the current state

        :rtype: :py:class:`~copr.client_v2.resources.OperationResult`
        """
        return self._handle.delete(self.id)

    def get_self(self):
        """ Retrieves fresh project object from the service

        :rtype: :py:class:`~copr.client_v2.resources.Project`
        """
        return self._handle.get_one(self.id)

    def get_builds(self, **query_options):
        """ Get builds owned by this project

        :param query_options: see :py:meth:`.handlers.BuildHandle.get_list`
        :rtype: :py:class:`~.BuildsList`
        """
        handle = self._handle.get_builds_handle()
        return handle.get_list(project_id=self.id, **query_options)

    def get_project_chroot(self, name):
        """ Retrieves project chroot object by the given name

        :param str name: mock chroot name
        :rtype: :py:class:`~copr.client_v2.resources.ProjectChroot`
        """
        handle = self._handle.get_project_chroots_handle()
        return handle.get_one(self, name)

    def get_project_chroot_list(self):
        """ Retrieves project chroots list

        :rtype: :py:class:`~copr.client_v2.resources.ProjectChrootList`
        """
        handle = self._handle.get_project_chroots_handle()
        return handle.get_list(self)

    def enable_project_chroot(self, name):
        """
        Enables given chroot for this project

        :param str name: mock chroot name
        :rtype: :py:class:`~copr.client_v2.resources.OperationResult`
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
        return self._handle.disable(self._project, self.name)

    def update(self):
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
            out += u" status: {}".format(self._response.status_code)
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

    @classmethod
    def from_response(cls, handle, response, options):
        raise NotImplementedError


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
        data_dict = response.json
        result = ProjectList(
            handle,
            response=response,
            links=Link.from_dict(data_dict["_links"]),
            individuals=[
                Project.from_response(
                    handle=handle,
                    data_dict=dict_part,
                )
                for dict_part in data_dict["projects"]
            ],
            options=options
        )
        return result


class BuildList(CollectionResource):
    """
    :type handle: copr.client_v2.handler.BuildHandle
    """
    def __init__(self, handle, **kwargs):
        super(BuildList, self).__init__(**kwargs)
        self._handle = handle

    @property
    def builds(self):
        return self._individuals

    @classmethod
    def from_response(cls, handle, response, options):
        data_dict = response.json
        result = BuildList(
            handle,
            response=response,
            links=Link.from_dict(data_dict["_links"]),
            individuals=[
                Build.from_response(
                    handle=handle,
                    data_dict=dict_part,
                )
                for dict_part in data_dict["builds"]
            ],
            options=options
        )
        return result


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
        data_dict = response.json
        return ProjectChrootList(
            handle,
            project=project,
            response=response,
            links=Link.from_dict(data_dict["_links"]),
            individuals=[
                ProjectChroot.from_response(
                    handle=handle,
                    data_dict=dict_part,
                    project=project
                )
                for dict_part in data_dict["chroots"]
            ]
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

        return self._individuals

    @classmethod
    def from_response(cls, handle, response, options):
        data_dict = response.json
        return MockChrootList(
            handle,
            response=response,
            links=Link.from_dict(data_dict["_links"]),
            individuals=[
                MockChroot.from_response(
                    handle=handle,
                    data_dict=dict_part,
                )
                for dict_part in data_dict["chroots"]
            ],
            options=options
        )
