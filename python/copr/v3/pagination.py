from __future__ import absolute_import

import requests
from .requests import munchify

try:
    import urlparse
    from urllib import urlencode
except ImportError:
    import urllib.parse as urlparse
    from urllib.parse import urlencode


def next_page(objects):
    request = objects.__response__.request

    # Add offset to the previous request URL
    url_parts = list(urlparse.urlparse(request.url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update({"offset": objects.meta.offset + objects.meta.limit})
    url_parts[4] = urlencode(query)
    request.url = urlparse.urlunparse(url_parts)

    session = requests.Session()
    response = session.send(request)
    return munchify(response)


# @TODO remove all_pages function if unlimited generator is preferred over it
def all_pages(objects):
    all_objects = []
    while objects:
        all_objects.extend(objects)
        objects = next_page(objects)
    return all_objects


def unlimited(objects):
    if not objects:
        objects = next_page(objects)

    if not objects:
        return

    yield objects.pop()
    for item in unlimited(objects):
        yield item
