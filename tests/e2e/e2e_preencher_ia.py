"""Preencher com IA, no cadastro do item (Home Assistant de mentira): sem foto avisa; com foto, a IA lê a primeira foto
(com a dica e o cômodo) e preenche nome, detalhes, categoria, quantidade e valor; Desfazer; o que a pessoa escreveu
fica; a capa é a foto lida; IA desligada esconde; IA que não lê fotos explica."""
import json
import os
import time

from e2e_lib import OVERFLOW, FakeHA, helpers, main

AI_ITEM = {"name": "Cafeteira Oster Primalatte", "details": "Cafeteira espresso inox com vaporizador de leite.", "cat": "cozinha",
           "qty": "1", "value": 520, "zone": "Bancada", "existing": "", "confidence": "alta"}
FIELDS = "(ids) => ids.map(i => document.getElementById(i).value)"
IDS = ["f-name", "f-details", "f-cat", "f-qty", "f-value"]


async def body(r, p):
    ha = FakeHA()
    r.start(search=False, mock_ai=False, ha=ha)
    ha.media_root = r.app.path("media")

    def reply(kind, payload):
        time.sleep(1.2)  # dá para ver o "Lendo a foto…"
        return json.dumps({"items": [AI_ITEM]})
    ha.ai_reply = reply
    fotos = [os.path.join(helpers.FIXTURE, "photos", n) for n in ("cozinha-1.jpg", "sala-2.jpg")]
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")
    sent = []
    pg.on("request", lambda q: sent.append(json.loads(q.post_data)) if q.url.endswith("api/ai/identify") else None)

    async def new_item(room="cozinha"):
        await r.open(pg, f"#/c/{room}", ".rhead")
        await pg.click('.rhead-actions [data-act="item-new"]')
        await pg.wait_for_selector("#f-name")

    async def upload(path):
        n = await pg.locator('[data-slot="photos"] .ph img').count()
        async with pg.expect_file_chooser() as fc:
            await pg.click('[data-ed="upload"]')
        await (await fc.value).set_files(path)
        await pg.wait_for_function(f"document.querySelectorAll('[data-slot=photos] .ph img').length > {n}", timeout=10000)

    async def run_ai():
        """Preencher com IA e espera terminar (o botão volta depois do "Lendo")."""
        await pg.click('[data-ed="ai"]')
        await pg.wait_for_selector(".aibox .spin", timeout=4000)
        await pg.wait_for_selector('[data-ed="ai"]', timeout=15000)
        await pg.wait_for_timeout(150)

    # -- sem foto: avisa que precisa de uma
    await new_item()
    r.eq(" ".join((await pg.text_content(".aibox")).split()), "Com uma foto, a IA preenche os campos.", "sem foto: diz que a IA precisa de uma foto")
    r.check(await pg.locator('[data-ed="ai"], [data-ed-hint]').count() == 0, "sem foto: sem o botão nem a dica")
    await r.shot(pg, "sem-foto")

    # -- com foto: o botão e a dica; Enter na dica já lê
    await upload(fotos[0])
    r.eq((await pg.text_content('[data-ed="ai"]')).strip(), "Preencher com IA", "com foto: Preencher com IA")
    r.check(await pg.locator("[data-ed-hint]").count() == 1, "e a dica para a IA")
    await pg.fill("[data-ed-hint]", "é uma cafeteira Oster")
    await pg.press("[data-ed-hint]", "Enter")
    await pg.wait_for_selector(".aibox .spin", timeout=4000)
    r.check("Lendo a foto…" in await pg.text_content(".aibox") and await pg.is_disabled(".aibox .btn"), "Enter na dica lê a foto: Lendo, com o botão parado")
    await r.shot(pg, "lendo")
    await pg.wait_for_selector('[data-ed="ai"]', timeout=15000)
    await pg.wait_for_timeout(150)
    photo0 = sent[-1]["file"]
    r.eq({k: sent[-1][k] for k in ("mode", "room", "hint")}, {"mode": "single", "room": "cozinha", "hint": "é uma cafeteira Oster"}, "pede um item só, com o cômodo e a dica")
    call = ha.calls("POST", "/core/api/services/ai_task/generate_data")[-1]
    ins = call["body"]["instructions"]
    r.check("exatamente 1 item" in ins and "Cômodo: Cozinha." in ins and "Dica de quem está cadastrando: é uma cafeteira Oster" in ins, "a IA recebe o pedido de 1 item, o cômodo e a dica")
    r.eq(call.get("attachments_present"), [True], "a foto estava em /media enquanto a IA lia")
    left = os.listdir(r.app.path("media", "inventario", "ia-temp"))
    r.eq(left, [], "e sai de /media depois")
    r.eq(await pg.evaluate(FIELDS, IDS), ["Cafeteira Oster Primalatte", "Cafeteira espresso inox com vaporizador de leite.", "cozinha", "1", "520"],
         "preenche nome, detalhes, categoria, quantidade e valor")
    r.check(await pg.locator(".toast", has_text="Campos preenchidos pela IA. Confira antes de salvar.").locator("button", has_text="Desfazer").count() == 1,
            "aviso: Campos preenchidos pela IA, com Desfazer")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "preenchido")
    await pg.locator(".toast button", has_text="Desfazer").click()
    await pg.wait_for_timeout(200)
    r.eq(await pg.evaluate(FIELDS, IDS), ["", "", "", "1", ""], "Desfazer volta os campos")
    await run_ai()
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("#f-name", state="detached", timeout=8000)
    it = r.item_named("Cafeteira Oster Primalatte")
    r.check(it is not None and (it["value"], it["cat"], it["source"], it["photos"]) == (520, "cozinha", "ia", [photo0]), f"salva com o que a IA leu e a origem IA ({it and (it['value'], it['source'])})")
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    r.check("Leitura por IA" in await pg.text_content("dialog.sheet .props"), "a ficha diz que veio da leitura por IA")

    # -- o que a pessoa escreveu fica
    r.api("PUT", "api/settings", {"zones": True})
    await new_item()
    await pg.fill("#f-details", "Comprada em 2022, com nota fiscal")
    await pg.fill("#f-value", "350")
    await pg.fill("#f-zone", "Armário")
    await upload(fotos[0])
    await run_ai()
    vals = dict(zip(IDS + ["f-zone"], await pg.evaluate(FIELDS, IDS + ["f-zone"])))
    r.eq(vals["f-zone"], "Armário", "a zona escrita fica (a da IA não entra)")
    r.eq(vals["f-value"], "350", "o valor escrito fica")
    r.eq(vals["f-details"], "Comprada em 2022, com nota fiscal", "os detalhes escritos ficam")
    await pg.fill("#f-zone", "")
    await pg.dispatch_event("#f-zone", "input")
    await run_ai()
    r.eq(await pg.input_value("#f-zone"), "Bancada", "zona vazia: vem a da IA")
    await r.shot(pg, "escrito-fica")

    # -- a IA lê a primeira foto: usar outra como capa muda a foto lida
    await upload(fotos[1])
    await pg.click('[data-ed="cover"][data-i="1"]')
    await run_ai()
    r.check(sent[-1]["file"] != sent[-2]["file"], "outra foto como capa: a IA lê a nova primeira foto")
    for _ in range(2):
        await pg.click('[data-ed="rmphoto"][data-i="0"]')
    r.eq(" ".join((await pg.text_content(".aibox")).split()), "Com uma foto, a IA preenche os campos.", "tirar as fotos: volta o aviso")
    await pg.click('[data-ed="cancel"]')
    await pg.click('[data-r="1"]')
    await ctx.close()

    # -- editar um item que já tem foto: o botão já aparece
    ctx, pg = await r.page(b, "pc", "light", accent="azul")
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    r.eq(await pg.locator('[data-ed="ai"]').count(), 1, "editar item com foto: Preencher com IA à vista")
    await r.shot(pg, "editar-computador")
    await pg.click('[data-ed="cancel"]')
    await ctx.close()

    # -- a IA escolhida não lê fotos: explica em vez de chamar
    n_calls = len(ha.calls("POST", "/core/api/services/ai_task/generate_data"))
    r.api("PUT", "api/settings", {"ai_entity": "ai_task.texto_apenas"})
    ctx, pg = await r.page(b, "cel", "light")
    await new_item("quarto")
    await upload(fotos[0])
    await pg.click('[data-ed="ai"]')
    await pg.wait_for_selector('dialog[aria-label="Leitura por IA"]', timeout=8000)
    r.check("A IA escolhida não aceita fotos. Escolha outra." in await pg.text_content('dialog[aria-label="Leitura por IA"]'), "IA que não lê fotos: diz para escolher outra")
    await r.shot(pg, "ia-sem-fotos")
    await pg.click('dialog[aria-label="Leitura por IA"] button.primary[data-x]')
    r.eq(len(ha.calls("POST", "/core/api/services/ai_task/generate_data")), n_calls, "e não chama a IA")
    r.eq(await pg.input_value("#f-name"), "", "nem mexe nos campos")
    r.api("PUT", "api/settings", {"ai_entity": ""})
    await ctx.close()

    # -- Usar IA desligada: o editor não mostra nada de IA e o servidor recusa
    r.api("PUT", "api/settings", {"ai": False})
    ctx, pg = await r.page(b, "cel", "dark")
    await new_item()
    await upload(fotos[0])
    r.eq(await pg.locator(".aibox, [data-ed='ai'], [data-ed-hint]").count(), 0, "IA desligada: com foto, nada de Preencher com IA")
    await r.shot(pg, "ia-desligada")
    st, _, out = r.app.post("api/ai/identify", {"file": photo0, "mode": "single"})
    r.eq((st, out.get("error")), (409, "A IA está desligada. Para usar, ligue em Mais > Integrações."), "e o servidor recusa a leitura")
    r.eq(len(ha.calls("POST", "/core/api/services/ai_task/generate_data")), n_calls, "nenhuma chamada à IA com ela desligada")
    await ctx.close()
    await b.close()
    ha.stop()


main("preencher_ia", body)
