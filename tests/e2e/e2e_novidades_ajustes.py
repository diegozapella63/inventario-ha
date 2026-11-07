"""Ajustes das novidades (Mais > Configurações > Opções): Usar novidades, Conferir sozinho, Avisar (os celulares do Home
Assistant) e Testar o aviso; desligadas, somem do menu Mais e da ficha; IA desligada, o painel some; o link do aviso
(/app/<app>/novidades) abre o app direto em Novidades, pela mensagem do painel do Home Assistant."""
from e2e_lib import OVERFLOW, FakeHA, main

PHONE = "mobile_app_celular_da_ana"
OPTS = "[...document.querySelectorAll('[data-input=\"news-notify\"] option')].map(o => o.textContent)"
# o painel do app no Home Assistant (/app/<app>/novidades): a tela pede as propriedades e recebe o resto do endereço
HA_PANEL = """<!doctype html><body style="margin:0"><iframe id="ha" src="%s" style="border:0;width:100vw;height:100vh"></iframe><script>
let path = "/novidades";
window.send = (p) => { if (p !== undefined) path = p; document.getElementById("ha").contentWindow.postMessage(
  {type: "home-assistant/properties", narrow: true, route: {prefix: "/app/local_inventario", path}}, "*"); };
addEventListener("message", (e) => { if (e.data && e.data.type === "home-assistant/subscribe-properties") { window.subscribed = true; send(); } });
</script></body>"""


async def body(r, p):
    ha = FakeHA()
    r.start(search=False, ha=ha)
    b = await r.browser(p)
    for size, scheme, accent in (("cel", "dark", "laranja"), ("cel", "light", "azul"), ("pc", "light", "verde")):
        ctx, pg = await r.page(b, size, scheme, accent=accent)
        await r.open(pg, "#/config/opcoes", "#p-news-opts")
        await pg.wait_for_function(f"{OPTS}.length > 2", timeout=8000)
        if size == "cel" and scheme == "dark":
            r.eq((await pg.text_content("#p-news-opts h2")).strip(), "Novidades", "o painel Novidades em Opções")
            r.check(await pg.is_checked('[data-input="news-on"]'), "ligadas de início")
            r.eq(await pg.input_value('[data-input="news-every"]'), "0", "Conferir sozinho: Não, de início")
            r.eq(await pg.evaluate(OPTS), ["Não avisar", "Notificação do Home Assistant", "Celular da Ana", "Tablet da Sala"],
                 "Avisar: nada, a notificação do Home Assistant ou um dos celulares")
            r.eq(await pg.locator('[data-act="news-notify-test"]').count(), 0, "sem aviso escolhido, sem Testar")
        sz = await pg.evaluate("[...document.querySelectorAll('#p-news-opts .oa > .select')].map(e => { const b = e.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height), Math.round(b.right)]; })")
        r.check(len({x[0] for x in sz}) == 1 and len({x[2] for x in sz}) == 1 and all(x[1] == 44 for x in sz),
                f"{size} {scheme}: as seleções do mesmo tamanho, alinhadas pela direita ({sz})")
        r.check(await pg.evaluate(OVERFLOW), f"{size} {scheme}: sem rolagem para o lado")
        await r.shot(pg, f"opcoes-{size}-{scheme}", full_page=True)
        await ctx.close()

    # escolher: grava na hora
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")
    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    await pg.wait_for_function(f"{OPTS}.length > 2", timeout=8000)
    await pg.select_option('[data-input="news-every"]', "7")
    await pg.locator(".toast", has_text="Conferir sozinho: toda semana").wait_for(timeout=5000)
    r.eq(r.data()["settings"]["news_every"], 7, "Toda semana fica gravado")
    await pg.select_option('[data-input="news-notify"]', PHONE)
    await pg.locator(".toast", has_text="Aviso das novidades ligado").wait_for(timeout=5000)
    r.eq(r.data()["settings"]["news_notify"], PHONE, "o celular fica gravado")
    test = pg.locator('[data-act="news-notify-test"]')
    await test.wait_for(timeout=4000)
    n = len(ha.calls("POST", "/core/api/services/notify/"))
    await test.click()
    await pg.locator(".toast", has_text="Aviso enviado").wait_for(timeout=8000)
    c = ha.calls("POST", "/core/api/services/notify/")
    r.eq(len(c), n + 1, "Testar manda um aviso")
    r.eq(c[-1]["path"], f"/core/api/services/notify/{PHONE}", "para o celular escolhido")
    r.eq(c[-1]["body"]["message"], "Novidades em 2 itens. Toque para abrir.", "com o texto do aviso")
    w = await pg.evaluate("[...document.querySelectorAll('#p-news-opts .oa > .select, #p-news-opts .oa > .btn')].map(e => Math.round(e.getBoundingClientRect().width))")
    r.check(len(set(w)) == 1, f"Testar com a largura das seleções ({w})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "escolhido", full_page=True)
    await pg.reload()
    await pg.wait_for_selector("#p-news-opts", timeout=8000)
    r.eq(await pg.input_value('[data-input="news-every"]'), "7", "ao abrir de novo, continua Toda semana")

    # desligar: somem do menu Mais, do endereço e da ficha
    await pg.click('label.switch:has([data-input="news-on"])')
    await pg.locator(".toast", has_text="Novidades desligadas").wait_for(timeout=5000)
    r.check(r.data()["settings"]["news"] is False, "desligadas fica gravado")
    r.eq(await pg.locator('#p-news-opts select, [data-act="news-notify-test"]').count(), 0, "desligadas: sem Conferir sozinho nem Avisar")
    await r.shot(pg, "desligadas", full_page=True)
    await r.open(pg, "#/mais", ".menu-list")
    r.check("Novidades" not in await pg.evaluate("[...document.querySelectorAll('.menu-row b')].map(b => b.textContent)"), "o menu Mais fica sem Novidades")
    await r.open(pg, "#/novidades", ".menu-list")
    r.check(pg.url.endswith("#/mais"), "o endereço de Novidades abre o menu Mais")
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    r.eq(await pg.locator('dialog.sheet .inews, dialog.sheet [data-act="item-news"]').count(), 0, "a ficha fica sem Novidades")
    r.api("PUT", "api/settings", {"news": True})
    await ctx.close()

    # IA desligada: o painel some
    r.api("PUT", "api/settings", {"ai": False})
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/config/opcoes", "#p-zones")
    r.eq(await pg.locator("#p-news-opts").count(), 0, "IA desligada: sem o painel Novidades")
    r.api("PUT", "api/settings", {"ai": True})
    await ctx.close()

    # o aviso abre o app em Novidades: o painel do Home Assistant manda o resto do endereço (/novidades)
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")
    await pg.set_content(HA_PANEL % r.base)
    await pg.wait_for_function("window.subscribed === true", timeout=15000)
    r.check(True, "a tela pede as propriedades ao painel do Home Assistant")
    app = next(f for f in pg.frames if f.url.startswith(r.base))
    await app.wait_for_selector("#p-news", timeout=15000)
    r.check(app.url.endswith("#/novidades"), "o link do aviso abre direto em Novidades")
    await r.shot(pg, "aviso-abre")
    await app.evaluate("location.hash = '#/'")
    await app.wait_for_selector(".tag", timeout=8000)
    await pg.evaluate("send()")  # a mesma mensagem volta quando a largura muda: não puxa de volta
    await pg.wait_for_timeout(600)
    r.check(app.url.endswith("#/"), "a mesma mensagem de novo não tira a pessoa de onde está")
    await pg.evaluate("send('/'); send('/novidades')")  # outro aviso tocado com o app aberto
    await app.wait_for_selector("#p-news", timeout=8000)
    r.check(app.url.endswith("#/novidades"), "outro aviso com o app aberto: vai para Novidades")
    await ctx.close()
    await b.close()
    ha.stop()


main("novidades_ajustes", body)
