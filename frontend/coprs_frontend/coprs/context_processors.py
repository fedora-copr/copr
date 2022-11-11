import os
import flask

from coprs import app
from coprs.helpers import current_url


BANNER_LOCATION = "/var/lib/copr/banner-include.html"


@app.context_processor
def include_banner():
    if os.path.exists(BANNER_LOCATION):
        return {"copr_banner": open(BANNER_LOCATION).read()}
    else:
        return {}


@app.context_processor
def inject_fedmenu():
    """ Inject fedmenu url if available. """
    if 'FEDMENU_URL' in app.config:
        return dict(
            fedmenu_url=app.config['FEDMENU_URL'],
            fedmenu_data_url=app.config['FEDMENU_DATA_URL'],
        )
    return dict()

@app.context_processor
def login_menu():
    """
    Based on authentication configuration, construct the login menu links
    to be placed at the top of each webui page.
    """

    menu = []
    config = app.config
    info = config['LOGIN_INFO']

    if flask.g.user:
        # User authenticated.
        user = flask.g.user
        menu.append({
            'link': flask.url_for('coprs_ns.coprs_by_user', username=user.name),
            'desc': user.name,
        })

        menu.append({
            'link': flask.url_for('misc.logout'),
            'desc': 'log out',
        })

    else:
        if config['FAS_LOGIN']:
            menu.append({
                'link': flask.url_for('misc.oid_login'),
                'desc': 'log in',
            })

        if config['KRB5_LOGIN']:
            menu.append({
                'link': flask.url_for("apiv3_ns.gssapi_login"),
                'desc': config['KRB5_LOGIN']['log_text'],
            })

        if config['FAS_LOGIN']:
            menu.append({
                'link': config["FAS_SIGNUP_URL"],
                'desc': 'sign up',
            })

    return dict(login_menu=menu)

@app.context_processor
def counter_processor():
    def counter(name):
        if not 'counters' in flask.g:
            flask.g.counters = {}
        if not name in flask.g.counters:
            flask.g.counters[name] = 0

        flask.g.counters[name] += 1
        return str(flask.g.counters[name])

    return dict(counter=counter)


@app.context_processor
def current_url_processor():
    """ Provide 'current_url()' method in templates """
    return dict(current_url=current_url)
