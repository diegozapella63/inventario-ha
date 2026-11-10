"""Desfazer em cada lugar que oferece (excluir item, foto da internet e dados do produto na ficha, Preencher com IA no cadastro),
Mover (que ainda não oferece), e os avisos empilhados: no máximo três, cada Desfazer volta o seu item, e o aviso com uma janela aberta."""
import time

from e2e_lib import main

KEEP = ("id", "seq", "room", "zone", "name", "details", "cat", "qty", "value", "photos", "createdAt")
# o botão do aviso está por cima de tudo (dá para tocar), ou atrás de uma janela aberta?
TOAST_ON_TOP = """(() => { const b = [...document.querySelectorAll('.toast button')].pop(); if (!b) return null;
  const r = b.getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!e && b.contains(e); })()"""


def item(r, iid):
    return next((i for i in r.data()["items"] if i["id"] == iid), None)


def snap(it):
    return {k: it.get(k) for k in KEEP}


async def delete_from_room(pg, row_name):
    await pg.locator("#view .irow", has_text=row_name).click()
    await pg.wait_for_selector("dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-delete"]')
    await pg.click('[data-r="1"]')
    await pg.wait_for_selector("dialog.sheet", state="detached", timeout=5000)
    await pg.wait_for_selector("dialog[open]", state="detached", timeout=5000)


async def body(r, p):
    r.start(search=True)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", "light", accent="rosa")

    # -- excluir e desfazer: volta igual, com o mesmo código
    before = snap(item(r, "sal-005"))
    await r.open(pg, "#/c/sala", ".rhead")
    await delete_from_room(pg, "Quadro de paisagem")
    r.check(item(r, "sal-005") is None and await pg.locator("#view .irow", has_text="Quadro de paisagem").count() == 0, "Excluir tira o item da lista e do servidor")
    t = pg.locator(".toast", has_text="Item apagado")
    r.eq((await t.locator("button").text_content()).strip(), "Desfazer", "o aviso oferece Desfazer")
    await t.locator("button").click()
    await pg.locator(".toast", has_text="Item restaurado").wait_for(timeout=5000)
    r.eq(snap(item(r, "sal-005") or {}), before, "Desfazer devolve o item igual: mesmo código, cômodo, zona, fotos e data do cadastro")
    r.check(await t.count() == 0 and await pg.locator("#view .irow", has_text="SAL-005").count() == 1, "o aviso de excluído some e o item volta à lista")

    # -- avisos empilhados: no máximo três; cada Desfazer volta o seu
    for name in ("Soundbar", "Caixa de som de estante", "Tapete listrado", "Almofadas decorativas"):
        await delete_from_room(pg, name)
    msgs = await pg.locator(".toast .tmsg").all_text_contents()
    r.eq(msgs, ["Item apagado"] * 3, "quatro exclusões seguidas: ficam só os três avisos mais novos")
    ids = {"Soundbar": "sal-009", "Caixa de som de estante": "sal-010", "Tapete listrado": "sal-006", "Almofadas decorativas": "sal-002"}
    r.check(all(item(r, i) is None for i in ids.values()), "os quatro saíram")
    await pg.locator(".toast", has_text="Item apagado").first.locator("button").click()
    await pg.locator(".toast", has_text="Item restaurado").wait_for(timeout=5000)
    r.check(item(r, "sal-010") is not None and item(r, "sal-006") is None and item(r, "sal-002") is None,
            "Desfazer no aviso mais antigo que sobrou volta a Caixa de som (a segunda), só ela")
    await pg.locator(".toast", has_text="Item apagado").last.locator("button").click()
    await pg.wait_for_timeout(800)
    r.check(item(r, "sal-002") is not None and item(r, "sal-006") is None, "Desfazer no mais novo volta as Almofadas")
    r.eq(item(r, "sal-009"), None, "o aviso que saiu da pilha (Soundbar) não tem mais como desfazer")
    await r.shot(pg, "avisos-empilhados")

    # -- com uma janela aberta depois do aviso
    await r.open(pg, "#/c/sala", ".rhead")
    await delete_from_room(pg, "Luminária de chão")
    await pg.locator(".toast", has_text="Item apagado").wait_for()
    await pg.locator("body").click(position={"x": 5, "y": 600})
    await pg.keyboard.press("n")
    await pg.wait_for_selector("#f-name")
    await pg.wait_for_timeout(300)
    on_top = await pg.evaluate(TOAST_ON_TOP)
    await r.shot(pg, "aviso-com-janela")
    r.check(on_top, "o Desfazer de antes continua à mão com o cadastro aberto")
    await pg.keyboard.press("Escape")
    await pg.wait_for_selector("#f-name", state="detached", timeout=4000)
    await pg.locator(".toast", has_text="Item apagado").locator("button").click()
    await pg.wait_for_timeout(800)
    r.check(item(r, "sal-003") is not None, "fechada a janela, o Desfazer funciona")

    # -- Mover: sem Desfazer (o item muda de código)
    await r.open(pg, "#/i/sal-004", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.select_option("#mv-room", "varanda")
    await pg.click("dialog.modal [data-ok]")
    t = pg.locator(".toast", has_text="Movido para Varanda")
    await t.wait_for(timeout=4000)
    moved = item(r, "sal-004")
    r.check(moved["room"] == "varanda" and (await pg.text_content("dialog.sheet .dlg-h .mt")).startswith("VAR-"), "Mover leva para a Varanda, com código novo")
    has_undo = await t.locator("button").count()
    r.check(has_undo == 1, "o aviso de Mover oferece Desfazer, que devolve o cômodo e o código")
    await r.shot(pg, "mover")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)

    # -- foto da internet na ficha (item sem foto, já com detalhes, valor e categoria): Desfazer tira só a foto
    micro = item(r, "coz-005")
    await r.open(pg, "#/i/coz-005", 'dialog.sheet [data-act="web-photo"]')
    await pg.click('dialog.sheet [data-act="web-photo"]')
    await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
    r.eq(await pg.locator(".wprod").count(), 0, "item já completo: só a foto, sem dados para preencher")
    await pg.locator(".wimg").first.click()
    await pg.click("dialog [data-ok]")
    t = pg.locator(".toast", has_text="adicionada")
    await t.wait_for(timeout=15000)
    r.check(len(item(r, "coz-005")["photos"]) == 1 and (await t.locator(".tmsg").text_content()).startswith("Foto de 127.0.0.1"),
            "a foto entra, e o aviso diz de que site veio")
    await t.locator("button").click()
    await pg.wait_for_selector("dialog.sheet .gal-none", timeout=5000)
    after = item(r, "coz-005")
    r.check(after["photos"] == [] and not after.get("photoSrc") and (after["details"], after["value"], after["cat"]) == (micro["details"], micro["value"], micro["cat"]),
            "Desfazer tira a foto e o site de origem, e o resto fica")

    # -- dados do produto na ficha: outro aparelho mudou o item antes do Desfazer
    vazio = r.api("POST", "api/items", {"name": "Cafeteira", "room": "cozinha", "value": 0})["item"]
    await r.open(pg, f"#/i/{vazio['id']}", 'dialog.sheet [data-act="web-photo"]')
    await pg.click('dialog.sheet [data-act="web-photo"]')
    await pg.wait_for_selector(".wprod [data-only]", timeout=20000)
    await pg.click(".wprod [data-only]")
    t = pg.locator(".toast", has_text="Dados do produto preenchidos")
    await t.wait_for(timeout=5000)
    filled = item(r, vazio["id"])
    r.check(filled["value"] == 450 and filled["cat"] == "cozinha", "Usar só os dados preenche valor e categoria")
    time.sleep(1.05)
    r.api("PUT", f"api/items/{vazio['id']}", {"flag": "Mudado no outro celular"})
    await t.locator("button").click()
    err = pg.locator(".toast.err")
    await err.wait_for(timeout=5000)
    now = item(r, vazio["id"])
    r.check(now["value"] == 450 and now["flag"] == "Mudado no outro celular" and "outro aparelho" in await err.text_content(),
            "Desfazer depois de outro aparelho mudar o item: avisa e não passa por cima")
    await r.shot(pg, "desfazer-conflito")
    await ctx.close()

    # -- Preencher com IA no cadastro (celular)
    ctx, pg = await r.page(b, "cel", "dark", accent="rosa")
    await r.open(pg, "#/c/escritorio", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector('[data-ed="roomphotos"]')
    await pg.click('[data-ed="roomphotos"]')
    await pg.locator("dialog .pick label").first.click()
    await pg.click("dialog[open]:last-of-type [data-ok]")
    await pg.wait_for_selector('[data-ed="ai"]', timeout=5000)
    await pg.fill("#f-name", "abajur")
    await pg.fill("#f-value", "50")
    await pg.click('[data-ed="ai"]')
    t = pg.locator(".toast", has_text="Campos preenchidos pela IA")
    await t.wait_for(timeout=15000)
    r.check(await pg.input_value("#f-name") == "Luminária de mesa articulada preta" and await pg.input_value("#f-cat") == "decoracao",
            "Preencher com IA troca os campos e avisa, com Desfazer")
    r.check(await pg.evaluate("!!document.querySelector('dialog.modal[open] #toasts')"), "o aviso aparece dentro do cadastro, à mão")
    await t.locator("button").click()
    vals = await pg.evaluate("['f-name', 'f-details', 'f-cat', 'f-value'].map(i => document.getElementById(i).value)")
    r.eq(vals, ["abajur", "", "", "50"], "Desfazer volta o que estava escrito")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    r.eq(r.item_named("abajur")["source"], "manual", "e o item salvo fica como Cadastro manual, não Leitura por IA")
    await ctx.close()
    await b.close()


main("desfazer", body)
