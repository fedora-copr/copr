import datetime
import random
import string
import time

import flask

from coprs import app
from coprs import db
from coprs import exceptions
from coprs import forms

from coprs.views.misc import login_required

from coprs.views.api_ns import api_ns

from coprs.logic import builds_logic
from coprs.logic import coprs_logic


def generate_api_token(size=30):
    """ Generate a random string used as token to access the API
    remotely.

    :kwarg: size, the size of the token to generate, defaults to 30
        chars.
    :return: a string, the API token for the user.

    """
    return ''.join(random.choice(string.ascii_lowercase) for x in range(size))


@api_ns.route('/')
def api_home():
    """ Renders the home page of the api.
    This page provides information on how to call/use the API.
    """
    return flask.render_template('api.html')


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
    return flask.redirect(flask.url_for('api_ns.api_home'))


@api_ns.route('/copr/new/', methods=['POST'])
@login_required
def api_new_copr():
    """ Receive information from the user on how to create its new copr,
    check their validity and create the corresponding copr.

    :arg name: the name of the copr to add
    :arg chroots: a comma separated list of chroots to use
    :kwarg repos: a comma separated list of repository that this copr
        can use.
    :kwarg initial_pkgs: a comma separated list of initial packages to
        build in this new copr

    """
    form = forms.CoprFormFactory.create_form_cls()(csrf_enabled=False)
    if form.validate_on_submit():
        infos = []
        try:
            copr = coprs_logic.CoprsLogic.add(
                name=form.name.data.strip(),
                repos=" ".join(form.repos.data.split()),
                user=flask.g.user,
                selected_chroots=form.selected_chroots,
                description=form.description.data,
                instructions=form.instructions.data,
                check_for_duplicates=True,
                )
            infos.append('New copr was successfully created.')

            if form.initial_pkgs.data:
                builds_logic.BuildsLogic.add_build(
                    pkgs=" ".join(form.initial_pkgs.data.split()),
                    copr=copr,
                    owner=flask.g.user)
                infos.append('Initial packages were successfully submitted '
                        'for building.')

            output = '{"output" : "ok", "message" : "%s"}' % ("\n".join(infos))
            db.session.commit()
        except exceptions.DuplicateCoprNameException, err:
            output = '{"output": "notok", "error": "%s"}' % err
            db.session.rollback()

    else:
        errormsg = "\n".join(form.errors['name'])
        errormsg = errormsg.replace('"', "'")
        output = '{"output": "notok", "error": "%s"}' % errormsg

    return flask.Response(output, mimetype='application/json')


@api_ns.route('/owned/')
def api_list_copr():
    """ Return the list of coprs owned by the given user.

    :arg username: the username of the person one would like to the
        coprs of.

    """
    if 'username' in flask.request.args:
        username = flask.request.args['username']
        query = coprs_logic.CoprsLogic.get_multiple(flask.g.user,
            user_relation = 'owned', username = username)
        repos = query.all()
        output = '{"output": "ok",\n"repos":[\n'
        for cnt, repo in enumerate(repos):
            output += '{'\
            '"name" : "%s", '\
            '"repos" : "%s", '\
            '"description": "%s", '\
            '"instructions": "%s" '\
            '}\n' % (repo.name, repo.repos, repo.description,
                repo.instructions)
            if cnt < len(repos):
                output += ','
        output += "]}\n"
    else:
        output = '{"output": "notok", "error": "Invalid request"}'

    return flask.Response(output, mimetype='application/json')
