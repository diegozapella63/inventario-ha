"""Zonas do começo ao fim: ligar em Opções, itens separados por zona com subtotal, o campo Zona com sugestões do cômodo,
a última zona lembrada, a ficha, Mover com zona, o relatório com a coluna Zona e desligar sem apagar nada."""
from e2e_lib import OVERFLOW, main

ZONES = """[...document.querySelectorAll('#view .zone')].map(s => [s.querySelector('.zone-h h3').textContent,
  s.querySelector('.zs').firstChild.textContent, s.querySelector('.zs b').textContent.replace(/\\s/g, ' '), s.querySelectorAll('.irow').length])"""
DATALIST = "(id) => [...document.querySelectorAll('#' + id + ' option')].map(o => o.value)"


def brl(v):
    return "R$ " + f"{round(v):,}".replace(",", ".")


async def switch(pg, on):
    await pg.click('label.switch:has([data-input="zones-on"])')
    await pg.locator(".toast", has_text="Zonas ligadas" if on else "Zonas desligadas").wait_for(timeout=5000)
    await pg.wait_for_timeout(200)


async def new_in(r, pg, room):
    await r.open(pg, f"#/c/{room}", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")


async def props(pg):
    return await pg.evaluate("Object.fromEntries([...document.querySelectorAll('dialog.sheet .props dt')].map(d => [d.textContent, d.nextElementSibling.textContent.trim()]))")


async def body(r, p):
    r.start(search=False)
    items = r.data()["items"]
    sala = sorted((i for i in items if i["room"] == "sala"), key=lambda i: i["seq"])
    groups = {}
    for i in sala:
        g = groups.setdefault(i["zone"], [0, 0])
        g[0] += 1
        g[1] += i["value"]
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="turquesa")

    # -- ligar
    await r.open(pg, "#/c/sala", ".rhead")
    r.eq(await pg.locator("#view .zone-h").count(), 0, "de início, zonas desligadas: a sala é uma lista só")
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    await switch(pg, True)
    r.check(r.data()["settings"]["zones"] is True and await pg.is_checked('[data-input="zones-on"]'), "a chave liga as zonas para a casa toda")

    # -- o cômodo separado por zona, com subtotal
    await r.open(pg, "#/c/sala", ".rhead")
    got = await pg.evaluate(ZONES)
    want = [[z, f"{n} {'item' if n == 1 else 'itens'}", brl(v), n] for z, (n, v) in groups.items()]
    r.eq(got, want, "cada zona com quantos itens e o subtotal, na ordem dos itens")
    r.eq(sum(int(x[2].replace("R$ ", "").replace(".", "")) for x in got), sum(i["value"] for i in sala), "os subtotais somam o total do cômodo")
    r.check(f"{len(groups)} zonas" in " ".join((await pg.text_content(".rhead .stats")).split()), "o alto do cômodo conta as zonas")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "sala")

    # -- o campo Zona: sugestões do cômodo, lembra a última
    await new_in(r, pg, "sala")
    r.check(await pg.input_value("#f-zone") == "" and await pg.evaluate(DATALIST, "f-zones") == list(groups),
            "o cadastro ganha Zona, vazia, com as zonas da sala como sugestão")
    await pg.fill("#f-name", "Controle universal")
    await pg.fill("#f-zone", "Rack")
    await pg.fill("#f-value", "80")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    ctrl = r.item_named("Controle universal")
    r.eq(ctrl and ctrl["zone"], "Rack", "a zona é gravada")
    await new_in(r, pg, "sala")
    r.eq(await pg.input_value("#f-zone"), "Rack", "o próximo item da sala já vem com a última zona usada nela")
    await r.shot(pg, "zona-lembrada")
    await pg.select_option("#f-room", "cozinha")
    await pg.wait_for_timeout(150)
    r.eq(await pg.evaluate(DATALIST, "f-zones"), ["Bancada", "Geladeira", "Armário", "Mesa"], "trocar para a Cozinha troca as sugestões")
    zone_after = await pg.input_value("#f-zone")
    r.eq(zone_after, "", "e a zona lembrada da sala não vai junto para a Cozinha")
    await pg.click('[data-ed="cancel"]')
    await pg.click('[data-r="1"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)
    await new_in(r, pg, "cozinha")
    r.eq(await pg.input_value("#f-zone"), "", "na Cozinha (sem zona usada ainda), a zona começa vazia")
    await pg.click('[data-ed="cancel"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=4000)

    # -- sem zona: grupo Sem zona; a ficha mostra a zona
    solto = r.api("POST", "api/items", {"name": "Banqueta", "room": "sala", "value": 120})["item"]
    await r.open(pg, "#/c/sala", ".rhead")
    last = (await pg.evaluate(ZONES))[-1]
    r.check(last[0] == "Sem zona" and last[3] == 1, f"item sem zona vai para Sem zona ({last})")
    await r.open(pg, f"#/i/{solto['id']}", "dialog.sheet h1")
    r.eq((await props(pg)).get("Zona"), "Sem zona", "ficha de item sem zona: Sem zona")
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    r.eq((await props(pg)).get("Zona"), "Rack", "ficha: a zona do item")

    # -- Mover com zona
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-zone")
    r.check(await pg.input_value("#mv-zone") == "Rack" and await pg.evaluate(DATALIST, "mv-zones") == list(groups),
            "Mover: a zona atual, com as zonas do cômodo como sugestão")
    await pg.fill("#mv-zone", "Parede")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="Zona atualizada").wait_for(timeout=4000)
    r.eq(next(i for i in r.data()["items"] if i["id"] == "sal-007")["zone"], "Parede", "no mesmo cômodo, Mover só troca a zona")
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-zone")
    await pg.select_option("#mv-room", "quarto")
    r.check(await pg.input_value("#mv-zone") == "" and "Cabeceira" in await pg.evaluate(DATALIST, "mv-zones"), "outro cômodo: a zona se apaga e as sugestões são as do Quarto")
    await pg.fill("#mv-zone", "Cabeceira")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="Movido para Quarto").wait_for(timeout=4000)
    tv = next(i for i in r.data()["items"] if i["id"] == "sal-007")
    r.check(tv["room"] == "quarto" and tv["zone"] == "Cabeceira", f"movido para o Quarto, na Cabeceira ({tv['room']}, {tv['zone']})")
    await ctx.close()

    # -- relatório com a coluna Zona
    ctx, pg = await r.page(b, "pc", "light", accent="turquesa")
    await r.open(pg, "#/relatorio", ".report")
    heads = await pg.evaluate("[...document.querySelectorAll('.rep-room')].map(s => [...s.querySelectorAll('thead th')].map(t => t.textContent))")
    r.check(heads and all("Zona" in h for h in heads), "relatório: coluna Zona em todos os cômodos")
    row = await pg.evaluate("""(() => { const tr = [...document.querySelectorAll('.rep-room tbody tr')].find(t => t.textContent.includes('Controle universal'));
      const i = [...tr.closest('table').querySelectorAll('thead th')].findIndex(t => t.textContent === 'Zona'); return tr.children[i].textContent; })()""")
    r.eq(row, "Rack", "a zona de cada item na coluna")
    span = await pg.evaluate("[...document.querySelectorAll('.rep-room tfoot td[colspan]')].map(t => t.colSpan)")
    r.check(span and set(span) == {4}, f"o Subtotal ocupa as colunas certas ({set(span)})")
    await r.shot(pg, "relatorio", full_page=False)

    # -- desligar não apaga
    zoned = {i["id"]: i["zone"] for i in r.data()["items"] if i.get("zone")}
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    await switch(pg, False)
    r.eq({i["id"]: i["zone"] for i in r.data()["items"] if i.get("zone")}, zoned, "desligar as zonas não apaga nenhuma")
    await r.open(pg, "#/c/sala", ".rhead")
    r.check(await pg.locator("#view .zone-h").count() == 0 and "zona" not in await pg.text_content(".rhead .stats"), "desligadas: lista única, sem contar zonas")
    await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
    r.check("Zona" not in await props(pg), "desligadas: a ficha não mostra a zona")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    r.eq(await pg.locator("#f-zone").count(), 0, "desligadas: o cadastro não tem o campo Zona")
    await pg.fill("#f-name", "Sofá de 3 lugares azul")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    r.eq(next(i for i in r.data()["items"] if i["id"] == "sal-001")["zone"], "Sofá", "editar com as zonas desligadas guarda a zona escondida")
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.wait_for_selector("#mv-room")
    r.eq(await pg.locator("#mv-zone").count(), 0, "desligadas: Mover sem o campo Zona")
    await pg.select_option("#mv-room", "varanda")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="Movido para Varanda").wait_for(timeout=4000)
    r.eq(next(i for i in r.data()["items"] if i["id"] == "sal-001")["zone"], "", "desligadas: mudar de cômodo deixa a zona antiga para trás")
    await r.open(pg, "#/c/sala", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-name", "Porta-retrato")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    r.eq(r.item_named("Porta-retrato")["zone"], "", "desligadas: item novo nasce sem zona, mesmo com a última zona lembrada")
    # ligar de novo: tudo volta
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    await switch(pg, True)
    await r.open(pg, "#/c/sala", ".rhead")
    names = [z[0] for z in await pg.evaluate(ZONES)]
    r.check({"Parede", "Rack", "Estante"} <= set(names) and "Sofá" in names, f"ligar de novo: as zonas voltam ({names})")
    await ctx.close()
    await b.close()


main("zonas", body)
