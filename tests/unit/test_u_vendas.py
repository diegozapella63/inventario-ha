"""1.115.0 (o dono: "criar nova aba na parte mais chamada vendas, e criar a possibilidade de marcar itens para venda"; "Ao
marcar como vendido solicitar se quer adicionar este recebido"): o À venda de um item, vender (o item sai do inventário e
fica nos Vendidos), desfazer, o recebimento no GerencIA (um GerencIA de mentira) e as ferramentas do CorrerIA. A casa é a
de teste; os valores são inventados."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from _boot import UnitBase, server as S

import ferramentas as F

ANA = {"id": "person.ana", "nome": "Ana"}


class Gerencia(BaseHTTPRequestHandler):
    pedidos, status = [], 200

    def log_message(self, *a):
        pass

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        type(self).pedidos.append((self.path, self.headers.get("Authorization"), corpo))
        st = type(self).status
        dado = json.dumps({"ok": True, "id": "l-1", "rev": 2} if st == 200 else {"erro": "Coloque o valor."} if st == 400 else {}).encode()
        self.send_response(st)
        self.send_header("Content-Length", str(len(dado)))
        self.end_headers()
        self.wfile.write(dado)


class Base(UnitBase):
    def setUp(self):
        super().setUp()
        self.it = next(i for i in self.store.data["items"] if not self.store.is_cons(i["room"]))
        Gerencia.pedidos, Gerencia.status = [], 200

    def gerencia(self, **mais):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Gerencia)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        arq = os.path.join(S.DATA_DIR, "gerencia-integracao.json")
        with open(arq, "w", encoding="utf-8") as f:
            json.dump({"app": "gerencia", "url": f"http://127.0.0.1:{srv.server_address[1]}", "chave": "segredo-de-teste",
                       "recebimentos": "/api/integracao/nova", **mais}, f)
        p = mock.patch.object(S, "GERENCIA_ARQ", arq)
        p.start()
        self.addCleanup(p.stop)

    def chamar(self, nome, args=None):
        return F.chamar(S, nome, args or {}, ANA, "Claude")

    def erro(self, nome, args, parte):
        with self.assertRaises(F.ErroFerramenta) as cm:
            self.chamar(nome, args)
        self.assertIn(parte, str(cm.exception))


class AVenda(Base):
    def test_por_tirar_e_o_que_fica_guardado(self):
        it = self.store.update_item(self.it["id"], {"sale": {"price": "1.200,50", "note": "  Com a caixa  "}}, "Ana")
        self.assertEqual((it["sale"]["price"], it["sale"]["note"], bool(it["sale"]["at"])), (1200.5, "Com a caixa", True))
        desde = it["sale"]["at"]
        it = self.store.update_item(self.it["id"], {"sale": {"price": 900}}, "Ana")
        self.assertEqual((it["sale"]["price"], it["sale"]["note"], it["sale"]["at"]), (900, "Com a caixa", desde), "mudar o preço não muda o resto")
        it = self.store.update_item(self.it["id"], {"sale": {"price": "", "note": ""}}, "Ana")
        self.assertEqual(set(it["sale"]), {"at"}, "à venda sem preço nem observação")
        it = self.store.update_item(self.it["id"], {"name": it["name"]}, "Ana")
        self.assertIn("sale", it, "editar outra coisa não tira da venda")
        it = self.store.update_item(self.it["id"], {"sale": False}, "Ana")
        self.assertNotIn("sale", it)
        with self.assertRaises(S.ApiError):
            self.store.update_item(self.it["id"], {"sale": {"price": "caro"}}, "Ana")
        self.assertEqual([S.clean_sale(x) for x in (None, False, "", 0)], [None] * 4)

    def test_varios_de_uma_vez_e_um_consumivel_nao(self):
        outros = [i for i in self.store.data["items"] if not self.store.is_cons(i["room"])][:3]
        self.store.update_items([{"id": i["id"], "sale": True} for i in outros], "Ana")
        self.assertTrue(all(self.store.item(i["id"]).get("sale") for i in outros))
        self.store.update_items([{"id": outros[0]["id"], "sale": False}], "Ana")
        self.assertNotIn("sale", self.store.item(outros[0]["id"]))
        self.store.settings["consumiveis"] = True
        area = self.store.create_room({"kind": "consumiveis"})
        cons = self.store.create_items([{"room": area["id"], "name": "Creme de exemplo", "sale": True}], "Ana")[0]
        self.assertNotIn("sale", cons)
        self.assertNotIn("sale", self.store.update_item(cons["id"], {"sale": True}, "Ana"))
        self.store.update_items([{"id": cons["id"], "sale": True}], "Ana")
        self.assertNotIn("sale", self.store.item(cons["id"]))
        with self.assertRaises(S.ApiError):
            self.store.sell_item(cons["id"], 10, None, "Ana")
        # um item à venda que vira consumível sai da venda
        self.store.update_items([{"id": outros[1]["id"], "room": area["id"]}], "Ana")
        self.assertNotIn("sale", self.store.item(outros[1]["id"]))


class Vender(Base):
    def test_vender_tira_do_inventario_e_desfazer_traz_de_volta(self):
        antes, n = dict(self.it), len(self.store.data["items"])
        self.store.update_item(antes["id"], {"sale": {"price": 500}}, "Ana")
        r = S.vender(antes["id"], "450,00", None, "Ana")
        v = r["sold"]
        self.assertEqual((v["soldValue"], v["soldAt"], v["soldBy"], v["name"], r["recebido"]), (450, "2026-11-04", "Ana", antes["name"], False))
        self.assertEqual((v["soldTag"], bool(v["soldRoom"])), (self.store.tag(antes), True))
        self.assertIsNone(self.store.item(antes["id"]))
        self.assertEqual(len(self.store.data["items"]), n - 1)
        self.assertNotIn(antes["id"], [i["id"] for i in S.visible_data()[1]], "fora do patrimônio e dos outros apps")
        self.assertEqual([i["id"] for i in self.store.public()["sold"]], [antes["id"]])
        # um item novo pega o número seguinte, não o do vendido
        novo = self.store.create_items([{"room": antes["room"], "name": "Item novo de exemplo"}], "Ana")[0]
        self.assertGreater(novo["seq"], antes["seq"])
        de_volta = self.store.unsell_item(antes["id"])
        self.assertEqual((de_volta["id"], de_volta["seq"], de_volta["value"], de_volta["sale"]["price"]), (antes["id"], antes["seq"], antes["value"], 500))
        self.assertFalse(any(k.startswith("sold") for k in de_volta))
        self.assertEqual(self.store.sold(), [])
        with self.assertRaises(S.ApiError):
            self.store.unsell_item(antes["id"])

    def test_erros_da_venda(self):
        for valor, dia in (("caro", None), (10, "28/11/2026"), (10, "2026-13-40"), (10, "2099-01-01")):
            with self.assertRaises(S.ApiError):
                self.store.sell_item(self.it["id"], valor, dia, "Ana")
        with self.assertRaises(S.ApiError):
            self.store.sell_item("nao-existe", 10, None, "Ana")
        self.assertIsNotNone(self.store.item(self.it["id"]))
        v = self.store.sell_item(self.it["id"], 0, "2026-10-30", None)
        self.assertEqual((v["soldValue"], v["soldAt"]), (0, "2026-10-30"))
        self.assertNotIn("soldBy", v)
        with self.assertRaises(S.ApiError):
            self.store.delete_sold("nao-existe")
        with self.assertRaises(S.ApiError):
            self.store.mark_received("nao-existe", "gerencia")
        self.assertEqual(self.store.delete_sold(v["id"])["id"], v["id"])
        self.assertEqual(self.store.sold(), [])

    def test_desfazer_sem_o_comodo_ou_com_o_numero_ocupado(self):
        a = self.it
        outro = self.store.create_items([{"room": a["room"], "name": "Vizinho de exemplo"}], "Ana")[0]
        self.store.sell_item(outro["id"], 10, None, "Ana")
        # o número do vendido foi dado a outro: ao voltar, ganha o próximo
        self.store.data["items"].append(dict(a, id="clone-de-teste", seq=outro["seq"]))
        de_volta = self.store.unsell_item(outro["id"])
        self.assertNotEqual(de_volta["seq"], outro["seq"])
        self.store.sell_item(de_volta["id"], 10, None, "Ana")
        self.store.data["sold"][0]["room"] = "comodo-que-sumiu"
        with self.assertRaises(S.ApiError) as cm:
            self.store.unsell_item(de_volta["id"])
        self.assertIn("cômodo", cm.exception.msg)

    def test_os_vendidos_no_arquivo_e_no_comecar_do_zero(self):
        self.store.sell_item(self.it["id"], 99, None, "Ana")
        d = S.Store.check_inventory(json.loads(json.dumps(self.store.data)))
        self.assertEqual([i["id"] for i in d["sold"]], [self.it["id"]])
        d["sold"] += ["x", {"id": "sem-data", "name": "Sem data"}, dict(d["sold"][0])]
        self.assertEqual(len(S.Store.check_inventory(d)["sold"]), 1, "só o que parece um vendido, sem repetir")
        d["sold"] = "x"
        self.assertNotIn("sold", S.Store.check_inventory(d))
        self.assertEqual(len(S.clean_sold([{"id": f"v{i}", "name": "x", "soldAt": "2026-11-01"} for i in range(S.MAX_SOLD + 5)])), S.MAX_SOLD)


class Recebimento(Base):
    def test_sem_o_gerencia(self):
        self.assertIsNone(S.gerencia_recebe())
        r = S.vender(self.it["id"], 300, None, "Ana", receber=True)
        self.assertEqual((r["recebido"], "GerencIA não está ligado" in r["erro_gerencia"]), (False, True))
        self.assertIsNotNone(self.store.sold_item(self.it["id"]), "a venda vale mesmo sem o recebimento")

    def test_lanca_no_gerencia(self):
        self.gerencia()
        self.assertIsNotNone(S.gerencia_recebe())
        r = S.vender(self.it["id"], 300, "2026-11-02", "Ana", receber=True)
        self.assertEqual((r["recebido"], r["erro_gerencia"], r["sold"]["soldReceived"]), (True, "", "gerencia"))
        caminho, auth, corpo = Gerencia.pedidos[-1]
        self.assertEqual((caminho, auth), ("/api/integracao/nova", "Bearer segredo-de-teste"))
        self.assertEqual(corpo, {"tipo": "receita", "descricao": "Venda: " + self.it["name"], "valor": 300, "vencimento": "2026-11-02", "pago": True, "obs": "Pelo InventarIA"})

    def test_o_gerencia_recusa_ou_some(self):
        self.gerencia()
        for st, parte in ((400, "Coloque o valor."), (401, "ligue de novo"), (500, "respondeu 500")):
            Gerencia.status = st
            it = next(i for i in self.store.data["items"] if not self.store.is_cons(i["room"]))
            r = S.vender(it["id"], 50, None, "Ana", receber=True)
            self.assertIn(parte, r["erro_gerencia"], st)
            self.assertNotIn("soldReceived", self.store.sold_item(it["id"]))
        v = self.store.sold()[0]
        with self.assertRaises(S.ApiError) as cm:
            S.gerencia_receber(dict(v, soldValue=0))
        self.assertIn("Sem o valor", cm.exception.msg)
        with mock.patch.object(S, "GERENCIA_ARQ", os.path.join(S.DATA_DIR, "nao-existe.json")):
            self.assertIsNone(S.gerencia_recebe())
        arq = os.path.join(S.DATA_DIR, "g2.json")
        for conteudo in ("{", json.dumps({"url": "http://127.0.0.1:9", "chave": "k"}), json.dumps([1])):
            with open(arq, "w") as f:
                f.write(conteudo)
            with mock.patch.object(S, "GERENCIA_ARQ", arq):
                self.assertIsNone(S.gerencia_recebe(), conteudo)
        with open(arq, "w") as f:
            json.dump({"url": "", "ip_url": "http://127.0.0.1:9", "chave": "k", "recebimentos": "/api/integracao/nova"}, f)
        with mock.patch.object(S, "GERENCIA_ARQ", arq), self.assertRaises(S.ApiError) as cm:
            S.gerencia_receber(v)
        self.assertIn("não respondeu", cm.exception.msg)


class Ferramentas(Base):
    def test_por_a_venda_buscar_e_vendas(self):
        self.assertIn("À venda: ", self.chamar("por_a_venda", {"ids": [self.it["id"]], "preco": 800, "observacao": "Com a nota"}))
        self.assertIn("pedindo R$ 800,00", self.chamar("por_a_venda", {"ids": [self.store.tag(self.it)], "preco": 800}))
        achados = json.loads(self.chamar("buscar_itens", {"a_venda": True}))
        linha = achados["itens"][0] if "itens" in achados else achados[0]
        self.assertEqual((linha["id"], linha["a_venda"], linha["preco_pedido"], linha["observacao_da_venda"]), (self.it["id"], True, 800.0, "Com a nota"))
        outros = [i["id"] for i in self.store.data["items"] if not self.store.is_cons(i["room"]) and i["id"] != self.it["id"]][:2]
        self.assertIn("2 itens à venda", self.chamar("por_a_venda", {"ids": outros}))
        self.erro("por_a_venda", {"ids": outros, "preco": 10}, "um item só")
        v = json.loads(self.chamar("vendas"))
        self.assertEqual((v["total_a_venda"], v["soma_pedida"], v["total_vendidos"], v["gerencia_recebe"]), (3, 800.0, 0, False))
        self.assertIn("Fora da venda", self.chamar("por_a_venda", {"ids": outros, "tirar": True}))
        self.erro("por_a_venda", {"ids": outros, "tirar": True}, "não está à venda")
        self.store.settings["consumiveis"] = True
        area = self.store.create_room({"kind": "consumiveis"})
        cons = self.store.create_items([{"room": area["id"], "name": "Creme de exemplo"}], "Ana")[0]
        self.erro("por_a_venda", {"ids": [cons["id"]]}, "consumível")

    def test_marcar_vendido_e_desfazer(self):
        self.gerencia()
        self.erro("marcar_vendido", {"id": "nao-existe", "valor": 10}, "")
        r = self.chamar("marcar_vendido", {"id": self.it["id"], "valor": 650.5, "receber_no_gerencia": True})
        self.assertIn(f"Vendido: {self.it['name']} por R$ 650,50, em 2026-11-04.", r)
        self.assertIn("O recebimento foi lançado no GerencIA.", r)
        v = json.loads(self.chamar("vendas"))
        self.assertEqual((v["total_vendidos"], v["soma_vendida"], v["vendidos"][0]["recebimento_no_gerencia"], v["gerencia_recebe"]), (1, 650.5, True, True))
        de_volta = self.chamar("desfazer_venda", {"id": self.it["name"].upper()})
        self.assertIn("De volta ao inventário", de_volta)
        self.assertIn("continua lá", de_volta)
        self.erro("desfazer_venda", {"id": self.it["id"]}, "não está nos vendidos")
        # sem pedir o recebimento, a resposta lembra que dá para lançar depois; com o GerencIA recusando, diz por quê
        self.assertIn("dá para lançar na tela Vendas", self.chamar("marcar_vendido", {"id": self.it["id"], "valor": 10}))
        self.chamar("desfazer_venda", {"id": self.it["id"]})
        Gerencia.status = 400
        self.assertIn("não foi para o GerencIA: Coloque o valor.", self.chamar("marcar_vendido", {"id": self.it["id"], "valor": 10, "receber_no_gerencia": True}))
        nomes = [f["nome"] for f in F.lista()]
        self.assertEqual(nomes[-3:], ["por_a_venda", "marcar_vendido", "desfazer_venda"])
        self.assertFalse(F.POR_NOME["vendas"]["grava"])
