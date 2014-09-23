import datetime
import pytz
import time
import markdown

import os

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


@app.template_filter("state_from_num")
def state_from_num(num):
    if num is None:
        return "unknown"
    return helpers.StatusEnum(num)


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
    format_tz = "%y-%m-%d %H:%M %Z"
    utc_tz = pytz.timezone('UTC')
    if timezone:
        user_tz = pytz.timezone(timezone)
    else:
        user_tz = utc_tz
    dt_aware = datetime.datetime.fromtimestamp(time_in).replace(tzinfo=utc_tz)
    dt_my_tz = dt_aware.astimezone(user_tz)
    return dt_my_tz.strftime(format_tz)


@app.template_filter('time_ago')
def time_ago(time_in, until=None):
    """ returns string saying how long ago the time on input was

    Input is in EPOCH (seconds since epoch).
    """
    if time_in is None:
        return " - "
    if until is not None:
        now = datetime.datetime.fromtimestamp(until)
    else:
        now = datetime.datetime.now()
    diff = now - datetime.datetime.fromtimestamp(time_in)
    secdiff = int(diff.total_seconds())
    if secdiff < 120:
        # less than 2 minutes
        return "1 minute"
    elif secdiff < 7200:
        # less than 2 hours
        return str(secdiff/60) + " minutes"
    elif secdiff < 172800:
        # less than 2 days
        return str(secdiff/3600) + " hours"
    elif secdiff < 5184000:
        # less than 2 months
        return str(secdiff/86400) + " days"
    elif secdiff < 63072000:
        # less than 2 years
        return str(secdiff/2592000) + " months"
    else:
        # more than 2 years
        return str(secdiff/31536000) + " days"


@app.template_filter("markdown")
def markdown_filter(data):
    if not data:
        return ''

    md = markdown.Markdown(
        safe_mode="replace",
        html_replacement_text="--RAW HTML NOT ALLOWED--")

    return Markup(md.convert(data))


@app.template_filter("pkg_name")
def parse_package_name(pkg):
    if pkg is not None:
        return helpers.parse_package_name(os.path.basename(pkg))
    return pkg


@app.template_filter("basename")
def parse_package_name(pkg):
    if pkg is not None:
        return os.path.basename(pkg)
    return pkg


@app.template_filter("build_state_description")
def build_state_decoration(state):
    description = ""
    if state == "skipped":
        description = "This package has already been built previously"

    return description


@app.template_filter("fix_url_https_backend")
def fix_url_https_backend(url):
    return helpers.fix_protocol_for_backend(url)


@app.template_filter("fix_url_https_frontend")
def fix_url_https_fronend(url):
    return helpers.fix_protocol_for_frontend(url)
