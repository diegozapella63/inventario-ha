"""Mais > Configurações > Integrações > Memória da IA (1.96.0): o cartão logo depois do IA, dizendo que a memória é uma só,
compartilhada por todos os apps; escrever uma frase, ver na lista e apagar; a frase fica na pasta share (fora do app) e o
que outro app escreveu ali aparece aqui; com Usar IA desligado, o cartão some. Celular de 390 px e computador, claro e escuro."""
import json
import os

import e2e_lib
from e2e_lib import OVERFLOW, main

e2e_lib.SIZES.setdefault("cel390", (390, 844, True))


async def body(r, p):
    r.start(search=False)
    arq = os.path.join(os.path.dirname(r.app.path("share")), "familia", "memoria_ia.json")
    os.makedirs(os.path.dirname(arq), exist_ok=True)
    with open(arq, "w", encoding="utf-8") as f:   # o que outro app da casa já escreveu
        json.dump({"versao": 1, "lista": [{"id": "r1", "texto": "A feira é no sábado", "em": "2026-11-02T09:30:00-0300", "app": "ResolvIA"}]}, f)

    b = await r.browser(p)
    for tam, tema in (("cel390", "light"), ("pc", "dark")):
        ctx, pg = await r.page(b, tam, tema, accent="laranja")
        await r.open(pg, "#/config/integracoes", ".more-tabs")
        card = pg.locator("#p-memoria")
        await card.locator(".mem-lista li").first.wait_for(timeout=8000)
        r.eq(" ".join((await card.locator("h2").text_content()).split()), "Memória da IA", f"{tam}: o cartão Memória da IA")
        r.check("Uma memória só, da casa, compartilhada por todos os apps" in await card.locator(".lead").text_content(), f"{tam}: diz que é compartilhada")
        ids = await pg.evaluate("[...document.querySelectorAll('#view section.panel')].map(s => s.id)")
        r.eq(ids.index("p-memoria"), ids.index("p-ai") + 1, f"{tam}: logo depois do IA ({ids})")
        r.check("A feira é no sábado" in await card.locator(".mem-lista li").first.text_content(), f"{tam}: o que outro app escreveu aparece")
        r.check("ResolvIA" in await card.locator(".mem-lista li .ot > span").first.text_content(), f"{tam}: e diz de que app veio")
        r.check(await card.locator("h2 svg").count() >= 1, f"{tam}: o título com ícone")
        r.eq(await card.locator(".lbl svg").count(), 1, f"{tam}: o campo com ícone")
        r.eq(await card.locator(".btn:not(:has(svg))").count(), 0, f"{tam}: todo botão com ícone")
        caixa = await pg.evaluate("(() => { const t = document.querySelector('#mem-texto').getBoundingClientRect(), b = document.querySelector('[data-act=\"mem-add\"]').getBoundingClientRect(); return [Math.round(t.height), Math.round(b.height)]; })()")
        r.eq(caixa, [50, 50], f"{tam}: o campo e o botão com a altura da família")
        r.check(await pg.evaluate(OVERFLOW), f"{tam}: nada passa da largura")
        await card.scroll_into_view_if_needed()
        await r.shot(pg, f"memoria-{tam}-{tema}")
        if tam == "cel390":
            await pg.fill("#mem-texto", "A feira da casa é sempre no sábado de manhã, e o pão é o da padaria da esquina, nunca o do mercado")
            r.check(await pg.evaluate("(() => { const t = document.querySelector('#mem-texto'); return t.scrollHeight <= t.clientHeight + 1 && t.offsetHeight > 60; })()"), "o campo cresce com o texto, sem rolagem dentro dele")
            await pg.fill("#mem-texto", "Creme é sempre da categoria Higiene")
            await pg.click('[data-act="mem-add"]')
            await pg.locator(".toast", has_text="A IA vai lembrar").wait_for(timeout=8000)
            r.eq(await card.locator(".mem-lista li").count(), 2, "a frase nova entra na lista")
            with open(arq, encoding="utf-8") as f:
                lista = json.load(f)["lista"]
            r.eq([(x["texto"], x["app"]) for x in lista], [("A feira é no sábado", "ResolvIA"), ("Creme é sempre da categoria Higiene", "InventarIA")], "e fica na pasta share, para todos os apps")
            await pg.click('[data-act="mem-add"]')
            await pg.locator(".toast", has_text="Escreva o que é para lembrar.").wait_for(timeout=8000)
            await card.locator('[data-act="mem-del"]').nth(1).click()
            await pg.locator(".toast", has_text="Apagado da memória").wait_for(timeout=8000)
            r.eq(await card.locator(".mem-lista li").count(), 1, "apagar tira da lista")
            # a memória é da IA: com Usar IA desligado, o cartão some
            await pg.click('label.switch:has([data-input="ai-on"])')
            await pg.locator(".toast", has_text="IA desligada").wait_for(timeout=8000)
            r.eq(await pg.locator("#p-memoria").count(), 0, "com a IA desligada, o cartão some")
            await pg.click('label.switch:has([data-input="ai-on"])')
            await pg.locator(".toast", has_text="IA ligada").wait_for(timeout=8000)
        await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_memoria_ia", body)
