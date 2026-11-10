"""Buscar › Selecionar (1.39.0; 1.40.0 como no ResolvIA): marcar vários itens e, num Alterar só, mudar de uma vez a
categoria, o cômodo e a zona (cada campo começa em Manter), com Desfazer. Todos vale para a lista inteira; mudar o filtro
tira da seleção o que sumiu; os bens não entram; o Voltar do celular e o X saem do Selecionar; a barra de baixo fica
acima da barra de abas, no celular estreito também."""
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
    r.check(await pg.is_disabled('.selbar [data-act="sel-change"]'), "sem nada marcado, o Alterar fica desligado")
    rows = pg.locator(".irow.selr")
    ids = [await rows.nth(k).get_attribute("data-id") for k in range(2)]
    await rows.nth(0).click()
    await rows.nth(1).click()
    r.eq(await pg.evaluate(PRESSED), ids, "tocar marca (e não abre a ficha)")
    r.check("#/i/" not in pg.url, "continua no Buscar")
    r.eq((await pg.text_content(".ssum.sel .sel-n")).strip(), "2 selecionados", "a conta dos marcados")
    r.eq((await pg.text_content(".selbar .btn")).strip(), "Alterar 2 itens", "um botão só, como no ResolvIA")
    tab = await pg.locator(".tabbar").bounding_box()
    bar = await pg.locator(".selbar").bounding_box()
    r.check(bar["y"] + bar["height"] <= tab["y"] + 1, f"a barra fica acima das abas ({bar}, {tab})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "selecionados")

    # Alterar: cada campo começa em Manter; a categoria e o cômodo juntos, e Desfazer volta os dois
    antes = {i["id"]: (i["room"], i["seq"], i["cat"]) for i in r.data()["items"] if i["id"] in ids}
    await pg.click('.selbar [data-act="sel-change"]')
    await pg.wait_for_selector("dialog.modal [data-bk]")
    r.eq((await pg.text_content("dialog.modal h2")).strip(), "Alterar 2 itens", "a janela")
    r.eq(await pg.evaluate("[...document.querySelectorAll('dialog.modal .chips input:checked')].map(i => i.value)"), ["__manter__", "__manter__"],
         "Cômodo e Categoria começam em Manter (zonas desligadas: sem Zona)")
    r.check(await pg.is_disabled("dialog.modal [data-ok]"), "sem mudança, o Aplicar fica desligado")
    await pg.locator("dialog.modal .chip", has=pg.locator('input[name="bk-cat"][value="decoracao"]')).click()
    await pg.locator("dialog.modal .chip", has=pg.locator('input[name="bk-room"][value="varanda"]')).click()
    r.check(await pg.is_visible("#bk-help"), "escolher outro cômodo avisa do código novo")
    r.check(not await pg.is_disabled("dialog.modal [data-ok]"), "com uma mudança, o Aplicar liga")
    await r.shot(pg, "alterar")
    await pg.click("dialog.modal [data-ok]")
    t = pg.locator(".toast", has_text="2 itens alterados")
    await t.wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq([(d[i]["cat"], d[i]["room"]) for i in ids], [("decoracao", "varanda")] * 2, "a categoria e o cômodo mudam juntos")
    r.eq(len({d[i]["seq"] for i in ids}), 2, "cada um com o seu número na Varanda")
    r.eq(await pg.locator(".irow.selr").count(), n - 2, "e saem da lista de Móveis (e da seleção)")
    r.eq((await pg.text_content(".ssum.sel .sel-n")).strip(), "Selecionar", "nada marcado")
    await t.locator("button").click()
    await pg.wait_for_timeout(700)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq({i: (d[i]["room"], d[i]["seq"], d[i]["cat"]) for i in ids}, antes, "Desfazer: o cômodo, o número e a categoria de antes")
    r.eq(await pg.locator(".irow.selr").count(), n, "e eles voltam para a lista")

    # Todos: a lista toda; de novo, Nenhum
    await pg.click('[data-act="sel-all"]')
    await pg.wait_for_timeout(300)
    r.eq(len(await pg.evaluate(PRESSED)), n, "Todos marca a lista toda")
    r.eq((await pg.text_content('[data-act="sel-all"]')).strip(), "Nenhum", "e vira Nenhum")
    await pg.click('[data-act="sel-all"]')
    await pg.wait_for_timeout(300)
    r.eq(len(await pg.evaluate(PRESSED)), 0, "Nenhum desmarca")
    await pg.click('[data-act="sel-all"]')
    await pg.wait_for_timeout(300)
    # só o cômodo de todos: Manter na categoria
    antes = {i["id"]: (i["room"], i["seq"], i["cat"]) for i in r.data()["items"] if i["cat"] == "moveis"}
    await pg.click('.selbar [data-act="sel-change"]')
    await pg.wait_for_selector("dialog.modal [data-bk]")
    await pg.locator("dialog.modal .chip", has=pg.locator('input[name="bk-room"][value="varanda"]')).click()
    await pg.click("dialog.modal [data-ok]")
    t = pg.locator(".toast", has_text="itens alterados")
    await t.first.wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.check(all(d[i]["room"] == "varanda" and d[i]["cat"] == "moveis" for i in antes), "todos vão para a Varanda, na mesma categoria")
    await t.first.locator("button").click()
    await pg.wait_for_timeout(700)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq({i: (d[i]["room"], d[i]["seq"], d[i]["cat"]) for i in antes}, antes, "Desfazer: cada um no seu cômodo, com o número de antes")

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

    # segurar o dedo num item (o contextmenu do celular) começa o Selecionar com ele marcado, sem abrir a ficha
    await r.open(pg, "#/buscar?cat=moveis", ".ssum")
    primeiro = await pg.locator("#results a.irow").first.get_attribute("href")
    await pg.locator("#results a.irow").first.click(button="right")
    await pg.wait_for_selector(".selbar")
    r.eq(await pg.evaluate(PRESSED), [primeiro.split("/")[-1]], "segurar: começa o Selecionar com o item marcado")
    r.check("#/i/" not in pg.url, "e não abre a ficha")
    await pg.locator(".irow.selr").nth(1).click(button="right")
    await pg.wait_for_timeout(300)
    r.eq(len(await pg.evaluate(PRESSED)), 1, "já selecionando, segurar não muda nada (o toque marca)")
    await pg.click('[data-act="sel-end"]')
    await pg.wait_for_timeout(300)
    await ctx.close()

    # zonas ligadas: Zona na mesma janela (uma nova e tirar a zona); celular estreito sem passar da largura
    r.api("PUT", "api/settings", {"zones": True})
    ctx, pg = await r.page(b, "estreito", "light", accent="verde")
    await r.open(pg, "#/buscar?room=sala", ".ssum")
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".selbar")
    rows = pg.locator(".irow.selr")
    ids = [await rows.nth(k).get_attribute("data-id") for k in range(3)]
    for k in range(3):
        await rows.nth(k).click()
    r.check(await pg.evaluate(OVERFLOW), "estreito: sem rolagem para o lado")
    cut = await pg.evaluate("[...document.querySelectorAll('.ssum.sel .btn, .selbar .btn')].filter(b => b.scrollWidth > b.clientWidth + 1).map(b => b.textContent.trim())")
    r.eq(cut, [], "estreito: os botões inteiros")
    await r.shot(pg, "estreito-zonas")
    await pg.click('.selbar [data-act="sel-change"]')
    await pg.wait_for_selector("#bk-zones")
    await pg.locator("#bk-zones .chip", has_text="Outra").click()
    r.check(await pg.is_disabled("dialog.modal [data-ok]"), "Outra sem nome: o Aplicar espera o nome")
    await pg.fill("#bk-zone-new", "Parede da TV")
    r.check(await pg.evaluate(OVERFLOW), "estreito: a janela sem rolagem para o lado")
    await r.shot(pg, "alterar-zona")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="3 itens alterados").wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq([d[i]["zone"] for i in ids], ["Parede da TV"] * 3, "a zona dos três")
    await pg.click('.selbar [data-act="sel-change"]')
    await pg.wait_for_selector("#bk-zones")
    r.check(await pg.locator("#bk-zones .chip", has_text="Parede da TV").count() == 1, "as zonas do cômodo viram opções")
    await pg.locator("#bk-zones .chip", has_text="Sem zona").click()
    # o aviso de antes ainda pode estar saindo (no GitHub, mais lento): espera o novo
    await pg.evaluate("document.querySelectorAll('.toast').forEach(t => t.dataset.velho = '1')")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast:not([data-velho])", has_text="3 itens alterados").wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq([d[i]["zone"] for i in ids], [""] * 3, "Sem zona tira a zona")
    await pg.click('[data-act="sel-end"]')
    await pg.wait_for_timeout(400)
    r.eq(await pg.locator(".selbar").count(), 0, "o X sai do Selecionar")
    await ctx.close()
    r.api("PUT", "api/settings", {"zones": False})

    # os bens ficam de fora (não têm cômodo nem categoria)
    r.api("POST", "api/rooms", {"kind": "bens"})
    bem = r.api("POST", "api/items", {"room": "bens", "name": "Carro hatch 2020", "cat": "veiculos", "value": 50000})["item"]
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/buscar?q=carro", ".ssum")
    r.eq(await pg.locator('[data-act="sel-start"]').count(), 0, "só bens na lista: sem Selecionar")
    await pg.locator("#results a.irow").first.click(button="right")
    await pg.wait_for_timeout(300)
    r.eq(await pg.locator(".selbar").count(), 0, "segurar um bem não começa o Selecionar")
    await r.open(pg, "#/buscar", ".ssum")
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".selbar")
    await pg.click('[data-act="sel-all"]')
    await pg.wait_for_timeout(300)
    r.check(bem["id"] not in await pg.evaluate(PRESSED), "Todos deixa os bens de fora")
    await ctx.close()
    await b.close()


main("selecionar", body)
