import time

from coprs import app
from coprs import helpers

@app.template_filter('date_from_secs')
def date_from_secs(secs):
    return time.strftime('%m-%d-%y %H:%M:%S', time.gmtime(secs)) if secs else None

@app.template_filter('perm_type_from_num')
def perm_type_from_num(num):
    return helpers.PermissionEnum.key(num)

# this should probably be stored in DB with the whole mock_chroot...
@app.template_filter('os_name_short')
def os_name_short(os_name):
    if os_name == 'fedora':
        return 'fc'
    elif os_name == 'epel':
        return 'el'
    return os_name
