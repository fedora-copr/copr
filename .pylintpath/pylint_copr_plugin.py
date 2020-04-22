"""
pylint plugin doing copr-specific transformation to shut-down specific errors
which we can not easily ignore because the ignore mechanisms don't have the
needed granularity.
"""

from astroid import MANAGER, scoped_nodes, extract_node

def register(_linter):
    """ required pylint entrypoint """

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

MANAGER.register_transform(scoped_nodes.FunctionDef, transform_functions)
