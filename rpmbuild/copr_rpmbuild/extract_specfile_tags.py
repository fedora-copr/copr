"""
Extract macro-expanded tag value (e.g., BuildArch) from given specfile.
"""

import logging
import os
import tempfile

from copr_common.request import SafeRequest

from norpm.macrofile import system_macro_registry
from norpm.specfile import specfile_expand, ParserHooks
from norpm.overrides import override_macro_registry
from norpm.exceptions import NorpmError

DEFAULT_TAG_MAP = {
    # EPEL is RHEL+EPEL in Copr
    "epel-7": "rhel+epel-7",
    "epel-8": "rhel+epel-8",
    "epel-9": "rhel+epel-9",
    # Since EPEL 10 we switched to centos-stream.
    "epel-10": "centos-stream+epel-10",
    # what do we do about custom-* chroots?
    "custom-0": "fedora-rawhide",
    "custom-1": "fedora-rawhide",
}

class _TagHooks(ParserHooks):
    """ Gather access to spec tags """
    def __init__(self, expanded_tags):
        self.expanded_tags = set(expanded_tags)
        self.tags = {}

    def tag_found(self, name, value, _tag_raw):
        """
        Parser hook that gathers the tags' values, if defined.
        """
        if name not in self.expanded_tags:
            return
        if name not in self.tags:
            self.tags[name] = []
        # tags may be specified multiple times within a single spec file
        self.tags[name] += [value]


def collapse_tag_values_cb(array_of_tag_values):
    """
    Process tags that represent sets of strings (e.g., ExcludeArch).

    If a tag is specified multiple times within the specfile, this function
    performs a union of all encountered values.  The resulting set contains
    every unique string defined across all instances of the tag.

    Returns:
        set: A set of all unique strings extracted from the tag definitions.
    """
    concat = " ".join(array_of_tag_values)
    return sorted(list(set(concat.split())))


def extract_tags_from_specfile(specfile, extract_tags, override_database=None,
                               target=None, tag_cb=None, log=logging):
    """
    Parse the given SPECFILE against system macros and optionally TARGET macros.

    If TARGET is specified, OVERRIDE_DATABASE (a file path) must also be
    provided.  If TARGET is omitted, the local system macros are used by
    default.

    Args:
        specfile (str): Path to the specfile to be parsed.
        target (str, optional): Target distribution (e.g., "rhel-7").
        override_database (str, optional): Database file path required if target
            is set.
        tag_cb (callable, optional): A callback function used to transform the
            list of values for each tag.  If provided, each item in the return
            dictionary is passed through this function. A common choice is
            `collapse_tag_values_cb`, which collapses the list into a set of
            unique strings.

    Returns:
        dict: A mapping of lowercase tagnames to their processed values.
            Default format: {'excludearch': ['ppc64 ppc64le', 's390x i386']}
            With tag_cb: The value type is determined by the callback's return.
            With tag_cb=collapse_tag_values_cb:
                {'excludearch': {'ppc64', 'ppc64le', 's390x', 'i386'}}
    Note:
        Since RPM tags are case-insensitive, all tagnames are normalized
        using .lower().
    """
    registry = system_macro_registry()
    if override_database:
        registry = override_macro_registry(registry, override_database, target)

    # %dist definition contains %lua mess, it's safer to clear it (since we
    # don't necessarily need it)
    registry["dist"] = ""

    # norpm maintains a few tricks to ease the spec file parsing
    registry.known_norpm_hacks()

    tags = _TagHooks(extract_tags)
    try:
        with open(specfile, "r", encoding="utf8") as fd:
            specfile_expand(fd.read(), registry, tags)
    except NorpmError as err:
        log.warning(f"Can not extract tags from {specfile} for {target}, "
                    f"spec file parser error: {err}")

    if not tag_cb:
        return tags.tags

    processed = {}
    for tag, values in tags.tags.items():
        processed[tag] = tag_cb(values)

    return processed


def get_architecture_specific_tags(specfile, extract_tags, targets,
                                   override_database, log=logging):
    """
    A high-level tool for Copr, working with temporary files, etc.
    """
    architecture_tags = {}
    request = SafeRequest(log=log)
    response = request.get(override_database)
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp:
        temp_path = temp.name
        temp.write(response.content)

    try:
        for distro in targets:
            ask = DEFAULT_TAG_MAP.get(distro, distro)
            log.info("Extracting arch-specific tags for %s", distro)
            architecture_tags[distro] = extract_tags_from_specfile(
                specfile,
                extract_tags,
                override_database=temp_path,
                target=ask,
                tag_cb=collapse_tag_values_cb,
                log=log,
            )
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
    return architecture_tags
