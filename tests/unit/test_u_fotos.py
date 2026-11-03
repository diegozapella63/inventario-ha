"""Fotos no servidor: save_photo (conteúdo, miniatura, tamanho mínimo e máximo do pedido, base64, nome do arquivo),
photo_exists, clean_photos (limite de 12, repetidas, ordem, caminhos perigosos), clean_photo_src e a rota que serve
/photos e /thumbs (Handler.static), chamada com um pedido de mentira, sem servidor.

Complementa test_basicos.py (Fotos) e tests/integration/test_api.py (Fotos), sem repetir o que eles já conferem.
"""
import base64
import io
import os
import unittest
from datetime import datetime
from unittest import mock

from _boot import UnitBase, helpers, server as S


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def ler(path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


class Pedido(S.Handler):
    """Um pedido HTTP de mentira: guarda status, cabeçalhos e corpo da resposta, sem socket."""

    def __init__(self, command="GET", headers=None, body=b""):
        self.command = command
        self.headers = headers or {}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.status, self.sent = None, {}
        self.close_connection = False
        self._body_read = False

    def send_response(self, code, message=None):
        self.status = code

    def send_header(self, key, value):
        self.sent[key] = value

    def end_headers(self):
        pass

    def servir(self, path):
        self.static(path)
        return self.status, self.sent, self.wfile.getvalue()


def dia_fixo(quando):
    class Agora(datetime):
        @classmethod
        def now(cls, tz=None):
            return quando
    return mock.patch.object(S, "datetime", Agora)


class SalvarFoto(UnitBase):
    def test_conteudo_gravado_e_o_enviado(self):
        jpg = helpers.fixture_photo("sala-2.jpg")
        f = S.save_photo({"full": b64(jpg)})["file"]
        self.assertEqual(ler(os.path.join(S.PHOTOS_DIR, f)), jpg)

    def test_miniatura_valida_e_gravada_separada(self):
        full, mini = helpers.fixture_photo("sala-1.jpg"), helpers.fixture_photo("quarto-1.jpg")
        f = S.save_photo({"full": b64(full), "thumb": b64(mini)})["file"]
        self.assertEqual(ler(os.path.join(S.PHOTOS_DIR, f)), full)
        self.assertEqual(ler(os.path.join(S.THUMBS_DIR, f)), mini)

    def test_menos_de_100_bytes_recusado_e_100_aceito(self):
        self.assertApiError(400, S.save_photo, {"full": b64(b"\xff\xd8" + b"0" * 97)}, msg_part="JPG")
        self.assertTrue(S.photo_exists(S.save_photo({"full": b64(b"\xff\xd8" + b"0" * 98)})["file"]))

    def test_foto_grande_e_aceita(self):
        grande = b"\xff\xd8" + os.urandom(5 * 1024 * 1024)
        f = S.save_photo({"full": b64(grande)})["file"]
        self.assertEqual(os.path.getsize(os.path.join(S.PHOTOS_DIR, f)), len(grande), "o limite é o do pedido, não o da foto")

    def test_pedido_acima_de_30_mb_recusado(self):
        h = Pedido("POST", {"Content-Length": str(S.MAX_BODY + 1)}, b"{}")
        e = self.assertApiError(413, h.read_body)
        self.assertIn("grande demais", e.msg)
        self.assertTrue(h.close_connection, "não lê o resto: fecha a conexão")

    def test_foto_que_nao_e_texto_recusada(self):
        for full in (123, ["x"], {"a": 1}):
            with self.subTest(full=full):
                self.assertApiError(400, S.save_photo, {"full": full}, msg_part="Foto inválida")

    def test_base64_com_prefixo_ou_quebra_de_linha_recusado(self):
        puro = b64(helpers.jpeg())
        for ruim in ("data:image/jpeg;base64," + puro, puro[:80] + "\n" + puro[80:], "ção" + puro):
            with self.subTest(ruim=ruim[:30]):
                self.assertApiError(400, S.save_photo, {"full": ruim}, msg_part="Foto inválida")

    def test_so_miniatura_sem_a_foto_recusado(self):
        self.assertApiError(400, S.save_photo, {"thumb": b64(helpers.jpeg())})
        self.assertEqual(sorted(os.listdir(S.PHOTOS_DIR)), sorted(os.listdir(os.path.join(helpers.FIXTURE, "photos"))), "nada é gravado")

    def test_nome_com_a_data_e_a_hora(self):
        with dia_fixo(datetime(2026, 3, 4, 5, 6, 7)):
            f = S.save_photo({"full": b64(helpers.jpeg())})["file"]
        self.assertRegex(f, r"^20260304-050607-[0-9a-f]{6}\.jpg$")

    def test_nomes_diferentes_no_mesmo_segundo(self):
        jpg = b64(helpers.jpeg())
        with dia_fixo(datetime(2026, 3, 4, 5, 6, 7)):
            nomes = {S.save_photo({"full": jpg})["file"] for _ in range(20)}
        self.assertEqual(len(nomes), 20, "uma foto não sobrescreve a outra")

    def test_nao_deixa_temporarios(self):
        S.save_photo({"full": b64(helpers.jpeg()), "thumb": b64(helpers.jpeg())})
        for d in (S.PHOTOS_DIR, S.THUMBS_DIR):
            self.assertEqual([n for n in os.listdir(d) if n.endswith(".tmp")], [], d)

    def test_foto_enviada_ja_pode_ir_para_um_item(self):
        f = S.save_photo({"full": b64(helpers.jpeg())})["file"]
        it = self.store.create_items([{"room": "sala", "name": "Quadro", "photos": [f]}], None)[0]
        self.assertEqual(it["photos"], [f])


class FotoExiste(UnitBase):
    def test_png_webp_e_jpeg_valem(self):
        for nome in ("da-internet.png", "da-internet.webp", "camera.jpeg"):
            helpers.write_file(os.path.join(S.PHOTOS_DIR, nome), helpers.jpeg())
            with self.subTest(nome=nome):
                self.assertTrue(S.photo_exists(nome))

    def test_so_a_miniatura_nao_conta(self):
        helpers.write_file(os.path.join(S.THUMBS_DIR, "so-mini.jpg"), helpers.jpeg())
        self.assertFalse(S.photo_exists("so-mini.jpg"))

    def test_pasta_com_nome_de_foto_nao_conta(self):
        os.makedirs(os.path.join(S.PHOTOS_DIR, "pasta.jpg"))
        self.assertFalse(S.photo_exists("pasta.jpg"))

    def test_nome_longo_demais_nao_conta(self):
        ok, longo = "a" * 151 + ".jpg", "a" * 152 + ".jpg"
        for nome in (ok, longo):
            helpers.write_file(os.path.join(S.PHOTOS_DIR, nome), helpers.jpeg())
        self.assertTrue(S.photo_exists(ok))
        self.assertFalse(S.photo_exists(longo))


class LimparFotos(UnitBase):
    def fotos(self, n):
        nomes = [f"foto-{k:02d}.jpg" for k in range(n)]
        for nome in nomes:
            helpers.write_file(os.path.join(S.PHOTOS_DIR, nome), helpers.jpeg())
        return nomes

    def test_doze_fotos_passam(self):
        nomes = self.fotos(12)
        self.assertEqual(S.clean_photos(nomes), nomes)

    def test_repetidas_nao_contam_no_limite(self):
        nomes = self.fotos(12)
        self.assertEqual(S.clean_photos(nomes + [nomes[0], nomes[5]]), nomes)

    def test_ordem_e_mantida(self):
        self.assertEqual(S.clean_photos(["sala-3.jpg", "sala-1.jpg", "sala-2.jpg"]), ["sala-3.jpg", "sala-1.jpg", "sala-2.jpg"], "a primeira é a capa do item")

    def test_lista_vazia(self):
        self.assertEqual(S.clean_photos([]), [])

    def test_caminho_para_foto_que_existe_recusado(self):
        for nome in ("../photos/sala-1.jpg", "photos/sala-1.jpg", "./sala-1.jpg", "sala-1.jpg/", " sala-1.jpg"):
            with self.subTest(nome=nome):
                self.assertApiError(400, S.clean_photos, [nome])

    def test_uma_ruim_recusa_a_lista_inteira(self):
        self.assertApiError(400, S.clean_photos, ["sala-1.jpg", "sumiu.jpg", "sala-2.jpg"], msg_part="Envie a foto de novo")


class OrigemDasFotos(UnitBase):
    def test_http_tambem_vale(self):
        self.assertEqual(S.clean_photo_src({"a.jpg": "http://loja.exemplo/p"}, ["a.jpg"]), {"a.jpg": "http://loja.exemplo/p"})

    def test_endereco_de_ate_1000_caracteres(self):
        base = "https://loja.exemplo/"
        ok, longo = base + "p" * (1000 - len(base)), base + "p" * (1001 - len(base))
        self.assertEqual(S.clean_photo_src({"a.jpg": ok, "b.jpg": longo}, ["a.jpg", "b.jpg"]), {"a.jpg": ok})

    def test_item_sem_fotos_fica_sem_origem(self):
        self.assertEqual(S.clean_photo_src({"a.jpg": "https://loja.exemplo/p"}, []), {})


class ServirFotos(UnitBase):
    def test_foto_grande_com_cache_longo(self):
        st, h, corpo = Pedido().servir("/photos/sala-1.jpg")
        self.assertEqual((st, h["Content-Type"]), (200, "image/jpeg"))
        self.assertEqual(h["Cache-Control"], "private, max-age=31536000, immutable", "o nome muda a cada foto nova: pode guardar para sempre")
        self.assertEqual(corpo, helpers.fixture_photo("sala-1.jpg"))
        self.assertEqual((h["Content-Length"], h["X-Content-Type-Options"]), (str(len(corpo)), "nosniff"))

    def test_miniatura_e_a_menor(self):
        st, _, corpo = Pedido().servir("/thumbs/sala-1.jpg")
        self.assertEqual(st, 200)
        self.assertEqual(corpo, ler(os.path.join(helpers.FIXTURE, "thumbs", "sala-1.jpg")))
        self.assertLess(len(corpo), len(helpers.fixture_photo("sala-1.jpg")))

    def test_foto_no_lugar_da_miniatura_sem_cache(self):
        helpers.write_file(os.path.join(S.PHOTOS_DIR, "so-grande.jpg"), helpers.jpeg())
        st, h, corpo = Pedido().servir("/thumbs/so-grande.jpg")
        self.assertEqual((st, h["Cache-Control"], corpo), (200, "no-cache", helpers.jpeg()), "quando a miniatura chegar, a tela pega a certa")

    def test_foto_que_nao_existe_404(self):
        for path in ("/photos/nao-existe.jpg", "/thumbs/nao-existe.jpg"):
            with self.subTest(path=path):
                self.assertApiError(404, Pedido().servir, path, msg_part="Foto não encontrada")

    def test_nome_perigoso_404_mesmo_se_o_arquivo_existe(self):
        helpers.write_file(os.path.join(S.PHOTOS_DIR, ".oculta.jpg"), helpers.jpeg())
        helpers.write_file(os.path.join(S.PHOTOS_DIR, "anim.gif"), b"GIF89a")
        for path in ("/photos/..", "/photos/.oculta.jpg", "/photos/anim.gif", "/photos/sala-1.jpg\x00", "/thumbs/a b.jpg"):
            with self.subTest(path=path):
                self.assertApiError(404, Pedido().servir, path)

    def test_tipo_pela_extensao(self):
        for nome, tipo in (("x.webp", "image/webp"), ("x.png", "image/png"), ("x.jpeg", "image/jpeg")):
            helpers.write_file(os.path.join(S.PHOTOS_DIR, nome), b"conteudo")
            with self.subTest(nome=nome):
                self.assertEqual(Pedido().servir(f"/photos/{nome}")[1]["Content-Type"], tipo)

    def test_head_nao_manda_o_corpo(self):
        st, h, corpo = Pedido("HEAD").servir("/photos/sala-1.jpg")
        self.assertEqual((st, corpo), (200, b""))
        self.assertEqual(h["Content-Length"], str(len(helpers.fixture_photo("sala-1.jpg"))), "o tamanho é o da foto")

    def test_foto_enviada_agora_ja_e_servida(self):
        jpg = helpers.fixture_photo("varanda-1.jpg")
        f = S.save_photo({"full": b64(jpg)})["file"]
        self.assertEqual(Pedido().servir(f"/photos/{f}")[2], jpg)
        self.assertEqual(Pedido().servir(f"/thumbs/{f}")[2], jpg, "sem miniatura, a miniatura é a própria foto")


if __name__ == "__main__":
    unittest.main()
