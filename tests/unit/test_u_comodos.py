"""Cômodos no servidor: criar (nome, id, código sugerido ou informado, código único), editar (nome, código, fotos com
legenda, capa e ordem das fotos), foto do cômodo, ordem dos cômodos, excluir, os códigos dos itens quando o código do
cômodo muda e o que check_inventory confere e completa num inventário importado.

Complementa test_itens_comodos.py (Comodos), sem repetir o que ele já confere.
"""
import copy
import csv
import io
import os
import unittest

from _boot import UnitBase, helpers, server as S


def ids(store):
    return [r["id"] for r in store.data["rooms"]]


def linhas_csv():
    return list(csv.reader(io.StringIO(S.export_csv_bytes().decode("utf-8-sig")), delimiter=";"))


class CriarComodo(UnitBase):
    def test_nome_sem_espacos_nas_pontas(self):
        r = self.store.create_room({"name": "   Garagem  "})
        self.assertEqual((r["name"], r["id"]), ("Garagem", "garagem"))

    def test_nome_com_60_caracteres_entra_e_id_fica_com_40(self):
        nome = "Depósito " + "x" * 51
        self.assertEqual(len(nome), 60)
        r = self.store.create_room({"name": nome})
        self.assertEqual(r["name"], nome)
        self.assertEqual(len(r["id"]), 40, "o id é cortado em 40 caracteres")
        self.assertTrue(r["id"].startswith("deposito-"), "o id não tem acento")

    def test_nome_que_daria_o_id_de_outro_comodo_ganha_numero(self):
        r = self.store.create_room({"name": "Sala"})
        self.assertEqual((r["id"], r["code"]), ("sala-2", "SALA"))
        self.assertEqual(self.store.room("sala")["name"], "Sala de estar", "o cômodo que já existia não muda")

    def test_terceiro_com_o_mesmo_nome_ganha_3(self):
        rs = [self.store.create_room({"name": "Garagem"}) for _ in range(3)]
        self.assertEqual([r["id"] for r in rs], ["garagem", "garagem-2", "garagem-3"])
        self.assertEqual([r["code"] for r in rs], ["GARA", "GAR2", "GAR3"])

    def test_codigo_sugerido_pelo_nome_sem_acento(self):
        self.assertEqual(self.store.create_room({"name": "Área gourmet"})["code"], "AREA")

    def test_codigo_so_com_espacos_usa_o_nome(self):
        self.assertEqual(self.store.create_room({"name": "Garagem", "code": "   "})["code"], "GARA")

    def test_codigo_com_mais_de_4_caracteres_recusado(self):
        self.assertApiError(400, self.store.create_room, {"name": "Garagem", "code": "GARAG"}, msg_part="4 caracteres")
        self.assertEqual(len(self.store.data["rooms"]), 6, "nada é criado")

    def test_id_fotos_capa_e_ordem_do_pedido_sao_ignorados(self):
        r = self.store.create_room({"name": "Garagem", "id": "../fora", "photos": [{"file": "sala-1.jpg", "label": "x"}], "cover": 2, "order": -5})
        self.assertEqual((r["id"], r["photos"], r["cover"], r["order"]), ("garagem", [], 0, 6))

    def test_novo_comodo_fica_gravado_no_arquivo(self):
        rev = self.store.data["rev"]
        r = self.store.create_room({"name": "Garagem"})
        disco = S.read_json(S.DATA_FILE)
        self.assertEqual(disco["rooms"][-1], r)
        self.assertEqual(disco["rev"], rev + 1)

    def test_codigo_sugerido_nunca_passa_de_4(self):
        codigos = [self.store.create_room({"name": f"Quarto {n}", "code": "QUA"})["code"] for n in range(2, 12)]
        self.assertTrue(all(1 <= len(c) <= 4 for c in codigos), codigos)
        self.assertEqual(len(set(codigos + ["QUA"])), 11, "todos diferentes")


class CodigoUnico(UnitBase):
    def test_numero_pula_os_codigos_ja_usados(self):
        self.store.update_room("cozinha", {"code": "SAL2"})
        self.assertEqual(self.store._unique_code("SAL"), "SAL3")

    def test_ignora_o_codigo_do_proprio_comodo(self):
        self.assertEqual(self.store._unique_code("SAL", skip_id="sala"), "SAL")
        self.assertEqual(self.store._unique_code("SAL"), "SAL2")

    def test_sem_letras_nem_numeros_vira_cmd_e_depois_cmd2(self):
        self.assertEqual(self.store.create_room({"name": "???"})["code"], "CMD")
        self.assertEqual(self.store._unique_code("—★—"), "CMD2")


class EditarComodo(UnitBase):
    def test_renomear_nao_muda_id_codigo_nem_fotos(self):
        fotos = copy.deepcopy(self.store.room("sala")["photos"])
        r = self.store.update_room("sala", {"name": "  Sala de TV "})
        self.assertEqual((r["id"], r["name"], r["code"], r["photos"]), ("sala", "Sala de TV", "SAL", fotos))

    def test_nome_vazio_ou_longo_recusado(self):
        for nome in ("", "   ", "x" * 61, None):
            with self.subTest(nome=nome):
                self.assertApiError(400, self.store.update_room, "sala", {"name": nome})
                self.assertEqual(self.store.room("sala")["name"], "Sala de estar")

    def test_codigo_com_mais_de_4_e_cortado(self):
        self.assertEqual(self.store.update_room("sala", {"code": "abcdef"})["code"], "ABCD")

    def test_o_proprio_codigo_em_minusculas_passa(self):
        r = self.store.update_room("sala", {"code": "sal"})
        self.assertEqual(r["code"], "SAL")
        self.assertEqual(self.store.tag(self.items_in("sala")[0]), "SAL-001")

    def test_codigo_liberado_pode_ser_usado_por_outro(self):
        self.store.update_room("cozinha", {"code": "CZ"})
        self.assertEqual(self.store.update_room("sala", {"code": "COZ"})["code"], "COZ")

    def test_codigo_com_acento_igual_ao_criar(self):
        self.assertEqual(self.store.update_room("lavanderia", {"code": "ÁRE"})["code"], "ARE")

    def test_pedido_recusado_nao_muda_nada(self):
        for body in ({"name": "Sala grande", "code": "COZ"}, {"name": "Sala grande", "code": "XYZ", "photos": [{"file": "sumiu.jpg"}]}):
            with self.subTest(body=body):
                antes = copy.deepcopy(self.store.room("sala"))
                self.assertApiError(400, self.store.update_room, "sala", body)
                self.assertEqual(self.store.room("sala"), antes, "nada vale pela metade")
                self.store.save()
                self.assertEqual(S.read_json(S.DATA_FILE)["rooms"][0]["name"], "Sala de estar", "nem na gravação seguinte")

    def test_pedido_vazio_so_muda_a_data(self):
        antes = copy.deepcopy(self.store.room("sala"))
        rev = self.store.data["rev"]
        r = self.store.update_room("sala", {})
        self.assertEqual({k: r[k] for k in ("name", "code", "photos", "cover")}, {k: antes[k] for k in ("name", "code", "photos", "cover")})
        self.assertNotEqual(r["updatedAt"], antes["updatedAt"])
        self.assertEqual(self.store.data["rev"], rev + 1)


class FotosAoEditar(UnitBase):
    def test_legenda_sem_espacos_e_com_limite_de_160(self):
        r = self.store.update_room("sala", {"photos": [{"file": "sala-1.jpg", "label": "  Sofá  "}, {"file": "sala-2.jpg", "label": "x" * 160}]})
        self.assertEqual([p["label"] for p in r["photos"]], ["Sofá", "x" * 160])
        self.assertApiError(400, self.store.update_room, "sala", {"photos": [{"file": "sala-1.jpg", "label": "x" * 161}]}, msg_part="160")

    def test_mudar_a_ordem_das_fotos(self):
        fotos = self.store.room("sala")["photos"]
        r = self.store.update_room("sala", {"photos": list(reversed(fotos))})
        self.assertEqual([p["file"] for p in r["photos"]], ["sala-3.jpg", "sala-2.jpg", "sala-1.jpg"])
        self.assertEqual(r["photos"][0]["label"], "Estante de livros", "a legenda vai junto com a foto")

    def test_capa_conferida_com_as_fotos_novas(self):
        r = self.store.update_room("sala", {"photos": [{"file": "sala-2.jpg"}, {"file": "sala-3.jpg"}], "cover": 1})
        self.assertEqual(r["cover"], 1)
        r = self.store.update_room("sala", {"photos": [{"file": "sala-3.jpg"}], "cover": 1})
        self.assertEqual(r["cover"], 0, "a capa pedida não existe na lista nova")

    def test_capa_continua_se_a_foto_ainda_existe(self):
        self.store.update_room("sala", {"cover": 1})
        fotos = self.store.room("sala")["photos"][:2]
        self.assertEqual(self.store.update_room("sala", {"photos": fotos})["cover"], 1)

    def test_capa_invalida_vira_zero(self):
        for capa in ("1", -1, 1.5, None):
            with self.subTest(capa=capa):
                self.store.update_room("sala", {"cover": 2})
                self.assertEqual(self.store.update_room("sala", {"cover": capa})["cover"], 0)

    def test_fotos_nulas_ou_vazias_tiram_todas(self):
        for vazio in (None, []):
            with self.subTest(vazio=vazio):
                self.store.update_room("sala", {"photos": [{"file": "sala-1.jpg"}, {"file": "sala-2.jpg"}], "cover": 1})
                r = self.store.update_room("sala", {"photos": vazio})
                self.assertEqual((r["photos"], r["cover"]), ([], 0))

    def test_so_guarda_arquivo_e_legenda(self):
        r = self.store.update_room("sala", {"photos": [{"file": "sala-1.jpg", "extra": "x", "label": None}]})
        self.assertEqual(r["photos"], [{"file": "sala-1.jpg", "label": ""}])

    def test_caminho_perigoso_na_foto_recusado(self):
        for nome in ("../photos/sala-1.jpg", "photos/sala-1.jpg", "/etc/passwd", "../inventario.json"):
            with self.subTest(nome=nome):
                self.assertApiError(400, self.store.update_room, "sala", {"photos": [{"file": nome}]})
                self.assertEqual(len(self.store.room("sala")["photos"]), 3, "as fotos do cômodo não mudam")

    def test_lista_de_fotos_que_nao_e_lista_recusada(self):
        for fotos in ({"file": "sala-1.jpg"}, "sala-1.jpg"):
            with self.subTest(fotos=fotos):
                self.assertApiError(400, self.store.update_room, "sala", {"photos": fotos})

    def test_fotos_que_saem_do_comodo_continuam_no_disco(self):
        self.store.update_room("sala", {"photos": []})
        for nome in ("sala-1.jpg", "sala-2.jpg", "sala-3.jpg"):
            self.assertTrue(S.photo_exists(nome), "os itens continuam usando a foto")
        self.assertEqual(self.item("sal-001")["photos"], ["sala-1.jpg"])


class FotoDoComodo(UnitBase):
    def test_interna_ignora_comodo_ou_foto_que_nao_existe(self):
        antes = copy.deepcopy(self.store.data["rooms"])
        self.store._add_room_photo("nao-existe", "sala-1.jpg", "x")
        self.store._add_room_photo("quarto", "sumiu.jpg", "x")
        self.store._add_room_photo("quarto", None, "x")
        self.store._add_room_photo("quarto", "../photos/sala-1.jpg", "x")
        self.assertEqual(self.store.data["rooms"], antes, "sem erro e sem mudança")

    def test_interna_sem_legenda_fica_vazia(self):
        self.store._add_room_photo("quarto", "sala-1.jpg", None)
        self.assertEqual(self.store.room("quarto")["photos"][-1], {"file": "sala-1.jpg", "label": ""})

    def test_interna_muda_a_data_so_quando_a_foto_entra(self):
        quarto = self.store.room("quarto")
        antes = quarto["updatedAt"]
        self.store._add_room_photo("quarto", "sala-1.jpg", "Cama")
        self.assertNotEqual(quarto["updatedAt"], antes)
        quarto["updatedAt"] = "marca"
        self.store._add_room_photo("quarto", "sala-1.jpg", "De novo")
        self.assertEqual(quarto["updatedAt"], "marca", "a foto repetida não conta como mudança")

    def test_adicionar_vai_para_o_fim_grava_e_mantem_a_capa(self):
        self.store.update_room("sala", {"cover": 1})
        rev = self.store.data["rev"]
        r = self.store.add_room_photo("sala", {"file": "quarto-1.jpg", "label": "  Vista da porta "})
        self.assertEqual(r["photos"][-1], {"file": "quarto-1.jpg", "label": "Vista da porta"})
        self.assertEqual((len(r["photos"]), r["cover"]), (4, 1))
        self.assertEqual(self.store.data["rev"], rev + 1)
        self.assertEqual(S.read_json(S.DATA_FILE)["rooms"][0]["photos"][-1]["file"], "quarto-1.jpg")

    def test_pedido_sem_arquivo_recusado(self):
        for body in ({}, {"file": None}, {"file": ""}, {"file": "../photos/sala-1.jpg"}):
            with self.subTest(body=body):
                self.assertApiError(400, self.store.add_room_photo, "quarto", body, msg_part="não foi encontrada")

    def test_legenda_longa_recusada_sem_mudar_as_fotos(self):
        self.assertApiError(400, self.store.add_room_photo, "quarto", {"file": "sala-1.jpg", "label": "x" * 161})
        self.assertEqual([p["file"] for p in self.store.room("quarto")["photos"]], ["quarto-1.jpg"])


class OrdemDosComodos(UnitBase):
    def test_ids_desconhecidos_sao_ignorados(self):
        self.store.reorder_rooms(["fantasma", "varanda", "../x"])
        self.assertEqual(ids(self.store), ["varanda", "sala", "cozinha", "quarto", "escritorio", "lavanderia"])

    def test_ids_repetidos_nao_duplicam_comodos(self):
        self.store.reorder_rooms(["varanda", "varanda", "cozinha", "varanda"])
        self.assertEqual(sorted(ids(self.store)), sorted(["sala", "cozinha", "quarto", "escritorio", "lavanderia", "varanda"]), "cada cômodo uma vez só")
        self.assertEqual([r["order"] for r in self.store.data["rooms"]], list(range(6)))
        self.assertEqual([r["id"] for r in S.read_json(S.DATA_FILE)["rooms"]], ids(self.store))

    def test_lista_vazia_ou_nula_mantem_a_ordem(self):
        antes = ids(self.store)
        for vazio in ([], None):
            with self.subTest(vazio=vazio):
                self.store.reorder_rooms(vazio)
                self.assertEqual(ids(self.store), antes)

    def test_nova_ordem_fica_gravada_e_volta_na_resposta(self):
        rev = self.store.data["rev"]
        nova = ["lavanderia", "sala", "varanda", "cozinha", "quarto", "escritorio"]
        out = self.store.reorder_rooms(nova)
        self.assertEqual([r["id"] for r in out], nova)
        disco = S.read_json(S.DATA_FILE)
        self.assertEqual([r["id"] for r in disco["rooms"]], nova)
        self.assertEqual([r["order"] for r in disco["rooms"]], list(range(6)))
        self.assertEqual(disco["rev"], rev + 1)

    def test_itens_e_planilha_seguem_a_nova_ordem(self):
        self.store.reorder_rooms(["varanda"])
        self.assertEqual(self.store.tag(self.store.sorted_items()[0]), "VAR-001")
        self.assertEqual(linhas_csv()[1][0], "VAR-001", "a planilha (e o relatório) começa pelo primeiro cômodo")

    def test_ordem_quebrada_vira_sequencia(self):
        quebrada = {"sala": 5, "cozinha": 2.5, "escritorio": 2.5, "lavanderia": 10, "varanda": 1}
        for r in self.store.data["rooms"]:
            if r["id"] in quebrada:
                r["order"] = quebrada[r["id"]]
            else:
                r.pop("order")  # quarto sem ordem conta como 0
        self.store._normalize_order()
        self.assertEqual(ids(self.store), ["quarto", "varanda", "cozinha", "escritorio", "sala", "lavanderia"], "empate fica na ordem em que estava")
        self.assertEqual([r["order"] for r in self.store.data["rooms"]], list(range(6)))


class ExcluirComodo(UnitBase):
    def test_excluir_renumera_a_ordem(self):
        self.store.create_room({"name": "A"})
        self.store.create_room({"name": "B"})
        self.store.delete_room("a")
        self.assertEqual([r["order"] for r in self.store.data["rooms"]], list(range(7)))
        self.assertEqual(self.store.room("b")["order"], 6)

    def test_excluir_grava_e_devolve_o_comodo(self):
        r = self.store.create_room({"name": "Garagem"})
        rev = self.store.data["rev"]
        self.assertEqual(self.store.delete_room("garagem"), r)
        disco = S.read_json(S.DATA_FILE)
        self.assertNotIn("garagem", [x["id"] for x in disco["rooms"]])
        self.assertEqual(disco["rev"], rev + 1)

    def test_fotos_do_comodo_excluido_continuam(self):
        self.store.create_room({"name": "Garagem"})
        self.store.add_room_photo("garagem", {"file": "sala-1.jpg"})
        self.store.delete_room("garagem")
        self.assertTrue(S.photo_exists("sala-1.jpg"))
        self.assertTrue(os.path.isfile(os.path.join(S.THUMBS_DIR, "sala-1.jpg")))
        self.assertIn("sala-1.jpg", [p["file"] for p in self.store.room("sala")["photos"]])

    def test_depois_de_mover_os_itens_pode_excluir(self):
        movidos = [i["id"] for i in self.items_in("varanda")]
        for iid in movidos:
            self.store.update_item(iid, {"room": "sala"}, None)
        self.store.delete_room("varanda")
        self.assertIsNone(self.store.room("varanda"))
        self.assertTrue(all(self.item(iid)["room"] == "sala" for iid in movidos))


class CodigosDosItens(UnitBase):
    def test_todos_os_itens_do_comodo_mudam_de_codigo(self):
        self.store.update_room("cozinha", {"code": "CZ"})
        tags = sorted(self.store.tag(i) for i in self.items_in("cozinha"))
        self.assertEqual(tags, [f"CZ-{n:03d}" for n in range(1, 8)], "o número de cada item continua o mesmo")

    def test_ids_dos_itens_nao_mudam(self):
        antes = sorted(i["id"] for i in self.items_in("cozinha"))
        self.store.update_room("cozinha", {"code": "CZ"})
        self.assertEqual(sorted(i["id"] for i in self.items_in("cozinha")), antes, "links e fotos dos itens continuam")

    def test_item_novo_usa_o_codigo_novo_e_continua_o_numero(self):
        self.store.update_room("cozinha", {"code": "CZ"})
        it = self.store.create_items([{"room": "cozinha", "name": "Torradeira"}], None)[0]
        self.assertEqual((it["id"], it["seq"], self.store.tag(it)), ("cz-008", 8, "CZ-008"))

    def test_itens_de_outros_comodos_nao_mudam(self):
        outros = {i["id"]: self.store.tag(i) for i in self.store.data["items"] if i["room"] != "cozinha"}
        self.store.update_room("cozinha", {"code": "CZ"})
        self.assertEqual({iid: self.store.tag(self.item(iid)) for iid in outros}, outros)

    def test_codigo_novo_vai_para_a_planilha(self):
        self.store.update_room("cozinha", {"code": "CZ"})
        cozinha = [r[0] for r in linhas_csv()[1:] if r[1] == "Cozinha"]
        self.assertEqual(len(cozinha), 7)
        self.assertTrue(all(c.startswith("CZ-") for c in cozinha), cozinha)


class ConferirInventario(UnitBase):
    def conferir(self, rooms, items=()):
        return S.Store.check_inventory({"rooms": list(rooms), "items": list(items)})

    def test_comodo_sem_codigo_ganha_o_comeco_do_id(self):
        d = self.conferir([{"id": "garagem", "name": "Garagem"}, {"id": "sala", "name": "Sala", "code": "XY"}])
        self.assertEqual([r["code"] for r in d["rooms"]], ["GAR", "XY"], "o código que veio no arquivo fica")

    def test_comodo_sem_fotos_e_capa_ganha_o_padrao(self):
        r = self.conferir([{"id": "garagem", "name": "Garagem"}])["rooms"][0]
        self.assertEqual((r["photos"], r["cover"]), ([], 0))

    def test_fotos_do_comodo_em_texto_viram_objetos(self):
        r = self.conferir([{"id": "g", "name": "G", "photos": ["a.jpg", {"file": "b.jpg", "label": "B"}]}])["rooms"][0]
        self.assertEqual(r["photos"], [{"file": "a.jpg", "label": ""}, {"file": "b.jpg", "label": "B"}])

    def test_comodo_sem_nome_ou_que_nao_e_objeto_recusado(self):
        for room in ({"id": "a"}, {"id": "a", "name": ""}, "sala", None):
            with self.subTest(room=room):
                self.assertApiError(400, self.conferir, [room], msg_part="cômodo sem id ou nome")

    def test_item_sem_id_ou_que_nao_e_objeto_recusado(self):
        for item in ({"room": "g"}, {"id": "", "room": "g"}, "texto", None):
            with self.subTest(item=item):
                self.assertApiError(400, self.conferir, [{"id": "g", "name": "G"}], [item], msg_part="item sem id")

    def test_item_com_photo_e_photos_fica_com_photos(self):
        it = self.conferir([{"id": "g", "name": "G"}], [{"id": "i", "room": "g", "photo": "a.jpg", "photos": ["b.jpg"]}])["items"][0]
        self.assertEqual(it["photos"], ["b.jpg"])
        self.assertNotIn("photo", it)

    def test_foto_que_nao_existe_continua_no_item(self):
        it = self.conferir([{"id": "g", "name": "G"}], [{"id": "i", "room": "g", "photos": ["vem-depois.jpg"]}])["items"][0]
        self.assertEqual(it["photos"], ["vem-depois.jpg"], "a foto pode chegar depois, numa parte só de fotos do backup")

    def test_categoria_desconhecida_nao_recusa_e_sai_como_outros_na_planilha(self):
        d = self.conferir([{"id": "g", "name": "Garagem", "code": "GAR"}], [{"id": "i", "room": "g", "name": "Serrote", "cat": "ferramentas-velhas"}])
        self.assertEqual(d["items"][0]["cat"], "ferramentas-velhas", "o arquivo é aceito como veio")
        self.store.replace_all(d)
        self.assertEqual(linhas_csv()[1][5], "Outros")

    def test_item_minimo_entra_e_nao_quebra_a_planilha(self):
        d = self.conferir([{"id": "r", "name": "Depósito"}], [{"id": "i1", "room": "r"}])
        self.assertEqual(d["items"][0]["photos"], [])
        self.store.replace_all(d)
        linha = linhas_csv()[1]
        self.assertEqual((linha[0], linha[1], linha[3], linha[7]), ("R-000", "Depósito", "", "0,00"))

    def test_codigos_gerados_nao_se_repetem(self):
        d = self.conferir([{"id": "quarto", "name": "Quarto"}, {"id": "quarto-2", "name": "Quarto de hóspedes"}])
        codigos = [r["code"] for r in d["rooms"]]
        self.assertEqual(len(set(codigos)), 2, codigos)


if __name__ == "__main__":
    unittest.main()
