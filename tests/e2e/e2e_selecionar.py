"""Buscar › Selecionar (1.39.0): marcar vários itens e mudar de uma vez a categoria, o cômodo ou a zona, com Desfazer.
Selecionar todos vale para a lista inteira; mudar o filtro tira da seleção o que sumiu; os bens não entram; o Voltar do
celular e o Cancelar saem do Selecionar; a barra de baixo fica acima da barra de abas, no celular estreito também."""
from e2e_lib import OVERFLOW, main

PRESSED = "[...document.querySelectorAll('.irow.selr[aria-pressed=\"true\"]')].map(b => b.dataset.id)"


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="coral")
    await r.open(pg, "#/buscar?cat=moveis", ".ssum")
    n = int((await pg.text_content(".ssum span")).split()[0])
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".selbar")
    r.eq(await pg.locator(".irow.selr").count(), n, "Selecionar: cada linha vira uma marcação")
    r.check(await pg.is_disabled('.selbar [data-kind="cat"]'), "sem nada marcado, os botões ficam desligados")
    rows = pg.locator(".irow.selr")
    ids = [await rows.nth(k).get_attribute("data-id") for k in range(2)]
    await rows.nth(0).click()
    await rows.nth(1).click()
    r.eq(await pg.evaluate(PRESSED), ids, "tocar marca (e não abre a ficha)")
    r.check("#/i/" not in pg.url, "continua no Buscar")
    r.eq((await pg.text_content(".ssum.sel .check")).strip(), "2 selecionados", "a conta dos marcados")
    sel = await pg.evaluate("[...document.querySelectorAll('.selbar .btn')].map(b => [b.textContent.trim(), Math.round(b.getBoundingClientRect().width)])")
    r.eq([t for t, _ in sel], ["Cômodo", "Categoria"], "zonas desligadas: Cômodo e Categoria")
    r.check(len({w for _, w in sel}) == 1, f"os botões com a mesma largura ({sel})")
    tab = await pg.locator(".tabbar").bounding_box()
    bar = await pg.locator(".selbar").bounding_box()
    r.check(bar["y"] + bar["height"] <= tab["y"] + 1, f"a barra fica acima das abas ({bar}, {tab})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "selecionados")

    # Categoria de dois itens, e Desfazer
    await pg.click('.selbar [data-kind="cat"]')
    await pg.wait_for_selector("#bk-v")
    r.eq((await pg.text_content("dialog.modal h2")).strip(), "Mudar a categoria", "a janela")
    r.eq((await pg.text_content("dialog.modal [data-ok]")).strip(), "Mudar 2 itens", "o botão diz quantos")
    await pg.select_option("#bk-v", "decoracao")
    await r.shot(pg, "mudar-categoria")
    await pg.click("dialog.modal [data-ok]")
    t = pg.locator(".toast", has_text="2 itens em Decoração e arte")
    await t.wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq([d[i]["cat"] for i in ids], ["decoracao", "decoracao"], "os dois mudam de categoria")
    r.eq(await pg.locator(".irow.selr").count(), n - 2, "e saem da lista de Móveis (e da seleção)")
    r.eq((await pg.text_content(".ssum.sel .check")).strip(), "Selecionar todos", "nada marcado")
    await t.locator("button").click()
    await pg.wait_for_timeout(700)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq([d[i]["cat"] for i in ids], ["moveis", "moveis"], "Desfazer volta a categoria")
    r.eq(await pg.locator(".irow.selr").count(), n, "e eles voltam para a lista")

    # Cômodo: Selecionar todos (a lista toda) e mudar para a Varanda; o código muda, o Desfazer volta o de antes
    await pg.check('[data-input="sel-all"]')
    await pg.wait_for_timeout(300)
    r.eq(len(await pg.evaluate(PRESSED)), n, "Selecionar todos marca a lista toda")
    antes = {i["id"]: (i["room"], i["seq"]) for i in r.data()["items"] if i["cat"] == "moveis"}
    await pg.click('.selbar [data-kind="room"]')
    await pg.wait_for_selector("#bk-v")
    r.check("Em outro cômodo, o item ganha um código novo." in await pg.text_content("dialog.modal .help"), "avisa do código novo")
    await pg.select_option("#bk-v", "varanda")
    await pg.click("dialog.modal [data-ok]")
    t = pg.locator(".toast", has_text="na Varanda").or_(pg.locator(".toast", has_text="em Varanda"))
    await t.first.wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.check(all(d[i]["room"] == "varanda" for i in antes), "todos vão para a Varanda")
    r.eq(len({d[i]["seq"] for i in antes}), len(antes), "cada um com o seu número")
    await t.first.locator("button").click()
    await pg.wait_for_timeout(700)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq({i: (d[i]["room"], d[i]["seq"]) for i in antes}, antes, "Desfazer: cada um no seu cômodo, com o número de antes")

    # mudar o filtro tira da seleção o que sumiu; o Voltar do celular sai do Selecionar
    await pg.select_option('[data-input="search-cat"]', "")
    await pg.wait_for_timeout(300)
    r.eq(len(await pg.evaluate(PRESSED)), n, "sem filtro, os marcados continuam")
    await pg.select_option('[data-input="search-room"]', "cozinha")
    await pg.wait_for_timeout(300)
    marcados = await pg.evaluate(PRESSED)
    r.check(all(d[i]["room"] == "cozinha" for i in marcados), "só fica marcado o que está na lista")
    await pg.go_back()
    await pg.wait_for_timeout(400)
    r.check(await pg.locator(".selbar").count() == 0 and await pg.locator('[data-act="sel-start"]').count() == 1, "o Voltar sai do Selecionar")
    r.check("#/buscar" in pg.url, "e fica no Buscar")
    await ctx.close()

    # zonas ligadas: Zona de vários (e tirar a zona); celular estreito sem passar da largura
    r.api("PUT", "api/settings", {"zones": True})
    ctx, pg = await r.page(b, "estreito", "light", accent="verde")
    await r.open(pg, "#/buscar?room=sala", ".ssum")
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".selbar.n3")
    rows = pg.locator(".irow.selr")
    ids = [await rows.nth(k).get_attribute("data-id") for k in range(3)]
    for k in range(3):
        await rows.nth(k).click()
    r.check(await pg.evaluate(OVERFLOW), "estreito: sem rolagem para o lado")
    cut = await pg.evaluate("[...document.querySelectorAll('.selbar .btn')].filter(b => b.scrollWidth > b.clientWidth + 1).map(b => b.textContent.trim())")
    r.eq(cut, [], "estreito: Cômodo, Categoria e Zona inteiros")
    await r.shot(pg, "estreito-zonas")
    await pg.click('.selbar [data-kind="zone"]')
    await pg.wait_for_selector("#bk-v")
    await pg.fill("#bk-v", "Parede da TV")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="3 itens na zona Parede da TV").wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq([d[i]["zone"] for i in ids], ["Parede da TV"] * 3, "a zona dos três")
    await pg.click('.selbar [data-kind="zone"]')
    await pg.wait_for_selector("#bk-v")
    r.eq(await pg.input_value("#bk-v"), "Parede da TV", "a zona em comum já vem escrita")
    await pg.fill("#bk-v", "")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="3 itens sem zona").wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq([d[i]["zone"] for i in ids], [""] * 3, "vazio tira a zona")
    await pg.click('[data-act="sel-end"]')
    await pg.wait_for_timeout(400)
    r.eq(await pg.locator(".selbar").count(), 0, "Cancelar sai do Selecionar")
    await ctx.close()
    r.api("PUT", "api/settings", {"zones": False})

    # os bens ficam de fora (não têm cômodo nem categoria)
    r.api("POST", "api/rooms", {"kind": "bens"})
    bem = r.api("POST", "api/items", {"room": "bens", "name": "Carro hatch 2020", "cat": "veiculos", "value": 50000})["item"]
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/buscar?q=carro", ".ssum")
    r.eq(await pg.locator('[data-act="sel-start"]').count(), 0, "só bens na lista: sem Selecionar")
    await r.open(pg, "#/buscar", ".ssum")
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".selbar")
    await pg.check('[data-input="sel-all"]')
    await pg.wait_for_timeout(300)
    r.check(bem["id"] not in await pg.evaluate(PRESSED), "Selecionar todos deixa os bens de fora")
    await ctx.close()
    await b.close()


main("selecionar", body)
