"""Rotas dos cômodos e das categorias pelo HTTP, com o servidor de verdade: /api/rooms (criar), /api/rooms/order
(Organizar), /api/rooms/<id> (editar e excluir), /api/rooms/<id>/photos, /api/cats e /api/cats/<id>."""
import csv
import io
import json
import unittest

from _boot import ServerCase

JSON = {"Content-Type": "application/json"}
ORDEM = ["sala", "cozinha", "quarto", "escritorio", "lavanderia", "varanda"]


def planilha(app) -> list[dict]:
    raw = app.get("api/export.csv")[2]
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))


class ComodosCase(ServerCase):
    def comodo(self, rid):
        return next((r for r in self.app.data()["rooms"] if r["id"] == rid), None)

    def rev(self):
        return self.app.ok("GET", "api/rev")["rev"]

    def novo(self, name="Cômodo de teste", **campos):
        st, _, out = self.app.post("api/rooms", {"name": name, **campos})
        self.assertEqual(st, 201, out)
        rid = out["room"]["id"]
        self.addCleanup(self.app.delete, f"api/rooms/{rid}")
        return out["room"]

    def erro(self, method, path, body, status, msg):
        st, _, out = self.app.request(method, path, body)
        self.assertEqual((st, out.get("error") if isinstance(out, dict) else out), (status, msg), body)
        return out


class CriarComodo(ComodosCase):
    def test_responde_201_com_o_comodo_a_lista_e_a_revisao(self):
        st, _, out = self.app.post("api/rooms", {"name": "Garagem"})
        self.addCleanup(self.app.delete, f"api/rooms/{out['room']['id']}")
        self.assertEqual((st, set(out)), (201, {"room", "rooms", "rev"}))
        self.assertIn(out["room"], out["rooms"])
        self.assertEqual(out["rev"], self.rev())

    def test_id_vem_do_nome_sem_acento_e_codigo_das_4_primeiras_letras(self):
        r = self.novo("Área de Serviço")
        self.assertEqual((r["id"], r["code"], r["name"]), ("area-de-servico", "AREA", "Área de Serviço"))

    def test_nome_repetido_ganha_sufixo_no_id_e_numero_no_codigo(self):
        a, b = self.novo("Garagem"), self.novo("Garagem")
        self.assertEqual((a["id"], a["code"]), ("garagem", "GARA"))
        self.assertEqual((b["id"], b["code"]), ("garagem-2", "GAR2"))

    def test_codigo_de_outro_comodo_ganha_numero(self):
        self.assertEqual(self.novo("Sala de jantar", code="SAL")["code"], "SAL2")

    def test_codigo_fica_so_com_letras_e_numeros_em_maiusculas(self):
        self.assertEqual(self.novo("Depósito", code="d-1")["code"], "D1")

    def test_codigo_com_mais_de_4_recusado(self):
        self.erro("POST", "api/rooms", {"name": "Depósito", "code": "DEPOS"}, 400, "O campo código passou do limite de 4 caracteres.")

    def test_codigo_so_com_simbolos_vira_cmd(self):
        self.assertEqual(self.novo("Depósito", code="--")["code"], "CMD")

    def test_nome_so_com_simbolos_ganha_id_comodo(self):
        r = self.novo("!!!")
        self.assertEqual((r["id"], r["name"]), ("comodo", "!!!"))

    def test_nome_obrigatorio(self):
        for name in ("", "   ", None):
            with self.subTest(name=name):
                self.erro("POST", "api/rooms", {"name": name}, 400, "Preencha o campo nome do cômodo.")

    def test_nome_de_60_aceito_e_de_61_recusado(self):
        self.assertEqual(len(self.novo("n" * 60)["name"]), 60)
        self.erro("POST", "api/rooms", {"name": "n" * 61}, 400, "O campo nome do cômodo passou do limite de 60 caracteres.")

    def test_nome_aparado(self):
        self.assertEqual(self.novo("  Escada  ")["name"], "Escada")

    def test_novo_comodo_vai_para_o_fim_da_lista(self):
        r = self.novo("Sótão")
        rooms = self.app.data()["rooms"]
        self.assertEqual((rooms[-1]["id"], r["order"]), (r["id"], len(rooms) - 1))
        self.assertEqual([x["order"] for x in rooms], list(range(len(rooms))))

    def test_comeca_sem_fotos_e_com_capa_zero(self):
        r = self.novo("Closet")
        self.assertEqual((r["photos"], r["cover"]), ([], 0))
        self.assertIn("updatedAt", r)

    def test_campos_a_mais_ignorados(self):
        r = self.novo("Porão", id="hack", photos=[{"file": "sala-1.jpg", "label": "x"}], order=-5, cover=2, foo=1)
        self.assertEqual((r["id"], r["photos"], r["cover"]), ("porao", [], 0))
        self.assertNotIn("foo", r)
        self.assertEqual(self.app.data()["rooms"][-1]["id"], "porao", "a ordem pedida não vale: entra no fim")

    def test_gravado_no_arquivo(self):
        r = self.novo("Despensa")
        self.assertIn(r["id"], [x["id"] for x in self.app.stored()["rooms"]])

    def test_corpo_que_nao_e_json_recusado(self):
        st, _, out = self.app.request("POST", "api/rooms", raw=b"name=Garagem", headers=JSON)
        self.assertEqual((st, out["error"]), (400, "Pedido inválido (JSON)."))

class OrganizarComodos(ComodosCase):
    def setUp(self):
        self.app.ok("POST", "api/rooms/order", {"ids": ORDEM})

    def ordem(self):
        return [r["id"] for r in self.app.data()["rooms"]]

    def test_ordem_nova_numerada_de_zero(self):
        out = self.app.ok("POST", "api/rooms/order", {"ids": ORDEM[::-1]})
        self.assertEqual([(r["id"], r["order"]) for r in out["rooms"]], [(rid, n) for n, rid in enumerate(ORDEM[::-1])])
        self.assertEqual(self.ordem(), ORDEM[::-1])

    def test_os_que_faltam_vao_para_o_fim_na_ordem_de_antes(self):
        self.app.ok("POST", "api/rooms/order", {"ids": ["varanda", "quarto"]})
        self.assertEqual(self.ordem(), ["varanda", "quarto", "sala", "cozinha", "escritorio", "lavanderia"])

    def test_ids_desconhecidos_sao_ignorados(self):
        self.app.ok("POST", "api/rooms/order", {"ids": ["nao-existe", "cozinha", "../sala"]})
        self.assertEqual(self.ordem()[0], "cozinha")
        self.assertEqual(len(self.ordem()), 6)

    def test_sem_ids_mantem_a_ordem(self):
        for body in ({}, {"ids": []}, {"ids": None}):
            with self.subTest(body=body):
                self.app.ok("POST", "api/rooms/order", body)
                self.assertEqual(self.ordem(), ORDEM)

    def test_ids_que_nao_sao_lista_nao_baguncam(self):
        self.app.ok("POST", "api/rooms/order", {"ids": "sala"})
        self.assertEqual(self.ordem(), ORDEM)

    def test_responde_lista_e_revisao_e_grava(self):
        r0 = self.rev()
        st, _, out = self.app.post("api/rooms/order", {"ids": ["escritorio"]})
        self.assertEqual((st, set(out), out["rev"]), (200, {"rooms", "rev"}, r0 + 1))
        self.assertEqual([r["id"] for r in self.app.stored()["rooms"]][0], "escritorio")

    def test_planilha_segue_a_ordem_dos_comodos(self):
        self.app.ok("POST", "api/rooms/order", {"ids": ["varanda", "sala"]})
        linhas = planilha(self.app)
        self.assertEqual(linhas[0]["Cômodo"], "Varanda")
        self.assertEqual([x["Código"] for x in linhas[:4]], ["VAR-001", "VAR-002", "VAR-003", "SAL-001"])

    def test_corpo_que_nao_e_json_recusado(self):
        st, _, out = self.app.request("POST", "api/rooms/order", raw=b"sala,cozinha", headers=JSON)
        self.assertEqual((st, out["error"]), (400, "Pedido inválido (JSON)."))
        self.assertEqual(self.ordem(), ORDEM)


class EditarComodo(ComodosCase):
    def test_editar_nome_mantem_o_codigo_e_o_id(self):
        r = self.novo("Garagem")
        out = self.app.ok("PUT", f"api/rooms/{r['id']}", {"name": "Garagem coberta"})["room"]
        self.assertEqual((out["id"], out["code"], out["name"]), ("garagem", "GARA", "Garagem coberta"))

    def test_responde_o_comodo_e_a_revisao(self):
        r = self.novo()
        r0 = self.rev()
        st, _, out = self.app.put(f"api/rooms/{r['id']}", {"name": "Outro"})
        self.assertEqual((st, set(out), out["rev"]), (200, {"room", "rev"}, r0 + 1))

    def test_nome_vazio_recusado(self):
        r = self.novo()
        self.erro("PUT", f"api/rooms/{r['id']}", {"name": "  "}, 400, "Preencha o campo nome do cômodo.")

    def test_codigo_em_minusculas_e_com_simbolos_limpo(self):
        r = self.novo()
        self.assertEqual(self.app.ok("PUT", f"api/rooms/{r['id']}", {"code": "q-1"})["room"]["code"], "Q1")

    def test_codigo_vazio_ou_so_simbolos_recusado(self):
        r = self.novo()
        for code in ("", "--", "  ", None):
            with self.subTest(code=code):
                self.erro("PUT", f"api/rooms/{r['id']}", {"code": code}, 400, "O código precisa ter de 1 a 4 letras ou números.")

    def test_codigo_com_acento_perde_o_acento(self):
        r = self.novo()
        self.assertEqual(self.app.ok("PUT", f"api/rooms/{r['id']}", {"code": "çã1"})["room"]["code"], "CA1")

    def test_codigo_longo_fica_com_as_4_primeiras(self):
        r = self.novo()
        self.assertEqual(self.app.ok("PUT", f"api/rooms/{r['id']}", {"code": "ABCDEF"})["room"]["code"], "ABCD")

    def test_codigo_de_outro_comodo_recusado(self):
        r = self.novo()
        self.erro("PUT", f"api/rooms/{r['id']}", {"code": "coz"}, 400, "O código COZ já é usado por outro cômodo.")

    def test_o_proprio_codigo_aceito(self):
        self.assertEqual(self.app.ok("PUT", "api/rooms/sala", {"code": "SAL", "name": "Sala de estar"})["room"]["code"], "SAL")

    def test_codigo_novo_muda_a_etiqueta_mas_nao_o_id_dos_itens(self):
        self.app.ok("PUT", "api/rooms/varanda", {"code": "VRD"})
        self.addCleanup(self.app.put, "api/rooms/varanda", {"code": "VAR"})
        ids = [i["id"] for i in self.app.data()["items"] if i["room"] == "varanda"]
        self.assertEqual(ids, ["var-001", "var-002", "var-003"])
        self.assertEqual([x["Código"] for x in planilha(self.app) if x["Cômodo"] == "Varanda"], ["VRD-001", "VRD-002", "VRD-003"])

    def test_erro_no_codigo_nao_muda_o_nome(self):
        r = self.novo("Garagem")
        self.erro("PUT", f"api/rooms/{r['id']}", {"name": "Oficina", "code": "COZ"}, 400, "O código COZ já é usado por outro cômodo.")
        self.assertEqual(self.comodo(r["id"])["name"], "Garagem", "nada vale pela metade")
        self.erro("PUT", f"api/rooms/{r['id']}", {"name": "Oficina", "photos": [{"file": "sumiu.jpg"}]}, 400, "Uma das fotos do cômodo não foi encontrada.")
        self.assertEqual(self.comodo(r["id"])["name"], "Garagem")

    def test_fotos_com_legenda(self):
        r = self.novo()
        fotos = [{"file": "sala-1.jpg", "label": "Visão geral"}, {"file": "sala-2.jpg"}]
        out = self.app.ok("PUT", f"api/rooms/{r['id']}", {"photos": fotos})["room"]
        self.assertEqual(out["photos"], [{"file": "sala-1.jpg", "label": "Visão geral"}, {"file": "sala-2.jpg", "label": ""}])

    def test_legenda_acima_de_160_recusada(self):
        r = self.novo()
        self.erro("PUT", f"api/rooms/{r['id']}", {"photos": [{"file": "sala-1.jpg", "label": "l" * 161}]}, 400,
                  "O campo legenda passou do limite de 160 caracteres.")
        self.assertEqual(self.comodo(r["id"])["photos"], [])

    def test_foto_que_nao_existe_ou_fora_do_formato_recusada(self):
        r = self.novo()
        for foto in ({"file": "sumiu.jpg"}, {"file": "../inventario.json"}, "sala-1.jpg", {"label": "sem arquivo"}):
            with self.subTest(foto=foto):
                self.erro("PUT", f"api/rooms/{r['id']}", {"photos": [foto]}, 400, "Uma das fotos do cômodo não foi encontrada.")

    def test_fotos_nulas_esvaziam(self):
        r = self.novo()
        self.app.ok("PUT", f"api/rooms/{r['id']}", {"photos": [{"file": "sala-1.jpg"}]})
        self.assertEqual(self.app.ok("PUT", f"api/rooms/{r['id']}", {"photos": None})["room"]["photos"], [])

    def test_capa_valida_e_fora_do_intervalo(self):
        r = self.novo()
        self.app.ok("PUT", f"api/rooms/{r['id']}", {"photos": [{"file": "sala-1.jpg"}, {"file": "sala-2.jpg"}]})
        for cover, esperado in ((1, 1), (2, 0), (-1, 0), ("1", 0), (None, 0), (0, 0)):
            with self.subTest(cover=cover):
                self.assertEqual(self.app.ok("PUT", f"api/rooms/{r['id']}", {"cover": cover})["room"]["cover"], esperado)

    def test_tirar_fotos_corrige_a_capa(self):
        r = self.novo()
        self.app.ok("PUT", f"api/rooms/{r['id']}", {"photos": [{"file": "sala-1.jpg"}, {"file": "sala-2.jpg"}], "cover": 1})
        out = self.app.ok("PUT", f"api/rooms/{r['id']}", {"photos": [{"file": "sala-2.jpg"}]})["room"]
        self.assertEqual(out["cover"], 0)

    def test_inexistente_404_com_mensagem(self):
        self.erro("PUT", "api/rooms/nao-existe", {"name": "x"}, 404, "Este cômodo não existe mais.")

    def test_campos_a_mais_ignorados(self):
        r = self.novo()
        out = self.app.ok("PUT", f"api/rooms/{r['id']}", {"id": "outro", "order": 0, "foo": 1})["room"]
        self.assertEqual((out["id"], out["order"]), (r["id"], r["order"]))
        self.assertNotIn("foo", out)

    def test_corpo_vazio_so_atualiza_a_data(self):
        r = self.novo()
        out = self.app.ok("PUT", f"api/rooms/{r['id']}", None)["room"]
        self.assertEqual({k: v for k, v in out.items() if k != "updatedAt"}, {k: v for k, v in r.items() if k != "updatedAt"})


class ExcluirComodo(ComodosCase):
    def criar(self, name="Para excluir", **campos):
        return self.app.ok("POST", "api/rooms", {"name": name, **campos})["room"]

    def test_devolve_o_comodo_a_lista_sem_ele_e_a_revisao(self):
        r = self.criar()
        r0 = self.rev()
        st, _, out = self.app.delete(f"api/rooms/{r['id']}")
        self.assertEqual((st, out["room"]["id"], out["rev"]), (200, r["id"], r0 + 1))
        self.assertNotIn(r["id"], [x["id"] for x in out["rooms"]])
        self.assertNotIn(r["id"], [x["id"] for x in self.app.stored()["rooms"]])

    def test_ordem_renumerada_depois_de_excluir(self):
        r = self.criar()
        self.app.ok("POST", "api/rooms/order", {"ids": [r["id"]] + ORDEM})
        out = self.app.ok("DELETE", f"api/rooms/{r['id']}")
        self.assertEqual([(x["id"], x["order"]) for x in out["rooms"]], [(rid, n) for n, rid in enumerate(ORDEM)])

    def test_inexistente_404_com_mensagem(self):
        self.erro("DELETE", "api/rooms/nao-existe", None, 404, "Este cômodo não existe mais.")

    def test_com_itens_nao_sai_nem_muda_a_revisao(self):
        r0 = self.rev()
        self.erro("DELETE", "api/rooms/varanda", None, 400, "Mova ou exclua os itens deste cômodo antes de excluí-lo.")
        self.assertEqual(self.rev(), r0)
        self.assertIsNotNone(self.comodo("varanda"))

    def test_fotos_do_comodo_continuam_no_disco(self):
        foto = self.upload_photo()
        r = self.criar()
        self.app.ok("POST", f"api/rooms/{r['id']}/photos", {"file": foto})
        self.app.ok("DELETE", f"api/rooms/{r['id']}")
        self.assertEqual(self.app.get(f"photos/{foto}")[0], 200)

    def test_codigo_liberado_pode_ser_usado_de_novo(self):
        r = self.criar("Garagem", code="GAR")
        self.app.ok("DELETE", f"api/rooms/{r['id']}")
        self.assertEqual(self.novo("Garagem nova", code="GAR")["code"], "GAR")

    def test_corpo_json_e_aceito_e_ignorado(self):
        r = self.criar()
        self.assertEqual(self.app.request("DELETE", f"api/rooms/{r['id']}", {"motivo": "obra"})[0], 200)


class FotosDoComodo(ComodosCase):
    def test_acrescenta_no_fim_com_a_legenda(self):
        r = self.novo()
        self.app.ok("POST", f"api/rooms/{r['id']}/photos", {"file": "sala-1.jpg", "label": "Primeira"})
        out = self.app.ok("POST", f"api/rooms/{r['id']}/photos", {"file": "sala-2.jpg", "label": "Segunda"})["room"]
        self.assertEqual(out["photos"], [{"file": "sala-1.jpg", "label": "Primeira"}, {"file": "sala-2.jpg", "label": "Segunda"}])

    def test_responde_o_comodo_e_a_revisao(self):
        r = self.novo()
        r0 = self.rev()
        st, _, out = self.app.post(f"api/rooms/{r['id']}/photos", {"file": "sala-1.jpg"})
        self.assertEqual((st, set(out), out["rev"]), (200, {"room", "rev"}, r0 + 1))

    def test_foto_repetida_nao_duplica(self):
        r = self.novo()
        self.app.ok("POST", f"api/rooms/{r['id']}/photos", {"file": "sala-1.jpg", "label": "A"})
        out = self.app.ok("POST", f"api/rooms/{r['id']}/photos", {"file": "sala-1.jpg", "label": "B"})["room"]
        self.assertEqual(out["photos"], [{"file": "sala-1.jpg", "label": "A"}])

    def test_sem_legenda_fica_vazia(self):
        r = self.novo()
        self.assertEqual(self.app.ok("POST", f"api/rooms/{r['id']}/photos", {"file": "sala-1.jpg"})["room"]["photos"][0]["label"], "")

    def test_foto_que_nao_existe_recusada(self):
        r = self.novo()
        for body in ({"file": "sumiu.jpg"}, {"file": "../inventario.json"}, {}, {"file": ""}):
            with self.subTest(body=body):
                self.erro("POST", f"api/rooms/{r['id']}/photos", body, 400, "A foto não foi encontrada. Envie de novo.")

    def test_comodo_inexistente_404_antes_de_olhar_a_foto(self):
        self.erro("POST", "api/rooms/nao-existe/photos", {"file": "sumiu.jpg"}, 404, "Este cômodo não existe mais.")

    def test_legenda_longa_recusada_sem_mudar_nada(self):
        r = self.novo()
        r0 = self.rev()
        self.erro("POST", f"api/rooms/{r['id']}/photos", {"file": "sala-1.jpg", "label": "l" * 161}, 400,
                  "O campo legenda passou do limite de 160 caracteres.")
        self.assertEqual((self.comodo(r["id"])["photos"], self.rev()), ([], r0))

    def test_miniatura_sozinha_nao_vale(self):
        r = self.novo()
        with open(self.app.path("data", "thumbs", "so-miniatura-comodo.jpg"), "wb") as f:
            f.write(b"\xff\xd8" + b"0" * 200)
        self.erro("POST", f"api/rooms/{r['id']}/photos", {"file": "so-miniatura-comodo.jpg"}, 400, "A foto não foi encontrada. Envie de novo.")


class Categorias(ComodosCase):
    def nova(self, name):
        st, _, out = self.app.post("api/cats", {"name": name})
        self.assertEqual(st, 201, out)
        self.addCleanup(self.app.delete, f"api/cats/{out['cat']['id']}")
        return out["cat"]

    def ids(self):
        return [c["id"] for c in self.app.data()["cats"]]

    def test_criar_responde_201_com_a_categoria_a_lista_e_a_revisao(self):
        r0 = self.rev()
        st, _, out = self.app.post("api/cats", {"name": "Bicicletas"})
        self.addCleanup(self.app.delete, "api/cats/bicicletas")
        self.assertEqual((st, set(out), out["rev"]), (201, {"cat", "cats", "rev"}, r0 + 1))
        self.assertEqual(out["cat"], {"id": "bicicletas", "name": "Bicicletas"})
        self.assertEqual(out["cats"], self.app.data()["cats"])

    def test_id_sem_acento_e_com_hifen(self):
        self.assertEqual(self.nova("Ferramentas Elétricas")["id"], "ferramentas-eletricas")

    def test_espacos_repetidos_no_nome_somem(self):
        self.assertEqual(self.nova("  Jardim   de  inverno ")["name"], "Jardim de inverno")

    def test_nome_igual_sem_acento_ou_em_maiusculas_recusado(self):
        for name in ("moveis", "MÓVEIS", " Móveis "):
            with self.subTest(name=name):
                self.erro("POST", "api/cats", {"name": name}, 400, f"Já existe a categoria {name.strip()}.")

    def test_nome_vazio_recusado(self):
        for name in ("", "   ", None):
            with self.subTest(name=name):
                self.erro("POST", "api/cats", {"name": name}, 400, "Preencha o campo nome da categoria.")

    def test_nome_acima_de_60_recusado(self):
        self.erro("POST", "api/cats", {"name": "c" * 61}, 400, "O campo nome da categoria passou do limite de 60 caracteres.")

    def test_nome_so_com_simbolos_ganha_id_categoria(self):
        c = self.nova("+++")
        self.assertEqual((c["id"], c["name"]), ("categoria", "+++"))

    def test_id_ja_usado_ganha_numero(self):
        a = self.nova("Oficina")
        self.app.ok("PUT", f"api/cats/{a['id']}", {"name": "Garagem e oficina"})
        b = self.nova("Oficina")
        self.assertEqual((a["id"], b["id"]), ("oficina", "oficina-2"))

    def test_lista_editada_passa_a_ficar_no_inventario(self):
        app = self.fresh()
        self.assertNotIn("cats", app.stored(), "até alguém editar, vale a lista padrão")
        app.ok("POST", "api/cats", {"name": "Brinquedos"})
        self.assertEqual(app.stored()["cats"], app.data()["cats"])
        self.assertIn("brinquedos", [c["id"] for c in app.ok("GET", "api/export.json")["cats"]])

    def test_renomear_para_o_proprio_nome_aceito(self):
        self.assertEqual(self.app.ok("PUT", "api/cats/moveis", {"name": "Móveis"})["cat"], {"id": "moveis", "name": "Móveis"})

    def test_renomear_para_o_nome_de_outra_recusado(self):
        self.erro("PUT", "api/cats/moveis", {"name": "plantas"}, 400, "Já existe a categoria plantas.")

    def test_renomear_inexistente_404(self):
        self.erro("PUT", "api/cats/nao-existe", {"name": "Qualquer"}, 404, "Esta categoria não existe mais.")

    def test_renomear_mantem_o_id_e_os_itens(self):
        n = len([i for i in self.app.data()["items"] if i["cat"] == "texteis"])
        out = self.app.ok("PUT", "api/cats/texteis", {"name": "Tapetes, cortinas e almofadas"})
        self.addCleanup(self.app.put, "api/cats/texteis", {"name": "Tapetes e têxteis"})
        self.assertEqual(out["cat"]["id"], "texteis")
        self.assertEqual(len([i for i in self.app.data()["items"] if i["cat"] == "texteis"]), n)

    def test_nome_novo_aparece_na_planilha(self):
        self.app.ok("PUT", "api/cats/plantas", {"name": "Plantas e vasos"})
        self.addCleanup(self.app.put, "api/cats/plantas", {"name": "Plantas"})
        cats = {x["Código"]: x["Categoria"] for x in planilha(self.app)}
        plantas = [i for i in self.app.data()["items"] if i["cat"] == "plantas"]
        self.assertTrue(plantas)
        tag = {r["id"]: r["code"] for r in self.app.data()["rooms"]}
        for i in plantas:
            self.assertEqual(cats[f"{tag[i['room']]}-{i['seq']:03d}"], "Plantas e vasos")

    def test_outros_apps_recebem_os_nomes_editados(self):
        with open(self.app.path("share", "integracao.json"), encoding="utf-8") as f:
            chave = json.load(f)["chave"]
        self.app.ok("PUT", "api/cats/livros", {"name": "Livros, jogos e discos"})
        self.addCleanup(self.app.put, "api/cats/livros", {"name": "Livros e jogos"})
        out = self.app.ok("GET", "api/integracao/itens", headers={"Authorization": f"Bearer {chave}"})
        self.assertEqual(out["categorias"]["livros"], "Livros, jogos e discos")

    def test_excluir_vazia_move_zero(self):
        c = self.nova("Vazia")
        out = self.app.ok("DELETE", f"api/cats/{c['id']}")
        self.assertEqual((out["moved"], c["id"] in [x["id"] for x in out["cats"]]), (0, False))
        self.assertIn("rev", out)

    def test_excluir_inexistente_404_e_outros_400(self):
        self.erro("DELETE", "api/cats/nao-existe", None, 404, "Esta categoria não existe mais.")
        self.erro("DELETE", "api/cats/outros", None, 400, "A categoria Outros não pode ser excluída.")
        self.assertIn("outros", self.ids())

    def test_excluir_leva_os_itens_para_outros_com_data_nova(self):
        app = self.fresh()
        antes = {i["id"]: i for i in app.data()["items"] if i["cat"] == "plantas"}
        out = app.ok("DELETE", "api/cats/plantas")
        self.assertEqual(out["moved"], len(antes))
        depois = {i["id"]: i for i in app.data()["items"] if i["id"] in antes}
        for iid, it in depois.items():
            self.assertEqual(it["cat"], "outros")
            self.assertGreater(it["updatedAt"], antes[iid]["updatedAt"], "mudou: os outros aparelhos percebem")

    def test_categoria_excluida_nao_vale_mais_no_cadastro(self):
        c = self.nova("Temporária")
        self.app.ok("DELETE", f"api/cats/{c['id']}")
        it = self.app.ok("POST", "api/items", {"room": "varanda", "name": "Sem categoria", "cat": c["id"]})["item"]
        self.addCleanup(self.app.delete, f"api/items/{it['id']}")
        self.assertEqual(it["cat"], "outros")


if __name__ == "__main__":
    unittest.main()
