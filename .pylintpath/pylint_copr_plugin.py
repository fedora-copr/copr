"""
pylint plugin doing copr-specific transformation to shut-down specific errors
which we can not easily ignore because the ignore mechanisms don't have the
needed granularity.
"""

import os
import subprocess
from astroid import MANAGER, scoped_nodes, nodes, extract_node

def register(_linter):
    """ required pylint entrypoint """

class Cache:
    """
    Some rather expensive checks cached (as a class to avoid using globals).
    """
    _gitroot = None
    _test_files = {
        # Some modules have None in the file argument:
        # ipdb> function
        # <FunctionDef.cmp_to_key l.None at 0x7febf4adcb20>
        # ipdb> function.parent
        # <Module._functools l.0 at 0x7febf4adcbb0>
        # ipdb> function.parent.file is None
        # True
        None: False,
    }
    test_paths = {
        "backend/tests",
        "cli/tests",
        "common/tests",
        "dist-git/tests",
        "frontend/coprs_frontend/tests",
        "keygen/tests",
        "messaging/copr_messaging/tests",
        "python/copr/test",
        "rpmbuild/tests",
    }

    @classmethod
    @property
    def gitroot(cls):
        """ Obtain the git-root of the current directory, and cache """
        if cls._gitroot:
            return cls._gitroot
        cls._gitroot = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode("utf-8").strip()
        return cls.gitroot

    @classmethod
    def _slow_is_test_file(cls, test_file):
        if not test_file.startswith(cls.gitroot + os.sep):
            return False
        relpath = os.path.relpath(test_file, cls.gitroot)
        for test_path in cls.test_paths:
            if relpath.startswith(test_path):
                return True
        return False

    @classmethod
    def is_test_file(cls, file_path):
        """
        Check if file_path (path relative to the gitroot) is a test-file (per
        cls.test_paths configuration).
        """
        cached = cls._test_files.get(file_path)
        if cached is None:
            cls._test_files[file_path] = cls._slow_is_test_file(file_path)
        return cls._test_files[file_path]


def module_path(node):
    """
    Filename where the node (e.g. method) is defined.
    """
    while node:
        if isinstance(node, scoped_nodes.Module):
            return node.file
        node = node.parent
    return None


def add_fake_docs(the_object):
    """
    Add fake docs to the specified object so PyLint later doesn't complain about
    missing docs.
    """
    the_object.doc_node = nodes.Const("fake docs")
    the_object.doc = "fake docs"


def transform_functions(function):
    """
    Transformate some function definitions so pylint doesn't object.
    """

    filename = module_path(function)

    if function.name == 'logger':
        for prop in ['debug', 'info', 'warning', 'error', 'exception']:
            function.instance_attrs[prop] = extract_node('def {name}(arg): return'.format(name=prop))

    if function.name in ["upgrade", "downgrade"]:
        # ignore missing-function-docstring in migrations
        add_fake_docs(function)

    if function.name == "step_impl":
        # behave step definition
        add_fake_docs(function)

    if Cache.is_test_file(filename):
        add_fake_docs(function)

def transform_classes(classdef):
    """
    Transform Class definitions that don't need to have docstrings.
    """
    filename = module_path(classdef)
    if Cache.is_test_file(filename):
        add_fake_docs(classdef)

def transform_modules(moduledef):
    """
    Testing modules don't nave to have the doc-strings either.
    """
    if Cache.is_test_file(moduledef.file):
        add_fake_docs(moduledef)


MANAGER.register_transform(scoped_nodes.FunctionDef, transform_functions)
MANAGER.register_transform(scoped_nodes.ClassDef, transform_classes)
MANAGER.register_transform(scoped_nodes.Module, transform_modules)
