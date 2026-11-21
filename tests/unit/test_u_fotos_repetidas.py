"""1.84.0: a busca de fotos na internet não mostra a mesma foto duas vezes (os mesmos bytes, a mesma foto em outro tamanho
ou com outro endereço no mesmo site), e a de um consumível não pede nem traz valor, com as categorias dele."""
import unittest

from _boot import UnitBase, server as S


def foto(url, size, body, sha=None):
    return {"sha": sha or S.hashlib.sha1(body).hexdigest(), "key": S.img_key(url), "size": size, "kind": "jpeg", "image": url, "page": "", "body": body}


class FotosRepetidas(UnitBase):
    def test_a_chave_tira_as_marcas_de_tamanho(self):
        iguais = ["https://www.loja.test/image/cache/catalog/creme-maos-500x500.jpg", "https://loja.test/image/cache/catalog/creme-maos-1000x1000.jpg",
                  "https://loja.test/img/creme-maos_thumb.png?w=300", "https://loja.test/img/creme-maos-large.webp", "https://loja.test/creme-maos@2x.jpg"]
        self.assertEqual({S.img_key(u) for u in iguais}, {"loja.test/creme-maos"})
        self.assertNotEqual(S.img_key("https://loja.test/img/creme-maos.jpg"), S.img_key("https://loja.test/img/creme-rosto.jpg"))
        self.assertNotEqual(S.img_key("https://loja.test/img/creme-maos.jpg"), S.img_key("https://outra.test/img/creme-maos.jpg"), "outro site, outra chave")
        self.assertEqual(S.img_key("https://loja.test/500x500.jpg"), "loja.test//500x500.jpg", "só o tamanho no nome: o caminho inteiro")

    def test_fica_uma_de_cada_e_a_maior(self):
        a = foto("https://loja.test/c/creme-500x500.jpg", (500, 500), b"a" * 1000)
        b = foto("https://loja.test/c/creme-1000x1000.jpg", (1000, 1000), b"b" * 4000)
        c = foto("https://loja.test/c/creme.jpg", (500, 500), b"a" * 1000)  # os mesmos bytes
        d = foto("https://outra.test/x/pote.jpg", (800, 600), b"d" * 3000)
        f = foto("https://outra.test/y/tampa.jpg", (800, 600), b"f" * 9000)  # outra foto do mesmo tamanho
        g = foto("https://loja.test/c/creme-300x600.jpg", (300, 600), b"g" * 700)  # a mesma chave, outra proporção: outra foto
        out = S.web_dedupe([a, b, c, d, f, g])
        self.assertEqual([o["image"] for o in out], [b["image"], d["image"], f["image"], g["image"]])
        self.assertEqual(S.web_dedupe([]), [])
        sem = [foto("https://loja.test/c/creme-500x500.jpg", None, b"1"), foto("https://loja.test/c/creme-900x900.jpg", None, b"22")]
        self.assertEqual(len(S.web_dedupe(sem)), 1, "sem o tamanho lido, vale a chave")

    def test_o_consumivel_sem_valor_e_com_as_categorias_dele(self):
        p = S.web_prompt("Creme de mãos", "", cons=True)
        self.assertNotIn("valor", p)
        self.assertNotIn("OLX", p)
        self.assertIn("c-limpeza (Limpeza)", p)
        self.assertIn("para que serve", p)
        casa = S.web_prompt("Smart TV", "")
        self.assertIn('"valor": 0', casa)
        self.assertIn("OLX", casa)
        self.assertNotIn("c-limpeza", casa)
        dado = {"produto": {"nome": "Creme de mãos", "detalhes": "Hidrata as mãos.", "categoria": "c-higiene-e-cuidados", "valor": 25}}
        cats = S.STORE.cons_cat_map()
        dado["produto"]["categoria"] = next(k for k, v in cats.items() if v == "Higiene e cuidados")
        got = S.web_product(dado, cons=True)
        self.assertEqual((got["value"], cats[got["cat"]]), (0, "Higiene e cuidados"))
        self.assertEqual(S.web_product(dict(dado), cons=False)["cat"], "", "a categoria do consumível não vale num item da casa")
        self.assertEqual(S.web_product({"produto": {"nome": "X", "categoria": "eletronicos", "valor": 10}}, cons=True)["cat"], "")


if __name__ == "__main__":
    unittest.main()
