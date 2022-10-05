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
            data=json.dumps(data, ensure_ascii=False) if data != None else None,
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
        hook_payload = {'utf-8': 'data ❤'}
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


class TestGithubWebhook(CoprsTestCase):
    def github_post(self, data, token, copr_id, headers):
        url = "/webhooks/github/{copr_id}/{uuid}/"
        url = url.format(uuid=token, copr_id=copr_id)

        return self.tc.post(
            url,
            content_type="application/json",
            data=json.dumps(data) if data is not None else None,
            headers=headers
        )

    def test_package_bad_request(self, f_hook_package, f_db):
        headers = {'X-GitHub-Event': 'test'}
        hook_payload = {'some': 'data'}
        r = self.github_post(
            hook_payload,
            self.c1.webhook_secret,
            self.c1.id,
            headers
        )
        assert r.data.decode('ascii') == "Bad Request"
        assert r.status_code == 400

    def test_hook_status_ping_event(self, f_hook_package, f_db):
        hook_payload = {'some': 'data'}
        headers = {'X-GitHub-Event': 'ping'}
        r = self.github_post(
            hook_payload,
            self.c1.webhook_secret,
            self.c1.id,
            headers
        )

        assert r.data.decode('ascii') == 'OK'
        assert r.status_code == 200

    def test_hook_data_stored(self, f_hook_package, f_db):
        package_name = self.pHook.name
        source_json = {"type": "git",
                       "clone_url": "https://github.com/{0}/{1}.git".format(self.u1.username, package_name),
                       "subdirectory": "", "committish": "", "spec": "",
                       "srpm_build_method": "rpkg"}
        self.pHook.source_json = json.dumps(source_json)
        headers = {'X-GitHub-Event': 'push'}
        self.pHook.webhook_rebuild = True
        hook_payload = {
            "ref": "refs/heads/master",
            "before": "2a7a2e3e0ee63ac5abcca96209e1fc50cd457226",
            "commits": [{"added": ["{0}".format(package_name)], "removed": [], "modified": []}],
            "repository": {"clone_url": "https://github.com/{0}/{1}.git".format(self.u1.username, package_name)},
            "sender": {
                "login": self.u1.username,
                "url": "https://api.github.com/users/{0}".format(self.u1.username)
            }
        }
        r = self.github_post(
            hook_payload,
            self.c1.webhook_secret,
            self.c1.id,
            headers
        )
        package = self.models.Package.query.filter_by(name=package_name).first()

        assert r.data.decode('ascii') == 'OK'
        assert r.status_code == 200
        assert len(package.builds) == 1

    def test_bad_uuid(self, f_hook_package, f_db):
        r = self.github_post(
            None,
            "invalid-token",
            self.c1.id,
            {'X-GitHub-Event': 'issues'}
        )
        assert r.status_code == 403


class TestGitlabWebhook(CoprsTestCase):
    def gitlab_post(self, data, token, copr_id, headers):
        url = "/webhooks/gitlab/{copr_id}/{uuid}/"
        url = url.format(uuid=token, copr_id=copr_id)

        return self.tc.post(
            url,
            content_type="application/json",
            data=json.dumps(data) if data is not None else None,
            headers=headers
        )

    def test_package_bad_request(self, f_hook_package, f_db):
        headers = {'X-Gitlab-Event': 'test'}
        hook_payload = {'some': 'data'}
        r = self.gitlab_post(
            hook_payload,
            self.c1.webhook_secret,
            self.c1.id,
            headers
        )
        assert r.data.decode('ascii') == "Bad Request"
        assert r.status_code == 400

    def test_hook_data_stored(self, f_hook_package, f_db):
        package_name = self.pHook.name
        source_json = {"type": "git",
                       "clone_url": "https://gitlab.com/{0}/{1}.git".format(self.u1.username, package_name),
                       "subdirectory": "", "committish": "", "spec": "",
                       "srpm_build_method": "rpkg"}
        self.pHook.source_json = json.dumps(source_json)
        headers = {'X-Gitlab-Event': 'Push Hook'}
        self.pHook.webhook_rebuild = True
        hook_payload = {
            "object_kind": "push",
            "ref": "refs/heads/master",
            "before": "9e6f31bead67d176a71a198f0c10fc764799a4a7",
            "after": "f956357fe84ba899faf9efadeed1f32c8c8cac85",
            "commits": [{"added": ["{0}".format(package_name)], "removed": [], "modified": []}],
            "project": {"git_http_url": "https://gitlab.com/{0}/{1}.git".format(self.u1.username, package_name)},
            "user_username": self.u1.username
        }
        r = self.gitlab_post(
            hook_payload,
            self.c1.webhook_secret,
            self.c1.id,
            headers
        )
        package = self.models.Package.query.filter_by(name=package_name).first()

        assert r.data.decode('ascii') == 'OK'
        assert r.status_code == 200
        assert len(package.builds) == 1

    def test_bad_uuid(self, f_hook_package, f_db):
        r = self.gitlab_post(
            None,
            "invalid-token",
            self.c1.id,
            {'X-Gitlab-Event': 'Push Hook'}
        )
        assert r.status_code == 403


class TestBitbucketWebhook(CoprsTestCase):
    def bitbucket_post(self, data, token, copr_id, headers):
        url = "/webhooks/bitbucket/{copr_id}/{uuid}/"
        url = url.format(uuid=token, copr_id=copr_id)

        return self.tc.post(
            url,
            content_type="application/json",
            data=json.dumps(data) if data is not None else None,
            headers=headers
        )

    def test_package_bad_request(self, f_hook_package, f_db):
        headers = {'X-Event-Key': 'repo:test'}
        hook_payload = {'some': 'data'}
        r = self.bitbucket_post(
            hook_payload,
            self.c1.webhook_secret,
            self.c1.id,
            headers
        )
        assert r.data.decode('ascii') == "Bad Request"
        assert r.status_code == 400

    def test_hook_data_stored(self, f_hook_package, f_db):
        package_name = self.pHook.name
        source_json = {"type": "git",
                       "clone_url": "https://bitbucket.org/{0}/{1}".format(self.u1.username, package_name),
                       "subdirectory": "", "committish": "", "spec": "",
                       "srpm_build_method": "rpkg"}
        self.pHook.source_json = json.dumps(source_json)
        headers = {'X-Event-Key': 'repo:push'}
        self.pHook.webhook_rebuild = True
        hook_payload = {
            "object_kind": "push",
            "ref": "refs/heads/master",
            "before": "9e6f31bead67d176a71a198f0c10fc764799a4a7",
            "after": "f956357fe84ba899faf9efadeed1f32c8c8cac85",
            "push": {
                "changes": [{"new": {"name": "{0}-1".format(package_name), "type": "tag",
                                     "target": {"hash": "82c876a27ceafd80465c35e601afab604463ae86"}}}]
            },
            "commits": [{"added": ["{0}".format(package_name)], "removed": [], "modified": []}],
            "repository": {
                "links": {
                    "self": {
                        "href": "https://api.bitbucket.org/2.0/repositories/{0}/{1}".format(self.u1.username,
                                                                                            package_name)},
                    "html": {
                        "href": "https://bitbucket.org/{0}/{1}".format(self.u1.username, package_name)
                    },
                },
            },
            "actor": {
                "links": {
                    "html": {
                        "href": "https://bitbucket.org/%7B4610cba6-e60c-4a9d-9e9f-481e6ce42327%7D/"
                    },
                }
            },
            "user_username": self.u1.username
        }
        r = self.bitbucket_post(
            hook_payload,
            self.c1.webhook_secret,
            self.c1.id,
            headers
        )
        package = self.models.Package.query.filter_by(name=package_name).first()

        assert r.data.decode('ascii') == 'OK'
        assert r.status_code == 200
        assert len(package.builds) == 1

    def test_bad_uuid(self, f_hook_package, f_db):
        r = self.bitbucket_post(
            None,
            "invalid-token",
            self.c1.id,
            {'X-Event-Key': 'repo:push'}
        )
        assert r.status_code == 403
