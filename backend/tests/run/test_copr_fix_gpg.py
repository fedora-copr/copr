import sys
from unittest.mock import Mock, patch

from copr_common.enums import StorageEnum

sys.path.append('../../run')

# The script opens its log file in /var/log/copr-backend/ at import time,
# don't let it do that here.
with patch("logging.basicConfig"):
    from run import copr_fix_gpg  # pylint: disable=wrong-import-position

MODULE_REF = 'run.copr_fix_gpg'


class TestFixCopr:
    """
    Test that fix_copr() dispatches to the right storage backend.
    """

    def _setup_project(self, tmp_path, storage):
        """Create a project layout, return (opts, builddir, project_info)."""
        copr_path = tmp_path / "praiskup" / "proj"
        builddir = copr_path / "rhel-9-x86_64" / "00052887-dummy-pkg"
        builddir.mkdir(parents=True)
        # not a build dir, has to be skipped
        (copr_path / "rhel-9-x86_64" / "not-a-build-dir").mkdir()
        # not a chroot, has to be skipped
        (copr_path / "srpm-builds" / "something").mkdir(parents=True)

        opts = Mock(
            frontend_base_url="http://frontend",
            destdir=str(tmp_path),
            sign_domain="fedorahosted.org",
            results_baseurl="https://example.com/results",
            aws_cloudfront_distribution=None,
        )
        project_info = {"storage": storage, "appstream": False}
        return opts, builddir, project_info

    def _run(self, mc_info, opts, project_info):
        mc_info.return_value = project_info
        args = Mock(chroot=[])
        copr_fix_gpg.fix_copr(args, opts, "praiskup/proj")
        mc_info.assert_called_once_with("http://frontend", "praiskup", "proj")

    @patch(MODULE_REF + '.call_copr_repo')
    @patch(MODULE_REF + '.storage_for_enum')
    @patch(MODULE_REF + '.get_signer')
    @patch(MODULE_REF + '.get_project_info')
    def test_pulp_project(self, mc_info, _mc_signer,
                          mc_storage_for_enum, mc_call_copr_repo, tmp_path):
        """Pulp projects are re-signed through PulpStorage."""
        opts, _builddir, project_info = self._setup_project(
            tmp_path, storage="pulp")
        mc_storage_for_enum.return_value = mock_storage = Mock()
        mock_storage.resign_builds.return_value = []

        self._run(mc_info, opts, project_info)

        # PulpStorage was created for the project
        assert mc_storage_for_enum.call_args[0][:3] == \
            (StorageEnum.pulp, "praiskup", "proj")

        # the build was re-signed in Pulp, with the builds enumerated by
        # PulpStorage itself (not from the local results directory)
        mock_storage.resign_builds.assert_called_once_with(
            "proj", "rhel-9-x86_64")

        # no local re-signing / createrepo happened
        assert not mc_call_copr_repo.called

    @patch(MODULE_REF + '.log')
    @patch(MODULE_REF + '.storage_for_enum')
    @patch(MODULE_REF + '.get_signer')
    @patch(MODULE_REF + '.get_project_info')
    def test_pulp_project_failed_builds(self, mc_info, _mc_signer,
                                        mc_storage_for_enum,
                                        mc_log, tmp_path):
        """Builds that failed to re-sign in Pulp are loudly reported."""
        opts, _builddir, project_info = self._setup_project(
            tmp_path, storage="pulp")
        mc_storage_for_enum.return_value = mock_storage = Mock()
        mock_storage.resign_builds.return_value = [52887]

        self._run(mc_info, opts, project_info)

        mc_log.error.assert_called_once_with(
            "Builds %s in %s/%s were not re-signed, they still have "
            "the old GPG signature", [52887], "praiskup/proj",
            "rhel-9-x86_64")

    @patch(MODULE_REF + '.log')
    @patch(MODULE_REF + '.storage_for_enum')
    @patch(MODULE_REF + '.get_signer')
    @patch(MODULE_REF + '.get_project_info')
    def test_pulp_project_resign_builds_error(self, mc_info, _mc_signer,
                                              mc_storage_for_enum,
                                              mc_log, tmp_path):
        """A chroot that fails to re-sign doesn't block the other chroots."""
        opts, _builddir, project_info = self._setup_project(
            tmp_path, storage="pulp")
        # a second chroot, to check it is still processed
        (tmp_path / "praiskup" / "proj" / "fedora-42-x86_64").mkdir(parents=True)
        mc_storage_for_enum.return_value = mock_storage = Mock()

        def resign(_dirname, chroot):
            if chroot == "fedora-42-x86_64":
                raise RuntimeError("boom")
            return []
        mock_storage.resign_builds.side_effect = resign

        self._run(mc_info, opts, project_info)

        # both chroots were attempted ...
        assert mock_storage.resign_builds.call_count == 2
        # ... the exception was logged ...
        mc_log.exception.assert_called_once_with("boom")
        # ... and didn't propagate out of fix_copr()

    @patch(MODULE_REF + '.call_copr_repo')
    @patch(MODULE_REF + '.sign_rpms_in_dir')
    @patch(MODULE_REF + '.unsign_rpms_in_dir')
    @patch(MODULE_REF + '.storage_for_enum')
    @patch(MODULE_REF + '.get_signer')
    @patch(MODULE_REF + '.get_project_info')
    def test_backend_project(self, mc_info, _mc_signer,
                             mc_storage_for_enum, mc_unsign, mc_sign,
                             mc_call_copr_repo, tmp_path):
        """Backend-storage projects keep being re-signed locally."""
        opts, builddir, project_info = self._setup_project(
            tmp_path, storage="backend")

        self._run(mc_info, opts, project_info)

        assert not mc_storage_for_enum.called
        assert not mc_storage_for_enum.return_value.resign_builds.called

        # the local RPMs were un-signed and re-signed
        assert mc_unsign.call_args[0][0] == str(builddir)
        assert mc_sign.call_args[0][:4] == \
            ("praiskup", "proj", str(builddir), "rhel-9-x86_64")

        # and the local repodata was regenerated
        assert mc_call_copr_repo.called
