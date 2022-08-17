"""
Shared logic for hitcounter scripts
"""

import os
import re
from datetime import datetime
from requests.utils import unquote
from copr_common.request import SafeRequest
from copr_backend.helpers import BackendConfigReader

base_regex = "/results/(?P<owner>[^/]*)/(?P<project>[^/]*)/(?P<chroot>[^/]*)/"
repomd_url_regex = re.compile(base_regex + "repodata/repomd.xml", re.IGNORECASE)
rpm_url_regex = re.compile(
    base_regex + r"(?P<build_dir>[^/]*)/(?P<rpm>[^/]*\.rpm)", re.IGNORECASE)

spider_regex = re.compile(
    '.*(ahrefs|bot/[0-9]|bingbot|borg|google|googlebot|yahoo|slurp|msnbot'
    '|openbot|archiver|netresearch|lycos|scooter|altavista|teoma|gigabot'
    '|blitzbot|oegp|charlotte|furlbot|http://client|polybot|htdig|ichiro'
    '|larbin|pompos|scrubby|searchsight|seekbot|semanticdiscovery|silk|snappy'
    '|spider|voila|vortex|voyager|zao|zeal|fast-webcrawler|converacrawler'
    '|msrbot|baiduspider|mogimogi|speedy|dataparksearch'
    '|findlinks|crawler|yandex|blexbot|semrushbot).*',
    re.IGNORECASE)


def url_to_key_strings(url):
    """
    Take a full URL and return a list of unique strings representing it,
    that copr-frontend will understand.
    """
    url_match = repomd_url_regex.match(url)
    if url_match:
        chroot_key = (
            'chroot_repo_metadata_dl_stat',
            url_match.group('owner'),
            url_match.group('project'),
            url_match.group('chroot')
        )
        chroot_key_str = '|'.join(chroot_key)
        return [chroot_key_str]

    url_match = rpm_url_regex.match(url)
    if url_match:
        chroot_key = (
            'chroot_rpms_dl_stat',
            url_match.group('owner'),
            url_match.group('project'),
            url_match.group('chroot')
        )
        chroot_key_str = '|'.join(chroot_key)
        project_key = (
            'project_rpms_dl_stat',
            url_match.group('owner'),
            url_match.group('project')
        )
        project_key_str = '|'.join(project_key)
        return [chroot_key_str, project_key_str]
    return []


def update_frontend(accesses, log, dry_run=False, try_indefinitely=False):
    """
    Increment frontend statistics based on these `accesses`
    """
    result = get_hit_data(accesses, log)
    if not result:
        log.debug("No recognizable hits among these accesses, skipping.")
        return

    log.debug(
        "Sending: %i results from %i to %i",
        len(result["hits"]),
        result["ts_from"],
        result["ts_to"]
    )
    if len(result["hits"]) < 100:
        log.debug("Hits: %s", result["hits"])
    else:
        log.debug("Not logging the whole dict: %s hits", len(result["hits"]))

    opts = BackendConfigReader().read()
    url = os.path.join(
        opts.frontend_base_url,
        "stats_rcv",
        "from_backend",
    )
    if not dry_run:
        request = SafeRequest(
            auth=opts.frontend_auth,
            log=log,
            try_indefinitely=try_indefinitely,
        )
        request.post(url, result)


def get_hit_data(accesses, log):
    """
    Prepare body for the frontend request in the same format that
    copr_log_hitcounter.py does.
    """
    hits = {}
    timestamps = []
    for access in accesses:
        url = access["cs-uri-stem"]

        if access["sc-status"] == "404":
            log.debug("Skipping: %s (404 Not Found)", url)
            continue

        if access["cs(User-Agent)"].startswith("Mock"):
            log.debug("Skipping: %s (user-agent: Mock)", url)
            continue

        bot = spider_regex.match(access["cs(User-Agent)"])
        if bot:
            log.debug("Skipping: %s (user-agent '%s' is a known bot)",
                      url, bot.group(1))
            continue

        # Convert encoded characters from their %40 values back to @.
        url = unquote(url)

        # I don't know how or why but occasionally there is an URL that is
        # encoded twice (%2540oamg -> %40oamg - > @oamg), and yet its status
        # code is 200. AFAIK these appear only for EPEL-7 chroots and their
        # User-Agent is something like urlgrabber/3.10%20yum/3.4.3
        # I wasn't able to reproduce such accesses, and we decided to not count
        # them
        if url != unquote(url):
            log.warning("Skipping: %s (double encoded URL, user-agent: '%s', "
                        "status: %s)", access["cs-uri-stem"],
                        access["cs(User-Agent)"], access["sc-status"])
            continue

        # We don't want to count every accessed URL, only those pointing to
        # RPM files and repo file
        key_strings = url_to_key_strings(url)
        if not key_strings:
            log.debug("Skipping: %s", url)
            continue

        if any(x for x in key_strings
               if x.startswith("chroot_rpms_dl_stat|")
               and x.endswith("|srpm-builds")):
            log.debug("Skipping %s (SRPM build)", url)
            continue

        log.debug("Processing: %s", url)

        # When counting RPM access, we want to iterate both project hits and
        # chroot hits. That way we can get multiple `key_strings` for one URL
        for key_str in key_strings:
            hits.setdefault(key_str, 0)
            hits[key_str] += 1

        # Remember this access timestamp
        datetime_format = "%Y-%m-%d %H:%M:%S"
        datetime_string = "{0} {1}".format(access["date"], access["time"])
        datetime_object = datetime.strptime(datetime_string, datetime_format)
        timestamps.append(int(datetime_object.timestamp()))

    return {
        "ts_from": min(timestamps),
        "ts_to": max(timestamps),
        "hits": hits,
    } if hits else {}
