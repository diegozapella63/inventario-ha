"""Mais > Configurações > Dados > Versões anteriores: nenhuma no começo; a cópia automática (uma a cada 10 minutos de uso); as de antes
de restaurar e de antes de importar, com o motivo, a data e o número de itens; restaurar cada uma (pergunta antes,
guarda uma cópia do atual e ficam só as 3 mais recentes)."""
import copy
import json
import os
import time

from e2e_lib import OVERFLOW, TMP, helpers, main

ROWS = """[...document.querySelectorAll('dialog .versions li')].map(li => [li.querySelector('b').textContent,
  li.querySelector('.ot span').textContent.split(' · ').slice(1).join(' · ')])"""
DLG = 'dialog[aria-label="Versões anteriores"]'
ASK = 'dialog[aria-label="Restaurar esta versão?"]'


async def body(r, p):
    r.start(search=False)
    hist_dir = r.app.path("data", "history")
    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", "light", accent="rosa")

    async def versions():
        await r.open(pg, "#/config/dados", ".more-tabs")
        await pg.click('[data-act="versions"]')
        await pg.wait_for_function(f"(e => e && !e.textContent.includes('Carregando'))(document.querySelector('{DLG} [data-slot=versions]'))", timeout=8000)
        return await pg.evaluate(ROWS)

    async def restore(i, items):
        await pg.click(f'{DLG} [data-ver="{i}"]')
        await pg.locator(ASK).wait_for(timeout=4000)
        await pg.click(f'{ASK} [data-r="1"]')
        await pg.locator(".toast", has_text="Versão restaurada").wait_for(timeout=10000)
        await pg.wait_for_selector(DLG, state="detached", timeout=4000)
        await pg.wait_for_timeout(1100)  # a próxima cópia ganha outro nome (o nome vem da hora, em segundos)
        return len(r.data()["items"]) == items

    # -- nenhuma ainda
    r.eq(await versions(), [], "app novo: nenhuma versão na lista")
    r.eq((await pg.text_content(f"{DLG} .dlg-b")).strip(), "Ainda não há versões anteriores.", "e diz que ainda não há")
    await r.shot(pg, "nenhuma")
    await pg.click(f"{DLG} [data-x]")
    await pg.wait_for_selector(DLG, state="detached", timeout=4000)
    r.check(True, "o X fecha a lista")

    # -- a primeira mudança guarda uma cópia automática; a segunda, logo depois, não
    r.api("POST", "api/items", {"name": "Primeiro item novo", "room": "sala"})
    rows = await versions()
    r.eq([x[1] for x in rows], ["38 itens · automática"], "a primeira mudança guarda uma cópia automática de antes dela")
    await pg.click(f"{DLG} [data-x]")
    r.api("POST", "api/items", {"name": "Segundo item novo", "room": "sala"})
    r.eq(len(await versions()), 1, "outra mudança logo depois não guarda outra (uma a cada 10 minutos)")
    await pg.click(f"{DLG} [data-x]")

    # -- duas cópias antigas: uma de antes de restaurar e outra de antes de importar
    fx = helpers.fixture_data()
    olds = []
    for days, reason, items in ((8, "restore", [i for i in fx["items"] if i["room"] not in ("lavanderia", "varanda")]), (15, "import", fx["items"][:25])):
        t = time.time() - days * 86400
        name = f"inventario-{time.strftime('%Y%m%d-%H%M%S', time.localtime(t))}.json"
        d = copy.deepcopy(fx)
        d["items"] = items
        helpers.write_file(os.path.join(hist_dir, name), json.dumps(d, ensure_ascii=False))
        os.utime(os.path.join(hist_dir, name), (t, t))
        olds.append((name, reason, t))
    helpers.write_file(os.path.join(hist_dir, "motivos.json"), json.dumps({n: why for n, why, _ in olds}))
    rows = await versions()
    r.eq([x[1] for x in rows], ["38 itens · automática", "30 itens · antes de restaurar", "25 itens · antes de importar"],
         "três versões, da mais nova à mais antiga, com os itens e o motivo")
    dates = await pg.evaluate("(ts) => ts.map(t => new Intl.DateTimeFormat('pt-BR', {day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'}).format(new Date(t * 1000)))",
                              [t for _, _, t in olds])
    r.eq([x[0] for x in rows[1:]], dates, "cada uma com a data e a hora da cópia")
    when = await pg.evaluate("[...document.querySelectorAll('dialog .versions li .ot span')].map(s => s.textContent.split(' · ')[0])")
    r.check(when[0] in ("agora", "há 1 minuto") and "de 20" in when[1], f"quanto tempo faz: agora, ou a data quando passou de uma semana ({when[:2]})")
    btns = await pg.evaluate(f"[...document.querySelectorAll('{DLG} [data-ver]')].map(b => b.textContent.trim())")
    r.eq(btns, ["Restaurar"] * 3, "cada uma tem o seu Restaurar")
    await r.shot(pg, "tres-versoes")

    # -- restaurar a mais antiga (antes de importar): pergunta, e Cancelar não muda nada
    rev = r.data()["rev"]
    await pg.click(f'{DLG} [data-ver="2"]')
    await pg.locator(ASK).wait_for(timeout=4000)
    txt = " ".join((await pg.text_content(f"{ASK} .dlg-b")).split())
    r.eq(txt, f"O inventário volta a ser o de {dates[1]}, com 25 itens em 6 cômodos. Antes, o app guarda uma cópia do atual.", "Restaurar pergunta antes, com a data e os números")
    await r.shot(pg, "restaurar-pergunta")
    await pg.click(f'{ASK} [data-r="0"]')
    await pg.wait_for_timeout(300)
    r.check(r.data()["rev"] == rev and await pg.locator(DLG).count() == 1, "Cancelar: nada muda e a lista continua aberta")
    r.check(await restore(2, 25), "Restaurar a de antes de importar: volta aos 25 itens, e a lista fecha")
    r.eq((await pg.text_content(".page-sub")).split(" e ")[0], "25 itens", "a tela já mostra a versão restaurada")
    rows = await versions()
    r.eq([x[1] for x in rows], ["40 itens · antes de restaurar", "38 itens · automática", "30 itens · antes de restaurar"],
         "guardou o de antes (40 itens) e ficaram só as 3 mais recentes")

    # -- restaurar a de antes de restaurar e depois a automática
    r.check(await restore(2, 30), "Restaurar a de antes de restaurar: 30 itens")
    rows = await versions()
    r.eq([x[1] for x in rows], ["25 itens · antes de restaurar", "40 itens · antes de restaurar", "38 itens · automática"], "a lista anda: a nova cópia em primeiro")
    r.check(await restore(2, 38), "Restaurar a automática: os 38 itens")
    r.check(r.item_named("Primeiro item novo") is None and r.item_named("Segundo item novo") is None, "sem os itens criados depois dela")
    rows = await versions()
    r.eq([x[1] for x in rows], ["30 itens · antes de restaurar", "25 itens · antes de restaurar", "40 itens · antes de restaurar"], "dá para voltar a qualquer uma das 3")
    await pg.click(f"{DLG} [data-x]")

    # -- importar guarda uma de antes de importar
    js = os.path.join(TMP, "versoes-importar.json")
    d = copy.deepcopy(fx)
    d["items"] = d["items"][:10]
    helpers.write_file(js, json.dumps(d, ensure_ascii=False))
    await r.open(pg, "#/config/dados", ".more-tabs")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-act="import-file"]')
    await (await fc.value).set_files(js)
    await pg.wait_for_selector('dialog[aria-label="Trocar o inventário atual?"] [data-r="1"]', timeout=15000)
    await pg.click('dialog[aria-label="Trocar o inventário atual?"] [data-r="1"]')
    await pg.locator(".toast", has_text="Inventário importado").wait_for(timeout=15000)
    rows = await versions()
    r.eq(rows[0][1], "38 itens · antes de importar", "importar guarda uma versão de antes de importar")
    await ctx.close()

    # -- celular: a lista cabe
    ctx, pg = await r.page(b, "estreito", "dark", accent="azul")
    await r.open(pg, "#/config/dados", ".more-tabs")
    await pg.click('[data-act="versions"]')
    await pg.wait_for_selector(f"{DLG} .versions li", timeout=8000)
    r.check(await pg.evaluate(OVERFLOW), "celular de 320 px: a lista de versões sem rolagem para o lado")
    await r.shot(pg, "estreito")
    await ctx.close()
    await b.close()


main("versoes", body)
