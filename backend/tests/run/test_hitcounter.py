from copr_backend.hitcounter import url_to_key_strings


class TestHitcounter:
    def test_url_to_key_strings(self):
        # RPM package in the backend storage
        url = (
            "/results/frostyx/hello/fedora-41-x86_64/"
            "09144301-hello/hello-2.12.2-1.fc41.x86_64.rpm"
        )
        assert set(url_to_key_strings(url)) == {
            "chroot_rpms_dl_stat|frostyx|hello|fedora-41-x86_64",
            "project_rpms_dl_stat|frostyx|hello",
        }

        # URL for a directory
        url = (
            "/results/frostyx/foo/fedora-42-x86_64/"
            "02923998-ed/"
        )
        assert set(url_to_key_strings(url)) == set()

        # URL for a primary.xml.gz in Pulp
        url = (
            "/results/frostyx/foo/fedora-42-x86_64/"
            "repodata/8eff304fewmorehashchars-primary.xml.gz"
        )
        assert set(url_to_key_strings(url)) == set()

        # URL for a repofile. Same for both backend and Pulp
        url = (
            "/results/frostyx/foo/fedora-42-x86_64/"
            "repodata/repomd.xml"
        )
        assert set(url_to_key_strings(url)) == {
            "chroot_repo_metadata_dl_stat|frostyx|foo|fedora-42-x86_64"
        }

        # URL for an RPM package in Pulp
        url = (
            "/results/frostyx/foo/fedora-42-x86_64/"
            "Packages/e/ed-1.22.2-1.fc42.x86_64.rpm"
        )
        assert set(url_to_key_strings(url)) == {
            "chroot_rpms_dl_stat|frostyx|foo|fedora-42-x86_64",
            "project_rpms_dl_stat|frostyx|foo",
        }
