from coprs.helpers import parse_package_name

from tests.coprs_test_case import CoprsTestCase


class TestHelpers(CoprsTestCase):

    def test_guess_package_name(self):
        EXP = {
            'wat-1.2.rpm': 'wat',
            'will-crash-0.5-2.fc20.src.rpm': 'will-crash',
            'will-crash-0.5-2.fc20.src': 'will-crash',
            'will-crash-0.5-2.fc20': 'will-crash',
            'will-crash-0.5-2': 'will-crash',
            'will-crash-0.5-2.rpm': 'will-crash',
            'will-crash-0.5-2.src.rpm': 'will-crash',
            'will-crash': 'will-crash',
            'pkgname7.src.rpm': 'pkgname7',
            'copr-frontend-1.14-1.git.65.9ba5393.fc20.noarch': 'copr-frontend',
            'noversion.fc20.src.rpm': 'noversion',
            'nothing': 'nothing',
            'ruby193': 'ruby193',
            'xorg-x11-fonts-ISO8859-1-75dpi-7.1-2.1.el5.noarch.rpm': 'xorg-x11-fonts-ISO8859-1-75dpi',
        }

        for pkg, expected in EXP.iteritems():
            assert parse_package_name(pkg) == expected
