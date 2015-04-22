import os
from . import app

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
