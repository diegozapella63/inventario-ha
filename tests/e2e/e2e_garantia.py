"""1.113.0: a Garantia até de um item da casa (ou de um bem): no Editar item, um campo que fecha, escrito DD/MM/AAAA (os
números ganham as barras); a ficha diz até quando e, perto do fim, quantos dias faltam; um consumível não tem."""
from datetime import date, timedelta

from e2e_lib import OVERFLOW, main


async def body(r, p):
    r.start()
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="coral")
    await r.open(pg, "#/i/qua-001", "dialog.sheet h1")
    r.check(await pg.locator('[data-slot="garantia"]').count() == 0, "sem garantia, a ficha não fala dela")
    await pg.click('dialog.sheet [data-act="item-edit"]')
    await pg.wait_for_selector("#f-gar-f")
    lbl = pg.locator("#f-gar-f > .lbl")
    r.check("shut" in (await pg.get_attribute("#f-gar-f", "class")) and await lbl.get_attribute("data-val") == "Nenhuma", "vazia, começa fechada e diz Nenhuma")
    r.check(await lbl.locator("svg").count() == 1, "o título tem o ícone")
    await lbl.click()
    await pg.wait_for_timeout(200)
    r.check(await pg.locator("#f-gar").is_visible(), "o toque no título abre o campo")
    await pg.fill("#f-gar", "")
    await pg.type("#f-gar", "31022027")
    r.eq(await pg.input_value("#f-gar"), "31/02/2027", "os números ganham as barras")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_timeout(300)
    r.check(await pg.is_visible('[data-err="warranty"]'), "uma data que não existe: o editor avisa e não salva")
    em = date.today() + timedelta(days=20)
    await pg.fill("#f-gar", "")
    await pg.type("#f-gar", em.strftime("%d%m%Y"))
    r.check(await pg.evaluate(OVERFLOW), "o editor sem rolagem para o lado")
    await r.shot(pg, "garantia-editor")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    it = next(i for i in r.data()["items"] if i["id"] == "qua-001")
    r.eq(it.get("warranty"), em.isoformat(), "gravada AAAA-MM-DD")
    await pg.wait_for_selector('[data-slot="garantia"]')
    r.eq(await pg.text_content('[data-slot="garantia"]'), f"{em.strftime('%d/%m/%Y')} · faltam 20 dias", "a ficha diz até quando e quantos dias faltam")
    await r.shot(pg, "garantia-ficha")
    # de novo no editor: vem preenchida e aberta; apagada, sai
    await pg.click('dialog.sheet [data-act="item-edit"]')
    await pg.wait_for_selector("#f-gar")
    r.eq(await pg.input_value("#f-gar"), em.strftime("%d/%m/%Y"), "no editor, a data como foi escrita")
    await pg.fill("#f-gar", "")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    it = next(i for i in r.data()["items"] if i["id"] == "qua-001")
    r.check("warranty" not in it, "apagada, a garantia sai do item")
    await ctx.close()
    await b.close()


main("garantia", body)
