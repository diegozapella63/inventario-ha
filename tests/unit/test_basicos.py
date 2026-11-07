"""Valores, textos, nomes e categorias: as conferências que todo o resto usa."""
import base64
import json
import os
import unittest

from _boot import UnitBase, helpers, server as S


class Valores(UnitBase):
    def test_numeros_e_formatos_brasileiros(self):
        casos = {None: 0, "": 0, 0: 0, 12: 12, 12.5: 12.5, "1200": 1200, "1.200": 1200, "1.200,50": 1200.5, "R$ 1.200,50": 1200.5,
                 "R$2.000": 2000, " 300 ": 300, "0,99": 0.99, "1.234.567,89": 1234567.89, "12,345": 12.35, 99.999: 100, "3.5": 3.5}
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(S.parse_value(entrada), esperado)

    def test_inteiro_quando_nao_tem_centavos(self):
        self.assertIsInstance(S.parse_value("1.200,00"), int)
        self.assertIsInstance(S.parse_value(10.0), int)

    def test_recusa_o_que_nao_e_valor(self):
        for ruim in ("abc", "1,2,3", True, False, "-5", -1, float("nan"), "1e10", 2e9, [1], {"v": 1}):
            with self.subTest(ruim=ruim):
                self.assertApiError(400, S.parse_value, ruim)

    def test_texto_com_limite_e_obrigatorio(self):
        self.assertEqual(S.text("  oi  ", 10, "nome"), "oi")
        self.assertEqual(S.text(None, 10, "nome"), "")
        self.assertEqual(S.text(123, 10, "nome"), "123")
        e = self.assertApiError(400, S.text, "x" * 11, 10, "nome")
        self.assertIn("10 caracteres", e.msg)
        e = self.assertApiError(400, S.text, "   ", 10, "nome", required=True)
        self.assertIn("Preencha o campo nome", e.msg)

    def test_slug_e_fold(self):
        self.assertEqual(S.slug("Sala de Estar"), "sala-de-estar")
        self.assertEqual(S.slug("Escritório & Cia."), "escritorio-cia")
        self.assertEqual(S.slug("???"), "comodo")
        self.assertEqual(len(S.slug("a" * 90)), 40)
        self.assertEqual(S.fold("  Ação ÉLÉTRICA "), "acao eletrica")

    def test_json_atomico_sem_arquivo_pela_metade(self):
        p = os.path.join(S.DATA_DIR, "sub", "x.json")
        S.write_json_atomic(p, {"a": "ç", "n": [1, 2]})
        self.assertEqual(S.read_json(p), {"a": "ç", "n": [1, 2]})
        self.assertEqual([n for n in os.listdir(os.path.dirname(p)) if n.startswith(".tmp-")], [])
        with self.assertRaises(TypeError):
            S.write_json_atomic(p, {"x": object()})
        self.assertEqual(S.read_json(p), {"a": "ç", "n": [1, 2]}, "uma gravação que falha não estraga a anterior")
        self.assertEqual([n for n in os.listdir(os.path.dirname(p)) if n.startswith(".tmp-")], [])
        self.assertEqual(S.read_json(os.path.join(S.DATA_DIR, "nao-existe.json"), {"padrao": 1}), {"padrao": 1})


class Categorias(UnitBase):
    def test_lista_padrao(self):
        cats = S.default_cats()
        self.assertEqual(len(cats), 15)
        self.assertEqual(cats[-1], {"id": "outros", "name": "Outros"})
        self.assertEqual(self.store.cats(), cats, "sem categorias gravadas, vale a lista padrão")

    def test_limpa_categorias_gravadas(self):
        raw = [{"id": "ferramentas", "name": "  Ferramentas   e  oficina "}, {"id": "Com Espaço", "name": "x"}, {"id": "moveis", "name": ""},
               {"id": "ferramentas", "name": "repetida"}, "texto", {"id": "-ruim", "name": "x"}, {"id": "a" * 42, "name": "longo"}]
        out = S.clean_cats(raw)
        self.assertEqual(out, [{"id": "ferramentas", "name": "Ferramentas e oficina"}, {"id": "outros", "name": "Outros"}])
        self.assertIsNone(S.clean_cats([]))
        self.assertIsNone(S.clean_cats("nada"))
        self.assertIsNone(S.clean_cats([{"id": "", "name": ""}]))
        self.assertEqual(S.clean_cats([{"id": "x", "name": "y" * 80}])[0]["name"], "y" * 60)

    def test_criar_renomear_excluir(self):
        rev = self.store.data["rev"]
        c = self.store.create_cat({"name": "  Ferramentas  "})
        self.assertEqual(c, {"id": "ferramentas", "name": "Ferramentas"})
        ids = [x["id"] for x in self.store.cats()]
        self.assertEqual(ids[-2:], ["ferramentas", "outros"], "a nova entra antes de Outros")
        self.assertGreater(self.store.data["rev"], rev)
        self.assertEqual(self.store.create_cat({"name": "Áudio & Vídeo!"})["id"], "audio-video")
        self.assertEqual(self.store.create_cat({"name": "Áudio/Vídeo"})["id"], "audio-video-2", "id repetido ganha um número")
        self.assertEqual(self.store.create_cat({"name": "★"})["id"], "categoria")
        self.assertApiError(400, self.store.create_cat, {"name": "ferramentas"}, msg_part="Já existe")
        self.assertApiError(400, self.store.create_cat, {"name": "MÓVEIS"}, msg_part="Já existe")
        self.assertApiError(400, self.store.create_cat, {"name": "  "})
        self.assertApiError(400, self.store.create_cat, {"name": "x" * 61})
        self.assertEqual(self.store.update_cat("ferramentas", {"name": "Oficina"})["name"], "Oficina")
        self.assertEqual(self.store.update_cat("ferramentas", {"name": "oficina"})["name"], "oficina", "pode mudar só as maiúsculas")
        self.assertApiError(400, self.store.update_cat, "ferramentas", {"name": "Móveis"})
        self.assertApiError(404, self.store.update_cat, "nao-existe", {"name": "X"})
        self.assertEqual(self.store.update_cat("outros", {"name": "Diversos"})["name"], "Diversos")
        self.assertEqual(self.store.cat_map()["outros"], "Diversos")

    def test_excluir_leva_os_itens_para_outros(self):
        self.store.create_cat({"name": "Oficina"})
        alvo = self.store.data["items"][:3]
        for it in alvo:
            self.store.update_item(it["id"], {"cat": "oficina"}, None)
        self.assertEqual(self.store.delete_cat("oficina"), 3)
        self.assertTrue(all(self.item(it["id"])["cat"] == "outros" for it in alvo))
        self.assertNotIn("oficina", self.store.cat_map())
        self.assertApiError(400, self.store.delete_cat, "outros", msg_part="Outros")
        self.assertApiError(404, self.store.delete_cat, "oficina")
        self.assertEqual(self.store.delete_cat("plantas"), 2, "a casa de teste tem 2 plantas")

    def test_item_com_categoria_desconhecida_vai_para_outros(self):
        it = self.store.create_items([{"room": "sala", "name": "Coisa", "cat": "nao-existe"}], None)[0]
        self.assertEqual(it["cat"], "outros")
        self.store.create_cat({"name": "Oficina"})
        it = self.store.update_item(it["id"], {"cat": "oficina"}, None)
        self.assertEqual(it["cat"], "oficina")

    def test_categorias_vao_junto_no_inventario(self):
        self.store.create_cat({"name": "Oficina"})
        salvo = S.read_json(S.DATA_FILE)
        self.assertIn({"id": "oficina", "name": "Oficina"}, salvo["cats"])
        self.assertIn("cats", self.store.public())
        sem = S.Store.check_inventory({"rooms": [], "items": [], "cats": "ruim"})
        self.assertNotIn("cats", sem)
        com = S.Store.check_inventory({"rooms": [], "items": [], "cats": [{"id": "x", "name": "X"}]})
        self.assertEqual([c["id"] for c in com["cats"]], ["x", "outros"])


class Fotos(UnitBase):
    def _b64(self, b):
        return base64.b64encode(b).decode()

    def test_salva_foto_e_miniatura(self):
        jpg = helpers.jpeg()
        out = S.save_photo({"full": self._b64(jpg), "thumb": self._b64(jpg[:2] + jpg[2:])})
        self.assertRegex(out["file"], r"^\d{8}-\d{6}-[0-9a-f]{6}\.jpg$")
        self.assertTrue(S.photo_exists(out["file"]))
        self.assertTrue(os.path.isfile(os.path.join(S.THUMBS_DIR, out["file"])))

    def test_sem_miniatura_usa_a_foto(self):
        jpg = helpers.jpeg()
        f = S.save_photo({"full": self._b64(jpg), "thumb": self._b64(b"nao e jpg")})["file"]
        with open(os.path.join(S.THUMBS_DIR, f), "rb") as fh:
            self.assertEqual(fh.read(), jpg)

    def test_recusa_o_que_nao_e_jpg(self):
        self.assertApiError(400, S.save_photo, {"full": "@@@"}, msg_part="inválida")
        self.assertApiError(400, S.save_photo, {"full": self._b64(b"\x89PNG" + b"0" * 200)}, msg_part="JPG")
        self.assertApiError(400, S.save_photo, {"full": self._b64(b"\xff\xd8" + b"0" * 10)})
        self.assertApiError(400, S.save_photo, {})

    def test_nomes_de_foto_seguros(self):
        self.assertTrue(S.photo_exists("sala-1.jpg"))
        for ruim in ("../inventario.json", "/etc/passwd", "sala-1.jpg/..", ".oculta.jpg", "a b.jpg", "x.gif", "", None):
            with self.subTest(ruim=ruim):
                self.assertFalse(S.photo_exists(ruim))

    def test_lista_de_fotos_do_item(self):
        self.assertEqual(S.clean_photos(None), [])
        self.assertEqual(S.clean_photos(["sala-1.jpg", "sala-1.jpg", "sala-2.jpg"]), ["sala-1.jpg", "sala-2.jpg"])
        self.assertApiError(400, S.clean_photos, "sala-1.jpg")
        self.assertApiError(400, S.clean_photos, ["nao-existe.jpg"], msg_part="não foi encontrada")
        self.assertApiError(400, S.clean_photos, [1])
        jpg = self._b64(helpers.jpeg())
        muitas = [S.save_photo({"full": jpg})["file"] for _ in range(13)]
        self.assertApiError(400, S.clean_photos, muitas, msg_part="12 fotos")

    def test_origem_das_fotos_da_internet(self):
        src = S.clean_photo_src({"a.jpg": "https://loja.exemplo/p", "b.jpg": "ftp://x", "c.jpg": "https://x", "d.jpg": 5,
                                 "e.jpg": "https://" + "x" * 1000}, ["a.jpg", "b.jpg", "d.jpg", "e.jpg"])
        self.assertEqual(src, {"a.jpg": "https://loja.exemplo/p"})
        self.assertEqual(S.clean_photo_src("nada", ["a.jpg"]), {})


class Carga(UnitBase):
    def test_primeira_vez_copia_a_casa_inicial(self):
        d = self.store.data
        self.assertEqual((len(d["rooms"]), len(d["items"])), (6, 38))
        self.assertTrue(os.path.isfile(os.path.join(S.PHOTOS_DIR, "sala-1.jpg")))
        self.assertTrue(os.path.isfile(os.path.join(S.THUMBS_DIR, "sala-1.jpg")))
        self.assertEqual(d["format"], "inventario-casa")

    def test_sem_casa_inicial_comeca_vazio(self):
        import shutil
        from unittest import mock
        shutil.rmtree(S.DATA_DIR)
        with mock.patch.object(S, "SEED_DIR", os.path.join(S.DATA_DIR, "nada")):
            st = S.Store()
            st.load()
        self.assertEqual((st.data["rooms"], st.data["items"]), ([], []))
        self.assertFalse(st.has_data())

    def test_arquivo_antigo_ganha_os_campos_que_faltam(self):
        S.write_json_atomic(S.DATA_FILE, {"rooms": [], "items": []})
        st = S.Store()
        st.load()
        self.assertEqual((st.data["format"], st.data["schema"], st.data["rev"]), ("inventario-casa", 1, 1))

    def test_configuracoes_ficam_no_arquivo(self):
        self.store.settings["zones"] = True
        self.store.save_settings()
        st = S.Store()
        st.load()
        self.assertTrue(st.settings["zones"])
        with open(S.SETTINGS_FILE, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["zones"], True)


if __name__ == "__main__":
    unittest.main()
