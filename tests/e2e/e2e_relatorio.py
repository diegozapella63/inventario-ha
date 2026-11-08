"""Relatório do inventário: totais, cômodos na ordem, fotos liga/desliga (e o menu Mais só diz "com fotos" com elas ligadas),
zonas e a impressão (PDF). 1.36.0: o padrão dos relatórios dos apps: o cabeçalho (a faixa na cor do app, o ícone, o app,
o título, a contagem e quando), os gráficos da tela Gráficos, a marca da CorrerIA Code no fim e Baixar PDF (o servidor faz
o arquivo, com as fotos ou sem, na cor do app: o app do Home Assistant no Android não imprime a página)."""
import os
import re

from e2e_lib import TMP, main

PRINT = "window.__printed = 0; window.print = () => { window.__printed++; };"
MENU_REP = "document.querySelector('.menu-row[href=\"#/relatorio\"] .mb > span').textContent"


async def body(r, p):
    r.start(search=False)
    d = r.data()
    total = sum(i["value"] for i in d["items"])
    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", "light", accent="azul", init=PRINT)
    await r.open(pg, "#/relatorio", ".report")
    tot = await pg.evaluate("[...document.querySelectorAll('.rtotal b')].map(e => e.textContent.replace(/\\s/g, ' '))")
    r.eq(tot, ["R$ " + f"{round(total):,}".replace(",", "."), "38", "6"], "patrimônio, itens e cômodos")
    rooms = await pg.evaluate("[...document.querySelectorAll('.rep-room h2')].map(e => e.textContent.trim())")
    r.eq(rooms, ["SALSala de estar", "COZCozinha", "QUAQuarto", "ESCEscritório", "LAVLavanderia", "VARVaranda"], "cômodos na ordem da casa")
    # o cabeçalho dos relatórios dos apps
    cab = " ".join((await pg.inner_text(".rcab > div")).split())
    r.check(cab.startswith("InventarIA · inventário da casa Relatório do inventário 38 itens em 6 cômodos · ") and re.search(r"\d\d/\d\d/\d{4} às \d\d:\d\d$", cab), f"o cabeçalho: o app, o título, a contagem e quando ({cab})")
    r.eq(await pg.locator(".rcab svg.app-ic").count(), 1, "o ícone do app no cabeçalho")
    # os gráficos da tela Gráficos
    titulos = [t.strip() for t in await pg.locator(".rep-g h2").all_inner_texts()]
    r.eq(titulos, ["Cômodos", "Categorias", "Faixas de valor", "Itens mais valiosos"], "os gráficos da tela Gráficos")
    parts = await pg.evaluate("[...document.querySelectorAll('#rg-rooms .hb-v span')].map(e => parseFloat(e.textContent.replace(',', '.')))")
    r.check(len(parts) == 6 and 97 <= sum(parts) <= 103, f"as partes dos cômodos somam 100% ({parts})")
    # no fim, a marca da CorrerIA Code (como no Mais > Sobre)
    marca = " ".join((await pg.inner_text(".report .marca")).split())
    r.eq(marca, "CorrerIA Code DESENVOLVIMENTO DE SOFTWARES", "no fim, a marca da CorrerIA Code")
    r.eq(await pg.evaluate("document.querySelector('.report').lastElementChild.className"), "marca", "a marca é a última coisa")
    secs = await pg.locator(".rep-room").count()
    r.eq(secs, 6, "uma seção por cômodo com itens")
    subtotal = await pg.evaluate("[...document.querySelectorAll('.rep-room')].map(s => s.querySelectorAll('tbody tr').length)")
    r.eq(sum(subtotal), 38, "todos os itens no relatório")
    r.eq(await pg.locator(".rep-room td.t img").count(), sum(1 for i in d["items"] if i["photos"]), "a foto de cada item que tem foto")
    await r.shot(pg, "pc", full_page=True)

    # fotos desligadas: fica guardado
    await pg.uncheck('[data-input="rep-photos"]')
    await pg.wait_for_timeout(300)
    r.eq(await pg.locator(".rep-room td.t").count(), 0, "sem fotos: sem a coluna")
    await pg.reload()
    await pg.wait_for_selector(".report")
    r.check(not await pg.is_checked('[data-input="rep-photos"]'), "a escolha fica para a próxima vez")
    # o menu Mais só diz "com fotos" quando o relatório mostra as fotos
    await r.open(pg, "#/mais", ".menu-list")
    r.eq(await pg.evaluate(MENU_REP), "Por cômodo, com gráficos. Baixa em PDF.", "sem fotos, a linha do menu Mais não promete fotos")
    await r.open(pg, "#/relatorio", ".report")
    await pg.check('[data-input="rep-photos"]')
    await r.open(pg, "#/mais", ".menu-list")
    r.eq(await pg.evaluate(MENU_REP), "Por cômodo, com fotos e gráficos. Baixa em PDF.", "com fotos, a linha do menu Mais diz com fotos")
    await r.open(pg, "#/relatorio", ".report")

    # Baixar PDF: o servidor faz o arquivo, com as fotos (ou sem) e na cor do app
    pdfa = pg.locator('[data-act="rep-pdf"]')
    href = await pdfa.get_attribute("href")
    r.check(href.startswith("api/relatorio.pdf?fotos=1&cor=%23") and "tinta=%23" in href, f"Baixar PDF: com fotos, na cor do app ({href})")
    bb = [await pg.locator(sel).bounding_box() for sel in (".rep-fotos", '[data-act="rep-pdf"]')]
    r.check(abs(bb[0]["width"] - bb[1]["width"]) < 1.5 and abs(bb[0]["height"] - bb[1]["height"]) < 1.5 and abs(bb[0]["y"] - bb[1]["y"]) < 1.5, f"Mostrar fotos e Baixar PDF lado a lado, do mesmo tamanho ({bb})")
    async with pg.expect_download() as dl:
        await pdfa.click()
    d1 = await dl.value
    with open(await d1.path(), "rb") as f:
        raw = f.read()
    r.check(d1.suggested_filename.startswith("inventario-") and d1.suggested_filename.endswith(".pdf") and raw.startswith(b"%PDF-"), f"o PDF baixa ({d1.suggested_filename})")
    r.check(raw.count(b"/Subtype /Image") >= 5 and raw.count(b"/Type /Page ") >= 2, "com as fotos, em várias páginas")
    r.eq(await pg.evaluate("window.__printed"), 0, "não abre a impressão (o app do Home Assistant não imprime)")
    await pg.uncheck('[data-input="rep-photos"]')
    await pg.wait_for_timeout(300)
    r.check("fotos=0" in await pg.get_attribute('[data-act="rep-pdf"]', "href"), "sem fotos, o PDF sai sem elas")
    await pg.check('[data-input="rep-photos"]')
    await pg.wait_for_timeout(300)
    await pg.emulate_media(media="print")
    hidden = await pg.evaluate("['.rep-tools', '.tabbar', '.side', '.topbar'].map(s => { const e = document.querySelector(s); return !e || getComputedStyle(e).display === 'none'; })")
    r.check(all(hidden), f"no papel, sem botões, abas nem menu ({hidden})")
    pdf = os.path.join(TMP, "relatorio.pdf")
    await pg.pdf(path=pdf, format="A4", print_background=True)
    with open(pdf, "rb") as f:
        n = f.read().count(b"/Type /Page\n") or f.seek(0) or f.read().count(b"/Type /Page")
    r.check(n >= 2, f"o PDF sai com várias páginas ({n})")
    await pg.emulate_media(media="screen")

    # 1.36.1: no Home Assistant a tela fica num quadro, e o app do Home Assistant no Android só baixa o que a página de
    # cima pede: o Baixar PDF põe o link lá e clica (como o Home Assistant faz com os backups)
    fctx, fpg = await r.page(b, "cel", "light")
    await fpg.goto(r.base + "api/rev")
    await fpg.evaluate("""(u) => { document.documentElement.innerHTML = '<body style="margin:0"><iframe id="ha" src="' + u + '#/relatorio" style="width:384px;height:800px;border:0"></iframe></body>';
      document.addEventListener('click', (e) => { if (e.target.download) window.__top = [e.target.href, e.target.download, e.target.target]; }, true); }""", r.base)
    fr = fpg.frame_locator("#ha")
    await fr.locator('[data-act="rep-pdf"]').wait_for(timeout=15000)
    async with fpg.expect_download() as dl:
        await fr.locator('[data-act="rep-pdf"]').click()
    d2 = await dl.value
    top = await fpg.evaluate("window.__top")
    r.check(top and "api/relatorio.pdf?fotos=1" in top[0] and top[1].startswith("inventario-") and top[2] == "_blank", f"num quadro: o link vai para a página de cima ({top})")
    with open(await d2.path(), "rb") as f:
        r.check(f.read(5) == b"%PDF-", f"num quadro: o PDF baixa ({d2.suggested_filename})")
    r.check("Baixando o PDF" in (await fr.locator(".toast").first.inner_text()), "diz que está baixando")
    r.eq(await fpg.locator("a[download]").count(), 0, "o link da página de cima sai depois")
    await fctx.close()

    # zonas ligadas: coluna Zona; ordem dos cômodos muda junto
    r.api("PUT", "api/settings", {"zones": True})
    r.api("POST", "api/rooms/order", {"ids": ["varanda", "sala", "cozinha", "quarto", "escritorio", "lavanderia"]})
    await r.open(pg, "#/relatorio", ".report")
    r.check("Zona" in await pg.evaluate("[...document.querySelectorAll('.rep-room thead th')].map(e => e.textContent)"), "zonas ligadas: coluna Zona")
    r.eq(await pg.text_content(".rep-room h2"), "VARVaranda", "a ordem do Organizar vale para o relatório")
    r.api("PUT", "api/settings", {"zones": False})
    await ctx.close()

    ctx, pg = await r.page(b, "cel", "dark")
    await r.open(pg, "#/relatorio", ".report")
    r.check(await pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1 && innerWidth <= screen.width + 1"), "celular: sem rolagem para o lado")
    await r.shot(pg, "cel")
    await ctx.close()
    await b.close()


main("relatorio", body)
