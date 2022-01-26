import os
import time
import base64
import requests
from collections import defaultdict
from sqlalchemy import and_
from datetime import datetime
import modulemd_tools.yaml
from coprs import models
from coprs import db
from coprs import exceptions
from coprs.logic import builds_logic
from coprs.logic.dist_git_logic import DistGitLogic
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
        try:
            name, stream, version = nsv.rsplit("-", 2)
            return cls.get_by_nsv(copr, name, stream, version)
        except ValueError:
            raise exceptions.BadRequest("The '{}' is not a valid NSV".format(nsv))

    @classmethod
    def get_multiple(cls):
        return models.Module.query.order_by(models.Module.id.desc())

    @classmethod
    def get_multiple_by_copr(cls, copr):
        return cls.get_multiple().filter(models.Module.copr_id == copr.id)

    @classmethod
    def yaml2modulemd(cls, yaml):
        try:
            modulemd_tools.yaml.validate(yaml)
            mmd = modulemd_tools.yaml._yaml2stream(yaml)
            return mmd
        except (RuntimeError, ValueError) as ex:
            raise exceptions.BadRequest("Invalid modulemd yaml - {0}" .format(str(ex)))

    @classmethod
    def from_modulemd(cls, mmd):
        try:
            yaml = modulemd_tools.yaml._stream2yaml(mmd)
            modulemd_tools.yaml.validate(yaml)
        except RuntimeError as ex:
            raise exceptions.BadRequest("Unsupported or malformed modulemd yaml - {0}"
                                        .format(str(ex)))  # pylint: disable=no-member

        yaml_b64 = base64.b64encode(yaml.encode("utf-8")).decode("utf-8")
        return models.Module(name=mmd.get_module_name(), stream=mmd.get_stream_name(),
                                version=mmd.get_version(), summary=mmd.get_summary(),
                                description=mmd.get_description(), yaml_b64=yaml_b64)

    @classmethod
    def validate(cls, mmd):
        if not all([mmd.get_module_name(), mmd.get_stream_name(), mmd.get_version()]):
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
    def set_defaults_for_optional_params(cls, mmd, yaml, filename=None):
        name = mmd.get_module_name() or str(os.path.splitext(filename)[0])
        stream = mmd.get_stream_name() or "master"
        version = mmd.get_version() or int(datetime.now().strftime("%Y%m%d%H%M%S"))
        return modulemd_tools.yaml.update(yaml, name, stream, version)


class ModuleBuildFacade(object):
    def __init__(self, user, copr, yaml, filename=None, distgit_name=None):
        self.user = user
        self.copr = copr
        self.filename = filename
        self.distgit = DistGitLogic.get_with_default(distgit_name)

        try:
            yaml = modulemd_tools.yaml.upgrade(yaml, 2)
        except ValueError as ex:
            raise exceptions.BadRequest("Invalid modulemd yaml - {0}" .format(str(ex)))

        modulemd = modulemd_tools.yaml._yaml2stream(yaml)
        self.yaml = ModulesLogic.set_defaults_for_optional_params(modulemd, yaml, filename)
        self.modulemd = modulemd_tools.yaml._yaml2stream(self.yaml)
        ModulesLogic.validate(self.modulemd)

    def submit_build(self):
        module = ModulesLogic.add(self.user, self.copr, ModulesLogic.from_modulemd(self.modulemd))
        if not self.platform_chroots:
            raise ValidationError("Module platform is {} which doesn't match to any chroots enabled in {} project"
                                  .format(self.platform, self.copr.full_name))
        components = {name: self.modulemd.get_rpm_component(name)
                      for name in self.modulemd.get_rpm_component_names()}
        self.add_builds(components, module)
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
            batches[rpm.get_buildorder()][pkgname] = rpm
        return [batches[number] for number in sorted(batches.keys())]

    @property
    def platform(self):
        if not self.modulemd.get_dependencies():
            return []

        streams = set()
        for dependencies in self.modulemd.get_dependencies():
            if not "platform" in dependencies.get_buildtime_modules():
                continue
            streams.update(dependencies.get_buildtime_streams("platform"))
        return list(streams)

    @property
    def platform_chroots(self):
        """
        Return a list of chroot names based on buildrequired platform and enabled chroots for the project.
        Example: Copr chroots are ["fedora-22-x86-64", "fedora-23-x86_64"] and modulemd specifies "f23" as a platform,
                 then `platform_chroots` are ["fedora-23-x86_64"]
                 Alternatively, the result will be same for "-f22" platform
        :return: list of strings
        """

        # Just to be sure, that all chroot abbreviations from platform are in expected format, e.g. f28 or -f30
        for abbrev in self.platform:
            if not (abbrev.startswith(("f", "-f")) and abbrev.lstrip("-f").isnumeric()):
                raise ValidationError("Unexpected platform '{}', it should be e.g. f28 or -f30".format(abbrev))

        chroot_archs = {}
        for chroot in self.copr.active_chroots:
            chroot_archs.setdefault(chroot.name_release, []).append(chroot.arch)

        def abbrev2chroots(abbrev):
            name_release = abbrev.replace("-", "").replace("f", "fedora-")
            return ["{}-{}".format(name_release, arch) for arch in chroot_archs.get(name_release, [])]

        exclude_chroots = set()
        select_chroots = set()
        for abbrev in self.platform:
            abbrev_chroots = abbrev2chroots(abbrev)
            if not abbrev_chroots:
                raise ValidationError("Module platform stream {} doesn't match to any enabled chroots in the {} project"
                                      .format(abbrev, self.copr.full_name))
            (exclude_chroots if abbrev.startswith("-") else select_chroots).update(abbrev_chroots)

        chroots = {chroot.name for chroot in self.copr.active_chroots}
        chroots -= exclude_chroots
        if select_chroots:
            chroots &= select_chroots
        return chroots


    def add_builds(self, rpms, module):
        blocked_by_id = None
        for group in self.get_build_batches(rpms):
            batch = models.Batch()
            batch.blocked_by_id = blocked_by_id
            db.session.add(batch)
            for pkgname, rpm in group.items():
                build = self.get_build(rpm, pkgname)
                build.batch = batch
                build.batch_id = batch.id
                build.module_id = module.id
                db.session.add(build)

            # Every batch needs to by blocked by the previous one
            blocked_by_id = batch.id

    def get_build(self, rpm, pkgname):
        """
        Create a (DistGit method) Build instance for the given RPM and PKGNAME
        """
        build_options = {}

        # User wants to use a different clone_url, using the
        # 'components.rpms.<component>.repository' option.  Perhaps
        # a different dist-git instance is needed.
        if rpm.get_repository():
            build_options["clone_url"] = rpm.get_repository()

        return builds_logic.BuildsLogic.create_new_from_distgit(
            self.user, self.copr,
            pkgname, distgit_name=self.distgit.name,
            committish=rpm.get_ref(),
            chroot_names=self.platform_chroots,
            **build_options,
        )

    def get_clone_url(self, pkgname, rpm):
        if rpm.get_repository():
            return rpm.get_repository()

        return self.distgit.package_clone_url(pkgname)


class ModulemdGenerator(object):
    def __init__(self, name="", stream="", version=0, summary="", config=None):
        self.config = config
        self.yaml = modulemd_tools.yaml.create(name, stream)
        self.yaml = modulemd_tools.yaml.update(self.yaml, version=version, summary=summary,
                                               module_licenses=["unknown"])

    @property
    def nsv(self):
        return "{}-{}-{}".format(self.mmd.get_module_name(),
                                 self.mmd.get_stream_name(),
                                 self.mmd.get_version())

    @property
    def mmd(self):
        return modulemd_tools.yaml._yaml2stream(self.yaml)

    def add_api(self, packages):
        self.yaml = modulemd_tools.yaml.update(self.yaml, api=packages)

    def add_filter(self, packages):
        self.yaml = modulemd_tools.yaml.update(self.yaml, filters=packages)

    def add_profiles(self, profiles):
        self.yaml = modulemd_tools.yaml.update(self.yaml, profiles=dict(profiles))

    def add_components(self, packages, components_rpms, builds):
        components = []
        build_ids = sorted(list(set([int(id) for p, id in zip(packages, builds)
                                     if p in components_rpms])))
        for package in components_rpms:
            build_id = builds[packages.index(package)]
            build = builds_logic.BuildsLogic.get_by_id(build_id).first()
            chroot = self._build_chroot(build)

            repository = os.path.join(self.config["DIST_GIT_CLONE_URL"],
                                      build.copr.full_name,
                                      "{}.git".format(build.package.name))

            components.append({
                "name": package,
                "rationale": "User selected the package as a part of the module",
                "repository": repository,
                "ref": chroot.git_hash if chroot else "",
                "buildorder": build_ids.index(int(build.id)),

            })
        self.yaml = modulemd_tools.yaml.update(self.yaml, components=components)

    def _build_chroot(self, build):
        chroot = None
        for chroot in build.build_chroots:
            if chroot.name == "custom-1-x86_64":
                break
        return chroot

    def generate(self):
        return self.yaml


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
        return cls(ref.filename, ref.read().decode("utf-8"))

    @classmethod
    def from_url(cls, url):
        if not url.endswith(".yaml"):
            raise ValidationError("This URL doesn't point to a .yaml file")

        request = requests.get(url)
        if request.status_code != 200:
            raise requests.RequestException("This URL seems to be wrong")
        return cls(os.path.basename(url), request.text)
