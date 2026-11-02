"""Os testes de integração sobem o server.py de verdade (helpers.AppServer) e, quando precisam, o Home Assistant simulado."""
import base64
import os
import sys
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)
import helpers  # noqa: E402
from helpers import AppServer, FakeHA, FakeSite  # noqa: E402,F401


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


class ServerCase(unittest.TestCase):
    """Um servidor para a classe toda (mais rápido); quem muda muito usa self.fresh()."""
    server_kw: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.app = AppServer(**cls.server_kw)

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def fresh(self, **kw) -> AppServer:
        app = AppServer(**kw)
        self.addCleanup(app.stop)
        return app

    def upload_photo(self, app=None, data: bytes | None = None) -> str:
        app = app or self.app
        jpg = data or helpers.jpeg()
        return app.ok("POST", "api/photos", {"full": b64(jpg), "thumb": b64(jpg)})["file"]
