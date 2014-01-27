import datetime
import pytz
import time
import markdown

from flask import Markup

from coprs import app
from coprs import helpers


@app.template_filter("date_from_secs")
def date_from_secs(secs):
    if secs:
        return time.strftime("%Y-%m-%d %H:%M:%S %Z", time.gmtime(secs))

    return None


@app.template_filter("perm_type_from_num")
def perm_type_from_num(num):
    return helpers.PermissionEnum(num)


@app.template_filter("os_name_short")
def os_name_short(os_name, os_version):
    # TODO: make it models.MockChroot method or not?
    if os_version:
        if os_version == "rawhide":
            return os_version
        if os_name == "fedora":
            return "fc.{0}".format(os_version)
        elif os_name == "epel":
            return "el{0}".format(os_version)
    return os_name


@app.template_filter('localized_time')
def localized_time(time_in, timezone):
    """ return time shifted into timezone (and printed in ISO format)

    Input is in EPOCH (seconds since epoch).
    """
    if not time_in:
        return "Not yet"
    format_tz = "%Y-%m-%d %H:%M:%S %Z"
    utc_tz = pytz.timezone('UTC')
    if timezone:
        user_tz = pytz.timezone(timezone)
    else:
        user_tz = utc_tz
    dt_aware = datetime.datetime.fromtimestamp(time_in).replace(tzinfo=utc_tz)
    dt_my_tz = dt_aware.astimezone(user_tz)
    return dt_my_tz.strftime(format_tz)


@app.template_filter("markdown")
def markdown_filter(data):
    if not data:
        return ''

    md = markdown.Markdown(
        safe_mode="replace",
        html_replacement_text="--RAW HTML NOT ALLOWED--")

    return Markup(md.convert(data))
