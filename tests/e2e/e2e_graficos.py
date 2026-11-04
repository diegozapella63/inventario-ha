"""Mais > Gráficos: os números do alto, os cômodos e as categorias que mais valem (da maior para a menor, com o valor
escrito), as faixas de valor, os itens mais valiosos, o patrimônio mês a mês (quando há mais de um mês), cada linha
levando à sua tela, sem passar da largura no celular estreito e lado a lado no computador."""
from e2e_lib import OVERFLOW, main

ROWS = "(sel) => [...document.querySelectorAll(sel + ' .hbar')].map(a => [a.querySelector('.hb-t b').textContent, a.querySelector('.hb-v b').textContent.replace(/\\u00a0/g, ' '), a.querySelector('.hb-v span').textContent, a.getAttribute('href')])"


def brl(v):
    return "R$ " + f"{round(v):,}".replace(",", ".")


async def body(r, p):
    r.start(search=False)
    d = r.data()
    items = d["items"]
    total = sum(i.get("value") or 0 for i in items)
    rooms = {x["id"]: x for x in d["rooms"]}
    by_room = {}
    for i in items:
        by_room[i["room"]] = by_room.get(i["room"], 0) + (i.get("value") or 0)
    ranked = sorted(by_room.items(), key=lambda kv: -kv[1])

    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="azul")
    await r.open(pg, "#/mais", ".menu-list")
    await pg.click('.menu-row[href="#/graficos"]')
    await pg.wait_for_selector(".kpis")
    r.check(pg.url.endswith("#/graficos"), "Mais > Gráficos abre a tela")
    r.eq((await pg.text_content(".page-title")).strip(), "Gráficos", "com o título")
    kpis = await pg.evaluate("[...document.querySelectorAll('.kpi')].map(k => [k.querySelector('span').textContent, k.querySelector('b').textContent.replace(/\\u00a0/g, ' ')])")
    r.eq(kpis[0], ["Patrimônio", brl(total)], "o patrimônio no alto")
    r.eq(kpis[1], ["Itens", str(len(items))], "quantos itens")
    com_foto = sum(1 for i in items if i.get("photos"))
    r.eq(kpis[3], ["Com foto", f"{round(com_foto / len(items) * 100)}%"], "quantos têm foto")

    # cômodos: do que mais vale para o que menos vale, com valor e parte do total
    got = await pg.evaluate(ROWS, "#g-rooms")
    r.eq([x[0] for x in got], [rooms[k]["name"] for k, _ in ranked], "cômodos do que mais vale para o que menos vale")
    r.eq(got[0][1], brl(ranked[0][1]), "o valor de cada um")
    r.eq(got[0][2], f"{round(ranked[0][1] / total * 100)}%", "e a parte do patrimônio")
    acc = half = 0
    for _, v in ranked:
        if acc * 2 >= total:
            break
        acc += v
        half += 1
    r.check(f"{half} cômodos somam metade do patrimônio." in await pg.text_content("#g-rooms .lead"), "quantos cômodos somam metade")
    widths = await pg.evaluate("[...document.querySelectorAll('#g-rooms .hb-bar i')].map(i => i.getBoundingClientRect().width)")
    track = await pg.evaluate("document.querySelector('#g-rooms .hb-bar').getBoundingClientRect().width")
    r.check(abs(widths[0] - track) < 1.5 and all(a >= b - 0.5 for a, b in zip(widths, widths[1:])), f"a maior barra vai até o fim e as outras diminuem ({[round(w) for w in widths]})")

    # categorias
    cats = {c["id"]: c["name"] for c in d["cats"]}
    by_cat = {}
    for i in items:
        by_cat[i.get("cat") or "outros"] = by_cat.get(i.get("cat") or "outros", 0) + (i.get("value") or 0)
    got = await pg.evaluate(ROWS, "#g-cats")
    r.eq([x[0] for x in got], [cats[k] for k, _ in sorted(by_cat.items(), key=lambda kv: -kv[1])], "categorias da que mais vale para a que menos vale")

    # faixas de valor
    cols = await pg.evaluate("[...document.querySelectorAll('#g-bands .band')].map(c => [c.querySelector('.bd-l').textContent, +c.querySelector('.bd-n').textContent])")
    r.eq([c[0] for c in cols], ["até 100", "100–500", "500–1 mil", "1–5 mil", "5 mil+"], "as cinco faixas")
    bands = [(0, 100), (100, 500), (500, 1000), (1000, 5000), (5000, 10 ** 12)]
    want = [sum(1 for i in items if (i.get("value") or 0) > 0 and lo <= i["value"] < hi) for lo, hi in bands]
    r.eq([c[1] for c in cols], want, "quantos itens em cada faixa")
    lab = await pg.get_attribute("#g-bands .band", "aria-label")
    r.check(lab.startswith("até 100 reais: ") and "no total" in lab, f"cada coluna diz o que mostra para o leitor de tela ({lab})")

    # itens mais valiosos
    top = sorted(items, key=lambda i: -(i.get("value") or 0))
    got = await pg.evaluate(ROWS, "#g-top")
    r.eq([x[0] for x in got[:3]], [i["name"] for i in top[:3]], "os itens mais valiosos primeiro")
    r.eq(len(got), 10, "os dez mais valiosos")
    r.eq(await pg.locator("#g-time").count(), 0, "tudo cadastrado num mês só: sem o gráfico mês a mês")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "cel-escuro", full_page=True)

    # cada linha leva à sua tela
    await pg.click(f'#g-rooms .hbar[href="#/c/{ranked[0][0]}"]')
    await pg.wait_for_selector(".rhead")
    r.check(pg.url.endswith(f"#/c/{ranked[0][0]}"), "tocar num cômodo abre o cômodo")
    await pg.go_back()
    await pg.wait_for_selector(".kpis")
    await pg.locator("#g-cats .hbar").first.click()
    await pg.wait_for_selector(".sbar")
    r.check("#/buscar?cat=" in pg.url and "ord=val" in pg.url, f"tocar numa categoria busca os itens dela, dos mais caros ({pg.url.split('#')[1]})")
    await pg.go_back()
    await pg.wait_for_selector(".kpis")
    await pg.locator("#g-top .hbar").first.click()
    await pg.wait_for_selector("dialog.sheet h1")
    r.eq((await pg.text_content("dialog.sheet h1")).strip(), top[0]["name"], "tocar num item abre a ficha")
    await ctx.close()

    # um item cadastrado agora: dois meses, aparece o patrimônio mês a mês
    r.api("POST", "api/items", {"room": "sala", "name": "Projetor portátil", "cat": "eletronicos", "value": 2400})
    ctx, pg = await r.page(b, "cel", "light", accent="verde")
    await r.open(pg, "#/graficos", ".kpis")
    await pg.wait_for_selector("#g-time .area svg .ln")
    r.check(True, "com mais de um mês, o patrimônio mês a mês aparece")
    r.check(brl(total + 2400) in (await pg.text_content("#g-time .lead")).replace("\xa0", " "), "e diz o total de hoje")
    rows = await pg.locator("#g-time tbody tr").count()
    r.check(rows >= 2, f"a tabela mês a mês ({rows} meses)")
    await pg.locator("#g-time").scroll_into_view_if_needed()
    box = await pg.locator("#g-time .area svg").bounding_box()
    await pg.touchscreen.tap(box["x"] + box["width"] - 10, box["y"] + box["height"] / 2)  # no celular, tocar mostra o valor
    await pg.wait_for_selector("#g-time .ctip:not([hidden])")
    tip = (await pg.text_content("#g-time .ctip")).replace("\xa0", " ")
    r.check(brl(total + 2400) in tip, f"passar o dedo ou o mouse mostra o valor do mês ({tip})")
    inside = await pg.evaluate("(() => { const t = document.querySelector('#g-time .ctip').getBoundingClientRect(), a = document.querySelector('#g-time .area').getBoundingClientRect(); return t.left >= a.left - 1 && t.right <= a.right + 1; })()")
    r.check(inside, "a caixinha do valor não sai do gráfico")
    await pg.locator("#g-time").scroll_into_view_if_needed()
    await r.shot(pg, "mes-a-mes")
    await ctx.close()

    # celular estreito e computador
    for size, scheme in (("estreito", "light"), ("pc", "dark")):
        ctx, pg = await r.page(b, size, scheme, accent="coral")
        await r.open(pg, "#/graficos", ".kpis")
        await pg.wait_for_selector("#g-time .area svg")
        r.check(await pg.evaluate(OVERFLOW), f"[{size}] sem rolagem para o lado")
        cut = await pg.evaluate("[...document.querySelectorAll('.hb-v b, .kpi b, .bd-l')].some(e => e.scrollWidth > e.clientWidth + 1)")
        r.check(not cut, f"[{size}] valores e nomes das faixas inteiros")
        if size == "pc":
            pair = await pg.evaluate("[document.querySelector('#g-rooms').getBoundingClientRect(), document.querySelector('#g-cats').getBoundingClientRect()].map(b => [Math.round(b.left), Math.round(b.top)])")
            r.check(pair[1][0] > pair[0][0] and abs(pair[1][1] - pair[0][1]) <= 1, f"[pc] cômodos e categorias lado a lado ({pair})")
            svg_w = await pg.evaluate("document.querySelector('#g-time .area svg').getBoundingClientRect().width")
            area_w = await pg.evaluate("document.querySelector('#g-time .area').getBoundingClientRect().width")
            r.check(abs(svg_w - area_w) < 2, "[pc] o gráfico mês a mês ocupa a largura")
        await r.shot(pg, size, full_page=True)
        await ctx.close()

    # sem itens
    for i in r.data()["items"]:
        r.api("DELETE", f"api/items/{i['id']}")
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/graficos", "#view .empty")
    r.check("Cadastre itens para ver os gráficos." in await pg.text_content("#view .empty"), "sem itens: diz o que fazer")
    await ctx.close()
    await b.close()


main("graficos", body)
