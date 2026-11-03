"""Backups na pasta share e versões anteriores.

backups_list (ordem, só .zip do app, tamanho e data), create_backup (nome, conteúdo, share indisponível),
share_available, safety_backup (a cópia antes de importar ou restaurar), restore_backup (nomes ruins, inexistente,
backup corrompido) e restaurar uma versão anterior pela função da rota (r_history_restore). A lista das versões
(history_list) e as cópias automáticas estão em test_u_store.py.
"""
import io
import json
import os
import re
import shutil
import tempfile
import time
import unittest
import zipfile
from datetime import datetime
from unittest import mock

from _boot import UnitBase, helpers, server as S

DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}")


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


def backup_da_casa(**extra) -> bytes:
    """Um backup como o app faz, da casa de teste (com mais arquivos, se pedir)."""
    files = {"inventario.json": json.dumps(helpers.fixture_data()), "photos/sala-1.jpg": helpers.fixture_photo("sala-1.jpg")}
    files.update(extra)
    return helpers.zip_bytes(files)


def na_share(nome, conteudo=b"", quando=None) -> str:
    p = helpers.write_file(os.path.join(S.SHARE_DIR, nome), conteudo)
    if quando is not None:
        os.utime(p, (quando, quando))
    return p


def zips_na_share():
    return sorted(n for n in os.listdir(S.SHARE_DIR) if n.endswith(".zip"))


def data_de(path) -> str:
    return datetime.fromtimestamp(os.path.getmtime(path)).astimezone().isoformat(timespec="seconds")


class ListaDeBackups(UnitBase):
    def test_mais_novo_primeiro(self):
        t = time.time()
        na_share("a.zip", backup_da_casa(), t - 3000)
        na_share("b.zip", backup_da_casa(), t - 1000)
        na_share("c.zip", backup_da_casa(), t - 2000)
        self.assertEqual([b["name"] for b in S.backups_list()], ["b.zip", "c.zip", "a.zip"])

    def test_so_entram_zip_com_nome_aceito(self):
        na_share("inventario-2026-01-02-0304.zip", backup_da_casa())
        for outro in ("leia.txt", ".oculto.zip", ".inventario-2026-01-02-0305.zip.tmp", "integracao.json", "parte.zip.part"):
            na_share(outro, b"x")
        self.assertEqual([b["name"] for b in S.backups_list()], ["inventario-2026-01-02-0304.zip"],
                         "nem o .tmp de um backup sendo gravado, nem o integracao.json dos outros apps")

    def test_tamanho_e_data_do_arquivo(self):
        p = na_share("x.zip", backup_da_casa(), time.time() - 600)
        b = S.backups_list()[0]
        self.assertEqual(b["size"], os.path.getsize(p))
        self.assertRegex(b["date"], DATA_ISO, "data com o fuso, como 2026-11-02T10:00:00-03:00")
        self.assertEqual(b["date"], data_de(p))

    def test_sem_a_pasta_inventario_a_lista_fica_vazia(self):
        shutil.rmtree(S.SHARE_DIR)
        self.assertTrue(S.share_available(), "a share existe; só falta a pasta do app")
        self.assertEqual(S.backups_list(), [])

    def test_copias_de_seguranca_aparecem_na_lista(self):
        safety = S.safety_backup("antes-de-importar")
        self.assertIn(safety["name"], [b["name"] for b in S.backups_list()], "dá para voltar ao que era antes de importar")

    def test_backup_com_espaco_ou_parenteses_no_nome_aparece_na_lista(self):
        nomes = ["inventario-2026-11-02-1200 (1).zip", "inventario - Cópia.zip"]
        for n in nomes:
            na_share(n, backup_da_casa())
        self.assertEqual(sorted(b["name"] for b in S.backups_list()), sorted(nomes))
        self.assertIsNotNone(S.restore_backup(nomes[0]))


class CriarBackup(UnitBase):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(S, "stamp", return_value="2026-03-04-0506")
        p.start()
        self.addCleanup(p.stop)

    def test_nome_leva_a_data_e_a_hora(self):
        self.assertEqual(S.create_backup()["name"], "inventario-2026-03-04-0506.zip")

    def test_no_mesmo_minuto_ganha_um_numero(self):
        nomes = [S.create_backup()["name"] for _ in range(3)]
        self.assertEqual(nomes, ["inventario-2026-03-04-0506.zip", "inventario-2026-03-04-0506-2.zip", "inventario-2026-03-04-0506-3.zip"])

    def test_prefixo_da_copia_de_seguranca(self):
        self.assertEqual(S.create_backup("antes-de-importar")["name"], "antes-de-importar-2026-03-04-0506.zip")

    def test_conteudo_e_o_inventario_atual(self):
        self.store.create_room({"name": "Garagem"})
        b = S.create_backup()
        with zipfile.ZipFile(os.path.join(S.SHARE_DIR, b["name"])) as z:
            d = json.loads(z.read("inventario.json"))
            names = set(z.namelist())
        self.assertIn("garagem", [r["id"] for r in d["rooms"]])
        self.assertEqual(len(d["items"]), 38)
        self.assertTrue({"inventario.csv", "LEIA-ME.txt", "photos/sala-1.jpg", "thumbs/sala-1.jpg"} <= names)

    def test_devolve_o_mesmo_que_a_lista_mostra(self):
        b = S.create_backup()
        self.assertEqual(b, next(x for x in S.backups_list() if x["name"] == b["name"]))
        self.assertEqual(b["size"], os.path.getsize(os.path.join(S.SHARE_DIR, b["name"])))

    def test_cria_a_pasta_inventario_se_faltar(self):
        shutil.rmtree(S.SHARE_DIR)
        b = S.create_backup()
        self.assertTrue(os.path.isfile(os.path.join(S.SHARE_DIR, b["name"])))

    def test_backup_que_falha_no_meio_nao_deixa_temporario(self):
        with mock.patch.object(S, "write_zip", side_effect=OSError("disco cheio")):
            with self.assertRaises(OSError):
                S.create_backup()
        self.assertEqual(os.listdir(S.SHARE_DIR), [])


class PastaShare(UnitBase):
    def base(self):
        d = tempfile.mkdtemp(prefix="inventaria-share-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    def test_basta_existir_a_pasta_share(self):
        d = self.base()
        os.makedirs(os.path.join(d, "share"))
        with mock.patch.object(S, "SHARE_DIR", os.path.join(d, "share", "inventario")):
            self.assertTrue(S.share_available(), "share/inventario é criada no primeiro backup")
        with mock.patch.object(S, "SHARE_DIR", os.path.join(d, "sem-share", "inventario")):
            self.assertFalse(S.share_available())

    def test_barra_no_fim_do_caminho_nao_atrapalha(self):
        d = self.base()
        os.makedirs(os.path.join(d, "share"))
        with mock.patch.object(S, "SHARE_DIR", os.path.join(d, "share", "inventario") + "/"):
            self.assertTrue(S.share_available())
        with mock.patch.object(S, "SHARE_DIR", os.path.join(d, "sem-share", "inventario") + "/"):
            self.assertFalse(S.share_available())


class CopiaDeSeguranca(UnitBase):
    def test_guarda_um_zip_na_share_com_o_prefixo(self):
        safety = S.safety_backup("antes-de-importar")
        self.assertTrue(safety["name"].startswith("antes-de-importar-"))
        with zipfile.ZipFile(os.path.join(S.SHARE_DIR, safety["name"])) as z:
            self.assertEqual(len(json.loads(z.read("inventario.json"))["items"]), 38)

    def test_antes_de_importar_guarda_versao_com_motivo_import(self):
        S.safety_backup("antes-de-importar")
        v = self.store.history_list()[0]
        self.assertEqual((v["reason"], v["items"], v["rooms"]), ("import", 38, 6))

    def test_antes_de_restaurar_guarda_versao_com_motivo_restore(self):
        S.safety_backup("antes-de-restaurar")
        self.assertEqual(self.store.history_list()[0]["reason"], "restore")

    def test_casa_vazia_nao_gera_zip(self):
        self.store.data["rooms"], self.store.data["items"] = [], []
        self.store.save()
        self.assertIsNone(S.safety_backup("antes-de-importar"))
        self.assertEqual(zips_na_share(), [], "não há o que guardar")

    def test_sem_share_nao_da_erro_e_guarda_a_versao(self):
        with mock.patch.object(S, "SHARE_DIR", "/nao/existe/inventario"):
            self.assertIsNone(S.safety_backup("antes-de-importar"))
        self.assertEqual(self.store.history_list()[0]["reason"], "import", "a versão anterior continua garantindo o desfazer")


class RestaurarBackup(UnitBase):
    def test_nomes_ocultos_absolutos_ou_compridos_sao_recusados(self):
        for ruim in (".oculto.zip", "/tmp/x.zip", "..\\x.zip", "a\\b.zip", "a" * 152 + ".zip", "x.zip\n", "x.zip/"):
            with self.subTest(ruim=ruim):
                self.assertApiError(400, S.restore_backup, ruim, msg_part="Nome de backup inválido")

    def test_pasta_com_nome_de_zip_nao_e_backup(self):
        os.makedirs(os.path.join(S.SHARE_DIR, "pasta.zip"))
        self.assertApiError(404, S.restore_backup, "pasta.zip", msg_part="share/inventario")

    def test_arquivo_que_nao_e_zip_nao_muda_nada(self):
        na_share("falso.zip", "isto não é um zip")
        rev = self.store.data["rev"]
        self.assertApiError(400, S.restore_backup, "falso.zip", msg_part="não é um .zip válido")
        self.assertEqual(self.store.data["rev"], rev)
        self.assertEqual(zips_na_share(), ["falso.zip"], "nem cópia de segurança")

    def test_zip_cortado_ao_meio_e_recusado(self):
        inteiro = backup_da_casa()
        na_share("cortado.zip", inteiro[: len(inteiro) // 2])
        rev = self.store.data["rev"]
        self.assertApiError(400, S.restore_backup, "cortado.zip")
        self.assertEqual(self.store.data["rev"], rev)

    def test_inventario_corrompido_nao_traz_fotos_nem_faz_copia(self):
        na_share("ruim.zip", helpers.zip_bytes({"inventario.json": '{"rooms": [', "photos/nova.jpg": helpers.jpeg()}))
        self.assertApiError(400, S.restore_backup, "ruim.zip", msg_part="corrompido")
        self.assertFalse(S.photo_exists("nova.jpg"))
        self.assertEqual(zips_na_share(), ["ruim.zip"])
        self.assertEqual(self.store.history_list(), [])
        self.assertEqual(len(self.store.data["items"]), 38)

    def test_backup_so_de_fotos_acrescenta_sem_trocar_os_itens(self):
        na_share("parte-2.zip", helpers.zip_bytes({"photos/parte2.jpg": helpers.jpeg(), "thumbs/parte2.jpg": helpers.jpeg()}))
        rev = self.store.data["rev"]
        self.assertIsNone(S.restore_backup("parte-2.zip"), "sem troca, sem cópia de segurança")
        self.assertTrue(S.photo_exists("parte2.jpg"))
        self.assertEqual(self.store.data["rev"], rev)

    def test_categorias_voltam_com_o_backup(self):
        self.store.create_cat({"name": "Ferramentas"})
        b = S.create_backup()
        self.store.delete_cat("ferramentas")
        S.restore_backup(b["name"])
        self.assertIn("Ferramentas", [c["name"] for c in self.store.cats()])

    def test_guarda_a_casa_de_antes_como_versao_restore(self):
        b = S.create_backup()
        self.store.create_room({"name": "Garagem"})
        S.restore_backup(b["name"])
        v = self.store.history_list()[0]
        self.assertEqual((v["reason"], v["rooms"]), ("restore", 7))
        self.assertEqual(len(self.store.data["rooms"]), 6)

    def test_foto_corrompida_no_backup_nao_vira_erro_interno(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            z.writestr("inventario.json", json.dumps(helpers.fixture_data()))
            z.writestr("photos/estragada.jpg", b"\xff\xd8" + b"A" * 200)
        raw = bytearray(buf.getvalue())
        raw[raw.find(b"A" * 200) + 10] = ord("B")
        na_share("estragado.zip", bytes(raw))
        try:
            S.restore_backup("estragado.zip")
        except S.ApiError as e:
            self.assertEqual(e.status, 400, e.msg)
        self.assertEqual([n for n in os.listdir(S.PHOTOS_DIR) if n.endswith(".tmp")], [])


class Versoes(UnitBase):
    def versao(self, nome, data) -> str:
        p = os.path.join(S.HISTORY_DIR, nome)
        if isinstance(data, dict):
            S.write_json_atomic(p, data)
        else:
            helpers.write_file(p, data)
        return p

    def so_duas_salas(self) -> dict:
        d = helpers.fixture_data()
        d["rooms"] = [r for r in d["rooms"] if r["id"] in ("sala", "cozinha")]
        d["items"] = [i for i in d["items"] if i["room"] in ("sala", "cozinha")]
        return d

    def restaurar(self, nome):
        h = Resposta({"name": nome})
        S.r_history_restore(h, query={})
        return h

    def test_restaurar_versao_com_nome_invalido(self):
        for ruim in ("../inventario.json", "motivos.json", "", None, "inventario-2026-01-01.json", "inventario-20260101-120000.json/"):
            with self.subTest(ruim=ruim):
                self.assertApiError(400, self.restaurar, ruim, msg_part="Versão inválida")

    def test_restaurar_versao_que_nao_existe(self):
        self.assertApiError(404, self.restaurar, "inventario-20200101-000000.json", msg_part="não encontrada")

    def test_restaurar_versao_volta_o_inventario(self):
        self.versao("inventario-20260101-120000.json", self.so_duas_salas())
        rev = self.store.data["rev"]
        h = self.restaurar("inventario-20260101-120000.json")
        self.assertEqual(h.status, 200)
        self.assertEqual([r["id"] for r in self.store.data["rooms"]], ["sala", "cozinha"])
        self.assertEqual(len(self.store.data["items"]), 19)
        resp = h.json()
        self.assertEqual(resp, {"ok": True, "rev": self.store.data["rev"]})
        self.assertGreater(resp["rev"], rev, "a revisão sobe, e os outros aparelhos recarregam")

    def test_restaurar_versao_guarda_a_atual_antes(self):
        self.versao("inventario-20260101-120000.json", self.so_duas_salas())
        self.restaurar("inventario-20260101-120000.json")
        v = self.store.history_list()[0]
        self.assertEqual((v["reason"], v["rooms"], v["items"]), ("restore", 6, 38), "dá para desfazer a restauração")

    def test_restauracao_fica_gravada_no_disco(self):
        self.versao("inventario-20260101-120000.json", self.so_duas_salas())
        self.restaurar("inventario-20260101-120000.json")
        st = S.Store()
        st.load()
        self.assertEqual([r["id"] for r in st.data["rooms"]], ["sala", "cozinha"], "continua assim depois de reiniciar o app")

    def test_restaurar_versao_que_nao_e_inventario(self):
        self.versao("inventario-20260101-120000.json", {"rooms": "nada"})
        self.assertApiError(400, self.restaurar, "inventario-20260101-120000.json", msg_part="não parece um inventário")
        self.assertEqual(len(self.store.data["items"]), 38)

    def test_restaurar_versao_corrompida_responde_erro_claro(self):
        self.versao("inventario-20260101-120000.json", '{"rooms": [')
        try:
            self.restaurar("inventario-20260101-120000.json")
        except S.ApiError as e:
            self.assertIn(e.status, (400, 404), e.msg)
        else:
            self.fail("uma versão corrompida não pode ser restaurada")
        self.assertEqual(len(self.store.data["items"]), 38)


if __name__ == "__main__":
    unittest.main()
