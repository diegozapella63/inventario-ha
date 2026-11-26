"""1.108.0 (o dono: "do mesmo jeito que criamos esse agrupar por… a gente precisa adicionar ele em outros locais… no buscar";
"deixa tudo bem bonito nesse padrão"): Buscar › Agrupar por, no padrão dos Consumíveis e fora dos Filtros: Nenhum, Cômodo,
Categoria (só com um tipo que as tem) e, em Todos os tipos, Tipo. Cada grupo com o ícone, o nome, a contagem e a soma, que
fecha pelo título; o aparelho lembra a escolha, o bloco fechado (com o escolhido ao lado) e os grupos fechados. O Selecionar
vale com os grupos. Os grupos dos Bens também fecham. Casa de teste e bens inventados."""
from e2e_lib import OVERFLOW, main


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


OPCOES = "() => [...document.querySelectorAll('.agrupar .seg button')].map(b => [b.textContent.trim(), b.getAttribute('aria-pressed')])"
GRUPOS = "() => [...document.querySelectorAll('#results .zone .zone-h')].map(h => [h.querySelector('h3').textContent.trim(), h.querySelector('.zs').textContent.replace(/\\s+/g, ' ').trim()])"


async def body(r, p):
    r.start(search=False)
    st, _, area = r.app.request("POST", "api/rooms", {"kind": "bens"})
    rid = area["room"]["id"]
    r.app.request("POST", "api/items", {"room": rid, "name": "Apartamento Exemplo", "cat": "imoveis", "value": 300000})
    r.app.request("POST", "api/items", {"room": rid, "name": "Carro Exemplo", "cat": "veiculos", "value": 50000})
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/buscar", ".sbar")
    await pg.wait_for_selector("#results .irow", timeout=8000)
    r.eq(await pg.evaluate(OPCOES), [["Nenhum", "true"], ["Cômodo", "false"], ["Tipo", "false"]], "Todos os tipos: Nenhum, Cômodo e Tipo (sem Categoria)")
    r.check(await pg.evaluate("() => { const a = document.querySelector('.agrupar'), f = document.querySelector('.sfilters'); return !f.contains(a) && f.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING; }"),
            "um bloco dele, depois dos Filtros")
    r.eq(await pg.locator("#results .zone").count(), 0, "Nenhum: a lista de sempre")
    n_todos = await pg.locator("#results .irow").count()
    await pg.click('.agrupar [data-v="comodo"]')
    await pg.wait_for_selector("#results .zone .zone-h", timeout=6000)
    gs = await pg.evaluate(GRUPOS)
    r.eq(gs[0][0], "Sala de estar", "Cômodo: os cômodos na ordem da casa")
    r.check(gs[-1][0] == "Bens" and gs[-1][1].startswith("2 bens") is False and gs[-1][1].startswith("2 itens"), f"os bens à parte, no fim ({gs[-1]})")
    r.check(all("R$" in x[1] for x in gs), "cada grupo com a soma")
    r.eq(await pg.locator("#results .irow").count(), n_todos, "os mesmos itens, nos grupos")
    caixas = [await x.bounding_box() for x in await pg.locator(".agrupar .seg button").all()]
    r.check(len({round(c["y"]) for c in caixas}) == 1 and max(c["width"] for c in caixas) - min(c["width"] for c in caixas) < 2, "as escolhas numa linha, do mesmo tamanho")
    await r.shot(pg, "comodo")
    # um grupo fecha pelo título; o aparelho lembra
    await pg.click('#results .zone[data-zk="r:sala"] .zone-h')
    r.check(not await pg.locator('#results .zone[data-zk="r:sala"] .ilist').is_visible(), "o grupo fecha pelo título")
    await pg.reload()
    await pg.wait_for_selector('#results .zone[data-zk="r:sala"]', timeout=8000)
    r.check(await pg.locator('#results .zone[data-zk="r:sala"].fechada').count() == 1 and await pg.get_attribute('.agrupar [data-v="comodo"]', "aria-pressed") == "true",
            "o aparelho lembra a escolha e o grupo fechado")
    await pg.click('#results .zone[data-zk="r:sala"] .zone-h')
    # Tipo
    await pg.click('.agrupar [data-v="tipo"]')
    await pg.wait_for_function("document.querySelector('#results .zone h3') && document.querySelector('#results .zone h3').textContent.includes('Itens da casa')", timeout=6000)
    r.eq([x[0] for x in await pg.evaluate(GRUPOS)], ["Itens da casa", "Imóveis", "Veículos"], "Tipo: os itens da casa e cada tipo de bem")
    # um tipo com categorias: Nenhum, Cômodo e Categoria; o Tipo de antes vira Nenhum
    await pg.select_option('[data-input="search-tipo"]', "casa")
    await pg.wait_for_function("document.querySelectorAll('.agrupar .seg button').length === 3 && [...document.querySelectorAll('.agrupar .seg button')].some(b => b.dataset.v === 'cat')", timeout=6000)
    r.eq(await pg.evaluate(OPCOES), [["Nenhum", "true"], ["Cômodo", "false"], ["Categoria", "false"]], "Itens da casa: Nenhum, Cômodo e Categoria; o Tipo de antes vira Nenhum")
    await pg.click('.agrupar [data-v="cat"]')
    await pg.wait_for_selector("#results .zone .zone-h", timeout=6000)
    nomes = [x[0] for x in await pg.evaluate(GRUPOS)]
    r.check("Eletrônicos" in nomes and "Imóveis" not in nomes and len(nomes) == len(set(nomes)), f"Categoria: as dos itens da casa ({nomes})")
    # o bloco fecha pelo título: o escolhido ao lado
    await pg.click(".agrupar-l")
    r.check(await pg.locator(".agrupar-seg").is_hidden() and txt(await pg.text_content(".agrupar-val")) == "· Categoria", "fechado, o escolhido ao lado")
    await pg.reload()
    await pg.wait_for_selector(".agrupar.fechado", timeout=8000)
    r.check(True, "o aparelho lembra o bloco fechado")
    await pg.click(".agrupar-l")
    # o Selecionar vale com os grupos
    await pg.click('[data-act="sel-start"]')
    await pg.wait_for_selector(".selbar")
    await pg.locator("#results .zone .irow.selr").first.click()
    r.eq(txt(await pg.text_content(".selbar .btn")), "Alterar 1 item", "o Selecionar marca dentro de um grupo")
    await pg.click('[data-act="sel-end"]')
    # um tipo de bem: sem nada a agrupar
    await pg.select_option('[data-input="search-tipo"]', "imoveis")
    await pg.wait_for_timeout(500)
    r.eq(await pg.locator(".agrupar").count(), 0, "um tipo de bem: sem o Agrupar por")
    await pg.set_viewport_size({"width": 320, "height": 760})
    await pg.select_option('[data-input="search-tipo"]', "")
    await pg.click('.agrupar [data-v="comodo"]')
    await pg.wait_for_timeout(300)
    r.check(await pg.evaluate(OVERFLOW), "320 px: sem rolagem para o lado")
    await r.shot(pg, "320")
    # os grupos dos Bens também fecham pelo título
    await r.open(pg, "#/bens", ".zone")
    r.eq([txt(t) for t in await pg.locator(".bens .zone h3").all_inner_texts()], ["Imóveis", "Veículos"], "os grupos dos Bens")
    await pg.click('.bens .zone[data-zk="Imóveis"] .zone-h')
    r.check(not await pg.locator('.bens .zone[data-zk="Imóveis"] .ilist').is_visible() and await pg.get_attribute('.bens .zone[data-zk="Imóveis"] .zone-h', "aria-expanded") == "false",
            "um grupo dos Bens fecha pelo título")
    await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_agrupar", body)
