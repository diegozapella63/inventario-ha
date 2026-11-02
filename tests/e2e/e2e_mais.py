"""Mais > Dados: abas, exportar (CSV, JSON, ZIP), backup na pasta share, versões anteriores, importar; botões do mesmo tamanho e alinhados."""
import csv
import io
import json
import os
import zipfile

from e2e_lib import OVERFLOW, TMP, main

# botões e seleções das linhas de Mais: 280 × 44 e com a borda direita alinhada (ou a largura toda, no celular estreito)
BUTTONS = """(() => [...document.querySelectorAll('.more-panel .opts .oa > .btn:not(.icon), .more-panel .opts .oa > .select')]
  .filter(e => e.offsetParent).map(e => { const b = e.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height), Math.round(b.right)]; }))()"""


async def tab(pg, k):
    await pg.click(f'.more-tabs [data-tab="{k}"]')
    await pg.wait_for_selector(f'#mt-{k}[aria-selected="true"]')
    await pg.wait_for_timeout(500)


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="azul")
    await r.open(pg, "#/mais", ".more-tabs")
    tabs = await pg.evaluate("[...document.querySelectorAll('.more-tabs [role=tab]')].map(t => t.textContent.trim())")
    r.eq(tabs, ["Dados", "Integrações", "Aparência", "Opções"], "as quatro abas")
    r.eq((await pg.text_content(".page-sub")).replace("\xa0", " "), "38 itens e 9 fotos no inventário", "resumo no alto")
    foot = await pg.text_content(".foot")
    r.check(f"v{r.data()['version']}" in foot, f"rodapé com a versão ({foot.strip()[:40]})")
    for k in ("integracoes", "aparencia", "opcoes", "dados"):
        await tab(pg, k)
        r.check(pg.url.endswith("#/mais" if k == "dados" else f"#/mais/{k}"), f"aba {k} no endereço")
        sizes = await pg.evaluate(BUTTONS)
        if k == "aparencia":  # tema e cor: botões de escolha, sem linhas
            continue
        r.check(sizes and all(w == 280 and h == 44 for w, h, _ in sizes), f"[{k}] botões 280×44 ({sorted({(w, h) for w, h, _ in sizes})})")
        r.check(len({x for _, _, x in sizes}) == 1, f"[{k}] alinhados pela direita ({sorted({x for _, _, x in sizes})})")
        r.check(await pg.evaluate(OVERFLOW), f"[{k}] sem rolagem para o lado")
        await r.shot(pg, f"aba-{k}", full_page=True)
    # teclado nas abas
    await pg.focus("#mt-dados")
    await pg.keyboard.press("ArrowRight")
    await pg.wait_for_timeout(400)
    r.check(pg.url.endswith("#/mais/integracoes"), "seta para a direita troca de aba")
    await tab(pg, "dados")
    await ctx.close()

    # celular estreito: tudo cabe
    ctx, pg = await r.page(b, "estreito", "light")
    await r.open(pg, "#/mais", ".more-tabs")
    for k in ("dados", "integracoes", "aparencia", "opcoes"):
        await tab(pg, k)
        sizes = await pg.evaluate(BUTTONS)
        r.check(all(h == 44 for _, h, _ in sizes) and len({w for w, _, _ in sizes}) <= 1, f"[estreito {k}] botões iguais ({sorted({(w, h) for w, h, _ in sizes})})")
        r.check(await pg.evaluate(OVERFLOW), f"[estreito {k}] sem rolagem para o lado")
    await r.shot(pg, "estreito-dados", full_page=True)
    await ctx.close()

    # exportar
    ctx, pg = await r.page(b, "pc", "light")
    await r.open(pg, "#/mais", ".more-tabs")
    got = {}
    for kind in ("csv", "json", "zip"):
        async with pg.expect_download() as dl:
            await pg.click(f'[data-act="export"][data-kind="{kind}"]')
        d = await dl.value
        path = os.path.join(TMP, f"export.{kind}")
        await d.save_as(path)
        got[kind] = (d.suggested_filename, path)
    rows = list(csv.reader(io.StringIO(open(got["csv"][1], encoding="utf-8-sig").read()), delimiter=";"))
    r.check(got["csv"][0].endswith(".csv") and len(rows) == 39 and rows[0][:4] == ["Código", "Cômodo", "Zona", "Item"] and rows[1][7] == "1800,00", f"CSV: cabeçalho e 38 itens ({got['csv'][0]}, {len(rows)} linhas)")
    js = json.load(open(got["json"][1], encoding="utf-8"))
    r.check(len(js["items"]) == 38 and len(js["rooms"]) == 6, "JSON: todos os itens e cômodos")
    with zipfile.ZipFile(got["zip"][1]) as z:
        names = z.namelist()
    r.check("inventario.json" in names and sum(1 for n in names if n.startswith("photos/")) == 9, f"ZIP: dados e as 9 fotos ({len(names)} arquivos)")
    r.check(await pg.locator(".toast", has_text="Preparando o ZIP").count() == 1, "o ZIP avisa que demora um pouco")

    # backup na pasta share
    await pg.wait_for_selector('[data-act="backup-create"]')
    await pg.click('[data-act="backup-create"]')
    await pg.locator(".toast", has_text="Backup salvo").wait_for(timeout=15000)
    await pg.wait_for_selector('[data-act="backup-restore"]')
    name = await pg.get_attribute('[data-act="backup-restore"]', "data-name")
    r.check(name and name.endswith(".zip"), f"backup aparece na lista ({name})")
    await r.shot(pg, "backup")
    r.api("POST", "api/items", {"name": "Item depois do backup", "room": "sala"})
    await pg.click('[data-act="backup-restore"]')
    await pg.wait_for_selector('[data-r="1"]')
    await pg.click('[data-r="1"]')
    await pg.locator(".toast", has_text="Backup restaurado").wait_for(timeout=15000)
    r.check(r.item_named("Item depois do backup") is None and len(r.data()["items"]) == 38, "Restaurar volta ao backup")
    r.eq(await pg.text_content(".page-sub"), "38 itens e 9 fotos no inventário", "a tela já mostra o restaurado")

    # versões anteriores
    await pg.click('[data-act="versions"]')
    await pg.wait_for_selector("dialog .versions li", timeout=8000)
    rows = await pg.evaluate("[...document.querySelectorAll('dialog .versions li .ot span')].map(e => e.textContent)")
    r.check(any("antes de restaurar" in x for x in rows), f"a versão de antes de restaurar ({rows})")
    await r.shot(pg, "versoes")
    await pg.click('dialog .versions [data-ver="0"]')
    await pg.wait_for_selector('[data-r="1"]')
    await pg.click('[data-r="1"]')
    await pg.locator(".toast", has_text="Versão restaurada").wait_for(timeout=15000)
    r.check(r.item_named("Item depois do backup") is not None, "Restaurar a versão traz o item de volta")

    # importar o ZIP exportado (troca o inventário, com confirmação)
    r.api("DELETE", f"api/items/{r.data()['items'][0]['id']}")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-act="import-file"]')
    await (await fc.value).set_files(got["zip"][1])
    await pg.wait_for_selector('[data-r="1"]', timeout=15000)
    r.check("Trocar o inventário atual" in await pg.text_content("dialog[open]:last-of-type"), "importar pergunta antes de trocar")
    await r.shot(pg, "importar-confirmar")
    await pg.click('[data-r="1"]')
    await pg.locator(".toast", has_text="Inventário importado: 38 itens em 6 cômodos").wait_for(timeout=20000)
    r.eq(len(r.data()["items"]), 38, "importado")
    r.check(pg.url.endswith("#/"), f"depois de importar, vai para o Início ({pg.url.split('#')[-1]})")

    # arquivo errado
    bad = os.path.join(TMP, "lista.txt")
    with open(bad, "w") as f:
        f.write("não é backup")
    await r.open(pg, "#/mais", ".more-tabs")
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-act="import-file"]')
    await (await fc.value).set_files(bad)
    t = pg.locator(".toast", has_text="não é um backup")
    await t.wait_for(timeout=5000)
    r.check(True, "arquivo que não é backup: aviso, nada muda")
    await ctx.close()
    await b.close()


main("mais", body)
