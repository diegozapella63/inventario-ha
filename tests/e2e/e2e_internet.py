"""Buscar na internet: fotos do produto e os dados (nome, detalhes, categoria, valor) na ficha e no editor; Desfazer; IA desligada."""
import json

from e2e_lib import OVERFLOW, helpers, main

ROWS = "[...document.querySelectorAll('.wprod dl > div')].map(d => [d.querySelector('dt').textContent, d.querySelector('dd').textContent])"
FIELDS = "(ids) => ids.map(i => document.getElementById(i).value)"


async def body(r, p):
    r.start(search=True)
    room = "cozinha"
    iid = r.api("POST", "api/items", {"name": "Cafeteira", "details": "", "room": room, "cat": "outros", "qty": "1", "value": 0, "photos": []})["item"]["id"]
    item = lambda: next(i for i in r.data()["items"] if i["id"] == iid)  # noqa: E731
    b = await r.browser(p)

    for scheme in ("dark", "light"):
        ctx, pg = await r.page(b, "cel", scheme, accent="verde")
        sent = []
        pg.on("request", lambda q: sent.append(q.post_data) if q.url.endswith("api/web-photos") and q.method == "POST" else None)

        if scheme == "dark":
            # ficha: item sem detalhes, categoria Outros e valor zero
            await r.open(pg, f"#/i/{iid}", 'dialog.sheet [data-act="web-photo"]')
            await pg.click('dialog.sheet [data-act="web-photo"]')
            await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
            await pg.wait_for_timeout(300)
            n = await pg.locator(".wgrid .wimg").count()
            r.check(n >= 3, f"fotos de várias lojas, sem repetidas nem miniaturas ({n})")
            sites = await pg.evaluate("[...document.querySelectorAll('.wgrid .wimg .site')].map(e => e.textContent.trim())")
            r.check(all(sites), f"cada foto diz de que site veio ({sites[:3]})")
            rows = await pg.evaluate(ROWS)
            r.eq([x[0] for x in rows], ["Detalhes", "Categoria", "Valor"], "ficha: sem o nome, só o que está vazio")
            r.check(rows[1][1] == "Cozinha e bar" and rows[2][1].replace("\xa0", " ") == "R$ 450", f"categoria e valor legíveis ({rows[1:]})")
            r.eq((await pg.text_content(".wprod .check")).strip(), "Preencher também detalhes, categoria e valor", "texto da opção")
            r.check(await pg.is_checked("[data-fill]"), "vem marcado")
            r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
            await r.shot(pg, f"ficha-dados-{scheme}")
            await pg.locator(".wimg").nth(1).click()
            await pg.click("dialog [data-ok]")
            await pg.wait_for_selector("dialog.sheet .gal-main img", timeout=15000)
            await pg.wait_for_timeout(500)
            it = item()
            r.check(len(it["photos"]) == 1 and it["details"].startswith("Cafeteira espresso") and it["cat"] == "cozinha" and it["value"] == 450,
                    f"ficha: foto e dados salvos ({it['cat']}, {it['value']}, {it['details'][:30]})")
            r.eq(it["name"], "Cafeteira", "ficha: o nome não muda")
            r.check((it["photoSources"] or {}).get(it["photos"][0], "").startswith(r.site.base) if it.get("photoSources") else True, "a foto guarda de onde veio")
            t = pg.locator(".toast", has_text="com os dados do produto")
            await t.wait_for(timeout=4000)
            await r.shot(pg, f"ficha-depois-{scheme}")
            await t.locator("button").click()
            await pg.wait_for_timeout(700)
            it = item()
            r.check(it["photos"] == [] and it["details"] == "" and it["cat"] == "outros" and it["value"] == 0, f"Desfazer volta tudo ({it['cat']}, {it['value']})")

            # desmarcado: só a foto
            await pg.wait_for_selector('dialog.sheet [data-act="web-photo"]')
            await pg.click('dialog.sheet [data-act="web-photo"]')
            await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
            await pg.uncheck("[data-fill]")
            await pg.locator(".wimg").nth(0).click()
            await pg.click("dialog [data-ok]")
            await pg.wait_for_selector("dialog.sheet .gal-main img", timeout=15000)
            await pg.wait_for_timeout(500)
            it = item()
            r.check(len(it["photos"]) == 1 and it["details"] == "" and it["value"] == 0, "desmarcado: só a foto")
            await pg.locator(".toast button").last.click()
            await pg.wait_for_timeout(700)

            # só os dados, sem foto
            await pg.wait_for_selector('dialog.sheet [data-act="web-photo"]')
            await pg.click('dialog.sheet [data-act="web-photo"]')
            await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
            await pg.click("[data-only]")
            await pg.wait_for_timeout(700)
            it = item()
            r.check(it["photos"] == [] and it["cat"] == "cozinha" and it["value"] == 450, "Usar só os dados: sem foto, com os dados")
            t = pg.locator(".toast", has_text="Dados do produto preenchidos")
            await t.wait_for(timeout=4000)
            await t.locator("button").click()
            await pg.wait_for_timeout(700)

            # item já completo: nada para preencher, sem o quadro; a quantidade vai na busca
            full = next(i for i in r.data()["items"] if i.get("details") and i["value"] > 0 and i["cat"] != "outros" and not i.get("photos"))
            await r.open(pg, f"#/i/{full['id']}", 'dialog.sheet [data-act="web-photo"]')
            await pg.click('dialog.sheet [data-act="web-photo"]')
            await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
            r.eq(await pg.locator(".wprod").count(), 0, f"item completo ({full['name']}): sem o quadro de dados")
            await pg.click("dialog [data-x]")
            await pg.wait_for_timeout(300)
            r.eq(json.loads(sent[-1]).get("qty"), full["qty"], "a quantidade vai para a busca")

            # sem fotos, os dados ainda servem
            r.set_search({"paginas": [{"url": r.site.base + "semfoto.html"}], "imagens": [], "produto": helpers.search_answer(r.site)["produto"]})
            await r.open(pg, f"#/i/{iid}", 'dialog.sheet [data-act="web-photo"]')
            await pg.click('dialog.sheet [data-act="web-photo"]')
            await pg.wait_for_selector("dialog .formerr", timeout=20000)
            await pg.wait_for_timeout(200)
            r.check(await pg.locator(".wprod [data-fill]").count() == 0 and (await pg.text_content(".wprod [data-only]")).strip() == "Usar estes dados",
                    "sem fotos: Usar estes dados")
            await r.shot(pg, f"sem-fotos-{scheme}")
            await pg.click(".wprod [data-only]")
            await pg.wait_for_timeout(700)
            r.eq(item()["value"], 450, "sem fotos: dados salvos")
            await pg.locator(".toast button").last.click()
            await pg.wait_for_timeout(600)

            # a IA não achou a busca na web: aviso, sem quadro
            r.set_search({"paginas": [], "imagens": [], "erro": "sem_busca"})
            await r.open(pg, f"#/i/{iid}", 'dialog.sheet [data-act="web-photo"]')
            await pg.click('dialog.sheet [data-act="web-photo"]')
            await pg.wait_for_selector("dialog .formerr", timeout=20000)
            r.eq(await pg.locator(".wprod").count(), 0, "sem busca na web: sem o quadro")
            r.check(len((await pg.text_content("dialog .formerr")).strip()) > 10, "e diz o que fazer")
            await r.shot(pg, f"sem-busca-{scheme}")
            r.set_search(helpers.search_answer(r.site))

        # editor de item novo: preenche o nome também
        await r.open(pg, "#/", ".tabbar .plus")
        await pg.click(".tabbar .plus")
        await pg.click('[data-go="item"]')
        await pg.wait_for_selector("#f-name")
        await pg.fill("#f-name", "cafeteira expresso")
        await pg.fill("#f-qty", "2")
        await pg.click('[data-ed="web"]')
        await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
        await pg.wait_for_timeout(300)
        rows = await pg.evaluate(ROWS)
        r.eq([x[0] for x in rows], ["Nome", "Detalhes", "Categoria", "Valor"], f"[{scheme}] editor novo: os quatro")
        r.eq(json.loads(sent[-1]).get("qty"), "2", f"[{scheme}] editor: a quantidade vai para a busca")
        await r.shot(pg, f"editor-dados-{scheme}")
        await pg.locator(".wimg").nth(0).click()
        await pg.click("dialog [data-ok]")
        await pg.wait_for_selector(".phs .ph .web", timeout=15000)
        await pg.wait_for_timeout(200)
        vals = await pg.evaluate(FIELDS, ["f-name", "f-details", "f-cat", "f-value", "f-qty"])
        r.check(vals[0] == "Cafeteira Espresso Exemplo CX-20" and vals[1].startswith("Cafeteira espresso") and vals[2:] == ["cozinha", "450", "2"],
                f"[{scheme}] editor preenchido ({vals})")
        unit = (await pg.text_content('[data-slot="unit"]')).replace("\xa0", " ")
        r.check("225" in unit, f"[{scheme}] valor por unidade atualizado ({unit!r})")
        t = pg.locator(".toast", has_text="Foto e dados do produto")
        await t.wait_for(timeout=4000)
        await r.shot(pg, f"editor-depois-{scheme}")
        await t.locator("button").click()
        await pg.wait_for_timeout(200)
        r.eq(await pg.evaluate(FIELDS, ["f-name", "f-details", "f-cat", "f-value"]), ["cafeteira expresso", "", "", ""], f"[{scheme}] Desfazer volta os campos")
        r.eq(await pg.locator(".phs .ph .web").count(), 1, f"[{scheme}] e a foto fica")

        if scheme == "dark":
            # o que a pessoa escreveu fica
            await pg.fill("#f-details", "Preta, comprada em 2023")
            await pg.fill("#f-value", "350")
            await pg.click('[data-ed="web"]')
            await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
            rows = await pg.evaluate(ROWS)
            r.eq([x[0] for x in rows], ["Nome", "Categoria"], "editor: não mexe no que foi escrito")
            await pg.click("[data-only]")
            await pg.wait_for_timeout(200)
            vals = await pg.evaluate(FIELDS, ["f-name", "f-details", "f-cat", "f-value"])
            r.check(vals[1] == "Preta, comprada em 2023" and vals[3] == "350" and vals[2] == "cozinha", f"editor: só nome e categoria ({vals})")
            await pg.click('[data-ed="save"]')
            await pg.wait_for_timeout(700)
            last = sorted(r.data()["items"], key=lambda i: i["createdAt"])[-1]
            r.check(last["name"].startswith("Cafeteira Espresso") and last["value"] == 350 and last["qty"] == "2" and len(last["photos"]) == 1,
                    f"editor salva com a foto da internet ({last['name']}, {last['value']}, {last['qty']})")
            r.api("DELETE", f"api/items/{last['id']}")

            # editar item existente: o nome não muda
            await r.open(pg, f"#/i/{iid}", 'dialog.sheet [data-act="item-edit"]')
            await pg.click('dialog.sheet [data-act="item-edit"].primary')
            await pg.wait_for_selector('[data-ed="web"]')
            await pg.click('[data-ed="web"]')
            await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
            r.eq([x[0] for x in await pg.evaluate(ROWS)], ["Categoria"] if item()["value"] else ["Detalhes", "Categoria", "Valor"], "editar existente: sem o nome")
            # cancelar no meio da busca
            await pg.click("dialog [data-x]")
        await ctx.close()

    # computador
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, f"#/i/{iid}", 'dialog.sheet [data-act="web-photo"]')
    await pg.click('dialog.sheet [data-act="web-photo"]')
    await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
    await pg.wait_for_timeout(400)
    await r.shot(pg, "computador")
    await ctx.close()

    # IA desligada: a tela some com o que usa IA e não chama nada
    r.api("PUT", "api/settings", {"ai": False})
    n0 = r.api("GET", "api/ai/usage")["today"]["calls"]
    ctx, pg = await r.page(b, "cel", "dark")
    reqs = []
    pg.on("request", lambda q: reqs.append(q.url) if any(k in q.url for k in ("api/ai/identify", "api/ai/text", "api/web-photos")) else None)
    nophoto = next(i for i in r.data()["items"] if not i.get("photos"))
    await r.open(pg, f"#/i/{nophoto['id']}", "dialog.sheet h1")
    r.eq(await pg.locator('[data-act="web-photo"]').count(), 0, "IA desligada: ficha sem Buscar na internet")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    r.check(await pg.locator('[data-ed="web"]').count() == 0 and await pg.locator(".aibox").count() == 0, "IA desligada: editor sem Buscar na internet nem Preencher com IA")
    await r.shot(pg, "ia-desligada-editor")
    await pg.click('[data-ed="cancel"]')
    r.eq(reqs, [], "IA desligada: a tela não chamou a IA")
    r.eq(r.api("GET", "api/ai/usage")["today"]["calls"], n0, "nenhuma chamada de IA contada")
    r.api("PUT", "api/settings", {"ai": True})
    await r.open(pg, f"#/i/{nophoto['id']}", "dialog.sheet h1")
    r.eq(await pg.locator('[data-act="web-photo"]').count(), 1, "ligada de novo: Buscar na internet volta")
    await ctx.close()
    await b.close()


main("internet", body)
