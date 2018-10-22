from __future__ import absolute_import
import munch


class Munch(munch.Munch):
    """
    We are extending a Munch class to modify some of its functionality.
    The goal is to not do a great differences from the original. This class
    is not a place for implementing methods that communicates with frontend
    e.g. project.save(), build.chroots(), etc.

    Changes should be in line with the APIv3 philosophy. We want to e.g.
    store some special attributes in munch, that we don't want to necessarily
    show to user when printing because of degradation of data readability.
    """

    def __repr__(self):
        public = {k: v for k, v in self.items()}
        return '{0}({1})'.format(self.__class__.__name__, dict.__repr__(public))

    def items(self):
        return [(k, v) for k, v in super(Munch, self).items() if not k.startswith("__")]

    def keys(self):
        return [k for k in super(Munch, self).keys() if not k.startswith("__")]
