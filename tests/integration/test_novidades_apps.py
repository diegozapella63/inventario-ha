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

    def test_6_abrir_um_app_deixa_de_ser_nova(self):
        self.ligar()
        self.app.ok("GET", "api/news")
        self.conferir(MUSICA)
        res = lambda: next(a for a in self.app.ok("GET", "api/news")["apps"]["lista"] if a["pacote"] == MUSICA)["res"]  # noqa: E731
        self.assertTrue(any(n.get("nova") for n in res()["news"]["novidades"]))
        self.assertGreater(self.app.ok("POST", "api/news/visto", {"pacote": MUSICA})["vistas"], 0)
        self.assertFalse(any(n.get("nova") for n in res()["news"]["novidades"]))

    def test_7_apagar_um_app(self):
        """1.68.0: sai de Apps detectados com o que foi achado."""
        self.ligar()
        self.app.ok("GET", "api/news")
        self.conferir(MUSICA)
        ov = self.app.ok("DELETE", f"api/news/app?pacote={MUSICA}")
        self.assertNotIn(MUSICA, [a["pacote"] for a in ov["apps"]["lista"]])
        self.erro("DELETE", f"api/news/app?pacote={MUSICA}", None, 404, "App não encontrado.")

    def test_8_apagar_as_novidades_de_um_app(self):
        """1.70.0: DELETE api/news?pacote= apaga as novidades achadas do app (como as de um equipamento); elas não voltam ao
        buscar de novo, e Limpar só apps começa do zero."""
        self.ligar()
        self.app.ok("GET", "api/news")
        self.conferir(CASA)
        n = len(next(a for a in self.app.ok("GET", "api/news")["apps"]["lista"] if a["pacote"] == CASA)["res"]["news"]["novidades"])
        self.assertGreater(n, 0)
        r = self.app.ok("DELETE", f"api/news?pacote={CASA}")
        self.assertEqual((r["news"]["novidades"], r["news"]["apagadas"]), ([], n))
        casa = lambda: next(a for a in self.app.ok("GET", "api/news")["apps"]["lista"] if a["pacote"] == CASA)  # noqa: E731
        self.assertEqual(casa()["res"]["news"]["novidades"], [], "a lista também")
        self.conferir(CASA)
        self.assertEqual((casa()["res"]["news"]["novidades"], casa()["res"]["news"]["apagadas"]), ([], n), "buscar de novo: não voltam")
        self.erro("DELETE", f"api/news?pacote={MUSICA}", None, 404, "Este app não tem novidades.")
        self.app.ok("DELETE", "api/news?so=apps")
        self.conferir(CASA)
        self.assertEqual(len(casa()["res"]["news"]["novidades"]), n, "Limpar só apps começa do zero: voltam")

    def test_5_renomear_um_app(self):
        """1.66.0: o nome que a pessoa dá vale na lista e na busca; vazio volta ao de antes; fica depois de Limpar."""
        self.ligar()
        self.app.ok("GET", "api/news")
        ov = self.app.ok("PUT", "api/news/app/nome", {"pacote": CASA, "nome": "  Casa   Esperta "})
        casa = next(a for a in ov["apps"]["lista"] if a["pacote"] == CASA)
        self.assertEqual((casa["nome"], casa["renomeado"]), ("Casa Esperta", True))
        self.app.ok("DELETE", "api/news")
        self.assertEqual(next(a for a in self.app.ok("GET", "api/news")["apps"]["lista"] if a["pacote"] == CASA)["nome"], "Casa Esperta", "fica depois de Limpar")
        ov = self.app.ok("PUT", "api/news/app/nome", {"pacote": CASA, "nome": ""})
        casa = next(a for a in ov["apps"]["lista"] if a["pacote"] == CASA)
        self.assertEqual((casa["nome"], "renomeado" in casa), ("Casa Conectada", False), "vazio: o nome de antes")
        self.erro("PUT", "api/news/app/nome", {"pacote": "com.nao.existe", "nome": "X"}, 404, "App não encontrado.")
        self.erro("PUT", "api/news/app/nome", {"pacote": CASA, "nome": "x" * 61}, 400, "Use um nome de até 60 letras.")

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
