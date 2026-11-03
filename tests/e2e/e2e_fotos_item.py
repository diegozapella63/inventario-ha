"""Várias fotos no item: enviar várias de uma vez, o limite de 12, a capa, remover, tirar foto (celular), colar com Ctrl+V,
arrastar e soltar, arquivo que não é imagem (PDF, texto, JPG estragado, HEIC), foto ainda enviando e as fotos do cômodo no editor."""
import asyncio
import os
import shutil

from e2e_lib import TMP, helpers, main

PHOTOS = sorted(os.listdir(os.path.join(helpers.FIXTURE, "photos")))
SRCS = "[...document.querySelectorAll('[data-slot=photos] .ph img')].map(i => decodeURIComponent(i.getAttribute('src').split('/').pop()))"

# um arquivo de verdade (as fotos da casa de teste, pelo próprio servidor) ou um arquivo inventado, num DataTransfer
MAKE_FILES = """async (specs) => {
  const dt = new DataTransfer();
  for (const [name, type, from, text] of specs) {
    const blob = from ? await (await fetch(from)).blob() : new Blob([text || 'não é uma imagem'], { type });
    dt.items.add(new File([blob], name, { type }));
  }
  return dt;
}"""
PASTE = "async (specs) => { const dt = await (" + MAKE_FILES + """)(specs);
  const ev = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
  (document.activeElement || document.body).dispatchEvent(ev);
  return ev.defaultPrevented; }"""
DROP = "async ([sel, specs]) => { const dt = await (" + MAKE_FILES + """)(specs);
  const el = document.querySelector(sel);
  el.dispatchEvent(new DragEvent('dragover', { dataTransfer: dt, bubbles: true, cancelable: true }));
  const over = el.classList.contains('over');
  el.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
  return [over, el.classList.contains('over')]; }"""


def jpg(name):
    return [f"{name}", "image/jpeg", f"photos/{name}", None]


async def photos_settled(pg, n, timeout=15000):
    await pg.wait_for_function(f"document.querySelectorAll('[data-slot=photos] .ph img').length === {n} && !document.querySelector('[data-slot=photos] .ph.loading')", timeout=timeout)


async def toast_text(pg, timeout=4000):
    try:
        await pg.wait_for_selector(".toast", timeout=timeout)
    except Exception:  # noqa: BLE001
        return ""
    return " | ".join(t.strip() for t in await pg.locator(".toast .tmsg").all_text_contents())


async def body(r, p):
    r.start(search=False)
    # 13 fotos de verdade para escolher de uma vez (cópias das fotos da casa de teste)
    folder = os.path.join(TMP, "fotos-item")
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    thirteen = []
    for k in range(13):
        dst = os.path.join(folder, f"foto-{k + 1:02d}.jpg")
        shutil.copyfile(os.path.join(helpers.FIXTURE, "photos", PHOTOS[k % len(PHOTOS)]), dst)
        thirteen.append(dst)
    texto = helpers.write_file(os.path.join(folder, "lista.txt"), "sofá, mesa, cadeira")
    r.api("POST", "api/rooms", {"name": "Garagem", "code": "GAR"})
    b = await r.browser(p, camera=True)
    ctx, pg = await r.page(b, "pc", "light", accent="coral")

    # -- enviar várias de uma vez; capa; remover
    await r.open(pg, "#/c/garagem", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    r.eq(await pg.locator('[data-ed="roomphotos"]').count(), 0, "cômodo sem fotos: sem o botão Fotos do cômodo")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-ed="upload"]')
    chooser = await fc.value
    r.check(chooser.is_multiple(), "Enviar foto deixa escolher várias de uma vez")
    await chooser.set_files(thirteen[:3])
    await photos_settled(pg, 3)
    labels = await pg.evaluate("[...document.querySelectorAll('[data-slot=photos] .ph')].map(p => (p.querySelector('.cover, .mkcover') || {}).textContent)")
    r.eq(labels, ["Capa", "Usar como capa", "Usar como capa"], "três fotos: a primeira é a capa, as outras podem virar capa")
    first = await pg.evaluate(SRCS)
    await pg.click('[data-ed="cover"][data-i="2"]')
    after = await pg.evaluate(SRCS)
    r.eq(after, [first[2], first[0], first[1]], "Usar como capa leva a foto para o começo")
    await pg.click('[data-ed="rmphoto"][data-i="1"]')
    r.eq(await pg.evaluate(SRCS), [first[2], first[1]], "o X tira só aquela foto")
    r.eq(await pg.get_attribute('[data-ed="rmphoto"][data-i="0"]', "aria-label"), "Remover foto 1", "o X diz qual foto remove")

    # -- colar (Ctrl+V) e arrastar e soltar
    prevented = await pg.evaluate(PASTE, [jpg("varanda-1.jpg")])
    await photos_settled(pg, 3)
    r.check(prevented, "colar uma imagem (Ctrl+V) adiciona a foto")
    over = await pg.evaluate(DROP, ["form[data-ed-form]", [jpg("quarto-1.jpg"), jpg("escritorio-1.jpg")]])
    await photos_settled(pg, 5)
    r.eq(over, [True, False], "arrastar por cima marca a área; soltar tira a marca")
    r.eq(len(await pg.evaluate(SRCS)), 5, "soltar duas imagens adiciona as duas")
    await r.shot(pg, "cinco-fotos")

    # -- foto ainda enviando: Salvar espera
    async def slow(route):
        await asyncio.sleep(1.5)
        await route.continue_()
    await pg.route("**/api/photos", slow)
    await pg.evaluate(PASTE, [jpg("sala-3.jpg")])
    await pg.wait_for_selector("[data-slot=photos] .ph.loading", timeout=3000)
    await pg.fill("#f-name", "Caixa de ferramentas")
    await pg.click('[data-ed="save"]')
    t = await toast_text(pg)
    r.check("Espere as fotos terminarem de enviar" in t and await pg.locator("#f-name").count() == 1, f"com uma foto enviando, Salvar pede para esperar ({t})")
    await photos_settled(pg, 6)
    await pg.unroute("**/api/photos", slow)
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    it = r.item_named("Caixa de ferramentas")
    r.check(it and len(it["photos"]) == 6 and it["photos"][0] == after[0], f"salvo com as seis fotos, a capa primeiro ({it and len(it['photos'])})")
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    r.eq(await pg.locator("dialog.sheet .gal-thumbs button").count(), 6, "a ficha mostra as seis fotos")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)

    # -- o que não é imagem
    await r.open(pg, "#/c/garagem", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    await pg.evaluate(DROP, ["form[data-ed-form]", [["manual.pdf", "application/pdf", None, "%PDF-1.4"]]])
    await pg.wait_for_timeout(400)
    r.eq(len(await pg.evaluate(SRCS)), 0, "soltar um PDF não vira foto")
    t = await toast_text(pg, 1500)
    r.check("imagem" in t, f"soltar um PDF avisa que precisa ser uma imagem ({t})")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-ed="upload"]')
    await (await fc.value).set_files(texto)
    await pg.wait_for_timeout(400)
    await r.shot(pg, "nao-imagem")
    r.eq(len(await pg.evaluate(SRCS)), 0, "escolher um .txt não vira foto")
    await pg.evaluate(PASTE, [["estragada.jpg", "image/jpeg", None, "isto não é um JPG"]])
    t = await toast_text(pg)
    await pg.wait_for_function("!document.querySelector('[data-slot=photos] .ph.loading')", timeout=8000)
    r.check("Não deu para abrir esta imagem" in t and len(await pg.evaluate(SRCS)) == 0, f"JPG estragado: aviso e nenhuma foto ({t})")
    await pg.wait_for_selector(".toast", state="detached", timeout=10000)
    await pg.evaluate(PASTE, [["IMG_0001.HEIC", "image/heic", None, "ftypheic"]])
    t = await toast_text(pg)
    r.check("HEIC" in t, f"foto em HEIC: diz o que fazer ({t})")
    await pg.wait_for_function("!document.querySelector('[data-slot=photos] .ph.loading')", timeout=8000)
    await pg.wait_for_selector(".toast", state="detached", timeout=10000)

    # -- limite de 12
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-ed="upload"]')
    await (await fc.value).set_files(thirteen)
    await photos_settled(pg, 12, timeout=30000)
    await pg.wait_for_timeout(300)
    r.eq(len(await pg.evaluate(SRCS)), 12, "escolher 13 fotos: entram 12, o limite do item")
    r.eq(await pg.locator('[data-ed="web"]').count(), 0, "com 12 fotos, some o Buscar na internet")
    await r.shot(pg, "doze-fotos")
    t = await toast_text(pg, 1500)
    r.check("12" in t, f"escolher 13 fotos avisa que o limite é 12 ({t})")
    await pg.fill("#f-name", "Caixa de parafusos")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    r.eq(len(r.item_named("Caixa de parafusos")["photos"]), 12, "o item é salvo com as 12")

    # -- colar fora de uma janela de foto não faz nada; colar em Editar cômodo adiciona ao cômodo
    await r.open(pg, "#/", ".tag")
    r.check(await pg.evaluate(PASTE, [jpg("sala-1.jpg")]) is False and await pg.locator("dialog[open]").count() == 0,
            "colar uma imagem no Início não abre nada")
    await r.open(pg, "#/c/garagem", ".rhead")
    await pg.click('.rhead-actions [data-act="room-edit"]')
    await pg.wait_for_selector("#re-name")
    await pg.evaluate(PASTE, [jpg("lavanderia-1.jpg")])
    await pg.wait_for_function("document.querySelectorAll('[data-slot=rphotos] .rph img').length === 1", timeout=10000)
    await pg.click('[data-re="save"]')
    await pg.wait_for_selector("#re-name", state="detached", timeout=5000)
    r.eq(len(next(x for x in r.data()["rooms"] if x["id"] == "garagem")["photos"]), 1, "colar em Editar cômodo adiciona a foto ao cômodo")
    await ctx.close()

    # -- celular: fotos do cômodo e Tirar foto
    ctx, pg = await r.page(b, "cel", "dark", accent="coral")
    await r.open(pg, "#/c/sala", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector('[data-ed="roomphotos"]')
    await pg.click('[data-ed="roomphotos"]')
    await pg.wait_for_selector("dialog .pick")
    r.eq(await pg.locator("dialog .pick input").count(), 3, "Fotos do cômodo: as três fotos da sala")
    ok = pg.locator("dialog[open]:last-of-type [data-ok]")
    r.check(await ok.is_disabled(), "Usar fotos começa desligado")
    await pg.locator("dialog .pick label").nth(0).click()
    await pg.locator("dialog .pick label").nth(2).click()
    r.eq((await ok.text_content()).strip(), "Usar 2 fotos", "o botão conta as escolhidas")
    await r.shot(pg, "fotos-do-comodo")
    await ok.click()
    await photos_settled(pg, 2)
    r.eq(await pg.evaluate(SRCS), ["sala-1.jpg", "sala-3.jpg"], "as duas entram no item, na ordem")
    await pg.click('[data-ed="roomphotos"]')
    await pg.wait_for_selector("dialog .pick")
    r.eq(await pg.locator("dialog .pick input").count(), 1, "de novo: só a que falta")
    await pg.locator("dialog .pick label").first.click()
    await ok.click()
    await photos_settled(pg, 3)
    r.eq(await pg.locator('[data-ed="roomphotos"]').count(), 0, "todas usadas: o botão some")
    await pg.select_option("#f-room", "varanda")
    r.eq(await pg.locator('[data-ed="roomphotos"]').count(), 1, "trocar para a Varanda: o botão volta, com as fotos dela")
    await pg.select_option("#f-room", "garagem")
    await pg.wait_for_timeout(100)
    await pg.select_option("#f-room", "lavanderia")
    await pg.click('[data-ed="roomphotos"]')
    await pg.wait_for_selector("dialog .pick")
    await pg.click('dialog[open]:last-of-type .dlg-f [data-x]')
    await pg.wait_for_selector("dialog .pick", state="detached")
    r.eq(len(await pg.evaluate(SRCS)), 3, "Cancelar nas fotos do cômodo não muda nada")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-ed="camera"]')
    chooser = await fc.value
    r.check(await chooser.element.get_attribute("capture") is not None, "Tirar foto abre a câmera do celular")
    await chooser.set_files(thirteen[0])
    await photos_settled(pg, 4)
    r.eq(len(await pg.evaluate(SRCS)), 4, "a foto tirada entra depois das outras")
    await r.shot(pg, "celular")
    await ctx.close()
    await b.close()


main("fotos_item", body)
