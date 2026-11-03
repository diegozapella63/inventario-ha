"""Organizar cômodos: as setas das pontas desligadas, cada toque grava a ordem (toques seguidos entram na fila), o foco fica
na seta, Concluir, e a mesma ordem no Início, na barra lateral, no relatório, na busca, no cadastro e em outro aparelho."""
from e2e_lib import main

ROWS = "[...document.querySelectorAll('.ilist.rooms [data-room-row]')].map(e => e.dataset.roomRow)"
ARROWS = """[...document.querySelectorAll('.ilist.rooms [data-room-row]')].map(e => [e.dataset.roomRow,
  e.querySelector('[data-act=room-up]').disabled, e.querySelector('[data-act=room-down]').disabled])"""
NAMES = {"sala": "Sala de estar", "cozinha": "Cozinha", "quarto": "Quarto", "escritorio": "Escritório", "lavanderia": "Lavanderia", "varanda": "Varanda"}


def order(r):
    return [x["id"] for x in sorted(r.data()["rooms"], key=lambda x: x.get("order", 0))]


async def wait_order(r, pg, want, timeout=6000):
    for _ in range(timeout // 100):
        if order(r) == want and await pg.evaluate(ROWS) == want:
            return True
        await pg.wait_for_timeout(100)
    return False


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")
    await r.open(pg, "#/comodos", ".ilist.rooms")
    r.eq(await pg.locator(".ilist.rooms a.croom").count(), 6, "fora do Organizar, cada cômodo é um link")
    await pg.click('[data-act="rooms-organize"]')
    await pg.wait_for_selector(".rooms-hint")
    r.check((await pg.text_content('[data-act="rooms-organize"]')).strip() == "Concluir" and await pg.locator(".ilist.rooms a.croom").count() == 0,
            "Organizar: o botão vira Concluir e as linhas deixam de ser links")
    r.eq((await pg.text_content(".rooms-hint")).strip(), "A ordem vale também para o relatório.", "explica onde a ordem vale")
    arrows = await pg.evaluate(ARROWS)
    r.check(arrows[0][1] and not arrows[0][2] and arrows[-1][2] and not arrows[-1][1] and all(not u and not d for _, u, d in arrows[1:-1]),
            "a seta para cima do primeiro e a para baixo do último ficam desligadas; as outras, ligadas")
    r.eq([await pg.get_attribute('[data-act="room-up"][data-room="quarto"]', "aria-label"), await pg.get_attribute('[data-act="room-down"][data-room="quarto"]', "aria-label")],
         ["Subir Quarto", "Descer Quarto"], "cada seta diz o que faz e com qual cômodo")
    await r.shot(pg, "organizar")

    # -- uma seta por vez
    await pg.click('[data-act="room-down"][data-room="sala"]')
    want = ["cozinha", "sala", "quarto", "escritorio", "lavanderia", "varanda"]
    r.check(await wait_order(r, pg, want), "descer a Sala grava a ordem nova")
    arrows = dict((k, (u, d)) for k, u, d in await pg.evaluate(ARROWS))
    r.check(arrows["cozinha"][0] and not arrows["sala"][0], "agora a Cozinha é a primeira (sem subir) e a Sala pode subir")
    r.eq(await pg.evaluate("[document.activeElement.dataset.act, document.activeElement.dataset.room]"), ["room-down", "sala"],
         "o foco continua na seta da Sala, para tocar de novo")
    await pg.click('[data-act="room-up"][data-room="varanda"]')
    want = ["cozinha", "sala", "quarto", "escritorio", "varanda", "lavanderia"]
    r.check(await wait_order(r, pg, want), "subir a Varanda grava")
    arrows = dict((k, (u, d)) for k, u, d in await pg.evaluate(ARROWS))
    r.check(arrows["lavanderia"][1] and not arrows["varanda"][1], "a Lavanderia vira a última (sem descer)")
    # toques seguidos entram na fila
    await pg.evaluate("(() => { const b = document.querySelector('[data-act=room-down][data-room=sala]'); b.click(); b.click(); b.click(); })()")
    want = ["cozinha", "quarto", "escritorio", "varanda", "sala", "lavanderia"]
    r.check(await wait_order(r, pg, want), f"três toques seguidos descem três posições ({order(r)})")
    # o lápis abre o cômodo para editar
    await pg.click('[data-act="room-edit"][data-room="quarto"]')
    await pg.wait_for_selector("#re-name")
    r.eq(await pg.input_value("#re-name"), "Quarto", "o lápis abre Editar cômodo")
    await pg.click('[data-re="cancel"]')
    await pg.wait_for_selector("#re-name", state="detached")
    await pg.click('[data-act="rooms-organize"]')
    await pg.wait_for_selector(".rooms-hint", state="detached")
    names = await pg.evaluate("[...document.querySelectorAll('.ilist.rooms .croom .nm')].map(e => e.textContent)")
    r.eq(names, [NAMES[k] for k in want], "Concluir: a lista volta a ser de links, na ordem nova")
    # sair e voltar: não fica no Organizar
    await pg.click('[data-act="rooms-organize"]')
    await pg.click('.tabbar [data-tab="home"]')
    await pg.wait_for_selector(".tag")
    home = await pg.evaluate("[...document.querySelector('.sec .rows').querySelectorAll('.rrow .rn')].map(e => e.firstChild.textContent.trim())")
    r.eq(home, [NAMES[k] for k in want], "Início: os cômodos na ordem nova")
    await pg.click('.tabbar [data-tab="rooms"]')
    await pg.wait_for_selector(".ilist.rooms")
    r.eq(await pg.locator(".rooms-hint").count(), 0, "sair de Cômodos no meio do Organizar e voltar: lista normal")

    # -- vale para o relatório, a busca e o cadastro
    await r.open(pg, "#/relatorio", ".report")
    rep = await pg.evaluate("[...document.querySelectorAll('.rep-room h2')].map(h => h.lastChild.textContent)")
    tab = await pg.evaluate("[...document.querySelectorAll('.report > .rtable tbody tr td:first-child')].map(e => e.textContent.trim().split(' ').slice(1).join(' '))")
    r.check(rep == tab == [NAMES[k] for k in want], f"relatório: o resumo e as seções na ordem nova ({rep[:2]})")
    await r.open(pg, "#/buscar", ".sbar")
    opts = await pg.evaluate("[...document.querySelectorAll('[data-input=search-room] option')].map(o => o.value).slice(1)")
    r.eq(opts, want, "Buscar: os cômodos do filtro na ordem nova")
    await pg.click(".tabbar .plus")
    await pg.click('[data-go="item"]')
    await pg.wait_for_selector("#f-room")
    r.eq(await pg.evaluate("[...document.querySelectorAll('#f-room option')].map(o => o.value)"), want, "cadastro: os cômodos na ordem nova")
    await pg.click('[data-ed="cancel"]')
    await pg.wait_for_selector("#f-room", state="detached")

    # -- outro aparelho (outro navegador, sem nada guardado) vê a mesma ordem
    ctx2, pc = await r.page(b, "pc", "light", accent="azul", user="Ana")
    await r.open(pc, "#/", ".tag")
    side = await pc.evaluate("[...document.querySelectorAll('.side .side-room .rn')].map(e => e.textContent.trim())")
    r.eq(side[:6], [NAMES[k] for k in want], "outro aparelho, no computador: a barra lateral na ordem nova")
    r.eq(await pc.evaluate("document.querySelector('.side .side-room .mt').textContent"), "COZ", "com o código de cada cômodo")
    # e quando o outro aparelho muda a ordem, este atualiza ao voltar para o app
    await r.open(pg, "#/comodos", ".ilist.rooms")
    await r.open(pc, "#/comodos", ".ilist.rooms")
    await pc.click('[data-act="rooms-organize"]')
    await pc.click('[data-act="room-up"][data-room="sala"]')
    want = ["cozinha", "quarto", "escritorio", "sala", "varanda", "lavanderia"]
    r.check(await wait_order(r, pc, want), "no computador, a Sala sobe uma posição")
    await pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    await pg.wait_for_function(f"[...document.querySelectorAll('.ilist.rooms [data-room-row]')].map(e => e.dataset.roomRow).join() === '{','.join(want)}'", timeout=5000)
    r.check(True, "o celular, ao voltar para o app, mostra a ordem que o computador gravou")
    await r.shot(pg, "outro-aparelho")
    await ctx2.close()
    await ctx.close()
    await b.close()


main("organizar", body)
