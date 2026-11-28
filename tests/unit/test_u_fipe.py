"""1.114.0 (o dono: "Tabela FIPE (BrasilAPI) é confiável? Se sim pode fazer"): o fipe.py (o código, o ano, a resposta da
BrasilAPI), o código e o ano guardados num veículo (só num bem do tipo Veículos), o valor do mês guardado por uma semana, a
rota da ficha e as ferramentas do CorrerIA. A BrasilAPI é de mentira; o carro e os valores, inventados. Nada muda o valor
de um bem sem a pessoa pedir."""
import json
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from _boot import UnitBase, server as S

import ferramentas as F
import fipe as P

ANA = {"id": "person.ana", "nome": "Ana"}
TABELA = [{"valor": "R$ 85.608,00", "marca": "Marca Exemplo", "modelo": "Carro Exemplo 2.0", "anoModelo": 2014, "combustivel": "Gasolina", "codigoFipe": "005340-6", "mesReferencia": "novembro de 2026 "},
          {"valor": "R$ 80.000,00", "marca": "Marca Exemplo", "modelo": "Carro Exemplo 2.0", "anoModelo": 2014, "combustivel": "Álcool", "codigoFipe": "005340-6", "mesReferencia": "novembro de 2026 "},
          {"valor": "R$ 120.500,50", "marca": "Marca Exemplo", "modelo": "Carro Exemplo 2.0", "anoModelo": 32000, "combustivel": "Gasolina", "codigoFipe": "005340-6", "mesReferencia": "novembro de 2026 "},
          {"valor": 70000, "marca": "Marca Exemplo", "modelo": "Carro Exemplo 2.0", "anoModelo": 2012, "combustivel": "Gasolina", "mesReferencia": "novembro de 2026"},
          {"valor": "x", "anoModelo": 2011}, "ruim"]


class Api(BaseHTTPRequestHandler):
    pedidos, status = [], {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        cod = self.path.rsplit("/", 1)[-1]
        type(self).pedidos.append(cod)
        st = type(self).status.get(cod) or (200 if cod == "005340-6" else 404)
        dado = json.dumps(TABELA if st == 200 else {"message": "x"}).encode()
        self.send_response(st)
        self.send_header("Content-Length", str(len(dado)))
        self.end_headers()
        self.wfile.write(dado)


class Base(UnitBase):
    def setUp(self):
        super().setUp()
        Api.pedidos, Api.status = [], {}
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Api)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (self.srv.shutdown(), self.srv.server_close()))
        p = mock.patch.object(P, "BASE", f"http://127.0.0.1:{self.srv.server_address[1]}")
        p.start()
        self.addCleanup(p.stop)
        S.write_json_atomic(S.FIPE_FILE, {})

    def chamar(self, nome, args=None):
        return F.chamar(S, nome, args or {}, ANA, "Claude")

    def json(self, nome, args=None):
        return json.loads(self.chamar(nome, args))

    def erro(self, nome, args, parte):
        with self.assertRaises(F.ErroFerramenta) as cm:
            self.chamar(nome, args)
        self.assertIn(parte, str(cm.exception))

    def carro(self, **mais):
        bens = self.store.create_room({"kind": "bens"}) if not any(r.get("kind") == "bens" for r in self.store.data["rooms"]) else None
        bens = bens or next(r for r in self.store.data["rooms"] if r.get("kind") == "bens")
        return self.store.create_items([{"room": bens["id"], "name": "Carro Exemplo", "cat": "veiculos", "value": 50000, **mais}], "Ana")[0]


class Modulo(Base):
    def test_codigo_ano_e_o_que_a_pessoa_escreve(self):
        self.assertEqual([P.codigo(x) for x in ("005340-6", "0053406", " 005.340-6 ", "12345", "", None)], ["005340-6", "005340-6", "005340-6", "", "", ""])
        self.assertEqual([P.ano(x) for x in (2014, "2014", 32000, 1900, "x", None)], [2014, 2014, 32000, 0, 0, 0])
        self.assertEqual([P.separar(x) for x in ("005340-6 2014", "0053406/2014", "005340-6", "2014", "ano 1999 cod 001004-9", "")],
                         [("005340-6", 2014), ("005340-6", 2014), ("005340-6", 0), ("", 2014), ("001004-9", 0), ("", 0)])
        self.assertEqual([P._valor(x) for x in ("R$ 85.608,00", 70000, True, "x", -1, None)], [85608.0, 70000.0, 0.0, 0.0, 0.0, 0.0])

    def test_consultar_e_os_erros(self):
        ls = P.consultar("0053406")
        self.assertEqual([(x["ano"], x["combustivel"], x["valor"]) for x in ls], [(32000, "Gasolina", 120500.5), (2014, "Gasolina", 85608.0), (2014, "Álcool", 80000.0), (2012, "Gasolina", 70000.0)])
        self.assertEqual(ls[1]["mes"], "novembro de 2026")
        self.assertEqual(P.do_ano(ls, 2014)["valor"], 85608.0, "com dois combustíveis, o de maior valor")
        self.assertIsNone(P.do_ano(ls, 1999))
        self.assertEqual(Api.pedidos, ["005340-6"])
        for cod, st, frase in (("123", None, "7 números"), ("001004-9", None, "não está na Tabela FIPE"), ("005340-6", 500, "não respondeu agora")):
            Api.status = {cod: st} if st else {}
            with self.assertRaises(P.Erro) as cm:
                P.consultar(cod)
            self.assertIn(frase, str(cm.exception))
        with self.assertRaises(P.Erro):
            P.consultar("005340-6", base="http://127.0.0.1:9/x", timeout=2)
        self.assertEqual(P.da_resposta({"erro": 1}), [])
        with mock.patch.object(P, "da_resposta", return_value=[]), self.assertRaises(P.Erro):
            P.consultar("005340-6")


class Guardado(Base):
    def test_so_num_veiculo_e_o_que_vale(self):
        c = self.carro(fipe="0053406 2014")
        self.assertEqual((c["fipe"], c["fipeYear"], c["value"]), ("005340-6", 2014, 50000.0))
        c = self.store.update_item(c["id"], {"fipe": "001004-9", "fipeYear": "2020"}, "Ana")
        self.assertEqual((c["fipe"], c["fipeYear"]), ("001004-9", 2020))
        for ruim in ("005340-6", "2014", "abc", "005340-6 32000"):
            with self.assertRaises(S.ApiError) as cm:
                self.store.update_item(c["id"], {"fipe": ruim}, "Ana")
            self.assertIn("o código e o ano do veículo", cm.exception.msg)
        c = self.store.update_item(c["id"], {"name": "Carro Novo"}, "Ana")
        self.assertEqual(c["fipe"], "001004-9", "mudar outra coisa não tira")
        c = self.store.update_item(c["id"], {"cat": "imoveis"}, "Ana")
        self.assertNotIn("fipe", c, "deixou de ser veículo: sai")
        self.assertNotIn("fipeYear", c)
        c = self.store.update_item(c["id"], {"cat": "veiculos", "fipe": "005340-6 2014"}, "Ana")
        c = self.store.update_item(c["id"], {"fipe": ""}, "Ana")
        self.assertNotIn("fipe", c, "vazio tira")
        casa = next(r for r in self.store.data["rooms"] if not r.get("kind"))
        it = self.store.create_items([{"room": casa["id"], "name": "Sofá", "fipe": "005340-6 2014"}], "Ana")[0]
        self.assertNotIn("fipe", it, "num item da casa, não guarda")
        self.assertEqual(S.clean_fipe(""), ("", 0))

    def test_valor_do_mes_guardado_por_uma_semana(self):
        c = self.carro(fipe="005340-6 2014")
        r = S.fipe_item(c["id"])
        self.assertEqual(r, {"codigo": "005340-6", "ano": 2014, "valor": 85608.0, "marca": "Marca Exemplo", "modelo": "Carro Exemplo 2.0", "combustivel": "Gasolina",
                             "mes": "novembro de 2026", "anos": [2012, 2014]})
        S.fipe_item(c["id"])
        self.assertEqual(len(Api.pedidos), 1, "dentro da semana, não consulta de novo")
        self.assertEqual(self.store.item(c["id"])["value"], 50000.0, "consultar não muda o valor do bem")
        d = S.read_json(S.FIPE_FILE)
        d["005340-6"]["em"] = (datetime.now() - timedelta(days=S.FIPE_DIAS + 1)).isoformat(timespec="seconds")
        S.write_json_atomic(S.FIPE_FILE, d)
        Api.status = {"005340-6": 500}
        self.assertEqual(S.fipe_item(c["id"])["valor"], 85608.0, "sem resposta, vale o guardado")
        self.assertEqual(len(Api.pedidos), 2)
        self.assertEqual(S.fipe_de("005340-6", 1999)["valor"], 0, "o código não tem esse ano")
        S.write_json_atomic(S.FIPE_FILE, {"005340-6": {"em": "ruim", "linhas": []}})
        with self.assertRaises(S.ApiError) as cm:
            S.fipe_item(c["id"])
        self.assertEqual(cm.exception.status, 502)
        with self.assertRaises(S.ApiError) as cm:
            S.fipe_de("001004-9", 2014)
        self.assertEqual(cm.exception.status, 404)
        for iid, st in (("nao-existe", 404), (self.carro()["id"], 400)):
            with self.assertRaises(S.ApiError) as cm:
                S.fipe_item(iid)
            self.assertEqual(cm.exception.status, st)

        class H:
            def send_json(self, o, st=200):
                self.o = o
        h = H()
        Api.status = {}
        S.r_fipe(h, {"item": [c["id"]]})
        self.assertEqual(h.o["valor"], 85608.0)


class Ferramentas(Base):
    def test_fipe_pelo_bem_e_pelo_codigo(self):
        c = self.carro(fipe="005340-6 2014")
        r = self.json("fipe", {"id": c["id"]})
        self.assertEqual((r["valor_fipe"], r["valor_gravado"], r["diferenca"], r["veiculo"], r["tabela_de"], r["combustivel"]),
                         (85608.0, 50000.0, 35608.0, "Marca Exemplo Carro Exemplo 2.0", "novembro de 2026", "Gasolina"))
        self.assertEqual(self.store.item(c["id"])["value"], 50000.0, "só lê")
        r = self.json("fipe", {"codigo": "0053406", "ano": 2012})
        self.assertEqual((r["valor_fipe"], "item" in r), (70000.0, False))
        r = self.json("fipe", {"codigo": "005340-6", "ano": 1999})
        self.assertEqual((r["aviso"], r["anos_do_codigo"], "valor_fipe" in r), ("O código não tem o ano 1999 na tabela.", [2012, 2014], False))
        self.erro("fipe", {}, "Mande o id de um bem com o código FIPE")
        self.erro("fipe", {"codigo": "001004-9", "ano": 2014}, "não está na Tabela FIPE")
        self.erro("fipe", {"id": self.carro()["id"]}, "não tem o código da Tabela FIPE")
        self.assertFalse(F.POR_NOME["fipe"]["grava"])
        self.assertEqual(self.json("ver_item", {"id": c["id"]})["fipe"], "005340-6 2014")

    def test_guardar_o_codigo_pelas_ferramentas(self):
        c = self.carro()
        self.chamar("editar_item", {"id": c["id"], "fipe": "005340-6 2014"})
        self.assertEqual((self.store.item(c["id"])["fipe"], self.store.item(c["id"])["fipeYear"]), ("005340-6", 2014))
        self.erro("editar_item", {"id": c["id"], "fipe": "abc"}, "o código e o ano do veículo")
        self.chamar("editar_item", {"id": c["id"], "fipe": ""})
        self.assertNotIn("fipe", self.store.item(c["id"]))
        casa = next(i for i in self.store.data["items"] if not (self.store.room(i["room"]) or {}).get("kind"))
        self.erro("editar_item", {"id": casa["id"], "fipe": "005340-6 2014"}, "fipe só vale num veículo")
        self.chamar("cadastrar_itens", {"comodo": "Bens", "itens": [{"nome": "Moto Exemplo", "valor": 9000, "categoria": "Veículos", "fipe": "005340-6 2012"}]})
        moto = next(i for i in self.store.data["items"] if i["name"] == "Moto Exemplo")
        self.assertEqual((moto["fipe"], moto["fipeYear"]), ("005340-6", 2012))
