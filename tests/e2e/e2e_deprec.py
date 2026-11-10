"""Mais > Configurações > Integrações > GerencIA > Valor de hoje (1.46.0): o cartão só aparece quando o GerencIA publica a
depreciação (share/gerencia/integracao.json), vem antes do CorrerIA e começa desligado. Ligado, o patrimônio vira o de hoje
(Patrimônio hoje), com a perda por ano de cada categoria, composta, desde a data do valor; a ficha mostra o valor gravado,
a data e a taxa; o relatório diz "valor de hoje"; o valor gravado não muda. Desligado, tudo volta. Casa e taxas inventadas."""
import json
import os
from datetime import date

import e2e_lib
from e2e_lib import OVERFLOW, TMP, main

e2e_lib.SIZES.setdefault("cel390", (390, 844, True))
TAXAS = {"eletronicos": 20, "moveis": 10, "imoveis": -3, "outros": 10}


def hoje_de(it, hoje):
    v = float(it.get("value") or 0)
    d0 = date.fromisoformat(str(it.get("valueAt") or it.get("createdAt") or "")[:10])
    return v * (1 - TAXAS.get(it.get("cat") or "outros", 10) / 100) ** (max(0, (hoje - d0).days) / 365.25)


def num(txt):
    return int("".join(ch for ch in txt if ch.isdigit()) or 0)


async def body(r, p):
    arq = os.path.join(TMP, "gerencia-deprec.json")
    with open(arq, "w", encoding="utf-8") as f:
        json.dump({"app": "gerencia", "nome": "GerencIA", "depreciacao": TAXAS}, f)
    r.start(search=False, env={"INV_GERENCIA": arq})
    # um item eletrônico com o valor de dois anos atrás
    d = r.data()
    tv = next(i for i in d["items"] if float(i.get("value") or 0) > 0)
    r.api("PUT", f"api/items/{tv['id']}", {"cat": "eletronicos", "_base": tv["updatedAt"]})
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel390", "dark")
    await r.open(pg, "#/")
    gravado = num(await pg.locator(".tag-value").text_content())
    r.eq((await pg.locator(".tag-label").text_content()).strip(), "Patrimônio", "desligado: o patrimônio gravado")
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    ids = await pg.evaluate("[...document.querySelectorAll('#view section.panel')].map(s => s.id)")
    r.check(ids[:2] == ["p-gerencia", "p-correria"], f"o GerencIA primeiro, antes do CorrerIA ({ids[:3]})")
    sw = pg.get_by_role("switch", name="Valor de hoje")
    r.check(not await sw.is_checked(), "desligado de início")
    await pg.locator("#p-gerencia").screenshot(path=r.shot_path("cartao"))
    await pg.click('label.switch:has([data-input="deprec-on"])')
    await pg.locator(".toast", has_text="Valor de hoje ligado").wait_for(timeout=8000)
    r.check(r.data()["settings"]["deprec"] is True, "ligado fica gravado")
    r.eq(" ".join((await pg.locator("#p-gerencia .ot span").text_content()).split()), "Ligado: os valores perdem, por ano, a taxa de cada categoria do GerencIA.",
         "ligado: diz o que faz")
    # o patrimônio de hoje: a conta do GerencIA
    hoje = date.today()
    d = r.data()
    esperado = round(sum(hoje_de(i, hoje) for i in d["items"]))
    await r.open(pg, "#/")
    r.eq((await pg.locator(".tag-label").text_content()).strip(), "Patrimônio hoje", "ligado: Patrimônio hoje")
    agora = num(await pg.locator(".tag-value").text_content())
    r.check(abs(agora - esperado) <= 1 and agora < gravado, f"o patrimônio de hoje, com a depreciação ({gravado} → {agora}, esperava {esperado})")
    await r.shot(pg, "inicio")
    # a ficha: o valor de hoje, e embaixo o gravado, a data e a taxa
    tv = next(i for i in d["items"] if i["id"] == tv["id"])
    await r.open(pg, f"#/i/{tv['id']}", ".ihead")
    linha = " ".join((await pg.locator('[data-slot="valor-gravado"]').text_content()).split())
    dia = date.fromisoformat(str(tv.get("valueAt") or tv.get("createdAt"))[:10])
    r.check(linha.endswith(f"em {dia:%d/%m/%Y}, −20% ao ano") and linha.startswith("R$"), f"a ficha: o gravado, a data e a taxa ({linha})")
    big = num(await pg.locator(".ival .big").text_content())
    r.check(abs(big / 100 - hoje_de(tv, hoje)) < 0.02 or (hoje - dia).days == 0, f"o valor de hoje do item ({big / 100})")
    await r.shot(pg, "ficha")
    # o relatório diz
    await r.open(pg, "#/relatorio", ".rhead, .report")
    r.check("valor de hoje" in await pg.locator(".rmeta").first.text_content(), "o relatório: valor de hoje")
    r.check(await pg.evaluate(OVERFLOW), "nada passa da largura")
    # o valor gravado não mudou
    r.eq(float(next(i for i in r.data()["items"] if i["id"] == tv["id"])["value"]), float(tv["value"]), "o valor gravado continua o mesmo")
    # desligar volta
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    await pg.click('label.switch:has([data-input="deprec-on"])')
    await pg.locator(".toast", has_text="Valor de hoje desligado").wait_for(timeout=8000)
    await r.open(pg, "#/")
    r.eq(num(await pg.locator(".tag-value").text_content()), gravado, "desligado: o patrimônio gravado de volta")
    await b.close()


if __name__ == "__main__":
    main("e2e_deprec", body)
