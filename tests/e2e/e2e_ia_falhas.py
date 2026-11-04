"""Quando a IA falha (Home Assistant de mentira): cota excedida, resposta fora do formato (com "Ver resposta da IA"),
erro do Home Assistant e nenhum item, no Catalogar, no Preencher com IA e na busca na internet; Tentar de novo;
a IA desligada no meio da busca; o Home Assistant fora do ar."""
import json
import time

from e2e_lib import OVERFLOW, FakeHA, helpers, main

QUOTA = "429 RESOURCE_EXHAUSTED: You exceeded your current quota"
AI_CALLS = "/core/api/services/ai_task/generate_data"
GOOD = [
    {"name": "Abajur de cerâmica azul", "details": "Base de cerâmica e cúpula de linho.", "cat": "decoracao", "qty": "1", "value": 160, "zone": "", "existing": "", "confidence": "alta"},
    {"name": "Porta-retratos de madeira", "details": "", "cat": "decoracao", "qty": "2", "value": 40, "zone": "", "existing": "", "confidence": "media"},
]


def results(r):
    return [c["result"] for c in r.api("GET", "api/ai/usage")["recent"]]


async def pick_room_photo(pg):
    await pg.click('[data-ct="roomphoto"]')
    picker = pg.locator("dialog", has=pg.locator(".pick"))
    await picker.locator(".pick label").first.click()
    await picker.locator("[data-ok]").click()
    await pg.wait_for_selector(".cat-photo img", timeout=8000)


async def read_error(pg):
    """Clica em Ler foto (ou Tentar de novo) e espera a tela de erro."""
    await pg.click('dialog .dlg-f [data-ct="read"]')
    await pg.wait_for_selector("dialog .dlg-b .formerr", timeout=15000)
    return " ".join((await pg.text_content("dialog .dlg-b .formerr")).split())


async def body(r, p):
    ha = FakeHA()
    r.start(search=True, mock_ai=False, ha=ha)
    ha.media_root = r.app.path("media")
    reply = {"foto": "", "catalogo": "", "busca": ""}
    ha.ai_reply = lambda kind, payload: reply.get(kind, "") if not callable(reply.get(kind)) else reply[kind]()
    b = await r.browser(p)

    # -- Catalogar: cada falha mostra o motivo, e Tentar de novo lê de novo
    ctx, pg = await r.page(b, "cel", "dark", accent="coral")
    await r.open(pg, "#/c/sala", ".rhead")
    await pg.click('.rhead-actions [data-act="catalog"]')
    await pg.wait_for_selector('[data-ct="roomphoto"]')
    await pick_room_photo(pg)
    n_items = len(r.data()["items"])

    ha.ai_error = (500, QUOTA)
    msg = await read_error(pg)
    r.check("cota" in msg.lower(), "cota excedida: o aviso diz em português que a cota da IA acabou")
    r.eq(await pg.locator("dialog details").count(), 0, "cota excedida: sem Ver resposta da IA (não houve resposta)")
    foot = await pg.evaluate("[...document.querySelectorAll('dialog .dlg-f .btn')].map(b => b.textContent.trim())")
    r.eq(foot, ["Voltar", "Tentar de novo"], "na falha: Voltar e Tentar de novo")
    r.check(await pg.evaluate(OVERFLOW), "falha sem rolagem para o lado")
    await r.shot(pg, "catalogar-cota")
    r.eq(results(r)[0], "cota", "o uso da IA conta como cota excedida")

    ha.ai_error = None
    reply["catalogo"] = "Desculpe, não consigo identificar objetos nesta imagem."
    msg = await read_error(pg)
    r.eq(msg, "A IA respondeu sem uma lista de itens. Tente de novo ou use uma dica.", "Tentar de novo: resposta sem JSON")
    r.check(not await pg.is_visible("dialog details pre"), "Ver resposta da IA começa fechado")
    await pg.click("dialog details summary")
    raw = await pg.text_content("dialog details pre")
    r.eq(raw, reply["catalogo"], "Ver resposta da IA mostra o que a IA escreveu")
    await r.shot(pg, "catalogar-formato")
    r.eq(results(r)[0], "formato", "o uso conta como fora do formato")

    reply["catalogo"] = '{"items": [{"name": "Abajur", "value": 1'
    msg = await read_error(pg)
    r.eq(msg, "Não deu para entender a resposta da IA. Tente de novo.", "JSON cortado: não deu para entender")
    await pg.click("dialog details summary")
    r.eq(await pg.text_content("dialog details pre"), reply["catalogo"], "e mostra o JSON cortado")

    ha.ai_error = (500, "Erro inesperado no modelo")
    msg = await read_error(pg)
    r.eq(msg, "O Home Assistant recusou o pedido: Erro inesperado no modelo", "erro do Home Assistant: a mensagem dele")
    r.eq(results(r)[0], "erro", "o uso conta como erro")
    await pg.click('dialog .dlg-f [data-ct="back"]')
    await pg.wait_for_selector('dialog .dlg-f [data-ct="read"]:not([disabled])', timeout=4000)
    r.eq((await pg.text_content('dialog .dlg-f [data-ct="read"]')).strip(), "Ler foto", "Voltar: de novo em Ler foto, com a mesma foto")

    ha.ai_error = None
    reply["catalogo"] = json.dumps({"items": []})
    await pg.click('dialog .dlg-f [data-ct="read"]')
    await pg.wait_for_function("(document.querySelector('dialog .dlg-b') || {}).textContent?.includes('Nenhum item encontrado')", timeout=15000)
    r.check("Nenhum objeto encontrado. Tente uma foto mais próxima ou uma dica." in await pg.text_content("dialog .dlg-b"), "nenhum item: sugere outra foto ou uma dica")
    r.check(await pg.is_disabled('[data-ct="add"]'), "nenhum item: Adicionar desligado")
    await r.shot(pg, "catalogar-nenhum")

    reply["catalogo"] = json.dumps({"items": GOOD})
    await pg.click('dialog .dlg-f [data-ct="back"]')
    await pg.wait_for_selector('dialog .dlg-f [data-ct="read"]:not([disabled])', timeout=4000)
    await pg.click('dialog .dlg-f [data-ct="read"]')
    await pg.wait_for_selector(".found li", timeout=15000)
    names = await pg.evaluate("[...document.querySelectorAll('.found .fname')].map(i => i.value)")
    r.eq(names, ["Abajur de cerâmica azul", "Porta-retratos de madeira"], "depois das falhas, a leitura certa lista os itens")
    r.eq(len(ha.calls("POST", AI_CALLS)), 6, "cada Ler foto e Tentar de novo chamou a IA uma vez")
    r.eq(len(r.data()["items"]), n_items, "nenhuma falha adicionou itens")
    await pg.click('[data-ct="add"]')
    await pg.locator(".toast", has_text="2 itens adicionados").wait_for(timeout=6000)
    await ctx.close()

    # -- Preencher com IA, no cadastro
    ctx, pg = await r.page(b, "cel", "light", accent="verde")
    await r.open(pg, "#/c/escritorio", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    await pg.click('[data-ed="roomphotos"]')
    picker = pg.locator("dialog", has=pg.locator(".pick"))
    await picker.locator(".pick label").first.click()
    await picker.locator("[data-ok]").click()
    await pg.wait_for_selector('[data-ed="ai"]', timeout=6000)

    async def fill_error(text):
        await pg.click('[data-ed="ai"]')
        t = pg.locator(".toast.err", has_text=text)
        await t.wait_for(timeout=15000)
        await pg.wait_for_selector('[data-ed="ai"]:not([disabled])', timeout=4000)
        return " ".join((await t.first.text_content()).split())

    ha.ai_error = (500, QUOTA)
    msg = await fill_error("cota da IA acabou")
    r.check("cota da IA acabou" in msg, f"Preencher com IA, cota excedida: diz em português ({msg[:70]})")
    r.eq(await pg.input_value("#f-name"), "", "e os campos ficam como estavam")
    await r.shot(pg, "preencher-cota")
    ha.ai_error = None
    reply["foto"] = "Não sei dizer o que é."
    msg = await fill_error("sem uma lista")
    r.eq(msg, "A IA respondeu sem uma lista de itens. Tente de novo ou use uma dica.", "Preencher com IA, fora do formato: aviso")
    reply["foto"] = json.dumps({"items": []})
    msg = await fill_error("não reconheceu")
    r.eq(msg, "A IA não reconheceu um item nesta foto. Tente outra foto ou escreva uma dica.", "Preencher com IA, nenhum item: aviso")
    reply["foto"] = json.dumps({"items": GOOD[:1]})
    await pg.click('[data-ed="ai"]')
    await pg.locator(".toast", has_text="Campos preenchidos pela IA").wait_for(timeout=15000)
    r.eq([await pg.input_value("#f-name"), await pg.input_value("#f-value")], ["Abajur de cerâmica azul", "160"], "Preencher com IA de novo: agora preenche")
    await pg.click('[data-ed="cancel"]')
    await pg.click('[data-r="1"]')
    await ctx.close()

    # -- Buscar na internet, na ficha
    iid = r.api("POST", "api/items", {"name": "Cafeteira", "room": "cozinha", "cat": "outros", "value": 0})["item"]["id"]
    ctx, pg = await r.page(b, "cel", "dark", accent="azul")

    async def web_error(start=True):
        if start:
            await r.open(pg, f"#/i/{iid}", 'dialog.sheet [data-act="web-photo"]')
            await pg.click('dialog.sheet [data-act="web-photo"]')
        else:
            await pg.click("dialog [data-go]")
        await pg.wait_for_selector('[data-slot="web"] .formerr', timeout=20000)
        return " ".join((await pg.text_content('[data-slot="web"] .formerr')).split())

    ha.ai_error = (500, QUOTA)
    msg = await web_error()
    r.check("cota da IA acabou" in msg, f"busca, cota excedida: diz em português ({msg[:70]})")
    r.check(await pg.locator(".wgrid, .wprod").count() == 0 and await pg.is_disabled("dialog [data-ok]"), "sem fotos, sem dados e Usar foto desligado")
    r.eq(await pg.locator(".wtip").count(), 0, "cota excedida: sem a dica da busca na web")
    await r.shot(pg, "busca-cota")
    ha.ai_error = None
    reply["busca"] = "Encontrei várias cafeteiras parecidas nas lojas."
    msg = await web_error(start=False)
    r.check(msg.startswith("A IA respondeu sem usar a busca na web."), f"Buscar de novo, resposta fora do formato: sem busca na web ({msg[:60]})")
    slot = await pg.text_content('[data-slot="web"]')
    r.check("Mais, Configurações, Integrações" in slot, "e diz onde fica a IA de busca")
    r.eq(slot.count("Mais, Configurações, Integrações"), 1, "diz uma vez só onde fica a IA de busca, sem aviso repetido")
    reply["busca"] = json.dumps({"erro": "sem_busca"})
    msg = await web_error(start=False)
    r.check(msg.startswith("A IA não usou a busca na web."), f"a IA avisa que não buscou: diz o que ligar ({msg[:60]})")
    await r.shot(pg, "busca-sem-busca")
    reply["busca"] = json.dumps(helpers.search_answer(r.site))
    await pg.click("dialog [data-go]")
    await pg.wait_for_selector(".wgrid .wimg", timeout=20000)
    r.check(await pg.locator(".wgrid .wimg").count() >= 3, "Buscar de novo com a busca certa: as fotos aparecem")
    r.eq(results(r)[:4], ["ok", "sem_busca", "sem_busca", "cota"], "o uso da IA conta cada busca com o resultado")

    # a IA desligada no meio da busca: o resultado não chega
    def slow():
        time.sleep(2.5)
        return json.dumps(helpers.search_answer(r.site))
    reply["busca"] = slow
    await pg.click("dialog [data-go]")
    await pg.wait_for_selector(".wbusy", timeout=5000)
    r.api("PUT", "api/settings", {"ai": False})
    await pg.wait_for_selector('[data-slot="web"] .formerr', timeout=20000)
    r.eq((await pg.text_content('[data-slot="web"] .formerr')).strip(), "A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações.", "IA desligada no meio da busca: o resultado não chega")
    r.eq(await pg.locator(".wgrid .wimg").count(), 0, "e nenhuma foto aparece")
    await r.shot(pg, "busca-ia-desligada")
    r.api("PUT", "api/settings", {"ai": True})
    await pg.click("dialog [data-x]")
    await ctx.close()

    # -- Home Assistant fora do ar: o Catalogar explica e não abre
    ha.stop()
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/c/quarto", ".rhead")
    await pg.click('.rhead-actions [data-act="catalog"]')
    t = pg.locator(".toast.err", has_text="O Home Assistant não respondeu")
    await t.wait_for(timeout=10000)
    r.check(True, "Home Assistant fora do ar: Catalogar diz em português que não teve resposta")
    r.eq(await pg.locator('[data-ct="upload"]').count(), 0, "e não abre a leitura")
    r.eq(await pg.locator('dialog[aria-label="Leitura por IA"]').count(), 0, "sem resposta do Home Assistant: não manda configurar a IA de novo")
    await r.shot(pg, "ha-fora-do-ar")
    await ctx.close()
    await b.close()


main("ia_falhas", body)
