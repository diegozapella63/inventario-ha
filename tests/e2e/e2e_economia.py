"""1.85.0: Compras no EconomIA, na ficha de um consumível (como as Tarefas no ResolvIA). Um EconomIA de mentira (o
contrato do 1.47.0) diz se o consumível está na lista de compras, a última compra e a Reposição; Pôr na lista e Repor a
cada duração mandam só o nome (e a duração). Um item da casa não tem a seção. Dados inventados."""
import json
import os
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "integration"))
from test_economia import CHAVE, EconomiaFalso  # noqa: E402  o mesmo EconomIA de mentira dos testes do servidor

from e2e_lib import OVERFLOW, main  # noqa: E402

LINHAS = "[...document.querySelectorAll('dialog.sheet .icompras .clist li')].map(li => [li.querySelector('b').textContent, li.querySelector('span').textContent])"
BOTOES = "[...document.querySelectorAll('dialog.sheet .icompras .cbtns .btn')].map(b => b.textContent.trim())"


async def body(r, p):
    eco = ThreadingHTTPServer(("127.0.0.1", 0), EconomiaFalso)
    threading.Thread(target=eco.serve_forever, daemon=True).start()
    arq = os.path.join(tempfile.mkdtemp(prefix="inv-eco-"), "integracao.json")
    with open(arq, "w", encoding="utf-8") as f:
        json.dump({"app": "economia", "nome": "EconomIA", "versao": "1.47.0", "url": f"http://127.0.0.1:{eco.server_address[1]}", "ip_url": None,
                   "chave": CHAVE, "compras": "/api/integracao/compras"}, f)
    r.start(env={"INV_ECONOMIA": arq})
    r.api("PUT", "api/settings", {"consumiveis": True})
    r.api("POST", "api/rooms", {"kind": "consumiveis"})
    creme = r.api("POST", "api/items", {"room": "consumiveis", "name": "Creme de mãos", "dur": 180})["item"]
    casa = next(i for i in r.data()["items"] if i["room"] != "consumiveis")
    b = await r.browser(p)
    for size, scheme in (("cel", "dark"), ("estreito", "light")):
        EconomiaFalso.estado = {"na_lista": False, "vezes": 2, "ultima": "2026-10-28", "compras": ["2026-10-28", "2026-09-01"], "reposicao": None}
        tag = f"[{size} {scheme}]"
        ctx, pg = await r.page(b, size, scheme)
        await r.open(pg, f"#/i/{creme['id']}", "dialog.sheet .icompras .clist")
        r.eq((await pg.text_content("dialog.sheet .icompras h3")).strip(), "Compras no EconomIA", f"{tag} o título da seção")
        r.eq(await pg.evaluate(LINHAS), [["Lista de compras", "Fora da lista"], ["Última compra", "28/10/2026 · 2 compras"], ["Reposição", "Não"]], f"{tag} o que o EconomIA sabe")
        r.eq(await pg.evaluate(BOTOES), ["Pôr na lista", "Repor a cada 6 meses"], f"{tag} os dois botões")
        hs = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .icompras .cbtns .btn')].map(b => [Math.round(b.getBoundingClientRect().width), Math.round(b.getBoundingClientRect().top)])")
        r.check(abs(hs[0][0] - hs[1][0]) <= 1 and hs[0][1] == hs[1][1], f"{tag} lado a lado, do mesmo tamanho ({hs})")
        r.check(await pg.evaluate(OVERFLOW), f"{tag} sem rolagem para o lado")
        await pg.locator("dialog.sheet .icompras").scroll_into_view_if_needed()
        await r.shot(pg, f"ficha-{size}-{scheme}")
        await pg.locator("dialog.sheet .icompras .btn", has_text="Pôr na lista").click()
        await pg.locator(".toast", has_text="Pus Creme de mãos na lista.").wait_for(timeout=6000)
        r.eq((await pg.evaluate(LINHAS))[0], ["Lista de compras", "Está na lista"], f"{tag} depois do Pôr na lista")
        r.eq(await pg.evaluate(BOTOES), ["Repor a cada 6 meses"], f"{tag} o Pôr na lista sai")
        await pg.locator("dialog.sheet .icompras .btn", has_text="Repor a cada 6 meses").click()
        await pg.locator(".toast", has_text="Pus Creme de mãos na Reposição.").wait_for(timeout=6000)
        r.eq((await pg.evaluate(LINHAS))[2], ["Reposição", "a cada 6 meses · volta em 02/05/2027"], f"{tag} depois do Repor")
        r.eq(await pg.evaluate(BOTOES), [], f"{tag} sem mais o que fazer, sem botões")
        r.eq(EconomiaFalso.pedidos[-1]["corpo"], {"nome": "Creme de mãos", "acao": "repor", "dias": 180}, f"{tag} só o nome e a duração vão")
        await r.open(pg, f"#/i/{casa['id']}", "dialog.sheet h1")
        r.eq(await pg.locator("dialog.sheet .icompras").count(), 0, f"{tag} um item da casa não tem Compras no EconomIA")
        await ctx.close()
    await b.close()
    eco.shutdown()


main("economia", body)
