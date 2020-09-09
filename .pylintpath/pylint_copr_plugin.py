"""
pylint plugin doing copr-specific transformation to shut-down specific errors
which we can not easily ignore because the ignore mechanisms don't have the
needed granularity.
"""

from astroid import MANAGER, scoped_nodes, extract_node

def register(_linter):
    """ required pylint entrypoint """

def is_test_method(method):
    """ ignore missing-function-docstring in tests """
    if method.name.startswith("test_"):
        return True
    if method.name in ["setup_method", "teardown_method"]:
        return True
    return False

def transform_functions(function):
    """
    Transformate some function definitions so pylint doesn't object.
    """
    if function.name == 'logger':
        for prop in ['debug', 'info', 'warning', 'error']:
            function.instance_attrs[prop] = extract_node('def {name}(arg): return'.format(name=prop))

    if function.name in ["upgrade", "downgrade"]:
        # ignore missing-function-docstring in migrations
        function.doc = "fake docs"

    if function.name == "step_impl":
        # behave step definition
        function.doc = "fake docs"

    if is_test_method(function):
        function.doc = "fake docs"

def transform_classes(classdef):
    """
    Transformate some function definitions so pylint doesn't object.
    """
    if classdef.name.startswith("Test"):
        # ignore missing-function-docstring in migrations
        classdef.doc = "fake docs"


MANAGER.register_transform(scoped_nodes.FunctionDef, transform_functions)
MANAGER.register_transform(scoped_nodes.ClassDef, transform_classes)
