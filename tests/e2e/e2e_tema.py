"""1.75.0: o fundo e os cartões são os do tema do Home Assistant (hatema.js, o mesmo arquivo em todos os apps da família),
para todos os apps terem o mesmo fundo. Dentro de um Home Assistant de mentira, com um tema dele (claro e depois escuro,
trocado com o app aberto), o app pinta aquele fundo e aqueles cartões; aberto sozinho, as cores do tema padrão do Home
Assistant (#fafafa e #111111). O Home Assistant e o app ficam na mesma origem (http://ha.test), como no Ingress."""
from e2e_lib import main

# o Home Assistant em volta do app: o tema no <html>, como ele pinta, e o <home-assistant> com o hass.themes
HA = """<!doctype html><html style="--primary-background-color:#eef3fb;--card-background-color:#fcfdff"><body style="margin:0">
<home-assistant></home-assistant><iframe id="app" src="/app/" style="position:fixed;inset:0;width:100%;height:100%;border:0"></iframe>
<script>document.querySelector("home-assistant").hass = { themes: { darkMode: false } };
window.modo = (dark, bg, card) => { document.querySelector("home-assistant").hass = { themes: { darkMode: dark } };
  document.documentElement.style.setProperty("--primary-background-color", bg); document.documentElement.style.setProperty("--card-background-color", card); };</script></body></html>"""

# o fundo atrás da beira esquerda da tela (o que a pessoa vê em volta dos cartões)
FUNDO = """() => {
  const y = Math.round(innerHeight * 0.55);
  let el = document.elementFromPoint(3, y);
  for (let e = el; e; e = e.parentElement) {
    const bg = getComputedStyle(e).backgroundColor;
    if (bg && bg !== "rgba(0, 0, 0, 0)" && bg !== "transparent") return bg;
  }
  return getComputedStyle(document.body).backgroundColor;
}"""
CORES = "() => ['--ha-bg-light', '--ha-card-light', '--ha-bg-dark', '--ha-card-dark'].map((v) => document.documentElement.style.getPropertyValue(v))"
CARTAO = "() => getComputedStyle(document.querySelector('.tabbar')).backgroundColor"  # a barra de baixo, na cor dos cartões


async def body(run, p):
    run.start()
    b = await run.browser(p)

    async def servir(route):
        url = route.request.url
        if url.rstrip("/") == "http://ha.test":
            await route.fulfill(body=HA, content_type="text/html")
        elif url.startswith("http://ha.test/app/"):
            # pelo servidor do app, como o Ingress faz
            r = await route.fetch(url=run.base.rstrip("/") + "/" + url[len("http://ha.test/app/"):])
            await route.fulfill(response=r)
        else:
            await route.fulfill(status=404, body="")

    ctx, pg = await run.page(b, scheme="light")
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    await ctx.route("http://ha.test/**", servir)
    await pg.goto("http://ha.test/")
    app = pg.frames[1]
    await app.wait_for_selector(".tabbar")
    await pg.wait_for_timeout(600)
    run.eq(await app.evaluate("() => window.__haTema.doHA"), "light", "dentro do Home Assistant: lê o tema dele (claro)")
    run.eq(await app.evaluate(CORES), ["#eef3fb", "#fcfdff", "#111111", "#1c1c1c"], "as cores claras do tema, as escuras do padrão")
    run.eq(await app.evaluate(FUNDO), "rgb(238, 243, 251)", "claro: o fundo do tema")
    run.eq(await app.evaluate(CARTAO), "rgb(252, 253, 255)", "claro: o cartão do tema")
    await run.shot(pg, "claro")
    # a pessoa deixa o Home Assistant escuro (um tema com o escuro dele): o app vai junto, sem abrir de novo
    await pg.emulate_media(color_scheme="dark")
    await pg.evaluate("() => window.modo(true, '#0d1a26', '#172636')")
    await pg.wait_for_timeout(900)
    run.eq(await app.evaluate("() => window.__haTema.doHA"), "dark", "Home Assistant escuro: lê de novo")
    run.eq(await app.evaluate(CORES), ["#fafafa", "#ffffff", "#0d1a26", "#172636"], "agora as cores escuras do tema")
    run.eq(await app.evaluate(FUNDO), "rgb(13, 26, 38)", "escuro: o fundo do tema")
    run.eq(await app.evaluate(CARTAO), "rgb(23, 38, 54)", "escuro: o cartão do tema")
    await run.shot(pg, "escuro")
    run.eq(erros, [], "sem erros")
    await ctx.close()

    # sozinho (fora do Home Assistant): as cores do tema padrão do Home Assistant
    for esquema, fundo, cartao in (("light", "rgb(250, 250, 250)", "rgb(255, 255, 255)"), ("dark", "rgb(17, 17, 17)", "rgb(28, 28, 28)")):
        ctx, pg = await run.page(b, scheme=esquema)
        await pg.goto(run.base)
        await pg.wait_for_selector(".tabbar")
        run.eq(await pg.evaluate("() => window.__haTema.doHA"), None, f"{esquema}, sozinho: sem o Home Assistant")
        run.eq(await pg.evaluate(FUNDO), fundo, f"{esquema}, sozinho: o fundo do tema padrão")
        run.eq(await pg.evaluate(CARTAO), cartao, f"{esquema}, sozinho: o cartão do tema padrão")
        await ctx.close()
    await b.close()


main("e2e_tema", body)
