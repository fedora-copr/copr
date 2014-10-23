from operator import methodcaller
import optparse

__author__ = 'vgologuz'


class SortedOptParser(optparse.OptionParser):

    """Optparser which sorts the options by opt before outputting --help"""

    def format_help(self, formatter=None):
        self.option_list.sort(key=methodcaller("get_opt_string"))
        return optparse.OptionParser.format_help(self, formatter=None)
