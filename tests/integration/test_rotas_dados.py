"""Rotas de dados pelo HTTP, com o servidor de verdade: /api/data, /api/rev, /api/health, /api/settings, exportar
(/api/export.csv, .json e .zip, com os cabeçalhos), backups na pasta share, importar, envio em partes (/api/upload*),
versões anteriores (/api/history*), enviar fotos (/api/photos) e servir /photos/<arquivo> e /thumbs/<arquivo>."""
import csv
import io
import json
import os
import time
import re
import unittest
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from _boot import AppServer, ServerCase, b64, helpers

ROOT = os.path.dirname(helpers.APP)
OCTET = {"Content-Type": "application/octet-stream"}
JSON = {"Content-Type": "application/json"}


def hoje_no_servidor(app) -> set[str]:
    """O dia de hoje no fuso do servidor (e o de ontem, para um teste que cruza a meia-noite)."""
    agora = datetime.now(ZoneInfo(app.env["TZ"]))
    return {agora.strftime("%Y-%m-%d"), (agora - timedelta(minutes=1)).strftime("%Y-%m-%d")}


def enviar(app, data: bytes, name="arquivo.zip", chunk=None) -> str:
    st, _, out = app.post("api/upload", {"name": name, "size": len(data)})
    assert st == 201, out
    uid, size, off = out["id"], chunk or out["chunk"], 0
    while off < len(data):
        st, _, r = app.request("PUT", f"api/upload/{uid}?offset={off}", raw=data[off:off + size], headers=OCTET)
        assert st == 200, r
        off = r["received"]
    return uid


def casa(**mudancas) -> dict:
    data = helpers.fixture_data()
    data.update(mudancas)
    return data


class DadosCase(ServerCase):
    def rev(self, app=None):
        return (app or self.app).ok("GET", "api/rev")["rev"]

    def erro(self, method, path, body, status, msg, app=None):
        st, _, out = (app or self.app).request(method, path, body)
        self.assertEqual((st, out.get("error") if isinstance(out, dict) else out), (status, msg), body)
        return out


class DadosDaCasa(DadosCase):
    def test_sem_usuario_do_home_assistant_user_nulo(self):
        self.assertIsNone(self.app.data()["user"])

    def test_revisao_e_data_iguais_as_do_arquivo(self):
        d, s = self.app.data(), self.app.stored()
        self.assertEqual((d["rev"], d["updatedAt"]), (s["rev"], s["updatedAt"]))

    def test_rev_responde_so_a_revisao_e_o_uso_do_correria(self):
        self.assertEqual(self.app.ok("GET", "api/rev"), {"rev": self.app.stored()["rev"], "correria_uso": None})

    def test_versao_igual_na_saude_nos_dados_na_pagina_e_no_config_yaml(self):
        with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
            config = re.search(r'^version:\s*"?([\d.]+)"?', f.read(), re.M).group(1)
        saude = self.app.ok("GET", "api/health")
        self.assertEqual(saude, {"ok": True, "version": config})
        self.assertEqual(self.app.data()["version"], config)
        self.assertIn(f'data-v="{config}"'.encode(), self.app.get("/")[2])

    def test_so_ler_nao_sobe_a_revisao(self):
        r0 = self.rev()
        for path in ("api/data", "api/health", "api/settings", "api/export.csv", "api/export.json", "api/export.zip", "api/backups",
                     "api/history", "api/ai/usage", "api/ai/status", "api/voice/status", "photos/sala-1.jpg", "/"):
            with self.subTest(path=path):
                self.assertEqual(self.app.get(path)[0], 200)
        self.assertEqual(self.rev(), r0)


class Reiniciar(unittest.TestCase):
    """O app reinicia (atualização, Home Assistant reiniciando): tudo continua de onde parou."""

    def reiniciar(self, app: AppServer) -> AppServer:
        app.stop(clean=False)
        novo = AppServer(root=app.root)
        self.addCleanup(novo.stop)
        return novo

    def test_itens_opcoes_e_revisao_ficam(self):
        app = AppServer()
        self.addCleanup(app.stop)
        it = app.ok("POST", "api/items", {"room": "quarto", "name": "Abajur de cabeceira", "value": "89,90"})["item"]
        app.ok("PUT", "api/settings", {"zones": True, "ai": False})
        rev = app.ok("GET", "api/rev")["rev"]
        app = self.reiniciar(app)
        self.assertEqual(next(i for i in app.data()["items"] if i["id"] == it["id"]), it)
        self.assertEqual(app.ok("GET", "api/rev")["rev"], rev)
        self.assertEqual((app.data()["settings"]["zones"], app.data()["settings"]["ai"]), (True, False))

    def test_chave_dos_outros_apps_continua_a_mesma(self):
        app = AppServer()
        self.addCleanup(app.stop)
        with open(app.path("share", "integracao.json"), encoding="utf-8") as f:
            chave = json.load(f)["chave"]
        app = self.reiniciar(app)
        self.assertEqual(app.get("api/integracao/comodos", headers={"Authorization": f"Bearer {chave}"})[0], 200)

    def test_envio_em_partes_continua_depois_de_reiniciar(self):
        app = AppServer()
        self.addCleanup(app.stop)
        z = helpers.zip_bytes({"inventario.json": json.dumps(casa())})
        uid = app.ok("POST", "api/upload", {"name": "backup.zip", "size": len(z)})["id"]
        app.ok("PUT", f"api/upload/{uid}?offset=0", raw=z[:100], headers=OCTET)
        app = self.reiniciar(app)
        self.assertEqual(app.ok("PUT", f"api/upload/{uid}?offset=100", raw=z[100:], headers=OCTET)["received"], len(z))
        self.assertEqual(app.ok("GET", f"api/upload/{uid}")["kind"], "backup")


class SemPastaShare(unittest.TestCase):
    """O app sem a pasta share (mapeamento tirado): backup avisa, o resto funciona."""

    @classmethod
    def setUpClass(cls):
        # uma pasta que não existe e que nem o app consegue criar (dentro de /proc)
        cls.app = AppServer(env={"INV_SHARE": "/proc/inventaria-sem-share/inventario"})

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def test_backup_explica_e_a_lista_vem_vazia(self):
        self.assertFalse(self.app.data()["features"]["share"])
        self.assertEqual(self.app.ok("GET", "api/backups"), {"backups": [], "dir": "share/inventario", "available": False})
        st, _, out = self.app.post("api/backups")
        self.assertEqual((st, out["error"]), (500, "A pasta share não está disponível para o app."))

    def test_importar_funciona_sem_copia_de_seguranca(self):
        z = helpers.zip_bytes({"inventario.json": json.dumps(casa())})
        out = self.app.ok("POST", f"api/upload/{enviar(self.app, z)}/restore")
        self.assertEqual((out["safety"], out["items"]), (None, 38))
        self.assertEqual(self.app.ok("POST", "api/import", {"data": casa()}), {"ok": True, "rev": self.app.ok("GET", "api/rev")["rev"]})


class Configuracoes(DadosCase):
    def setUp(self):
        self.addCleanup(self.app.put, "api/settings", {"zones": False, "ai": True, "ai_entity": "", "ai_search": "", "voice_stt": "", "ha_sensors": False})

    def test_chaves_desconhecidas_ignoradas(self):
        out = self.app.ok("PUT", "api/settings", {"foo": 1, "rev": 99, "zones": True})
        self.assertNotIn("foo", out)
        self.assertNotIn("rev", self.app.ok("GET", "api/settings"))

    def test_nulo_vira_vazio(self):
        self.app.ok("PUT", "api/settings", {"ai_entity": "ai_task.google"})
        self.assertEqual(self.app.ok("PUT", "api/settings", {"ai_entity": None})["ai_entity"], "")

    def test_corpo_vazio_nao_muda_nada(self):
        self.app.ok("PUT", "api/settings", {"zones": True})
        antes = self.app.ok("GET", "api/settings")
        self.assertEqual(self.app.ok("PUT", "api/settings", {}), antes)
        self.assertEqual(self.app.ok("PUT", "api/settings", None), antes)

    def test_sensores_sem_home_assistant_nao_quebra(self):
        self.assertTrue(self.app.ok("PUT", "api/settings", {"ha_sensors": True})["ha_sensors"])
        self.assertTrue(self.app.data()["settings"]["ha_sensors"])
        self.assertEqual(self.app.get("api/health")[0], 200)

    def test_opcoes_nao_sobem_a_revisao_do_inventario(self):
        r0 = self.rev()
        self.app.ok("PUT", "api/settings", {"zones": True, "ai": False})
        self.assertEqual(self.rev(), r0)

    def test_resposta_igual_ao_que_ficou_gravado(self):
        out = self.app.ok("PUT", "api/settings", {"ai_search": "conversation.google_generative_ai", "voice_stt": "stt.faster_whisper"})
        self.assertEqual(out, self.app.ok("GET", "api/settings"))
        with open(self.app.path("data", "settings.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), out)

    def test_texto_no_lugar_de_verdadeiro_ou_falso_mensagem(self):
        self.erro("PUT", "api/settings", {"zones": "true"}, 400, "Use verdadeiro ou falso nesta opção.")
        self.erro("PUT", "api/settings", {"ai_entity": "AI_TASK.X"}, 400, "Entidade de IA inválida.")
        self.erro("PUT", "api/settings", {"voice_stt": "stt.Fala"}, 400, "Fala para texto inválida.")


class CorDoApp(DadosCase):
    """Aparência > Cor do app (1.42.0): vale para a casa toda, gravada no servidor. A paleta da família (12 cores); de
    início, nenhuma (a tela adota a do aparelho na primeira vez); uma cor de antes da paleta vira a mais próxima."""

    def setUp(self):
        self.app = AppServer()
        self.addCleanup(lambda: self.app.stop())

    def test_de_inicio_nenhuma(self):
        st = self.app.data()["settings"]
        self.assertEqual((st["accent"], st["accent_daily"]), (None, None))

    def test_grava_para_a_casa(self):
        out = self.app.ok("PUT", "api/settings", {"accent": "indigo", "accent_daily": False})
        self.assertEqual((out["accent"], out["accent_daily"]), ("indigo", False))
        st = self.app.data()["settings"]
        self.assertEqual((st["accent"], st["accent_daily"]), ("indigo", False), "quem abrir em outro aparelho vê a mesma")
        self.assertTrue(self.app.ok("PUT", "api/settings", {"accent_daily": True})["accent_daily"])

    def test_so_as_12_cores(self):
        for a in ("vermelho", "coral", "laranja", "ouro", "verde", "menta", "turquesa", "azul", "indigo", "lilas", "rosa", "grafite"):
            self.assertEqual(self.app.ok("PUT", "api/settings", {"accent": a})["accent"], a)
        for a in ("amarelo", "kraft", "cinza", "", None, 3, "#ff0000"):
            with self.subTest(a=a):
                self.erro("PUT", "api/settings", {"accent": a}, 400, "Escolha uma das cores do app.")
        self.erro("PUT", "api/settings", {"accent_daily": "sim"}, 400, "Use verdadeiro ou falso nesta opção.")

    def test_cor_antiga_vira_a_mais_proxima(self):
        for velha, nova in (("amarelo", "ouro"), ("kraft", "coral"), ("cinza", "grafite"), ("roxo", None)):
            with self.subTest(velha=velha):
                path = self.app.path("data", "settings.json")
                st = {}
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        st = json.load(f)
                st["accent"] = velha
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(st, f)
                self.app.stop(clean=False)
                self.app = AppServer(root=self.app.root)
                self.assertEqual(self.app.data()["settings"]["accent"], nova)


class ComecarDoZero(unittest.TestCase):
    """Configurações > Dados > Começar do zero (1.42.0): apaga os cômodos, os bens e os itens só com a confirmação, depois de
    guardar uma versão ("antes de apagar tudo"); as categorias, as opções e as fotos ficam, e a versão traz tudo de volta."""

    def setUp(self):
        self.app = AppServer()
        self.addCleanup(self.app.stop)

    def test_sem_confirmar_nada_muda(self):
        for body in ({}, {"confirm": "sim"}, {"confirm": 1}, None):
            with self.subTest(body=body):
                st, _, out = self.app.request("POST", "api/erase", body)
                self.assertEqual((st, out.get("error")), (400, "Confirme para apagar tudo."))
        d = self.app.data()
        self.assertEqual((len(d["rooms"]), len(d["items"])), (6, 38))

    def test_apaga_tudo_e_a_versao_traz_de_volta(self):
        self.app.ok("PUT", "api/settings", {"zones": True})
        cat = self.app.ok("POST", "api/cats", {"name": "Ferramentas"})["cat"]
        fotos = sorted(os.listdir(self.app.path("data", "photos")))
        r0 = self.app.ok("GET", "api/rev")["rev"]
        out = self.app.ok("POST", "api/erase", {"confirm": True})
        self.assertGreater(out["rev"], r0, "a revisão sobe: os outros aparelhos recarregam")
        d = self.app.data()
        self.assertEqual((d["rooms"], d["items"]), ([], []), "nem cômodos, nem itens")
        self.assertIn(cat["id"], [c["id"] for c in d["cats"]], "as categorias continuam")
        self.assertTrue(d["settings"]["zones"], "as opções continuam")
        self.assertEqual(sorted(os.listdir(self.app.path("data", "photos"))), fotos, "as fotos ficam no disco")
        hist = self.app.ok("GET", "api/history")["history"]
        antes = next((v for v in hist if v["reason"] == "erase"), None)
        self.assertIsNotNone(antes, f"uma versão antes de apagar tudo ({hist})")
        self.assertEqual((antes["rooms"], antes["items"]), (6, 38))
        self.app.ok("POST", "api/history/restore", {"name": antes["name"]})
        d = self.app.data()
        self.assertEqual((len(d["rooms"]), len(d["items"])), (6, 38), "restaurar a versão traz tudo de volta")


class Exportar(DadosCase):
    def planilha(self, app=None):
        raw = (app or self.app).get("api/export.csv")[2]
        return list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))

    def test_planilha_tipo_nome_com_o_dia_e_sem_cache(self):
        st, h, _ = self.app.get("api/export.csv")
        self.assertEqual((st, h["Content-Type"], h["Cache-Control"]), (200, "text/csv; charset=utf-8", "no-store"))
        dia = re.fullmatch(r'attachment; filename="inventario-(\d{4}-\d{2}-\d{2})\.csv"', h["Content-Disposition"]).group(1)
        self.assertIn(dia, hoje_no_servidor(self.app))

    def test_planilha_com_bom_e_as_11_colunas(self):
        raw = self.app.get("api/export.csv")[2]
        self.assertTrue(raw.startswith("﻿".encode()), "o Excel abre em UTF-8")
        self.assertEqual(self.planilha()[0], ["Código", "Cômodo", "Zona", "Item", "Detalhes", "Categoria", "Quantidade", "Valor (R$)", "Fotos",
                                              "Criado em", "Atualizado em"])
        self.assertIn(b"\r\n", raw)

    def test_planilha_linha_do_sofa(self):
        linha = self.planilha()[1]
        self.assertEqual(linha[:9], ["SAL-001", "Sala de estar", "Sofá", "Sofá de 3 lugares cinza-azulado",
                                     "Tecido liso, almofadas de encosto soltas e pés de madeira.", "Móveis", "1", "1800,00", "sala-1.jpg"])

    def test_planilha_com_ponto_e_virgula_aspas_e_quebra_de_linha(self):
        nome, det = 'Mesa; "redonda"', "linha 1\nlinha 2; com ponto e vírgula"
        it = self.app.ok("POST", "api/items", {"room": "varanda", "name": nome, "details": det, "value": "1.234,5"})["item"]
        self.addCleanup(self.app.delete, f"api/items/{it['id']}")
        linha = next(x for x in self.planilha() if x[0] == f"VAR-{it['seq']:03d}")
        self.assertEqual((linha[3], linha[4], linha[7]), (nome, det, "1234,50"))

    def test_planilha_com_categoria_que_sumiu_mostra_outros(self):
        app = self.fresh()
        data = casa()
        data["items"][0]["cat"] = "categoria-que-sumiu"
        app.ok("POST", "api/import", {"data": data})
        self.assertEqual(self.planilha(app)[1][5], "Outros")

    def test_json_tipo_nome_e_igual_ao_arquivo(self):
        st, h, data = self.app.get("api/export.json")
        self.assertEqual((h["Content-Type"], h["Cache-Control"]), ("application/json; charset=utf-8", "no-store"))
        self.assertRegex(h["Content-Disposition"], r'^attachment; filename="inventario-\d{4}-\d{2}-\d{2}\.json"$')
        self.assertEqual(data, self.app.stored())

    def test_zip_tipo_tamanho_nome_e_sem_cache(self):
        st, h, z = self.app.get("api/export.zip")
        self.assertEqual((st, h["Content-Type"], h["Cache-Control"], int(h["Content-Length"])), (200, "application/zip", "no-store", len(z)))
        self.assertRegex(h["Content-Disposition"], r'^attachment; filename="inventario-\d{4}-\d{2}-\d{2}\.zip"$')

    def test_zip_tem_leia_me_planilha_e_o_inventario_de_agora(self):
        with zipfile.ZipFile(io.BytesIO(self.app.get("api/export.zip")[2])) as z:
            self.assertTrue({"LEIA-ME.txt", "inventario.csv", "inventario.json"} <= set(z.namelist()))
            self.assertEqual(json.loads(z.read("inventario.json")), self.app.stored())
            self.assertEqual(z.read("inventario.csv"), self.app.get("api/export.csv")[2])
            self.assertIn("share/inventario", z.read("LEIA-ME.txt").decode())

    def test_zip_leva_fotos_dos_itens_e_dos_comodos_com_miniaturas_e_deixa_as_soltas(self):
        app = self.fresh()
        solta = self.upload_photo(app)
        do_comodo = self.upload_photo(app)
        app.ok("POST", "api/rooms/varanda/photos", {"file": do_comodo})
        with zipfile.ZipFile(io.BytesIO(app.get("api/export.zip")[2])) as z:
            nomes = set(z.namelist())
        self.assertIn(f"photos/{do_comodo}", nomes)
        self.assertIn(f"thumbs/{do_comodo}", nomes)
        self.assertNotIn(f"photos/{solta}", nomes, "foto que nenhum item ou cômodo usa fica de fora")
        self.assertEqual({n for n in nomes if n.startswith("photos/")}, {n.replace("thumbs/", "photos/") for n in nomes if n.startswith("thumbs/")})

    def test_zip_nao_deixa_arquivo_temporario(self):
        self.app.get("api/export.zip")
        sobra = lambda: [n for n in os.listdir(self.app.path("data", "tmp")) if n.endswith(".zip")]  # noqa: E731
        fim = time.time() + 3  # o servidor apaga logo depois de mandar o último byte: espera um instante
        while sobra() and time.time() < fim:
            time.sleep(0.05)
        self.assertEqual(sobra(), [])


class Backups(DadosCase):
    def no_share(self, name, data: bytes):
        p = helpers.write_file(self.app.path("share", name), data)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        return name

    def test_criar_responde_201_com_o_backup_e_a_lista(self):
        st, _, out = self.app.post("api/backups")
        self.assertEqual((st, set(out)), (201, {"backup", "backups"}))
        b = out["backup"]
        self.assertRegex(b["name"], r"^inventario-\d{4}-\d{2}-\d{2}-\d{4}(-\d+)?\.zip$")
        self.assertEqual(b["size"], os.path.getsize(self.app.path("share", b["name"])))
        self.assertIn(b, out["backups"])

    def test_dois_no_mesmo_minuto_nao_se_sobrescrevem(self):
        a = self.app.ok("POST", "api/backups")["backup"]["name"]
        b = self.app.ok("POST", "api/backups")["backup"]["name"]
        self.assertNotEqual(a, b)
        self.assertTrue(os.path.isfile(self.app.path("share", a)) and os.path.isfile(self.app.path("share", b)))

    def test_backup_e_um_zip_com_o_inventario_de_agora(self):
        nome = self.app.ok("POST", "api/backups")["backup"]["name"]
        with zipfile.ZipFile(self.app.path("share", nome)) as z:
            self.assertEqual(json.loads(z.read("inventario.json")), self.app.stored())
        self.assertEqual([n for n in os.listdir(self.app.path("share")) if n.endswith(".tmp")], [], "sem arquivo pela metade")

    def test_lista_ignora_o_que_nao_e_backup(self):
        for nome in ("notas.txt", ".escondido.zip", "foto.jpg", "sem extensao"):
            self.no_share(nome, b"x")
        nomes = [b["name"] for b in self.app.ok("GET", "api/backups")["backups"]]
        self.assertTrue(all(n.endswith(".zip") and not n.startswith(".") for n in nomes), nomes)
        self.assertNotIn("integracao.json", nomes)

    def test_restaurar_responde_ok_copia_de_seguranca_e_revisao_maior(self):
        nome = self.no_share("casa-de-teste.zip", helpers.zip_bytes({"inventario.json": json.dumps(casa())}))
        r0 = self.rev()
        out = self.app.ok("POST", "api/backups/restore", {"name": nome})
        self.assertEqual((out["ok"], out["rev"] > r0), (True, True))
        self.assertRegex(out["safety"]["name"], r"^antes-de-restaurar-.*\.zip$")
        self.assertTrue(os.path.isfile(self.app.path("share", out["safety"]["name"])))

    def test_restaurar_deixa_versao_com_motivo(self):
        nome = self.no_share("casa-de-teste-2.zip", helpers.zip_bytes({"inventario.json": json.dumps(casa())}))
        self.app.ok("POST", "api/backups/restore", {"name": nome})
        self.assertEqual(self.app.ok("GET", "api/history")["history"][0]["reason"], "restore")

    def test_restaurar_zip_corrompido(self):
        nome = self.no_share("quebrado.zip", b"PK\x03\x04 isto nao e um zip de verdade")
        self.erro("POST", "api/backups/restore", {"name": nome}, 400, "O arquivo não é um .zip válido.")

    def test_restaurar_zip_sem_inventario_nem_fotos(self):
        nome = self.no_share("outra-coisa.zip", helpers.zip_bytes({"notas.txt": "nada aqui"}))
        self.erro("POST", "api/backups/restore", {"name": nome}, 400, "Este .zip não tem inventário nem fotos do InventarIA.")

    def test_restaurar_zip_so_com_fotos_traz_as_fotos_e_nao_mexe_nos_itens(self):
        nome = self.no_share("so-fotos.zip", helpers.zip_bytes({"photos/so-fotos-1.jpg": helpers.jpeg(), "thumbs/so-fotos-1.jpg": helpers.jpeg()}))
        r0 = self.rev()
        out = self.app.ok("POST", "api/backups/restore", {"name": nome})
        self.assertIsNone(out["safety"])
        self.assertEqual(self.rev(), r0)
        self.assertEqual(self.app.get("photos/so-fotos-1.jpg")[2], helpers.jpeg())

    def test_restaurar_inventario_corrompido_dentro_do_zip(self):
        nome = self.no_share("json-quebrado.zip", helpers.zip_bytes({"inventario.json": "{quebrado"}))
        self.erro("POST", "api/backups/restore", {"name": nome}, 400, "O inventario.json de dentro do .zip está corrompido.")

    def test_restaurar_zip_com_pasta_e_lixo_do_mac(self):
        nome = self.no_share("de-um-mac.zip", helpers.zip_bytes({"backup/inventario.json": json.dumps(casa()), "__MACOSX/backup/._inventario.json": "lixo",
                                                                  "backup/photos/do-mac.jpg": helpers.jpeg(), "__MACOSX/backup/photos/._do-mac.jpg": "lixo"}))
        self.app.ok("POST", "api/backups/restore", {"name": nome})
        self.assertEqual(len(self.app.data()["items"]), 38)
        self.assertEqual(self.app.get("photos/do-mac.jpg")[0], 200)

    def test_restaurar_nome_fora_do_padrao_ou_que_nao_existe(self):
        for name in ("sub/backup.zip", "backup.txt", ".escondido.zip", None, ""):
            with self.subTest(name=name):
                self.erro("POST", "api/backups/restore", {"name": name}, 400, "Nome de backup inválido.")
        self.erro("POST", "api/backups/restore", {"name": "nao-existe.zip"}, 404, "Backup não encontrado na pasta share/inventario.")


class Importar(DadosCase):
    def setUp(self):
        self.addCleanup(self.app.ok, "POST", "api/import", {"data": casa()})

    def test_guarda_copia_na_share_antes_de_importar(self):
        self.app.ok("POST", "api/import", {"data": casa()})
        self.assertTrue(any(b["name"].startswith("antes-de-importar-") for b in self.app.ok("GET", "api/backups")["backups"]))

    def test_sem_inventario_recusado(self):
        for body in ({}, {"data": None}, {"data": []}, {"data": {"rooms": []}}, {"data": {"items": []}}, {"data": {"rooms": {}, "items": []}}):
            with self.subTest(body=body):
                self.erro("POST", "api/import", body, 400, "Arquivo inválido: não parece um inventário exportado pelo app.")

    def test_comodo_sem_id_ou_nome_recusado(self):
        for room in ({"id": "x"}, {"name": "X"}, "sala"):
            with self.subTest(room=room):
                self.erro("POST", "api/import", {"data": {"rooms": [room], "items": []}}, 400, "Arquivo inválido: cômodo sem id ou nome.")

    def test_item_sem_id_ou_de_comodo_desconhecido_recusado(self):
        rooms = [{"id": "r", "name": "R"}]
        for item in ({"room": "r", "name": "Sem id"}, {"id": "i", "room": "outro"}, "item"):
            with self.subTest(item=item):
                self.erro("POST", "api/import", {"data": {"rooms": rooms, "items": [item]}}, 400,
                          "Arquivo inválido: item sem id ou com cômodo desconhecido.")

    def test_recusado_nao_muda_nada(self):
        antes = self.app.stored()
        self.erro("POST", "api/import", {"data": {"rooms": [{"id": "r", "name": "R"}], "items": [{"id": "i", "room": "x"}]}}, 400,
                  "Arquivo inválido: item sem id ou com cômodo desconhecido.")
        self.assertEqual(self.app.stored(), antes)

    def test_completa_o_que_falta_no_arquivo(self):
        data = {"rooms": [{"id": "garagem", "name": "Garagem", "photos": ["sala-1.jpg"]}],
                "items": [{"id": "g1", "room": "garagem", "name": "Furadeira", "photo": "sala-2.jpg"}]}
        self.app.ok("POST", "api/import", {"data": data})
        d = self.app.data()
        r, it = d["rooms"][0], d["items"][0]
        self.assertEqual((r["code"], r["cover"], r["photos"], r["order"]), ("GAR", 0, [{"file": "sala-1.jpg", "label": ""}], 0))
        self.assertEqual(it["photos"], ["sala-2.jpg"])
        self.assertNotIn("photo", it)
        self.assertEqual((self.app.stored()["format"], self.app.stored()["schema"]), ("inventario-casa", 1))

    def test_revisao_nunca_volta(self):
        r0 = self.rev()
        out = self.app.ok("POST", "api/import", {"data": casa(rev=1)})
        self.assertGreater(out["rev"], r0, "os outros aparelhos percebem a troca")
        self.assertEqual(self.app.ok("POST", "api/import", {"data": casa(rev=r0 + 100)})["rev"], r0 + 101)

    def test_categorias_validas_ficam_e_invalidas_voltam_ao_padrao(self):
        self.app.ok("POST", "api/import", {"data": casa(cats=[{"id": "ferramentas", "name": "Ferramentas"}, {"id": "Inválida!", "name": "x"}])})
        self.assertEqual(self.app.data()["cats"], [{"id": "eletronicos", "name": "Eletrônicos"}, {"id": "ferramentas", "name": "Ferramentas"}, {"id": "utilidades", "name": "Utilidades"}, {"id": "outros", "name": "Outros"}],
                         "Eletrônicos (a das novidades) sempre existe")
        self.app.ok("POST", "api/import", {"data": casa(cats=[{"id": "Inválida!", "name": "x"}])})
        self.assertEqual(len(self.app.data()["cats"]), 15)
        self.assertNotIn("cats", self.app.stored())

    def test_deixa_versao_com_motivo_importar(self):
        self.app.ok("POST", "api/import", {"data": casa()})
        self.assertEqual(self.app.ok("GET", "api/history")["history"][0]["reason"], "import")


class EnvioEmPartes(DadosCase):
    def comecar(self, size=10, name="arquivo.json"):
        st, _, out = self.app.post("api/upload", {"name": name, "size": size})
        self.assertEqual(st, 201, out)
        self.addCleanup(self.app.delete, f"api/upload/{out['id']}")
        return out["id"]

    def parte(self, uid, data, offset=None):
        q = "" if offset is None else f"?offset={offset}"
        return self.app.request("PUT", f"api/upload/{uid}{q}", raw=data, headers=OCTET)

    def arquivos(self, uid):
        return sorted(n for n in os.listdir(self.app.path("data", "tmp")) if n.startswith(f"upload-{uid}"))

    def test_inicio_devolve_id_e_tamanho_da_parte(self):
        st, _, out = self.app.post("api/upload", {"name": "backup.zip", "size": 1000})
        self.addCleanup(self.app.delete, f"api/upload/{out['id']}")
        self.assertEqual((st, set(out), out["chunk"]), (201, {"id", "chunk"}, 4 * 1024 * 1024))
        self.assertRegex(out["id"], r"^[0-9a-f]{16}$")
        self.assertEqual(self.arquivos(out["id"]), [f"upload-{out['id']}.json", f"upload-{out['id']}.part"])

    def test_tamanho_em_texto_e_limite_de_4_gb(self):
        self.comecar(size="10")
        self.comecar(size=4 * 1024 ** 3)
        for size in (4 * 1024 ** 3 + 1, None, "", [10]):
            with self.subTest(size=size):
                self.erro("POST", "api/upload", {"size": size}, 400, "Tamanho de arquivo inválido.")

    def test_posicao_negativa_409_e_texto_400(self):
        uid = self.comecar()
        st, _, out = self.parte(uid, b"ab", -1)
        self.assertEqual((st, out), (409, {"error": "Parte fora de ordem.", "received": 0}))
        st, _, out = self.parte(uid, b"ab", "dois")
        self.assertEqual((st, out["error"]), (400, "Posição inválida."))

    def test_sem_posicao_comeca_do_zero(self):
        uid = self.comecar()
        self.assertEqual(self.parte(uid, b"abc")[2], {"received": 3, "size": 10})
        self.assertEqual(self.parte(uid, b"xy")[2], {"received": 2, "size": 10}, "sem posição, regrava do começo")

    def test_parte_responde_recebido_e_tamanho(self):
        uid = self.comecar(size=6)
        self.assertEqual(self.parte(uid, b"abc", 0)[2], {"received": 3, "size": 6})
        self.assertEqual(self.parte(uid, b"def", 3)[2], {"received": 6, "size": 6})
        with open(self.app.path("data", "tmp", f"upload-{uid}.part"), "rb") as f:
            self.assertEqual(f.read(), b"abcdef")

    def test_envio_desconhecido_404(self):
        uid = "0123456789abcdef"
        for method, path, raw in (("PUT", f"api/upload/{uid}?offset=0", b"ab"), ("GET", f"api/upload/{uid}", None), ("POST", f"api/upload/{uid}/restore", None)):
            with self.subTest(method=method):
                st, _, out = self.app.request(method, path, raw=raw, headers=OCTET)
                self.assertEqual((st, out["error"]), (404, "Este envio expirou. Comece de novo."))

    def test_parte_grande_demais_413(self):
        uid = self.comecar(size=100)
        st, _, out = self.app.request("PUT", f"api/upload/{uid}?offset=0", raw=b"x" * (16 * 1024 * 1024 + 1), headers=OCTET)
        self.assertEqual((st, out["error"]), (413, "Arquivo grande demais."))
        self.assertEqual(os.path.getsize(self.app.path("data", "tmp", f"upload-{uid}.part")), 0, "nada da parte grande foi gravado")

    def test_informacao_e_restaurar_antes_de_terminar_400(self):
        uid = self.comecar(size=100)
        self.parte(uid, b"x" * 50, 0)
        for method, path in (("GET", f"api/upload/{uid}"), ("POST", f"api/upload/{uid}/restore")):
            with self.subTest(method=method):
                self.erro(method, path, None, 400, "O envio do arquivo não terminou. Tente de novo.")
        self.assertEqual(len(self.arquivos(uid)), 2, "o envio continua lá para terminar")

    def test_json_em_partes_informa_e_restaura(self):
        data = json.dumps(casa()).encode()
        uid = enviar(self.app, data, name="inventario.json", chunk=4096)
        self.assertEqual(self.app.ok("GET", f"api/upload/{uid}"), {"kind": "json", "hasData": True, "items": 38, "rooms": 6, "photos": 0})
        out = self.app.ok("POST", f"api/upload/{uid}/restore")
        self.assertEqual((out["replaced"], out["photosAdded"], out["items"], out["rooms"]), (True, 0, 38, 6))
        self.assertTrue(out["safety"]["name"].startswith("antes-de-importar-"))
        self.assertEqual(self.arquivos(uid), [], "restaurado, o envio é apagado")

    def test_json_com_bom_aceito(self):
        uid = enviar(self.app, "﻿".encode() + json.dumps(casa()).encode())
        self.assertEqual(self.app.ok("GET", f"api/upload/{uid}")["kind"], "json")
        self.assertTrue(self.app.ok("POST", f"api/upload/{uid}/restore")["replaced"])

    def test_restaurar_com_erro_apaga_o_envio(self):
        uid = enviar(self.app, b"{isto nao e json")
        self.erro("POST", f"api/upload/{uid}/restore", None, 400, "Use um backup .zip ou um .json exportado pelo app.")
        self.assertEqual(self.arquivos(uid), [])
        self.assertEqual(self.app.get(f"api/upload/{uid}")[0], 404)

    def test_cancelar_apaga_os_arquivos(self):
        uid = self.comecar()
        self.parte(uid, b"abc", 0)
        self.assertEqual(self.app.ok("DELETE", f"api/upload/{uid}"), {"ok": True})
        self.assertEqual(self.arquivos(uid), [])

    def test_cancelar_desconhecido_responde_ok(self):
        self.assertEqual(self.app.ok("DELETE", "api/upload/fedcba9876543210"), {"ok": True})

    def test_id_em_formato_errado_nao_e_rota(self):
        for method, path, msg in (("GET", "api/upload/XYZ", "Arquivo não encontrado."), ("DELETE", "api/upload/abc", "Endereço não encontrado."),
                                  ("PUT", "api/upload/0123456789ABCDEF", "Endereço não encontrado."),
                                  ("POST", "api/upload/0123456789abcdef0/restore", "Endereço não encontrado.")):
            with self.subTest(path=path):
                self.erro(method, path, None, 404, msg)

    def test_zip_sem_inventario_nem_fotos_informa_400(self):
        uid = enviar(self.app, helpers.zip_bytes({"leia.txt": "nada"}))
        self.erro("GET", f"api/upload/{uid}", None, 400, "Este .zip não tem inventário nem fotos do InventarIA.")

    def test_inicio_com_corpo_que_nao_e_json(self):
        st, _, out = self.app.request("POST", "api/upload", raw=b"size=10", headers=JSON)
        self.assertEqual((st, out["error"]), (400, "Pedido inválido (JSON)."))


class Versoes(DadosCase):
    def versao(self, nome, data):
        p = helpers.write_file(self.app.path("data", "history", nome), json.dumps(data) if not isinstance(data, str) else data)
        self.addCleanup(lambda: os.path.exists(p) and os.unlink(p))
        return nome

    def test_lista_com_tamanho_data_e_contagens(self):
        nome = self.versao("inventario-20990101-000000.json", {"rooms": [{"id": "r", "name": "R"}], "items": [{"id": "a", "room": "r"}, {"id": "b", "room": "r"}]})
        v = next(x for x in self.app.ok("GET", "api/history")["history"] if x["name"] == nome)
        self.assertEqual((v["items"], v["rooms"], v["reason"]), (2, 1, "auto"))
        self.assertEqual(v["size"], os.path.getsize(self.app.path("data", "history", nome)))
        self.assertRegex(v["date"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

    def test_mais_nova_primeiro(self):
        self.versao("inventario-20980101-000000.json", casa())
        self.versao("inventario-20990101-000000.json", casa())
        nomes = [v["name"] for v in self.app.ok("GET", "api/history")["history"]]
        self.assertEqual(nomes[:2], ["inventario-20990101-000000.json", "inventario-20980101-000000.json"])

    def test_arquivos_fora_do_padrao_nao_aparecem(self):
        self.versao("outra-coisa.json", casa())
        self.versao("inventario-2099-01-01.json", casa())
        nomes = [v["name"] for v in self.app.ok("GET", "api/history")["history"]]
        self.assertNotIn("outra-coisa.json", nomes)
        self.assertNotIn("inventario-2099-01-01.json", nomes)
        self.assertNotIn("motivos.json", nomes)

    def test_restaurar_responde_ok_e_revisao_maior(self):
        data = casa()
        data["items"][0]["name"] = "Sofá da versão antiga"
        nome = self.versao("inventario-20990101-000000.json", data)
        self.addCleanup(self.app.ok, "POST", "api/import", {"data": casa()})
        r0 = self.rev()
        out = self.app.ok("POST", "api/history/restore", {"name": nome})
        self.assertEqual((out["ok"], out["rev"] > r0), (True, True))
        self.assertEqual(self.app.data()["items"][0]["name"], "Sofá da versão antiga")

    def test_restaurar_versao_que_nao_e_inventario_recusado(self):
        nome = self.versao("inventario-20990101-000000.json", {"rooms": "x"})
        r0 = self.rev()
        self.erro("POST", "api/history/restore", {"name": nome}, 400, "Arquivo inválido: não parece um inventário exportado pelo app.")
        self.assertEqual(self.rev(), r0)

    def test_restaurar_mensagens(self):
        self.erro("POST", "api/history/restore", {"name": "inventario-19990101-000000.json"}, 404, "Versão não encontrada.")
        for name in ("../inventario.json", "motivos.json", None, ""):
            with self.subTest(name=name):
                self.erro("POST", "api/history/restore", {"name": name}, 400, "Versão inválida.")

    def test_versao_corrompida_nao_derruba_a_lista(self):
        nome = self.versao("inventario-20990101-000000.json", "{cortado")
        st, _, out = self.app.get("api/history")
        self.assertEqual(st, 200, out)
        self.assertNotIn(nome, [v["name"] for v in out["history"] if v.get("items")])
        st, _, out = self.app.post("api/history/restore", {"name": nome})
        self.assertIn(st, (400, 404), out)


class EnviarFoto(DadosCase):
    def miniatura(self, nome):
        with open(self.app.path("data", "thumbs", nome), "rb") as f:
            return f.read()

    def test_sem_miniatura_usa_a_propria_foto(self):
        jpg = helpers.fixture_photo("quarto-1.jpg")
        nome = self.app.ok("POST", "api/photos", {"full": b64(jpg)})["file"]
        self.assertEqual(self.miniatura(nome), jpg)

    def test_miniatura_que_nao_e_jpg_e_trocada_pela_foto(self):
        jpg = helpers.fixture_photo("quarto-1.jpg")
        nome = self.app.ok("POST", "api/photos", {"full": b64(jpg), "thumb": b64(b"\x89PNG\r\n\x1a\n" + b"0" * 200)})["file"]
        self.assertEqual(self.miniatura(nome), jpg)

    def test_miniatura_jpg_fica_separada(self):
        full, thumb = helpers.fixture_photo("quarto-1.jpg"), helpers.fixture_photo("varanda-1.jpg")
        nome = self.app.ok("POST", "api/photos", {"full": b64(full), "thumb": b64(thumb)})["file"]
        self.assertEqual((self.app.get(f"photos/{nome}")[2], self.app.get(f"thumbs/{nome}")[2]), (full, thumb))

    def test_base64_invalido_ou_com_prefixo_de_endereco(self):
        for full in ("!!!", "data:image/jpeg;base64," + b64(helpers.jpeg()), 123):
            with self.subTest(full=str(full)[:30]):
                self.erro("POST", "api/photos", {"full": full}, 400, "Foto inválida.")

    def test_vazia_ou_pequena_demais(self):
        for body in ({}, {"full": ""}, {"full": b64(b"\xff\xd8" + b"0" * 50)}):
            with self.subTest(body=str(body)[:30]):
                self.erro("POST", "api/photos", body, 400, "Envie a foto em JPG.")

    def test_nome_com_data_hora_e_sufixo(self):
        st, _, out = self.app.post("api/photos", {"full": b64(helpers.jpeg())})
        self.assertEqual((st, set(out)), (201, {"file"}))
        self.assertRegex(out["file"], r"^\d{8}-\d{6}-[0-9a-f]{6}\.jpg$")

    def test_duas_iguais_ganham_nomes_diferentes(self):
        a, b = self.upload_photo(), self.upload_photo()
        self.assertNotEqual(a, b)

    def test_enviar_foto_nao_mexe_no_inventario(self):
        r0 = self.rev()
        self.upload_photo()
        self.assertEqual(self.rev(), r0)

    def test_sem_arquivo_pela_metade(self):
        self.upload_photo()
        for d in ("photos", "thumbs"):
            self.assertEqual([n for n in os.listdir(self.app.path("data", d)) if n.endswith(".tmp")], [])


class ServirFotos(DadosCase):
    def test_inexistente_404_em_json(self):
        for path in ("photos/nao-existe.jpg", "thumbs/nao-existe.jpg"):
            with self.subTest(path=path):
                st, h, out = self.app.get(path)
                self.assertEqual((st, out), (404, {"error": "Foto não encontrada."}))
                self.assertIn("application/json", h["Content-Type"])

    def test_nomes_que_nao_sao_de_foto(self):
        helpers.write_file(self.app.path("data", "photos", "nota.txt"), "x")
        for path in ("photos/nota.txt", "photos/inventario.json", "photos/.oculta.jpg", "photos/x.gif", "thumbs/-x.jpg", "photos/a%2fb.jpg", "photos/"):
            with self.subTest(path=path):
                self.assertEqual(self.app.get(path)[0], 404)

    def test_png_e_webp_com_o_tipo_certo(self):
        helpers.write_file(self.app.path("data", "photos", "da-internet.png"), b"\x89PNG\r\n\x1a\n" + b"0" * 100)
        helpers.write_file(self.app.path("data", "photos", "da-internet.webp"), b"RIFF0000WEBP" + b"0" * 100)
        self.assertEqual(self.app.get("photos/da-internet.png")[1]["Content-Type"], "image/png")
        self.assertEqual(self.app.get("photos/da-internet.webp")[1]["Content-Type"], "image/webp")

    def test_foto_no_lugar_da_miniatura_que_falta_sem_cache(self):
        helpers.write_file(self.app.path("data", "photos", "sem-miniatura.jpg"), helpers.jpeg())
        st, h, body = self.app.get("thumbs/sem-miniatura.jpg")
        self.assertEqual((st, h["Cache-Control"], body), (200, "no-cache", helpers.jpeg()))

    def test_miniatura_guardada_por_um_ano(self):
        st, h, body = self.app.get("thumbs/sala-1.jpg")
        self.assertEqual((st, h["Content-Type"], h["Cache-Control"]), (200, "image/jpeg", "private, max-age=31536000, immutable"))
        with open(self.app.path("data", "thumbs", "sala-1.jpg"), "rb") as f:
            self.assertEqual(body, f.read())


if __name__ == "__main__":
    unittest.main()
