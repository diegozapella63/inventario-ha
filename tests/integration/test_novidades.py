"""Novidades do produto pelo HTTP: começar, acompanhar, cancelar, IA desligada e com o Home Assistant de mentira."""
import json
import os
import tempfile
import time
import unittest

from _boot import AppServer, FakeHA, ServerCase

ITEM = "sal-007"


def esperar(app, jid, timeout=8):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = app.ok("GET", f"api/news/{jid}")
        if st["stage"] != "busy":
            return st
        time.sleep(0.15)
    raise AssertionError("a busca de novidades não terminou")


class Simulado(ServerCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.mock = os.path.join(cls.tmp.name, "novidades.json")
        with open(cls.mock, "w", encoding="utf-8") as f:
            json.dump({"produto": "TV de teste", "novidades": [
                {"tipo": "recall", "titulo": "Troca de fonte", "resumo": "Lote com defeito.", "data": "2026-08", "fonte": "https://fab.exemplo/recall"},
                {"tipo": "sucessor", "titulo": "Modelo 2027", "data": "2026-10-20", "fonte": "https://fab.exemplo/novo"},
                {"tipo": "outro", "titulo": "Sem fonte", "fonte": ""},
            ]}, f)
        cls.server_kw = {"mock_ai": True, "env": {"INV_MOCK_NEWS": cls.mock}}
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.tmp.cleanup()

    def setUp(self):
        self.app.ok("PUT", "api/settings", {"ai": True})

    def test_comeca_com_202_e_um_id(self):
        st, _, body = self.app.request("POST", "api/news", {"item": ITEM})
        self.assertEqual(st, 202)
        self.assertRegex(body["id"], r"^[a-f0-9]{16}$")

    def test_termina_com_as_novidades_conferidas(self):
        jid = self.app.ok("POST", "api/news", {"item": ITEM})["id"]
        st = esperar(self.app, jid)
        self.assertEqual(st["stage"], "done")
        self.assertEqual([n["titulo"] for n in st["news"]["novidades"]], ["Modelo 2027", "Troca de fonte"], "sem a que não tem fonte, a mais nova primeiro")
        self.assertEqual(st["news"]["produto"], "TV de teste")

    def test_enquanto_busca_diz_o_que_faz(self):
        jid = self.app.ok("POST", "api/news", {"item": ITEM})["id"]
        st = self.app.ok("GET", f"api/news/{jid}")
        self.assertIn(st["stage"], ("busy", "done"))
        if st["stage"] == "busy":
            self.assertEqual(st["msg"], "Procurando novidades…")
        esperar(self.app, jid)

    def test_item_que_nao_existe_404(self):
        st, _, body = self.app.request("POST", "api/news", {"item": "nao-existe"})
        self.assertEqual((st, body["error"]), (404, "Item não encontrado."))

    def test_sem_item_404(self):
        self.assertEqual(self.app.request("POST", "api/news", {})[0], 404)

    def test_busca_que_nao_existe_404(self):
        self.assertEqual(self.app.request("GET", "api/news/0123456789abcdef")[0], 404)

    def test_id_fora_do_formato_nao_e_rota(self):
        self.assertEqual(self.app.request("GET", "api/news/xyz")[0], 404)

    def test_cancelar_tira_a_busca(self):
        jid = self.app.ok("POST", "api/news", {"item": ITEM})["id"]
        self.assertEqual(self.app.ok("DELETE", f"api/news/{jid}"), {"ok": True})
        self.assertEqual(self.app.request("GET", f"api/news/{jid}")[0], 404)

    def test_cancelar_de_novo_nao_da_erro(self):
        self.assertEqual(self.app.ok("DELETE", "api/news/0123456789abcdef"), {"ok": True})

    def test_ia_desligada_recusa_comecar(self):
        self.app.ok("PUT", "api/settings", {"ai": False})
        st, _, body = self.app.request("POST", "api/news", {"item": ITEM})
        self.assertEqual(st, 409)
        self.assertIn("IA está desligada", body["error"])

    def test_ia_desligada_no_meio_nao_entrega(self):
        jid = self.app.ok("POST", "api/news", {"item": ITEM})["id"]
        esperar(self.app, jid)
        self.app.ok("PUT", "api/settings", {"ai": False})
        self.assertEqual(self.app.request("GET", f"api/news/{jid}")[0], 409)

    def test_conta_no_uso_da_ia(self):
        app = self.fresh(**self.server_kw)  # sozinho: as buscas dos outros testes também contam
        esperar(app, app.ok("POST", "api/news", {"item": ITEM})["id"])
        self.assertEqual(app.ok("GET", "api/ai/usage")["today"]["kinds"].get("novidades"), 1)

    def test_nao_muda_o_inventario(self):
        rev = self.app.ok("GET", "api/rev")["rev"]
        esperar(self.app, self.app.ok("POST", "api/news", {"item": ITEM})["id"])
        self.assertEqual(self.app.ok("GET", "api/rev")["rev"], rev)


class SemHomeAssistant(ServerCase):
    def test_sem_acesso_ao_home_assistant_503(self):
        st, _, body = self.app.request("POST", "api/news", {"item": ITEM})
        self.assertEqual(st, 503)
        self.assertIn("API do Home Assistant", body["error"])


class ComHomeAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ha = FakeHA()
        cls.app = AppServer(ha=cls.ha)

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()
        cls.ha.stop()

    def test_pergunta_a_ia_de_busca_e_traz_as_novidades(self):
        self.ha.ai_reply = lambda kind, payload: json.dumps({"produto": "Smart TV", "novidades": [
            {"tipo": "atualizacao", "titulo": "Firmware novo", "data": "2026-09", "fonte": "https://fab.exemplo/fw"}]})
        st = esperar(self.app, self.app.ok("POST", "api/news", {"item": ITEM})["id"])
        self.assertEqual(st["news"]["novidades"][0]["site"], "fab.exemplo")
        instr = self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]
        self.assertIn("Use a busca na web agora", instr)

    def test_sem_busca_na_web_vira_erro_explicado(self):
        self.ha.ai_reply = lambda kind, payload: '{"erro": "sem_busca"}'
        st = esperar(self.app, self.app.ok("POST", "api/news", {"item": ITEM})["id"])
        self.assertEqual(st["stage"], "error")
        self.assertIn("busca na web", st["msg"])

    def test_erro_do_home_assistant_vira_erro(self):
        self.ha.ai_error = (500, "falhou")
        try:
            st = esperar(self.app, self.app.ok("POST", "api/news", {"item": ITEM})["id"])
        finally:
            self.ha.ai_error = None
        self.assertEqual(st["stage"], "error")
        self.assertTrue(st["msg"])


if __name__ == "__main__":
    unittest.main()
