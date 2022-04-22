"""
The 'copr-frontend chroots-template' command implementation.
"""

import importlib
import click
from templated_dictionary import TemplatedDictionary

from coprs import db_session_scope
from coprs.logic import coprs_logic


def apply_rule(chroot, rule):
    """
    The rule is to be applied to this chroot.
    """
    already_modified = getattr(chroot, "_already_modified", False)
    setattr(chroot, "_already_modified", True)
    if "comment" in rule:
        chroot.comment = rule["comment"]
        return
    if "comment_append" in rule:
        if not already_modified:
            chroot.comment = ""
        chroot.comment += rule["comment_append"]
        return
    raise click.ClickException("Unknown rule type.")


def matches(string, rule):
    """
    Helper to accept both string and list() values in match argument.
    """
    rule = rule["match"]
    if isinstance(rule, list):
        return string in rule
    return string == rule


def apply_rules(chroot, config):
    """
    Iterate over the rules from the config file, and attempt to apply them.
    """
    for rule in config["rules"]:
        match_type = rule.get("match_type", "name")
        if match_type == "name":
            if matches(chroot.name, rule) or matches(chroot.name_release, rule):
                apply_rule(chroot, rule)
            continue
        if match_type == "arch" and matches(chroot.arch, rule):
            apply_rule(chroot, rule)
            continue


@click.command()
@click.option(
    "-t", "--template",
    help="Batch-configure the enabled chroots from a template file.",
    type=click.Path(exists=True, readable=True),
    default="/etc/copr/chroots.conf",
)
def chroots_template(template):
    """
    Load the MockChroot configuration from /etc/copr/chroots.conf.  For more
    info take a look at
    https://docs.pagure.org/copr.copr/how_to_manage_chroots.html#managing-chroot-comments
    """

    # Meh, this used to be just 'imp.load_source()' (but 'imp' is deprecated).
    loader = importlib.machinery.SourceFileLoader("config", template)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    obj = getattr(module, "config")
    config = TemplatedDictionary(obj)
    config["__jinja_expand"] = True
    with db_session_scope():
        for ch in coprs_logic.MockChrootsLogic.get_multiple(active_only=True):
            apply_rules(ch, config)
