"""Cômodos: a lista, Organizar (ordem), Novo cômodo com código sugerido, a página do cômodo, editar, excluir e as zonas."""
import os

from e2e_lib import OVERFLOW, helpers, main


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="lilas")

    await r.open(pg, "#/comodos", ".ilist.rooms")
    rows = await pg.evaluate("[...document.querySelectorAll('.ilist.rooms .croom .nm')].map(e => e.textContent.trim())")
    r.eq(rows, ["Sala de estar", "Cozinha", "Quarto", "Escritório", "Lavanderia", "Varanda"], "lista de cômodos na ordem da casa")
    meta = await pg.text_content(".ilist.rooms .croom .meta")
    r.check("12 itens" in meta, f"número de itens do cômodo ({meta.strip()})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "lista")

    # organizar
    await pg.click('[data-act="rooms-organize"]')
    await pg.wait_for_selector(".rooms-hint")
    await pg.click('[data-act="room-down"][data-room="sala"]')
    await pg.wait_for_timeout(500)
    r.eq([x["id"] for x in r.data()["rooms"]][:2], ["cozinha", "sala"], "a seta muda a ordem e grava")
    await r.shot(pg, "organizar")
    await pg.click('[data-act="room-up"][data-room="sala"]')
    await pg.wait_for_timeout(500)
    r.eq(r.data()["rooms"][0]["id"], "sala", "e volta")
    await pg.click('[data-act="rooms-organize"]')

    # novo cômodo
    await pg.click('#view [data-act="room-new"]')
    await pg.wait_for_selector("#rn-name")
    await pg.fill("#rn-name", "Área de serviço")
    r.eq(await pg.input_value("#rn-code"), "ARE", "código sugerido pelo nome")
    await pg.click("dialog.modal [data-ok]")
    await pg.wait_for_selector(".rhead h1")
    r.eq(await pg.text_content(".rhead h1"), "Área de serviço", "abre o cômodo novo")
    r.check("#/c/area-de-servico" in pg.url, "endereço do cômodo")
    r.check(await pg.locator("#view .empty").count() == 1, "cômodo vazio convida a adicionar")
    await r.shot(pg, "novo-vazio")

    # editar: nome, código, foto; e excluir vazio
    await pg.click('.rhead-actions [data-act="room-edit"]')
    await pg.wait_for_selector("#re-name")
    await pg.fill("#re-name", "Área")
    await pg.fill("#re-code", "AS")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-re="upload"]')
    await (await fc.value).set_files(os.path.join(helpers.FIXTURE, "photos", "lavanderia-1.jpg"))
    await pg.wait_for_function("document.querySelectorAll('dialog .phs .ph img, dialog .re-photos img').length > 0 || document.querySelectorAll('dialog img').length > 0", timeout=10000)
    await pg.click('[data-re="save"]')
    await pg.wait_for_timeout(800)
    room = next(x for x in r.data()["rooms"] if x["id"] == "area-de-servico")
    r.eq((room["name"], room["code"], len(room["photos"])), ("Área", "AS", 1), "editar grava nome, código e foto")
    r.check(await pg.locator(".strip .ph img").count() >= 1, "a foto aparece no cômodo")
    await pg.click('.rhead-actions [data-act="room-edit"]')
    await pg.wait_for_selector("#re-name")
    await pg.click('[data-re="delete"]')
    await pg.wait_for_selector('[data-r="1"]')
    await pg.click('[data-r="1"]')
    await pg.wait_for_timeout(800)
    r.check(not any(x["id"] == "area-de-servico" for x in r.data()["rooms"]), "excluir um cômodo vazio")

    # cômodo com itens: não exclui
    await r.open(pg, "#/c/varanda", ".rhead")
    await pg.click('.rhead-actions [data-act="room-edit"]')
    await pg.wait_for_selector("#re-name")
    await pg.click('[data-re="delete"]')
    t = pg.locator(".toast", has_text="Mova ou exclua")
    await t.wait_for(timeout=4000)
    r.check(any(x["id"] == "varanda" for x in r.data()["rooms"]), f"cômodo com itens não é excluído ({(await t.text_content()).strip()})")
    await pg.click('[data-re="cancel"]')
    await pg.wait_for_timeout(300)

    # página do cômodo: filtro, ordem pelos códigos, fotos
    await r.open(pg, "#/c/sala", ".rhead")
    tags = await pg.evaluate("[...document.querySelectorAll('#view .irow .mt')].map(e => e.textContent.trim())")
    r.check(tags == sorted(tags), f"itens na ordem dos códigos ({tags[:4]})")
    r.check(await pg.locator(".strip .ph").count() >= 3, "fotos do cômodo no alto")
    await pg.fill('[data-input="room-filter"]', "tv")
    await pg.wait_for_timeout(300)
    names = await pg.evaluate("[...document.querySelectorAll('#view .irow .nm')].map(e => e.textContent)")
    r.check(names and all("TV" in n or "tv" in n.lower() for n in names), f"filtro do cômodo ({names})")
    await pg.fill('[data-input="room-filter"]', "")
    await r.shot(pg, "sala")
    await pg.click(".strip .ph")
    await pg.wait_for_selector("dialog.viewer")
    r.check(await pg.locator("dialog.viewer .vimg img").count() == 1, "a foto do cômodo abre grande")
    vlist = await pg.locator("dialog.viewer .vlist a").count()
    r.check(vlist >= 1, f"com os itens que aparecem nela ({vlist})")
    await r.shot(pg, "visualizador")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)

    # zonas ligadas: itens separados por zona, com subtotal
    r.api("PUT", "api/settings", {"zones": True})
    await r.open(pg, "#/c/sala", ".rhead")
    zonas = await pg.evaluate("[...document.querySelectorAll('#view .zone-h h3')].map(e => e.textContent.trim())")
    r.check(len(zonas) >= 3 and "Sofá" in zonas, f"zonas ligadas: itens separados por zona ({zonas})")
    await r.shot(pg, "sala-zonas")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    r.check(await pg.locator("#f-zone").count() == 1, "o cadastro ganha o campo Zona")
    await pg.click('[data-ed="cancel"]')
    r.api("PUT", "api/settings", {"zones": False})
    await r.open(pg, "#/c/sala", ".rhead")
    r.eq(await pg.locator("#view .zone-h").count(), 0, "zonas desligadas: lista única")
    await ctx.close()

    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/c/escritorio", ".rhead")
    side = await pg.evaluate("[...document.querySelectorAll('.side .side-room .rn')].map(e => e.textContent.trim())")
    r.check("Escritório" in side, "barra lateral do computador lista os cômodos")
    await r.shot(pg, "escritorio-pc")
    await ctx.close()
    await b.close()


main("comodos", body)
