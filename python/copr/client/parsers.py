__docformat__ = "restructuredtext en"

from .responses import ProjectWrapper, BuildWrapper, ProjectChrootWrapper, PackageWrapper, CoprChrootWrapper


class IParser(object):
    """ Parser interface
    """
    provided_fields = set()

    @staticmethod
    def parse(data, field, **kwargs):
        """
        Creates `value` from field

        :param data: json structure from api
        :param field:

        :return: parsed value
        """
        raise NotImplementedError("Interface doesn't provide fields")


def fabric_simple_fields_parser(fields, name=None):
    class FieldsParser(IParser):
        provided_fields = set(fields)

        @staticmethod
        def parse(data, field, **kwargs):
            if field in FieldsParser.provided_fields:
                if field in data:
                    return data[field]
                else:
                    raise KeyError("Response missing field `{}`".format(field))
            else:
                raise KeyError("Field `{}` not supported by parser".
                               format(field))

    if name:
        FieldsParser.__name__ = str(name)

    return FieldsParser


CommonMsgErrorOutParser = fabric_simple_fields_parser(
    ["output", "message", "error"], "CommonMsgErrorOutParser"
)

BuildConfigParser = fabric_simple_fields_parser(
    ["build_config"], "BuildConfigParser"
)


class ProjectDetailsFieldsParser(IParser):
    provided_fields = set(["description", "instructions", "last_modified", "name"])

    @staticmethod
    def parse(data, field, **kwargs):
        if field in ProjectDetailsFieldsParser.provided_fields:
            if "detail" in data:
                if field in data["detail"]:
                    return data["detail"][field]
                else:
                    raise KeyError("Response missing field `{}`".format(field))
            else:
                raise KeyError("Response missing `detail` section")
        else:
            raise KeyError("Field `{}` not supported by parser".
                           format(field))


class ProjectChrootsParser(IParser):
    provided_fields = set(["chroots"])

    @staticmethod
    def parse(data, field, client=None, **kwargs):
        if field == "chroots":
            if "detail" in data and "yum_repos" in data["detail"]:
                request_kwargs = kwargs.get("request_kwargs")
                return [
                    ProjectChrootWrapper(
                        client=client,
                        username=request_kwargs["username"],
                        projectname=request_kwargs["projectname"],
                        chrootname=chrootname,
                        repo_url=url
                    )
                    for chrootname, url in data["detail"]["yum_repos"].items()
                ]
            else:
                raise KeyError("Response missing data about chroots")
        else:
            raise KeyError("Field `{}` not supported by parser".
                           format(field))


class ProjectListParser(IParser):
    provided_fields = set(["projects_list"])

    @staticmethod
    def parse(data, field, client=None, **kwargs):
        if field == "projects_list":
            if "repos" in data:
                return [
                    ProjectWrapper(
                        client=client,
                        username=prj.get("username", None),
                        # TODO:, sad api doesn't
                        # include username into the response
                        # of user_projects_list

                        # TODO: inconsistency in api between search ans list
                        # user projects
                        projectname=prj.get("name") or prj.get("coprname"),

                        description=prj.get("description"),
                        yum_repos=prj.get("yum_repos"),
                        additional_repos=prj.get("additional_repos"),
                    )
                    for prj in data["repos"]
                ]
            else:
                raise KeyError("Response missing data about projects")
        else:
            raise KeyError("Field `{}` not supported by parser".
                           format(field))


class NewBuildListParser(IParser):
    provided_fields = set(["builds_list"])

    @staticmethod
    def parse(data, field, client=None, **kwargs):
        if field == "builds_list":
            if "ids" in data:
                request_kwargs = kwargs.get("request_kwargs")
                return [
                    BuildWrapper(
                        client=client,
                        build_id=build_id,
                        username=request_kwargs["username"],
                        projectname=request_kwargs["projectname"],

                    ) for build_id in data["ids"]
                ]
            else:
                raise KeyError("Response missing data about new builds")
        else:
            raise KeyError("Field `{}` not supported by parser".
                           format(field))


class PackageListParser(IParser):
    provided_fields = set(["packages_list"])

    @staticmethod
    def parse(data, field, client=None, **kwargs):
        request_kwargs = kwargs.get("request_kwargs")
        if field == "packages_list":
            if "packages" in data:
                ownername=request_kwargs["ownername"]
                projectname=request_kwargs["projectname"]
                return [PackageWrapper(client=client, ownername=ownername, projectname=projectname, **package) for package in data["packages"]]
            else:
                raise KeyError("Response missing data about projects")
        else:
            raise KeyError("Field `{}` not supported by parser".format(field))


class PackageParser(IParser):
    provided_fields = set(["package"])

    @staticmethod
    def parse(data, field, client=None, **kwargs):
        request_kwargs = kwargs.get("request_kwargs")
        if field == "package":
            if "package" in data:
                ownername=request_kwargs["ownername"]
                projectname=request_kwargs["projectname"]
                return PackageWrapper(client=client, ownername=ownername, projectname=projectname, **data['package'])
            else:
                raise KeyError("Response missing data about projects")
        else:
            raise KeyError("Field `{}` not supported by parser".format(field))


class CoprChrootParser(IParser):
    provided_fields = set(["chroot"])

    @staticmethod
    def parse(data, field, client=None, **kwargs):
        request_kwargs = kwargs.get("request_kwargs")
        if field == "chroot":
            if "chroot" in data:
                ownername=request_kwargs["ownername"]
                projectname=request_kwargs["projectname"]
                return CoprChrootWrapper(client=client, ownername=ownername, projectname=projectname, **data['chroot'])
            else:
                raise KeyError("Response missing data about projects")
        else:
            raise KeyError("Field `{}` not supported by parser".format(field))
