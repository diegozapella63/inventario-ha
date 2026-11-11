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

    def test_so_eletronicos(self):
        st, _, body = self.app.request("POST", "api/news", {"item": "sal-001"})  # o sofá: Móveis
        self.assertEqual((st, body["error"]), (400, "As novidades são só dos eletrônicos."))

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


class Todos(ServerCase):
    server_kw = {"mock_ai": True}

    def setUp(self):
        self.app.ok("PUT", "api/settings", {"ai": True})

    def test_visao_da_aba(self):
        ov = self.app.ok("GET", "api/news")
        self.assertEqual(ov["cats"], ["eletronicos"])
        self.assertIn("pendentes", ov)
        self.assertIn("itens", ov)

    def test_visao_com_ia_desligada_recusa(self):
        self.app.ok("PUT", "api/settings", {"ai": False})
        self.assertEqual(self.app.request("GET", "api/news")[0], 409)

    def test_conferir_todos_do_comeco_ao_fim(self):
        app = self.fresh(mock_ai=True)
        st, _, body = app.request("POST", "api/news/all", {})
        self.assertEqual(st, 202)
        fim = esperar(app, body["id"], timeout=30)
        self.assertEqual(fim["stage"], "done")
        n = sum(1 for i in app.data()["items"] if i["cat"] == "eletronicos" and i["name"] != "Caixa de som de estante")
        self.assertEqual(fim["summary"]["conferidos"], n, "a IA simulada escolhe os eletrônicos, menos a caixa de som de estante")
        ov = app.ok("GET", "api/news")
        self.assertEqual(len(ov["itens"]), n)
        self.assertEqual(ov["ultima"]["conferidos"], n)
        self.assertEqual(ov["pendentes"], 0)

    def test_corpo_vazio_nao_atrapalha_o_proximo_pedido(self):
        # o pedido de conferir todos chega com "{}": o corpo não pode sobrar na conexão
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=10)
        try:
            conn.request("POST", "/api/news/all", body=b"{}", headers={"Content-Type": "application/json"})
            r = conn.getresponse()
            jid = json.loads(r.read())["id"]
            conn.request("GET", f"/api/news/{jid}")
            r2 = conn.getresponse()
            self.assertEqual(r2.status, 200)
            r2.read()
            conn.request("DELETE", f"/api/news/{jid}")
            conn.getresponse().read()
        finally:
            conn.close()

    def test_uma_conferencia_por_vez(self):
        a = self.app.ok("POST", "api/news/all", {})["id"]
        b = self.app.ok("POST", "api/news/all", {})["id"]
        self.assertEqual(a, b)
        self.app.ok("DELETE", f"api/news/{a}")

    def test_parar_responde_ok(self):
        jid = self.app.ok("POST", "api/news/all", {})["id"]
        self.assertEqual(self.app.ok("DELETE", f"api/news/{jid}"), {"ok": True})

    def test_eletronicos_fica_sempre(self):
        """Eletrônicos é a categoria das novidades: não se renomeia nem se exclui, e volta se faltar na lista guardada."""
        app = self.fresh(mock_ai=True)
        st, _, body = app.request("DELETE", "api/cats/eletronicos")
        self.assertEqual((st, body["error"]), (400, "Eletrônicos é uma categoria fixa (as novidades e os recursos): não dá para apagar."))
        st, _, body = app.request("PUT", "api/cats/eletronicos", {"name": "Aparelhos"})
        self.assertEqual((st, body["error"]), (400, "Eletrônicos é uma categoria fixa (as novidades e os recursos): não dá para renomear."))
        self.assertEqual(app.data()["cats"][0], {"id": "eletronicos", "name": "Eletrônicos"})
        self.assertEqual(app.ok("POST", "api/news/all", {})["id"] != "", True, "e as novidades continuam")

    def test_escolher_categorias_nao_vale_mais(self):
        app = self.fresh(mock_ai=True)
        self.assertEqual(app.request("PUT", "api/settings", {"news_cats": ["cozinha"]})[0], 200)
        self.assertEqual(app.ok("GET", "api/news")["cats"], ["eletronicos"])

    def test_novidades_de_um_item_para_a_ficha(self):
        app = self.fresh(mock_ai=True)
        self.assertEqual(app.ok("GET", "api/news?item=sal-007"), {}, "nunca conferido")
        esperar(app, app.ok("POST", "api/news", {"item": "sal-007"})["id"])
        r = app.ok("GET", "api/news?item=sal-007")
        self.assertTrue(r["at"])
        self.assertEqual(len(r["news"]["novidades"]), 3)
        self.assertEqual(app.ok("GET", "api/news?item=nao-existe"), {})
        app.ok("PUT", "api/settings", {"ai": False})
        self.assertEqual(app.request("GET", "api/news?item=sal-007")[0], 409, "IA desligada: recusa")

    def test_padrao_so_eletronicos(self):
        app = self.fresh(mock_ai=True)
        self.assertEqual(app.ok("GET", "api/news")["cats"], ["eletronicos"])

    def test_limpar_novidades(self):
        app = self.fresh(mock_ai=True)
        esperar(app, app.ok("POST", "api/news/all", {})["id"], timeout=30)
        self.assertTrue(app.ok("GET", "api/news")["itens"])
        rev = app.ok("GET", "api/rev")["rev"]
        st, _, ov = app.request("DELETE", "api/news")
        self.assertEqual(st, 200)
        self.assertEqual((ov["itens"], ov["triagem"], ov["ultima"]), ({}, {}, None))
        self.assertEqual(app.ok("GET", "api/news")["itens"], {}, "continua limpo")
        self.assertEqual(app.ok("GET", "api/rev")["rev"], rev, "o inventário não muda")
        self.assertEqual(app.ok("GET", "api/news")["cats"], ["eletronicos"], "continua em Eletrônicos")

    def test_ia_desligada_recusa_conferir_todos(self):
        self.app.ok("PUT", "api/settings", {"ai": False})
        self.assertEqual(self.app.request("POST", "api/news/all", {})[0], 409)


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
