"""As caixas de seleção (1.35.0): web/selectsheet.js, o mesmo arquivo dos outros apps da família. Uma caixa não abre a
janela padrão do celular: abre uma janela no visual do app, de baixo para cima, com as opções em linhas e a atual
marcada na cor do app, no claro e no escuro. Escolher entra na própria caixa (o app ouve como sempre); o Voltar do
celular, o X e tocar fora fecham só ela, e o Voltar seguinte é o do app. No computador, no meio; o teclado também.
A caixa fechada (1.41.0) é igual aos outros campos: 44 px de altura (38 nas linhas do Catalogar, como os campos de lá),
os mesmos cantos, a seta na cor do texto apagado do tema (claro e escuro) e o texto inteiro, em 384 e 320 px."""
from e2e_lib import main

HEX = "(h) => { h = h.trim().replace('#', ''); return `rgb(${parseInt(h.slice(0, 2), 16)}, ${parseInt(h.slice(2, 4), 16)}, ${parseInt(h.slice(4, 6), 16)})`; }"


# cada caixa visível: altura, cantos (os do campo de texto), a seta (cor do --muted do tema), o texto inteiro e o toque barrado
CLOSED = """() => { const bad = [], muted = getComputedStyle(document.documentElement).getPropertyValue('--muted').trim().replace('#', '').toLowerCase();
  const inp = document.createElement('input'); inp.className = 'input'; document.body.append(inp); const rad = getComputedStyle(inp).borderRadius; inp.remove();
  const c = document.createElement('canvas').getContext('2d'); let n = 0;
  for (const s of document.querySelectorAll('select')) {
    if (!s.offsetParent) continue; n++;
    const cs = getComputedStyle(s), r = s.getBoundingClientRect(), name = s.getAttribute('aria-label') || s.id || s.dataset.input;
    const want = s.closest('.found') ? 38 : 44;
    if (Math.round(r.height) !== want) bad.push(name + ': altura ' + r.height);
    if (cs.borderRadius !== rad) bad.push(name + ': cantos ' + cs.borderRadius + ' (campo ' + rad + ')');
    if (!cs.backgroundImage.toLowerCase().includes('%23' + muted)) bad.push(name + ': seta fora da cor do tema');
    if (cs.pointerEvents !== 'none') bad.push(name + ': a caixa recebe o toque');
    c.font = cs.fontSize + ' ' + cs.fontFamily;
    const t = (s.options[s.selectedIndex] || {}).text || '';
    if (c.measureText(t).width > r.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) + 1) bad.push(name + ': texto cortado');
    if (r.right > innerWidth + 1 || r.left < -1) bad.push(name + ': passa da tela');
  }
  return n ? bad : ['nenhuma caixa']; }"""


async def tap(pg, sel):
    loc = pg.locator(sel).first
    await loc.evaluate("e => e.scrollIntoView({ block: 'center' })")  # longe da barra de baixo, que fica por cima
    await pg.wait_for_timeout(100)
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
    await pg.wait_for_selector(ai)
    await pg.wait_for_selector('[data-slot="voice-panel"] .opts, [data-slot="voice-panel"] .status', timeout=8000)
    await pg.wait_for_timeout(600)  # os painéis de baixo (Falar, Uso da IA) terminam de carregar: a caixa não muda de lugar
    await tap(pg, ai)
    r.eq((await pg.locator(".ss-wrap.in .ss-head b").inner_text()).strip(), "IA para ler fotos", "Integrações: o título")
    want = await pg.locator(f"{ai} option").nth(1).get_attribute("value")
    await tap(pg, ".ss-opt >> nth=1")
    await pg.wait_for_timeout(700)
    r.eq(r.data()["settings"]["ai_entity"], want, "a escolha fica gravada (o app ouve como sempre)")
    await tap(pg, ai)
    await pg.go_back()
    await pg.wait_for_timeout(500)
    r.check(await pg.locator(".ss-wrap").count() == 0 and pg.url.endswith("#/config"), f"Voltar fecha só a caixa ({pg.url})")
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
    # a caixa fechada, igual aos outros campos: nas telas e nas janelas, claro e escuro, 384 e 320 px (em Opções, o Horário
    # e o A cada do Conferir sozinho)
    r.api("PUT", "api/settings", {"news_every": 7})
    for size in ("cel", "estreito"):
        for scheme in ("light", "dark"):
            ctx, pg = await r.page(b, size, scheme, accent="verde")
            for h in ("#/buscar", "#/config/integracoes", "#/config/opcoes"):
                await r.open(pg, h)
                await pg.wait_for_timeout(500)
                bad = await pg.evaluate(CLOSED)
                r.check(not bad, f"[{size} {scheme}] {h}: as caixas fechadas iguais aos campos" + (f": {bad[:3]}" if bad else ""))
            for h, opener, wait in (("#/i/sal-001", 'dialog.sheet [data-act="item-edit"].primary', "#f-cat"), ("#/i/sal-002", 'dialog.sheet [data-act="item-move"]', "#mv-room"),
                                    ("#/c/quarto", '.rhead-actions [data-act="catalog"]', "#c-room")):
                await r.open(pg, h, "dialog.sheet h1, .rhead")
                await pg.click(opener)
                await pg.wait_for_selector(wait)
                await pg.wait_for_timeout(400)
                bad = await pg.evaluate(CLOSED)
                r.check(not bad, f"[{size} {scheme}] {wait}: as caixas fechadas iguais aos campos" + (f": {bad[:3]}" if bad else ""))
                if wait == "#f-cat" and size == "cel":
                    await r.shot(pg, f"fechada-{scheme}")
            await ctx.close()
    await b.close()


main("selecao", body)
