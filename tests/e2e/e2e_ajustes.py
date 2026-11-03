"""Mais > Integrações (com um Home Assistant de mentira), Aparência (tema e cor) e Opções (zonas e categorias)."""
import datetime
import json
import time

from e2e_lib import FakeHA, main

SENSOR = "sensor.inventaria_ia_hoje"


async def tab(pg, k):
    await pg.click(f'.more-tabs [data-tab="{k}"]')
    await pg.wait_for_selector(f'#mt-{k}[aria-selected="true"]')
    await pg.wait_for_timeout(600)


async def body(r, p):
    ha = FakeHA()
    r.start(search=False, mock_ai=False, ha=ha)
    ha.media_root = r.app.path("media")
    photo = next(i["photos"][0] for i in r.data()["items"] if i["photos"])
    item = {"name": "Abajur de cerâmica", "details": "Cúpula de linho.", "cat": "decoracao", "qty": "1", "value": 160, "zone": "", "existing": "", "confidence": "alta"}
    ha.ai_reply = lambda kind, payload: json.dumps({"items": [item]})
    b = await r.browser(p)

    # -- Integrações
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")
    await r.open(pg, "#/mais/integracoes", ".more-tabs")
    await pg.wait_for_selector('#p-ai .status.ok', timeout=10000)
    r.eq((await pg.text_content("#p-ai .status")).strip(), "Pronta para ler fotos", "a IA do Home Assistant está pronta")
    opts = await pg.evaluate("[...document.querySelectorAll('[data-input=ai-entity] option')].map(o => [o.textContent, o.disabled])")
    r.eq(opts, [["Padrão do Home Assistant", False], ["Google AI Task", False], ["IA só de texto (não lê fotos)", True]], "IA para ler fotos: a que não lê fotos fica desligada")
    await pg.select_option('[data-input="ai-entity"]', "ai_task.google_ai_task")
    await pg.locator(".toast").first.wait_for()
    await pg.wait_for_timeout(300)
    r.eq(r.data()["settings"]["ai_entity"], "ai_task.google_ai_task", "a escolha da IA para fotos fica gravada")
    groups = await pg.evaluate("[...document.querySelectorAll('[data-input=ai-search] optgroup')].map(g => [g.label, [...g.children].map(o => o.value)])")
    r.check(groups == [["Tarefas de IA", ["ai_task.google_ai_task", "ai_task.texto_apenas"]], ["Assistentes de conversa", ["conversation.google_generative_ai"]]],
            f"IA para buscar na internet: tarefas e assistentes, sem o assistente sem IA ({groups})")
    await pg.select_option('[data-input="ai-search"]', "conversation.google_generative_ai")
    await pg.locator(".toast", has_text="IA para buscar fotos atualizada").wait_for(timeout=5000)
    r.eq(r.data()["settings"]["ai_search"], "conversation.google_generative_ai", "e a de buscar também")

    # Falar
    await pg.wait_for_selector('[data-input="voice-stt"]', timeout=10000)
    st = " ".join((await pg.text_content('[data-slot="voice-panel"] li .ot')).split())
    r.check(st.startswith("Pronto para ouvir") and "Home Assistant Cloud (pt-BR), do assistente Gemini" in st, f"Falar: quem transcreve ({st})")
    engines = await pg.evaluate("[...document.querySelectorAll('[data-input=voice-stt] option')].map(o => o.textContent)")
    r.eq(engines, ["Padrão do Home Assistant", "faster-whisper", "Home Assistant Cloud"], "Fala para texto: as do Home Assistant, em ordem")
    await pg.select_option('[data-input="voice-stt"]', "stt.faster_whisper")
    await pg.locator(".toast", has_text="faster-whisper").wait_for(timeout=8000)
    r.eq(r.data()["settings"]["voice_stt"], "stt.faster_whisper", "a fala para texto escolhida fica gravada")
    await r.shot(pg, "integracoes", full_page=True)

    # uso da IA: uma leitura de foto conta
    r.api("POST", "api/ai/identify", {"file": photo, "mode": "single"})
    await r.open(pg, "#/mais/integracoes", ".more-tabs")
    await pg.wait_for_selector(".uso-tiles", timeout=10000)
    hoje = await pg.text_content(".uso-tiles .uso-tile .v")
    r.eq(hoje.strip(), "1", "Uso da IA: 1 chamada hoje")
    await pg.click(".uso-ult summary")
    ult = await pg.text_content(".uso-ult li")
    r.check("Preencher com IA" in ult and "Google AI Task" in ult, f"última chamada, com a IA usada ({' '.join(ult.split())[:60]})")
    r.check("Google Cloud Console" in await pg.text_content("#p-usage .help"), "link do consumo exato do Gemini")
    await pg.locator(".uso-bar").first.click()
    cap = await pg.text_content(".uso-cap")
    r.check("0 chamadas" in cap, f"tocar num dia mostra o dia ({cap.strip()})")
    await pg.evaluate("document.querySelector('#p-usage').scrollIntoView()")
    await r.shot(pg, "uso-ia")

    # sensores no Home Assistant
    r.check(ha.state(SENSOR) is None, "sem o sensor até ligar")
    await pg.click('label.switch:has([data-input="sensors-on"])')
    await pg.locator(".toast", has_text="Sensor criado").wait_for(timeout=8000)
    for _ in range(30):
        if ha.state(SENSOR):
            break
        time.sleep(0.2)
    s = ha.state(SENSOR)
    r.check(s is not None and str(s["state"]) == "1" and s["attributes"]["imagens"] == 1, f"sensor criado com as chamadas de hoje ({s and s['state']})")
    await pg.click('label.switch:has([data-input="sensors-on"])')
    await pg.locator(".toast", has_text="Sensores desligados").wait_for(timeout=8000)
    for _ in range(30):
        if ha.state(SENSOR) is None:
            break
        time.sleep(0.2)
    r.check(ha.state(SENSOR) is None, "desligar tira o sensor do Home Assistant")

    # Usar IA desligada: some o que usa IA, o Falar continua sem IA
    await pg.click('label.switch:has([data-input="ai-on"])')
    await pg.locator(".toast", has_text="IA desligada").wait_for(timeout=8000)
    r.check(r.data()["settings"]["ai"] is False, "Usar IA desligada fica gravada")
    for sel, label in (("[data-input=ai-entity]", "IA para ler fotos"), ("#p-usage", "Uso da IA"), ("#p-sensors", "Sensores"), ('[data-act="catalog"]', "Catalogar no alto")):
        r.eq(await pg.locator(sel).count(), 0, f"IA desligada: sem {label}")
    await pg.wait_for_function("(e => e && e.textContent.includes('sem IA'))(document.querySelector('[data-slot=voice-panel] .status'))", timeout=8000)
    r.check("Sem IA, o app separa os itens pelas vírgulas." in await pg.text_content('[data-slot="voice-panel"]'), "Falar continua, sem IA")
    await r.shot(pg, "ia-desligada", full_page=True)
    n = len(ha.calls("POST", "/core/api/services"))
    await pg.click('label.switch:has([data-input="ai-on"])')
    await pg.locator(".toast", has_text="IA ligada").wait_for(timeout=8000)
    r.eq(await pg.locator("#p-usage").count(), 1, "ligada de novo: tudo volta")
    r.eq(len(ha.calls("POST", "/core/api/services")), n, "ligar e desligar não chama a IA")
    await ctx.close()

    # sem Home Assistant que transcreva: o Falar some do alto e diz o que configurar
    ha.pipelines = {"preferred_pipeline": "sem-fala", "pipelines": [{"id": "sem-fala", "name": "Só texto", "stt_engine": None}]}
    ha.states = [s for s in ha.states if not s["entity_id"].startswith("stt.")]
    r.api("PUT", "api/settings", {"voice_stt": ""})
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/mais/integracoes", ".more-tabs")
    await pg.click('[data-act="voice-refresh"]')
    await pg.wait_for_function("(e => e && e.textContent.includes('Sem fala para texto'))(document.querySelector('[data-slot=voice-panel] .status'))", timeout=10000)
    r.check("Assistentes de voz" in await pg.text_content('[data-slot="voice-panel"]'), "sem fala para texto: diz onde configurar")
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.locator(".mic-top").count(), 0, "e o microfone sai do alto")
    await ctx.close()

    # -- Aparência: tema e cor, só neste aparelho; a Cor do dia vem ligada
    ctx, pg = await r.page(b, "cel", "light", accent=None)
    await ctx.clock.install(time=datetime.datetime(2026, 11, 3, 23, 59, 30))  # hora local
    await r.open(pg, "#/mais/aparencia", ".more-tabs")
    r.eq(await pg.evaluate("[new Date().getDate(), new Date().getHours()]"), [3, 23], "o navegador está em 3 de novembro, 23h59")
    html_ = pg.locator("html")
    daily = pg.get_by_role("switch", name="Cor do dia")
    r.check(await daily.is_checked(), "Cor do dia vem ligada")
    r.eq(await pg.evaluate("[...document.querySelectorAll('#p-accent .opts .ot > *')].map(e => e.textContent)"), ["Cor do dia", "Muda a cor do app todo dia."], "Cor do dia, com a dica curta, junto da cor do app")
    r.eq(await html_.get_attribute("data-accent"), "turquesa", "3 de novembro de 2026: turquesa")
    checked = "document.querySelector('[data-input=accent]:checked').value"
    r.eq(await pg.evaluate(checked), "turquesa", "a cor do dia é a marcada")
    box = await pg.evaluate("(() => { const s = document.querySelector('#p-accent .switch').getBoundingClientRect(), z = document.querySelector('#p-accent .swatches').getBoundingClientRect(); return [Math.round(innerWidth - s.right), s.bottom <= z.top]; })()")
    r.check(box[1] and box[0] <= 24, f"a chave fica à direita, acima das cores ({box})")
    await r.shot(pg, "cor-do-dia", full_page=True)
    await pg.set_viewport_size({"width": 320, "height": 700})
    box = await pg.evaluate("(() => { const s = document.querySelector('#p-accent .switch').getBoundingClientRect(), t = document.querySelector('#daily-h').getBoundingClientRect(); return [Math.round(innerWidth - s.right), s.top < t.bottom]; })()")
    r.check(box[1] and box[0] <= 24, f"no celular de 320 px, a chave continua à direita, na linha do nome ({box})")
    await r.shot(pg, "cor-do-dia-320")
    await pg.set_viewport_size({"width": 384, "height": 854})
    await ctx.clock.fast_forward("02:00")  # passa da meia-noite com o app aberto
    await pg.wait_for_function("document.documentElement.dataset.accent === 'verde'", timeout=5000)
    r.eq([await html_.get_attribute("data-accent"), await pg.evaluate(checked)], ["verde", "verde"], "passou da meia-noite: a cor do dia seguinte, sem recarregar")
    await pg.click('[data-act="theme"][data-theme="dark"]')
    r.eq(await pg.evaluate("document.documentElement.dataset.theme"), "dark", "tema Escuro")
    r.eq(await pg.get_attribute('[data-act="theme"][data-theme="dark"]', "aria-pressed"), "true", "o botão fica marcado")
    accents = await pg.evaluate("[...document.querySelectorAll('.sw')].map(s => s.dataset.accent)")
    r.eq(accents, ["amarelo", "laranja", "coral", "rosa", "lilas", "azul", "turquesa", "verde", "kraft", "cinza"], "as 10 cores do app")
    # escolher uma cor desliga a Cor do dia
    await pg.click('.sw[data-accent="rosa"]')
    r.eq(await html_.get_attribute("data-accent"), "rosa", "cor Rosa")
    r.check(not await daily.is_checked(), "escolher uma cor desliga a Cor do dia")
    r.eq(await pg.evaluate("[localStorage.getItem('inv:accent'), localStorage.getItem('inv:accentDaily')]"), ['"rosa"', "false"], "e fica gravado neste aparelho")
    await ctx.clock.fast_forward("24:00:00")
    await pg.evaluate("window.dispatchEvent(new Event('focus'))")
    r.eq(await html_.get_attribute("data-accent"), "rosa", "desligada, a cor não muda no outro dia")
    # ligar de novo volta à cor do dia (5 de novembro: kraft); desligar volta à escolhida
    await daily.click()
    r.eq([await html_.get_attribute("data-accent"), await pg.evaluate(checked)], ["kraft", "kraft"], "ligar de novo: a cor do dia, marcada")
    await daily.click()
    r.eq([await html_.get_attribute("data-accent"), await pg.evaluate(checked)], ["rosa", "rosa"], "desligar: a cor escolhida antes")
    await pg.click('.sw[data-accent="verde"]')
    r.eq(await html_.get_attribute("data-accent"), "verde", "cor Verde")
    await pg.reload()
    await pg.wait_for_selector(".more-tabs")
    r.eq(await pg.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.accent]"), ["dark", "verde"], "tema e cor ficam depois de recarregar")
    r.check(not await daily.is_checked() and await pg.evaluate(checked) == "verde", "e a Cor do dia continua desligada")
    await r.shot(pg, "aparencia", full_page=True)
    await pg.click('[data-act="theme"][data-theme="auto"]')
    r.check(await pg.evaluate("!document.documentElement.dataset.theme"), "Automático segue o celular")
    await ctx.close()

    # quem já tinha escolhido uma cor também passa a ter a Cor do dia; depois da última cor da paleta, volta à primeira
    ctx, pg = await r.page(b, "cel", "dark", accent=None, init="try{if(!localStorage.getItem('inv:accent'))localStorage.setItem('inv:accent', JSON.stringify('coral'))}catch(e){}")
    await ctx.clock.install(time=datetime.datetime(2026, 11, 5, 23, 59, 0))
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.locator("html").get_attribute("data-accent"), "kraft", "cor escolhida antes (Coral): vale a do dia (Kraft)")
    await ctx.clock.fast_forward("02:00")
    await pg.wait_for_function("document.documentElement.dataset.accent !== 'kraft'", timeout=5000)
    r.eq(await pg.evaluate("document.documentElement.dataset.accent || 'amarelo'"), "amarelo", "6 de novembro: depois do Kraft, o Amarelo de novo (o Cinza fica de fora)")
    await r.shot(pg, "cor-do-dia-inicio")
    await r.open(pg, "#/mais/aparencia", ".more-tabs")
    r.check(await pg.get_by_role("switch", name="Cor do dia").is_checked() and await pg.evaluate(checked) == "amarelo", "na Aparência, ligada e com o Amarelo marcado")
    await ctx.close()

    # o index.html pinta a cor do dia antes do app.js (a mesma conta, dias seguidos)
    ctx, pg = await r.page(b, "cel", "light", accent=None)
    await pg.route("**/app.js*", lambda route: route.abort())
    want = ["turquesa", "verde", "kraft", "amarelo", "laranja", "coral", "rosa", "lilas", "azul", "turquesa"]
    got = []
    for d in range(10):
        await ctx.clock.set_fixed_time(datetime.datetime(2026, 11, 3 + d, 8, 0, 0))
        await pg.goto("about:blank")
        await pg.goto(r.base + "#/")
        got.append(await pg.evaluate("document.documentElement.dataset.accent || 'amarelo'"))
    r.eq(got, want, "antes do app.js: a mesma cor do dia, de 3 a 12 de novembro")
    await pg.evaluate("localStorage.setItem('inv:accent', JSON.stringify('azul')); localStorage.setItem('inv:accentDaily', 'false')")
    await pg.reload()
    r.eq(await pg.evaluate("document.documentElement.dataset.accent"), "azul", "e, desligada, a cor escolhida")
    await ctx.close()

    # cada cor, clara e escura, no Início
    for scheme in ("light", "dark"):
        ctx, pg = await r.page(b, "cel", scheme, accent=None)
        await r.open(pg, "#/", ".tag")
        for a in accents:
            await pg.evaluate(f"localStorage.setItem('inv:accent', JSON.stringify('{a}')); localStorage.setItem('inv:accentDaily', 'false')")
            await pg.reload()
            await pg.wait_for_selector(".tag")
            await pg.wait_for_timeout(200)
            await r.shot(pg, f"cor-{a}-{scheme}")
        await ctx.close()

    # -- Opções: zonas e categorias
    ctx, pg = await r.page(b, "cel", "dark", accent="rosa")
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    await pg.click('label.switch:has([data-input="zones-on"])')
    await pg.locator(".toast", has_text="Zonas ligadas").wait_for(timeout=5000)
    r.check(r.data()["settings"]["zones"] is True, "Usar zonas fica gravado")
    await pg.click('label.switch:has([data-input="zones-on"])')
    await pg.locator(".toast", has_text="Zonas desligadas").wait_for(timeout=5000)
    r.check(r.data()["settings"]["zones"] is False and any(i.get("zone") for i in r.data()["items"]), "desligar não apaga as zonas")

    r.eq((await pg.text_content("#p-cats .opts li .ot b")).strip(), "13 categorias", "13 categorias de início")
    r.eq(await pg.locator('#p-cats [data-act="cat-del"][data-cat="outros"]').count(), 0, "Outros não se exclui")
    await pg.click('[data-act="cat-new"]')
    await pg.wait_for_selector("#cn-name")
    await pg.click("dialog [data-ok]")
    r.check(await pg.is_visible("dialog [data-err]"), "sem nome: avisa")
    await pg.fill("#cn-name", "Ferramentas")
    await pg.click("dialog [data-ok]")
    await pg.locator(".toast", has_text="Ferramentas").wait_for(timeout=5000)
    cat = next((c for c in r.data()["cats"] if c["name"] == "Ferramentas"), None)
    r.check(cat is not None, f"categoria nova gravada ({cat})")
    r.eq((await pg.text_content("#p-cats .opts li .ot b")).strip(), "14 categorias", "e conta na lista")
    await pg.click('[data-act="cat-new"]')
    await pg.fill("#cn-name", "móveis")
    await pg.click("dialog [data-ok]")
    await pg.wait_for_selector("dialog [data-err]:not([hidden])", timeout=4000)
    r.check("Já existe" in await pg.text_content("dialog [data-err]"), "nome repetido (sem ligar para acento): avisa")
    await pg.click("dialog [data-x]")
    await pg.click(f'[data-act="cat-edit"][data-cat="{cat["id"]}"]')
    await pg.fill("#cn-name", "Ferramentas e jardim")
    await pg.click("dialog [data-ok]")
    await pg.wait_for_timeout(600)
    r.eq(next(c["name"] for c in r.data()["cats"] if c["id"] == cat["id"]), "Ferramentas e jardim", "renomear")
    furadeira = r.api("POST", "api/items", {"name": "Furadeira", "room": "lavanderia", "cat": cat["id"], "value": 300})["item"]
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    await pg.click(f'[data-act="cat-del"][data-cat="{cat["id"]}"]')
    await pg.wait_for_selector('[data-r="1"]')
    r.check("1 item vai para Outros" in await pg.text_content("dialog[open]:last-of-type"), "excluir avisa para onde vão os itens")
    await r.shot(pg, "categoria-excluir")
    await pg.click('[data-r="1"]')
    await pg.locator(".toast", has_text="excluída").wait_for(timeout=5000)
    r.check(all(c["id"] != cat["id"] for c in r.data()["cats"]), "categoria excluída")
    r.eq(next(i for i in r.data()["items"] if i["id"] == furadeira["id"])["cat"], "outros", "o item foi para Outros")
    # a categoria renomeada aparece no cadastro e na busca
    await pg.click('[data-act="cat-edit"][data-cat="moveis"]')
    await pg.fill("#cn-name", "Mobília")
    await pg.click("dialog [data-ok]")
    await pg.wait_for_timeout(600)
    await r.open(pg, "#/buscar", ".sbar")
    r.check("Mobília" in await pg.evaluate("[...document.querySelectorAll('[data-input=search-cat] option')].map(o => o.textContent)"), "o nome novo aparece na busca")
    await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
    r.check("Mobília" in await pg.text_content("dialog.sheet .props"), "e na ficha do item")
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    await r.shot(pg, "opcoes", full_page=True)
    await ctx.close()
    await b.close()
    ha.stop()


main("ajustes", body)
