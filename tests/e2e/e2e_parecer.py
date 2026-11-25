"""1.103.0 (o dono: "criar botão para avaliar com a IA, para que a IA traga um parecer do consumível, qualidade, etc."): na
ficha de um consumível, a seção Parecer da IA com Avaliar com IA; avaliando, "Avaliando…"; depois, a nota em estrelas, o
resumo, o preço, os pontos fortes e fracos, as dicas, as outras opções, as fontes e Avaliado em, com Avaliar de novo. Fechada
e aberta de novo, a ficha mostra o parecer guardado. Um item da casa não tem a seção; com a IA desligada, some. IA simulada,
consumível inventado; 390 px escuro e 320 px claro."""
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
