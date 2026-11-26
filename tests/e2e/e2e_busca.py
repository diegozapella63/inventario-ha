"""Buscar, além do básico (e2e_inicio_busca): ordem por nome, valor, recentes e código; código e categoria na busca; zonas
ligadas e desligadas; todos de uma vez, com muitos itens; o X que limpa; Voltar mantém a busca; cômodo e categoria pelo endereço."""
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
    # 1.80.0: o título dos filtros se chama Filtros, como nos outros apps; fecha e abre num toque, e o aparelho lembra
    fh = pg.locator(".sbar .filtros-h")
    r.eq([(await fh.inner_text()).strip(), await fh.get_attribute("aria-expanded"), await fh.locator("svg").count()], ["Filtros", "true", 2], "Buscar: o título Filtros, com o ícone e a seta, aberto")
    r.check(await pg.locator(".sfilters select").first.is_visible(), "aberto: os filtros à mostra")
    await fh.click()
    r.eq([await fh.get_attribute("aria-expanded"), await pg.locator(".sfilters").is_visible()], ["false", False], "um toque fecha os filtros")
    r.check(" ".join((await fh.inner_text()).split()).startswith("Filtros · "), f"fechado, sem nada escolhido, diz o que vale ({(await fh.inner_text())!r})")
    await pg.reload(); await pg.wait_for_selector(".ssum")
    r.eq([await pg.locator(".sbar .filtros-h").get_attribute("aria-expanded"), await pg.locator(".sfilters").is_visible()], ["false", False], "o aparelho lembra fechado")
    await pg.locator(".sbar .filtros-h").click()
    r.eq([await pg.locator(".sbar .filtros-h").get_attribute("aria-expanded"), await pg.locator(".sfilters").is_visible()], ["true", True], "outro toque abre")
    # 1.110.0 (PADROES.md): fechado, o que está escolhido ao lado do nome
    sala = await pg.evaluate("document.querySelector('[data-input=\"search-room\"] option:nth-child(2)').value")
    await pg.select_option('[data-input="search-room"]', sala); await pg.wait_for_timeout(300)
    nome_sala = await pg.evaluate(f"(document.querySelector('[data-input=\"search-room\"] option[value=\"{sala}\"]') || {{}}).textContent")
    await pg.locator(".sbar .filtros-h").click()
    val = " ".join((await pg.locator(".sbar .filtros-h").inner_text()).split())
    r.check(val.startswith("Filtros · ") and val.endswith(nome_sala), f"fechado, o escolhido ao lado ({val})")
    await pg.locator(".sbar .filtros-h").click()
    await pg.select_option('[data-input="search-room"]', ""); await pg.wait_for_timeout(300)
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

    # -- muitos itens: tudo de uma vez (1.109.0, o dono: "ódio mortal pelo mostrar mais 120… buscar tudo por padrão")
    for start in (0, 60, 120):
        r.api("POST", "api/items/batch", {"items": [{"name": f"Pote organizador {k + 1:03d}", "room": "lavanderia", "cat": "utilidades", "value": 10}
                                                    for k in range(start, min(start + 60, 130))]})
    await r.open(pg, "#/buscar", ".ssum")
    r.check((await pg.text_content(".ssum .ssum-n")).strip().startswith("168 itens") and await rows(pg) == 168, "168 itens: todos na tela")
    r.eq(await pg.locator('[data-act="more-results"]').count(), 0, "sem o Mostrar mais")
    await query(pg, "pote")
    r.check(await rows(pg) == 130, "uma busca: todos os que batem")
    # a contagem e a soma à esquerda, o Selecionar à direita (PADROES.md)
    pos = await pg.evaluate("(() => { const c = document.querySelector('.ssum').getBoundingClientRect(), n = document.querySelector('.ssum .ssum-n').getBoundingClientRect(), s = document.querySelector('.ssum .sel-go').getBoundingClientRect(); return [Math.round(n.left - c.left), Math.round(c.right - s.right)]; })()")
    r.check(pos[0] <= 4 and pos[1] <= 4, f"a contagem à esquerda e o Selecionar à direita ({pos})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "mostrar-mais")
    await ctx.close()
    await b.close()


main("busca", body)
