"""Ajustes das novidades (Mais > Configurações > Opções), com o aviso no celular igual nos apps da família (1.43.0): Usar
novidades, Conferir sozinho com o Horário (sem AM/PM) e A cada lado a lado, Avisar no celular, Quem recebe (um botão por pessoa
da casa, do mesmo tamanho, nunca um aparelho) e Testar no meu celular (o de quem está na tela) na largura toda, embaixo; tudo
só com Conferir sozinho ligado; desligadas, somem do menu Mais e da ficha; IA desligada,
o painel some; o link do aviso (/app/<app>/novidades) abre o app direto em Novidades, pela mensagem do painel do Home Assistant."""
from e2e_lib import OVERFLOW, FakeHA, main

PHONE = "mobile_app_celular_da_ana"  # o celular ligado à Ana no Home Assistant de mentira
ANA = "person.ana"
PESSOAS = "[...document.querySelectorAll('.quem-p')].map(b => [b.querySelector('b').textContent, b.getAttribute('aria-pressed') === 'true', (b.querySelector('span') || {}).textContent || ''])"
GEO = """(() => { const r = (e) => { const b = e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), b.width, Math.round(b.height)]; };
  const li = document.querySelector('.aviso-quem');
  return { quando: [...document.querySelectorAll('.aviso-quando select')].map(r), quem: [...document.querySelectorAll('.quem-p')].map(r),
           testar: r(document.querySelector('[data-act=news-notify-test]')), largura: li.getBoundingClientRect().width - parseFloat(getComputedStyle(li).paddingLeft) - parseFloat(getComputedStyle(li).paddingRight) }; })()"""
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
    # de início, Conferir sozinho desligado. O aviso vem só dessa conferência: sem ela, nem horário nem aviso
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")
    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    r.eq((await pg.text_content("#p-news-opts h2")).strip(), "Novidades", "o painel Novidades em Opções")
    r.check(await pg.is_checked('[data-input="news-on"]'), "ligadas de início")
    r.check(not await pg.is_checked('[data-input="news-auto"]'), "Conferir sozinho desligado, de início")
    r.eq(await pg.locator('[data-input="news-hora"], [data-input="news-aviso"], [data-act="news-notify-test"]').count(), 0,
         "sem Conferir sozinho: sem horário, sem aviso nem Testar (nada avisaria)")
    r.check("avis" not in (await pg.text_content("#p-news-opts")).lower(), "nenhum texto fala de aviso")
    await r.shot(pg, "sem-conferir", full_page=True)
    await ctx.close()

    # o componente do aviso, igual nos apps da família, em cada tamanho e tema
    r.api("PUT", "api/settings", {"news_every": 7, "news_aviso": True, "news_para": [ANA]})
    for size, scheme, accent in (("cel", "dark", "laranja"), ("estreito", "light", "azul"), ("pc", "light", "verde")):
        ctx, pg = await r.page(b, size, scheme, accent=accent, user="Ana", user_id="u-ana")
        await r.open(pg, "#/config/opcoes", "#p-news-opts")
        await pg.wait_for_selector(".quem-p", timeout=8000)
        if size == "cel":
            r.eq((await pg.evaluate("[...document.querySelectorAll('#news-hora option')].map(o => o.textContent)"))[:3], ["00:00", "00:30", "01:00"], "o horário de meia em meia hora, sem AM/PM")
            r.eq(await pg.input_value("#news-hora"), "10:00", "às 10:00, de início")
            r.eq(await pg.evaluate("[...document.querySelectorAll('#news-every option')].map(o => o.textContent)"), ["7 dias", "15 dias", "30 dias"], "A cada: 7, 15 ou 30 dias")
            r.eq(await pg.evaluate(PESSOAS), [["Ana", True, ""], ["Beto", False, "sem celular"], ["Carla", False, ""]], "Quem recebe: um botão por pessoa da casa (nenhum aparelho), a Ana marcada")
        geo = await pg.evaluate(GEO)
        r.check(geo["quando"] and geo["quando"][0][1] == geo["quando"][1][1] and abs(geo["quando"][0][2] - geo["quando"][1][2]) < 1 and all(h == 50 for _, _, _, h in geo["quando"]),
                f"{size} {scheme}: Horário e A cada lado a lado, do mesmo tamanho ({geo['quando']})")
        ws = {round(w) for _, _, w, _ in geo["quem"]}
        r.check(len(ws) == 1 and len({y for _, y, _, _ in geo["quem"][:2]}) == 1, f"{size} {scheme}: os botões das pessoas do mesmo tamanho, lado a lado ({geo['quem']})")
        r.check(abs(geo["testar"][2] - geo["largura"]) < 1 and geo["testar"][1] > max(y for _, y, _, _ in geo["quem"]), f"{size} {scheme}: Testar no meu celular na largura toda, embaixo ({geo['testar']}, {geo['largura']})")
        r.check(await pg.evaluate(OVERFLOW), f"{size} {scheme}: sem rolagem para o lado")
        await r.shot(pg, f"opcoes-{size}-{scheme}", full_page=True)
        await ctx.close()
    r.api("PUT", "api/settings", {"news_every": 0, "news_aviso": False, "news_para": []})

    # ligar e escolher: grava na hora. Quem está na tela é a Ana (o user_id dela no Home Assistant)
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja", user="Ana", user_id="u-ana")
    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    await pg.click('label.switch:has([data-input="news-auto"])')
    await pg.locator(".toast", has_text="Conferir sozinho: a cada 7 dias, às 10:00").wait_for(timeout=5000)
    r.eq(r.data()["settings"]["news_every"], 7, "Conferir sozinho fica gravado (a cada 7 dias)")
    await pg.select_option("#news-hora", "21:30")
    await pg.locator(".toast", has_text="Conferir às 21:30").wait_for(timeout=5000)
    await pg.select_option("#news-every", "15")
    await pg.locator(".toast", has_text="Conferir a cada 15 dias").wait_for(timeout=5000)
    st = r.data()["settings"]
    r.eq((st["news_hora"], st["news_every"]), ("21:30", 15), "o horário e a cada quantos dias ficam gravados")
    await pg.click('label.switch:has([data-input="news-aviso"])')
    await pg.locator(".toast", has_text="Aviso no celular ligado").wait_for(timeout=5000)
    await pg.wait_for_selector(".quem-p", timeout=8000)
    st = r.data()["settings"]
    r.eq((st["news_aviso"], st["news_para"]), (True, [ANA]), "ligar o aviso sem ninguém escolhido: começa com quem está usando o app")
    await pg.click('.quem-p[data-id="person.carla"]')
    await pg.locator(".toast", has_text="Carla recebe o aviso").wait_for(timeout=5000)
    r.eq(r.data()["settings"]["news_para"], [ANA, "person.carla"], "tocar numa pessoa a põe em Quem recebe")
    await pg.click('.quem-p[data-id="person.beto"]')
    await pg.locator(".help", has_text="Sem celular para Beto").wait_for(timeout=5000)
    r.check(True, "quem não tem celular: diz para ligar o celular à pessoa")
    await pg.click('.quem-p[data-id="person.beto"]')
    await pg.locator(".toast", has_text="Beto não recebe o aviso").wait_for(timeout=5000)
    r.eq(await pg.evaluate("[...document.querySelectorAll('.quem-p[aria-pressed=true] b')].map(b => b.textContent)"), ["Ana", "Carla"], "tocar de novo tira")
    test = pg.locator('[data-act="news-notify-test"]')
    n = len(ha.calls("POST", "/core/api/services/notify/"))
    await test.click()
    await pg.locator(".toast", has_text="Aviso enviado").wait_for(timeout=8000)
    c = ha.calls("POST", "/core/api/services/notify/")
    r.eq(len(c), n + 1, "Testar no meu celular manda um aviso só")
    r.eq(c[-1]["path"], f"/core/api/services/notify/{PHONE}", "no meu celular (o ligado à Ana, quem está na tela)")
    r.eq(c[-1]["body"]["message"], "Novidades em 2 itens. Toque para abrir.", "com o texto do aviso")
    r.eq((await test.text_content()).strip(), "Testar no meu celular", "Testar no meu celular, como nos outros apps")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "escolhido", full_page=True)
    await pg.reload()
    await pg.wait_for_selector(".quem-p", timeout=8000)
    r.eq([await pg.input_value("#news-hora"), await pg.input_value("#news-every")], ["21:30", "15"], "ao abrir de novo, o mesmo horário e intervalo")

    # Conferir sozinho desligado: o horário e o aviso somem, e o que foi escolhido fica guardado
    await pg.click('label.switch:has([data-input="news-auto"])')
    await pg.locator(".toast", has_text="Conferir sozinho desligado").wait_for(timeout=5000)
    r.eq(await pg.locator('#news-hora, [data-input="news-aviso"], [data-act="news-notify-test"]').count(), 0, "desligado: sem horário nem aviso")
    r.eq(r.data()["settings"]["news_para"], [ANA, "person.carla"], "quem recebe continua guardado")
    await pg.click('label.switch:has([data-input="news-auto"])')
    await pg.locator('[data-act="news-notify-test"]').wait_for(timeout=5000)
    r.eq(await pg.evaluate("[...document.querySelectorAll('.quem-p[aria-pressed=true] b')].map(b => b.textContent)"), ["Ana", "Carla"], "ligado de novo: o aviso volta com as mesmas pessoas")

    # quem está na tela sem celular: o Testar fica inativo e diz o porquê
    ctx2, pg2 = await r.page(b, "cel", "light", user="Beto", user_id="u-beto")
    await r.open(pg2, "#/config/opcoes", "#p-news-opts")
    await pg2.wait_for_selector(".quem-p", timeout=8000)
    r.check(await pg2.is_disabled('[data-act="news-notify-test"]') and "Sem celular ligado a você" in await pg2.text_content(".aviso-quem"), "sem celular: Testar inativo, com o porquê")
    await ctx2.close()

    # desligar: somem do menu Mais, do endereço e da ficha
    await pg.click('label.switch:has([data-input="news-on"])')
    await pg.locator(".toast", has_text="Novidades desligadas").wait_for(timeout=5000)
    r.check(r.data()["settings"]["news"] is False, "desligadas fica gravado")
    r.eq(await pg.locator('#p-news-opts select, [data-input="news-auto"], [data-act="news-notify-test"]').count(), 0, "desligadas: sem Conferir sozinho nem Avisar")
    await r.shot(pg, "desligadas", full_page=True)
    await r.open(pg, "#/mais", ".menu-list")
    r.check("Novidades" not in await pg.evaluate("[...document.querySelectorAll('.menu-row b')].map(b => b.textContent)"), "o menu Mais fica sem Novidades")
    await r.open(pg, "#/novidades", ".menu-list")
    r.check(pg.url.endswith("#/mais"), "o endereço de Novidades abre o menu Mais")
    await r.open(pg, "#/i/sal-007", "dialog.sheet h1")
    r.eq(await pg.locator('dialog.sheet [data-slot="item-news"], dialog.sheet [data-act="item-news"]').count(), 0, "a ficha fica sem Novidades")
    r.eq(await pg.locator('dialog.sheet [data-slot="item-rec"]').count(), 1, "os Recursos continuam (não dependem das Novidades)")
    r.api("PUT", "api/settings", {"news": True})
    await ctx.close()

    # ninguém com celular ligado: cada pessoa diz "sem celular" e o aviso diz onde ligar
    trackers, ha.trackers = ha.trackers, []
    states = ha.states
    ha.states = [x for x in states if x["entity_id"] != "person.carla"]
    r.app.stop(); r.app = None  # o servidor guarda as pessoas por um minuto: um novo, já sem os celulares
    r.start(search=False, ha=ha)
    r.api("PUT", "api/settings", {"news_every": 7, "news_aviso": True, "news_para": [ANA]})
    ctx, pg = await r.page(b, "estreito", "light", accent="verde", user="Ana", user_id="u-ana")
    await r.open(pg, "#/config/opcoes", "#p-news-opts")
    await pg.wait_for_selector(".quem-p", timeout=8000)
    r.eq(await pg.evaluate(PESSOAS), [["Ana", True, "sem celular"], ["Beto", False, "sem celular"]], "ninguém com celular: cada pessoa diz")
    r.check("Sem celular para Ana" in await pg.text_content(".aviso-quem") and await pg.is_disabled('[data-act="news-notify-test"]'), "o aviso diz onde ligar, e o Testar fica inativo")
    r.check(await pg.evaluate(OVERFLOW), "320 px: sem rolagem para o lado")
    await r.shot(pg, "sem-celular", full_page=True)
    await ctx.close()
    ha.trackers, ha.states = trackers, states

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
