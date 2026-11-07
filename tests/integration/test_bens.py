"""Bens pelo HTTP: criar a área (uma vez), um bem nela, e o que os outros apps leem (o ResolvIA e a CronologIA veem Bens
ao lado dos cômodos, com "tipo": "bens"; o GerencIA soma os bens no patrimônio pela categoria)."""
import json
import unittest

from _boot import ServerCase


class Bens(ServerCase):
    def chave(self):
        with open(self.app.path("share", "integracao.json"), encoding="utf-8") as f:
            return {"Authorization": f"Bearer {json.load(f)['chave']}"}

    def test_area_itens_e_integracao(self):
        st, _, out = self.app.post("api/rooms", {"kind": "bens"})
        self.assertEqual(st, 201)
        ben = out["room"]
        self.assertEqual((ben["id"], ben["code"], ben["kind"]), ("bens", "BEN", "bens"))
        self.assertEqual(out["rooms"][-1]["id"], "bens", "Bens no fim")
        self.assertIn("imoveis", [c["id"] for c in out["cats"]], "devolve as categorias (Imóveis e Veículos)")
        self.assertEqual(self.app.ok("POST", "api/rooms", {"kind": "bens"})["room"]["id"], "bens", "de novo: a mesma área")
        self.assertEqual(self.app.post("api/rooms", {"kind": "x", "name": "X"})[0], 400)

        it = self.app.ok("POST", "api/items", {"room": "bens", "name": "Terreno na serra", "cat": "imoveis", "value": "120.000"})["item"]
        self.assertEqual((it["room"], it["value"]), ("bens", 120000))

        st, _, out = self.app.get("api/integracao/comodos", headers=self.chave())
        self.assertEqual(st, 200)
        self.assertEqual(out["comodos"][-1], {"id": "bens", "nome": "Bens", "codigo": "BEN", "itens": 1, "tipo": "bens"},
                         "os outros apps veem Bens ao lado dos cômodos")
        self.assertNotIn("tipo", out["comodos"][0], "os cômodos continuam como antes")
        st, _, out = self.app.get("api/integracao/itens", headers=self.chave())
        terreno = next(i for i in out["itens"] if i["id"] == it["id"])
        self.assertEqual((terreno["comodo"], terreno["categoria"], terreno["valor"]), ("bens", "imoveis", 120000.0))
        self.assertEqual(out["categorias"]["imoveis"], "Imóveis", "o GerencIA recebe o nome da categoria")
        self.assertEqual(out["itens"][-1]["id"], it["id"], "os bens vêm depois dos itens da casa")

        rows = self.app.request("GET", "api/export.csv")[2].decode("utf-8-sig")
        self.assertIn("Terreno na serra", rows, "a planilha tem os bens")

    def test_desligado_some_dos_outros_apps(self):
        self.app.ok("POST", "api/rooms", {"kind": "bens"})
        it = self.app.ok("POST", "api/items", {"room": "bens", "name": "Moto 150", "cat": "veiculos", "value": "9.000"})["item"]
        self.assertEqual(self.app.ok("PUT", "api/settings", {"bens": False})["bens"], False)
        self.assertIs(self.app.data()["settings"]["bens"], False)
        try:
            com = self.app.get("api/integracao/comodos", headers=self.chave())[2]["comodos"]
            self.assertNotIn("bens", [c["id"] for c in com], "o ResolvIA e a CronologIA ficam sem a área Bens")
            its = self.app.get("api/integracao/itens", headers=self.chave())[2]["itens"]
            self.assertNotIn(it["id"], [i["id"] for i in its], "o GerencIA fica sem os bens no patrimônio")
            self.assertIn(it["id"], [i["id"] for i in self.app.data()["items"]], "e o bem continua guardado")
            self.assertEqual(self.app.post("api/rooms", {"kind": "bens"})[0], 409)
            self.assertEqual(self.app.request("PUT", "api/settings", {"bens": "não"})[0], 400)
        finally:
            self.app.ok("PUT", "api/settings", {"bens": True})
        its = self.app.get("api/integracao/itens", headers=self.chave())[2]["itens"]
        self.assertIn(it["id"], [i["id"] for i in its], "ligado de novo: volta")


if __name__ == "__main__":
    unittest.main()
