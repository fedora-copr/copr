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
