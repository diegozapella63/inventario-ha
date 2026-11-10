"""Mais > Configurações > Opções > Atalho no celular (1.48.0): o caminho do app no Home Assistant (/app/<slug>, pelo nome do
contêiner), os passos e o Copiar; fora do Home Assistant, o cartão não aparece. Igual em todos os apps da família."""
import e2e_lib
from e2e_lib import OVERFLOW, main

e2e_lib.SIZES.setdefault("cel390", (390, 844, True))


async def body(r, p):
    r.start(search=False, env={"INV_HOST": "a1b2c3d4-inventario"})
    r.eq(r.data()["atalho"], "/app/a1b2c3d4_inventario", "o caminho pelo nome do contêiner")
    b = await r.browser(p)
    for size, scheme in (("cel390", "dark"), ("estreito", "light")):
        ctx, pg = await r.page(b, size, scheme)
        await r.open(pg, "#/config/opcoes", ".more-tabs")
        card = pg.locator("#p-atalho")
        r.eq(await card.count(), 1, f"{size}: Opções tem o Atalho no celular")
        ids = await pg.evaluate("[...document.querySelectorAll('#view section.panel')].map(s => s.id)")
        r.eq(ids[-1], "p-atalho", f"{size}: por último")
        r.eq(await pg.input_value("#atalho-c"), "/app/a1b2c3d4_inventario", f"{size}: o caminho")
        r.check("Gerenciar atalhos" in await card.locator(".steps").inner_text(), f"{size}: os passos")
        await card.locator('[data-act="copy-field"]').click()
        await pg.locator(".toast", has_text="Toque e segure no texto para copiar").or_(pg.locator(".toast", has_text="Copiado")).first.wait_for(timeout=8000)
        r.eq(await pg.evaluate("document.activeElement.id"), "atalho-c", f"{size}: o texto fica selecionado")
        hs = await card.locator(".copy-row > *").evaluate_all("es => es.map(e => Math.round(e.getBoundingClientRect().height))")
        r.check(len(hs) == 2 and hs[0] == hs[1] == 50, f"{size}: o campo e o Copiar com 50 px ({hs})")
        r.check(await pg.evaluate(OVERFLOW), f"{size}: nada passa da largura")
        r.check(await pg.eval_on_selector("#atalho-c", "(e) => e.scrollWidth <= e.clientWidth"), f"{size}: o caminho inteiro à vista, sem cortar")
        bx = await card.locator(".copy-row > *").evaluate_all("es => es.map(e => e.getBoundingClientRect()).map(b => [Math.round(b.top), Math.round(b.bottom), Math.round(b.width)])")
        r.check(bx[1][0] >= bx[0][1] and bx[0][2] == bx[1][2], f"{size}: o Copiar embaixo, da mesma largura ({bx})")
        await card.screenshot(path=r.shot_path(f"{size}-{scheme}"))
        await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_atalho", body)
