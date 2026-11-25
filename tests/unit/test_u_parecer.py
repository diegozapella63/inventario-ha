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
