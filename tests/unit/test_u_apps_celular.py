"""Novidades › Apps do celular (1.56.0): os apps usados nos celulares, pelo sensor Último app usado do app Home Assistant
(o registro e o histórico do Home Assistant), a escolha da IA, a busca das novidades de cada app, a conferência de todos e
o aviso. Apps e pessoas inventados."""
import json
import os
import time
import unittest
from datetime import datetime, timedelta
from unittest import mock

from _boot import UnitBase, server

SENSOR = "sensor.celular_da_ana_app_em_uso"  # o nome muda com a língua do celular: vale o unique_id do registro
CASA, MUSICA, MERCADO = "com.exemplo.casaconectada", "com.exemplo.musicaja", "com.exemplo.mercadinho"


def quando(**delta) -> str:
    return (datetime.now().astimezone() - timedelta(**delta)).isoformat(timespec="seconds")


def estado(pkg, t, label=""):
    return {"entity_id": SENSOR, "state": pkg, "last_changed": t, "last_updated": t, "attributes": {"Label": label} if label else {}}


class ComHA(UnitBase):
    """Com o Home Assistant de mentira: o sensor no registro (no celular da Ana) e o histórico dele."""

    def setUp(self):
        super().setUp()
        self.ha = self.fake_ha()
        self.ha.registry = [{"entity_id": "device_tracker.pixel_ana", "device_id": "d-ana", "platform": "mobile_app", "unique_id": "abc123_location"},
                            {"entity_id": SENSOR, "device_id": "d-ana", "platform": "mobile_app", "unique_id": "abc123_last_used_app"},
                            {"entity_id": "sensor.celular_da_ana_bateria", "device_id": "d-ana", "platform": "mobile_app", "unique_id": "abc123_battery_level"}]
        self.ha.states.append({"entity_id": SENSOR, "state": CASA, "last_changed": quando(days=1), "attributes": {"Label": "Casa Conectada"}})
        self.ha.history[SENSOR] = [estado(CASA, quando(days=3), "Casa Conectada"), estado(MUSICA, quando(days=2), "Música Já"),
                                   estado("unavailable", quando(days=2, hours=-1)), estado(CASA, quando(days=1), "Casa Conectada")]

    def historicos(self):
        return [r for r in self.ha.requests if r["method"] == "GET" and r["path"].startswith("/core/api/history/period/")]


class Sensores(ComHA):
    def test_pelo_registro_em_qualquer_lingua_e_a_pessoa_do_celular(self):
        sensores, estados = server.apps_sensors()
        self.assertEqual(sensores, [{"entity": SENSOR, "pessoas": ["Ana"]}], "só o Último app usado, não a bateria")
        self.assertIn(SENSOR, estados)

    def test_desligado_no_registro_fica_de_fora(self):
        self.ha.registry[1]["disabled_by"] = "user"
        self.assertEqual(server.apps_sensors()[0], [])

    def test_sem_o_registro_pelo_nome_da_entidade(self):
        self.ha.ws_fail = True
        self.ha.states.append({"entity_id": "sensor.tablet_da_sala_last_used_app", "state": MERCADO, "attributes": {}})
        self.ha.states.append({"entity_id": "sensor.tablet_da_sala_battery_level", "state": "80", "attributes": {}})
        self.assertEqual(server.apps_sensors()[0], [{"entity": "sensor.tablet_da_sala_last_used_app", "pessoas": ["Carla"]}],
                         "a Carla tem o rastreador device_tracker.tablet_da_sala")

    def test_em_portugues_pelo_nome_tambem(self):
        self.ha.ws_fail = True
        self.ha.states.append({"entity_id": "sensor.celular_velho_ultimo_aplicativo_usado", "state": MERCADO, "attributes": {}})
        self.assertEqual([s["entity"] for s in server.apps_sensors()[0]], ["sensor.celular_velho_ultimo_aplicativo_usado"])


class Coleta(ComHA):
    def test_junta_os_apps_do_historico(self):
        d = server.apps_collect(force=True)
        self.assertEqual(sorted(d["apps"]), [CASA, MUSICA], "unavailable não é app")
        a = d["apps"][CASA]
        self.assertEqual((a["nome"], a["vezes"], a["dias"], a["pessoas"]), ("Casa Conectada", 2, 2, ["Ana"]))
        self.assertEqual((d["apps"][MUSICA]["nome"], d["apps"][MUSICA]["vezes"]), ("Música Já", 1))
        self.assertEqual(d["sensores"], 1)
        self.assertEqual(d["celulares"], [{"entity": SENSOR, "pessoas": ["Ana"]}], "os celulares com o sensor, para as Opções")
        with mock.patch.object(server, "apps_collect", lambda force=False: d):
            self.assertEqual(server.apps_overview()["celulares"], ["Ana"])
        self.assertTrue(os.path.isfile(server.APPS_FILE))
        self.assertIn("filter_entity_id=" + SENSOR, self.historicos()[0]["path"])

    def test_a_segunda_leitura_so_traz_o_que_veio_depois(self):
        server.apps_collect(force=True)
        self.ha.history[SENSOR].append(estado(MERCADO, quando(seconds=-30), "Mercadinho"))  # depois da primeira leitura
        d = server.apps_collect(force=True)
        self.assertEqual(d["apps"][CASA]["vezes"], 2, "o estado de antes da leitura (o primeiro do histórico) não conta de novo")
        self.assertEqual(d["apps"][MERCADO]["vezes"], 1)

    def test_le_o_historico_de_novo_so_depois_de_10_minutos(self):
        server.apps_collect()
        server.apps_collect()
        self.assertEqual(len(self.historicos()), 1)
        server.apps_collect(force=True)
        self.assertEqual(len(self.historicos()), 2)

    def test_sem_historico_vale_o_estado_de_agora(self):
        del self.ha.history[SENSOR]  # o sensor fora do registro do Home Assistant (recorder)
        self.assertEqual(sorted(server.apps_collect(force=True)["apps"]), [CASA])

    def test_sem_sensor_nada(self):
        self.ha.registry = []
        self.ha.states = [s for s in self.ha.states if s["entity_id"] != SENSOR]
        d = server.apps_collect(force=True)
        self.assertEqual((d["apps"], d["sensores"]), ({}, 0))

    def test_historico_que_falha_nao_derruba(self):
        original = server.ha_request

        def falha(method, path, *a, **k):
            if path.startswith("/history/"):
                raise server.ApiError(504, "O Home Assistant não respondeu.")
            return original(method, path, *a, **k)
        with mock.patch.object(server, "ha_request", falha):
            self.assertEqual(sorted(server.apps_collect(force=True)["apps"]), [CASA], "vale o estado de agora")

    def test_no_maximo_300_apps_os_mais_recentes(self):
        with mock.patch.object(server, "APPS_MAX", 1):
            self.assertEqual(sorted(server.apps_collect(force=True)["apps"]), [CASA], "a Música foi usada há mais tempo")


class SemHA(UnitBase):
    def test_sem_home_assistant_os_apps_de_exemplo(self):
        with mock.patch.object(server, "AI_MOCK", True):
            d = server.apps_collect(force=True)
        self.assertEqual(len(d["apps"]), len(server.MOCK_APPS))
        self.assertEqual(d["apps"]["com.exemplo.musicaja"]["pessoas"], ["Pessoa de Teste"])

    def test_opcao_desligada_de_inicio_e_depende_das_novidades(self):
        self.assertFalse(server.apps_enabled())
        self.store.settings["news_apps"] = True
        self.assertTrue(server.apps_enabled())
        self.store.settings["news"] = False
        self.assertFalse(server.apps_enabled(), "sem as Novidades")
        self.store.settings.update(news=True, ai=False)
        self.assertFalse(server.apps_enabled(), "sem a IA")

    def test_nome_do_app(self):
        self.assertEqual(server.app_name(CASA, {CASA: {"nome": "Do sensor"}}, {CASA: {"nome": "Da IA"}}), "Da IA")
        self.assertEqual(server.app_name(CASA, {CASA: {"nome": "Do sensor"}}, {}), "Do sensor")
        self.assertEqual(server.app_name(CASA, {}, {}), "casaconectada")

    def test_nome_do_celular(self):
        self.assertEqual(server.celular_nome({"entity": "sensor.x_last_used_app", "pessoas": ["Ana"]}), "Ana")
        self.assertEqual(server.celular_nome({"entity": "sensor.x_last_used_app", "pessoas": ["Ana", "Beto", "Carla"]}), "Ana, Beto e Carla")
        self.assertEqual(server.celular_nome({"entity": "sensor.tablet_da_sala_last_used_app", "pessoas": []}), "tablet da sala", "sem pessoa: o aparelho")
        self.assertEqual(server.celular_nome({"entity": "sensor.celular_velho_ultimo_aplicativo_usado"}), "celular velho")
        self.assertEqual(server.celular_nome({}), "um celular")

    def test_rotulo_do_sensor(self):
        self.assertEqual(server._app_label({"Label": "  Casa   Conectada "}), "Casa Conectada")
        self.assertEqual(server._app_label({"label": "Música"}), "Música")
        self.assertEqual(server._app_label({"Label": ""}), "")
        self.assertEqual(server._app_label(None), "")


class Triagem(UnitBase):
    def test_instrucoes(self):
        p = server.apps_triage_prompt([(CASA, "Casa Conectada"), ("com.android.launcher3", "")])
        self.assertIn(f"{CASA}: Casa Conectada", p)
        self.assertIn("com.android.launcher3", p)
        for t in ("tela inicial", "configurações", "teclado", '"conferir": true'):
            self.assertIn(t, p)

    def test_simulada_deixa_o_sistema_de_fora(self):
        with mock.patch.object(server, "AI_MOCK", True):
            got = server.ai_apps_triage([(CASA, "Casa Conectada"), ("com.android.launcher3", ""), ("com.android.settings", "Configurações")])
        self.assertEqual({p: v["conferir"] for p, v in got.items()}, {CASA: True, "com.android.launcher3": False, "com.android.settings": False})
        self.assertEqual(got["com.android.launcher3"]["nome"], "Launcher3", "sem nome, a simulada usa o fim do pacote")

    def test_com_o_home_assistant(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"apps": [{"pacote": CASA, "nome": "Casa Conectada", "conferir": True},
                                                                 {"pacote": "com.nao.estava", "nome": "X", "conferir": True}]})
        got = server.ai_apps_triage([(CASA, ""), (MUSICA, "Música Já")])
        self.assertEqual(got[CASA], {"conferir": True, "nome": "Casa Conectada"})
        self.assertEqual(got[MUSICA], {"conferir": False, "nome": "Música Já", "faltou": True}, "o que a IA não devolveu fica para a próxima")
        self.assertNotIn("com.nao.estava", got)
        self.assertEqual(ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["task_name"], "InventarIA: escolher apps")

    def test_resposta_fora_do_formato_e_erro(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "não sei"
        self.assertApiError(502, server.ai_apps_triage, [(CASA, "")])

    def test_muitos_em_blocos(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"apps": []})
        with mock.patch.object(server, "TRIAGE_CHUNK", 2):
            server.ai_apps_triage([(f"com.exemplo.app{i}", "") for i in range(5)])
        self.assertEqual(len(ha.calls("POST", "/core/api/services/ai_task")), 3)


class Busca(UnitBase):
    def test_instrucoes(self):
        p = server.app_news_prompt("Casa Conectada", CASA)
        for t in ("Aplicativo: Casa Conectada", CASA, "Use a busca na web agora.", "Google Play", "Só o que vale no Brasil", "beta",
                  "correções de erros", '"novidades"', "Hoje é 2026-11-04"):
            self.assertIn(t, p)

    def test_com_o_home_assistant(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"produto": "Casa Conectada", "novidades": [
            {"tipo": "atualizacao", "titulo": "Modo escuro", "data": "2026-10-02", "fonte": "https://exemplo.com/modo-escuro"},
            {"tipo": "atualizacao", "titulo": "Sem fonte"},
            {"tipo": "outro", "titulo": "Antiga", "data": "2024-01", "fonte": "https://exemplo.com/antiga"}]})
        got = server.ai_find_app_news("Casa Conectada", CASA, "ai_task.google_ai_task")
        self.assertEqual([n["titulo"] for n in got["novidades"]], ["Modo escuro"], "sem fonte e de anos atrás ficam de fora")
        self.assertEqual(ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["task_name"], "InventarIA: novidades de app")

    def test_sem_busca_na_web_e_erro(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: '{"erro": "sem_busca"}'
        self.assertApiError(502, server.ai_find_app_news, "Casa Conectada", CASA, "ai_task.google_ai_task", msg_part="busca na web")

    def test_simulada(self):
        with mock.patch.object(server, "AI_MOCK", True), mock.patch.object(server.time, "sleep", lambda s: None):
            got = server.ai_find_app_news("Casa Conectada", CASA, "")
        self.assertEqual(len(got["novidades"]), 2)


class Lote(UnitBase):
    """Conferir novidades com os apps: a IA simulada e os apps de exemplo (sem Home Assistant)."""

    def setUp(self):
        super().setUp()
        for p in (mock.patch.object(server, "AI_MOCK", True), mock.patch.object(server.time, "sleep", lambda s: None)):
            p.start()
            self.addCleanup(p.stop)

    def run_batch(self, auto=False, so=""):
        jid = server.news_batch_start(auto=auto, so=so)["id"]
        t0 = time.time()
        while server.WEB_JOBS[jid]["stage"] == "busy":
            if time.time() - t0 > 10:
                self.fail("a conferência não terminou")
            time.sleep(0.05)
        return server.WEB_JOBS[jid]

    def test_sem_a_opcao_so_os_eletronicos(self):
        job = self.run_batch()
        self.assertFalse(os.path.exists(server.APPS_FILE), "nem lê os apps")
        self.assertEqual(server.news_read()["apps"], {})
        self.assertIsNone(server.news_overview()["apps"])
        self.assertEqual(job["summary"]["selecionados"], job["summary"]["conferidos"])

    def test_com_a_opcao_confere_os_apps_que_a_ia_escolheu(self):
        self.store.settings["news_apps"] = True
        antes = self.run_batch_sem_apps()
        job = self.run_batch()
        d = server.news_read()
        self.assertEqual(sorted(d["apps"]), sorted([CASA, MUSICA, MERCADO]), "a tela inicial e as configurações ficam de fora")
        self.assertEqual(job["summary"]["conferidos"], antes + 3)
        ov = server.news_overview()["apps"]
        fora = sorted(a["pacote"] for a in ov["lista"] if a["conferir"] is False)
        self.assertEqual(fora, ["com.android.launcher3", "com.android.settings"])
        casa = next(a for a in ov["lista"] if a["pacote"] == CASA)
        self.assertEqual((casa["nome"], casa["pessoas"], len(casa["res"]["news"]["novidades"])), ("Casa Conectada", ["Pessoa de Teste"], 2))

    def run_batch_sem_apps(self):
        self.store.settings["news_apps"] = False
        n = self.run_batch()["summary"]["conferidos"]
        server.news_clear()
        self.store.settings["news_apps"] = True
        return n

    def test_so_apps_e_so_equipamentos(self):
        """1.58.0: Só apps confere só os apps; Só equipamentos, só os equipamentos."""
        self.store.settings["news_apps"] = True
        job = self.run_batch(so="apps")
        d = server.news_read()
        self.assertEqual((sorted(d["apps"]), d["itens"], d["triagem"]), (sorted([CASA, MUSICA, MERCADO]), {}, {}), "nenhum equipamento")
        self.assertEqual(job["summary"]["conferidos"], 3)
        server.news_clear()
        job = self.run_batch(so="itens")
        d = server.news_read()
        self.assertEqual(d["apps"], {}, "nenhum app")
        self.assertTrue(d["itens"])
        self.assertGreater(job["summary"]["conferidos"], 0)
        self.assertApiError(400, server.news_batch_start, so="tudo", msg_part="Escolha o que conferir")
        self.store.settings["news_apps"] = False
        self.assertApiError(409, server.news_batch_start, so="apps", msg_part="Ligue Apps do celular")

    def test_na_semana_nao_confere_de_novo(self):
        self.store.settings["news_apps"] = True
        self.run_batch()
        job = self.run_batch()
        self.assertEqual(job["summary"]["conferidos"], 0)

    def test_aviso_conta_os_apps(self):
        self.store.settings.update(news_apps=True, news_aviso=True, news_para=["person.pessoa_de_teste"])
        with mock.patch.object(server, "send_news_notice") as aviso:
            self.run_batch(auto=True)
        n, k = aviso.call_args.args[0], aviso.call_args.kwargs
        self.assertEqual(k, {"apps": 3})
        self.assertGreater(n, 0)

    def test_escolha_da_pessoa(self):
        self.store.settings["news_apps"] = True
        self.run_batch()
        ov = server.app_choice({"pacote": CASA, "acompanhar": False})
        casa = next(a for a in ov["apps"]["lista"] if a["pacote"] == CASA)
        self.assertEqual((casa["conferir"], casa["manual"], casa["res"]), (False, True, None), "deixado de fora: sai o que foi achado")
        server.app_choice({"pacote": "com.android.launcher3", "acompanhar": True})
        server.news_clear()
        tri = server.news_read()["apps_triagem"]
        self.assertEqual(sorted(tri), sorted([CASA, "com.android.launcher3"]), "Limpar apaga as escolhas da IA, não as da pessoa")
        self.run_batch()
        d = server.news_read()
        self.assertIn("com.android.launcher3", d["apps"], "a pessoa escolheu acompanhar")
        self.assertNotIn(CASA, d["apps"], "a pessoa deixou de fora: a IA não muda")

    def test_conferir_um_app(self):
        self.store.settings["news_apps"] = True
        server.apps_collect(force=True)
        jid = server.app_news_job_start({"pacote": "com.android.settings"})["id"]
        t0 = time.time()
        while server.WEB_JOBS[jid]["stage"] == "busy" and time.time() - t0 < 5:
            time.sleep(0.05)
        self.assertEqual(server.WEB_JOBS[jid]["stage"], "done")
        self.assertIn("com.android.settings", server.news_read()["apps"], "um deixado de fora conferido passa para a lista")

    def test_recusas(self):
        self.assertApiError(409, server.app_news_job_start, {"pacote": CASA}, msg_part="apps do celular estão desligados")
        self.store.settings["news_apps"] = True
        server.apps_collect(force=True)
        self.assertApiError(404, server.app_news_job_start, {"pacote": "com.nao.existe"})
        self.assertApiError(404, server.app_choice, {"pacote": "com.nao.existe", "acompanhar": True})
        self.assertApiError(400, server.app_choice, {"pacote": CASA, "acompanhar": "sim"})


class Aviso(UnitBase):
    def test_texto(self):
        self.assertEqual(server.news_notice(2, apps=1)["message"], "Novidades em 2 itens e 1 app. Toque para abrir.")
        self.assertEqual(server.news_notice(0, apps=3)["message"], "Novidades em 3 apps. Toque para abrir.")
        self.assertEqual(server.news_notice(1)["message"], "Novidades em 1 item. Toque para abrir.")


if __name__ == "__main__":
    unittest.main()


PNG = "data:image/png;base64," + __import__("base64").b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode()


class Encontrar(UnitBase):
    """1.59.0: Encontrar apps com IA: os prints (ou os nomes colados) lidos pela IA, a pessoa escolhe e eles entram em Apps
    detectados, acompanhados. Apps e nomes inventados."""

    def setUp(self):
        super().setUp()
        self.store.settings["news_apps"] = True

    def test_simulada_marca_o_que_ja_esta(self):
        with mock.patch.object(server, "AI_MOCK", True), mock.patch.object(server.time, "sleep", lambda s: None):
            server.apps_collect(force=True)
            got = server.apps_ler({"texto": "Banco Lua, Mapa Fácil"})["apps"]
        self.assertEqual([(x["nome"], x["id"], x["ja"], x["sistema"]) for x in got], [
            ("Casa Conectada", CASA, True, False), ("Banco Lua", "com.exemplo.bancolua", False, False),
            ("Mapa Fácil", "ia.mapa_facil", False, False), ("Configurações", "com.android.settings", True, True)])

    def test_validacoes(self):
        self.assertApiError(400, server.apps_ler, {}, msg_part="Escolha os prints")
        self.assertApiError(400, server.apps_ler, {"fotos": [PNG] * 7}, msg_part="No máximo 6")
        self.assertApiError(400, server.apps_ler, {"fotos": ["não é base64!"]}, msg_part="não abriu")
        self.assertApiError(400, server.apps_ler, {"fotos": [__import__("base64").b64encode(b"GIF89a....").decode()]}, msg_part="JPG ou PNG")
        self.store.settings["news_apps"] = False
        self.assertApiError(409, server.apps_ler, {"texto": "x"})
        self.assertApiError(409, server.apps_adicionar, {"apps": [{"nome": "x"}]})

    def test_com_o_home_assistant(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"apps": [
            {"nome": "Banco  Lua", "pacote": "com.exemplo.bancolua"}, {"nome": "banco lua", "pacote": ""},
            {"nome": "Mapa Fácil", "pacote": "não é pacote"}, {"nome": "", "pacote": "com.x.y"}, "lixo",
            {"nome": "Relógio", "pacote": "ia.truque", "sistema": True}]})
        got = server.apps_ler({"fotos": [PNG], "texto": "e o Mapa Fácil"})["apps"]
        self.assertEqual([(x["nome"], x["id"], x["sistema"]) for x in got],
                         [("Banco Lua", "com.exemplo.bancolua", False), ("Mapa Fácil", "ia.mapa_facil", False), ("Relógio", "ia.relogio", True)],
                         "sem repetir, sem nome vazio; o pacote que não parece de verdade vira ia.<nome>")
        pedido = ha.calls("POST", "/core/api/services/ai_task")[-1]
        b = pedido["body"]
        self.assertEqual((b["task_name"], len(b["attachments"]), b["attachments"][0]["media_content_type"]), ("InventarIA: encontrar apps", 1, "image/png"))
        self.assertEqual(pedido.get("attachments_present"), [True], "o print existe em /media enquanto a IA lê")
        self.assertIn("e o Mapa Fácil", b["instructions"])
        self.assertEqual(os.listdir(os.path.join(server.MEDIA_ROOT, server.AI_TMP_REL)), [], "e sai de lá depois")
        ha.ai_reply = lambda kind, payload: "isto não é JSON"
        self.assertApiError(502, server.apps_ler, {"texto": "Banco Lua"})
        self.assertIn("Aplicativo: Mapa Fácil (Android)", server.app_news_prompt("Mapa Fácil", "ia.mapa_facil"))
        self.assertIn("pacote com.exemplo.bancolua", server.app_news_prompt("Banco Lua", "com.exemplo.bancolua"))

    def test_adicionar(self):
        with mock.patch.object(server, "AI_MOCK", True):
            server.apps_collect(force=True)
            r = server.apps_adicionar({"apps": [{"id": "ia.mapa_facil", "nome": "Mapa Fácil", "pacote": ""},
                                                {"nome": "Banco Lua", "pacote": "com.exemplo.bancolua"},
                                                {"nome": "Casa Conectada", "pacote": CASA}]}, "u-qualquer")
        self.assertEqual(r["adicionados"], 2, "o que já estava fica como estava")
        lista = {a["pacote"]: a for a in r["apps"]["lista"]}
        banco = lista["com.exemplo.bancolua"]
        self.assertEqual((banco["nome"], banco["ia"], banco["conferir"], banco["manual"], banco["ultimo"], banco["pessoas"]),
                         ("Banco Lua", True, True, True, None, ["Pessoa de Teste"]), "acompanhado, de quem adicionou, sem uso")
        self.assertIn("ia.mapa_facil", lista)
        self.assertNotIn("ia", lista[CASA])
        self.assertIn("ia.mapa_facil", server.apps_selected(server.news_read(), server.apps_read()["apps"]), "entra na próxima conferência")
        self.assertApiError(400, server.apps_adicionar, {"apps": []}, msg_part="Escolha os apps")
