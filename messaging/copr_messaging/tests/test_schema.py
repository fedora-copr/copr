# Copyright (C) 2019  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# pylint: skip-file

"""Unit tests for the message schema."""

import copy
import unittest

from jsonschema import ValidationError
from .. import schema


class BuildChrootStartedV1Test(unittest.TestCase):
    """A set of unit tests to ensure the schema works as expected."""

    msg_class = schema.BuildChrootStartedV1
    required_fields = ['status', 'what', 'chroot', 'ip', 'user', 'who',
                       'pid', 'copr', 'version', 'build', 'owner', 'pkg']

    def setUp(self):
        self.fedmsg_message = {
            "username": "copr",
            "source_name": "datanommer",
            "certificate": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUVUakNDQTdlZ0F3SUJBZ0lDQVBZd0RRWUpL\nb1pJaHZjTkFRRUZCUUF3Z2FBeEN6QUpCZ05WQkFZVEFsVlQKTVFzd0NRWURWUVFJRXdKT1F6RVFN\nQTRHQTFVRUJ4TUhVbUZzWldsbmFERVhNQlVHQTFVRUNoTU9SbVZrYjNKaApJRkJ5YjJwbFkzUXhE\nekFOQmdOVkJBc1RCbVpsWkcxelp6RVBNQTBHQTFVRUF4TUdabVZrYlhObk1ROHdEUVlEClZRUXBF\nd1ptWldSdGMyY3hKakFrQmdrcWhraUc5dzBCQ1FFV0YyRmtiV2x1UUdabFpHOXlZWEJ5YjJwbFkz\nUXUKYjNKbk1CNFhEVEUwTURReU16RTBNamsxTVZvWERUSTBNRFF5TURFME1qazFNVm93Z2R3eEN6\nQUpCZ05WQkFZVApBbFZUTVFzd0NRWURWUVFJRXdKT1F6RVFNQTRHQTFVRUJ4TUhVbUZzWldsbmFE\nRVhNQlVHQTFVRUNoTU9SbVZrCmIzSmhJRkJ5YjJwbFkzUXhEekFOQmdOVkJBc1RCbVpsWkcxelp6\nRXRNQ3NHQTFVRUF4TWtZMjl3Y2kxamIzQnkKTFdKbExtTnNiM1ZrTG1abFpHOXlZWEJ5YjJwbFkz\nUXViM0puTVMwd0t3WURWUVFwRXlSamIzQnlMV052Y0hJdApZbVV1WTJ4dmRXUXVabVZrYjNKaGNI\nSnZhbVZqZEM1dmNtY3hKakFrQmdrcWhraUc5dzBCQ1FFV0YyRmtiV2x1ClFHWmxaRzl5WVhCeWIy\ncGxZM1F1YjNKbk1JR2ZNQTBHQ1NxR1NJYjNEUUVCQVFVQUE0R05BRENCaVFLQmdRQ2UKREs5VFQy\nM05BdTZPWTVGMnVVNHpMRW9Ld2k1RnRRTU5jVWV5eDdmOHJxMUZXaUxDWHBjWFhpU2tzUE1XV1NM\nWQo5SHNoa1pvM3ZjMHFSRXVBWDNweWRuM2VFRDA0UExrUmRlaWpvSXA5L0Y2YlZ3MmlLMDdXRmc5\nU2MwNlRsKzhSCld1RHNaeTQ1SVJKYXhCRTlJaHBYL0x2Y2JnQ1cvZmVHVGp5WG1iRHd0UUlEQVFB\nQm80SUJWekNDQVZNd0NRWUQKVlIwVEJBSXdBREF0QmdsZ2hrZ0JodmhDQVEwRUlCWWVSV0Z6ZVMx\nU1UwRWdSMlZ1WlhKaGRHVmtJRU5sY25ScApabWxqWVhSbE1CMEdBMVVkRGdRV0JCUm5lNTg0d3Bs\nWGYrZVE2K25zSTZCbm5BNENaRENCMVFZRFZSMGpCSUhOCk1JSEtnQlJyUUZyNUVnaUpXZWRaNVFY\nMUFoMEtUbjhVQUtHQnBxU0JvekNCb0RFTE1Ba0dBMVVFQmhNQ1ZWTXgKQ3pBSkJnTlZCQWdUQWs1\nRE1SQXdEZ1lEVlFRSEV3ZFNZV3hsYVdkb01SY3dGUVlEVlFRS0V3NUdaV1J2Y21FZwpVSEp2YW1W\namRERVBNQTBHQTFVRUN4TUdabVZrYlhObk1ROHdEUVlEVlFRREV3Wm1aV1J0YzJjeER6QU5CZ05W\nCkJDa1RCbVpsWkcxelp6RW1NQ1FHQ1NxR1NJYjNEUUVKQVJZWFlXUnRhVzVBWm1Wa2IzSmhjSEp2\nYW1WamRDNXYKY21lQ0NRRGpVQjVIVHhjZVJUQVRCZ05WSFNVRUREQUtCZ2dyQmdFRkJRY0RBakFM\nQmdOVkhROEVCQU1DQjRBdwpEUVlKS29aSWh2Y05BUUVGQlFBRGdZRUFVazNlbjBYUXpDQm5IUlh4\nZDhyOHp2ZFAwVURvbEpiUysyTEl3Z3NDClJDMnNkZ1UwNGdFblYxdFpVTjNydEk1SzQ2MnpKT0JQ\nOFhQd3h4eUZMN1lOYmVtWTgyTG52Y1pHdzliMGdxTDMKdHNKbzllSFV5SXBZMG93TlVKdzgzU1Ax\neFJvb3NwVGJRK3BsNm9qdjVPNVpGZ1lBUG1yckRWZ0M4a2gzRlp4Rgp0SWc9Ci0tLS0tRU5EIENF\nUlRJRklDQVRFLS0tLS0K\n",
            "i": 1,
            "timestamp": 1561545908.0,
            "msg_id": "2019-77336a2c-bbe1-4362-b466-32d6595d328b",
            "crypto": "x509",
            "topic": "org.fedoraproject.prod.copr.build.start",
            "headers": {},
            "signature": "kMANxtkdgupoXP5VAbyp6Hc//G+i4KGUhaRvlStb1uSNMRoUG+rqeNio4JXwez9C9ppT7oGezTAn\nSNfW2F0mt/XikqQrhpP3cOpE47327udgP+IwrP+WT3lZv1wH9LTpHj+eRgKmXNcCNUXYCWvCgGqi\nQ5PSpDcZsn+MJaCwP/M=\n",
            "source_version": "0.9.0",
            "msg": {
                "status": 3,
                "what": "build start: user:churchyard copr:python3.8 pkg:python-hypothesis build:945012 ip:172.25.93.20 pid:3762",
                "chroot": "fedora-rawhide-x86_64",
                "ip": "172.25.93.20",
                "user": "churchyard",
                "who": "backend.worker-23551-PC",
                "pid": 3762,
                "copr": "python3.8",
                "version": "4.23.8-1.fc31",
                "build": 945012,
                "owner": "@python",
                "pkg": "python-hypothesis"
            }
        }
        self.build_id = 945012
        self.name = "@python/python3.8"

    def test_correct_messages(self):
        """
        Assert the message schema validates a correct message.
        """
        message = self.msg_class(body=self.fedmsg_message)
        message.validate()

    def test_missing_fields(self):
        """Assert an exception is actually raised on validation failure."""
        for key in self.required_fields:
            body = copy.deepcopy(self.fedmsg_message)
            del body['msg'][key]
            message = self.msg_class(body=body)
            self.assertRaises(ValidationError, message.validate)

    def test_bad_type(self):
        int_fields = ['status', 'build', 'pid']
        for key in self.required_fields:
            body = copy.deepcopy(self.fedmsg_message)

            if key in int_fields:
                body['msg'][key] = "str"
            else:
                body['msg'][key] = 1

            message = self.msg_class(body=body)
            self.assertRaises(ValidationError, message.validate)

    def test_str(self):
        message = self.msg_class(body=self.fedmsg_message)
        assert message.project_full_name == self.name
        assert message.build_id == self.build_id

    def test_no_wrap(self):
        message = self.msg_class(body=self.fedmsg_message['msg'])
        message.validate()

    def test_nevr(self):
        message = self.msg_class(body=self.fedmsg_message['msg'])
        assert message.package_name == 'python-hypothesis'
        assert message.package_version == '4.23.8'
        assert message.package_release == '1.fc31'
        assert message.package_epoch is None


class BuildChrootEndedV1Test(BuildChrootStartedV1Test):
    msg_class = schema.BuildChrootEndedV1

    def setUp(self):
        self.fedmsg_message = {
            "username": "copr",
            "source_name": "datanommer",
            "certificate": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUVUakNDQTdlZ0F3SUJBZ0lDQVBZd0RRWUpL\nb1pJaHZjTkFRRUZCUUF3Z2FBeEN6QUpCZ05WQkFZVEFsVlQKTVFzd0NRWURWUVFJRXdKT1F6RVFN\nQTRHQTFVRUJ4TUhVbUZzWldsbmFERVhNQlVHQTFVRUNoTU9SbVZrYjNKaApJRkJ5YjJwbFkzUXhE\nekFOQmdOVkJBc1RCbVpsWkcxelp6RVBNQTBHQTFVRUF4TUdabVZrYlhObk1ROHdEUVlEClZRUXBF\nd1ptWldSdGMyY3hKakFrQmdrcWhraUc5dzBCQ1FFV0YyRmtiV2x1UUdabFpHOXlZWEJ5YjJwbFkz\nUXUKYjNKbk1CNFhEVEUwTURReU16RTBNamsxTVZvWERUSTBNRFF5TURFME1qazFNVm93Z2R3eEN6\nQUpCZ05WQkFZVApBbFZUTVFzd0NRWURWUVFJRXdKT1F6RVFNQTRHQTFVRUJ4TUhVbUZzWldsbmFE\nRVhNQlVHQTFVRUNoTU9SbVZrCmIzSmhJRkJ5YjJwbFkzUXhEekFOQmdOVkJBc1RCbVpsWkcxelp6\nRXRNQ3NHQTFVRUF4TWtZMjl3Y2kxamIzQnkKTFdKbExtTnNiM1ZrTG1abFpHOXlZWEJ5YjJwbFkz\nUXViM0puTVMwd0t3WURWUVFwRXlSamIzQnlMV052Y0hJdApZbVV1WTJ4dmRXUXVabVZrYjNKaGNI\nSnZhbVZqZEM1dmNtY3hKakFrQmdrcWhraUc5dzBCQ1FFV0YyRmtiV2x1ClFHWmxaRzl5WVhCeWIy\ncGxZM1F1YjNKbk1JR2ZNQTBHQ1NxR1NJYjNEUUVCQVFVQUE0R05BRENCaVFLQmdRQ2UKREs5VFQy\nM05BdTZPWTVGMnVVNHpMRW9Ld2k1RnRRTU5jVWV5eDdmOHJxMUZXaUxDWHBjWFhpU2tzUE1XV1NM\nWQo5SHNoa1pvM3ZjMHFSRXVBWDNweWRuM2VFRDA0UExrUmRlaWpvSXA5L0Y2YlZ3MmlLMDdXRmc5\nU2MwNlRsKzhSCld1RHNaeTQ1SVJKYXhCRTlJaHBYL0x2Y2JnQ1cvZmVHVGp5WG1iRHd0UUlEQVFB\nQm80SUJWekNDQVZNd0NRWUQKVlIwVEJBSXdBREF0QmdsZ2hrZ0JodmhDQVEwRUlCWWVSV0Z6ZVMx\nU1UwRWdSMlZ1WlhKaGRHVmtJRU5sY25ScApabWxqWVhSbE1CMEdBMVVkRGdRV0JCUm5lNTg0d3Bs\nWGYrZVE2K25zSTZCbm5BNENaRENCMVFZRFZSMGpCSUhOCk1JSEtnQlJyUUZyNUVnaUpXZWRaNVFY\nMUFoMEtUbjhVQUtHQnBxU0JvekNCb0RFTE1Ba0dBMVVFQmhNQ1ZWTXgKQ3pBSkJnTlZCQWdUQWs1\nRE1SQXdEZ1lEVlFRSEV3ZFNZV3hsYVdkb01SY3dGUVlEVlFRS0V3NUdaV1J2Y21FZwpVSEp2YW1W\namRERVBNQTBHQTFVRUN4TUdabVZrYlhObk1ROHdEUVlEVlFRREV3Wm1aV1J0YzJjeER6QU5CZ05W\nCkJDa1RCbVpsWkcxelp6RW1NQ1FHQ1NxR1NJYjNEUUVKQVJZWFlXUnRhVzVBWm1Wa2IzSmhjSEp2\nYW1WamRDNXYKY21lQ0NRRGpVQjVIVHhjZVJUQVRCZ05WSFNVRUREQUtCZ2dyQmdFRkJRY0RBakFM\nQmdOVkhROEVCQU1DQjRBdwpEUVlKS29aSWh2Y05BUUVGQlFBRGdZRUFVazNlbjBYUXpDQm5IUlh4\nZDhyOHp2ZFAwVURvbEpiUysyTEl3Z3NDClJDMnNkZ1UwNGdFblYxdFpVTjNydEk1SzQ2MnpKT0JQ\nOFhQd3h4eUZMN1lOYmVtWTgyTG52Y1pHdzliMGdxTDMKdHNKbzllSFV5SXBZMG93TlVKdzgzU1Ax\neFJvb3NwVGJRK3BsNm9qdjVPNVpGZ1lBUG1yckRWZ0M4a2gzRlp4Rgp0SWc9Ci0tLS0tRU5EIENF\nUlRJRklDQVRFLS0tLS0K\n",
            "i": 3,
            "timestamp": 1561043053.0,
            "msg_id": "2019-f916a75e-6a89-48e2-a4e5-53e71fef92fa",
            "crypto": "x509",
            "topic": "org.fedoraproject.prod.copr.build.end",
            "headers": {},
            "signature": "GWWEIfcVvLh59XWrYmDlJoRpxJ3DKYFBwAojVwWncbvfj3gVwJ33UHP5GJXTCsk+gvEUQdn07/Fs\nw9hGIfuiXlH7EjqOFvaiHIScq0VxLvwsManjbij9Ud8au9rLs9NkyS/pdLKq5QtwgXO9Y9LnsZB5\nyWURshXlLZsbZfq7fsE=\n",
            "source_version": "0.9.0",
            "msg": {
                "status": 0,
                "what": "build end: user:kbaig copr:test build:942697 pkg:tkn version:0.1.2-1.fc30 ip:172.25.91.143 pid:26197 status:0",
                "chroot": "fedora-29-x86_64",
                "ip": "172.25.91.143",
                "user": "kbaig",
                "who": "backend.worker-14783-PC",
                "pid": 26197,
                "copr": "test",
                "version": "0.1.2-1.fc30",
                "build": 942697,
                "owner": "kbaig",
                "pkg": "tkn"
            }
        }
        self.build_id = 942697
        self.name = "kbaig/test"

    def test_nevr(self):
        message = self.msg_class(body=self.fedmsg_message['msg'])
        assert message.package_name == 'tkn'
        assert message.package_version == '0.1.2'
        assert message.package_release == '1.fc30'
        assert message.package_epoch is None


class BuildChrootStartedV1DontUseTest(BuildChrootStartedV1Test):
    msg_class = schema.BuildChrootStartedV1DontUse

    def setUp(self):
        self.fedmsg_message = {
            "username": "copr",
            "source_name": "datanommer",
            "certificate": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUVUakNDQTdlZ0F3SUJBZ0lDQVBZd0RRWUpL\nb1pJaHZjTkFRRUZCUUF3Z2FBeEN6QUpCZ05WQkFZVEFsVlQKTVFzd0NRWURWUVFJRXdKT1F6RVFN\nQTRHQTFVRUJ4TUhVbUZzWldsbmFERVhNQlVHQTFVRUNoTU9SbVZrYjNKaApJRkJ5YjJwbFkzUXhE\nekFOQmdOVkJBc1RCbVpsWkcxelp6RVBNQTBHQTFVRUF4TUdabVZrYlhObk1ROHdEUVlEClZRUXBF\nd1ptWldSdGMyY3hKakFrQmdrcWhraUc5dzBCQ1FFV0YyRmtiV2x1UUdabFpHOXlZWEJ5YjJwbFkz\nUXUKYjNKbk1CNFhEVEUwTURReU16RTBNamsxTVZvWERUSTBNRFF5TURFME1qazFNVm93Z2R3eEN6\nQUpCZ05WQkFZVApBbFZUTVFzd0NRWURWUVFJRXdKT1F6RVFNQTRHQTFVRUJ4TUhVbUZzWldsbmFE\nRVhNQlVHQTFVRUNoTU9SbVZrCmIzSmhJRkJ5YjJwbFkzUXhEekFOQmdOVkJBc1RCbVpsWkcxelp6\nRXRNQ3NHQTFVRUF4TWtZMjl3Y2kxamIzQnkKTFdKbExtTnNiM1ZrTG1abFpHOXlZWEJ5YjJwbFkz\nUXViM0puTVMwd0t3WURWUVFwRXlSamIzQnlMV052Y0hJdApZbVV1WTJ4dmRXUXVabVZrYjNKaGNI\nSnZhbVZqZEM1dmNtY3hKakFrQmdrcWhraUc5dzBCQ1FFV0YyRmtiV2x1ClFHWmxaRzl5WVhCeWIy\ncGxZM1F1YjNKbk1JR2ZNQTBHQ1NxR1NJYjNEUUVCQVFVQUE0R05BRENCaVFLQmdRQ2UKREs5VFQy\nM05BdTZPWTVGMnVVNHpMRW9Ld2k1RnRRTU5jVWV5eDdmOHJxMUZXaUxDWHBjWFhpU2tzUE1XV1NM\nWQo5SHNoa1pvM3ZjMHFSRXVBWDNweWRuM2VFRDA0UExrUmRlaWpvSXA5L0Y2YlZ3MmlLMDdXRmc5\nU2MwNlRsKzhSCld1RHNaeTQ1SVJKYXhCRTlJaHBYL0x2Y2JnQ1cvZmVHVGp5WG1iRHd0UUlEQVFB\nQm80SUJWekNDQVZNd0NRWUQKVlIwVEJBSXdBREF0QmdsZ2hrZ0JodmhDQVEwRUlCWWVSV0Z6ZVMx\nU1UwRWdSMlZ1WlhKaGRHVmtJRU5sY25ScApabWxqWVhSbE1CMEdBMVVkRGdRV0JCUm5lNTg0d3Bs\nWGYrZVE2K25zSTZCbm5BNENaRENCMVFZRFZSMGpCSUhOCk1JSEtnQlJyUUZyNUVnaUpXZWRaNVFY\nMUFoMEtUbjhVQUtHQnBxU0JvekNCb0RFTE1Ba0dBMVVFQmhNQ1ZWTXgKQ3pBSkJnTlZCQWdUQWs1\nRE1SQXdEZ1lEVlFRSEV3ZFNZV3hsYVdkb01SY3dGUVlEVlFRS0V3NUdaV1J2Y21FZwpVSEp2YW1W\namRERVBNQTBHQTFVRUN4TUdabVZrYlhObk1ROHdEUVlEVlFRREV3Wm1aV1J0YzJjeER6QU5CZ05W\nCkJDa1RCbVpsWkcxelp6RW1NQ1FHQ1NxR1NJYjNEUUVKQVJZWFlXUnRhVzVBWm1Wa2IzSmhjSEp2\nYW1WamRDNXYKY21lQ0NRRGpVQjVIVHhjZVJUQVRCZ05WSFNVRUREQUtCZ2dyQmdFRkJRY0RBakFM\nQmdOVkhROEVCQU1DQjRBdwpEUVlKS29aSWh2Y05BUUVGQlFBRGdZRUFVazNlbjBYUXpDQm5IUlh4\nZDhyOHp2ZFAwVURvbEpiUysyTEl3Z3NDClJDMnNkZ1UwNGdFblYxdFpVTjNydEk1SzQ2MnpKT0JQ\nOFhQd3h4eUZMN1lOYmVtWTgyTG52Y1pHdzliMGdxTDMKdHNKbzllSFV5SXBZMG93TlVKdzgzU1Ax\neFJvb3NwVGJRK3BsNm9qdjVPNVpGZ1lBUG1yckRWZ0M4a2gzRlp4Rgp0SWc9Ci0tLS0tRU5EIENF\nUlRJRklDQVRFLS0tLS0K\n",
            "i": 2,
            "timestamp": 1561550552.0,
            "msg_id": "2019-99461b95-66c1-4097-b4ec-ab2e3ba59047",
            "crypto": "x509",
            "topic": "org.fedoraproject.prod.copr.chroot.start",
            "headers": {},
            "signature": "S4N4QRS7IPAfrng3wwQWxQjjnCUcSQtAvbwZu4IPwVQs1uUv+gbSITIDblCVPCudPZ3yWL4ApP/L\nfNJepkUp/+mu0vDpRZQ+ZzOFSSIlemSaO8Ce1k8uymwbFhrU1L+7lMkY1Q+C4JCj/kXmn8Gs7hWF\noyrmQx0vAraBJc+ZIzQ=\n",
            "source_version": "0.9.0",
            "msg": {
                "status": 3,
                "what": "chroot start: chroot:fedora-29-aarch64 user:praiskup copr:ping pkg:dummy-pkg build:945056 ip:38.145.48.104 pid:9272",
                "chroot": "fedora-29-aarch64",
                "ip": "38.145.48.104",
                "user": "praiskup",
                "who": "backend.worker-23731-AARCH64",
                "pid": 9272,
                "copr": "ping",
                "version": "10:20190626_1356-0",
                "build": 945056,
                "owner": "praiskup",
                "pkg": "dummy-pkg"
            }
        }
        self.build_id = 945056
        self.name = "praiskup/ping"

    def test_nevr(self):
        message = self.msg_class(body=self.fedmsg_message['msg'])
        assert message.package_name == "dummy-pkg"
        assert message.package_version == "20190626_1356"
        assert message.package_release == "0"
        assert message.package_epoch == '10'


class BuildChrootStompOldStartTest(unittest.TestCase):
    msg_class = schema.BuildChrootStartedV1Stomp

    required = [
        "build",
        "owner",
        "copr",
        "submitter",
        "package",
        "chroot",
        "builder",
        "status",
        "status_int",
    ]

    int_fields = [
        'build',
        'status_int'
    ]

    def setUp(self):
        self.fedmsg_message = {
            "build": "38492",
            "owner": "praiskup",
            "copr": "ping",
            "submitter": "None",
            "package": "None-None",
            "chroot":
            "srpm-builds",
            "builder": "10.8.29.188",
            "status": "SUCCEEDED",
            "status_int": "1"
        }
        self.build_id = 38492
        self.name = "praiskup/ping"

    def test_correct_messages(self):
        """
        Assert the message schema validates a correct message.
        """
        message = self.msg_class(body=self.fedmsg_message)
        message.validate()

    def test_package(self):
        message = self.msg_class(body=self.fedmsg_message)
        message.validate()
        assert message.status == "succeeded"

    def test_nevr(self):
        message = self.msg_class(body=self.fedmsg_message)
        assert message.package_name == None
        assert message.package_version == None
        assert message.package_release == None
        assert message.package_epoch is None


class BuildChrootStompOldEndTest(BuildChrootStompOldStartTest):
    msg_class = schema.BuildChrootEndedV1Stomp

    def setUp(self):
        self.fedmsg_message = {
            "build": "38492",
            "owner": "praiskup",
            "copr": "ping",
            "submitter": "praiskup",
            "package": "dummy-pkg-1:20190701_2127-0",
            "chroot": "fedora-rawhide-x86_64",
            "builder": "10.0.150.161",
            "status": "SUCCEEDED",
            "status_int": "1"
        }
        self.build_id = 38492
        self.name = "praiskup/ping"

    def test_nevr(self):
        message = self.msg_class(body=self.fedmsg_message)
        assert message.package_name == 'dummy-pkg'
        assert message.package_version == '20190701_2127'
        assert message.package_release == '0'
        assert message.package_epoch == '1'


class BuildChrootStartedV1StompDontUseTest(unittest.TestCase):
    msg_class = schema.BuildChrootStartedV1StompDontUse

    def setUp(self):
        self.fedmsg_message = {
            "chroot": "fedora-29-x86_64"
        }

    def test_chroot(self):
        msg = self.msg_class(body=self.fedmsg_message)
        msg.validate()
