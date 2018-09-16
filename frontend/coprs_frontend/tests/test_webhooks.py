import os
import json

from tests.coprs_test_case import CoprsTestCase

class TestCustomWebhook(CoprsTestCase):
    def custom_post(self, data, token, copr_id, package_name=None):
        url = "/webhooks/custom/{copr_id}/{uuid}/"
        url = url.format(uuid=token, copr_id=copr_id)
        if package_name:
            url = "{0}{1}/".format(url, package_name)

        return self.tc.post(
            url,
            content_type="application/json",
            data=json.dumps(data) if data != None else None,
        )


    def test_package_not_found(self, f_hook_package, f_db):
        r = self.custom_post(
            None,
            self.c1.webhook_secret,
            self.c1.id,
            'ddd',
        )
        assert r.data.decode('ascii') == "PACKAGE_NOT_FOUND\n"
        assert r.status_code == 404


    def test_hook_data_stored(self, f_hook_package, f_db):
        package_name = self.pHook.name
        hook_payload = {'some': 'data'}
        r = self.custom_post(
            hook_payload,
            self.c1.webhook_secret,
            self.c1.id,
            package_name,
        )

        build_id = int(r.data)
        builds = self.models.Build.query.filter_by(id=build_id).all()
        assert len(builds) == 1

        build = builds[0]
        assert package_name == build.package.name

        storage = self.app.config['STORAGE_DIR']
        source = json.loads(build.source_json)
        hook_file= os.path.join(storage, source['tmp'], 'hook_payload')
        with open(hook_file, 'r') as f:
            decoded = json.loads(f.read())
            assert decoded == hook_payload


    def test_bad_uuid(self, f_hook_package, f_db):
        assert self.custom_post(
            None,
            "invalid-token",
            self.c1.id,
            self.pHook.name,
        ).status_code == 403

        assert self.custom_post(
            None,
            "invalid-token",
            self.c1.id,
            "invalid-pkg-name",
        ).status_code == 403

        resp = self.custom_post(
            None,
            "invalid-token",
            '2',
            "invalid-pkg-name",
        )

        assert resp.status_code == 403
        assert resp.data.decode('ascii') == "BAD_UUID\n"
