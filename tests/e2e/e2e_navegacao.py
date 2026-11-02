"""Navegação: abas, arrastar para o lado (celular), Voltar, endereços que não existem e a atualização quando outro aparelho muda o inventário."""
from e2e_lib import main

SWIPE = """([x0, x1, y]) => {
  const el = document.elementFromPoint(x0, y) || document.body;
  const t = (x) => new Touch({ identifier: 1, target: el, clientX: x, clientY: y });
  el.dispatchEvent(new TouchEvent('touchstart', { touches: [t(x0)], changedTouches: [t(x0)], bubbles: true }));
  el.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [t(x1)], bubbles: true }));
}"""


async def swipe(pg, x0, x1, y=600):  # longe da busca do Início (num campo, arrastar não troca de aba)
    await pg.evaluate(SWIPE, [x0, x1, y])
    await pg.wait_for_timeout(450)


def hash_(pg):
    return "#" + pg.url.split("#", 1)[1] if "#" in pg.url else "#/"


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="turquesa")
    await r.open(pg, "#/", ".tag")

    # abas de baixo
    for tab, h in (("search", "#/buscar"), ("rooms", "#/comodos"), ("data", "#/mais"), ("home", "#/")):
        await pg.click(f'.tabbar [data-tab="{tab}"]')
        await pg.wait_for_timeout(400)
        r.check(hash_(pg) == h and await pg.get_attribute(f'.tabbar [data-tab="{tab}"]', "aria-current") == "page", f"aba {tab} ({hash_(pg)})")

    # arrastar para o lado
    seq = []
    for _ in range(4):
        await swipe(pg, 300, 120)
        seq.append(hash_(pg))
    r.eq(seq, ["#/buscar", "#/comodos", "#/mais", "#/mais"], "arrastar para a esquerda: a próxima aba, até Mais")
    await swipe(pg, 100, 300)
    r.eq(hash_(pg), "#/comodos", "para a direita: a aba anterior")
    await swipe(pg, 10, 300)
    r.eq(hash_(pg), "#/comodos", "começando na borda (o Voltar do celular): nada")
    await swipe(pg, 300, 250)
    r.eq(hash_(pg), "#/comodos", "movimento curto: nada")
    await r.open(pg, "#/c/sala", ".rhead")
    await swipe(pg, 100, 300, 700)
    r.eq(hash_(pg), "#/comodos", "no cômodo, para a direita volta para Cômodos")
    await r.open(pg, "#/relatorio", ".report")
    await swipe(pg, 100, 300)
    r.eq(hash_(pg), "#/mais", "no relatório, volta para Mais")
    await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
    await swipe(pg, 300, 100)
    r.check(hash_(pg) == "#/i/sal-001" and await pg.locator("dialog.sheet[open]").count() == 1, "com a ficha aberta, arrastar não troca de aba")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)
    await r.open(pg, "#/buscar", ".sbar")
    await pg.focus('[data-input="search-q"]')
    await swipe(pg, 300, 100, int(await pg.evaluate("document.querySelector('[data-input=search-q]').getBoundingClientRect().top + 10")))
    r.eq(hash_(pg), "#/buscar", "arrastar num campo de texto: nada")

    # Voltar
    await r.open(pg, "#/", ".tag")
    await pg.click('.tabbar [data-tab="rooms"]')
    await pg.wait_for_selector(".ilist.rooms")
    await pg.click('.ilist.rooms .croom >> nth=1')
    await pg.wait_for_selector(".rhead")
    await pg.locator("#view .irow").first.click()
    await pg.wait_for_selector("dialog.sheet h1")
    await pg.go_back()
    await pg.wait_for_timeout(400)
    r.check(await pg.locator("dialog[open]").count() == 0 and hash_(pg) == "#/c/cozinha", f"Voltar fecha a ficha e fica no cômodo ({hash_(pg)})")
    await pg.go_back()
    await pg.wait_for_timeout(400)
    r.eq(hash_(pg), "#/comodos", "Voltar de novo: Cômodos")
    await r.open(pg, "#/c/cozinha", ".rhead")
    await pg.click(".uplink")
    await pg.wait_for_timeout(300)
    r.eq(hash_(pg), "#/comodos", "o link Cômodos no alto do cômodo")

    # foto do cômodo: setas trocam a foto
    await r.open(pg, "#/c/sala", ".rhead")
    await pg.click(".strip .ph >> nth=0")
    await pg.wait_for_selector("dialog.viewer")
    first = await pg.get_attribute("dialog.viewer .vimg img", "src")
    await pg.keyboard.press("ArrowRight")
    await pg.wait_for_timeout(300)
    r.check(await pg.get_attribute("dialog.viewer .vimg img", "src") != first, "seta para a direita: próxima foto")
    await pg.locator("dialog.viewer .vlist a").first.click()
    await pg.wait_for_selector("dialog.sheet h1", timeout=5000)
    r.check(hash_(pg).startswith("#/i/sal-"), f"um item da foto abre a ficha ({hash_(pg)})")
    await pg.keyboard.press("Escape")
    await pg.wait_for_timeout(300)

    # endereços que não existem
    await r.open(pg, "#/c/nao-existe", "#view .empty")
    r.eq((await pg.text_content("#view .empty h2")).strip(), "Cômodo não encontrado", "cômodo que não existe")
    await r.open(pg, "#/i/nao-existe", ".tag")
    await pg.locator(".toast", has_text="Este item não existe mais").wait_for(timeout=4000)
    r.eq(hash_(pg), "#/", "item que não existe: aviso e Início")
    await r.open(pg, "#/qualquer-coisa", ".tag")
    r.check(True, "endereço desconhecido: Início")

    # outro aparelho mudou o inventário: ao voltar para o app, a tela atualiza
    await r.open(pg, "#/c/varanda", ".rhead")
    before = await pg.locator("#view .irow").count()
    r.api("POST", "api/items", {"name": "Rede de descanso", "room": "varanda", "value": 180})
    await pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    await pg.wait_for_function(f"document.querySelectorAll('#view .irow').length === {before + 1}", timeout=5000)
    r.check(True, "voltar para o app traz o que outro aparelho cadastrou")
    # com o editor aberto, não atrapalha: atualiza depois de fechar
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-name", "Digitando")
    r.api("POST", "api/items", {"name": "Vaso grande", "room": "varanda", "value": 90})
    await pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    await pg.wait_for_timeout(800)
    r.eq(await pg.input_value("#f-name"), "Digitando", "com o editor aberto, o que se digita fica")
    await pg.click('[data-ed="cancel"]')
    await pg.click('[data-r="1"]')
    await pg.wait_for_timeout(300)
    await pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    await pg.wait_for_function(f"document.querySelectorAll('#view .irow').length === {before + 2}", timeout=5000)
    r.check(True, "e depois de fechar, atualiza")
    await ctx.close()

    # computador: sem arrastar; menu lateral
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/", ".tag")
    links = await pg.evaluate("[...document.querySelectorAll('.side nav a')].map(a => a.textContent.trim())")
    r.check([x.rstrip("/") for x in links[:5]] == ["Início", "Buscar", "Cômodos", "Relatório", "Mais"] and links[1].endswith("/"),
            f"menu lateral, com o atalho / da busca ({links})")
    await pg.click('.side .side-room >> nth=2')
    await pg.wait_for_timeout(300)
    r.eq(hash_(pg), "#/c/quarto", "cômodo pelo menu lateral")
    r.eq(await pg.get_attribute('.side .side-room >> nth=2', "aria-current"), "page", "e fica marcado")
    await ctx.close()
    await b.close()


main("navegacao", body)
