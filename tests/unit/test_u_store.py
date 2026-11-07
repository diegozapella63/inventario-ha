"""Armazenamento (Store): carregar (primeira vez, casa inicial, arquivos corrompidos), gravar (revisão, data, arquivo
legível e atômico), configurações, versões anteriores (a cada HISTORY_EVERY, só HISTORY_KEEP, motivos), has_data,
public, replace_all e a revisão entre as operações.

O relógio das versões é de mentira (Relogio): o tempo só anda quando o teste manda, sem sleep.
Complementa test_basicos.py (Carga) e test_dados.py (Versoes), sem repetir o que eles já conferem.
"""
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from unittest import mock

from _boot import UnitBase, helpers, server as S

CASA_DATA = "2026-10-18T18:00:00-03:00"  # updatedAt gravado em tests/fixtures/casa/inventario.json


class Relogio:
    """time.time() e datetime.now() do servidor: só andam com passa()."""

    def __init__(self, t):
        self.t = float(t)

    def time(self):
        return self.t

    def passa(self, segundos):
        self.t += segundos


def relogio(case, t=None) -> Relogio:
    r = Relogio(time.time() if t is None else t)

    class Agora(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromtimestamp(r.t, tz)

    for p in (mock.patch.object(S, "time", r), mock.patch.object(S, "datetime", Agora)):
        p.start()
        case.addCleanup(p.stop)
    return r


def copias():
    try:
        return sorted(n for n in os.listdir(S.HISTORY_DIR) if S.HISTORY_NAME.fullmatch(n))
    except FileNotFoundError:
        return []


def bytes_de(path):
    with open(path, "rb") as f:
        return f.read()


class Carga(UnitBase):
    def test_primeira_vez_nao_troca_fotos_que_ja_existem(self):
        shutil.rmtree(S.DATA_DIR)
        outra = helpers.fixture_photo("cozinha-1.jpg")
        helpers.write_file(os.path.join(S.PHOTOS_DIR, "sala-1.jpg"), outra)
        S.Store().load()
        self.assertEqual(bytes_de(os.path.join(S.PHOTOS_DIR, "sala-1.jpg")), outra, "a foto que já estava lá fica")
        self.assertEqual(bytes_de(os.path.join(S.PHOTOS_DIR, "sala-2.jpg")), helpers.fixture_photo("sala-2.jpg"), "as outras são copiadas")

    def test_primeira_vez_marca_a_data_de_agora(self):
        quando = self.store.data["updatedAt"]
        self.assertNotEqual(quando, CASA_DATA)
        self.assertLess(abs(datetime.fromisoformat(quando).timestamp() - time.time()), 120)

    def test_quem_apagou_tudo_nao_ganha_a_casa_inicial_de_volta(self):
        self.store.data["items"], self.store.data["rooms"] = [], []
        self.store.save()
        st = S.Store()
        st.load()
        self.assertEqual((st.data["rooms"], st.data["items"]), ([], []))

    def test_cria_as_pastas_de_trabalho(self):
        shutil.rmtree(S.DATA_DIR)
        S.Store().load()
        for d in (S.PHOTOS_DIR, S.THUMBS_DIR, S.HISTORY_DIR, S.TMP_DIR):
            self.assertTrue(os.path.isdir(d), d)

    def test_casa_inicial_sem_pasta_de_fotos(self):
        seed = tempfile.mkdtemp(prefix="inventaria-seed-")
        self.addCleanup(shutil.rmtree, seed, True)
        S.write_json_atomic(os.path.join(seed, "inventario.json"), {"rooms": [{"id": "sala", "name": "Sala", "code": "SAL"}], "items": []})
        shutil.rmtree(S.DATA_DIR)
        with mock.patch.object(S, "SEED_DIR", seed):
            st = S.Store()
            st.load()
        self.assertEqual([r["id"] for r in st.data["rooms"]], ["sala"])
        self.assertEqual(os.listdir(S.PHOTOS_DIR), [])

    def test_lembra_a_ultima_copia_ao_reiniciar(self):
        r = relogio(self)
        self.store.save()
        self.assertEqual(len(copias()), 1)
        st = S.Store()
        st.load()
        self.assertEqual(st.last_snapshot, os.path.getmtime(os.path.join(S.HISTORY_DIR, copias()[0])))
        r.passa(1)
        st.save()
        self.assertEqual(len(copias()), 1, "reiniciar o app não faz uma cópia nova se a última é recente")

    def test_inventario_corrompido_nao_derruba_e_nao_se_perde(self):
        self.store.save()  # guarda uma versão anterior com a casa inteira
        quebrado = '{"rooms": [{"id": "sala", "name": "Sala de es'
        helpers.write_file(S.DATA_FILE, quebrado)
        st = S.Store()
        st.load()
        self.assertEqual(len(st.data["rooms"]), 6, "volta para a última versão anterior")
        st.save()
        guardados = [os.path.join(d, n) for d, _, ns in os.walk(S.DATA_DIR) for n in ns]
        self.assertTrue(any(bytes_de(p) == quebrado.encode() for p in guardados), "o arquivo corrompido fica guardado")

    def test_inventario_vazio_em_bytes_nao_derruba(self):
        self.store.save()
        helpers.write_file(S.DATA_FILE, b"")
        st = S.Store()
        st.load()
        self.assertEqual(len(st.data["rooms"]), 6, "volta para a última versão anterior")

    def test_versao_anterior_cortada_nao_derruba(self):
        self.store.save()
        helpers.write_file(os.path.join(S.HISTORY_DIR, copias()[0]), '{"rooms": [')
        st = S.Store()
        st.load()
        self.assertEqual(len(st.data["rooms"]), 6)
        self.assertEqual(len(st.history_list()), 1, "a lista de versões continua abrindo")

    def test_configuracoes_corrompidas_nao_derrubam(self):
        helpers.write_file(S.SETTINGS_FILE, '{"zones": tr')
        st = S.Store()
        st.load()
        self.assertEqual(st.settings, {})
        self.assertEqual(len(st.data["rooms"]), 6)


class Gravar(UnitBase):
    def test_revisao_sobe_um_e_data_de_agora(self):
        rev = self.store.data["rev"]
        self.store.save()
        disco = S.read_json(S.DATA_FILE)
        self.assertEqual((self.store.data["rev"], disco["rev"]), (rev + 1, rev + 1))
        self.assertRegex(disco["updatedAt"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$", "com o fuso, sem frações de segundo")
        self.assertEqual(disco["updatedAt"], self.store.data["updatedAt"])

    def test_revisao_em_texto_vira_numero(self):
        self.store.data["rev"] = "7"
        self.store.save()
        self.assertEqual(S.read_json(S.DATA_FILE)["rev"], 8)

    def test_arquivo_legivel_com_acentos(self):
        self.store.save()
        with open(S.DATA_FILE, encoding="utf-8") as f:
            texto = f.read()
        self.assertIn('"Escritório"', texto, "acentos sem escapar: dá para abrir em qualquer editor")
        self.assertNotIn("\\u00", texto)
        self.assertGreater(texto.count("\n"), 100, "uma informação por linha")

    def test_gravacao_nao_deixa_temporarios(self):
        for _ in range(3):
            self.store.save()
        self.assertEqual([n for n in os.listdir(S.DATA_DIR) if n.startswith(".tmp-")], [])

    def test_configuracoes_nao_mexem_no_inventario(self):
        antes = bytes_de(S.DATA_FILE)
        rev = self.store.data["rev"]
        self.store.settings["zones"] = True
        self.store.save_settings()
        self.assertEqual(bytes_de(S.DATA_FILE), antes)
        self.assertEqual(self.store.data["rev"], rev, "mudar uma opção não muda a revisão do inventário")
        self.assertEqual(copias(), [], "nem guarda versão")


class Versoes(UnitBase):
    def test_copia_guarda_o_que_havia_antes_da_gravacao(self):
        relogio(self)
        rev, quando = self.store.data["rev"], self.store.data["updatedAt"]
        self.store.save()
        copia = S.read_json(os.path.join(S.HISTORY_DIR, copias()[0]))
        self.assertEqual((copia["rev"], copia["updatedAt"]), (rev, quando))
        self.assertEqual(S.read_json(S.DATA_FILE)["rev"], rev + 1)

    def test_sem_arquivo_nao_copia(self):
        os.remove(S.DATA_FILE)
        self.store.snapshot_if_due(force=True, reason="import")
        self.assertEqual(copias(), [])
        self.store.save()
        self.assertTrue(os.path.isfile(S.DATA_FILE), "a gravação recria o arquivo")
        self.assertEqual(copias(), [])

    def test_copia_exatamente_a_cada_10_minutos(self):
        r = relogio(self)
        self.store.save()
        self.assertEqual(len(copias()), 1)
        r.passa(S.HISTORY_EVERY - 1)
        self.store.save()
        self.assertEqual(len(copias()), 1, "um segundo antes dos 10 minutos, não")
        r.passa(1)
        self.store.save()
        self.assertEqual(len(copias()), 2, "aos 10 minutos, sim")

    def test_copia_forcada_sem_motivo_e_automatica(self):
        relogio(self)
        self.store.snapshot_if_due(force=True)
        self.assertEqual(len(copias()), 1)
        self.assertFalse(os.path.exists(os.path.join(S.HISTORY_DIR, S.HISTORY_REASONS)), "motivo só para importar e restaurar")
        self.assertEqual(self.store.history_list()[0]["reason"], "auto")

    def test_copia_forcada_logo_depois_com_mudanca_copia_de_novo(self):
        r = relogio(self, time.time() - 30)
        self.store.snapshot_if_due(force=True, reason="import")
        r.passa(2)
        self.store.create_room({"name": "Depois da cópia"})  # muda o arquivo, dentro dos 10 minutos (sem cópia automática)
        self.assertEqual(len(copias()), 1)
        self.store.snapshot_if_due(force=True, reason="restore")
        self.assertEqual(len(copias()), 2, "o arquivo mudou depois da última cópia")
        self.assertEqual([v["reason"] for v in self.store.history_list()], ["restore", "import"])
        self.assertEqual(self.store.history_list()[0]["rooms"], 7)

    def test_copia_forcada_depois_de_5_segundos_copia_de_novo(self):
        r = relogio(self)
        self.store.snapshot_if_due(force=True, reason="import")
        r.passa(5)
        self.store.snapshot_if_due(force=True, reason="restore")
        self.assertEqual(len(copias()), 2)

    def test_guarda_so_history_keep_e_apaga_as_mais_antigas(self):
        r = relogio(self)
        feitas = []
        with mock.patch.object(S, "HISTORY_KEEP", 2):
            for _ in range(4):
                self.store.save()
                feitas.append(copias()[-1])
                r.passa(S.HISTORY_EVERY + 1)
        self.assertEqual(copias(), feitas[-2:])

    def test_outros_arquivos_da_pasta_ficam(self):
        r = relogio(self)
        outros = ("notas.txt", "inventario-copia.json", "inventario-2026.json")
        for n in outros:
            helpers.write_file(os.path.join(S.HISTORY_DIR, n), "{}")
        for _ in range(S.HISTORY_KEEP + 2):
            self.store.save()
            r.passa(S.HISTORY_EVERY)
        self.assertEqual(len(copias()), S.HISTORY_KEEP)
        for n in outros:
            self.assertTrue(os.path.exists(os.path.join(S.HISTORY_DIR, n)), n)
        self.assertNotIn("notas.txt", [v["name"] for v in self.store.history_list()])

    def test_lista_sem_detalhes_nao_abre_as_copias(self):
        relogio(self)
        self.store.save()
        self.assertEqual(set(self.store.history_list(details=False)[0]), {"name", "size", "date"})

    def test_lista_sem_pasta_fica_vazia(self):
        shutil.rmtree(S.HISTORY_DIR)
        self.assertEqual(self.store.history_list(), [])
        self.store.prune_history()  # e não dá erro

    def test_tamanho_e_data_de_cada_copia(self):
        relogio(self)
        self.store.save()
        v = self.store.history_list()[0]
        p = os.path.join(S.HISTORY_DIR, v["name"])
        self.assertEqual(v["size"], os.path.getsize(p))
        self.assertLess(abs(datetime.fromisoformat(v["date"]).timestamp() - os.path.getmtime(p)), 1)
        self.assertEqual((v["items"], v["rooms"], v["reason"]), (38, 6, "auto"))


class Consultas(UnitBase):
    def test_tem_dados_so_com_comodos(self):
        self.store.data["items"] = []
        self.assertTrue(self.store.has_data())

    def test_sem_comodos_nem_itens_nao_tem_dados(self):
        self.store.data["items"], self.store.data["rooms"] = [], []
        self.assertFalse(self.store.has_data())

    def test_publico_tem_so_o_que_a_tela_usa(self):
        self.store.data["segredo"] = "não vai"
        self.store.settings["ai_entity"] = "ai_task.x"
        out = self.store.public()
        self.assertEqual(set(out), {"rev", "updatedAt", "rooms", "items", "cats"})
        self.assertEqual((out["rev"], len(out["rooms"]), len(out["items"]), len(out["cats"])), (self.store.data["rev"], 6, 38, 15))

    def test_publico_sem_data_de_atualizacao(self):
        self.store.data.pop("updatedAt")
        self.assertIsNone(self.store.public()["updatedAt"])


class TrocarTudo(UnitBase):
    def novo(self, **kw):
        return {"rooms": [{"id": "r", "name": "Único"}], "items": [{"id": "i1", "room": "r", "name": "Coisa"}], **kw}

    def test_revisao_do_arquivo_maior_e_respeitada(self):
        self.store.replace_all(self.novo(rev=500))
        self.assertEqual(self.store.data["rev"], 501)
        self.assertEqual(S.read_json(S.DATA_FILE)["rev"], 501)

    def test_arquivo_invalido_nao_muda_nada(self):
        antes = bytes_de(S.DATA_FILE)
        rev = self.store.data["rev"]
        self.assertApiError(400, self.store.replace_all, {"rooms": "x", "items": []})
        self.assertEqual((self.store.data["rev"], len(self.store.data["items"])), (rev, 38))
        self.assertEqual(bytes_de(S.DATA_FILE), antes)
        self.assertEqual(copias(), [], "nem guarda cópia")

    def test_configuracoes_continuam(self):
        self.store.settings.update(zones=True, ai=False)
        self.store.save_settings()
        self.store.replace_all(self.novo())
        self.assertEqual(self.store.settings, {"zones": True, "ai": False})
        self.assertEqual(S.read_json(S.SETTINGS_FILE), {"zones": True, "ai": False})

    def test_ordem_do_arquivo_e_normalizada(self):
        d = {"rooms": [{"id": "a", "name": "A", "order": 7}, {"id": "b", "name": "B", "order": 3}, {"id": "c", "name": "C"}], "items": []}
        self.store.replace_all(d)
        self.assertEqual([(r["id"], r["order"]) for r in self.store.data["rooms"]], [("c", 0), ("b", 1), ("a", 2)])

    def test_arquivo_sem_formato_ganha_formato(self):
        self.store.replace_all(self.novo())
        disco = S.read_json(S.DATA_FILE)
        self.assertEqual((disco["format"], disco["schema"]), ("inventario-casa", 1))
        self.assertEqual(disco["rooms"][0]["code"], "R")


class Revisao(UnitBase):
    def test_cada_operacao_de_comodo_sobe_um(self):
        operacoes = [
            ("criar", lambda: self.store.create_room({"name": "Garagem"})),
            ("editar", lambda: self.store.update_room("garagem", {"name": "Garagem coberta"})),
            ("foto", lambda: self.store.add_room_photo("garagem", {"file": "sala-1.jpg"})),
            ("ordem", lambda: self.store.reorder_rooms(["garagem"])),
            ("excluir", lambda: self.store.delete_room("garagem")),
        ]
        for nome, fn in operacoes:
            with self.subTest(operacao=nome):
                rev = self.store.data["rev"]
                fn()
                self.assertEqual(self.store.data["rev"], rev + 1)
                self.assertEqual(S.read_json(S.DATA_FILE)["rev"], rev + 1)

    def test_operacao_recusada_nao_muda_revisao_nem_arquivo(self):
        antes = bytes_de(S.DATA_FILE)
        rev = self.store.data["rev"]
        recusadas = [
            (400, self.store.delete_room, "sala"), (404, self.store.delete_room, "nao-existe"),
            (404, self.store.update_room, "nao-existe", {"name": "X"}), (400, self.store.add_room_photo, "sala", {"file": "sumiu.jpg"}),
            (400, self.store.create_room, {"name": ""}), (400, self.store.update_room, "sala", {"code": "--"}),
        ]
        for status, fn, *args in recusadas:
            with self.subTest(fn=fn.__name__, args=args):
                self.assertApiError(status, fn, *args)
        self.assertEqual(self.store.data["rev"], rev)
        self.assertEqual(bytes_de(S.DATA_FILE), antes)


if __name__ == "__main__":
    unittest.main()
