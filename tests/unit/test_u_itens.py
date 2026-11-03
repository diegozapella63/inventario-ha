"""Itens no servidor, um comportamento por teste: build_item campo a campo (nome, detalhes, cômodo, zona, categoria,
quantidade, valor, fotos e de onde vieram, quem cadastrou, restaurar), create_items (lote, desfazer o lote, foto do
cômodo), update_item (cada campo, mover de cômodo, conflito, data do valor, fotos), delete_item, next_seq, tag,
sorted_items e item(). Complementa test_itens_comodos.py sem repetir os casos de lá."""
import re
import unittest

from _boot import UnitBase, server as S

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")
LOJA = "https://loja.exemplo/produto"


class Base(UnitBase):
    def novo(self, user=None, **kw):
        return self.store.create_items([{"room": "sala", "name": "Poltrona", **kw}], user)[0]

    def build(self, user=None, restore=False, **kw):
        return self.store.build_item({"room": "sala", "name": "Poltrona", **kw}, user, restore=restore)


class MontarItem(Base):
    def test_montar_nao_poe_na_lista_nem_grava(self):
        n, rev = len(self.store.data["items"]), self.store.data["rev"]
        self.build()
        self.assertEqual((len(self.store.data["items"]), self.store.data["rev"]), (n, rev))

    def test_nome_com_200_caracteres_passa(self):
        self.assertEqual(self.build(name="N" * 200)["name"], "N" * 200)

    def test_nome_aparado(self):
        self.assertEqual(self.build(name="  Poltrona azul  ")["name"], "Poltrona azul")

    def test_detalhes_mantem_as_quebras_de_linha(self):
        self.assertEqual(self.build(details="Couro marrom.\nPés de madeira.")["details"], "Couro marrom.\nPés de madeira.")

    def test_detalhes_acima_de_4000_recusados(self):
        self.assertApiError(400, self.build, details="d" * 4001, msg_part="detalhes")

    def test_zona_aparada(self):
        self.assertEqual(self.build(zone="  Estante ")["zone"], "Estante")

    def test_zona_acima_de_120_recusada(self):
        self.assertApiError(400, self.build, zone="z" * 121, msg_part="zona")

    def test_quantidade_so_com_espacos_vira_1(self):
        self.assertEqual(self.build(qty="   ")["qty"], "1")

    def test_quantidade_numero_vira_texto(self):
        self.assertEqual(self.build(qty=3)["qty"], "3")

    def test_quantidade_em_texto_livre(self):
        self.assertEqual(self.build(qty="1 par")["qty"], "1 par")

    def test_quantidade_acima_de_30_recusada(self):
        self.assertApiError(400, self.build, qty="9" * 31, msg_part="quantidade")

    def test_valor_em_formato_brasileiro(self):
        self.assertEqual(self.build(value="R$ 2.300,90")["value"], 2300.9)

    def test_criar_grava_a_data_do_valor_igual_a_de_criacao(self):
        it = self.build(value=100)
        self.assertEqual(it["valueAt"], it["createdAt"], "os outros apps (GerencIA) depreciam a partir daqui")

    def test_categoria_criada_pela_casa_aceita(self):
        self.store.create_cat({"name": "Oficina"})
        self.assertEqual(self.build(cat="oficina")["cat"], "oficina")

    def test_categoria_com_maiusculas_vai_para_outros(self):
        self.assertEqual(self.build(cat="MOVEIS")["cat"], "outros", "o id da categoria é exato")

    def test_foto_que_nao_existe_recusa_o_item(self):
        self.assertApiError(400, self.build, photos=["sumiu.jpg"], msg_part="foto")

    def test_fotos_na_ordem_enviada(self):
        self.assertEqual(self.build(photos=["sala-3.jpg", "sala-1.jpg"])["photos"], ["sala-3.jpg", "sala-1.jpg"])

    def test_sem_origem_das_fotos_nao_grava_photoSrc(self):
        self.assertNotIn("photoSrc", self.build(photos=["sala-1.jpg"], photoSrc={}))

    def test_origem_de_foto_que_o_item_nao_tem_e_descartada(self):
        self.assertNotIn("photoSrc", self.build(photos=["sala-1.jpg"], photoSrc={"sala-2.jpg": LOJA}))

    def test_observacao_so_com_espacos_vira_nula(self):
        self.assertIsNone(self.build(flag="   ")["flag"])

    def test_observacao_acima_de_200_recusada(self):
        self.assertApiError(400, self.build, flag="o" * 201, msg_part="observação")

    def test_origem_informada_fica(self):
        self.assertEqual(self.build(source="foto")["source"], "foto")

    def test_origem_acima_de_40_recusada(self):
        self.assertApiError(400, self.build, source="s" * 41, msg_part="origem")

    def test_conferido_vira_verdadeiro_ou_falso(self):
        self.assertIs(self.build(checked="sim")["checked"], True)

    def test_aproximado_sempre_verdadeiro_sem_restaurar(self):
        self.assertIs(self.build(approx=False)["approx"], True)

    def test_campos_desconhecidos_nao_entram(self):
        it = self.build(foo=1, valueAt="2020-01-01T00:00:00-03:00", updatedBy="Alguém", checkedAt="2020-01-01T00:00:00-03:00")
        for k in ("foo", "updatedBy", "checkedAt"):
            with self.subTest(campo=k):
                self.assertNotIn(k, it)
        self.assertNotEqual(it["valueAt"], "2020-01-01T00:00:00-03:00", "a data do valor que veio no pedido não vale (só ao restaurar)")

    def test_sem_restaurar_ignora_id_numero_e_criacao(self):
        it = self.build(id="sal-900", seq=900, createdAt="2020-01-01T00:00:00-03:00", createdBy="Alguém")
        self.assertEqual((it["id"], it["seq"]), ("sal-013", 13))
        self.assertNotEqual(it["createdAt"], "2020-01-01T00:00:00-03:00")
        self.assertNotIn("createdBy", it)

    def test_sem_usuario_nao_grava_quem_cadastrou(self):
        for user in (None, ""):
            with self.subTest(user=user):
                it = self.build(user=user)
                self.assertNotIn("createdBy", it)
                self.assertNotIn("updatedBy", it)

    def test_datas_de_criacao_com_fuso(self):
        self.assertRegex(self.build()["createdAt"], ISO)

    def test_id_usa_o_codigo_do_comodo_em_minusculas(self):
        r = self.store.create_room({"name": "Garagem"})
        it = self.store.build_item({"room": r["id"], "name": "Bicicleta"}, None)
        self.assertEqual((it["id"], it["seq"]), ("gara-001", 1))


class Restaurar(Base):
    def test_restaurar_mantem_aproximado_falso(self):
        self.assertIs(self.build(restore=True, approx=False)["approx"], False)

    def test_restaurar_mantem_quando_foi_conferido(self):
        it = self.build(restore=True, checked=True, checkedAt="2026-10-05T10:00:00-03:00")
        self.assertEqual((it["checked"], it["checkedAt"]), (True, "2026-10-05T10:00:00-03:00"))

    def test_restaurar_numero_em_texto_ganha_o_proximo(self):
        self.assertEqual(self.build(restore=True, seq="5")["seq"], 13)

    def test_restaurar_numero_zero_ganha_o_proximo(self):
        self.assertEqual(self.build(restore=True, seq=0)["seq"], 13)

    def test_restaurar_mantem_quem_cadastrou_e_marca_quem_restaurou(self):
        it = self.build(user="Bia", restore=True, createdBy="Ana")
        self.assertEqual((it["createdBy"], it["updatedBy"]), ("Ana", "Bia"))

    def test_restaurar_mantem_a_data_do_valor(self):
        it = self.build(restore=True, value=500, valueAt="2025-05-01T10:00:00-03:00")
        self.assertEqual(it.get("valueAt"), "2025-05-01T10:00:00-03:00")

    def test_excluir_e_desfazer_nao_muda_a_data_do_valor_para_os_outros_apps(self):
        antes = self._valor_em("sal-001")
        apagado = dict(self.store.delete_item("sal-001"))
        self.store.create_items([apagado], None, restore=True)
        self.assertEqual(self._valor_em("sal-001"), antes)

    def _valor_em(self, iid):
        class H:
            def send_json(self, obj, status=200):
                self.out = obj
        h = H()
        S.r_integracao_itens(h, {})
        return next(i["valor_em"] for i in h.out["itens"] if i["id"] == iid)


class CriarLote(Base):
    def test_lote_em_comodos_diferentes_numera_cada_um(self):
        its = self.store.create_items([{"room": "sala", "name": "A"}, {"room": "cozinha", "name": "B"}, {"room": "sala", "name": "C"}], None)
        self.assertEqual([self.store.tag(i) for i in its], ["SAL-013", "COZ-008", "SAL-014"])

    def test_lote_grava_uma_vez(self):
        rev = self.store.data["rev"]
        self.store.create_items([{"room": "sala", "name": n} for n in "ABC"], None)
        self.assertEqual(self.store.data["rev"], rev + 1)

    def test_lote_vazio_nao_cria_nada(self):
        self.assertEqual(self.store.create_items([], None), [])
        self.assertEqual(len(self.store.data["items"]), 38)

    def test_itens_devolvidos_sao_os_da_lista(self):
        it = self.novo()
        self.assertIs(self.store.item(it["id"]), it)

    def test_item_gravado_igual_ao_devolvido(self):
        it = self.novo(details="Couro", value="350", zone="Janela")
        self.assertEqual(next(i for i in S.read_json(S.DATA_FILE)["items"] if i["id"] == it["id"]), it)

    def test_lote_que_falha_nao_muda_a_revisao(self):
        rev = self.store.data["rev"]
        self.assertApiError(400, self.store.create_items, [{"room": "sala", "name": "A"}, {"room": "sala", "name": "B", "value": "caro"}], None)
        self.assertEqual((self.store.data["rev"], S.read_json(S.DATA_FILE)["rev"]), (rev, rev))

    def test_lote_que_falha_por_foto_desfaz_os_anteriores(self):
        self.assertApiError(400, self.store.create_items, [{"room": "sala", "name": "A"}, {"room": "sala", "name": "B", "photos": ["sumiu.jpg"]}], None)
        self.assertFalse(any(i["name"] == "A" for i in self.store.data["items"]))

    def test_lote_que_falha_nao_gasta_numero(self):
        self.assertApiError(400, self.store.create_items, [{"room": "sala", "name": "A"}, {"room": "sala", "name": ""}], None)
        self.assertEqual(self.store.tag(self.novo()), "SAL-013")

    def test_quem_cadastrou_vale_para_todo_o_lote(self):
        its = self.store.create_items([{"room": "sala", "name": "A"}, {"room": "quarto", "name": "B"}], "Ana")
        self.assertEqual([i["createdBy"] for i in its], ["Ana", "Ana"])

    def test_foto_do_comodo_que_nao_existe_e_ignorada(self):
        antes = list(self.store.room("cozinha")["photos"])
        its = self.store.create_items([{"room": "cozinha", "name": "A"}], None, room_photo={"room": "cozinha", "file": "sumiu.jpg"})
        self.assertEqual((len(its), self.store.room("cozinha")["photos"]), (1, antes))

    def test_foto_para_comodo_que_nao_existe_e_ignorada(self):
        its = self.store.create_items([{"room": "cozinha", "name": "A"}], None, room_photo={"room": "nao-existe", "file": "sala-2.jpg"})
        self.assertEqual(self.store.item(its[0]["id"])["name"], "A")

    def test_foto_do_comodo_sem_legenda_fica_vazia(self):
        self.store.create_items([{"room": "cozinha", "name": "A"}], None, room_photo={"room": "cozinha", "file": "sala-3.jpg"})
        self.assertIn({"file": "sala-3.jpg", "label": ""}, self.store.room("cozinha")["photos"])

    def test_legenda_longa_da_foto_do_comodo_nao_deixa_itens_na_memoria(self):
        self.assertApiError(400, self.store.create_items, [{"room": "cozinha", "name": "A"}], None,
                            room_photo={"room": "cozinha", "file": "sala-2.jpg", "label": "x" * 161})
        self.assertEqual(len(self.store.data["items"]), 38)

    def test_item_que_nao_e_objeto_recusa_o_lote_inteiro(self):
        self.assertApiError(400, self.store.create_items, [{"room": "sala", "name": "A"}, "texto"], None)
        self.assertEqual(len(self.store.data["items"]), 38)


class Editar(Base):
    def edit(self, iid="sal-001", user=None, **kw):
        return self.store.update_item(iid, kw, user)

    def test_zona_aparada(self):
        self.assertEqual(self.edit(zone=" Canto ")["zone"], "Canto")

    def test_detalhes_vazios_limpam(self):
        self.assertEqual(self.edit(details="")["details"], "")

    def test_categoria_desconhecida_vai_para_outros(self):
        self.assertEqual(self.edit(cat="nao-existe")["cat"], "outros")

    def test_quantidade_aparada(self):
        self.assertEqual(self.edit(qty=" 2 pares ")["qty"], "2 pares")

    def test_nome_acima_de_200_recusado(self):
        self.assertApiError(400, self.edit, name="n" * 201, msg_part="nome")

    def test_valor_invalido_nao_muda_os_outros_campos(self):
        antes = dict(self.item("sal-001"))
        self.assertApiError(400, self.edit, name="Outro nome", value="caro")
        self.assertEqual(self.item("sal-001"), antes)

    def test_erro_na_edicao_nao_muda_a_revisao(self):
        rev = self.store.data["rev"]
        self.assertApiError(400, self.edit, name="")
        self.assertEqual(self.store.data["rev"], rev)

    def test_mesmo_valor_escrito_em_texto_nao_marca_a_data_do_valor(self):
        self.assertNotIn("valueAt", self.edit(value="1.800"), "o sofá já vale 1800")

    def test_valor_novo_marca_a_data_do_valor(self):
        self.assertRegex(self.edit(value="2.000")["valueAt"], ISO)

    def test_valor_zerado_tambem_marca_a_data_do_valor(self):
        it = self.edit(value="")
        self.assertEqual(it["value"], 0)
        self.assertIn("valueAt", it)

    def test_mudar_outro_campo_nao_marca_a_data_do_valor(self):
        self.assertNotIn("valueAt", self.edit(name="Sofá novo", zone="Janela", qty="2"))

    def test_base_igual_a_atual_passa(self):
        base = self.item("sal-001")["updatedAt"]
        self.assertEqual(self.edit(name="Sofá retrátil", _base=base)["name"], "Sofá retrátil")

    def test_base_vazia_nao_confere(self):
        self.assertEqual(self.edit(name="Sofá retrátil", _base="")["name"], "Sofá retrátil")

    def test_conflito_nao_muda_o_item_nem_a_revisao(self):
        antes, rev = dict(self.item("sal-001")), self.store.data["rev"]
        self.assertApiError(409, self.edit, name="Outro", room="quarto", _base="2026-10-01T00:00:00-03:00")
        self.assertEqual((self.item("sal-001"), self.store.data["rev"]), (antes, rev))

    def test_corpo_vazio_so_muda_a_data_de_alteracao(self):
        antes = dict(self.item("sal-001"))
        depois = dict(self.edit())
        self.assertNotEqual(depois.pop("updatedAt"), antes.pop("updatedAt"))
        self.assertEqual(depois, antes)

    def test_sem_usuario_mantem_quem_editou_antes(self):
        self.edit(user="Ana", name="Sofá A")
        self.assertEqual(self.edit(name="Sofá B")["updatedBy"], "Ana")

    def test_id_numero_e_criacao_nao_mudam_pelo_corpo(self):
        it = self.edit(id="xyz", seq=99, createdAt="2000-01-01T00:00:00-03:00", createdBy="Alguém")
        self.assertEqual((it["id"], it["seq"], it["createdAt"]), ("sal-001", 1, "2026-10-02T02:00:00-03:00"))
        self.assertNotIn("createdBy", it)

    def test_campos_desconhecidos_ignorados(self):
        self.assertNotIn("foo", self.edit(foo=1))

    def test_devolve_o_mesmo_objeto_da_lista(self):
        self.assertIs(self.edit(name="Sofá"), self.item("sal-001"))

    def test_edicao_fica_no_arquivo(self):
        self.edit(name="Sofá de canto")
        self.assertEqual(next(i for i in S.read_json(S.DATA_FILE)["items"] if i["id"] == "sal-001")["name"], "Sofá de canto")

    def test_tirar_todas_as_fotos_tira_a_origem(self):
        self.edit(photos=["sala-1.jpg"], photoSrc={"sala-1.jpg": LOJA})
        it = self.edit(photos=[])
        self.assertEqual(it["photos"], [])
        self.assertNotIn("photoSrc", it)

    def test_so_a_origem_vale_para_as_fotos_atuais(self):
        it = self.edit(photoSrc={"sala-1.jpg": LOJA, "sala-2.jpg": LOJA})
        self.assertEqual(it["photoSrc"], {"sala-1.jpg": LOJA}, "o sofá só tem a sala-1.jpg")

    def test_origem_vazia_tira_a_origem(self):
        self.edit(photoSrc={"sala-1.jpg": LOJA})
        self.assertNotIn("photoSrc", self.edit(photoSrc={}))


class Mover(Base):
    def test_mover_nao_renumera_os_que_ficaram(self):
        self.store.update_item("sal-005", {"room": "quarto"}, None)
        self.assertEqual(self.store.tag(self.item("sal-006")), "SAL-006")

    def test_mover_e_voltar_ganha_numero_novo(self):
        self.store.update_item("sal-001", {"room": "quarto"}, None)
        it = self.store.update_item("sal-001", {"room": "sala"}, None)
        self.assertEqual(self.store.tag(it), "SAL-013")

    def test_mover_para_comodo_vazio_vira_001(self):
        r = self.store.create_room({"name": "Garagem"})
        it = self.store.update_item("var-002", {"room": r["id"]}, None)
        self.assertEqual(self.store.tag(it), "GARA-001")


class Excluir(Base):
    def test_excluir_tira_do_arquivo(self):
        self.store.delete_item("coz-003")
        self.assertNotIn("coz-003", [i["id"] for i in S.read_json(S.DATA_FILE)["items"]])

    def test_excluir_nao_mexe_nos_outros(self):
        antes = [dict(i) for i in self.store.data["items"] if i["id"] != "sal-005"]
        self.store.delete_item("sal-005")
        self.assertEqual(self.store.data["items"], antes)

    def test_numero_do_meio_excluido_nao_e_reaproveitado(self):
        self.store.delete_item("sal-005")
        self.assertEqual(self.store.next_seq("sala"), 13)


class Numeros(Base):
    def test_proximo_numero_de_cada_comodo(self):
        self.assertEqual((self.store.next_seq("sala"), self.store.next_seq("varanda")), (13, 4))

    def test_proximo_numero_de_comodo_vazio_e_1(self):
        self.assertEqual(self.store.next_seq("nao-existe"), 1)

    def test_item_sem_numero_conta_como_zero(self):
        r = self.store.create_room({"name": "Sótão"})
        self.store.data["items"].append({"id": "x", "room": r["id"], "seq": None, "name": "x"})
        self.assertEqual(self.store.next_seq(r["id"]), 1)

    def test_codigo_com_tres_digitos(self):
        self.assertEqual(self.store.tag({"room": "sala", "seq": 7}), "SAL-007")

    def test_codigo_acima_de_999(self):
        self.assertEqual(self.store.tag({"room": "sala", "seq": 1234}), "SAL-1234")

    def test_codigo_de_item_sem_comodo(self):
        self.assertEqual(self.store.tag({"room": "sumiu", "seq": 1}), "ITM-001")

    def test_codigo_sem_numero(self):
        self.assertEqual(self.store.tag({"room": "cozinha", "seq": None}), "COZ-000")


class Ordem(Base):
    def test_segue_a_nova_ordem_dos_comodos(self):
        ids = [r["id"] for r in self.store.data["rooms"]]
        self.store.reorder_rooms(["varanda"] + [i for i in ids if i != "varanda"])
        self.assertEqual([i["id"] for i in self.store.sorted_items()[:3]], ["var-001", "var-002", "var-003"])

    def test_item_de_comodo_desconhecido_vai_para_o_fim(self):
        self.store.data["items"].insert(0, {"id": "perdido", "room": "sumiu", "seq": 1, "name": "x"})
        self.assertEqual(self.store.sorted_items()[-1]["id"], "perdido")

    def test_dentro_do_comodo_pelo_numero(self):
        self.store.data["items"].insert(0, {"id": "sal-099", "room": "sala", "seq": 99, "name": "x"})
        sala = [i["seq"] for i in self.store.sorted_items() if i["room"] == "sala"]
        self.assertEqual(sala, list(range(1, 13)) + [99])

    def test_ordenar_nao_muda_a_lista_gravada(self):
        self.store.data["items"].reverse()
        antes = [i["id"] for i in self.store.data["items"]]
        self.store.sorted_items()
        self.assertEqual([i["id"] for i in self.store.data["items"]], antes)


class Buscar(Base):
    def test_devolve_o_objeto_da_lista(self):
        self.assertIs(self.store.item("coz-001"), next(i for i in self.store.data["items"] if i["id"] == "coz-001"))

    def test_inexistente_e_none(self):
        self.assertIsNone(self.store.item("nao-existe"))
        self.assertIsNone(self.store.item(None))


if __name__ == "__main__":
    unittest.main()
