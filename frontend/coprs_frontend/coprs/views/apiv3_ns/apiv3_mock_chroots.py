# pylint: disable=missing-class-docstring


from http import HTTPStatus

from flask_restx import Namespace, Resource
from html2text import html2text

from coprs.views.apiv3_ns import api
from coprs.logic.coprs_logic import MockChrootsLogic


apiv3_mock_chroots_ns = Namespace("mock-chroots", description="Mock chroots")
api.add_namespace(apiv3_mock_chroots_ns)


@apiv3_mock_chroots_ns.route("/list")
class MockChroot(Resource):
    # FIXME: we can't have proper model here, - one of REST API rules that flask-restx follows
    # is to have keys in JSON constant, we don't do that here.
    @apiv3_mock_chroots_ns.response(HTTPStatus.OK.value, "OK, Mock chroot data follows...")
    def get(self):
        """
        Get list of mock chroots
        Get list of all currently active mock chroots with additional comment in format
        `mock_chroot_name: additional_comment`.
        """
        chroots = MockChrootsLogic.active_names_with_comments()
        response = {}
        for chroot, comment in chroots:
            if comment:
                response[chroot] = html2text(comment).strip("\n")
            else:
                response[chroot] = ""

        return response
