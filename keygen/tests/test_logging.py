from unittest import TestCase
from copr_keygen import app


class TestRemoteAddrFilter(TestCase):
    def test_server(self):
        with self.assertLogs(app.logger) as cm:
            app.logger.info("foo")
            assert cm.records[0].remote_addr == "SERVER"

    def test_backend(self):
        with self.assertLogs(app.logger, level="DEBUG") as cm:
            app.test_client().get("/ping")
            assert cm.records[0].remote_addr == "127.0.0.1"
