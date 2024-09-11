import random
import string

# We don't know how to define the enums without `class`.
# pylint: disable=too-few-public-methods

class EnumType(type):
    def _wrap(cls, attr=None):
        if attr is None:
            raise NotImplementedError
        if isinstance(attr, int):
            for k, v in cls.vals.items():
                if v == attr:
                    return k
            raise KeyError("num {0} is not mapped".format(attr))
        return cls.vals[attr]
    def __call__(cls, attr):
        return cls._wrap(attr)
    def __getattr__(cls, attr):
        return cls._wrap(attr)


class ActionTypeEnum(metaclass=EnumType):
    vals = {
        "delete": 0,
        "rename": 1,
        "legal-flag": 2,
        "createrepo": 3,
        "update_comps": 4,
        "gen_gpg_key": 5,
        "rawhide_to_release": 6,
        "fork": 7,
        "update_module_md": 8,
        "build_module": 9,
        "cancel_build": 10,
        "remove_dirs": 11,
    }


class ActionResult(metaclass=EnumType):
    vals = {
        'WAITING': 0,
        'SUCCESS': 1,
        'FAILURE': 2,
    }


class DefaultActionPriorityEnum(metaclass=EnumType):
    """
    The higher the 'priority' is, the later the task is taken.
    Keep actions priority in range -100 to 100
    """
    vals = {
        "gen_gpg_key": -70,
        "cancel_build": -10,
        "createrepo": 0,
        "fork": 0,
        "build_module": 0,
        "update_comps": 0,
        "delete": 60,
        "rawhide_to_release": 70,
    }


class ActionPriorityEnum(metaclass=EnumType):
    """
    Naming/assigning the values is a little bit tricky because
    how the current implementation works (i.e. it is inverted).
    However, from the most abstract point of view,
    "highest priority" means "do this as soon as possible"
    """
    vals = {"highest": -99, "lowest": 99}


class BackendResultEnum(metaclass=EnumType):
    vals = {"waiting": 0, "success": 1, "failure": 2}


class RoleEnum(metaclass=EnumType):
    vals = {"user": 0, "admin": 1}


class StatusEnum(metaclass=EnumType):
    vals = {
        "failed": 0,     # build failed
        "succeeded": 1,  # build succeeded
        "canceled": 2,   # build was canceled
        "running": 3,    # SRPM or RPM build is running
        "pending": 4,    # build(-chroot) is waiting to be picked
        "skipped": 5,    # if there was this package built already
        "starting": 6,   # build was picked by worker but no VM initialized yet
        "importing": 7,  # SRPM is being imported into dist-git
        "forked": 8,     # build(-chroot) was forked
        "waiting": 9,    # build(-chroot) is waiting for something else to finish
        "unknown": 1000, # undefined
    }


def _filtered_status_enum(keys):
    new_values = {}
    for key, value in StatusEnum.vals.items():
        if key in keys:
            new_values[key] = value
    return new_values


class ModuleStatusEnum(StatusEnum):
    vals = _filtered_status_enum(["canceled", "running", "starting", "pending",
                                  "failed", "succeeded", "waiting", "unknown"])


class BuildSourceEnum(metaclass=EnumType):
    vals = {"unset": 0,
            "link": 1,  # url
            "upload": 2,  # pkg, tmp, url
            "pypi": 5, # package_name, version, python_versions
            "rubygems": 6, # gem_name
            "scm": 8, # type, clone_url, committish, subdirectory, spec, srpm_build_method
            "custom": 9, # user-provided script to build sources
            "distgit": 10, # distgit_instance, package_name, committish
           }


class FailTypeEnum(metaclass=EnumType):
    vals = {"unset": 0,
            # General errors mixed with errors for SRPM URL/upload:
            "unknown_error": 1,
            "build_error": 2,
            "srpm_import_failed": 3,
            "srpm_download_failed": 4,
            "srpm_query_failed": 5,
            "import_timeout_exceeded": 6,
            "git_clone_failed": 31,
            "git_wrong_directory": 32,
            "git_checkout_error": 33,
            "srpm_build_error": 34,
           }


class StorageEnum(metaclass=EnumType):
    """
    Supported storages
    """
    vals = {"backend": 0, "pulp": 1}
