"""Carrega o server.py uma vez, com pastas temporárias, para os testes unitários.

Cada teste (UnitBase) começa da casa de teste fictícia, sem configurações, sem uso de IA e sem Home Assistant;
quem precisa do Home Assistant usa self.fake_ha(), que liga o Home Assistant simulado só durante o teste.
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)
import helpers  # noqa: E402

TMP = tempfile.mkdtemp(prefix="inventaria-unit-")
for k in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN", "INV_AI_MOCK", "INV_HA_API", "INV_HA_WS", "INV_MOCK_SEARCH", "INV_WEB_ALLOW_LOCAL", "INV_ALLOW"):
    os.environ.pop(k, None)
os.environ.update({
    "INV_DATA": os.path.join(TMP, "data"), "INV_SHARE": os.path.join(TMP, "share"), "INV_MEDIA": os.path.join(TMP, "media"),
    "INV_SEED": helpers.FIXTURE, "INV_WEB": helpers.WEB, "INV_DEV": "1",
})
if helpers.APP not in sys.path:
    sys.path.insert(0, helpers.APP)
import server  # noqa: E402

logging.getLogger("inventario").setLevel(logging.CRITICAL)


def reset_store():
    """Pasta de dados nova, com a casa de teste, e tudo o que fica na memória do servidor zerado."""
    for d in (server.DATA_DIR, server.SHARE_DIR, server.MEDIA_ROOT):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(server.SHARE_DIR, exist_ok=True)
    os.makedirs(server.MEDIA_ROOT, exist_ok=True)
    server.STORE = server.Store()
    server.STORE.load()
    server._voice_cache.update(at=0.0, value=None)
    server._voice_cache.pop("engines", None)
    server._voice_cache.pop("missing", None)
    server.WEB_JOBS.clear()
    server._usage_sensor.update(day=None, checked=0.0)
    server.CONEXAO = server.Conexao()


class UnitBase(unittest.TestCase):
    """Um teste unitário do servidor: a casa de teste carregada, sem Home Assistant e sem IA simulada."""

    def setUp(self):
        reset_store()
        self.S = server
        self.store = server.STORE
        self._patches = [mock.patch.object(server, "SUPERVISOR_TOKEN", None), mock.patch.object(server, "AI_MOCK", False)]
        for p in self._patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patches])

    def fake_ha(self) -> helpers.FakeHA:
        """Liga o Home Assistant simulado só neste teste."""
        ha = helpers.FakeHA(media_root=server.MEDIA_ROOT)
        for p in (mock.patch.object(server, "SUPERVISOR_TOKEN", ha.token), mock.patch.object(server, "HA_API", ha.api), mock.patch.object(server, "HA_WS", ha.ws)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(ha.stop)
        return ha

    def item(self, iid):
        return self.store.item(iid)

    def items_in(self, rid):
        return [i for i in self.store.data["items"] if i["room"] == rid]

    def assertApiError(self, status, fn, *a, msg_part=None, **k):
        with self.assertRaises(server.ApiError) as cm:
            fn(*a, **k)
        self.assertEqual(cm.exception.status, status, cm.exception.msg)
        if msg_part:
            self.assertIn(msg_part, cm.exception.msg)
        return cm.exception
