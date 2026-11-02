"""Itens: ficha, cadastro com foto, salvar e adicionar outro, editar, mover, duplicar, excluir e desfazer, conflito, rascunho e atalhos."""
import os

from e2e_lib import OVERFLOW, helpers, main


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    foto = os.path.join(helpers.FIXTURE, "photos", "quarto-1.jpg")

    for size, scheme in (("cel", "dark"), ("pc", "light")):
        ctx, pg = await r.page(b, size, scheme, accent="azul")
        # ficha do item
        await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
        r.eq(await pg.text_content("dialog.sheet h1"), "Sofá de 3 lugares cinza-azulado", f"[{size}] ficha abre pelo endereço")
        r.eq((await pg.text_content("dialog.sheet .ival .big")).replace("\xa0", " "), "R$ 1.800", f"[{size}] valor")
        r.eq(await pg.text_content("dialog.sheet .dlg-h .mt"), "SAL-001", f"[{size}] código do item")
        props = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .props dt')].map(e => e.textContent)")
        r.check({"Cômodo", "Categoria", "Quantidade"} <= set(props), f"[{size}] dados da ficha ({props})")
        r.check(await pg.locator("dialog.sheet .gal-main img").count() == 1, f"[{size}] foto na ficha")
        r.check(await pg.evaluate(OVERFLOW), f"[{size}] ficha sem rolagem para o lado")
        await r.shot(pg, f"ficha-{size}")
        await pg.go_back()
        await pg.wait_for_timeout(400)
        r.eq(await pg.locator("dialog[open]").count(), 0, f"[{size}] Voltar fecha a ficha")
        await ctx.close()

    ctx, pg = await r.page(b, "cel", "dark")
    # cadastro com foto, valor e quantidade
    await r.open(pg, "#/c/escritorio", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    r.eq(await pg.input_value("#f-room"), "escritorio", "dentro do cômodo, o item novo vai para ele")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-ed="upload"]')
    await (await fc.value).set_files(foto)
    await pg.wait_for_selector('[data-slot="photos"] .ph img', timeout=10000)
    await pg.click('[data-ed="save"]')
    await pg.wait_for_timeout(300)
    r.check(await pg.is_visible('[data-err="name"]'), "sem nome, o editor avisa")
    await pg.fill("#f-name", "Luminária de mesa")
    await pg.fill("#f-details", "Braço articulado")
    await pg.select_option("#f-cat", "decoracao")
    await pg.fill("#f-qty", "2")
    await pg.fill("#f-value", "1.234,50")
    unit = (await pg.text_content('[data-slot="unit"]')).replace("\xa0", " ")
    r.eq(unit, "R$ 617,25 cada", "valor por unidade")
    await r.shot(pg, "editor-novo")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    it = r.item_named("Luminária de mesa")
    r.check(it and (it["value"], it["qty"], it["cat"], it["room"], len(it["photos"]), it["createdBy"]) == (1234.5, "2", "decoracao", "escritorio", 1, "Diego"),
            f"item salvo com tudo ({it and (it['value'], it['qty'], it['cat'], it['room'], len(it['photos']))})")
    toast = await pg.text_content(".toast")
    r.check("Item adicionado" in toast, f"aviso com Ver ({toast.strip()})")

    # salvar e adicionar outro
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-name", "Grampeador")
    await pg.click('[data-ed="again"]')
    await pg.wait_for_timeout(700)
    r.eq(await pg.input_value("#f-name"), "", "Salvar e adicionar outro limpa o nome")
    r.eq(await pg.input_value("#f-room"), "escritorio", "e mantém o cômodo")
    r.check(r.item_named("Grampeador") is not None, "o primeiro foi salvo")
    await pg.fill("#f-name", "rascunho")
    await pg.go_back()
    await pg.wait_for_selector('[data-r="1"]', timeout=4000)
    r.check(True, "Voltar com rascunho pergunta antes de descartar")
    await pg.click('[data-r="0"]')
    await pg.wait_for_timeout(300)
    r.eq(await pg.input_value("#f-name"), "rascunho", "Continuar editando mantém o rascunho")
    await pg.click('[data-ed="cancel"]')
    await pg.click('[data-r="1"]')
    await pg.wait_for_timeout(400)
    r.eq(await pg.locator("dialog[open]").count(), 0, "Descartar fecha")

    # editar
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-name", "Luminária de mesa preta")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached")
    await pg.wait_for_timeout(300)
    r.eq(await pg.text_content("dialog.sheet h1"), "Luminária de mesa preta", "a ficha mostra o nome novo")

    # mover
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-room")
    await pg.select_option("#mv-room", "quarto")
    await pg.click("dialog.modal [data-ok]")
    await pg.wait_for_timeout(700)
    moved = next(i for i in r.data()["items"] if i["id"] == it["id"])
    r.eq(moved["room"], "quarto", "Mover leva para o outro cômodo")
    r.check((await pg.text_content("dialog.sheet .dlg-h .mt")).startswith("QUA-"), "e o código muda")

    # duplicar
    await pg.click('dialog.sheet [data-act="item-dup"]')
    await pg.wait_for_selector("#f-name")
    r.eq(await pg.input_value("#f-name"), "Luminária de mesa preta", "Duplicar abre com os dados")
    await pg.fill("#f-name", "Luminária de mesa branca")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_timeout(800)
    r.check(r.item_named("Luminária de mesa branca") is not None and r.item_named("Luminária de mesa preta") is not None, "a cópia é um item novo")

    # excluir e desfazer
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-delete"]')
    await pg.wait_for_selector('[data-r="1"]')
    await pg.click('[data-r="1"]')
    await pg.wait_for_timeout(700)
    r.check(not any(i["id"] == it["id"] for i in r.data()["items"]), "Excluir tira o item")
    await pg.locator(".toast", has_text="Item excluído").locator("button").click()
    await pg.wait_for_timeout(700)
    back = next((i for i in r.data()["items"] if i["id"] == it["id"]), None)
    r.check(back is not None and back["room"] == "quarto", "Desfazer devolve o item, no mesmo cômodo")

    # conflito com outro aparelho
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    import time
    time.sleep(1.05)
    r.api("PUT", f"api/items/{it['id']}", {"name": "Mudado no outro celular"})
    await pg.fill("#f-name", "Mudado aqui")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector('[data-ed="theirs"]', timeout=5000)
    r.check(True, "conflito: o editor oferece carregar a versão atual ou salvar a minha")
    await r.shot(pg, "conflito")
    await pg.click('[data-ed="theirs"]')
    r.eq(await pg.input_value("#f-name"), "Mudado no outro celular", "Carregar a versão atual traz o nome de lá")
    await pg.fill("#f-name", "Mudado aqui")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_timeout(700)
    r.eq(next(i for i in r.data()["items"] if i["id"] == it["id"])["name"], "Mudado aqui", "e depois salva por cima")
    await ctx.close()

    # computador: atalhos
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/c/cozinha", ".rhead")
    await pg.locator("body").click(position={"x": 5, "y": 500})
    await pg.keyboard.press("n")
    await pg.wait_for_selector("#f-name", timeout=4000)
    r.check(True, "N abre o cadastro")
    await pg.fill("#f-name", "Tábua de corte")
    await pg.keyboard.press("Control+Enter")
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=5000)
    r.check(r.item_named("Tábua de corte") is not None, "Ctrl+Enter salva")
    await pg.keyboard.press("/")
    await pg.wait_for_timeout(500)
    r.check("#/buscar" in pg.url, "/ abre a busca")
    await r.shot(pg, "atalhos-pc")
    await ctx.close()
    await b.close()


main("itens", body)
