"""1.54.0: Recursos. A IA diz o que um equipamento tem (funções, modos, conexões), só em Eletrônicos, Utilidades e Veículos
e só com a IA ligada; o resultado fica guardado até o item mudar (nome ou detalhes) e conta no Uso da IA. 1.65.0: os de
todos os eletrônicos de uma vez (Novidades › Eletrônicos)."""
import time
import unittest

from _boot import ServerCase


def esperar(app, jid, timeout=8):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = app.ok("GET", f"api/recursos/{jid}")
        if st["stage"] != "busy":
            return st
        time.sleep(0.15)
    raise AssertionError("a busca dos recursos não terminou")


class Recursos(ServerCase):
    def test_recursos_de_um_eletronico_guardados_ate_o_item_mudar(self):
        app = self.fresh(mock_ai=True)
        self.assertEqual(app.ok("GET", "api/recursos?item=sal-007"), {}, "nunca visto")
        st = esperar(app, app.ok("POST", "api/recursos", {"item": "sal-007"})["id"])
        self.assertEqual(st["stage"], "done")
        self.assertEqual([r["nome"] for r in st["rec"]["recursos"]], ["Wi-Fi", "Modo econômico", "Timer"])
        r = app.ok("GET", "api/recursos?item=sal-007")
        self.assertTrue(r["at"])
        self.assertEqual((len(r["recursos"]), r["site"]), (3, "exemplo.com.br"))
        self.assertEqual(app.ok("DELETE", f"api/recursos/{app.ok('POST', 'api/recursos', {'item': 'sal-007'})['id']}"), {"ok": True})
        # o item mudou de nome: o que foi visto não vale mais
        it = next(i for i in app.data()["items"] if i["id"] == "sal-007")
        app.ok("PUT", "api/items/sal-007", {**it, "name": it["name"] + " (outro modelo)"})
        self.assertEqual(app.ok("GET", "api/recursos?item=sal-007"), {})

    def test_os_de_todos_os_eletronicos(self):
        """1.65.0: GET api/recursos/todos lista os eletrônicos e quantos recursos cada um tem; POST busca os que faltam (o
        mesmo equipamento em vários cômodos numa busca só, guardada em todos); de novo, nada a buscar."""
        app = self.fresh(mock_ai=True)
        els = {i["id"] for i in app.data()["items"] if i["cat"] == "eletronicos"}
        tv = next(i for i in app.data()["items"] if i["id"] == "sal-007")
        outro = app.ok("POST", "api/items", {"room": "quarto", "name": tv["name"], "cat": "eletronicos", "value": 10})["item"]["id"]
        esperar(app, app.ok("POST", "api/recursos", {"item": "sal-007"})["id"])
        ov = app.ok("GET", "api/recursos/todos")
        self.assertEqual(set(ov["itens"]), els | {outro}, "só os eletrônicos")
        self.assertEqual((ov["itens"]["sal-007"]["n"], ov["itens"][outro], ov["job"]), (3, None, None))
        self.assertEqual(ov["grupos"][outro], ov["grupos"]["sal-007"], "o mesmo equipamento em dois cômodos")
        st = esperar(app, app.ok("POST", "api/recursos/todos", {})["id"], timeout=20)
        self.assertEqual(st["stage"], "done", st)
        grupos = {ov["grupos"][i] for i in els | {outro}}
        self.assertEqual(st["summary"], {"buscados": len(grupos) - 1, "erros": 0, "total": len(grupos) - 1}, "a TV já tinha: o outro cômodo ganha o mesmo, sem buscar")
        ov = app.ok("GET", "api/recursos/todos")
        self.assertTrue(all(v and v["n"] for v in ov["itens"].values()), ov["itens"])
        self.assertEqual(app.ok("GET", f"api/recursos?item={outro}")["recursos"], app.ok("GET", "api/recursos?item=sal-007")["recursos"])
        st = esperar(app, app.ok("POST", "api/recursos/todos", {})["id"])
        self.assertEqual(st["summary"], {"buscados": 0, "erros": 0, "total": 0}, "de novo: nada a buscar")
        app.ok("PUT", "api/settings", {"ai": False})
        self.assertEqual(app.request("GET", "api/recursos/todos")[0], 409, "IA desligada: recusa")
        self.assertEqual(app.request("POST", "api/recursos/todos", {})[0], 409)

    def test_so_nas_categorias_dos_recursos_e_com_a_ia(self):
        app = self.fresh(mock_ai=True)
        st, _, body = app.request("POST", "api/recursos", {"item": "sal-001"})
        self.assertEqual((st, body["error"]), (400, "Os recursos são dos eletrônicos, das utilidades e dos veículos."))
        self.assertEqual(app.request("POST", "api/recursos", {"item": "nao-existe"})[0], 404)
        app.ok("PUT", "api/settings", {"ai": False})
        self.assertEqual(app.request("POST", "api/recursos", {"item": "sal-007"})[0], 409, "IA desligada: recusa")
        self.assertEqual(app.request("GET", "api/recursos?item=sal-007")[0], 409)

    def test_utilidades_e_veiculos_fixas(self):
        app = self.fresh(mock_ai=True)
        for cid in ("utilidades", "veiculos"):
            self.assertEqual(app.request("DELETE", f"api/cats/{cid}")[0], 400)
            self.assertEqual(app.request("PUT", f"api/cats/{cid}", {"name": "Outra"})[0], 400)


if __name__ == "__main__":
    unittest.main()
