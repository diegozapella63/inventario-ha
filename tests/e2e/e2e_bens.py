"""Bens (Mais > Bens): o que tem valor e fica fora de casa (casa, terreno, carro). A área é criada com o primeiro bem;
Imóveis, Veículos e Outros com o total de cada; conta no patrimônio do Início, nos gráficos e na busca; fora da lista de
cômodos; no relatório, numa seção à parte (o total da casa não muda); a ficha, Mover para Bens e o tema claro e o 320 px."""
from e2e_lib import OVERFLOW, main


# o texto escolhido de cada seleção da busca que não cabe nela (com a fonte do app)
CUT = "[...document.querySelectorAll('.sfilters select')].filter(s => { const c = document.createElement('canvas').getContext('2d'); const st = getComputedStyle(s); c.font = st.fontSize + ' ' + st.fontFamily; return c.measureText(s.selectedOptions[0].textContent).width > s.clientWidth - parseFloat(st.paddingLeft) - parseFloat(st.paddingRight) + 1; }).map(s => s.selectedOptions[0].textContent)"


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


async def body(r, p):
    r.start(search=False)
    d0 = r.data()
    house_total = sum(float(i["value"] or 0) for i in d0["items"])
    n_house = len(d0["items"])
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="turquesa")

    # -- o menu Mais começa por Bens; sem nenhum, o convite
    await r.open(pg, "#/mais", ".menu-list")
    rows = await pg.evaluate("[...document.querySelectorAll('.menu-row b')].map(b => b.textContent)")
    r.eq(rows[0], "Bens", "Bens é a primeira linha do menu Mais")
    await pg.click('.menu-row[href="#/bens"]')
    await pg.wait_for_selector(".mscreen .empty", timeout=5000)
    r.eq(txt(await pg.text_content(".page-title")), "Bens", "a tela Bens, com ‹ Mais no alto")
    r.eq(txt(await pg.text_content(".mscreen .empty h2")), "Nenhum bem ainda", "sem bens: o convite")
    r.check(not any(x.get("kind") == "bens" for x in r.data()["rooms"]), "a área Bens só é criada com o primeiro bem")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "vazio")

    # -- o primeiro bem, pelo botão da tela
    await pg.click('.mscreen [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    r.eq(txt(await pg.text_content("dialog.modal .dlg-h h2")), "Novo bem", "a janela diz Novo bem")
    r.eq(await pg.locator("#f-room, #f-zone, #f-cat").count(), 0, "um bem não tem Cômodo nem Categoria")
    tipos = await pg.evaluate("[...document.querySelectorAll('.seg.tipo button')].map(b => [b.textContent, b.getAttribute('aria-pressed')])")
    r.eq(tipos, [["Imóvel", "false"], ["Veículo", "false"], ["Outro", "true"]], "só o Tipo: Imóvel, Veículo ou Outro (de início, Outro)")
    w = await pg.evaluate("[...document.querySelectorAll('.seg.tipo button')].map(b => Math.round(b.getBoundingClientRect().width))")
    r.check(len(set(w)) == 1, f"os três do mesmo tamanho ({w})")
    r.eq(txt(await pg.text_content('[data-ed="save"]')), "Salvar bem", "o botão diz Salvar bem")
    await pg.fill("#f-name", "Apartamento na praia")
    await pg.click('.seg.tipo [data-v="imoveis"]')
    r.eq(await pg.get_attribute('.seg.tipo [data-v="imoveis"]', "aria-pressed"), "true", "Imóvel marcado")
    await pg.fill("#f-value", "450.000")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "novo-bem")
    await pg.click('[data-ed="save"]')
    await pg.locator(".toast", has_text="Bem adicionado").wait_for(timeout=8000)
    d = r.data()
    bens = [x for x in d["rooms"] if x.get("kind") == "bens"]
    r.check(len(bens) == 1 and bens[0]["code"] == "BEN" and bens[0]["name"] == "Bens", f"a área Bens foi criada, com o código BEN ({bens})")
    ben = bens[0]["id"]
    apto = next(i for i in d["items"] if i["name"] == "Apartamento na praia")
    r.check(apto["room"] == ben and apto["cat"] == "imoveis" and apto["value"] == 450000, "o bem foi gravado em Bens, como Imóveis, com o valor")
    r.check(d["rooms"][-1]["id"] == ben, "Bens fica depois de todos os cômodos")
    r.api("POST", "api/items", {"room": ben, "name": "Carro hatch 2020", "cat": "veiculos", "value": 60000})
    r.api("POST", "api/items", {"room": ben, "name": "Barco inflável", "cat": "outros", "value": 3000})
    r.api("POST", "api/rooms", {"name": "Garagem", "code": "GAR"})
    order = [x["name"] for x in r.data()["rooms"]]
    r.eq(order[-2:], ["Garagem", "Bens"], "um cômodo novo entra antes de Bens")
    bens_total = 450000 + 60000 + 3000

    # -- a tela Bens: Imóveis, Veículos e Outros, cada um com o total
    await r.open(pg, "#/bens", ".mscreen.bens .zone")
    groups = await pg.evaluate("[...document.querySelectorAll('.bens .zone')].map(z => [z.querySelector('h3').textContent, [...z.querySelectorAll('.nm')].map(n => n.textContent)])")
    r.eq(groups, [["Imóveis", ["Apartamento na praia"]], ["Veículos", ["Carro hatch 2020"]], ["Outros", ["Barco inflável"]]], "Imóveis, Veículos e Outros")
    r.eq(await pg.locator('#view [data-act="item-new"]').count(), 0, "com bens, sem o Adicionar bem repetido no alto")
    await pg.click(".tabbar .plus")
    await pg.wait_for_selector("#f-name")
    r.eq(txt(await pg.text_content("dialog.modal .dlg-h h2")), "Novo bem", "o + de baixo, em Bens, adiciona um bem")
    await pg.click('dialog.modal .dlg-h [data-ed="cancel"]')
    await pg.wait_for_timeout(300)
    r.eq(txt(await pg.text_content(".page-sub")), "3 bens, R$ 513.000", "quantos bens e o total, no alto")
    r.check("Outros" in txt(await pg.text_content(".bens .zone:last-child .irow .z")), "em Outros, cada um diz a categoria")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "lista", full_page=True)

    # -- Início: o patrimônio soma os bens; Bens tem a sua lista e não entra em Cômodos
    await r.open(pg, "#/", ".tag")
    r.eq(txt(await pg.text_content(".tag-sub")), f"{n_house} itens em 7 cômodos e 3 bens", "a etiqueta diz quantos itens, cômodos e bens")
    val = int("".join(ch for ch in await pg.text_content(".tag-value") if ch.isdigit()))
    r.eq(val, round(house_total + bens_total), "o patrimônio soma a casa e os bens")
    r.eq(await pg.evaluate("[...document.querySelectorAll('#home-bens .nm')].map(n => n.textContent)"),
         ["Apartamento na praia", "Carro hatch 2020", "Barco inflável"], "Início: Bens, do maior para o menor")
    r.check("Bens" not in await pg.evaluate("[...document.querySelectorAll('.rows .rn')].map(n => n.firstChild.textContent)"), "Bens não aparece entre os cômodos")
    r.check("Bens" not in txt(await pg.text_content(".facts")).split("Maior cômodo")[1].split("Último")[0], "nem como Maior cômodo")
    await r.shot(pg, "inicio", full_page=True)
    await pg.click('#home-bens a.aside')
    await pg.wait_for_selector(".mscreen.bens", timeout=5000)
    r.check(pg.url.endswith("#/bens"), "Ver todos abre Bens")

    # -- Cômodos: sem Bens, com o total da casa
    await r.open(pg, "#/comodos", ".rooms")
    r.check("Bens" not in txt(await pg.text_content("#view .rooms")), "a aba Cômodos não tem Bens")
    r.check(f"{n_house} itens" in txt(await pg.text_content(".page-sub")), "e conta só os itens da casa")

    # -- a ficha de um bem
    await r.open(pg, f"#/i/{apto['id']}", "dialog.sheet h1")
    r.check("Onde" in txt(await pg.text_content("dialog.sheet .facts, dialog.sheet dl")), "a ficha diz Onde: Bens")
    await pg.click('dialog.sheet a[href="#/bens"]')
    await pg.wait_for_selector(".mscreen.bens", timeout=5000)
    r.check(True, "e o link leva para Bens")

    # -- busca: o filtro Tipo, antes do de cômodos (itens da casa, imóveis, veículos, outros bens)
    await r.open(pg, "#/buscar", ".sbar")
    sels = await pg.evaluate("[...document.querySelectorAll('.sfilters select')].map(s => s.dataset.input)")
    r.eq(sels, ["search-tipo", "search-room", "search-cat", "search-ord"], "com bens, o Tipo vem antes de Cômodo, Categoria e Ordem")
    r.eq(await pg.evaluate("[...document.querySelectorAll('[data-input=\"search-tipo\"] option')].map(o => o.textContent)"),
         ["Todos os tipos", "Itens da casa", "Imóveis", "Veículos", "Outros bens"], "os tipos")
    r.check("Bens" not in await pg.evaluate("[...document.querySelectorAll('[data-input=\"search-room\"] option')].map(o => o.textContent)"), "Bens sai da lista de cômodos")
    grid = await pg.evaluate("[...document.querySelectorAll('.sfilters select')].map(s => { const b = s.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width)]; })")
    r.check(len({x[2] for x in grid}) == 1 and len({x[0] for x in grid}) == 2 and len({x[1] for x in grid}) == 2, f"no celular, quatro seleções iguais em duas linhas ({grid})")
    await pg.evaluate("document.fonts.ready.then(() => 1)")  # medir com a fonte do app, não com a de reserva
    cut = await pg.evaluate(CUT)
    r.eq(cut, [], "nenhum texto das seleções cortado")
    await r.shot(pg, "busca-tipos")
    all_n = len(await pg.query_selector_all("#results .irow"))
    await pg.select_option('[data-input="search-tipo"]', "imoveis")
    await pg.wait_for_selector('.sfilters.n2', timeout=4000)
    r.eq(await pg.locator('[data-input="search-room"], [data-input="search-cat"]').count(), 0, "num tipo de bem, sem Cômodo e Categoria")
    r.eq(await pg.evaluate("[...document.querySelectorAll('#results .irow .nm')].map(n => n.textContent)"), ["Apartamento na praia"], "Imóveis: só o apartamento")
    r.check(pg.url.endswith("tipo=imoveis"), "o tipo fica no endereço")
    await pg.select_option('[data-input="search-tipo"]', "outros")
    await pg.wait_for_timeout(300)
    r.eq(await pg.evaluate("[...document.querySelectorAll('#results .irow .nm')].map(n => n.textContent)"), ["Barco inflável"], "Outros bens")
    await pg.select_option('[data-input="search-tipo"]', "casa")
    await pg.wait_for_selector('[data-input="search-room"]', timeout=4000)
    r.eq(len(await pg.query_selector_all("#results .irow")), all_n - 3, "Itens da casa: sem os 3 bens")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")

    # -- Mover um item para Bens, e Desfazer
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-room")
    r.eq((await pg.evaluate("[...document.querySelectorAll('#mv-room option')].map(o => o.textContent)"))[-1], "Bens", "Mover: Bens no fim")
    await pg.select_option("#mv-room", ben)
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="Movido para Bens").wait_for(timeout=5000)
    r.eq(next(i for i in r.data()["items"] if i["id"] == "sal-007")["room"], ben, "o item foi para Bens")
    sal = next(i for i in r.data()["items"] if i["id"] == "sal-007")
    await pg.locator(".toast button", has_text="Desfazer").click()
    await pg.wait_for_timeout(600)
    r.eq(next(i for i in r.data()["items"] if i["id"] == "sal-007")["room"], "sala", "Desfazer volta para a sala")

    # -- Editar um bem: sem Cômodo nem Categoria; Outro guarda a categoria que o item trouxe do cômodo
    r.api("PUT", f"api/items/{sal['id']}", {"room": ben, "_base": next(i for i in r.data()["items"] if i["id"] == "sal-007")["updatedAt"]})
    cat0, sal_zone = sal["cat"], next(i for i in d0["items"] if i["id"] == "sal-007").get("zone", "")
    await r.open(pg, f"#/i/{sal['id']}", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"]')
    await pg.wait_for_selector("#f-name")
    r.eq(txt(await pg.text_content("dialog.modal .dlg-h h2")), "Editar bem", "a janela diz Editar bem")
    r.eq(await pg.locator("#f-room, #f-cat").count(), 0, "editar um bem: sem Cômodo nem Categoria")
    r.eq(await pg.get_attribute('.seg.tipo [data-v=""]', "aria-pressed"), "true", "o item que veio da sala é Outro")
    await pg.click('.seg.tipo [data-v="veiculos"]')
    await pg.click('.seg.tipo [data-v=""]')
    await pg.click('[data-ed="save"]')
    await pg.locator(".toast", has_text="Alterações salvas").wait_for(timeout=5000)
    r.eq(next(i for i in r.data()["items"] if i["id"] == "sal-007")["cat"], cat0, "Outro de novo: a categoria que ele tinha continua")
    await r.open(pg, f"#/i/{apto['id']}", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"]')
    await pg.wait_for_selector("#f-name")
    r.eq(await pg.get_attribute('.seg.tipo [data-v="imoveis"]', "aria-pressed"), "true", "o apartamento abre como Imóvel")
    await pg.click('.seg.tipo [data-v="veiculos"]')
    await pg.click('[data-ed="save"]')
    await pg.locator(".toast", has_text="Alterações salvas").wait_for(timeout=5000)
    r.eq(next(i for i in r.data()["items"] if i["id"] == apto["id"])["cat"], "veiculos", "trocar o tipo grava a categoria")
    cur = next(i for i in r.data()["items"] if i["id"] == "sal-007")
    r.api("PUT", "api/items/sal-007", {"room": "sala", "zone": sal_zone, "_base": cur["updatedAt"]})  # de volta, para o relatório
    await ctx.close()

    # -- relatório: a casa como antes; Bens numa seção à parte, com o total dele
    ctx, pg = await r.page(b, "pc", "light", accent="verde")
    await r.open(pg, "#/relatorio", ".report")
    boxes = await pg.evaluate("[...document.querySelectorAll('.rtotal > div')].map(d => [d.querySelector('span').textContent, d.querySelector('b').textContent.replace(/\\s/g, ' ')])")
    r.eq([x[0] for x in boxes], ["Na casa", "Itens", "Cômodos", "Bens"], "no alto: na casa, itens, cômodos e bens")
    r.eq(boxes[1][1], str(n_house), "os itens da casa")
    r.eq(txt(boxes[3][1]), "R$ 513.000", "o total dos bens")
    foot = txt(await pg.text_content(".report > .rtable tfoot"))
    r.check(foot.replace(" ", "").startswith(f"Total{n_house}R$") and "513.000" not in foot, f"o total da casa não muda com os bens ({foot})")
    r.check("Bens" not in txt(await pg.text_content(".report > .rtable tbody")), "Bens fora da tabela dos cômodos")
    last = pg.locator(".rep-room").last
    r.eq(await last.get_attribute("class"), "rep-room rep-bens", "a seção Bens é a última")
    tf = txt(await last.locator("tfoot").text_content())
    r.check("Total dos bens" in tf and "513.000" in tf, f"com o total dos bens ({tf})")
    await r.shot(pg, "relatorio", full_page=True)

    # -- gráficos: a casa de um lado (cômodos, categorias, faixas, mais valiosos), os bens no gráfico deles
    await r.open(pg, "#/graficos", ".kpis")
    r.eq(txt(await pg.text_content("#g-rooms h2")), "Cômodos", "Cômodos só com os cômodos")
    r.check("Bens" not in txt(await pg.text_content("#g-rooms")), "sem Bens entre os cômodos")
    r.check("do que há em casa" in txt(await pg.text_content("#g-rooms .lead")), "a parte de cada cômodo é do que há em casa")
    r.check("Veículos" not in txt(await pg.text_content("#g-cats")) and "Barco" not in txt(await pg.text_content("#g-top")), "categorias e mais valiosos só da casa")
    r.eq(txt(await pg.text_content("#g-bens h2")), "Bens", "o gráfico exclusivo dos bens")
    hrefs = await pg.evaluate("[...document.querySelectorAll('#g-bens a')].map(a => a.getAttribute('href'))")
    r.eq(hrefs, [f"#/i/{apto['id']}"] + [f"#/i/{i['id']}" for i in sorted([x for x in r.data()["items"] if x["room"] == ben and x["id"] != apto["id"]], key=lambda x: -x["value"])],
         "cada bem, do maior para o menor, abre a ficha")
    r.check(txt(await pg.text_content("#g-bens .lead")).startswith("Veículos são"), f"o tipo que mais vale ({txt(await pg.text_content('#g-bens .lead'))})")
    r.check("R$ 513.000 em bens" in txt(await pg.text_content(".kpis")), "o patrimônio do alto diz quanto está em bens")
    await r.shot(pg, "graficos", full_page=True)
    await r.open(pg, "#/bens", ".mscreen.bens")
    r.check(await pg.evaluate(OVERFLOW), "Bens no computador, sem rolagem para o lado")
    await r.shot(pg, "lista-pc", full_page=True)
    await ctx.close()

    # -- 320 px, claro
    ctx, pg = await r.page(b, "estreito", "light", accent="coral")
    for h, w in (("#/bens", ".mscreen.bens"), ("#/", ".tag")):
        await r.open(pg, h, w)
        r.check(await pg.evaluate(OVERFLOW), f"320 px, {h}: nada passa da largura")
    await r.open(pg, "#/buscar", ".sfilters")
    await pg.evaluate("document.fonts.ready.then(() => 1)")
    r.eq(await pg.evaluate(CUT), [], "320 px: as seleções da busca, uma por linha, sem texto cortado")
    await r.shot(pg, "estreito", full_page=True)
    await ctx.close()
    await b.close()


main("bens", body)
