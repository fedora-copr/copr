# coding: utf-8

from coprs.views.rss_ns import rss_ns
from coprs import app
from coprs.helpers import fix_protocol_for_frontend
from coprs.logic.coprs_logic import CoprsLogic
from flask import render_template, Response
from coprs import models


@rss_ns.route("/all", defaults={"limit": 200})
def rss_all(limit=200):
    """
    Simple route that returns all projects
    name, description, link to selected project
    as rss feed

    """

    coprs = CoprsLogic.get_all().order_by(models.Copr.id.desc()).limit(limit)

    answer = render_template("rss/rss.xml", coprs=coprs)
    return Response(answer, mimetype="text/xml")


@rss_ns.route("/", defaults={"limit": 200})
@rss_ns.route("/<int:limit>/")
def rss(limit=200):
    """
    Simple route that returns all projects
    name, description, link to selected project
    as rss feed except projects hidden from homepage
    """

    coprs = CoprsLogic.get_multiple(include_unlisted_on_hp=False).order_by(models.Copr.id.desc()).limit(limit)
    answer = render_template("rss/rss.xml", coprs=coprs)
    return Response(answer, mimetype="text/xml")
