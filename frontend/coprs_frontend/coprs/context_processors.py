import os
from . import app
import flask

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
        desc = " ({})".format(info['user_desc']) if 'user_desc' in info else ''
        menu.append({
            'link': info['user_link'].format(username=user.name),
            'desc': "{0}{1}".format(user.name, desc),
        })

        menu.append({
            'link': flask.url_for('misc.logout'),
            'desc': 'log out',
        })

    else:
        if config['FAS_LOGIN']:
            menu.append({
                'link': flask.url_for('misc.login'),
                'desc': 'log in',
            })

        if config['KRB5_LOGIN']:
            base = config['KRB5_LOGIN_BASEURI']
            for _, login in config['KRB5_LOGIN'].iteritems():
                menu.append({
                    'link': base + login['URI'],
                    'desc': login['log_text'],
                })

        if config['FAS_LOGIN']:
            menu.append({
                'link': 'https://admin.fedoraproject.org/accounts/user/new',
                'desc': 'sign up',
            })

    return dict(login_menu=menu)
