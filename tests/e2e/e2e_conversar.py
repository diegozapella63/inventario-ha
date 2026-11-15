"""Conversar com a IA: o botão ao lado do microfone, ideias de pergunta pela tela, enviar com Enter, a resposta formatada,
a conversa que continua, Nova conversa, da ficha do item, erro e Tentar de novo, ditar a pergunta e a IA desligada."""
import json

from e2e_lib import OVERFLOW, FakeHA, main

MSGS = "[...document.querySelectorAll('dialog.chat .msg:not(.typing)')].map(m => [m.classList.contains('me') ? 'eu' : 'ia', m.textContent.trim()])"


async def body(r, p):
    ha = FakeHA()
    r.start(search=False, mock_ai=False, ha=ha)
    asked = []

    def reply(kind, payload):
        asked.append(payload.get("instructions", ""))
        return "A sala vale **R$ 7.630**.\n- Sofá: R$ 1.800\n- TV: R$ 2.300\nMais em https://exemplo.com/dicas."
    ha.ai_reply = reply
    b = await r.browser(p, mic=True)
    ctx, pg = await r.page(b, "cel", "dark", accent="lilas", perms=["microphone"])
    await r.open(pg, "#/c/sala", ".rhead")
    pos = await pg.evaluate("[document.querySelector('.chat-top').getBoundingClientRect().right, document.querySelector('.mic-top').getBoundingClientRect().left]")
    r.check(pos[0] <= pos[1], "o botão Conversar fica ao lado do microfone")
    r.eq(await pg.get_attribute(".chat-top", "aria-label"), "Conversar com a IA", "com rótulo")
    await pg.click(".chat-top")
    await pg.wait_for_selector("dialog.chat .chat-ideas")
    r.eq((await pg.text_content(".chat-ctx")).strip(), "Sobre Sala de estar", "diz sobre o que é a conversa")
    ideas = await pg.evaluate("[...document.querySelectorAll('.chat-ideas .chip')].map(c => c.textContent)")
    r.check("Qual o item mais caro daqui?" in ideas, f"ideias de pergunta pelo cômodo ({ideas})")
    r.check(await pg.is_hidden("[data-new]"), "sem conversa, sem Nova conversa")
    await r.shot(pg, "vazio")

    # uma ideia vira pergunta
    await pg.locator(".chat-ideas .chip", has_text="Qual o item mais caro daqui?").click()
    await pg.wait_for_selector("dialog.chat .msg.ai:not(.typing)", timeout=15000)
    msgs = await pg.evaluate(MSGS)
    r.eq(msgs[0], ["eu", "Qual o item mais caro daqui?"], "a pergunta aparece do lado de quem pergunta")
    r.check(msgs[1][0] == "ia" and "A sala vale R$ 7.630" in msgs[1][1], "e a resposta da IA")
    r.eq(await pg.evaluate("document.querySelector('dialog.chat .msg.ai b')?.textContent"), "R$ 7.630", "negrito")
    r.eq(await pg.locator("dialog.chat .msg.ai .li").count(), 2, "lista")
    link = pg.locator("dialog.chat .msg.ai a")
    r.check(await link.get_attribute("href") == "https://exemplo.com/dicas" and await link.get_attribute("target") == "_blank", "link abre fora do app")
    r.check("Cômodo na tela: SAL Sala de estar" in asked[-1], "a IA recebe os itens do cômodo da tela")
    r.check("SAL-001 Sofá de 3 lugares cinza-azulado" in asked[-1], "com cada item e valor")

    # Enter envia; Shift+Enter quebra a linha
    await pg.fill("dialog.chat textarea", "e o mais barato?")
    await pg.press("dialog.chat textarea", "Shift+Enter")
    r.eq(await pg.input_value("dialog.chat textarea"), "e o mais barato?\n", "Shift+Enter quebra a linha")
    await pg.press("dialog.chat textarea", "Enter")
    await pg.wait_for_function("document.querySelectorAll('dialog.chat .msg.ai:not(.typing)').length === 2", timeout=15000)
    r.check("Pessoa: Qual o item mais caro daqui?" in asked[-1] and "Pessoa: e o mais barato?" in asked[-1], "a conversa anterior vai junto")
    r.eq(await pg.input_value("dialog.chat textarea"), "", "o campo limpa depois de enviar")
    r.check(await pg.is_visible("[data-new]"), "Nova conversa aparece")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "conversa")

    # 1.69.0: o botão redondo da direita: vazio, o microfone; com texto, o Enviar
    r.eq(await pg.locator("dialog.chat .chat-in [data-mic]").count(), 1, "caixa vazia: o microfone")
    r.eq(await pg.locator('dialog.chat .chat-in button[type="submit"]').count(), 0, "sem o Enviar ao lado")
    await pg.fill("dialog.chat textarea", "oi")
    r.eq(await pg.locator('dialog.chat .chat-in button[type="submit"]').count(), 1, "escrevendo: o Enviar no lugar do microfone")
    await pg.fill("dialog.chat textarea", "")
    r.eq(await pg.locator("dialog.chat .chat-in [data-mic]").count(), 1, "apagou: o microfone de novo")

    # 1.69.0: as perguntas prontas a qualquer momento (✨), editáveis e guardadas no aparelho
    q = pg.locator("dialog.chat [data-quick]")
    r.check(await q.is_visible(), "com a conversa andando, o ✨ ao lado da caixa")
    await q.click()
    r.eq(await q.get_attribute("aria-expanded"), "true", "o ✨ abre as perguntas")
    ideas2 = await pg.evaluate("[...document.querySelectorAll('dialog.chat .chat-quick .chip')].map(c => c.textContent)")
    r.eq(ideas2, ideas, "as mesmas da conversa vazia")
    await pg.click("dialog.chat .chat-quick [data-ed-open]")
    await pg.click("dialog.chat [data-ed-rm] >> nth=0")
    await pg.fill("dialog.chat [data-ed-in]", "Quanto vale a cozinha?")
    await pg.click("dialog.chat [data-ed-add]")
    r.eq(await pg.input_value("dialog.chat [data-ed-in]"), "", "Adicionar limpa a caixa")
    w = await pg.evaluate("[...document.querySelectorAll('dialog.chat .chat-ed-acts .btn')].map(b => Math.round(b.getBoundingClientRect().width))")
    r.check(len(set(w)) == 1, f"Padrão e Pronto do mesmo tamanho ({w})")
    r.check(await pg.evaluate(OVERFLOW), "editar: sem rolagem para o lado")
    await r.shot(pg, "perguntas")
    await pg.click("dialog.chat [data-ed-ok]")
    novas = ideas[1:] + ["Quanto vale a cozinha?"]
    r.eq(await pg.evaluate("[...document.querySelectorAll('dialog.chat .chat-quick .chip')].map(c => c.textContent)"), novas, "Pronto: as perguntas novas")
    r.eq(await pg.evaluate("JSON.parse(localStorage.getItem('inv.perguntas'))"), novas, "guardadas no aparelho")
    await q.click()
    r.eq(await pg.locator("dialog.chat .chat-quick").count(), 0, "o mesmo botão fecha")

    # 1.69.0: o clipe: Tirar foto, Escolher fotos e Escolher arquivo; a foto vai junto com a pergunta
    await pg.click("dialog.chat [data-clip]")
    ops = await pg.evaluate("[...document.querySelectorAll('dialog.chat .chat-op')].map(b => b.textContent.trim())")
    r.eq(ops, ["Tirar foto", "Escolher fotos", "Escolher arquivo"], "o menu do clipe")
    r.eq(await pg.locator("dialog.chat .chat-op svg").count(), 3, "cada opção com o seu ícone")
    await r.shot(pg, "clipe")
    async with pg.expect_file_chooser() as fc:
        await pg.click('dialog.chat [data-op="fotos"]')
    chooser = await fc.value
    r.check(chooser.is_multiple(), "a galeria deixa escolher várias")
    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201" "5a8a3b4b0000000049454e44ae426082")
    await chooser.set_files(files=[{"name": "etiqueta.png", "mimeType": "image/png", "buffer": png}])
    await pg.wait_for_selector("dialog.chat .chat-prev")
    r.eq((await pg.text_content("dialog.chat .chat-prev > span:not(.chat-pdf)")).strip(), "etiqueta.png", "a foto escolhida, antes de mandar")
    r.eq(await pg.locator('dialog.chat .chat-in button[type="submit"]').count(), 1, "com arquivo: o Enviar")
    await pg.fill("dialog.chat textarea", "o que diz?")
    ha.ai_reply = lambda kind, payload: (asked.append(payload.get("instructions", "")), f"Diz 220 V. ({len(payload.get('attachments') or [])} arquivo)")[1]
    await pg.press("dialog.chat textarea", "Enter")
    await pg.wait_for_function("document.querySelectorAll('dialog.chat .msg.ai:not(.typing)').length === 3", timeout=15000)
    r.eq(await pg.evaluate("[...document.querySelectorAll('dialog.chat .msg.me .msg-arq')].map(x => x.textContent.trim())"), ["etiqueta.png"], "o nome do arquivo na pergunta")
    r.check("Diz 220 V. (1 arquivo)" in (await pg.evaluate(MSGS))[-1][1], "a foto foi junto para a IA")
    r.check("Pessoa: [mandou etiqueta.png] o que diz?" in asked[-1], "a IA sabe que a pessoa mandou um arquivo")
    r.eq(await pg.locator("dialog.chat .chat-prev").count(), 0, "depois de mandar, a caixa limpa")
    ha.ai_reply = reply

    # fechar e abrir de novo: a conversa continua; Nova conversa limpa
    await pg.click("dialog.chat [data-x]")
    await pg.wait_for_timeout(300)
    await pg.click(".chat-top")
    await pg.wait_for_selector("dialog.chat .msg")
    r.eq(len(await pg.evaluate(MSGS)), 6, "abrir de novo: a conversa continua")
    await pg.click("[data-new]")
    r.eq(await pg.locator("dialog.chat .msg").count(), 0, "Nova conversa limpa")
    await pg.click("dialog.chat [data-x]")
    await pg.wait_for_timeout(300)

    # da ficha do item: sobre o item
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="chat"]')
    await pg.wait_for_selector("dialog.chat .chat-ideas")
    r.eq((await pg.text_content(".chat-ctx")).strip(), "Sobre Smart TV 55 polegadas", "da ficha, a conversa é sobre o item")
    r.eq(await pg.evaluate("[...document.querySelectorAll('dialog.chat .chat-ideas .chip')].map(c => c.textContent)"), novas, "editadas, valem em todas as telas")
    await pg.fill("dialog.chat textarea", "vale pôr no seguro?")
    await pg.click('dialog.chat button[type="submit"]')
    await pg.wait_for_selector("dialog.chat .msg.ai:not(.typing)", timeout=15000)
    r.check("Item na tela: SAL-007 Smart TV 55 polegadas" in asked[-1], "a IA recebe o item")
    await r.shot(pg, "item")

    # erro e Tentar de novo
    ha.ai_error = (429, "RESOURCE_EXHAUSTED: quota")
    await pg.fill("dialog.chat textarea", "e a garantia?")
    await pg.press("dialog.chat textarea", "Enter")
    await pg.wait_for_selector("dialog.chat .msg.err", timeout=15000)
    r.check("cota da IA acabou" in await pg.text_content("dialog.chat .msg.err"), "erro em português, na conversa")
    await r.shot(pg, "erro")
    ha.ai_error = None
    await pg.click("[data-retry]")
    await pg.wait_for_function("!document.querySelector('dialog.chat .msg.err') && document.querySelectorAll('dialog.chat .msg.ai:not(.typing)').length === 2", timeout=15000)
    r.check(True, "Tentar de novo pergunta outra vez")
    await pg.click("dialog.chat [data-x]")
    await pg.wait_for_timeout(300)
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)

    # ditar a pergunta (microfone de mentira do Chromium)
    ha.stt_text = "quantos itens tem a cozinha"
    await r.open(pg, "#/", ".tag")
    await pg.click(".chat-top")
    await pg.wait_for_selector("dialog.chat .chat-f")
    await pg.wait_for_timeout(350)  # a janela entra subindo
    r.eq(await pg.locator(".chat-ctx").count(), 0, "1.60.0: no Agora, sem o óbvio (Sobre o inventário)")
    g = await pg.evaluate("(() => { const d = document.querySelector('dialog.chat').getBoundingClientRect(); return [Math.round(d.bottom), innerHeight, Math.round(d.top), Math.round(d.width), innerWidth, getComputedStyle(document.querySelector('dialog.chat')).borderTopLeftRadius]; })()")
    r.check(abs(g[0] - g[1]) <= 1 and g[2] > g[1] * 0.15 and g[3] == g[4] and g[5] != "0px", f"1.60.0: no celular, uma janela que sobe de baixo, sem a tela toda, como nos outros apps ({g})")
    await pg.click("[data-new]") if await pg.is_visible("[data-new]") else None
    await pg.click("dialog.chat [data-mic]")
    await pg.wait_for_selector("dialog.chat [data-mic].on", timeout=8000)
    await pg.wait_for_timeout(900)
    await pg.click("dialog.chat [data-mic]")
    await pg.wait_for_function("[...document.querySelectorAll('dialog.chat .msg.me')].some(m => m.textContent.includes('quantos itens tem a cozinha'))", timeout=15000)
    r.check(True, "ditar: o que foi falado vira a pergunta")
    await ctx.close()

    # computador: no meio da tela
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/buscar?q=geladeira", ".sbar")
    await pg.click(".chat-top")
    await pg.wait_for_selector("dialog.chat .chat-ideas")
    await pg.wait_for_timeout(300)  # a janela entra deslizando
    g = await pg.evaluate("(() => { const d = document.querySelector('dialog.chat').getBoundingClientRect(); return [Math.round(d.left + d.right), innerWidth, Math.round(d.width), Math.round(d.height), innerHeight]; })()")
    r.check(abs(g[0] - g[1]) <= 2 and g[2] <= 561 and g[3] < g[4] * 0.9, f"1.60.0: no computador, no meio da tela, como nos outros apps ({g})")
    r.eq((await pg.text_content(".chat-ctx")).strip(), "Sobre a busca “geladeira”", "da busca, a conversa é sobre a busca")
    try:
        await pg.wait_for_function("document.activeElement && document.activeElement.matches('dialog.chat textarea')", timeout=2000)
        focused = True
    except Exception:  # noqa: BLE001
        focused = False
    r.check(focused, "no computador, o cursor já está no campo")
    await r.shot(pg, "computador")
    await ctx.close()

    # IA desligada: sem o botão
    r.api("PUT", "api/settings", {"ai": False})
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.locator(".chat-top").count(), 0, "IA desligada: sem Conversar")
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    r.eq(await pg.locator('[data-act="chat"]').count(), 0, "nem na ficha")
    await ctx.close()
    await b.close()
    ha.stop()


main("conversar", body)
