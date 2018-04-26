import flask
from werkzeug.datastructures import MultiDict


def get_form_compatible_data():
    input = flask.request.json or flask.request.form
    output = {}

    # Transform lists to strings separated with spaces
    for k, v in input.items():
        if type(v) == list:
            v = " ".join(map(str, v))
        output[k] = v

    # Our WTForms expect chroots to be this way
    for chroot in input.get("chroots") or []:
        output[chroot] = True

    output.update(flask.request.files or {})
    return MultiDict(output)
