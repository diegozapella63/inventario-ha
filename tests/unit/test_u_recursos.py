"""1.54.0: Recursos. O pedido à IA (o produto, os detalhes, a página indicada), a limpeza do que ela responde (nomes
curtos sem repetir, no máximo 12, a fonte só com http) e as respostas fora do formato ou sem nada."""
import threading
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
    """1.65.0: Buscar todos os recursos: um que a IA não achou conta como erro e os outros seguem; a cota acabou para."""
    def rodar(self, fake):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S, "ai_find_rec", fake):
            jid = S.rec_batch_start()["id"]
            job = S.WEB_JOBS[jid]
            t0 = time.time()
            while job["stage"] == "busy" and time.time() - t0 < 10:
                time.sleep(0.02)
            return job

    def test_uma_busca_andando_acompanha_a_mesma(self):
        solta = threading.Event()

        def fake(name, details, entity):
            solta.wait(5)
            return {"produto": name, "recursos": [{"nome": "Wi-Fi", "detalhe": ""}], "fonte": "", "site": ""}
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S, "ai_find_rec", fake):
            jid = S.rec_batch_start()["id"]
            self.assertEqual(S.rec_batch_start()["id"], jid)
            ov = S.rec_overview()
            self.assertEqual(ov["job"]["id"], jid, "e a lista diz que está andando")
            solta.set()
            t0 = time.time()
            while S.WEB_JOBS[jid]["stage"] == "busy" and time.time() - t0 < 10:
                time.sleep(0.02)

    def test_um_erro_nao_para_os_outros(self):
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            if len(calls) == 1:
                raise S.ApiError(502, "A IA não achou os recursos deste item.")
            return {"produto": name, "recursos": [{"nome": "Wi-Fi", "detalhe": ""}], "fonte": "", "site": ""}
        job = self.rodar(fake)
        self.assertEqual(job["stage"], "done", job)
        self.assertEqual((job["summary"]["erros"], job["summary"]["buscados"]), (1, len(calls) - 1))
        self.assertGreater(len(calls), 1)

    def test_a_cota_acabou_para(self):
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            if len(calls) == 2:
                raise S.ApiError(429, "A cota da IA acabou por hoje.")
            return {"produto": name, "recursos": [{"nome": "Wi-Fi", "detalhe": ""}], "fonte": "", "site": ""}
        job = self.rodar(fake)
        self.assertEqual((job["stage"], len(calls)), ("error", 2))
        self.assertIn("Os recursos já achados (1) ficaram salvos.", job["msg"])

    def test_parar(self):
        def fake(name, details, entity):
            for j in S.WEB_JOBS.values():
                if j.get("kind") == "recursos-lote":
                    j["cancelled"] = True
            return {"produto": name, "recursos": [{"nome": "Wi-Fi", "detalhe": ""}], "fonte": "", "site": ""}
        job = self.rodar(fake)
        self.assertEqual((job["stage"], job["summary"]["buscados"]), ("done", 0), "parou: o que estava sendo buscado não grava")

    def test_um_erro_inesperado(self):
        def fake(name, details, entity):
            raise ValueError("x")
        job = self.rodar(fake)
        self.assertEqual((job["stage"], job["msg"]), ("error", "Não deu para buscar agora. Tente de novo em instantes."))


if __name__ == "__main__":
    unittest.main()
