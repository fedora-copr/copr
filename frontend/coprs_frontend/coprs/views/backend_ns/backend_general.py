import flask
import sys
import time

from coprs import db
from coprs.logic import actions_logic
from coprs.logic import builds_logic

from coprs.views import misc
from coprs.views.backend_ns import backend_ns
from whoosh.index import LockError


@backend_ns.route("/waiting/")
@misc.backend_authenticated
def waiting():
    """
    Return list of waiting actions and builds.
    """

    # models.Actions
    actions_list = [action.to_dict(
        options={"__columns_except__": ["result", "message", "ended_on"]})
        for action in actions_logic.ActionsLogic.get_waiting()
    ]

    # models.Builds
    builds_list = []

    for build in builds_logic.BuildsLogic.get_waiting():
        build_dict = build.to_dict(
            options={"copr": {"owner": {},
                              "__columns_only__": ["id", "name"],
                              "__included_ids__": False
                              },
                     "__included_ids__": False})

        # return separate build for each chroot this build
        # is assigned with
        for chroot in build.chroots:
            build_dict_copy = build_dict.copy()
            build_dict_copy["chroot"] = chroot.name
            build_dict_copy[
                "buildroot_pkgs"] = build.copr.buildroot_pkgs(chroot)
            builds_list.append(build_dict_copy)

    return flask.jsonify({"actions": actions_list, "builds": builds_list})


@backend_ns.route("/update/", methods=["POST", "PUT"])
@misc.backend_authenticated
def update():
    result = {}

    for typ, logic_cls in [("actions", actions_logic.ActionsLogic),
                           ("builds", builds_logic.BuildsLogic)]:

        if typ not in flask.request.json:
            continue

        to_update = {}
        for obj in flask.request.json[typ]:
            to_update[obj["id"]] = obj

        existing = {}
        for obj in logic_cls.get_by_ids(to_update.keys()).all():
            existing[obj.id] = obj

        non_existing_ids = list(set(to_update.keys()) - set(existing.keys()))

        for i, obj in existing.items():
            logic_cls.update_state_from_dict(obj, to_update[i])

        i = 5
        exc_info = None
        while i > 0:
            try:
                db.session.commit()
                i = -100
            except LockError:
                i -= 1
                exc_info = sys.exc_info()[2]
                time.sleep(5)
        if i != -100:
            raise LockError, None, exc_info

        result.update({"updated_{0}_ids".format(typ): list(existing.keys()),
                       "non_existing_{0}_ids".format(typ): non_existing_ids})

    return flask.jsonify(result)
