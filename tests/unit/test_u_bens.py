"""Bens no servidor: a área Bens (o que fica fora de casa: casa, terreno, carro) é um "cômodo" do sistema (kind "bens"),
criado com o primeiro bem e sempre depois dos cômodos; as categorias Imóveis e Veículos; nada muda nos itens que já existem."""
import unittest

from _boot import UnitBase, server as S


class Area(UnitBase):
    def test_criada_uma_vez(self):
        n = len(self.store.data["rooms"])
        a = self.store.create_room({"kind": "bens"})
        self.assertEqual((a["id"], a["code"], a["name"], a["kind"]), ("bens", "BEN", "Bens", "bens"))
        b = self.store.create_room({"kind": "bens", "name": "Outro nome"})
        self.assertIs(a, b, "a segunda vez devolve a mesma área")
        self.assertEqual(len(self.store.data["rooms"]), n + 1)
        self.assertIs(self.store.bens_room(), a)

    def test_sem_bens_nao_ha_area(self):
        self.assertIsNone(self.store.bens_room())

    def test_um_comodo_chamado_bens_nao_e_a_area(self):
        c = self.store.create_room({"name": "Bens", "code": "BEN"})
        self.assertNotIn("kind", c)
        self.assertIsNone(self.store.bens_room(), "um cômodo com o nome Bens continua um cômodo")
        a = self.store.create_room({"kind": "bens"})
        self.assertEqual((a["id"], a["code"]), ("bens-2", "BEN2"), "a área ganha outro id e outro código")

    def test_outro_tipo_recusa(self):
        with self.assertRaises(S.ApiError) as e:
            self.store.create_room({"kind": "garagem", "name": "Garagem"})
        self.assertEqual(e.exception.status, 400)

    def test_sempre_depois_dos_comodos(self):
        a = self.store.create_room({"kind": "bens"})
        self.store.create_room({"name": "Garagem"})
        self.assertEqual(self.store.data["rooms"][-1]["id"], a["id"], "um cômodo novo entra antes de Bens")
        casa = [r["id"] for r in self.store.data["rooms"] if r is not a]
        self.store.reorder_rooms(list(reversed(casa)))
        self.assertEqual([r["id"] for r in self.store.data["rooms"]], list(reversed(casa)) + [a["id"]], "Organizar os cômodos deixa Bens no fim")
        self.store.reorder_rooms([a["id"]] + casa)
        self.assertEqual(self.store.data["rooms"][-1]["id"], a["id"], "nem pedindo, Bens sai do fim")

    def test_bens_e_itens_como_os_outros(self):
        a = self.store.create_room({"kind": "bens"})
        it = self.store.create_items([{"room": a["id"], "name": "Carro hatch", "cat": "veiculos", "value": 60000}], None)[0]
        self.assertEqual((self.store.tag(it), it["cat"], it["value"]), ("BEN-001", "veiculos", 60000))


class Categorias(UnitBase):
    def test_padrao_tem_imoveis_e_veiculos_antes_de_outros(self):
        ids = [c["id"] for c in self.store.cats()]
        self.assertEqual(ids[-3:], ["imoveis", "veiculos", "outros"])
        self.assertEqual(self.store.cat_map()["imoveis"], "Imóveis")

    def test_lista_editada_ganha_as_duas_com_o_primeiro_bem(self):
        self.store.data["cats"] = [{"id": "moveis", "name": "Móveis"}, {"id": "eletronicos", "name": "Aparelhos"}, {"id": "outros", "name": "Outros"}]
        antes = {i["id"]: (i["cat"], i["value"]) for i in self.store.data["items"]}
        self.store.create_room({"kind": "bens"})
        self.assertEqual([c["id"] for c in self.store.cats()], ["moveis", "eletronicos", "imoveis", "veiculos", "outros"])
        self.assertEqual(self.store.cat_map()["eletronicos"], "Aparelhos", "o nome que a casa deu continua")
        self.assertEqual({i["id"]: (i["cat"], i["value"]) for i in self.store.data["items"]}, antes, "nenhum item muda")

    def test_lista_editada_com_imoveis_nao_repete(self):
        self.store.data["cats"] = [{"id": "imoveis", "name": "Casas"}, {"id": "outros", "name": "Outros"}]
        self.store.create_room({"kind": "bens"})
        self.assertEqual([(c["id"], c["name"]) for c in self.store.cats()], [("eletronicos", "Eletrônicos"), ("imoveis", "Casas"), ("veiculos", "Veículos"), ("outros", "Outros")],
                         "Eletrônicos (a das novidades) sempre existe")

    def test_lista_padrao_continua_padrao(self):
        self.store.create_room({"kind": "bens"})
        self.assertNotIn("cats", self.store.data, "sem lista editada, nada é gravado")



class UsarBens(UnitBase):
    """Mais > Configurações > Opções > Usar bens: vem ligado; desligado, os bens somem do app, dos outros apps e da IA."""

    def setUp(self):
        super().setUp()
        self.area = self.store.create_room({"kind": "bens"})
        self.carro = self.store.create_items([{"room": self.area["id"], "name": "Carro hatch", "cat": "veiculos", "value": 60000}], None)[0]

    def test_vem_ligado(self):
        self.assertTrue(S.bens_enabled())
        rooms, items = S.visible_data()
        self.assertIn(self.area, rooms)
        self.assertIn(self.carro, items)

    def test_desligado_some_sem_apagar(self):
        self.store.settings["bens"] = False
        rooms, items = S.visible_data()
        self.assertNotIn(self.area["id"], [r["id"] for r in rooms])
        self.assertNotIn(self.carro["id"], [i["id"] for i in items])
        self.assertIn(self.carro, self.store.data["items"], "o bem continua guardado")
        self.assertNotIn("Carro hatch", S.chat_context({}), "a IA não vê os bens")
        self.assertNotIn("Bens", S.chat_context({}).split("Cômodos:")[1].split(".")[0], "nem a área Bens")

    def test_desligado_nao_cria_a_area(self):
        self.store.data["rooms"] = [r for r in self.store.data["rooms"] if r.get("kind") != "bens"]
        self.store.settings["bens"] = False
        with self.assertRaises(S.ApiError) as e:
            self.store.create_room({"kind": "bens"})
        self.assertEqual((e.exception.status, e.exception.msg), (409, "Os bens estão desligados. Para usar, ligue em Mais > Configurações > Opções."))


if __name__ == "__main__":
    unittest.main()
