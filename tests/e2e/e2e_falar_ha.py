"""Falar com o Home Assistant de mentira de verdade (microfone de mentira do Chromium): o áudio vai para a fala para
texto do assistente preferido, no idioma dele; a fala para texto escolhida em Integrações; a escolhida que saiu do
Home Assistant; erros da fala para texto; "Não ouvi nada" com áudio curto; a IA separa os itens (e o cômodo dito);
resposta da IA fora do formato; sem uma IA que responda, o app separa sozinho; com Usar IA desligada, o Falar some."""
import json

from e2e_lib import OVERFLOW, FakeHA, main

SPOKEN = "Sofá cinza, dois mil reais. Televisão de 50 polegadas, mil e quinhentos reais."
AI_ITEMS = {"room": "quarto", "items": [
    {"name": "Sofá cinza", "details": "", "cat": "moveis", "qty": "1", "value": 2000, "zone": "", "existing": "", "confidence": "alta"},
    {"name": "Televisão 50 polegadas", "details": "", "cat": "eletronicos", "qty": "1", "value": 1500, "zone": "", "existing": "", "confidence": "alta"},
]}
STT = "/core/api/stt/"


def stt_posts(ha):
    return [c for c in ha.calls("POST", STT)]


async def body(r, p):
    ha = FakeHA()
    r.start(search=False, mock_ai=False, ha=ha)
    ha.media_root = r.app.path("media")
    ha.stt_text = SPOKEN
    answer = {"fala": json.dumps(AI_ITEMS)}
    ha.ai_reply = lambda kind, payload: answer.get(kind, "{}")
    b = await r.browser(p, mic=True)
    ctx, pg = await r.page(b, "cel", "dark", accent="lilas", perms=["microphone"])

    async def speak(ms=1300, start=True):
        """Abre o Falar (ou fala de novo), fala `ms` milissegundos e toca em Pronto."""
        if start:
            await r.open(pg, "#/", ".mic-top")
            await pg.click(".mic-top")
        else:
            await pg.click('[data-ct="mic"]')
        await pg.wait_for_selector(".voice.on", timeout=8000)
        await pg.wait_for_timeout(ms)
        await pg.click('[data-ct="done"]')

    async def voice_error():
        await pg.wait_for_selector(".voice .formerr, .dlg-b > .formerr", timeout=15000)
        return " ".join((await pg.text_content("dialog .dlg-b .formerr")).split())

    # -- o assistente preferido do Home Assistant transcreve, em pt-BR, e a IA separa os itens
    await speak()
    await pg.wait_for_selector(".found li", timeout=15000)
    post = stt_posts(ha)[-1]
    r.eq(post["path"], STT + "stt.home_assistant_cloud", "o áudio vai para a fala para texto do assistente preferido")
    r.eq(post["body"]["speech"], "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1; language=pt-BR", "como áudio de 16 kHz, em pt-BR")
    r.check(post["body"]["bytes"] >= 12800 and post["body"]["bytes"] % 2 == 0, f"com o som gravado (mais de 0,4 s, {post['body']['bytes']} bytes)")
    r.eq((await pg.text_content(".heard span")).strip(), f"“{SPOKEN}”", "mostra o que a fala para texto ouviu")
    ins = ha.calls("POST", "/core/api/services/ai_task/generate_data")[-1]["body"]["instructions"]
    r.check("O texto no fim é o que a pessoa falou" in ins and SPOKEN in ins, "a IA recebe o que foi dito")
    found = await pg.evaluate("[...document.querySelectorAll('.found li')].map(li => [li.querySelector('.fname').value, li.querySelector('[data-rf=value]').value])")
    r.eq(found, [["Sofá cinza", "2.000"], ["Televisão 50 polegadas", "1.500"]], "a IA separa os itens com os valores ditos")
    r.eq(await pg.input_value("#c-room"), "quarto", "o cômodo que a pessoa disse já vem escolhido")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "revisar")
    await pg.click('[data-ct="add"]')
    await pg.locator(".toast", has_text="2 itens adicionados em Quarto").wait_for(timeout=6000)
    voz = [i for i in r.data()["items"] if i.get("source") == "voz"]
    r.check(len(voz) == 2 and all(i["room"] == "quarto" for i in voz), "os itens falados vão para o Quarto, como falados")

    # -- outra fala para texto, escolhida em Integrações: o idioma é o que ela aceita
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    await pg.wait_for_selector('[data-input="voice-stt"]', timeout=10000)
    await pg.select_option('[data-input="voice-stt"]', "stt.faster_whisper")
    await pg.locator(".toast", has_text="Falar agora transcreve com faster-whisper").wait_for(timeout=8000)
    st = " ".join((await pg.text_content('[data-slot="voice-panel"] .ot span:not(.status)')).split())
    r.eq(st, "Transcreve com faster-whisper (pt).", "Integrações: a escolhida e o idioma dela")
    await r.shot(pg, "integracoes-faster-whisper")
    await speak()
    await pg.wait_for_selector(".found li", timeout=15000)
    post = stt_posts(ha)[-1]
    r.eq([post["path"], post["body"]["speech"].rsplit("language=", 1)[1]], [STT + "stt.faster_whisper", "pt"], "o áudio vai para a escolhida, no idioma que ela aceita (pt)")
    await pg.click('.dlg-f [data-ct="cancel"]')
    await pg.click('[data-r="1"]')

    # -- a escolhida saiu do Home Assistant: volta para a do assistente
    ha.states = [s for s in ha.states if s["entity_id"] != "stt.faster_whisper"]
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    await pg.click('[data-act="voice-refresh"]')
    await pg.wait_for_function("(document.querySelector('[data-slot=voice-panel]') || {}).textContent?.includes('saiu do Home Assistant')", timeout=10000)
    st = " ".join((await pg.text_content('[data-slot="voice-panel"] .ot span:not(.status)')).split())
    r.check("A escolhida saiu do Home Assistant: usando o padrão." in st and "Home Assistant Cloud (pt-BR)" in st, f"a escolhida sumiu: avisa e usa o padrão ({st[:70]})")
    await speak()
    await pg.wait_for_selector(".found li", timeout=15000)
    r.eq(stt_posts(ha)[-1]["path"], STT + "stt.home_assistant_cloud", "e transcreve com a do assistente")
    await pg.click('.dlg-f [data-ct="cancel"]')
    await pg.click('[data-r="1"]')
    ha.states.append({"entity_id": "stt.faster_whisper", "state": "unknown", "attributes": {"friendly_name": "faster-whisper"}})
    r.api("PUT", "api/settings", {"voice_stt": ""})

    # -- erros da fala para texto: a pessoa fala de novo ali mesmo
    n_ai = len(ha.calls("POST", "/core/api/services/ai_task/generate_data"))
    ha.stt_status = 500
    await speak()
    msg = await voice_error()
    r.eq(msg, "A fala para texto do Home Assistant falhou (500: falhou).", "a fala para texto falhou: diz o que houve")
    r.check(await pg.locator(".voice").count() == 1 and await pg.is_disabled('[data-ct="done"]'), "e volta para o microfone, sem ouvir")
    await r.shot(pg, "erro-fala-para-texto")
    ha.stt_status = 400
    await speak(start=False)
    r.eq(await voice_error(), "A fala para texto não aceitou o áudio (falhou).", "a fala para texto recusou o áudio: diz isso")
    ha.stt_status, ha.stt_result = 200, "error"
    await speak(start=False)
    r.eq(await voice_error(), "Não entendi. Tente de novo, mais perto do microfone.", "não entendeu: pede para falar mais perto")
    ha.stt_result = "success"
    r.eq(len(ha.calls("POST", "/core/api/services/ai_task/generate_data")), n_ai, "nenhuma falha da fala para texto chamou a IA")
    await speak(start=False)
    await pg.wait_for_selector(".found li", timeout=15000)
    r.check(True, "falar de novo, com a fala para texto de volta, dá certo")
    await pg.click('.dlg-f [data-ct="cancel"]')
    await pg.click('[data-r="1"]')

    # -- áudio curto: nem manda
    n_stt = len(stt_posts(ha))
    await speak(ms=0)
    r.eq(await voice_error(), "Não ouvi nada. Toque no microfone e fale.", "Pronto logo depois de abrir: Não ouvi nada")
    r.eq(len(stt_posts(ha)), n_stt, "e o áudio curto nem vai para o Home Assistant")
    await r.shot(pg, "nao-ouvi")
    await pg.click('.dlg-f [data-ct="cancel"]')

    # -- a IA responde fora do formato: Ver resposta da IA e Tentar de novo (sem falar de novo)
    answer["fala"] = "Ok! Anotei o sofá e a televisão."
    await speak()
    await pg.wait_for_selector("dialog details summary", timeout=15000)
    r.eq(" ".join((await pg.text_content("dialog .dlg-b .formerr")).split()), "A IA respondeu sem uma lista de itens. Tente de novo ou use uma dica.", "IA fora do formato: avisa")
    await pg.click("dialog details summary")
    r.eq(await pg.text_content("dialog details pre"), answer["fala"], "Ver resposta da IA")
    r.eq(await pg.evaluate("[...document.querySelectorAll('dialog .dlg-f .btn')].map(b => b.textContent.trim())"), ["Falar de novo", "Tentar de novo"], "Falar de novo ou Tentar de novo")
    await r.shot(pg, "ia-formato")
    n_stt = len(stt_posts(ha))
    answer["fala"] = json.dumps(AI_ITEMS)
    await pg.click('dialog .dlg-f [data-ct="read"]')
    await pg.wait_for_selector(".found li", timeout=15000)
    r.eq(len(stt_posts(ha)), n_stt, "Tentar de novo lê o mesmo texto, sem gravar de novo")
    await pg.click('.dlg-f [data-ct="cancel"]')
    await pg.click('[data-r="1"]')
    await ctx.close()

    # -- IA ligada, mas sem uma IA no Home Assistant que responda: a fala para texto continua, e o app separa pelas vírgulas
    ai_states = [s for s in ha.states if s["entity_id"].startswith("ai_task.")]
    ha.states = [s for s in ha.states if not s["entity_id"].startswith("ai_task.")]
    n_ai = len(ha.calls("POST", "/core/api/services/ai_task/generate_data"))
    ctx, pg = await r.page(b, "cel", "light", accent="verde", perms=["microphone"])
    await speak()
    await pg.wait_for_selector(".found li", timeout=15000)
    found = await pg.evaluate("[...document.querySelectorAll('.found li')].map(li => [li.querySelector('.fname').value, li.querySelector('[data-rf=value]').value])")
    r.eq(found, [["Sofá cinza", "2.000"], ["Televisão de 50 polegadas", "1.500"]], "sem IA que responda: o Home Assistant transcreve e o app separa, com os valores falados")
    r.eq(len(ha.calls("POST", "/core/api/services/ai_task/generate_data")), n_ai, "sem chamar a IA")
    await r.shot(pg, "sem-ia")
    await ctx.close()
    ha.states += ai_states

    # -- Usar IA desligada: o Falar some junto, e o servidor recusa o áudio sem mandar para a fala para texto
    r.api("PUT", "api/settings", {"ai": False})
    n_stt = len(stt_posts(ha))
    ctx, pg = await r.page(b, "cel", "light", accent="verde", perms=["microphone"])
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.locator(".mic-top").count(), 0, "IA desligada: sem o microfone no alto")
    st, _, out = r.app.request("POST", "api/voice", raw=b"\x01\x00" * 16000, headers={"Content-Type": "application/octet-stream"})
    r.eq((st, out.get("error")), (409, "A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações."), "o servidor recusa o Falar")
    r.eq(len(stt_posts(ha)), n_stt, "sem mandar o áudio para a fala para texto")
    r.api("PUT", "api/settings", {"ai": True})
    await ctx.close()
    await b.close()
    ha.stop()


main("falar_ha", body)
