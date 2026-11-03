"""Conversar pelo HTTP: a rota do chat com a IA simulada, com a IA desligada e com o Home Assistant de mentira."""
import json
import unittest

from _boot import AppServer, FakeHA, ServerCase


def conversa(*texts):
    return [{"role": "user" if k % 2 == 0 else "assistant", "text": t} for k, t in enumerate(texts)]


class Simulado(ServerCase):
    server_kw = {"mock_ai": True}

    def setUp(self):
        self.app.ok("PUT", "api/settings", {"ai": True})

    def test_responde(self):
        st, _, out = self.app.request("POST", "api/chat", {"messages": conversa("oi")})
        self.assertEqual(st, 200)
        self.assertTrue(out["reply"].startswith("Exemplo da IA simulada"))

    def test_sem_mensagens_400(self):
        st, _, out = self.app.request("POST", "api/chat", {})
        self.assertEqual((st, out["error"]), (400, "Escreva uma mensagem."))

    def test_corpo_que_nao_e_objeto_400(self):
        self.assertEqual(self.app.request("POST", "api/chat", raw=b"[1]", headers={"Content-Type": "application/json"})[0], 400)

    def test_ia_desligada_409(self):
        self.app.ok("PUT", "api/settings", {"ai": False})
        self.assertEqual(self.app.request("POST", "api/chat", {"messages": conversa("oi")})[0], 409)

    def test_get_nao_e_rota(self):
        st, _, _ = self.app.request("GET", "api/chat")
        self.assertEqual(st, 404)

    def test_conta_no_uso(self):
        app = self.fresh(mock_ai=True)
        app.ok("POST", "api/chat", {"messages": conversa("oi")})
        self.assertEqual(app.ok("GET", "api/ai/usage")["today"]["kinds"].get("chat"), 1)

    def test_nao_muda_o_inventario(self):
        rev = self.app.ok("GET", "api/rev")["rev"]
        self.app.ok("POST", "api/chat", {"messages": conversa("apague tudo")})
        self.assertEqual(self.app.ok("GET", "api/rev")["rev"], rev)


class SemHomeAssistant(ServerCase):
    def test_503(self):
        st, _, out = self.app.request("POST", "api/chat", {"messages": conversa("oi")})
        self.assertEqual(st, 503)
        self.assertIn("API do Home Assistant", out["error"])


class ComHomeAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ha = FakeHA()
        cls.app = AppServer(ha=cls.ha)

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()
        cls.ha.stop()

    def setUp(self):
        self.ha.ai_error = None
        self.app.ok("PUT", "api/settings", {"ai_search": "", "ai_entity": ""})

    def test_leva_a_tela_e_o_nome_de_quem_pergunta(self):
        self.ha.ai_reply = lambda kind, payload: "A TV vale R$ 2.300."
        st, _, out = self.app.request("POST", "api/chat", {"messages": conversa("quanto vale?"), "screen": {"view": "item", "item": "sal-007"}},
                                      headers={"X-Remote-User-Display-Name": "Diego"})
        self.assertEqual((st, out["reply"]), (200, "A TV vale R$ 2.300."))
        instr = self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]
        self.assertIn("Item na tela: SAL-007 Smart TV 55 polegadas", instr)
        self.assertIn("da casa de Diego", instr)

    def test_conversa_inteira_vai_junto(self):
        self.ha.ai_reply = lambda kind, payload: "ok"
        self.app.ok("POST", "api/chat", {"messages": conversa("qual o mais caro?", "O notebook.", "e o mais barato?")})
        instr = self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]
        self.assertIn("Pessoa: qual o mais caro?\nAssistente: O notebook.\nPessoa: e o mais barato?", instr)

    def test_assistente_de_conversa_da_busca(self):
        self.app.ok("PUT", "api/settings", {"ai_search": "conversation.google_generative_ai"})
        self.ha.conversation_reply = lambda payload: "Sim, saiu um modelo novo."
        out = self.app.ok("POST", "api/chat", {"messages": conversa("saiu modelo novo da minha TV?")})
        self.assertEqual(out["entity"], "conversation.google_generative_ai")

    def test_cota_em_portugues(self):
        self.ha.ai_error = (429, "RESOURCE_EXHAUSTED: quota")
        st, _, out = self.app.request("POST", "api/chat", {"messages": conversa("oi")})
        self.assertEqual(st, 502)
        self.assertIn("cota da IA acabou", out["error"])

    def test_erro_do_assistente(self):
        self.app.ok("PUT", "api/settings", {"ai_search": "conversation.google_generative_ai"})
        self.ha.conversation_reply = lambda payload: "ERRO:Não entendi"
        st, _, out = self.app.request("POST", "api/chat", {"messages": conversa("oi")})
        self.assertEqual(st, 502)
        self.assertIn("respondeu com erro", out["error"])

    def test_resposta_vem_em_json(self):
        self.ha.ai_reply = lambda kind, payload: "Linha 1\n- item"
        st, h, raw = self.app.request("POST", "api/chat", {"messages": conversa("oi")})
        self.assertIn("application/json", h["Content-Type"])
        self.assertEqual(raw["reply"], "Linha 1\n- item")
        json.dumps(raw)


if __name__ == "__main__":
    unittest.main()
