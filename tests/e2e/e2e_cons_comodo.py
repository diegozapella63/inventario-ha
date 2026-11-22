"""1.88.0: Consumíveis por cômodo (Mais > Configurações > Opções > Inventário, embaixo do Usar consumíveis; desligado de
início): ligado, o consumível ganha o campo Cômodo onde é usado (Nenhum ou um cômodo da casa), a linha da lista e a ficha
dizem o cômodo, e o /api/integracao/consumiveis leva o comodo. E os botões das fotos do cômodo (Editar cômodo) alinhados
no celular: a Capa, o Subir e o Apagar na mesma linha e com a mesma altura, sem texto para fora do botão."""
from e2e_lib import OVERFLOW, main


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


async def body(r, p):
    r.start(search=False)
    r.app.request("PUT", "api/settings", {"consumiveis": True})
    st, _, area = r.app.request("POST", "api/rooms", {"kind": "consumiveis"})
    area = area["room"]
    st, _, novo = r.app.request("POST", "api/items", {"room": area["id"], "name": "Detergente", "dur": 30})
    iid = (novo.get("item") or novo)["id"]
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark")

    # -- desligado de início: a chave embaixo do Usar consumíveis, num quadro recuado; o editor sem o campo
    await r.open(pg, "#/config/opcoes", "#p-tipos")
    r.eq(txt(await pg.text_content("#p-tipos li.sub .ot b")), "Consumíveis por cômodo", "a sub-opção embaixo do Usar consumíveis")
    r.check(await pg.locator("#p-tipos li.sub .sub-box .ot b .ic").count() == 1, "com o ícone antes do título")
    r.check(not await pg.is_checked('[data-input="consc-on"]'), "desligada de início")
    await r.open(pg, f"#/i/{iid}", "dl")
    r.eq(await pg.locator('[data-slot="usado-em"]').count(), 0, "desligado: a ficha sem o Usado em")

    await r.open(pg, "#/config/opcoes", "#p-tipos")
    await pg.click('label.switch:has([data-input="consc-on"])')
    await pg.locator(".toast", has_text="Consumíveis por cômodo ligados").wait_for(timeout=5000)
    r.check(r.data()["settings"]["cons_comodo"] is True, "ligado fica gravado")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "opcoes", full_page=True)

    # -- o editor do consumível com o campo; escolher grava
    await r.open(pg, f"#/i/{iid}", '[data-slot="usado-em"]')
    r.eq(txt(await pg.text_content('[data-slot="usado-em"]')), "Nenhum cômodo", "ligado e sem cômodo: a ficha diz")
    await pg.click('.btn.primary[data-act="item-edit"]')
    await pg.wait_for_selector("#f-usado", state="attached", timeout=5000)
    r.eq(txt(await pg.text_content('label[for="f-usado"]')), "Cômodo onde é usado", "o campo no editor")
    ops = await pg.evaluate("[...document.querySelector('#f-usado').options].map(o => o.textContent)")
    r.check(ops[0] == "Nenhum" and "Cozinha" in ops and "Consumíveis" not in ops and "Bens" not in ops, f"Nenhum e os cômodos da casa, sem as áreas ({ops})")
    await pg.evaluate("(s => { s.value = 'cozinha'; s.dispatchEvent(new Event('input', { bubbles: true })); s.dispatchEvent(new Event('change', { bubbles: true })); })(document.querySelector('#f-usado'))")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_function("document.querySelector('[data-slot=\"usado-em\"]') && document.querySelector('[data-slot=\"usado-em\"]').textContent.includes('Cozinha')", timeout=5000)
    r.eq(next(i for i in r.data()["items"] if i["id"] == iid).get("usedIn"), "cozinha", "o cômodo fica gravado no consumível")
    await r.shot(pg, "ficha")
    await r.open(pg, "#/consumiveis", ".irow")
    r.check("Cozinha" in txt(await pg.text_content(".irow .meta")), "a linha da lista diz o cômodo")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")

    # -- os outros apps (o EconomIA) recebem o cômodo
    import json, os
    with open(os.path.join(r.app.path("share"), "integracao.json"), encoding="utf-8") as f:
        chave = json.load(f)["chave"]
    st, _, d = r.app.request("GET", "api/integracao/consumiveis", headers={"Authorization": "Bearer " + chave})
    r.eq([c.get("comodo") for c in d["consumiveis"]], ["Cozinha"], "o /api/integracao/consumiveis leva o comodo")

    # -- 1.89.0: Buscar › Selecionar com consumíveis: vários de uma vez, a categoria e o cômodo onde são usados
    st, _, n2 = r.app.request("POST", "api/items", {"room": area["id"], "name": "Sabão em pó", "dur": 30})
    i2 = (n2.get("item") or n2)["id"]
    await r.open(pg, "#/buscar?tipo=consumiveis", ".ssum")
    r.eq(await pg.locator(".ssum > b").count(), 0, "só consumíveis: sem a soma em reais")
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".selbar")
    r.eq(await pg.locator(".irow.selr:not([disabled])").count(), 2, "os consumíveis entram no Selecionar")
    await pg.click('[data-act="sel-all"]')
    r.eq(txt(await pg.text_content(".selbar .btn")), "Alterar 2 consumíveis", "o botão diz consumíveis")
    await pg.click('.selbar [data-act="sel-change"]')
    await pg.wait_for_selector("dialog.modal [data-bk]")
    r.eq(txt(await pg.text_content("dialog.modal h2")), "Alterar 2 consumíveis", "a janela")
    r.eq([txt(t) for t in await pg.locator("dialog.modal .field > .lbl").all_text_contents()], ["Categoria", "Cômodo onde é usado"], "a categoria e o cômodo onde é usado")
    r.check(await pg.locator('dialog.modal input[name="bk-cat"][value="c-limpeza"]').count() == 1 and await pg.locator('dialog.modal input[name="bk-cat"][value="moveis"]').count() == 0,
            "as categorias dos consumíveis, não as da casa")
    r.check(await pg.is_disabled("dialog.modal [data-ok]"), "tudo em Manter: o Aplicar desligado")
    await pg.locator("dialog.modal .chip", has=pg.locator('input[name="bk-cat"][value="c-limpeza"]')).click()
    await pg.locator("dialog.modal .chip", has=pg.locator('input[name="bk-usado"][value="sala"]')).click()
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "alterar-consumiveis")
    await pg.click("dialog.modal [data-ok]")
    t = pg.locator(".toast", has_text="2 consumíveis alterados")
    await t.wait_for(timeout=6000)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq([(d[k]["cat"], d[k].get("usedIn")) for k in (iid, i2)], [("c-limpeza", "sala"), ("c-limpeza", "sala")], "a categoria e o cômodo dos dois")
    r.eq(await pg.locator('.irow.selr[aria-pressed="true"]').count(), 0, "feita a alteração, ficam desmarcados")
    await t.locator("button", has_text="Desfazer").click()
    await pg.wait_for_timeout(600)
    d = {i["id"]: i for i in r.data()["items"]}
    r.eq((d[iid].get("usedIn"), d[i2].get("usedIn")), ("cozinha", None), "o Desfazer volta o cômodo de cada um")
    await pg.click('[data-act="sel-end"]')
    # numa lista misturada, a seleção é de um lado só
    await r.open(pg, "#/buscar", ".ssum")
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".selbar")
    r.eq(await pg.locator(".irow.selr[disabled]").count(), 0, "sem nada marcado, a casa e os consumíveis podem")
    await pg.locator(f'.irow.selr[data-id="{iid}"]').scroll_into_view_if_needed()
    await pg.click(f'.irow.selr[data-id="{iid}"]')
    r.check(await pg.locator(".irow.selr[disabled]").count() > 0 and await pg.locator(f'.irow.selr[data-id="{i2}"]:not([disabled])').count() == 1,
            "marcado um consumível, os itens da casa ficam de fora")
    await pg.click('[data-act="sel-end"]')

    # -- as fotos do cômodo no celular: os três botões na mesma linha, com a mesma altura, e o texto dentro do botão
    sala = next(x for x in r.data()["rooms"] if (x.get("photos") or []) and not x.get("kind"))
    await r.open(pg, f"#/c/{sala['id']}", ".rhead")
    await pg.click('.rhead [data-act="room-edit"], [data-act="room-edit"]')
    await pg.wait_for_selector(".rph", timeout=5000)
    cx = await pg.evaluate("""[...document.querySelectorAll('.rph')].map(li => ['cover', 'up', 'rm'].map(k => { const b = li.querySelector(`[data-re="${k}"]`), q = b.getBoundingClientRect();
      return [Math.round(q.top), Math.round(q.height), b.scrollWidth <= b.clientWidth + 1]; }))""")
    r.check(all(len({(t, h) for t, h, _ in li}) == 1 for li in cx), f"Capa, Subir e Apagar na mesma linha e com a mesma altura ({cx[:2]})")
    r.check(all(ok for li in cx for _, _, ok in li), "o texto da capa cabe no botão")
    quad = await pg.evaluate("[...document.querySelectorAll('.rph [data-re=\"up\"], .rph [data-re=\"rm\"]')].map(b => { const q = b.getBoundingClientRect(); return Math.round(q.width) === Math.round(q.height); })")
    borda = await pg.evaluate("(li => Math.round(li.querySelector('[data-re=\"rm\"]').getBoundingClientRect().right - li.querySelector('.input').getBoundingClientRect().right))(document.querySelector('.rph'))")
    r.check(all(quad) and abs(borda) <= 1, f"o Subir e o Apagar quadrados, até a borda da legenda ({borda})")
    ad = await pg.evaluate("[...document.querySelectorAll('.rph-add .btn')].map(b => { const q = b.getBoundingClientRect(); return [Math.round(q.top), Math.round(q.width)]; })")
    r.check(len(set(map(tuple, ad))) == 1, f"Tirar foto e Escolher fotos dividem a linha ({ad})")
    await r.shot(pg, "fotos-comodo")
    await ctx.close()
    await b.close()


main("cons_comodo", body)
