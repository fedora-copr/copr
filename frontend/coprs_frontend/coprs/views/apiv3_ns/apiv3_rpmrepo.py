# pylint: disable=missing-class-docstring

"""
/api_3/rpmrepo routes
"""

from flask_restx import Resource, Namespace

from coprs import app
from coprs.logic.coprs_logic import (
    CoprsLogic,
    CoprDirsLogic,
)

from coprs.logic.complex_logic import (
    ComplexLogic
)

from coprs.views.apiv3_ns import api

from coprs import cache
from coprs.logic.complex_logic import ReposLogic
from coprs.logic.stat_logic import CounterStatLogic
from coprs.helpers import (
    get_stat_name,
    CounterStatType,
)
from coprs.repos import (
    generate_repo_id_and_name,
    generate_repo_id_and_name_ext,
)


apiv3_rpmrepo_ns = Namespace("rpmrepo", description="RPM Repo")
api.add_namespace(apiv3_rpmrepo_ns)


@cache.memoize(timeout=2*60)
def get_project_rpmrepo_metadata(copr):
    """
    Get the copr-related JSON data with available
    chroots/directories/external/etc.  This is parsed by DNF5 copr plugin.
    We cache (memoize) this for several minutes because generating the data can
    be relatively DB demanding (for rather larger dependency trees).
    """

    # pylint: disable=too-many-locals

    repo_dl_stat = CounterStatLogic.get_copr_repo_dl_stat(copr)
    repos_info = ReposLogic.repos_for_copr(copr, repo_dl_stat)

    data = {
        "results_url": "/".join([app.config["BACKEND_BASE_URL"], "results"]),
    }

    repos = data['repos'] = {}
    chroots = {}  # TODO: data["chroots"] = {}
    directories = data["directories"] = {}

    gen_opts = {}
    if copr.module_hotfixes:
        gen_opts["module_hotfixes"] = "1"
    if copr.repo_priority:
        gen_opts["priority"] = copr.repo_priority

    for name_release, info in repos_info.items():
        repo = repos[name_release] = {
            "arch": {},
        }
        for arch in info["arch_list"]:
            archspec = repo["arch"][arch] = {"opts": {**gen_opts}}
            if arch in info["expirations"]:
                archspec["delete_after_days"] = info["expirations"][arch]

        for arch, multilib in info.get("arch_repos", {}).items():
            repo["arch"][arch]["multilib"] = {
                multilib: {
                    "opts": {
                        "cost": "1100",
                        **gen_opts,
                    },
                },
            }

    for copr_chroot in copr.enable_permissible_copr_chroots:
        cc_data = chroots[copr_chroot.name] = {}
        delete = copr_chroot.delete_after_days
        if delete is not None:
            cc_data["delete_after_days"] = delete

    copr_dirs = CoprDirsLogic.get_all_with_latest_submitted_build(copr.id)
    for dir_info in copr_dirs:
        dir_data = directories[dir_info["copr_dir"].name] = {}
        if dir_info["removal_candidate"]:
            dir_data["delete_after_days"] = dir_info["remaining_days"]

    delete = copr.delete_after_days
    if delete is not None:
        data["delete_after_days"] = delete

    internal_deps, external_deps, _ = \
            ComplexLogic.get_transitive_runtime_dependencies(copr)

    dependencies = data["dependencies"] = []

    dep_idx = 1
    for dep in internal_deps:
        repo_id, repo_name = generate_repo_id_and_name(
            dep, dep.name, dep_idx=dep_idx,
            dependent=copr)
        dependencies.append({
            "opts": {
                "id": repo_id,
                "name": repo_name,
            },
            "type": "copr",
            "data": {
                "owner": dep.owner_name,
                "projectname": dep.name,
            },
        })
        dep_idx += 1

    for dep in external_deps:
        repo_id, repo_name = generate_repo_id_and_name_ext(
            copr, dep, dep_idx)
        dependencies.append({
            "opts": {
                "id": repo_id,
                "name": repo_name,
            },
            "type": "external_baseurl",
            "data": {
                "pattern": dep,
            }
        })

    return data


@apiv3_rpmrepo_ns.route("/<ownername>/<dirname>/<name_release>")
class RpmRepo(Resource):
    def get(self, ownername, dirname, name_release):
        """
        Wrap get_project_rpmrepo_metadata() JSON provider, and gather some
        statistics.
        """
        copr = CoprsLogic.get_by_ownername_and_dirname(ownername, dirname)
        name = get_stat_name(
            CounterStatType.REPO_DL,
            copr_dir=copr.main_dir,
            name_release=name_release,
        )
        CounterStatLogic.incr(name=name, counter_type=CounterStatType.REPO_DL)
        return get_project_rpmrepo_metadata(copr)
