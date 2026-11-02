"""Com o Home Assistant simulado de verdade (sem o modo simulado do app): IA, Falar, sensor de uso e busca de fotos na internet."""
import json
import os
import time
import unittest

from _boot import AppServer, FakeHA, FakeSite, helpers

PCM = b"\x01\x00" * 16000


class ComHomeAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ha = FakeHA()
        cls.site = FakeSite()
        cls.app = AppServer(ha=cls.ha, env={"INV_WEB_ALLOW_LOCAL": "1"})
        cls.ha.media_root = cls.app.path("media")

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()
        cls.ha.stop()
        cls.site.stop()

    def setUp(self):
        self.ha.ai_error = None
        self.ha.stt_status, self.ha.stt_result = 200, "success"
        self.app.ok("PUT", "api/settings", {"ai": True, "ai_entity": "", "ai_search": "", "voice_stt": "", "ha_sensors": False})

    def wait_job(self, jid, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            st, _, out = self.app.get(f"api/web-photos/{jid}")
            if st != 200 or out["stage"] != "busy":
                return st, out
            time.sleep(0.2)
        self.fail("a busca não terminou")

    # -- IA
    def test_estado_da_ia(self):
        d = self.app.data()
        self.assertTrue(d["features"]["ai"])
        st = self.app.ok("GET", "api/ai/status")
        self.assertEqual((st["ready"], [e["id"] for e in st["entities"]]), (True, ["ai_task.google_ai_task", "ai_task.texto_apenas"]))

    def test_preencher_com_ia(self):
        self.ha.ai_reply = lambda kind, p: json.dumps({"items": [{"name": "Luminária articulada", "cat": "decoracao", "value": "120", "confidence": "alta"}]}) if kind == "foto" else "{}"
        out = self.app.ok("POST", "api/ai/identify", {"file": "sala-1.jpg", "mode": "single", "room": "sala"})
        self.assertEqual((out["items"][0]["name"], out["items"][0]["value"]), ("Luminária articulada", 120))
        call = self.ha.calls("POST", "/core/api/services/ai_task")[-1]
        self.assertEqual(call["attachments_present"], [True])
        self.assertEqual(os.listdir(self.app.path("media", "inventario", "ia-temp")), [])

    def test_catalogar_com_ia_escolhida(self):
        self.app.ok("PUT", "api/settings", {"ai_entity": "ai_task.google_ai_task"})
        self.ha.ai_reply = lambda kind, p: {"items": [{"name": f"Objeto {i}"} for i in range(3)]}
        out = self.app.ok("POST", "api/ai/identify", {"file": "sala-1.jpg", "mode": "multi", "room": "sala", "hint": "estante"})
        self.assertEqual(len(out["items"]), 3)
        self.assertEqual(out["entity"], "ai_task.google_ai_task")
        self.assertEqual(self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["entity_id"], "ai_task.google_ai_task")

    def test_ia_com_erro_e_cota(self):
        self.ha.ai_error = (500, "429 You exceeded your current quota")
        st, _, out = self.app.post("api/ai/identify", {"file": "sala-1.jpg"})
        self.assertEqual(st, 502)
        self.ha.ai_error = None
        self.ha.ai_reply = lambda k, p: "Desculpe, não consegui ver a foto."
        st, _, out = self.app.post("api/ai/identify", {"file": "sala-1.jpg"})
        self.assertEqual(st, 502)
        self.assertIn("Desculpe", out["raw"], "a resposta da IA vai para a tela")
        uso = self.app.ok("GET", "api/ai/usage")
        self.assertEqual([r["result"] for r in uso["recent"][:2]], ["formato", "cota"])

    def test_ia_desligada_recusa(self):
        self.app.ok("PUT", "api/settings", {"ai": False})
        for path, body in (("api/ai/identify", {"file": "sala-1.jpg"}), ("api/ai/text", {"text": "sofá"}), ("api/web-photos", {"name": "x"})):
            with self.subTest(path=path):
                st, _, out = self.app.post(path, body)
                self.assertEqual(st, 409)
                self.assertIn("desligada", out["error"])

    # -- Falar
    def test_falar_de_ponta_a_ponta(self):
        st = self.app.ok("GET", "api/voice/status?fresh=1")
        self.assertEqual((st["ready"], st["name"], st["assistant"]), (True, "Home Assistant Cloud", "Gemini"))
        out = self.app.ok("POST", "api/voice", raw=PCM, headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(out["text"], self.ha.stt_text)
        stt = self.ha.calls("POST", "/core/api/stt/")[-1]
        self.assertIn("X-Speech-Content", stt["headers"])
        self.assertEqual(stt["body"]["bytes"], len(PCM))
        self.ha.ai_reply = lambda kind, p: json.dumps({"room": "sala", "items": [{"name": "Sofá cinza", "value": 2000, "cat": "moveis"},
                                                                                {"name": "Televisão 50 polegadas", "value": 1500, "cat": "eletronicos"}]}) if kind == "fala" else "{}"
        out = self.app.ok("POST", "api/ai/text", {"text": out["text"]})
        self.assertEqual((out["room"], [i["value"] for i in out["items"]]), ("sala", [2000, 1500]))
        self.assertIn(self.ha.stt_text, self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"])

    def test_falar_escolhendo_a_fala_para_texto(self):
        self.app.ok("PUT", "api/settings", {"voice_stt": "stt.faster_whisper"})
        st = self.app.ok("GET", "api/voice/status")
        self.assertEqual((st["engine"], st["language"], st["selected"]), ("stt.faster_whisper", "pt", "stt.faster_whisper"))
        self.app.ok("POST", "api/voice", raw=PCM, headers={"Content-Type": "application/octet-stream"})
        self.assertTrue(self.ha.calls("POST", "/core/api/stt/")[-1]["path"].endswith("stt.faster_whisper"))
        self.assertIn("language=pt", self.ha.calls("POST", "/core/api/stt/")[-1]["body"]["speech"])

    def test_falar_erros(self):
        st, _, out = self.app.post("api/voice", raw=b"\0" * 10, headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(st, 422)
        self.ha.stt_result = "error"
        st, _, out = self.app.post("api/voice", raw=PCM, headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(st, 422)
        self.assertIn("Não entendi", out["error"])

    # -- sensor
    def test_sensor_liga_e_desliga(self):
        self.app.ok("PUT", "api/settings", {"ha_sensors": True})
        for _ in range(30):
            if self.ha.state("sensor.inventaria_ia_hoje"):
                break
            time.sleep(0.1)
        st = self.ha.state("sensor.inventaria_ia_hoje")
        self.assertIsNotNone(st, "ligar cria o sensor na hora")
        self.assertEqual(st["attributes"]["friendly_name"], "InventarIA: chamadas de IA hoje")
        self.app.ok("PUT", "api/settings", {"ha_sensors": False})
        for _ in range(30):
            if not self.ha.state("sensor.inventaria_ia_hoje"):
                break
            time.sleep(0.1)
        self.assertIsNone(self.ha.state("sensor.inventaria_ia_hoje"), "desligar tira o sensor na hora")

    # -- busca na internet
    def test_busca_com_fotos_e_dados_do_produto(self):
        self.ha.ai_reply = lambda kind, p: json.dumps(helpers.search_answer(self.site)) if kind == "busca" else "{}"
        st, _, out = self.app.post("api/web-photos", {"name": "Cafeteira", "details": "inox", "qty": "1"})
        self.assertEqual(st, 202)
        jid = out["id"]
        st, res = self.wait_job(jid)
        self.assertEqual(res["stage"], "done", res["msg"])
        self.assertEqual(len(res["results"]), 5)
        self.assertEqual(res["product"], {"name": "Cafeteira Espresso Exemplo CX-20", "details": "Cafeteira espresso de 15 bar, inox, reservatório de 1,2 L.",
                                          "cat": "cozinha", "value": 450})
        sites = {r["site"] for r in res["results"]}
        self.assertEqual(sites, {"127.0.0.1"})
        st, h, img = self.app.get(f"api/web-photos/{jid}/0")
        self.assertEqual(st, 200)
        self.assertTrue(h["Content-Type"].startswith("image/"))
        self.assertEqual(self.app.get(f"api/web-photos/{jid}/9")[0], 404)
        self.app.ok("DELETE", f"api/web-photos/{jid}")
        self.assertEqual(self.app.get(f"api/web-photos/{jid}")[0], 404, "cancelada, some")
        self.assertEqual([n for n in os.listdir(self.app.path("data", "tmp")) if n.startswith(f"web-{jid}")], [])

    def test_busca_sem_busca_na_web(self):
        self.ha.ai_reply = lambda kind, p: '{"erro": "sem_busca"}'
        jid = self.app.ok("POST", "api/web-photos", {"name": "Cafeteira"})["id"]
        st, res = self.wait_job(jid)
        self.assertEqual(res["stage"], "error")
        self.assertIn("busca na web", res["msg"])
        self.assertIsNone(res.get("product"))

    def test_desligar_a_ia_no_meio_da_busca(self):
        self.ha.ai_reply = lambda kind, p: json.dumps(helpers.search_answer(self.site))
        jid = self.app.ok("POST", "api/web-photos", {"name": "Cafeteira"})["id"]
        self.wait_job(jid)
        self.app.ok("PUT", "api/settings", {"ai": False})
        self.assertEqual(self.app.get(f"api/web-photos/{jid}")[0], 409)
        self.assertEqual(self.app.get(f"api/web-photos/{jid}/0")[0], 409)
        self.assertEqual(self.app.delete(f"api/web-photos/{jid}")[0], 200, "cancelar continua funcionando")

    def test_uso_da_ia_por_tipo(self):
        uso = self.app.ok("GET", "api/ai/usage")
        self.assertGreaterEqual(uso["today"]["calls"], 1)
        self.assertEqual(set(uso["today"]["kinds"]) - {"foto", "catalogo", "busca", "fala"}, set())
        self.assertEqual(len(uso["days"]), 7)


class SemHomeAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = AppServer()

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def test_sem_acesso(self):
        self.assertEqual(self.app.ok("GET", "api/ai/status")["reason"], "no_api")
        st = self.app.ok("GET", "api/voice/status")
        self.assertFalse(st["ready"])
        self.assertEqual(self.app.post("api/voice", raw=PCM, headers={"Content-Type": "application/octet-stream"})[0], 409)
        self.assertEqual(self.app.post("api/web-photos", {"name": "x"})[0], 503)


class Simulado(unittest.TestCase):
    """O modo simulado (INV_AI_MOCK) que a prévia e os testes visuais usam."""

    @classmethod
    def setUpClass(cls):
        cls.app = AppServer(mock_ai=True)

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def test_tudo_responde_sem_home_assistant(self):
        self.assertTrue(self.app.ok("GET", "api/ai/status")["ready"])
        self.assertEqual(len(self.app.ok("POST", "api/ai/identify", {"file": "sala-1.jpg", "mode": "multi"})["items"]), 3)
        self.assertTrue(self.app.ok("GET", "api/voice/status")["ready"])
        self.assertIn("Sofá", self.app.ok("POST", "api/voice", raw=PCM, headers={"Content-Type": "application/octet-stream"})["text"])
        self.assertEqual(len(self.app.ok("POST", "api/ai/text", {"text": "x"})["items"]), 3)


if __name__ == "__main__":
    unittest.main()
