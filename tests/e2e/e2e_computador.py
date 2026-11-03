"""O layout do computador, em 1280 e 1920 de largura: a barra lateral (seções, cômodos com o código e o valor, Novo
cômodo, a versão), sem a barra de abas; os botões no alto alinhados à direita; o Início em duas colunas; o conteúdo
com largura máxima e centralizado; as janelas no meio da tela; a ficha do item à direita; o visualizador com o painel
ao lado; e o cursor já na busca ao abrir Buscar pelo menu."""
from e2e_lib import SIZES, main

SIZES.setdefault("pc-grande", (1920, 1080, False))  # só neste teste

MEASURE = """() => {
  const box = (s) => { const e = typeof s === 'string' ? document.querySelector(s) : s; if (!e) return null; const r = e.getBoundingClientRect();
    return { l: Math.round(r.left), r: Math.round(r.right), t: Math.round(r.top), b: Math.round(r.bottom), w: Math.round(r.width), h: Math.round(r.height) }; };
  const shown = (s) => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== 'none' && e.getClientRects().length > 0; };
  return { vw: document.documentElement.clientWidth, vh: innerHeight, side: box('.side'), main: box('.main'), view: box('#view'), topbar: box('.topbar'),
    padR: parseFloat(getComputedStyle(document.querySelector('.topbar')).paddingRight), tabbar: shown('.tabbar'), brandWord: shown('.eyebrow .brand-word'),
    top: [...document.querySelectorAll('.top-actions .btn')].map(box), scrollX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 };
}"""
DLG = "(() => { const d = [...document.querySelectorAll('dialog[open]')].pop(), r = d.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height, vw: document.documentElement.clientWidth, iw: innerWidth, vh: innerHeight}; })()"


def near(a, b, tol=2):
    return abs(a - b) <= tol


def centered(g):
    """No meio da tela (a sobra de cada lado igual, com a folga da barra de rolagem reservada à direita)."""
    return abs(g["l"] - (g["iw"] - g["r"])) <= 16 and near(g["t"], g["vh"] - g["b"])


async def body(r, p):
    r.start(search=False)
    d = r.data()
    totals = {x["id"]: sum(i["value"] for i in d["items"] if i["room"] == x["id"]) for x in d["rooms"]}
    want_rooms = [[x["code"], x["name"], f"{round(totals[x['id']]):,}".replace(",", ".")] for x in d["rooms"]]
    b = await r.browser(p)
    for size, scheme, accent in (("pc", "light", "azul"), ("pc-grande", "dark", "turquesa")):
        w = SIZES[size][0]
        ctx, pg = await r.page(b, size, scheme, accent=accent)
        await r.open(pg, "#/", ".tag")
        m = await pg.evaluate(MEASURE)
        tag = f"[{w}]"

        # -- barra lateral, sem a barra de abas
        nav = await pg.evaluate("[...document.querySelectorAll('.side .nav a')].map(a => a.textContent.trim())")
        r.check(m["side"]["l"] == 0 and m["side"]["w"] == 272 and m["side"]["h"] == m["vh"] and not m["tabbar"] and not m["brandWord"],
                f"{tag} barra lateral de 272 px na altura toda, sem a barra de abas embaixo nem o nome no alto")
        r.eq(nav, ["Início", "Buscar/", "Cômodos", "Relatório", "Mais"], f"{tag} as seções na barra lateral, com o atalho / do Buscar")
        rooms = await pg.evaluate("[...document.querySelectorAll('.side a.side-room')].map(a => [...a.children].map(c => c.textContent.trim()))")
        r.eq(rooms, want_rooms, f"{tag} os cômodos na ordem da casa, com o código e o valor")
        r.check(await pg.text_content(".side-h span") == "6" and (await pg.text_content(".side-foot")).strip() == f"Versão {d['version']}", f"{tag} quantos cômodos e a versão no pé")
        r.eq(await pg.get_attribute(".side .nav a[href='#/']", "aria-current"), "page", f"{tag} Início marcado")

        # -- botões no alto, à direita, alinhados
        top = m["top"]
        r.check(len(top) == 2 and top[0]["h"] == top[1]["h"] == 40 and top[0]["t"] == top[1]["t"] and top[0]["r"] < top[1]["l"]
                and near(top[1]["r"], m["topbar"]["r"] - m["padR"]), f"{tag} Catalogar e Adicionar item no alto, do mesmo tamanho, à direita ({top})")

        # -- Início em duas colunas, com largura máxima
        hero = await pg.evaluate("[document.querySelector('.hero .tagwrap'), document.querySelector('.hero .hero-side')].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), Math.round(r.top)]; })")
        r.check(hero[1][0] > hero[0][1] and abs(hero[0][2] - hero[1][2]) < 80, f"{tag} etiqueta e busca lado a lado ({hero})")
        cols = await pg.evaluate("[...document.querySelectorAll('.cols > .sec')].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; })")
        r.check(len(cols) == 2 and cols[1][0] > cols[0][0] and cols[0][1] == cols[1][1], f"{tag} Categorias e Mais valiosos em duas colunas ({cols})")
        if w == 1920:
            r.check(m["view"]["w"] == 1040 and near(m["view"]["l"] - m["main"]["l"], m["main"]["r"] - m["view"]["r"]), f"{tag} conteúdo com 1040 px, no meio da área ({m['view']})")
        else:
            r.check(m["view"]["l"] == m["main"]["l"] == 272 and near(m["view"]["r"], m["main"]["r"]), f"{tag} conteúdo ocupa a área ao lado da barra ({m['view']})")
        r.check(not m["scrollX"], f"{tag} sem rolagem para o lado")
        await r.shot(pg, f"inicio-{w}")

        # -- abrir pelo menu: o cômodo fica marcado; Buscar já com o cursor
        await pg.click(".side a.side-room[href='#/c/escritorio']")
        await pg.wait_for_selector(".rhead h1")
        r.eq(await pg.evaluate("[...document.querySelectorAll('.side [aria-current=page]')].map(a => [...a.children].map(c => c.textContent.trim()))"),
             [want_rooms[3]], f"{tag} o cômodo aberto fica marcado na barra lateral")
        await pg.click(".side .nav a[href='#/buscar']")
        await pg.wait_for_selector(".sbar")
        await pg.wait_for_timeout(200)
        r.eq(await pg.evaluate("document.activeElement.dataset.input"), "search-q", f"{tag} Buscar pelo menu: o cursor já na busca")

        # -- janelas no meio da tela
        await pg.click('.top-actions [data-act="item-new"]')
        await pg.wait_for_selector("#f-name")
        await pg.wait_for_timeout(300)
        g = await pg.evaluate(DLG)
        r.check(g["w"] == 660 and centered(g), f"{tag} Novo item no meio da tela, com 660 px ({g})")
        await r.shot(pg, f"janela-item-{w}")
        await pg.click('[data-ed="cancel"]')
        await pg.click('.side [data-act="room-new"]')
        await pg.wait_for_selector("#rn-name")
        await pg.wait_for_timeout(300)
        g = await pg.evaluate(DLG)
        r.check(g["w"] == 460 and centered(g), f"{tag} Novo cômodo, pela barra lateral: janela estreita no meio")
        await pg.click("dialog [data-x]")

        # -- a ficha do item à direita, com a página atrás
        await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
        await pg.wait_for_timeout(350)
        g = await pg.evaluate(DLG)
        r.check(g["w"] == 560 and g["r"] > g["iw"] - 20 and g["t"] == 0 and near(g["h"], g["vh"]), f"{tag} a ficha abre à direita, na altura toda, com 560 px")
        r.check(near(g["r"], g["iw"]), f"{tag} a ficha encosta na borda direita da janela ({g['r']} de {g['iw']})")
        await r.shot(pg, f"ficha-{w}")

        # -- visualizador: a foto e o painel ao lado
        await r.open(pg, "#/c/sala", ".rhead")
        await pg.click(".strip .ph")
        await pg.wait_for_selector("dialog.viewer .vside")
        await pg.wait_for_timeout(300)
        v = await pg.evaluate("['.vimg', '.vside'].map(s => { const r = document.querySelector('dialog.viewer ' + s).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), Math.round(r.width)]; })")
        r.check(v[1][2] == 340 and v[1][0] >= v[0][1] - 1, f"{tag} visualizador: o painel de 340 px ao lado da foto ({v})")
        await r.shot(pg, f"visualizador-{w}")
        await ctx.close()
    await b.close()


main("computador", body)
