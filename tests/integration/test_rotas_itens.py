"""Rotas dos itens pelo HTTP, com o servidor de verdade: POST, PUT e DELETE /api/items e o lote /api/items/batch
(Catalogar foto e Falar). Sucesso, cada erro de validação com o status e a mensagem, item inexistente, conflito entre
aparelhos, corpo que não é JSON, corpo grande demais e campos a mais ignorados."""
import os
import socket
import unittest

from _boot import ServerCase, helpers

JSON = {"Content-Type": "application/json"}
VALOR_INVALIDO = "Valor inválido. Use só números, como 1200 ou 1.200,50."
FORA_DO_INTERVALO = "Valor fora do intervalo permitido."
SEM_COMODO = "Escolha um cômodo que exista."
FOTO_SUMIU = "Uma das fotos não foi encontrada. Envie a foto de novo."


def troca(app, pedido: bytes, timeout=10) -> tuple[int, bytes]:
    """Manda um pedido HTTP escrito à mão e lê a resposta até o servidor fechar: (status, corpo)."""
    buf = b""
    with socket.create_connection(("127.0.0.1", app.port), timeout=timeout) as s:
        s.sendall(pedido)
        try:
            while True:
                d = s.recv(65536)
                if not d:
                    break
                buf += d
        except (ConnectionResetError, socket.timeout):
            pass
    head, _, body = buf.partition(b"\r\n\r\n")
    return int(head.split(b" ", 2)[1]), body


class ItensCase(ServerCase):
    """Cada teste cria os próprios itens e os apaga no fim: o servidor da classe continua com a casa de teste."""

    def novo(self, headers=None, **campos):
        body = {"room": "varanda", "name": "Item de teste", **campos}
        st, _, out = self.app.post("api/items", body, headers=headers)
        self.assertEqual(st, 201, out)
        self.addCleanup(self.app.delete, f"api/items/{out['item']['id']}")
        return out["item"]

    def item(self, iid):
        return next((i for i in self.app.data()["items"] if i["id"] == iid), None)

    def rev(self):
        return self.app.ok("GET", "api/rev")["rev"]

    def erro(self, method, path, body, status, msg):
        st, _, out = self.app.request(method, path, body)
        self.assertEqual((st, out.get("error") if isinstance(out, dict) else out), (status, msg), body)
        return out


class CriarItem(ItensCase):
    def test_responde_201_so_com_o_item_e_a_revisao(self):
        st, h, out = self.app.post("api/items", {"room": "varanda", "name": "Rede de descanso"})
        self.addCleanup(self.app.delete, f"api/items/{out['item']['id']}")
        self.assertEqual(st, 201)
        self.assertEqual(set(out), {"item", "rev"})
        self.assertEqual(out["rev"], self.rev())
        self.assertEqual(self.item(out["item"]["id"]), out["item"], "o que volta é o que ficou guardado")

    def test_codigo_e_numero_seguem_o_comodo(self):
        maior = max(i["seq"] for i in self.app.data()["items"] if i["room"] == "lavanderia")
        it = self.novo(room="lavanderia", name="Varal de chão")
        self.assertEqual((it["seq"], it["id"], it["room"]), (maior + 1, f"lav-{maior + 1:03d}", "lavanderia"))

    def test_campos_que_nao_vieram_ganham_o_padrao(self):
        it = self.novo(name="Vaso")
        esperado = {"zone": "", "details": "", "cat": "outros", "qty": "1", "value": 0, "photos": [], "checked": False,
                    "flag": None, "approx": True, "source": "manual"}
        self.assertEqual({k: it[k] for k in esperado}, esperado)
        self.assertEqual((it["updatedAt"], it["valueAt"]), (it["createdAt"], it["createdAt"]), "a data do valor é a do cadastro")
        self.assertNotIn("createdBy", it, "sem usuário do Home Assistant, sem autor")
        self.assertNotIn("photoSrc", it)

    def test_textos_sao_aparados(self):
        it = self.novo(name="  Rede  ", details="  azul  ", zone="  Canto  ", qty="  2  ")
        self.assertEqual((it["name"], it["details"], it["zone"], it["qty"]), ("Rede", "azul", "Canto", "2"))

    def test_valor_em_numero_ou_em_texto_brasileiro_da_o_mesmo(self):
        a = self.novo(name="A", value=1200.5)
        b = self.novo(name="B", value="R$ 1.200,50")
        self.assertEqual((a["value"], b["value"]), (1200.5, 1200.5))
        self.assertEqual(self.novo(name="C", value="1.200")["value"], 1200, "1.200 é mil e duzentos")

    def test_valor_fora_do_intervalo_recusado(self):
        for v in (-1, "-5", 1e9 + 1):
            with self.subTest(valor=v):
                self.erro("POST", "api/items", {"room": "varanda", "name": "X", "value": v}, 400, FORA_DO_INTERVALO)

    def test_valor_de_um_bilhao_exato_aceito(self):
        self.assertEqual(self.novo(value=1e9)["value"], 1000000000)

    def test_valor_que_nao_e_numero_nem_texto_recusado(self):
        for v in (True, False, [1], {"v": 1}, "12,3,4"):
            with self.subTest(valor=v):
                self.erro("POST", "api/items", {"room": "varanda", "name": "X", "value": v}, 400, VALOR_INVALIDO)

    def test_nome_so_com_espacos_recusado(self):
        self.erro("POST", "api/items", {"room": "varanda", "name": "   "}, 400, "Preencha o campo nome.")

    def test_nome_de_200_caracteres_aceito_e_de_201_recusado(self):
        self.assertEqual(len(self.novo(name="n" * 200)["name"]), 200)
        self.erro("POST", "api/items", {"room": "varanda", "name": "n" * 201}, 400, "O campo nome passou do limite de 200 caracteres.")

    def test_detalhes_acima_de_4000_recusados(self):
        self.assertEqual(len(self.novo(details="d" * 4000)["details"]), 4000)
        self.erro("POST", "api/items", {"room": "varanda", "name": "X", "details": "d" * 4001}, 400,
                  "O campo detalhes passou do limite de 4000 caracteres.")

    def test_zona_acima_de_120_recusada(self):
        self.erro("POST", "api/items", {"room": "varanda", "name": "X", "zone": "z" * 121}, 400, "O campo zona passou do limite de 120 caracteres.")

    def test_quantidade_acima_de_30_recusada(self):
        self.erro("POST", "api/items", {"room": "varanda", "name": "X", "qty": "q" * 31}, 400, "O campo quantidade passou do limite de 30 caracteres.")

    def test_quantidade_vazia_ou_so_espacos_vira_1(self):
        for q in ("", "   ", None):
            with self.subTest(qty=q):
                self.assertEqual(self.novo(qty=q)["qty"], "1")

    def test_quantidade_em_numero_vira_texto(self):
        self.assertEqual(self.novo(qty=3)["qty"], "3")

    def test_observacao_vazia_vira_nula_e_longa_recusada(self):
        self.assertIsNone(self.novo(flag="")["flag"])
        self.assertEqual(self.novo(flag="Conferir a nota")["flag"], "Conferir a nota")
        self.erro("POST", "api/items", {"room": "varanda", "name": "X", "flag": "f" * 201}, 400, "O campo observação passou do limite de 200 caracteres.")

    def test_origem_escolhida_fica_e_longa_recusada(self):
        self.assertEqual(self.novo(source="voz")["source"], "voz")
        self.erro("POST", "api/items", {"room": "varanda", "name": "X", "source": "s" * 41}, 400, "O campo origem passou do limite de 40 caracteres.")

    def test_categoria_so_vale_pelo_id_exato(self):
        self.assertEqual(self.novo(cat="moveis")["cat"], "moveis")
        for cat in ("MOVEIS", "Móveis", "moveis ", 7):
            with self.subTest(cat=cat):
                self.assertEqual(self.novo(cat=cat)["cat"], "outros")

    def test_comodo_pelo_id_e_nao_pelo_nome_nem_pelo_codigo(self):
        for room in ("Sala de estar", "SAL", "Sala", None):
            with self.subTest(room=room):
                self.erro("POST", "api/items", {"room": room, "name": "X"}, 400, SEM_COMODO)

    def test_sem_corpo_pede_o_comodo(self):
        st, _, out = self.app.request("POST", "api/items")
        self.assertEqual((st, out["error"]), (400, SEM_COMODO))

    def test_foto_repetida_entra_uma_vez(self):
        self.assertEqual(self.novo(photos=["sala-1.jpg", "sala-2.jpg", "sala-1.jpg"])["photos"], ["sala-1.jpg", "sala-2.jpg"])

    def test_doze_fotos_aceitas_e_treze_recusadas(self):
        fotos = sorted(f for f in os.listdir(self.app.path("data", "photos")) if f.endswith(".jpg"))
        while len(fotos) < 13:
            fotos.append(self.upload_photo())
        self.assertEqual(len(self.novo(photos=fotos[:12])["photos"]), 12)
        self.erro("POST", "api/items", {"room": "varanda", "name": "X", "photos": fotos[:13]}, 400, "Use no máximo 12 fotos por item.")

    def test_fotos_que_nao_sao_lista_recusadas(self):
        for photos in ("sala-1.jpg", {"sala-1.jpg": 1}, 3):
            with self.subTest(photos=photos):
                self.erro("POST", "api/items", {"room": "varanda", "name": "X", "photos": photos}, 400, "Lista de fotos inválida.")

    def test_foto_com_caminho_ou_que_nao_e_texto_recusada(self):
        for nome in ("../inventario.json", "photos/sala-1.jpg", "sala-1.gif", 123, None):
            with self.subTest(foto=nome):
                self.erro("POST", "api/items", {"room": "varanda", "name": "X", "photos": [nome]}, 400, FOTO_SUMIU)

    def test_so_a_miniatura_nao_vale_como_foto(self):
        helpers.write_file(self.app.path("data", "thumbs", "so-a-miniatura.jpg"), helpers.jpeg())
        self.erro("POST", "api/items", {"room": "varanda", "name": "X", "photos": ["so-a-miniatura.jpg"]}, 400, FOTO_SUMIU)

    def test_origem_das_fotos_so_com_endereco_da_internet(self):
        it = self.novo(photos=["sala-1.jpg"], photoSrc={"sala-1.jpg": "javascript:alert(1)", "sala-2.jpg": "https://loja.exemplo/p"})
        self.assertNotIn("photoSrc", it, "nenhuma origem valeu: o campo nem aparece")
        it = self.novo(photos=["sala-1.jpg"], photoSrc={"sala-1.jpg": "https://loja.exemplo/p"})
        self.assertEqual(it["photoSrc"], {"sala-1.jpg": "https://loja.exemplo/p"})

    def test_campos_a_mais_sao_ignorados(self):
        it = self.novo(foo="bar", id="meu-codigo", seq=900, createdAt="2000-01-01T00:00:00-03:00", updatedBy="outro", approx=False,
                       valueAt="2000-01-01", rev=1)
        self.assertNotIn("foo", it)
        self.assertEqual(it["valueAt"], it["createdAt"], "a data do valor não vem do pedido")
        self.assertNotIn("rev", it)
        self.assertNotIn("updatedBy", it)
        self.assertNotEqual(it["id"], "meu-codigo", "só o Desfazer escolhe o código")
        self.assertNotEqual(it["seq"], 900)
        self.assertTrue(it["approx"])
        self.assertNotEqual(it["createdAt"], "2000-01-01T00:00:00-03:00")

    def test_desfazer_exclusao_volta_com_o_mesmo_codigo_numero_e_autor(self):
        st, _, out = self.app.post("api/items", {"room": "varanda", "name": "Bicicleta de criança", "value": 300}, headers={"X-Remote-User-Name": "ana"})
        it = out["item"]
        self.app.ok("DELETE", f"api/items/{it['id']}")
        volta = self.app.ok("POST", "api/items", {**it, "_restore": True}, headers={"X-Remote-User-Name": "bia"})["item"]
        self.addCleanup(self.app.delete, f"api/items/{volta['id']}")
        self.assertEqual((volta["id"], volta["seq"], volta["createdAt"], volta["createdBy"], volta["value"]),
                         (it["id"], it["seq"], it["createdAt"], "ana", 300))
        self.assertNotIn("_restore", volta)

    def test_desfazer_mantem_as_datas_do_item(self):
        datas = {"createdAt": "2026-01-10T10:00:00-03:00", "updatedAt": "2026-02-10T10:00:00-03:00", "valueAt": "2026-03-10T10:00:00-03:00",
                 "checkedAt": "2026-04-10T10:00:00-03:00"}
        it = self.novo(name="Volta como era", checked=True, _restore=True, **datas)
        self.assertEqual({k: it[k] for k in datas}, datas)

    def test_desfazer_de_item_antigo_sem_data_do_valor_usa_a_do_cadastro(self):
        it = self.novo(name="Antigo", _restore=True, createdAt="2025-05-01T09:00:00-03:00")
        self.assertEqual(it["valueAt"], "2025-05-01T09:00:00-03:00")

    def test_gravado_no_arquivo_antes_de_responder(self):
        it = self.novo(name="Gravado na hora")
        self.assertIn(it["id"], [i["id"] for i in self.app.stored()["items"]])

    def test_corpo_com_bytes_que_nao_sao_utf8_recusado(self):
        st, _, out = self.app.request("POST", "api/items", raw=b'{"room": "varanda", "name": "\xff\xfe"}', headers=JSON)
        self.assertEqual((st, out["error"]), (400, "Pedido inválido (JSON)."))

    def test_corpo_em_partes_grande_demais_recusado_sem_ler_tudo(self):
        n = len(self.app.stored()["items"])
        st, body = troca(self.app, b"POST /api/items HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
                         + b"%x\r\n" % (31 * 1024 * 1024) + b'{"room": "varanda"')
        self.assertEqual(st, 413, "o tamanho anunciado já basta para recusar")
        self.assertIn("Arquivo grande demais.", body.decode())
        self.assertEqual(len(self.app.stored()["items"]), n)

    def test_corpo_em_partes_com_tamanho_que_nao_e_numero_recusado(self):
        st, body = troca(self.app, b"POST /api/items HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
                         b"zz\r\n{}\r\n0\r\n\r\n")
        self.assertEqual(st, 400)
        self.assertIn("Pedido inválido.", body.decode())

class EditarItem(ItensCase):
    def test_so_muda_o_que_veio(self):
        it = self.novo(name="Cadeira", details="de ferro", value=120, cat="moveis")
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"details": "de ferro, pintada"})["item"]
        self.assertEqual((out["name"], out["details"], out["value"], out["cat"], out["room"], out["seq"]),
                         ("Cadeira", "de ferro, pintada", 120, "moveis", "varanda", it["seq"]))

    def test_responde_200_com_o_item_e_a_revisao(self):
        it = self.novo()
        r0 = self.rev()
        st, _, out = self.app.put(f"api/items/{it['id']}", {"name": "Outro nome"})
        self.assertEqual((st, set(out), out["rev"]), (200, {"item", "rev"}, r0 + 1))

    def test_valor_novo_marca_a_data_do_valor(self):
        it = self.novo(value=100, _restore=True, valueAt="2026-01-01T00:00:00-03:00")
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"value": "150,00"})["item"]
        self.assertEqual(out["value"], 150)
        self.assertTrue(out["valueAt"].startswith(out["updatedAt"][:10]), "a data em que o valor mudou (o GerencIA deprecia daí)")

    def test_mesmo_valor_escrito_de_outro_jeito_nao_mexe_na_data_do_valor(self):
        it = self.novo(value=1200, _restore=True, valueAt="2026-01-01T00:00:00-03:00")
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"value": "1.200,00", "name": "Renomeado"})["item"]
        self.assertEqual(out["valueAt"], "2026-01-01T00:00:00-03:00")

    def test_erro_de_validacao_nao_muda_nada(self):
        it = self.novo(name="Mesa", details="de madeira")
        r0 = self.rev()
        for body, msg in (({"details": "mudou", "name": ""}, "Preencha o campo nome."), ({"name": "Mudou", "value": "caro"}, VALOR_INVALIDO),
                          ({"name": "Mudou", "photos": ["sumiu.jpg"]}, FOTO_SUMIU), ({"name": "Mudou", "room": "nao-existe"}, SEM_COMODO)):
            with self.subTest(body=body):
                self.erro("PUT", f"api/items/{it['id']}", body, 400, msg)
                self.assertEqual(self.item(it["id"]), it, "nada vale pela metade")
        self.assertEqual(self.rev(), r0)

    def test_mover_de_comodo_mantem_o_codigo_e_ganha_numero_novo(self):
        it = self.novo(name="Escada dobrável")
        maior = max(i["seq"] for i in self.app.data()["items"] if i["room"] == "lavanderia")
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"room": "lavanderia"})["item"]
        self.assertEqual((out["id"], out["room"], out["seq"]), (it["id"], "lavanderia", maior + 1))

    def test_mesmo_comodo_nao_muda_o_numero(self):
        it = self.novo()
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"room": "varanda", "name": "Mesmo lugar"})["item"]
        self.assertEqual(out["seq"], it["seq"])

    def test_conflito_nao_grava_nem_sobe_a_revisao(self):
        it = self.novo(name="Original")
        r0 = self.rev()
        st, _, out = self.app.put(f"api/items/{it['id']}", {"name": "Velho", "_base": "2000-01-01T00:00:00-03:00"})
        self.assertEqual(st, 409)
        self.assertEqual(out["error"], "Este item foi alterado em outro aparelho. Confira a versão atual antes de salvar.")
        self.assertEqual(out["item"], it, "a resposta traz a versão atual")
        self.assertEqual((self.item(it["id"])["name"], self.rev()), ("Original", r0))

    def test_base_vazia_nao_confere(self):
        it = self.novo()
        for base in ("", None):
            with self.subTest(base=base):
                self.assertEqual(self.app.put(f"api/items/{it['id']}", {"name": f"Sem base {base!r}", "_base": base})[0], 200)

    def test_base_nao_fica_guardada_no_item(self):
        it = self.novo()
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"name": "Com base", "_base": it["updatedAt"]})["item"]
        self.assertNotIn("_base", out)

    def test_campos_a_mais_ignorados_na_edicao(self):
        it = self.novo(headers={"X-Remote-User-Name": "ana"})
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"id": "outro", "seq": 999, "createdAt": "2000-01-01", "createdBy": "intruso",
                                                           "approx": False, "source": "voz", "foo": 1})["item"]
        self.assertEqual((out["id"], out["seq"], out["createdAt"], out["createdBy"], out["approx"], out["source"]),
                         (it["id"], it["seq"], it["createdAt"], "ana", True, "manual"))
        self.assertNotIn("foo", out)

    def test_quem_editou_fica_e_quem_criou_nao_muda(self):
        it = self.novo(headers={"X-Remote-User-Name": "ana"})
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"name": "Editado pela Bia"}, headers={"X-Remote-User-Name": "bia"})["item"]
        self.assertEqual((out["createdBy"], out["updatedBy"]), ("ana", "bia"))
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"name": "Editado sem usuário"})["item"]
        self.assertEqual(out["updatedBy"], "bia", "sem usuário, fica quem editou por último")

    def test_conferido_de_novo_nao_troca_a_data(self):
        it = self.novo()
        primeira = self.app.ok("PUT", f"api/items/{it['id']}", {"checked": True})["item"]["checkedAt"]
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"checked": True, "name": "Ainda conferido"})["item"]
        self.assertEqual(out["checkedAt"], primeira)
        self.assertNotIn("checkedAt", self.app.ok("PUT", f"api/items/{it['id']}", {"checked": False})["item"])

    def test_fotos_novas_tiram_a_origem_das_que_sairam(self):
        src = {"sala-1.jpg": "https://loja.exemplo/a", "sala-2.jpg": "https://loja.exemplo/b"}
        it = self.novo(photos=["sala-1.jpg", "sala-2.jpg"], photoSrc=src)
        self.assertEqual(it["photoSrc"], src)
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"photos": ["sala-2.jpg"]})["item"]
        self.assertEqual(out["photoSrc"], {"sala-2.jpg": "https://loja.exemplo/b"})
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"photos": []})["item"]
        self.assertNotIn("photoSrc", out)

    def test_so_a_origem_usa_as_fotos_que_o_item_ja_tem(self):
        it = self.novo(photos=["sala-1.jpg"])
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"photoSrc": {"sala-1.jpg": "https://loja.exemplo/a", "sala-3.jpg": "https://x.exemplo"}})["item"]
        self.assertEqual((out["photos"], out["photoSrc"]), (["sala-1.jpg"], {"sala-1.jpg": "https://loja.exemplo/a"}))

    def test_categoria_que_nao_existe_vai_para_outros(self):
        it = self.novo(cat="moveis")
        self.assertEqual(self.app.ok("PUT", f"api/items/{it['id']}", {"cat": "nao-existe"})["item"]["cat"], "outros")

    def test_quantidade_e_observacao_vazias(self):
        it = self.novo(qty="2", flag="Ver garantia")
        out = self.app.ok("PUT", f"api/items/{it['id']}", {"qty": "", "flag": ""})["item"]
        self.assertEqual((out["qty"], out["flag"]), ("1", None))

    def test_corpo_vazio_so_regrava(self):
        it = self.novo(name="Intacto")
        r0 = self.rev()
        out = self.app.ok("PUT", f"api/items/{it['id']}", None)["item"]
        self.assertEqual({k: v for k, v in out.items() if k != "updatedAt"}, {k: v for k, v in it.items() if k != "updatedAt"})
        self.assertEqual(self.rev(), r0 + 1)

    def test_item_inexistente_404_com_mensagem(self):
        self.erro("PUT", "api/items/nao-existe-999", {"name": "x"}, 404, "Este item não existe mais. Atualize a página.")

    def test_codigo_com_caracteres_fora_do_padrao_nao_e_rota(self):
        for iid in ("sal.001", "sal%20001", "sal-001/extra"):
            with self.subTest(id=iid):
                self.erro("PUT", f"api/items/{iid}", {"name": "x"}, 404, "Endereço não encontrado.")

    def test_corpo_que_nao_e_json_recusado_sem_mudar_nada(self):
        it = self.novo(name="Firme")
        st, _, out = self.app.request("PUT", f"api/items/{it['id']}", raw=b"name=Mole", headers=JSON)
        self.assertEqual((st, out["error"]), (400, "Pedido inválido (JSON)."))
        self.assertEqual(self.item(it["id"])["name"], "Firme")


class ExcluirItem(ItensCase):
    def criar(self, **campos):
        return self.app.ok("POST", "api/items", {"room": "varanda", "name": "Para excluir", **campos})["item"]

    def test_devolve_o_item_excluido_e_a_revisao(self):
        it = self.criar()
        r0 = self.rev()
        st, _, out = self.app.delete(f"api/items/{it['id']}")
        self.assertEqual((st, out["item"], out["rev"]), (200, it, r0 + 1))

    def test_some_dos_dados_e_do_arquivo(self):
        it = self.criar()
        self.app.ok("DELETE", f"api/items/{it['id']}")
        self.assertIsNone(self.item(it["id"]))
        self.assertNotIn(it["id"], [i["id"] for i in self.app.stored()["items"]])

    def test_inexistente_404_com_mensagem(self):
        self.erro("DELETE", "api/items/nao-existe-999", None, 404, "Este item não existe mais.")

    def test_fotos_ficam_para_o_desfazer(self):
        foto = self.upload_photo()
        it = self.criar(photos=[foto])
        self.app.ok("DELETE", f"api/items/{it['id']}")
        self.assertEqual(self.app.get(f"photos/{foto}")[0], 200)
        self.assertEqual(self.app.get(f"thumbs/{foto}")[0], 200)

    def test_corpo_json_e_aceito_e_ignorado(self):
        it = self.criar()
        st, _, out = self.app.request("DELETE", f"api/items/{it['id']}", {"motivo": "quebrou"})
        self.assertEqual((st, out["item"]["id"]), (200, it["id"]))

    def test_excluir_nao_mexe_nos_outros_itens_do_comodo(self):
        a, b = self.criar(name="Fica"), self.criar(name="Sai")
        self.addCleanup(self.app.delete, f"api/items/{a['id']}")
        self.app.ok("DELETE", f"api/items/{b['id']}")
        self.assertEqual(self.item(a["id"]), a)


class Lote(ItensCase):
    def lote(self, body, headers=None):
        st, _, out = self.app.post("api/items/batch", body, headers=headers)
        if st == 201:
            for it in out["items"]:
                self.addCleanup(self.app.delete, f"api/items/{it['id']}")
        return st, out

    def test_numeros_seguidos_e_codigos_unicos(self):
        maior = max(i["seq"] for i in self.app.data()["items"] if i["room"] == "escritorio")
        st, out = self.lote({"items": [{"room": "escritorio", "name": n} for n in ("Grampeador", "Régua", "Estojo")]})
        self.assertEqual(st, 201)
        self.assertEqual([i["seq"] for i in out["items"]], [maior + 1, maior + 2, maior + 3])
        self.assertEqual([i["id"] for i in out["items"]], [f"esc-{maior + n:03d}" for n in (1, 2, 3)])

    def test_grava_uma_vez_so(self):
        r0 = self.rev()
        st, out = self.lote({"items": [{"room": "cozinha", "name": "Garfo"}, {"room": "cozinha", "name": "Faca"}]})
        self.assertEqual((st, out["rev"], self.rev()), (201, r0 + 1, r0 + 1))

    def test_responde_itens_revisao_e_comodos(self):
        st, out = self.lote({"items": [{"room": "cozinha", "name": "Colher"}]})
        self.assertEqual(set(out), {"items", "rev", "rooms"})
        self.assertEqual([r["id"] for r in out["rooms"]], [r["id"] for r in self.app.data()["rooms"]])

    def test_lote_de_60_aceito(self):
        st, out = self.lote({"items": [{"room": "quarto", "name": f"Livro {n}"} for n in range(60)]})
        self.assertEqual((st, len(out["items"])), (201, 60))

    def test_sem_itens_mensagem(self):
        for body in ({}, {"items": []}, {"items": None}, {"items": {"room": "sala"}}):
            with self.subTest(body=body):
                self.erro("POST", "api/items/batch", body, 400, "Envie de 1 a 60 itens.")

    def test_item_ruim_traz_a_mensagem_dele_e_nada_entra(self):
        r0 = self.rev()
        self.erro("POST", "api/items/batch", {"items": [{"room": "cozinha", "name": "Bom"}, {"room": "cozinha", "name": "Ruim", "value": "caro"}]},
                  400, VALOR_INVALIDO)
        self.assertEqual(self.rev(), r0)
        self.assertFalse(any(i["name"] == "Bom" for i in self.app.data()["items"]))

    def test_foto_do_comodo_que_nao_existe_e_ignorada(self):
        antes = next(r for r in self.app.data()["rooms"] if r["id"] == "cozinha")["photos"]
        st, out = self.lote({"items": [{"room": "cozinha", "name": "Pano"}], "roomPhoto": {"room": "cozinha", "file": "nao-existe.jpg", "label": "x"}})
        self.assertEqual(st, 201)
        self.assertEqual(next(r for r in out["rooms"] if r["id"] == "cozinha")["photos"], antes)

    def test_foto_que_o_comodo_ja_tem_nao_repete(self):
        antes = next(r for r in self.app.data()["rooms"] if r["id"] == "cozinha")["photos"]
        st, out = self.lote({"items": [{"room": "cozinha", "name": "Pote"}], "roomPhoto": {"room": "cozinha", "file": antes[0]["file"], "label": "Outra legenda"}})
        self.assertEqual(next(r for r in out["rooms"] if r["id"] == "cozinha")["photos"], antes)

    def test_foto_para_comodo_inexistente_e_ignorada(self):
        st, out = self.lote({"items": [{"room": "cozinha", "name": "Bule"}], "roomPhoto": {"room": "nao-existe", "file": "sala-1.jpg"}})
        self.assertEqual(st, 201)

    def test_foto_vai_para_o_comodo_indicado_com_a_legenda(self):
        foto = self.upload_photo()
        st, out = self.lote({"items": [{"room": "sala", "name": "Abajur"}], "roomPhoto": {"room": "varanda", "file": foto, "label": "Canto da rede"}})
        self.addCleanup(self.app.put, "api/rooms/varanda", {"photos": [{"file": "varanda-1.jpg", "label": "Mesinha e bicicleta"}]})
        varanda = next(r for r in out["rooms"] if r["id"] == "varanda")
        self.assertEqual(varanda["photos"][-1], {"file": foto, "label": "Canto da rede"})
        self.assertFalse(any(p["file"] == foto for r in out["rooms"] if r["id"] == "sala" for p in r["photos"]))

    def test_quem_cadastrou_vale_para_todos(self):
        st, out = self.lote({"items": [{"room": "sala", "name": "A"}, {"room": "quarto", "name": "B"}]}, headers={"X-Remote-User-Display-Name": "Carla"})
        self.assertEqual([(i["createdBy"], i["updatedBy"]) for i in out["items"]], [("Carla", "Carla")] * 2)

    def test_lote_nao_escolhe_codigo_nem_com_restore(self):
        st, out = self.lote({"items": [{"room": "sala", "name": "A", "id": "codigo-meu", "seq": 500, "_restore": True}]})
        self.assertEqual(st, 201)
        self.assertNotEqual((out["items"][0]["id"], out["items"][0]["seq"]), ("codigo-meu", 500))

    def test_foto_do_comodo_ruim_nao_deixa_itens_pela_metade(self):
        n, r0 = len(self.app.data()["items"]), self.rev()
        for room_photo in ({"room": "cozinha", "file": "sala-2.jpg", "label": "x" * 161}, "sala-2.jpg"):
            with self.subTest(roomPhoto=str(room_photo)[:30]):
                st, _, out = self.app.post("api/items/batch", {"items": [{"room": "cozinha", "name": "Fantasma"}], "roomPhoto": room_photo})
                self.assertGreaterEqual(st, 400, out)
                self.assertEqual(len(self.app.data()["items"]), n, "nada do lote fica, nem na memória")
        self.app.ok("PUT", "api/settings", {"zones": False})
        self.assertEqual((len(self.app.stored()["items"]), self.rev()), (n, r0), "nem numa gravação seguinte")

    def test_item_que_nao_e_objeto_recusado(self):
        n = len(self.app.data()["items"])
        for itens in ([1], [{"room": "cozinha", "name": "Bom"}, "Ruim"], [None]):
            with self.subTest(itens=itens):
                self.erro("POST", "api/items/batch", {"items": itens}, 400, "Item inválido.")
        self.assertEqual(len(self.app.data()["items"]), n)


if __name__ == "__main__":
    unittest.main()
