"""
Test PulpStorage
"""

# pylint: disable=attribute-defined-outside-init

from unittest.mock import Mock, patch

import pytest
from copr_common.request import RequestError
from copr_backend.exceptions import CoprBackendError
from copr_backend.storage import PulpStorage

RPM_NAME = "dummy-pkg-1.0-1.el9.noarch.rpm"
OLD_HREF = "/pulp/api/v3/content/rpm/packages/old/"
NEW_HREF = "/pulp/api/v3/content/rpm/packages/new/"
REPO_HREF = "/pulp/api/v3/repositories/rpm/rpm/repo/"
OLD_PUB_HREF = "/pulp/api/v3/publications/rpm/rpm/old/"
NEW_PUB_HREF = "/pulp/api/v3/publications/rpm/rpm/new/"
DIST_HREF = "/pulp/api/v3/distributions/rpm/rpm/dist/"
CHROOT = "fedora-rawhide-x86_64"


def _pulp_storage(destdir):
    opts = Mock(
        destdir=str(destdir),
        pulp_content_url="https://pulp.example.com",
    )
    with patch("copr_backend.storage.PulpClient.create_from_config_file"), \
         patch("copr_backend.storage.get_redis_connection"):
        storage = PulpStorage(
            "@foo", "proj", False, False, True, opts, Mock())
    storage.client = Mock()
    return storage


class TestPulpResignBuilds:
    """
    Test PulpStorage.resign_builds() and the _fork_build() refactoring on
    top of the shared _resign_pulp_build() helper.
    """

    def _storage(self, tmp_path):
        storage = _pulp_storage(tmp_path)

        # Pulp content of a build: one RPM
        content = Mock()
        content.json.return_value = {"results": [
            {"location_href": RPM_NAME, "pulp_href": OLD_HREF}]}
        storage.client.get_content.return_value = content

        # Uploading the re-signed RPM creates a new content unit
        upload = Mock()
        upload.ok = True
        upload.json.return_value = {"pulp_href": NEW_HREF, "prn": "prn:new"}
        storage.client.create_content.return_value = upload

        # The Pulp repository of the project
        repository = Mock()
        repository.json.return_value = {"results": [{"pulp_href": REPO_HREF}]}
        storage.client.get_repository.return_value = repository

        # The builds hosted in the Pulp repository
        storage.client.get_build_ids.return_value = [123]

        # The publication created by the modify_content() batch
        publication = Mock()
        publication.json.return_value = {"results": [
            {"pulp_href": NEW_PUB_HREF}]}
        storage.client.get_publication.return_value = publication

        # The public distribution of the project, repository-backed by default
        # (i.e. the project doesn't use the manual createrepo feature)
        self.distribution = Mock()
        self.distribution.json.return_value = {"results": [{
            "pulp_href": DIST_HREF,
            "publication": None,
        }]}
        storage.client.get_distribution.return_value = self.distribution

        # Downloading the RPM from Pulp
        self.download = Mock()
        self.download.content = b"an rpm file"

        return storage

    def _builddir(self, tmp_path, project, name):
        path = tmp_path / project / CHROOT / name
        path.mkdir(parents=True)
        return path

    def test_resign_builds_no_signing(self, tmp_path):
        """
        With signing disabled the repair refuses to run — the re-signed
        (i.e. unsigned) RPMs would replace the signed published content.
        """
        storage = _pulp_storage(tmp_path)
        storage.opts.do_sign = False

        with pytest.raises(CoprBackendError, match="do_sign=false"):
            storage.resign_builds("proj", CHROOT)

        assert not storage.client.get_build_ids.called

    @patch("copr_backend.storage.SafeRequest")
    @patch("copr_backend.storage.resign_rpms_in_dir")
    def test_resign_builds(self, mc_resign, mc_safe_request, tmp_path):
        storage = self._storage(tmp_path)
        mc_safe_request.return_value.get.return_value = self.download

        result = storage.resign_builds("proj", CHROOT)

        # the builds to re-sign were enumerated from the Pulp repository
        storage.client.get_build_ids.assert_called_once_with(REPO_HREF)

        # the build's RPMs were found in Pulp by the build id
        storage.client.get_content.assert_called_once_with(
            [123], CHROOT, fields=["location_href", "pulp_href"])

        # the RPM was downloaded ...
        mc_safe_request.return_value.get.assert_called_once_with(
            f"https://pulp.example.com/@foo/proj/{CHROOT}/Packages/d/{RPM_NAME}")

        # ... re-signed with this project's key ...
        args = mc_resign.call_args[0]
        assert args[0] == "@foo"
        assert args[1] == "proj"
        assert args[3] == CHROOT

        # ... and uploaded back under the very same build id
        assert storage.client.create_content.call_args[0][1] == {
            "build_id": 123, "chroot": CHROOT}

        # the new content replaced the old one
        storage.client.modify_content.assert_called_once_with(
            REPO_HREF, [NEW_HREF], [OLD_HREF])

        # a repository-backed distribution serves the new version as-is
        assert not storage.client.update_distribution.called
        assert not result

    @patch("copr_backend.storage.SafeRequest")
    @patch("copr_backend.storage.resign_rpms_in_dir")
    def test_resign_builds_manual_createrepo(self, _mc_resign, mc_safe_request,
                                             tmp_path):
        """
        A public distribution pointed to a fixed publication (a project with
        the manual createrepo feature) must be re-pointed to the publication
        created by the re-signing.
        """
        storage = self._storage(tmp_path)
        self.distribution.json.return_value = {"results": [{
            "pulp_href": DIST_HREF,
            "publication": OLD_PUB_HREF,
        }]}
        mc_safe_request.return_value.get.return_value = self.download

        storage.resign_builds("proj", CHROOT)

        storage.client.update_distribution.assert_called_once_with(
            DIST_HREF, publication=NEW_PUB_HREF)

    @patch("copr_backend.storage.SafeRequest")
    @patch("copr_backend.storage.resign_rpms_in_dir")
    def test_resign_builds_not_found(self, mc_resign, mc_safe_request,
                                     tmp_path):
        """A 404 download (a CoprDir build) is skipped, nothing is removed."""
        storage = self._storage(tmp_path)
        mc_safe_request.return_value.get.side_effect = RequestError(
            "not found", Mock(status_code=404))

        storage.resign_builds("proj", CHROOT)

        assert not mc_resign.called
        assert not storage.client.create_content.called
        assert not storage.client.modify_content.called

    @patch("copr_backend.storage.SafeRequest")
    @patch("copr_backend.storage.resign_rpms_in_dir")
    def test_resign_builds_download_failure(self, mc_resign, mc_safe_request,
                                            tmp_path):
        """A failed download doesn't create a repository version, and is
        reported back to the caller."""
        storage = self._storage(tmp_path)
        mc_safe_request.return_value.get.side_effect = RequestError("boom")

        failed = storage.resign_builds("proj", CHROOT)

        assert failed == [123]
        assert not mc_resign.called
        assert not storage.client.modify_content.called

    @patch("copr_backend.storage.SafeRequest")
    @patch("copr_backend.storage.resign_rpms_in_dir")
    def test_fork_build(self, mc_resign, mc_safe_request, tmp_path):
        """_fork_build() shares the re-signing helper, but only adds content."""
        storage = self._storage(tmp_path)
        mc_safe_request.return_value.get.return_value = self.download
        dst_dir = "00000456-dummy-pkg"
        self._builddir(tmp_path, "dst", dst_dir)

        hrefs = storage._fork_build(  # pylint: disable=protected-access
            123, 456, "@foo", "proj", "@foo", "dst", CHROOT, dst_dir)

        assert hrefs == [NEW_HREF]

        # the forked RPMs are signed with the destination project's key ...
        args = mc_resign.call_args[0]
        assert args[0] == "@foo"
        assert args[1] == "dst"

        # ... looked up by the source build id ...
        assert storage.client.get_content.call_args[0][0] == [123]

        # ... and uploaded under the destination build id
        assert storage.client.create_content.call_args[0][1]["build_id"] == 456

        # forking only adds content, the caller creates the repo version
        assert not storage.client.modify_content.called

    @patch("copr_backend.storage.SafeRequest")
    @patch("copr_backend.storage.resign_rpms_in_dir")
    def test_fork_build_download_failure(self, _mc_resign, mc_safe_request,
                                         tmp_path):
        """A failed download propagates to the fork caller."""
        storage = self._storage(tmp_path)
        mc_safe_request.return_value.get.side_effect = RequestError("boom")
        dst_dir = "00000456-dummy-pkg"
        self._builddir(tmp_path, "dst", dst_dir)

        with pytest.raises(RequestError):
            storage._fork_build(  # pylint: disable=protected-access
                123, 456, "@foo", "proj", "@foo", "dst", CHROOT, dst_dir)
