"""1.90.0: o link de uma ronda do CorrerIA. O painel do Home Assistant passa o resto do endereço (/app/<app>/comodo/<nome>
ou /consumiveis) e a tela abre o cômodo (pelo nome, sem acento nem maiúsculas, ou pelo id) ou os consumíveis. Um cômodo
que não existe, ou os consumíveis desligados: fica onde estava."""
from urllib.parse import quote

from e2e_lib import main


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark")
    await ctx.add_init_script("window.INV_TESTE = true")
    await r.open(pg, "#/", "body")
    await pg.reload()
    await pg.wait_for_function("typeof window.__haOpen === 'function'")
    sala = r.data()["rooms"][0]

    await pg.evaluate("(p) => window.__haOpen(p)", "/comodo/" + quote(sala["name"].upper()))
    await pg.wait_for_function("(h) => location.hash === h", arg="#/c/" + quote(sala["id"]))
    r.check(True, "pelo nome (em maiúsculas): abre o cômodo")

    await pg.evaluate("location.hash = '#/'")
    await pg.evaluate("(p) => window.__haOpen(p)", "/comodo/" + sala["id"])
    await pg.wait_for_function("(h) => location.hash === h", arg="#/c/" + quote(sala["id"]))
    r.check(True, "pelo id também")

    await pg.evaluate("location.hash = '#/'")
    await pg.evaluate("window.__haOpen('/comodo/Um%20que%20n%C3%A3o%20existe'); window.__haOpen('/consumiveis')")
    await pg.wait_for_timeout(400)
    r.eq(await pg.evaluate("location.hash"), "#/", "cômodo desconhecido e consumíveis desligados: fica onde estava")

    r.app.request("PUT", "api/settings", {"consumiveis": True})
    await pg.reload()
    await pg.wait_for_function("typeof window.__haOpen === 'function'")
    await pg.evaluate("window.__haOpen('/consumiveis')")
    await pg.wait_for_function("location.hash === '#/consumiveis'")
    r.check(True, "com os consumíveis ligados: abre a tela deles")
    await ctx.close()
    await b.close()


main("link_ronda", body)
