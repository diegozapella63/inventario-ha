"""Sugestões de zona no visual do app (1.41.0), como no GerencIA: nenhum campo usa a lista do celular (<datalist> ligado
por list=, que no Android abre fora do padrão). O campo com data-sug mostra logo abaixo, dentro da janela, até 6
sugestões das zonas do cômodo que combinam com o que foi digitado (sem acento); ao entrar num campo que já tem uma
zona, as outras. Tocar numa preenche o campo (e o app ouve como se fosse digitado), o teclado fica; sair do campo, Esc
ou escolher fecha. No computador, as setas e o Enter. Vale no Editar item, no Mover e no Catalogar (a zona de cada item
lido, embaixo da linha dele). Claro e escuro, 384 e 320 px, nada passando da largura."""
import os

from e2e_lib import OVERFLOW, helpers, main

HEX = "(h) => { h = h.trim().replace('#', ''); return `rgb(${parseInt(h.slice(0, 2), 16)}, ${parseInt(h.slice(2, 4), 16)}, ${parseInt(h.slice(4, 6), 16)})`; }"
SUGS = "() => [...document.querySelectorAll('.sug-box .sug-op')].map(b => b.textContent.trim())"
# a lista: embaixo do campo (ou da linha dele), da mesma largura, inteira na tela e na janela, linhas de 44 px no mínimo
GEOM = """(sel) => { const i = document.querySelector(sel), box = document.querySelector('.sug-box');
  if (!i || !box) return 'sem lista';
  const row = i.closest('.frow2') || i, a = row.getBoundingClientRect(), b = box.getBoundingClientRect(), bad = [];
  if (b.top < a.bottom - 1 || b.top > a.bottom + 10) bad.push('não está logo abaixo: ' + Math.round(a.bottom) + ' / ' + Math.round(b.top));
  if (Math.abs(b.left - a.left) > 1 || Math.abs(b.width - a.width) > 1) bad.push('largura diferente do campo: ' + Math.round(a.width) + ' / ' + Math.round(b.width));
  if (b.left < 0 || b.right > innerWidth) bad.push('passa da tela');
  const d = box.closest('dialog'); if (!d || !d.contains(i)) bad.push('fora da janela do campo');
  for (const o of box.querySelectorAll('.sug-op')) { const r = o.getBoundingClientRect(); if (r.height < 44) bad.push('linha baixa: ' + r.height); if (o.scrollWidth > o.clientWidth + 1) bad.push('texto cortado'); }
  return bad.join('; ') || 'ok'; }"""


async def tap(pg, sel):
    loc = pg.locator(sel).first
    await loc.scroll_into_view_if_needed()
    bx = await loc.bounding_box()
    await pg.touchscreen.tap(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
    await pg.wait_for_timeout(350)


def zones_of(r, room, skip=""):
    seen = []
    for i in sorted((i for i in r.data()["items"] if i["room"] == room), key=lambda i: i["seq"]):
        z = i.get("zone") or ""
        if z and z not in seen:
            seen.append(z)
    return [z for z in seen if z != skip]


async def body(r, p):
    r.start(search=False)
    r.api("PUT", "api/settings", {"zones": True})
    b = await r.browser(p)
    for size, scheme in (("cel", "dark"), ("cel", "light"), ("estreito", "light")):
        tag = f"{size} {scheme}"
        sala = zones_of(r, "sala")
        ctx, pg = await r.page(b, size, scheme, accent="lilas")
        # -- Editar item: a zona
        await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
        await pg.click('dialog.sheet [data-act="item-edit"].primary')
        await pg.wait_for_selector("#f-zone")
        r.eq(await pg.evaluate("document.querySelectorAll('input[list]').length"), 0, f"{tag}: nenhum campo com a lista do celular (list=)")
        r.eq(await pg.get_attribute("#f-zone", "data-sug"), "f-zones", f"{tag}: a Zona tem as sugestões do app")
        r.eq(await pg.locator(".sug-box").count(), 0, f"{tag}: fechada até tocar no campo")
        cur = await pg.input_value("#f-zone")
        await tap(pg, "#f-zone")
        r.eq(await pg.evaluate(SUGS), [z for z in sala if z != cur][:6], f"{tag}: tocar mostra as outras zonas da sala ({cur} é a atual)")
        r.eq(await pg.evaluate(GEOM, "#f-zone"), "ok", f"{tag}: logo abaixo do campo, da mesma largura, linhas de 44 px")
        cores = await pg.evaluate(f"""(() => {{ const hex = {HEX}, c = getComputedStyle(document.documentElement), box = document.querySelector('.sug-box'), o = box.querySelector('.sug-op');
          return [getComputedStyle(box).backgroundColor === hex(c.getPropertyValue('--surface')), getComputedStyle(o).color === hex(c.getPropertyValue('--ink')),
                  getComputedStyle(o).fontSize, getComputedStyle(box).borderRadius === getComputedStyle(document.querySelector('#f-zone')).borderRadius]; }})()""")
        r.eq(cores, [True, True, "16px", True], f"{tag}: no visual do app (fundo, texto, 16 px, cantos do campo)")
        r.check(await pg.evaluate(OVERFLOW), f"{tag}: nada passa da largura")
        await r.shot(pg, f"editar-{size}-{scheme}")
        # digitar filtra, sem acento e sem maiúscula
        await pg.fill("#f-zone", "ESTA")
        await pg.wait_for_timeout(150)
        r.eq(await pg.evaluate(SUGS), [z for z in sala if "esta" in z.lower()], f"{tag}: digitar filtra (ESTA)")
        await pg.fill("#f-zone", "pare")
        await pg.wait_for_timeout(150)
        r.eq(await pg.evaluate(SUGS), ["Parede"], f"{tag}: pare")
        await pg.fill("#f-zone", "Zona que não existe")
        await pg.wait_for_timeout(150)
        r.eq(await pg.locator(".sug-box").count(), 0, f"{tag}: nenhuma combina: a lista some")
        await pg.fill("#f-zone", "es")
        await pg.wait_for_timeout(150)
        # tocar escolhe: o campo recebe, a lista fecha, o foco fica no campo (o teclado do celular não fecha)
        await tap(pg, ".sug-op >> text=Estante")
        r.eq(await pg.input_value("#f-zone"), "Estante", f"{tag}: tocar preenche o campo")
        r.check(await pg.locator(".sug-box").count() == 0 and await pg.evaluate("document.activeElement && document.activeElement.id") == "f-zone",
                f"{tag}: e a lista fecha, com o foco no campo")
        # trocar o cômodo troca as sugestões
        await tap(pg, "#f-room")
        await pg.locator(".ss-wrap.in .ss-opt", has_text="Cozinha").click()
        await pg.wait_for_timeout(450)
        await pg.fill("#f-zone", "")
        await tap(pg, "#f-zone")
        r.eq(await pg.evaluate(SUGS), zones_of(r, "cozinha")[:6], f"{tag}: na Cozinha, as zonas da Cozinha")
        # sair do campo fecha
        await tap(pg, "#f-name")
        await pg.wait_for_timeout(250)
        r.eq(await pg.locator(".sug-box").count(), 0, f"{tag}: sair do campo fecha a lista")
        if size == "cel" and scheme == "dark":
            # salvar grava a zona escolhida pela sugestão (no cômodo de antes)
            await tap(pg, "#f-room")
            await pg.locator(".ss-wrap.in .ss-opt", has_text="Sala").first.click()
            await pg.wait_for_timeout(450)
            await pg.fill("#f-zone", "")
            await tap(pg, "#f-zone")
            await tap(pg, ".sug-op >> text=Rack")
            await pg.click('[data-ed="save"]')
            await pg.wait_for_selector("#f-zone", state="detached", timeout=8000)
            it = next(i for i in r.data()["items"] if i["id"] == "sal-001")
            r.check(it["zone"] == "Rack" and it["room"] == "sala", f"{tag}: Salvar grava a zona escolhida ({it['room']}, {it['zone']})")
        await ctx.close()

    # -- Mover: as zonas do cômodo de destino
    ctx, pg = await r.page(b, "cel", "light", accent="verde")
    await r.open(pg, "#/i/sal-002", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-zone")
    r.eq(await pg.evaluate("document.querySelectorAll('input[list]').length"), 0, "Mover: sem a lista do celular")
    cur = await pg.input_value("#mv-zone")
    await tap(pg, "#mv-zone")
    r.eq(await pg.evaluate(SUGS), [z for z in zones_of(r, "sala") if z != cur][:6], "Mover: as outras zonas do cômodo")
    r.eq(await pg.evaluate(GEOM, "#mv-zone"), "ok", "Mover: logo abaixo do campo")
    await r.shot(pg, "mover")
    await tap(pg, "#mv-room")
    await pg.locator(".ss-wrap.in .ss-opt", has_text="Quarto").click()
    await pg.wait_for_timeout(450)
    await tap(pg, "#mv-zone")
    r.eq(await pg.evaluate(SUGS), zones_of(r, "quarto")[:6], "Mover: outro cômodo, as zonas dele")
    await tap(pg, ".sug-op >> nth=0")
    want = zones_of(r, "quarto")[0]
    r.eq(await pg.input_value("#mv-zone"), want, "Mover: tocar preenche")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="Movido para Quarto").wait_for(timeout=5000)
    it = next(i for i in r.data()["items"] if i["id"] == "sal-002")
    r.check(it["room"] == "quarto" and it["zone"] == want, f"Mover grava o cômodo e a zona escolhida ({it['room']}, {it['zone']})")
    await ctx.close()

    # -- Catalogar: a zona da foto e a de cada item lido (embaixo da linha dele)
    ctx, pg = await r.page(b, "cel", "dark", accent="azul")
    await r.open(pg, "#/c/quarto", ".rhead")
    antes = {i["id"] for i in r.data()["items"]}
    await pg.click('.rhead-actions [data-act="catalog"]')
    await pg.wait_for_selector('[data-ct="upload"]')
    r.eq(await pg.get_attribute("#c-zone", "data-sug"), "c-zones", "Catalogar: a zona da foto tem as sugestões do app")
    await tap(pg, "#c-zone")
    r.eq(await pg.evaluate(SUGS), zones_of(r, "quarto")[:6], "Catalogar: as zonas do cômodo")
    r.eq(await pg.evaluate(GEOM, "#c-zone"), "ok", "Catalogar: logo abaixo do campo")
    await r.shot(pg, "catalogar-zona")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(250)
    r.check(await pg.locator(".sug-box").count() == 0 and await pg.locator("#c-zone").is_visible(), "Esc fecha só a lista (a janela fica)")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-ct="upload"]')
    await (await fc.value).set_files(os.path.join(helpers.FIXTURE, "photos", "escritorio-1.jpg"))
    await pg.wait_for_selector(".cat-photo img", timeout=10000)
    await pg.click('[data-ct="read"]')
    await pg.wait_for_selector(".found li", timeout=15000)
    r.eq(await pg.evaluate("document.querySelectorAll('input[list]').length"), 0, "revisão: sem a lista do celular")
    z0 = '[data-ri="0"][data-rf="zone"]'
    await pg.fill(z0, "")
    await tap(pg, z0)
    r.eq(await pg.evaluate(SUGS), zones_of(r, "quarto")[:6], "revisão: a zona de cada item, com as zonas do cômodo")
    r.eq(await pg.evaluate(GEOM, z0), "ok", "revisão: a lista embaixo da linha do item, da largura dela")
    r.check(await pg.evaluate(OVERFLOW), "revisão: nada passa da largura")
    await r.shot(pg, "catalogar-revisar")
    first = (await pg.locator(".sug-op").first.text_content()).strip()
    await tap(pg, ".sug-op >> nth=0")
    r.eq(await pg.input_value(z0), first, "revisão: tocar preenche a zona do item")
    for k in ("1", "2"):
        await pg.uncheck(f'.fcheck[data-ri="{k}"]')
    await pg.click('[data-ct="add"]')
    await pg.locator(".toast", has_text="adicionado").wait_for(timeout=6000)
    novo = [i for i in r.data()["items"] if i["id"] not in antes]
    r.check(len(novo) == 1 and novo[0]["zone"] == first and novo[0]["room"] == "quarto", f"Adicionar grava a zona escolhida ({[(i['name'], i['zone']) for i in novo]})")
    await ctx.close()

    # -- computador: as setas e o Enter (o Enter escolhe, não salva); o Esc fecha só a lista
    ctx, pg = await r.page(b, "pc", "light", accent="coral")
    await r.open(pg, "#/i/sal-003", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-zone")
    await pg.fill("#f-zone", "")
    await pg.click("#f-zone")
    await pg.wait_for_timeout(200)
    opts = await pg.evaluate(SUGS)
    await pg.keyboard.press("ArrowDown")
    await pg.keyboard.press("ArrowDown")
    r.eq(await pg.locator(".sug-op.on").count(), 1, "computador: as setas marcam uma")
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(200)
    r.check(await pg.input_value("#f-zone") == opts[1] and await pg.locator("#f-zone").is_visible(), f"computador: o Enter escolhe ({opts[1]}) e o Editar continua aberto")
    await pg.fill("#f-zone", "")
    await pg.wait_for_timeout(150)
    r.check(await pg.locator(".sug-box").count() == 1, "apagar mostra a lista de novo")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(250)
    r.check(await pg.locator(".sug-box").count() == 0 and await pg.locator("#f-zone").is_visible(), "computador: o Esc fecha só a lista")
    await pg.click("#f-name")
    await pg.click("#f-zone")
    await pg.wait_for_timeout(150)
    await pg.locator(".sug-op").first.click()
    r.eq(await pg.input_value("#f-zone"), opts[0], "computador: o clique escolhe")
    await r.shot(pg, "pc")
    await ctx.close()
    await b.close()


main("sugestoes", body)
