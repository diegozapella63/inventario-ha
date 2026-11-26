"""1.103.0 (o dono: "criar botão para avaliar com a IA, para que a IA traga um parecer do consumível, qualidade, etc."): na
ficha de um consumível, a seção Parecer da IA com Avaliar com IA; avaliando, "Avaliando…"; depois, a nota em estrelas, o
resumo, o preço, os pontos fortes e fracos, as dicas, as outras opções, as fontes e Avaliado em, com Avaliar de novo. Fechada
e aberta de novo, a ficha mostra o parecer guardado. Um item da casa não tem a seção; com a IA desligada, some. IA simulada,
consumível inventado; 390 px escuro e 320 px claro. 1.107.0: Pesquisas da IA › Pareceres e o Apagar."""
from e2e_lib import OVERFLOW, main


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


async def body(r, p):
    r.start(search=False)
    r.app.request("PUT", "api/settings", {"consumiveis": True})
    st, _, area = r.app.request("POST", "api/rooms", {"kind": "consumiveis"})
    st, _, res = r.app.request("POST", "api/items", {"room": area["room"]["id"], "name": "Pasta térmica Exemplo", "dur": 365})
    cid = res["item"]["id"]
    b = await r.browser(p)
    for tam, tema in (("cel", "dark"), ("estreito", "light")):
        ctx, pg = await r.page(b, tam, tema)
        await r.open(pg, f"#/i/{cid}", ".dlg .ihead")
        sec = pg.locator('[data-slot="item-par"]')
        r.check(await sec.count() == 1, f"{tam}: a seção Parecer da IA na ficha do consumível")
        if tam == "cel":
            r.eq(txt(await sec.locator(".inews-h").inner_text()), "Parecer da IA", "o título")
            btn = sec.locator('[data-act="item-par"]')
            r.eq(txt(await btn.inner_text()), "Avaliar com IA", "o botão")
            await r.shot(pg, "antes")
            await btn.click()
            await pg.wait_for_selector('[data-slot="item-par"] .par', timeout=15000)
            r.check(await sec.locator(".par-nota .on").count() == 4, "a nota em estrelas (4 de 5)")
            t = txt(await sec.inner_text())
            for parte in ("Bem avaliado pelos compradores", "Preço hoje: R$ 20 a R$ 30", "Pontos fortes", "Rende bastante", "Pontos fracos", "Dicas",
                          "Outras opções", "Outra marca de exemplo", "Fontes: exemplo.com.br", "Avaliado em", "Avaliar de novo"):
                r.check(parte in t, f"o parecer mostra «{parte}»")
            await r.shot(pg, "parecer", full_page=True)
        else:
            await pg.wait_for_selector('[data-slot="item-par"] .par', timeout=8000)
            r.check("Avaliado em" in txt(await sec.inner_text()), "aberta de novo: o parecer guardado")
            r.check(await pg.evaluate(OVERFLOW), "320 px: sem rolagem para o lado")
            await r.shot(pg, "parecer-320", full_page=True)
        await ctx.close()
    # 1.107.0 (o dono: "uma central mesmo de coisas que eu vou buscar de novidades, recursos, avaliações"): Mais › Pesquisas da
    # IA › Pareceres: os consumíveis com a nota, Avaliar consumíveis (os sem parecer ou os escolhidos), a janela de um e o Apagar
    for nome in ("Pilhas AA Exemplo", "Creme Exemplo"):
        r.app.request("POST", "api/items", {"room": area["room"]["id"], "name": nome, "dur": 90})
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/mais", ".menu-list")
    r.eq([txt(await pg.text_content(f'.menu-row[href="#/pesquisas"] {q}')) for q in ("b", ".mb span")], ["Pesquisas da IA", "Novidades, recursos e pareceres, pela internet."], "no menu Mais")
    await r.open(pg, "#/pesquisas/pareceres", "#p-par-list")
    await pg.wait_for_selector("#p-par-list .nrow", timeout=8000)
    r.eq(await pg.evaluate("[...document.querySelectorAll('#view .more-tabs [role=tab]')].map(t => t.textContent.trim())"), ["Novidades", "Recursos", "Pareceres"], "as três abas")
    ROWS = "() => [...document.querySelectorAll('#p-par-list .nrow')].map(b => [b.querySelector('b').textContent, b.querySelector('.nm').textContent, (b.querySelector('.pill') || {}).textContent || ''])"
    rows = await pg.evaluate(ROWS)
    r.eq([x[0] for x in rows], ["Pasta térmica Exemplo", "Creme Exemplo", "Pilhas AA Exemplo"], "os avaliados primeiro")
    r.check(rows[0][2] == "4" and rows[0][1].startswith("Outros · Avaliado") and rows[1][1].endswith("Ainda não avaliado"), f"a nota e quando ({rows[:2]})")
    bts = await pg.evaluate("""[...document.querySelectorAll('#p-par .btn')].map(b => { const q = b.getBoundingClientRect(); return [b.textContent.trim(), Math.round(q.width), Math.round(q.top)]; })""")
    r.check([x[0] for x in bts] == ["Os sem parecer", "Escolher quais"] and bts[0][1] == bts[1][1] and bts[0][2] < bts[1][2], f"os dois botões, um por linha ({bts})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "pareceres")
    corpos = []
    pg.on("request", lambda q: corpos.append(q.post_data) if q.url.endswith("/api/parecer/lote") else None)
    await pg.click('[data-act="par-faltam"]')
    await pg.locator(".toast", has_text="2 consumíveis avaliados").wait_for(timeout=20000)
    await pg.wait_for_timeout(500)
    r.eq(corpos, ["{}"], "Os sem parecer: o servidor escolhe os que faltam")
    r.check(all(x[2] == "4" for x in await pg.evaluate(ROWS)), "todos com a nota")
    # Escolher quais: vêm marcados os sem parecer (nenhum agora); Todos marca e o botão diz quantos
    await pg.click('[data-act="par-escolher"]')
    await pg.wait_for_selector("dialog.modal .par-esc .fcheck")
    r.eq(await pg.locator("dialog.modal .fcheck:checked").count(), 0, "nenhum sem parecer: nada marcado")
    r.check(await pg.is_disabled("dialog.modal [data-ok]"), "sem nada marcado, o Avaliar fica inativo")
    await pg.click("dialog.modal [data-todos]")
    r.eq(txt(await pg.text_content("dialog.modal [data-ok]")), "Avaliar 3", "Todos: o botão diz quantos")
    await pg.locator("dialog.modal .par-esc .nrow").nth(1).click()
    r.eq(txt(await pg.text_content("dialog.modal [data-ok]")), "Avaliar 2", "desmarcar um")
    r.check(await pg.evaluate(OVERFLOW), "a janela sem rolagem para o lado")
    await r.shot(pg, "escolher")
    corpos.clear()
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast", has_text="2 consumíveis avaliados").wait_for(timeout=20000)
    r.check(len(corpos) == 1 and len(__import__("json").loads(corpos[0])["itens"]) == 2, f"manda os escolhidos ({corpos})")
    # a janela de um: o parecer guardado, Avaliar de novo, Apagar e Ver item; Apagar pede confirmação
    await pg.locator("#p-par-list .nrow").first.click()
    await pg.wait_for_selector("dialog.modal .par", timeout=6000)
    r.eq([t.strip() for t in await pg.locator("dialog.modal .dlg-f .btn:visible").all_inner_texts()], ["Avaliar de novo", "Apagar", "Ver item"], "Avaliar de novo, Apagar e Ver item")
    await pg.click("dialog.modal [data-apagar]")
    await pg.locator('dialog[open] [data-r="1"]').last.click()
    await pg.locator(".toast", has_text="Parecer apagado").wait_for(timeout=6000)
    r.check("Parecer apagado" in await pg.text_content("dialog.modal [data-slot=par]"), "a janela diz que apagou")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    rows = await pg.evaluate(ROWS)
    r.check(rows[-1][1].endswith("Ainda não avaliado") and rows[-1][2] == "", f"e a lista também, no fim ({rows[-1]})")
    # na ficha: Avaliar de novo e Apagar lado a lado
    await r.open(pg, f"#/i/{cid}", ".dlg .ihead")
    if await pg.locator('[data-act="item-par-del"]').count() == 0:
        await pg.click('[data-act="item-par"]')
    await pg.wait_for_selector('[data-act="item-par-del"]', timeout=15000)
    b2 = await pg.evaluate("""[...document.querySelectorAll('[data-slot="item-par"] .inews-acts .btn')].map(b => { const q = b.getBoundingClientRect(); return [b.textContent.trim(), Math.round(q.width), Math.round(q.top)]; })""")
    r.check([x[0] for x in b2] == ["Avaliar de novo", "Apagar"] and b2[0][1:] == b2[1][1:], f"na ficha, Avaliar de novo e Apagar lado a lado ({b2})")
    await pg.click('[data-act="item-par-del"]')
    await pg.locator('dialog[open] [data-r="1"]').last.click()
    await pg.locator(".toast", has_text="Parecer apagado").wait_for(timeout=6000)
    r.eq(txt(await pg.locator('[data-act="item-par"]').inner_text()), "Avaliar com IA", "apagado: volta o Avaliar com IA")
    await ctx.close()
    # um item da casa não tem a seção; com a IA desligada, some
    st, _, d = r.app.request("GET", "api/data")
    casa = next(i for i in d["items"] if i["room"] != area["room"]["id"])
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, f"#/i/{casa['id']}", ".dlg .ihead")
    r.check(await pg.locator('[data-slot="item-par"]').count() == 0, "um item da casa não tem o Parecer da IA")
    r.app.request("PUT", "api/settings", {"ai": False})
    await r.open(pg, f"#/i/{cid}", ".dlg .ihead")
    r.check(await pg.locator('[data-slot="item-par"]').count() == 0, "a IA desligada: some")
    await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_parecer", body)
