"""Valor de hoje pelo HTTP (1.46.0): /api/data manda as taxas do GerencIA (share/gerencia/integracao.json) e a opção
(desligada de início); a opção só aceita verdadeiro ou falso; o PDF sai com ela ligada; os outros apps (/api/integracao/itens)
continuam recebendo o valor gravado. Itens e valores inventados."""
import json
import os
import tempfile
import unittest

from _boot import AppServer


class ValorDeHoje(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pasta = tempfile.mkdtemp(prefix="inv-ger-")
        cls.arq = os.path.join(pasta, "integracao.json")
        with open(cls.arq, "w", encoding="utf-8") as f:
            json.dump({"app": "gerencia", "nome": "GerencIA", "depreciacao": {"eletronicos": 20, "outros": 10}}, f)
        cls.app = AppServer(env={"INV_GERENCIA": cls.arq})

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def test_as_taxas_e_a_opcao(self):
        d = self.app.data()
        self.assertEqual(d["gerencia"], {"taxas": {"eletronicos": 20.0, "outros": 10.0}})
        self.assertIs(d["settings"]["deprec"], False, "desligada de início")
        self.assertEqual(self.app.put("api/settings", {"deprec": "sim"})[0], 400)
        self.app.ok("PUT", "api/settings", {"deprec": True})
        try:
            self.assertIs(self.app.data()["settings"]["deprec"], True)
            st, _, body = self.app.get("api/relatorio.pdf?fotos=0")
            self.assertEqual((st, body[:5]), (200, b"%PDF-"))
        finally:
            self.app.ok("PUT", "api/settings", {"deprec": False})

    def test_os_outros_apps_recebem_o_valor_gravado(self):
        self.app.ok("PUT", "api/settings", {"deprec": True})
        self.addCleanup(self.app.ok, "PUT", "api/settings", {"deprec": False})
        with open(self.app.path("share", "integracao.json"), encoding="utf-8") as f:
            info = json.load(f)
        itens = self.app.ok("GET", "api/integracao/itens", headers={"Authorization": f"Bearer {info['chave']}"})["itens"]
        gravados = {i["id"]: float(i.get("value") or 0) for i in self.app.data()["items"]}
        self.assertTrue(itens and all(abs(float(i["valor"] or 0) - gravados[i["id"]]) < 0.01 for i in itens), "o GerencIA deprecia sozinho")

    def test_sem_o_gerencia(self):
        app = AppServer(env={"INV_GERENCIA": self.arq + ".nada"})
        self.addCleanup(app.stop)
        self.assertIsNone(app.data()["gerencia"])
