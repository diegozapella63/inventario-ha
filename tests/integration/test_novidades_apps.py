"""Novidades › Apps do celular pelo HTTP (1.56.0): a opção (desligada de início), os apps lidos do histórico do Home
Assistant de mentira (o sensor Último app usado do celular da Ana), conferir um app, Deixar de fora e Acompanhar."""
import time
import unittest
from datetime import datetime, timedelta

from _boot import AppServer, FakeHA

SENSOR = "sensor.celular_da_ana_last_used_app"
CASA, MUSICA = "com.exemplo.casaconectada", "com.exemplo.musicaja"
DESLIGADOS = "Os apps do celular estão desligados. Para usar, ligue em Mais > Configurações > Opções."


def quando(**delta) -> str:
    return (datetime.now().astimezone() - timedelta(**delta)).isoformat(timespec="seconds")


class Apps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ha = FakeHA()
        cls.ha.registry = [{"entity_id": "device_tracker.pixel_ana", "device_id": "d-ana", "platform": "mobile_app", "unique_id": "abc_location"},
                           {"entity_id": SENSOR, "device_id": "d-ana", "platform": "mobile_app", "unique_id": "abc_last_used_app"}]
        cls.ha.states.append({"entity_id": SENSOR, "state": MUSICA, "attributes": {"Label": "Música Já"}})
        cls.ha.history[SENSOR] = [
            {"entity_id": SENSOR, "state": CASA, "last_changed": quando(days=2), "attributes": {"Label": "Casa Conectada"}},
            {"entity_id": SENSOR, "state": MUSICA, "last_changed": quando(hours=5), "attributes": {"Label": "Música Já"}}]
        cls.app = AppServer(mock_ai=True, ha=cls.ha)

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()
        cls.ha.stop()

    def erro(self, method, path, body, status, msg):
        st, _, out = self.app.request(method, path, body)
        self.assertEqual((st, out.get("error") if isinstance(out, dict) else out), (status, msg), (method, path, body))

    def ligar(self):
        self.app.ok("PUT", "api/settings", {"news_apps": True})
        self.addCleanup(self.app.ok, "PUT", "api/settings", {"news_apps": False})

    def test_1_opcao_desligada_de_inicio(self):
        self.assertIs(self.app.data()["settings"]["news_apps"], False)
        self.assertIsNone(self.app.ok("GET", "api/news")["apps"])
        self.erro("POST", "api/news/app", {"pacote": CASA}, 409, DESLIGADOS)
        self.erro("PUT", "api/news/app", {"pacote": CASA, "acompanhar": True}, 409, DESLIGADOS)
        for v in ("sim", 1, None):
            with self.subTest(v=v):
                self.erro("PUT", "api/settings", {"news_apps": v}, 400, "Use verdadeiro ou falso nesta opção.")

    def test_2_ligada_le_os_apps_do_celular(self):
        self.ligar()
        self.assertIs(self.app.data()["settings"]["news_apps"], True)
        apps = self.app.ok("GET", "api/news")["apps"]
        self.assertEqual(apps["sensores"], 1)
        got = {a["pacote"]: (a["nome"], a["pessoas"], a["conferir"], a["res"]) for a in apps["lista"]}
        self.assertEqual(got, {CASA: ("Casa Conectada", ["Ana"], None, None), MUSICA: ("Música Já", ["Ana"], None, None)},
                         "de quem é o celular; a IA ainda não escolheu")

    def test_3_conferir_um_app_e_deixar_de_fora(self):
        self.ligar()
        self.app.ok("GET", "api/news")
        jid = self.app.ok("POST", "api/news/app", {"pacote": CASA})["id"]
        t0 = time.time()
        while (st := self.app.ok("GET", f"api/news/{jid}"))["stage"] == "busy" and time.time() - t0 < 10:
            time.sleep(0.1)
        self.assertEqual(st["stage"], "done", st)
        self.assertTrue(st["news"]["novidades"])
        casa = next(a for a in self.app.ok("GET", "api/news")["apps"]["lista"] if a["pacote"] == CASA)
        self.assertTrue(casa["res"]["news"]["novidades"], "fica guardado")
        ov = self.app.ok("PUT", "api/news/app", {"pacote": CASA, "acompanhar": False})
        casa = next(a for a in ov["apps"]["lista"] if a["pacote"] == CASA)
        self.assertEqual((casa["conferir"], casa["manual"], casa["res"]), (False, True, None))
        ov = self.app.ok("PUT", "api/news/app", {"pacote": CASA, "acompanhar": True})
        self.assertIs(next(a for a in ov["apps"]["lista"] if a["pacote"] == CASA)["conferir"], True)
        self.erro("POST", "api/news/app", {"pacote": "com.nao.existe"}, 404, "App não encontrado.")
        self.erro("PUT", "api/news/app", {"pacote": CASA}, 400, "Diga se é para acompanhar o app.")

    def conferir(self, pacote):
        jid = self.app.ok("POST", "api/news/app", {"pacote": pacote})["id"]
        t0 = time.time()
        while (st := self.app.ok("GET", f"api/news/{jid}"))["stage"] == "busy" and time.time() - t0 < 10:
            time.sleep(0.1)
        self.assertEqual(st["stage"], "done", st)

    def test_4_limpar_novidades_limpa_as_dos_apps(self):
        """1.64.0: Limpar novidades apaga também as dos apps (o Acompanhar e o Deixar de fora da pessoa ficam)."""
        self.ligar()
        self.app.ok("GET", "api/news")
        self.conferir(CASA)
        ov = self.app.ok("DELETE", "api/news")
        self.assertEqual({a["pacote"]: a["res"] for a in ov["apps"]["lista"]}, {CASA: None, MUSICA: None}, "na resposta")
        self.assertEqual({a["pacote"]: a["res"] for a in self.app.ok("GET", "api/news")["apps"]["lista"]}, {CASA: None, MUSICA: None}, "e ao abrir de novo")


if __name__ == "__main__":
    unittest.main()
