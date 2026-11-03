"""Números e ids dos itens: um número que já foi usado não volta, porque o ResolvIA liga tarefas pelo id do item."""
import unittest

from _boot import UnitBase


class NumeroNaoVolta(UnitBase):
    def ultimo(self, rid):
        return max(i["seq"] for i in self.items_in(rid))

    def novo(self, rid="sala", name="Item novo"):
        return self.store.create_items([{"room": rid, "name": name}], "Diego")[0]

    def test_excluir_o_ultimo_nao_devolve_o_numero(self):
        it = self.novo()
        self.store.delete_item(it["id"])
        de_novo = self.novo()
        self.assertEqual(de_novo["seq"], it["seq"] + 1)
        self.assertNotEqual(de_novo["id"], it["id"], "o id do excluído não volta para outro item")

    def test_mover_o_ultimo_para_outro_comodo_nao_devolve_o_numero(self):
        it = self.novo()
        seq = it["seq"]
        self.store.update_item(it["id"], {"room": "cozinha"}, "Diego")
        self.assertEqual(self.novo()["seq"], seq + 1)

    def test_o_comodo_guarda_o_maior_numero_usado(self):
        it = self.novo()
        self.store.delete_item(it["id"])
        self.assertEqual(self.store.room("sala")["lastSeq"], it["seq"])

    def test_desfazer_volta_o_item_com_o_mesmo_numero_e_id(self):
        it = self.novo()
        apagado = self.store.delete_item(it["id"])
        volta = self.store.create_items([dict(apagado)], "Diego", restore=True)[0]
        self.assertEqual((volta["id"], volta["seq"]), (it["id"], it["seq"]))

    def test_comodo_sem_lastseq_continua_do_maior_item(self):
        self.store.room("sala").pop("lastSeq", None)
        maior = self.ultimo("sala")
        self.assertEqual(self.store.next_seq("sala"), maior + 1)

    def test_lote_desfeito_nao_deixa_numero_guardado(self):
        antes = self.store.next_seq("sala")
        with self.assertRaises(self.S.ApiError):
            self.store.create_items([{"room": "sala", "name": "a"}, {"room": "sala", "name": ""}], "Diego")
        self.assertEqual(self.store.next_seq("sala"), antes)

    def test_lastseq_vai_para_a_gravacao(self):
        it = self.novo()
        self.store.delete_item(it["id"])
        self.store.load()
        self.assertEqual(self.store.room("sala").get("lastSeq"), it["seq"])


if __name__ == "__main__":
    unittest.main()
