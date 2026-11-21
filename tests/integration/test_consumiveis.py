"""1.78.0, pelo HTTP: Usar consumíveis e Usar itens da casa (Mais > Configurações > Opções). A área Consumíveis, um
consumível nela, a leitura por IA (simulada), o que os outros apps leem (nunca os consumíveis; sem os itens da casa, só
os bens), o relatório em PDF e a regra de pelo menos um tipo ligado."""
import json
import unittest

from _boot import ServerCase


class Consumiveis(ServerCase):
    server_kw = {"mock_ai": True}  # a IA simulada do app (a mesma da prévia)

    def chave(self):
        with open(self.app.path("share", "integracao.json"), encoding="utf-8") as f:
            return {"Authorization": f"Bearer {json.load(f)['chave']}"}

    def tearDown(self):
        self.app.ok("PUT", "api/settings", {"itens": True, "bens": True})
        self.app.ok("PUT", "api/settings", {"consumiveis": False})

    def test_vem_desligado_e_a_tela_recebe_as_tres_chaves(self):
        s = self.app.data()["settings"]
        self.assertEqual((s["itens"], s["bens"], s["consumiveis"]), (True, True, False))
        self.assertEqual(self.app.post("api/rooms", {"kind": "consumiveis"})[0], 409)
        self.assertEqual(self.app.request("PUT", "api/settings", {"consumiveis": "sim"})[0], 400)

    def test_area_item_ia_e_fora_dos_outros_apps(self):
        self.app.ok("PUT", "api/settings", {"consumiveis": True})
        st, _, out = self.app.post("api/rooms", {"kind": "consumiveis"})
        self.assertEqual(st, 201)
        con = out["room"]
        self.assertEqual((con["id"], con["code"], con["kind"]), ("consumiveis", "CON", "consumiveis"))
        self.assertEqual(out["rooms"][-1]["id"], "consumiveis", "no fim, depois dos cômodos")
        self.assertEqual(self.app.ok("POST", "api/rooms", {"kind": "consumiveis"})["room"]["id"], "consumiveis", "de novo: a mesma área")

        foto = next(i["photos"][0] for i in self.app.data()["items"] if i.get("photos"))
        lido = self.app.ok("POST", "api/ai/identify", {"file": foto, "mode": "single", "room": "consumiveis", "consumivel": True})["items"][0]
        self.assertEqual((lido["name"], lido["zone"], lido["room"]), ("Pasta térmica", "", ""))
        self.assertIn("entre o processador e o cooler", lido["details"], "o que é e para que serve")
        comum = self.app.ok("POST", "api/ai/identify", {"file": foto, "mode": "single", "room": "sala"})["items"][0]
        self.assertNotEqual(comum["name"], "Pasta térmica", "sem o aviso, a leitura de um item comum")

        it = self.app.ok("POST", "api/items", {"room": "consumiveis", "name": lido["name"], "details": lido["details"], "qty": "2", "value": 45})["item"]
        self.assertEqual((it["room"], it["qty"], it["value"]), ("consumiveis", "2", 45))

        com = self.app.get("api/integracao/comodos", headers=self.chave())[2]["comodos"]
        self.assertNotIn("consumiveis", [c["id"] for c in com], "o ResolvIA e a CronologIA não veem a área")
        its = self.app.get("api/integracao/itens", headers=self.chave())[2]["itens"]
        self.assertNotIn(it["id"], [i["id"] for i in its], "o GerencIA não soma os consumíveis no patrimônio")
        self.assertEqual(len(its), len(self.app.data()["items"]) - 1, "todos os outros")

        # 1.81.0: os consumíveis à parte, para o EconomIA (a Reposição): o nome, a categoria, a quantidade e para que serve; sem valor
        st, _, out = self.app.get("api/integracao/consumiveis", headers=self.chave())
        self.assertEqual((st, out["ligado"], [c["id"] for c in out["consumiveis"]]), (200, True, [it["id"]]))
        c = out["consumiveis"][0]
        self.assertEqual((c["nome"], c["quantidade"], c["para_que_serve"] != "", sorted(c)), ("Pasta térmica", "2", True, ["categoria", "id", "nome", "para_que_serve", "quantidade"]))
        self.assertEqual(self.app.get("api/integracao/consumiveis")[0], 401, "só com a chave")
        self.assertEqual(self.app.post("api/integracao/consumiveis", {}, headers=self.chave())[0], 404, "só leitura")

        st, hd, pdf = self.app.request("GET", "api/relatorio.pdf")
        self.assertEqual((st, pdf[:5]), (200, b"%PDF-"))
        self.assertNotIn("Pasta t".encode("latin-1"), pdf, "o relatório é do patrimônio: sem os consumíveis")
        self.assertIn("Pasta térmica", self.app.request("GET", "api/export.csv")[2].decode("utf-8-sig"), "a planilha tem tudo")

        self.app.ok("PUT", "api/settings", {"consumiveis": False})
        self.assertIn(it["id"], [i["id"] for i in self.app.data()["items"]], "desligado: continua guardado")
        self.assertEqual(self.app.get("api/integracao/consumiveis", headers=self.chave())[2], {"versao": self.app.get("api/health")[2]["version"], "ligado": False, "consumiveis": []}, "desligado: nenhum para os outros apps")
        self.assertEqual(self.app.post("api/rooms", {"kind": "consumiveis"})[0], 409)

    def test_sem_os_itens_da_casa(self):
        self.app.ok("POST", "api/rooms", {"kind": "bens"})
        bem = self.app.ok("POST", "api/items", {"room": "bens", "name": "Moto 150", "cat": "veiculos", "value": "9.000"})["item"]
        n0, fora0 = len(self.app.data()["items"]), len(self.app.get("api/integracao/itens", headers=self.chave())[2]["itens"])
        self.assertIs(self.app.ok("PUT", "api/settings", {"itens": False})["itens"], False)
        com = self.app.get("api/integracao/comodos", headers=self.chave())[2]["comodos"]
        self.assertEqual([c["id"] for c in com], ["bens"], "os outros apps ficam só com os Bens")
        its = self.app.get("api/integracao/itens", headers=self.chave())[2]["itens"]
        self.assertEqual([i["id"] for i in its], [bem["id"]])
        self.assertEqual(len(self.app.data()["items"]), n0, "os itens da casa continuam guardados")
        st, _, out = self.app.post("api/rooms", {"name": "Garagem"})
        self.assertEqual(st, 409)
        st, _, pdf = self.app.request("GET", "api/relatorio.pdf")
        self.assertEqual((st, pdf[:5]), (200, b"%PDF-"), "o relatório sai só com os bens")
        self.app.ok("PUT", "api/settings", {"itens": True})
        self.assertEqual(len(self.app.get("api/integracao/itens", headers=self.chave())[2]["itens"]), fora0, "ligado de novo: volta")

    def test_pelo_menos_um_fica_ligado(self):
        self.app.ok("PUT", "api/settings", {"itens": False})
        st, _, out = self.app.request("PUT", "api/settings", {"bens": False})
        self.assertEqual(st, 409)
        self.assertIn("Pelo menos um fica ligado", json.dumps(out, ensure_ascii=False))
        self.assertIs(self.app.data()["settings"]["bens"], True, "nada mudou")
        self.assertEqual(self.app.request("PUT", "api/settings", {"itens": False, "bens": False, "consumiveis": False})[0], 409)
        self.app.ok("PUT", "api/settings", {"bens": False, "consumiveis": True})  # trocar um pelo outro vale
        s = self.app.data()["settings"]
        self.assertEqual((s["itens"], s["bens"], s["consumiveis"]), (False, False, True))


if __name__ == "__main__":
    unittest.main()
