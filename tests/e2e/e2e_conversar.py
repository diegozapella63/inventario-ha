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

    # fechar e abrir de novo: a conversa continua; Nova conversa limpa
    await pg.click("dialog.chat [data-x]")
    await pg.wait_for_timeout(300)
    await pg.click(".chat-top")
    await pg.wait_for_selector("dialog.chat .msg")
    r.eq(len(await pg.evaluate(MSGS)), 4, "abrir de novo: a conversa continua")
    await pg.click("[data-new]")
    r.eq(await pg.locator("dialog.chat .msg").count(), 0, "Nova conversa limpa")
    await pg.click("dialog.chat [data-x]")
    await pg.wait_for_timeout(300)

    # da ficha do item: sobre o item
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="chat"]')
    await pg.wait_for_selector("dialog.chat .chat-ideas")
    r.eq((await pg.text_content(".chat-ctx")).strip(), "Sobre Smart TV 55 polegadas", "da ficha, a conversa é sobre o item")
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
    await pg.click("[data-new]") if await pg.is_visible("[data-new]") else None
    await pg.click("dialog.chat [data-mic]")
    await pg.wait_for_selector("dialog.chat [data-mic].on", timeout=8000)
    await pg.wait_for_timeout(900)
    await pg.click("dialog.chat [data-mic]")
    await pg.wait_for_function("[...document.querySelectorAll('dialog.chat .msg.me')].some(m => m.textContent.includes('quantos itens tem a cozinha'))", timeout=15000)
    r.check(True, "ditar: o que foi falado vira a pergunta")
    await ctx.close()

    # computador: à direita, encostada na borda
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/buscar?q=geladeira", ".sbar")
    await pg.click(".chat-top")
    await pg.wait_for_selector("dialog.chat .chat-ideas")
    await pg.wait_for_timeout(300)  # a janela entra deslizando
    g = await pg.evaluate("(() => { const d = document.querySelector('dialog.chat').getBoundingClientRect(); return [Math.round(d.right), innerWidth, Math.round(d.width)]; })()")
    r.check(abs(g[0] - g[1]) <= 1 and g[2] <= 481, f"no computador, à direita ({g})")
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
