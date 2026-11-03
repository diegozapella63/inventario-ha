"""Novidades do produto na ficha do item: só as 3 mais recentes, com tipo, data, fonte e boato; guardada ao abrir de novo; Buscar de novo;
nada novo; erro da busca na web; IA desligada esconde o botão."""
import json
import os

from e2e_lib import OVERFLOW, TMP, FakeHA, main

NEWS = {"produto": "Smart TV 55 polegadas", "novidades": [
    {"tipo": "atualizacao", "titulo": "Atualização de software melhora o Wi-Fi", "resumo": "Versão nova corrige quedas de conexão.",
     "data": "2026-09-12", "fonte": "https://fabricante.exemplo/notas"},
    {"tipo": "recall", "titulo": "Troca da fonte de alimentação em um lote", "resumo": "Aparelhos de um lote podem esquentar.",
     "data": "2026-07", "fonte": "https://www.noticias.exemplo/recall"},
    {"tipo": "sucessor", "titulo": "Modelo novo da mesma linha", "resumo": "", "data": "2026-10", "fonte": "https://blog.exemplo/rumor", "boato": True},
    {"tipo": "atualizacao", "titulo": "Atualização antiga", "resumo": "", "data": "2025-12-01", "fonte": "https://fabricante.exemplo/antiga"},
]}


async def body(r, p):
    mock = os.path.join(TMP, "novidades.json")
    with open(mock, "w", encoding="utf-8") as f:
        json.dump(NEWS, f, ensure_ascii=False)
    r.start(search=False, env={"INV_MOCK_NEWS": mock})
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="azul")
    sent = []
    pg.on("request", lambda q: sent.append(q.method) if q.url.endswith("/api/news") else None)

    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    btn = pg.locator('dialog.sheet [data-act="item-news"]')
    r.eq(await btn.count(), 1, "a ficha tem o botão Novidades")
    r.eq((await btn.text_content()).strip(), "Novidades", "com o nome curto")
    await btn.click()
    await pg.wait_for_selector("dialog.modal .wbusy", timeout=4000)
    r.check("Procurando novidades" in await pg.text_content("dialog.modal .wbusy"), "enquanto busca, diz o que faz")
    await r.shot(pg, "buscando")
    await pg.wait_for_selector(".news li", timeout=10000)
    r.eq((await pg.text_content("dialog.modal .news-of")).strip(), "Smart TV 55 polegadas", "o nome do item no alto")
    rows = await pg.evaluate("""[...document.querySelectorAll('.news li')].map(li => ({
        tipo: [...li.querySelectorAll('.pill')].map(p => p.textContent), data: li.querySelector('.news-date')?.textContent || '',
        titulo: li.querySelector('b').textContent, site: li.querySelector('a').textContent, href: li.querySelector('a').href,
        alvo: li.querySelector('a').target }))""")
    r.eq([x["titulo"] for x in rows], ["Modelo novo da mesma linha", "Atualização de software melhora o Wi-Fi", "Troca da fonte de alimentação em um lote"],
         "só as 3 mais recentes, das mais novas para as mais antigas")
    r.eq(rows[1]["tipo"], ["Atualização"], "o tipo de cada uma")
    r.eq(rows[1]["data"], "12 set. 2026", "data por extenso, curta")
    r.eq(rows[2]["data"], "jul. 2026", "só mês e ano quando é o que se sabe")
    r.eq(rows[0]["tipo"], ["Modelo novo", "Boato"], "boato vem marcado")
    r.eq(rows[2]["site"], "noticias.exemplo", "a fonte aparece pelo site")
    r.check(rows[1]["href"] == "https://fabricante.exemplo/notas" and rows[1]["alvo"] == "_blank", "e abre a página fora do app")
    r.check(await pg.locator(".news .pill.warn", has_text="Recall").count() == 1, "recall em destaque")
    foot = await pg.text_content(".news-foot")
    r.check(foot.startswith("Buscado hoje"), f"quando foi buscado ({foot.strip()})")
    r.check(await pg.is_visible("[data-again]"), "Buscar de novo aparece")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "lista")
    await pg.click("dialog.modal .dlg-f [data-x]")
    await pg.wait_for_timeout(300)
    r.eq(await pg.locator("dialog.modal").count(), 0, "Fechar volta para a ficha")

    # abrir de novo não chama a IA outra vez
    n = len(sent)
    await pg.click('dialog.sheet [data-act="item-news"]')
    await pg.wait_for_selector(".news li", timeout=3000)
    r.eq(len(sent), n, "abrir de novo mostra o que já foi buscado, sem chamar a IA")
    await pg.click("[data-again]")
    await pg.wait_for_selector(".news li", timeout=10000)
    r.eq(len(sent), n + 1, "Buscar de novo chama a IA outra vez")
    await pg.click("dialog.modal .dlg-h [data-x]")
    await pg.wait_for_timeout(300)

    # nada novo
    with open(mock, "w", encoding="utf-8") as f:
        json.dump({"produto": "Sofá", "novidades": []}, f)
    await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-news"]')
    await pg.wait_for_selector("dialog.modal .news-foot", timeout=10000)
    r.check("Nada novo nos últimos 12 meses" in await pg.text_content('dialog.modal [data-slot="news"]'), "nada novo: diz em uma linha")
    r.check(", como Sofá." in await pg.text_content(".news-foot"), "diz como a IA identificou o produto quando o nome é outro")
    await r.shot(pg, "nada-novo")
    await ctx.close()

    # celular estreito e computador
    with open(mock, "w", encoding="utf-8") as f:
        json.dump(NEWS, f, ensure_ascii=False)
    for size, scheme in (("estreito", "light"), ("pc", "light")):
        ctx, pg = await r.page(b, size, scheme, accent="verde")
        await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
        await pg.click('dialog.sheet [data-act="item-news"]')
        await pg.wait_for_selector(".news li", timeout=10000)
        r.check(await pg.evaluate(OVERFLOW), f"[{size}] sem rolagem para o lado")
        fits = await pg.evaluate("[...document.querySelectorAll('.news a')].every(a => a.getBoundingClientRect().right <= a.closest('li').getBoundingClientRect().right + 1)")
        r.check(fits, f"[{size}] links dentro da borda")
        await r.shot(pg, f"lista-{size}")
        await ctx.close()

    # IA desligada: sem o botão
    r.api("PUT", "api/settings", {"ai": False})
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    r.eq(await pg.locator('[data-act="item-news"]').count(), 0, "IA desligada: sem Novidades")
    r.api("PUT", "api/settings", {"ai": True})
    await ctx.close()
    await b.close()
    r.app.stop()

    # com o Home Assistant de mentira: a IA sem busca na web
    ha = FakeHA()
    r.start(search=False, mock_ai=False, ha=ha)
    ha.ai_reply = lambda kind, payload: '{"erro": "sem_busca"}'
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="coral")
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-news"]')
    await pg.wait_for_selector("dialog.modal .formerr", timeout=10000)
    r.check("busca na web" in await pg.text_content("dialog.modal .formerr"), "sem busca na web: explica")
    err = await pg.text_content("dialog.modal .formerr")
    r.check(err.count("Mais, Integrações") == 1 and await pg.locator("dialog.modal .wtip").count() == 0, "e diz uma vez só onde escolher a IA de busca")
    r.check(await pg.is_visible("[data-again]"), "dá para tentar de novo")
    await r.shot(pg, "erro")
    ha.ai_reply = lambda kind, payload: json.dumps(NEWS)
    await pg.click("[data-again]")
    await pg.wait_for_selector(".news li", timeout=10000)
    r.eq(await pg.locator(".news li").count(), 3, "Tentar de novo traz as novidades")
    instr = ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]
    r.check("Produto: Smart TV 55 polegadas" in instr, "a IA recebe o nome do item")
    await ctx.close()
    await b.close()
    ha.stop()


main("novidades", body)
