"""Relatório para seguro: totais, cômodos na ordem, fotos liga/desliga, zonas e a impressão (PDF)."""
import os

from e2e_lib import TMP, main

PRINT = "window.__printed = 0; window.print = () => { window.__printed++; };"


async def body(r, p):
    r.start(search=False)
    d = r.data()
    total = sum(i["value"] for i in d["items"])
    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", "light", accent="azul", init=PRINT)
    await r.open(pg, "#/relatorio", ".report")
    tot = await pg.evaluate("[...document.querySelectorAll('.rtotal b')].map(e => e.textContent.replace(/\\s/g, ' '))")
    r.eq(tot, ["R$ " + f"{round(total):,}".replace(",", "."), "38", "6"], "patrimônio, itens e cômodos")
    rooms = await pg.evaluate("[...document.querySelectorAll('.report > .rtable tbody tr td:first-child')].map(e => e.textContent.trim())")
    r.eq(rooms, ["SAL Sala de estar", "COZ Cozinha", "QUA Quarto", "ESC Escritório", "LAV Lavanderia", "VAR Varanda"], "cômodos na ordem da casa")
    parts = await pg.evaluate("[...document.querySelectorAll('.report > .rtable tbody tr td:last-child')].map(e => +e.textContent.replace(/\\D/g, ''))")
    r.check(97 <= sum(parts) <= 103, f"as partes somam 100% ({parts})")
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
    await pg.check('[data-input="rep-photos"]')

    # imprimir
    await pg.click('[data-act="print"]')
    r.eq(await pg.evaluate("window.__printed"), 1, "Imprimir abre a impressão do navegador")
    await pg.emulate_media(media="print")
    hidden = await pg.evaluate("['.rep-tools', '.tabbar', '.side', '.topbar'].map(s => { const e = document.querySelector(s); return !e || getComputedStyle(e).display === 'none'; })")
    r.check(all(hidden), f"no papel, sem botões, abas nem menu ({hidden})")
    pdf = os.path.join(TMP, "relatorio.pdf")
    await pg.pdf(path=pdf, format="A4", print_background=True)
    with open(pdf, "rb") as f:
        n = f.read().count(b"/Type /Page\n") or f.seek(0) or f.read().count(b"/Type /Page")
    r.check(n >= 2, f"o PDF sai com várias páginas ({n})")
    await pg.emulate_media(media="screen")

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
