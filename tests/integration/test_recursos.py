"""1.54.0: Recursos. A IA diz o que um equipamento tem (funções, modos, conexões), só em Eletrônicos, Utilidades e Veículos
e só com a IA ligada; o resultado fica guardado até o item mudar (nome ou detalhes) e conta no Uso da IA."""
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
