"""Mais > Novidades: conferir todos (a IA escolhe os equipamentos das categorias marcadas, sem móveis), progresso e Parar,
a lista com recall primeiro, abrir um item, os deixados de fora, categorias gravadas e a aba some com a IA desligada."""
from e2e_lib import OVERFLOW, main

ROWS = "[...document.querySelectorAll('#p-news-list > div > .nlist .nrow')].map(b => [b.querySelector('b').textContent, b.querySelector('.nm').textContent, [...b.querySelectorAll('.pill')].map(p => p.textContent)])"


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")
    await r.open(pg, "#/mais/novidades", ".more-tabs")
    await pg.wait_for_selector(".chips", timeout=8000)
    tabs = await pg.evaluate("[...document.querySelectorAll('.more-tabs [role=tab]')].map(t => t.textContent.trim())")
    r.eq(tabs, ["Dados", "Novidades", "Integrações", "Aparência", "Opções"], "a aba Novidades em Mais")
    r.eq(await pg.get_attribute("#mt-novidades", "aria-selected"), "true", "abre pelo endereço")
    chips = await pg.evaluate("[...document.querySelectorAll('.chip')].map(c => [c.textContent.trim(), c.querySelector('input').checked])")
    marcadas = [n for n, on in chips if on]
    r.eq(marcadas, ["Eletrônicos", "Cozinha e bar", "Saúde", "Utilidades", "Outros"], "de início, as categorias que costumam ter equipamentos")
    r.check(("Móveis", False) in [tuple(c) for c in chips], "Móveis fica desmarcada")
    r.check("Toque em Conferir novidades" in await pg.text_content('[data-slot="news-list"]'), "antes da primeira vez, diz o que fazer")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "antes", full_page=True)

    # conferir todos
    await pg.click('[data-act="news-all"]')
    await pg.wait_for_selector(".njob .prog", timeout=8000)
    r.check(await pg.is_disabled('[data-act="news-all"]'), "enquanto confere, o botão fica desligado")
    await pg.wait_for_function("document.querySelector('.njob span:nth-child(2)') && /Conferindo \\d+ de \\d+/.test(document.querySelector('.njob').textContent)", timeout=10000)
    r.check(True, "mostra quantos já foram e qual está sendo conferido")
    await r.shot(pg, "conferindo")
    await pg.wait_for_selector("#p-news-list .nlist .nrow", timeout=60000)
    await pg.locator(".toast", has_text="Conferidos").wait_for(timeout=10000)
    rows = await pg.evaluate(ROWS)
    nomes = [x[0] for x in rows]
    r.check("Smart TV 55 polegadas" in nomes and "Geladeira frost free inox" in nomes, f"a IA escolheu os aparelhos ({len(nomes)})")
    r.check(not any(n in nomes for n in ("Fruteira de madeira", "Jogo de panelas antiaderentes (5 peças)", "Cesto de roupas de vime")),
            "sem fruteira, panelas nem cesto")
    r.check(all("novidades" in x[1] and "hoje" in x[1] for x in rows), "cada um com quantas novidades e quando")
    r.check(all(x[2] == ["3"] for x in rows), f"o número de novidades ao lado ({rows[0][2]})")
    fora = await pg.text_content(".news-out summary")
    r.check(fora.startswith("Deixados de fora pela IA ("), f"os que a IA deixou de fora ficam recolhidos ({fora.strip()})")
    foot = await pg.text_content('[data-slot="news-job"]')
    r.check("Conferido hoje" in foot and "com novidades" in foot, f"resumo da última conferência ({foot.strip()})")
    r.check(await pg.is_enabled('[data-act="news-all"]'), "o botão volta")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "depois", full_page=True)

    # abrir um da lista: o que já foi conferido, sem chamar a IA
    sent = []
    pg.on("request", lambda q: sent.append(q.url) if q.method == "POST" and "/api/news" in q.url else None)
    await pg.locator(".nrow", has_text="Smart TV 55 polegadas").first.click()
    await pg.wait_for_selector("dialog.modal .news li", timeout=4000)
    r.eq(sent, [], "abrir um item mostra o resultado guardado, sem chamar a IA")
    r.check("Buscado hoje" in await pg.text_content(".news-foot"), "com a data")
    await pg.click("dialog.modal .dlg-h [data-x]")
    await pg.wait_for_timeout(300)

    # os deixados de fora: dá para conferir um por um
    await pg.click(".news-out summary")
    out_rows = pg.locator(".news-out .nrow")
    r.check(await out_rows.count() >= 1, "abre a lista dos deixados de fora")
    nome = (await out_rows.first.locator("b").text_content()).strip()
    r.check("Ainda não conferido" in await out_rows.first.text_content(), "ainda não conferido")
    await out_rows.first.click()
    await pg.wait_for_selector("dialog.modal .news li", timeout=10000)
    r.check(len(sent) == 1, f"um deixado de fora pode ser conferido sozinho ({nome})")
    await pg.click("dialog.modal .dlg-h [data-x]")
    await pg.wait_for_timeout(500)
    r.check("novidades" in await pg.locator(".news-out .nrow", has_text=nome).first.text_content(), "e a lista já mostra o resultado")

    # de novo na mesma semana: nada a conferir
    await pg.click('[data-act="news-all"]')
    await pg.locator(".toast", has_text="Tudo conferido nos últimos 7 dias").wait_for(timeout=15000)
    r.check(True, "conferir de novo na mesma semana não gasta a IA")

    # categorias gravadas
    await pg.locator(".chip", has_text="Utilidades").click()
    await pg.wait_for_timeout(600)
    r.check("utilidades" not in r.data()["settings"].get("news_cats", ["x"]) if "news_cats" in r.data()["settings"] else True, "desmarcar grava")
    await r.open(pg, "#/mais/novidades", ".chips")
    on = await pg.evaluate("[...document.querySelectorAll('.chip')].filter(c => c.querySelector('input').checked).map(c => c.textContent.trim())")
    r.check("Utilidades" not in on and "Eletrônicos" in on, f"a escolha fica ({on})")
    await ctx.close()

    # Parar no meio: o que já foi conferido fica
    app2 = r.app
    r.app = None
    r.start(search=False)
    ctx, pg = await r.page(b, "estreito", "light", accent="verde")
    await r.open(pg, "#/mais/novidades", ".chips")
    vis = await pg.evaluate("(() => { const bar = document.querySelector('.more-tabs'), on = bar.querySelector('[aria-selected=true]'); const a = bar.getBoundingClientRect(), o = on.getBoundingClientRect(); return o.left >= a.left - 1 && o.right <= a.right + 1; })()")
    r.check(vis, "no celular estreito, a aba escolhida fica à vista na barra")
    cut = await pg.evaluate("[...document.querySelectorAll('.more-tabs button')].some(b => b.scrollWidth > b.clientWidth + 1)")
    r.check(not cut, "nenhum nome de aba cortado")
    await pg.click('[data-act="news-all"]')
    await pg.wait_for_function("/Conferindo [2-9] de/.test(document.querySelector('.njob')?.textContent || '')", timeout=20000)
    await pg.click('[data-act="news-cancel"]')
    await pg.locator(".toast", has_text="Conferência parada").wait_for(timeout=5000)
    await pg.wait_for_timeout(1200)
    n = len(r.api("GET", "api/news")["itens"])
    r.check(n >= 1, f"Parar: o que já foi conferido ficou ({n})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "parado", full_page=True)
    await ctx.close()

    # IA desligada: a aba some e o endereço volta para Dados
    r.api("PUT", "api/settings", {"ai": False})
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/mais/novidades", ".more-tabs")
    r.eq(await pg.locator("#mt-novidades").count(), 0, "IA desligada: sem a aba Novidades")
    r.eq(await pg.get_attribute("#mt-dados", "aria-selected"), "true", "e abre em Dados")
    await ctx.close()
    await b.close()
    app2.stop()


main("novidades_todos", body)
