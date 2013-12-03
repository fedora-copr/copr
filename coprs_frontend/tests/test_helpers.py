from coprs.helpers import guess_package_name

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
        }

        for pkg, expected in EXP.iteritems():
            assert guess_package_name(pkg) == expected
