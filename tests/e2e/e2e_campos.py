"""1.51.0, o padrão da família: os campos de texto aberto (Detalhes) aumentam puxando o canto e guardam o tamanho no
aparelho (textareas.js, igual em todos os apps); aberto de novo, o campo volta como ficou. A caixa da conversa (que cresce
sozinha) fica de fora. No celular, os botões das telas de Mais na largura do cartão (Nova categoria, Conferir novidades), o
Limpar novidades no fim da tela, o Digitalizar com IA na largura toda e, sem foto, Adicionar foto e Buscar na internet do
mesmo tamanho. 1.52.0: o Adicionar da barra de baixo só com o + (o nome no aria-label), no meio da barra."""
import e2e_lib
from e2e_lib import OVERFLOW, main

e2e_lib.SIZES.setdefault("cel390", (390, 844, True))
LARG = "(s) => [...document.querySelectorAll(s)].map(e => Math.round(e.getBoundingClientRect().width))"


async def body(r, p):
    r.start(search=False)
    it = next(i for i in r.data()["items"] if not i.get("photos"))
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel390", "dark")
    # o Adicionar só com o +, no meio da barra
    await r.open(pg, "#/", ".tabbar .plus")
    add = await pg.evaluate("""() => { const b = document.querySelector('.tabbar .tab-add'), c = (e) => { const r = e.getBoundingClientRect(); return r.top + r.height / 2; };
      return [b.textContent.trim(), b.getAttribute('aria-label'), Math.round(Math.abs(c(b.querySelector('.plus')) - c(document.querySelector('.tabbar [data-tab=home] .ic')) - 0))]; }""")
    r.check(add[0] == "" and add[1] == "Adicionar", f"Adicionar só com o + ({add})")
    await r.shot(pg, "barra")
    # Detalhes: aumentado, fica do tamanho na próxima vez
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-details")
    r.eq(await pg.eval_on_selector("#f-details", "(e) => getComputedStyle(e).resize"), "vertical", "Detalhes: dá para aumentar")
    await pg.eval_on_selector("#f-details", "(e) => { e.style.height = '240px'; }")  # como puxar o canto
    await pg.wait_for_timeout(700)
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-details")
    h = await pg.eval_on_selector("#f-details", "(e) => Math.round(parseFloat(e.style.height))")
    r.eq(h, 240, "aberto de novo, do tamanho que ficou")
    # Digitalizar com IA na largura toda (com uma foto); sem foto, os dois botões do mesmo tamanho
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    ws = await pg.evaluate(LARG, "dialog.sheet .gal-acts > .btn")
    r.check(len(ws) == 2 and ws[0] == ws[1], f"sem foto: Adicionar foto e Buscar na internet do mesmo tamanho ({ws})")
    await r.shot(pg, "sem-foto")
    # Mais › Categorias e Novidades: os botões na largura do cartão; o Limpar no fim
    await r.open(pg, "#/categorias", "#p-cats")
    nova = await pg.evaluate(LARG, '[data-act="cat-new"]')
    card = await pg.evaluate(LARG, "#p-cats .opts > li")
    r.check(nova and card and abs(nova[0] - (card[0] - 8)) <= 12, f"Nova categoria na largura do cartão ({nova}, {card})")
    await r.open(pg, "#/novidades", "#p-news")
    ids = await pg.evaluate("[...document.querySelectorAll('#view section.panel')].map(s => s.id)")
    r.eq(ids[-1], "p-news-clear", "Limpar novidades no fim da tela")
    conf = await pg.evaluate(LARG, '[data-act="news-all"]')
    r.check(conf and conf[0] > 300, f"Conferir novidades na largura do cartão ({conf})")
    r.check(await pg.evaluate(OVERFLOW), "nada passa da largura")
    await r.shot(pg, "novidades", full_page=True)
    await ctx.close()
    # no computador, como antes: 280 px
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/categorias", "#p-cats")
    r.eq(await pg.evaluate(LARG, '[data-act="cat-new"]'), [280], "no computador, 280 px")
    await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_campos", body)
