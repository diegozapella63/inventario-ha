"""1.78.0: os três tipos do inventário, cada um com a sua chave (Mais > Configurações > Opções > Inventário): Usar itens
da casa, Usar bens e Usar consumíveis (pelo menos um ligado; desligar não apaga). Os Consumíveis (pasta térmica, creme de
massagem): a área criada com o primeiro, a tela por categoria com a quantidade em destaque, "O que é e para que serve" no
lugar dos detalhes, a leitura por IA, fora do patrimônio, dos gráficos, do relatório e dos outros apps. Com os três
ligados, o Agora mostra um quadro para cada. Sem os itens da casa, a aba Cômodos vira Bens (ou Consumíveis)."""
from e2e_lib import OVERFLOW, main


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


TIPOS = "[...document.querySelectorAll('.tipos .tipo')].map(a => [a.querySelector('b').textContent, a.querySelector('.tn').textContent, a.querySelector('.ts').textContent, a.getAttribute('href')])"
MENU = "[...document.querySelectorAll('.menu-row b')].map(b => b.textContent)"
TAB3 = "(a => [a.textContent.trim(), a.getAttribute('href'), a.getAttribute('aria-current')])(document.querySelector('.tabbar [data-tab=\"rooms\"]'))"


async def body(r, p):
    r.start(search=False)
    d0 = r.data()
    house_total = sum(float(i["value"] or 0) for i in d0["items"])
    n_house = len(d0["items"])
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="turquesa")

    # -- de início: os itens da casa e os bens ligados, os consumíveis desligados; nada deles na tela
    await r.open(pg, "#/mais", ".menu-list")
    r.check("Consumíveis" not in await pg.evaluate(MENU), "desligados: o Mais sem Consumíveis")
    await r.open(pg, "#/consumiveis", ".menu-list")
    r.check(pg.url.endswith("#/mais"), "o endereço de Consumíveis abre o menu Mais")
    st, _, _ = r.app.request("POST", "api/rooms", {"kind": "consumiveis"})
    r.eq(st, 409, "o servidor não cria a área com os consumíveis desligados")
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.locator(".tipos").count(), 0, "Agora: só com os itens da casa em uso, sem os quadros (como antes)")

    # -- Opções: o cartão Inventário com as três chaves
    await r.open(pg, "#/config/opcoes", "#p-tipos")
    linhas = await pg.evaluate("[...document.querySelectorAll('#p-tipos .opts li')].map(li => [li.querySelector('b').textContent, li.querySelector('.ot > span').textContent, li.querySelector('input').checked, !!li.querySelector('b .ic')])")
    r.eq(linhas, [["Usar itens da casa", "Os cômodos e o que há neles.", True, True], ["Usar bens", "Casa, terreno, carro: o que fica fora de casa.", True, True],
                  ["Usar consumíveis", "Pasta térmica, creme, pilhas: o que se gasta.", False, True]], "as três chaves, cada uma com o ícone e o que é")
    r.eq(txt(await pg.text_content("#p-tipos h2")), "Inventário", "o cartão se chama Inventário")
    await pg.click('label.switch:has([data-input="cons-on"])')
    await pg.locator(".toast", has_text="Consumíveis ligados").wait_for(timeout=5000)
    r.check(r.data()["settings"]["consumiveis"] is True, "ligado fica gravado")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "opcoes", full_page=True)

    await r.open(pg, "#/", ".tag")
    r.eq(await pg.evaluate(TIPOS), [["Itens da casa", str(n_house), "itens", "#/comodos"], ["Bens", "0", "bens", "#/bens"], ["Consumíveis", "0", "consumíveis", "#/consumiveis"]],
         "com os consumíveis ligados, o Agora ganha um quadro para cada tipo")

    # -- o Mais ganha Consumíveis, depois de Bens; sem nenhum, o convite
    await r.open(pg, "#/mais", ".menu-list")
    r.eq((await pg.evaluate(MENU))[:2], ["Bens", "Consumíveis"], "o Mais com Bens e Consumíveis no alto")
    await pg.click('.menu-row[href="#/consumiveis"]')
    await pg.wait_for_selector(".mscreen .empty", timeout=5000)
    r.eq(txt(await pg.text_content(".page-title")), "Consumíveis", "a tela Consumíveis")
    r.check(await pg.locator(".page-title .sec-ic .ic").count() == 1, "o título com o ícone")
    r.eq(txt(await pg.text_content(".mscreen .empty h2")), "Nenhum consumível ainda", "sem consumíveis: o convite")
    r.check(not any(x.get("kind") == "consumiveis" for x in r.data()["rooms"]), "a área só é criada com o primeiro consumível")
    await r.shot(pg, "vazio")

    # -- o primeiro, pelo botão da tela: sem cômodo nem zona; a categoria, a quantidade e o que é e para que serve
    await pg.click('.mscreen [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    r.eq(txt(await pg.text_content("dialog.modal .dlg-h h2")), "Novo consumível", "a janela diz Novo consumível")
    r.eq(await pg.locator("#f-room, #f-zone, .seg.tipo").count(), 0, "um consumível não tem Cômodo, Zona nem o Tipo dos bens")
    # 1.82.0: sem a Quantidade e sem o Valor; a Categoria é a dos consumíveis e, no lugar, a Duração estimada com os atalhos
    r.eq(await pg.locator("#f-cat").count(), 1, "tem a Categoria")
    r.check(not await pg.locator("#f-qty").is_visible() and not await pg.locator("#f-value").is_visible(), "sem a Quantidade e sem o Valor")
    opcoes = await pg.evaluate("[...document.querySelectorAll('#f-cat option')].map(o => o.textContent)")
    r.eq(opcoes, ["Escolha a categoria", "Limpeza", "Higiene e cuidados", "Cozinha e despensa", "Farmácia", "Pets", "Escritório e papelaria", "Manutenção e reparos",
                  "Pilhas e eletrônicos", "Carro", "Jardim", "Outros"], "as categorias dos consumíveis, já com as sugestões (nenhuma da casa)")
    durs = await pg.evaluate("[...document.querySelectorAll('#f-dur .chip')].map(c => c.textContent.trim())")
    r.eq(durs, ["Sem duração", "1 semana", "15 dias", "1 mês", "3 meses", "6 meses", "1 ano"], "a Duração estimada com os atalhos")
    r.eq(txt(await pg.text_content("#f-dur .lbl")), "Duração estimada", "o título do campo")
    cx = await pg.evaluate("[...document.querySelectorAll('#f-dur .chip')].map(c => { const b = c.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height), c.scrollWidth > c.clientWidth + 1]; })")
    r.check(len({c[0] for c in cx}) == 1 and len({c[1] for c in cx}) == 1 and not any(c[2] for c in cx), f"os atalhos do mesmo tamanho, sem cortar ({cx})")
    r.eq(txt(await pg.text_content('label[for="f-details"]')), "O que é e para que serve", "no lugar dos Detalhes")
    r.eq(txt(await pg.text_content('[data-ed="save"]')), "Salvar consumível", "o botão diz Salvar consumível")
    await pg.fill("#f-name", "Creme de massagem")
    await pg.fill("#f-details", "Creme para massagem nas costas e nas pernas, de arnica.")
    await pg.select_option("#f-cat", "c-higiene")
    await pg.locator("#f-dur .chip", has_text="3 meses").click()
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "novo")
    await pg.click('[data-ed="save"]')
    await pg.locator(".toast", has_text="Consumível adicionado").wait_for(timeout=8000)
    d = r.data()
    areas = [x for x in d["rooms"] if x.get("kind") == "consumiveis"]
    r.check(len(areas) == 1 and areas[0]["code"] == "CON" and areas[0]["name"] == "Consumíveis", f"a área foi criada, com o código CON ({areas})")
    con = areas[0]["id"]
    creme = next(i for i in d["items"] if i["name"] == "Creme de massagem")
    r.check(creme["room"] == con and creme["dur"] == 90 and creme["cat"] == "c-higiene" and creme["value"] == 0 and creme["qty"] == "1" and not creme.get("zone"),
            f"gravado na área, com a duração e a categoria, sem valor, quantidade nem zona ({creme})")
    r.check(d["rooms"][-1]["id"] == con, "a área fica depois de todos os cômodos")

    # -- a leitura por IA: com uma foto, a IA preenche o nome e o que é e para que serve
    foto = next(i["photos"][0] for i in d["items"] if i.get("photos"))
    await r.open(pg, "#/consumiveis", ".mscreen.cons")
    await pg.click(".tabbar .plus")
    await pg.wait_for_selector("#f-name")
    r.eq(txt(await pg.text_content("dialog.modal .dlg-h h2")), "Novo consumível", "em Consumíveis, o + já abre um consumível")
    await pg.click("dialog.modal [data-x], dialog.modal [data-ed='cancel']")
    await pg.wait_for_timeout(300)
    st, _, out = r.app.request("POST", "api/ai/identify", {"file": foto, "mode": "single", "room": con, "consumivel": True})
    r.eq((st, out["items"][0]["name"], out["items"][0]["zone"]), (200, "Pasta térmica", ""), "a IA lê um consumível (a simulada devolve a pasta térmica)")
    r.check("para o calor passar" in out["items"][0]["details"], "com o que é e para que serve nos detalhes")
    r.api("POST", "api/items", {"room": con, "name": out["items"][0]["name"], "details": out["items"][0]["details"], "cat": out["items"][0]["cat"], "dur": out["items"][0]["dur"], "source": "ia"})
    r.api("POST", "api/items", {"room": con, "name": "Pilhas AA", "details": "Pilhas alcalinas para controles e brinquedos.", "cat": "c-manutencao"})

    # -- a tela: por categoria, com a quantidade em destaque; o valor, só de quem tem
    await r.open(pg, "#/consumiveis", ".mscreen.cons")
    grupos = await pg.evaluate("[...document.querySelectorAll('.mscreen.cons .zone')].map(z => [z.querySelector('h3').textContent.trim(), z.querySelector('.zs').textContent.trim(), [...z.querySelectorAll('.irow')].map(r => [r.querySelector('.nm').textContent, (r.querySelector('.iv .val') || {textContent: ''}).textContent, ((r.querySelector('.iv .qty') || {}).textContent || '').replace(/\u00a0/g, ' ')])])")
    r.eq([(g[0], g[1]) for g in grupos], [("Higiene e cuidados", "1 consumível"), ("Manutenção e reparos", "2 consumíveis")], "os grupos são as categorias dos consumíveis, com a contagem")
    r.eq(grupos[1][2], [["Pasta térmica", "1 ano", ""], ["Pilhas AA", "", ""]], "cada linha com a duração em destaque (de quem tem); sem quantidade e sem valor")
    r.eq(txt(await pg.text_content(".page-sub")), "3 consumíveis", "o alto diz quantos")
    r.check(await pg.locator(".uplink").count() == 1, "com ‹ Mais no alto")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "lista", full_page=True)

    # -- a ficha: a quantidade em destaque, Onde: Consumíveis, sem zona
    await pg.locator(".mscreen.cons .irow", has_text="Pasta térmica").click()
    await pg.wait_for_selector("dialog.sheet h1")
    r.eq(txt(await pg.text_content("dialog.sheet .ival .big")), "1 ano", "a ficha com a duração em destaque")
    props = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .props dt')].map(d => d.textContent)")
    r.check(props[0] == "Onde" and "Zona" not in props and "Quantidade" not in props and "Duração estimada" in props, f"Onde e Duração estimada, sem Zona e sem Quantidade ({props})")
    r.check("para o calor passar" in txt(await pg.text_content("dialog.sheet .idet")), "com o que é e para que serve")
    await r.shot(pg, "ficha")
    await pg.click('dialog.sheet [data-act="sheet-close"]')
    await pg.wait_for_timeout(300)

    # -- Agora: os três quadros lado a lado; o patrimônio sem os consumíveis; a seção Consumíveis
    r.api("POST", "api/rooms", {"kind": "bens"})
    ben = next(x["id"] for x in r.data()["rooms"] if x.get("kind") == "bens")
    r.api("POST", "api/items", {"room": ben, "name": "Carro hatch 2020", "cat": "veiculos", "value": 60000})
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.evaluate(TIPOS), [["Itens da casa", str(n_house), "itens", "#/comodos"], ["Bens", "1", "bem", "#/bens"], ["Consumíveis", "3", "consumíveis", "#/consumiveis"]],
         "Agora: os três quadros, cada um com a contagem e o caminho")
    caixas = await pg.evaluate("[...document.querySelectorAll('.tipos .tipo')].map(a => { const b = a.getBoundingClientRect(); return [Math.round(b.top), Math.round(b.width), Math.round(b.height)]; })")
    r.check(len({c[0] for c in caixas}) == 1 and len({c[1] for c in caixas}) == 1 and len({c[2] for c in caixas}) == 1, f"lado a lado, do mesmo tamanho ({caixas})")
    await pg.evaluate("document.fonts.ready.then(() => 1)")
    cortado = await pg.evaluate("[...document.querySelectorAll('.tipos .tipo b, .tipos .tipo .tv')].filter(e => e.scrollWidth > e.clientWidth).map(e => e.textContent)")
    r.eq(cortado, [], "nenhum nome ou total cortado nos quadros")
    val = int("".join(ch for ch in await pg.text_content(".tag-value") if ch.isdigit()))
    r.eq(val, round(house_total + 60000), "o patrimônio com os bens e sem os consumíveis")
    r.eq(txt(await pg.text_content(".tag-sub")), f"{n_house} itens em 6 cômodos e 1 bem", "a etiqueta sem os consumíveis")
    r.eq(await pg.locator("#home-cons .nm").count(), 3, "a seção Consumíveis do Agora")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "agora", full_page=True)
    await pg.evaluate("document.querySelector('.tipos').scrollIntoView({ block: 'center' })")
    await r.shot(pg, "quadros")
    await pg.click('.tipos [data-tipo="cons"]')
    await pg.wait_for_selector(".mscreen.cons")
    r.check(pg.url.endswith("#/consumiveis"), "o quadro abre a tela do tipo")

    # -- Adicionar (+) pergunta o que é; a busca filtra por tipo
    await r.open(pg, "#/", ".tag")
    await pg.click(".tabbar .plus")
    await pg.wait_for_selector("[data-go]", timeout=4000)
    gos = await pg.evaluate("[...document.querySelectorAll('[data-go]')].map(b => b.dataset.go)")
    r.check(gos[0] == "item" and gos[-2:] == ["bem", "cons"], f"Adicionar: o item, depois o bem e o consumível ({gos})")
    await r.shot(pg, "adicionar")
    await pg.click("dialog.modal [data-x]")
    await pg.wait_for_timeout(300)
    await r.open(pg, "#/buscar", ".sfilters")
    ops = await pg.evaluate("[...document.querySelectorAll('[data-input=\"search-tipo\"] option')].map(o => o.textContent)")
    r.eq(ops, ["Todos os tipos", "Itens da casa", "Imóveis", "Veículos", "Outros bens", "Consumíveis"], "o filtro Tipo ganha Consumíveis")
    await pg.fill('[data-input="search-q"]', "massag")
    await pg.wait_for_timeout(500)
    r.eq(await pg.evaluate("[...document.querySelectorAll('#results .irow .nm')].map(n => n.textContent)"), ["Creme de massagem"], "a busca acha o consumível pelo nome e pelo para que serve")
    await pg.fill('[data-input="search-q"]', "")
    await pg.select_option('[data-input="search-tipo"]', "consumiveis")
    await pg.wait_for_timeout(400)
    r.eq(sorted(await pg.evaluate("[...document.querySelectorAll('#results .irow .nm')].map(n => n.textContent)")), ["Creme de massagem", "Pasta térmica", "Pilhas AA"], "Tipo Consumíveis: só eles")
    r.eq(await pg.locator('[data-input="search-room"], [data-input="search-cat"]').count(), 0, "num tipo fora dos cômodos, sem Cômodo e Categoria")

    # -- fora do patrimônio: gráficos, relatório e os outros apps
    await r.open(pg, "#/graficos", ".kpis")
    r.check("Pasta térmica" not in txt(await pg.text_content("#view")), "Gráficos sem os consumíveis")
    await r.open(pg, "#/relatorio", ".report")
    r.check("Pilhas AA" not in txt(await pg.text_content(".report")), "o relatório sem os consumíveis")
    await ctx.close()

    # -- computador: a lateral com os três tipos; os quadros
    ctx, pg = await r.page(b, "pc", "light", accent="ouro")
    await r.open(pg, "#/", ".tag")
    nav = await pg.evaluate("[...document.querySelectorAll('#side .nav a')].map(a => a.textContent.replace('/', '').trim())")
    r.eq(nav, ["Agora", "Buscar", "Cômodos", "Bens", "Consumíveis", "Relatório", "Mais"], "no computador, a lateral com os três tipos")
    r.eq(await pg.locator(".tipos .tipo").count(), 3, "e os três quadros no Agora")
    r.check(await pg.evaluate(OVERFLOW), "Agora no computador, sem rolagem para o lado")
    await r.shot(pg, "agora-pc", full_page=True)
    await pg.click('#side .nav a[href="#/consumiveis"]')
    await pg.wait_for_selector(".mscreen.cons")
    r.eq(await pg.get_attribute('#side .nav a[href="#/consumiveis"]', "aria-current"), "page", "Consumíveis marcado na lateral")
    await r.shot(pg, "lista-pc", full_page=True)
    await ctx.close()

    # -- Usar itens da casa desligado: somem os cômodos e os itens; a aba vira Bens; nada é apagado
    ctx, pg = await r.page(b, "cel", "dark", accent="turquesa")
    await r.open(pg, "#/config/opcoes", "#p-tipos")
    await pg.click('label.switch:has([data-input="itens-on"])')
    await pg.locator(".toast", has_text="Itens da casa desligados").wait_for(timeout=5000)
    d = r.data()
    r.check(d["settings"]["itens"] is False and len(d["items"]) == n_house + 4, "desligado fica gravado, e os itens continuam guardados")
    r.eq(await pg.locator("#p-zones").count(), 0, "sem os itens da casa, as Zonas somem das Opções")
    r.eq(await pg.evaluate(TAB3), ["Bens", "#/bens", None], "a 3ª aba vira Bens")
    await r.shot(pg, "opcoes-sem-itens", full_page=True)
    await pg.click('.tabbar [data-tab="rooms"]')
    await pg.wait_for_selector(".mscreen.bens")
    r.eq((await pg.evaluate(TAB3))[2], "page", "Bens marcado na barra")
    r.eq(await pg.locator(".uplink").count(), 0, "na aba, sem o ‹ Mais")
    await r.open(pg, "#/mais", ".menu-list")
    m = await pg.evaluate(MENU)
    r.check(m[0] == "Consumíveis" and "Bens" not in m, f"o Mais sem Bens (está na barra) e com Consumíveis ({m[:3]})")
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.evaluate(TIPOS), [["Bens", "1", "bem", "#/bens"], ["Consumíveis", "3", "consumíveis", "#/consumiveis"]], "Agora: só os dois quadros")
    r.eq(txt(await pg.text_content(".tag-sub")), "1 bem", "a etiqueta só com o bem")
    r.eq(int("".join(ch for ch in await pg.text_content(".tag-value") if ch.isdigit())), 60000, "o patrimônio só com o bem")
    r.eq(await pg.locator('.sec [data-act="room-new"]').count(), 0, "sem a seção Cômodos")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "agora-sem-itens", full_page=True)
    await r.open(pg, "#/comodos", ".mscreen.bens")
    r.check(pg.url.endswith("#/bens"), "o endereço dos Cômodos abre Bens")
    await r.open(pg, "#/", ".tag")
    await pg.click(".tabbar .plus")
    await pg.wait_for_selector("[data-go]", timeout=4000)
    r.eq(await pg.evaluate("[...document.querySelectorAll('[data-go]')].map(b => b.dataset.go)"), ["bem", "cons"], "Adicionar: só o bem e o consumível")
    await pg.click("dialog.modal [data-x]")
    await pg.wait_for_timeout(300)
    await r.open(pg, "#/buscar", ".sfilters")
    r.check(not any("SAL-" in t or "COZ-" in t for t in await pg.evaluate("[...document.querySelectorAll('#results .irow')].map(r => r.textContent)")), "a busca sem os itens da casa")
    st, _, _ = r.app.request("POST", "api/rooms", {"name": "Garagem"})
    r.eq(st, 409, "o servidor não cria cômodo com os itens da casa desligados")

    # -- pelo menos um fica ligado: com um só, a chave fica presa
    await r.open(pg, "#/config/opcoes", "#p-tipos")
    await pg.click('label.switch:has([data-input="bens-on"])')
    await pg.locator(".toast", has_text="Bens desligados").wait_for(timeout=5000)
    r.eq(await pg.evaluate(TAB3), ["Consumíveis", "#/consumiveis", None], "sem itens e sem bens, a 3ª aba vira Consumíveis")
    so = await pg.evaluate("(i => [i.disabled, i.checked, i.closest('li').querySelector('.ot > span').textContent])(document.querySelector('[data-input=\"cons-on\"]'))")
    r.eq(so, [True, True, "Pelo menos um fica ligado."], "o único ligado fica preso, com o porquê")
    st, _, out = r.app.request("PUT", "api/settings", {"consumiveis": False})
    r.eq((st, out.get("error") or out.get("erro") or out.get("message")), (409, "Pelo menos um fica ligado: itens da casa, bens ou consumíveis."), "e o servidor recusa desligar o último")
    await r.shot(pg, "opcoes-um-so", full_page=True)
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.locator(".tipos").count(), 0, "com um tipo só, sem os quadros")
    await r.open(pg, "#/mais", ".menu-list")
    r.check("Consumíveis" not in await pg.evaluate(MENU), "o Mais sem Consumíveis (está na barra)")
    await r.open(pg, "#/config/opcoes", "#p-tipos")
    for k, t in (("itens-on", "Itens da casa ligados"), ("bens-on", "Bens ligados")):
        await pg.click(f'label.switch:has([data-input="{k}"])')
        await pg.locator(".toast", has_text=t).wait_for(timeout=5000)
    r.eq(await pg.evaluate(TAB3), ["Cômodos", "#/comodos", None], "ligados de novo: a aba volta a ser Cômodos")
    await r.open(pg, "#/", ".tag")
    r.eq(txt(await pg.text_content(".tag-sub")), f"{n_house} itens em 6 cômodos e 1 bem", "e tudo volta, como estava")
    await ctx.close()

    # -- 320 px, claro
    ctx, pg = await r.page(b, "estreito", "light", accent="coral")
    for h, w in (("#/", ".tag"), ("#/consumiveis", ".mscreen.cons"), ("#/config/opcoes", "#p-tipos")):
        await r.open(pg, h, w)
        r.check(await pg.evaluate(OVERFLOW), f"320 px, {h}: nada passa da largura")
    await r.open(pg, "#/", ".tag")
    await pg.evaluate("document.fonts.ready.then(() => 1)")
    cortado = await pg.evaluate("[...document.querySelectorAll('.tipos .tipo b, .tipos .tipo .tv')].filter(e => e.scrollWidth > e.clientWidth || e.scrollHeight > e.clientHeight + 1).map(e => e.textContent)")
    r.eq(cortado, [], "320 px: nenhum nome ou total cortado nos quadros")
    tops = await pg.evaluate("[...document.querySelectorAll('.tipos .tipo .tn')].map(e => Math.round(e.getBoundingClientRect().top))")
    r.check(len(set(tops)) == 1, f"320 px: os números dos três quadros na mesma linha ({tops})")
    await pg.evaluate("document.querySelector('.tipos').scrollIntoView({ block: 'center' })")
    await r.shot(pg, "estreito")
    await ctx.close()
    await b.close()


main("consumiveis", body)
