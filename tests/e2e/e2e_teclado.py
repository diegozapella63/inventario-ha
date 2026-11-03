"""Teclado no computador: N e /, Esc em cada janela, Ctrl+Enter, Enter nos formulários de uma linha, setas no visualizador e
nas abas de Mais, Tab que não sai da janela aberta e o foco que volta para quem abriu a janela."""
from e2e_lib import main

# quem está com o foco: o id, o data-act/ed/r/input ou o endereço do link
ACTIVE = "(() => { const a = document.activeElement; return a ? (a.id || a.dataset.act || a.dataset.ed || a.dataset.r || a.dataset.input || a.getAttribute('href') || a.tagName) : null; })()"


def hash_(pg):
    return "#" + pg.url.split("#", 1)[1] if "#" in pg.url else "#/"


async def walk_tab(pg, n=30, back=False):
    """Aperta Tab n vezes. Devolve (onde o foco parou atrás da janela, quantas vezes ficou dentro dela).
    Fora da página (o corpo, que no navegador é a barra de endereço) não conta como sair: só o que está atrás da janela."""
    out, inside = [], 0
    for _ in range(n):
        await pg.keyboard.press("Shift+Tab" if back else "Tab")
        where = await pg.evaluate("""(() => { const top = [...document.querySelectorAll('dialog[open]')].pop(), a = document.activeElement;
          if (!a || a === document.body || a === document.documentElement) return 'fora';
          return top && top.contains(a) ? 'dentro' : a.tagName + '.' + a.className; })()""")
        if where == "dentro":
            inside += 1
        elif where != "fora":
            out.append(where)
    return out, inside


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", "light", accent="cinza")

    # -- N e /
    await r.open(pg, "#/", ".tag")
    await pg.locator("body").click(position={"x": 700, "y": 880})
    await pg.keyboard.press("Shift+N")
    await pg.wait_for_selector("#f-name", timeout=4000)
    await pg.wait_for_function("document.activeElement && document.activeElement.id === 'f-name'", timeout=3000)
    r.check(await pg.text_content("dialog.modal h2") == "Novo item", "N (maiúsculo também) abre o cadastro com o cursor no nome")
    await pg.keyboard.press("n")
    r.check(await pg.input_value("#f-name") == "n" and await pg.locator("dialog.modal[open]").count() == 1, "com o cadastro aberto, N é só uma letra")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector('[data-r="0"]')
    await pg.click('[data-r="1"]')
    await pg.wait_for_selector("dialog[open]", state="detached", timeout=4000)
    await pg.keyboard.press("/")
    await pg.wait_for_selector(".sbar")
    await pg.wait_for_timeout(200)
    r.check(hash_(pg) == "#/buscar" and await pg.evaluate("document.activeElement.dataset.input") == "search-q", "/ vai para Buscar com o cursor na busca")
    await pg.keyboard.type("1/2")
    await pg.wait_for_timeout(300)
    r.eq(await pg.input_value('[data-input="search-q"]'), "1/2", "dentro da busca, / é só uma letra")
    await pg.locator("body").click(position={"x": 700, "y": 880})
    await pg.keyboard.press("/")
    r.eq(await pg.evaluate("document.activeElement.dataset.input"), "search-q", "em Buscar, / volta o cursor para a busca")
    await r.open(pg, "#/", ".tag")
    await pg.focus('[data-input="home-q"]')
    await pg.keyboard.press("n")
    await pg.wait_for_selector(".sbar")
    await pg.wait_for_timeout(200)
    r.check(await pg.locator("dialog[open]").count() == 0 and await pg.input_value('[data-input="search-q"]') == "n",
            "N na busca do Início é letra: vai para Buscar com o n")

    # -- Esc e o foco de volta: ficha aberta pelo teclado
    await r.open(pg, "#/c/cozinha", ".rhead")
    row = pg.locator("#view .irow").nth(2)
    href = await row.get_attribute("href")
    await row.focus()
    await pg.keyboard.press("Enter")
    await pg.wait_for_selector("dialog.sheet h1")
    r.eq(hash_(pg), href, "Enter numa linha abre a ficha")
    await pg.keyboard.press("n")
    await pg.wait_for_timeout(300)
    r.eq(await pg.locator("#f-name").count(), 0, "com a ficha aberta, N não abre o cadastro por cima")
    out, inside = await walk_tab(pg, 25)
    r.check(not out and inside >= 20, f"Tab na ficha dá a volta nela, sem ir para a página de trás ({out[:2]}, {inside} de 25 dentro)")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("dialog.sheet", state="detached", timeout=4000)
    r.check(hash_(pg) == "#/c/cozinha" and await pg.evaluate(ACTIVE) == href, "Esc fecha a ficha e o foco volta para a linha que a abriu")

    # -- dentro da ficha: Mover e Excluir pelo teclado
    await row.focus()
    await pg.keyboard.press("Enter")
    await pg.wait_for_selector("dialog.sheet h1")
    await pg.focus('dialog.sheet [data-act="item-move"]')
    await pg.keyboard.press("Enter")
    await pg.wait_for_selector("#mv-room")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("#mv-room", state="detached", timeout=4000)
    r.eq(await pg.evaluate(ACTIVE), "item-move", "Esc no Mover: o foco volta para o botão Mover")
    await pg.focus('dialog.sheet [data-act="item-delete"]')
    await pg.keyboard.press("Enter")
    await pg.wait_for_selector('[data-r="0"]')
    await pg.wait_for_timeout(100)
    r.eq(await pg.evaluate(ACTIVE), "0", "Excluir: o foco começa em Cancelar")
    (o1, i1), (o2, i2) = await walk_tab(pg, 8), await walk_tab(pg, 8, back=True)
    r.check(not o1 + o2 and i1 + i2 >= 8, f"Tab e Shift+Tab na pergunta não vão para a ficha atrás dela ({(o1 + o2)[:2]})")
    await pg.focus('[data-r="0"]')
    await pg.keyboard.press("Enter")
    await pg.wait_for_selector('[data-r="0"]', state="detached", timeout=4000)
    r.check(len(r.data()["items"]) == 38 and await pg.evaluate(ACTIVE) == "item-delete", "Enter em Cancelar não exclui, e o foco volta para Excluir")

    # -- visualizador: setas e Esc
    await pg.click("dialog.sheet .gal-main")
    await pg.wait_for_selector("dialog.viewer")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("dialog.viewer", state="detached", timeout=4000)
    r.eq(await pg.locator("dialog.sheet[open]").count(), 1, "Esc na foto grande fecha só ela e a ficha fica")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("dialog.sheet", state="detached", timeout=4000)
    await r.open(pg, "#/c/sala", ".rhead")
    await pg.focus(".strip .ph >> nth=0")
    await pg.keyboard.press("Enter")
    await pg.wait_for_selector("dialog.viewer")
    pos = []
    for k in ("ArrowLeft", "ArrowLeft", "ArrowRight"):
        await pg.keyboard.press(k)
        pos.append(await pg.text_content("dialog.viewer .pos"))
    r.eq(pos, ["3 de 3", "2 de 3", "3 de 3"], "setas para os lados passam as fotos do cômodo, dando a volta")
    await pg.focus("#v-label")
    await pg.keyboard.press("ArrowLeft")
    r.eq(await pg.text_content("dialog.viewer .pos"), "3 de 3", "na legenda, as setas andam no texto e não trocam a foto")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("dialog.viewer", state="detached", timeout=4000)
    r.eq(await pg.evaluate("document.activeElement.dataset.act + ':' + document.activeElement.dataset.i"), "viewer-room:0", "Esc fecha a foto e o foco volta para ela na fileira")

    # -- cadastro: Tab não sai, Ctrl+Enter no texto dos detalhes, foco de volta
    await pg.focus('.rhead-actions [data-act="item-new"]')
    await pg.keyboard.press("Enter")
    await pg.wait_for_selector("#f-name")
    (o1, i1), (o2, i2) = await walk_tab(pg, 30), await walk_tab(pg, 30, back=True)
    r.check(not o1 + o2 and i1 + i2 >= 55, f"Tab e Shift+Tab no cadastro não vão para a página de trás ({(o1 + o2)[:2]}, {i1 + i2} de 60 dentro)")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("#f-name", state="detached", timeout=4000)
    r.eq(await pg.evaluate(ACTIVE), "item-new", "Esc sem mudar nada: o foco volta para Adicionar item")
    await pg.keyboard.press("Enter")
    await pg.wait_for_function("document.activeElement && document.activeElement.id === 'f-name'", timeout=3000)
    await pg.keyboard.type("Vela aromática")
    await pg.focus("#f-details")
    await pg.keyboard.type("Pote de vidro")
    await pg.keyboard.press("Enter")
    await pg.keyboard.type("Cheiro de lavanda")
    r.check(await pg.input_value("#f-details") == "Pote de vidro\nCheiro de lavanda" and await pg.locator("#f-name").count() == 1,
            "Enter nos detalhes pula a linha, sem salvar")
    await pg.keyboard.press("Control+Enter")
    await pg.wait_for_selector("#f-name", state="detached", timeout=5000)
    vela = r.item_named("Vela aromática")
    r.check(vela is not None and vela["details"] == "Pote de vidro\nCheiro de lavanda", "Ctrl+Enter nos detalhes salva, com as duas linhas")
    await pg.wait_for_timeout(300)
    focus_after = await pg.evaluate(ACTIVE)
    r.eq(focus_after, "item-new", "depois de salvar, o foco volta para Adicionar item")

    # -- Enter nos formulários de uma linha
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    await pg.click('[data-act="cat-new"]')
    await pg.wait_for_function("document.activeElement && document.activeElement.id === 'cn-name'", timeout=3000)
    await pg.keyboard.type("Ferramentas")
    await pg.keyboard.press("Enter")
    await pg.locator(".toast", has_text="Ferramentas criada").wait_for(timeout=5000)
    r.check(any(c["name"] == "Ferramentas" for c in r.data()["cats"]), "Nova categoria: Enter no nome cria")
    await r.open(pg, "#/comodos", ".ilist.rooms")
    await pg.click('#view [data-act="room-new"]')
    await pg.wait_for_function("document.activeElement && document.activeElement.id === 'rn-name'", timeout=3000)
    await pg.keyboard.type("Garagem")
    await pg.keyboard.press("Enter")
    await pg.wait_for_timeout(800)
    created = any(x["name"] == "Garagem" for x in r.data()["rooms"])
    await r.shot(pg, "novo-comodo-enter")
    r.check(created, "Novo cômodo: Enter no nome cria")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)

    # -- abas de Mais: setas, Home e End
    await r.open(pg, "#/mais", ".more-tabs")
    await pg.focus("#mt-dados")
    seq = []
    for k in ("ArrowLeft", "Home", "End", "ArrowRight"):
        await pg.keyboard.press(k)
        await pg.wait_for_timeout(250)
        seq.append([hash_(pg), await pg.evaluate("document.activeElement.id")])
    r.eq(seq, [["#/mais/opcoes", "mt-opcoes"], ["#/mais", "mt-dados"], ["#/mais/opcoes", "mt-opcoes"], ["#/mais", "mt-dados"]],
         "abas de Mais: seta para a esquerda dá a volta, Home e End vão às pontas, e o foco acompanha")
    tabidx = await pg.evaluate("[...document.querySelectorAll('.more-tabs [role=tab]')].map(t => t.tabIndex)")
    r.check(len(tabidx) >= 4 and tabidx[0] == 0 and set(tabidx[1:]) == {-1}, f"só a aba atual entra no Tab; as outras, pelas setas ({tabidx})")
    await ctx.close()
    await b.close()


main("teclado", body)
