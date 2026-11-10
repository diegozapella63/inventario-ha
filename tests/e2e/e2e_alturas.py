"""Uma altura só, a mesma em todos os apps da família (1.45: 50 px): botões, campos, caixas de seleção, botões de escolha
(as abas de Configurações, o Tema) e as escolhas em botões nas quatro abas de Configurações, em Bens, Categorias,
Novidades, Buscar e na ficha de um item novo; no celular (384 e 320 px) e no computador. Ficam de fora os botões só com
ícone, os quadrinhos da IA, as linhas compactas da conferência da IA, as linhas das listas, os interruptores e as cores."""
from e2e_lib import main

H = 50
CONTROLES = ".btn:not(.icon), .input, .select, .seg, .chip, .quem-p, .more-tabs"
MEDIR = """(sel) => [...document.querySelectorAll(sel)].filter(e => e.offsetParent && e.getBoundingClientRect().width > 4 && !e.closest('.found, .imp-tiles, .rph, .chat-in, .tabbar, .side'))
  .map(e => [e.offsetHeight, (e.className || e.tagName) + ' ' + (e.textContent || e.placeholder || '').replace(/\\s+/g, ' ').trim().slice(0, 30)])"""


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    for size in ("cel", "estreito", "pc"):
        ctx, pg = await r.page(b, size, "dark")
        for rota in ("#/config", "#/config/dados", "#/config/aparencia", "#/config/opcoes", "#/bens", "#/categorias", "#/novidades", "#/buscar", "#/item/novo"):
            await r.open(pg, rota, "#view")
            await pg.wait_for_timeout(500)
            hs = await pg.evaluate(MEDIR, CONTROLES)
            fora = [x for x in hs if x[0] != H]
            r.check(not fora, f"[{size}] {rota}: {len(hs)} controles, todos com {H} px {fora[:4]}")
        await r.shot(pg, f"alturas-{size}")
        await ctx.close()
    await b.close()


main("alturas", body)
