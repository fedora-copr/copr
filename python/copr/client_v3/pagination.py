class Pagination(object):
    def __init__(self, limit=None, offset=None, order=None, order_type=None):
        self.limit = limit
        self.offset = offset
        self.order = order
        self.order_type = order_type

    def to_dict(self):
        return {k: v for k, v in vars(self).items() if v is not None}


def next_page(objects):
    objects.__response__.request.params["offset"] = objects.meta.offset + objects.meta.limit
    response = objects.__response__.request.send()
    return response.munchify()


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
