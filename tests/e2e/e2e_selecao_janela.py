"""As caixas de seleção dentro de uma janela (1.38.4): a janela do app é modal (fica por cima de tudo e o resto não recebe
o toque), então a folha das opções (selectsheet.js) também abre como janela modal, por cima dela. No Editar item, o
Cômodo e a Categoria mudam pelo toque, no celular, e pelo clique, no computador; o Voltar do celular fecha só a folha;
no Mover, o cômodo também muda."""
from e2e_lib import OVERFLOW, main

# o que está no ponto do meio da primeira opção não marcada: a folha (e não a janela de baixo)
EM_CIMA = """() => { const o = document.querySelector('.ss-wrap.in .ss-opt:not(.on)'); if (!o) return 'sem folha';
  const b = o.getBoundingClientRect(), hit = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
  return hit && hit.closest('.ss-wrap') ? 'folha' : (hit ? hit.tagName + '.' + hit.className : 'nada'); }"""


async def tap(pg, sel):
    loc = pg.locator(sel).first
    await loc.scroll_into_view_if_needed()
    bx = await loc.bounding_box()
    await pg.touchscreen.tap(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
    await pg.wait_for_timeout(450)


async def body(r, p):
    r.start()
    b = await r.browser(p)
    for scheme in ("dark", "light"):
        ctx, pg = await r.page(b, "cel", scheme, accent="coral")
        await r.open(pg, "#/i/qua-001", "dialog.sheet h1")
        await pg.click('dialog.sheet [data-act="item-edit"]')
        # 1.97.0: no Editar item, o Cômodo e a Categoria são botões na tela (sem a folha); quem guarda o valor é a caixa de
        # seleção, fora da vista
        await pg.wait_for_selector("#f-room-g .pk")
        r.eq(await pg.locator(".ss-wrap").count(), 0, f"{scheme}: o Cômodo e a Categoria direto na tela, sem folha")
        r.check(await pg.locator("#f-room-g .pk.on").count() == 1 and (await pg.locator("#f-room-g .pk.on").inner_text()).strip() == "Quarto", f"{scheme}: o cômodo do item vem marcado")
        r.check(await pg.evaluate("[...document.querySelectorAll('#f-room, #f-cat')].every((s) => s.getBoundingClientRect().width <= 1 && getComputedStyle(s).pointerEvents === 'none')"), f"{scheme}: as caixas de seleção fora da vista")
        cols = await pg.evaluate("[...document.querySelectorAll('#f-room-g .pk')].slice(0, 2).map((b) => { const r = b.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.width), Math.round(r.height)]; })")
        r.check(cols[0][0] == cols[1][0] and abs(cols[0][1] - cols[1][1]) <= 1 and cols[0][2] >= 50, f"{scheme}: dois por linha, do mesmo tamanho, com 50 px ({cols})")
        if scheme == "dark":
            await r.shot(pg, "editar-comodo")
        await pg.locator("#f-room-g .pk", has_text="Cozinha").click()
        await pg.wait_for_timeout(300)
        r.eq(await pg.input_value("#f-room"), "cozinha", f"{scheme}: o Cômodo muda")
        r.eq([t.strip() for t in await pg.locator("#f-room-g .pk.on").all_inner_texts()], ["Cozinha"], f"{scheme}: e só ele fica marcado")
        await pg.locator("#f-cat-g .pk", has_text="Eletrônicos").click()
        await pg.wait_for_timeout(300)
        r.eq(await pg.input_value("#f-cat"), "eletronicos", f"{scheme}: a Categoria muda")
        r.eq(await pg.get_attribute("#f-cat-g .pk.on", "aria-pressed"), "true", f"{scheme}: marcada para quem ouve a tela")
        r.check(await pg.evaluate(OVERFLOW), f"{scheme}: sem rolagem para o lado")
        await ctx.close()
    # o Editar item gravado com o cômodo e a categoria novos (no claro, a cama ficou como estava)
    ctx, pg = await r.page(b, "cel", "dark")
    await r.open(pg, "#/i/qua-001", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"]')
    await pg.wait_for_selector("#f-room")
    await pg.locator("#f-cat-g .pk", has_text="Eletrônicos").click()
    await pg.wait_for_timeout(300)
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("#f-room", state="detached", timeout=6000)
    r.eq(next(i for i in r.data()["items"] if i["id"] == "qua-001")["cat"], "eletronicos", "Salvar alterações grava a categoria escolhida")
    # Mover: o cômodo de destino também abre por cima
    await pg.wait_for_selector('dialog.sheet [data-act="item-move"]')
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-room")
    await pg.wait_for_timeout(500)  # a janela termina de subir
    await pg.wait_for_selector(".toast", state="detached", timeout=10000)  # o aviso do Salvar não fica por cima da caixa
    await tap(pg, "#mv-room")
    r.eq(await pg.evaluate(EM_CIMA), "folha", "Mover: a folha fica por cima")
    await pg.locator(".ss-wrap.in .ss-opt", has_text="Escritório").click()
    await pg.wait_for_timeout(400)
    r.eq(await pg.input_value("#mv-room"), "escritorio", "Mover: o cômodo muda")
    # o Voltar do celular fecha só a folha; o Mover continua aberto, com o que mudou
    await tap(pg, "#mv-room")
    await pg.go_back()
    await pg.wait_for_timeout(500)
    r.check(await pg.locator(".ss-wrap").count() == 0 and await pg.locator("#mv-room").is_visible(), "o Voltar fecha só a folha")
    r.eq(await pg.input_value("#mv-room"), "escritorio", "e nada se perde")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await ctx.close()
    # no computador, pelo clique; o Esc fecha só a folha
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-room")
    await pg.wait_for_timeout(400)
    await pg.click("#mv-room", force=True)
    await pg.wait_for_timeout(400)
    r.eq(await pg.evaluate(EM_CIMA), "folha", "computador: a folha fica por cima")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(400)
    r.check(await pg.locator(".ss-wrap").count() == 0 and await pg.locator("#mv-room").is_visible(), "computador: o Esc fecha só a folha")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(400)
    await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"]')
    await pg.wait_for_selector("#f-cat-g .pk")
    await pg.locator("#f-cat-g .pk", has_text="Decoração").first.click()
    await pg.wait_for_timeout(300)
    r.eq(await pg.input_value("#f-cat"), "decoracao", "computador: a Categoria muda pelo clique")
    await ctx.close()
    await b.close()


main("selecao_janela", body)
