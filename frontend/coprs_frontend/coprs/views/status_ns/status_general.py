import flask, os

from urlparse import urlparse
from coprs.views.status_ns import status_ns
from coprs.logic import builds_logic

@status_ns.route("/")
def status_home():
    builds_number = 0
    builds_list = []

    for build in builds_logic.BuildsLogic.get_waiting():
        for chroot in build.chroots:
            pkgs = []
            for url in build.pkgs.split(' '):
                pkgs.append(os.path.basename(urlparse(url)[2]))
            build_dict = {
                'chroot' : chroot.name,
                'time' : build.submitted_on,
                'owner' : build.user.name,
                'pkgs' : pkgs,
                'copr' : build.copr.name}
            builds_list.append(build_dict)
    builds_number = len(builds_list)
    return flask.render_template("status.html", 
                                builds=builds_list,
                                number=builds_number)
