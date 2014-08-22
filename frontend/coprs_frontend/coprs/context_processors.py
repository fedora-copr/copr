import os
from . import app

BANNER_LOCATION = "/var/lib/copr/banner-include.html"


@app.context_processor
def include_banner():
    if os.path.exists(BANNER_LOCATION):
        return {"copr_banner": open(BANNER_LOCATION).read()}
