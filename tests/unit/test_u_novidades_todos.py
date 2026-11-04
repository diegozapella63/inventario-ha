"""Novidades de todos os equipamentos (Mais > Novidades): só Eletrônicos, a escolha da IA, a conferência em lote e o que fica guardado."""
import json
import time
import unittest
from unittest import mock

from _boot import UnitBase, server

TV, SOFA, GELADEIRA, FRUTEIRA = "sal-007", "sal-001", "coz-004", "coz-003"
AR, NOTEBOOK, CAIXA = "qua-005", "esc-001", "sal-010"  # eletrônicos: a IA simulada deixa a caixa de som de estante de fora


def novidade(titulo="Firmware novo", tipo="atualizacao"):
    return {"produto": "x", "novidades": [{"tipo": tipo, "titulo": titulo, "data": "2026-09", "fonte": "https://fab.exemplo/n"}]}


class Categorias(UnitBase):
    def test_so_eletronicos(self):
        self.assertEqual(server.news_cats(), ["eletronicos"])

    def test_nada_de_moveis_cozinha_ou_outras(self):
        for c in ("moveis", "decoracao", "texteis", "plantas", "livros", "vestuario", "cozinha", "utilidades", "saude", "outros"):
            self.assertNotIn(c, server.news_cats())

    def test_categoria_criada_com_nome_parecido_nao_entra(self):
        self.store.create_cat({"name": "Informática"})
        self.assertEqual(server.news_cats(), ["eletronicos"])

    def test_escolha_antiga_gravada_nao_vale_mais(self):
        self.store.settings["news_cats"] = ["cozinha", "utilidades"]
        self.assertEqual(server.news_cats(), ["eletronicos"])

    def test_eletronicos_renomeada_continua(self):
        self.store.update_cat("eletronicos", {"name": "Tecnologia"})
        self.assertEqual(server.news_cats(), ["eletronicos"])

    def test_eletronicos_excluida_fica_sem(self):
        self.store.delete_cat("eletronicos")
        self.assertEqual(server.news_cats(), [])

    def test_eletronicos_criada_de_novo_volta(self):
        self.store.delete_cat("eletronicos")
        self.store.create_cat({"name": "Eletrônicos"})
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
        self.assertIn(NOTEBOOK, saved)
        self.assertIn(AR, saved)
        self.assertNotIn(CAIXA, saved, "a IA deixou de fora")
        self.assertNotIn(SOFA, saved)
        self.assertEqual(job["summary"]["conferidos"], len(saved))

    def test_escolha_da_ia_fica_guardada(self):
        self.run_batch()
        tri = server.news_read()["triagem"]
        self.assertTrue(tri[TV]["conferir"])
        self.assertFalse(tri[CAIXA]["conferir"], "a caixa de som de estante fica de fora")
        self.assertNotIn(SOFA, tri, "sofá nem vai para a IA: não é eletrônico")
        self.assertNotIn(GELADEIRA, tri, "nem a geladeira (Cozinha e bar)")

    def test_escolha_antiga_de_categorias_nao_vale(self):
        self.store.settings["news_cats"] = ["cozinha"]
        self.run_batch()
        saved = server.news_read()["itens"]
        self.assertIn(TV, saved)
        self.assertNotIn(GELADEIRA, saved)

    def test_sem_a_categoria_eletronicos_recusa(self):
        self.store.delete_cat("eletronicos")
        self.assertApiError(400, server.news_batch_start, msg_part="Eletrônicos foi excluída")

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
        self.assertFalse(server.news_read()["triagem"][CAIXA]["conferir"])
        self.store.update_item(CAIXA, {"name": "Smart TV 32 polegadas"}, "Diego")
        self.run_batch()
        self.assertTrue(server.news_read()["triagem"][CAIXA]["conferir"])

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
        d["itens"][NOTEBOOK]["at"] = "2020-01-01T00:00:00-03:00"
        server.write_json_atomic(server.NEWS_FILE, d)
        seen = []
        real = server.ai_find_news
        with mock.patch.object(server, "ai_find_news", lambda n, de, e: seen.append(n) or real(n, de, e)):
            self.run_batch()
        self.assertEqual(seen[0], self.store.item(NOTEBOOK)["name"])

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


class Limite(UnitBase):
    def test_guardadas_antes_do_limite_mostram_so_as_3_mais_recentes(self):
        velhas = {"produto": "TV", "novidades": [{"tipo": "outro", "titulo": f"n{i}", "data": f"2026-{12 - i:02d}", "fonte": f"https://s.exemplo/{i}"}
                                               for i in range(10)]}
        server.write_json_atomic(server.NEWS_FILE, {"itens": {TV: {"at": "2026-11-01T10:00:00-03:00", "news": velhas}}, "triagem": {}})
        got = server.news_overview()["itens"][TV]["news"]["novidades"]
        self.assertEqual([n["titulo"] for n in got], ["n0", "n1", "n2"])

    def test_guardada_estranha_nao_quebra(self):
        server.write_json_atomic(server.NEWS_FILE, {"itens": {TV: {"at": "x", "news": {"novidades": "nada"}}, SOFA: "lixo"}, "triagem": {}})
        self.assertIn(TV, server.news_overview()["itens"])


class Limpar(UnitBase):
    def guardar(self):
        server.news_save_result(TV, server.news_clean(novidade()))
        d = server.news_read()
        d["triagem"][TV] = {"sig": server.item_sig(self.store.item(TV)), "conferir": True}
        d["ultima"] = {"at": "2026-11-01T10:00:00-03:00", "conferidos": 1, "com_novidades": 1}
        server.write_json_atomic(server.NEWS_FILE, d)

    def test_apaga_novidades_escolhas_e_a_ultima(self):
        self.guardar()
        ov = server.news_clear()
        self.assertEqual((ov["itens"], ov["triagem"], ov["ultima"]), ({}, {}, None))
        self.assertEqual(server.news_overview()["itens"], {})

    def test_nao_muda_o_inventario(self):
        self.guardar()
        antes = json.dumps(self.store.public(), sort_keys=True)
        server.news_clear()
        self.assertEqual(json.dumps(self.store.public(), sort_keys=True), antes)

    def test_continua_so_eletronicos(self):
        server.news_clear()
        self.assertEqual(server.news_cats(), ["eletronicos"])

    def test_para_a_conferencia_em_andamento(self):
        job = {"stage": "busy", "msg": "", "kind": "lote", "at": time.time(), "results": []}
        server.WEB_JOBS["0123456789abcdef"] = job
        server.news_clear()
        self.assertTrue(job["cancelled"])
        self.assertNotIn("0123456789abcdef", server.WEB_JOBS)

    def test_busca_de_um_item_continua(self):
        job = {"stage": "busy", "msg": "", "kind": "novidades", "at": time.time(), "results": []}
        server.WEB_JOBS["0123456789abcdef"] = job
        server.news_clear()
        self.assertIn("0123456789abcdef", server.WEB_JOBS)

    def test_conferencia_limpa_no_meio_nao_grava_mais_nada(self):
        with mock.patch.object(server, "AI_MOCK", True), mock.patch.object(server.time, "sleep", lambda s: None):
            calls = []

            def fake(name, details, entity):
                calls.append(name)
                if len(calls) == 2:
                    server.news_clear()
                return novidade()
            with mock.patch.object(server, "ai_find_news", fake):
                jid = server.news_batch_start()["id"]
                job = server.WEB_JOBS[jid]
                t0 = time.time()
                while job["stage"] == "busy" and time.time() - t0 < 10:
                    time.sleep(0.02)
        self.assertEqual(len(calls), 2, "parou logo depois de limpar")
        d = server.news_read()
        self.assertEqual((d["itens"], d.get("ultima")), ({}, None), "nada gravado depois de limpar")

    def test_limpar_sem_nada_guardado(self):
        ov = server.news_clear()
        self.assertEqual(ov["itens"], {})


class DeUmItem(UnitBase):
    """O que a ficha do item mostra: o que já foi conferido dele."""
    def test_nunca_conferido_vem_vazio(self):
        self.assertEqual(server.news_of(TV), {})

    def test_conferido_vem_com_data_e_novidades(self):
        server.news_save_result(TV, server.news_clean(novidade()))
        r = server.news_of(TV)
        self.assertTrue(r["at"])
        self.assertEqual(r["news"]["novidades"][0]["titulo"], "Firmware novo")

    def test_so_as_3_mais_recentes(self):
        velhas = {"produto": "TV", "novidades": [{"tipo": "outro", "titulo": f"n{i}", "data": f"2026-{12 - i:02d}", "fonte": f"https://s.exemplo/{i}"}
                                               for i in range(6)]}
        server.write_json_atomic(server.NEWS_FILE, {"itens": {TV: {"at": "2026-11-01T10:00:00-03:00", "news": velhas}}, "triagem": {}})
        self.assertEqual(len(server.news_of(TV)["news"]["novidades"]), 3)

    def test_item_excluido_vem_vazio(self):
        server.news_save_result(TV, server.news_clean(novidade()))
        self.store.delete_item(TV)
        self.assertEqual(server.news_of(TV), {})

    def test_item_de_outra_categoria_tambem(self):
        server.news_save_result(GELADEIRA, server.news_clean(novidade()))
        self.assertIn("news", server.news_of(GELADEIRA), "a ficha mostra mesmo fora de Eletrônicos")

    def test_guardado_estranho_vem_vazio(self):
        server.write_json_atomic(server.NEWS_FILE, {"itens": {TV: {"at": "x", "news": "lixo"}}, "triagem": {}})
        self.assertEqual(server.news_of(TV), {})

    def test_depois_de_limpar_vem_vazio(self):
        server.news_save_result(TV, server.news_clean(novidade()))
        server.news_clear()
        self.assertEqual(server.news_of(TV), {})


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

    def test_categorias_nao_se_escolhem_mais(self):
        st, out = self.put({"news_cats": ["cozinha"], "zones": True})
        self.assertEqual(st, 200)
        self.assertNotIn("news_cats", out, "o pedido antigo não grava nada")
        self.assertTrue(out["zones"], "e o resto do pedido vale")
        self.assertEqual(server.news_cats(), ["eletronicos"])


if __name__ == "__main__":
    unittest.main()
