"""Itens e cômodos: criar, editar, mover, conflitos entre aparelhos, códigos e ordem."""
import os
import time
import unittest
from unittest import mock

from _boot import UnitBase, server as S


class Itens(UnitBase):
    def novo(self, **kw):
        body = {"room": "sala", "name": "Poltrona", **kw}
        return self.store.create_items([body], kw.pop("user", None))[0]

    def test_cria_com_codigo_do_comodo_e_proximo_numero(self):
        antes = max(i["seq"] for i in self.items_in("sala"))
        it = self.novo(details=" couro ", cat="moveis", qty="2", value="1.500,00", zone="Canto", flag=" ver pé ")
        self.assertEqual(it["seq"], antes + 1)
        self.assertEqual(it["id"], f"sal-{antes + 1:03d}")
        self.assertEqual(self.store.tag(it), f"SAL-{antes + 1:03d}")
        self.assertEqual((it["details"], it["cat"], it["qty"], it["value"], it["zone"], it["flag"]), ("couro", "moveis", "2", 1500, "Canto", "ver pé"))
        self.assertEqual(it["source"], "manual")
        self.assertEqual(it["createdAt"], it["updatedAt"])
        self.assertIn(it, self.store.data["items"])
        self.assertEqual(S.read_json(S.DATA_FILE)["items"][-1]["id"], it["id"], "fica gravado no arquivo")

    def test_padroes_e_campos_obrigatorios(self):
        it = self.novo()
        self.assertEqual((it["qty"], it["value"], it["cat"], it["photos"], it["flag"], it["zone"], it["checked"]), ("1", 0, "outros", [], None, "", False))
        self.assertApiError(400, self.store.create_items, [{"room": "sala", "name": "  "}], None, msg_part="nome")
        self.assertApiError(400, self.store.create_items, [{"room": "nao-existe", "name": "X"}], None, msg_part="cômodo")
        self.assertApiError(400, self.store.create_items, [{"room": "sala", "name": "X", "value": "caro"}], None)
        self.assertApiError(400, self.store.create_items, [{"room": "sala", "name": "X" * 201}], None)

    def test_quem_cadastrou(self):
        it = self.store.create_items([{"room": "sala", "name": "X"}], "Davi")[0]
        self.assertEqual((it["createdBy"], it["updatedBy"]), ("Davi", "Davi"))
        it = self.store.update_item(it["id"], {"name": "Y"}, "Outra pessoa")
        self.assertEqual((it["createdBy"], it["updatedBy"]), ("Davi", "Outra pessoa"))

    def test_lote_falha_inteiro_se_um_item_e_ruim(self):
        n = len(self.store.data["items"])
        self.assertApiError(400, self.store.create_items, [{"room": "sala", "name": "A"}, {"room": "sala", "name": ""}], None)
        self.assertEqual(len(self.store.data["items"]), n, "nem na memória: senão a próxima gravação salvaria o item pela metade")
        disk = S.read_json(S.DATA_FILE)
        self.assertEqual(len(disk["items"]), 38, "nada vai para o arquivo quando o lote falha")

    def test_lote_com_foto_do_comodo(self):
        its = self.store.create_items([{"room": "cozinha", "name": "A"}, {"room": "cozinha", "name": "B"}], None,
                                      room_photo={"room": "cozinha", "file": "sala-2.jpg", "label": "Bancada"})
        self.assertEqual([i["seq"] for i in its], [its[0]["seq"], its[0]["seq"] + 1])
        fotos = self.store.room("cozinha")["photos"]
        self.assertIn({"file": "sala-2.jpg", "label": "Bancada"}, fotos)
        self.store.create_items([{"room": "cozinha", "name": "C"}], None, room_photo={"room": "cozinha", "file": "sala-2.jpg"})
        self.assertEqual(sum(p["file"] == "sala-2.jpg" for p in self.store.room("cozinha")["photos"]), 1, "a mesma foto não entra duas vezes")

    def test_restaurar_mantem_id_e_numero_quando_livres(self):
        it = self.store.create_items([{"room": "sala", "name": "Velho", "id": "sal-900", "seq": 900, "createdAt": "2020-01-01T00:00:00-03:00",
                                       "createdBy": "Alguém"}], None, restore=True)[0]
        self.assertEqual((it["id"], it["seq"], it["createdAt"], it["createdBy"]), ("sal-900", 900, "2020-01-01T00:00:00-03:00", "Alguém"))
        dup = self.store.create_items([{"room": "sala", "name": "Outro", "id": "sal-900", "seq": 900}], None, restore=True)[0]
        self.assertNotEqual(dup["id"], "sal-900")
        self.assertNotEqual(dup["seq"], 900)
        ruim = self.store.create_items([{"room": "sala", "name": "R", "id": "../x", "seq": -3}], None, restore=True)[0]
        self.assertRegex(ruim["id"], r"^sal-\d{3}")

    def test_id_repetido_ganha_sufixo(self):
        livre = self.store.next_seq("sala")
        self.store.data["items"].append({"id": f"sal-{livre:03d}", "room": "cozinha", "seq": 99, "name": "x"})
        it = self.novo()
        self.assertTrue(it["id"].startswith(f"sal-{livre:03d}-"))

    def test_editar_campos(self):
        it = self.novo(value=100, qty="1")
        time.sleep(1.01)
        novo = self.store.update_item(it["id"], {"name": " Poltrona de couro ", "details": "marrom", "zone": "Janela", "qty": "", "value": "250,5",
                                                 "flag": "", "cat": "moveis"}, None)
        self.assertEqual((novo["name"], novo["details"], novo["zone"], novo["qty"], novo["value"], novo["flag"], novo["cat"]),
                         ("Poltrona de couro", "marrom", "Janela", "1", 250.5, None, "moveis"))
        self.assertNotEqual(novo["updatedAt"], novo["createdAt"])
        self.assertIn("valueAt", novo, "mudar o valor guarda quando mudou (para o GerencIA)")
        de_novo = self.store.update_item(it["id"], {"value": 250.5, "name": "Outro nome"}, None)
        self.assertEqual(de_novo["valueAt"], novo["valueAt"], "o mesmo valor não muda a data do valor")
        self.assertApiError(400, self.store.update_item, it["id"], {"name": ""}, None)
        self.assertApiError(404, self.store.update_item, "nao-existe", {"name": "x"}, None)

    def test_conflito_entre_aparelhos(self):
        it = self.novo()
        base = it["updatedAt"]
        time.sleep(1.01)
        self.store.update_item(it["id"], {"name": "Mudou no celular", "_base": base}, None)
        e = self.assertApiError(409, self.store.update_item, it["id"], {"name": "Mudou no computador", "_base": base}, None)
        self.assertEqual(e.extra["item"]["name"], "Mudou no celular", "o erro traz a versão atual para comparar")
        self.store.update_item(it["id"], {"name": "Sem base passa"}, None)

    def test_mudar_de_comodo_ganha_numero_novo(self):
        it = self.novo()
        seq_quarto = self.store.next_seq("quarto")
        movido = self.store.update_item(it["id"], {"room": "quarto"}, None)
        self.assertEqual((movido["room"], movido["seq"]), ("quarto", seq_quarto))
        self.assertEqual(self.store.tag(movido), f"QUA-{seq_quarto:03d}")
        self.assertEqual(movido["id"], it["id"], "o id não muda (links e fotos continuam)")
        self.assertApiError(400, self.store.update_item, it["id"], {"room": "nao-existe"}, None)
        mesmo = self.store.update_item(it["id"], {"room": "quarto"}, None)
        self.assertEqual(mesmo["seq"], seq_quarto, "o mesmo cômodo não muda o número")

    def test_conferido(self):
        it = self.novo()
        it = self.store.update_item(it["id"], {"checked": True}, None)
        self.assertTrue(it["checked"])
        quando = it["checkedAt"]
        it = self.store.update_item(it["id"], {"checked": True}, None)
        self.assertEqual(it["checkedAt"], quando)
        it = self.store.update_item(it["id"], {"checked": False}, None)
        self.assertNotIn("checkedAt", it)

    def test_fotos_e_origem_da_internet(self):
        it = self.novo(photos=["sala-1.jpg", "sala-2.jpg"], photoSrc={"sala-2.jpg": "https://loja.exemplo/p", "outra.jpg": "https://x"})
        self.assertEqual(it["photoSrc"], {"sala-2.jpg": "https://loja.exemplo/p"})
        it = self.store.update_item(it["id"], {"photos": ["sala-1.jpg"]}, None)
        self.assertNotIn("photoSrc", it, "sem a foto da internet, sai a origem")
        it = self.store.update_item(it["id"], {"photos": ["sala-1.jpg", "sala-3.jpg"], "photoSrc": {"sala-3.jpg": "https://loja.exemplo/q"}}, None)
        self.assertEqual(it["photoSrc"], {"sala-3.jpg": "https://loja.exemplo/q"})
        it = self.store.update_item(it["id"], {"name": "Só o nome"}, None)
        self.assertEqual(it["photoSrc"], {"sala-3.jpg": "https://loja.exemplo/q"}, "editar outro campo mantém a origem")
        self.assertApiError(400, self.store.update_item, it["id"], {"photos": ["sumiu.jpg"]}, None)

    def test_excluir(self):
        it = self.novo()
        self.assertEqual(self.store.delete_item(it["id"])["id"], it["id"])
        self.assertIsNone(self.item(it["id"]))
        self.assertApiError(404, self.store.delete_item, it["id"])

    def test_ordem_dos_itens(self):
        tags = [self.store.tag(i) for i in self.store.sorted_items()]
        self.assertEqual(tags[0][:3], "SAL", "segue a ordem dos cômodos")
        sala = [i["seq"] for i in self.store.sorted_items() if i["room"] == "sala"]
        self.assertEqual(sala, sorted(sala))

    def test_cada_gravacao_aumenta_a_revisao(self):
        r = self.store.data["rev"]
        it = self.novo()
        self.store.update_item(it["id"], {"name": "B"}, None)
        self.store.delete_item(it["id"])
        self.assertEqual(self.store.data["rev"], r + 3)
        self.assertEqual(S.read_json(S.DATA_FILE)["rev"], r + 3)


class Comodos(UnitBase):
    def test_criar(self):
        r = self.store.create_room({"name": "Garagem"})
        self.assertEqual((r["id"], r["code"], r["photos"], r["cover"]), ("garagem", "GARA", [], 0))
        self.assertEqual(self.store.data["rooms"][-1]["id"], "garagem", "novos cômodos vão para o fim")
        self.assertEqual([x["order"] for x in self.store.data["rooms"]], list(range(7)))
        r2 = self.store.create_room({"name": "Garagem", "code": "gar"})
        self.assertEqual((r2["id"], r2["code"]), ("garagem-2", "GAR"))
        r3 = self.store.create_room({"name": "Garagem dos fundos", "code": "GAR"})
        self.assertEqual(r3["code"], "GAR2", "código repetido ganha um número")
        self.assertEqual(self.store.create_room({"name": "Área de serviço", "code": "ÁRE"})["code"], "ARE")
        self.assertEqual(self.store.create_room({"name": "???"})["code"], "CMD")
        self.assertApiError(400, self.store.create_room, {"name": ""})
        self.assertApiError(400, self.store.create_room, {"name": "x" * 61})

    def test_novo_comodo_fica_antes_de_geral(self):
        self.store.create_room({"name": "Geral"})
        self.store.create_room({"name": "Sótão"})
        ids = [r["id"] for r in self.store.data["rooms"]]
        self.assertEqual(ids[-2:], ["sotao", "geral"])

    def test_editar_nome_codigo_fotos_e_capa(self):
        r = self.store.update_room("sala", {"name": "Sala", "code": "sl-1", "cover": 2})
        self.assertEqual((r["name"], r["code"], r["cover"]), ("Sala", "SL1", 2))
        self.assertEqual(self.store.tag(self.items_in("sala")[0])[:3], "SL1", "o código dos itens acompanha")
        self.assertApiError(400, self.store.update_room, "sala", {"code": "COZ"}, msg_part="já é usado")
        self.assertApiError(400, self.store.update_room, "sala", {"code": "--"})
        r = self.store.update_room("sala", {"photos": [{"file": "sala-1.jpg", "label": "Sofá"}]})
        self.assertEqual((r["photos"], r["cover"]), ([{"file": "sala-1.jpg", "label": "Sofá"}], 0), "a capa volta para a primeira se sumiu")
        self.assertApiError(400, self.store.update_room, "sala", {"photos": [{"file": "sumiu.jpg"}]})
        self.assertApiError(400, self.store.update_room, "sala", {"photos": ["sala-1.jpg"]})
        r = self.store.update_room("sala", {"cover": 5})
        self.assertEqual(r["cover"], 0)
        self.assertApiError(404, self.store.update_room, "nao-existe", {"name": "x"})

    def test_foto_do_comodo(self):
        r = self.store.add_room_photo("quarto", {"file": "sala-3.jpg", "label": "Cama"})
        self.assertIn({"file": "sala-3.jpg", "label": "Cama"}, r["photos"])
        n = len(r["photos"])
        self.assertEqual(len(self.store.add_room_photo("quarto", {"file": "sala-3.jpg"})["photos"]), n)
        self.assertApiError(400, self.store.add_room_photo, "quarto", {"file": "sumiu.jpg"})
        self.assertApiError(404, self.store.add_room_photo, "nao-existe", {"file": "sala-3.jpg"})

    def test_reordenar(self):
        ids = [r["id"] for r in self.store.data["rooms"]]
        self.store.reorder_rooms(list(reversed(ids)))
        self.assertEqual([r["id"] for r in self.store.data["rooms"]], list(reversed(ids)))
        self.store.reorder_rooms(["cozinha"])
        self.assertEqual(self.store.data["rooms"][0]["id"], "cozinha", "os que não vieram ficam depois, na ordem que estavam")
        self.assertEqual([r["order"] for r in self.store.data["rooms"]], list(range(6)))

    def test_excluir_so_vazio(self):
        self.assertApiError(400, self.store.delete_room, "sala", msg_part="Mova ou apague")
        r = self.store.create_room({"name": "Vazio"})
        self.store.delete_room(r["id"])
        self.assertIsNone(self.store.room(r["id"]))
        self.assertApiError(404, self.store.delete_room, r["id"])


if __name__ == "__main__":
    unittest.main()
