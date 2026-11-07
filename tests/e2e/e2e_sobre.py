"""Mais > Sobre, a última linha do menu (a mesma página do CronologIA 1.51.0): CorrerIA Code (desenvolvimento de softwares),
por que esse nome, os seis apps da família, cada um com uma linha e o link para o GitHub (o InventarIA marcado com a
versão), e Meu GitHub. Voltar do celular e o "‹ Mais" voltam ao menu. De 320 px ao computador, claro e escuro."""
import os
import re

from e2e_lib import OVERFLOW, SIZES, main

SIZES.setdefault("cel390", (390, 844, True))  # só neste teste: o celular de 390 px

GH = "https://github.com/diegozapella63"
APPS = [
    ("CronologIA", "cronologia-ha", "Agenda da família, remédios, rotinas e placar."),
    ("ResolvIA", "resolvia-ha", "Listas de tarefas com prazos, pontos e repetição."),
    ("GerencIA", "gerencia-ha", "Finanças da casa: caixa, cartões e investimentos."),
    ("InventarIA", "inventario-ha", "Inventário da casa: cômodos, itens e valores."),
    ("EconomIA", "economia-ha", "Lista de compras com o melhor preço perto de casa."),
    ("MemorIA", "memoria-ha", "Cadernos de anotação que abrem na hora certa."),
]
WHY = ("Porque eu sou um programador sem tempo: vivo na correria. Então eu uso a IA para rodar tudo isso aqui. "
       "Ela escreve, testa e publica; eu dou as ideias e reclamo dos botões tortos.")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERSION = re.search(r'^version:\s*"?([\d.]+)', open(os.path.join(ROOT, "inventario", "config.yaml"), encoding="utf-8").read(), re.M).group(1)

# o que fica dentro da página: nenhum pedaço passa da borda da coluna
INSIDE = """() => { const page = document.querySelector('.about').getBoundingClientRect();
  return [...document.querySelectorAll('.about-hero, .about .panel, .about .ab-row, .about .ab-github, .about .ab-here, .about .ab-row .mb > span')]
    .filter(x => { const b = x.getBoundingClientRect(); return b.left < page.left - 1 || b.right > page.right + 1; }).map(x => x.className); }"""
SQUISH = "(s) => s.replace(/\\s+/g, ' ').trim()"


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    for size, scheme in (("cel390", "dark"), ("estreito", "light"), ("pc", "dark"), ("pc", "light")):
        tag = f"[{SIZES[size][0]} px {'escuro' if scheme == 'dark' else 'claro'}]"
        ctx, pg = await r.page(b, size, scheme)
        mobile = SIZES[size][2]

        # o menu: Sobre é a última linha, com o ícone de informação e a linha de baixo
        await r.open(pg, "#/", ".tag")
        await pg.click('.tabbar a[data-tab="data"]' if mobile else '.side .nav a[href="#/mais"]')
        await pg.wait_for_selector(".menu-list")
        rows = await pg.evaluate("[...document.querySelectorAll('.menu-row')].map(a => [a.querySelector('b').textContent, a.getAttribute('href')])")
        r.eq(rows[-1], ["Sobre", "#/sobre"], f"{tag} Sobre é a última linha do Mais, depois de Configurações")
        r.eq(rows[-2][0], "Configurações", f"{tag} logo abaixo de Configurações")
        last = pg.locator(".menu-row").last
        r.eq(await last.locator(".mb > span").text_content(), "CorrerIA Code, os apps e o GitHub.", f"{tag} com a linha de baixo")
        r.eq(await last.locator(".sec-ic use").get_attribute("href"), "#i-info", f"{tag} com o ícone de informação, no quadradinho das outras linhas")
        hs = await pg.evaluate("[...document.querySelectorAll('.menu-row')].map(a => Math.round(a.getBoundingClientRect().height))")
        r.check(hs[-1] >= 64, f"{tag} a linha do Sobre é grande como as outras ({hs})")

        # a tela
        await last.click()
        await pg.wait_for_selector(".about")
        r.check(pg.url.endswith("#/sobre"), f"{tag} Sobre abre a sua tela (#/sobre)")
        r.eq((await pg.text_content(".page-title")).strip(), "Sobre", f"{tag} com o título Sobre")
        r.eq(await pg.locator('.uplink[href="#/mais"]').count(), 1, f"{tag} com o ‹ Mais no alto")
        if mobile:
            r.eq(await pg.get_attribute('.tabbar a[data-tab="data"]', "aria-current"), "page", f"{tag} a aba Mais continua marcada")
        else:
            r.eq(await pg.get_attribute('.side .nav a[href="#/mais"]', "aria-current"), "page", f"{tag} Mais marcado na barra lateral")
        r.eq(await pg.title(), "InventarIA – Sobre", f"{tag} o título da aba do navegador")

        # o cartão do alto
        name = await pg.evaluate(f"({SQUISH})(document.querySelector('.ab-name').textContent)")
        r.eq(name, "CorrerIA Code", f"{tag} CorrerIA Code")
        accent = await pg.evaluate("""() => { const h = document.querySelector('.ab-name'), s = h.querySelector('span');
          return [s.textContent, getComputedStyle(s).color !== getComputedStyle(h).color, getComputedStyle(s).color === getComputedStyle(document.querySelector('.brand-word span') || s).color]; }""")
        r.check(accent[0] == "IA" and accent[1] and accent[2], f"{tag} o IA na cor de destaque, a mesma do InventarIA do alto ({accent})")
        what = await pg.evaluate("""() => { const x = document.querySelector('.ab-what'), cs = getComputedStyle(x);
          return [x.textContent, cs.textTransform, x.getBoundingClientRect().height, parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.5]; }""")
        r.check(what[0] == "desenvolvimento de softwares" and what[1] == "uppercase", f"{tag} embaixo, desenvolvimento de softwares em maiúsculas pequenas ({what[:2]})")
        r.check(what[2] < what[3] * 1.6, f"{tag} numa linha só ({what[2]:.0f} px de altura)")
        tagline = await pg.evaluate("() => { const x = document.querySelector('.ab-tag'); return [x.textContent, getComputedStyle(x).fontStyle]; }")
        r.eq(tagline, ["Feito na correria, rodado pela IA.", "italic"], f"{tag} Feito na correria, rodado pela IA., em itálico")
        r.eq(await pg.locator(".about-hero .ab-mark use").get_attribute("href"), "#i-flash", f"{tag} com o raio")

        # por que CorrerIA
        r.eq((await pg.text_content(".about-why h2")).strip(), "Por que CorrerIA?", f"{tag} Por que CorrerIA?")
        r.eq(await pg.evaluate(f"({SQUISH})(document.querySelector('.about-why p').textContent)"), WHY, f"{tag} o porquê, com o texto do CronologIA")

        # os apps: cada um com o seu GitHub, o nome com o IA em destaque e uma linha
        rows = pg.locator(".about-apps .ab-row")
        r.eq(await rows.count(), 6, f"{tag} os seis apps")
        r.eq([await rows.nth(i).get_attribute("href") for i in range(6)], [f"{GH}/{repo}" for _, repo, _ in APPS], f"{tag} na ordem, cada um para o seu GitHub")
        wms = await pg.evaluate("[...document.querySelectorAll('.about-apps .ab-wm')].map(w => [w.textContent, w.querySelector('span').textContent, getComputedStyle(w.querySelector('span')).color !== getComputedStyle(w).color])")
        r.eq([w[0] for w in wms], [n for n, _, _ in APPS], f"{tag} os nomes, sem espaço no meio")
        r.check(all(w[1] == "IA" and w[2] for w in wms), f"{tag} o IA de cada nome na cor de destaque")
        r.eq(await pg.evaluate("[...document.querySelectorAll('.about-apps .ab-row .mb > span')].map(s => s.textContent)"), [l for _, _, l in APPS], f"{tag} uma linha para cada app")
        nowrap = await pg.evaluate("[...document.querySelectorAll('.about-apps .ab-wm')].every(w => w.getClientRects().length === 1)")
        r.check(nowrap, f"{tag} nenhum nome quebra no meio")
        here = pg.locator(".about-apps .ab-row.here")
        r.eq(await here.count(), 1, f"{tag} um app marcado")
        r.eq(await here.get_attribute("href"), f"{GH}/inventario-ha", f"{tag} o marcado é o InventarIA")
        r.eq((await here.locator(".ab-here").text_content()).strip(), f"Este app · v{VERSION}", f"{tag} com Este app · v{VERSION}")
        r.eq(VERSION, r.data()["version"], f"{tag} a versão do config.yaml é a do servidor")

        # os links abrem fora do app
        links = await pg.evaluate("[...document.querySelectorAll('.about a')].map(a => [a.getAttribute('target'), a.getAttribute('rel')])")
        r.check(len(links) == 7 and all(x == ["_blank", "noopener"] for x in links), f"{tag} os 7 links abrem fora (target=_blank, rel=noopener) ({len(links)})")
        gh = pg.locator(".about a.ab-github")
        r.eq([await gh.get_attribute("href"), (await gh.text_content()).strip()], [GH, "Meu GitHub"], f"{tag} o botão Meu GitHub")
        gb, lb = await gh.bounding_box(), await pg.locator(".about-apps").bounding_box()
        r.check(abs(gb["width"] - lb["width"]) <= 1 and abs(gb["x"] - lb["x"]) <= 1, f"{tag} Meu GitHub da largura da lista ({gb['width']:.0f} / {lb['width']:.0f})")
        r.check("primary" in (await gh.get_attribute("class")), f"{tag} na cor do app")

        # nada passa da borda
        r.check(await pg.evaluate(OVERFLOW), f"{tag} sem rolagem para o lado")
        out = await pg.evaluate(INSIDE)
        r.check(not out, f"{tag} nada passa da borda da página" + (f" ({out[:3]})" if out else ""))
        label = f"{scheme}-{SIZES[size][0]}"
        await r.shot(pg, label)
        await r.shot(pg, f"{label}-inteira", full_page=True)

        if size == "cel390":
            # tocar num app abre o GitHub dele numa aba nova; o app fica no Sobre
            await ctx.route("https://github.com/**", lambda rt: rt.fulfill(body="<title>GitHub</title>ok", content_type="text/html"))
            async with ctx.expect_page() as np:
                await rows.nth(1).click()
            new = await np.value
            await new.wait_for_load_state()
            r.eq(new.url, f"{GH}/resolvia-ha", f"{tag} tocar no ResolvIA abre o GitHub dele numa aba nova")
            await new.close()
            r.check(pg.url.endswith("#/sobre") and await pg.locator(".about").count() == 1, f"{tag} e o app continua no Sobre")
            # Voltar do celular: volta ao menu
            await pg.go_back()
            await pg.wait_for_selector(".menu-list")
            r.check(pg.url.endswith("#/mais"), f"{tag} Voltar volta ao menu")
            # o ‹ Mais do alto também
            await pg.click('.menu-row[href="#/sobre"]')
            await pg.wait_for_selector(".about")
            await pg.click('.uplink[href="#/mais"]')
            await pg.wait_for_selector(".menu-list")
            r.check(pg.url.endswith("#/mais"), f"{tag} o ‹ Mais volta ao menu")
            # o endereço do CronologIA (#/mais/sobre) vira o daqui
            await pg.goto("about:blank")
            await pg.goto(r.base + "#/mais/sobre")
            await pg.wait_for_selector(".about")
            r.check(pg.url.endswith("#/sobre"), f"{tag} #/mais/sobre abre o Sobre (e vira #/sobre)")
        await ctx.close()

    # IA desligada: o Sobre continua (não depende da IA), sem o Novidades no menu
    r.api("PUT", "api/settings", {"ai": False})
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/mais", ".menu-list")
    rows = await pg.evaluate("[...document.querySelectorAll('.menu-row b')].map(b => b.textContent)")
    r.eq(rows, ["Bens", "Gráficos", "Categorias", "Relatório para seguro", "Configurações", "Sobre"], "IA desligada: o Sobre continua no fim do menu")
    await ctx.close()
    await b.close()


main("e2e_sobre", body)
