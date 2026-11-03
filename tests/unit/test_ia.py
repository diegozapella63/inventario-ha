"""IA do Home Assistant: instruções, resposta, itens, estado, leitura de foto e do que foi falado, e o uso da IA."""
import json
import os
import time
import unittest
from unittest import mock

from _boot import UnitBase, helpers, server as S


class Instrucoes(UnitBase):
    def test_uma_foto_um_item(self):
        p = S.ai_prompt("single", None, "")
        self.assertIn("exatamente 1 item", p)
        self.assertIn("eletronicos (Eletrônicos)", p)
        self.assertNotIn("Itens já cadastrados", p)

    def test_catalogo_com_comodo_lista_os_itens_ja_cadastrados(self):
        p = S.ai_prompt("multi", self.store.room("sala"), "são almofadas")
        self.assertIn("até 25", p)
        self.assertIn("Cômodo: Sala de estar.", p)
        self.assertIn("Itens já cadastrados neste cômodo: Smart TV 55 polegadas", p, "os mais valiosos primeiro")
        self.assertIn("Dica de quem está cadastrando: são almofadas", p)

    def test_zonas_so_quando_ligadas(self):
        p = S.ai_prompt("multi", self.store.room("sala"), "")
        self.assertNotIn('"zone"', p)
        self.assertNotIn("Zonas já usadas", p)
        self.store.settings["zones"] = True
        p = S.ai_prompt("multi", self.store.room("sala"), "")
        self.assertIn('"zone"', p)
        self.assertIn("Zonas já usadas neste cômodo (prefira uma delas): Estante; Parede; Piso; Rack; Sofá.", p)

    def test_fala_lista_os_comodos_e_o_valor_dito_vale_mais(self):
        p = S.ai_prompt("voice", None, "", "sofá dois mil reais")
        self.assertIn("use exatamente esse valor", p)
        self.assertIn("sala = Sala de estar; cozinha = Cozinha", p)
        self.assertTrue(p.endswith("O que a pessoa falou:\nsofá dois mil reais"))

    def test_categorias_da_casa_entram_nas_instrucoes(self):
        self.store.create_cat({"name": "Oficina"})
        self.assertIn("oficina (Oficina)", S.ai_prompt("single", None, ""))
        self.assertIn("oficina (Oficina)", S.web_prompt("furadeira", ""))


class RespostaDaIA(UnitBase):
    def test_json_puro_com_cerca_ou_com_texto_em_volta(self):
        casos = ['{"items": [1]}', '```json\n{"items": [1]}\n```', 'Claro! Aqui está:\n{"items": [1]}\nEspero ter ajudado.',
                 '```\n{"items": [1]}```', 'texto [1, 2] fim']
        esperado = [{"items": [1]}] * 4 + [[1, 2]]
        for raw, exp in zip(casos, esperado):
            with self.subTest(raw=raw):
                self.assertEqual(S.extract_json(raw), exp)
        self.assertEqual(S.extract_json({"items": []}), {"items": []})

    def test_resposta_sem_json(self):
        e = self.assertApiError(502, S.extract_json, "Não consigo ver a imagem.")
        self.assertEqual(e.extra["raw"], "Não consigo ver a imagem.", "a resposta vai junto para a tela mostrar")
        self.assertApiError(502, S.extract_json, "{quebrado: }")
        self.assertApiError(502, S.extract_json, None)

    def test_itens_limpos(self):
        parsed = {"items": [
            {"name": " Sofá ", "details": "cinza", "cat": "moveis", "qty": 2, "value": "1.500", "zone": "Sala", "existing": "Sofá de 3 lugares cinza-azulado", "confidence": "Média"},
            {"name": "", "value": 10},
            "texto",
            {"name": "Vaso", "cat": "inventada", "value": "caro", "existing": "Não existe aqui", "confidence": "talvez"},
        ]}
        out = S.clean_ai_items(parsed, self.store.room("sala"))
        self.assertEqual(len(out), 2)
        a, b = out
        self.assertEqual((a["name"], a["qty"], a["value"], a["cat"], a["existing"], a["confidence"]), ("Sofá", "2", 1500, "moveis", "Sofá de 3 lugares cinza-azulado", "media"))
        self.assertEqual((b["cat"], b["value"], b["existing"], b["confidence"], b["qty"]), ("outros", 0, "", "media", "1"))

    def test_existing_so_vale_para_o_comodo(self):
        out = S.clean_ai_items({"items": [{"name": "X", "existing": "Sofá de 3 lugares cinza-azulado"}]}, self.store.room("cozinha"))
        self.assertEqual(out[0]["existing"], "")
        out = S.clean_ai_items({"items": [{"name": "X", "existing": "Sofá de 3 lugares cinza-azulado"}]}, None)
        self.assertEqual(out[0]["existing"], "")

    def test_formatos_aceitos(self):
        self.assertEqual(len(S.clean_ai_items([{"name": "A"}, {"name": "B"}], None)), 2, "lista solta")
        self.assertEqual(len(S.clean_ai_items({"name": "Um só"}, None)), 1, "um item solto")
        self.assertEqual(len(S.clean_ai_items({"items": [{"name": f"I{i}"} for i in range(40)]}, None)), 25, "até 25")
        self.assertApiError(502, S.clean_ai_items, {"resposta": "nada"}, None)
        out = S.clean_ai_items({"items": [{"name": "x" * 300, "details": "d" * 2000, "qty": "q" * 50, "zone": "z" * 200}]}, None)[0]
        self.assertEqual((len(out["name"]), len(out["details"]), len(out["qty"]), len(out["zone"])), (200, 1000, 30, 120))


class EstadoDaIA(UnitBase):
    def test_sem_acesso_ao_home_assistant(self):
        st = S.ai_status()
        self.assertEqual((st["ready"], st["reason"]), (False, "no_api"))

    def test_lista_tarefas_e_assistentes(self):
        ha = self.fake_ha()
        st = S.ai_status()
        self.assertTrue(st["ready"])
        self.assertEqual([e["id"] for e in st["entities"]], ["ai_task.google_ai_task", "ai_task.texto_apenas"], "as que leem fotos primeiro")
        self.assertEqual([e["attachments"] for e in st["entities"]], [True, False])
        self.assertEqual([a["id"] for a in st["agents"]], ["conversation.google_generative_ai"], "sem o assistente embutido do Home Assistant")
        self.store.settings["ai_entity"] = "ai_task.texto_apenas"
        st = S.ai_status()
        self.assertEqual((st["ready"], st["reason"]), (False, "no_vision"))
        ha.states = [s for s in ha.states if not s["entity_id"].startswith("ai_task.")]
        self.store.settings["ai_entity"] = ""
        self.assertEqual(S.ai_status()["reason"], "no_entity")

    def test_home_assistant_recusa(self):
        ha = self.fake_ha()
        ha.token = "outro"
        st = S.ai_status()
        self.assertEqual((st["ready"], st["reason"]), (False, "error"))
        self.assertIn("recusou", st["message"])

    def test_ia_desligada(self):
        self.store.settings["ai"] = False
        for fn, body in ((S.ai_identify, {"file": "sala-1.jpg"}), (S.ai_from_speech, {"text": "sofá"}), (S.web_job_start, {"name": "x"})):
            with self.subTest(fn=fn.__name__):
                self.assertApiError(409, fn, body, msg_part="IA está desligada")


class LerFoto(UnitBase):
    def test_le_pelo_home_assistant_com_a_foto_em_media(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"items": [{"name": "Poltrona", "cat": "moveis", "value": 700, "confidence": "alta"}]})
        res = S.ai_identify({"file": "sala-1.jpg", "mode": "single", "room": "sala", "hint": "é de couro"})
        self.assertEqual(res["items"][0]["name"], "Poltrona")
        self.assertEqual(res["entity"], "padrão do Home Assistant")
        call = ha.calls("POST", "/core/api/services/ai_task/generate_data")[-1]
        self.assertEqual(call["attachments_present"], [True], "a foto estava em /media enquanto a IA lia")
        self.assertNotIn("entity_id", call["body"], "sem escolha, usa a IA preferida do Home Assistant")
        self.assertIn("é de couro", call["body"]["instructions"])
        self.assertEqual(os.listdir(os.path.join(S.MEDIA_ROOT, S.AI_TMP_REL)), [], "a cópia em /media é apagada")

    def test_ia_escolhida(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda k, p: {"items": [{"name": "A"}, {"name": "B"}]}
        self.store.settings["ai_entity"] = "ai_task.google_ai_task"
        res = S.ai_identify({"file": "sala-1.jpg", "mode": "multi"})
        self.assertEqual(len(res["items"]), 2)
        self.assertEqual(ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["entity_id"], "ai_task.google_ai_task")

    def test_falhas(self):
        ha = self.fake_ha()
        self.assertApiError(400, S.ai_identify, {"file": "nao-existe.jpg"}, msg_part="Envie uma foto")
        ha.ai_reply = lambda k, p: "Desculpe, não consigo."
        e = self.assertApiError(502, S.ai_identify, {"file": "sala-1.jpg"})
        self.assertIn("raw", e.extra)
        ha.ai_error = (500, "429 RESOURCE_EXHAUSTED quota")
        self.assertApiError(502, S.ai_identify, {"file": "sala-1.jpg"}, msg_part="cota da IA acabou")
        ha.ai_reply = lambda k, p: None
        ha.ai_error = None
        self.assertApiError(502, S.ai_identify, {"file": "sala-1.jpg"}, msg_part="não devolveu")
        self.assertEqual(os.listdir(os.path.join(S.MEDIA_ROOT, S.AI_TMP_REL)), [], "mesmo com erro, a cópia é apagada")
        resultados = [r["result"] for r in S.usage_summary()["recent"]]
        self.assertEqual(resultados[:3], ["formato", "cota", "formato"], "o uso registra cada tipo de falha")

    def test_simulado(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep"):
            res = S.ai_identify({"file": "sala-1.jpg", "mode": "multi"})
            self.assertEqual(len(res["items"]), 3)
            self.assertEqual(len(S.ai_identify({"file": "sala-1.jpg", "mode": "single"})["items"]), 1)


class Falado(UnitBase):
    def test_itens_e_comodo_do_que_foi_falado(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda k, p: '{"room": "cozinha", "items": [{"name": "Batedeira", "value": 300, "cat": "cozinha"}]}'
        res = S.ai_from_speech({"text": "na cozinha tem uma batedeira de 300 reais"})
        self.assertEqual(res["room"], "cozinha")
        self.assertEqual(res["items"][0]["name"], "Batedeira")
        self.assertEqual(ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["task_name"], "InventarIA: itens falados")
        ha.ai_reply = lambda k, p: '{"room": "nao-existe", "items": [{"name": "X"}]}'
        self.assertEqual(S.ai_from_speech({"text": "x"})["room"], "")
        self.assertApiError(400, S.ai_from_speech, {"text": "  "})

    def test_assistente_de_conversa(self):
        ha = self.fake_ha()
        ha.conversation_reply = lambda body: '{"items": [{"name": "Banco"}]}'
        self.store.settings["ai_entity"] = "conversation.google_generative_ai"
        self.assertEqual(S.ai_from_speech({"text": "um banco"})["items"][0]["name"], "Banco")
        ha.conversation_reply = lambda body: "ERRO:Não entendi"
        self.assertApiError(502, S.ai_from_speech, {"text": "um banco"}, msg_part="respondeu com erro")


class UsoDaIA(UnitBase):
    def test_conta_chamadas_tokens_e_resultados(self):
        with S.AiCall("foto", "ai_task.x", "a" * 400, images=1) as c:
            c.answer({"items": []})
        with self.assertRaises(S.ApiError):
            with S.AiCall("catalogo", "", "b" * 40) as c:
                raise S.ApiError(502, "429 Too Many Requests")
        with self.assertRaises(S.ApiError):
            with S.AiCall("busca", "", "c") as c:
                raise S.ApiError(502, "falhou")
        with S.AiCall("fala", "", "d") as c:
            c.result = "formato"
        u = S.usage_summary()
        self.assertEqual((u["today"]["calls"], u["today"]["errors"], u["today"]["quota"], u["today"]["images"]), (4, 2, 1, 1))
        self.assertEqual(u["today"]["kinds"], {"foto": 1, "catalogo": 1, "busca": 1, "fala": 1})
        self.assertEqual(u["today"]["entities"]["padrão do Home Assistant"], 3)
        self.assertEqual([r["result"] for r in u["recent"]], ["formato", "erro", "cota", "ok"])
        self.assertEqual(u["recent"][-1]["tokens"], round((400 + len('{"items": []}')) / 4))
        self.assertEqual(len(u["days"]), 7)
        self.assertEqual(u["days"][-1]["day"], S.usage_day())
        self.assertEqual(u["week"]["calls"], 4)
        self.assertEqual(u["month"]["calls"], 4)
        self.assertEqual(u["sensor"], "sensor.inventaria_ia_hoje")

    def test_guarda_120_dias_e_40_chamadas(self):
        u = {"days": {f"2025-{m:02d}-{d:02d}": {"calls": 1} for m in range(1, 7) for d in range(1, 29)}}
        S.write_json_atomic(S.USAGE_FILE, u)
        for _ in range(45):
            S.record_usage("foto", "", 10, 10, 0, 0.1, "ok")
        salvo = S.read_json(S.USAGE_FILE)
        self.assertEqual(len(salvo["days"]), 120)
        self.assertIn(S.usage_day(), salvo["days"])
        self.assertEqual(len(salvo["recent"]), 40)
        self.assertEqual(len(S.usage_summary()["recent"]), 12, "a tela mostra as 12 últimas")

    def test_cota(self):
        for msg in ("Error 429", "Quota exceeded", "RESOURCE_EXHAUSTED", "rate limit reached"):
            self.assertTrue(S.is_quota(msg))
        self.assertFalse(S.is_quota("timeout"))

    def test_dia_no_horario_de_brasilia(self):
        meia_noite_utc = 1767225600  # 2026-01-01 00:00 UTC = 31/12 21h em Brasília
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TZ", None)
            self.assertEqual(S.usage_day(meia_noite_utc), "2025-12-31")


class SensorNoHomeAssistant(UnitBase):
    def test_so_com_a_opcao_ligada(self):
        ha = self.fake_ha()
        S.publish_usage_sensor()
        self.assertIsNone(ha.state(S.USAGE_SENSOR), "vem desligado")
        self.store.settings["ha_sensors"] = True
        with S.AiCall("foto", "", "x") as c:
            c.answer("y")
        time.sleep(0.3)
        st = ha.state(S.USAGE_SENSOR)
        self.assertEqual(st["state"], "1")
        a = st["attributes"]
        self.assertEqual((a["erros"], a["cota_excedida"], a["por_tipo"], a["unit_of_measurement"]), (0, 0, {"foto": 1}, "chamadas"))
        self.store.settings["ai"] = False
        S.publish_usage_sensor()
        self.assertEqual(ha.state(S.USAGE_SENSOR)["state"], "1", "com a IA desligada não atualiza")
        S.remove_usage_sensor()
        self.assertIsNone(ha.state(S.USAGE_SENSOR))
        S.remove_usage_sensor()  # já não existia: sem erro

    def test_falha_do_home_assistant_nao_quebra_a_chamada(self):
        ha = self.fake_ha()
        self.store.settings["ha_sensors"] = True
        ha.token = "outro"
        S.publish_usage_sensor()
        self.assertEqual(S._usage_sensor["day"], S.usage_day())


if __name__ == "__main__":
    unittest.main()
