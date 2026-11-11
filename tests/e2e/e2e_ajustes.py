"""Mais > Configurações > Integrações (com um Home Assistant de mentira), Aparência (o tema no aparelho, a cor do app para a casa toda,
as 12 cores da família e a Cor do dia) e Opções (zonas e categorias)."""
import datetime
import json
import time

from e2e_lib import OVERFLOW, AppServer, FakeHA, main

PALETA = ["vermelho", "coral", "laranja", "ouro", "verde", "menta", "turquesa", "azul", "indigo", "lilas", "rosa", "grafite"]
DIAS = ["ouro", "verde", "menta", "turquesa", "azul", "indigo", "lilas", "rosa", "vermelho", "coral", "laranja"]  # de 3 a 13 de novembro de 2026
ACC = "document.documentElement.dataset.accent || 'ouro'"  # o Ouro é o padrão (sem data-accent)
CHECKED = "document.querySelector('[data-input=accent]:checked').value"

SENSOR = "sensor.inventaria_ia_hoje"
RECALL = "binary_sensor.inventaria_recall"


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
    await r.open(pg, "#/config/integracoes", ".more-tabs")
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
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    await pg.wait_for_selector(".uso-tiles", timeout=10000)
    hoje = await pg.text_content(".uso-tiles .uso-tile .v")
    r.eq(hoje.strip(), "1", "Uso da IA: 1 chamada hoje")
    await pg.click(".uso-ult summary")
    ult = await pg.text_content(".uso-ult li")
    r.check("Digitalizar com IA" in ult and "Google AI Task" in ult, f"última chamada, com a IA usada ({' '.join(ult.split())[:60]})")
    r.check("Google Cloud Console" in await pg.text_content("#p-usage .help"), "link do consumo exato do Gemini")
    await pg.locator(".uso-bar").first.click()
    cap = await pg.text_content(".uso-cap")
    r.check("0 chamadas" in cap, f"tocar num dia mostra o dia ({cap.strip()})")
    await pg.evaluate("document.querySelector('#p-usage').scrollIntoView()")
    await r.shot(pg, "uso-ia")

    # sensores no Home Assistant
    r.check(ha.state(SENSOR) is None, "sem o sensor até ligar")
    await pg.click('label.switch:has([data-input="sensors-on"])')
    await pg.locator(".toast", has_text="Sensores criados").wait_for(timeout=8000)
    for _ in range(30):
        if ha.state(SENSOR):
            break
        time.sleep(0.2)
    s = ha.state(SENSOR)
    r.check(s is not None and str(s["state"]) == "1" and s["attributes"]["imagens"] == 1, f"sensor criado com as chamadas de hoje ({s and s['state']})")
    # 1.55.0: o do recall, com as Novidades ligadas
    for _ in range(30):
        if ha.state(RECALL):
            break
        time.sleep(0.2)
    rc = ha.state(RECALL)
    r.check(rc is not None and rc["state"] == "off" and rc["attributes"]["quantidade"] == 0, f"binary_sensor.inventaria_recall criado, desligado sem recall ({rc and rc['state']})")
    r.check("binary_sensor.inventaria_recall" in await pg.text_content("#p-sensors"), "o cartão diz o sensor do recall")
    await pg.click('label.switch:has([data-input="sensors-on"])')
    await pg.locator(".toast", has_text="Sensores desligados").wait_for(timeout=8000)
    for _ in range(30):
        if ha.state(SENSOR) is None:
            break
        time.sleep(0.2)
    r.check(ha.state(SENSOR) is None and ha.state(RECALL) is None, "desligar tira os sensores do Home Assistant")

    # Usar IA desligada: some o que usa IA, e o Falar junto
    await pg.click('label.switch:has([data-input="ai-on"])')
    await pg.locator(".toast", has_text="IA desligada").wait_for(timeout=8000)
    r.check(r.data()["settings"]["ai"] is False, "Usar IA desligada fica gravada")
    for sel, label in (("[data-input=ai-entity]", "IA para ler fotos"), ("#p-usage", "Uso da IA"), ("#p-sensors", "Sensores"), ('[data-act="catalog"]', "Catalogar no alto")):
        r.eq(await pg.locator(sel).count(), 0, f"IA desligada: sem {label}")
    r.eq(await pg.locator("#p-voice").count(), 0, "IA desligada: sem o Falar")
    r.check("Os botões de IA e o Falar ficam escondidos." in await pg.text_content("#p-ai"), "e diz que o Falar some junto")
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
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    await pg.click('[data-act="voice-refresh"]')
    await pg.wait_for_function("(e => e && e.textContent.includes('Sem fala para texto'))(document.querySelector('[data-slot=voice-panel] .status'))", timeout=10000)
    r.check("Assistentes de voz" in await pg.text_content('[data-slot="voice-panel"]'), "sem fala para texto: diz onde configurar")
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.locator(".mic-top").count(), 0, "e o microfone sai do alto")
    await ctx.close()

    # -- Aparência (1.42.0, o padrão da família): o tema vale neste aparelho; a cor do app, para a casa toda (gravada no
    # servidor); a paleta da família, 12 cores; a Cor do dia vem ligada e é a mesma em todos os apps (as 11 sem o Grafite, pelo
    # número do dia). Numa casa nova (outro servidor), para começar sem cor escolhida.
    principal = (r.app, r.base)
    casas = []

    def casa_nova():
        c = AppServer(mock_ai=True)
        casas.append(c)
        r.app, r.base = c, c.base
        return c

    try:
        casa_nova()
        ctx, pg = await r.page(b, "cel", "light", accent=None)
        await ctx.clock.install(time=datetime.datetime(2026, 11, 3, 23, 59, 30))  # hora local
        await r.open(pg, "#/config/aparencia", ".more-tabs")
        r.eq(await pg.evaluate("[new Date().getDate(), new Date().getHours()]"), [3, 23], "o navegador está em 3 de novembro, 23h59")
        daily = pg.get_by_role("switch", name="Cor do dia")
        r.check(await daily.is_checked(), "Cor do dia vem ligada")
        r.eq(await pg.evaluate("[...document.querySelectorAll('#p-look .lead, #p-accent .lead')].map(e => e.textContent)"),
             ["Cada aparelho guarda a sua escolha.", "Vale para todos os aparelhos."], "o tema é do aparelho; a cor, da casa")
        r.eq(await pg.evaluate("[...document.querySelectorAll('#p-accent .opts .ot > *')].map(e => e.textContent)"), ["Cor do dia", "Muda a cor do app todo dia."], "Cor do dia, com a dica curta, junto da cor do app")
        r.eq(await pg.evaluate(ACC), "ouro", "3 de novembro de 2026: Ouro")
        r.eq(await pg.evaluate(CHECKED), "ouro", "a cor do dia é a marcada")
        r.eq(r.data()["settings"]["accent"], None, "ninguém escolheu: a casa continua sem cor gravada")
        box = await pg.evaluate("(() => { const s = document.querySelector('#p-accent .switch').getBoundingClientRect(), z = document.querySelector('#p-accent .swatches').getBoundingClientRect(); return [Math.round(innerWidth - s.right), s.bottom <= z.top]; })()")
        r.check(box[1] and box[0] <= 24, f"a chave fica à direita, acima das cores ({box})")
        r.check(await pg.evaluate(OVERFLOW), "as 12 cores cabem na largura")
        await r.shot(pg, "cor-do-dia", full_page=True)
        await pg.set_viewport_size({"width": 320, "height": 700})
        box = await pg.evaluate("(() => { const s = document.querySelector('#p-accent .switch').getBoundingClientRect(), t = document.querySelector('#daily-h').getBoundingClientRect(); return [Math.round(innerWidth - s.right), s.top < t.bottom]; })()")
        r.check(box[1] and box[0] <= 24, f"no celular de 320 px, a chave continua à direita, na linha do nome ({box})")
        cut = await pg.evaluate("[...document.querySelectorAll('.sw span')].filter(e => e.scrollWidth > e.parentElement.clientWidth + 1).map(e => e.textContent)")
        r.check(not cut and await pg.evaluate(OVERFLOW), f"em 320 px, os nomes das cores inteiros ({cut})")
        await r.shot(pg, "cor-do-dia-320", full_page=True)
        await pg.set_viewport_size({"width": 384, "height": 854})
        await ctx.clock.fast_forward("02:00")  # passa da meia-noite com o app aberto
        await pg.wait_for_function("document.documentElement.dataset.accent === 'verde'", timeout=5000)
        r.eq([await pg.evaluate(ACC), await pg.evaluate(CHECKED)], ["verde", "verde"], "passou da meia-noite: a cor do dia seguinte, sem recarregar")
        # 1.45.1: Sistema no lugar de Automático, igual em todos os apps da família
        r.eq(await pg.locator('[data-act="theme"]').all_inner_texts(), ["Sistema", "Claro", "Escuro"], "o Tema: Sistema, Claro e Escuro")
        await pg.click('[data-act="theme"][data-theme="dark"]')
        r.eq(await pg.evaluate("document.documentElement.dataset.theme"), "dark", "tema Escuro")
        r.eq(await pg.get_attribute('[data-act="theme"][data-theme="dark"]', "aria-pressed"), "true", "o botão fica marcado")
        r.eq(await pg.evaluate("[...document.querySelectorAll('.sw')].map(s => s.dataset.accent)"), PALETA, "as 12 cores da família, na ordem")
        r.eq(await pg.evaluate("[...document.querySelectorAll('.sw span')].map(s => s.textContent)"),
             ["Vermelho", "Coral", "Laranja", "Ouro", "Verde", "Menta", "Turquesa", "Azul", "Índigo", "Lilás", "Rosa", "Grafite"], "com os nomes da família")
        fills = await pg.evaluate("[...document.querySelectorAll('.sw')].map(s => getComputedStyle(s).getPropertyValue('--a').trim().toLowerCase())")
        r.eq(fills, ["#ff5a4f", "#ff8a65", "#ffa23e", "#f2c14e", "#8bd45f", "#4ed3a6", "#3ccbda", "#62b5ff", "#8f9bff", "#b99bff", "#ff77a9", "#b5b9c2"], "e as cores da família")
        # escolher uma cor desliga a Cor do dia e vale para a casa toda
        await pg.click('.sw[data-accent="rosa"]')
        await pg.wait_for_timeout(300)
        r.eq(await pg.evaluate(ACC), "rosa", "cor Rosa")
        r.check(not await daily.is_checked(), "escolher uma cor desliga a Cor do dia")
        st = r.data()["settings"]
        r.eq([st["accent"], st["accent_daily"]], ["rosa", False], "e fica gravado para a casa toda")
        r.eq(await pg.evaluate("[localStorage.getItem('inv:accent'), localStorage.getItem('inv:accentDaily')]"), ['"rosa"', "false"], "com a cópia do aparelho, para pintar antes de carregar")
        await ctx.clock.fast_forward("24:00:00")
        await pg.evaluate("window.dispatchEvent(new Event('focus'))")
        r.eq(await pg.evaluate(ACC), "rosa", "desligada, a cor não muda no outro dia")
        # ligar de novo volta à cor do dia (5 de novembro: Menta); desligar volta à escolhida
        await daily.click()
        await pg.wait_for_timeout(300)
        r.eq([await pg.evaluate(ACC), await pg.evaluate(CHECKED)], ["menta", "menta"], "ligar de novo: a cor do dia, marcada")
        r.eq(r.data()["settings"]["accent_daily"], True, "a Cor do dia também vale para a casa")
        await daily.click()
        await pg.wait_for_timeout(300)
        r.eq([await pg.evaluate(ACC), await pg.evaluate(CHECKED)], ["rosa", "rosa"], "desligar: a cor escolhida antes")
        await pg.click('.sw[data-accent="indigo"]')
        await pg.wait_for_timeout(300)
        r.eq(await pg.evaluate(ACC), "indigo", "cor Índigo")
        await pg.reload()
        await pg.wait_for_selector(".more-tabs")
        r.eq(await pg.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.accent]"), ["dark", "indigo"], "tema e cor ficam depois de recarregar")
        r.check(not await daily.is_checked() and await pg.evaluate(CHECKED) == "indigo", "e a Cor do dia continua desligada")
        await r.shot(pg, "aparencia", full_page=True)
        await pg.click('[data-act="theme"][data-theme="auto"]')
        r.check(await pg.evaluate("!document.documentElement.dataset.theme"), "Sistema segue o celular")
        await ctx.close()
        # outro aparelho: a mesma cor (a da casa), com o tema dele
        ctx, pg = await r.page(b, "cel", "light", accent=None, init="try{localStorage.setItem('inv:theme', JSON.stringify('light'))}catch(e){}")
        await r.open(pg, "#/", ".tag")
        r.eq(await pg.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.accent]"), ["light", "indigo"], "outro aparelho: a cor da casa, com o tema dele")
        r.eq(await pg.evaluate("localStorage.getItem('inv:accent')"), '"indigo"', "e guarda a cópia da cor da casa")
        await ctx.close()

        # primeira vez numa casa sem cor: vale a escolhida neste aparelho, que passa para a casa; uma cor de antes da paleta
        # vira a mais próxima (Kraft: Coral)
        casa_nova()
        ctx, pg = await r.page(b, "cel", "dark", accent=None, init="try{if(!sessionStorage.getItem('x')){sessionStorage.setItem('x',1);localStorage.setItem('inv:accent', JSON.stringify('kraft'));localStorage.setItem('inv:accentDaily', 'false')}}catch(e){}")
        await r.open(pg, "#/", ".tag")
        await pg.wait_for_timeout(500)
        r.eq(await pg.evaluate(ACC), "coral", "o Kraft deste aparelho vira o Coral")
        st = r.data()["settings"]
        r.eq([st["accent"], st["accent_daily"]], ["coral", False], "e passa para a casa toda, na primeira vez")
        await ctx.close()
        # quem tinha escolhido uma cor antes da Cor do dia passa a ter a Cor do dia; depois da última cor, a primeira
        casa_nova()
        ctx, pg = await r.page(b, "cel", "dark", accent=None, init="try{if(!localStorage.getItem('inv:accent'))localStorage.setItem('inv:accent', JSON.stringify('coral'))}catch(e){}")
        await ctx.clock.install(time=datetime.datetime(2026, 11, 13, 23, 59, 0))
        await r.open(pg, "#/", ".tag")
        r.eq(await pg.evaluate(ACC), "laranja", "cor escolhida antes (Coral): vale a do dia (13 de novembro: Laranja)")
        r.eq(r.data()["settings"]["accent_daily"], True, "a casa fica com a Cor do dia")
        await ctx.clock.fast_forward("02:00")
        await pg.wait_for_function("document.documentElement.dataset.accent !== 'laranja'", timeout=5000)
        r.eq(await pg.evaluate(ACC), "ouro", "14 de novembro: depois do Laranja, o Ouro de novo (11 cores; o Grafite fica de fora)")
        await r.open(pg, "#/config/aparencia", ".more-tabs")
        r.check(await pg.get_by_role("switch", name="Cor do dia").is_checked() and await pg.evaluate(CHECKED) == "ouro", "na Aparência, ligada e com o Ouro marcado")
        await ctx.close()

        # o index.html pinta a cor do dia antes do app.js (a mesma conta, dias seguidos), e a cópia da cor da casa
        ctx, pg = await r.page(b, "cel", "light", accent=None)
        await pg.route("**/app.js*", lambda route: route.abort())
        got = []
        for d in range(12):
            await ctx.clock.set_fixed_time(datetime.datetime(2026, 11, 3 + d, 8, 0, 0))
            await pg.goto("about:blank")
            await pg.goto(r.base + "#/")
            got.append(await pg.evaluate(ACC))
        r.eq(got, DIAS + ["ouro"], "antes do app.js: a mesma cor do dia, de 3 a 14 de novembro")
        for guardada, vale in (("azul", "azul"), ("kraft", "coral"), ("amarelo", "ouro"), ("cinza", "grafite")):
            await pg.evaluate(f"localStorage.setItem('inv:accent', JSON.stringify('{guardada}')); localStorage.setItem('inv:accentDaily', 'false')")
            await pg.reload()
            r.eq(await pg.evaluate(ACC), vale, f"desligada, a cor guardada ({guardada}: {vale})")
        await ctx.close()

        # cada cor, clara e escura, no Início
        for scheme in ("light", "dark"):
            ctx, pg = await r.page(b, "cel", scheme, accent=None)
            for a in PALETA:
                r.api("PUT", "api/settings", {"accent": a, "accent_daily": False})
                await r.open(pg, "#/", ".tag")
                await pg.wait_for_timeout(200)
                await r.shot(pg, f"cor-{a}-{scheme}")
            r.eq(await pg.evaluate(ACC), "grafite", f"{scheme}: a cor da casa vale ao abrir")
            await ctx.close()
    finally:
        r.app, r.base = principal
        for c in casas:
            c.stop()

    # -- Opções: zonas; Categorias: tela própria, no menu Mais
    ctx, pg = await r.page(b, "cel", "dark", accent="rosa")
    await r.open(pg, "#/config/opcoes", ".more-tabs")
    r.eq(await pg.locator("#p-cats").count(), 0, "Opções sem as categorias")
    await pg.click('label.switch:has([data-input="zones-on"])')
    await pg.locator(".toast", has_text="Zonas ligadas").wait_for(timeout=5000)
    r.check(r.data()["settings"]["zones"] is True, "Usar zonas fica gravado")
    await pg.click('label.switch:has([data-input="zones-on"])')
    await pg.locator(".toast", has_text="Zonas desligadas").wait_for(timeout=5000)
    r.check(r.data()["settings"]["zones"] is False and any(i.get("zone") for i in r.data()["items"]), "desligar não apaga as zonas")

    await r.open(pg, "#/categorias", "#p-cats")
    r.eq((await pg.text_content(".page-title")).strip(), "Categorias", "Categorias numa tela própria")
    r.eq((await pg.text_content("#p-cats .opts li .ot b")).strip(), "15 categorias", "15 categorias de início")
    r.eq(await pg.locator('#p-cats [data-act="cat-del"][data-cat="outros"]').count(), 0, "Outros não se exclui")
    r.eq(await pg.locator('#p-cats [data-cat="eletronicos"]').count(), 0, "Eletrônicos (a das novidades) não se renomeia nem se exclui")
    r.check("novidades" not in await pg.locator("#p-cats li", has_text="Eletrônicos").first.text_content(), "sem explicar o porquê")
    r.check("todos os aparelhos" not in await pg.text_content("#p-cats"), "nem que vale para todos os aparelhos")
    await pg.click('[data-act="cat-new"]')
    await pg.wait_for_selector("#cn-name")
    await pg.click("dialog [data-ok]")
    r.check(await pg.is_visible("dialog [data-err]"), "sem nome: avisa")
    await pg.fill("#cn-name", "Ferramentas")
    await pg.click("dialog [data-ok]")
    await pg.locator(".toast", has_text="Ferramentas").wait_for(timeout=5000)
    cat = next((c for c in r.data()["cats"] if c["name"] == "Ferramentas"), None)
    r.check(cat is not None, f"categoria nova gravada ({cat})")
    r.eq((await pg.text_content("#p-cats .opts li .ot b")).strip(), "16 categorias", "e conta na lista")
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
    await r.open(pg, "#/categorias", "#p-cats")
    await pg.click(f'[data-act="cat-del"][data-cat="{cat["id"]}"]')
    await pg.wait_for_selector('[data-r="1"]')
    r.check("1 item vai para Outros" in await pg.text_content("dialog[open]:last-of-type"), "excluir avisa para onde vão os itens")
    await r.shot(pg, "categoria-excluir")
    await pg.click('[data-r="1"]')
    await pg.locator(".toast", has_text="apagada").wait_for(timeout=5000)
    r.check(all(c["id"] != cat["id"] for c in r.data()["cats"]), "categoria apagada")
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
    await r.open(pg, "#/config/opcoes", ".more-tabs")
    await r.shot(pg, "opcoes", full_page=True)
    await r.open(pg, "#/categorias", "#p-cats")
    await r.shot(pg, "categorias", full_page=True)
    await ctx.close()
    await b.close()
    ha.stop()


main("ajustes", body)
