"""Exportar: a planilha (export_csv_bytes), o .zip completo (write_zip) e as rotas /api/export.csv, .json e .zip.

Confere cada coluna da planilha (valores com vírgula, textos com ponto e vírgula, aspas e quebras de linha, zonas,
categorias da casa, fotos, datas e a ordem), o que entra e o que não entra no .zip, e o JSON baixado.
"""
import csv
import io
import json
import os
import random
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime
from unittest import mock

from _boot import UnitBase, helpers, server as S

COLUNAS = ["Código", "Cômodo", "Zona", "Item", "Detalhes", "Categoria", "Quantidade", "Valor (R$)", "Fotos", "Criado em", "Atualizado em"]
FIXOS = {"inventario.json", "inventario.csv", "LEIA-ME.txt"}
FOTOS_DA_CASA = {"sala-1.jpg", "sala-2.jpg", "sala-3.jpg", "cozinha-1.jpg", "quarto-1.jpg", "escritorio-1.jpg",
                 "escritorio-2.jpg", "lavanderia-1.jpg", "varanda-1.jpg"}
ORDEM_DA_CASA = ([f"SAL-{n:03d}" for n in range(1, 13)] + [f"COZ-{n:03d}" for n in range(1, 8)] + [f"QUA-{n:03d}" for n in range(1, 7)]
                 + [f"ESC-{n:03d}" for n in range(1, 6)] + [f"LAV-{n:03d}" for n in range(1, 6)] + [f"VAR-{n:03d}" for n in range(1, 4)])


def linhas(raw=None):
    """A planilha lida como o Excel leria: UTF-8 com BOM, separador ponto e vírgula."""
    raw = S.export_csv_bytes() if raw is None else raw
    return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), delimiter=";"))


def zip_bytes_do_app() -> bytes:
    buf = io.BytesIO()
    S.write_zip(buf)
    return buf.getvalue()


class Resposta:
    """Um pedido de mentira para chamar as funções das rotas direto; guarda o que seria enviado ao navegador."""
    send_bytes = S.Handler.send_bytes
    send_json = S.Handler.send_json

    def __init__(self, body=None, command="GET"):
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

    def corpo(self) -> bytes:
        return self.wfile.getvalue()


class PlanilhaBase(UnitBase):
    def linha(self, iid):
        tag = self.store.tag(self.item(iid))
        return next(r for r in linhas()[1:] if r[0] == tag)

    def muda(self, iid, **campos):
        self.item(iid).update(campos)


class Planilha(PlanilhaBase):
    def test_cabecalho_tem_as_onze_colunas_na_ordem(self):
        self.assertEqual(linhas()[0], COLUNAS)

    def test_acentos_saem_em_utf8_com_um_bom_so(self):
        raw = S.export_csv_bytes()
        self.assertEqual(raw.count("﻿".encode()), 1, "o BOM aparece só uma vez, no começo")
        self.assertIn("Cômodo".encode("utf-8"), raw)
        self.assertIn("Sofá de 3 lugares".encode("utf-8"), raw)
        self.assertIn("Escritório", raw[3:].decode("utf-8"), "depois do BOM, tudo é UTF-8 válido")

    def test_linhas_terminam_em_crlf(self):
        raw = S.export_csv_bytes()
        self.assertEqual(raw.count(b"\r\n"), 39, "cabeçalho e 38 itens, cada um terminando em CRLF")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "sem quebra de linha solta")

    def test_virgula_no_texto_nao_vira_coluna_nem_ganha_aspas(self):
        raw = S.export_csv_bytes().decode("utf-8-sig")
        self.assertIn(";Tecido liso, almofadas de encosto soltas e pés de madeira.;", raw)
        self.assertTrue(all(len(r) == 11 for r in linhas()), "toda linha tem as 11 colunas")

    def test_ponto_e_virgula_no_texto_fica_entre_aspas(self):
        self.muda("sal-001", name="Mesa; 4 cadeiras")
        self.assertIn(';"Mesa; 4 cadeiras";', S.export_csv_bytes().decode("utf-8-sig"))
        row = self.linha("sal-001")
        self.assertEqual((len(row), row[3]), (11, "Mesa; 4 cadeiras"))

    def test_aspas_no_texto_sao_dobradas(self):
        self.muda("sal-007", details='Tela de 55" com "suporte"')
        self.assertIn('"Tela de 55"" com ""suporte"""', S.export_csv_bytes().decode("utf-8-sig"))
        self.assertEqual(self.linha("sal-007")[4], 'Tela de 55" com "suporte"')

    def test_quebra_de_linha_nos_detalhes_fica_na_mesma_celula(self):
        texto = "Linha um\nLinha dois\r\nLinha três"
        self.muda("coz-004", details=texto)
        rows = linhas()
        self.assertEqual(len(rows), 39, "a quebra não cria uma linha nova na planilha")
        self.assertEqual(self.linha("coz-004")[4], texto)

    def test_colunas_vem_do_cadastro_do_item(self):
        row = self.linha("sal-001")
        self.assertEqual(row[2], "Sofá", "zona")
        self.assertEqual(row[3], "Sofá de 3 lugares cinza-azulado")
        self.assertEqual(row[4], "Tecido liso, almofadas de encosto soltas e pés de madeira.")
        self.assertEqual(row[6], "1", "quantidade")
        self.assertEqual(row[8], "sala-1.jpg", "fotos")
        self.assertEqual((row[9], row[10]), ("2026-10-02T02:00:00-03:00", "2026-10-02T02:00:00-03:00"), "criado e atualizado em")

    def test_valor_com_centavos_usa_virgula_e_dois_digitos(self):
        for valor, esperado in ((1234.5, "1234,50"), (0.99, "0,99"), (10.05, "10,05"), (7, "7,00")):
            with self.subTest(valor=valor):
                self.muda("sal-002", value=valor)
                self.assertEqual(self.linha("sal-002")[7], esperado)

    def test_valor_grande_sai_sem_ponto_de_milhar(self):
        self.muda("sal-001", value=1250000)
        self.assertEqual(self.linha("sal-001")[7], "1250000,00", "o Excel lê sem confundir o ponto com decimal")

    def test_valor_vazio_nulo_ou_ausente_sai_zero(self):
        for campos in ({"value": None}, {"value": ""}, {"value": 0}):
            with self.subTest(campos=campos):
                self.muda("sal-003", **campos)
                self.assertEqual(self.linha("sal-003")[7], "0,00")
        self.item("sal-003").pop("value")
        self.assertEqual(self.linha("sal-003")[7], "0,00")

    def test_valor_digitado_na_tela_sai_igual_na_planilha(self):
        self.store.update_item("sal-004", {"value": "1.234,56"}, None)
        self.assertEqual(self.linha("sal-004")[7], "1234,56")

    def test_zona_ausente_ou_nula_fica_vazia(self):
        self.muda("sal-005", zone=None)
        self.assertEqual(self.linha("sal-005")[2], "")
        self.item("sal-005").pop("zone")
        self.assertEqual(self.linha("sal-005")[2], "")

    def test_quantidade_em_texto_sai_como_esta_e_sem_quantidade_e_1(self):
        self.muda("sal-002", qty="2 pares")
        self.assertEqual(self.linha("sal-002")[6], "2 pares")
        self.item("sal-002").pop("qty")
        self.assertEqual(self.linha("sal-002")[6], "1")

    def test_fotos_separadas_por_virgula_e_espaco(self):
        self.muda("sal-001", photos=["sala-1.jpg", "sala-2.jpg", "sala-3.jpg"])
        self.assertEqual(self.linha("sal-001")[8], "sala-1.jpg, sala-2.jpg, sala-3.jpg")

    def test_item_sem_fotos_fica_com_a_coluna_vazia(self):
        self.assertEqual(self.linha("coz-005")[8], "", "item da casa de teste sem foto")
        self.muda("coz-005", photos=None)
        self.assertEqual(self.linha("coz-005")[8], "")

    def test_datas_ausentes_ficam_vazias(self):
        it = self.item("qua-001")
        it.pop("createdAt")
        it["updatedAt"] = None
        row = self.linha("qua-001")
        self.assertEqual((row[9], row[10]), ("", ""))

    def test_ordem_por_comodo_e_numero_mesmo_com_a_lista_embaralhada(self):
        random.Random(7).shuffle(self.store.data["items"])
        self.assertEqual([r[0] for r in linhas()[1:]], ORDEM_DA_CASA)

    def test_item_novo_entra_no_fim_do_seu_comodo(self):
        self.store.create_items([{"room": "sala", "name": "Abajur de mesa", "value": "75,5"}], None)
        codigos = [r[0] for r in linhas()[1:]]
        self.assertEqual(codigos[12], "SAL-013", "depois do último da sala, antes da cozinha")
        self.assertEqual(codigos[13], "COZ-001")
        self.assertEqual(linhas()[13][7], "75,50")

    def test_item_de_comodo_que_nao_existe_vai_para_o_fim_com_codigo_itm(self):
        self.store.data["items"].append({"id": "perdido", "room": "sumiu", "seq": 7, "name": "Caixa perdida", "value": 10})
        ultima = linhas()[-1]
        self.assertEqual((ultima[0], ultima[1], ultima[3]), ("ITM-007", "sumiu", "Caixa perdida"),
                         "sem o cômodo, o código vira ITM e a coluna mostra o id do cômodo")

    def test_casa_vazia_tem_so_o_cabecalho(self):
        self.store.data["items"] = []
        self.store.data["rooms"] = []
        self.assertEqual(linhas(), [COLUNAS])

    def test_valor_em_texto_de_json_importado_nao_quebra_a_planilha(self):
        d = helpers.fixture_data()
        d["items"][0]["value"] = "1.200,50"
        try:
            self.store.replace_all(d, "import")
        except S.ApiError:
            return  # recusar o arquivo na importação também resolve
        self.assertEqual(self.linha("sal-001")[7], "1200,50")


class ZipCompleto(UnitBase):
    def abrir(self) -> zipfile.ZipFile:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes_do_app()))
        self.addCleanup(z.close)
        return z

    def test_entram_as_fotos_do_comodo_que_nenhum_item_usa(self):
        helpers.write_file(os.path.join(S.PHOTOS_DIR, "sala-parede.jpg"), helpers.jpeg())
        helpers.write_file(os.path.join(S.THUMBS_DIR, "sala-parede.jpg"), helpers.jpeg())
        self.store.room("sala")["photos"].append({"file": "sala-parede.jpg", "label": "Parede"})
        names = set(self.abrir().namelist())
        self.assertTrue({"photos/sala-parede.jpg", "thumbs/sala-parede.jpg"} <= names)

    def test_foto_citada_sem_arquivo_fica_de_fora_sem_erro(self):
        self.item("sal-001")["photos"] = ["sala-1.jpg", "sumiu.jpg"]
        names = self.abrir().namelist()
        self.assertNotIn("photos/sumiu.jpg", names)
        self.assertIn("photos/sala-1.jpg", names)

    def test_foto_sem_miniatura_entra_so_em_photos(self):
        os.unlink(os.path.join(S.THUMBS_DIR, "varanda-1.jpg"))
        names = self.abrir().namelist()
        self.assertIn("photos/varanda-1.jpg", names)
        self.assertNotIn("thumbs/varanda-1.jpg", names)

    def test_cada_foto_entra_uma_vez_so(self):
        names = self.abrir().namelist()
        self.assertEqual(len(names), len(set(names)), "a sala-1.jpg é usada por vários itens e pelo cômodo")
        self.assertEqual({n.split("/", 1)[1] for n in names if n.startswith("photos/")}, FOTOS_DA_CASA)
        self.assertEqual({n.split("/", 1)[1] for n in names if n.startswith("thumbs/")}, FOTOS_DA_CASA)

    def test_fotos_e_miniaturas_sao_copias_exatas(self):
        z = self.abrir()
        for nome in sorted(FOTOS_DA_CASA):
            for sub, pasta in (("photos", S.PHOTOS_DIR), ("thumbs", S.THUMBS_DIR)):
                with self.subTest(foto=f"{sub}/{nome}"), open(os.path.join(pasta, nome), "rb") as f:
                    self.assertEqual(z.read(f"{sub}/{nome}"), f.read())

    def test_json_do_zip_e_o_inventario_atual(self):
        self.store.create_cat({"name": "Ferramentas"})
        self.store.create_room({"name": "Garagem"})
        dentro = json.loads(self.abrir().read("inventario.json"))
        self.assertEqual(dentro, json.loads(json.dumps(self.store.data)))
        self.assertIn("Ferramentas", [c["name"] for c in dentro["cats"]], "as categorias da casa vão junto")

    def test_json_do_zip_mantem_os_acentos(self):
        raw = self.abrir().read("inventario.json")
        self.assertIn("Sofá de 3 lugares".encode("utf-8"), raw)
        self.assertNotIn(b"\\u00e1", raw, "acentos gravados como letras, não como \\u00e1")

    def test_csv_do_zip_e_a_mesma_planilha(self):
        self.assertEqual(self.abrir().read("inventario.csv"), S.export_csv_bytes())

    def test_textos_sao_comprimidos(self):
        z = self.abrir()
        for nome in sorted(FIXOS):
            with self.subTest(nome=nome):
                self.assertEqual(z.getinfo(nome).compress_type, zipfile.ZIP_DEFLATED)

    def test_nao_entram_configuracoes_versoes_nem_temporarios(self):
        self.store.settings["ai_entity"] = "ai_task.casa"
        self.store.save_settings()
        helpers.write_file(S.USAGE_FILE, "{}")
        helpers.write_file(os.path.join(S.DATA_DIR, "integracao.key"), "chave-de-teste")
        helpers.write_file(os.path.join(S.TMP_DIR, "upload-0123456789abcdef.part"), b"x")
        self.store.create_room({"name": "Garagem"})  # a primeira gravação guarda uma versão em history/
        self.assertTrue(os.listdir(S.HISTORY_DIR))
        for n in self.abrir().namelist():
            with self.subTest(arquivo=n):
                self.assertTrue(n in FIXOS or n.startswith(("photos/", "thumbs/")), f"{n} não devia estar no .zip")

    def test_casa_vazia_tem_so_os_tres_arquivos(self):
        self.store.data["items"] = []
        self.store.data["rooms"] = []
        z = self.abrir()
        self.assertEqual(set(z.namelist()), FIXOS)
        self.assertEqual(json.loads(z.read("inventario.json"))["items"], [])

    def test_leia_me_diz_o_que_tem_e_como_restaurar(self):
        texto = self.abrir().read("LEIA-ME.txt").decode("utf-8")
        for trecho in ("inventario.json", "inventario.csv", "photos/", "thumbs/", "share/inventario"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, texto)

    def test_foto_com_caminho_para_fora_da_pasta_nao_entra_no_zip(self):
        fora = tempfile.mkdtemp(prefix="inventaria-fora-")
        self.addCleanup(shutil.rmtree, fora, ignore_errors=True)
        segredo = helpers.write_file(os.path.join(fora, "segredo.jpg"), b"nao e foto da casa")
        self.store.settings["ai_entity"] = "ai_task.casa"
        self.store.save_settings()
        for nome in ("../settings.json", segredo):
            with self.subTest(nome=nome):
                d = helpers.fixture_data()
                d["items"][0]["photos"] = [nome]
                self.store.replace_all(d, "import")
                for n in self.abrir().namelist():
                    if n not in FIXOS:
                        sub, _, arq = n.partition("/")
                        self.assertIn(sub, ("photos", "thumbs"), n)
                        self.assertTrue(S.SAFE_FILE.fullmatch(arq), n)


class Rotas(UnitBase):
    def dias(self):
        return {datetime.now().strftime("%Y-%m-%d")}

    def baixar(self, kind):
        antes = self.dias()
        h = Resposta()
        S.r_export(h, kind, query={})
        return h, antes | self.dias()

    def test_csv_baixa_com_o_nome_do_dia(self):
        h, dias = self.baixar("csv")
        self.assertEqual(h.status, 200)
        self.assertEqual(h.headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(h.headers["Content-Disposition"], {f'attachment; filename="inventario-{d}.csv"' for d in dias})
        self.assertEqual(h.headers["Cache-Control"], "no-store")
        self.assertEqual(h.corpo(), S.export_csv_bytes())
        self.assertEqual(int(h.headers["Content-Length"]), len(h.corpo()))

    def test_json_tem_o_inventario_inteiro(self):
        self.store.create_cat({"name": "Ferramentas"})
        h, dias = self.baixar("json")
        self.assertEqual(h.headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn(h.headers["Content-Disposition"], {f'attachment; filename="inventario-{d}.json"' for d in dias})
        d = json.loads(h.corpo())
        self.assertEqual(d, json.loads(json.dumps(self.store.data)))
        self.assertEqual((d["format"], len(d["rooms"]), len(d["items"])), ("inventario-casa", 6, 38))

    def test_json_nao_leva_as_configuracoes_do_app(self):
        self.store.settings.update(ai_entity="ai_task.casa", ai=True)
        self.store.save_settings()
        h, _ = self.baixar("json")
        self.assertNotIn(b"ai_task.casa", h.corpo())
        self.assertLessEqual(set(json.loads(h.corpo())), {"format", "schema", "rev", "updatedAt", "rooms", "items", "cats"})

    def test_json_baixado_volta_pelo_importar(self):
        h, _ = self.baixar("json")
        p = helpers.write_file(os.path.join(S.TMP_DIR, "baixado.json"), h.corpo())
        self.assertEqual(S.inspect_file(p), {"kind": "json", "hasData": True, "items": 38, "rooms": 6, "photos": 0})
        itens = json.loads(json.dumps(self.store.data["items"]))
        self.store.data["items"] = []
        with open(p, encoding="utf-8") as f:
            self.store.replace_all(json.load(f), "import")
        self.assertEqual(self.store.data["items"], itens)

    def test_zip_manda_o_tamanho_certo_e_apaga_o_temporario(self):
        antes = set(os.listdir(S.TMP_DIR))
        h, dias = self.baixar("zip")
        self.assertEqual(h.headers["Content-Type"], "application/zip")
        self.assertIn(h.headers["Content-Disposition"], {f'attachment; filename="inventario-{d}.zip"' for d in dias})
        self.assertEqual(int(h.headers["Content-Length"]), len(h.corpo()))
        with zipfile.ZipFile(io.BytesIO(h.corpo())) as z:
            self.assertIn("photos/sala-1.jpg", z.namelist())
        self.assertEqual(set(os.listdir(S.TMP_DIR)), antes, "o .zip temporário em data/tmp sai depois de enviado")

    def test_zip_apaga_o_temporario_mesmo_quando_falha(self):
        antes = set(os.listdir(S.TMP_DIR))
        with mock.patch.object(S, "write_zip", side_effect=OSError("disco cheio")):
            with self.assertRaises(OSError):
                S.r_export(Resposta(), "zip", query={})
        self.assertEqual(set(os.listdir(S.TMP_DIR)), antes)


if __name__ == "__main__":
    unittest.main()
