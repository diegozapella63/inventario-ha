"""Categorias no servidor, um comportamento por teste: default_cats, clean_cats, cats, cat_map, _cat_name, create_cat,
update_cat e delete_cat (itens vão para Outros, Outros não sai, nomes repetidos sem ligar para acento e maiúsculas,
tamanho do nome, ids), e o efeito em public(), na planilha (CSV), nas instruções e respostas da IA e na lista para os
outros apps. Complementa test_basicos.py sem repetir os casos de lá."""
import csv
import io
import unittest

from _boot import UnitBase, server as S


class Base(UnitBase):
    def ids(self):
        return [c["id"] for c in self.store.cats()]

    def de_cat(self, cid):
        return [i for i in self.store.data["items"] if i["cat"] == cid]

    def planilha(self):
        rows = csv.reader(io.StringIO(S.export_csv_bytes().decode("utf-8-sig")), delimiter=";")
        return {r[0]: r for r in rows}


class Padrao(Base):
    def test_cada_chamada_devolve_uma_lista_nova(self):
        a = S.default_cats()
        a[0]["name"] = "Mudou"
        a.pop()
        self.assertEqual((S.default_cats()[0]["name"], len(S.default_cats())), ("Eletrônicos", 15))

    def test_ids_validos_e_sem_repeticao(self):
        ids = [c["id"] for c in S.default_cats()]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertTrue(all(S.SAFE_CAT.fullmatch(i) for i in ids), ids)

    def test_nomes_sem_repeticao_ignorando_acento(self):
        nomes = [S.fold(c["name"]) for c in S.default_cats()]
        self.assertEqual(len(set(nomes)), len(nomes), "senão a casa não conseguiria renomear nenhuma")


class Limpar(Base):
    def test_mantem_a_ordem_recebida(self):
        out = S.clean_cats([{"id": "b", "name": "B"}, {"id": "a", "name": "A"}, {"id": "outros", "name": "Outros"}])
        self.assertEqual([c["id"] for c in out], ["b", "a", "outros"])

    def test_outros_no_meio_fica_onde_esta(self):
        out = S.clean_cats([{"id": "outros", "name": "Outros"}, {"id": "a", "name": "A"}])
        self.assertEqual([c["id"] for c in out], ["outros", "a"])

    def test_nome_proprio_de_outros_e_mantido(self):
        self.assertIn({"id": "outros", "name": "Diversos"}, S.clean_cats([{"id": "outros", "name": "Diversos"}]))

    def test_id_com_maiuscula_descartado(self):
        self.assertIsNone(S.clean_cats([{"id": "Moveis", "name": "Móveis"}]))

    def test_id_com_41_caracteres_aceito(self):
        self.assertEqual(S.clean_cats([{"id": "a" * 41, "name": "Longa"}])[0]["id"], "a" * 41)

    def test_id_com_sublinhado_ou_comecando_por_numero_aceito(self):
        out = S.clean_cats([{"id": "ar_condicionado", "name": "Ar"}, {"id": "3d", "name": "Impressão 3D"}])
        self.assertEqual([c["id"] for c in out][:2], ["ar_condicionado", "3d"])

    def test_id_numerico_vira_texto(self):
        self.assertEqual(S.clean_cats([{"id": 5, "name": "Cinco"}])[0]["id"], "5")

    def test_nome_numerico_vira_texto(self):
        self.assertEqual(S.clean_cats([{"id": "x", "name": 10}])[0]["name"], "10")

    def test_quebra_de_linha_no_nome_vira_espaco(self):
        self.assertEqual(S.clean_cats([{"id": "x", "name": "Ferramentas\nde\tjardim"}])[0]["name"], "Ferramentas de jardim")

    def test_so_outros_continua_valido(self):
        self.assertEqual(S.clean_cats([{"id": "outros", "name": "Outros"}]), [{"id": "outros", "name": "Outros"}])


class Lista(Base):
    def test_gravadas_ruins_voltam_ao_padrao(self):
        self.store.data["cats"] = [{"id": "", "name": ""}, "texto"]
        self.assertEqual(self.store.cats(), S.default_cats())

    def test_lista_devolvida_e_uma_copia(self):
        self.store.create_cat({"name": "Oficina"})
        self.store.cats()[0]["name"] = "Mudou de fora"
        self.assertEqual(self.store.cats()[0]["name"], "Eletrônicos")

    def test_mapa_na_mesma_ordem_da_lista(self):
        self.store.create_cat({"name": "Oficina"})
        self.assertEqual(list(self.store.cat_map()), self.ids())


class NomeDaCategoria(Base):
    def test_sem_acento_igual_a_existente_recusado(self):
        self.assertApiError(400, self.store.create_cat, {"name": "Moveis"}, msg_part="Já existe")

    def test_com_espacos_a_mais_igual_a_existente_recusado(self):
        self.assertApiError(400, self.store.create_cat, {"name": "  Decoração   e   arte "}, msg_part="Já existe")

    def test_mensagem_de_repetida_diz_o_nome(self):
        self.assertApiError(400, self.store.create_cat, {"name": "plantas"}, msg_part="Já existe a categoria plantas.")

    def test_nome_com_60_caracteres_aceito(self):
        self.assertEqual(self.store.create_cat({"name": "N" * 60})["name"], "N" * 60)

    def test_junta_espacos_do_meio(self):
        self.assertEqual(self.store.create_cat({"name": "Ferramentas   de   jardim"})["name"], "Ferramentas de jardim")

    def test_sem_nome_pede_para_preencher(self):
        self.assertApiError(400, self.store.create_cat, {}, msg_part="Preencha o campo nome da categoria")


class Criar(Base):
    def test_id_cortado_em_36(self):
        c = self.store.create_cat({"name": "Ferramentas elétricas e manuais da oficina do fundo"})
        self.assertEqual(c["id"], "ferramentas-eletricas-e-manuais-da-o")

    def test_terceira_com_o_mesmo_id_ganha_3(self):
        for nome in ("Áudio & Vídeo", "Áudio/Vídeo"):
            self.store.create_cat({"name": nome})
        self.assertEqual(self.store.create_cat({"name": "Áudio - Vídeo"})["id"], "audio-video-3")

    def test_nova_fica_antes_de_outros_renomeada(self):
        self.store.update_cat("outros", {"name": "Diversos"})
        self.store.create_cat({"name": "Oficina"})
        self.assertEqual(self.ids()[-2:], ["oficina", "outros"])

    def test_criar_outros_depois_de_renomear_ganha_outro_id(self):
        self.store.update_cat("outros", {"name": "Diversos"})
        self.assertEqual(self.store.create_cat({"name": "Outros"})["id"], "outros-2")

    def test_primeira_criacao_grava_a_lista_padrao_inteira(self):
        self.assertNotIn("cats", self.store.data)
        self.store.create_cat({"name": "Oficina"})
        self.assertEqual(len(self.store.data["cats"]), 16)

    def test_nome_recusado_nao_grava(self):
        rev = self.store.data["rev"]
        self.assertApiError(400, self.store.create_cat, {"name": "Móveis"})
        self.assertEqual((self.store.data["rev"], "cats" in self.store.data), (rev, False))


class Renomear(Base):
    def test_nao_muda_o_id_nem_os_itens(self):
        moveis = [i["id"] for i in self.de_cat("moveis")]
        c = self.store.update_cat("moveis", {"name": "Mobília"})
        self.assertEqual((c["id"], [i["id"] for i in self.de_cat("moveis")]), ("moveis", moveis))

    def test_junta_espacos(self):
        self.assertEqual(self.store.update_cat("moveis", {"name": "  Mobília   da  casa "})["name"], "Mobília da casa")

    def test_fica_no_arquivo(self):
        self.store.update_cat("moveis", {"name": "Mobília"})
        self.assertIn({"id": "moveis", "name": "Mobília"}, S.read_json(S.DATA_FILE)["cats"])

    def test_nome_vazio_nao_muda_o_nome(self):
        self.assertApiError(400, self.store.update_cat, "moveis", {"name": "  "})
        self.assertEqual(self.store.cat_map()["moveis"], "Móveis")

    def test_primeira_vez_mantem_as_outras_do_padrao(self):
        self.store.update_cat("moveis", {"name": "Mobília"})
        esperado = [dict(c, name="Mobília") if c["id"] == "moveis" else c for c in S.default_cats()]
        self.assertEqual(self.store.data["cats"], esperado)


class Excluir(Base):
    def test_itens_de_outras_categorias_nao_mudam_de_data(self):
        sofa = self.item("sal-001")["updatedAt"]
        self.store.delete_cat("plantas")
        self.assertEqual(self.item("sal-001")["updatedAt"], sofa)

    def test_movidos_ganham_data_nova_para_os_outros_aparelhos(self):
        iid = self.de_cat("plantas")[0]["id"]
        antes = self.item(iid)["updatedAt"]
        self.store.delete_cat("plantas")
        self.assertNotEqual(self.item(iid)["updatedAt"], antes, "quem estava editando vê o conflito")

    def test_sem_itens_devolve_zero(self):
        self.assertEqual(self.store.delete_cat("pets"), 0)

    def test_tira_do_arquivo(self):
        self.store.delete_cat("pets")
        self.assertNotIn("pets", [c["id"] for c in S.read_json(S.DATA_FILE)["cats"]])

    def test_mantem_a_ordem_das_outras(self):
        self.store.delete_cat("colecao")
        self.assertEqual(self.ids(), [c["id"] for c in S.default_cats() if c["id"] != "colecao"])

    def test_recriar_volta_o_mesmo_id(self):
        self.store.delete_cat("pets")
        self.assertEqual(self.store.create_cat({"name": "Pets"})["id"], "pets")

    def test_excluida_nao_vale_para_item_novo(self):
        self.store.delete_cat("pets")
        it = self.store.create_items([{"room": "sala", "name": "Caminha", "cat": "pets"}], None)[0]
        self.assertEqual(it["cat"], "outros")

    def test_outros_recusada_nao_grava(self):
        rev = self.store.data["rev"]
        self.assertApiError(400, self.store.delete_cat, "outros")
        self.assertEqual(self.store.data["rev"], rev)


class Efeitos(Base):
    def test_public_traz_o_nome_novo(self):
        self.store.update_cat("moveis", {"name": "Mobília"})
        self.assertIn({"id": "moveis", "name": "Mobília"}, self.store.public()["cats"])

    def test_public_sem_categorias_gravadas_traz_o_padrao(self):
        self.assertEqual(self.store.public()["cats"], S.default_cats())

    def test_planilha_categoria_excluida_vira_outros(self):
        iid = self.de_cat("plantas")[0]["id"]
        self.store.delete_cat("plantas")
        self.assertEqual(self.planilha()[self.store.tag(self.item(iid))][5], "Outros")

    def test_planilha_categoria_desconhecida_usa_o_nome_de_outros(self):
        self.store.update_cat("outros", {"name": "Diversos"})
        self.item("sal-001")["cat"] = "sumiu"
        self.assertEqual(self.planilha()["SAL-001"][5], "Diversos")

    def test_planilha_categoria_criada_pela_casa(self):
        self.store.create_cat({"name": "Oficina"})
        self.store.update_item("lav-005", {"cat": "oficina"}, None)
        self.assertEqual(self.planilha()["LAV-005"][5], "Oficina")

    def test_ia_recebe_o_nome_novo(self):
        self.store.update_cat("moveis", {"name": "Mobília"})
        p = S.ai_prompt("single", None, "")
        self.assertIn("moveis (Mobília)", p)
        self.assertNotIn("moveis (Móveis)", p)

    def test_ia_nao_recebe_a_categoria_excluida(self):
        self.store.delete_cat("pets")
        self.assertNotIn("pets (", S.ai_prompt("multi", None, ""))

    def test_ia_recebe_as_categorias_na_ordem_da_casa(self):
        self.store.create_cat({"name": "Oficina"})
        linha = next(ln for ln in S.ai_prompt("single", None, "").splitlines() if ln.startswith('- "cat"'))
        self.assertEqual(linha, '- "cat": uma destas chaves: ' + ", ".join(f"{c['id']} ({c['name']})" for c in self.store.cats()) + ".")

    def test_resposta_da_ia_com_categoria_excluida_vai_para_outros(self):
        self.store.delete_cat("plantas")
        out = S.clean_ai_items({"items": [{"name": "Samambaia", "cat": "plantas"}]}, None)
        self.assertEqual(out[0]["cat"], "outros")

    def test_outros_apps_recebem_o_nome_novo(self):
        class H:
            def send_json(self, obj, status=200):
                self.out = obj
        self.store.update_cat("moveis", {"name": "Mobília"})
        h = H()
        S.r_integracao_itens(h, {})
        self.assertEqual(h.out["categorias"]["moveis"], "Mobília")



class EletronicosFicaSempre(UnitBase):
    """Eletrônicos é a categoria das novidades: sempre existe, com o mesmo nome."""

    def test_lista_guardada_sem_eletronicos_ganha_de_volta(self):
        self.store.data["cats"] = [{"id": "moveis", "name": "Móveis"}, {"id": "outros", "name": "Outros"}]
        self.assertEqual([c["id"] for c in self.store.cats()], ["eletronicos", "moveis", "outros"])

    def test_nao_renomeia_nem_exclui(self):
        for f, args, msg in ((self.store.update_cat, ("eletronicos", {"name": "Aparelhos"}), "renomear"), (self.store.delete_cat, ("eletronicos",), "excluir")):
            with self.assertRaises(S.ApiError) as e:
                f(*args)
            self.assertEqual((e.exception.status, e.exception.msg), (400, f"Eletrônicos é a categoria das novidades: não dá para {msg}."))
        self.assertEqual(self.store.cat_map()["eletronicos"], "Eletrônicos")


if __name__ == "__main__":
    unittest.main()
