"""Novidades do produto: as instruções para a IA, a conferência do que ela achou e o trabalho em segundo plano."""
import json
import time
import unittest
from unittest import mock

from _boot import UnitBase, server

ITEM = "sal-007"  # Smart TV 55 polegadas, na casa de teste


def resposta(*novidades, produto="Smart TV 55 polegadas", **extra):
    return {"produto": produto, "novidades": list(novidades), **extra}


def nova(**kw):
    base = {"tipo": "atualizacao", "titulo": "Atualização de software", "resumo": "Corrige o Wi-Fi.", "data": "2026-09-12",
            "fonte": "https://fabricante.exemplo/notas", "boato": False}
    base.update(kw)
    return base


class Instrucoes(UnitBase):
    def test_traz_o_nome_e_os_detalhes(self):
        p = server.news_prompt("Lâmpada Wi-Fi Exemplo LX-10", "Colorida, rosca E27")
        self.assertIn("Produto: Lâmpada Wi-Fi Exemplo LX-10", p)
        self.assertIn("Detalhes: Colorida, rosca E27", p)

    def test_sem_detalhes_nao_tem_a_linha(self):
        self.assertNotIn("Detalhes:", server.news_prompt("Lâmpada", ""))

    def test_pede_a_busca_na_web(self):
        self.assertIn("Use a busca na web agora", server.news_prompt("Lâmpada", ""))

    def test_diz_a_data_de_hoje(self):
        self.assertIn("Hoje é 2026-11-04", server.news_prompt("Lâmpada", ""), "a data de hoje (INV_HOJE nos testes)")

    def test_pede_os_cinco_assuntos(self):
        p = server.news_prompt("Lâmpada", "")
        for t in ("firmware", "modelo novo", "lançamentos anunciados", "recall deste modelo", "fim de suporte"):
            self.assertIn(t, p)

    def test_pede_fonte_e_nada_inventado(self):
        p = server.news_prompt("Lâmpada", "")
        self.assertIn("Cada novidade precisa de uma fonte", p)
        self.assertIn("Não invente", p)

    def test_boato_so_marcado(self):
        self.assertIn("boato", server.news_prompt("Lâmpada", ""))

    def test_pede_json_e_o_erro_sem_busca(self):
        p = server.news_prompt("Lâmpada", "")
        self.assertIn('"novidades"', p)
        self.assertIn('{"erro": "sem_busca"}', p)

    def test_pede_so_as_3_mais_recentes(self):
        self.assertEqual(server.NEWS_MAX, 3)
        self.assertIn("Só as 3 novidades mais recentes", server.news_prompt("Lâmpada", ""))

    def test_recall_so_o_de_verdade(self):
        p = server.news_prompt("Lâmpada", "")
        self.assertIn("chama o produto de volta para troca, conserto ou reembolso", p)
        self.assertIn("Falha de segurança corrigida por atualização é atualizacao, não recall", p)


class SoRecentes(UnitBase):
    """Só o que é dos últimos 12 meses (hoje é 2026-11-04 nos testes): a IA às vezes traz notícia de anos atrás."""
    def test_regra_dos_12_meses(self):
        for data, ok in (("", True), ("2026-11-04", True), ("2025-11-04", True), ("2025-11-03", False), ("2025-11", True), ("2025-10", False),
                         ("2025", True), ("2024", False), ("2023-09", False), ("2027-03", True)):
            with self.subTest(data=data):
                self.assertIs(server.news_recent(data), ok)

    def test_antigas_saem_da_resposta(self):
        r = server.news_clean(resposta(nova(titulo="nova", data="2026-09"), nova(titulo="velha", data="2023"), nova(titulo="velha2", data="2024-05-01")))
        self.assertEqual([n["titulo"] for n in r["novidades"]], ["nova"])

    def test_antigas_guardadas_tambem_saem(self):
        TV = "sal-007"
        server.write_json_atomic(server.NEWS_FILE, {"itens": {TV: {"at": "2026-11-01T10:00:00-03:00", "news": {"produto": "TV", "novidades": [
            {"tipo": "atualizacao", "titulo": "Nova", "data": "2026-09", "fonte": "https://f.exemplo/a"},
            {"tipo": "recall", "titulo": "Recall antigo", "data": "2023-09", "fonte": "https://f.exemplo/b"}]}}}, "triagem": {}})
        self.assertEqual([n["titulo"] for n in server.news_of(TV)["news"]["novidades"]], ["Nova"])

    def test_sem_INV_HOJE_vale_o_dia_de_hoje(self):
        import datetime as dt
        with mock.patch.dict("os.environ", {"INV_HOJE": ""}):
            self.assertEqual(server.news_today(), dt.date.today())


class Recall(UnitBase):
    """A IA marcava recall demais: só fica recall quando o texto fala de recall de verdade."""
    def tipo(self, titulo, resumo=""):
        return server.news_clean({"novidades": [{"tipo": "recall", "titulo": titulo, "resumo": resumo, "data": "2026-09",
                                                 "fonte": "https://fab.exemplo/n"}]})["novidades"][0]["tipo"]

    def test_recall_de_verdade_fica(self):
        for titulo, resumo in (("Recall de carregadores", ""), ("Chamamento para troca da bateria", ""),
                               ("Troca da fonte em um lote", "Aparelhos de um lote podem esquentar."),
                               ("Senacon anuncia convocação", ""), ("Fabricante oferece reembolso", "Risco de incêndio na tomada."),
                               ("Devolução de unidades com defeito", "")):
            self.assertEqual(self.tipo(titulo, resumo), "recall", titulo)

    def test_falha_de_seguranca_corrigida_vira_atualizacao(self):
        self.assertEqual(self.tipo("Vulnerabilidade corrigida", "Firmware novo fecha falha de segurança."), "atualizacao")
        self.assertEqual(self.tipo("Patch de segurança para a câmera"), "atualizacao")
        self.assertEqual(self.tipo("Vulnerabilidades de segurança CVE-2026-1234 corrigidas"), "atualizacao")

    def test_falha_so_anunciada_vira_novidade(self):
        self.assertEqual(self.tipo("Vulnerabilidades com potencial roubo de senha Wi-Fi", "Pesquisadores acharam falhas na autenticação."), "outro")

    def test_noticia_comum_vira_outro(self):
        self.assertEqual(self.tipo("Marca lança linha nova de lâmpadas", "Mais brilho e cores."), "outro")

    def test_outros_tipos_nao_mudam(self):
        for k in ("atualizacao", "lancamento", "sucessor", "suporte", "outro"):
            self.assertEqual(server.news_kind(k, "Recall em massa"), k)

    def test_tipo_desconhecido_vira_outro(self):
        self.assertEqual(server.news_kind("aviso", "x"), "outro")

    def test_guardados_antes_tambem_sao_conferidos(self):
        TV = "sal-007"
        server.write_json_atomic(server.NEWS_FILE, {"itens": {TV: {"at": "2026-11-01T10:00:00-03:00", "news": {"produto": "TV", "novidades": [
            {"tipo": "recall", "titulo": "Atualização de firmware", "resumo": "Corrige falha de segurança.", "data": "2026-10", "fonte": "https://f.exemplo/a"},
            {"tipo": "recall", "titulo": "Recall de controles remotos", "resumo": "", "data": "2026-09", "fonte": "https://f.exemplo/b"},
            {"tipo": "recall", "titulo": "Nova cor disponível", "resumo": "", "data": "2026-08", "fonte": "https://f.exemplo/c"}]}}}, "triagem": {}})
        got = [n["tipo"] for n in server.news_overview()["itens"][TV]["news"]["novidades"]]
        self.assertEqual(got, ["atualizacao", "recall", "outro"])
        self.assertEqual([n["tipo"] for n in server.news_of(TV)["news"]["novidades"]], ["atualizacao", "recall", "outro"], "na ficha também")


class Conferencia(UnitBase):
    def test_novidade_completa(self):
        r = server.news_clean(resposta(nova()))
        self.assertEqual(r["novidades"], [{"tipo": "atualizacao", "titulo": "Atualização de software", "resumo": "Corrige o Wi-Fi.",
                                           "data": "2026-09-12", "fonte": "https://fabricante.exemplo/notas", "site": "fabricante.exemplo", "boato": False}])

    def test_produto_identificado(self):
        self.assertEqual(server.news_clean(resposta(produto="  Exemplo   LX-10 ")).get("produto"), "Exemplo LX-10")

    def test_sem_fonte_sai(self):
        self.assertEqual(server.news_clean(resposta(nova(fonte="")))["novidades"], [])

    def test_fonte_que_nao_e_http_sai(self):
        for u in ("javascript:alert(1)", "ftp://x.exemplo/a", "data:text/html,oi", "fabricante.exemplo/notas"):
            with self.subTest(u=u):
                self.assertEqual(server.news_clean(resposta(nova(fonte=u)))["novidades"], [])

    def test_fonte_sem_protocolo_com_barras_vira_https(self):
        self.assertEqual(server.news_clean(resposta(nova(fonte="//fabricante.exemplo/a")))["novidades"][0]["fonte"], "https://fabricante.exemplo/a")

    def test_sem_titulo_sai(self):
        self.assertEqual(server.news_clean(resposta(nova(titulo="   ")))["novidades"], [])

    def test_titulo_longo_cortado(self):
        self.assertEqual(len(server.news_clean(resposta(nova(titulo="x" * 500)))["novidades"][0]["titulo"]), 160)

    def test_resumo_longo_cortado_e_espacos_juntos(self):
        n = server.news_clean(resposta(nova(resumo="a  b\n\nc" + " d" * 400)))["novidades"][0]
        self.assertTrue(n["resumo"].startswith("a b c d"))
        self.assertLessEqual(len(n["resumo"]), 400)

    def test_tipo_desconhecido_vira_outro(self):
        self.assertEqual(server.news_clean(resposta(nova(tipo="promoção")))["novidades"][0]["tipo"], "outro")

    def test_tipo_com_acento_e_maiuscula(self):
        self.assertEqual(server.news_clean(resposta(nova(tipo="Atualização")))["novidades"][0]["tipo"], "atualizacao")

    def test_todos_os_tipos_conhecidos(self):
        for k in server.NEWS_KINDS:
            with self.subTest(k=k):
                self.assertEqual(server.news_clean(resposta(nova(tipo=k, titulo="Recall do controle" if k == "recall" else "Atualização")))["novidades"][0]["tipo"], k)

    def test_datas_aceitas(self):
        for d in ("2026", "2026-09", "2026-09-12"):
            with self.subTest(d=d):
                self.assertEqual(server.news_clean(resposta(nova(data=d)))["novidades"][0]["data"], d)

    def test_data_em_outro_formato_fica_vazia(self):
        for d in ("12/09/2026", "setembro de 2026", "2026/09", "26", None):
            with self.subTest(d=d):
                self.assertEqual(server.news_clean(resposta(nova(data=d)))["novidades"][0]["data"], "")

    def test_ano_em_numero_vale(self):
        self.assertEqual(server.news_clean(resposta(nova(data=2026)))["novidades"][0]["data"], "2026")

    def test_das_mais_novas_para_as_mais_antigas_sem_data_no_fim(self):
        r = server.news_clean(resposta(nova(titulo="a", data="2026-01"), nova(titulo="b", data=""), nova(titulo="c", data="2026-10-01")))
        self.assertEqual([n["titulo"] for n in r["novidades"]], ["c", "a", "b"])

    def test_ficam_so_as_3_mais_recentes(self):
        r = server.news_clean(resposta(nova(titulo="a", data="2025-01"), nova(titulo="b", data=""), nova(titulo="c", data="2026-10-01"),
                                       nova(titulo="d", data="2026"), nova(titulo="e", data="2026-08")))
        self.assertEqual([n["titulo"] for n in r["novidades"]], ["c", "e", "d"])

    def test_repetidas_saem(self):
        r = server.news_clean(resposta(nova(), nova(titulo="ATUALIZAÇÃO DE SOFTWARE".lower()), nova(fonte="https://outro.exemplo/x")))
        self.assertEqual(len(r["novidades"]), 2)

    def test_limite_de_novidades(self):
        r = server.news_clean(resposta(*[nova(titulo=f"n{i}", fonte=f"https://s.exemplo/{i}") for i in range(30)]))
        self.assertEqual(len(r["novidades"]), server.NEWS_MAX)

    def test_boato_so_quando_verdadeiro(self):
        self.assertTrue(server.news_clean(resposta(nova(boato=True)))["novidades"][0]["boato"])
        for v in ("sim", 1, None, "true"):
            with self.subTest(v=v):
                self.assertFalse(server.news_clean(resposta(nova(boato=v)))["novidades"][0]["boato"])

    def test_nomes_em_ingles_tambem(self):
        r = server.news_clean({"product": "TV", "news": [{"type": "recall", "title": "Recall", "summary": "Troca.", "date": "2026-01",
                                                          "url": "https://x.exemplo/r", "rumor": True}]})
        self.assertEqual((r["produto"], r["novidades"][0]["tipo"], r["novidades"][0]["boato"]), ("TV", "recall", True))

    def test_resposta_que_nao_e_objeto(self):
        for v in (None, [], "texto", 3):
            with self.subTest(v=v):
                self.assertEqual(server.news_clean(v), {"produto": "", "novidades": []})

    def test_novidades_que_nao_sao_lista_ou_objeto(self):
        self.assertEqual(server.news_clean({"novidades": "várias"})["novidades"], [])
        self.assertEqual(server.news_clean({"novidades": ["texto", 3, None, nova()]})["novidades"][0]["titulo"], "Atualização de software")

    def test_site_da_fonte(self):
        self.assertEqual(server.news_clean(resposta(nova(fonte="https://www.loja.exemplo/p?a=1")))["novidades"][0]["site"], "loja.exemplo")


class ComHomeAssistant(UnitBase):
    def test_tarefa_de_ia_traz_as_novidades(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps(resposta(nova()))
        r = server.ai_find_news("Smart TV", "", "ai_task.google_ai_task")
        self.assertEqual(len(r["novidades"]), 1)
        req = ha.calls("POST", "/core/api/services/ai_task")[-1]
        self.assertEqual(req["body"]["entity_id"], "ai_task.google_ai_task")
        self.assertEqual(req["body"]["task_name"], "InventarIA: novidades")

    def test_assistente_de_conversa_traz_as_novidades(self):
        ha = self.fake_ha()
        ha.conversation_reply = lambda payload: "Aqui está:\n```json\n" + json.dumps(resposta(nova())) + "\n```"
        r = server.ai_find_news("Smart TV", "", "conversation.google_generative_ai")
        self.assertEqual(r["novidades"][0]["fonte"], "https://fabricante.exemplo/notas")
        self.assertEqual(ha.calls("POST", "/core/api/services/conversation")[-1]["body"]["agent_id"], "conversation.google_generative_ai")

    def test_sem_busca_na_web_explica(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: '{"erro": "sem_busca"}'
        e = self.assertApiError(502, server.ai_find_news, "TV", "", "")
        self.assertIn("busca na web", e.msg)

    def test_resposta_fora_do_formato_explica(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: "Não sei de novidades."
        self.assertApiError(502, server.ai_find_news, "TV", "", "", msg_part="busca na web")

    def test_nada_novo_e_lista_vazia(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps(resposta())
        self.assertEqual(server.ai_find_news("TV", "", "")["novidades"], [])

    def test_conta_no_uso_da_ia_como_novidades(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps(resposta(nova()))
        server.ai_find_news("TV", "", "")
        u = server.usage_summary()
        self.assertEqual(u["today"]["kinds"].get("novidades"), 1)
        self.assertEqual(u["recent"][0]["kind"], "novidades")

    def test_sem_busca_conta_como_sem_busca(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: '{"erro": "sem_busca"}'
        with self.assertRaises(server.ApiError):
            server.ai_find_news("TV", "", "")
        self.assertEqual(server.usage_summary()["recent"][0]["result"], "sem_busca")


class Trabalho(UnitBase):
    def wait(self, jid, timeout=5):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if server.WEB_JOBS[jid]["stage"] != "busy":
                return server.WEB_JOBS[jid]
            time.sleep(0.05)
        self.fail("a busca não terminou")

    def test_item_que_nao_existe(self):
        with mock.patch.object(server, "AI_MOCK", True):
            self.assertApiError(404, server.news_job_start, {"item": "nao-existe"})

    def test_ia_desligada_recusa(self):
        self.store.settings["ai"] = False
        with mock.patch.object(server, "AI_MOCK", True):
            self.assertApiError(409, server.news_job_start, {"item": ITEM})

    def test_sem_home_assistant_recusa(self):
        self.assertApiError(503, server.news_job_start, {"item": ITEM})

    def test_simulado_termina_com_o_exemplo(self):
        with mock.patch.object(server, "AI_MOCK", True), mock.patch.dict("os.environ", {"INV_MOCK_NEWS": ""}):
            jid = server.news_job_start({"item": ITEM})["id"]
            job = self.wait(jid)
        self.assertEqual(job["stage"], "done")
        self.assertEqual(len(job["news"]["novidades"]), 3)

    def test_usa_o_nome_e_os_detalhes_do_item(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps(resposta())
        it = self.store.item(ITEM)
        self.wait(server.news_job_start({"item": ITEM})["id"])
        instr = ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]
        self.assertIn(f"Produto: {it['name']}", instr)
        if it.get("details"):
            self.assertIn(" ".join(it["details"].split())[:60], instr)

    def test_usa_a_ia_de_busca_escolhida(self):
        ha = self.fake_ha()
        ha.conversation_reply = lambda payload: json.dumps(resposta())
        self.store.settings["ai_search"] = "conversation.google_generative_ai"
        self.wait(server.news_job_start({"item": ITEM})["id"])
        self.assertEqual(len(ha.calls("POST", "/core/api/services/conversation")), 1)

    def test_erro_da_ia_vira_mensagem_do_trabalho(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: '{"erro": "sem_busca"}'
        job = self.wait(server.news_job_start({"item": ITEM})["id"])
        self.assertEqual(job["stage"], "error")
        self.assertIn("busca na web", job["msg"])

    def test_desligar_a_ia_no_meio_nao_entrega(self):
        with mock.patch.object(server, "AI_MOCK", True):
            jid = server.news_job_start({"item": ITEM})["id"]
            self.wait(jid)
        self.store.settings["ai"] = False
        self.assertApiError(409, server.web_job, jid)

    def test_cancelada_nao_guarda_o_resultado(self):
        with mock.patch.object(server, "AI_MOCK", True):
            jid = server.news_job_start({"item": ITEM})["id"]
            server.WEB_JOBS[jid]["cancelled"] = True
            job = self.wait(jid) if server.WEB_JOBS[jid]["stage"] != "busy" else None
            time.sleep(0.6)
        self.assertIsNone(server.WEB_JOBS[jid].get("news"))
        del job


if __name__ == "__main__":
    unittest.main()
