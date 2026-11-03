"""Configuração da IA no servidor: as IAs do Home Assistant (ai_entities), o estado mostrado em Integrações (ai_status),
as opções da casa (ai_enabled, zones_enabled, sensors_enabled, need_ai_on, search_entity), a leitura de foto pelo
Home Assistant simulado (ai_identify) e as rotas de configuração (r_settings_get, r_settings_put) com um pedido falso.
Complementa o test_ia.py e o integration/test_api.py, sem repetir o que eles já conferem."""
import json
import os
import unittest
from unittest import mock

from _boot import UnitBase, helpers, server as S
from fake_ha import DEFAULT_STATES, TOKEN

SOFA = "Sofá de 3 lugares cinza-azulado"
GOOGLE = "ai_task.google_ai_task"
SO_TEXTO = "ai_task.texto_apenas"
GEMINI = "conversation.google_generative_ai"


def tarefa(eid, nome=None, recursos=None, estado="unknown"):
    attrs = {} if nome is None else {"friendly_name": nome}
    if recursos is not None:
        attrs["supported_features"] = recursos
    return {"entity_id": eid, "state": estado, "attributes": attrs}


def pasta_temporaria() -> list[str]:
    d = os.path.join(S.MEDIA_ROOT, S.AI_TMP_REL)
    return os.listdir(d) if os.path.isdir(d) else []


def ha_fora_do_ar():
    return mock.patch.object(S, "HA_API", f"http://127.0.0.1:{helpers.free_port()}/core/api")


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

    def pedidos_ia(self):
        return self.ha.calls("POST", "/core/api/services/ai_task/generate_data")


class Pedido:
    """O que as rotas de configuração usam do Handler: read_body() e send_json()."""

    def __init__(self, body=None):
        self.body = {} if body is None else body
        self.status, self.resposta = None, None

    def read_body(self):
        return self.body

    def send_json(self, obj, status=200):
        self.status, self.resposta = status, json.loads(json.dumps(obj, ensure_ascii=False))


# ---------------------------------------------------------------------------- IAs do Home Assistant

class Entidades(ComHA):
    def test_tarefas_que_leem_fotos_vem_primeiro_e_depois_por_nome(self):
        self.ha.states += [tarefa("ai_task.anthropic", "Anthropic", 2), tarefa("ai_task.ollama", "Ollama", 0)]
        tasks, _ = S.ai_entities()
        self.assertEqual([t["id"] for t in tasks], ["ai_task.anthropic", GOOGLE, SO_TEXTO, "ai_task.ollama"])

    def test_ordem_por_nome_ignora_maiusculas(self):
        self.ha.states = [tarefa("ai_task.b", "Beta", 2), tarefa("ai_task.a", "alfa", 2)]
        self.assertEqual([t["name"] for t in S.ai_entities()[0]], ["alfa", "Beta"])

    def test_sem_nome_usa_o_id(self):
        self.ha.states = [tarefa("ai_task.sem_nome", recursos=2), tarefa("conversation.sem_nome")]
        tasks, agents = S.ai_entities()
        self.assertEqual((tasks[0]["name"], agents[0]["name"]), ("ai_task.sem_nome", "conversation.sem_nome"))

    def test_le_fotos_pelo_recurso_de_anexos(self):
        casos = {2: True, 3: True, 6: True, 1: False, 4: False, 0: False, None: False}
        self.ha.states = [tarefa(f"ai_task.r{n}", f"R{n}", r) for n, r in enumerate(casos)]
        lidas = {t["id"]: t["attachments"] for t in S.ai_entities()[0]}
        for n, (recursos, esperado) in enumerate(casos.items()):
            with self.subTest(recursos=recursos):
                self.assertEqual(lidas[f"ai_task.r{n}"], esperado)

    def test_estado_da_tarefa_vem_junto(self):
        self.ha.states = [tarefa("ai_task.fora", "Fora do ar", 2, estado="unavailable")]
        self.assertEqual(S.ai_entities()[0][0]["state"], "unavailable")

    def test_estado_sem_atributos_nao_quebra(self):
        self.ha.states = [{"entity_id": "ai_task.cru"}]
        self.assertEqual(S.ai_entities()[0], [{"id": "ai_task.cru", "name": "ai_task.cru", "attachments": False, "state": None}])

    def test_assistentes_em_ordem_de_nome(self):
        self.ha.states += [tarefa("conversation.zeta", "Zeta"), tarefa("conversation.anthropic", "anthropic")]
        self.assertEqual([a["name"] for a in S.ai_entities()[1]], ["anthropic", "Google Generative AI", "Zeta"])

    def test_outras_entidades_ficam_de_fora(self):
        tasks, agents = S.ai_entities()
        ids = [e["id"] for e in tasks + agents]
        self.assertTrue(all(i.startswith(("ai_task.", "conversation.")) for i in ids), ids)
        self.assertNotIn("light.sala", ids)
        self.assertNotIn("stt.faster_whisper", ids)

    def test_sem_entidades_listas_vazias(self):
        self.ha.states = []
        self.assertEqual(S.ai_entities(), ([], []))

    def test_ia_simulada_nao_chama_o_home_assistant(self):
        with mock.patch.object(S, "AI_MOCK", True):
            tasks, agents = S.ai_entities()
        self.assertEqual(([t["id"] for t in tasks], [a["id"] for a in agents]), (["ai_task.simulado"], ["conversation.simulado"]))
        self.assertEqual(self.ha.calls(), [])

    def test_home_assistant_que_recusa_repassa_o_erro(self):
        self.ha.token = "outro"
        self.assertApiError(502, S.ai_entities, msg_part="recusou")


class Estado(ComHA):
    def test_pronta_sem_motivo_e_sem_escolha(self):
        st = S.ai_status()
        self.assertEqual((st["ready"], st["reason"], st["selected"], st["search"]), (True, None, "", ""))

    def test_so_ias_de_texto_sem_escolha_da_no_vision(self):
        self.ha.states = [s for s in self.ha.states if s["entity_id"] != GOOGLE]
        st = S.ai_status()
        self.assertEqual((st["ready"], st["reason"], st["selected"]), (False, "no_vision", ""), "a tela diz: as IAs configuradas não aceitam fotos")

    def test_escolhida_que_le_fotos_fica_pronta(self):
        self.store.settings["ai_entity"] = GOOGLE
        st = S.ai_status()
        self.assertEqual((st["ready"], st["reason"], st["selected"]), (True, None, GOOGLE))

    def test_escolhida_que_saiu_do_home_assistant_nao_aparece_como_sem_foto(self):
        self.store.settings["ai_entity"] = "ai_task.removida"
        st = S.ai_status()
        self.assertNotEqual(st["reason"], "no_vision", "ela não existe mais; não é que não leia fotos")

    def test_busca_escolhida_vem_junto(self):
        self.store.settings["ai_search"] = GEMINI
        self.assertEqual(S.ai_status()["search"], GEMINI)

    def test_home_assistant_fora_do_ar_da_error_com_a_mensagem(self):
        self.store.settings.update(ai_entity=GOOGLE, ai_search=GEMINI)
        with ha_fora_do_ar():
            st = S.ai_status()
        self.assertEqual((st["ready"], st["reason"], st["entities"], st["agents"], st["selected"]), (False, "error", [], [], ""))
        self.assertIn("O Home Assistant não respondeu", st["message"])
        self.assertEqual(st["search"], GEMINI)

    def test_com_ia_desligada_ainda_informa_sem_chamar_a_ia(self):
        self.store.settings["ai"] = False
        st = S.ai_status()
        self.assertTrue(st["ready"], "Integrações continua mostrando o que existe no Home Assistant")
        self.assertEqual([c["path"] for c in self.ha.calls()], ["/core/api/states"])
        self.assertEqual(self.pedidos_ia(), [])

    def test_ia_simulada_sem_token_fica_pronta(self):
        with mock.patch.object(S, "SUPERVISOR_TOKEN", None), mock.patch.object(S, "AI_MOCK", True):
            st = S.ai_status()
        self.assertEqual((st["ready"], [e["id"] for e in st["entities"]]), (True, ["ai_task.simulado"]))


class EstadoSemHomeAssistant(UnitBase):
    def test_sem_token_devolve_a_busca_escolhida(self):
        self.store.settings["ai_search"] = GEMINI
        st = S.ai_status()
        self.assertEqual((st["reason"], st["search"], st["entities"], st["agents"]), ("no_api", GEMINI, [], []))


# ---------------------------------------------------------------------------- opções da casa

class Opcoes(UnitBase):
    def test_ia_vem_ligada(self):
        self.assertEqual(self.store.settings, {})
        self.assertTrue(S.ai_enabled())

    def test_ia_so_desliga_com_falso(self):
        self.store.settings["ai"] = None
        self.assertTrue(S.ai_enabled())
        self.store.settings["ai"] = False
        self.assertFalse(S.ai_enabled())

    def test_zonas_vem_desligadas(self):
        self.assertFalse(S.zones_enabled())

    def test_zonas_so_ligam_com_verdadeiro(self):
        for v, esperado in (("true", False), (1, False), (True, True)):
            with self.subTest(v=v):
                self.store.settings["zones"] = v
                self.assertIs(S.zones_enabled(), esperado)

    def test_sensores_vem_desligados(self):
        self.assertFalse(S.sensors_enabled())

    def test_sensores_so_ligam_com_verdadeiro(self):
        for v, esperado in (("sim", False), (1, False), (True, True)):
            with self.subTest(v=v):
                self.store.settings["ha_sensors"] = v
                self.assertIs(S.sensors_enabled(), esperado)

    def test_ia_desligada_nao_desliga_as_zonas_nem_os_sensores(self):
        self.store.settings.update(ai=False, zones=True, ha_sensors=True)
        self.assertEqual((S.ai_enabled(), S.zones_enabled(), S.sensors_enabled()), (False, True, True))

    def test_need_ai_on_com_ia_desligada_diz_onde_ligar(self):
        self.store.settings["ai"] = False
        self.assertApiError(409, S.need_ai_on, msg_part="ligue em Mais > Integrações")

    def test_need_ai_on_ligada_ou_sem_opcao_gravada_passa(self):
        self.assertIsNone(S.need_ai_on())
        self.store.settings["ai"] = True
        self.assertIsNone(S.need_ai_on())

    def test_busca_padrao_e_vazia(self):
        self.assertEqual(S.search_entity(), "")

    def test_busca_escolhida(self):
        self.store.settings["ai_search"] = GEMINI
        self.assertEqual(S.search_entity(), GEMINI)

    def test_busca_nula_vira_vazia(self):
        self.store.settings["ai_search"] = None
        self.assertEqual(S.search_entity(), "")

    def test_busca_nao_herda_a_ia_de_fotos(self):
        self.store.settings["ai_entity"] = GOOGLE
        self.assertEqual(S.search_entity(), "", "vazio = a tarefa de IA preferida do Home Assistant")


# ---------------------------------------------------------------------------- leitura de foto

class LeituraDeFoto(ComHA):
    def responde(self, items):
        self.ha.ai_reply = lambda kind, body: json.dumps({"items": items}, ensure_ascii=False)

    def test_nome_de_foto_inseguro_e_recusado_sem_chamar_o_home_assistant(self):
        for nome in ("../inventario.json", "sala-1.gif", "", "/etc/passwd", None):
            with self.subTest(nome=nome):
                self.assertApiError(400, S.ai_identify, {"file": nome}, msg_part="Envie uma foto")
        self.assertEqual(self.ha.calls(), [])
        self.assertEqual(pasta_temporaria(), [])

    def test_ia_desligada_nao_copia_a_foto_nem_chama_o_home_assistant(self):
        self.store.settings["ai"] = False
        self.assertApiError(409, S.ai_identify, {"file": "sala-1.jpg"})
        self.assertEqual((self.ha.calls(), pasta_temporaria()), ([], []))

    def test_pedido_leva_a_foto_como_jpeg_da_pasta_temporaria(self):
        S.ai_identify({"file": "sala-1.jpg"})
        body = self.pedidos_ia()[-1]["body"]
        anexo = body["attachments"][0]
        self.assertEqual(body["task_name"], "InventarIA: ler foto")
        self.assertEqual(anexo["media_content_type"], "image/jpeg")
        self.assertRegex(anexo["media_content_id"], r"^media-source://media_source/local/inventario/ia-temp/[0-9a-f]{16}\.jpg$")

    def test_cada_leitura_usa_uma_copia_com_nome_novo(self):
        S.ai_identify({"file": "sala-1.jpg"})
        S.ai_identify({"file": "sala-1.jpg"})
        ids = [c["body"]["attachments"][0]["media_content_id"] for c in self.pedidos_ia()]
        self.assertEqual(len(set(ids)), 2)

    def test_foto_original_continua_depois_da_leitura(self):
        with open(os.path.join(S.PHOTOS_DIR, "sala-1.jpg"), "rb") as f:
            antes = f.read()
        S.ai_identify({"file": "sala-1.jpg"})
        with open(os.path.join(S.PHOTOS_DIR, "sala-1.jpg"), "rb") as f:
            self.assertEqual(f.read(), antes)

    def test_entidade_escolhida_aparece_na_resposta_e_no_uso(self):
        self.store.settings["ai_entity"] = GOOGLE
        self.responde([{"name": "Poltrona"}])
        self.assertEqual(S.ai_identify({"file": "sala-1.jpg"})["entity"], GOOGLE)
        self.assertEqual(S.usage_summary()["today"]["entities"], {GOOGLE: 1})

    def test_foto_unica_registra_foto_e_varias_registram_catalogo(self):
        S.ai_identify({"file": "sala-1.jpg", "mode": "single"})
        S.ai_identify({"file": "sala-1.jpg", "mode": "multi"})
        S.ai_identify({"file": "sala-1.jpg"})
        self.assertEqual(S.usage_summary()["today"]["kinds"], {"foto": 1, "catalogo": 2})

    def test_modo_desconhecido_le_varios_itens(self):
        S.ai_identify({"file": "sala-1.jpg", "mode": "qualquer"})
        self.assertIn("até 25", self.pedidos_ia()[-1]["body"]["instructions"])

    def test_uma_imagem_contada_no_uso(self):
        S.ai_identify({"file": "sala-1.jpg"})
        self.assertEqual(S.usage_summary()["today"]["images"], 1)

    def test_comodo_inexistente_e_ignorado(self):
        S.ai_identify({"file": "sala-1.jpg", "room": "nao-existe"})
        self.assertNotIn("Cômodo:", self.pedidos_ia()[-1]["body"]["instructions"])

    def test_item_ja_cadastrado_no_comodo_vem_marcado(self):
        self.responde([{"name": "Sofá cinza", "existing": SOFA}, {"name": "Smart TV", "existing": "Smart TV 55 polegadas"}])
        res = S.ai_identify({"file": "sala-1.jpg", "room": "sala"})
        self.assertIn("Cômodo: Sala de estar.", self.pedidos_ia()[-1]["body"]["instructions"])
        self.assertEqual([i["existing"] for i in res["items"]], [SOFA, "Smart TV 55 polegadas"])

    def test_resposta_com_cerca_markdown_funciona(self):
        self.ha.ai_reply = lambda kind, body: '```json\n{"items": [{"name": "Abajur", "cat": "decoracao"}]}\n```'
        self.assertEqual([(i["name"], i["cat"]) for i in S.ai_identify({"file": "quarto-1.jpg"})["items"]], [("Abajur", "decoracao")])

    def test_resposta_sem_itens_validos_devolve_lista_vazia(self):
        self.responde([{"name": ""}, {"name": "   "}])
        self.assertEqual(S.ai_identify({"file": "sala-1.jpg"})["items"], [])

    def test_dica_longa_recusada_antes_de_chamar_a_ia(self):
        self.assertApiError(400, S.ai_identify, {"file": "sala-1.jpg", "hint": "x" * 301}, msg_part="dica")
        self.assertEqual((self.pedidos_ia(), pasta_temporaria()), ([], []))

    def test_sem_pasta_media_da_500_sem_chamar_a_ia(self):
        with mock.patch.object(S, "MEDIA_ROOT", os.path.join(S.DATA_DIR, "nao-existe")):
            self.assertApiError(500, S.ai_identify, {"file": "sala-1.jpg"}, msg_part="pasta media")
        self.assertEqual(self.pedidos_ia(), [])

    def test_erro_comum_do_home_assistant_registra_erro(self):
        self.ha.ai_error = (500, "Falha ao gerar")
        self.assertApiError(502, S.ai_identify, {"file": "sala-1.jpg"}, msg_part="Falha ao gerar")
        hoje = S.usage_summary()["today"]
        self.assertEqual((S.usage_summary()["recent"][0]["result"], hoje["errors"], hoje["quota"]), ("erro", 1, 0))

    def test_cota_nao_conta_como_erro_no_dia(self):
        self.ha.ai_error = (429, "RESOURCE_EXHAUSTED")
        self.assertApiError(502, S.ai_identify, {"file": "sala-1.jpg"})
        hoje = S.usage_summary()["today"]
        self.assertEqual((hoje["calls"], hoje["errors"], hoje["quota"]), (1, 0, 1))

    def test_home_assistant_fora_do_ar_apaga_a_copia_temporaria(self):
        with ha_fora_do_ar():
            self.assertApiError(504, S.ai_identify, {"file": "sala-1.jpg"}, msg_part="não respondeu")
        self.assertEqual(pasta_temporaria(), [])
        self.assertEqual(S.usage_summary()["recent"][0]["result"], "erro")


# ---------------------------------------------------------------------------- rotas de configuração

class RotasDeConfiguracao(UnitBase):
    def put(self, body):
        h = Pedido(body)
        S.r_settings_put(h, {})
        return h

    def put_erro(self, body, msg_part=None):
        return self.assertApiError(400, self.put, body, msg_part=msg_part)

    def no_arquivo(self):
        return S.read_json(S.SETTINGS_FILE)

    def test_get_devolve_o_que_esta_gravado(self):
        h = Pedido()
        S.r_settings_get(h, {})
        self.assertEqual((h.status, h.resposta), (200, {}))
        self.store.settings.update(zones=True, ai_entity=GOOGLE)
        S.r_settings_get(h, {})
        self.assertEqual(h.resposta, {"zones": True, "ai_entity": GOOGLE})

    def test_ia_de_fotos_valida_grava_no_arquivo(self):
        h = self.put({"ai_entity": GOOGLE})
        self.assertEqual((h.status, h.resposta), (200, {"ai_entity": GOOGLE}))
        self.assertEqual(self.no_arquivo(), {"ai_entity": GOOGLE})

    def test_ia_de_fotos_vazia_ou_nula_volta_ao_padrao(self):
        for v in ("", None):
            with self.subTest(v=v):
                self.store.settings["ai_entity"] = GOOGLE
                self.assertEqual(self.put({"ai_entity": v}).resposta["ai_entity"], "")

    def test_ia_de_fotos_recusa_o_que_nao_e_tarefa_de_ia(self):
        for v in (GEMINI, "ai_task.Google", "ai_task.", "ai_task.x y", " ai_task.x", "ai_task.x\n", "sensor.x", 123):
            with self.subTest(v=v):
                self.put_erro({"ai_entity": v}, msg_part="Entidade de IA inválida.")
        self.assertEqual(self.store.settings, {})

    def test_busca_aceita_tarefa_de_ia_e_assistente_de_conversa(self):
        for v in (GOOGLE, GEMINI):
            with self.subTest(v=v):
                self.assertEqual(self.put({"ai_search": v}).resposta["ai_search"], v)

    def test_busca_recusa_outros_dominios(self):
        for v in ("light.sala", "stt.faster_whisper", "conversation", "conversation.Gemini"):
            with self.subTest(v=v):
                self.put_erro({"ai_search": v}, msg_part="Entidade de IA inválida.")

    def test_fala_aceita_fala_para_texto(self):
        self.assertEqual(self.put({"voice_stt": "stt.faster_whisper"}).resposta["voice_stt"], "stt.faster_whisper")

    def test_fala_recusa_o_que_nao_e_fala_para_texto(self):
        for v in ("ai_task.x", "stt", "stt.Cloud", "tts.google"):
            with self.subTest(v=v):
                self.put_erro({"voice_stt": v}, msg_part="Fala para texto inválida.")

    def test_fala_escolhida_zera_o_cache_da_voz(self):
        S._voice_cache["at"] = 12345.0
        self.put({"voice_stt": "stt.faster_whisper"})
        self.assertEqual(S._voice_cache["at"], 0.0, "a próxima consulta já usa a fala nova")

    def test_fala_de_volta_ao_padrao_tambem_zera_o_cache(self):
        S._voice_cache["at"] = 12345.0
        self.put({"voice_stt": ""})
        self.assertEqual(S._voice_cache["at"], 0.0)

    def test_sem_fala_no_pedido_mantem_o_cache_da_voz(self):
        S._voice_cache["at"] = 12345.0
        self.put({"ai_entity": GOOGLE, "zones": True})
        self.assertEqual(S._voice_cache["at"], 12345.0)

    def test_opcoes_ligam_e_desligam(self):
        for key in ("ai", "zones", "ha_sensors"):
            for v in (True, False):
                with self.subTest(key=key, v=v), mock.patch.object(S.threading, "Thread"):
                    self.assertIs(self.put({key: v}).resposta[key], v)
                    self.assertIs(self.no_arquivo()[key], v)

    def test_opcao_com_texto_numero_ou_nulo_e_recusada(self):
        for key in ("ai", "zones", "ha_sensors"):
            for v in ("true", "sim", 1, 0, None):
                with self.subTest(key=key, v=v):
                    self.put_erro({key: v}, msg_part="Use verdadeiro ou falso")

    def test_campo_invalido_nao_muda_nada_na_memoria(self):
        self.store.settings.update(zones=False)
        self.put_erro({"ai_entity": GOOGLE, "zones": True, "voice_stt": "ruim"})
        self.assertEqual(self.store.settings, {"zones": False})

    def test_campo_invalido_nao_grava_o_arquivo(self):
        self.put({"zones": True})
        self.put_erro({"zones": False, "ai_search": "light.sala"})
        self.assertEqual(self.no_arquivo(), {"zones": True})

    def test_campo_invalido_nao_zera_o_cache_da_voz(self):
        S._voice_cache["at"] = 12345.0
        self.put_erro({"voice_stt": "stt.faster_whisper", "ai": "nao"})
        self.assertEqual(S._voice_cache["at"], 12345.0)

    def test_chave_desconhecida_e_ignorada(self):
        h = self.put({"tema": "escuro", "cor": 3, "zones": True})
        self.assertEqual(h.resposta, {"zones": True})
        self.assertEqual(self.no_arquivo(), {"zones": True})

    def test_corpo_que_nao_e_objeto_e_recusado(self):
        for body in ([{"zones": True}], "zones", 5):
            with self.subTest(body=body):
                self.put_erro(body, msg_part="Pedido inválido.")
        self.assertEqual(self.store.settings, {})

    def test_pedido_vazio_nao_muda_nada_e_devolve_tudo(self):
        self.store.settings.update(zones=True, ai_entity=GOOGLE)
        self.assertEqual(self.put({}).resposta, {"zones": True, "ai_entity": GOOGLE})

    def test_mantem_o_que_nao_veio_no_pedido(self):
        self.put({"zones": True, "ai_search": GEMINI})
        with mock.patch.object(S.threading, "Thread"):
            h = self.put({"ai": False})
        self.assertEqual(h.resposta, {"zones": True, "ai_search": GEMINI, "ai": False})

    def alvo_do_sensor(self, body):
        """Qual função o pedido manda rodar em segundo plano para o sensor (ou None)."""
        with mock.patch.object(S.threading, "Thread") as T:
            self.put(body)
        if not T.called:
            return None
        T.return_value.start.assert_called_once()
        return T.call_args.kwargs["target"]

    def test_sensores_ligados_publicam_o_sensor_na_hora(self):
        self.assertIs(self.alvo_do_sensor({"ha_sensors": True}), S.publish_usage_sensor)

    def test_sensores_desligados_retiram_o_sensor(self):
        self.store.settings["ha_sensors"] = True
        self.assertIs(self.alvo_do_sensor({"ha_sensors": False}), S.remove_usage_sensor)

    def test_ia_desligada_retira_o_sensor_mesmo_com_sensores_ligados(self):
        self.store.settings["ha_sensors"] = True
        self.assertIs(self.alvo_do_sensor({"ai": False}), S.remove_usage_sensor)

    def test_ia_religada_com_sensores_ligados_publica_o_sensor(self):
        self.store.settings.update(ha_sensors=True, ai=False)
        self.assertIs(self.alvo_do_sensor({"ai": True}), S.publish_usage_sensor)

    def test_sensores_ligados_com_ia_desligada_nao_publicam(self):
        self.store.settings["ai"] = False
        self.assertIs(self.alvo_do_sensor({"ha_sensors": True}), S.remove_usage_sensor)

    def test_outras_opcoes_nao_mexem_no_sensor(self):
        self.assertIsNone(self.alvo_do_sensor({"zones": True, "ai_entity": GOOGLE, "voice_stt": "stt.faster_whisper"}))


if __name__ == "__main__":
    unittest.main()
