"""Ajustes das novidades pelo HTTP: ligar e desligar (as rotas recusam), de quanto em quanto tempo conferir sozinho, onde
avisar, os celulares do Home Assistant, Testar o aviso e a conferência sozinha que avisa o celular quando acha novidade."""
import json
import os
import tempfile
import time
import unittest

from _boot import AppServer, FakeHA

DESLIGADAS = "As novidades estão desligadas. Para usar, ligue em Mais > Configurações > Opções."
PHONE = "mobile_app_celular_da_ana"


class Ajustes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ha = FakeHA()
        cls.app = AppServer(mock_ai=True, ha=cls.ha)

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()
        cls.ha.stop()

    def tearDown(self):
        self.app.ok("PUT", "api/settings", {"news": True, "news_every": 0, "news_notify": ""})

    def erro(self, method, path, body, status, msg):
        st, _, out = self.app.request(method, path, body)
        self.assertEqual((st, out.get("error") if isinstance(out, dict) else out), (status, msg), (method, path, body))

    def test_de_inicio(self):
        s = self.app.data()["settings"]
        self.assertEqual((s["news"], s["news_every"], s["news_notify"]), (True, 0, ""), "ligadas, sem conferir sozinho e sem aviso")

    def test_desligadas_as_rotas_recusam(self):
        self.app.ok("PUT", "api/settings", {"news": False})
        self.assertIs(self.app.data()["settings"]["news"], False)
        self.erro("GET", "api/news", None, 409, DESLIGADAS)
        self.erro("POST", "api/news", {"item": "sal-007"}, 409, DESLIGADAS)
        self.erro("POST", "api/news/all", {}, 409, DESLIGADAS)
        self.app.ok("PUT", "api/settings", {"news": True})
        self.assertIn("itens", self.app.ok("GET", "api/news"), "ligadas de novo: voltam")

    def test_intervalo(self):
        for v in (7, 15, 30, 0):
            self.assertEqual(self.app.ok("PUT", "api/settings", {"news_every": v})["news_every"], v)
        for v in (3, "7", True, None, 365):
            with self.subTest(v=v):
                self.erro("PUT", "api/settings", {"news_every": v}, 400, "Escolha de quanto em quanto tempo conferir.")
        self.assertEqual(self.app.data()["settings"]["news_every"], 0, "o pedido ruim não muda nada")

    def test_onde_avisar(self):
        for v in ("persistent", PHONE, ""):
            self.assertEqual(self.app.ok("PUT", "api/settings", {"news_notify": v})["news_notify"], v)
        for v in ("notify.mobile_app_x", "mobile_app_A", "light.sala", "mobile_app_../x"):
            with self.subTest(v=v):
                self.erro("PUT", "api/settings", {"news_notify": v}, 400, "Escolha onde avisar.")
        self.erro("PUT", "api/settings", {"news": "sim"}, 400, "Use verdadeiro ou falso nesta opção.")

    def test_celulares(self):
        self.assertEqual(self.app.ok("GET", "api/news/targets")["targets"],
                         [{"id": PHONE, "name": "Celular da Ana"}, {"id": "mobile_app_tablet_da_sala", "name": "Tablet da Sala"}])

    def test_testar_o_aviso(self):
        n = len(self.ha.calls("POST", "/core/api/services/notify/"))
        self.assertEqual(self.app.ok("POST", "api/news/notify-test", {"target": PHONE}), {"ok": True})
        c = self.ha.calls("POST", "/core/api/services/notify/")
        self.assertEqual(len(c), n + 1)
        self.assertEqual(c[-1]["path"], f"/core/api/services/notify/{PHONE}")
        self.assertEqual((c[-1]["body"]["title"], c[-1]["body"]["message"]), ("InventarIA (teste)", "Novidades em 2 itens. Toque para abrir."))
        self.app.ok("POST", "api/news/notify-test", {"target": "persistent"})
        self.assertEqual(len(self.ha.calls("POST", "/core/api/services/persistent_notification/create")), 1)

    def test_testar_sem_destino_recusa(self):
        self.erro("POST", "api/news/notify-test", {}, 400, "Escolha onde avisar.")
        self.erro("POST", "api/news/notify-test", {"target": "light.sala"}, 400, "Escolha onde avisar.")

    def test_testar_com_o_escolhido(self):
        self.app.ok("PUT", "api/settings", {"news_notify": PHONE})
        n = len(self.ha.calls("POST", f"/core/api/services/notify/{PHONE}"))
        self.app.ok("POST", "api/news/notify-test", {})
        self.assertEqual(len(self.ha.calls("POST", f"/core/api/services/notify/{PHONE}")), n + 1)

    def test_home_assistant_recusa(self):
        self.ha.notify_status = 500
        try:
            st, _, out = self.app.request("POST", "api/news/notify-test", {"target": PHONE})
            self.assertEqual(st, 502)
            self.assertIn("O Home Assistant recusou o pedido", out["error"])
        finally:
            self.ha.notify_status = 200


class Sozinho(unittest.TestCase):
    """INV_NEWS_TICK=1: o servidor olha a cada segundo se está na hora de conferir sozinho."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.mock = os.path.join(cls.tmp.name, "novidades.json")
        with open(cls.mock, "w", encoding="utf-8") as f:
            json.dump({"produto": "Aparelho", "novidades": [{"tipo": "atualizacao", "titulo": "Atualização 3.0", "data": "2026-10-20",
                                                             "fonte": "https://fab.exemplo/notas"}]}, f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def subir(self, **settings):
        ha = FakeHA()
        self.addCleanup(ha.stop)
        app = AppServer(mock_ai=True, ha=ha, env={"INV_NEWS_TICK": "1", "INV_MOCK_NEWS": self.mock})
        self.addCleanup(app.stop)
        app.ok("PUT", "api/settings", settings)
        return app, ha

    def esperar(self, cond, timeout=40):
        fim = time.time() + timeout
        while time.time() < fim:
            if cond():
                return True
            time.sleep(0.3)
        return False

    def test_confere_e_avisa_uma_vez(self):
        app, ha = self.subir(news_every=7, news_notify=PHONE)
        self.assertTrue(self.esperar(lambda: ha.calls("POST", "/core/api/services/notify/")), "conferiu sozinho e avisou")
        c = ha.calls("POST", "/core/api/services/notify/")
        ultima = app.ok("GET", "api/news")["ultima"]
        self.assertGreater(ultima["novos"], 0)
        self.assertEqual(c[0]["path"], f"/core/api/services/notify/{PHONE}")
        n = ultima["novos"]
        self.assertEqual(c[0]["body"]["message"], f"Novidades em {n} {'item' if n == 1 else 'itens'}. Toque para abrir.")
        self.assertEqual(c[0]["body"]["title"], "InventarIA")
        time.sleep(3)
        self.assertEqual(len(ha.calls("POST", "/core/api/services/notify/")), 1, "na mesma semana, não confere de novo")

    def test_sem_aviso_confere_calado(self):
        app, ha = self.subir(news_every=7)
        self.assertTrue(self.esperar(lambda: (app.ok("GET", "api/news")["ultima"] or {}).get("conferidos")), "conferiu sozinho")
        self.assertEqual(ha.calls("POST", "/core/api/services/notify/"), [], "sem aviso escolhido, não avisa")

    def test_sem_intervalo_nao_confere(self):
        app, ha = self.subir(news_notify=PHONE)
        time.sleep(3)
        self.assertIsNone(app.ok("GET", "api/news")["ultima"], "Conferir sozinho: Não")
        self.assertEqual(app.ok("GET", "api/ai/usage")["today"]["calls"], 0, "e não chama a IA")


if __name__ == "__main__":
    unittest.main()
