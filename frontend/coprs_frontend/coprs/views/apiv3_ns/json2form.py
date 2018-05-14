import flask
from werkzeug.datastructures import MultiDict


def get_form_compatible_data():
    input = flask.request.json or flask.request.form
    output = {}

    for k, v in input.items():
        # Transform lists to strings separated with spaces
        if type(v) == list:
            v = " ".join(map(str, v))

        # Field with None value is like if it wasn't send with forms
        if v is None:
            continue

        output[k] = v

    # Our WTForms expect chroots to be this way
    for chroot in input.get("chroots") or []:
        output[chroot] = True

    output.update(flask.request.files or {})
    return MultiDict(output)
