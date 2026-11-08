"""Relatório para seguro em PDF (1.36.0): os números, os gráficos da tela Gráficos, os cômodos na ordem da casa, os bens
por último, as fotos (ou sem elas), o cabeçalho dos relatórios dos apps e a marca da CorrerIA Code no pé; o pdf.py (o
mesmo do GerencIA) com as fotos JPG e o espaço entre as letras."""
import json
import os
import re
import unittest
import zlib
from datetime import datetime

from _boot import helpers  # noqa: F401  (põe o app no caminho)
import pdf
import relatorio

with open(os.path.join(helpers.FIXTURE, "inventario.json"), encoding="utf-8") as _f:
    CASA = json.load(_f)
CATS = {"eletronicos": "Eletrônicos", "moveis": "Móveis", "cozinha": "Cozinha e bar", "utilidades": "Utilidades", "outros": "Outros",
        "tapetes": "Tapetes e têxteis", "decoracao": "Decoração e arte", "livros": "Livros e jogos", "plantas": "Plantas",
        "imoveis": "Imóveis", "veiculos": "Veículos"}
AGORA = datetime(2026, 11, 7, 17, 5)


def thumb(nome):
    p = os.path.join(helpers.FIXTURE, "thumbs", nome or "")
    if not (nome and os.path.isfile(p)):
        return None
    with open(p, "rb") as f:
        return f.read()


def textos(raw):
    """Os textos de todas as páginas (os conteúdos vêm comprimidos)."""
    out = []
    for m in re.finditer(rb"stream\n(.*?)\nendstream", raw, re.S):
        try:
            out.append(zlib.decompress(m.group(1)).decode("latin-1"))
        except zlib.error:
            pass  # uma foto
    return "\n".join(out)


class Dados(unittest.TestCase):
    def setUp(self):
        self.d = relatorio.dados(CASA["rooms"], CASA["items"], CATS, agora=AGORA)

    def test_cabecalho_e_numeros(self):
        d = self.d
        self.assertEqual(d["quando"], "07/11/2026 às 17:05")
        self.assertEqual(d["contagem"], "38 itens em 6 cômodos")
        total = sum(i["value"] for i in CASA["items"])
        self.assertEqual(d["numeros"], [("Patrimônio", relatorio.brl(total, False)), ("Itens", "38"), ("Cômodos", "6")])
        self.assertEqual(relatorio.nome_arquivo(d), "inventario-2026-11-07.pdf")

    def test_graficos_como_na_tela(self):
        g = {x["titulo"]: x for x in self.d["graficos"]}
        self.assertEqual(list(g), ["Cômodos", "Categorias", "Faixas de valor", "Itens mais valiosos"])
        vs = [l["v"] for l in g["Cômodos"]["linhas"]]
        self.assertEqual(vs, sorted(vs, reverse=True), "do maior para o menor")
        self.assertEqual(sum(vs), self.d["casa_total"])
        self.assertEqual(g["Cômodos"]["linhas"][0]["sub"], "12 itens")
        self.assertEqual(sum(f["n"] for f in g["Faixas de valor"]["faixas"]), 38 - g["Faixas de valor"]["sem_valor"])
        self.assertEqual(len(g["Itens mais valiosos"]["linhas"]), 10)
        self.assertEqual(g["Itens mais valiosos"]["linhas"][0]["nome"], max(CASA["items"], key=lambda i: i["value"])["name"])

    def test_comodos_na_ordem_da_casa_e_os_itens_pelo_codigo(self):
        ordem = [r["name"] for r in sorted(CASA["rooms"], key=lambda r: r.get("order") or 0)]
        self.assertEqual([s["nome"] for s in self.d["secoes"]], ordem)
        cods = [i["codigo"] for i in self.d["secoes"][0]["itens"]]
        self.assertEqual(cods, sorted(cods))
        self.assertTrue(cods[0].endswith("-001"))

    def test_bens_por_ultimo_e_sem_fotos(self):
        rooms = CASA["rooms"] + [{"id": "bens", "name": "Bens", "code": "BEN", "kind": "bens", "order": 0}]
        items = CASA["items"] + [{"id": "b1", "room": "bens", "seq": 1, "name": "Terreno na serra", "cat": "imoveis", "value": 90000, "qty": "1"}]
        d = relatorio.dados(rooms, items, CATS, fotos=False, agora=AGORA)
        self.assertEqual(d["secoes"][-1]["nome"], "Bens")
        self.assertTrue(d["secoes"][-1]["bens"])
        self.assertEqual(d["numeros"][0][0], "Na casa")
        self.assertEqual(d["numeros"][-1], ("Bens", "R$ 90.000"))
        self.assertEqual(d["graficos"][-1]["titulo"], "Bens")
        self.assertTrue(all(i["foto"] is None for s in d["secoes"] for i in s["itens"]), "sem fotos")

    def test_formatos(self):
        self.assertEqual(relatorio.brl(1234.5), "R$ 1.234,50")
        self.assertEqual(relatorio.brl(28795), "R$ 28.795")
        self.assertEqual(relatorio.brl(10.4, False), "R$ 10")
        self.assertEqual(relatorio.brl_k(5100), "R$ 5,1 mil")
        self.assertEqual(relatorio.brl_k(20400), "R$ 20 mil")
        self.assertEqual(relatorio.brl_k(1_250_000), "R$ 1,2 mi")
        self.assertEqual(relatorio.parte(26, 100), "26%")
        self.assertEqual(relatorio.parte(8.24, 100), "8,2%")
        self.assertEqual(relatorio.parte(1, 0), "0%")
        self.assertEqual(relatorio.qtd("~ 3"), "3")


class Pdf(unittest.TestCase):
    def test_o_relatorio(self):
        d = relatorio.dados(CASA["rooms"], CASA["items"], CATS, agora=AGORA)
        raw = relatorio.gerar_pdf(d, cor="#b48cf6", tinta="#7f56bb", ler_foto=thumb)
        self.assertTrue(raw.startswith(b"%PDF-1.4") and raw.rstrip().endswith(b"%%EOF"))
        t = textos(raw)
        for s in ("(Inventar) Tj", "(IA) Tj", "(Relat\xf3rio para seguro) Tj", "(38 itens em 6 c\xf4modos \xb7 07/11/2026 \xe0s 17:05) Tj",
                  "(Faixas de valor) Tj", "(Itens mais valiosos) Tj", "(Sala de estar) Tj", "(SAL-001) Tj", "(Subtotal) Tj",
                  "(Correr) Tj", "( Code) Tj", "(DESENVOLVIMENTO DE SOFTWARES) Tj", "0.90 Tc"):
            self.assertIn(s, t)
        self.assertNotIn("(Bens) Tj", t)
        paginas = int(re.search(rb"/Count (\d+)", raw).group(1))
        self.assertGreaterEqual(paginas, 2)
        self.assertIn(f"(p\xe1gina {paginas} de {paginas}) Tj", t)
        self.assertEqual(raw.count(b"/Subtype /Image"), len({i["photos"][0] for i in CASA["items"] if i.get("photos")}), "cada foto uma vez só")
        self.assertIn("0.706 0.549 0.965 rg", t, "a cor do app")

    def test_sem_fotos(self):
        d = relatorio.dados(CASA["rooms"], CASA["items"], CATS, fotos=False, agora=AGORA)
        raw = relatorio.gerar_pdf(d, ler_foto=thumb)
        self.assertNotIn(b"/Subtype /Image", raw)

    def test_casa_vazia(self):
        d = relatorio.dados([], [], CATS, agora=AGORA)
        t = textos(relatorio.gerar_pdf(d))
        self.assertIn("(Nenhum item cadastrado.) Tj", t)
        self.assertEqual(d["graficos"], [])


class Documento(unittest.TestCase):
    def test_jpeg_info(self):
        self.assertIsNone(pdf.jpeg_info(b"nada"))
        larg, alt, comp = pdf.jpeg_info(thumb("cozinha-1.jpg"))
        self.assertTrue(larg > 0 and alt > 0 and comp == 3)

    def test_imagem_e_espaco(self):
        doc = pdf.Documento("t", "InventarIA")
        self.assertFalse(doc.imagem(10, 10, 30, 30, b"x"))
        self.assertTrue(doc.imagem(10, 10, 30, 30, thumb("cozinha-1.jpg"), raio=4))
        doc.texto(10, 60, "ABC", 8, True, espaco=1)
        doc.texto(10, 80, "depois", 8)
        raw = doc.bytes()
        t = textos(raw)
        self.assertIn("/Im1 Do Q", t)
        self.assertRegex(t, r"q BT /F2 8\.00 Tf 1\.00 Tc .* Tj ET Q", "o espaço entre as letras só neste texto")
        self.assertRegex(raw.decode("latin-1"), r"/XObject << /Im1 \d+ 0 R >>")
        # a tabela de posições aponta para cada objeto
        s = raw.decode("latin-1")
        at = s.index("\nxref\n") + 1
        offs = [int(m.group(1)) for m in re.finditer(r"^(\d{10}) 00000 n $", s[at:], re.M)]
        for k, o in enumerate(offs, 1):
            self.assertTrue(s[o:].startswith(f"{k} 0 obj"))


if __name__ == "__main__":
    unittest.main()
