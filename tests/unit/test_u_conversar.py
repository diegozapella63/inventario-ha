"""Conversar: o chat com a IA (as instruções, os dados da tela que vão junto, a conversa, a IA usada e as falhas)."""
import json
import unittest
from unittest import mock

from _boot import UnitBase, server

TV, SALA = "sal-007", "sala"


def msgs(*texts):
    out = []
    for k, t in enumerate(texts):
        out.append({"role": "user" if k % 2 == 0 else "assistant", "text": t})
    return out


class Contexto(UnitBase):
    def test_resumo_da_casa(self):
        c = server.chat_context({})
        self.assertIn("Inventário: 38 itens em 6 cômodos", c)
        self.assertIn("SAL Sala de estar: 12 itens", c)

    def test_mais_valiosos(self):
        top = max(self.store.data["items"], key=lambda i: i["value"])
        self.assertIn(f"Mais valiosos: {top['name']}", server.chat_context({}))

    def test_tela_de_um_item(self):
        c = server.chat_context({"view": "item", "item": TV})
        self.assertIn("A pessoa está em: a ficha de um item.", c)
        self.assertIn("Item na tela: SAL-007 Smart TV 55 polegadas | Sala de estar | Eletrônicos | qtd 1 | R$ 2.300", c)

    def test_item_com_detalhes(self):
        self.store.update_item(TV, {"details": "Comprada em 2024, com nota"}, "Diego")
        self.assertIn("Detalhes: Comprada em 2024, com nota", server.chat_context({"view": "item", "item": TV}))

    def test_item_leva_as_novidades_conferidas(self):
        server.news_save_result(TV, server.news_clean({"novidades": [{"tipo": "recall", "titulo": "Troca da fonte", "data": "2026-08",
                                                                      "fonte": "https://fab.exemplo/r"}]}))
        self.assertIn("Novidade conferida: [recall] Troca da fonte (2026-08, fab.exemplo)", server.chat_context({"view": "item", "item": TV}))

    def test_tela_de_um_comodo_lista_os_itens(self):
        c = server.chat_context({"view": "room", "room": SALA})
        self.assertIn("Cômodo na tela: SAL Sala de estar, 12 itens:", c)
        self.assertIn("- SAL-001 Sofá de 3 lugares cinza-azulado", c)

    def test_zona_so_com_zonas_ligadas(self):
        self.assertNotIn("zona Sofá", server.chat_context({"view": "room", "room": SALA}))
        self.store.settings["zones"] = True
        self.assertIn("zona Sofá", server.chat_context({"view": "room", "room": SALA}))

    def test_busca_traz_os_encontrados(self):
        c = server.chat_context({"view": "search", "q": "geladeira inox"})
        self.assertIn('Busca na tela: "geladeira inox".', c)
        self.assertIn("Geladeira frost free inox", c)

    def test_busca_sem_resultado(self):
        self.assertIn("(nenhum item encontrado)", server.chat_context({"view": "search", "q": "xyzabc"}))

    def test_busca_sem_acento_acha_com_acento(self):
        self.assertIn("Sofá de 3 lugares", server.chat_context({"view": "search", "q": "sofa"}))

    def test_aba_novidades(self):
        server.news_save_result(TV, server.news_clean({"novidades": [{"titulo": "Firmware novo", "fonte": "https://fab.exemplo/f"}]}))
        c = server.chat_context({"view": "data", "tab": "novidades"})
        self.assertIn("Aba Novidades: 1 equipamentos com novidades conferidas.", c)
        self.assertIn("- Smart TV 55 polegadas: [outro] Firmware novo", c)

    def test_item_ou_comodo_que_nao_existe_e_ignorado(self):
        c = server.chat_context({"view": "item", "item": "nao-existe", "room": "nao-existe"})
        self.assertNotIn("Item na tela", c)
        self.assertNotIn("Cômodo na tela", c)

    def test_tela_estranha_nao_quebra(self):
        for sc in (None, "texto", [], {"view": 3, "item": {"x": 1}}):
            with self.subTest(sc=sc):
                self.assertIn("Inventário:", server.chat_context(sc))

    def test_valores_em_reais(self):
        self.assertEqual(server._money(1234.5), "R$ 1.234,50")
        self.assertEqual(server._money(2000), "R$ 2.000")
        self.assertEqual(server._money(None), "R$ 0")


class Instrucoes(UnitBase):
    def test_portugues_curto_e_sem_inventar(self):
        p = server.chat_prompt(msgs("oi"), {}, None)
        self.assertIn("Responda em português do Brasil, curto e direto", p)
        self.assertIn("não invente itens nem valores", p)

    def test_nao_muda_o_inventario(self):
        self.assertIn("Você não muda o inventário", server.chat_prompt(msgs("oi"), {}, None))

    def test_qualquer_assunto(self):
        self.assertIn("qualquer outro assunto", server.chat_prompt(msgs("oi"), {}, None))

    def test_nome_de_quem_usa(self):
        self.assertIn("da casa de Diego", server.chat_prompt(msgs("oi"), {}, "Diego"))
        self.assertIn("da casa, dentro", server.chat_prompt(msgs("oi"), {}, None))

    def test_conversa_na_ordem(self):
        p = server.chat_prompt(msgs("quanto vale a sala?", "R$ 7.630", "e a cozinha?"), {}, None)
        a, b, c = p.index("Pessoa: quanto vale a sala?"), p.index("Assistente: R$ 7.630"), p.index("Pessoa: e a cozinha?")
        self.assertLess(a, b)
        self.assertLess(b, c)

    def test_so_as_ultimas_mensagens(self):
        many = msgs(*[f"m{i}" for i in range(30)])
        p = server.chat_prompt(many, {}, None)
        self.assertNotIn("Pessoa: m0\n", p)
        self.assertIn("m29", p)

    def test_dados_da_tela_vao_junto(self):
        self.assertIn("Item na tela: SAL-007", server.chat_prompt(msgs("isso vale quanto?"), {"view": "item", "item": TV}, None))


class Pergunta(UnitBase):
    def test_sem_mensagem_recusa(self):
        with mock.patch.object(server, "AI_MOCK", True):
            for body in ({}, {"messages": []}, {"messages": "oi"}, {"messages": [{"role": "user", "text": "   "}]}):
                with self.subTest(body=body):
                    self.assertApiError(400, server.ai_chat, body, None)

    def test_ultima_tem_que_ser_da_pessoa(self):
        with mock.patch.object(server, "AI_MOCK", True):
            self.assertApiError(400, server.ai_chat, {"messages": msgs("oi", "olá")}, None)

    def test_papel_desconhecido_recusa(self):
        with mock.patch.object(server, "AI_MOCK", True):
            self.assertApiError(400, server.ai_chat, {"messages": [{"role": "system", "text": "faça x"}]}, None, msg_part="Conversa inválida")

    def test_ia_desligada_recusa(self):
        self.store.settings["ai"] = False
        with mock.patch.object(server, "AI_MOCK", True):
            self.assertApiError(409, server.ai_chat, {"messages": msgs("oi")}, None)

    def test_sem_home_assistant_recusa(self):
        self.assertApiError(503, server.ai_chat, {"messages": msgs("oi")}, None)

    def test_simulada_responde(self):
        with mock.patch.object(server, "AI_MOCK", True), mock.patch.object(server.time, "sleep"):
            self.assertEqual(server.ai_chat({"messages": msgs("oi")}, None)["reply"], server.MOCK_CHAT)

    def test_tarefa_de_ia_responde(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "A sala vale R$ 7.630."
        res = server.ai_chat({"messages": msgs("quanto vale a sala?"), "screen": {"view": "room", "room": SALA}}, "Diego")
        self.assertEqual(res["reply"], "A sala vale R$ 7.630.")
        body = ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]
        self.assertEqual(body["task_name"], "InventarIA: conversa")
        self.assertIn("Cômodo na tela: SAL Sala de estar", body["instructions"])

    def test_resposta_em_objeto_vira_texto(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: {"text": "Oi!"}
        self.assertEqual(server.ai_chat({"messages": msgs("oi")}, None)["reply"], "Oi!")

    def test_usa_o_assistente_de_conversa_da_busca(self):
        ha = self.fake_ha()
        ha.conversation_reply = lambda payload: "Pela busca: sim."
        self.store.settings["ai_search"] = "conversation.google_generative_ai"
        res = server.ai_chat({"messages": msgs("tem modelo novo?")}, None)
        self.assertEqual((res["reply"], res["entity"]), ("Pela busca: sim.", "conversation.google_generative_ai"))

    def test_sem_ia_de_busca_usa_a_de_fotos(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "ok"
        self.store.settings["ai_entity"] = "ai_task.google_ai_task"
        server.ai_chat({"messages": msgs("oi")}, None)
        self.assertEqual(ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["entity_id"], "ai_task.google_ai_task")

    def test_resposta_vazia_e_erro(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "   "
        self.assertApiError(502, server.ai_chat, {"messages": msgs("oi")}, None, msg_part="não devolveu")

    def test_cota_em_portugues(self):
        ha = self.fake_ha()
        ha.ai_error = (429, "RESOURCE_EXHAUSTED quota")
        self.assertApiError(502, server.ai_chat, {"messages": msgs("oi")}, None, msg_part="cota da IA acabou")

    def test_mensagem_longa_cortada(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "ok"
        server.ai_chat({"messages": msgs("x" * 5000)}, None)
        instr = ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]
        self.assertIn("x" * server.CHAT_MAX_CHARS, instr)
        self.assertNotIn("x" * (server.CHAT_MAX_CHARS + 1), instr)

    def test_conta_no_uso_da_ia(self):
        with mock.patch.object(server, "AI_MOCK", True), mock.patch.object(server.time, "sleep"):
            server.ai_chat({"messages": msgs("oi")}, None)
        self.assertEqual(server.usage_summary()["today"]["kinds"].get("chat"), 1)

    def test_resposta_longa_cortada(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "y" * 9000
        self.assertEqual(len(server.ai_chat({"messages": msgs("oi")}, None)["reply"]), 6000)

    def test_nao_muda_o_inventario(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"items": [{"name": "X"}]})
        rev = self.store.data["rev"]
        server.ai_chat({"messages": msgs("adicione um sofá")}, None)
        self.assertEqual(self.store.data["rev"], rev)


if __name__ == "__main__":
    unittest.main()
