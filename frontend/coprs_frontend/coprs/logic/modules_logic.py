import os
import time
import base64
import json
import requests
import modulemd
from collections import defaultdict
from sqlalchemy import and_
from datetime import datetime
from coprs import models
from coprs import db
from coprs import exceptions
from coprs.logic import builds_logic
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
    def get_by_nsv_str(cls, copr, nsv):
        name, stream, version = nsv.split("-")
        return cls.get_by_nsv(copr, name, stream, version)

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
    def from_modulemd(cls, mmd):
        yaml_b64 = base64.b64encode(mmd.dumps().encode("utf-8")).decode("utf-8")
        return models.Module(name=mmd.name, stream=mmd.stream, version=mmd.version, summary=mmd.summary,
                             description=mmd.description, yaml_b64=yaml_b64)

    @classmethod
    def validate(cls, mmd):
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

    @classmethod
    def set_defaults_for_optional_params(cls, mmd, filename=None):
        mmd.name = mmd.name or str(os.path.splitext(filename)[0])
        mmd.stream = mmd.stream or "master"
        mmd.version = mmd.version or int(datetime.now().strftime("%Y%m%d%H%M%S"))


class ModuleBuildFacade(object):
    def __init__(self, user, copr, yaml, filename=None):
        self.user = user
        self.copr = copr
        self.yaml = yaml
        self.filename = filename

        self.modulemd = ModulesLogic.yaml2modulemd(yaml)
        ModulesLogic.set_defaults_for_optional_params(self.modulemd, filename=filename)
        ModulesLogic.validate(self.modulemd)

    def submit_build(self):
        module = ModulesLogic.add(self.user, self.copr, ModulesLogic.from_modulemd(self.modulemd))
        self.add_builds(self.modulemd.components.rpms, module)
        return module

    @classmethod
    def get_build_batches(cls, rpms):
        """
        Determines Which component should be built in which batch. Returns an ordered list of grouped components,
        first group of components should be built as a first batch, second as second and so on.
        Particular components groups are represented by dicts and can by built in a random order within the batch.
        :return: list of lists
        """
        batches = defaultdict(dict)
        for pkgname, rpm in rpms.items():
            batches[rpm.buildorder][pkgname] = rpm
        return [batches[number] for number in sorted(batches.keys())]

    def add_builds(self, rpms, module):
        for group in self.get_build_batches(rpms):
            batch = models.Batch()
            db.session.add(batch)
            for pkgname, rpm in group.items():
                clone_url = self.get_clone_url(pkgname, rpm)
                build = builds_logic.BuildsLogic.create_new_from_scm(self.user, self.copr, scm_type="git",
                                                                     clone_url=clone_url, committish=rpm.ref)
                build.batch = batch
                build.batch_id = batch.id
                build.module_id = module.id
                db.session.add(build)

    def get_clone_url(self, pkgname, rpm):
        return rpm.repository if rpm.repository else self.default_distgit.format(pkgname=pkgname)

    @property
    def default_distgit(self):
        # @TODO move to better place
        return "https://src.fedoraproject.org/rpms/{pkgname}"


class ModulemdGenerator(object):
    def __init__(self, name="", stream="", version=0, summary="", config=None):
        self.config = config
        self.mmd = modulemd.ModuleMetadata()
        self.mmd.name = name
        self.mmd.stream = stream
        self.mmd.version = version
        self.mmd.summary = summary

    @property
    def nsv(self):
        return "{}-{}-{}".format(self.mmd.name, self.mmd.stream, self.mmd.version)

    def add_api(self, packages):
        for package in packages:
            self.mmd.api.add_rpm(str(package))

    def add_filter(self, packages):
        for package in packages:
            self.mmd.filter.add_rpm(str(package))

    def add_profiles(self, profiles):
        for i, values in profiles:
            name, packages = values
            self.mmd.profiles[name] = modulemd.profile.ModuleProfile()
            for package in packages:
                self.mmd.profiles[name].add_rpm(str(package))

    def add_components(self, packages, filter_packages, builds):
        build_ids = sorted(list(set([int(id) for p, id in zip(packages, builds)
                                     if p in filter_packages])))
        for package in filter_packages:
            build_id = builds[packages.index(package)]
            build = builds_logic.BuildsLogic.get_by_id(build_id).first()
            build_chroot = self._build_chroot(build)
            buildorder = build_ids.index(int(build.id))
            rationale = "User selected the package as a part of the module"
            self.add_component(package, build, build_chroot, rationale, buildorder)

    def _build_chroot(self, build):
        chroot = None
        for chroot in build.build_chroots:
            if chroot.name == "custom-1-x86_64":
                break
        return chroot

    def add_component(self, package_name, build, chroot, rationale, buildorder=1):
        ref = str(chroot.git_hash) if chroot else ""
        distgit_url = self.config["DIST_GIT_URL"].replace("/cgit", "/git")
        url = os.path.join(distgit_url, build.copr.full_name, "{}.git".format(build.package.name))
        self.mmd.components.add_rpm(str(package_name), rationale,
                                    repository=url, ref=ref,
                                    buildorder=buildorder)

    def add_requires(self, module, stream):
        self.mmd.add_requires(module, stream)

    def add_buildrequires(self, module, stream):
        self.mmd.add_buildrequires(module, stream)

    def generate(self):
        return self.mmd.dumps()

    def dump(self, handle):
        return self.mmd.dump(handle)


class MBSProxy(object):
    def __init__(self, mbs_url, user_name=None):
        self.url = mbs_url
        self.user = user_name

    def post(self, json=None, data=None, files=None):
        request = requests.post(self.url, verify=False,
                                json=json, data=data, files=files)
        return MBSResponse(request)

    def build_module(self, owner, project, nsv, modulemd):
        return self.post(
            data={"owner": self.user, "copr_owner": owner, "copr_project": project},
            files={"yaml": ("{}.yaml".format(nsv), modulemd)},
        )


class MBSResponse(object):
    def __init__(self, response):
        self.response = response

    @property
    def failed(self):
        return self.response.status_code != 201

    @property
    def message(self):
        if self.response.status_code in [500, 403, 404]:
            return "Error from MBS: {} - {}".format(self.response.status_code, self.response.reason)
        resp = json.loads(self.response.content)
        if self.response.status_code != 201:
            return "Error from MBS: {}".format(resp["message"])
        return "Created module {}-{}-{}".format(resp["name"], resp["stream"], resp["version"])


class ModuleProvider(object):
    def __init__(self, filename, yaml):
        self.filename = filename
        self.yaml = yaml

    @classmethod
    def from_input(cls, obj):
        if hasattr(obj, "read"):
            return cls.from_file(obj)
        return cls.from_url(obj)

    @classmethod
    def from_file(cls, ref):
        return cls(ref.filename, ref.read())

    @classmethod
    def from_url(cls, url):
        if not url.endswith(".yaml"):
            raise ValidationError("This URL doesn't point to a .yaml file")

        request = requests.get(url)
        if request.status_code != 200:
            raise requests.RequestException("This URL seems to be wrong")
        return cls(os.path.basename(url), request.text)
