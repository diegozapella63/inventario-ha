"""Uso da IA no servidor: o dia (usage_day), a cota (is_quota), o registro de cada chamada (record_usage, AiCall),
o resumo da tela (usage_summary), o sensor no Home Assistant (publish_usage_sensor, remove_usage_sensor) e a
pergunta em texto à IA (ai_call_text) com o Home Assistant simulado. Complementa o test_ia.py, sem repetir."""
import json
import os
import time
import unittest
from datetime import datetime
from unittest import mock

from _boot import UnitBase, helpers, server as S
from fake_ha import DEFAULT_STATES, TOKEN

MEIA_NOITE_UTC = 1767225600  # 2026-01-01 00:00 UTC
PADRAO = "padrão do Home Assistant"


def dia(atras=0) -> str:
    return S.usage_day(time.time() - atras * 86400)


def grava_uso(days: dict, recent: list | None = None):
    """Escreve o arquivo de uso direto, sem disparar o sensor em segundo plano."""
    S.write_json_atomic(S.USAGE_FILE, {"days": days, "recent": recent or []})


def uso_salvo() -> dict:
    return S.read_json(S.USAGE_FILE, {}) or {}


class ComHA(UnitBase):
    """Um Home Assistant simulado para a classe toda (subir e parar custa meio segundo), zerado a cada teste."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ha = helpers.FakeHA(media_root=S.MEDIA_ROOT)
        cls.addClassCleanup(cls._ha.stop)

    def setUp(self):
        super().setUp()
        ha = self.ha = self._ha
        with ha.lock:
            ha.requests.clear()
        ha.token, ha.states, ha.ai_error = TOKEN, json.loads(json.dumps(DEFAULT_STATES)), None
        ha.ai_reply = lambda kind, payload: json.dumps({"items": []})
        ha.conversation_reply = lambda payload: '{"erro": "sem_busca"}'
        for p in (mock.patch.object(S, "SUPERVISOR_TOKEN", ha.token), mock.patch.object(S, "HA_API", ha.api), mock.patch.object(S, "HA_WS", ha.ws)):
            p.start()
            self.addCleanup(p.stop)


class Dia(UnitBase):
    def test_sem_fuso_o_dia_vira_as_tres_da_manha_utc(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("TZ", None)
            self.assertEqual(S.usage_day(MEIA_NOITE_UTC + 3 * 3600 - 1), "2025-12-31", "23h59 em Brasília ainda é o dia anterior")
            self.assertEqual(S.usage_day(MEIA_NOITE_UTC + 3 * 3600), "2026-01-01", "meia-noite em Brasília")

    def test_com_fuso_no_ambiente_usa_o_fuso(self):
        antes = os.environ.get("TZ")

        def volta():
            if antes is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = antes
            time.tzset()
        self.addCleanup(volta)
        os.environ["TZ"] = "JST-9"  # UTC+9, sem precisar da base de fusos
        time.tzset()
        self.assertEqual(S.usage_day(MEIA_NOITE_UTC - 5 * 3600), "2026-01-01", "19h UTC de 31/12 já é 1º de janeiro no Japão")

    def test_sem_argumento_e_o_dia_de_agora(self):
        self.assertEqual(S.usage_day(), S.usage_day(time.time()))


class Cota(UnitBase):
    def test_sem_mensagem_nao_e_cota(self):
        for msg in (None, "", 0):
            with self.subTest(msg=msg):
                self.assertFalse(S.is_quota(msg))

    def test_cota_ignora_maiusculas_e_minusculas(self):
        for msg in ("QUOTA EXCEEDED", "Rate Limit hit", "resource_exhausted"):
            with self.subTest(msg=msg):
                self.assertTrue(S.is_quota(msg))

    def test_cota_le_o_texto_de_um_erro(self):
        self.assertTrue(S.is_quota(S.ApiError(502, "O Home Assistant recusou o pedido: 429 Too Many Requests")))

    def test_erros_comuns_nao_sao_cota(self):
        for msg in ("Sem resposta do Home Assistant (timed out).", "500 Internal Server Error", "Entity not found.", "A IA não devolveu resposta."):
            with self.subTest(msg=msg):
                self.assertFalse(S.is_quota(msg))


class RegistroDeChamadas(UnitBase):
    def test_tokens_estimados_por_quatro_caracteres(self):
        S.record_usage("foto", "", 30, 10, 1, 0.5, "ok")
        self.assertEqual(uso_salvo()["recent"][0]["tokens"], 10)
        self.assertEqual(uso_salvo()["days"][dia()]["tokens"], 10)

    def test_erros_contam_formato_sem_busca_e_erro_mas_nao_ok_nem_cota(self):
        for result in ("ok", "cota", "formato", "sem_busca", "erro"):
            S.record_usage("busca", "", 1, 1, 0, 0.1, result)
        d = uso_salvo()["days"][dia()]
        self.assertEqual((d["calls"], d["errors"], d["quota"]), (5, 3, 1))

    def test_segundos_arredondados_a_um_decimo(self):
        S.record_usage("foto", "", 1, 1, 0, 2.345, "ok")
        S.record_usage("foto", "", 1, 1, 0, 1.0, "ok")
        u = uso_salvo()
        self.assertEqual(u["recent"][1]["seconds"], 2.3)
        self.assertEqual(u["days"][dia()]["seconds"], 3.3)

    def test_ultima_chamada_vem_primeiro(self):
        S.record_usage("foto", "", 1, 1, 0, 0.1, "ok")
        S.record_usage("fala", "", 1, 1, 0, 0.1, "erro")
        self.assertEqual([(r["kind"], r["result"]) for r in uso_salvo()["recent"]], [("fala", "erro"), ("foto", "ok")])

    def test_entidade_vazia_fica_como_padrao_do_home_assistant(self):
        S.record_usage("foto", "", 1, 1, 0, 0.1, "ok")
        u = uso_salvo()
        self.assertEqual(u["recent"][0]["entity"], PADRAO)
        self.assertEqual(u["days"][dia()]["entities"], {PADRAO: 1})

    def test_conta_por_entidade_escolhida(self):
        S.record_usage("foto", "ai_task.google_ai_task", 1, 1, 1, 0.1, "ok")
        S.record_usage("busca", "conversation.google_generative_ai", 1, 1, 0, 0.1, "ok")
        S.record_usage("foto", "ai_task.google_ai_task", 1, 1, 1, 0.1, "ok")
        self.assertEqual(uso_salvo()["days"][dia()]["entities"], {"ai_task.google_ai_task": 2, "conversation.google_generative_ai": 1})

    def test_imagens_somadas_no_dia(self):
        S.record_usage("foto", "", 1, 1, 1, 0.1, "ok")
        S.record_usage("catalogo", "", 1, 1, 1, 0.1, "ok")
        S.record_usage("fala", "", 1, 1, 0, 0.1, "ok")
        self.assertEqual(uso_salvo()["days"][dia()]["images"], 2)

    def test_cada_chamada_guarda_a_hora_com_fuso(self):
        S.record_usage("foto", "", 1, 1, 0, 0.1, "ok")
        at = datetime.fromisoformat(uso_salvo()["recent"][0]["at"])
        self.assertIsNotNone(at.tzinfo)
        self.assertLess(abs(at.timestamp() - time.time()), 60)

    def test_soma_no_dia_que_ja_existia(self):
        grava_uso({dia(): {"calls": 5, "tokens": 100, "kinds": {"foto": 5}, "entities": {PADRAO: 5}}})
        S.record_usage("foto", "", 40, 0, 1, 0.1, "ok")
        d = uso_salvo()["days"][dia()]
        self.assertEqual((d["calls"], d["tokens"], d["kinds"], d["entities"]), (6, 110, {"foto": 6}, {PADRAO: 6}))


class ChamadaMedida(UnitBase):
    def ultima(self) -> dict:
        return S.usage_summary()["recent"][0]

    def test_chamada_sem_erro_registra_ok(self):
        with S.AiCall("foto", "ai_task.x", "prompt") as c:
            c.answer("resposta")
        self.assertEqual((self.ultima()["result"], self.ultima()["kind"], self.ultima()["entity"]), ("ok", "foto", "ai_task.x"))

    def test_erro_comum_registra_erro_e_repassa_o_mesmo_erro(self):
        erro = S.ApiError(504, "Sem resposta do Home Assistant (timed out).")
        with self.assertRaises(S.ApiError) as cm:
            with S.AiCall("catalogo", "", "p"):
                raise erro
        self.assertIs(cm.exception, erro)
        self.assertEqual(self.ultima()["result"], "erro")

    def test_cota_reconhecida_em_erro_que_nao_e_do_app(self):
        with self.assertRaises(RuntimeError):
            with S.AiCall("fala", "", "p"):
                raise RuntimeError("Quota exceeded for model")
        self.assertEqual(self.ultima()["result"], "cota")

    def test_resultado_marcado_vale_mais_que_o_erro(self):
        with self.assertRaises(S.ApiError):
            with S.AiCall("busca", "", "p") as c:
                c.result = "sem_busca"
                raise S.ApiError(502, "429 Too Many Requests")
        self.assertEqual(self.ultima()["result"], "sem_busca", "não conta como cota quando já se sabe o motivo")

    def test_tempo_da_chamada_medido(self):
        tempos, real = iter([1000.0, 1003.26]), time.time
        with mock.patch.object(S.time, "time", side_effect=lambda: next(tempos, None) or real()):
            with S.AiCall("foto", "", "p"):
                pass
        self.assertEqual(self.ultima()["seconds"], 3.3)

    def test_tokens_somam_instrucoes_e_resposta_em_texto(self):
        with S.AiCall("foto", "", "a" * 100) as c:
            c.answer("b" * 20)
        self.assertEqual(self.ultima()["tokens"], 30)

    def test_resposta_em_objeto_conta_acentos_como_um_caractere(self):
        with S.AiCall("foto", "", "") as c:
            c.answer({"n": "ção"})  # '{"n": "ção"}' tem 12 caracteres; escapado teria 24
        self.assertEqual(self.ultima()["tokens"], 3)

    def test_resposta_que_nao_vira_json_conta_zero(self):
        with S.AiCall("foto", "", "a" * 40) as c:
            c.answer({"x": object()})
        self.assertEqual(self.ultima()["tokens"], 10, "só as instruções")

    def test_sem_resposta_conta_so_as_instrucoes(self):
        with self.assertRaises(S.ApiError):
            with S.AiCall("foto", "", "a" * 80):
                raise S.ApiError(502, "falhou")
        self.assertEqual(self.ultima()["tokens"], 20)

    def test_instrucoes_vazias_nao_quebram(self):
        with S.AiCall("foto", "", None) as c:
            c.answer("")
        self.assertEqual(self.ultima()["tokens"], 0)

    def test_imagens_da_chamada_vao_para_o_registro(self):
        with S.AiCall("catalogo", "", "p", images=1):
            pass
        self.assertEqual(self.ultima()["images"], 1)
        self.assertEqual(S.usage_summary()["today"]["images"], 1)

    def test_uso_corrompido_nao_derruba_a_chamada(self):
        helpers.write_file(S.USAGE_FILE, "{quebrado")
        with S.AiCall("foto", "", "p") as c:
            c.answer("ok")
            resultado = "chegou ao fim"
        self.assertEqual(resultado, "chegou ao fim")


class Resumo(UnitBase):
    def test_sem_uso_tudo_zerado(self):
        u = S.usage_summary()
        zerado = {"calls": 0, "errors": 0, "quota": 0, "tokens": 0, "images": 0, "seconds": 0, "kinds": {}, "entities": {}}
        self.assertEqual((u["today"], u["week"], u["month"]), (zerado, zerado, zerado))
        self.assertEqual((u["recent"], u["since"]), ([], None))
        self.assertEqual([d["calls"] for d in u["days"]], [0] * 7)

    def test_sete_dias_em_ordem_terminando_hoje(self):
        self.assertEqual([d["day"] for d in S.usage_summary()["days"]], [dia(n) for n in range(6, -1, -1)])

    def test_semana_conta_seis_dias_atras_mas_nao_sete(self):
        grava_uso({dia(6): {"calls": 2}, dia(7): {"calls": 5}, dia(): {"calls": 1}})
        self.assertEqual(S.usage_summary()["week"]["calls"], 3)

    def test_mes_so_do_mes_de_hoje(self):
        hoje = dia()
        grava_uso({"2020-01-15": {"calls": 9}, hoje: {"calls": 2}, f"{hoje[:7]}-01": {"calls": 1}})
        esperado = 2 if hoje.endswith("-01") else 3
        self.assertEqual(S.usage_summary()["month"]["calls"], esperado)

    def test_dias_sem_chamadas_aparecem_com_zero(self):
        grava_uso({dia(): {"calls": 4, "errors": 1, "quota": 1}})
        dias = S.usage_summary()["days"]
        self.assertEqual(dias[0], {"day": dia(6), "calls": 0, "errors": 0, "quota": 0})
        self.assertEqual(dias[-1], {"day": dia(), "calls": 4, "errors": 1, "quota": 1})

    def test_por_tipo_soma_os_dias_da_semana(self):
        grava_uso({dia(2): {"calls": 3, "kinds": {"foto": 2, "fala": 1}}, dia(): {"calls": 2, "kinds": {"foto": 1, "busca": 1}}})
        u = S.usage_summary()
        self.assertEqual(u["week"]["kinds"], {"foto": 3, "fala": 1, "busca": 1})
        self.assertEqual(u["today"]["kinds"], {"foto": 1, "busca": 1})

    def test_por_entidade_soma_os_dias_da_semana(self):
        grava_uso({dia(1): {"calls": 1, "entities": {PADRAO: 1}}, dia(): {"calls": 2, "entities": {PADRAO: 1, "ai_task.x": 1}}})
        self.assertEqual(S.usage_summary()["week"]["entities"], {PADRAO: 2, "ai_task.x": 1})

    def test_desde_e_o_dia_mais_antigo_guardado(self):
        grava_uso({dia(): {"calls": 1}, "2026-03-04": {"calls": 1}, "2025-12-31": {"calls": 1}})
        self.assertEqual(S.usage_summary()["since"], "2025-12-31")

    def test_dia_gravado_sem_alguns_campos(self):
        grava_uso({dia(): {"calls": 2}})
        t = S.usage_summary()["today"]
        self.assertEqual((t["calls"], t["errors"], t["tokens"], t["kinds"]), (2, 0, 0, {}))

    def test_segundos_somados_sem_casas_a_mais(self):
        grava_uso({dia(1): {"calls": 1, "seconds": 0.1}, dia(): {"calls": 1, "seconds": 0.2}})
        self.assertEqual(S.usage_summary()["week"]["seconds"], 0.3)

    def test_arquivo_sem_dias_nem_chamadas(self):
        S.write_json_atomic(S.USAGE_FILE, {})
        u = S.usage_summary()
        self.assertEqual((u["today"]["calls"], u["recent"], u["since"]), (0, [], None))


class SensorDeUso(ComHA):
    def posts(self):
        return self.ha.calls("POST", "/core/api/states/" + S.USAGE_SENSOR)

    def test_atributos_do_sensor(self):
        hoje, ontem = dia(), dia(1)
        grava_uso({hoje: {"calls": 3, "errors": 1, "quota": 1, "tokens": 250, "images": 2, "kinds": {"foto": 2, "fala": 1}},
                   ontem: {"calls": 4}},
                  [{"at": "2026-01-10T10:00:00-03:00", "kind": "foto", "entity": PADRAO, "result": "ok", "seconds": 1, "tokens": 1, "images": 1}])
        self.store.settings["ha_sensors"] = True
        S.publish_usage_sensor()
        st = self.ha.state(S.USAGE_SENSOR)
        a = st["attributes"]
        self.assertEqual(st["state"], "3")
        self.assertEqual((a["friendly_name"], a["icon"], a["state_class"]), ("InventarIA: chamadas de IA hoje", "mdi:robot-outline", "total_increasing"))
        self.assertEqual((a["tokens_texto_estimados"], a["imagens"], a["ultimos_7_dias"]), (250, 2, 7))
        self.assertEqual(a["este_mes"], 7 if ontem[:7] == hoje[:7] else 3)
        self.assertEqual(a["ultima_chamada"], "2026-01-10T10:00:00-03:00")

    def test_sensor_sem_chamadas_fica_zerado(self):
        self.store.settings["ha_sensors"] = True
        S.publish_usage_sensor()
        st = self.ha.state(S.USAGE_SENSOR)
        self.assertEqual(st["state"], "0")
        self.assertIsNone(st["attributes"]["ultima_chamada"])
        self.assertEqual(st["attributes"]["por_tipo"], {})

    def test_sensor_marca_o_dia_publicado(self):
        self.store.settings["ha_sensors"] = True
        S.publish_usage_sensor()
        self.assertEqual(S._usage_sensor["day"], S.usage_day())

    def test_sensores_desligados_nem_chamam_o_home_assistant(self):
        S.publish_usage_sensor()
        self.assertEqual(self.ha.calls(), [])

    def test_ia_desligada_nem_chama_o_home_assistant(self):
        self.store.settings.update(ha_sensors=True, ai=False)
        S.publish_usage_sensor()
        self.assertEqual(self.ha.calls(), [])

    def test_ia_simulada_nao_publica(self):
        self.store.settings["ha_sensors"] = True
        with mock.patch.object(S, "AI_MOCK", True):
            S.publish_usage_sensor()
        self.assertEqual(self.posts(), [])

    def test_remover_manda_delete_e_esquece_o_dia(self):
        self.store.settings["ha_sensors"] = True
        S.publish_usage_sensor()
        S.remove_usage_sensor()
        self.assertEqual(len(self.ha.calls("DELETE", "/core/api/states/" + S.USAGE_SENSOR)), 1)
        self.assertIsNone(S._usage_sensor["day"], "na próxima vez publica de novo")

    def test_remover_sem_acesso_ao_home_assistant_nao_tenta(self):
        with mock.patch.object(S, "SUPERVISOR_TOKEN", None):
            S.remove_usage_sensor()
        self.assertEqual(self.ha.calls(), [])

    def test_remover_com_ia_simulada_nao_tenta(self):
        with mock.patch.object(S, "AI_MOCK", True):
            S.remove_usage_sensor()
        self.assertEqual(self.ha.calls(), [])

    def test_remover_com_home_assistant_fora_do_ar_nao_quebra(self):
        S._usage_sensor["day"] = S.usage_day()
        with mock.patch.object(S, "HA_API", f"http://127.0.0.1:{helpers.free_port()}/core/api"):
            S.remove_usage_sensor()
        self.assertIsNone(S._usage_sensor["day"])


class PerguntaEmTexto(ComHA):
    def ultimo(self, prefixo="/core/api/services/"):
        return self.ha.calls("POST", prefixo)[-1]

    def test_tarefa_de_ia_devolve_o_texto(self):
        self.ha.ai_reply = lambda kind, body: "resposta da IA"
        self.assertEqual(S.ai_call_text("InventarIA: teste", "instruções", ""), "resposta da IA")
        body = self.ultimo("/core/api/services/ai_task/generate_data")["body"]
        self.assertEqual(body, {"task_name": "InventarIA: teste", "instructions": "instruções"}, "sem escolha, sem entity_id")

    def test_tarefa_escolhida_vai_no_pedido(self):
        S.ai_call_text("InventarIA: teste", "x", "ai_task.google_ai_task")
        self.assertEqual(self.ultimo()["body"]["entity_id"], "ai_task.google_ai_task")

    def test_pedido_em_texto_vai_sem_anexos(self):
        S.ai_call_text("InventarIA: teste", "x", "ai_task.google_ai_task")
        self.assertNotIn("attachments", self.ultimo()["body"])

    def test_resposta_em_objeto_volta_como_objeto(self):
        self.ha.ai_reply = lambda kind, body: {"items": [{"name": "Banco"}]}
        self.assertEqual(S.ai_call_text("t", "x", ""), {"items": [{"name": "Banco"}]})

    def test_resposta_vazia_devolve_none(self):
        self.ha.ai_reply = lambda kind, body: None
        self.assertIsNone(S.ai_call_text("t", "x", ""))

    def test_erro_do_home_assistant_vira_502_com_a_mensagem(self):
        self.ha.ai_error = (500, "Erro ao gerar dados")
        self.assertApiError(502, S.ai_call_text, "t", "x", "", msg_part="O Home Assistant recusou o pedido: Erro ao gerar dados")

    def test_assistente_de_conversa_recebe_o_texto_e_o_agente(self):
        self.ha.conversation_reply = lambda body: '{"items": []}'
        self.assertEqual(S.ai_call_text("t", "liste os itens", "conversation.google_generative_ai"), '{"items": []}')
        call = self.ultimo("/core/api/services/conversation/process")
        self.assertEqual(call["body"], {"text": "liste os itens", "agent_id": "conversation.google_generative_ai"})
        self.assertEqual(self.ha.calls("POST", "/core/api/services/ai_task"), [], "não usa a tarefa de IA")

    def test_assistente_de_conversa_sem_fala_devolve_texto_vazio(self):
        self.ha.conversation_reply = lambda body: ""
        self.assertEqual(S.ai_call_text("t", "x", "conversation.google_generative_ai"), "")

    def test_erro_do_assistente_resumido_numa_linha(self):
        self.ha.conversation_reply = lambda body: "ERRO:" + "não   entendi\n" * 40
        e = self.assertApiError(502, S.ai_call_text, "t", "x", "conversation.google_generative_ai", msg_part="respondeu com erro: não entendi não")
        detalhe = e.msg.split("respondeu com erro: ", 1)[1]
        self.assertEqual(len(detalhe), 160)
        self.assertNotIn("\n", detalhe)
        self.assertNotIn("  ", detalhe)

    def test_erro_do_home_assistant_no_assistente_de_conversa(self):
        self.ha.ai_error = (500, "Agente indisponível")
        self.assertApiError(502, S.ai_call_text, "t", "x", "conversation.google_generative_ai", msg_part="Agente indisponível")

    def test_home_assistant_fora_do_ar_da_504(self):
        with mock.patch.object(S, "HA_API", f"http://127.0.0.1:{helpers.free_port()}/core/api"):
            self.assertApiError(504, S.ai_call_text, "t", "x", "", msg_part="O Home Assistant não respondeu")


class PerguntaSemHomeAssistant(UnitBase):
    def test_sem_acesso_a_api_da_503(self):
        self.assertApiError(503, S.ai_call_text, "t", "x", "", msg_part="não tem acesso à API do Home Assistant")


if __name__ == "__main__":
    unittest.main()
