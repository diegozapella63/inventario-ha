"""1.114.0: a Tabela FIPE de um veículo (um bem do tipo Veículos): no editor, o campo Tabela FIPE (o código e o ano), só num
veículo; a ficha mostra o valor do mês e o Usar este valor, que é o único jeito de o valor do bem mudar (com o Desfazer).
A consulta é a um servidor de mentira; o carro e os valores são inventados."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from e2e_lib import OVERFLOW, main

TABELA = [{"valor": "R$ 85.608,00", "marca": "Marca Exemplo", "modelo": "Carro Exemplo 2.0", "anoModelo": 2014, "combustivel": "Gasolina", "mesReferencia": "novembro de 2026"}]


class Api(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        ok = self.path.endswith("/005340-6")
        dado = json.dumps(TABELA if ok else {"message": "x"}).encode()
        self.send_response(200 if ok else 404)
        self.send_header("Content-Length", str(len(dado)))
        self.end_headers()
        self.wfile.write(dado)


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


async def body(r, p):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Api)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r.start(search=False, env={"INV_FIPE": f"http://127.0.0.1:{srv.server_address[1]}"})
    bens = r.api("POST", "/api/rooms", {"kind": "bens"})["room"]
    carro = r.api("POST", "/api/items", {"room": bens["id"], "name": "Carro Exemplo", "cat": "veiculos", "value": 50000})["item"]
    casa = r.api("POST", "/api/items", {"room": bens["id"], "name": "Casa Exemplo", "cat": "imoveis", "value": 300000})["item"]
    b = await r.browser(p)
    for aparelho, tema in (("cel", "dark"), ("estreito", "light")):
        ctx, pg = await r.page(b, aparelho, tema, accent="azul")
        if aparelho == "cel":
            await r.open(pg, f"#/i/{casa['id']}", "dialog.sheet h1")
            await pg.click('dialog.sheet [data-act="item-edit"]')
            await pg.wait_for_selector('[data-ed="save"]')
            r.check(await pg.locator("#f-fipe-f").is_hidden(), "num imóvel, o campo Tabela FIPE não aparece")
            await pg.click('[data-ed="tipo"][data-v="veiculos"]')
            r.check(await pg.locator("#f-fipe-f").is_visible(), "trocando para Veículo, aparece")
            await pg.click('[data-ed="tipo"][data-v="imoveis"]')
            await pg.go_back()
            await pg.wait_for_timeout(300)
            await r.open(pg, f"#/i/{carro['id']}", "dialog.sheet h1")
            r.check(await pg.locator('[data-slot="fipe"]').count() == 0, "sem o código, a ficha não fala da FIPE")
            await pg.click('dialog.sheet [data-act="item-edit"]')
            await pg.wait_for_selector("#f-fipe-f")
            lbl = pg.locator("#f-fipe-f > .lbl")
            r.check("shut" in (await pg.get_attribute("#f-fipe-f", "class")) and await lbl.locator("svg").count() == 1, "vazio, começa fechado; o título com o ícone")
            await lbl.click()
            await pg.fill("#f-fipe", "005340-6")
            await pg.click('[data-ed="save"]')
            await pg.wait_for_timeout(300)
            r.check(await pg.is_visible('[data-err="fipe"]'), "sem o ano: o editor avisa e não salva")
            await pg.fill("#f-fipe", "0053406 2014")
            r.check(await pg.evaluate(OVERFLOW), "o editor sem rolagem para o lado")
            await r.shot(pg, "fipe-editor")
            await pg.click('[data-ed="save"]')
            await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
            it = next(i for i in r.data()["items"] if i["id"] == carro["id"])
            r.eq((it.get("fipe"), it.get("fipeYear"), it["value"]), ("005340-6", 2014, 50000), "o código e o ano gravados; o valor do bem igual")
        else:
            await r.open(pg, f"#/i/{carro['id']}", "dialog.sheet h1")
        await pg.wait_for_selector('[data-slot="fipe-valor"]', timeout=8000)
        r.eq(txt(await pg.text_content('[data-slot="fipe-valor"]')), "R$ 85.608", f"{aparelho}: o valor do mês na ficha")
        r.check("novembro de 2026" in txt(await pg.text_content('[data-slot="fipe"]')), f"{aparelho}: de quando é a tabela")
        bt = pg.locator('[data-act="fipe-usar"]')
        r.check(await bt.count() == 1 and await bt.locator("svg").count() == 1, f"{aparelho}: o Usar este valor, com ícone")
        r.eq(round((await bt.bounding_box())["height"]), 50, f"{aparelho}: o botão com 50 px")
        r.check(await pg.evaluate(OVERFLOW), f"{aparelho}: a ficha sem rolagem para o lado")
        await r.shot(pg, f"fipe-ficha-{aparelho}")
        if aparelho == "cel":
            await bt.click()
            await pg.wait_for_function("document.body.innerText.includes('Desfazer')")
            r.eq(next(i for i in r.data()["items"] if i["id"] == carro["id"])["value"], 85608, "o Usar este valor grava o valor da tabela")
            await pg.wait_for_function("!document.querySelector('[data-act=\"fipe-usar\"]')")
            r.check(True, "com o valor igual, o botão some")
            await pg.click("#toasts .toast button")
            await pg.wait_for_timeout(600)
            r.eq(next(i for i in r.data()["items"] if i["id"] == carro["id"])["value"], 50000, "o Desfazer volta o valor de antes")
        await ctx.close()
    await b.close()
    srv.shutdown()


main("fipe", body)
