"""As ferramentas do CorrerIA (ferramentas.py), sem servidor: a lista no formato do contrato, cada leitura (resumo, buscar,
ver) e cada gravação (cadastrar, editar, mover, apagar, novo cômodo) pelas regras do Store, os erros que dizem o que vale,
as zonas e os bens ligados ou não, e a conexão própria do CorrerIA (chave, arquivo em share/inventario, último uso)."""
import json
import os
import re
import stat
import unittest
from unittest import mock

from _boot import UnitBase, server as S

import ferramentas as F

ANA = {"id": "person.ana", "nome": "Ana"}


class Base(UnitBase):
    def chamar(self, nome, args=None, pessoa=ANA, cliente="Claude"):
        return F.chamar(S, nome, args or {}, pessoa, cliente)

    def json(self, nome, args=None):
        return json.loads(self.chamar(nome, args))

    def erro(self, nome, args=None, parte=None):
        with self.assertRaises(F.ErroFerramenta) as cm:
            self.chamar(nome, args)
        if parte:
            self.assertIn(parte, str(cm.exception))
        return str(cm.exception)

    def rev(self):
        return self.store.data["rev"]


class Lista(Base):
    def test_formato_do_contrato(self):
        fs = F.lista()
        self.assertTrue(5 <= len(fs) <= 12)
        nomes = [f["nome"] for f in fs]
        self.assertEqual(len(set(nomes)), len(nomes))
        for f in fs:
            with self.subTest(f=f["nome"]):
                self.assertRegex(f["nome"], r"^[a-z0-9_]{1,40}$")
                self.assertEqual(set(f), {"nome", "titulo", "descricao", "entrada", "grava", "apaga"})
                self.assertTrue(f["titulo"] and len(f["titulo"]) <= 40)
                self.assertGreater(len(f["descricao"]), 30)
                e = f["entrada"]
                self.assertEqual((e["type"], e["additionalProperties"]), ("object", False))
                self.assertTrue(set(e["required"]) <= set(e["properties"]))
                self.assertIsInstance(f["grava"], bool)
                self.assertIsInstance(f["apaga"], bool)
                json.dumps(e)

    def test_leituras_primeiro_e_so_apagar_item_apaga(self):
        fs = F.lista()
        grava = [f["grava"] for f in fs]
        self.assertEqual(grava, sorted(grava), "primeiro as leituras, depois as gravações")
        self.assertEqual([f["nome"] for f in fs if f["apaga"]], ["apagar_item"])
        self.assertEqual([f["nome"] for f in fs if not f["grava"]], ["resumo", "buscar_itens", "ver_item"])

    def test_nada_de_fotos_backups_ou_configuracoes(self):
        texto = json.dumps(F.lista(), ensure_ascii=False).lower()
        for proibido in ("backup", "chave", "configura", "senha"):
            self.assertNotIn(proibido, texto)
        for f in F.lista():
            self.assertFalse({"foto", "fotos", "photos"} & set(f["entrada"]["properties"]))

    def test_instrucoes_dizem_por_onde_comecar_e_o_que_esta_ligado(self):
        t = F.instrucoes(S)
        self.assertIn("inventario_resumo", t)
        self.assertIn("bens", t)
        self.assertNotIn("zonas", t)
        self.store.settings.update(zones=True, bens=False)
        t = F.instrucoes(S)
        self.assertIn("zonas", t)
        self.assertNotIn("os bens", t)

    def test_lista_e_uma_copia(self):
        F.lista()[0]["nome"] = "outro"
        self.assertEqual(F.lista()[0]["nome"], "resumo")


class Argumentos(Base):
    def test_ferramenta_desconhecida(self):
        with self.assertRaises(LookupError) as cm:
            self.chamar("fotos")
        self.assertEqual(str(cm.exception), "Ferramenta desconhecida: fotos.")

    def test_argumento_desconhecido_diz_os_que_valem(self):
        self.erro("ver_item", {"id": "sal-001", "foto": 1}, "Argumento desconhecido: foto. Valem: id.")

    def test_argumentos_que_nao_sao_objeto(self):
        self.erro("ver_item", ["sal-001"], "argumentos precisa ser um objeto")

    def test_sem_argumentos_vale_vazio(self):
        self.assertIn('"total"', F.chamar(S, "resumo", None))

    def test_falta_o_obrigatorio(self):
        self.erro("ver_item", {}, "Falta: id.")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": []}, "Falta: itens.")


class Resumo(Base):
    def test_totais_comodos_e_categorias(self):
        r = self.json("resumo")
        self.assertEqual((r["total"], r["itens"]), (28795.0, 38))
        self.assertEqual([c["codigo"] for c in r["comodos"]], ["SAL", "COZ", "QUA", "ESC", "LAV", "VAR"])
        self.assertEqual(r["comodos"][1], {"id": "cozinha", "codigo": "COZ", "nome": "Cozinha", "itens": 7, "valor": 5430.0})
        self.assertEqual(len(r["categorias"]), 15, "todas as categorias, também as sem itens (os ids servem no cadastro)")
        self.assertEqual(next(c for c in r["categorias"] if c["id"] == "eletronicos"), {"id": "eletronicos", "nome": "Eletrônicos", "itens": 6, "valor": 10050.0})
        self.assertEqual(r["mais_valiosos"][0]["codigo"], "ESC-001")
        self.assertEqual(len(r["mais_valiosos"]), 10)
        self.assertEqual(len(r["ultimos_cadastrados"]), 10)
        self.assertEqual(r["opcoes"], {"zonas": False, "bens": True})
        self.assertNotIn("zonas", r["comodos"][0])
        self.assertEqual(r["bens"]["itens"], 0)

    def test_zonas_so_com_elas_ligadas(self):
        self.store.settings["zones"] = True
        r = self.json("resumo")
        self.assertEqual(r["comodos"][0]["zonas"], ["Sofá", "Parede", "Piso", "Rack", "Estante"])
        self.assertEqual(r["mais_valiosos"][0].get("zona"), "Mesa")

    def test_bens_a_parte_e_desligados_somem(self):
        self.chamar("cadastrar_itens", {"comodo": "Bens", "itens": [{"nome": "Carro de exemplo", "valor": 40000, "categoria": "veiculos"},
                                                                    {"nome": "Barco de exemplo", "valor": 5000}]})
        r = self.json("resumo")
        self.assertEqual(r["total"], 73795.0)
        self.assertEqual(r["dentro_de_casa"], 28795.0)
        self.assertEqual((r["bens"]["codigo"], r["bens"]["itens"], r["bens"]["por_tipo"]), ("BEN", 2, {"Veículos": 40000.0, "Outros": 5000.0}))
        self.assertNotIn("BEN", [c["codigo"] for c in r["comodos"]])
        self.store.settings["bens"] = False
        r = self.json("resumo")
        self.assertEqual((r["total"], r["itens"]), (28795.0, 38))
        self.assertNotIn("bens", r)
        self.assertNotIn("dentro_de_casa", r)

    def test_nao_grava_nada(self):
        antes = self.rev()
        self.chamar("resumo")
        self.assertEqual(self.rev(), antes)


class Buscar(Base):
    def test_texto_sem_acento_e_todas_as_palavras(self):
        r = self.json("buscar_itens", {"texto": "sofa"})
        self.assertEqual([i["id"] for i in r["itens"]], ["sal-001"], "sem zonas, a zona Sofá não conta")
        r = self.json("buscar_itens", {"texto": "MESA trabalho"})
        self.assertEqual([i["id"] for i in r["itens"]], ["esc-004"])
        r = self.json("buscar_itens", {"texto": "mesa madeira"})
        self.assertEqual([i["id"] for i in r["itens"]], ["coz-007", "esc-004"], "os detalhes contam")

    def test_com_zonas_a_zona_conta_e_aparece(self):
        self.store.settings["zones"] = True
        r = self.json("buscar_itens", {"texto": "rack"})
        self.assertEqual(r["encontrados"], 4)
        self.assertTrue(all(i["zona"] == "Rack" for i in r["itens"]))
        r = self.json("buscar_itens", {"zona": "mesa", "comodo": "ESC"})
        self.assertEqual(r["encontrados"], 5)

    def test_zona_com_zonas_desligadas(self):
        self.erro("buscar_itens", {"zona": "Rack"}, "zonas estão desligadas")

    def test_pelo_codigo_comodo_categoria_e_cômodo_na_busca(self):
        self.assertEqual(self.json("buscar_itens", {"texto": "sal-007"})["itens"][0]["nome"], "Smart TV 55 polegadas")
        self.assertEqual(self.json("buscar_itens", {"comodo": "Lavanderia"})["encontrados"], 5)
        self.assertEqual(self.json("buscar_itens", {"comodo": "var"})["encontrados"], 3)
        self.assertEqual(self.json("buscar_itens", {"comodo": "escritorio"})["encontrados"], 5)
        self.assertEqual(self.json("buscar_itens", {"comodo": "sala"})["encontrados"], 12, "um pedaço do nome, se for um só")
        r = self.json("buscar_itens", {"categoria": "Eletrônicos", "ordem": "valor"})
        self.assertEqual((r["encontrados"], r["itens"][0]["id"], r["valor_total"]), (6, "esc-001", 10050.0))
        self.assertEqual(self.json("buscar_itens", {"texto": "cozinha bar"})["encontrados"], 7, "a categoria entra no texto, como na tela")

    def test_faixa_de_valor_ordem_e_limite(self):
        r = self.json("buscar_itens", {"valor_min": 1000, "valor_max": 2000, "ordem": "valor", "limite": 3})
        self.assertEqual((r["encontrados"], r["mostrando"]), (8, 3))
        self.assertEqual([i["valor"] for i in r["itens"]], [1900.0, 1800.0, 1600.0])
        self.assertEqual(r["valor_total"], 11500.0, "a soma de todos os encontrados, não só dos mostrados")
        self.assertEqual(self.json("buscar_itens", {"ordem": "nome", "limite": 1})["itens"][0]["nome"], "Abajur com cúpula clara")
        todos = self.json("buscar_itens")
        self.assertEqual((todos["encontrados"], todos["mostrando"]), (38, 38))
        self.assertEqual(todos["itens"][0]["codigo"], "SAL-001")
        self.assertEqual(todos["itens"][-1]["codigo"], "VAR-003")

    def test_quantidade_so_quando_nao_e_1(self):
        livros = self.json("buscar_itens", {"texto": "livros"})["itens"][0]
        self.assertEqual(livros["quantidade"], "28")
        self.assertNotIn("quantidade", self.json("buscar_itens", {"texto": "geladeira"})["itens"][0])

    def test_recentes_primeiro(self):
        self.chamar("cadastrar_itens", {"comodo": "varanda", "itens": [{"nome": "Rede de descanso"}]})
        self.assertEqual(self.json("buscar_itens", {"ordem": "recentes", "limite": 1})["itens"][0]["nome"], "Rede de descanso")

    def test_erros_dizem_o_que_vale(self):
        msg = self.erro("buscar_itens", {"comodo": "Sótão"})
        self.assertIn("Cômodo não encontrado: Sótão. Os cômodos: Sala de estar (SAL), Cozinha (COZ)", msg)
        self.assertIn("Bens (casa, terreno, carro)", msg)
        self.assertIn("Móveis (moveis)", self.erro("buscar_itens", {"categoria": "Ferramentas"}))
        self.erro("buscar_itens", {"limite": 0}, "limite: de 1 a 200.")
        self.erro("buscar_itens", {"limite": 500}, "limite: de 1 a 200.")
        self.erro("buscar_itens", {"ordem": "preco"}, "ordem: codigo, valor, nome ou recentes.")
        self.erro("buscar_itens", {"valor_min": 500, "valor_max": 100}, "valor_max é menor que valor_min.")
        self.erro("buscar_itens", {"valor_min": "muito"}, "Valor inválido")

    def test_bens_sem_area_ainda_nao_acha_nada(self):
        self.assertEqual(self.json("buscar_itens", {"comodo": "Bens"})["encontrados"], 0)
        self.assertIsNone(self.store.bens_room(), "buscar não cria a área")

    def test_bens_desligados_ficam_de_fora(self):
        self.chamar("cadastrar_itens", {"comodo": "Bens", "itens": [{"nome": "Carro de exemplo", "valor": 40000}]})
        self.store.settings["bens"] = False
        self.assertEqual(self.json("buscar_itens", {"texto": "carro"})["encontrados"], 0)
        self.erro("buscar_itens", {"comodo": "Bens"}, "Os bens estão desligados")


class Ver(Base):
    def test_tudo_do_item(self):
        r = self.json("ver_item", {"id": "coz-004"})
        self.assertEqual(r["codigo"], "COZ-004")
        self.assertEqual(r["comodo"], {"id": "cozinha", "codigo": "COZ", "nome": "Cozinha"})
        self.assertEqual(r["categoria"], {"id": "cozinha", "nome": "Cozinha e bar"})
        self.assertEqual((r["valor"], r["quantidade"], r["fotos"], r["valor_desde"]), (2600.0, "1", 1, "2026-10-06"))
        self.assertEqual(r["detalhes"], "Duas portas, cerca de 450 L.")
        self.assertNotIn("zona", r)
        self.assertNotIn("alterado", r)
        self.assertNotIn("valor_de_cada", r)

    def test_pelo_codigo_ou_id_sem_diferenca_de_maiusculas(self):
        for v in ("SAL-012", "sal-012", "Sal-012", " SAL-012 "):
            with self.subTest(v=v):
                self.assertEqual(self.json("ver_item", {"id": v})["id"], "sal-012")

    def test_valor_de_cada_unidade(self):
        self.assertEqual(self.json("ver_item", {"id": "sal-012"})["valor_de_cada"], 20.0)

    def test_zona_com_zonas_e_quem_alterou(self):
        self.store.settings["zones"] = True
        self.chamar("editar_item", {"id": "sal-001", "valor": 1500}, cliente="Gemini")
        r = self.json("ver_item", {"id": "sal-001"})
        self.assertEqual(r["zona"], "Sofá")
        self.assertEqual(r["alterado"]["por"], "Ana")

    def test_item_que_nao_existe(self):
        self.erro("ver_item", {"id": "XYZ-999"}, "Item não encontrado: XYZ-999. Busque o id com inventario_buscar_itens.")


class Cadastrar(Base):
    def test_cadastra_com_o_proximo_codigo_quem_e_a_origem(self):
        antes = self.rev()
        txt = self.chamar("cadastrar_itens", {"comodo": "SAL", "itens": [{"nome": "Abajur de mesa", "valor": 120, "categoria": "decoração"},
                                                                         {"nome": "Vaso de vidro", "valor": "1.200,50", "quantidade": 2}]})
        self.assertEqual(self.rev(), antes + 1, "o lote grava uma vez só")
        a, v = self.item("sal-013"), self.item("sal-014")
        self.assertEqual((a["name"], a["cat"], a["value"], a["source"], a["createdBy"]), ("Abajur de mesa", "decoracao", 120, "correria", "Ana"))
        self.assertEqual((v["value"], v["qty"], v["cat"], v["zone"]), (1200.5, "2", "outros", ""))
        self.assertTrue(a["valueAt"])
        self.assertIn("Cadastrados 2 itens em Sala de estar: Abajur de mesa (SAL-013, Sala de estar, R$ 120, id sal-013)", txt)
        self.assertIn("Total: R$ 1.320,50.", txt)

    def test_um_item_so(self):
        txt = self.chamar("cadastrar_itens", {"comodo": "varanda", "itens": [{"nome": "Rede", "valor": 80, "detalhes": "Algodão cru\nlistrada",
                                                                             "observacao": "Lavar à mão"}]})
        it = self.item("var-004")
        self.assertEqual((it["details"], it["flag"]), ("Algodão cru\nlistrada", "Lavar à mão"))
        self.assertTrue(txt.startswith("Cadastrado em Varanda: Rede (VAR-004"))

    def test_quem_e_o_cliente_sem_pessoa(self):
        self.chamar("cadastrar_itens", {"comodo": "varanda", "itens": [{"nome": "Rede"}]}, pessoa=None, cliente="WhatsApp")
        self.assertEqual(self.item("var-004")["createdBy"], "WhatsApp")

    def test_quantidade_numero(self):
        self.chamar("cadastrar_itens", {"comodo": "varanda", "itens": [{"nome": "Cadeira", "quantidade": 4.0}, {"nome": "Banco", "quantidade": 2}]})
        self.assertEqual((self.item("var-004")["qty"], self.item("var-005")["qty"]), ("4", "2"))

    def test_lote_com_um_item_ruim_nao_grava_nada(self):
        antes = (self.rev(), len(self.store.data["items"]))
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Bom"}, {"nome": "Ruim", "valor": "caro"}]}, "Item 2: Valor inválido")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Bom"}, {"nome": ""}]}, "Item 2: Preencha o campo nome.")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Bom"}, {"nome": "X", "categoria": "Ferramentas"}]}, "Item 2: Categoria não encontrada")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Bom", "foto": "a.jpg"}]}, "Item 1: campo desconhecido: foto")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": ["Abajur"]}, "Item 1: mande um objeto")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "N" * 201}]}, "passou do limite de 200")
        self.assertEqual((self.rev(), len(self.store.data["items"])), antes)

    def test_limite_do_lote(self):
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": f"Item {n}"} for n in range(31)]}, "No máximo 30")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": "Abajur"}, "Mande os itens numa lista")

    def test_zona_so_com_zonas_ligadas(self):
        self.erro("cadastrar_itens", {"comodo": "sala", "zona": "Rack", "itens": [{"nome": "Roteador"}]}, "As zonas estão desligadas")
        self.erro("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Roteador", "zona": "Rack"}]}, "Item 1: As zonas estão desligadas")
        self.store.settings["zones"] = True
        self.chamar("cadastrar_itens", {"comodo": "sala", "zona": "Rack", "itens": [{"nome": "Roteador"}, {"nome": "Quadro", "zona": "Parede"}]})
        self.assertEqual((self.item("sal-013")["zone"], self.item("sal-014")["zone"]), ("Rack", "Parede"))

    def test_o_primeiro_bem_cria_a_area_bens(self):
        txt = self.chamar("cadastrar_itens", {"comodo": "Bens", "itens": [{"nome": "Apartamento de exemplo", "valor": 300000, "categoria": "Imóveis"}]})
        area = self.store.bens_room()
        self.assertEqual((area["code"], area["kind"]), ("BEN", "bens"))
        it = self.item("ben-001")
        self.assertEqual((it["room"], it["cat"], it["zone"]), (area["id"], "imoveis", ""))
        self.assertIn("Cadastrado em Bens: Apartamento de exemplo (BEN-001", txt)
        self.chamar("cadastrar_itens", {"comodo": "bens", "itens": [{"nome": "Carro de exemplo"}]})
        self.assertEqual(len([r for r in self.store.data["rooms"] if r.get("kind") == "bens"]), 1, "a mesma área")

    def test_bem_sem_zona_e_bens_desligados(self):
        self.store.settings["zones"] = True
        self.erro("cadastrar_itens", {"comodo": "Bens", "zona": "Garagem", "itens": [{"nome": "Carro"}]}, "Um bem não tem zona")
        self.assertIsNone(self.store.bens_room(), "nada criado antes de conferir")
        self.store.settings["bens"] = False
        self.erro("cadastrar_itens", {"comodo": "Bens", "itens": [{"nome": "Carro"}]}, "Os bens estão desligados")

    def test_avisa_de_um_item_igual_no_comodo(self):
        txt = self.chamar("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "smart tv 55 polegadas"}]})
        self.assertIn("Atenção: já havia Smart TV 55 polegadas (SAL-007, id sal-007) em Sala de estar.", txt)
        self.assertIsNotNone(self.item("sal-013"), "cadastra mesmo assim: pode ser outra igual")

    def test_versao_automatica_antes_de_gravar(self):
        self.assertEqual(self.store.history_list(details=False), [])
        self.chamar("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Abajur"}]})
        self.assertEqual(len(self.store.history_list(details=False)), 1, "como na tela: a cópia de antes da mudança")


class Editar(Base):
    def test_valor_novo_muda_a_data_do_valor(self):
        with mock.patch.object(S, "now_iso", return_value="2026-11-15T10:00:00-03:00"):
            txt = self.chamar("editar_item", {"id": "SAL-001", "valor": 1500})
        it = self.item("sal-001")
        self.assertEqual((it["value"], it["valueAt"], it["updatedBy"]), (1500, "2026-11-15T10:00:00-03:00", "Ana"))
        self.assertEqual(txt, "Alterado: Sofá de 3 lugares cinza-azulado (SAL-001, Sala de estar, R$ 1.500, id sal-001). valor: R$ 1.800 → R$ 1.500.")

    def test_so_o_nome_nao_muda_a_data_do_valor(self):
        self.chamar("editar_item", {"id": "sal-001", "nome": "Sofá azul", "categoria": "Decoração e arte", "quantidade": 2})
        it = self.item("sal-001")
        self.assertEqual((it["name"], it["cat"], it["qty"]), ("Sofá azul", "decoracao", "2"))
        self.assertNotIn("valueAt", it)

    def test_textos_e_apagar_com_vazio(self):
        self.chamar("editar_item", {"id": "sal-001", "observacao": "Comprado em promoção", "detalhes": "Linho"})
        self.assertEqual((self.item("sal-001")["flag"], self.item("sal-001")["details"]), ("Comprado em promoção", "Linho"))
        txt = self.chamar("editar_item", {"id": "sal-001", "observacao": "", "detalhes": ""})
        self.assertEqual((self.item("sal-001")["flag"], self.item("sal-001")["details"]), (None, ""))
        self.assertIn('observação: "Comprado em promoção" → (vazio)', txt)

    def test_nada_mudou_nao_grava(self):
        antes = (self.rev(), self.item("sal-001")["updatedAt"])
        txt = self.chamar("editar_item", {"id": "sal-001", "valor": 1800.0, "nome": "Sofá de 3 lugares cinza-azulado", "categoria": "moveis"})
        self.assertTrue(txt.startswith("Nada mudou"))
        self.assertEqual((self.rev(), self.item("sal-001")["updatedAt"]), antes)

    def test_erros(self):
        self.erro("editar_item", {"id": "sal-001"}, "Diga o que muda")
        self.erro("editar_item", {"id": "sal-001", "valor": "abc"}, "Valor inválido")
        self.erro("editar_item", {"id": "sal-001", "valor": None}, "mande 0")
        self.erro("editar_item", {"id": "sal-001", "valor": -5}, "Valor fora do intervalo")
        self.erro("editar_item", {"id": "sal-001", "nome": ""}, "Preencha o campo nome.")
        self.erro("editar_item", {"id": "sal-001", "categoria": ""}, "mande Outros")
        self.erro("editar_item", {"id": "sal-001", "zona": "Rack"}, "As zonas estão desligadas")
        self.erro("editar_item", {"id": "sal-001", "valor": True}, "Valor inválido")
        self.erro("editar_item", {"id": "nada", "valor": 1}, "Item não encontrado")

    def test_zona_com_zonas_ligadas(self):
        self.store.settings["zones"] = True
        self.chamar("editar_item", {"id": "sal-001", "zona": "Janela"})
        self.assertEqual(self.item("sal-001")["zone"], "Janela")


class Mover(Base):
    def test_outro_comodo_codigo_novo_mesmo_id_sem_zona(self):
        txt = self.chamar("mover_itens", {"ids": ["sal-009", "SAL-010"], "comodo": "Escritório"})
        a, b = self.item("sal-009"), self.item("sal-010")
        self.assertEqual((a["room"], self.store.tag(a), a["zone"]), ("escritorio", "ESC-006", ""))
        self.assertEqual(self.store.tag(b), "ESC-007")
        self.assertIn("Movidos 2 itens para Escritório: Soundbar (SAL-009 → ESC-006, id sal-009)", txt)
        self.chamar("cadastrar_itens", {"comodo": "sala", "itens": [{"nome": "Abajur"}]})
        self.assertEqual(self.store.tag(self.store.data["items"][-1]), "SAL-013", "o número que saiu não volta (o ResolvIA liga pelo id)")

    def test_um_id_em_texto_e_repetidos_uma_vez(self):
        txt = self.chamar("mover_itens", {"ids": "sal-009", "comodo": "esc"})
        self.assertIn("Movido para Escritório", txt)
        txt = self.chamar("mover_itens", {"ids": ["sal-010", "SAL-010", "sal-010"], "comodo": "esc"})
        self.assertIn("Movido para Escritório: Caixa de som de estante (SAL-010 → ESC-007", txt)

    def test_ja_estava_la(self):
        antes = self.rev()
        txt = self.chamar("mover_itens", {"ids": ["sal-001"], "comodo": "sala"})
        self.assertTrue(txt.startswith("Já estava lá: Sofá"))
        self.assertEqual(self.rev(), antes)

    def test_zona_no_mesmo_ou_em_outro_comodo(self):
        self.store.settings["zones"] = True
        self.chamar("mover_itens", {"ids": ["sal-001"], "comodo": "sala", "zona": "Janela"})
        self.assertEqual((self.item("sal-001")["zone"], self.store.tag(self.item("sal-001"))), ("Janela", "SAL-001"))
        self.chamar("mover_itens", {"ids": ["sal-001"], "comodo": "quarto"})
        self.assertEqual(self.item("sal-001")["zone"], "", "num cômodo novo, sem dizer a zona, ela sai")
        self.chamar("mover_itens", {"ids": ["sal-002"], "comodo": "quarto", "zona": "Cama"})
        self.assertEqual(self.item("sal-002")["zone"], "Cama")

    def test_um_id_ruim_nao_move_nenhum(self):
        antes = self.rev()
        self.erro("mover_itens", {"ids": ["sal-001", "nada"], "comodo": "quarto"}, "Item não encontrado: nada")
        self.assertEqual((self.rev(), self.item("sal-001")["room"]), (antes, "sala"))
        self.erro("mover_itens", {"ids": ["sal-001"], "comodo": "Sótão"}, "Cômodo não encontrado")
        self.erro("mover_itens", {"ids": [f"x{n}" for n in range(61)], "comodo": "sala"}, "No máximo 60")
        self.erro("mover_itens", {"ids": ["sal-001"], "comodo": "sala", "zona": "Rack"}, "As zonas estão desligadas")

    def test_para_bens_cria_a_area(self):
        self.chamar("mover_itens", {"ids": ["var-002"], "comodo": "Bens"})
        self.assertEqual(self.store.tag(self.item("var-002")), "BEN-001")


class Apagar(Base):
    def test_apaga_e_devolve_os_dados(self):
        antes = self.rev()
        txt = self.chamar("apagar_item", {"id": "QUA-004"})
        self.assertIsNone(self.item("qua-004"))
        self.assertEqual(self.rev(), antes + 1)
        self.assertTrue(txt.startswith("Apagado: Abajur com cúpula clara (QUA-004, Quarto, quantidade 2, R$ 180, id qua-004)."))
        dados = json.loads(txt.split("Para cadastrar de novo: ", 1)[1])
        self.assertEqual(dados, {"nome": "Abajur com cúpula clara", "comodo": "Quarto", "valor": 180.0, "quantidade": "2", "categoria": "Decoração e arte",
                                 "detalhes": "Base de cerâmica creme."})

    def test_item_que_nao_existe(self):
        self.erro("apagar_item", {"id": "qua-099"}, "Item não encontrado")


class NovoComodo(Base):
    def test_codigo_como_a_tela_sugere(self):
        txt = self.chamar("novo_comodo", {"nome": "Garagem"})
        r = self.store.room("garagem")
        self.assertEqual((r["name"], r["code"]), ("Garagem", "GAR"))
        self.assertEqual(txt, "Cômodo criado: Garagem, código GAR. Os itens vão ser GAR-001, GAR-002… id garagem")

    def test_codigo_dado_e_codigo_ja_usado(self):
        self.chamar("novo_comodo", {"nome": "Área de serviço", "codigo": "as"})
        self.assertEqual(self.store.room("area-de-servico")["code"], "AS")
        txt = self.chamar("novo_comodo", {"nome": "Sala de jantar", "codigo": "SAL"})
        self.assertIn("código SAL2 (SAL já era de outro cômodo)", txt)

    def test_erros(self):
        self.erro("novo_comodo", {"nome": "cozinha"}, "Já existe o cômodo Cozinha (COZ, id cozinha).")
        self.erro("novo_comodo", {"nome": "Bens"}, "Bens é a área do que fica fora de casa")
        self.erro("novo_comodo", {"nome": "Sótão", "codigo": "!!"}, "de 1 a 4 letras ou números")
        self.erro("novo_comodo", {"nome": "Sótão", "codigo": "SOTAO"}, "passou do limite de 4")
        self.erro("novo_comodo", {"nome": "N" * 61}, "passou do limite de 60")


class ConexaoCorreria(UnitBase):
    def ler(self, c):
        with open(c.arq_share, encoding="utf-8") as f:
            return json.load(f)

    def test_desligado_de_inicio(self):
        self.assertFalse(S.correria_enabled())
        self.assertIsNone(S.correria_uso())

    def test_chave_e_arquivo_proprios(self):
        c = S.correria_conexao()
        self.assertEqual(c.arq_chave, os.path.join(S.DATA_DIR, "correria.key"))
        self.assertEqual(c.arq_share, os.path.join(S.SHARE_DIR, "correria.json"))
        self.assertNotEqual(c.chave(), S.Conexao().chave(), "a chave do CorrerIA não abre o resto (nem o contrário)")
        self.assertEqual(stat.S_IMODE(os.stat(c.arq_chave).st_mode), 0o600)

    def test_ligado_grava_o_arquivo_do_contrato(self):
        c = S.correria_conexao()
        with mock.patch.object(c, "endereco", return_value=("http://inventaria-teste:8099", "172.30.33.5")):
            c.publicar(True)
        info = self.ler(c)
        self.assertEqual(set(info), {"app", "nome", "assunto", "url", "ip_url", "chave", "versao", "ferramentas", "gravado_em"})
        self.assertEqual((info["app"], info["nome"], info["ferramentas"], info["versao"]), ("inventario", "InventarIA", "/api/integracao/ferramentas", S.VERSION))
        self.assertRegex(info["app"], r"^[a-z0-9]+$")
        self.assertEqual((info["url"], info["ip_url"], info["chave"]), ("http://inventaria-teste:8099", f"http://172.30.33.5:{S.PORT}", c.chave()))
        self.assertNotIn("rota", info, "só o GerencIA conversa pelo WhatsApp")
        self.assertEqual(stat.S_IMODE(os.stat(c.arq_share).st_mode), 0o600)
        self.assertFalse(os.path.exists(c.arq_share + ".tmp"), "grava num temporário e troca de nome")

    def test_desligado_apaga_o_arquivo(self):
        c = S.correria_conexao()
        c.publicar(True)
        c.publicar(False)
        self.assertFalse(os.path.exists(c.arq_share))
        c.publicar(False)  # já sem arquivo: nada acontece

    def test_publicar_segue_a_opcao(self):
        S.correria_publicar()
        self.assertFalse(os.path.exists(S.CORRERIA.arq_share))
        self.store.settings["correria"] = True
        S.correria_publicar()
        self.assertTrue(os.path.exists(S.CORRERIA.arq_share))

    def test_integracao_json_continua_igual(self):
        c = S.Conexao()
        c.publicar()
        self.assertEqual((self.ler(c)["app"], self.ler(c)["nome"]), ("inventario", "InventarIA"), "o ResolvIA e o GerencIA leem este arquivo (não olham o app)")
        self.assertNotIn("ferramentas", self.ler(c))

    def test_autorizado_sem_marcar_nao_guarda_o_ultimo(self):
        c = S.correria_conexao()
        self.assertTrue(c.autorizado({"Authorization": f"Bearer {c.chave()}", "X-App": "CorrerIA"}, marcar=False))
        self.assertIsNone(c.ultimo)

    def test_ultimo_uso_vem_do_arquivo(self):
        with open(os.path.join(S.DATA_DIR, "correria_uso.json"), "w", encoding="utf-8") as f:
            json.dump({"app": "Claude", "em": "2026-11-08T09:41:00-03:00", "nome": "resumo"}, f)
        self.assertEqual(S.correria_uso()["app"], "Claude")
        with open(os.path.join(S.DATA_DIR, "correria_uso.json"), "w", encoding="utf-8") as f:
            f.write("{quebrado")
        self.assertIsNone(S.correria_uso())


class Origem(UnitBase):
    def test_origem_correria_na_tela(self):
        with open(os.path.join(os.path.dirname(S.__file__), "web", "app.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertTrue(re.search(r'correria: "Pelo CorrerIA"', js), "a ficha diz de onde veio o item")


if __name__ == "__main__":
    unittest.main()
