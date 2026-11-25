"""1.102.0 (o dono: "agrupar por vencimento, onde mostra o que está vencendo essa semana, esse mês, mês que vem"): em
Consumíveis, Agrupar por Vencimento põe cada consumível no grupo do Dura até (Esta semana, até o domingo; Este mês; Mês que
vem; Depois; Sem duração), o que acaba primeiro no alto. Sem os Consumíveis por cômodo, o Agrupar por mostra Categoria e
Vencimento. Consumíveis inventados."""
from datetime import date, timedelta

from e2e_lib import OVERFLOW, main


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


def grupo(dias, hoje=None):
    """A mesma regra do venceGrupo do app.js."""
    if not dias:
        return "Sem duração"
    hoje = hoje or date.today()
    d = hoje + timedelta(days=dias)
    if d <= hoje + timedelta(days=(6 - hoje.weekday()) % 7):
        return "Esta semana"
    if (d.year, d.month) == (hoje.year, hoje.month):
        return "Este mês"
    prox = date(hoje.year + (hoje.month == 12), hoje.month % 12 + 1, 1)
    if (d.year, d.month) == (prox.year, prox.month):
        return "Mês que vem"
    return "Depois"


async def body(r, p):
    r.start(search=False)
    r.app.request("PUT", "api/settings", {"consumiveis": True})
    st, _, area = r.app.request("POST", "api/rooms", {"kind": "consumiveis"})
    area = area["room"]
    itens = [("Pilhas AA", 400), ("Detergente", 1), ("Sabão em pó", 20), ("Filtro de café", 45), ("Fita isolante", 0)]
    for nome, dias in itens:
        r.app.request("POST", "api/items", {"room": area["id"], "name": nome, **({"dur": dias} if dias else {})})
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark")
    await r.open(pg, "#/consumiveis", ".irow")
    r.eq([txt(t) for t in await pg.locator(".agrupar .seg button").all_inner_texts()], ["Categoria", "Vencimento"], "sem os Consumíveis por cômodo: Categoria e Vencimento")
    await pg.click('.agrupar [data-v="vence"]')
    await pg.wait_for_selector('.zone[data-zk^="v:"]')
    ordem = ["Já acabou", "Esta semana", "Este mês", "Mês que vem", "Depois", "Sem duração"]
    esperado = {}
    for nome, dias in itens:
        esperado.setdefault(grupo(dias), []).append((dias or 99999, nome))
    grupos = [g for g in ordem if g in esperado]
    r.eq([txt(t) for t in await pg.locator(".zone .zone-h h3").all_inner_texts()], grupos, "os grupos do vencimento, na ordem")
    for g in grupos:
        nomes = [txt(t) for t in await pg.locator(".zone", has=pg.locator("h3", has_text=g)).locator(".irow .nm, .irow b").first.locator("xpath=ancestor::ul").locator(".irow").all_inner_texts()]
        r.check(all(any(n in x for x in nomes) for _, n in esperado[g]), f"{g}: {[n for _, n in esperado[g]]} ({nomes})")
        primeiro = sorted(esperado[g])[0][1]
        r.check(primeiro in nomes[0], f"{g}: o que acaba primeiro no alto ({primeiro})")
    await pg.reload()
    await pg.wait_for_selector('.zone[data-zk^="v:"]')
    r.eq(await pg.get_attribute('.agrupar [data-v="vence"]', "aria-pressed"), "true", "o aparelho lembra o agrupamento")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "vencimento", full_page=True)
    await ctx.close()
    # 1.102.1: em 320 px as escolhas cabem numa linha, sem nada cortado
    ctx, pg = await r.page(b, "estreito", "light")
    await r.open(pg, "#/consumiveis", ".irow")
    caixas = [await x.bounding_box() for x in await pg.locator(".agrupar .seg button").all()]
    r.check(len({round(c["y"]) for c in caixas}) == 1, "320 px: numa linha")
    cortado = await pg.evaluate("() => [...document.querySelectorAll('.agrupar .seg button > span')].filter(s => s.scrollWidth > s.clientWidth + 1).map(s => s.textContent)")
    r.check(not cortado, f"320 px: nenhum nome cortado {cortado}")
    r.check(await pg.evaluate(OVERFLOW), "320 px: sem rolagem para o lado")
    await r.shot(pg, "vencimento-320")
    await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_cons_vence", body)
