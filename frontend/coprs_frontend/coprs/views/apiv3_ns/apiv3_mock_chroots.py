import flask
from html2text import html2text
from coprs.views.apiv3_ns import apiv3_ns
from coprs.logic.coprs_logic import MockChrootsLogic


@apiv3_ns.route("/mock-chroots/list")
def list_chroots():
    chroots = MockChrootsLogic.active_names_with_comments()
    response = {}
    for chroot, comment in chroots:
        if comment:
            response[chroot] = html2text(comment).strip("\n")
        else:
            response[chroot] = ""

    return flask.jsonify(response)
