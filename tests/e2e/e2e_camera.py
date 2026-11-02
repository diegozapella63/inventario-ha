"""Câmera dentro do app (como no ResolvIA): no app do Home Assistant no Android abre a câmera na tela; no navegador do celular, a do aparelho."""
from e2e_lib import ANDROID_APP_UA, ANDROID_CHROME_UA, main

VIDEO_ON = "(() => { const v = document.querySelector('dialog.camera video'); return v && v.videoWidth > 0; })()"
NO_MEDIA = "Object.defineProperty(navigator, 'mediaDevices', {value: undefined, configurable: true})"


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p, camera=True)

    # Catalogar no app do Android: Tirar foto e Escolher foto; uma foto, sem Pronto
    ctx, pg = await r.page(b, "cel", "dark", accent="verde", ua=ANDROID_APP_UA, perms=["camera"])
    await r.open(pg, "#/", ".tabbar .plus")
    await pg.click(".tabbar .plus")
    await pg.click('[data-go="catalog"]')
    await pg.wait_for_selector('[data-ct="upload"]')
    tiles = await pg.evaluate("[...document.querySelectorAll('dialog .phs .add')].map(b => b.textContent.trim())")
    r.eq(tiles[:2], ["Tirar foto", "Escolher foto"], "Catalogar: Tirar foto e Escolher foto")
    await r.shot(pg, "catalogar")
    await pg.click('[data-ct="camera"]')
    await pg.wait_for_selector("dialog.camera")
    await pg.wait_for_function(VIDEO_ON, timeout=10000)
    r.check(await pg.is_enabled('[data-cam="shoot"]'), "câmera aberta, botão de fotografar ligado")
    r.eq(await pg.locator('[data-cam="done"]').count(), 0, "Catalogar: uma foto só, sem Pronto")
    await pg.wait_for_timeout(300)
    await r.shot(pg, "camera")
    await pg.click('[data-cam="shoot"]')
    await pg.wait_for_selector("dialog.camera", state="detached", timeout=8000)
    await pg.wait_for_selector(".cat-photo img", timeout=10000)
    r.check(await pg.is_enabled('[data-ct="read"]'), "a foto entra no Catalogar e Ler foto liga")
    await ctx.close()

    # editor: várias fotos, Pronto (n); Voltar e X fecham sem foto
    ctx, pg = await r.page(b, "cel", "light", ua=ANDROID_APP_UA, perms=["camera"])
    await r.open(pg, "#/", ".tabbar .plus")
    await pg.click(".tabbar .plus")
    await pg.click('[data-go="item"]')
    await pg.wait_for_selector('[data-ed="camera"]')
    await pg.click('[data-ed="camera"]')
    await pg.wait_for_selector("dialog.camera")
    await pg.wait_for_function(VIDEO_ON, timeout=10000)
    await pg.click('[data-cam="shoot"]')
    await pg.wait_for_timeout(500)
    await pg.click('[data-cam="shoot"]')
    await pg.wait_for_timeout(500)
    t = (await pg.text_content('[data-cam="done"]')).strip()
    r.check(t == "Pronto (2)" and await pg.locator("[data-cam-shots] img").count() == 2, f"duas fotos, com as miniaturas ({t})")
    await r.shot(pg, "camera-duas")
    await pg.click('[data-cam="done"]')
    await pg.wait_for_selector("dialog.camera", state="detached")
    await pg.wait_for_function("document.querySelectorAll('.phs .ph img').length === 2", timeout=10000)
    r.check(True, "as duas fotos entram no item")
    await pg.click('[data-ed="camera"]')
    await pg.wait_for_selector("dialog.camera")
    await pg.wait_for_timeout(600)
    await pg.go_back()
    await pg.wait_for_selector("dialog.camera", state="detached", timeout=5000)
    r.check(await pg.locator(".phs .ph img").count() == 2 and await pg.locator("#f-name").count() == 1, "Voltar fecha a câmera e fica no item")
    await pg.click('[data-ed="camera"]')
    await pg.wait_for_selector("dialog.camera")
    await pg.wait_for_timeout(400)
    await pg.click('[data-cam="close"]')
    await pg.wait_for_selector("dialog.camera", state="detached")
    r.eq(await pg.locator(".phs .ph img").count(), 2, "X fecha sem foto")
    await pg.fill("#f-name", "Foto da câmera")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    it = r.item_named("Foto da câmera")
    r.check(it is not None and len(it["photos"]) == 2, "item salvo com as duas fotos")
    await ctx.close()

    # sem câmera (http sem permissão, aparelho sem câmera): diz por quê e oferece Escolher foto
    ctx, pg = await r.page(b, "cel", "dark", ua=ANDROID_APP_UA, init=NO_MEDIA)
    await r.open(pg, "#/", ".tabbar .plus")
    await pg.click(".tabbar .plus")
    await pg.click('[data-go="catalog"]')
    await pg.wait_for_selector('[data-ct="camera"]')
    await pg.click('[data-ct="camera"]')
    await pg.wait_for_selector(".cam-msg")
    msg = await pg.text_content(".cam-msg p")
    r.check(len(msg.strip()) > 10, f"sem câmera, diz por quê ({msg.strip()})")
    await r.shot(pg, "sem-camera")
    async with pg.expect_file_chooser():
        await pg.click('[data-cam="pick"]')
    r.check(True, "Escolher foto abre a galeria")
    await ctx.close()

    # navegador do celular (não o app): continua a câmera do aparelho
    ctx, pg = await r.page(b, "cel", "dark", ua=ANDROID_CHROME_UA)
    await r.open(pg, "#/", ".tabbar .plus")
    await pg.click(".tabbar .plus")
    await pg.click('[data-go="item"]')
    await pg.wait_for_selector('[data-ed="camera"]')
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-ed="camera"]')
    chooser = await fc.value
    r.eq(await pg.locator("dialog.camera").count(), 0, "navegador do celular usa a câmera do aparelho")
    r.check(await chooser.element.get_attribute("capture") is not None, "o seletor pede a câmera (capture)")
    await ctx.close()

    # computador: sem Tirar foto
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/", ".tag")
    await pg.click('.side [data-act="item-new"], [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    r.eq(await pg.locator('[data-ed="camera"]').count(), 0, "computador: sem Tirar foto, só Enviar")
    await ctx.close()
    await b.close()


main("camera", body)
