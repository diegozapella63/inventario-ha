"""Primeiro uso, sem inventário: boas-vindas, começar do zero (primeiro cômodo e item) e importar um backup."""
import json
import os
import zipfile

from e2e_lib import OVERFLOW, TMP, helpers, main


def backup_zip() -> str:
    """Um backup como o do app: inventario.json e as fotos da casa de teste."""
    path = os.path.join(TMP, "backup-casa.zip")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("inventario.json", json.dumps(helpers.fixture_data(), ensure_ascii=False))
        for d in ("photos", "thumbs"):
            for f in sorted(os.listdir(os.path.join(helpers.FIXTURE, d))):
                z.write(os.path.join(helpers.FIXTURE, d, f), f"{d}/{f}")
    return path


async def body(r, p):
    zpath = backup_zip()
    r.start(seed=False, search=False)
    r.eq((len(r.data()["rooms"]), len(r.data()["items"])), (0, 0), "app novo: sem cômodos nem itens")
    b = await r.browser(p)

    for size, scheme in (("cel", "dark"), ("estreito", "light"), ("pc", "light")):
        ctx, pg = await r.page(b, size, scheme, accent="kraft")
        await r.open(pg, "#/", ".welcome")
        r.eq((await pg.text_content(".welcome h1")).strip(), "Vamos começar", f"[{size}] boas-vindas")
        acts = await pg.evaluate("[...document.querySelectorAll('.welcome .acts .btn')].map(b => b.textContent.trim())")
        r.eq(acts, ["Importar backup", "Começar do zero"], f"[{size}] importar ou começar do zero")
        r.check(await pg.evaluate(OVERFLOW), f"[{size}] sem rolagem para o lado")
        await r.shot(pg, f"inicio-{size}")
        await ctx.close()

    ctx, pg = await r.page(b, "cel", "dark")
    await r.open(pg, "#/comodos", "#view .empty")
    r.eq((await pg.text_content("#view .empty h2")).strip(), "Nenhum cômodo ainda", "Cômodos vazio convida a criar")
    # Adicionar sem cômodo: pede o cômodo antes
    await pg.click(".tabbar .plus")
    await pg.click('[data-go="item"]')
    await pg.wait_for_selector("#rn-name", timeout=5000)
    r.check(await pg.locator(".toast", has_text="Crie um cômodo antes").count() == 1, "Adicionar sem cômodo: cria o cômodo antes")
    await pg.click("dialog [data-x]")
    await r.open(pg, "#/", ".welcome")
    await pg.click('.welcome [data-act="room-new"]')
    await pg.wait_for_selector("#rn-name")
    await pg.fill("#rn-name", "Sala")
    r.eq(await pg.input_value("#rn-code"), "SAL", "código sugerido")
    await pg.click("dialog.modal [data-ok]")
    await pg.wait_for_selector(".rhead h1")
    await pg.click('#view .empty [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-name", "Sofá")
    await pg.fill("#f-value", "1.500")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("dialog.modal", state="detached", timeout=8000)
    await r.open(pg, "#/", ".tag")
    r.eq((await pg.text_content(".tag-value")).replace("\xa0", "").replace(" ", ""), "R$1.500", "o primeiro item já aparece no Início")
    r.eq(await pg.text_content(".tag-sub"), "1 item em 1 cômodo", "no singular")
    await r.shot(pg, "primeiro-item")
    await ctx.close()

    # outro app novo: importar o backup pelas boas-vindas (sem perguntar, não há o que trocar)
    r.app.stop()
    r.start(seed=False, search=False)
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/", ".welcome")
    async with pg.expect_file_chooser() as fc:
        await pg.click('.welcome [data-act="import-file"]')
    await (await fc.value).set_files(zpath)
    await pg.locator(".toast", has_text="Inventário importado: 38 itens em 6 cômodos, 9 fotos").wait_for(timeout=20000)
    r.eq(await pg.locator('[data-r="1"]').count(), 0, "inventário vazio: importa sem perguntar")
    await pg.wait_for_selector(".tag")
    r.eq(await pg.text_content(".tag-sub"), "38 itens em 6 cômodos", "o Início já mostra a casa importada")
    await r.open(pg, "#/i/sal-001", "dialog.sheet .gal-main img")
    ok = await pg.evaluate("document.querySelector('dialog.sheet .gal-main img').naturalWidth > 0")
    r.check(ok, "as fotos vieram junto")
    await r.shot(pg, "importado")
    await ctx.close()
    await b.close()


main("boasvindas", body)
