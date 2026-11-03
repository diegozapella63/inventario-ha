"""Leitura por IA no servidor: as instruções mandadas à IA (ai_prompt), o JSON tirado da resposta (extract_json)
e os itens limpos que a tela recebe (clean_ai_items). Complementa o test_ia.py, sem repetir o que ele já confere."""
import json
import unittest

from _boot import UnitBase, server as S

# os itens da sala na casa de teste, do mais caro para o mais barato
SALA_POR_VALOR = ["Smart TV 55 polegadas", "Sofá de 3 lugares cinza-azulado", "Soundbar", "Livros variados",
                  "Estante de madeira com três prateleiras", "Rack de madeira com três portas", "Tapete listrado",
                  "Caixa de som de estante", "Luminária de chão com cúpula de tecido", "Quadro de paisagem com moldura preta",
                  "Costela-de-adão em vaso de cerâmica", "Almofadas decorativas"]
SOFA = "Sofá de 3 lugares cinza-azulado"
GARAGEM = {"id": "garagem", "name": "Garagem"}  # cômodo inventado, sem itens na casa de teste


def formato_pedido(prompt: str) -> dict:
    """O modelo de resposta em JSON que vai no fim das regras."""
    linha = next(ln for ln in prompt.splitlines() if ln.startswith('{"items":'))
    return json.loads(linha)["items"][0]


class InstrucoesFotoUnica(UnitBase):
    def test_foto_unica_nao_pede_lista_de_ate_25(self):
        p = S.ai_prompt("single", None, "")
        self.assertNotIn("até 25", p)
        self.assertNotIn("Ignore paredes", p)

    def test_foto_unica_com_comodo_traz_o_nome_mas_nao_os_itens(self):
        p = S.ai_prompt("single", self.store.room("sala"), "")
        self.assertIn("Cômodo: Sala de estar.", p)
        self.assertNotIn("Itens já cadastrados", p, "uma foto só não compara com o que já existe")

    def test_foto_unica_com_zonas_ligadas_traz_as_zonas_do_comodo(self):
        self.store.settings["zones"] = True
        p = S.ai_prompt("single", self.store.room("cozinha"), "")
        self.assertIn("Zonas já usadas neste cômodo (prefira uma delas): Armário; Bancada; Geladeira; Mesa.", p)

    def test_foto_unica_nao_lista_os_comodos_da_casa(self):
        p = S.ai_prompt("single", None, "")
        self.assertNotIn("Cômodos da casa", p)
        self.assertNotIn('"room"', p)


class InstrucoesCatalogo(UnitBase):
    def test_catalogo_ignora_paredes_tomadas_e_embalagens(self):
        p = S.ai_prompt("multi", None, "")
        self.assertIn("Ignore paredes, piso, tomadas, interruptores, embalagens vazias", p)
        self.assertIn("Junte objetos iguais num item só, com a quantidade.", p)

    def test_catalogo_sem_comodo_nao_traz_comodo_nem_itens(self):
        p = S.ai_prompt("multi", None, "")
        self.assertNotIn("Cômodo:", p)
        self.assertNotIn("Itens já cadastrados", p)

    def test_catalogo_lista_os_itens_do_mais_caro_para_o_mais_barato(self):
        p = S.ai_prompt("multi", self.store.room("sala"), "")
        self.assertIn("Itens já cadastrados neste cômodo: " + "; ".join(SALA_POR_VALOR) + ".", p)

    def test_catalogo_lista_so_os_itens_do_proprio_comodo(self):
        p = S.ai_prompt("multi", self.store.room("cozinha"), "")
        self.assertIn("Geladeira frost free inox", p)
        self.assertNotIn("Smart TV", p)
        self.assertNotIn("Notebook", p)

    def test_catalogo_de_comodo_sem_itens_nao_traz_lista(self):
        p = S.ai_prompt("multi", GARAGEM, "")
        self.assertIn("Cômodo: Garagem.", p)
        self.assertNotIn("Itens já cadastrados", p)

    def test_catalogo_lista_no_maximo_150_itens(self):
        for n in range(160):
            self.store.data["items"].append({"id": f"gar-{n:03d}", "room": "garagem", "name": f"Ferramenta {n:03d}", "value": 1000 - n})
        p = S.ai_prompt("multi", GARAGEM, "")
        linha = next(ln for ln in p.split("\n\n") if ln.startswith("Itens já cadastrados"))
        nomes = linha.split(": ", 1)[1].rstrip(".").split("; ")
        self.assertEqual(len(nomes), 150)
        self.assertEqual((nomes[0], nomes[-1]), ("Ferramenta 000", "Ferramenta 149"), "ficam de fora os mais baratos")

    def test_item_sem_valor_vai_para_o_fim_da_lista(self):
        self.store.data["items"] += [{"id": "g1", "room": "garagem", "name": "Escada", "value": None},
                                     {"id": "g2", "room": "garagem", "name": "Furadeira", "value": 300},
                                     {"id": "g3", "room": "garagem", "name": "Trena"}]
        p = S.ai_prompt("multi", GARAGEM, "")
        self.assertIn("Itens já cadastrados neste cômodo: Furadeira; Escada; Trena.", p)

    def test_modo_desconhecido_vira_catalogo(self):
        p = S.ai_prompt("qualquer", None, "")
        self.assertIn("até 25", p)
        self.assertIn("Ignore paredes", p)
        self.assertNotIn("exatamente 1 item", p)


class InstrucoesFala(UnitBase):
    def test_fala_lista_os_seis_comodos_na_ordem_da_casa(self):
        p = S.ai_prompt("voice", None, "", "um sofá")
        self.assertIn("Cômodos da casa (id = nome): sala = Sala de estar; cozinha = Cozinha; quarto = Quarto; "
                      "escritorio = Escritório; lavanderia = Lavanderia; varanda = Varanda.", p)
        self.assertIn('responda também "room" com o id desse cômodo', p)

    def test_fala_em_casa_sem_comodos_nao_pede_o_comodo(self):
        self.store.data["rooms"] = []
        p = S.ai_prompt("voice", None, "", "um sofá")
        self.assertNotIn("Cômodos da casa", p)
        self.assertNotIn('"room"', p)

    def test_fala_com_comodo_traz_os_itens_ja_cadastrados(self):
        p = S.ai_prompt("voice", self.store.room("varanda"), "", "uma rede")
        self.assertIn("Cômodo: Varanda.", p)
        self.assertIn("Itens já cadastrados neste cômodo: Bicicleta aro 29; Mesa bistrô com 2 cadeiras; Vasos com plantas.", p)

    def test_fala_pede_para_corrigir_o_que_a_transcricao_trocou(self):
        self.assertIn("Corrija nomes, marcas e modelos que a transcrição claramente trocou.", S.ai_prompt("voice", None, "", "x"))
        self.assertNotIn("transcrição", S.ai_prompt("multi", None, ""))

    def test_valor_dito_so_vale_nas_instrucoes_da_fala(self):
        for mode in ("single", "multi"):
            with self.subTest(mode=mode):
                self.assertNotIn("use exatamente esse valor", S.ai_prompt(mode, None, ""))

    def test_o_que_foi_falado_vem_por_ultimo_depois_da_dica(self):
        p = S.ai_prompt("voice", None, "é tudo da sala", "sofá e tapete")
        self.assertLess(p.index("Dica de quem está cadastrando: é tudo da sala"), p.index("O que a pessoa falou:"))
        self.assertTrue(p.endswith("O que a pessoa falou:\nsofá e tapete"))


class InstrucoesDicaZonasCategorias(UnitBase):
    def test_sem_dica_nao_tem_linha_de_dica(self):
        self.assertNotIn("Dica de quem está cadastrando", S.ai_prompt("multi", self.store.room("sala"), ""))

    def test_dica_com_chaves_e_aspas_vai_como_foi_escrita(self):
        dica = 'tem {chaves}, {cats} e "aspas"'
        self.assertIn(f"Dica de quem está cadastrando: {dica}", S.ai_prompt("single", None, dica))

    def test_zonas_desligadas_tiram_a_zona_do_modelo_de_resposta(self):
        p = S.ai_prompt("multi", self.store.room("sala"), "")
        self.assertEqual(list(formato_pedido(p)), ["name", "details", "cat", "qty", "value", "existing", "confidence"])
        self.assertNotIn('Eletrônicos e aparelhos de saúde usam "Eletrônicos"', p)

    def test_zonas_ligadas_pedem_a_zona_no_modelo_de_resposta(self):
        self.store.settings["zones"] = True
        p = S.ai_prompt("single", None, "")
        self.assertEqual(list(formato_pedido(p)), ["name", "details", "cat", "qty", "value", "zone", "existing", "confidence"])
        self.assertIn('Eletrônicos e aparelhos de saúde usam "Eletrônicos"', p)

    def test_zonas_ligadas_em_comodo_sem_zonas_nao_traz_a_linha(self):
        self.store.settings["zones"] = True
        self.store.data["items"].append({"id": "g1", "room": "garagem", "name": "Escada", "value": 100, "zone": ""})
        self.assertNotIn("Zonas já usadas", S.ai_prompt("multi", GARAGEM, ""))

    def test_categorias_padrao_na_ordem_com_outros_no_fim(self):
        p = S.ai_prompt("multi", None, "")
        esperado = ", ".join(f"{k} ({v})" for k, v in S.CATS.items())
        self.assertIn(f'- "cat": uma destas chaves: {esperado}.', p)
        self.assertTrue(esperado.endswith("outros (Outros)"))

    def test_categoria_renomeada_vai_com_o_nome_novo(self):
        self.store.update_cat("moveis", {"name": "Mobília"})
        p = S.ai_prompt("multi", None, "")
        self.assertIn("moveis (Mobília)", p)
        self.assertNotIn("moveis (Móveis)", p)

    def test_categoria_excluida_some_das_instrucoes(self):
        self.store.delete_cat("pets")
        self.assertNotIn("pets (", S.ai_prompt("single", None, ""))

    def test_todas_as_instrucoes_proibem_dados_pessoais(self):
        for mode in ("single", "multi", "voice"):
            with self.subTest(mode=mode):
                self.assertIn("Nunca inclua número de série, IMEI, telefone, nome de pessoa ou endereço.", S.ai_prompt(mode, None, "", "x"))

    def test_instrucoes_comecam_pelo_papel_da_ia(self):
        for mode in ("single", "multi", "voice"):
            with self.subTest(mode=mode):
                self.assertTrue(S.ai_prompt(mode, None, "").startswith("Você ajuda a catalogar o inventário de uma casa no Brasil"))


class JsonDaResposta(UnitBase):
    def test_objeto_ja_decodificado_volta_o_mesmo(self):
        obj = {"items": [{"name": "Sofá"}]}
        self.assertIs(S.extract_json(obj), obj)

    def test_cerca_markdown_em_maiusculas(self):
        self.assertEqual(S.extract_json('```JSON\n{"items": []}\n```'), {"items": []})

    def test_cerca_markdown_no_meio_do_texto(self):
        raw = 'Segue a lista:\n```json\n{"items": [{"name": "Vaso"}]}\n```\nQualquer dúvida, pergunte.'
        self.assertEqual(S.extract_json(raw), {"items": [{"name": "Vaso"}]})

    def test_lista_em_texto_volta_lista(self):
        self.assertEqual(S.extract_json('[{"name": "A"}, {"name": "B"}]'), [{"name": "A"}, {"name": "B"}])

    def test_aspas_tipograficas_dentro_do_texto_ficam(self):
        out = S.extract_json('{"items": [{"name": "Quadro “Paisagem”", "details": "moldura ‘preta’"}]}')
        self.assertEqual(out["items"][0]["name"], "Quadro “Paisagem”")
        self.assertEqual(out["items"][0]["details"], "moldura ‘preta’")

    def test_aspas_tipograficas_no_lugar_das_aspas_sao_recusadas(self):
        raw = "{“items”: [{“name”: “Sofá”}]}"
        e = self.assertApiError(502, S.extract_json, raw, msg_part="Não deu para entender")
        self.assertEqual(e.extra["raw"], raw, "a resposta vai junto para a tela mostrar")

    def test_resposta_vazia_e_recusada(self):
        e = self.assertApiError(502, S.extract_json, "", msg_part="sem uma lista de itens")
        self.assertEqual(e.extra["raw"], "")

    def test_so_espacos_conta_como_vazia(self):
        e = self.assertApiError(502, S.extract_json, "  \n\t ", msg_part="sem uma lista de itens")
        self.assertEqual(e.extra["raw"], "")

    def test_dois_objetos_seguidos_fica_o_primeiro(self):
        self.assertEqual(S.extract_json('{"items": [{"name": "A"}]} {"items": [{"name": "B"}]}'), {"items": [{"name": "A"}]})

    def test_virgula_sobrando_e_recusada(self):
        self.assertApiError(502, S.extract_json, '{"items": [{"name": "A"},]}', msg_part="Não deu para entender")

    def test_json_cortado_no_meio_e_recusado(self):
        e = self.assertApiError(502, S.extract_json, '{"items": [{"name": "Sofá", "details": "cin', msg_part="Não deu para entender")
        self.assertIn("Sofá", e.extra["raw"])

    def test_resposta_enorme_valida_com_texto_depois(self):
        itens = [{"name": f"Item {n}", "details": "d" * 1000, "value": n} for n in range(25)]
        raw = json.dumps({"items": itens}, ensure_ascii=False) + "\n\nObservação: " + "texto " * 500
        out = S.extract_json(raw)
        self.assertEqual(len(out["items"]), 25)
        self.assertEqual(out["items"][24]["value"], 24)

    def test_resposta_enorme_sem_json_guarda_so_2000_caracteres(self):
        e = self.assertApiError(502, S.extract_json, "Não consigo. " * 600)
        self.assertEqual(len(e.extra["raw"]), 2000)

    def test_resposta_enorme_quebrada_guarda_so_2000_caracteres(self):
        e = self.assertApiError(502, S.extract_json, "{" + '"a": 1, ' * 1000, msg_part="Não deu para entender")
        self.assertEqual(len(e.extra["raw"]), 2000)

    def test_json_que_nao_e_objeto_nem_lista_nao_vira_item(self):
        for raw in ("42", '"oi"', "true", "null"):
            with self.subTest(raw=raw):
                self.assertApiError(502, S.clean_ai_items, S.extract_json(raw), None, msg_part="não devolveu itens")


class ItensLimpos(UnitBase):
    def limpa(self, item: dict, room=None) -> dict:
        out = S.clean_ai_items({"items": [item]}, room)
        self.assertEqual(len(out), 1, "o item devia ter passado")
        return out[0]

    def test_saida_tem_sempre_os_oito_campos(self):
        out = self.limpa({"name": "Banco", "preco": 10, "marca": "X", "serial": "abc"})
        self.assertEqual(sorted(out), ["cat", "confidence", "details", "existing", "name", "qty", "value", "zone"], "campos a mais ficam de fora")

    def test_nome_vazio_so_espacos_ou_ausente_sai(self):
        out = S.clean_ai_items({"items": [{"name": ""}, {"name": "   "}, {"name": None}, {"details": "sem nome"}, {"name": "Banco"}]}, None)
        self.assertEqual([o["name"] for o in out], ["Banco"])

    def test_nome_em_numero_vira_texto(self):
        self.assertEqual(self.limpa({"name": 2024})["name"], "2024")

    def test_ordem_da_ia_e_mantida(self):
        out = S.clean_ai_items({"items": [{"name": n} for n in ("Cadeira", "Abajur", "Mesa")]}, None)
        self.assertEqual([o["name"] for o in out], ["Cadeira", "Abajur", "Mesa"])

    def test_categoria_criada_na_casa_e_aceita(self):
        self.store.create_cat({"name": "Oficina"})
        self.assertEqual(self.limpa({"name": "Furadeira", "cat": "oficina"})["cat"], "oficina")

    def test_categoria_excluida_vira_outros(self):
        self.store.delete_cat("pets")
        self.assertEqual(self.limpa({"name": "Casinha de cachorro", "cat": "pets"})["cat"], "outros")

    def test_categoria_vazia_ou_ausente_vira_outros(self):
        for cat in ("", None):
            with self.subTest(cat=cat):
                self.assertEqual(self.limpa({"name": "Coisa", "cat": cat})["cat"], "outros")
        self.assertEqual(self.limpa({"name": "Coisa"})["cat"], "outros")

    def test_categoria_em_lista_ou_objeto_vira_outros(self):
        out = S.clean_ai_items({"items": [{"name": "Sofá", "cat": ["moveis"]}, {"name": "Vaso", "cat": {"id": "decoracao"}}]}, None)
        self.assertEqual([o["cat"] for o in out], ["outros", "outros"])

    def test_quantidade_em_numero_vira_texto(self):
        self.assertEqual(self.limpa({"name": "Cadeira", "qty": 4})["qty"], "4")

    def test_quantidade_zero_vazia_ou_ausente_vira_um(self):
        for qty in (0, "", "   ", None):
            with self.subTest(qty=qty):
                self.assertEqual(self.limpa({"name": "Cadeira", "qty": qty})["qty"], "1")

    def test_quantidade_com_unidade_fica_como_veio(self):
        self.assertEqual(self.limpa({"name": "Brincos", "qty": " 1 par "})["qty"], "1 par")

    def test_valor_em_texto_com_reais_milhar_e_centavos(self):
        self.assertEqual(self.limpa({"name": "Sofá", "value": "R$ 1.200,50"})["value"], 1200.5)

    def test_valor_negativo_vira_zero(self):
        self.assertEqual(self.limpa({"name": "Sofá", "value": -300})["value"], 0)

    def test_valor_acima_de_um_bilhao_vira_zero(self):
        self.assertEqual(self.limpa({"name": "Quadro", "value": 5e9})["value"], 0)

    def test_valor_nan_vindo_do_json_vira_zero(self):
        parsed = S.extract_json('{"items": [{"name": "Vaso", "value": NaN}]}')
        self.assertEqual(S.clean_ai_items(parsed, None)[0]["value"], 0)

    def test_valor_verdadeiro_ou_lista_vira_zero(self):
        for v in (True, [100], {"valor": 100}):
            with self.subTest(v=v):
                self.assertEqual(self.limpa({"name": "Vaso", "value": v})["value"], 0)

    def test_zona_aparada_e_ausente_vira_vazia(self):
        self.assertEqual(self.limpa({"name": "Livro", "zone": "  Estante  "})["zone"], "Estante")
        self.assertEqual(self.limpa({"name": "Livro"})["zone"], "")

    def test_detalhes_ausentes_viram_texto_vazio(self):
        self.assertEqual(self.limpa({"name": "Livro", "details": None})["details"], "")

    def test_confianca_em_maiusculas_ou_com_acento(self):
        casos = {"ALTA": "alta", "Média": "media", "MÉDIA": "media", "Baixa": "baixa"}
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(self.limpa({"name": "X", "confidence": entrada})["confidence"], esperado)

    def test_confianca_ausente_ou_em_numero_vira_media(self):
        for conf in (None, 0.9, ""):
            with self.subTest(conf=conf):
                self.assertEqual(self.limpa({"name": "X", "confidence": conf})["confidence"], "media")

    def test_existing_com_espacos_nas_pontas_ainda_casa(self):
        out = self.limpa({"name": "Sofá", "existing": f"  {SOFA}  "}, self.store.room("sala"))
        self.assertEqual(out["existing"], SOFA)

    def test_existing_de_outro_comodo_nao_casa(self):
        out = self.limpa({"name": "TV", "existing": "Smart TV 55 polegadas"}, self.store.room("quarto"))
        self.assertEqual(out["existing"], "")

    def test_existing_em_lista_nao_casa(self):
        out = self.limpa({"name": "Sofá", "existing": [SOFA]}, self.store.room("sala"))
        self.assertEqual(out["existing"], "")

    def test_itens_que_nao_sao_objetos_saem(self):
        out = S.clean_ai_items({"items": [1, None, ["Sofá"], True, {"name": "Mesa"}]}, None)
        self.assertEqual([o["name"] for o in out], ["Mesa"])

    def test_lista_vazia_devolve_nenhum_item_sem_erro(self):
        self.assertEqual(S.clean_ai_items({"items": []}, None), [])

    def test_items_vazio_com_nome_solto_nao_vira_item(self):
        self.assertEqual(S.clean_ai_items({"items": [], "name": "Solto"}, None), [], "a lista vale mais que o nome solto")

    def test_items_que_nao_e_lista_e_recusado(self):
        for items in ({"name": "X"}, "Sofá, Mesa", 3):
            with self.subTest(items=items):
                self.assertApiError(502, S.clean_ai_items, {"items": items}, None, msg_part="não devolveu itens")


if __name__ == "__main__":
    unittest.main()
