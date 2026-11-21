"""1.78.0: os três tipos do inventário, cada um com a sua chave: os itens da casa (vem ligado), os bens (vem ligado) e os
consumíveis (vem desligado; o que se gasta: pasta térmica, creme de massagem). O que aparece (visible_data), o que conta
no patrimônio (sem os consumíveis), a área Consumíveis no Store, a leitura por IA de um consumível, o que a Conversa
recebe e as ferramentas do CorrerIA (achar pelo uso, cadastrar, mover, o resumo)."""
import json
import unittest

from _boot import UnitBase, server as S

import ferramentas as F

ANA = {"id": "person.ana", "nome": "Ana"}


class Base(UnitBase):
    def setUp(self):
        super().setUp()
        self.store.settings["consumiveis"] = True

    def chamar(self, nome, args=None):
        return F.chamar(S, nome, args or {}, ANA, "Claude")

    def json(self, nome, args=None):
        return json.loads(self.chamar(nome, args))

    def erro(self, nome, args, parte):
        with self.assertRaises(F.ErroFerramenta) as cm:
            self.chamar(nome, args)
        self.assertIn(parte, str(cm.exception))

    def consumivel(self, nome="Creme de massagem", detalhes="Creme para massagem nas costas, de arnica.", **mais):
        area = self.store.create_room({"kind": "consumiveis"})
        return self.store.create_items([{"room": area["id"], "name": nome, "details": detalhes, **mais}], "Ana")[0]


class Area(Base):
    def test_criada_uma_vez_depois_dos_comodos_e_dos_bens(self):
        con = self.store.create_room({"kind": "consumiveis"})
        self.assertEqual((con["id"], con["code"], con["name"], con["kind"]), ("consumiveis", "CON", "Consumíveis", "consumiveis"))
        self.assertIs(self.store.create_room({"kind": "consumiveis"}), con, "de novo: a mesma área")
        ben = self.store.create_room({"kind": "bens"})
        self.assertEqual([r["id"] for r in self.store.data["rooms"]][-2:], [ben["id"], con["id"]], "os cômodos, depois Bens, depois Consumíveis")
        sala = self.store.create_room({"name": "Sala nova"})
        ordem = [r.get("kind") or "" for r in self.store.data["rooms"]]
        self.assertEqual(ordem[-2:], ["bens", "consumiveis"], "um cômodo novo entra antes das áreas")
        self.assertLess(sala["order"], ben["order"])

    def test_o_codigo_con_ja_usado(self):
        self.store.create_room({"name": "Construção", "code": "CON"})
        self.assertEqual(self.store.create_room({"kind": "consumiveis"})["code"], "CON2")

    def test_desligados_nao_cria(self):
        self.store.settings["consumiveis"] = False
        with self.assertRaises(S.ApiError) as cm:
            self.store.create_room({"kind": "consumiveis"})
        self.assertEqual(cm.exception.status, 409)
        self.assertIsNone(self.store.consumiveis_room())

    def test_tipo_desconhecido(self):
        with self.assertRaises(S.ApiError) as cm:
            self.store.create_room({"kind": "outro", "name": "X"})
        self.assertEqual(cm.exception.status, 400)


class OQueAparece(Base):
    def test_cada_tipo_com_a_sua_chave(self):
        self.assertIs(S.itens_enabled(), True)
        self.assertIs(S.bens_enabled(), True)
        self.assertIs(S.consumiveis_enabled(), True)
        self.store.settings.pop("consumiveis")
        self.assertIs(S.consumiveis_enabled(), False, "os consumíveis vêm desligados")
        self.store.settings.update(itens=False)
        self.assertIs(S.itens_enabled(), False)
        self.assertEqual([S.area_enabled(k) for k in (None, "", "bens", "consumiveis")], [False, False, True, False])

    def test_visible_data(self):
        it = self.consumivel()
        ben = self.store.create_room({"kind": "bens"})
        carro = self.store.create_items([{"room": ben["id"], "name": "Carro de exemplo", "value": 40000}], "Ana")[0]
        ids = lambda **k: {i["id"] for i in S.visible_data(**k)[1]}  # noqa: E731
        self.assertEqual(len(ids()), 40)
        self.assertIn(it["id"], ids())
        self.assertNotIn(it["id"], ids(consumiveis=False), "os consumíveis não contam no patrimônio")
        self.assertIn(carro["id"], ids(consumiveis=False))
        self.assertNotIn("consumiveis", [r["id"] for r in S.visible_data(consumiveis=False)[0]])
        self.store.settings["itens"] = False  # sem os itens da casa: só as áreas
        self.assertEqual(ids(), {it["id"], carro["id"]})
        self.assertEqual([r["id"] for r in S.visible_data()[0]], ["bens", "consumiveis"])
        self.store.settings["consumiveis"] = False
        self.assertEqual(ids(), {carro["id"]})
        self.assertEqual(len(self.store.data["items"]), 40, "nada é apagado")

    def test_sem_os_itens_da_casa_nao_cria_comodo(self):
        self.store.settings["itens"] = False
        with self.assertRaises(S.ApiError) as cm:
            self.store.create_room({"name": "Garagem"})
        self.assertEqual(cm.exception.status, 409)
        self.assertIn("itens da casa estão desligados", cm.exception.msg)
        self.assertEqual(self.store.create_room({"kind": "bens"})["kind"], "bens", "as áreas continuam valendo")


class LeituraPorIA(Base):
    def test_o_pedido_de_um_consumivel(self):
        self.store.settings["zones"] = True
        p = S.ai_prompt("single", None, "", consumivel=True)
        self.assertIn("Este item é um consumível", p)
        self.assertIn("o que é e para que serve", p)
        self.assertIn("preço TOTAL em reais (número, sem símbolo) de comprar novo", p)
        self.assertNotIn("mercado de usados", p, "um consumível não é um usado")
        self.assertNotIn('"zone"', p, "sem zona, mesmo com as zonas ligadas")
        comum = S.ai_prompt("single", None, "")
        self.assertNotIn("consumível", comum)
        self.assertIn("mercado de usados", comum)
        self.assertIn('"zone"', comum)

    def test_a_ia_nao_escolhe_uma_area_como_comodo(self):
        self.consumivel()
        self.store.create_room({"kind": "bens"})
        self.assertEqual([r["id"] for r, _ in S.ai_house()], ["sala", "cozinha", "quarto", "escritorio", "lavanderia", "varanda"])
        self.assertEqual(S.ai_room_id("consumiveis"), "")
        self.assertEqual(S.ai_room_id("Consumíveis"), "")
        self.assertIsNone(S.ai_fixed_room({"room": "consumiveis"}))
        self.assertEqual(S.ai_fixed_room({"room": "sala"})["id"], "sala")
        self.store.settings["itens"] = False  # sem os itens da casa, a IA não tem cômodo para escolher
        self.assertEqual(S.ai_house(), [])
        self.assertEqual(S.ai_room_id("sala"), "")
        self.assertIsNone(S.ai_fixed_room({"room": "sala"}))

    def test_o_nome_igual_de_um_consumivel_nao_e_item_ja_cadastrado(self):
        self.consumivel(nome="Luminária de exemplo")
        its = S.clean_ai_items({"items": [{"name": "Luminária de exemplo", "existing": "Luminária de exemplo"}]}, None)
        self.assertEqual(its[0]["existing"], "", "os consumíveis não entram na lista do que já há na casa")


class Conversa(Base):
    def test_consumiveis_a_parte_com_para_que_serve(self):
        self.consumivel(qty="2")
        txt = S.chat_context({})
        self.assertIn("Inventário da casa: 38 itens em 6 cômodos", txt, "o patrimônio sem os consumíveis")
        linha = next(ln for ln in txt.splitlines() if ln.startswith("Consumíveis (1;"))
        self.assertIn("não contam no patrimônio", linha)
        self.assertIn("- CON-001 Creme de massagem | Outros | qtd 2 | Creme para massagem nas costas, de arnica.", txt)
        todos = txt.split("Todos os itens (")[1].split("Consumíveis (")[0]
        self.assertNotIn("Creme de massagem", todos, "fora da lista dos itens com valor")

    def test_sem_os_itens_da_casa(self):
        self.consumivel()
        self.store.settings["itens"] = False
        txt = S.chat_context({})
        self.assertIn("Os itens da casa (os cômodos) estão desligados", txt)
        self.assertNotIn("Cômodos:", txt)
        self.assertNotIn("SAL-001", txt)
        self.assertIn("CON-001 Creme de massagem", txt)

    def test_desligados_a_ia_nao_ve(self):
        self.consumivel()
        self.store.settings["consumiveis"] = False
        self.assertNotIn("Creme de massagem", S.chat_context({}))


class Ferramentas(Base):
    def test_instrucoes_dizem_o_que_esta_ligado(self):
        self.assertIn("os consumíveis (o que se gasta", F.instrucoes(S))
        self.store.settings["consumiveis"] = False
        self.assertNotIn("consumíveis", F.instrucoes(S))
        self.store.settings["itens"] = False
        self.assertIn("sem os itens da casa (desligados)", F.instrucoes(S))

    def test_cadastrar_cria_a_area_e_guarda_o_para_que_serve(self):
        txt = self.chamar("cadastrar_itens", {"comodo": "Consumíveis", "itens": [
            {"nome": "Creme de massagem", "quantidade": 2, "detalhes": "Creme para massagem nas costas, de arnica."},
            {"nome": "Pasta térmica", "valor": 45, "detalhes": "Vai entre o processador e o cooler."}]})
        area = self.store.consumiveis_room()
        self.assertEqual((area["code"], area["kind"]), ("CON", "consumiveis"))
        self.assertIn("Cadastrados 2 itens em Consumíveis: Creme de massagem (CON-001", txt)
        it = self.item("con-001")
        self.assertEqual((it["room"], it["qty"], it["zone"], it["source"], it["createdBy"]), (area["id"], "2", "", "correria", "Ana"))
        self.chamar("cadastrar_itens", {"comodo": "consumivel", "itens": [{"nome": "Pilhas AA"}]})
        self.assertEqual(len([r for r in self.store.data["rooms"] if r.get("kind") == "consumiveis"]), 1, "a mesma área")

    def test_o_que_temos_para_massagem(self):
        """A pergunta do dono no CorrerIA: achar pelo uso, o consumível (pelo para que serve) e o item da casa (pelo nome)."""
        self.consumivel()
        self.store.create_items([{"room": "quarto", "name": "Massageador elétrico de exemplo", "value": 200}], "Ana")
        r = self.json("buscar_itens", {"texto": "massag"})
        self.assertEqual(sorted(i["nome"] for i in r["itens"]), ["Creme de massagem", "Massageador elétrico de exemplo"])
        creme = next(i for i in r["itens"] if i["nome"] == "Creme de massagem")
        self.assertEqual((creme["tipo"], creme["para_que_serve"], creme["comodo"]), ("consumível", "Creme para massagem nas costas, de arnica.", "Consumíveis"))
        self.assertNotIn("tipo", next(i for i in r["itens"] if i["nome"].startswith("Massageador")))
        self.assertEqual(r["valor_total"], 200.0, "a soma sem os consumíveis")
        self.assertIn("massag acha massagem e massageador", F.POR_NOME["buscar_itens"]["descricao"])
        so = self.json("buscar_itens", {"comodo": "consumíveis"})
        self.assertEqual([i["nome"] for i in so["itens"]], ["Creme de massagem"])

    def test_buscar_sem_a_area_ainda(self):
        self.assertEqual(self.json("buscar_itens", {"comodo": "Consumíveis"})["encontrados"], 0)

    def test_resumo_a_parte_e_fora_do_total(self):
        self.consumivel(value=30)
        r = self.json("resumo")
        self.assertEqual((r["total"], r["itens"]), (28795.0, 38), "o total sem os consumíveis")
        self.assertEqual(r["consumiveis"]["itens"], 1)
        self.assertEqual(r["consumiveis"]["lista"][0]["para_que_serve"], "Creme para massagem nas costas, de arnica.")
        self.assertNotIn("CON", [c["codigo"] for c in r["comodos"]])
        self.assertEqual(r["opcoes"], {"zonas": False, "itens_da_casa": True, "bens": True, "consumiveis": True})
        self.store.settings["consumiveis"] = False
        self.assertNotIn("consumiveis", self.json("resumo"))

    def test_ver_e_mover(self):
        it = self.consumivel()
        v = self.json("ver_item", {"id": "CON-001"})
        self.assertEqual(v["comodo"]["obs"], "Consumíveis: o que se gasta e se compra de novo; fora do patrimônio")
        txt = self.chamar("mover_itens", {"ids": ["sal-001"], "comodo": "Consumíveis"})
        self.assertIn("para Consumíveis", txt)
        self.assertEqual(self.item("sal-001")["room"], it["room"])

    def test_sem_zona_e_desligados(self):
        self.store.settings["zones"] = True
        self.erro("cadastrar_itens", {"comodo": "Consumíveis", "zona": "Gaveta", "itens": [{"nome": "Pilhas"}]}, "Um consumível não tem zona")
        self.assertIsNone(self.store.consumiveis_room(), "nada criado antes de conferir")
        self.store.settings["consumiveis"] = False
        self.erro("cadastrar_itens", {"comodo": "Consumíveis", "itens": [{"nome": "Pilhas"}]}, "Os consumíveis estão desligados")

    def test_nomes_dos_comodos_no_erro(self):
        self.erro("cadastrar_itens", {"comodo": "porão", "itens": [{"nome": "X"}]}, "Consumíveis (o que se gasta)")

    def test_novo_comodo(self):
        self.erro("novo_comodo", {"nome": "Consumíveis"}, "Consumíveis é a área do que se gasta")
        self.store.settings["itens"] = False
        self.erro("novo_comodo", {"nome": "Garagem"}, "Os itens da casa estão desligados")

    def test_sem_os_itens_da_casa_o_resumo_so_com_as_areas(self):
        self.consumivel()
        self.store.settings["itens"] = False
        r = self.json("resumo")
        self.assertEqual((r["total"], r["itens"], r["comodos"]), (0, 0, []))
        self.assertEqual(r["consumiveis"]["itens"], 1)
        self.assertIs(r["opcoes"]["itens_da_casa"], False)
        self.erro("ver_item", {"id": "sal-001"}, "Item não encontrado")


if __name__ == "__main__":
    unittest.main()
