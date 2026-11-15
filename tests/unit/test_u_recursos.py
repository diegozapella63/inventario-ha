"""1.54.0: Recursos. O pedido à IA (o produto, os detalhes, a página indicada), a limpeza do que ela responde (nomes
curtos sem repetir, no máximo 12, a fonte só com http) e as respostas fora do formato ou sem nada."""
import time
import unittest
from unittest import mock

from _boot import UnitBase, server as S


class Pedido(UnitBase):
    def test_o_pedido_leva_o_produto_os_detalhes_e_a_pagina(self):
        p = S.rec_prompt("Cafeteira Oster", "Manual em https://fab.exemplo/manual.pdf")
        self.assertIn("Produto: Cafeteira Oster", p)
        self.assertIn("comece por https://fab.exemplo/manual.pdf", p)
        self.assertIn('"recursos"', p)
        self.assertNotIn("Detalhes:", S.rec_prompt("Cafeteira", ""))


class Limpeza(UnitBase):
    def test_nomes_curtos_sem_repetir_no_maximo_12_e_a_fonte(self):
        raw = {"produto": " TV  55 ", "recursos": ["HDR", {"nome": "hdr", "detalhe": "x"}, {"name": "Wi-Fi", "detail": "Rede"}, {"nome": ""}, 3]
               + [{"nome": f"R{i}"} for i in range(20)], "fonte": "https://fab.exemplo/tv"}
        r = S.rec_clean(raw)
        self.assertEqual(r["produto"], "TV 55")
        self.assertEqual([x["nome"] for x in r["recursos"]][:3], ["HDR", "Wi-Fi", "R0"])
        self.assertEqual(len(r["recursos"]), 12)
        self.assertEqual((r["fonte"], r["site"]), ("https://fab.exemplo/tv", "fab.exemplo"))
        self.assertEqual(S.rec_clean({"recursos": [], "fonte": "javascript:alert(1)"})["fonte"], "")
        self.assertEqual(S.rec_clean("nada")["recursos"], [])

    def test_a_ia_de_verdade_fora_do_formato_ou_sem_nada(self):
        with mock.patch.object(S, "AI_MOCK", False), mock.patch.object(S, "ai_call_text", return_value="não sei"):
            with self.assertRaises(S.ApiError) as e:
                S.ai_find_rec("TV", "", "ai_task.x")
            self.assertEqual(e.exception.status, 502)
        with mock.patch.object(S, "AI_MOCK", False), mock.patch.object(S, "ai_call_text", return_value='{"recursos": []}'):
            with self.assertRaises(S.ApiError) as e:
                S.ai_find_rec("TV", "", "ai_task.x")
            self.assertIn("marca e o modelo", e.exception.msg)
        with mock.patch.object(S, "AI_MOCK", False), mock.patch.object(S, "ai_call_text", return_value={"recursos": [{"nome": "Timer"}]}):
            self.assertEqual(S.ai_find_rec("TV", "", "ai_task.x")["recursos"], [{"nome": "Timer", "detalhe": ""}])


class Todos(UnitBase):
    """1.68.0: Conferir novidades › Só eletrônicos (so=recursos): um que a IA não achou conta como erro e os outros seguem;
    a cota acabou para; Parar não grava o que estava sendo buscado; Todas as novidades (não a sozinha) busca também."""
    REC = {"produto": "X", "recursos": [{"nome": "Wi-Fi", "detalhe": ""}], "fonte": "", "site": ""}

    def rodar(self, fake, so="recursos", auto=False):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S, "ai_find_rec", fake), \
                mock.patch.object(S, "ai_find_news", lambda *a: S.news_clean({"novidades": []})), mock.patch.object(S.time, "sleep", lambda s: None):
            jid = S.news_batch_start(so=so, auto=auto)["id"]
            job = S.WEB_JOBS[jid]
            t0 = time.time()
            while job["stage"] == "busy" and time.time() - t0 < 10:
                time.sleep(0.02)
            return job

    def test_um_erro_nao_para_os_outros(self):
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            if len(calls) == 1:
                raise S.ApiError(502, "A IA não achou os recursos deste item.")
            return self.REC
        job = self.rodar(fake)
        self.assertEqual(job["stage"], "done", job)
        self.assertEqual((job["summary"]["erros"], job["summary"]["recursos"]), (1, len(calls) - 1))
        self.assertGreater(len(calls), 1)
        self.assertIsNone(S.news_read().get("ultima"), "Só eletrônicos não é uma conferência das novidades")

    def test_a_cota_acabou_para(self):
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            if len(calls) == 2:
                raise S.ApiError(429, "A cota da IA acabou por hoje.")
            return self.REC
        job = self.rodar(fake)
        self.assertEqual((job["stage"], len(calls)), ("error", 2))
        self.assertIn("O que já foi conferido (1) ficou salvo.", job["msg"])

    def test_parar(self):
        def fake(name, details, entity):
            for j in S.WEB_JOBS.values():
                if j.get("kind") == "lote":
                    j["cancelled"] = True
            return self.REC
        job = self.rodar(fake)
        self.assertEqual(job["summary"]["recursos"], 0, "parou: o que estava sendo buscado não grava")

    def test_todas_busca_os_recursos_a_sozinha_nao(self):
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            return self.REC
        job = self.rodar(fake, so="", auto=True)
        self.assertEqual((job["stage"], calls), ("done", []), "o Conferir sozinho não busca os recursos")
        job = self.rodar(fake, so="")
        self.assertEqual(job["stage"], "done", job)
        self.assertTrue(calls and job["summary"]["recursos"] == len(calls), "Todas as novidades busca os recursos que faltam")


if __name__ == "__main__":
    unittest.main()
