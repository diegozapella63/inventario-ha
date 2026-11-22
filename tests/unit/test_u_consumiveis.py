"""1.78.0: os três tipos do inventário, cada um com a sua chave: os itens da casa (vem ligado), os bens (vem ligado) e os
consumíveis (vem desligado; o que se gasta: pasta térmica, creme de massagem). O que aparece (visible_data), o que conta
no patrimônio (sem os consumíveis), a área Consumíveis no Store, a leitura por IA de um consumível, o que a Conversa
recebe e as ferramentas do CorrerIA (achar pelo uso, cadastrar, mover, o resumo)."""
import re
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
        # 1.82.0: sem valor e sem quantidade: as categorias dos consumíveis e quanto dura
        self.assertNotIn("preço TOTAL", p)
        self.assertNotIn('"qty"', p)
        self.assertNotIn('"value"', p)
        self.assertIn('- "dur": quantos dias uma embalagem costuma durar numa casa, um destes números: 7, 15, 30, 90, 180 ou 365', p)
        self.assertIn("c-limpeza (Limpeza), c-higiene (Higiene e cuidados)", p)
        self.assertNotIn("eletronicos (Eletrônicos)", p, "as categorias da casa não valem num consumível")
        self.assertIn('{"name":"","details":"","cat":"","dur":0,', p)
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
        self.consumivel(qty="2", dur=30, cat="c-higiene")
        txt = S.chat_context({})
        self.assertIn("Inventário da casa: 38 itens em 6 cômodos", txt, "o patrimônio sem os consumíveis")
        linha = next(ln for ln in txt.splitlines() if ln.startswith("Consumíveis (1;"))
        self.assertIn("não contam no patrimônio", linha)
        self.assertRegex(txt, r"- CON-001 Creme de massagem \| Higiene e cuidados \| dura 1 mês, até \d\d/\d\d/\d{4} \| Creme para massagem nas costas, de arnica\.")
        self.assertIn("sem quantidade e sem valor", linha)
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
            {"nome": "Creme de massagem", "duracao_dias": 90, "categoria": "Higiene e cuidados", "detalhes": "Creme para massagem nas costas, de arnica."},
            {"nome": "Pasta térmica", "detalhes": "Vai entre o processador e o cooler."}]})
        area = self.store.consumiveis_room()
        self.assertEqual((area["code"], area["kind"]), ("CON", "consumiveis"))
        self.assertRegex(txt, re.escape("Cadastrados 2 itens em Consumíveis: Creme de massagem (CON-001, Consumíveis, dura 3 meses, até DATA, id con-001); Pasta térmica (CON-002, Consumíveis, id con-002).").replace("DATA", r"\d\d/\d\d/\d{4}"))
        self.assertNotIn("Total:", txt, "1.82.0: um consumível não tem valor")
        it = self.item("con-001")
        self.assertEqual((it["room"], it["qty"], it["value"], it["dur"], it["cat"], it["zone"], it["source"], it["createdBy"]),
                         (area["id"], "1", 0, 90, "c-higiene", "", "correria", "Ana"))
        self.assertEqual((self.item("con-002")["cat"], self.item("con-002")["dur"]), ("c-outros", 0))
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
        self.assertEqual(r["opcoes"], {"zonas": False, "itens_da_casa": True, "bens": True, "consumiveis": True, "consumiveis_por_comodo": False})
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


class CategoriasEDuracao(Base):
    """1.82.0: os consumíveis têm as categorias deles (à parte das da casa, já com sugestões) e, no lugar da quantidade e
    do valor, a duração estimada."""

    def test_as_sugestoes_e_a_lista_a_parte(self):
        nomes = [c["name"] for c in self.store.cons_cats()]
        self.assertEqual(nomes, ["Limpeza", "Higiene e cuidados", "Cozinha e despensa", "Farmácia", "Pets", "Escritório e papelaria",
                                 "Manutenção e reparos", "Pilhas e eletrônicos", "Carro", "Jardim", "Outros"])
        self.assertTrue(all(c["id"].startswith("c-") for c in self.store.cons_cats()))
        self.assertEqual(self.store.public()["consCats"], self.store.cons_cats())
        self.assertFalse(set(self.store.cons_cat_map()) & set(self.store.cat_map()), "nenhum id igual ao de uma categoria da casa")

    def test_criar_renomear_e_apagar(self):
        casa = list(self.store.cats())
        c = self.store.create_cat({"name": "Piscina", "kind": "consumiveis"})
        self.assertEqual(c, {"id": "c-piscina", "name": "Piscina"})
        self.assertEqual([x["id"] for x in self.store.cons_cats()][-2:], ["c-piscina", "c-outros"], "Outros fica no fim")
        self.assertEqual(self.store.cats(), casa, "a lista da casa não muda")
        with self.assertRaises(S.ApiError):
            self.store.create_cat({"name": "piscina", "kind": "consumiveis"})
        self.assertEqual(self.store.create_cat({"name": "Limpeza"})["id"], "limpeza", "o mesmo nome pode existir na casa")
        self.assertEqual(self.store.update_cat("c-piscina", {"name": "Piscina e spa"})["name"], "Piscina e spa")
        it = self.consumivel(cat="c-piscina")
        self.assertEqual(it["cat"], "c-piscina")
        self.assertEqual(self.store.delete_cat("c-piscina"), 1)
        self.assertEqual(self.item(it["id"])["cat"], "c-outros", "os dela vão para Outros dos consumíveis")
        with self.assertRaises(S.ApiError):
            self.store.delete_cat("c-outros")

    def test_o_consumivel_sem_quantidade_e_sem_valor_com_a_duracao(self):
        it = self.consumivel(qty="3", value=50, dur=15, cat="eletronicos")
        self.assertEqual((it["qty"], it["value"], it["dur"], it["cat"]), ("1", 0, 15, "c-outros"), "a categoria da casa não vale; sem quantidade e sem valor")
        n = self.store.update_item(it["id"], {"qty": "9", "value": 80, "dur": 365, "cat": "c-pets"}, "Ana")
        self.assertEqual((n["qty"], n["value"], n["dur"], n["cat"]), ("1", 0, 365, "c-pets"))
        self.assertEqual(self.store.update_item(it["id"], {"dur": "abc"}, "Ana")["dur"], 0)
        self.assertEqual([S.dur_text(d) for d in (7, 15, 30, 90, 180, 365, 45, 1, 0, 9999)],
                         ["1 semana", "15 dias", "1 mês", "3 meses", "6 meses", "1 ano", "45 dias", "1 dia", "", ""])
        self.assertEqual(self.store.cat_of(n), "Pets")

    def test_ate_quando_dura_e_a_duracao_escolhida_a_mao(self):
        """1.83.0: a duração conta do dia em que foi informada (durAt); a escolhida à mão diz a unidade."""
        self.assertEqual([S.dur_text(d) for d in (730, 120, 21, 45, 14, 3650)], ["2 anos", "4 meses", "3 semanas", "45 dias", "2 semanas", "10 anos"])
        self.assertEqual(S.dur_until({"dur": 365, "createdAt": "2026-11-21T09:20:00"}), "2027-11-21", "num de antes, do cadastro")
        self.assertEqual(S.dur_until({"dur": 30, "durAt": "2027-01-31T10:00:00", "createdAt": "2026-01-01T00:00:00"}), "2027-03-02")
        self.assertEqual([S.dur_until(x) for x in ({"dur": 0, "createdAt": "2026-01-01"}, {"dur": 30}, None, {"dur": 30, "durAt": "2026-13-40"})], ["", "", "", ""])
        self.assertEqual((S.dia_br("2027-11-21"), S.dia_br("")), ("21/11/2027", ""))
        sem = self.consumivel(name="Sabão")
        self.assertNotIn("durAt", sem, "sem duração, sem a data")
        it = self.consumivel(dur=30)
        self.assertEqual(it["durAt"], it["createdAt"])
        it["durAt"] = "2026-01-10T08:00:00"  # como se tivesse sido informada em janeiro
        self.assertEqual(self.store.update_item(it["id"], {"name": "Creme novo", "dur": 30}, "Ana")["durAt"], "2026-01-10T08:00:00", "a mesma duração: a data fica")
        n = self.store.update_item(it["id"], {"dur": 730}, "Ana")
        self.assertNotEqual(n["durAt"], "2026-01-10T08:00:00", "mudou a duração: conta de hoje")
        ate = S.dur_until(n)
        v = self.json("ver_item", {"id": it["id"]})
        self.assertEqual((v["duracao"], v["duracao_dias"], v["dura_ate"]), ("2 anos", 730, ate))
        linha = next(x for x in self.json("buscar_itens", {"texto": "Creme novo"})["itens"] if x["id"] == it["id"])
        self.assertEqual(linha["dura_ate"], ate)
        self.assertNotIn("dura_ate", self.json("ver_item", {"id": sem["id"]}))

    def test_de_antes_com_categoria_da_casa_aparece_em_outros_sem_mudar_o_gravado(self):
        it = self.consumivel()
        it["cat"], it["value"], it["qty"] = "cozinha", 30, "2"  # como um gravado antes da 1.82.0
        self.assertEqual(self.store.cat_of(it), "Outros")
        self.assertEqual((it["value"], it["qty"]), (30, "2"), "o que estava gravado continua guardado")
        self.assertEqual(self.store.update_item(it["id"], {"name": "Creme"}, "Ana")["cat"], "c-outros")

    def test_mudar_de_lado_troca_a_categoria(self):
        it = self.consumivel(cat="c-limpeza")
        area = it["room"]
        self.assertEqual(self.store.update_item(it["id"], {"room": "sala"}, "Ana")["cat"], "outros")
        out = self.store.update_items([{"id": "sal-001", "room": area}], "Ana")
        self.assertEqual(out[0]["cat"], "c-outros")
        with self.assertRaises(S.ApiError):
            self.store.update_items([{"id": "sal-001", "cat": "moveis"}], "Ana")
        self.assertEqual(self.store.update_items([{"id": "sal-001", "cat": "c-limpeza"}], "Ana")[0]["cat"], "c-limpeza")

    def test_a_leitura_por_ia(self):
        its = S.clean_ai_items({"items": [{"name": "Detergente", "cat": "c-limpeza", "dur": 30, "value": 5, "qty": "3"},
                                          {"name": "Outro", "cat": "cozinha", "dur": "x"}]}, None, consumivel=True)
        self.assertEqual([(i["cat"], i["dur"], i["value"], i["qty"]) for i in its], [("c-limpeza", 30, 0, "1"), ("c-outros", 0, 0, "1")])

    def test_ferramentas(self):
        self.erro("cadastrar_itens", {"comodo": "Consumíveis", "itens": [{"nome": "Pilhas", "valor": 20}]}, "Um consumível não tem valor nem quantidade: mande duracao_dias")
        self.erro("cadastrar_itens", {"comodo": "Consumíveis", "itens": [{"nome": "Pilhas", "quantidade": "4"}]}, "Um consumível não tem valor nem quantidade")
        self.erro("cadastrar_itens", {"comodo": "Consumíveis", "itens": [{"nome": "Pilhas", "categoria": "Móveis"}]}, "As categorias dos consumíveis: Limpeza (c-limpeza)")
        self.erro("cadastrar_itens", {"comodo": "Consumíveis", "itens": [{"nome": "Pilhas", "duracao_dias": 1.5}]}, "duracao_dias: um número inteiro de dias")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Vaso", "duracao_dias": 30}, {"nome": "Mesa", "valor": 10}]}, "Item 1: A duração só vale num consumível: mande comodo \"Consumíveis\"")
        self.chamar("cadastrar_itens", {"comodo": "Consumíveis", "itens": [{"nome": "Pilhas AA", "categoria": "pilhas", "duracao_dias": 180}]})
        v = self.json("ver_item", {"id": "CON-001"})
        self.assertEqual((v["categoria"], v["duracao_dias"], v["duracao"]), ({"id": "c-eletronicos", "nome": "Pilhas e eletrônicos"}, 180, "6 meses"))
        for k in ("quantidade", "valor", "valor_desde"):
            self.assertNotIn(k, v)
        txt = self.chamar("editar_item", {"id": "CON-001", "duracao_dias": 365, "categoria": "Carro"})
        self.assertIn("duração: 6 meses → 1 ano", txt)
        self.assertIn("categoria: Pilhas e eletrônicos → Carro", txt)
        self.erro("editar_item", {"id": "CON-001", "valor": 10}, "Um consumível não tem valor nem quantidade")
        self.erro("editar_item", {"id": "sal-001", "duracao_dias": 30}, "duracao_dias só vale num consumível")
        self.erro("editar_item", {"id": "CON-001"}, "Diga o que muda: nome, categoria, duracao_dias, detalhes ou observacao.")
        r = self.json("resumo")
        self.assertEqual(r["categorias_consumiveis"][0], {"id": "c-limpeza", "nome": "Limpeza"})
        linha = r["consumiveis"]["lista"][0]
        self.assertEqual((linha["categoria"], linha["duracao"], linha["duracao_dias"]), ("Carro", "1 ano", 365))
        self.assertNotIn("valor", linha)
        b = self.json("buscar_itens", {"categoria": "Carro"})
        self.assertEqual([i["nome"] for i in b["itens"]], ["Pilhas AA"], "a busca pela categoria dos consumíveis")
        self.assertNotIn("Pilhas AA", [i["nome"] for i in self.json("buscar_itens", {"categoria": "Outros"})["itens"]])
        self.assertIn("Um consumível não tem quantidade nem valor", F.instrucoes(S))


class PorComodo(Base):
    """1.88.0: Consumíveis por cômodo (desligado de início): cada consumível pode dizer em que cômodo é usado."""

    def test_desligado_nao_aparece_e_a_ferramenta_explica(self):
        it = self.consumivel(usedIn="sala")
        self.assertEqual(it["usedIn"], ["sala"], "o Store guarda")
        self.assertFalse(S.cons_comodo_enabled())
        self.assertEqual(S.used_in(it), [])
        self.assertNotIn("usado_em", self.json("ver_item", {"id": it["id"]}))
        self.assertFalse(self.json("resumo")["opcoes"]["consumiveis_por_comodo"])
        self.erro("buscar_itens", {"usado_em": "sala"}, "Consumíveis por cômodo estão desligados")
        self.erro("editar_item", {"id": it["id"], "usado_em": "sala"}, "Consumíveis por cômodo estão desligados")
        self.assertNotIn("usado_em", F.instrucoes(S))

    def test_ligado_cadastra_edita_busca_e_tira(self):
        self.store.settings["cons_comodo"] = True
        self.assertTrue(self.json("resumo")["opcoes"]["consumiveis_por_comodo"])
        self.assertIn("usado_em", F.instrucoes(S))
        self.chamar("cadastrar_itens", {"comodo": "Consumíveis", "itens": [{"nome": "Detergente", "duracao_dias": 30, "usado_em": "Cozinha"},
                                                                          {"nome": "Pilhas AA", "usado_em": "sala"}, {"nome": "Fita isolante"}]})
        r = self.json("buscar_itens", {"usado_em": "cozinha"})
        self.assertEqual([(i["nome"], i["usado_em"]) for i in r["itens"]], [("Detergente", "Cozinha")])
        self.assertEqual(self.json("buscar_itens", {"comodo": "Consumíveis", "usado_em": "COZ"})["encontrados"], 1, "pelo código do cômodo também")
        fita = next(i for i in self.json("buscar_itens", {"comodo": "Consumíveis"})["itens"] if i["nome"] == "Fita isolante")
        self.assertNotIn("usado_em", fita)
        self.assertIn("usado em: (nenhum) → Sala de estar", self.chamar("editar_item", {"id": fita["id"], "usado_em": "sala"}))
        self.assertEqual(self.json("ver_item", {"id": fita["id"]})["usado_em"], "Sala de estar")
        self.assertEqual(self.json("buscar_itens", {"usado_em": "sala"})["encontrados"], 2)
        self.assertIn("usado em: Sala de estar → (nenhum)", self.chamar("editar_item", {"id": fita["id"], "usado_em": ""}))
        self.assertNotIn("usedIn", self.store.item(fita["id"]))
        self.assertIn("usado em Cozinha", S.chat_context({}))

    def test_so_num_consumivel_e_so_um_comodo_da_casa(self):
        self.store.settings["cons_comodo"] = True
        it = self.consumivel()
        self.erro("editar_item", {"id": it["id"], "usado_em": "Consumíveis"}, "um cômodo da casa")
        self.erro("editar_item", {"id": "sal-001", "usado_em": "cozinha"}, "usado_em só vale num consumível")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Vaso", "usado_em": "cozinha"}, {"nome": "Mesa"}]}, "O cômodo onde é usado só vale num consumível")
        self.erro("editar_item", {"id": it["id"], "usado_em": "porão"}, "cômodo")
        novo = self.store.update_item(it["id"], {"usedIn": "consumiveis"}, "Ana")
        self.assertNotIn("usedIn", novo, "a área dos consumíveis não é um cômodo")

    def test_varios_de_uma_vez(self):
        """1.89.0: o Alterar em lote (Buscar › Selecionar) leva o cômodo onde é usado; só num consumível."""
        a, b = self.consumivel(), self.consumivel(name="Sabão em pó")
        out = self.store.update_items([{"id": a["id"], "usedIn": "sala", "cat": "c-limpeza"}, {"id": b["id"], "usedIn": "cozinha"}], "Ana")
        self.assertEqual([(i["cat"], i["usedIn"]) for i in out], [("c-limpeza", ["sala"]), (b["cat"], ["cozinha"])])
        self.store.update_items([{"id": a["id"], "usedIn": ""}], "Ana")
        self.assertNotIn("usedIn", self.store.item(a["id"]))
        with self.assertRaises(S.ApiError) as e:
            self.store.update_items([{"id": b["id"], "usedIn": "consumiveis"}], "Ana")
        self.assertEqual(e.exception.message if hasattr(e.exception, "message") else str(e.exception.args[-1]), "Escolha um cômodo que exista.")
        self.assertEqual(self.store.item(b["id"])["usedIn"], ["cozinha"], "tudo ou nada")
        self.store.update_items([{"id": "sal-001", "usedIn": "cozinha"}], "Ana")
        self.assertNotIn("usedIn", self.store.item("sal-001"), "num item da casa, não vale")

    def test_comodo_apagado_ou_itens_da_casa_desligados(self):
        self.store.settings["cons_comodo"] = True
        it = self.consumivel(usedIn="nao-existe")
        self.assertNotIn("usedIn", it)
        it = self.store.update_item(it["id"], {"usedIn": "sala"}, "Ana")
        self.assertEqual([r["name"] for r in S.used_in(it)], ["Sala de estar"])
        self.store.settings["itens"] = False
        self.assertFalse(S.cons_comodo_enabled(), "sem os cômodos, não há por cômodo")
        self.assertEqual(S.used_in(it), [])


class VariosComodosENaRonda(Base):
    """1.91.0: um consumível usado em mais de um cômodo; e o cadastro que a IA manda no meio de uma ronda, com o cômodo da
    ronda no lugar de Consumíveis (o dono viu "Não deu: duracao_dias só vale num consumível")."""

    def setUp(self):
        super().setUp()
        self.store.settings["cons_comodo"] = True

    def test_mais_de_um_comodo(self):
        it = self.consumivel(usedIn=["sala", "cozinha", "sala", "nao-existe", "consumiveis"])
        self.assertEqual(it["usedIn"], ["sala", "cozinha"], "sem repetir, só os cômodos da casa")
        self.assertEqual(S.used_in_text(it), "Sala de estar, Cozinha")
        self.assertEqual(self.json("ver_item", {"id": it["id"]})["usado_em"], "Sala de estar, Cozinha")
        for onde in ("sala", "cozinha"):
            self.assertEqual(self.json("buscar_itens", {"usado_em": onde})["encontrados"], 1, onde)
        self.chamar("editar_item", {"id": it["id"], "usado_em": "Cozinha; Quarto"})
        self.assertEqual(self.store.item(it["id"])["usedIn"], ["cozinha", "quarto"])
        self.chamar("editar_item", {"id": it["id"], "usado_em": ""})
        self.assertNotIn("usedIn", self.store.item(it["id"]))
        self.store.update_items([{"id": it["id"], "usedIn": ["sala", "quarto"]}], "Ana")
        self.assertEqual(self.store.item(it["id"])["usedIn"], ["sala", "quarto"])

    def test_o_de_antes_com_um_id_so_continua_valendo(self):
        it = self.consumivel()
        self.store.item(it["id"])["usedIn"] = "sala"  # como a 1.88.0 gravava
        self.assertEqual(S.used_in_text(self.store.item(it["id"])), "Sala de estar")
        self.assertEqual(self.json("buscar_itens", {"usado_em": "sala"})["encontrados"], 1)

    def test_com_duracao_e_o_comodo_da_ronda_vai_para_os_consumiveis(self):
        txt = self.chamar("cadastrar_itens", {"comodo": "Cozinha", "itens": [{"nome": "Detergente", "duracao_dias": 30, "categoria": "Limpeza"}]})
        self.assertIn("Cadastrado em Consumíveis", txt)
        it = next(i for i in self.store.data["items"] if i["name"] == "Detergente")
        self.assertTrue(self.store.is_cons(it["room"]))
        self.assertEqual((it["dur"], it["usedIn"]), (30, ["cozinha"]), "o cômodo mandado vira o usado em")
        self.chamar("cadastrar_itens", {"comodo": "Cozinha", "itens": [{"nome": "Sabão", "duracao_dias": 15, "usado_em": "Quarto"}]})
        self.assertEqual(next(i for i in self.store.data["items"] if i["name"] == "Sabão")["usedIn"], ["quarto"], "o usado_em dito vale")
        self.store.settings["cons_comodo"] = False
        self.chamar("cadastrar_itens", {"comodo": "Cozinha", "itens": [{"nome": "Esponja", "duracao_dias": 7}]})
        it = next(i for i in self.store.data["items"] if i["name"] == "Esponja")
        self.assertTrue(self.store.is_cons(it["room"]))
        self.assertNotIn("usedIn", it, "sem Consumíveis por cômodo, sem o cômodo")
        self.store.settings["consumiveis"] = False
        self.erro("cadastrar_itens", {"comodo": "Cozinha", "itens": [{"nome": "Pano", "duracao_dias": 7}]}, "A duração só vale num consumível")


if __name__ == "__main__":
    unittest.main()
