"""Versões anteriores, exportar (CSV, JSON, ZIP), backups na pasta share e importar."""
import csv
import io
import json
import os
import time
import unittest
import zipfile
from unittest import mock

from _boot import UnitBase, helpers, server as S


def nomes_historico():
    return sorted(n for n in os.listdir(S.HISTORY_DIR) if S.HISTORY_NAME.fullmatch(n))


class Versoes(UnitBase):
    def test_copia_automatica_a_cada_10_minutos(self):
        self.assertEqual(nomes_historico(), [])
        self.store.create_room({"name": "A"})
        self.assertEqual(len(nomes_historico()), 1, "a primeira gravação guarda uma cópia")
        self.store.create_room({"name": "B"})
        self.assertEqual(len(nomes_historico()), 1, "dentro dos 10 minutos, não guarda outra")
        self.store.last_snapshot -= S.HISTORY_EVERY + 1
        time.sleep(1.05)
        self.store.create_room({"name": "C"})
        self.assertEqual(len(nomes_historico()), 2)

    def test_fica_so_com_as_3_mais_recentes(self):
        for i in range(5):
            self.store.last_snapshot = 0
            self.store.create_room({"name": f"R{i}"})
            time.sleep(1.05)
        self.assertEqual(len(nomes_historico()), 3)
        lista = self.store.history_list()
        self.assertEqual([v["name"] for v in lista], sorted(nomes_historico(), reverse=True), "a mais nova primeiro")
        self.assertTrue(all({"date", "size", "items", "rooms", "reason"} <= set(v) for v in lista))
        self.assertEqual(lista[0]["rooms"], 6 + 4, "a cópia é de antes da última gravação")

    def test_versoes_antigas_sao_apagadas_ao_carregar(self):
        for i in range(6):
            helpers.write_file(os.path.join(S.HISTORY_DIR, f"inventario-2026010{i}-120000.json"), "{}")
        S.write_json_atomic(os.path.join(S.HISTORY_DIR, S.HISTORY_REASONS), {"inventario-20260100-120000.json": "import", "inventario-20260105-120000.json": "restore"})
        st = S.Store()
        st.load()
        self.assertEqual(nomes_historico(), ["inventario-20260103-120000.json", "inventario-20260104-120000.json", "inventario-20260105-120000.json"])
        self.assertEqual(S.read_json(os.path.join(S.HISTORY_DIR, S.HISTORY_REASONS)), {"inventario-20260105-120000.json": "restore"},
                         "o motivo de uma cópia apagada sai junto")

    def test_motivo_e_copia_forcada(self):
        self.store.create_room({"name": "A"})
        time.sleep(1.05)
        self.store.snapshot_if_due(force=True, reason="import")
        motivos = [v["reason"] for v in self.store.history_list()]
        self.assertEqual(motivos, ["import", "auto"])
        n = len(nomes_historico())
        self.store.snapshot_if_due(force=True, reason="restore")
        self.assertEqual(len(nomes_historico()), n, "uma cópia forçada logo depois de outra, sem mudança, não repete")

    def test_trocar_tudo_guarda_antes(self):
        novo = {"rooms": [{"id": "r", "name": "Único"}], "items": [{"id": "i1", "room": "r", "name": "Coisa", "photo": "sala-1.jpg"}]}
        rev = self.store.data["rev"]
        self.store.replace_all(novo, "restore")
        self.assertEqual([r["name"] for r in self.store.data["rooms"]], ["Único"])
        it = self.store.data["items"][0]
        self.assertEqual(it["photos"], ["sala-1.jpg"], "o formato antigo (photo) vira a lista photos")
        self.assertNotIn("photo", it)
        self.assertEqual(self.store.data["rooms"][0]["code"], "R")
        self.assertGreater(self.store.data["rev"], rev, "a revisão nunca volta (os aparelhos percebem a troca)")
        self.assertEqual(self.store.history_list()[0]["reason"], "restore")
        self.assertEqual(self.store.history_list()[0]["items"], 38, "a cópia é a casa de antes")

    def test_recusa_arquivo_que_nao_e_inventario(self):
        for ruim in ({}, {"rooms": []}, {"rooms": "x", "items": []}, {"rooms": [{"name": "sem id"}], "items": []},
                     {"rooms": [{"id": "a", "name": "A"}], "items": [{"id": "i", "room": "b"}]}, [1, 2]):
            with self.subTest(ruim=ruim):
                self.assertApiError(400, S.Store.check_inventory, ruim)


class Exportar(UnitBase):
    def test_planilha(self):
        raw = S.export_csv_bytes()
        self.assertTrue(raw.startswith("﻿".encode()), "BOM para o Excel abrir em UTF-8")
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(rows[0][:8], ["Código", "Cômodo", "Zona", "Item", "Detalhes", "Categoria", "Quantidade", "Valor (R$)"])
        self.assertEqual(len(rows), 39)
        sofa = next(r for r in rows if r[3].startswith("Sofá"))
        self.assertEqual((sofa[0], sofa[1], sofa[5], sofa[7]), ("SAL-001", "Sala de estar", "Móveis", "1800,00"))
        self.store.update_cat("moveis", {"name": "Mobília"})
        rows = list(csv.reader(io.StringIO(S.export_csv_bytes().decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(next(r for r in rows if r[3].startswith("Sofá"))[5], "Mobília", "usa os nomes das categorias da casa")

    def test_zip_com_tudo_e_so_as_fotos_usadas(self):
        helpers.write_file(os.path.join(S.PHOTOS_DIR, "sobrando.jpg"), helpers.jpeg())
        buf = io.BytesIO()
        S.write_zip(buf)
        z = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
        names = set(z.namelist())
        self.assertTrue({"inventario.json", "inventario.csv", "LEIA-ME.txt", "photos/sala-1.jpg", "thumbs/sala-1.jpg"} <= names)
        self.assertNotIn("photos/sobrando.jpg", names)
        self.assertEqual(len(json.loads(z.read("inventario.json"))["items"]), 38)
        self.assertEqual(z.getinfo("photos/sala-1.jpg").compress_type, zipfile.ZIP_STORED, "JPG não é comprimido de novo")


class Backups(UnitBase):
    def test_criar_listar_e_restaurar(self):
        b = S.create_backup()
        self.assertRegex(b["name"], r"^inventario-\d{4}-\d{2}-\d{2}-\d{4}\.zip$")
        b2 = S.create_backup()
        self.assertNotEqual(b2["name"], b["name"], "dois no mesmo minuto não se sobrescrevem")
        self.assertEqual({x["name"] for x in S.backups_list()}, {b["name"], b2["name"]})
        self.assertEqual([n for n in os.listdir(S.SHARE_DIR) if n.endswith(".tmp")], [])
        self.store.create_room({"name": "Depois do backup"})
        safety = S.restore_backup(b["name"])
        self.assertIsNotNone(safety)
        self.assertTrue(safety["name"].startswith("antes-de-restaurar-"))
        self.assertIsNone(self.store.room("depois-do-backup"), "voltou ao que era")
        with zipfile.ZipFile(os.path.join(S.SHARE_DIR, safety["name"])) as z:
            self.assertTrue(any(r["id"] == "depois-do-backup" for r in json.loads(z.read("inventario.json"))["rooms"]), "a cópia de segurança tem o de antes")

    def test_nomes_de_backup_seguros(self):
        for ruim in ("../x.zip", "x.txt", "", None, "a/b.zip"):
            with self.subTest(ruim=ruim):
                self.assertApiError(400, S.restore_backup, ruim)
        self.assertApiError(404, S.restore_backup, "nao-existe.zip")

    def test_sem_pasta_share(self):
        with mock.patch.object(S, "SHARE_DIR", "/nao/existe/inventario"):
            self.assertFalse(S.share_available())
            self.assertApiError(500, S.create_backup)
            self.assertEqual(S.backups_list(), [])


class Importar(UnitBase):
    def arquivo(self, nome, conteudo):
        p = os.path.join(S.TMP_DIR, nome)
        with open(p, "wb") as f:
            f.write(conteudo if isinstance(conteudo, bytes) else conteudo.encode())
        return p

    def test_o_que_tem_no_arquivo(self):
        dados = json.dumps(helpers.fixture_data())
        self.assertEqual(S.inspect_file(self.arquivo("a.json", dados)), {"kind": "json", "hasData": True, "items": 38, "rooms": 6, "photos": 0})
        self.assertEqual(S.inspect_file(self.arquivo("bom.json", "﻿" + dados))["items"], 38, "aceita o BOM do Windows")
        z = helpers.zip_bytes({"backup/inventario.json": dados, "backup/photos/a.jpg": helpers.jpeg(), "backup/thumbs/a.jpg": helpers.jpeg()})
        self.assertEqual(S.inspect_file(self.arquivo("b.zip", z)), {"kind": "backup", "hasData": True, "items": 38, "rooms": 6, "photos": 1})
        so_fotos = helpers.zip_bytes({"photos/x.jpg": helpers.jpeg(), "__MACOSX/photos/._x.jpg": b"lixo"})
        self.assertEqual(S.inspect_file(self.arquivo("c.zip", so_fotos))["kind"], "photos")
        self.assertApiError(400, S.inspect_file, self.arquivo("d.zip", helpers.zip_bytes({"leia.txt": "nada"})))
        self.assertApiError(400, S.inspect_file, self.arquivo("e.json", "{não é json"))
        self.assertApiError(400, S.inspect_file, self.arquivo("f.zip", helpers.zip_bytes({"inventario.json": "{quebrado"})), msg_part="corrompido")

    def test_restaurar_zip_traz_fotos_e_troca_o_inventario(self):
        data = {"rooms": [{"id": "r", "name": "Novo"}], "items": [{"id": "i", "room": "r", "name": "N", "photos": ["nova.jpg"]}]}
        z = helpers.zip_bytes({"pasta/funda/inventario.json": json.dumps(data), "pasta/funda/photos/nova.jpg": helpers.jpeg(),
                               "pasta/funda/thumbs/nova.jpg": helpers.jpeg(), "pasta/funda/photos/../../fuga.jpg": helpers.jpeg()})
        safety, fotos, trocou = S.restore_zip(self.arquivo("z.zip", z), "antes-de-importar")
        self.assertTrue(trocou)
        self.assertEqual(fotos, 1)
        self.assertTrue(S.photo_exists("nova.jpg"))
        self.assertFalse(os.path.exists(os.path.join(S.DATA_DIR, "fuga.jpg")))
        self.assertEqual(self.store.data["rooms"][0]["name"], "Novo")
        self.assertTrue(safety["name"].startswith("antes-de-importar-"))
        self.assertEqual(self.store.history_list()[0]["reason"], "import")

    def test_parte_so_com_fotos_nao_mexe_nos_itens(self):
        z = helpers.zip_bytes({"photos/parte2.jpg": helpers.jpeg(), "thumbs/parte2.jpg": helpers.jpeg()})
        rev = self.store.data["rev"]
        safety, fotos, trocou = S.restore_zip(self.arquivo("p.zip", z), "antes-de-importar")
        self.assertEqual((safety, fotos, trocou), (None, 1, False))
        self.assertEqual(self.store.data["rev"], rev)
        self.assertEqual(len(self.store.data["items"]), 38)

    def test_foto_que_ja_existe_nao_e_trocada(self):
        original = helpers.fixture_photo("sala-1.jpg")
        z = helpers.zip_bytes({"photos/sala-1.jpg": helpers.fixture_photo("cozinha-1.jpg")})
        S.restore_zip(self.arquivo("q.zip", z), "antes-de-importar")
        with open(os.path.join(S.PHOTOS_DIR, "sala-1.jpg"), "rb") as f:
            self.assertEqual(f.read(), original)

    def test_zip_ruim(self):
        self.assertApiError(400, S.restore_zip, self.arquivo("r.zip", b"PK\x03\x04 quebrado"), "x")
        self.assertApiError(400, S.restore_zip, self.arquivo("s.zip", helpers.zip_bytes({"nada.txt": "x"})), "x")

    def test_envio_em_partes(self):
        self.assertApiError(404, S.upload_paths, "../../etc")
        self.assertApiError(404, S.upload_meta, "0" * 16)
        part, meta = S.upload_paths("a" * 16)
        helpers.write_file(part, b"x")
        S.write_json_atomic(meta, {"size": 1})
        self.assertEqual(S.upload_meta("a" * 16)[2], {"size": 1})
        os.utime(part, (time.time() - 2 * 86400,) * 2)
        os.utime(meta, (time.time() - 2 * 86400,) * 2)
        S.cleanup_uploads()
        self.assertFalse(os.path.exists(part), "envios de mais de um dia são apagados")
        S.drop_upload("a" * 16)


if __name__ == "__main__":
    unittest.main()
