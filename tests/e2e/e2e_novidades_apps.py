"""Novidades › Apps do celular (1.56.0): a opção em Configurações › Opções (desligada de início), a seção Apps do celular
em Mais › Novidades (sem o Home Assistant, os apps de exemplo de um celular de teste), conferir todos com os apps, a janela
de um app (o guardado, sem chamar a IA), Deixar de fora (vai para os deixados de fora, recolhidos) e Acompanhar (volta e
busca), no celular de 320 px e no computador, no escuro e no claro."""
from e2e_lib import OVERFLOW, TEXTS, main

APPS = "[...document.querySelectorAll('#p-news-apps [data-slot=\"news-apps\"] > .nlist .nrow')].map(b => [b.querySelector('b').textContent, b.querySelector('.nm').textContent, [...b.querySelectorAll('.pill')].map(p => p.textContent)])"


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")

    # a opção, desligada de início
    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    sw = '[data-input="news-apps"]'
    r.check(not await pg.is_checked(sw), "Apps do celular começa desligado")
    txt = await pg.text_content("#p-news-opts")
    r.check("Apps do celular" in txt and "Último app usado" in txt, "diz de onde vêm os apps (o sensor do app Home Assistant)")
    await r.open(pg, "#/novidades", "#p-news")
    r.eq(await pg.locator("#p-news-apps").count(), 0, "desligada: sem a seção dos apps")
    r.check("apps" not in await pg.text_content("#p-news .lead"), "e o texto fala só dos eletrônicos")

    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    await pg.click(f'label.switch:has({sw})')
    await pg.locator(".toast", has_text="Apps do celular nas novidades").wait_for(timeout=4000)
    r.check(await pg.is_checked(sw), "liga")
    r.check(r.data()["settings"]["news_apps"] is True, "fica gravado")
    r.check("eletrônicos e os apps" in await pg.text_content("#p-news-opts"), "o Conferir sozinho também fala dos apps")
    await r.shot(pg, "opcoes")

    # a seção na tela das Novidades, antes da primeira conferência
    await r.open(pg, "#/novidades", "#p-news-apps")
    await pg.wait_for_selector('[data-slot="news-apps"] p', timeout=8000)
    r.check("dos eletrônicos e dos apps do celular" in await pg.text_content("#p-news .lead"), "o texto do alto fala dos apps")
    r.eq((await pg.text_content("#p-news-apps h2")).strip(), "Apps do celular", "a seção depois dos equipamentos")
    r.check("Toque em Conferir novidades: a IA escolhe os apps." in await pg.text_content('[data-slot="news-apps"]'), "antes da primeira vez, diz o que fazer")

    # conferir todos: os equipamentos e os apps
    await pg.click('[data-act="news-all"]')
    await pg.locator(".toast", has_text="Conferidos").wait_for(timeout=60000)
    await pg.wait_for_selector("#p-news-apps .nlist .nrow", timeout=8000)
    rows = await pg.evaluate(APPS)
    r.eq([x[0] for x in rows], ["Casa Conectada", "Mercadinho", "Música Já"], "os apps que a IA escolheu, em ordem")
    r.check(all(x[1].startswith("Pessoa de Teste · 2 novidades · hoje") for x in rows), f"de quem é o celular, quantas novidades e quando ({rows[0][1]})")
    r.check(all(x[2] == ["2"] for x in rows), "o número de novidades ao lado")
    fora = await pg.evaluate("""(() => { const d = document.querySelector('#p-news-apps .news-out'); return d ? [d.open, d.querySelector('summary').textContent.trim(),
      d === d.parentElement.lastElementChild] : null; })()""")
    r.eq(fora, [False, "Deixados de fora (2)", True], "a tela inicial e as configurações no fim, recolhidos, com a contagem")
    foot = await pg.text_content('[data-slot="news-job"]')
    r.check("com novidades" in foot, f"o resumo conta os apps também ({foot.strip()})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "depois", full_page=True)

    # a janela de um app: o que já foi conferido, sem chamar a IA
    sent = []
    pg.on("request", lambda q: sent.append(q.url) if q.method in ("POST", "PUT") and "/api/news" in q.url else None)
    await pg.locator("#p-news-apps .nrow", has_text="Casa Conectada").click()
    await pg.wait_for_selector("dialog.modal .news li", timeout=4000)
    r.eq(sent, [], "abre o guardado, sem chamar a IA")
    r.eq((await pg.text_content("dialog.modal .news-of")).strip(), "Casa Conectada", "o nome do app")
    r.eq(await pg.evaluate(TEXTS, "dialog.modal .dlg-f button:not([hidden])"), ["Buscar de novo", "Deixar de fora"], "Buscar de novo e Deixar de fora")
    await r.shot(pg, "janela")

    # Deixar de fora: fecha e o app vai para os deixados de fora
    await pg.click("dialog.modal [data-fora]")
    await pg.locator(".toast", has_text="Casa Conectada: deixado de fora").wait_for(timeout=4000)
    r.eq(await pg.locator("dialog.modal").count(), 0, "a janela fecha")
    r.eq([x[0] for x in await pg.evaluate(APPS)], ["Mercadinho", "Música Já"], "sai da lista")
    r.eq((await pg.text_content("#p-news-apps .news-out summary")).strip(), "Deixados de fora (3)", "e entra nos deixados de fora")

    # Acompanhar: de dentro dos deixados de fora, volta e busca
    await pg.click("#p-news-apps .news-out summary")
    await pg.locator("#p-news-apps .news-out .nrow", has_text="Casa Conectada").click()
    await pg.wait_for_selector("dialog.modal [data-dentro]:not([hidden])", timeout=4000)
    r.check("Deixado de fora das novidades." in await pg.text_content("dialog.modal .dlg-b"), "um deixado de fora diz isso")
    r.eq(await pg.evaluate(TEXTS, "dialog.modal .dlg-f button:not([hidden])"), ["Acompanhar"], "e só oferece Acompanhar")
    sent.clear()
    await pg.click("dialog.modal [data-dentro]")
    await pg.wait_for_selector("dialog.modal .news li", timeout=10000)
    r.check(any("/api/news/app" in u for u in sent), "Acompanhar busca as novidades")
    r.check(await pg.locator("#p-news-apps .news-out[open]").count() == 1, "os deixados de fora continuam abertos enquanto a tela está aberta")
    await pg.click("dialog.modal [data-x]")
    r.check("Casa Conectada" in [x[0] for x in await pg.evaluate(APPS)], "volta para a lista")

    # celular pequeno, claro, e computador
    ctx2, pg2 = await r.page(b, "estreito", "light", accent="verde")
    await r.open(pg2, "#/novidades", "#p-news-apps")
    await pg2.wait_for_selector("#p-news-apps .nlist .nrow", timeout=8000)
    r.check(await pg2.evaluate(OVERFLOW), "320 px: sem rolagem para o lado")
    await r.shot(pg2, "320-claro", full_page=True)
    ctx3, pg3 = await r.page(b, "pc", "dark")
    await r.open(pg3, "#/novidades", "#p-news-apps")
    await pg3.wait_for_selector("#p-news-apps .nlist .nrow", timeout=8000)
    await r.shot(pg3, "computador", full_page=True)

    # desligada de novo: some da tela, e a API recusa
    r.api("PUT", "api/settings", {"news_apps": False})
    await r.open(pg, "#/novidades", "#p-news")
    await pg.wait_for_timeout(300)
    r.eq(await pg.locator("#p-news-apps").count(), 0, "desligada: a seção some")
    st, _, out = r.app.request("POST", "api/news/app", {"pacote": "com.exemplo.casaconectada"})
    r.eq(st, 409, "e conferir um app é recusado")


if __name__ == "__main__":
    main("e2e_novidades_apps", body)
