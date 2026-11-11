"""1.54.0: Recursos. Na ficha de um eletrônico, de uma utilidade ou de um veículo, a seção Recursos (1.55.0: com título e
ícone, como Tarefas no ResolvIA e Novidades) e o botão Ver recursos (na largura toda, como o Buscar novidades e o Nova tarefa) pede à IA o que o equipamento tem; a lista fica na ficha, com a fonte e Ver de novo. Um móvel
não tem o botão; com a IA desligada, some. Em Mais › Categorias, Utilidades e Veículos ficam fixas, como Eletrônicos."""
import e2e_lib
from e2e_lib import OVERFLOW, main

e2e_lib.SIZES.setdefault("cel390", (390, 844, True))


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel390", "dark")
    await r.open(pg, "#/i/sal-007", ".ihead")
    btn = pg.locator('dialog.sheet [data-act="item-rec"]')
    r.eq((await btn.inner_text()).strip(), "Ver recursos", "um eletrônico: o botão Ver recursos")
    # 1.55.0: uma seção com título e ícone, como Tarefas no ResolvIA e Novidades (antes, só o botão)
    sec = pg.locator('dialog.sheet [data-slot="item-rec"]')
    r.eq((await sec.locator(".inews-h").inner_text()).strip(), "Recursos", "a seção Recursos, com título")
    r.eq(await sec.locator('.inews-h use[href="#i-sliders"]').count(), 1, "com o ícone dela")
    r.eq((await sec.locator("> .muted").inner_text()).strip(), "Funções, modos e conexões deste modelo.", "e diz o que vem ali")
    w = await pg.evaluate("() => { const b = document.querySelector('dialog.sheet [data-act=\"item-rec\"]'), s = b.parentElement; return [Math.round(b.getBoundingClientRect().width), Math.round(s.getBoundingClientRect().width)]; }")
    r.check(abs(w[0] - w[1]) <= 2, f"na largura toda ({w})")
    await btn.click()
    await pg.wait_for_selector("dialog.sheet .rec-list li", timeout=8000)
    r.eq(await sec.locator(".inews-h").count(), 1, "o título não repete")
    itens = [t.split("\n")[0] for t in await pg.locator("dialog.sheet .rec-list li").all_inner_texts()]
    r.eq(itens, ["Wi-Fi", "Modo econômico", "Timer"], "os recursos que a IA disse")
    r.check("exemplo.com.br" in await pg.locator("dialog.sheet .rec-src").inner_text(), "com a fonte")
    r.eq((await pg.locator('dialog.sheet [data-act="item-rec"]').inner_text()).strip(), "Ver de novo", "e Ver de novo")
    r.check(await pg.evaluate(OVERFLOW), "nada passa da largura")
    await r.shot(pg, "recursos")
    # fechada e aberta de novo: os recursos continuam lá
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    await r.open(pg, "#/i/sal-007", ".ihead")
    await pg.wait_for_selector("dialog.sheet .rec-list li", timeout=4000)
    r.check(True, "aberta de novo: guardados")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    # um móvel: sem o botão
    await r.open(pg, "#/i/sal-001", ".ihead")
    r.eq(await pg.locator('dialog.sheet [data-act="item-rec"]').count(), 0, "um móvel: sem Recursos")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    # Categorias: Utilidades e Veículos fixas
    await r.open(pg, "#/categorias", "#p-cats")
    for nome in ("Eletrônicos", "Utilidades", "Veículos"):
        li = pg.locator("#p-cats li", has=pg.locator("b", has_text=nome))
        if await li.count():
            r.eq(await li.locator("button").count(), 0, f"{nome}: fixa, sem Renomear nem Apagar")
    # IA desligada: sem o botão
    await pg.evaluate("() => fetch('api/settings', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ai: false})})")
    await pg.reload()
    await pg.wait_for_timeout(800)
    await r.open(pg, "#/i/sal-007", ".ihead")
    r.eq(await pg.locator('dialog.sheet [data-act="item-rec"]').count(), 0, "IA desligada: sem Recursos")
    await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_recursos", body)
