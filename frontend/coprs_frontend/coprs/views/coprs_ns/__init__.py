# coding: utf-8

import flask
from coprs.logic.outdated_chroots_logic import OutdatedChrootsLogic


def flash_outdated_chroots_warning():
    if not flask.g.user:
        return

    if not OutdatedChrootsLogic.has_not_reviewed(flask.g.user):
        return

    url = flask.url_for("user_ns.repositories", _external=True)
    flask.flash("Some of the chroots you maintain are <b>newly marked EOL</b>, "
                " and will be removed in the future. Please review "
                "<a href='{0}'>{0}</a> to hide this warning."
                .format(url), "warning")


coprs_ns = flask.Blueprint("coprs_ns", __name__, url_prefix="/coprs")
coprs_ns.before_request(flash_outdated_chroots_warning)
