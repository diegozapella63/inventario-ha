"""Ligação com os outros apps da família (ResolvIA e GerencIA): chave, arquivo em share/inventario e autorização."""
import json
import os
import stat
import unittest

from _boot import UnitBase, server as S


class Conexao(UnitBase):
    def test_chave_criada_uma_vez_e_guardada(self):
        c = S.Conexao()
        k = c.chave()
        self.assertGreaterEqual(len(k), 32)
        self.assertEqual(c.chave(), k)
        self.assertEqual(S.Conexao().chave(), k, "outra instância (o app reiniciado) lê a mesma chave")
        self.assertEqual(stat.S_IMODE(os.stat(c.arq_chave).st_mode), 0o600)

    def test_chave_curta_e_trocada(self):
        with open(os.path.join(S.DATA_DIR, "integracao.key"), "w") as f:
            f.write("curta")
        self.assertGreaterEqual(len(S.Conexao().chave()), 32)

    def test_arquivo_para_os_outros_apps(self):
        c = S.Conexao()
        c.publicar()
        with open(c.arq_share, encoding="utf-8") as f:
            info = json.load(f)
        self.assertEqual((info["app"], info["nome"], info["versao"], info["chave"]), ("inventario", "InventarIA", S.VERSION, c.chave()))
        self.assertEqual(list(info)[:2], ["app", "nome"], "o começo igual ao dos outros apps da família")
        self.assertRegex(info["gravado_em"], r"[+-]\d\d:\d\d$", "a hora com o fuso")
        self.assertTrue(info["url"].startswith("http://") and info["url"].endswith(f":{S.PORT}"))
        self.assertEqual(stat.S_IMODE(os.stat(c.arq_share).st_mode), 0o600, "só o dono lê a chave")
        self.assertFalse(os.path.exists(c.arq_share + ".tmp"))

    def test_endereco_configurado(self):
        os.environ["INV_URL_INTERNA"] = "http://inventaria.local:8099/"
        try:
            self.assertEqual(S.Conexao().endereco(), ("http://inventaria.local:8099", None))
        finally:
            del os.environ["INV_URL_INTERNA"]

    def test_autorizacao(self):
        c = S.Conexao()
        k = c.chave()
        self.assertTrue(c.autorizado({"Authorization": f"Bearer {k}", "X-App": "ResolvIA"}))
        self.assertEqual(c.ultimo["app"], "ResolvIA")
        for ruim in ({}, {"Authorization": k}, {"Authorization": "Bearer errada"}, {"Authorization": f"Basic {k}"}, {"Authorization": f"Bearer {k}x"}):
            with self.subTest(ruim=ruim):
                self.assertFalse(c.autorizado(ruim))

    def test_sem_pasta_share_nao_quebra(self):
        c = S.Conexao()
        c.arq_share = "/nao/existe/integracao.json"
        c.publicar()


if __name__ == "__main__":
    unittest.main()
