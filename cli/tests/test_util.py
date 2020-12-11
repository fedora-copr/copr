""" test copr_cli/util.py """

from munch import Munch

from copr.v3.helpers import List
import copr_cli.util as util

def test_serializable():
    x = Munch()
    x["__proxy__"] = test_serializable
    x["__response__"] = test_serializable
    x.y = List(items=[Munch({1: 2})])
    assert util.json_dumps(x) == "\n".join([
        '{',
        '    "y": [',
        '        {',
        '            "1": 2',
        '        }',
        '    ]',
        '}',
    ])
    assert x["__proxy__"] == x["__response__"] == test_serializable
