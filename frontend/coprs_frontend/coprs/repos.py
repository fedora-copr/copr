"""
External repositories helper functions
"""


import re
import posixpath
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import flask
from sqlalchemy.orm.exc import NoResultFound
from coprs import app
from coprs.logic.coprs_logic import CoprDirsLogic


def generate_repo_url(mock_chroot, url, arch=None):
    """ Generates url with build results for .repo file.
    No checks if copr or mock_chroot exists.
    """
    os_version = mock_chroot.os_version

    if mock_chroot.os_release == "fedora":
        os_version = "$releasever"

    if mock_chroot.os_release == "centos-stream":
        os_version = "$releasever"

    if mock_chroot.os_release == "opensuse-leap":
        os_version = "$releasever"

    if mock_chroot.os_release == "mageia":
        if mock_chroot.os_version != "cauldron":
            os_version = "$releasever"

    url = posixpath.join(
        url, "{0}-{1}-{2}/".format(mock_chroot.os_release,
                                   os_version, arch or '$basearch'))

    return url


def generate_repo_name(repo_url):
    """ based on url, generate repo name """
    repo_url = re.sub("[^a-zA-Z0-9]", '_', repo_url)
    repo_url = re.sub("(__*)", '_', repo_url)
    repo_url = re.sub("(_*$)|^_*", '', repo_url)
    return repo_url


def is_copr_repo(repo_url):
    """
    Is the repository in the copr://foo/bar format?
    """
    return copr_repo_fullname(repo_url) is not None


def copr_repo_fullname(repo_url):
    """
    For a copr://foo/bar repository, return foo/bar
    """
    parsed_url = urlparse(repo_url)
    if parsed_url.scheme != "copr":
        return None
    return parsed_url.netloc + parsed_url.path


def pre_process_repo_url(chroot, repo_url):
    """
    Expands variables and sanitize repo url to be used for mock config
    """
    parsed_url = urlparse(repo_url)
    query = parse_qs(parsed_url.query)

    if parsed_url.scheme == "copr":
        user = parsed_url.netloc
        prj = parsed_url.path.split("/")[1]
        try:
            coprdir = CoprDirsLogic.get_by_ownername(user, prj).one()
            repo_url = "{0}/{1}/".format(coprdir.repo_url, chroot)
        except NoResultFound:
            repo_url = "/".join([
                flask.current_app.config["BACKEND_BASE_URL"],
                "results", user, prj, chroot
            ]) + "/"

    elif "priority" in query:
        query.pop("priority")
        query_string = urlencode(query, doseq=True)
        parsed_url = parsed_url._replace(query=query_string)
        repo_url = urlunparse(parsed_url)

    repo_url = repo_url.replace("$chroot", chroot)
    repo_url = repo_url.replace("$distname", chroot.rsplit("-", 2)[0])
    return repo_url


def parse_repo_params(repo, supported_keys=None):
    """
    :param repo: str repo from Copr/CoprChroot/Build/...
    :param supported_keys list of supported optional parameters
    :return: dict of optional parameters parsed from the repo URL
    """
    supported_keys = supported_keys or ["priority"]
    params = {}
    qs = parse_qs(urlparse(repo).query)
    for k, v in qs.items():
        if k in supported_keys:
            # parse_qs returns values as lists, but we allow setting the param only once,
            # so we can take just first value from it
            value = int(v[0]) if v[0].isnumeric() else v[0]
            params[k] = value
    return params


def generate_repo_id_and_name(copr, copr_dir_name, multilib=False, dep_idx=None,
                              dependent=None):
    """
    Return (repo_id, repo_name) for a given copr.  If multilib is True, the
    rpeo_id has a specific suffix, if the repo is dependency of the dependend,
    the repo_id has a specific prefix.
    """
    repo_id = "{0}:{1}:{2}:{3}{4}".format(
        "coprdep" if dep_idx else "copr",
        app.config["PUBLIC_COPR_HOSTNAME"].split(":")[0],
        copr.owner_name.replace("@", "group_"),
        copr_dir_name,
        ":ml" if multilib else ""
    )

    if dep_idx and dependent:
        name = "Copr {0}/{1}/{2} runtime dependency #{3} - {4}/{5}".format(
            app.config["PUBLIC_COPR_HOSTNAME"].split(":")[0],
            dependent.owner_name, dependent.name, dep_idx,
            copr.owner_name, copr_dir_name
        )
    else:
        name = "Copr repo for {0} owned by {1}".format(copr_dir_name,
                                                       copr.owner_name)
    return repo_id, name


def generate_repo_id_and_name_ext(dependent, url, dep_idx):
    """
    Return (repo_id, repo_name) pair according to the repo URL and what
    DEPENDENT repository we depend on.
    """
    repo_id = "coprdep:{0}".format(generate_repo_name(url))
    name = "Copr {0}/{1}/{2} external runtime dependency #{3} - {4}".format(
        app.config["PUBLIC_COPR_HOSTNAME"].split(":")[0],
        dependent.owner_name, dependent.name, dep_idx,
        generate_repo_name(url),
    )
    return repo_id, name
