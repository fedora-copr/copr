import time

import flask

from coprs import db
from coprs import exceptions

from coprs.views.misc import login_required

from coprs.views.api_ns import api_ns

from coprs.logic import builds_logic
from coprs.logic import coprs_logic


@api_ns.route('/')
def api_home():
    """ Renders the home page of the api.
    This page provides information on how to call/use the API.
    """
    return flask.render_template('coprs/api.html')


@api_ns.route('/new/', methods = ["GET", "POST"])
@login_required
def api_new_token():
    """ Method use to generate a new API token for the current user.
    """
    user = flask.g.user
    user.api_token = generate_api_token(app.config['API_TOKEN_LENGTH'])
    user.api_token_expiration = datetime.date.today() \
        + datetime.timedelta(days=30)
    db.session.add(user)
    db.session.commit()
    flask.g.user = user
    return flask.redirect(flask.url_for('misc.api'))


@api_ns.route('/add/<name>/<chroots>/',
    defaults={'repos':"", 'initial_pkgs':""})
@api_ns.route('/add/<name>/<chroots>/<repos>/',
    defaults={'initial_pkgs':None})
@api_ns.route('/add/<name>/<chroots>/<repos>/<initial_pkgs>/')
@login_required
def api_add_copr(name, chroots, repos="", initial_pkgs=""):
    """ Receive information from the user on how to create its new copr,
    check their validity and create the corresponding copr.

    :arg name: the name of the copr to add
    :arg chroots: a comma separated list of chroots to use
    :kwarg repos: a comma separated list of repository that this copr
        can use.
    :kwarg initial_pkgs: a comma separated list of initial packages to
        build in this new copr

    """
    infos = []
    copr = coprs_logic.CoprsLogic.add_coprs(
        name=name.strip(),
        repos=" ".join([repo.strip() for repo in repos.split(',')]),
        owner=flask.g.user,
        selected_chroots=[chroot.strip()
            for chroot in chroots.split(',')]
        )
    infos.append('New copr was successfully created.')

    if initial_pkgs:
        builds_logic.BuildsLogic.add_build(
            pkgs=" ".join([pkg.strip() for pkg in initial_pkgs.split(',')]),
            copr=copr,
            owner=flask.g.user)
        infos.append('Initial packages were successfully submitted '
                'for building.')
    return '{"output" : "%s"}' % ("\n".join(infos))


@api_ns.route('/list/<username>/', methods=['GET'])
def api_list_copr(username):
    """ Return the list of coprs owned by the given user.

    :arg username: the username of the person one would like to the
        coprs of.
    """
    query = coprs_logic.CoprsLogic.get_multiple(flask.g.user,
        user_relation = 'owned', username = username)
    output = '{"repos":[\n'
    repos = query.all()
    cnt = 0
    for repo in repos:
        output += '{"name" : "%s", "repos" : "%s"}\n' % (
            repo.name, repo.repos)
        cnt = cnt + 1
        if cnt < len(repos):
            output += ','
    output += "]}\n"
    return output
