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
    # 1.56.1: logo abaixo da opção, os apps detectados, recolhidos
    det = "#p-news-opts .apps-det"
    await pg.wait_for_selector(det, timeout=8000)
    pos = await pg.evaluate("""(() => { const li = document.querySelector('#p-news-opts .apps-det').closest('li'); const prev = li.previousElementSibling;
      return [!!prev.querySelector('[data-input="news-apps"]'), document.querySelector('#p-news-opts .apps-det').open]; })()""")
    r.eq(pos, [True, False], "Apps detectados logo abaixo da opção, recolhido")
    r.eq((await pg.text_content(f"{det} summary")).strip(), "Apps detectados (5)", "com a contagem")
    await pg.click(f"{det} summary")
    r.eq((await pg.text_content(f"{det} .help")).strip(), "Com o sensor: Pessoa de Teste.", "os celulares com o sensor ligado")
    linhas = await pg.evaluate(TEXTS, f"{det} .nrow")
    r.eq(len(linhas), 5, "todos os apps que o sensor achou")
    r.check(all("Pessoa de Teste · usado hoje" in x and x.endswith("· novo") for x in linhas), f"de quem, quando foi usado e novo antes da IA escolher ({linhas[0]})")
    r.eq([x.split(" Pessoa")[0] for x in linhas][:2], ["Casa Conectada", "Configurações"], "em ordem de nome")
    chaves = f"{det} [data-input='app-considerar']"
    r.eq(await pg.evaluate(f"[...document.querySelectorAll(\"{chaves}\")].map(i => i.checked)"), [True] * 5, "1.57.0: cada um com a sua chave, ligada de início")
    # 1.57.0: buscar as novidades de um app só, pela linha dele (um novo busca na hora)
    await pg.click(f"{det} [data-act='app-open'][data-id='com.exemplo.musicaja']")
    await pg.wait_for_selector("dialog.modal .news li", timeout=10000)
    r.eq((await pg.text_content("dialog.modal .news-of")).strip(), "Música Já", "a linha abre as novidades do app")
    await pg.click("dialog.modal [data-x]")
    musica = await pg.text_content(f"{det} li:has([data-id='com.exemplo.musicaja']) .nm")
    r.check("novo" not in musica, f"depois de buscar, não é mais novo ({musica.strip()})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "opcoes")
    await pg.click('label.switch:has([data-input="news-auto"])')  # mexer em outra opção não fecha a lista
    await pg.wait_for_selector(f"{det}[open]", timeout=4000)
    r.check(True, "aberto, fica aberto enquanto a tela está aberta")
    await pg.click('label.switch:has([data-input="news-auto"])')
    await pg.locator(".toast", has_text="Conferir sozinho desligado").wait_for(timeout=4000)

    # a seção na tela das Novidades, antes da primeira conferência
    await r.open(pg, "#/novidades", "#p-news-apps")
    await pg.wait_for_selector('[data-slot="news-apps"] p', timeout=8000)
    r.check("dos eletrônicos e dos apps do celular" in await pg.text_content("#p-news .lead"), "o texto do alto fala dos apps")
    r.eq((await pg.text_content("#p-news-apps h2")).strip(), "Apps do celular", "a seção depois dos equipamentos")
    sl = await pg.text_content('[data-slot="news-apps"]')
    r.check("Música Já" in sl and "4 apps novos entram na próxima conferência." in sl, f"o buscado sozinho já está na lista; os outros, na próxima ({sl.strip()[:80]})")

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

    # nas Opções, depois da conferência: quem é acompanhado e quem ficou de fora
    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    await pg.wait_for_selector(det, timeout=8000)
    await pg.click(f"{det} summary")
    estados = dict(await pg.evaluate(f"""[...document.querySelectorAll("{det} .nrow")].map(r => [r.querySelector('b').textContent, r.querySelector('input').checked])"""))
    r.eq(estados, {"Casa Conectada": True, "Configurações": False, "Mercadinho": True, "Música Já": True, "Tela inicial": False},
         "acompanhados ligados, os que a IA deixou de fora desligados")
    r.check("a IA deixou de fora" in await pg.text_content(f"{det} li:has([data-id='com.android.settings']) .nm"), "com o porquê")
    cortados = await pg.evaluate(f"""[...document.querySelectorAll("{det} .nrow b, {det} .nrow .nm")].filter(e => e.scrollWidth > e.clientWidth + 1).length""")
    r.eq(cortados, 0, "nenhum texto cortado")
    # desconsiderar um app: desligado, sai da pesquisa e vai para os deixados de fora
    await pg.click(f"{det} li:has([data-id='com.exemplo.mercadinho']) label.switch")
    await pg.locator(".toast", has_text="Mercadinho: deixado de fora").wait_for(timeout=4000)
    r.check(await pg.locator(f"{det}[open]").count() == 1, "a lista continua aberta")
    merc = next(a for a in r.api("GET", "api/news")["apps"]["lista"] if a["pacote"] == "com.exemplo.mercadinho")
    r.eq((merc["conferir"], merc["manual"], merc["res"]), (False, True, None), "fica fora da pesquisa, pela escolha da pessoa")
    r.check("a IA deixou de fora" not in await pg.text_content(f"{det} li:has([data-id='com.exemplo.mercadinho']) .nm"), "sem dizer que foi a IA")
    # e trazer de volta um que a IA deixou de fora
    await pg.click(f"{det} li:has([data-id='com.android.launcher3']) label.switch")
    await pg.locator(".toast", has_text="Tela inicial: acompanhado").wait_for(timeout=4000)
    tela = next(a for a in r.api("GET", "api/news")["apps"]["lista"] if a["pacote"] == "com.android.launcher3")
    r.eq((tela["conferir"], tela["manual"]), (True, True), "a escolha da pessoa vale sobre a da IA")
    await r.shot(pg, "opcoes-depois")
    await r.open(pg, "#/novidades", "#p-news-apps")
    await pg.wait_for_selector("#p-news-apps .nlist .nrow", timeout=8000)
    r.check("Mercadinho" not in [x[0] for x in await pg.evaluate(APPS)], "nas Novidades, o desconsiderado sai da lista")

    # desligada de novo: some da tela, e a API recusa
    r.api("PUT", "api/settings", {"news_apps": False})
    await r.open(pg, "#/novidades", "#p-news")
    await pg.wait_for_timeout(300)
    r.eq(await pg.locator("#p-news-apps").count(), 0, "desligada: a seção some")
    st, _, out = r.app.request("POST", "api/news/app", {"pacote": "com.exemplo.casaconectada"})
    r.eq(st, 409, "e conferir um app é recusado")


if __name__ == "__main__":
    main("e2e_novidades_apps", body)
