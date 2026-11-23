"""A Memória da IA pelo HTTP, com o servidor de verdade: GET e POST /api/memoria-ia leem e escrevem a lista da casa, que fica
na pasta share (share/familia/memoria_ia.json), fora do app, para todos os apps da família."""
import json
import os
import unittest

from _boot import ServerCase


class MemoriaIA(ServerCase):
    def test_guardar_listar_e_apagar(self):
        arq = os.path.join(os.path.dirname(self.app.path("share")), "familia", "memoria_ia.json")
        if os.path.exists(arq):
            os.remove(arq)
        self.assertEqual(self.app.ok("GET", "api/memoria-ia"), {"lista": [], "max": 60})
        r = self.app.ok("POST", "api/memoria-ia", {"acao": "nova", "texto": "  Creme é   sempre Higiene "})
        self.assertEqual([(x["texto"], x["app"]) for x in r["lista"]], [("Creme é sempre Higiene", "InventarIA")])
        self.assertTrue(os.path.exists(arq), "na pasta share, ao lado da pasta do app")
        with open(arq, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["lista"][0]["texto"], "Creme é sempre Higiene")
        st, _, erro = self.app.request("POST", "api/memoria-ia", {"acao": "nova", "texto": " a "})[:3]
        self.assertEqual(st, 400)
        self.assertIn("Escreva o que é para lembrar.", json.dumps(erro, ensure_ascii=False) if not isinstance(erro, (bytes, str)) else (erro.decode() if isinstance(erro, bytes) else erro))
        r = self.app.ok("POST", "api/memoria-ia", {"acao": "apagar", "id": r["lista"][0]["id"]})
        self.assertEqual(r["lista"], [])


if __name__ == "__main__":
    unittest.main()
