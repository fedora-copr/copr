from unittest import TestCase

from copr_common import rpm as rpm_module

from . import mock


class TestGetRpmHeader(TestCase):
    def _fake_rpm_module(self, header):
        fake_ts = mock.MagicMock()
        fake_ts.hdrFromFdno.return_value = header
        fake_rpm = mock.MagicMock()
        fake_rpm.TransactionSet.return_value = fake_ts
        fake_rpm._RPMVSF_NOSIGNATURES = 0  # pylint: disable=protected-access
        return fake_rpm

    def test_get_rpm_header(self):
        header = {"name": "foo", "epoch": None, "version": "1.0",
                  "release": "1", "arch": "x86_64"}
        fake_rpm = self._fake_rpm_module(header)

        with mock.patch("builtins.open", mock.mock_open(read_data=b"")):
            with mock.patch.object(rpm_module, "rpm", fake_rpm):
                result = rpm_module.get_rpm_header("/tmp/foo-1.0-1.x86_64.rpm")

        self.assertEqual(result, header)
        fake_rpm.TransactionSet.return_value.setVSFlags.assert_called_once()

    def test_get_rpm_nevra_dict(self):
        header = {"name": "foo", "epoch": None, "version": "1.0",
                  "release": "1", "arch": "x86_64"}
        fake_rpm = self._fake_rpm_module(header)

        with mock.patch("builtins.open", mock.mock_open(read_data=b"")):
            with mock.patch.object(rpm_module, "rpm", fake_rpm):
                nevra = rpm_module.get_rpm_nevra_dict("/tmp/foo-1.0-1.x86_64.rpm")

        self.assertEqual(nevra, {
            "name": "foo", "epoch": None, "version": "1.0",
            "release": "1", "arch": "x86_64",
        })

    def test_get_rpm_nevra_dict_src_rpm_arch(self):
        header = {"name": "foo", "epoch": None, "version": "1.0",
                  "release": "1", "arch": "x86_64"}
        fake_rpm = self._fake_rpm_module(header)

        with mock.patch("builtins.open", mock.mock_open(read_data=b"")):
            with mock.patch.object(rpm_module, "rpm", fake_rpm):
                nevra = rpm_module.get_rpm_nevra_dict("/tmp/foo-1.0-1.src.rpm")

        self.assertEqual(nevra["arch"], "src")

    def test_get_rpm_nevra_dict_rejects_non_rpm(self):
        with self.assertRaises(ValueError):
            rpm_module.get_rpm_nevra_dict("/tmp/foo.txt")

    def test_get_rpm_nevra_dict_rejects_none_header(self):
        fake_rpm = self._fake_rpm_module(None)

        with mock.patch("builtins.open", mock.mock_open(read_data=b"")):
            with mock.patch.object(rpm_module, "rpm", fake_rpm):
                with self.assertRaises(ValueError):
                    rpm_module.get_rpm_nevra_dict("/tmp/foo-1.0-1.x86_64.rpm")
