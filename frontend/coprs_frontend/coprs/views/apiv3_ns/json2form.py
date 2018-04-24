import flask
from coprs import forms


def get_copr_form_factory():
    form = forms.CoprFormFactory.create_form_cls()(csrf_enabled=False)
    for chroot in form.chroots_list:
        if chroot in flask.request.json["chroots"]:
            getattr(form, chroot).data = True
    return form


def get_build_form_factory(factory, copr_chroots):
    form = factory(copr_chroots)(csrf_enabled=False)
    data = flask.request.json or flask.request.form
    for chroot in data.get("chroots", []):
        getattr(form, chroot).data = True
    return form
