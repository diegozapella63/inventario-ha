"""As caixas de seleção (1.35.0): web/selectsheet.js, o mesmo arquivo dos outros apps da família. Uma caixa não abre a
janela padrão do celular: abre uma janela no visual do app, de baixo para cima, com as opções em linhas e a atual
marcada na cor do app, no claro e no escuro. Escolher entra na própria caixa (o app ouve como sempre); o Voltar do
celular, o X e tocar fora fecham só ela, e o Voltar seguinte é o do app. No computador, no meio; o teclado também."""
from e2e_lib import main

HEX = "(h) => { h = h.trim().replace('#', ''); return `rgb(${parseInt(h.slice(0, 2), 16)}, ${parseInt(h.slice(2, 4), 16)}, ${parseInt(h.slice(4, 6), 16)})`; }"


async def tap(pg, sel):
    loc = pg.locator(sel).first
    await loc.scroll_into_view_if_needed()
    bx = await loc.bounding_box()
    await pg.touchscreen.tap(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
    await pg.wait_for_timeout(450)


async def body(r, p):
    r.start()
    b = await r.browser(p)
    for scheme in ("light", "dark"):
        ctx, pg = await r.page(b, "cel", scheme, accent="lilas")
        await r.open(pg, "#/")
        await r.open(pg, "#/buscar", ".ssum")
        room = '[data-input="search-room"]'
        r.eq(await pg.locator(room).evaluate("(s) => getComputedStyle(s).pointerEvents"), "none", f"{scheme}: a caixa nunca recebe o toque (a janela do celular não abre)")
        opts = [o.strip() for o in await pg.locator(f"{room} option").all_inner_texts()]
        n0 = await pg.locator("#view .irow").count()
        await tap(pg, room)
        sheet = pg.locator(".ss-wrap.in .ss-sheet")
        r.eq(await sheet.count(), 1, f"{scheme}: tocar abre a janela")
        r.eq((await sheet.locator(".ss-head b").inner_text()).strip(), "Cômodo", f"{scheme}: o título é o nome da caixa")
        r.eq([t.strip() for t in await sheet.locator(".ss-opt").all_inner_texts()], opts, f"{scheme}: as opções em linhas")
        r.eq([t.strip() for t in await sheet.locator(".ss-opt.on").all_inner_texts()], [opts[0]], f"{scheme}: a atual marcada")
        cores = await pg.evaluate(f"""(() => {{ const hex = {HEX}, c = getComputedStyle(document.documentElement), s = document.querySelector('.ss-sheet');
          return [getComputedStyle(s).backgroundColor, hex(c.getPropertyValue('--surface')), getComputedStyle(s.querySelector('.ss-opt.on svg')).color,
                  hex(c.getPropertyValue('--a')), getComputedStyle(s).color, hex(c.getPropertyValue('--ink'))]; }})()""")
        r.eq(cores[0], cores[1], f"{scheme}: o fundo das janelas do app")
        r.eq(cores[2], cores[3], f"{scheme}: a marca na cor do app")
        r.eq(cores[4], cores[5], f"{scheme}: o texto do app")
        bx = await sheet.bounding_box()
        r.check(abs(bx["y"] + bx["height"] - 854) < 2 and bx["width"] >= 383, f"{scheme}: de baixo para cima, na largura do celular ({bx})")
        await r.shot(pg, f"selecao-{scheme}")
        # escolher: entra na caixa e o app filtra
        await tap(pg, ".ss-opt >> nth=1")
        await pg.wait_for_timeout(500)
        r.eq(await pg.locator(".ss-wrap").count(), 0, f"{scheme}: escolher fecha")
        r.eq(await pg.input_value(room), await pg.locator(f"{room} option").nth(1).get_attribute("value"), f"{scheme}: a escolha entra na caixa")
        n1 = await pg.locator("#view .irow").count()
        r.check(0 < n1 < n0, f"{scheme}: e a busca filtra pelo cômodo ({n0} → {n1})")
        # Voltar, X e tocar fora: só a janela
        h = pg.url
        for como in ("Voltar", "X", "fora"):
            await tap(pg, room)
            r.eq(await pg.locator(".ss-wrap.in").count(), 1, f"{scheme} {como}: abre de novo")
            if como == "Voltar":
                await pg.go_back()
                await pg.wait_for_timeout(500)
            elif como == "X":
                await tap(pg, ".ss-x")
            else:
                await pg.touchscreen.tap(192, 40)
                await pg.wait_for_timeout(450)
            r.check(await pg.locator(".ss-wrap").count() == 0 and pg.url == h and await pg.locator("#view .irow").count() == n1, f"{scheme} {como}: fecha só ela, nada muda ({pg.url})")
        r.check(not [l for l in r.logs if "pageerror" in l], f"{scheme}: sem erros na página")
        await ctx.close()
    # numa janela do app: o Voltar fecha a caixa, o seguinte, a janela (Integrações › IA para ler fotos fica na tela)
    ctx, pg = await r.page(b, "cel", "dark")
    await r.open(pg, "#/")
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    ai = '[data-input="ai-entity"]'
    await tap(pg, ai)
    r.eq((await pg.locator(".ss-wrap.in .ss-head b").inner_text()).strip(), "IA para ler fotos", "Integrações: o título")
    want = await pg.locator(f"{ai} option").nth(1).get_attribute("value")
    await tap(pg, ".ss-opt >> nth=1")
    await pg.wait_for_timeout(700)
    r.eq(r.data()["settings"]["ai_entity"], want, "a escolha fica gravada (o app ouve como sempre)")
    await tap(pg, ai)
    await pg.go_back()
    await pg.wait_for_timeout(500)
    r.check(await pg.locator(".ss-wrap").count() == 0 and "#/config/integracoes" in pg.url, f"Voltar fecha só a caixa ({pg.url})")
    await pg.go_back()
    await pg.wait_for_timeout(600)
    r.check("#/config" not in pg.url, f"o Voltar seguinte é o do app ({pg.url})")
    await ctx.close()
    # computador: no meio da tela; o teclado
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/buscar", ".ssum")
    room = '[data-input="search-room"]'
    loc = pg.locator(room)
    bx = await loc.bounding_box()
    await pg.mouse.click(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
    await pg.wait_for_timeout(400)
    sb = await pg.locator(".ss-wrap.in .ss-sheet").bounding_box()
    wb = await pg.locator(".ss-wrap").bounding_box()  # a tela toda, sem a faixa da barra de rolagem
    r.check(sb and abs(sb["x"] + sb["width"] / 2 - (wb["x"] + wb["width"] / 2)) < 2 and abs(sb["y"] + sb["height"] / 2 - 450) < 2 and sb["width"] <= 440 and wb["width"] > 1200, f"computador: no meio da tela ({sb}, {wb})")
    await r.shot(pg, "selecao-pc")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(400)
    r.check(await pg.locator(".ss-wrap").count() == 0 and await loc.evaluate("(s) => document.activeElement === s"), "computador: Esc fecha e o foco volta para a caixa")
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(300)
    await pg.keyboard.press("ArrowDown")
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(600)
    r.eq(await loc.evaluate("(s) => s.selectedIndex"), 1, "computador: Enter abre, as setas e o Enter escolhem")
    await ctx.close()
    await b.close()


main("selecao", body)
