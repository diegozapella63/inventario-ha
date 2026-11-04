"""Buscar, além do básico (e2e_inicio_busca): ordem por nome, valor, recentes e código; código e categoria na busca; zonas
ligadas e desligadas; "Mostrar mais" com muitos itens; o X que limpa; Voltar mantém a busca; cômodo e categoria pelo endereço."""
from e2e_lib import OVERFLOW, main

NAMES = "[...document.querySelectorAll('#view .irow .nm')].map(e => e.textContent)"
VALS = "[...document.querySelectorAll('#view .irow .val')].map(e => +e.textContent.replace(/[^0-9,]/g, '').replace(',', '.'))"
CODES = "[...document.querySelectorAll('#view .irow .mt')].map(e => e.textContent.trim())"


def hash_(pg):
    return "#" + pg.url.split("#", 1)[1] if "#" in pg.url else "#/"


async def order(pg, k):
    await pg.select_option('[data-input="search-ord"]', k)
    await pg.wait_for_timeout(250)


async def query(pg, q):
    await pg.fill('[data-input="search-q"]', q)
    await pg.wait_for_timeout(350)


async def rows(pg):
    return await pg.locator("#view .irow").count()


async def body(r, p):
    r.start(search=False)
    items = r.data()["items"]
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="lilas")

    # -- ordens
    await r.open(pg, "#/buscar", ".ssum")
    r.eq(await pg.input_value('[data-input="search-ord"]'), "val", "sem busca, a ordem começa por Maior valor")
    await order(pg, "az")
    names = await pg.evaluate(NAMES)
    r.check(names == await pg.evaluate("(n) => [...n].sort((a, b) => a.localeCompare(b, 'pt-BR'))", names) and len(names) == 38,
            f"Nome, de A a Z (com acentos no lugar certo) ({names[:3]})")
    await order(pg, "valasc")
    vals = await pg.evaluate(VALS)
    r.check(vals == sorted(vals) and vals[0] == min(i["value"] for i in items), f"Menor valor primeiro ({vals[:4]})")
    await order(pg, "new")
    want = [i["name"] for i in sorted(items, key=lambda i: i["createdAt"], reverse=True)][:8]
    r.eq((await pg.evaluate(NAMES))[:8], want, "Mais recentes: pela data do cadastro")
    await order(pg, "code")
    codes = await pg.evaluate(CODES)
    r.check(codes[:2] == ["SAL-001", "SAL-002"] and codes[-1] == "VAR-003" and codes.index("COZ-001") == 12, f"Código: pela ordem dos cômodos e o número ({codes[11:14]})")
    r.check("ord=code" in hash_(pg), "a ordem fica no endereço")
    await r.open(pg, "#/buscar?ord=az", ".ssum")
    r.eq(await pg.input_value('[data-input="search-ord"]'), "az", "a ordem vem do endereço")

    # -- busca por texto: relevância, código, categoria
    await r.open(pg, "#/buscar", ".ssum")
    await query(pg, "madeira")
    names = await pg.evaluate(NAMES)
    r.check(names[0] == "Estante de madeira com três prateleiras" and names[-1] in ("Sofá de 3 lugares cinza-azulado", "Mesa de jantar com 4 cadeiras"),
            f"com texto, por relevância: madeira no nome vem antes de madeira só nos detalhes, mesmo valendo menos ({names[0]}, {names[-1]})")
    ord_shown = await pg.input_value('[data-input="search-ord"]')
    r.eq(ord_shown, "rel", "a seleção da ordem diz Mais relevantes, como a lista")
    await r.shot(pg, "relevancia")
    await query(pg, "coz-004")
    r.eq(await pg.evaluate(NAMES), ["Geladeira frost free inox"], "acha pelo código do item")
    await query(pg, "eletronicos")
    r.eq(await rows(pg), sum(1 for i in items if i["cat"] == "eletronicos"), "acha pelo nome da categoria, sem acento")
    await query(pg, "lavanderia")
    r.eq(await rows(pg), sum(1 for i in items if i["room"] == "lavanderia"), "acha pelo nome do cômodo")

    # -- o X limpa
    r.check(await pg.is_visible('[data-act="search-clear"]'), "com texto, o X de limpar aparece")
    await pg.click('[data-act="search-clear"]')
    await pg.wait_for_timeout(250)
    r.check(await pg.input_value('[data-input="search-q"]') == "" and await pg.evaluate("document.activeElement.dataset.input") == "search-q"
            and await rows(pg) == 38 and "q=" not in hash_(pg) and await pg.is_hidden('[data-act="search-clear"]'),
            "o X apaga o texto, deixa o cursor na busca, volta tudo, tira do endereço e some")

    # -- zonas: desligadas, a zona não entra na busca; ligadas, entra e aparece na linha
    await query(pg, "bancada")
    r.check(await pg.locator("#view .empty").count() == 1 and "Nome, marca ou detalhe" == await pg.get_attribute('[data-input="search-q"]', "placeholder"),
            "zonas desligadas: Bancada (só zona) não acha nada")
    r.api("PUT", "api/settings", {"zones": True})
    await r.open(pg, "#/buscar?q=bancada", ".ssum")
    r.eq(await pg.get_attribute('[data-input="search-q"]', "placeholder"), "Nome, marca, detalhe ou zona", "zonas ligadas: a busca diz que acha pela zona")
    r.eq(sorted(await pg.evaluate(NAMES)), ["Cafeteira espresso", "Chaleira elétrica de inox", "Fruteira de madeira"], "zonas ligadas: Bancada acha os itens da bancada")
    z = await pg.evaluate("[...document.querySelectorAll('#view .irow .z')].map(e => [e.textContent, e.querySelector('mark') && e.querySelector('mark').textContent])")
    r.check(z and all(x == ["Cozinha, Bancada", "Bancada"] for x in z), f"a linha mostra cômodo e zona, com a zona destacada ({z[:1]})")
    await r.shot(pg, "zonas")
    r.api("PUT", "api/settings", {"zones": False})

    # -- Voltar mantém a busca
    await r.open(pg, "#/buscar", ".ssum")
    await query(pg, "geladeira")
    await pg.select_option('[data-input="search-room"]', "cozinha")
    await pg.wait_for_timeout(250)
    await pg.locator("#view .irow").first.click()
    await pg.wait_for_selector("dialog.sheet h1")
    await pg.go_back()
    await pg.wait_for_selector("dialog.sheet", state="detached", timeout=4000)
    r.check(await pg.input_value('[data-input="search-q"]') == "geladeira" and await pg.input_value('[data-input="search-room"]') == "cozinha" and await rows(pg) == 1,
            "abrir um resultado e Voltar: a busca e o filtro continuam")
    await pg.click('.tabbar [data-tab="home"]')
    await pg.wait_for_selector(".tag")
    await pg.go_back()
    await pg.wait_for_selector(".ssum", timeout=4000)
    await pg.wait_for_timeout(250)
    r.check(await pg.input_value('[data-input="search-q"]') == "geladeira" and await pg.input_value('[data-input="search-room"]') == "cozinha",
            "ir para o Início e Voltar: a busca volta com o filtro")

    # -- cômodo e categoria pelo endereço
    await r.open(pg, "#/buscar?room=quarto&cat=moveis", ".ssum")
    want = [i for i in items if i["room"] == "quarto" and i["cat"] == "moveis"]
    r.check(await pg.input_value('[data-input="search-room"]') == "quarto" and await pg.input_value('[data-input="search-cat"]') == "moveis" and await rows(pg) == len(want),
            f"room=quarto&cat=moveis no endereço: os dois filtros aplicados ({len(want)} itens)")
    soma = (await pg.text_content(".ssum b")).replace("\xa0", " ")
    r.eq(soma, "R$ " + f"{sum(i['value'] for i in want):,}".replace(",", "."), "o resumo soma só o que aparece")
    await r.open(pg, "#/buscar?room=lavanderia&cat=livros", "#view .empty")
    await pg.click('[data-act="search-reset"]')
    await pg.wait_for_timeout(300)
    r.check(await rows(pg) == 38 and "room=" not in hash_(pg) and await pg.input_value('[data-input="search-cat"]') == "",
            "sem resultado com filtros: Limpar filtros volta tudo")
    await r.open(pg, "#/buscar?room=nao-existe", ".sbar")
    shown = await pg.input_value('[data-input="search-room"]')
    r.check(shown == "" and await rows(pg) == 38, f"cômodo que não existe no endereço: mostra todos, como diz a seleção ({await rows(pg)})")
    await r.shot(pg, "comodo-inexistente")
    # categoria pelos Gráficos
    await r.open(pg, "#/graficos", ".kpis")
    await pg.click('#g-cats .hbar[href*="cat=eletronicos"]')
    await pg.wait_for_selector(".ssum")
    await pg.wait_for_timeout(250)
    r.check(await pg.input_value('[data-input="search-cat"]') == "eletronicos" and await pg.input_value('[data-input="search-ord"]') == "val",
            "uma categoria nos Gráficos abre a busca dela, por valor")

    # -- muitos itens: Mostrar mais
    for start in (0, 60, 120):
        r.api("POST", "api/items/batch", {"items": [{"name": f"Pote organizador {k + 1:03d}", "room": "lavanderia", "cat": "utilidades", "value": 10}
                                                    for k in range(start, min(start + 60, 130))]})
    await r.open(pg, "#/buscar", ".ssum")
    r.check((await pg.text_content(".ssum span")).strip() == "168 itens" and await rows(pg) == 120, "168 itens: mostra os primeiros 120")
    r.eq((await pg.text_content('[data-act="more-results"]')).strip(), "Mostrar mais 48", "o botão diz quantos faltam")
    await pg.click('[data-act="more-results"]')
    await pg.wait_for_timeout(300)
    r.check(await rows(pg) == 168 and await pg.locator('[data-act="more-results"]').count() == 0, "Mostrar mais traz o resto e o botão some")
    await query(pg, "pote")
    r.check(await rows(pg) == 120 and (await pg.text_content('[data-act="more-results"]')).strip() == "Mostrar mais 10", "uma busca nova volta a mostrar 120 de cada vez")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "mostrar-mais")
    await ctx.close()
    await b.close()


main("busca", body)
