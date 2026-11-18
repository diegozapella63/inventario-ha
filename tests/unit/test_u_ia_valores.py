"""Os valores que a IA recebe (a Conversar e as ferramentas do CorrerIA) são os da tela, com cada opção (1.75.0).

Depois que a Conversar somou valores diferentes dos da tela, este arquivo confere o valor de cada item, o total da casa,
o de cada cômodo e categoria, os Bens à parte e o patrimônio, com:
- Valor de hoje (Mais › Configurações › Integrações › GerencIA) desligado: o valor gravado;
- ligado, com a depreciação do GerencIA: o valor de hoje, pela conta da tela (o valorHoje do app.js, escrita de novo
  aqui, a mesma do e2e_deprec.py, que confere a tela), também para uma categoria que valoriza (taxa negativa);
- ligado, mas sem o arquivo do GerencIA: o gravado, como a tela;
- Usar bens desligado: os bens somem de tudo (a tela esconde), sem apagar.
A data fica fixa (04/11/2026). A casa de teste é inventada."""
import json
import os
import tempfile
from datetime import date
from unittest import mock

from _boot import UnitBase, server as S

import ferramentas as F

HOJE = date(2026, 11, 4)
TAXAS = {"eletronicos": 20, "moveis": 10, "veiculos": 15, "imoveis": -3}
ANA = {"id": "person.ana", "nome": "Ana"}


class Dia(date):
    @classmethod
    def today(cls):
        return HOJE


def conta_da_tela(it, ligado=True):
    """O valorHoje do app.js: o valor perde a taxa da categoria (10 sem ela) por ano, composta, desde a data do valor."""
    v = float(it.get("value") or 0)
    try:
        d0 = date.fromisoformat(str(it.get("valueAt") or it.get("createdAt") or "")[:10])
    except ValueError:
        return v
    if not v or not ligado:
        return v
    return v * (1 - TAXAS.get(it.get("cat") or "outros", 10) / 100) ** (max(0, (HOJE - d0).days) / 365.25)


class Valores(UnitBase):
    def setUp(self):
        super().setUp()
        for p in (mock.patch.object(S, "date", Dia),):
            p.start()
            self.addCleanup(p.stop)
        self.arq = os.path.join(tempfile.mkdtemp(prefix="inv-ger-"), "integracao.json")
        with open(self.arq, "w", encoding="utf-8") as f:
            json.dump({"app": "gerencia", "depreciacao": TAXAS}, f)
        p = mock.patch.object(S, "GERENCIA_ARQ", self.arq)
        p.start()
        self.addCleanup(p.stop)
        S._ger.update(mtime=None, taxas=None)
        self.addCleanup(lambda: S._ger.update(mtime=None, taxas=None))
        self.addCleanup(lambda: [self.store.settings.pop(k, None) for k in ("deprec", "bens")])
        area = self.store.create_room({"kind": "bens"})
        self.store.create_items([
            {"room": area["id"], "name": "Carro hatch", "cat": "veiculos", "value": 60000},
            {"room": area["id"], "name": "Apartamento da praia", "cat": "imoveis", "value": 400000},
        ], None)
        # as datas dos valores: o carro há dois anos, o apartamento há três (valoriza)
        for it in self.store.data["items"]:
            if it["name"] == "Carro hatch":
                it["valueAt"] = "2024-11-04"
            elif it["name"] == "Apartamento da praia":
                it["valueAt"] = "2023-11-04T10:00:00-03:00"
        self.area = area["id"]

    def opcoes(self, deprec=False, bens=True):
        self.store.settings["deprec"] = deprec
        self.store.settings["bens"] = bens
        S._ger.update(mtime=None, taxas=None)

    def ferr(self, nome, args=None):
        return json.loads(F.chamar(S, nome, args or {}, ANA, "Claude"))

    def casa(self):
        return [i for i in self.store.data["items"] if i["room"] != self.area]

    def bens(self):
        return [i for i in self.store.data["items"] if i["room"] == self.area]

    def total(self, its, ligado):
        return sum(conta_da_tela(i, ligado) for i in its)

    # ---- cada combinação de opções: a Conversar e o resumo do CorrerIA com os números da tela
    def conferir(self, deprec, bens):
        self.opcoes(deprec, bens)
        ligado = deprec
        casa, area = self.casa(), self.bens() if bens else []
        c = S.chat_context({})
        rooms = sorted((r for r in self.store.data["rooms"] if r.get("kind") != "bens"), key=lambda r: r.get("order", 0))
        self.assertIn(f"Inventário da casa: {len(casa)} itens em {len(rooms)} cômodos, total {S._money(self.total(casa, ligado))}.", c)
        for r in rooms:
            its = [i for i in casa if i["room"] == r["id"]]
            self.assertIn(f"{r['code']} {r['name']}: {len(its)} itens, {S._money(self.total(its, ligado))}", c, r["name"])
        if bens:
            self.assertIn(f"Bens (o que fica fora de casa, como imóveis e veículos; não é um cômodo): 2 itens, {S._money(self.total(area, ligado))}.", c)
            self.assertIn(f"Com eles, o patrimônio é {S._money(self.total(casa, ligado) + self.total(area, ligado))}.", c)
        else:
            self.assertNotIn("Bens (", c)
            self.assertNotIn("Carro hatch", c)
            self.assertNotIn("Apartamento", c)
        self.assertEqual("Os valores são os de hoje, como na tela" in c, ligado)
        r = self.ferr("resumo")
        self.assertAlmostEqual(r["total"], self.total(casa + area, ligado), delta=0.01)
        self.assertEqual(r["itens"], len(casa) + len(area))
        for x in r["comodos"]:
            self.assertAlmostEqual(x["valor"], self.total([i for i in casa if i["room"] == x["id"]], ligado), delta=0.01, msg=x["nome"])
        for k in r["categorias"]:
            its = [i for i in casa + area if (i.get("cat") if i.get("cat") in self.store.cat_map() else "outros") == k["id"]]
            self.assertAlmostEqual(k["valor"], self.total(its, ligado), delta=0.01, msg=k["nome"])
        if bens:
            self.assertAlmostEqual(r["bens"]["valor"], self.total(area, ligado), delta=0.01)
            self.assertAlmostEqual(r["dentro_de_casa"], self.total(casa, ligado), delta=0.01)
            self.assertEqual(r["bens"]["por_tipo"], {"Veículos": round(conta_da_tela(area[0], ligado), 2), "Imóveis": round(conta_da_tela(area[1], ligado), 2)})
        else:
            self.assertNotIn("bens", r)
            self.assertNotIn("dentro_de_casa", r)
        self.assertEqual(r["opcoes"]["bens"], bens)
        return c, r

    def test_desligado_o_valor_gravado(self):
        c, r = self.conferir(deprec=False, bens=True)
        self.assertNotIn("valor_gravado", r["mais_valiosos"][0])
        self.assertEqual(r["mais_valiosos"][0]["valor"], 400000, "o apartamento, pelo gravado")

    def test_valor_de_hoje_ligado(self):
        c, r = self.conferir(deprec=True, bens=True)
        top = r["mais_valiosos"][0]
        self.assertEqual(top["nome"], "Apartamento da praia")
        self.assertEqual((top["valor"], top["valor_gravado"]), (round(400000 * 1.03 ** (1096 / 365.25), 2), 400000))
        self.assertGreater(top["valor"], top["valor_gravado"], "uma taxa negativa valoriza")
        carro = next(i for i in r["mais_valiosos"] if i["nome"] == "Carro hatch")
        self.assertEqual(carro["valor"], round(60000 * 0.85 ** (730 / 365.25), 2), "o carro perde 15% ao ano há dois anos")

    def test_usar_bens_desligado(self):
        self.conferir(deprec=False, bens=False)
        self.conferir(deprec=True, bens=False)
        b = self.ferr("buscar_itens", {"texto": "carro"})
        self.assertEqual((b["encontrados"], b["valor_total"]), (0, 0))

    def test_ligado_sem_o_gerencia_fica_o_gravado(self):
        os.remove(self.arq)
        self.opcoes(deprec=True, bens=True)
        self.assertFalse(S.deprec_enabled())
        c = S.chat_context({})
        self.assertNotIn("valores são os de hoje", c)
        self.assertIn(f"total {S._money(sum(float(i.get('value') or 0) for i in self.casa()))}.", c)
        self.assertNotIn("valores", self.ferr("resumo"))

    def test_cada_item_e_a_busca(self):
        """O item na tela da ficha, o ver_item e a busca do CorrerIA, com os filtros: o valor e as somas da tela."""
        self.opcoes(deprec=True, bens=True)
        for it in self.store.data["items"]:
            v = self.ferr("ver_item", {"id": it["id"]})
            self.assertEqual(v["valor"], round(conta_da_tela(it), 2), it["name"])
            self.assertEqual(v["valor_gravado"], round(float(it.get("value") or 0), 2))
            self.assertIn(S._money(conta_da_tela(it)), S.chat_context({"view": "item", "item": it["id"]}), it["name"])
        ele = [i for i in self.store.data["items"] if i.get("cat") == "eletronicos"]
        b = self.ferr("buscar_itens", {"categoria": "eletronicos", "limite": 100})
        self.assertEqual(b["encontrados"], len(ele))
        self.assertAlmostEqual(b["valor_total"], self.total(ele, True), delta=0.01)
        self.opcoes(deprec=False, bens=True)
        self.assertNotIn("valor_gravado", self.ferr("ver_item", {"id": ele[0]["id"]}))
        self.assertAlmostEqual(self.ferr("buscar_itens", {"categoria": "eletronicos", "limite": 100})["valor_total"], self.total(ele, False), delta=0.01)

    def test_sem_valor_ou_data_no_futuro(self):
        self.opcoes(deprec=True, bens=True)
        it = self.casa()[0]
        it["value"] = 0
        self.assertEqual(S.item_hoje(it, S.gerencia_taxas()), 0)
        it["value"], it["valueAt"] = 1000, "2027-01-01"
        self.assertEqual(S.item_hoje(it, S.gerencia_taxas()), 1000, "a data do valor no futuro: nada perdido")
        it["valueAt"], it["createdAt"] = "", "sem data"
        self.assertEqual(S.item_hoje(it, S.gerencia_taxas()), 1000)
        self.assertEqual(conta_da_tela(it), 1000)
