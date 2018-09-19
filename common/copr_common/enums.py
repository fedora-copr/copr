import random
import string

from six import with_metaclass


class EnumType(type):
    def __call__(self, attr):
        if isinstance(attr, int):
            for k, v in self.vals.items():
                if v == attr:
                    return k
            raise KeyError("num {0} is not mapped".format(attr))
        else:
            return self.vals[attr]


class ActionTypeEnum(with_metaclass(EnumType, object)):
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
    }


class BackendResultEnum(with_metaclass(EnumType, object)):
    vals = {"waiting": 0, "success": 1, "failure": 2}


class RoleEnum(with_metaclass(EnumType, object)):
    vals = {"user": 0, "admin": 1}


class StatusEnum(with_metaclass(EnumType, object)):
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


class ModuleStatusEnum(with_metaclass(EnumType, object)):
    vals = {"pending": 0, "succeeded": 1, "failed": 2}


class BuildSourceEnum(with_metaclass(EnumType, object)):
    vals = {"unset": 0,
            "link": 1,  # url
            "upload": 2,  # pkg, tmp, url
            "pypi": 5, # package_name, version, python_versions
            "rubygems": 6, # gem_name
            "scm": 8, # type, clone_url, committish, subdirectory, spec, srpm_build_method
            "custom": 9, # user-provided script to build sources
           }


class FailTypeEnum(with_metaclass(EnumType, object)):
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
