"""A ficha do item: galeria com miniaturas, foto grande com setas, o site de origem da foto da internet, os links do cômodo
e da categoria, item sem foto, a quantidade, e os botões (Editar, Mover, Duplicar, Excluir) e o que cada um abre, no celular e no computador."""
from e2e_lib import OVERFLOW, main

LOJA = "https://www.lojaexemplo.com.br/moveis/painel-de-tv"


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


def hash_(pg):
    return "#" + pg.url.split("#", 1)[1] if "#" in pg.url else "#/"


async def main_src(pg):
    return (await pg.get_attribute("dialog.sheet .gal-main img", "src")).split("/")[-1]


async def back_to_sheet(pg):
    """Fecha a janela de cima (Esc) e espera a ficha ser a única aberta."""
    await pg.keyboard.press("Escape")
    await pg.wait_for_function("document.querySelectorAll('dialog[open]').length === 1 && document.querySelector('dialog.sheet[open]')", timeout=4000)


async def body(r, p):
    r.start(search=False)
    it = r.api("POST", "api/items", {"name": "Painel de TV com estante", "room": "sala", "zone": "Rack", "cat": "moveis", "value": 890,
                                     "details": "Painel de madeira com nichos.", "photos": ["sala-1.jpg", "sala-2.jpg", "sala-3.jpg"],
                                     "photoSrc": {"sala-2.jpg": LOJA}})["item"]
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="kraft")

    # -- galeria
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    r.check(await pg.text_content("dialog.sheet h1") == it["name"] and await pg.get_attribute("dialog.sheet", "aria-label") == it["name"],
            "a ficha tem o nome no título e na janela")
    r.eq(await main_src(pg), "sala-1.jpg", "a foto grande é a primeira (a capa)")
    r.eq(await pg.get_attribute("dialog.sheet .gal-main img", "alt"), f"Foto de {it['name']}", "a foto grande diz o que é")
    thumbs = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .gal-thumbs button')].map(b => [b.getAttribute('aria-label'), b.getAttribute('aria-current')])")
    r.eq(thumbs, [["Foto 1", "true"], ["Foto 2", "false"], ["Foto 3", "false"]], "três miniaturas, a primeira marcada")
    r.eq(await pg.locator("dialog.sheet .gal-src").count(), 0, "foto tirada em casa: sem aviso de foto ilustrativa")
    await pg.click('dialog.sheet .gal-thumbs [aria-label="Foto 2"]')
    r.check(await main_src(pg) == "sala-2.jpg" and await pg.get_attribute('dialog.sheet .gal-thumbs [aria-label="Foto 2"]', "aria-current") == "true",
            "tocar na segunda miniatura troca a foto grande e marca a miniatura")
    r.eq(txt(await pg.text_content("dialog.sheet .gal-src")), "Foto ilustrativa de lojaexemplo.com.br", "foto da internet: diz o site de origem")
    link = await pg.evaluate("(a => [a.href, a.target, a.rel])(document.querySelector('dialog.sheet .gal-src a'))")
    r.check(link[0] == LOJA and link[1] == "_blank" and "noopener" in link[2], f"o site abre a página do produto em outra aba ({link})")
    r.check(await pg.evaluate(OVERFLOW), "ficha sem rolagem para o lado")
    await r.shot(pg, "galeria-cel")

    # -- foto grande e setas
    await pg.click("dialog.sheet .gal-main")
    await pg.wait_for_selector("dialog.viewer")
    pos = lambda: pg.text_content("dialog.viewer .pos")  # noqa: E731
    r.check(await pos() == "2 de 3" and (await pg.get_attribute("dialog.viewer .vimg img", "src")).endswith("photos/sala-2.jpg"),
            "a foto grande abre na foto que estava na ficha, no tamanho original")
    seq = []
    for btn in ("next", "next", "prev"):
        await pg.click(f'dialog.viewer [data-v="{btn}"]')
        seq.append(await pos())
    r.eq(seq, ["3 de 3", "1 de 3", "3 de 3"], "as setas passam as fotos e dão a volta")
    r.check(txt(await pg.text_content("dialog.viewer .cap")) == it["name"] and await pg.locator("dialog.viewer .vacts").count() == 0,
            "a legenda é o nome do item, sem os botões das fotos do cômodo")
    names = await pg.evaluate("[...document.querySelectorAll('dialog.viewer .vlist a span:first-child')].map(e => e.textContent)")
    r.check(it["name"] in names and "Estante de madeira com três prateleiras" in names, f"lista os itens que aparecem na foto ({len(names)})")
    await r.shot(pg, "visualizador")
    await pg.click('dialog.viewer [data-v="close"]')
    await pg.wait_for_selector("dialog.viewer", state="detached")
    r.check(await pg.locator("dialog.sheet[open]").count() == 1 and hash_(pg) == f"#/i/{it['id']}", "fechar a foto volta para a ficha")

    # -- links: categoria e cômodo
    await pg.click("dialog.sheet .props a[href^='#/buscar']")
    await pg.wait_for_selector(".sbar")
    await pg.wait_for_timeout(300)
    r.check(hash_(pg) == "#/buscar?cat=moveis&ord=val" and await pg.input_value('[data-input="search-cat"]') == "moveis" and await pg.locator("dialog[open]").count() == 0,
            "a categoria abre a busca só com Móveis, por valor")
    await pg.go_back()
    await pg.wait_for_selector("dialog.sheet h1", timeout=4000)
    r.eq(await pg.text_content("dialog.sheet h1"), it["name"], "Voltar da busca reabre a ficha")
    await pg.click("dialog.sheet .props a[href='#/c/sala']")
    await pg.wait_for_selector(".rhead h1")
    await pg.wait_for_timeout(300)
    r.check(await pg.text_content(".rhead h1") == "Sala de estar" and await pg.locator("dialog[open]").count() == 0, "o cômodo abre a página do cômodo")

    # -- botões: no celular, só ícones com nome; o que cada um abre
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    btns = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .dlg-f .btn')].map(b => [b.dataset.act, b.getAttribute('aria-label'), b.innerText.trim()])")
    r.eq(btns, [["item-delete", "Excluir", ""], ["item-move", "Mover", ""], ["item-dup", "Duplicar", ""], ["item-edit", None, "Editar"]],
         "celular: Excluir, Mover e Duplicar só com o ícone (e o nome para o leitor de tela); Editar com o texto")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    r.check(await pg.text_content("dialog.modal h2") == "Editar item" and await pg.input_value("#f-name") == it["name"], "Editar abre o cadastro do item")
    await back_to_sheet(pg)
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-room")
    r.eq(await pg.input_value("#mv-room"), "sala", "Mover abre com o cômodo atual escolhido")
    await pg.click("dialog.modal [data-ok]")
    t = pg.locator(".toast", has_text="O item já está em Sala de estar")
    await t.wait_for(timeout=4000)
    r.check(await pg.locator("#mv-room").count() == 0, "Mover para o mesmo cômodo: só avisa, sem mudar nada")
    await pg.click('dialog.sheet [data-act="item-delete"]')
    await pg.wait_for_selector('[data-r="1"]')
    r.check(it["name"] in await pg.text_content("dialog[open]:last-of-type .dlg-b"), "Excluir pergunta, com o nome do item")
    await pg.click('[data-r="0"]')
    await pg.wait_for_timeout(400)
    r.check(any(i["id"] == it["id"] for i in r.data()["items"]) and await pg.locator("dialog.sheet[open]").count() == 1, "Cancelar não exclui e a ficha fica")
    await pg.click('dialog.sheet [data-act="item-dup"]')
    await pg.wait_for_selector("#f-name")
    r.check(await pg.text_content("dialog.modal h2") == "Duplicar item" and await pg.locator("[data-slot=photos] .ph img").count() == 3, "Duplicar abre o cadastro com os dados e as fotos")
    await pg.fill("#f-name", "Painel de TV do quarto")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    dup = r.item_named("Painel de TV do quarto")
    r.check(dup and dup["id"] != it["id"] and dup["photos"] == it["photos"] and (dup.get("photoSrc") or {}).get("sala-2.jpg") == LOJA,
            "a cópia é outro item, com as mesmas fotos e o site de origem")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)

    # -- item sem foto; quantidade; alterado por
    await r.open(pg, "#/i/coz-005", "dialog.sheet h1")
    r.eq(txt(await pg.text_content("dialog.sheet .gal-none > span")), "Sem foto", "item sem foto: Sem foto no lugar da galeria")
    acts = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .gal-none .btn')].map(b => b.textContent.trim())")
    r.eq(acts, ["Adicionar foto", "Buscar na internet"], "com Adicionar foto e Buscar na internet")
    await r.shot(pg, "sem-foto")
    await pg.click('dialog.sheet .gal-none [data-act="item-edit"]')
    await pg.wait_for_selector('[data-ed="upload"]')
    r.check(await pg.input_value("#f-name") == "Micro-ondas 30 L", "Adicionar foto abre o cadastro, com o Enviar foto")
    await back_to_sheet(pg)
    await r.open(pg, "#/i/sal-002", "dialog.sheet h1")
    r.eq(txt(await pg.text_content("dialog.sheet .ival .unit")), "2 unidades, R$ 45 cada", "quantidade 2: o valor de cada uma")
    props = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .props dt')].map(d => d.textContent)")
    r.check("Origem" in props and "Cadastrado" in props and "Alterado" not in props, f"nunca alterado: sem a linha Alterado ({props})")
    await ctx.close()

    # -- computador: painel do lado, botões com o nome
    ctx, pg = await r.page(b, "pc", "light", accent="kraft")
    await r.open(pg, f"#/i/{dup['id']}", "dialog.sheet h1")
    box = await pg.evaluate("""(r => [Math.round(r.width), Math.round(innerWidth - r.right), Math.round(r.height)])(
      document.querySelector('dialog.sheet').getBoundingClientRect())""")
    r.check(box[0] == 560 and 0 <= box[1] <= 16 and box[2] == 900, f"computador: a ficha é um painel de 560 px à direita (fora a barra de rolagem), da altura da tela ({box})")
    labels = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .dlg-f .btn')].map(b => b.textContent.trim())")
    r.eq(labels, ["Excluir", "Mover", "Duplicar", "Editar"], "computador: os botões com o nome")
    r.check(await pg.locator(".side, #view").first.is_visible(), "a página continua atrás da ficha")
    props = await pg.evaluate("Object.fromEntries([...document.querySelectorAll('dialog.sheet .props dt')].map(d => [d.textContent, d.nextElementSibling.textContent.trim()]))")
    r.check(props.get("Cadastrado", "").endswith("por Diego"), f"quem cadastrou aparece ({props.get('Cadastrado')})")
    await r.shot(pg, "pc")
    await pg.click('dialog.sheet [data-act="sheet-close"]')
    await pg.wait_for_selector("dialog.sheet", state="detached", timeout=4000)
    r.check(hash_(pg) == "#/c/sala", f"o X fecha a ficha e fica no cômodo do item ({hash_(pg)})")
    await ctx.close()
    await b.close()


main("ficha", body)
