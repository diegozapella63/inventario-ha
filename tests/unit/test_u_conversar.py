"""Conversar: o chat com a IA (as instruções, os dados da tela que vão junto, a conversa, a IA usada e as falhas)."""
import base64
import json
import os
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
        self.assertIn("Inventário da casa: 38 itens em 6 cômodos", c)
        self.assertIn("SAL Sala de estar: 12 itens", c)
        self.assertNotIn("valores são os de hoje", c, "sem o Valor de hoje, o valor gravado")

    def test_os_valores_de_hoje_como_na_tela(self):
        """1.75.0: com o Valor de hoje ligado (a depreciação do GerencIA), a IA recebe os valores da tela, não os gravados."""
        import tempfile
        arq = os.path.join(tempfile.mkdtemp(prefix="inv-ger-"), "integracao.json")
        with open(arq, "w", encoding="utf-8") as f:
            json.dump({"depreciacao": {"eletronicos": 20, "moveis": 10}}, f)
        p = mock.patch.object(server, "GERENCIA_ARQ", arq)
        p.start()
        self.addCleanup(p.stop)
        server._ger.update(mtime=None, taxas=None)
        self.addCleanup(lambda: server._ger.update(mtime=None, taxas=None))
        self.store.settings["deprec"] = True
        self.addCleanup(lambda: self.store.settings.pop("deprec", None))
        taxas = server.gerencia_taxas()
        sala = [i for i in self.store.data["items"] if i["room"] == SALA]
        hoje = server._money(sum(server.item_hoje(i, taxas) for i in sala))
        gravado = server._money(sum(float(i.get("value") or 0) for i in sala))
        c = server.chat_context({})
        self.assertNotEqual(hoje, gravado, "a casa de teste tem valores antigos: o de hoje é menor")
        self.assertIn(f"SAL Sala de estar: {len(sala)} itens, {hoje}", c)
        self.assertNotIn(f"SAL Sala de estar: {len(sala)} itens, {gravado}", c)
        self.assertIn("Os valores são os de hoje, como na tela", c)
        tv = self.store.item(TV)
        self.assertIn(server._money(server.item_hoje(tv, taxas)), server.chat_context({"view": "item", "item": TV}))

    def test_os_bens_a_parte_dos_comodos(self):
        """1.75.0: os Bens (o que fica fora de casa) não entram como um cômodo."""
        area = self.store.create_room({"kind": "bens"})
        self.store.create_items([{"room": area["id"], "name": "Carro hatch", "cat": "veiculos", "value": 60000}], None)
        c = server.chat_context({})
        self.assertIn("Inventário da casa: 38 itens em 6 cômodos", c, "sem a área Bens")
        self.assertNotIn("BEN Bens:", c, "não está entre os cômodos")
        self.assertIn("Bens (o que fica fora de casa, como imóveis e veículos; não é um cômodo): 1 itens, R$ 60.000.", c)
        self.assertIn("Com eles, o patrimônio é", c)

    def test_mais_valiosos(self):
        top = max(self.store.data["items"], key=lambda i: i["value"])
        self.assertIn(f"Mais valiosos: {top['name']}", server.chat_context({}))

    def test_tela_de_um_item(self):
        c = server.chat_context({"view": "item", "item": TV})
        self.assertIn("A pessoa está em: a ficha de um item.", c)
        self.assertIn("Item na tela: SAL-007 Smart TV 55 polegadas | Sala de estar | Eletrônicos | qtd 1 | R$ 2.300", c)

    def test_item_com_detalhes(self):
        self.store.update_item(TV, {"details": "Comprada em 2024, com nota"}, "Davi")
        self.assertIn("Detalhes: Comprada em 2024, com nota", server.chat_context({"view": "item", "item": TV}))

    def test_item_leva_as_novidades_conferidas(self):
        server.news_save_result(TV, server.news_clean({"novidades": [{"tipo": "recall", "titulo": "Recall: troca da fonte", "data": "2026-08",
                                                                      "fonte": "https://fab.exemplo/r"}]}))
        self.assertIn("Novidade conferida: [recall] Recall: troca da fonte (2026-08, fab.exemplo)", server.chat_context({"view": "item", "item": TV}))

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

    def test_busca_leva_o_que_a_tela_achou(self):
        """1.75.0: a busca da tela (com os filtros de cômodo e categoria, e o código e o cômodo no texto) vai como a tela
        achou, na ordem dela; antes, a IA buscava de novo só no nome e nos detalhes e achava outra coisa."""
        sala = [i["id"] for i in self.store.data["items"] if i["room"] == SALA]
        c = server.chat_context({"view": "search", "q": "sala", "ids": sala[:3], "total": 12, "filtros": "Sala de estar"})
        self.assertIn('Busca na tela "sala" (Sala de estar): 12 itens, na ordem da tela:', c)
        busca = c.split("Busca na tela", 1)[1].split("Todos os itens", 1)[0]
        self.assertEqual(busca.count("\n- SAL-"), 3)
        self.assertIn("- … e mais 9 que não couberam aqui (são 12 ao todo).", c)
        c = server.chat_context({"view": "search", "q": "xyzabc", "ids": [], "total": 0})
        self.assertIn('Busca na tela "xyzabc": 0 itens.', c)
        c = server.chat_context({"view": "search", "ids": ["nao-existe", TV], "total": "?"})
        self.assertIn("Busca na tela: 1 item, na ordem da tela:", c, "um id que não existe fica de fora")

    def test_comodo_grande_diz_quantos_ficaram_de_fora(self):
        for k in range(80):
            self.store.data["items"].append(dict(self.store.data["items"][0], id=f"extra-{k}", room=SALA, seq=100 + k))
        c = server.chat_context({"view": "room", "room": SALA})
        self.assertIn("- … e mais 12 que não couberam aqui (são 92 ao todo).", c)

    def test_todos_os_itens_e_as_categorias(self):
        """1.76.0: de qualquer tela, todos os itens (o código, o cômodo, a categoria, o valor, a observação e quem cadastrou)
        e o total de cada categoria; antes, fora de um cômodo ou da busca, só os totais e os 10 mais valiosos ("Quantos
        eletrônicos eu tenho?" ficava sem resposta)."""
        c = server.chat_context({})
        self.assertIn("Todos os itens (38;", c)
        self.assertEqual(c.count("\n- "), 38)
        ele = [i for i in self.store.data["items"] if i.get("cat") == "eletronicos"]
        self.assertIn(f"Eletrônicos: {len(ele)} itens, {server._money(sum(float(i['value']) for i in ele))}", c)
        it = self.store.data["items"][0]
        it["flag"], it["createdBy"] = "Na garantia até 2027", "Ana"
        self.assertIn(" | obs: Na garantia até 2027 | cadastrado por Ana", server.chat_context({}))
        # muitos: corta e diz quantos
        for k in range(server.MAX_ITENS_CHAT):
            self.store.data["items"].append(dict(it, id=f"x{k}", seq=200 + k, flag="", createdBy=""))
        c = server.chat_context({})
        self.assertIn(f"- … e mais 38 que não couberam aqui (são {server.MAX_ITENS_CHAT + 38} ao todo).", c)

    def test_os_bens_na_lista_depois_dos_comodos(self):
        area = self.store.create_room({"kind": "bens"})
        self.store.create_items([{"room": area["id"], "name": "Carro hatch", "cat": "veiculos", "value": 60000}], None)
        c = server.chat_context({"view": "bens"})
        self.assertIn("A pessoa está em: Bens (o que fica fora de casa).", c)
        lista = c.split("Todos os itens", 1)[1]
        self.assertTrue(lista.rstrip().endswith("Carro hatch | Bens | Veículos | qtd 1 | R$ 60.000"), lista[-200:])
        self.assertIn("Veículos: 1 item, R$ 60.000", c)

    def test_busca_sem_acento_acha_com_acento(self):
        self.assertIn("Sofá de 3 lugares", server.chat_context({"view": "search", "q": "sofa"}))

    def test_tela_novidades(self):
        server.news_save_result(TV, server.news_clean({"novidades": [{"titulo": "Firmware novo", "fonte": "https://fab.exemplo/f"}]}))
        c = server.chat_context({"view": "news"})
        self.assertIn("Tela Pesquisas da IA › Novidades: 1 eletrônicos com novidades conferidas.", c)
        self.assertIn("- Smart TV 55 polegadas: [outro] Firmware novo", c)

    def test_tela_novidades_pelo_jeito_antigo(self):
        server.news_save_result(TV, server.news_clean({"novidades": [{"titulo": "Firmware novo", "fonte": "https://fab.exemplo/f"}]}))
        self.assertIn("Tela Pesquisas da IA › Novidades:", server.chat_context({"view": "data", "tab": "novidades"}))

    def test_menu_mais_e_categorias_levam_so_o_resumo(self):
        for view in ("menu", "cats"):
            c = server.chat_context({"view": view})
            self.assertNotIn("Tela Novidades", c)
            self.assertIn("Sala de estar", c)

    def test_item_ou_comodo_que_nao_existe_e_ignorado(self):
        c = server.chat_context({"view": "item", "item": "nao-existe", "room": "nao-existe"})
        self.assertNotIn("Item na tela", c)
        self.assertNotIn("Cômodo na tela", c)

    def test_tela_estranha_nao_quebra(self):
        for sc in (None, "texto", [], {"view": 3, "item": {"x": 1}}):
            with self.subTest(sc=sc):
                self.assertIn("Inventário da casa:", server.chat_context(sc))

    def test_valores_em_reais(self):
        self.assertEqual(server._money(1234.5), "R$ 1.234,50")
        self.assertEqual(server._money(2000), "R$ 2.000")
        self.assertEqual(server._money(None), "R$ 0")


class Instrucoes(UnitBase):
    def test_portugues_curto_e_sem_inventar(self):
        p = server.chat_prompt(msgs("oi"), {}, None)
        self.assertIn("Responda em português do Brasil, com todos os acentos e o ç (você, às, não, alimentação), curto e direto", p)  # 1.75.0: com os acentos
        self.assertIn("não invente itens nem valores", p)

    def test_nao_muda_o_inventario(self):
        self.assertIn("Você não muda o inventário", server.chat_prompt(msgs("oi"), {}, None))
        # 1.81.1: o contexto da família (a mesma frase em todos os apps)
        p = server.chat_prompt(msgs("oi"), {}, None)
        self.assertIn(server.FAMILIA_IA, p)
        for app in ("ResolvIA (listas de tarefas)", "CronologIA (agenda", "GerencIA (finanças)", "InventarIA (inventário", "MemorIA (blocos", "EconomIA (lista de compras", "CorrerIA (os apps no WhatsApp"):
            self.assertIn(app, server.FAMILIA_IA)
        self.assertTrue(server.FAMILIA_IA.endswith("Você só vê os dados deste app: se a pessoa perguntar algo que é de outro, diga em qual app está, sem inventar."))

    def test_qualquer_assunto(self):
        self.assertIn("qualquer outro assunto", server.chat_prompt(msgs("oi"), {}, None))

    def test_nome_de_quem_usa(self):
        self.assertIn("Quem está usando agora: Davi. Cada item diz quem o cadastrou", server.chat_prompt(msgs("oi"), {}, "Davi"))
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
        res = server.ai_chat({"messages": msgs("quanto vale a sala?"), "screen": {"view": "room", "room": SALA}}, "Davi")
        self.assertEqual(res["reply"], "A sala vale R$ 7.630.")
        body = ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]
        self.assertEqual(body["task_name"], "InventarIA: conversa")
        self.assertIn("Cômodo na tela: SAL Sala de estar", body["instructions"])

    def test_resposta_em_objeto_vira_texto(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: {"text": "Oi!"}
        self.assertEqual(server.ai_chat({"messages": msgs("oi")}, None)["reply"], "Oi!")

    def test_a_ia_para_conversar(self):
        """1.72.0: a Conversa vai para a IA Para conversar; a de pesquisar e a de fotos ficam com o que é delas."""
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "ok"
        self.store.settings.update(ai_entity="ai_task.google_ai_task", ai_search="conversation.google_generative_ai")
        self.assertEqual(server.ai_chat({"messages": msgs("oi")}, None)["entity"], "padrão do Home Assistant")
        self.assertNotIn("entity_id", ha.calls("POST", "/core/api/services/ai_task")[-1]["body"])
        self.store.settings["ai_chat"] = "ai_task.texto_apenas"
        server.ai_chat({"messages": msgs("oi")}, None)
        self.assertEqual(ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["entity_id"], "ai_task.texto_apenas")

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

    def test_com_foto_vai_junto_para_a_ia_de_fotos(self):
        """1.69.0: Tirar foto, Escolher fotos ou Escolher arquivo: o arquivo vai junto, pela IA de ler fotos, e some depois."""
        ha = self.fake_ha()
        vistos = []
        def responder(kind, payload):
            for a in payload.get("attachments") or []:
                rel = a["media_content_id"].split("media-source://media_source/local/", 1)[1]
                vistos.append((a["media_content_type"], os.path.isfile(os.path.join(server.MEDIA_ROOT, rel))))
            return "É uma TV de 55 polegadas."
        ha.ai_reply = responder
        self.store.settings["ai_entity"] = "ai_task.google_ai_task"
        self.store.settings["ai_chat"] = "ai_task.texto_apenas"
        jpg = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"\1" * 60).decode()
        pdf = base64.b64encode(b"%PDF-1.4 manual").decode()
        m = msgs("o que é isto?")
        res = server.ai_chat({"messages": m, "anexos": [{"nome": "tv.jpg", "b64": jpg}]}, None)
        self.assertEqual(res["reply"], "É uma TV de 55 polegadas.")
        body = ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]
        self.assertEqual(body["entity_id"], "ai_task.google_ai_task", "com arquivo, a IA de ler fotos")
        self.assertEqual(vistos, [("image/jpeg", True)], "o arquivo existe enquanto a IA lê")
        self.assertIn("Pessoa: [mandou tv.jpg] o que é isto?", body["instructions"])
        self.assertIn("mandou 1 arquivo (foto ou PDF)", body["instructions"])
        self.assertEqual(os.listdir(os.path.join(server.MEDIA_ROOT, server.AI_TMP_REL)), [], "e some depois")
        # sem texto vale (só o PDF); a próxima pergunta vai sem o arquivo
        server.ai_chat({"messages": [{"role": "user", "text": "", "anexos": ["manual.pdf"]}], "anexos": [{"nome": "manual.pdf", "b64": pdf}]}, None)
        self.assertEqual(vistos[-1], ("application/pdf", True), "um PDF também, sem texto")
        ha.ai_reply = lambda kind, payload: "Um ano."
        res = server.ai_chat({"messages": m + [{"role": "assistant", "text": "É uma TV."}, {"role": "user", "text": "e a garantia?"}]}, None)
        self.assertEqual((res["reply"], ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["entity_id"]), ("Um ano.", "ai_task.texto_apenas"),
                         "sem arquivo, a IA para conversar")

    def test_arquivos_que_nao_servem(self):
        with mock.patch.object(server, "AI_MOCK", True), mock.patch.object(server.time, "sleep"):
            jpg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\1" * 60).decode()
            self.assertApiError(400, server.ai_chat, {"messages": msgs("oi"), "anexos": [{"b64": base64.b64encode(b"texto").decode()}]}, None, msg_part="não abriu")
            self.assertApiError(400, server.ai_chat, {"messages": msgs("oi"), "anexos": [{"b64": jpg}] * 5}, None, msg_part="No máximo 4")
            self.assertApiError(400, server.ai_chat, {"messages": msgs("oi"), "anexos": [{"b64": jpg}, {"b64": base64.b64encode(b"%PDF-1").decode()}]}, None, msg_part="um PDF por vez")
            res = server.ai_chat({"messages": msgs("oi"), "anexos": [{"b64": jpg}]}, None)
            self.assertEqual(res["reply"], server.MOCK_CHAT_ARQ)
        self.assertEqual(server.usage_summary()["recent"][0]["images"], 1, "o uso conta o arquivo")

    def test_nao_muda_o_inventario(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"items": [{"name": "X"}]})
        rev = self.store.data["rev"]
        server.ai_chat({"messages": msgs("adicione um sofá")}, None)
        self.assertEqual(self.store.data["rev"], rev)


if __name__ == "__main__":
    unittest.main()
