import time

from coprs import app

@app.template_filter('date_from_secs')
def date_from_secs(secs):
    return time.strftime('%m-%d-%y %H:%M:%S', time.gmtime(secs)) if secs else None
