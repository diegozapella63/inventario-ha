"""Importar: abrir o arquivo enviado, ver o que tem nele, extrair as fotos com segurança, restaurar e os envios em partes.

_open_zip, inspect_file (zip com e sem inventario.json, json solto, arquivo que não é nem um nem outro, json inválido,
inventário sem cômodos), _zip_inventory, _media_entries, _extract_media (../, caminhos absolutos, nomes estranhos,
arquivos que não são imagem, repetidos, limites de tamanho), restore_zip (troca tudo ou só acrescenta as fotos de uma
parte, fotos novas contadas) e upload_paths, upload_meta, cleanup_uploads, drop_upload e as rotas do envio em partes.
"""
import io
import json
import os
import shutil
import time
import unittest
import zipfile
from unittest import mock

from _boot import UnitBase, helpers, server as S

UID = "0123456789abcdef"


class Resposta:
    """Um pedido de mentira para chamar as funções das rotas direto; guarda o que seria enviado ao navegador."""
    send_bytes = S.Handler.send_bytes
    send_json = S.Handler.send_json

    def __init__(self, body=None, command="POST"):
        self.body, self.command = body or {}, command
        self.status, self.headers, self.wfile = None, {}, io.BytesIO()

    def read_body(self):
        return self.body

    def send_response(self, status):
        self.status = status

    def send_header(self, k, v):
        self.headers[k] = v

    def end_headers(self):
        pass

    def json(self):
        return json.loads(self.wfile.getvalue())


class InfoFalsa:
    """Uma entrada de .zip só com nome e tamanho (para os limites de tamanho, sem gravar gigabytes)."""

    def __init__(self, nome, tamanho):
        self.filename, self.file_size = nome, tamanho

    def is_dir(self):
        return False


class ZipFalso:
    def __init__(self, infos):
        self.infos, self.abertos = infos, []

    def infolist(self):
        return self.infos

    def open(self, info):
        self.abertos.append(info.filename)
        return io.BytesIO(b"\xff\xd8 foto pequena")


def arquivo(nome, conteudo) -> str:
    return helpers.write_file(os.path.join(S.TMP_DIR, nome), conteudo)


def inventario(**mudar) -> str:
    d = helpers.fixture_data()
    d.update(mudar)
    return json.dumps(d)


def pouco(n_comodos=1) -> dict:
    """Um inventário pequeno, de outra casa inventada."""
    rooms = [{"id": f"r{n}", "name": f"Cômodo {n}"} for n in range(1, n_comodos + 1)]
    return {"rooms": rooms, "items": [{"id": "i1", "room": "r1", "name": "Banqueta"}] if rooms else []}


class ZipBase(UnitBase):
    def zip(self, files) -> zipfile.ZipFile:
        z = zipfile.ZipFile(io.BytesIO(helpers.zip_bytes(files)))
        self.addCleanup(z.close)
        return z

    def entradas(self, files):
        return [(kind, name) for _, kind, name in S._media_entries(self.zip(files))]


class AbrirZip(UnitBase):
    def test_abre_um_zip_valido(self):
        p = arquivo("a.zip", helpers.zip_bytes({"inventario.json": "{}", "photos/a.jpg": helpers.jpeg()}))
        with S._open_zip(p) as z:
            self.assertEqual(sorted(z.namelist()), ["inventario.json", "photos/a.jpg"])

    def test_arquivo_que_nao_e_zip(self):
        self.assertApiError(400, S._open_zip, arquivo("b.zip", "só texto"), msg_part="não é um .zip válido")

    def test_arquivo_vazio(self):
        self.assertApiError(400, S._open_zip, arquivo("c.zip", b""), msg_part="não é um .zip válido")


class OQueTemNoArquivo(UnitBase):
    def test_json_que_nao_e_inventario(self):
        for conteudo in ('{"nome": "lista de compras"}', "[]", '"texto"', '{"rooms": [], "items": "nada"}'):
            with self.subTest(conteudo=conteudo):
                self.assertApiError(400, S.inspect_file, arquivo("x.json", conteudo), msg_part="não parece um inventário")

    def test_inventario_sem_comodos_em_json(self):
        p = arquivo("vazio.json", json.dumps({"rooms": [], "items": []}))
        self.assertEqual(S.inspect_file(p), {"kind": "json", "hasData": True, "items": 0, "rooms": 0, "photos": 0})

    def test_inventario_sem_comodos_em_zip(self):
        p = arquivo("vazio.zip", helpers.zip_bytes({"inventario.json": json.dumps({"rooms": [], "items": []}), "photos/a.jpg": helpers.jpeg()}))
        self.assertEqual(S.inspect_file(p), {"kind": "backup", "hasData": True, "items": 0, "rooms": 0, "photos": 1})

    def test_foto_jpg_nao_e_backup(self):
        self.assertApiError(400, S.inspect_file, arquivo("foto.jpg", helpers.jpeg()), msg_part="Use um backup .zip ou um .json")

    def test_texto_qualquer_nao_e_backup(self):
        self.assertApiError(400, S.inspect_file, arquivo("notas.txt", "lista de compras: pão, leite"), msg_part="Use um backup .zip")

    def test_arquivo_vazio_nao_e_backup(self):
        self.assertApiError(400, S.inspect_file, arquivo("vazio.json", b""), msg_part="Use um backup .zip")

    def test_json_em_latin1_e_recusado(self):
        conteudo = '{"rooms": [{"id": "esc", "name": "Escritório"}], "items": []}'.encode("latin-1")
        self.assertApiError(400, S.inspect_file, arquivo("latin.json", conteudo), msg_part="Use um backup .zip")

    def test_zip_com_nome_de_json_e_reconhecido_pelo_conteudo(self):
        p = arquivo("backup.json", helpers.zip_bytes({"inventario.json": inventario()}))
        self.assertEqual(S.inspect_file(p)["kind"], "backup", "vale o que tem dentro, não o nome")

    def test_inventario_so_na_pasta_macosx_nao_conta(self):
        p = arquivo("mac.zip", helpers.zip_bytes({"__MACOSX/inventario.json": inventario(), "LEIA-ME.txt": "x"}))
        self.assertApiError(400, S.inspect_file, p, msg_part="não tem inventário nem fotos")

    def test_imagens_fora_das_pastas_do_app_nao_contam(self):
        p = arquivo("soltas.zip", helpers.zip_bytes({"x.jpg": helpers.jpeg(), "fotos/y.jpg": helpers.jpeg(), "photos/sub/z.jpg": helpers.jpeg()}))
        self.assertApiError(400, S.inspect_file, p, msg_part="não tem inventário nem fotos")

    def test_conta_so_as_fotos_com_nome_aceito(self):
        files = {f"photos/{n}": helpers.jpeg() for n in ("a.jpg", "b.png", "c.webp", "d.jpeg", "e.gif", "f g.jpg", ".h.jpg", "i.txt")}
        self.assertEqual(S.inspect_file(arquivo("p.zip", helpers.zip_bytes(files)))["photos"], 4)

    def test_parte_so_de_fotos_conta_as_fotos_e_nao_as_miniaturas(self):
        files = {"photos/a.jpg": helpers.jpeg(), "photos/b.jpg": helpers.jpeg(), "thumbs/a.jpg": helpers.jpeg(), "thumbs/b.jpg": helpers.jpeg()}
        self.assertEqual(S.inspect_file(arquivo("p2.zip", helpers.zip_bytes(files))),
                         {"kind": "photos", "hasData": False, "items": 0, "rooms": 0, "photos": 2})

    def test_olhar_o_arquivo_nao_muda_nada(self):
        rev = self.store.data["rev"]
        p = arquivo("olhar.zip", helpers.zip_bytes({"inventario.json": json.dumps(pouco()), "photos/olhada.jpg": helpers.jpeg()}))
        self.assertEqual(S.inspect_file(p)["rooms"], 1)
        self.assertEqual(self.store.data["rev"], rev)
        self.assertEqual(len(self.store.data["rooms"]), 6)
        self.assertFalse(S.photo_exists("olhada.jpg"), "a foto só entra ao restaurar")
        self.assertEqual(os.listdir(S.SHARE_DIR), [], "nem cópia de segurança")

    def test_inventario_dentro_do_zip_que_nao_e_inventario(self):
        p = arquivo("lista.zip", helpers.zip_bytes({"inventario.json": "[1, 2]"}))
        self.assertApiError(400, S.inspect_file, p, msg_part="não parece um inventário")

    def test_inventario_com_bom_dentro_do_zip_e_aceito(self):
        p = arquivo("bom.zip", helpers.zip_bytes({"inventario.json": "﻿" + inventario()}))
        self.assertEqual(S.inspect_file(p), {"kind": "backup", "hasData": True, "items": 38, "rooms": 6, "photos": 0})


class InventarioDoZip(ZipBase):
    def test_sem_inventario_devolve_none(self):
        self.assertIsNone(S._zip_inventory(self.zip({"photos/a.jpg": helpers.jpeg()})))

    def test_usa_o_inventario_mais_perto_da_raiz(self):
        z = self.zip({"a/b/inventario.json": json.dumps(pouco(3)), "inventario.json": json.dumps(pouco(2)), "a/inventario.json": json.dumps(pouco(1))})
        self.assertEqual(len(S._zip_inventory(z)["rooms"]), 2)

    def test_ignora_a_copia_do_macosx(self):
        z = self.zip({"__MACOSX/inventario.json": "lixo do Finder", "backup/inventario.json": json.dumps(pouco(2))})
        self.assertEqual(len(S._zip_inventory(z)["rooms"]), 2)

    def test_nomes_parecidos_nao_contam(self):
        z = self.zip({"meu-inventario.json": json.dumps(pouco()), "inventario.json.bak": json.dumps(pouco()), "inventario.JSON": json.dumps(pouco())})
        self.assertIsNone(S._zip_inventory(z))

    def test_texto_que_nao_e_utf8_e_corrompido(self):
        z = self.zip({"inventario.json": '{"rooms": [{"id": "s", "name": "Escritório"}], "items": []}'.encode("latin-1")})
        self.assertApiError(400, S._zip_inventory, z, msg_part="corrompido")

    def test_completa_o_formato_antigo(self):
        antigo = {"rooms": [{"id": "sala", "name": "Sala", "photos": ["s.jpg"]}],
                  "items": [{"id": "i1", "room": "sala", "name": "Poltrona", "photo": "p.jpg"}, {"id": "i2", "room": "sala", "name": "Pufe"}]}
        d = S._zip_inventory(self.zip({"inventario.json": json.dumps(antigo)}))
        sala = d["rooms"][0]
        self.assertEqual((sala["code"], sala["cover"], sala["photos"]), ("SAL", 0, [{"file": "s.jpg", "label": ""}]))
        self.assertEqual(d["items"][0]["photos"], ["p.jpg"])
        self.assertNotIn("photo", d["items"][0])
        self.assertEqual(d["items"][1]["photos"], [])


class FotosDoZip(ZipBase):
    def test_acha_fotos_e_miniaturas_em_qualquer_nivel(self):
        files = {"photos/a.jpg": b"1", "x/y/thumbs/a.jpg": b"2", "backup/photos/b.png": b"3", "inventario.json": "{}"}
        self.assertEqual(sorted(self.entradas(files)), [("photos", "a.jpg"), ("photos", "b.png"), ("thumbs", "a.jpg")])

    def test_pula_pastas_e_a_pasta_macosx(self):
        z = zipfile.ZipFile(io.BytesIO(helpers.zip_bytes({"photos/": b"", "photos/ok.jpg": b"1", "__MACOSX/photos/ok.jpg": b"lixo",
                                                          "__MACOSX/photos/._ok.jpg": b"lixo"})))
        self.addCleanup(z.close)
        self.assertEqual([(i.filename, kind, name) for i, kind, name in S._media_entries(z)], [("photos/ok.jpg", "photos", "ok.jpg")])

    def test_so_vale_a_pasta_logo_acima_do_arquivo(self):
        files = {"photos/sub/a.jpg": b"1", "a.jpg": b"2", "Photos/b.jpg": b"3", "fotos/c.jpg": b"4", "photos.jpg": b"5", "thumbs2/d.jpg": b"6"}
        self.assertEqual(self.entradas(files), [])

    def test_aceita_jpg_jpeg_png_e_webp(self):
        files = {f"photos/{n}": b"1" for n in ("a.jpg", "b.jpeg", "c.png", "d.webp")}
        self.assertEqual(sorted(n for _, n in self.entradas(files)), ["a.jpg", "b.jpeg", "c.png", "d.webp"])

    def test_recusa_o_que_nao_e_foto(self):
        files = {f"photos/{n}": b"1" for n in ("e.gif", "f.svg", "g.html", "h.txt", "sem-extensao", "j.jpg.exe", "k.heic", "l.js")}
        self.assertEqual(self.entradas(files), [])

    def test_recusa_nomes_estranhos(self):
        nomes = ("foto com espaço.jpg", "fotó.jpg", ".oculta.jpg", "-traco.jpg", "_baixo.jpg", "a" * 152 + ".jpg", "..jpg", "a;b.jpg", "a$b.jpg")
        self.assertEqual(self.entradas({f"photos/{n}": b"1" for n in nomes}), [])


class ExtrairFotos(ZipBase):
    def todos_os_arquivos(self):
        raiz = os.path.dirname(S.DATA_DIR)
        return {os.path.join(d, n) for d, _, ns in os.walk(raiz) for n in ns}

    def test_grava_fotos_e_miniaturas_nas_pastas_do_app(self):
        foto, mini = helpers.fixture_photo("sala-2.jpg"), helpers.fixture_photo("sala-3.jpg")
        added = S._extract_media(self.zip({"backup/photos/n1.jpg": foto, "backup/thumbs/n1.jpg": mini}))
        self.assertEqual(added, 1, "a miniatura não conta como foto nova")
        with open(os.path.join(S.PHOTOS_DIR, "n1.jpg"), "rb") as f:
            self.assertEqual(f.read(), foto)
        with open(os.path.join(S.THUMBS_DIR, "n1.jpg"), "rb") as f:
            self.assertEqual(f.read(), mini)

    def test_conta_so_as_fotos_novas(self):
        z = self.zip({"photos/sala-1.jpg": b"ja existe", "photos/n1.jpg": b"1", "photos/n2.jpg": b"2", "thumbs/n3.jpg": b"3"})
        self.assertEqual(S._extract_media(z), 2)

    def test_nada_novo_conta_zero(self):
        self.assertEqual(S._extract_media(self.zip({"photos/sala-1.jpg": b"x", "thumbs/sala-1.jpg": b"x"})), 0)

    def test_ponto_ponto_no_caminho_nao_sai_da_pasta(self):
        antes = self.todos_os_arquivos()
        z = self.zip({"../../photos/fora1.jpg": b"1", "photos/../../fora2.jpg": b"2", "photos/../fora3.jpg": b"3", "photos/../thumbs/fora4.jpg": b"4"})
        S._extract_media(z)
        novos = sorted(os.path.relpath(p, S.DATA_DIR) for p in self.todos_os_arquivos() - antes)
        self.assertEqual(novos, [os.path.join("photos", "fora1.jpg"), os.path.join("thumbs", "fora4.jpg")],
                         "só o nome do arquivo vale; nada fora de photos/ e thumbs/")

    def test_caminho_absoluto_vai_para_a_pasta_do_app(self):
        S._extract_media(self.zip({"/photos/abs1.jpg": b"1", "/etc/photos/abs2.jpg": b"2"}))
        self.assertTrue(S.photo_exists("abs1.jpg") and S.photo_exists("abs2.jpg"))
        self.assertFalse(os.path.exists("/photos/abs1.jpg"))
        self.assertFalse(os.path.exists("/etc/photos/abs2.jpg"))

    def test_barra_invertida_nao_e_extraida(self):
        antes = self.todos_os_arquivos()
        self.assertEqual(S._extract_media(self.zip({"photos\\inv1.jpg": b"1", "..\\..\\photos\\inv2.jpg": b"2"})), 0)
        self.assertEqual(self.todos_os_arquivos(), antes)

    def test_arquivo_que_nao_e_imagem_fica_de_fora(self):
        antes = set(os.listdir(S.PHOTOS_DIR))
        S._extract_media(self.zip({"photos/leia.txt": b"x", "photos/pagina.html": b"<script>", "photos/desenho.svg": b"<svg/>"}))
        self.assertEqual(set(os.listdir(S.PHOTOS_DIR)), antes)

    def test_foto_repetida_em_duas_pastas_entra_uma_vez(self):
        z = self.zip({"parte1/photos/rep.jpg": b"primeira", "parte2/photos/rep.jpg": b"segunda"})
        self.assertEqual(S._extract_media(z), 1)
        with open(os.path.join(S.PHOTOS_DIR, "rep.jpg"), "rb") as f:
            self.assertEqual(f.read(), b"primeira", "a primeira fica; a repetida não troca")

    def test_miniatura_que_ja_existe_nao_e_trocada(self):
        with open(os.path.join(S.THUMBS_DIR, "quarto-1.jpg"), "rb") as f:
            original = f.read()
        S._extract_media(self.zip({"thumbs/quarto-1.jpg": b"outra"}))
        with open(os.path.join(S.THUMBS_DIR, "quarto-1.jpg"), "rb") as f:
            self.assertEqual(f.read(), original)

    def test_nao_deixa_temporarios(self):
        S._extract_media(self.zip({"photos/t1.jpg": b"1", "thumbs/t1.jpg": b"1", "photos/t2.png": b"2"}))
        sobras = [n for d in (S.PHOTOS_DIR, S.THUMBS_DIR) for n in os.listdir(d) if n.endswith(".tmp")]
        self.assertEqual(sobras, [])

    def test_arquivo_acima_de_60_mb_e_pulado(self):
        z = ZipFalso([InfoFalsa("photos/grande.jpg", 60 * 1024 * 1024 + 1), InfoFalsa("photos/pequena.jpg", 1000)])
        self.assertEqual(S._extract_media(z), 1)
        self.assertEqual(z.abertos, ["photos/pequena.jpg"], "a grande nem é lida")
        self.assertFalse(S.photo_exists("grande.jpg"))

    def test_total_acima_de_8_gb_e_recusado(self):
        z = ZipFalso([InfoFalsa(f"photos/f{n:03d}.jpg", 59 * 1024 * 1024) for n in range(140)])
        self.assertApiError(400, S._extract_media, z, msg_part="grande demais")
        self.assertLess(len(z.abertos), 140, "para antes de ler tudo")


class RestaurarZip(UnitBase):
    def test_restaurar_marca_a_versao_como_restore(self):
        p = arquivo("r.zip", helpers.zip_bytes({"inventario.json": json.dumps(pouco())}))
        safety, _, trocou = S.restore_zip(p, "antes-de-restaurar")
        self.assertTrue(trocou)
        self.assertTrue(safety["name"].startswith("antes-de-restaurar-"))
        v = self.store.history_list()[0]
        self.assertEqual((v["reason"], v["items"]), ("restore", 38))

    def test_parte_so_de_fotos_nao_guarda_versao_nem_copia(self):
        S.restore_zip(arquivo("p.zip", helpers.zip_bytes({"photos/parte.jpg": helpers.jpeg()})), "antes-de-importar")
        self.assertEqual(self.store.history_list(), [])
        self.assertEqual(os.listdir(S.SHARE_DIR), [])

    def test_casa_vazia_troca_sem_copia_na_share(self):
        self.store.data["rooms"], self.store.data["items"] = [], []
        self.store.save()
        p = arquivo("primeiro.zip", helpers.zip_bytes({"inventario.json": inventario(), "photos/novidade.jpg": helpers.jpeg()}))
        self.assertEqual(S.restore_zip(p, "antes-de-importar"), (None, 1, True))
        self.assertEqual(len(self.store.data["items"]), 38)
        self.assertEqual(os.listdir(S.SHARE_DIR), [])

    def test_itens_podem_citar_fotos_que_chegam_em_outra_parte(self):
        d = pouco()
        d["items"][0]["photos"] = ["p1.jpg", "p2.jpg"]
        parte1 = arquivo("parte1.zip", helpers.zip_bytes({"inventario.json": json.dumps(d), "photos/p1.jpg": helpers.jpeg()}))
        self.assertEqual(S.restore_zip(parte1, "antes-de-importar")[1:], (1, True))
        self.assertEqual(self.store.item("i1")["photos"], ["p1.jpg", "p2.jpg"])
        rev = self.store.data["rev"]
        parte2 = arquivo("parte2.zip", helpers.zip_bytes({"photos/p2.jpg": helpers.jpeg(), "thumbs/p2.jpg": helpers.jpeg()}))
        self.assertEqual(S.restore_zip(parte2, "antes-de-importar"), (None, 1, False))
        self.assertTrue(S.photo_exists("p1.jpg") and S.photo_exists("p2.jpg"))
        self.assertEqual((self.store.data["rev"], self.store.item("i1")["photos"]), (rev, ["p1.jpg", "p2.jpg"]))

    def test_inventario_invalido_nao_traz_fotos(self):
        ruim = {"rooms": [{"id": "r", "name": "R"}], "items": [{"id": "i", "room": "outro"}]}
        p = arquivo("inv.zip", helpers.zip_bytes({"inventario.json": json.dumps(ruim), "photos/naovem.jpg": helpers.jpeg()}))
        self.assertApiError(400, S.restore_zip, p, "antes-de-importar", msg_part="cômodo desconhecido")
        self.assertFalse(S.photo_exists("naovem.jpg"))
        self.assertEqual((len(self.store.data["items"]), os.listdir(S.SHARE_DIR)), (38, []))

    def test_sem_share_restaura_e_guarda_a_versao(self):
        p = arquivo("s.zip", helpers.zip_bytes({"inventario.json": json.dumps(pouco())}))
        with mock.patch.object(S, "SHARE_DIR", "/nao/existe/inventario"):
            self.assertEqual(S.restore_zip(p, "antes-de-importar"), (None, 0, True))
        self.assertEqual([r["name"] for r in self.store.data["rooms"]], ["Cômodo 1"])
        self.assertEqual(self.store.history_list()[0]["reason"], "import")

    def test_zip_exportado_volta_igual(self):
        original = json.loads(json.dumps({k: self.store.data[k] for k in ("rooms", "items")}))
        self.store.create_cat({"name": "Ferramentas"})
        cats = self.store.cats()
        with open(os.path.join(S.TMP_DIR, "exportado.zip"), "wb") as f:
            S.write_zip(f)
        self.store.delete_item("sal-001")
        self.store.update_room("cozinha", {"name": "Copa"})
        self.store.delete_cat("ferramentas")
        S.restore_zip(os.path.join(S.TMP_DIR, "exportado.zip"), "antes-de-importar")
        self.assertEqual(self.store.data["rooms"], original["rooms"])
        self.assertEqual(self.store.data["items"], original["items"])
        self.assertEqual(self.store.cats(), cats)

    def test_backup_sem_categorias_volta_a_lista_padrao(self):
        self.store.create_cat({"name": "Ferramentas"})
        S.restore_zip(arquivo("antigo.zip", helpers.zip_bytes({"inventario.json": inventario()})), "antes-de-restaurar")
        self.assertNotIn("cats", self.store.data)
        self.assertEqual(self.store.cats(), S.default_cats())

    def test_valor_em_texto_nao_impede_restaurar_outro_backup(self):
        d = helpers.fixture_data()
        d["items"][0]["value"] = "1.200,50"
        try:
            self.store.replace_all(d, "import")
        except S.ApiError:
            return  # recusar o arquivo na importação também resolve
        p = arquivo("bom.zip", helpers.zip_bytes({"inventario.json": inventario()}))
        self.assertTrue(S.restore_zip(p, "antes-de-importar")[2])
        self.assertEqual(self.store.item("sal-001")["value"], 1800)


class Envios(UnitBase):
    def envio(self, conteudo: bytes, tamanho=None, uid=UID):
        part, meta = S.upload_paths(uid)
        helpers.write_file(part, conteudo)
        S.write_json_atomic(meta, {"name": "arquivo", "size": len(conteudo) if tamanho is None else tamanho, "created": S.now_iso()})
        return part, meta

    def envelhece(self, *paths, segundos):
        for p in paths:
            os.utime(p, (time.time() - segundos,) * 2)

    def test_caminhos_ficam_na_pasta_temporaria(self):
        part, meta = S.upload_paths(UID)
        self.assertEqual(part, os.path.join(S.TMP_DIR, f"upload-{UID}.part"))
        self.assertEqual(meta, os.path.join(S.TMP_DIR, f"upload-{UID}.json"))

    def test_id_invalido_e_recusado(self):
        for ruim in (UID.upper(), "abc", UID + "0", "g" * 16, None, "", UID[:-1] + "/", "../" + UID[3:]):
            with self.subTest(ruim=ruim):
                self.assertApiError(404, S.upload_paths, ruim, msg_part="Envio não encontrado")

    def test_devolve_os_caminhos_e_o_registro(self):
        part, meta = self.envio(b"abc")
        p, m, info = S.upload_meta(UID)
        self.assertEqual((p, m, info["size"], info["name"]), (part, meta, 3, "arquivo"))

    def test_sem_a_parte_o_envio_expirou(self):
        part, _ = self.envio(b"abc")
        os.unlink(part)
        self.assertApiError(404, S.upload_meta, UID, msg_part="expirou")

    def test_sem_o_registro_o_envio_expirou(self):
        _, meta = self.envio(b"abc")
        os.unlink(meta)
        self.assertApiError(404, S.upload_meta, UID, msg_part="expirou")

    def test_limpeza_mantem_os_envios_recentes(self):
        part, meta = self.envio(b"abc")
        self.envelhece(part, meta, segundos=23 * 3600)
        S.cleanup_uploads()
        self.assertTrue(os.path.exists(part) and os.path.exists(meta), "menos de um dia: o envio pode continuar")

    def test_limpeza_nao_mexe_em_outros_arquivos(self):
        part, meta = self.envio(b"abc")
        outros = [helpers.write_file(os.path.join(S.TMP_DIR, n), b"x") for n in ("exportando.zip", ".tmp-abc.json", "uploads.txt")]
        self.envelhece(part, meta, *outros, segundos=3 * 86400)
        S.cleanup_uploads()
        self.assertFalse(os.path.exists(part) or os.path.exists(meta))
        self.assertTrue(all(os.path.exists(p) for p in outros), "só os arquivos upload- são do envio")

    def test_limpeza_com_idade_escolhida(self):
        part, meta = self.envio(b"abc")
        self.envelhece(part, meta, segundos=600)
        S.cleanup_uploads()
        self.assertTrue(os.path.exists(part))
        S.cleanup_uploads(max_age=300)
        self.assertFalse(os.path.exists(part) or os.path.exists(meta))

    def test_limpeza_sem_a_pasta_temporaria_nao_da_erro(self):
        shutil.rmtree(S.TMP_DIR)
        S.cleanup_uploads()
        self.assertFalse(os.path.exists(S.TMP_DIR))

    def test_cancelar_apaga_as_duas_partes(self):
        part, meta = self.envio(b"abc")
        S.drop_upload(UID)
        self.assertFalse(os.path.exists(part) or os.path.exists(meta))
        S.drop_upload(UID)  # de novo, sem erro (o navegador pode cancelar duas vezes)

    def test_cancelar_com_id_invalido_nao_apaga_nada(self):
        sobra = [helpers.write_file(os.path.join(S.TMP_DIR, f"upload-{s}"), b"x") for s in (".part", ".json")]
        self.assertApiError(404, S.drop_upload, "")
        self.assertTrue(all(os.path.exists(p) for p in sobra))

    def test_cancelar_pela_rota_com_id_invalido(self):
        self.assertApiError(404, S.r_upload_cancel, Resposta(), "zz", query={})

    def test_envio_que_falha_ao_restaurar_e_apagado(self):
        part, meta = self.envio(b"nada disso e backup")
        self.assertApiError(400, S.r_upload_restore, Resposta(), UID, query={}, msg_part="Use um backup .zip")
        self.assertFalse(os.path.exists(part) or os.path.exists(meta), "um envio ruim não fica ocupando espaço")

    def test_envio_incompleto_nao_restaura_e_pode_continuar(self):
        part, meta = self.envio(b"{", tamanho=100)
        rev = self.store.data["rev"]
        self.assertApiError(400, S.r_upload_restore, Resposta(), UID, query={}, msg_part="não terminou")
        self.assertTrue(os.path.exists(part) and os.path.exists(meta))
        self.assertEqual(self.store.data["rev"], rev)

    def test_envio_de_json_completo_troca_o_inventario(self):
        self.envio(json.dumps(pouco(2)).encode())
        h = Resposta()
        S.r_upload_restore(h, UID, query={})
        r = h.json()
        self.assertEqual((r["ok"], r["replaced"], r["photosAdded"], r["items"], r["rooms"]), (True, True, 0, 1, 2))
        self.assertTrue(r["safety"]["name"].startswith("antes-de-importar-"))
        self.assertEqual(r["rev"], self.store.data["rev"])
        self.assertRaises(S.ApiError, S.upload_meta, UID)

    def test_envio_de_zip_so_de_fotos_responde_sem_trocar(self):
        self.envio(helpers.zip_bytes({"photos/enviada.jpg": helpers.jpeg()}))
        h = Resposta()
        S.r_upload_restore(h, UID, query={})
        r = h.json()
        self.assertEqual((r["replaced"], r["photosAdded"], r["safety"], r["items"]), (False, 1, None, 38))
        self.assertTrue(S.photo_exists("enviada.jpg"))

    def test_informacao_do_envio_completo(self):
        self.envio(helpers.zip_bytes({"inventario.json": inventario(), "photos/a.jpg": helpers.jpeg()}))
        h = Resposta(command="GET")
        S.r_upload_info(h, UID, query={})
        self.assertEqual(h.json(), {"kind": "backup", "hasData": True, "items": 38, "rooms": 6, "photos": 1})

    def test_informacao_do_envio_incompleto(self):
        self.envio(b"PK", tamanho=50)
        self.assertApiError(400, S.r_upload_info, Resposta(command="GET"), UID, query={}, msg_part="não terminou")


if __name__ == "__main__":
    unittest.main()
