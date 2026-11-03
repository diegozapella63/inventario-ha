"""A prévia (tools/build_preview.py): a mesma tela com o servidor imitado em memória, montada com a casa de teste.
Confere que abre, que dá para clicar em tudo e que nada vai para um servidor de verdade."""
import functools
import http.server
import os
import subprocess
import sys
import threading

from e2e_lib import OVERFLOW, TMP, helpers, main


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def build() -> str:
    out = os.path.join(TMP, "previa")
    tool = os.path.join(helpers.ROOT, "tools", "build_preview.py")
    subprocess.run([sys.executable, tool, out], check=True, capture_output=True)
    return out


async def body(r, p):
    out = build()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=out))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r.base = f"http://127.0.0.1:{srv.server_port}/index.html"
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="coral")
    api = []
    pg.on("request", lambda q: api.append(q.url) if "/api/" in q.url else None)
    await pg.goto(r.base + "#/")
    await pg.wait_for_selector(".tag", timeout=15000)
    r.check("Prévia do app" in await pg.text_content(".pv-note"), "aviso de prévia no alto")
    r.eq(await pg.text_content(".tag-sub"), "38 itens em 6 cômodos", "a casa de teste")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "inicio")

    # cadastrar um item (fica só na tela)
    await pg.click(".tabbar .plus")
    await pg.click('[data-go="item"]')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-name", "Item da prévia")
    await pg.fill("#f-value", "250")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    await pg.locator(".toast", has_text="Item adicionado").wait_for(timeout=4000)
    r.eq(await pg.text_content(".tag-sub"), "39 itens em 6 cômodos", "item novo entra na conta")

    # Falar e Catalogar: exemplos simulados
    await pg.click(".mic-top")
    await pg.wait_for_selector(".voice", timeout=5000)
    r.check("Na prévia, o microfone não grava" in await pg.text_content(".voice-note"), "Falar avisa que é exemplo")
    await pg.click('[data-ct="mic"]')
    await pg.wait_for_timeout(1200)
    await pg.click('[data-ct="mic"]')
    await pg.wait_for_selector(".found li", timeout=10000)
    r.check(await pg.locator(".found li").count() >= 2, "Falar: itens de exemplo para conferir")
    await r.shot(pg, "falar")
    await pg.click('.dlg-f [data-ct="cancel"]')
    await pg.click('[data-r="1"]')
    await pg.goto(r.base + "#/c/quarto")
    await pg.wait_for_selector(".rhead")
    await pg.click('.rhead-actions [data-act="catalog"]')
    await pg.wait_for_selector('[data-ct="roomphoto"]')
    await pg.click('[data-ct="roomphoto"]')
    picker = pg.locator("dialog", has=pg.locator(".pick"))
    await picker.locator(".pick label").first.click()
    await picker.locator("[data-ok]").click()
    await pg.click('[data-ct="read"]')
    await pg.wait_for_selector(".found li", timeout=10000)
    r.check(await pg.locator(".inote", has_text="Exemplo simulado da prévia").count() == 1, "Catalogar: exemplo marcado como simulado")
    await pg.check('.fcheck[data-ri="0"]')  # o exemplo do quarto já está cadastrado: vem desmarcado
    await pg.click('[data-ct="add"]')
    await pg.locator(".toast", has_text="adicionado em Quarto").wait_for(timeout=5000)
    r.check(True, "e os itens entram")

    # Buscar na internet: fotos de exemplo
    nophoto = next(i["id"] for i in helpers.fixture_data()["items"] if not i.get("photos"))
    await pg.goto(r.base + f"#/i/{nophoto}")
    await pg.wait_for_selector('dialog.sheet [data-act="web-photo"]', timeout=8000)
    await pg.click('dialog.sheet [data-act="web-photo"]')
    await pg.wait_for_selector(".wgrid .wimg", timeout=15000)
    r.check(await pg.locator(".wgrid .wimg").count() >= 1, "Buscar na internet: fotos de exemplo")
    await pg.click("dialog [data-x]")

    # Novidades: exemplo simulado
    await pg.goto(r.base + "#/i/sal-007")
    await pg.wait_for_selector('dialog.sheet [data-act="item-news"]', timeout=8000)
    await pg.click('dialog.sheet [data-act="item-news"]')
    await pg.wait_for_selector(".news li", timeout=10000)
    r.check(await pg.locator(".news li").count() == 3 and "Exemplo simulado da prévia" in await pg.text_content(".news-foot"), "Novidades: exemplo marcado como simulado")
    await pg.click("dialog.modal .dlg-h [data-x]")

    # Conversar: resposta de exemplo
    await pg.goto(r.base + "#/")
    await pg.wait_for_selector(".chat-top", timeout=8000)
    await pg.click(".chat-top")
    await pg.fill("dialog.chat textarea", "quanto vale a sala?")
    await pg.press("dialog.chat textarea", "Enter")
    await pg.wait_for_selector("dialog.chat .msg.ai:not(.typing)", timeout=10000)
    r.check("Exemplo da prévia" in await pg.text_content("dialog.chat .msg.ai"), "Conversar: resposta de exemplo")
    await pg.click("dialog.chat [data-x]")

    # Mais: as abas abrem; exportar explica que é prévia
    await pg.goto(r.base + "#/mais")
    await pg.wait_for_selector(".more-tabs")
    for k in ("integracoes", "aparencia", "opcoes", "dados"):
        await pg.click(f'.more-tabs [data-tab="{k}"]')
        await pg.wait_for_timeout(300)
    await pg.click('[data-act="export"][data-kind="csv"]')
    r.check(await pg.locator(".toast", has_text="baixa o arquivo").count() == 1, "Exportar na prévia: explica")
    await r.shot(pg, "mais")
    r.eq(api, [], "nada vai para um servidor de verdade")
    await ctx.close()

    ctx, pg = await r.page(b, "pc", "light")
    await pg.goto(r.base + "#/")
    await pg.wait_for_selector(".tag", timeout=15000)
    await r.shot(pg, "computador")
    await ctx.close()
    await b.close()
    srv.shutdown()
    srv.server_close()


main("previa", body)
