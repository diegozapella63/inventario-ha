"""1.115.0: Vendas. Na ficha de um item da casa, o bloco Venda: Pôr à venda (o preço pedido e a observação), Mudar, Tirar
da venda e Vendido (o valor, o dia e a pergunta do recebimento no GerencIA, de mentira aqui). Mais › Vendas mostra o que
está à venda, agrupado, e os Vendidos recolhidos no fim, com o Desfazer. Um consumível não tem o bloco. Dados inventados."""
import json
import os
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "unit"))
from e2e_lib import OVERFLOW, main  # noqa: E402

BOTOES = "[...document.querySelectorAll('dialog.sheet .ivenda .venda-b .btn')].map(b => b.textContent.trim())"


async def body(r, p):
    from http.server import BaseHTTPRequestHandler

    class Gerencia(BaseHTTPRequestHandler):
        pedidos = []

        def log_message(self, *a):
            pass

        def do_POST(self):
            corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            Gerencia.pedidos.append(corpo)
            dado = json.dumps({"ok": True, "id": "l-1", "rev": 2}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(dado)))
            self.end_headers()
            self.wfile.write(dado)

    ger = ThreadingHTTPServer(("127.0.0.1", 0), Gerencia)
    threading.Thread(target=ger.serve_forever, daemon=True).start()
    arq = os.path.join(tempfile.mkdtemp(prefix="inv-ger-"), "integracao.json")
    with open(arq, "w", encoding="utf-8") as f:
        json.dump({"app": "gerencia", "url": f"http://127.0.0.1:{ger.server_address[1]}", "chave": "segredo-de-teste", "recebimentos": "/api/integracao/nova"}, f)
    r.start(env={"INV_GERENCIA": arq})
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="coral")
    await r.open(pg, "#/mais", ".menu-list")
    r.check("Vendas" in await pg.inner_text(".menu-list"), "o Mais tem a linha Vendas")
    await pg.click('.menu-list a[href="#/vendas"]')
    await pg.wait_for_selector(".mscreen .empty")
    r.check("Nada à venda" in await pg.inner_text(".mscreen"), "sem nada à venda, a tela diz como pôr")
    r.eq((await pg.text_content("#topbar h1")).strip(), "Vendas", "o título da tela")

    # a ficha: Pôr à venda e Vendido, lado a lado
    await r.open(pg, "#/i/sal-001", "dialog.sheet .ivenda")
    r.eq(await pg.evaluate(BOTOES), ["Pôr à venda", "Vendido"], "fora da venda, os dois botões")
    hs = await pg.evaluate("[...document.querySelectorAll('dialog.sheet .ivenda .venda-b .btn')].map(b => [Math.round(b.getBoundingClientRect().width), Math.round(b.getBoundingClientRect().height), b.querySelectorAll('svg').length])")
    r.check(abs(hs[0][0] - hs[1][0]) <= 1 and hs[0][1] == hs[1][1] == 50 and all(h[2] == 1 for h in hs), f"do mesmo tamanho, com 50 px e ícone ({hs})")
    await pg.click('dialog.sheet [data-act="venda-por"]')
    await pg.wait_for_selector("#vp-preco")
    await pg.fill("#vp-preco", "caro")
    await pg.click("dialog.modal [data-ok]")
    await pg.wait_for_selector("dialog.modal [data-err]:not([hidden])")
    await pg.fill("#vp-preco", "1.500,00")
    await pg.fill("#vp-nota", "Com as capas")
    r.check(await pg.evaluate(OVERFLOW), "a janela sem rolagem para o lado")
    await pg.click("dialog.modal [data-ok]")
    await pg.wait_for_selector('[data-slot="venda-l"]')
    r.eq(" ".join((await pg.text_content('[data-slot="venda-l"]')).split()), "À venda · pedindo R$ 1.500 · Com as capas", "a ficha diz o preço pedido e a observação")
    r.eq(await pg.evaluate(BOTOES), ["Vendido", "Mudar", "Tirar da venda"], "à venda, os três botões")
    it = next(i for i in r.data()["items"] if i["id"] == "sal-001")
    r.eq((it["sale"]["price"], it["sale"]["note"]), (1500, "Com as capas"), "gravado no item")
    await pg.locator("dialog.sheet .ivenda").scroll_into_view_if_needed()
    await r.shot(pg, "vendas-ficha")
    r.api("PUT", "api/items/sal-003", {"sale": True})

    # Mais › Vendas: agrupado por cômodo, com a soma pedida
    await r.open(pg, "#/vendas", ".mscreen.vendas .ssum")
    r.eq(" ".join((await pg.text_content(".vendas .ssum-n")).split()), "2 itens à venda · R$ 1.500 pedidos", "a contagem e a soma pedida")
    r.eq(await pg.evaluate("[...document.querySelectorAll('.vendas .zone h3')].map(h => h.textContent.trim())"), ["Sala de estar"], "de início, agrupado por cômodo")
    r.check("pedido" in await pg.inner_text(".vendas .ilist"), "a linha diz o preço pedido")
    await pg.click('.vendas [data-act="vendas-agrupar"][data-v=""]')
    await pg.wait_for_function("document.querySelectorAll('.vendas .zone').length === 0")
    r.eq(await pg.locator(".vendas .ilist .irow").count(), 2, "sem agrupar, a lista inteira")
    r.check(await pg.evaluate(OVERFLOW), "Vendas sem rolagem para o lado")
    await r.shot(pg, "vendas-tela")
    await r.open(pg, "#/buscar", ".sbar")
    await pg.fill('[data-input="search-q"]', "Sofá")
    await pg.wait_for_selector(".irow .venda-tag")
    r.eq((await pg.text_content(".irow .venda-tag")).strip(), "À venda", "na busca, a linha diz À venda")

    # Vendido: o valor, o dia e a pergunta do recebimento
    await r.open(pg, "#/i/sal-001", "dialog.sheet .ivenda")
    await pg.click('dialog.sheet [data-act="venda-vendido"]')
    await pg.wait_for_selector("#vd-valor")
    r.eq(await pg.input_value("#vd-valor"), "1.500", "o valor começa no preço pedido")
    r.check("Lançar o recebimento no GerencIA?" in await pg.inner_text("dialog.modal"), "com o GerencIA, a janela pergunta do recebimento")
    await pg.fill("#vd-valor", "1.400,00")
    await pg.click("dialog.modal [data-ok]")
    await pg.wait_for_selector("dialog.modal [data-err]:not([hidden])")
    r.check("Escolha se o recebimento" in await pg.text_content("dialog.modal [data-err]"), "sem escolher, a janela pede a resposta")
    await pg.click('dialog.modal label.chip:has(input[name="vd-rec"][value="sim"])')
    r.check(await pg.evaluate(OVERFLOW), "a janela do Vendido sem rolagem para o lado")
    await r.shot(pg, "vendas-vendido")
    await pg.click("dialog.modal [data-ok]")
    await pg.wait_for_selector("dialog.sheet", state="detached", timeout=8000)
    d = r.data()
    r.check(all(i["id"] != "sal-001" for i in d["items"]), "o item saiu do inventário")
    r.eq([(v["id"], v["soldValue"], v.get("soldReceived")) for v in d["sold"]], [("sal-001", 1400, "gerencia")], "está nos vendidos, com o recebimento no GerencIA")
    r.eq((Gerencia.pedidos[-1]["tipo"], Gerencia.pedidos[-1]["valor"], Gerencia.pedidos[-1]["pago"]), ("receita", 1400, True), "o GerencIA recebeu o recebimento")

    # os Vendidos, recolhidos no fim, com o Desfazer
    await r.open(pg, "#/vendas", ".mscreen.vendas .vendidos")
    r.check(not await pg.evaluate("document.querySelector('.vendas .vendidos').open"), "os Vendidos começam recolhidos")
    r.eq(" ".join((await pg.text_content(".vendas .vendidos summary")).split()), "Vendidos (1)", "com a contagem")
    await pg.click(".vendas .vendidos summary")
    r.check("no GerencIA" in await pg.inner_text(".vendas .vend"), "a linha diz que o recebimento foi para o GerencIA")
    r.eq(await pg.locator('.vendas [data-act="vendido-receber"]').count(), 0, "já lançado: sem o botão de lançar")
    r.check(await pg.evaluate(OVERFLOW), "os Vendidos sem rolagem para o lado")
    await r.shot(pg, "vendas-vendidos")
    await pg.click('.vendas [data-act="vendido-desfazer"]')
    await pg.wait_for_function("!document.querySelector('.vendas .vendidos')")
    d = r.data()
    r.check(any(i["id"] == "sal-001" for i in d["items"]) and not d.get("sold"), "o Desfazer traz o item de volta")

    # vendido sem lançar: o botão de lançar fica nos Vendidos
    r.api("POST", "api/items/sal-003/sell", {"value": 200})
    await r.open(pg, "#/vendas", ".mscreen.vendas .vendidos")
    await pg.click(".vendas .vendidos summary")
    await pg.click('.vendas [data-act="vendido-receber"]')
    await pg.wait_for_function("!document.querySelector('.vendas [data-act=vendido-receber]')")
    r.eq(r.data()["sold"][0].get("soldReceived"), "gerencia", "lançado depois, pelos Vendidos")
    await pg.click('.vendas [data-act="vendido-apagar"]')
    await pg.click('dialog.modal [data-r="1"]')
    await pg.wait_for_function("!document.querySelector('.vendas .vendidos')")
    r.check(not r.data().get("sold"), "apagado dos vendidos")

    # Buscar › Selecionar › Alterar: À venda (Manter, Sim, Não), com o Desfazer
    r.check(any(i.get("sale") for i in r.data()["items"] if i["id"] == "sal-001"), "de volta dos vendidos, o item continua à venda")
    await r.open(pg, "#/buscar", ".sbar")
    await pg.fill('[data-input="search-q"]', "Sofá")
    await pg.wait_for_selector(".ilist .irow")
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".ilist .irow.selr")
    await pg.wait_for_timeout(300)
    await pg.click(".ilist .irow.selr")
    await pg.wait_for_selector('.ilist .irow.selr[aria-pressed="true"]')
    await pg.click('[data-act="sel-change"]')
    await pg.wait_for_selector('dialog.modal [data-f="venda"]')
    r.check(await pg.is_disabled("dialog.modal [data-ok]"), "tudo em Manter: o Aplicar inativo")
    await pg.click('dialog.modal label.chip:has(input[name="bk-venda"][value="nao"])')
    await pg.click("dialog.modal [data-ok]")
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    r.check(not any(i.get("sale") for i in r.data()["items"] if i["id"] == "sal-001"), "o Alterar tirou da venda")
    await pg.locator(".toast button").last.click()
    await pg.wait_for_timeout(700)
    it = next(i for i in r.data()["items"] if i["id"] == "sal-001")
    r.eq((it.get("sale") or {}).get("price"), 1500, "o Desfazer pôs de volta, com o preço pedido")

    # um consumível não tem o bloco
    r.api("PUT", "api/settings", {"consumiveis": True})
    r.api("POST", "api/rooms", {"kind": "consumiveis"})
    creme = r.api("POST", "api/items", {"room": "consumiveis", "name": "Creme de mãos", "dur": 180})["item"]
    await r.open(pg, f"#/i/{creme['id']}", "dialog.sheet h1")
    r.eq(await pg.locator("dialog.sheet .ivenda").count(), 0, "um consumível não vai à venda")
    await ctx.close()

    # em 320 px, claro: nada passa da largura
    ctx, pg = await r.page(b, "estreito", "light")
    r.api("PUT", "api/items/sal-001", {"sale": {"price": 1500}})
    await r.open(pg, "#/i/sal-001", "dialog.sheet .ivenda")
    r.check(await pg.evaluate(OVERFLOW), "[320] a ficha sem rolagem para o lado")
    await r.open(pg, "#/vendas", ".mscreen.vendas .ssum")
    r.check(await pg.evaluate(OVERFLOW), "[320] Vendas sem rolagem para o lado")
    await r.shot(pg, "vendas-320")
    await ctx.close()
    await b.close()
    ger.shutdown()


main("vendas", body)
