import json

import pytest

from copr_common.enums import StatusEnum

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator

class TestCoprResubmitBuild(CoprsTestCase):
    # pylint: disable=attribute-defined-outside-init

    def _distgit_chromium_built(self):
        self.api3.create_distgit_package("foocopr", "chromium")
        self.api3.rebuild_package("foocopr", "chromium")
        self.bdistgit = self.last_build
        self.backend.finish_build(self.bdistgit.id)

    @pytest.fixture
    def f_upload_processed(self, f_users, f_coprs, f_mock_chroots, f_builds):
        """
        Uploaded build with one succeeded, one failed and one skipped
        buildchroot.
        """
        _fixtures = f_users, f_coprs, f_mock_chroots, f_builds

        version = "1.0-2"
        data = {
            "url": f"https://copr.example.com/tmp/tmpu6sl_mi2/hello-world-{version}.el9.src.rpm",
            "pkg": f"hello-world-{version}.el9.src.rpm",
            "tmp": "tmpu6sl_mi2"
        }

        cc2 = self.models.CoprChroot()
        cc2.mock_chroot = self.mc2
        cc3 = self.models.CoprChroot()
        cc3.mock_chroot = self.mc3
        self.c1.copr_chroots.append(cc2)
        self.c1.copr_chroots.append(cc3)
        self.db.session.add_all([cc2, cc3])

        self.bupload = self.models.Build(
            copr=self.c1,
            pkgs=data["url"],
            pkg_version=version,
            source_json=json.dumps(data),
            source_type=2,
            copr_dir=self.c1_dir,
            user=self.u1,
            submitted_on=9,
            result_dir="06246100",
            source_status=1,
            srpm_url=data["url"],
            package=self.p1,
        )
        self.db.session.add_all([self.bupload])

        for (mc, cc, status) in [
            (self.mc1, self.c1.copr_chroots[0], "failed"),
            (self.mc2, self.c1.copr_chroots[1], "skipped"),
            (self.mc3, self.c1.copr_chroots[2], "succeeded"),
        ]:
            bch = self.models.BuildChroot(
                build=self.bupload,
                mock_chroot=mc,
                status=StatusEnum(status),
                git_hash="2a7eeee353531828f306167730cca1cc300e35ae",
                started_on=1674058555,
                ended_on=1674058639,
                result_dir='bar',
                copr_chroot=cc,
            )
            self.db.session.add(bch)

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_upload_processed", "f_db")
    def test_copr_repeat_build_attributes_upload(self):
        self.app.config["EXTRA_BUILDCHROOT_TAGS"] = [{
            "pattern": ".*",
            "tags": ["every_build"],
        }, {
            "pattern": "*invalid_regexp",
            "tags": ["invalid_not_attached"],
        }, {
            "pattern": "user1/foocopr/fedora-18-x86_64/hello-world",
            "tags": ["specific"],
        }, {
            "pattern": ".*/.*/.*/chromium",
            "tags": ["beefy"],
        }]

        self._distgit_chromium_built()

        # resubmitting uploaded build skips import
        self.web_ui.resubmit_build_id(self.bupload.id)
        new_build = self.last_build

        old_build = self.bdistgit
        for bch in old_build.build_chroots:
            assert bch.tags == ["every_build", "beefy"]

        # this is waiting for source processing, and import
        self.web_ui.resubmit_build_id(self.bdistgit.id)
        new_build2 = self.last_build

        assert len(new_build.build_chroots) == 3
        assert len(new_build2.build_chroots) == 3

        for bch in new_build.build_chroots:
            if bch.name == "fedora-18-x86_64":
                assert bch.tags == ["every_build", "specific"]
            else:
                assert bch.tags == ["every_build"]


        for bch in new_build2.build_chroots:
            # Nothing assigned till the package is imported
            assert bch.tags == []

        # Finish SRPM build by Backend, and import by DistGit.
        self.backend.finish_srpm_and_import(new_build2.id)
        for bch in new_build2.build_chroots:
            # Nothing assigned till the package is imported
            assert bch.state == "pending"
            assert bch.tags == ["every_build", "beefy"]
