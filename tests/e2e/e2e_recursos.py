"""1.54.0: Recursos. Na ficha de um eletrônico, de uma utilidade ou de um veículo, a seção Recursos (1.55.0: com título e
ícone, como Tarefas no ResolvIA e Novidades) e o botão Ver recursos (na largura toda, como o Buscar novidades e o Nova tarefa) pede à IA o que o equipamento tem; a lista fica na ficha, com a fonte e Ver de novo. Um móvel
não tem o botão; com a IA desligada, some. Em Mais › Categorias, Utilidades e Veículos ficam fixas, como Eletrônicos.
1.65.0: Novidades › Eletrônicos, os recursos de todos os eletrônicos: a lista e a janela de um; 1.68.0: Conferir novidades ›
Só eletrônicos busca os que faltam."""
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
    # 1.65.0: Novidades › Eletrônicos: cada eletrônico com os recursos (ou Ainda não buscado), entre Apps do celular e Conferir
    await r.open(pg, "#/novidades", "#p-news-rec")
    await pg.wait_for_selector("#p-news-rec .nlist .nrow", timeout=8000)
    secs = await pg.evaluate("() => [...document.querySelectorAll('#view section.panel')].map(s => s.id)")
    r.check(secs.index("p-news-rec") == secs.index("p-news") - 1 and secs.index("p-news-rec") > secs.index("p-news-list"), f"depois dos Equipamentos, antes de Conferir ({secs})")
    r.eq((await pg.text_content("#p-news-rec h2")).strip(), "Eletrônicos", "a seção Eletrônicos")
    r.eq(await pg.locator('#p-news-rec h2 use[href="#i-sliders"]').count(), 1, "com o ícone dos recursos")
    ROWS = "() => [...document.querySelectorAll('#p-news-rec .nrow')].map(b => [b.querySelector('b').textContent, b.querySelector('.nm').textContent, [...b.querySelectorAll('.pill')].map(p => p.textContent)])"
    rows = await pg.evaluate(ROWS)
    tv = next(x for x in rows if x[0].startswith("Smart TV"))
    r.check(" · 3 recursos · hoje" in tv[1] and tv[2] == ["3"] and rows[0] == tv, f"a TV, já vista na ficha, com 3 recursos, no alto ({tv})")
    r.check(len(rows) > 1 and all(x[1].endswith("Ainda não buscado") and x[2] == [] for x in rows[1:]), f"os outros ainda não buscados, embaixo ({rows[1:3]})")
    r.eq(await pg.locator('#p-news-rec .btn').count(), 0, "1.68.0: sem botão na seção: a busca fica em Conferir novidades")
    await r.shot(pg, "eletronicos")
    # Conferir novidades › Só eletrônicos (1.68.0): os recursos dos que ainda não têm; o Conferido das novidades fica
    corpos = []
    pg.on("request", lambda q: corpos.append(q.post_data) if q.url.endswith("/api/news/all") else None)
    await pg.click('#p-news [data-act="news-all"][data-so="recursos"]')
    await pg.locator(".toast", has_text="Recursos de").wait_for(timeout=20000)
    await pg.wait_for_timeout(400)
    r.eq(corpos, ['{"so":"recursos"}'], "pede só os recursos")
    rows = await pg.evaluate(ROWS)
    r.check(all(" recursos · hoje" in x[1] and x[2] == ["3"] for x in rows), f"Só eletrônicos: cada eletrônico com os recursos ({rows[:2]})")
    r.eq(r.api("GET", "api/news")["ultima"], None, "e não conta como conferência das novidades")
    await pg.click('#p-news [data-act="news-all"][data-so="recursos"]')
    await pg.locator(".toast", has_text="Todos os eletrônicos já têm os recursos").wait_for(timeout=10000)
    r.check(True, "de novo: nada a buscar")
    # um toque abre os recursos, guardados, com Ver de novo e Ver item
    await pg.locator("#p-news-rec .nrow").first.click()
    await pg.wait_for_selector("dialog.modal .rec-list li", timeout=6000)
    r.eq((await pg.text_content("dialog.modal .dlg-h h2")).strip(), "Recursos", "a janela dos recursos")
    r.eq([t.split("\n")[0] for t in await pg.locator("dialog.modal .rec-list li").all_inner_texts()], ["Wi-Fi", "Modo econômico", "Timer"], "os guardados")
    r.eq([t.strip() for t in await pg.locator("dialog.modal .dlg-f .btn:visible").all_inner_texts()], ["Ver de novo", "Ver item"], "Ver de novo e Ver item")
    await r.shot(pg, "eletronicos-janela")
    await pg.click("dialog.modal [data-item]")
    await pg.wait_for_selector("dialog.sheet .ihead", timeout=6000)
    r.check(True, "Ver item abre a ficha")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    r.check(await pg.evaluate(OVERFLOW), "nada passa da largura")
    # IA desligada: sem o botão
    await pg.evaluate("() => fetch('api/settings', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ai: false})})")
    await pg.reload()
    await pg.wait_for_timeout(800)
    await r.open(pg, "#/i/sal-007", ".ihead")
    r.eq(await pg.locator('dialog.sheet [data-act="item-rec"]').count(), 0, "IA desligada: sem Recursos")
    await pg.keyboard.press("Escape")
    await pg.evaluate("() => { location.hash = '#/novidades'; }")
    await pg.wait_for_timeout(800)
    r.eq(await pg.locator("#p-news-rec").count(), 0, "IA desligada: sem a seção Eletrônicos")
    await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_recursos", body)
