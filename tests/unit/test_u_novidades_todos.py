"""Novidades de todos os equipamentos (Mais > Novidades): categorias, a escolha da IA, a conferência em lote e o que fica guardado."""
import json
import time
import unittest
from unittest import mock

from _boot import UnitBase, server

TV, SOFA, GELADEIRA, FRUTEIRA = "sal-007", "sal-001", "coz-004", "coz-003"


def novidade(titulo="Firmware novo", tipo="atualizacao"):
    return {"produto": "x", "novidades": [{"tipo": tipo, "titulo": titulo, "data": "2026-09", "fonte": "https://fab.exemplo/n"}]}


class Categorias(UnitBase):
    def test_padrao_sao_as_que_costumam_ter_equipamentos(self):
        self.assertEqual(server.news_cats(), ["eletronicos", "cozinha", "saude", "utilidades", "outros"])

    def test_padrao_nao_tem_moveis_nem_decoracao(self):
        for c in ("moveis", "decoracao", "texteis", "plantas", "livros", "vestuario"):
            self.assertNotIn(c, server.news_cats())

    def test_categoria_da_casa_com_nome_de_equipamento_entra_no_padrao(self):
        self.store.create_cat({"name": "Ferramentas elétricas"})
        self.store.create_cat({"name": "Informática"})
        self.store.create_cat({"name": "Brinquedos"})
        cats = self.store.cat_map()
        ids = {v: k for k, v in cats.items()}
        self.assertIn(ids["Ferramentas elétricas"], server.news_cats())
        self.assertIn(ids["Informática"], server.news_cats())
        self.assertNotIn(ids["Brinquedos"], server.news_cats())

    def test_escolha_da_casa_vale(self):
        self.store.settings["news_cats"] = ["eletronicos"]
        self.assertEqual(server.news_cats(), ["eletronicos"])

    def test_escolha_vazia_vale_vazia(self):
        self.store.settings["news_cats"] = []
        self.assertEqual(server.news_cats(), [])

    def test_categoria_excluida_sai_da_escolha(self):
        self.store.settings["news_cats"] = ["eletronicos", "sumiu"]
        self.assertEqual(server.news_cats(), ["eletronicos"])


class Triagem(UnitBase):
    def test_instrucoes_listam_id_nome_detalhes_e_categoria(self):
        it = self.store.item(TV)
        p = server.triage_prompt([it])
        self.assertIn(f"{TV}: {it['name']}", p)
        self.assertIn("[Eletrônicos]", p)

    def test_instrucoes_deixam_de_fora_moveis_e_decoracao(self):
        p = server.triage_prompt([self.store.item(SOFA)])
        for t in ("móveis", "cama", "mesa", "decoração"):
            self.assertIn(t, p)

    def test_instrucoes_pedem_so_os_ids(self):
        self.assertIn('{"conferir": ["id", "id"]}', server.triage_prompt([self.store.item(TV)]))

    def test_simulada_escolhe_eletronicos_e_aparelhos(self):
        with mock.patch.object(server, "AI_MOCK", True):
            got = server.ai_triage([self.store.item(i) for i in (TV, SOFA, GELADEIRA)])
        self.assertEqual(got, {TV, GELADEIRA})

    def test_com_o_home_assistant_usa_a_resposta_da_ia(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"conferir": [TV, "id-que-nao-veio"]})
        self.assertEqual(server.ai_triage([self.store.item(TV), self.store.item(SOFA)]), {TV}, "id que não estava na lista não entra")
        self.assertEqual(ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["task_name"], "InventarIA: escolher equipamentos")

    def test_resposta_em_lista_tambem_vale(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps([TV])
        self.assertEqual(server.ai_triage([self.store.item(TV)]), {TV})

    def test_resposta_fora_do_formato_e_erro(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "não sei"
        self.assertApiError(502, server.ai_triage, [self.store.item(TV)])

    def test_muitos_itens_vao_em_blocos(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps({"conferir": []})
        with mock.patch.object(server, "TRIAGE_CHUNK", 10):
            server.ai_triage(self.store.data["items"][:25])
        self.assertEqual(len(ha.calls("POST", "/core/api/services/ai_task")), 3)

    def test_conta_no_uso_da_ia_como_triagem(self):
        with mock.patch.object(server, "AI_MOCK", True):
            server.ai_triage([self.store.item(TV)])
        self.assertEqual(server.usage_summary()["today"]["kinds"].get("triagem"), 1)


class Lote(UnitBase):
    def run_batch(self, timeout=10):
        jid = server.news_batch_start()["id"]
        t0 = time.time()
        while server.WEB_JOBS[jid]["stage"] == "busy":
            if time.time() - t0 > timeout:
                self.fail("a conferência não terminou")
            time.sleep(0.05)
        return server.WEB_JOBS[jid]

    def setUp(self):
        super().setUp()
        p = mock.patch.object(server, "AI_MOCK", True)
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.object(server.time, "sleep", lambda s: None)  # a IA simulada não espera
        p2.start()
        self.addCleanup(p2.stop)

    def test_confere_so_o_que_a_ia_escolheu(self):
        job = self.run_batch()
        saved = server.news_read()["itens"]
        self.assertIn(TV, saved)
        self.assertIn(GELADEIRA, saved)
        self.assertNotIn(SOFA, saved)
        self.assertEqual(job["summary"]["conferidos"], len(saved))

    def test_escolha_da_ia_fica_guardada(self):
        self.run_batch()
        tri = server.news_read()["triagem"]
        self.assertTrue(tri[TV]["conferir"])
        self.assertFalse(tri[FRUTEIRA]["conferir"], "fruteira de madeira fica de fora")
        self.assertNotIn(SOFA, tri, "sofá nem vai para a IA: móveis não está marcada")

    def test_so_as_categorias_marcadas(self):
        self.store.settings["news_cats"] = ["cozinha"]
        self.run_batch()
        saved = server.news_read()["itens"]
        self.assertIn(GELADEIRA, saved)
        self.assertNotIn(TV, saved)

    def test_sem_categoria_marcada_recusa(self):
        self.store.settings["news_cats"] = []
        self.assertApiError(400, server.news_batch_start, msg_part="ao menos uma categoria")

    def test_ia_desligada_recusa(self):
        self.store.settings["ai"] = False
        self.assertApiError(409, server.news_batch_start)

    def test_sem_home_assistant_recusa(self):
        with mock.patch.object(server, "AI_MOCK", False):
            self.assertApiError(503, server.news_batch_start)

    def test_segunda_vez_na_semana_nao_confere_de_novo(self):
        self.run_batch()
        job = self.run_batch()
        self.assertEqual(job["summary"]["conferidos"], 0)
        self.assertGreater(job["summary"]["em_dia"], 0)

    def test_segunda_vez_nao_pergunta_a_ia_de_novo_quem_escolher(self):
        self.run_batch()
        n = server.usage_summary()["today"]["kinds"].get("triagem")
        self.run_batch()
        self.assertEqual(server.usage_summary()["today"]["kinds"].get("triagem"), n)

    def test_item_mudado_volta_para_a_ia_escolher(self):
        self.run_batch()
        self.assertFalse(server.news_read()["triagem"][FRUTEIRA]["conferir"])
        self.store.update_item(FRUTEIRA, {"name": "Smart TV 32 polegadas"}, "Diego")
        self.run_batch()
        self.assertTrue(server.news_read()["triagem"][FRUTEIRA]["conferir"])

    def test_conferido_ha_mais_de_uma_semana_entra_de_novo(self):
        self.run_batch()
        d = server.news_read()
        d["itens"][TV]["at"] = "2020-01-01T00:00:00-03:00"
        server.write_json_atomic(server.NEWS_FILE, d)
        job = self.run_batch()
        self.assertEqual(job["summary"]["conferidos"], 1)

    def test_mais_antigo_primeiro(self):
        self.run_batch()
        d = server.news_read()
        for iid in d["itens"]:
            d["itens"][iid]["at"] = "2020-02-01T00:00:00-03:00"
        d["itens"][GELADEIRA]["at"] = "2020-01-01T00:00:00-03:00"
        server.write_json_atomic(server.NEWS_FILE, d)
        seen = []
        real = server.ai_find_news
        with mock.patch.object(server, "ai_find_news", lambda n, de, e: seen.append(n) or real(n, de, e)):
            self.run_batch()
        self.assertEqual(seen[0], self.store.item(GELADEIRA)["name"])

    def test_cota_da_ia_para_e_o_que_foi_conferido_fica(self):
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            if len(calls) == 3:
                raise server.ApiError(502, "Erro 429: quota excedida")
            return novidade()
        with mock.patch.object(server, "ai_find_news", fake):
            job = self.run_batch()
        self.assertEqual(job["stage"], "error")
        self.assertIn("ficou salvo", job["msg"])
        self.assertEqual(len(server.news_read()["itens"]), 2)
        self.assertEqual(len(calls), 3, "parou na cota")

    def test_sem_busca_na_web_para_tudo(self):
        with mock.patch.object(server, "ai_find_news", mock.Mock(side_effect=server.ApiError(502, "A IA não usou a busca na web."))) as m:
            job = self.run_batch()
        self.assertEqual(job["stage"], "error")
        self.assertEqual(m.call_count, 1)

    def test_erro_de_um_item_nao_para_os_outros(self):
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            if len(calls) == 1:
                raise server.ApiError(500, "falhou")
            return novidade()
        with mock.patch.object(server, "ai_find_news", fake):
            job = self.run_batch()
        self.assertEqual(job["stage"], "done")
        self.assertEqual(job["summary"]["erros"], 1)
        self.assertEqual(job["summary"]["conferidos"], len(calls) - 1)

    def test_desligar_a_ia_no_meio_para(self):
        def fake(name, details, entity):
            self.store.settings["ai"] = False
            return novidade()
        with mock.patch.object(server, "ai_find_news", fake):
            job = self.run_batch()
        self.assertEqual(job["stage"], "error")
        self.assertEqual(len(server.news_read()["itens"]), 1)

    def test_parar_no_meio(self):
        def fake(name, details, entity):
            for j in server.WEB_JOBS.values():
                j["cancelled"] = True
            return novidade()
        with mock.patch.object(server, "ai_find_news", fake):
            job = self.run_batch()
        self.assertEqual(job["summary"]["conferidos"], 1)

    def test_uma_conferencia_por_vez(self):
        gate = []

        def slow(name, details, entity):
            while not gate:
                time.sleep(0.01)
            return novidade()
        with mock.patch.object(server, "ai_find_news", slow):
            a = server.news_batch_start()["id"]
            b = server.news_batch_start()["id"]
            gate.append(1)
            while server.WEB_JOBS[a]["stage"] == "busy":
                time.sleep(0.02)
        self.assertEqual(a, b)

    def test_progresso_diz_quantos_e_qual(self):
        seen = []

        def fake(name, details, entity):
            job = next(j for j in server.WEB_JOBS.values() if j.get("kind") == "lote")
            seen.append(dict(job["progress"]))
            return novidade()
        with mock.patch.object(server, "ai_find_news", fake):
            self.run_batch()
        self.assertEqual(seen[0]["feitos"], 0)
        self.assertEqual(seen[1]["feitos"], 1)
        self.assertTrue(seen[0]["atual"])
        self.assertEqual(seen[0]["total"], len(seen))

    def test_resumo_guardado_como_ultima(self):
        self.run_batch()
        u = server.news_read()["ultima"]
        self.assertTrue(u["at"])
        self.assertEqual(u["com_novidades"], u["conferidos"])


class Visao(UnitBase):
    def test_vazia_no_comeco(self):
        ov = server.news_overview()
        self.assertEqual((ov["triagem"], ov["itens"], ov["ultima"], ov["job"]), ({}, {}, None, None))
        self.assertGreater(ov["pendentes"], 0)

    def test_pendentes_sao_os_das_categorias_sem_escolha(self):
        self.store.settings["news_cats"] = ["eletronicos"]
        n = sum(1 for i in self.store.data["items"] if i["cat"] == "eletronicos")
        self.assertEqual(server.news_overview()["pendentes"], n)

    def test_resultado_de_um_item_aparece(self):
        server.news_save_result(TV, novidade()["novidades"] and server.news_clean(novidade()))
        ov = server.news_overview()
        self.assertEqual(ov["itens"][TV]["news"]["novidades"][0]["titulo"], "Firmware novo")
        self.assertTrue(ov["itens"][TV]["at"])

    def test_item_excluido_sai(self):
        server.news_save_result(TV, server.news_clean(novidade()))
        self.store.delete_item(TV)
        self.assertNotIn(TV, server.news_overview()["itens"])

    def test_escolha_de_item_mudado_nao_vale(self):
        d = server.news_read()
        d["triagem"][SOFA] = {"sig": "outro", "conferir": True}
        server.write_json_atomic(server.NEWS_FILE, d)
        self.assertNotIn(SOFA, server.news_overview()["triagem"])

    def test_arquivo_corrompido_vale_vazio(self):
        with open(server.NEWS_FILE, "w") as f:
            f.write("{quebrado")
        self.assertEqual(server.news_overview()["itens"], {})

    def test_um_item_conferido_pela_ficha_fica_guardado(self):
        with mock.patch.object(server, "AI_MOCK", True), mock.patch.object(server.time, "sleep", lambda s: None):
            jid = server.news_job_start({"item": TV})["id"]
            while server.WEB_JOBS[jid]["stage"] == "busy":
                time.sleep(0.02)
        self.assertIn(TV, server.news_overview()["itens"])

    def test_conferencia_andando_aparece(self):
        server.WEB_JOBS["0123456789abcdef"] = {"stage": "busy", "msg": "Conferindo 1 de 3: TV", "kind": "lote", "progress": {"feitos": 0, "total": 3, "atual": "TV"},
                                               "at": time.time(), "results": []}
        job = server.news_overview()["job"]
        self.assertEqual((job["id"], job["progress"]["total"]), ("0123456789abcdef", 3))

    def test_novidades_nao_entram_no_inventario(self):
        server.news_save_result(TV, server.news_clean(novidade()))
        self.assertNotIn("novidades", json.dumps(self.store.public()))


class Configuracao(UnitBase):
    class Pedido:
        def __init__(self, body):
            self.body, self.sent = body, None

        def read_body(self):
            return self.body

        def send_json(self, obj, status=200):
            self.sent = (status, obj)

    def put(self, body):
        h = self.Pedido(body)
        server.r_settings_put(h, {})
        return h.sent

    def test_grava_as_categorias(self):
        self.assertEqual(self.put({"news_cats": ["eletronicos", "cozinha"]})[1]["news_cats"], ["eletronicos", "cozinha"])

    def test_repetidas_ficam_uma_vez(self):
        self.assertEqual(self.put({"news_cats": ["eletronicos", "eletronicos"]})[1]["news_cats"], ["eletronicos"])

    def test_categoria_que_nao_existe_recusa(self):
        self.assertApiError(400, self.put, {"news_cats": ["nao-existe"]})

    def test_tem_que_ser_lista(self):
        self.assertApiError(400, self.put, {"news_cats": "eletronicos"})

    def test_lista_vazia_vale(self):
        self.assertEqual(self.put({"news_cats": []})[1]["news_cats"], [])


if __name__ == "__main__":
    unittest.main()
