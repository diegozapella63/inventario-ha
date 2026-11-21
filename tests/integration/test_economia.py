"""1.85.0, pelo HTTP: Compras no EconomIA na ficha de um consumível. Um EconomIA de mentira (o contrato do 1.47.0: o
arquivo share/economia/integracao.json com url, chave e compras, e GET/POST /api/integracao/compras) responde pelo nome;
daqui só vai o nome (e, no Repor, a duração). Sem o arquivo, com os consumíveis desligados ou num item da casa, nada.
Dados inventados."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from _boot import AppServer

CHAVE = "chave-do-economia-" + "x" * 24


class EconomiaFalso(BaseHTTPRequestHandler):
    pedidos = []
    recusa = None  # (status, corpo)
    estado = {"na_lista": False, "vezes": 2, "ultima": "2026-10-28", "compras": ["2026-10-28", "2026-09-01", "ruim"], "reposicao": None}

    def log_message(self, *a):
        pass

    def _responde(self, corpo_pedido=None):
        u = urlsplit(self.path)
        type(self).pedidos.append({"metodo": self.command, "caminho": u.path, "q": parse_qs(u.query), "corpo": corpo_pedido,
                                   "chave": self.headers.get("Authorization"), "app": self.headers.get("X-App")})
        st, out = (200, dict(type(self).estado, versao="1.47.0", nome="x"))
        if self.headers.get("Authorization") != "Bearer " + CHAVE:
            st, out = 401, {"erro": "Chave inválida"}
        elif type(self).recusa:
            st, out = type(self).recusa
        elif corpo_pedido:
            if corpo_pedido.get("acao") == "lista":
                type(self).estado = dict(type(self).estado, na_lista=True)
                out = dict(type(self).estado, texto="Pus Creme de mãos na lista.")
            else:
                type(self).estado = dict(type(self).estado, reposicao={"cada": 6, "unidade": "mes", "texto": "a cada 6 meses", "proxima": "2027-05-02", "na_hora": False})
                out = dict(type(self).estado, texto="Pus Creme de mãos na Reposição.")
        dados = json.dumps(out).encode()
        self.send_response(st)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        self._responde()

    def do_POST(self):
        self._responde(json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}"))


class ComprasNoEconomia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eco = ThreadingHTTPServer(("127.0.0.1", 0), EconomiaFalso)
        threading.Thread(target=cls.eco.serve_forever, daemon=True).start()
        cls.pasta = tempfile.mkdtemp(prefix="inv-economia-")
        cls.arq = os.path.join(cls.pasta, "integracao.json")
        cls.app = AppServer(env={"INV_ECONOMIA": cls.arq})
        cls.app.ok("PUT", "api/settings", {"consumiveis": True})
        cls.app.ok("POST", "api/rooms", {"kind": "consumiveis"})
        cls.creme = cls.app.ok("POST", "api/items", {"room": "consumiveis", "name": "Creme de mãos", "dur": 180})["item"]
        cls.sabao = cls.app.ok("POST", "api/items", {"room": "consumiveis", "name": "Sabão"})["item"]

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()
        cls.eco.shutdown()
        cls.eco.server_close()

    def grava(self, **kw):
        corpo = {"app": "economia", "nome": "EconomIA", "versao": "1.47.0", "url": f"http://127.0.0.1:{self.eco.server_address[1]}", "ip_url": None,
                 "chave": CHAVE, "compras": "/api/integracao/compras"}
        corpo.update(kw)
        with open(self.arq, "w", encoding="utf-8") as f:
            json.dump(corpo, f)

    def setUp(self):
        EconomiaFalso.pedidos.clear()
        EconomiaFalso.recusa = None
        EconomiaFalso.estado = {"na_lista": False, "vezes": 2, "ultima": "2026-10-28", "compras": ["2026-10-28", "2026-09-01", "ruim"], "reposicao": None}
        self.grava()

    def test_sem_o_arquivo_nada_aparece(self):
        os.remove(self.arq)
        self.assertIs(self.app.data()["economia"], False)
        self.assertEqual(self.app.get(f"api/economia/compras?item={self.creme['id']}")[0], 404)
        self.grava(chave="")
        self.assertIs(self.app.data()["economia"], False, "um arquivo sem a chave não vale")
        self.grava(compras="http://outro.test/")
        self.assertIs(self.app.data()["economia"], False, "a rota tem de ser um caminho do próprio EconomIA")

    def test_as_compras_de_um_consumivel_pelo_nome(self):
        self.assertIs(self.app.data()["economia"], True)
        c = self.app.ok("GET", f"api/economia/compras?item={self.creme['id']}")["compras"]
        self.assertEqual(c, {"na_lista": False, "vezes": 2, "ultima": "2026-10-28", "compras": ["2026-10-28", "2026-09-01"], "reposicao": None, "texto": ""})
        p = EconomiaFalso.pedidos[-1]
        self.assertEqual((p["metodo"], p["caminho"], p["q"], p["chave"], p["app"]),
                         ("GET", "/api/integracao/compras", {"nome": ["Creme de mãos"]}, "Bearer " + CHAVE, "InventarIA"))
        casa = next(i for i in self.app.data()["items"] if i["room"] != "consumiveis")
        self.assertEqual(self.app.get(f"api/economia/compras?item={casa['id']}")[0], 404, "só os consumíveis")
        self.assertEqual(self.app.get("api/economia/compras?item=nao-existe")[0], 404)

    def test_por_na_lista_e_repor_pela_duracao(self):
        c = self.app.ok("POST", "api/economia/compras", {"item": self.creme["id"], "acao": "lista"})["compras"]
        self.assertEqual((c["na_lista"], c["texto"]), (True, "Pus Creme de mãos na lista."))
        self.assertEqual(EconomiaFalso.pedidos[-1]["corpo"], {"nome": "Creme de mãos", "acao": "lista"}, "só o nome vai")
        c = self.app.ok("POST", "api/economia/compras", {"item": self.creme["id"], "acao": "repor"})["compras"]
        self.assertEqual(c["reposicao"], {"texto": "a cada 6 meses", "proxima": "2027-05-02", "na_hora": False})
        self.assertEqual(EconomiaFalso.pedidos[-1]["corpo"], {"nome": "Creme de mãos", "acao": "repor", "dias": 180})
        st, _, out = self.app.post("api/economia/compras", {"item": self.sabao["id"], "acao": "repor"})
        self.assertEqual((st, out["error"] if "error" in out else out.get("erro")), (400, "Informe a Duração estimada do consumível para repor de tempos em tempos."))
        self.assertEqual(self.app.post("api/economia/compras", {"item": self.creme["id"], "acao": "apagar"})[0], 400)

    def test_o_economia_recusa_ou_some(self):
        EconomiaFalso.recusa = (400, {"erro": "Diga em qual lista pôr (lista): Mercado, Farmácia."})
        st, _, out = self.app.post("api/economia/compras", {"item": self.creme["id"], "acao": "lista"})
        self.assertEqual((st, out.get("error") or out.get("erro")), (400, "Diga em qual lista pôr (lista): Mercado, Farmácia."), "o que o EconomIA diz chega à tela")
        EconomiaFalso.recusa = (401, {"erro": "x"})
        st, _, out = self.app.get(f"api/economia/compras?item={self.creme['id']}")
        self.assertEqual(st, 409)
        self.assertIn("Consumíveis do InventarIA", out.get("error") or out.get("erro"))
        EconomiaFalso.recusa = (500, {})
        self.assertEqual(self.app.get(f"api/economia/compras?item={self.creme['id']}")[0], 502)
        self.grava(url="http://127.0.0.1:9", ip_url=f"http://127.0.0.1:{self.eco.server_address[1]}")
        EconomiaFalso.recusa = None
        self.assertEqual(self.app.ok("GET", f"api/economia/compras?item={self.creme['id']}")["compras"]["vezes"], 2, "sem o nome, vale o IP")
        self.grava(url="http://127.0.0.1:9")
        self.assertEqual(self.app.get(f"api/economia/compras?item={self.creme['id']}")[0], 502)
        self.app.ok("PUT", "api/settings", {"consumiveis": False})
        self.assertIs(self.app.data()["economia"], False, "com os consumíveis desligados, nada")
        self.app.ok("PUT", "api/settings", {"consumiveis": True})


if __name__ == "__main__":
    unittest.main()
