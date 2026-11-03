"""Cadastro de item, campo a campo: nome obrigatório, valor ("1.234,50", "R$ 2.000", inválido), quantidade ("2", "1 par", "~3")
e o valor por unidade, detalhes longos, observação, categoria (Outros quando não escolhe, e a criada em Opções), cômodo
(o último usado) e Esc/Cancelar com e sem alteração."""
from e2e_lib import OVERFLOW, main

# o corpo da janela não rola para o lado (uma palavra comprida, como um endereço, quebra a linha)
NO_SIDE_SCROLL = "[...document.querySelectorAll('dialog[open] .dlg-b')].every(b => b.scrollWidth <= b.clientWidth + 1)"


def txt(s):
    return (s or "").replace("\xa0", " ").strip()


async def open_new(r, pg, where="#/", opener='.top-actions [data-act="item-new"]'):
    await r.open(pg, where, ".tag, .rhead, .more-tabs")
    await pg.click(opener)
    await pg.wait_for_selector("#f-name")
    if not await pg.evaluate("matchMedia('(pointer: coarse)').matches"):  # no computador, o cursor vai sozinho para o nome: espera, para não digitar antes
        await pg.wait_for_function("document.activeElement && document.activeElement.id === 'f-name'", timeout=3000)


async def save_and_wait(pg):
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    await pg.wait_for_timeout(200)


async def body(r, p):
    r.start(search=False)
    n0 = len(r.data()["items"])
    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", "light", accent="verde")

    # -- como abre
    await open_new(r, pg)
    r.check(await pg.text_content("dialog.modal .dlg-h h2") == "Novo item" and await pg.input_value("#f-qty") == "1"
            and await pg.input_value("#f-value") == "" and await pg.input_value("#f-cat") == "",
            "Novo item: quantidade 1, valor e categoria vazios")
    r.eq(await pg.input_value("#f-room"), "sala", "sem cômodo usado antes, vem o primeiro da casa")
    await pg.wait_for_function("document.activeElement && document.activeElement.id === 'f-name'", timeout=3000)
    r.check(await pg.is_visible('[data-ed="again"]') and txt(await pg.text_content('[data-ed="save"]')) == "Salvar item",
            "no computador, o cursor já está no nome; botões Salvar item e Salvar e adicionar outro")

    # -- nome obrigatório
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector('[data-err="name"]:not([hidden])', timeout=3000)
    r.eq(txt(await pg.text_content('[data-err="name"]')), "Dê um nome ao item.", "sem nome: aviso embaixo do campo")
    r.check(await pg.get_attribute("#f-name", "aria-invalid") == "true" and await pg.evaluate("document.activeElement.id") == "f-name"
            and len(r.data()["items"]) == n0, "o campo fica marcado como inválido, recebe o cursor e nada é gravado")
    await pg.fill("#f-name", "Furadeira de impacto")
    r.check(await pg.is_hidden('[data-err="name"]') and await pg.get_attribute("#f-name", "aria-invalid") == "false", "ao digitar o nome, o aviso some")

    # -- valor inválido
    got = []
    for bad in ("doze reais", "-50", "1.2.3"):
        await pg.fill("#f-value", bad)
        await pg.click('[data-ed="save"]')
        await pg.wait_for_selector('[data-err="value"]:not([hidden])', timeout=3000)
        got.append((txt(await pg.text_content('[data-err="value"]')), await pg.evaluate("document.activeElement.id")))
    r.check(all(g == ("Use só números, como 1200 ou 1.200,50.", "f-value") for g in got) and len(r.data()["items"]) == n0,
            f"valor 'doze reais', '-50' ou '1.2.3': aviso com um exemplo, o cursor vai para o valor e nada é gravado ({got[0]})")
    await pg.fill("#f-name", "")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_timeout(200)
    r.check(await pg.is_visible('[data-err="name"]') and await pg.is_visible('[data-err="value"]') and await pg.evaluate("document.activeElement.id") == "f-name",
            "nome vazio e valor inválido: os dois avisos, o cursor no nome")
    await r.shot(pg, "avisos")
    await pg.fill("#f-value", "1")
    r.check(await pg.is_hidden('[data-err="value"]'), "ao corrigir o valor, o aviso some")

    # -- valor e quantidade: o valor por unidade acompanha
    await pg.fill("#f-name", "Furadeira de impacto")
    cases = [("3", "R$ 2.000", "R$ 666,67 cada"), ("~3", "300", "R$ 100 cada"), ("4", "1.000", "R$ 250 cada")]
    got = []
    for qty, val, _ in cases:
        await pg.fill("#f-qty", qty)
        await pg.fill("#f-value", val)
        got.append(txt(await pg.text_content('[data-slot="unit"]')))
    r.eq(got, [w for _, _, w in cases], "valor por unidade acompanha: 3 por R$ 2.000, ~3 por 300, 4 por 1.000")
    got = []
    for qty, val in (("1 par", "R$ 2.000"), ("1", "1.000"), ("5", "")):
        await pg.fill("#f-qty", qty)
        await pg.fill("#f-value", val)
        got.append(txt(await pg.text_content('[data-slot="unit"]')))
    r.eq(got, ["", "", ""], "sem valor por unidade com 1 par, com 1 unidade ou sem valor")
    await pg.fill("#f-value", "R$ 2.000")
    await pg.press("#f-value", "Tab")
    r.eq(await pg.input_value("#f-value"), "2.000", "R$ 2.000: ao sair do campo, fica 2.000")
    await pg.fill("#f-value", "1234,5")
    await pg.press("#f-value", "Tab")
    r.eq(await pg.input_value("#f-value"), "1.234,50", "1234,5: ao sair do campo, fica 1.234,50")

    # -- salvar: 1 par, 1.234,50, sem categoria
    await pg.fill("#f-qty", "1 par")
    await pg.fill("#f-value", "1.234,50")
    await save_and_wait(pg)
    it = r.item_named("Furadeira de impacto")
    r.check(it and (it["value"], it["qty"], it["cat"], it["room"]) == (1234.5, "1 par", "outros", "sala"),
            f"gravado: 1.234,50, 1 par, sem categoria vai para Outros ({it and (it['value'], it['qty'], it['cat'], it['room'])})")
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    props = await pg.evaluate("Object.fromEntries([...document.querySelectorAll('dialog.sheet .props dt')].map(d => [d.textContent, d.nextElementSibling.textContent.trim()]))")
    r.check(txt(await pg.text_content("dialog.sheet .ival .big")) == "R$ 1.234,50" and txt(await pg.text_content("dialog.sheet .ival .unit")) == "1 par"
            and props.get("Quantidade") == "1 par" and props.get("Categoria") == "Outros",
            f"na ficha: R$ 1.234,50, 1 par e categoria Outros ({props.get('Quantidade')}, {props.get('Categoria')})")
    # editar: o valor vem formatado, o botão diz Salvar alterações, sem Salvar e adicionar outro
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    r.check(await pg.text_content("dialog.modal .dlg-h h2") == "Editar item" and await pg.input_value("#f-value") == "1.234,50"
            and await pg.locator('[data-ed="again"]').count() == 0 and txt(await pg.text_content('[data-ed="save"]')) == "Salvar alterações",
            "editar: Editar item, valor 1.234,50, Salvar alterações e sem Salvar e adicionar outro")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)
    r.check(await pg.locator('[data-r="1"]').count() == 0 and await pg.locator("dialog.sheet[open]").count() == 1, "editar sem mudar nada: Esc fecha sem perguntar e volta para a ficha")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(400)

    # -- quantidade ~3: conta como 3
    await open_new(r, pg)
    await pg.fill("#f-name", "Pincéis de pintura")
    await pg.fill("#f-qty", "~3")
    await pg.fill("#f-value", "300")
    await save_and_wait(pg)
    it3 = r.item_named("Pincéis de pintura")
    await r.open(pg, f"#/i/{it3['id']}", "dialog.sheet h1")
    r.eq(txt(await pg.text_content("dialog.sheet .ival .unit")), "3 unidades, R$ 100 cada", "~3 na ficha: 3 unidades, R$ 100 cada")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(400)

    # -- detalhes longos e observação
    url = "https://exemplo.com/manual?arquivo=" + "furadeiradeimpactocommaleta" * 6
    longo = url + "\n" + "Furadeira com maleta, duas baterias e jogo de brocas para madeira, metal e concreto. " * 60
    await open_new(r, pg)
    await pg.fill("#f-name", "Furadeira com maleta")
    await pg.fill("#f-details", longo)
    r.eq(len(await pg.input_value("#f-details")), 4000, "detalhes aceitam até 4000 letras (o resto fica de fora)")
    r.check(not await pg.is_visible("#f-flag"), "Observação começa recolhida")
    await pg.click("details.more-fields summary")
    await pg.fill("#f-flag", "Emprestada para o vizinho")
    await save_and_wait(pg)
    itl = r.item_named("Furadeira com maleta")
    r.check(itl and len(itl["details"]) == 4000 and itl["flag"] == "Emprestada para o vizinho", f"detalhes inteiros e observação gravados ({itl and len(itl['details'])})")
    await r.open(pg, f"#/i/{itl['id']}", "dialog.sheet h1")
    r.check(txt(await pg.text_content("dialog.sheet .inote")) == "Emprestada para o vizinho"
            and await pg.evaluate("document.querySelector('dialog.sheet .idet').textContent.length") == 4000, "a ficha mostra a observação e os detalhes inteiros")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-flag")
    r.check(await pg.is_visible("#f-flag"), "item com observação: o editor já abre com ela à vista")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)
    await ctx.close()

    ctx, pg = await r.page(b, "cel", "dark", accent="verde")
    await r.open(pg, f"#/i/{itl['id']}", "dialog.sheet h1")
    r.check(await pg.evaluate(OVERFLOW), "celular: a ficha com detalhes longos não alarga a página")
    await r.shot(pg, "ficha-longa-cel", full_page=False)
    r.check(await pg.evaluate(NO_SIDE_SCROLL), "celular: um endereço comprido nos detalhes quebra a linha, sem rolar a ficha para o lado")
    await ctx.close()

    ctx, pg = await r.page(b, "pc", "light", accent="verde")
    # -- categoria nova criada em Opções aparece no cadastro
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    await pg.click('[data-act="cat-new"]')
    await pg.fill("#cn-name", "Ferramentas")
    await pg.click("dialog [data-ok]")
    await pg.locator(".toast", has_text="Ferramentas criada").wait_for(timeout=5000)
    await open_new(r, pg, "#/c/lavanderia", '.rhead-actions [data-act="item-new"]')
    opts = await pg.evaluate("[...document.querySelectorAll('#f-cat option')].map(o => o.textContent)")
    r.check(opts[-2:] == ["Ferramentas", "Outros"], f"a categoria nova aparece no cadastro, antes de Outros ({opts[-3:]})")
    await pg.fill("#f-name", "Serra tico-tico")
    await pg.select_option("#f-cat", label="Ferramentas")
    r.eq(await pg.input_value("#f-room"), "lavanderia", "dentro da Lavanderia, o item vai para ela")
    # -- cômodo: escolher outro
    await pg.select_option("#f-room", "quarto")
    await save_and_wait(pg)
    st = r.item_named("Serra tico-tico")
    r.check(st and st["cat"] == "ferramentas" and st["room"] == "quarto", f"gravado com a categoria nova e no cômodo escolhido ({st and (st['cat'], st['room'])})")
    await r.open(pg, f"#/i/{st['id']}", "dialog.sheet h1")
    r.check((await pg.text_content("dialog.sheet .dlg-h .mt")).startswith("QUA-") and "Ferramentas" in await pg.text_content("dialog.sheet .props"),
            "na ficha: código do Quarto e categoria Ferramentas")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    await open_new(r, pg)
    r.eq(await pg.input_value("#f-room"), "quarto", "o próximo item novo, fora de um cômodo, vem no último cômodo usado")

    # -- Esc e Cancelar sem alteração: fecham direto
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)
    r.eq(await pg.locator('[data-r="1"]').count(), 0, "sem alteração: Esc fecha sem perguntar")
    await open_new(r, pg)
    await pg.click('.dlg-f [data-ed="cancel"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)
    r.check(True, "sem alteração: Cancelar fecha sem perguntar")

    # -- com alteração: pergunta
    await open_new(r, pg)
    await pg.fill("#f-name", "Rascunho de teste")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector('[data-r="1"]', timeout=4000)
    r.eq(txt(await pg.text_content("dialog[open]:last-of-type h2")), "Descartar o que foi preenchido?", "com alteração: Esc pergunta antes de descartar")
    await r.shot(pg, "descartar")
    await pg.click('[data-r="0"]')
    await pg.wait_for_timeout(300)
    r.eq(await pg.input_value("#f-name"), "Rascunho de teste", "Continuar editando mantém o que foi digitado")
    await pg.click('.dlg-h [data-ed="cancel"]')
    await pg.wait_for_selector('[data-r="1"]', timeout=4000)
    await pg.click('[data-r="1"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)
    r.check(r.item_named("Rascunho de teste") is None, "o X também pergunta, e Descartar fecha sem gravar")
    # mudar só a categoria já conta como alteração
    await open_new(r, pg)
    await pg.select_option("#f-cat", "livros")
    await pg.click('.dlg-f [data-ed="cancel"]')
    await pg.wait_for_selector('[data-r="1"]', timeout=4000)
    r.check(True, "mudar só a categoria também pergunta antes de fechar")
    await pg.click('[data-r="1"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)
    # editar com alteração e descartar: nada muda no servidor
    await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-value", "9.999")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector('[data-r="1"]', timeout=4000)
    await pg.click('[data-r="1"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)
    r.check(next(i for i in r.data()["items"] if i["id"] == "sal-001")["value"] == 1800 and await pg.locator("dialog.sheet[open]").count() == 1,
            "editar, mudar o valor e descartar: o valor gravado não muda e a ficha continua aberta")
    await ctx.close()

    # -- celular: tudo cabe, com os avisos
    ctx, pg = await r.page(b, "estreito", "dark", accent="verde")
    await open_new(r, pg, "#/c/sala", '.rhead-actions [data-act="item-new"]')
    await pg.fill("#f-value", "abc")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_timeout(300)
    r.check(await pg.evaluate(OVERFLOW) and await pg.evaluate(NO_SIDE_SCROLL), "celular de 320 px: o cadastro com os avisos cabe na largura")
    await r.shot(pg, "avisos-320")
    await ctx.close()
    await b.close()


main("editor", body)
