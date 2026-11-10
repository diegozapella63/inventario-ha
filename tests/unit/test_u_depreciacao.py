"""Valor de hoje (1.46.0): a depreciação que o GerencIA publica em share/gerencia/integracao.json ("depreciacao": a perda
por ano, em %, de cada categoria). gerencia_taxas lê o arquivo (relê quando ele muda; sem o arquivo ou sem a depreciação,
None); deprec_enabled precisa da opção e do arquivo; valor_hoje é a conta do bens.valor_hoje do GerencIA (composta, desde
a data do valor); item_hoje usa a categoria do item (10% para a que o GerencIA não tem); o relatório em PDF usa o valor de
hoje e diz isso, sem mudar o valor gravado. Valores e itens inventados."""
import json
import os
import tempfile
from datetime import date
from unittest import mock

from _boot import UnitBase, server as S


class Depreciacao(UnitBase):
    def setUp(self):
        super().setUp()
        self.arq = os.path.join(tempfile.mkdtemp(prefix="inv-ger-"), "integracao.json")
        p = mock.patch.object(S, "GERENCIA_ARQ", self.arq)
        p.start()
        self.addCleanup(p.stop)
        S._ger.update(mtime=None, taxas=None)

    def grava(self, corpo, quando=None):
        with open(self.arq, "w", encoding="utf-8") as f:
            json.dump(corpo, f)
        if quando:
            os.utime(self.arq, (quando, quando))

    def test_sem_o_gerencia_nada(self):
        self.assertIsNone(S.gerencia_taxas())
        self.grava({"app": "gerencia", "nome": "GerencIA"})
        self.assertIsNone(S.gerencia_taxas(), "o GerencIA sem a depreciação (Bens da casa desligado lá)")
        with open(self.arq, "w", encoding="utf-8") as f:
            f.write("{quebrado")
        os.utime(self.arq, (1, 1))
        self.assertIsNone(S.gerencia_taxas(), "arquivo quebrado")

    def test_le_as_taxas_e_rele_quando_muda(self):
        self.grava({"depreciacao": {"eletronicos": 20, "imoveis": -3, "moveis": 250, "x": "dez", "y": True}}, quando=1000)
        self.assertEqual(S.gerencia_taxas(), {"eletronicos": 20.0, "imoveis": -3.0, "moveis": 100.0}, "só números, de -50 a 100")
        self.grava({"depreciacao": {"eletronicos": 30}}, quando=2000)
        self.assertEqual(S.gerencia_taxas(), {"eletronicos": 30.0}, "o arquivo mudou: lê de novo")

    def test_a_opcao_e_o_arquivo(self):
        self.assertFalse(S.deprec_enabled())
        self.store.settings["deprec"] = True
        self.assertFalse(S.deprec_enabled(), "ligada, mas sem o GerencIA")
        self.grava({"depreciacao": {"outros": 10}})
        self.assertTrue(S.deprec_enabled())

    def test_a_conta_do_gerencia(self):
        hoje = date(2026, 11, 10)
        self.assertAlmostEqual(S.valor_hoje(1000, "2024-11-10", 20, hoje), 1000 * 0.8 ** (730 / 365.25))
        self.assertAlmostEqual(S.valor_hoje(1000, "2025-11-10T08:30:00-03:00", -3, hoje), 1000 * 1.03 ** (365 / 365.25), "negativa: valoriza")
        self.assertEqual(S.valor_hoje(1000, "2027-01-01", 20, hoje), 1000, "valor do futuro: sem perda")
        self.assertEqual(S.valor_hoje(1000, "", 20, hoje), 1000, "sem data: o valor")

    def test_cada_item_pela_categoria(self):
        tx, hoje = {"eletronicos": 20, "outros": 5}, date(2026, 11, 10)
        tv = {"value": 4000, "cat": "eletronicos", "valueAt": "2025-11-10", "createdAt": "2020-01-01"}
        self.assertAlmostEqual(S.item_hoje(tv, tx, hoje), 4000 * 0.8 ** (365 / 365.25), "a data do valor, não a do cadastro")
        self.assertAlmostEqual(S.item_hoje({"value": 100, "cat": "", "createdAt": "2025-11-10"}, tx, hoje), 100 * 0.95 ** (365 / 365.25), "sem categoria: Outros")
        self.assertAlmostEqual(S.item_hoje({"value": 100, "cat": "minha-cat", "valueAt": "2025-11-10"}, tx, hoje), 100 * 0.9 ** (365 / 365.25),
                               "categoria que o GerencIA não tem: 10%")
        self.assertEqual(S.item_hoje({"value": 0, "cat": "eletronicos"}, tx, hoje), 0.0)

    def test_o_relatorio_com_o_valor_de_hoje(self):
        it = next(i for i in self.store.data["items"] if float(i.get("value") or 0) > 0)
        it["valueAt"] = "2020-01-01"
        gravado = it["value"]
        self.grava({"depreciacao": {it.get("cat") or "outros": 50}})
        self.store.settings["deprec"] = True
        visto = {}
        real = S.relatorio.dados

        def dados(rooms, items, cats, **kw):
            visto.update(kw, valor=next(i for i in items if i["id"] == it["id"])["value"])
            return real(rooms, items, cats, **kw)

        class H:
            def send_bytes(self, status, body, tipo, cab):
                visto["status"] = status
        with mock.patch.object(S.relatorio, "dados", dados):
            S.r_relatorio_pdf(H(), {"fotos": ["0"]})
        self.assertEqual((visto["status"], visto["hoje"]), (200, True))
        self.assertLess(visto["valor"], float(gravado) * 0.1, "perdeu metade por ano, desde 2020")
        self.assertEqual(it["value"], gravado, "o valor gravado não muda")
        self.store.settings["deprec"] = False
        with mock.patch.object(S.relatorio, "dados", dados):
            S.r_relatorio_pdf(H(), {"fotos": ["0"]})
        self.assertEqual((visto["hoje"], visto["valor"]), (False, float(gravado)), "desligada: o valor gravado")

    def test_a_contagem_do_relatorio_diz(self):
        rooms, items = S.visible_data()
        self.assertTrue(S.relatorio.dados(rooms, items, self.store.cat_map(), hoje=True)["contagem"].endswith(" · valor de hoje"))
        self.assertNotIn("valor de hoje", S.relatorio.dados(rooms, items, self.store.cat_map())["contagem"])
