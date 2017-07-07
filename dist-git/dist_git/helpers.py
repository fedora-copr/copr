import os
import logging
import ConfigParser
import re
import string
import munch

# todo: replace with munch, check availability in epel
from bunch import Bunch

log = logging.getLogger(__name__)


class ConfigReaderError(Exception):
    pass


class EnumType(type):
    def __call__(self, attr):
        if isinstance(attr, int):
            for k, v in self.vals.items():
                if v == attr:
                    return k
            raise KeyError("num {0} is not mapped".format(attr))
        else:
            return self.vals[attr]

# The same enum is also in frontend's helpers.py
class FailTypeEnum(object):
    __metaclass__ = EnumType
    vals = {"unset": 0,
            # General errors mixed with errors for SRPM URL/upload:
            "unknown_error": 1,
            "build_error": 2,
            "srpm_import_failed": 3,
            "srpm_download_failed": 4,
            "srpm_query_failed": 5,
            # Git and Tito errors:
            "tito_general_error": 30,
            "git_clone_failed": 31,
            "git_wrong_directory": 32,
            "git_checkout_error": 33,
            "srpm_build_error": 34,
           }


def _get_conf(cp, section, option, default, mode=None):
    """
    To make returning items from config parser less irritating

    :param mode: convert obtained value, possible modes:
      - None (default): do nothing
      - "bool" or "boolean"
      - "int"
      - "float"
    """

    if cp.has_section(section) and cp.has_option(section, option):
        if mode is None:
            return cp.get(section, option)
        elif mode in ["bool", "boolean"]:
            return cp.getboolean(section, option)
        elif mode == "int":
            return cp.getint(section, option)
        elif mode == "float":
            return cp.getfloat(section, option)
        elif mode == "path":
            path = cp.get(section, option)
            if path.startswith("~"):
                path = os.path.expanduser(path)
            path = os.path.abspath(path)
            path = os.path.normpath(path)

            return path
    return default


class DistGitConfigReader(object):
    def __init__(self, config_file=None):
        self.config_file = config_file or "/etc/copr/copr-dist-git.conf"

    def read(self):
        try:
            opts = self._read_unsafe()
            return opts

        except ConfigParser.Error as e:
            raise ConfigReaderError(
                "Error parsing config file: {0}: {1}".format(
                    self.config_file, e))

    def _read_unsafe(self):
        cp = ConfigParser.ConfigParser()
        cp.read(self.config_file)

        opts = Bunch()

        opts.frontend_base_url = _get_conf(
            cp, "dist-git", "frontend_base_url", "http://copr-fe")

        opts.frontend_auth = _get_conf(
            cp, "dist-git", "frontend_auth", "PASSWORDHERE")

        opts.log_dir = _get_conf(
            cp, "dist-git", "log_dir", "/var/log/copr-dist-git"
        )

        opts.per_task_log_dir = _get_conf(
            cp, "dist-git", "per_task_log_dir", "/var/lib/copr-dist-git/per-task-logs"
        )

        opts.sleep_time = _get_conf(
            cp, "dist-git", "sleep_time", 15, mode="int"
        )

        # Whether to use multi-threaded dist-git or not
        # It might be useful to set False for debugging
        # while ipdb does not support multiple threads.
        opts.multiple_threads = _get_conf(
            cp, "dist-git", "multiple_threads", True, mode="bool"
        )

        opts.pool_busy_sleep_time = _get_conf(
            cp, "dist-git", "pool_busy_sleep_time", 0.5, mode="float"
        )

        opts.cgit_pkg_list_location = _get_conf(
            cp, "dist-git", "cgit_pkg_list_location", "/var/lib/copr-dist-git/cgit_pkg_list"
        )

        opts.lookaside_location = _get_conf(
            cp, "dist-git", "lookaside_location", "/var/lib/dist-git/cache/lookaside/pkgs/"
        )

        opts.mock_scm_chroot = _get_conf(
            cp, "dist-git", "mock_scm_chroot", "fedora-rawhide-x86_64"
        )

        opts.git_base_url = _get_conf(
            cp, "dist-git", "git_base_url", "/var/lib/dist-git/git/%(module)s"
        )

        return opts


def substitute_spec_macros(spec_data, elem):
    """
    Substitute spec variable with its value or
    with empty string if definition is not found.

    :param str spec_data: text of a spec file
    :param str elem: value with macros in it

    :returns str: elem with the macros substituted
    """
    macros = re.findall(r'%{([^}]*)}', elem)
    if not macros:
        return elem
    for macro in macros:
        flags = re.MULTILINE
        pattern = r'^\s*(%global|%define)\s+{}\s+([^\s]*)'.format(macro)
        pattern_c = re.compile(pattern, flags)
        matches = pattern_c.search(spec_data)
        if not matches:
            substitution = ''
        else:
            substitution = substitute_spec_macros(spec_data, matches.group(2))
        elem = string.replace(elem, '%{'+macro+'}', substitution)
    return elem


def get_pkg_info(spec_path):
    """
    Extract information from a spec file by using regular
    expression parsing. We do not use rpm library here
    because the spec to be parsed may contain constructs
    supported only in the target build environment.

    :param str spec_path: filesystem path to spec file

    :return Munch: info about the package like name, version, ...
    """
    try:
        spec_file = open(spec_path, 'r')
        spec_data = spec_file.read()
        spec_file.close()
    except IOError as e:
        raise PackageImportException(str(e))

    flags = re.IGNORECASE | re.MULTILINE

    pattern = re.compile('^name:\s*([^\s]*)', flags)
    match = pattern.search(spec_data)
    raw_name = match.group(1) if match else ''
    name = substitute_spec_macros(spec_data, raw_name)

    pattern = re.compile('^version:\s*([^\s]*)', flags)
    match = pattern.search(spec_data)
    raw_version = match.group(1) if match else ''
    version = substitute_spec_macros(spec_data, raw_version)

    pattern = re.compile('^release:\s*([^\s]*)', flags)
    match = pattern.search(spec_data)
    raw_release = match.group(1) if match else ''
    release = substitute_spec_macros(spec_data, raw_release)

    pattern = re.compile('^epoch:\s*([^\s]*)', flags)
    match = pattern.search(spec_data)
    raw_epoch = match.group(1) if match else ''
    epoch = substitute_spec_macros(spec_data, raw_epoch)

    nv = '{}-{}'.format(name, version)
    vr = '{}-{}'.format(version, release)
    nvr = '{}-{}'.format(name, vr)

    if epoch:
        evr = '{}:{}'.format(epoch, vr)
        envr = '{}:{}'.format(epoch, nvr)
    else:
        evr = vr
        envr = nvr

    return munch.Munch(
        name=name,
        version=version,
        release=release,
        epoch=epoch,
        nv=nv,
        vr=vr,
        evr=evr,
        nvr=nvr,
        envr=envr
    )
