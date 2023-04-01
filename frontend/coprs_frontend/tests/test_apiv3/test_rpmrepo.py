from datetime import datetime, timedelta
import pytest
from tests.coprs_test_case import (
    CoprsTestCase,
    TransactionDecorator,
)


U1_DATA = {'dependencies': [],
 'directories': {'foocopr': {}},
 'repos': {'epel-5': {'arch': {'i386': {'opts': {}},
                               'x86_64': {'multilib': {'i386': {'opts': {'cost': '1100'}}},
                                          'opts': {}}}},
           'epel-6': {'arch': {'i386': {'opts': {}},
                               'x86_64': {'multilib': {'i386': {'opts': {'cost': '1100'}}},
                                          'opts': {}}}},
           'epel-7': {'arch': {'x86_64': {'opts': {}}}},
           'fedora-18': {'arch': {'x86_64': {'opts': {}}}},
           'fedora-19': {'arch': {'i386': {'opts': {}},
                                  'x86_64': {'multilib': {'i386': {'opts': {'cost': '1100'}}},
                                             'opts': {}}}},
           'fedora-20': {'arch': {'i386': {'opts': {}},
                                  'x86_64': {'multilib': {'i386': {'opts': {'cost': '1100'}}},
                                             'opts': {}}}},
           'fedora-21': {'arch': {'i386': {'opts': {}},
                                  'x86_64': {'multilib': {'i386': {'opts': {'cost': '1100'}}},
                                             'opts': {}}}},
           'fedora-22': {'arch': {'i386': {'opts': {}},
                                  'x86_64': {'multilib': {'i386': {'opts': {'cost': '1100'}}},
                                             'opts': {}}}},
           'fedora-23': {'arch': {'i386': {'opts': {}},
                                  'x86_64': {'multilib': {'i386': {'opts': {'cost': '1100'}}},
                                             'opts': {}}}}},
 'results_url': 'http://copr-be-dev.cloud.fedoraproject.org/results'}


U2_DATA = {'delete_after_days': 179,
 'dependencies': [{'data': {'owner': 'user1', 'projectname': 'foocopr'},
                   'opts': {'id': 'coprdep:localhost:user1:foocopr',
                            'name': 'Copr localhost/user2/barcopr runtime '
                                    'dependency #1 - user1/foocopr'},
                   'type': 'copr'},
                  {'data': {'pattern': 'https://url.to/external/repo'},
                   'opts': {'id': 'coprdep:https_url_to_external_repo',
                            'name': 'Copr localhost/user2/barcopr external '
                                    'runtime dependency #2 - '
                                    'https_url_to_external_repo'},
                   'type': 'external_baseurl'}],
 'directories': {'barcopr': {}},
 'repos': {'fedora-18': {'arch': {'x86_64': {'delete_after_days': 9,
                                             'opts': {}}}},
           'fedora-rawhide': {'arch': {'i386': {'opts': {}}}}},
 'results_url': 'http://copr-be-dev.cloud.fedoraproject.org/results'}


DIRS = {'dependencies': [],
 'directories': {'test': {}, 'test:pr:1123': {'delete_after_days': 39}},
 'repos': {'fedora-17': {'arch': {'i386': {'opts': {}},
                                  'x86_64': {'opts': {}}}}},
 'results_url': 'http://copr-be-dev.cloud.fedoraproject.org/results'}


class TestApiRPMRepo(CoprsTestCase):
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_apiv3_rpmrepo_external_deps(self):
        # both 'foo' and 'foo:pr:11' give the same output.

        self.c3.delete_after = datetime.now() + timedelta(days=180)
        self.c3.copr_chroots[0].deleted = True
        self.c3.copr_chroots[0].delete_after = \
                datetime.now() + timedelta(days=10)
        self.db.session.commit()

        for dirname in [self.c3.name, self.c3.name + ':pr:11']:
            repodata = self.tc.get(
                "/api_3/rpmrepo/{0}/{1}/fedora-18/".format(
                    self.u2.name, dirname))
            assert repodata.json == U2_DATA

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_mock_chroots_many", "f_custom_builds", "f_db")
    def test_apiv3_rpmrepo_multilib(self):
        self.c1.multilib = True
        self.db.session.commit()
        repodata = self.tc.get(
            "/api_3/rpmrepo/{0}/{1}/fedora-24/".format(
                self.u1.name, self.c1.name))
        assert repodata.json == U1_DATA

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_apiv3_rpmrepo_dirs(self):
        self.web_ui.new_project("test", ["fedora-17-i386", "fedora-17-x86_64"])
        self.web_ui.create_distgit_package("test", "copr-cli")
        self.api3.rebuild_package("test:pr:1123", "copr-cli")
        for dirname in ['test', 'test:pr:11']:
            repodata = self.tc.get(f"/api_3/rpmrepo/user1/{dirname}/fedora-18/")
            assert repodata.json == DIRS
