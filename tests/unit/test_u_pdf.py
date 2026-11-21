"""O pdf.py (o mesmo arquivo do GerencIA) nas partes que o Relatório do inventário não usa todo dia: o texto que não cabe
(cortado com "…" ou quebrado em linhas), um JPG com enchimento antes das medidas, o que não é JPG, uma cor mal escrita,
um texto vazio, um retângulo sem cantos arredondados e uma figura com menos de três pontos. Textos inventados."""
import re
import unittest
import zlib

from _boot import helpers  # noqa: F401  (põe o app no caminho)
import pdf


def jpg(larg, alt, comp=3, marcador=0xC0, extras=b""):
    """Um JPG mínimo: só o começo, os extras e o quadro com as medidas."""
    return b"\xff\xd8" + extras + bytes([0xFF, marcador, 0x00, 0x11, 0x08]) + alt.to_bytes(2, "big") + larg.to_bytes(2, "big") + bytes([comp]) + b"\x00" * 12


def conteudo(doc, k=0):
    """Os comandos da página k, já descompactados."""
    b = doc.bytes()
    streams = [zlib.decompress(b[m.end():m.end() + int(m.group(1))])
               for m in re.finditer(rb"/Length (\d+) /Filter /FlateDecode >>\nstream\n", b)]
    return streams[k].decode("latin-1")


class TestTextoQueNaoCabe(unittest.TestCase):
    def test_cortar(self):
        self.assertEqual(pdf.cortar("Sofá", 200, 10), "Sofá", "cabe: inteiro")
        curto = pdf.cortar("Sofá de três lugares da sala de estar", 80, 10)
        self.assertTrue(curto.endswith("…") and curto.startswith("Sofá de"), curto)
        self.assertLessEqual(pdf.largura(curto, 10), 80)
        self.assertFalse(curto[:-1].endswith(" "), "sem espaço antes das reticências")
        self.assertEqual(pdf.cortar("Sofá", 1, 10), "…", "numa largura mínima, só as reticências")
        self.assertEqual(pdf.cortar(1234567890, 20, 10)[-1], "…", "um número vira texto")

    def test_quebrar(self):
        linhas = pdf.quebrar("Mesa de jantar de madeira com seis cadeiras estofadas", 120, 10)
        self.assertGreater(len(linhas), 1)
        self.assertEqual(" ".join(linhas), "Mesa de jantar de madeira com seis cadeiras estofadas", "nada se perde")
        for linha in linhas:
            self.assertLessEqual(pdf.largura(linha, 10), 120)
        self.assertEqual(pdf.quebrar("Sala\nCozinha", 500, 10), ["Sala", "Cozinha"], "as linhas do texto ficam")
        self.assertEqual(pdf.quebrar("Inconstitucionalissimamente", 20, 10), ["Inconstitucionalissimamente"], "uma palavra maior que a linha fica inteira")
        self.assertEqual(pdf.quebrar("", 100, 10), [""])


class TestFotos(unittest.TestCase):
    def test_medidas_depois_de_enchimento(self):
        self.assertEqual(pdf.jpeg_info(jpg(40, 30)), (40, 30, 3))
        self.assertEqual(pdf.jpeg_info(b"\xff\xd8\x00\x00" + jpg(8, 6)[2:]), (8, 6, 3), "pula o que não é marcador")
        self.assertEqual(pdf.jpeg_info(b"\xff\xd8\xff\xff" + jpg(8, 6)[2:]), (8, 6, 3), "o enchimento 0xFF também")
        self.assertEqual(pdf.jpeg_info(b"\xff\xd8\xff\xd0" + jpg(8, 6)[2:]), (8, 6, 3), "os marcadores sem tamanho")
        self.assertEqual(pdf.jpeg_info(jpg(40, 30, comp=1, extras=b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")), (40, 30, 1), "depois de um APP0")

    def test_o_que_nao_e_jpg(self):
        for nada in (None, b"", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20, b"\xff\xd8\xff\xd9", b"\xff\xd8" + b"\xff\xe0\x00\x04\x00\x00" * 3):
            with self.subTest(nada=nada[:4] if nada else nada):
                self.assertIsNone(pdf.jpeg_info(nada))
        self.assertIsNone(pdf.jpeg_info(jpg(0, 30)), "sem largura")
        self.assertIsNone(pdf.jpeg_info(jpg(40, 30, comp=2)), "nem cinza, nem RGB, nem CMYK")
        doc = pdf.Documento("Relatório de teste")
        self.assertIs(doc.imagem(40, 40, 80, 60, b"isto nao e uma foto"), False)
        self.assertNotIn("Do", conteudo(doc))

    def test_foto_sem_cantos_arredondados(self):
        doc = pdf.Documento("Relatório de teste")
        self.assertTrue(doc.imagem(40, 40, 80, 60, jpg(40, 30)))
        self.assertRegex(conteudo(doc), r"40\.00 \d+\.\d\d 80\.00 60\.00 re", "a caixa da foto, reta")
        self.assertIn(" Do", conteudo(doc))


class TestFormas(unittest.TestCase):
    def test_cor_mal_escrita_vira_preto(self):
        self.assertEqual(pdf.cor_rgb("#ff0000"), (1.0, 0.0, 0.0))
        for ruim in (None, "", "#fff", "vermelho", "#gggggg"):
            with self.subTest(ruim=ruim):
                self.assertEqual(pdf.cor_rgb(ruim), (0, 0, 0))

    def test_texto_vazio_nao_escreve_nada(self):
        doc = pdf.Documento("Relatório de teste")
        doc.texto(40, 60, "")
        doc.texto(40, 60, None)
        self.assertNotIn("Tj", conteudo(doc))
        doc.texto(40, 60, 0)
        self.assertIn("(0) Tj", conteudo(doc), "o zero é um texto")

    def test_retangulo_sem_cantos_arredondados(self):
        doc = pdf.Documento("Relatório de teste")
        doc.retangulo(40, 50, 100, 20, fundo=(1, 0, 0))
        self.assertRegex(conteudo(doc), r"40\.00 \d+\.\d\d 100\.00 20\.00 re")
        doc.retangulo(40, 90, 100, 20, fundo=(1, 0, 0), raio=6)
        self.assertRegex(conteudo(doc), r" c\b", "com raio, as curvas dos cantos")

    def test_figura_com_menos_de_tres_pontos_nao_existe(self):
        doc = pdf.Documento("Relatório de teste")
        antes = conteudo(doc) if doc.bytes().count(b"FlateDecode") else ""
        doc.poligono([(10, 10), (20, 20)])
        self.assertEqual(conteudo(doc), antes)
        doc.poligono([(10, 10), (20, 20), (10, 30)], fundo=(0, 0, 1))
        self.assertRegex(conteudo(doc), r"10\.00 \d+\.\d\d m 20\.00 \d+\.\d\d l 10\.00 \d+\.\d\d l")


if __name__ == "__main__":
    unittest.main()
