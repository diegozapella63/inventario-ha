"""Fotos do cômodo: a faixa (com "N itens" em cada foto), adicionar pela faixa, o visualizador (posição, os itens daquela
foto, ir para um item), a legenda, a capa, tirar a foto do cômodo (os itens continuam com ela), adicionar um item com
a foto, e no Editar cômodo subir, legendar e tirar."""
import os

from e2e_lib import OVERFLOW, helpers, main

STRIP = "[...document.querySelectorAll('.strip .ph[data-act=viewer-room]')].map(b => [b.getAttribute('aria-label'), (b.querySelector('.cnt') || {}).textContent || ''])"
V = "dialog.viewer"


def room(r, rid="escritorio"):
    return next(x for x in r.data()["rooms"] if x["id"] == rid)


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="coral")

    async def viewer(i):
        await pg.click(f'.strip .ph[data-i="{i}"]')
        await pg.wait_for_selector(f"{V} .vside", timeout=6000)

    async def pos():
        return (await pg.text_content(f"{V} .vtop .pos")).strip()

    # -- a faixa: cada foto com quantos itens a usam
    await r.open(pg, "#/c/escritorio", ".rhead")
    r.eq(await pg.evaluate(STRIP), [["Mesa de trabalho", "5 itens"], ["Estante do escritório", ""]], "faixa: as fotos pela legenda, com quantos itens usam cada uma")
    r.eq((await pg.text_content(".strip .ph.add")).strip(), "Foto do cômodo", "e o botão Foto do cômodo no fim")

    # -- adicionar pela faixa, duas de uma vez
    async with pg.expect_file_chooser() as fc:
        await pg.click('.strip [data-act="room-photo-add"]')
    chooser = await fc.value
    r.check(chooser.is_multiple(), "dá para escolher várias fotos de uma vez")
    await chooser.set_files([os.path.join(helpers.FIXTURE, "photos", n) for n in ("quarto-1.jpg", "lavanderia-1.jpg")])
    await pg.locator(".toast", has_text="2 fotos adicionadas").wait_for(timeout=15000)
    ph = room(r)["photos"]
    r.check(len(ph) == 4 and ph[2]["label"] == ph[3]["label"] == "", "as duas entram no fim, sem legenda")
    r.eq([x[0] for x in await pg.evaluate(STRIP)][2:], ["Foto 3", "Foto 4"], "e aparecem na faixa")
    r.check("4 fotos" in await pg.text_content(".rhead .stats"), "o cômodo conta 4 fotos")
    await r.shot(pg, "faixa")

    # -- o visualizador: foto nova, legenda, andar entre as fotos
    await viewer(2)
    r.eq([(await pg.text_content(f"{V} .vtop .cap")).strip(), await pos()], ["Escritório", "3 de 4"], "foto sem legenda: o nome do cômodo e a posição")
    r.eq((await pg.text_content(f"{V} .vside h3")).strip(), "Nenhum item usa esta foto", "foto nova: nenhum item usa")
    await pg.fill("#v-label", "Cadeira nova")
    await pg.press("#v-label", "Tab")
    await pg.locator(".toast", has_text="Legenda salva").wait_for(timeout=6000)
    r.eq(room(r)["photos"][2]["label"], "Cadeira nova", "a legenda fica gravada ao sair do campo")
    await pg.click(f'{V} [data-v="next"]')
    r.eq(await pos(), "4 de 4", "Próxima foto")
    await pg.click(f'{V} [data-v="next"]')
    r.eq(await pos(), "1 de 4", "depois da última, volta para a primeira")
    names = await pg.evaluate(f"[...document.querySelectorAll('{V} .vlist a span:first-child')].map(s => s.textContent)")
    want = [i["name"] for i in r.data()["items"] if "escritorio-1.jpg" in (i.get("photos") or [])]
    r.check((await pg.text_content(f"{V} .vside h3")).strip() == "5 itens nesta foto" and names == want, f"a foto da mesa: os 5 itens dela ({names[:2]}…)")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "visualizador")
    await pg.click(f'{V} [data-v="prev"]')
    r.eq(await pos(), "4 de 4", "Foto anterior, da primeira para a última")

    # -- capa
    await pg.click(f'{V} [data-v="prev"]')
    await pg.click(f'{V} [data-v="prev"]')
    r.eq(await pos(), "2 de 4", "na foto da estante")
    await pg.click(f'{V} [data-v="cover"]')
    await pg.locator(".toast", has_text="Capa do cômodo atualizada").wait_for(timeout=6000)
    r.check(room(r)["cover"] == 1 and await pg.is_disabled(f'{V} [data-v="cover"]') and (await pg.text_content(f'{V} [data-v="cover"]')).strip() == "Capa do cômodo",
            "Usar como capa: gravada, e o botão vira Capa do cômodo, parado")
    await pg.click(f'{V} [data-v="close"]')
    await pg.wait_for_selector(V, state="detached", timeout=4000)
    r.eq((await pg.evaluate(STRIP))[2][0], "Cadeira nova", "a legenda nova aparece na faixa")
    await r.open(pg, "#/comodos", ".ilist.rooms")
    src = await pg.get_attribute('[data-room-row="escritorio"] img.thumb', "src")
    r.check(src.endswith("escritorio-2.jpg"), f"a lista de cômodos mostra a capa nova ({src})")

    # -- tirar uma foto do cômodo: pergunta; os itens continuam com ela
    await r.open(pg, "#/c/escritorio", ".rhead")
    await viewer(0)
    await pg.click(f'{V} [data-v="remove"]')
    ask = pg.locator('dialog[aria-label="Tirar a foto do cômodo?"]')
    await ask.wait_for(timeout=4000)
    r.eq(" ".join((await ask.locator(".dlg-b").text_content()).split()), "Os itens que usam esta foto continuam com ela.", "Tirar do cômodo pergunta antes e diz que os itens ficam com a foto")
    await r.shot(pg, "tirar-pergunta")
    await ask.locator('[data-r="0"]').click()
    await pg.wait_for_timeout(300)
    r.eq(len(room(r)["photos"]), 4, "Cancelar: a foto fica")
    await pg.click(f'{V} [data-v="remove"]')
    await ask.locator('[data-r="1"]').click()
    await pg.locator(".toast", has_text="Foto retirada do cômodo").wait_for(timeout=6000)
    rm = room(r)
    r.check([x["file"] for x in rm["photos"]][0] == "escritorio-2.jpg" and await pos() == "1 de 3", "a foto sai do cômodo e o visualizador segue na próxima")
    r.eq(sum(1 for i in r.data()["items"] if "escritorio-1.jpg" in (i.get("photos") or [])), 5, "os 5 itens continuam com a foto")
    r.eq(rm["photos"][rm["cover"]]["file"], "escritorio-2.jpg", "tirar uma foto antes da capa não troca a capa")
    await pg.click(f'{V} [data-v="close"]')

    # -- adicionar um item com a foto; a faixa passa a contar
    await viewer(1)
    r.eq((await pg.text_content(f"{V} .vtop .cap")).strip(), "Cadeira nova", "a foto com legenda mostra a legenda no alto")
    await pg.click(f'{V} [data-v="additem"]')
    await pg.wait_for_selector("#f-name")
    r.eq(await pg.locator('[data-slot="photos"] .ph img').count(), 1, "Adicionar item com esta foto: o editor já vem com ela")
    await pg.fill("#f-name", "Cadeira de escritório")
    await pg.fill("#f-value", "600")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("#f-name", state="detached", timeout=8000)
    await pg.wait_for_timeout(300)
    r.eq((await pg.evaluate(STRIP))[1], ["Cadeira nova", "1 item"], "a faixa conta o item novo nessa foto")

    # -- de um item da foto para a ficha dele
    await r.open(pg, "#/c/sala", ".rhead")
    await viewer(0)
    await pg.locator(f"{V} .vlist a").first.click()
    await pg.wait_for_selector("dialog.sheet h1", timeout=6000)
    r.check(pg.url.endswith("#/i/sal-001") and await pg.locator(V).count() == 0, "tocar num item da foto abre a ficha dele")
    await ctx.close()

    # -- Editar cômodo: subir, legendar e tirar; a capa acompanha a foto
    files = [x["file"] for x in room(r)["photos"]]  # estante, cadeira nova, foto 4
    r.api("PUT", "api/rooms/escritorio", {"photos": [{"file": files[0], "label": "Estante do escritório"}, {"file": files[1], "label": "Cadeira nova"},
                                                       {"file": files[2], "label": ""}], "cover": 0})
    ctx, pg = await r.page(b, "pc", "light", accent="verde")
    await r.open(pg, "#/c/escritorio", ".rhead")
    await pg.click('.rhead-actions [data-act="room-edit"]')
    await pg.wait_for_selector('[data-re="up"]')
    r.check(await pg.is_disabled('[data-re="up"][data-i="0"]'), "a primeira foto não sobe")
    widths = await pg.evaluate("[...document.querySelectorAll('[data-re-label]')].map(i => Math.round(i.getBoundingClientRect().width))")
    r.eq(len(set(widths)), 1, f"as legendas de todas as fotos com a mesma largura, alinhadas ({widths})")
    await pg.click('[data-re="up"][data-i="2"]')
    await pg.click('[data-re="up"][data-i="1"]')
    pressed = await pg.evaluate("[...document.querySelectorAll('[data-re=cover]')].map(b => b.getAttribute('aria-pressed'))")
    r.eq(pressed, ["false", "true", "false"], "subir a foto 3 duas vezes: ela vai para o começo e a capa acompanha a estante")
    await pg.fill('[data-re-label="0"]', "Janela")
    await pg.click('[data-re="rm"][data-i="2"]')
    await r.shot(pg, "editar-comodo")
    await pg.click('[data-re="save"]')
    await pg.locator(".toast", has_text="Cômodo salvo").wait_for(timeout=6000)
    rm = room(r)
    r.eq([[x["file"], x["label"]] for x in rm["photos"]] + [rm["cover"]], [[files[2], "Janela"], [files[0], "Estante do escritório"], 1],
         "Salvar grava a ordem, a legenda, a foto tirada e a capa")
    r.eq(await pg.evaluate(STRIP), [["Janela", ""], ["Estante do escritório", ""]], "a faixa fica na ordem nova")
    await viewer(0)
    v = await pg.evaluate(f"['.vimg', '.vside'].map(s => Math.round(document.querySelector('{V} ' + s).getBoundingClientRect().left))")
    r.check(v[1] > v[0], "no computador, o painel fica ao lado da foto")
    await r.shot(pg, "visualizador-computador")
    await ctx.close()
    await b.close()


main("fotos_comodo", body)
