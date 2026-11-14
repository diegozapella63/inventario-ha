"""Novidades › Apps do celular (1.56.0): a opção em Configurações › Opções (desligada de início), a seção Apps do celular
em Mais › Novidades (sem o Home Assistant, os apps de exemplo de um celular de teste), conferir todos com os apps, a janela
de um app (o guardado, sem chamar a IA), Deixar de fora (sai das Novidades e vai para Inativos, nas Opções) e Acompanhar
(volta e busca); 1.58.0: Todas as novidades, Só equipamentos e Só apps; Apps detectados como sub-opção, com Ver novidades e
os desligados em Inativos (n); no celular de 320 px e no computador, no escuro e no claro."""
import os

from e2e_lib import OVERFLOW, TEXTS, helpers, main

APPS = "[...document.querySelectorAll('#p-news-apps [data-slot=\"news-apps\"] > .nlist .nrow')].map(b => [b.querySelector('b').textContent, b.querySelector('.nm').textContent, [...b.querySelectorAll('.pill')].map(p => p.textContent)])"


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")

    # a opção, desligada de início
    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    sw = '[data-input="news-apps"]'
    r.check(not await pg.is_checked(sw), "Apps do celular começa desligado")
    txt = await pg.text_content("#p-apps")
    r.check("Apps do celular" in txt and "Último app usado" in txt, "diz de onde vêm os apps (o sensor do app Home Assistant)")
    r.eq((await pg.text_content("#p-apps h2")).strip(), "Apps do celular", "1.61.0: uma seção própria, depois de Novidades")
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
    det = "#p-apps .apps-det"
    await pg.wait_for_selector(det, timeout=8000)
    pos = await pg.evaluate("""(() => { const li = document.querySelector('#p-apps .apps-det').closest('li'); const prev = li.previousElementSibling;
      return [!!prev.querySelector('[data-input="news-apps"]'), document.querySelector('#p-apps .apps-det').open]; })()""")
    r.eq(pos, [True, False], "Apps detectados logo abaixo da opção, recolhido")
    r.eq((await pg.text_content(f"{det} summary")).strip(), "Apps detectados (5)", "com a contagem")
    await pg.click(f"{det} summary")
    r.eq((await pg.text_content(f"{det} .help")).strip(), "Com o sensor: Pessoa de Teste.", "os celulares com o sensor ligado")
    linhas = await pg.evaluate(TEXTS, f"{det} .app-det .nm")
    r.eq(len(linhas), 5, "todos os apps que o sensor achou")
    r.check(all(x.startswith("Pessoa de Teste · usado hoje") and x.endswith("· novo") for x in linhas), f"de quem, quando foi usado e novo antes da IA escolher ({linhas[0]})")
    r.eq((await pg.evaluate(TEXTS, f"{det} .app-det b"))[:2], ["Casa Conectada", "Configurações"], "em ordem de nome")
    # 1.58.0: uma sub-opção de Apps do celular: um quadro recuado, sem a linha entre os dois
    sub = await pg.evaluate("""(() => { const o = document.querySelector('#p-apps [data-input="news-apps"]').closest('li'), d = document.querySelector('#p-apps .apps-det');
      const a = o.querySelector('.ot').getBoundingClientRect(), b = d.getBoundingClientRect();
      return [Math.round(b.left - a.left), getComputedStyle(o).borderBottomStyle, getComputedStyle(d).borderTopStyle, getComputedStyle(d).borderRadius]; })()""")
    r.check(sub[0] >= 12 and sub[1] == "none" and sub[2] == "solid" and sub[3] != "0px", f"Apps detectados recuado num quadro, logo abaixo de Apps do celular ({sub})")
    # o Ver novidades: um botão como os outros dos apps (no lugar da lupa); 1.58.1: na largura toda da linha, embaixo
    bts = await pg.evaluate(f"""[...document.querySelectorAll("{det} .app-det-b")].map(b => {{ const li = b.closest('li').getBoundingClientRect(), r = b.getBoundingClientRect();
      return [b.textContent.trim(), b.classList.contains('btn'), Math.round(r.height), Math.round(li.width - r.width), r.top > b.closest('li').querySelector('.switch').getBoundingClientRect().bottom - 1]; }})""")
    r.eq({x[0] for x in bts}, {"Ver novidades"}, "cada app com o Ver novidades")
    r.check(all(x[1] and x[2] >= 44 and x[3] <= 1 and x[4] for x in bts), f"um botão do app, na largura toda, embaixo do nome e da chave ({bts[0]})")
    r.eq(await pg.locator(f"{det} .app-det .ic use[href='#i-search']").count(), 0, "sem a lupa")
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

    # 1.58.0: Todas as novidades na largura toda; Só equipamentos e Só apps embaixo, dividindo a linha
    bts = await pg.evaluate("""[...document.querySelectorAll('#p-news [data-act="news-all"]')].map(b => [b.textContent.trim(), b.dataset.so, Math.round(b.getBoundingClientRect().width), Math.round(b.getBoundingClientRect().top)])""")
    r.eq([(x[0], x[1]) for x in bts], [("Todas as novidades", ""), ("Só equipamentos", "itens"), ("Só apps", "apps")], "os três botões")
    r.check(bts[1][3] == bts[2][3] > bts[0][3] and abs(bts[1][2] - bts[2][2]) <= 1 and bts[0][2] > bts[1][2] * 1.8, f"Todas em cima, os outros dois lado a lado do mesmo tamanho ({bts})")
    # conferir todos: os equipamentos e os apps
    await pg.click('[data-act="news-all"][data-so=""]')
    await pg.locator(".toast", has_text="Conferidos").wait_for(timeout=60000)
    await pg.wait_for_selector("#p-news-apps .nlist .nrow", timeout=8000)
    rows = await pg.evaluate(APPS)
    r.eq([x[0] for x in rows], ["Casa Conectada", "Mercadinho", "Música Já"], "os apps que a IA escolheu, em ordem")
    r.check(all(x[1].startswith("Pessoa de Teste · 2 novidades · hoje") for x in rows), f"de quem é o celular, quantas novidades e quando ({rows[0][1]})")
    r.check(all(x[2] == ["2"] for x in rows), "o número de novidades ao lado")
    r.eq(await pg.locator("#p-news-apps .news-out").count(), 0, "1.58.0: sem os deixados de fora aqui (ficam nas Opções, em Inativos)")
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

    # Deixar de fora: fecha e o app sai das Novidades
    await pg.click("dialog.modal [data-fora]")
    await pg.locator(".toast", has_text="Casa Conectada: deixado de fora").wait_for(timeout=4000)
    r.eq(await pg.locator("dialog.modal").count(), 0, "a janela fecha")
    r.eq([x[0] for x in await pg.evaluate(APPS)], ["Mercadinho", "Música Já"], "sai da lista")
    r.eq(await pg.locator("#p-news-apps .news-out").count(), 0, "sem os deixados de fora aqui")

    # Só apps: confere só os apps (os da semana já estão em dia: termina sem buscar nada)
    corpos = []
    pg.on("request", lambda q: corpos.append(q.post_data) if q.method == "POST" and q.url.endswith("/api/news/all") else None)
    await pg.click('[data-act="news-all"][data-so="apps"]')
    await pg.locator(".toast", has_text="Conferid").wait_for(timeout=30000)
    r.eq(corpos, ['{"so":"apps"}'], "Só apps pede só os apps")

    # Acompanhar: nas Opções, em Inativos, o Ver novidades do app deixado de fora; volta e busca
    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    await pg.wait_for_selector(det, timeout=8000)
    if not await pg.eval_on_selector(det, "d => d.open"):
        await pg.click(f"{det} summary")
    inat = f"{det} .apps-inativos"
    r.eq((await pg.text_content(f"{inat} > summary")).strip(), "Inativos (3)", "os desligados no fim, em Inativos, com a contagem")
    r.check(not await pg.eval_on_selector(inat, "d => d.open"), "recolhidos")
    r.eq(await pg.evaluate(TEXTS, f"{inat} .app-det b"), ["Casa Conectada", "Configurações", "Tela inicial"], "o deixado de fora e os que a IA deixou")
    await pg.click(f"{inat} > summary")
    await pg.click(f"{inat} [data-act='app-open'][data-id='com.exemplo.casaconectada']")
    await pg.wait_for_selector("dialog.modal [data-dentro]:not([hidden])", timeout=4000)
    r.check("Deixado de fora das novidades." in await pg.text_content("dialog.modal .dlg-b"), "um deixado de fora diz isso")
    r.eq(await pg.evaluate(TEXTS, "dialog.modal .dlg-f button:not([hidden])"), ["Acompanhar"], "e só oferece Acompanhar")
    sent.clear()
    await pg.click("dialog.modal [data-dentro]")
    await pg.wait_for_selector("dialog.modal .news li", timeout=10000)
    r.check(any("/api/news/app" in u for u in sent), "Acompanhar busca as novidades")
    await pg.click("dialog.modal [data-x]")
    r.check("Casa Conectada" not in await pg.evaluate(TEXTS, f"{inat} .app-det b"), "sai dos Inativos")
    r.check(await pg.locator(f"{inat}[open]").count() == 1, "Inativos continua aberto enquanto a tela está aberta")
    await r.open(pg, "#/novidades", "#p-news-apps")
    await pg.wait_for_selector("#p-news-apps .nlist .nrow", timeout=8000)
    r.check("Casa Conectada" in [x[0] for x in await pg.evaluate(APPS)], "volta para a lista das Novidades")

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
    if not await pg.eval_on_selector(inat, "d => d.open"):
        await pg.click(f"{inat} > summary")
    estados = dict(await pg.evaluate(f"""[...document.querySelectorAll("{det} .app-det")].map(r => [r.querySelector('b').textContent, r.querySelector('input').checked])"""))
    r.eq(estados, {"Casa Conectada": True, "Configurações": False, "Mercadinho": True, "Música Já": True, "Tela inicial": False},
         "acompanhados ligados, os que a IA deixou de fora desligados")
    r.eq(await pg.evaluate(TEXTS, f"{det} > .app-det-l .app-det b"), ["Casa Conectada", "Mercadinho", "Música Já"], "os ligados primeiro")
    r.check("a IA deixou de fora" in await pg.text_content(f"{det} li:has([data-id='com.android.settings']) .nm"), "com o porquê")
    cortados = await pg.evaluate(f"""[...document.querySelectorAll("{det} .app-det b, {det} .app-det .nm")].filter(e => e.scrollWidth > e.clientWidth + 1).length""")
    r.eq(cortados, 0, "nenhum texto cortado")
    # desconsiderar um app: desligado, sai da pesquisa e vai para Inativos
    await pg.click(f"{det} li:has([data-id='com.exemplo.mercadinho']) label.switch")
    await pg.locator(".toast", has_text="Mercadinho: deixado de fora").wait_for(timeout=4000)
    r.check(await pg.locator(f"{det}[open]").count() == 1, "a lista continua aberta")
    r.check("Mercadinho" in await pg.evaluate(TEXTS, f"{inat} .app-det b"), "vai para Inativos")
    merc = next(a for a in r.api("GET", "api/news")["apps"]["lista"] if a["pacote"] == "com.exemplo.mercadinho")
    r.eq((merc["conferir"], merc["manual"], merc["res"]), (False, True, None), "fica fora da pesquisa, pela escolha da pessoa")
    r.check("a IA deixou de fora" not in await pg.text_content(f"{det} li:has([data-id='com.exemplo.mercadinho']) .nm"), "sem dizer que foi a IA")
    # e trazer de volta um que a IA deixou de fora
    await pg.click(f"{det} li:has([data-id='com.android.launcher3']) label.switch")
    await pg.locator(".toast", has_text="Tela inicial: acompanhado").wait_for(timeout=4000)
    tela = next(a for a in r.api("GET", "api/news")["apps"]["lista"] if a["pacote"] == "com.android.launcher3")
    r.eq((tela["conferir"], tela["manual"]), (True, True), "a escolha da pessoa vale sobre a da IA")
    r.check("Tela inicial" in await pg.evaluate(TEXTS, f"{det} > .app-det-l .app-det b"), "ligado, sai de Inativos")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "opcoes-depois")
    # 1.59.0: Encontrar apps com IA: um print (e os nomes colados), a IA lê, a pessoa marca e eles entram em Apps detectados
    await pg.click(f"{det} [data-act='apps-ia']")
    await pg.wait_for_selector("dialog.modal [data-af-act='fotos']", timeout=4000)
    r.eq((await pg.text_content("dialog.modal .dlg-h h2")).strip(), "Encontrar apps com IA", "a janela")
    r.check(await pg.is_disabled("dialog.modal [data-af-act='ler']"), "sem print nem texto, nada a ler")
    async with pg.expect_file_chooser() as fc:
        await pg.click("dialog.modal [data-af-act='fotos']")
    await (await fc.value).set_files(os.path.join(helpers.FIXTURE, "thumbs", "sala-1.jpg"))
    await pg.wait_for_selector("dialog.modal .af-foto img", timeout=4000)
    await pg.fill("dialog.modal #af-txt", "Banco Lua, Mapa Fácil")
    await pg.click("dialog.modal [data-af-act='ler']")
    await pg.wait_for_selector("dialog.modal .apps-achados", timeout=10000)
    achados = await pg.evaluate("""[...document.querySelectorAll('dialog.modal .apps-achados li')].map(l => [l.querySelector('b').textContent, l.querySelector('input').checked, l.querySelector('input').disabled, (l.querySelector('small') || {}).textContent || ''])""")
    r.eq(achados, [["Casa Conectada", False, True, "já está em Apps detectados"], ["Banco Lua", True, False, ""], ["Mapa Fácil", True, False, ""],
                   ["Configurações", False, True, "já está em Apps detectados"]], "o que já está vem marcado e desligado; o resto, marcado")
    r.eq((await pg.text_content("dialog.modal [data-af-act='add']")).strip(), "Adicionar 2 apps", "Adicionar com a contagem")
    await r.shot(pg, "encontrar")
    await pg.click("dialog.modal [data-af-act='add']")
    await pg.locator(".toast", has_text="2 apps adicionados").wait_for(timeout=4000)
    r.eq(await pg.locator("dialog.modal").count(), 0, "a janela fecha")
    nomes = await pg.evaluate(TEXTS, f"{det} > .app-det-l .app-det b")
    r.check("Banco Lua" in nomes and "Mapa Fácil" in nomes, f"entram em Apps detectados, ligados ({nomes})")
    r.check("pela IA" in await pg.text_content(f"{det} li:has([data-id='ia.mapa_facil']) .nm"), "com pela IA")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")

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
