"""1.54.0: Recursos. O pedido à IA (o produto, os detalhes, a página indicada), a limpeza do que ela responde (nomes
curtos sem repetir, no máximo 12, a fonte só com http) e as respostas fora do formato ou sem nada."""
import json
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
        # 1.74.0: pela busca na web, com a data de hoje, e não de memória (como as novidades)
        self.assertIn("Use a busca na web agora", p)
        self.assertIn(f"Hoje é {S.news_today().isoformat()}.", p)
        self.assertIn("Não use o que você lembra de antes.", p)
        self.assertIn('{"erro": "sem_busca"}', p)
        self.assertNotIn("Se puder", p)


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
        with mock.patch.object(S, "AI_MOCK", False), mock.patch.object(S, "ai_call_text", return_value='{"erro": "sem_busca"}'):
            with self.assertRaises(S.ApiError) as e:
                S.ai_find_rec("TV", "", "ai_task.x")
            self.assertIn("não usou a busca na web", e.exception.msg, "sem a busca na web, não responde de memória")


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


class Escolher(UnitBase):
    """1.110.0 (o dono, em Recursos: "igual do Pareceres, ter aquele Escolher quais"): só os eletrônicos escolhidos, um por
    equipamento, e também os que já têm (buscados de novo); o que não é eletrônico ou não existe fica de fora."""
    REC = {"produto": "X", "recursos": [{"nome": "Bluetooth", "detalhe": ""}], "fonte": "", "site": ""}

    def test_so_os_escolhidos_e_de_novo(self):
        eletr = [it for it in S.STORE.data["items"] if it.get("cat") == S.REC_LOTE_CAT]
        self.assertGreater(len(eletr), 1, "a casa de teste tem eletrônicos")
        um = eletr[0]
        S.rec_save(um["id"], {"recursos": [{"nome": "Velho", "detalhe": ""}], "fonte": "", "site": ""})
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            return self.REC
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S, "ai_find_rec", fake), mock.patch.object(S.time, "sleep", lambda s: None):
            jid = S.news_batch_start(so="recursos", itens=[um["id"], "nao-existe"])["id"]
            job = S.WEB_JOBS[jid]
            t0 = time.time()
            while job["stage"] == "busy" and time.time() - t0 < 10:
                time.sleep(0.02)
        self.assertEqual((job["stage"], len(calls)), ("done", 1), job)
        grupo = [it for it in eletr if S.news_group_key(it) == S.news_group_key(um)]
        for it in grupo:
            self.assertEqual([r["nome"] for r in S.rec_of(it["id"])["recursos"]], ["Bluetooth"], "o grupo inteiro, também o que já tinha")
        outros = [it for it in eletr if S.news_group_key(it) != S.news_group_key(um)]
        self.assertTrue(all(not S.rec_of(it["id"]) for it in outros), "os não escolhidos ficam como estão")

    def test_o_que_vale(self):
        with self.assertRaises(S.ApiError) as e:
            S.news_batch_start(so="recursos", itens=["nao-existe"])
        self.assertIn("pelo menos um eletrônico", e.exception.msg)
        with self.assertRaises(S.ApiError) as e:
            S.news_batch_start(so="recursos", itens="x")
        self.assertIn("lista", e.exception.msg)
        with mock.patch.object(S, "news_enabled", lambda: True):
            with self.assertRaises(S.ApiError) as e:
                S.news_batch_start(so="itens", itens=[])
            self.assertIn("só para os recursos", e.exception.msg)


class Ferramentas1111(UnitBase):
    """1.111.0 (o dono, às ferramentas que faltavam para o CorrerIA: "pode colocar todas"): recursos (lê os guardados, um
    por equipamento) e buscar_recursos (o Os que faltam e o Escolher quais, em segundo plano)."""
    REC = {"produto": "X", "recursos": [{"nome": "Bluetooth", "detalhe": "Liga no celular."}], "fonte": "https://exemplo.com/x", "site": "exemplo.com"}

    def chamar(self, nome, args):
        import ferramentas as F
        return json.loads(F.chamar(S, nome, args, {"nome": "Ana"}, "Claude"))

    def test_recursos_e_buscar_recursos(self):
        import ferramentas as F
        nomes = [f["nome"] for f in F.lista()]
        self.assertIn("recursos", nomes)
        self.assertTrue(F.POR_NOME["buscar_recursos"]["grava"], "a busca gasta a IA: espera o sim")
        eletr = [it for it in S.STORE.data["items"] if it.get("cat") == S.REC_LOTE_CAT]
        um = eletr[0]
        S.rec_save(um["id"], self.REC)
        r = self.chamar("recursos", {})
        self.assertEqual([g["recursos"] for g in r["com_recursos"]], [["Bluetooth"]])
        self.assertTrue(r["sem_recursos"], "os que ainda não têm")
        self.assertTrue(all(g["comodos"] for g in r["sem_recursos"]))
        grupos = {S.news_group_key(it) for it in eletr}
        self.assertEqual(len(r["com_recursos"]) + len(r["sem_recursos"]), len(grupos), "um por equipamento")
        self.assertNotIn("com_recursos", self.chamar("recursos", {"so_sem": True}))
        um_r = self.chamar("recursos", {"id": um["id"]})
        self.assertEqual((um_r["recursos"][0]["detalhe"], um_r["fonte"]), ("Liga no celular.", "https://exemplo.com/x"))
        outro = next(it for it in eletr if S.news_group_key(it) != S.news_group_key(um))
        self.assertIn("inventario_buscar_recursos", self.chamar("recursos", {"id": outro["id"]})["aviso"])
        movel = next(it for it in S.STORE.data["items"] if it.get("cat") not in S.REC_CATS and not S.STORE.is_cons(it["room"]))
        import ferramentas as F
        with self.assertRaises(F.ErroFerramenta) as e:
            self.chamar("recursos", {"id": movel["id"]})
        self.assertIn("não é um eletrônico", str(e.exception))
        with self.assertRaises(F.ErroFerramenta) as e:
            self.chamar("buscar_recursos", {"ids": [movel["id"]]})
        self.assertIn("Não são eletrônicos", str(e.exception))
        with self.assertRaises(F.ErroFerramenta) as e:
            self.chamar("buscar_recursos", {"ids": "x"})
        self.assertIn("uma lista", str(e.exception))
        calls = []

        def fake(name, details, entity):
            calls.append(name)
            return self.REC
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S, "ai_find_rec", fake), mock.patch.object(S.time, "sleep", lambda s: None):
            r = self.chamar("buscar_recursos", {})
            self.assertEqual((r["comecou"], r["equipamentos"]), (True, len(grupos) - 1), "os que faltam")
            job = next(v for v in S.WEB_JOBS.values() if v.get("kind") == "lote")
            t0 = time.time()
            while job["stage"] == "busy" and time.time() - t0 < 10:
                time.sleep(0.02)
            self.assertEqual(len(calls), len(grupos) - 1)
            with self.assertRaises(F.ErroFerramenta) as e:
                self.chamar("buscar_recursos", {})
            self.assertIn("já têm os recursos", str(e.exception))
            calls.clear()
            r = self.chamar("buscar_recursos", {"ids": [S.STORE.tag(um)]})
            self.assertEqual(r["equipamentos"], 1, "pelo código, de novo")
            job = [v for v in S.WEB_JOBS.values() if v.get("kind") == "lote"][-1]
            t0 = time.time()
            while job["stage"] == "busy" and time.time() - t0 < 10:
                time.sleep(0.02)
            self.assertEqual(len(calls), 1)
            job["stage"] = "busy"
            with self.assertRaises(F.ErroFerramenta) as e:
                self.chamar("buscar_recursos", {"ids": [um["id"]]})
            self.assertIn("andando", str(e.exception))
            self.assertIn("buscando_agora", self.chamar("recursos", {}))
            job["stage"] = "done"
        S.STORE.settings["ai"] = False
        for nome in ("recursos", "buscar_recursos"):
            with self.assertRaises(F.ErroFerramenta) as e:
                self.chamar(nome, {})
            self.assertIn("IA do InventarIA está desligada", str(e.exception))
