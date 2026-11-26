"""1.103.0 (o dono: "criar botão para avaliar com a IA, para que a IA traga um parecer do consumível, qualidade, etc."): o
Avaliar com IA de um consumível. O pedido (o produto, os detalhes, a busca na web), a limpeza do que a IA responde (a nota de
1 a 5 em meio ponto, as listas curtas, as fontes só com http), o parecer guardado até o item mudar, só dos consumíveis, só
com a IA ligada, e a ferramenta avaliar do CorrerIA. Os produtos são inventados."""
import json
import time
from unittest import mock

from _boot import UnitBase, server as S

import ferramentas as F


class Base(UnitBase):
    def setUp(self):
        super().setUp()
        self.store.settings["consumiveis"] = True
        area = self.store.create_room({"kind": "consumiveis"})
        self.cons = self.store.create_items([{"room": area["id"], "name": "Pasta térmica Exemplo", "details": "Em seringa, para o processador."}], "Ana")[0]


class Pedido(Base):
    def test_o_pedido_leva_o_produto_e_pede_a_busca_na_web(self):
        p = S.par_prompt(self.cons)
        self.assertIn("Produto: Pasta térmica Exemplo", p)
        self.assertIn("Detalhes: Em seringa, para o processador.", p)
        self.assertIn("Use a busca na web agora", p)
        self.assertIn(f"Hoje é {S.news_today().isoformat()}.", p)
        for k in ('"nota"', '"fortes"', '"fracos"', '"dicas"', '"alternativas"', '"preco"', '"fontes"', '{"erro": "sem_busca"}'):
            self.assertIn(k, p)


class Limpeza(Base):
    def test_a_nota_as_listas_e_as_fontes(self):
        r = S.par_clean({"produto": " Pasta  X ", "nota": "4,3", "resumo": "Boa.", "fortes": ["Rende", "", 3, "A", "B", "C", "D"],
                         "pontos_fracos": ["Cara"], "dicas": ["Guarde fechada"], "alternativas": ["Outra", {"nome": "Mais uma", "motivo": "barata"}, {"nome": ""}],
                         "preco": "R$ 30", "fontes": ["https://loja.exemplo/a", {"url": "https://loja.exemplo/a"}, {"url": "javascript:x"}, {"url": "https://teste.exemplo/b", "titulo": "Teste"}]})
        self.assertEqual((r["produto"], r["nota"], r["resumo"], r["preco"]), ("Pasta X", 4.5, "Boa.", "R$ 30"))
        self.assertEqual(r["fortes"], ["Rende", "3", "A", "B"], "até 4, sem os vazios")
        self.assertEqual(r["fracos"], ["Cara"])
        self.assertEqual(r["alternativas"], [{"nome": "Outra", "porque": ""}, {"nome": "Mais uma", "porque": "barata"}])
        self.assertEqual([(f["url"], f["site"]) for f in r["fontes"]], [("https://loja.exemplo/a", "loja.exemplo"), ("https://teste.exemplo/b", "teste.exemplo")])
        for nota in ("9", "zero", None, 0.2):
            self.assertIsNone(S.par_clean({"nota": nota})["nota"], nota)
        self.assertEqual(S.par_clean("nada")["fortes"], [])

    def test_a_ia_fora_do_formato_sem_nada_ou_sem_a_busca(self):
        for raw, parte in (("não sei", "fora do formato"), ('{"resumo": ""}', "Ponha a marca"), ('{"erro": "sem_busca"}', "não usou a busca na web")):
            with mock.patch.object(S, "ai_call_text", return_value=raw):
                with self.assertRaises(S.ApiError) as e:
                    S.ai_find_par(self.cons, "ai_task.x")
                self.assertIn(parte, e.exception.msg)
        with mock.patch.object(S, "ai_call_text", return_value={"nota": 3, "resumo": "Ok."}):
            self.assertEqual(S.ai_find_par(self.cons, "ai_task.x")["nota"], 3)


class Guardado(Base):
    def test_fica_guardado_ate_o_item_mudar_e_so_dos_consumiveis_com_a_ia_ligada(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            p = S.avaliar(self.cons["id"])
        self.assertEqual((p["nota"], p["resumo"]), (S.MOCK_PAR["nota"], S.MOCK_PAR["resumo"]))
        self.assertNotIn("sig", p)
        self.assertEqual(S.par_of(self.cons["id"])["nota"], 4)
        self.store.update_item(self.cons["id"], {"name": "Pasta térmica Outra"}, "Ana")
        self.assertEqual(S.par_of(self.cons["id"]), {}, "o item mudou: o parecer de antes não vale")
        casa = next(i for i in self.store.data["items"] if not self.store.is_cons(i["room"]))
        with self.assertRaises(S.ApiError) as e:
            S.par_item(casa["id"])
        self.assertIn("dos consumíveis", e.exception.msg)
        with self.assertRaises(S.ApiError) as e:
            S.par_item("nao-existe")
        self.assertEqual(e.exception.status, 404)
        self.store.settings["ai"] = False
        with self.assertRaises(S.ApiError):
            S.par_item(self.cons["id"])

    def test_o_trabalho_da_tela(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            jid = S.par_job_start({"item": self.cons["id"]})["id"]
            job = S.WEB_JOBS[jid]
            t0 = time.time()
            while job["stage"] == "busy" and time.time() - t0 < 5:
                time.sleep(0.02)
        self.assertEqual((job["stage"], job["parecer"]["nota"]), ("done", 4))
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S, "ai_find_par", side_effect=S.ApiError(502, "A IA não achou.")):
            jid = S.par_job_start({"item": self.cons["id"]})["id"]
            job = S.WEB_JOBS[jid]
            t0 = time.time()
            while job["stage"] == "busy" and time.time() - t0 < 5:
                time.sleep(0.02)
        self.assertEqual((job["stage"], job["msg"]), ("error", "A IA não achou."))
        with self.assertRaises(S.ApiError) as e:
            S.par_job_start({"item": self.cons["id"]})
        self.assertEqual(e.exception.status, 503, "sem o Home Assistant e sem a IA simulada")


class Ferramenta(Base):
    def chamar(self, args):
        return json.loads(F.chamar(S, "avaliar", args, {"nome": "Ana"}, "Claude"))

    def test_avaliar_pelo_correria(self):
        self.assertIn("avaliar", [f["nome"] for f in F.lista()])
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            r = self.chamar({"id": self.cons["id"]})
            self.assertEqual((r["item"], r["nota"], r["novo"]), ("Pasta térmica Exemplo", 4, True))
            self.assertEqual(r["fontes"], ["https://www.exemplo.com.br/avaliacoes"])
            with mock.patch.object(S, "ai_find_par", side_effect=AssertionError("não chama a IA de novo")):
                self.assertFalse(self.chamar({"id": self.cons["id"]})["novo"], "o guardado")
            self.assertTrue(self.chamar({"id": self.cons["id"], "nova": True})["novo"])
        ver = json.loads(F.chamar(S, "ver_item", {"id": self.cons["id"]}, {"nome": "Ana"}, "Claude"))
        self.assertEqual(ver["parecer"]["nota"], 4, "o ver_item leva o parecer guardado")
        casa = next(i for i in self.store.data["items"] if not self.store.is_cons(i["room"]))
        with self.assertRaises(F.ErroFerramenta) as e:
            self.chamar({"id": casa["id"]})
        self.assertIn("não é um consumível", str(e.exception))
        self.store.settings["ai"] = False
        with self.assertRaises(F.ErroFerramenta) as e:
            self.chamar({"id": self.cons["id"]})
        self.assertIn("IA do InventarIA está desligada", str(e.exception))


def _espera(job, s=5):
    t0 = time.time()
    while job["stage"] == "busy" and time.time() - t0 < s:
        time.sleep(0.02)


class Pesquisas(Base):
    """1.107.0 (o dono: "uma central mesmo de coisas que eu vou buscar de novidades, recursos, avaliações"; "todos esses caras
    que a gente buscou da IA, ele tem que ter uma opção para poder apagar"): Pesquisas da IA › Pareceres (a lista, Avaliar
    vários) e o Apagar dos recursos e do parecer."""

    def setUp(self):
        super().setUp()
        area = self.cons["room"]
        self.outro = self.store.create_items([{"room": area, "name": "Pilhas AA Exemplo"}, {"room": area, "name": "Creme Exemplo"}], "Ana")

    def test_a_lista_dos_pareceres(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            S.avaliar(self.cons["id"])
        ov = S.par_overview()
        self.assertEqual(set(ov["itens"]), {self.cons["id"]} | {i["id"] for i in self.outro}, "só os consumíveis")
        self.assertEqual(ov["itens"][self.cons["id"]]["nota"], 4)
        self.assertIsNone(ov["itens"][self.outro[0]["id"]])
        self.assertIsNone(ov["job"])
        c = S.chat_context({"view": "news"})
        self.assertIn("Pareceres: 1 de 3 consumíveis avaliados.", c)
        self.assertIn("- Pasta térmica Exemplo: nota 4;", c)
        self.store.settings["consumiveis"] = False
        with self.assertRaises(S.ApiError) as e:
            S.par_overview()
        self.assertEqual(e.exception.status, 409)

    def test_avaliar_os_sem_parecer_e_os_escolhidos(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            S.avaliar(self.cons["id"])
            vistos = []
            real = S.ai_find_par
            with mock.patch.object(S, "ai_find_par", side_effect=lambda it, e: vistos.append(it["name"]) or real(it, e)):
                jid = S.par_lote_start({})["id"]
                self.assertEqual(S.par_lote_start({})["id"], jid, "uma avaliação andando: acompanha a mesma")
                job = S.WEB_JOBS[jid]
                _espera(job)
            self.assertEqual(job["stage"], "done")
            self.assertEqual(sorted(vistos), ["Creme Exemplo", "Pilhas AA Exemplo"], "só os sem parecer")
            self.assertEqual(job["summary"], {"avaliados": 2, "erros": 0, "total": 2})
            with self.assertRaises(S.ApiError) as e:
                S.par_lote_start({})
            self.assertIn("já têm parecer", e.exception.msg)
            jid = S.par_lote_start({"itens": [self.cons["id"], "nao-existe"]})["id"]
            _espera(S.WEB_JOBS[jid])
            self.assertEqual(S.WEB_JOBS[jid]["summary"]["avaliados"], 1, "os escolhidos, mesmo os que já têm")
            for ruim, parte in (({"itens": []}, "pelo menos um"), ({"itens": "x"}, "numa lista"), ({"itens": [1]}, "numa lista")):
                with self.assertRaises(S.ApiError) as e:
                    S.par_lote_start(ruim)
                self.assertIn(parte, e.exception.msg)

    def test_um_que_falha_segue_e_a_cota_para(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            with mock.patch.object(S, "ai_find_par", side_effect=S.ApiError(502, "A IA não achou avaliações.")):
                jid = S.par_lote_start({})["id"]
                _espera(S.WEB_JOBS[jid])
            self.assertEqual((S.WEB_JOBS[jid]["stage"], S.WEB_JOBS[jid]["summary"]["erros"]), ("done", 3))
            n = []
            def cota(it, e):
                n.append(1)
                if len(n) == 1:
                    return S.MOCK_PAR
                raise S.ApiError(429, "A cota da IA acabou.")
            with mock.patch.object(S, "ai_find_par", side_effect=cota):
                jid = S.par_lote_start({})["id"]
                _espera(S.WEB_JOBS[jid])
            job = S.WEB_JOBS[jid]
            self.assertEqual(job["stage"], "error")
            self.assertTrue(job["msg"].startswith("1 avaliado antes de parar."), job["msg"])
            self.assertEqual(len(n), 2, "a cota acabou: os próximos não são tentados")

    def test_parar_guarda_os_que_ja_foram(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            ids = []
            def um(it, e):
                ids.append(it["id"])
                for v in S.WEB_JOBS.values():  # Parar no meio do primeiro (o jid pode ainda não ter voltado)
                    if v.get("kind") == "par-lote":
                        v["cancelled"] = True
                return S.MOCK_PAR
            with mock.patch.object(S, "ai_find_par", side_effect=um):
                jid = S.par_lote_start({})["id"]
                _espera(S.WEB_JOBS[jid])
        self.assertEqual(len(ids), 1, "parou depois do primeiro")
        self.assertTrue(S.par_of(ids[0]), "o que chegou ficou guardado")

    def test_apagar_o_parecer_e_os_recursos(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            S.avaliar(self.cons["id"])
        self.assertEqual(S.par_dismiss(self.cons["id"]), {})
        self.assertEqual(S.par_of(self.cons["id"]), {})
        self.assertEqual(S.par_dismiss(self.cons["id"]), {}, "de novo: nada a apagar, sem erro")
        el = [i for i in self.store.data["items"] if i.get("cat") == "eletronicos"][:1]
        if not el:
            self.skipTest("a casa de teste sem eletrônicos")
        sala = el[0]
        gemeo = self.store.create_items([{"room": next(r["id"] for r in self.store.data["rooms"] if not r.get("kind") and r["id"] != sala["room"]),
                                          "name": sala["name"], "cat": "eletronicos"}], "Ana")[0]
        for i in (sala, gemeo):
            S.rec_save(i["id"], {"recursos": [{"nome": "Wi-Fi", "detalhe": ""}], "fonte": "", "site": ""})
        self.assertTrue(S.rec_of(gemeo["id"]))
        S.rec_dismiss(sala["id"])
        self.assertEqual((S.rec_of(sala["id"]), S.rec_of(gemeo["id"])), ({}, {}), "o mesmo equipamento no outro cômodo também")
        with self.assertRaises(S.ApiError) as e:
            S.rec_dismiss("nao-existe")
        self.assertEqual(e.exception.status, 404)

    def test_limpar_todos(self):
        """1.109.0 (o dono: "criar opção para apagar todos"): o Limpar dos Recursos e dos Pareceres, pela rota e pela ferramenta."""
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            S.avaliar(self.cons["id"])
        S.rec_save(self.cons["id"], {"recursos": [{"nome": "Wi-Fi", "detalhe": ""}], "fonte": "", "site": ""})
        S.WEB_JOBS["a" * 16] = {"kind": "par-lote", "stage": "busy", "at": time.time()}
        S.WEB_JOBS["b" * 16] = {"kind": "lote", "so": "recursos", "stage": "busy", "at": time.time()}
        S.WEB_JOBS["c" * 16] = {"kind": "lote", "so": "", "stage": "busy", "at": time.time()}
        try:
            par_job, rec_job = S.WEB_JOBS["a" * 16], S.WEB_JOBS["b" * 16]
            self.assertEqual(S.par_clear(), {})
            self.assertEqual((S.par_of(self.cons["id"]), par_job.get("cancelled"), "a" * 16 in S.WEB_JOBS), ({}, True, False), "os pareceres e a avaliação em andamento")
            self.assertEqual(S.rec_clear(), {})
            self.assertEqual((S.rec_of(self.cons["id"]), rec_job.get("cancelled"), "c" * 16 in S.WEB_JOBS), ({}, True, True), "os recursos e a busca deles; a conferência das novidades segue")
        finally:
            S.WEB_JOBS.pop("c" * 16, None)
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            S.avaliar(self.cons["id"])
        r = json.loads(F.chamar(S, "apagar_pesquisa", {"o_que": "parecer", "todos": True}, {"nome": "Ana"}, "Claude"))
        self.assertEqual((r, S.par_of(self.cons["id"])), ({"apagado": "parecer", "todos": True}, {}))
        r = json.loads(F.chamar(S, "apagar_pesquisa", {"o_que": "recursos", "todos": True}, {"nome": "Ana"}, "Claude"))
        self.assertEqual(r["apagado"], "recursos")
        for args, parte in (({"o_que": "novidades", "todos": True}, "Limpar"), ({"o_que": "parecer"}, "id do item")):
            with self.assertRaises(F.ErroFerramenta) as e:
                F.chamar(S, "apagar_pesquisa", args, {"nome": "Ana"}, "Claude")
            self.assertIn(parte, str(e.exception))
        self.store.settings["ai"] = False
        try:
            with self.assertRaises(S.ApiError):
                S.par_clear()
        finally:
            self.store.settings["ai"] = True

    def test_recursos_sem_as_novidades_e_o_andamento_na_lista(self):
        self.store.settings["news"] = False
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S, "rec_pending", return_value=[]):
            jid = S.news_batch_start(so="recursos")["id"]
            _espera(S.WEB_JOBS[jid])
            self.assertEqual(S.WEB_JOBS[jid]["stage"], "done")
            with self.assertRaises(S.ApiError):
                S.news_batch_start(so="itens")
        S.WEB_JOBS["f" * 16] = {"kind": "lote", "stage": "busy", "msg": "Conferindo…", "so": "recursos", "at": time.time()}
        try:
            self.assertEqual((S.rec_overview()["job"]["id"], S.rec_overview()["job"]["so"]), ("f" * 16, "recursos"), "a busca andando vai para a aba Recursos")
        finally:
            S.WEB_JOBS.pop("f" * 16, None)

    def test_as_ferramentas(self):
        nomes = [f["nome"] for f in F.lista()]
        self.assertIn("pareceres", nomes)
        self.assertIn("apagar_pesquisa", nomes)
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep", lambda s: None):
            S.avaliar(self.cons["id"])
        r = json.loads(F.chamar(S, "pareceres", {}, {"nome": "Ana"}, "Claude"))
        self.assertEqual([x["item"] for x in r["com_parecer"]], ["Pasta térmica Exemplo"])
        self.assertEqual(sorted(x["item"] for x in r["sem_parecer"]), ["Creme Exemplo", "Pilhas AA Exemplo"])
        self.assertNotIn("com_parecer", json.loads(F.chamar(S, "pareceres", {"so_sem": True}, {"nome": "Ana"}, "Claude")))
        r = json.loads(F.chamar(S, "apagar_pesquisa", {"id": self.cons["id"], "o_que": "parecer"}, {"nome": "Ana"}, "Claude"))
        self.assertEqual(r["apagado"], "parecer")
        self.assertEqual(S.par_of(self.cons["id"]), {})
        for args, parte in (({"id": self.cons["id"], "o_que": "parecer"}, "não tem parecer"), ({"id": self.cons["id"], "o_que": "recursos"}, "não tem recursos"),
                            ({"id": self.cons["id"], "o_que": "tudo"}, "novidades, recursos ou parecer")):
            with self.assertRaises(F.ErroFerramenta) as e:
                F.chamar(S, "apagar_pesquisa", args, {"nome": "Ana"}, "Claude")
            self.assertIn(parte, str(e.exception))
        self.store.settings["consumiveis"] = False
        with self.assertRaises(F.ErroFerramenta) as e:
            F.chamar(S, "pareceres", {}, {"nome": "Ana"}, "Claude")
        self.assertIn("consumíveis estão desligados", str(e.exception))
