"""O cômodo na leitura por IA (Catalogar itens com IA e Falar): sem cômodo escolhido, a IA vê os cômodos da casa e
escolhe (na foto, o da foto; na fala, um para cada item); o que ela não souber fica "" e a pessoa escolhe na revisão."""
import json
import unittest

from _boot import UnitBase, server as S


class Instrucoes(UnitBase):
    def test_foto_sem_comodo_ve_a_casa_com_zonas_e_itens(self):
        self.store.settings["zones"] = True
        p = S.ai_prompt("multi", None, "")
        linha = next(ln for ln in p.splitlines() if ln.startswith("- cozinha = "))
        self.assertTrue(linha.startswith("- cozinha = Cozinha. Zonas: Armário; Bancada; Geladeira; Mesa. Itens já cadastrados: Geladeira frost free inox;"), linha)

    def test_foto_com_comodo_nao_lista_a_casa_nem_pede_o_comodo(self):
        p = S.ai_prompt("multi", self.store.room("sala"), "")
        self.assertNotIn("Cômodos da casa", p)
        self.assertNotIn('"room"', p)

    def test_fala_com_comodo_so_muda_se_a_pessoa_disser(self):
        p = S.ai_prompt("voice", self.store.room("quarto"), "", "um abajur")
        self.assertIn('o que a pessoa disse para ele (ou para todos); se ela não disse, "".', p)
        self.assertNotIn("geladeira na cozinha", p)
        self.assertIn("Cômodos da casa (id = nome): sala = Sala de estar;", p)
        self.assertIn("Cômodo: Quarto.", p)

    def test_fala_pede_o_comodo_em_cada_item(self):
        p = S.ai_prompt("voice", None, "", "um abajur")
        linha = next(ln for ln in p.splitlines() if ln.startswith('{"items":'))
        self.assertEqual(list(json.loads(linha)["items"][0]), ["name", "details", "cat", "qty", "value", "room", "existing", "confidence"])

    def test_bens_nao_e_comodo(self):
        area = self.store.create_room({"kind": "bens"})
        self.store.create_items([{"room": area["id"], "name": "Carro hatch", "cat": "veiculos", "value": 60000}], None)
        for mode in ("multi", "voice"):
            with self.subTest(mode=mode):
                p = S.ai_prompt(mode, None, "", "x" if mode == "voice" else "")
                self.assertNotIn("bens = Bens", p)
                self.assertNotIn("Carro hatch", p)

    def test_no_maximo_60_itens_por_comodo(self):
        self.store.create_room({"name": "Garagem"})
        for n in range(70):
            self.store.data["items"].append({"id": f"gar-{n:03d}", "room": "garagem", "name": f"Ferramenta {n:03d}", "value": 1000 - n})
        linha = next(ln for ln in S.ai_prompt("multi", None, "").splitlines() if ln.startswith("- garagem = "))
        nomes = linha.split("Itens já cadastrados: ", 1)[1].rstrip(".").split("; ")
        self.assertEqual((len(nomes), nomes[0], nomes[-1]), (60, "Ferramenta 000", "Ferramenta 059"), "os mais caros")


class Respostas(UnitBase):
    def limpa(self, parsed, room=None, per_item=False):
        return S.clean_ai_items(parsed, self.store.room(room) if room else None, per_item)

    def test_foto_o_comodo_que_a_ia_disse_vale_para_todos(self):
        out = self.limpa({"room": "cozinha", "items": [{"name": "Batedeira", "room": "sala"}, {"name": "Panela"}]})
        self.assertEqual([i["room"] for i in out], ["cozinha", "cozinha"], "a foto é de um cômodo só")

    def test_foto_o_comodo_escolhido_vale_mais_que_o_da_ia(self):
        out = self.limpa({"room": "cozinha", "items": [{"name": "Batedeira"}]}, "quarto")
        self.assertEqual(out[0]["room"], "quarto")

    def test_fala_cada_item_no_seu_comodo(self):
        out = self.limpa({"room": "", "items": [{"name": "Geladeira", "room": "cozinha"}, {"name": "Sofá", "room": "sala"}, {"name": "Abajur"}]},
                         per_item=True)
        self.assertEqual([i["room"] for i in out], ["cozinha", "sala", ""], "o que a IA não soube fica para a pessoa")
        out = self.limpa({"items": [{"name": "Geladeira", "room": "cozinha"}, {"name": "Abajur"}]}, "quarto", per_item=True)
        self.assertEqual([i["room"] for i in out], ["cozinha", "quarto"], "o resto vai para o cômodo de onde abriu")
        out = self.limpa({"room": "varanda", "items": [{"name": "Rede"}, {"name": "Geladeira", "room": "cozinha"}]}, "quarto", per_item=True)
        self.assertEqual([i["room"] for i in out], ["varanda", "cozinha"], "o cômodo dito para todos vale mais que o de onde abriu")

    def test_comodo_pelo_nome_tambem_vale(self):
        out = self.limpa({"items": [{"name": "Geladeira", "room": "  cozinha "}, {"name": "Sofá", "room": "SALA DE ESTAR"}]}, per_item=True)
        self.assertEqual([i["room"] for i in out], ["cozinha", "sala"])

    def test_comodo_que_nao_existe_ou_bens_vira_vazio(self):
        area = self.store.create_room({"kind": "bens"})
        for room in ("garagem", area["id"], "Bens", 3, ["sala"], None):
            with self.subTest(room=room):
                self.assertEqual(self.limpa({"items": [{"name": "X", "room": room}]}, per_item=True)[0]["room"], "")
                self.assertEqual(self.limpa({"room": room, "items": [{"name": "X"}]})[0]["room"], "")

    def test_ja_cadastrado_conferido_no_comodo_do_item(self):
        out = self.limpa({"items": [{"name": "Sofá", "room": "sala", "existing": "Sofá de 3 lugares cinza-azulado"},
                                    {"name": "Sofá", "room": "cozinha", "existing": "Sofá de 3 lugares cinza-azulado"}]}, per_item=True)
        self.assertEqual([i["existing"] for i in out], ["Sofá de 3 lugares cinza-azulado", ""])

    def test_bem_nao_e_item_ja_cadastrado(self):
        area = self.store.create_room({"kind": "bens"})
        self.store.create_items([{"room": area["id"], "name": "Carro hatch", "cat": "veiculos", "value": 60000}], None)
        self.assertEqual(self.limpa({"items": [{"name": "Carro", "existing": "Carro hatch"}]})[0]["existing"], "")

    def test_comodo_de_todos(self):
        self.assertEqual(S.common_room([{"room": "sala"}, {"room": "sala"}]), "sala")
        self.assertEqual(S.common_room([{"room": "sala"}, {"room": ""}]), "")
        self.assertEqual(S.common_room([]), "")


class Pedido(UnitBase):
    def test_bens_e_comodo_que_nao_existe_sao_sem_comodo(self):
        area = self.store.create_room({"kind": "bens"})
        for room in (area["id"], "garagem", "", None, 7):
            with self.subTest(room=room):
                self.assertIsNone(S.ai_fixed_room({"room": room}))
        self.assertEqual(S.ai_fixed_room({"room": "sala"})["id"], "sala")

    def test_fala_devolve_o_comodo_de_cada_item(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda k, p: json.dumps({"items": [{"name": "Geladeira", "room": "cozinha"}, {"name": "Abajur", "room": ""}]})
        res = S.ai_from_speech({"text": "a geladeira da cozinha e um abajur"})
        self.assertEqual(([i["room"] for i in res["items"]], res["room"]), (["cozinha", ""], ""))
        ins = ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]
        self.assertIn("- cozinha = Cozinha.", ins)

    def test_foto_devolve_o_comodo_que_a_ia_reconheceu(self):
        ha = self.fake_ha()
        ha.media_root = S.MEDIA_ROOT
        ha.ai_reply = lambda k, p: json.dumps({"room": "Lavanderia", "items": [{"name": "Varal"}]})
        res = S.ai_identify({"file": "sala-1.jpg", "mode": "multi"})
        self.assertEqual((res["room"], res["items"][0]["room"]), ("lavanderia", "lavanderia"))


if __name__ == "__main__":
    unittest.main()
