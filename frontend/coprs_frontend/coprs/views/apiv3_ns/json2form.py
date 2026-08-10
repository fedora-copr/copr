import flask
from werkzeug.datastructures import MultiDict


def get_form_compatible_data(preserve=None):
    """
    Load flask request data from API/CLI calls (typically Python dict uploaded
    as JSON data or set of uploaded files) and transform it to a dict in
    WTForms-compatible format; so we eventually can leverage the WTForms
    validation logic not only for web-UI but also for API.

    Objects of type list() are joined using a separator into one string.
    The separator string is set to one space.
    """
    input = without_empty_fields(get_input_dict())
    output = dict(input).copy()

    for k, v in input.items():
        # Preserve the original value and return it unchanged
        if k in (preserve or []):
            continue

        # Transform lists to strings separated with spaces
        if isinstance(v, list):
            v = " ".join(map(str, v))

        output[k] = v

    output.update(flask.request.files or {})
    return MultiDict(output)


def get_input_dict():
    json_data = flask.request.get_json(silent=True)
    if json_data is not None:
        return json_data

    # plain dict(MultiDict) would silently keep only the first value for
    # a repeated form key (e.g. multiple "chroots" fields sent over
    # multipart/form-data) -- keep such keys as a list instead
    form = flask.request.form
    return {k: form.getlist(k) if len(form.getlist(k)) > 1 else form[k]
           for k in form}


def get_input():
    return MultiDict(get_input_dict())


def without_empty_fields(input):
    output = input.copy()
    for k, v in input.items():
        # Field with None value is like if it wasn't send with forms
        if v is None:
            del output[k]
    return output
