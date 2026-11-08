"""Vários itens de uma vez (Buscar › Selecionar): o cômodo, a categoria ou a zona mudam juntos, tudo ou nada, com o
Desfazer (cada item volta como era, com o número de antes se estiver livre). Valores e datas do valor não mudam."""
import unittest

from _boot import UnitBase, server as S


class EmLote(UnitBase):
    def item(self, iid):
        return self.store.item(iid)

    def test_categoria_de_varios(self):
        antes = {i: (self.item(i)["value"], self.item(i).get("valueAt")) for i in ("sal-001", "sal-002")}
        out = self.store.update_items([{"id": "sal-001", "cat": "moveis"}, {"id": "sal-002", "cat": "moveis"}], "Ana")
        self.assertEqual([i["id"] for i in out], ["sal-001", "sal-002"])
        for i in ("sal-001", "sal-002"):
            self.assertEqual((self.item(i)["cat"], self.item(i)["updatedBy"]), ("moveis", "Ana"))
            self.assertEqual((self.item(i)["value"], self.item(i).get("valueAt")), antes[i], "o valor é do dono: não muda")

    def test_zona_de_varios_e_sem_zona(self):
        self.store.update_items([{"id": "coz-001", "zone": "  Bancada  "}, {"id": "coz-002", "zone": "Bancada"}], None)
        self.assertEqual({self.item(i)["zone"] for i in ("coz-001", "coz-002")}, {"Bancada"})
        self.store.update_items([{"id": "coz-001", "zone": ""}], None)
        self.assertEqual(self.item("coz-001")["zone"], "")

    def test_comodo_novo_da_o_proximo_numero_e_o_desfazer_volta_o_de_antes(self):
        a, b = self.item("sal-001"), self.item("sal-002")
        before = [{"id": x["id"], "room": x["room"], "seq": x["seq"], "zone": x.get("zone") or "", "cat": x["cat"]} for x in (a, b)]
        nxt = self.store.next_seq("varanda")
        self.store.update_items([{"id": "sal-001", "room": "varanda", "zone": ""}, {"id": "sal-002", "room": "varanda", "zone": ""}], None)
        self.assertEqual([(self.item(i)["room"], self.item(i)["seq"]) for i in ("sal-001", "sal-002")], [("varanda", nxt), ("varanda", nxt + 1)],
                         "na ordem, cada um com o próximo número da Varanda")
        self.assertEqual(self.store.tag(self.item("sal-001")), f"VAR-{nxt:03d}")
        self.assertEqual(self.item("sal-001")["id"], "sal-001", "o id não muda (o ResolvIA liga tarefas por ele)")
        self.store.update_items(before, None)
        self.assertEqual([(self.item(x["id"])["room"], self.item(x["id"])["seq"]) for x in before], [(x["room"], x["seq"]) for x in before],
                         "Desfazer: de volta, com o número de antes")

    def test_tudo_ou_nada(self):
        antes = self.item("sal-001")["cat"]
        for ruim, status in (([{"id": "sal-001", "cat": "moveis"}, {"id": "nao-existe", "cat": "moveis"}], 404),
                             ([{"id": "sal-001", "cat": "moveis"}, {"id": "sal-002", "cat": "inventada"}], 400),
                             ([{"id": "sal-001", "cat": "moveis"}, {"id": "sal-002", "room": "garagem"}], 400),
                             ([{"id": "sal-001", "cat": "moveis"}, "sal-002"], 400)):
            with self.subTest(ruim=ruim):
                self.assertApiError(status, self.store.update_items, ruim, None)
                self.assertEqual(self.item("sal-001")["cat"], antes, "um item ruim desfaz o lote inteiro")

    def test_pedido_vazio_ou_grande_demais(self):
        for ruim in (None, [], {}, "sal-001"):
            with self.subTest(ruim=ruim):
                self.assertApiError(400, self.store.update_items, ruim, None, msg_part="Escolha os itens")
        self.assertApiError(400, self.store.update_items, [{"id": "sal-001"}] * 2001, None, msg_part="2000")

    def test_o_mesmo_item_duas_vezes_vale_uma(self):
        out = self.store.update_items([{"id": "sal-001", "cat": "moveis"}, {"id": "sal-001", "cat": "outros"}], None)
        self.assertEqual((len(out), self.item("sal-001")["cat"]), (1, "moveis"))

    def test_sem_mudanca_nao_mexe_na_data(self):
        t = self.item("sal-001")["updatedAt"]
        self.store.update_items([{"id": "sal-001", "room": "sala"}], None)
        self.assertEqual(self.item("sal-001")["updatedAt"], t, "o mesmo cômodo: nada muda")

    def test_zona_longa_demais(self):
        self.assertApiError(400, self.store.update_items, [{"id": "sal-001", "zone": "z" * 121}], None)


if __name__ == "__main__":
    unittest.main()
