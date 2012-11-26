import math

import flask

from coprs import constants

def chroots():
    return ['{0}-{1}'.format(rel, arch) for rel, arches in constants.CHROOTS.items()
                                            for arch in arches]

class PermissionEnum(object):
    vals = {'No Action': 0, 'Request': 1, 'Approved': 2}

    @classmethod
    def num(cls, key):
        return cls.vals.get(key, None)

    @classmethod
    def key(cls, num):
        for k, n in cls.vals.items():
            if n == num:
                return k
        return None

    @classmethod
    def choices_list(cls, without = 2):
        return [(n, k) for k, n in cls.vals.items() if n != without]

class Paginator(object):
    def __init__(self, query, total_count, page = 1, per_page_override = None, urls_count_override = None):
        self.query = query
        self.total_count = total_count
        self.page = page
        self.per_page = per_page_override or constants.ITEMS_PER_PAGE
        self.urls_count = urls_count_override or constants.PAGES_URLS_COUNT
        self._sliced_query = None

    def page_slice(self, page):
        return (constants.ITEMS_PER_PAGE * (page - 1), constants.ITEMS_PER_PAGE * page)

    @property
    def sliced_query(self):
        if not self._sliced_query:
            self._sliced_query = self.query[slice(*self.page_slice(self.page))]
        return self._sliced_query

    @property
    def pages(self):
        return int(math.ceil(self.total_count / float(self.per_page)))

    def border_url(self, request, start):
        if start:
            if self.page - 1 > self.urls_count / 2:
                return (self.url_for_other_page(request, 1), 1)
        else:
            if self.page < self.pages - self.urls_count / 2:
                return (self.url_for_other_page(request, self.pages), self.pages)

        return None

    def get_urls(self, request):
        left_border = self.page - self.urls_count / 2
        left_border = 1 if left_border < 1 else left_border
        right_border = self.page + self.urls_count / 2
        right_border = self.pages if right_border > self.pages else right_border

        return [(self.url_for_other_page(request, i), i) for i in range(left_border, right_border + 1)]

    def url_for_other_page(self, request, page):
        args = request.view_args.copy()
        args['page'] = page
        return flask.url_for(request.endpoint, **args)
