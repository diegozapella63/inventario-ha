"""Backups na pasta share (Mais > Configurações > Dados): a lista (vários, do mais novo ao mais antigo, até 12, com data e tamanho, sem
outros arquivos da pasta), restaurar um antigo (pergunta antes, guarda uma cópia do atual), criar um novo; e a pasta
share indisponível (botão desligado, importar continua)."""
import copy
import json
import os
import shutil
import tempfile
import time
import zipfile

from e2e_lib import OVERFLOW, TMP, AppServer, helpers, main

# cada linha (1.45.1, como no ResolvIA): a data e a hora; embaixo, o tamanho e o nome (inteiro no title)
ROWS = "[...document.querySelectorAll('#p-backup .opts li')].map(li => [li.querySelector('.ot span').title, li.querySelector('b').textContent, li.querySelector('.ot span').textContent])"
LONG = "inventario-copia-da-casa-antes-da-mudanca-de-apartamento.zip"


def fmt_size(n):
    if n > 1048576:
        return f"{n / 1048576:.1f}".replace(".", ",").replace(",0", "") + " MB"
    return f"{max(1, round(n / 1024))} KB"


async def body(r, p):
    r.start(search=False)
    share = r.app.path("share")
    base = r.api("POST", "api/backups")["backup"]["name"]
    base_path = os.path.join(share, base)
    # um backup antigo com outro inventário (menos itens e um que hoje não existe)
    old = copy.deepcopy(helpers.fixture_data())
    old["items"] = [i for i in old["items"] if i["room"] != "varanda"] + [
        {"id": "sal-090", "room": "sala", "seq": 90, "name": "Item do backup antigo", "value": 250, "cat": "outros", "qty": "1", "photos": []}]
    now = time.time()
    made = []  # (nome, data)
    for k in range(1, 14):
        t = now - k * 86400 - 3600
        name = LONG if k == 2 else f"inventario-{time.strftime('%Y-%m-%d-%H%M', time.localtime(t))}.zip"
        path = os.path.join(share, name)
        if k == 6:  # o antigo, com outro inventário e um enchimento: mais de 1 MB
            with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
                z.writestr("inventario.json", json.dumps(old, ensure_ascii=False))
                z.writestr("extra/enchimento.bin", os.urandom(2_300_000))
            old_name = name
        else:
            shutil.copyfile(base_path, path)
        os.utime(path, (t, t))
        made.append((name, t))
    os.unlink(base_path)
    for junk in ("anotacoes.txt", ".inventario-x.zip.tmp", "copia.ZIP.bak"):
        helpers.write_file(os.path.join(share, junk), "não é backup")
    sizes = {n: os.path.getsize(os.path.join(share, n)) for n, _ in made}

    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", "light", accent="grafite")
    await r.open(pg, "#/config/dados", ".more-tabs")
    await pg.wait_for_selector('[data-act="backup-restore"]', timeout=10000)
    rows = await pg.evaluate(ROWS)
    r.eq(len(rows), 12, "mostra os 12 backups mais novos (eram 13)")
    r.eq([x[0] for x in rows], [n for n, _ in made[:12]], "do mais novo ao mais antigo, sem os outros arquivos da pasta")
    dates = [time.strftime("%d/%m/%Y às %H:%M", time.localtime(t)) for _, t in made[:12]]  # curta, como no ResolvIA
    r.eq([x[1] for x in rows], dates, "cada um com a data e a hora do arquivo, em destaque")
    r.eq([x[2] for x in rows], [f"{fmt_size(sizes[n])} · {n}" for n, _ in made[:12]], "embaixo, o tamanho e o nome do arquivo")
    r.eq(rows[5][2].split(" · ")[0], fmt_size(sizes[old_name]), f"um backup de mais de 1 MB mostra o tamanho em MB ({fmt_size(sizes[old_name])})")
    r.eq(rows[0][2].split(" · ")[0], fmt_size(sizes[made[0][0]]), f"um pequeno, em KB ({fmt_size(sizes[made[0][0]])})")
    btns = await pg.evaluate("[...document.querySelectorAll('#p-backup .oa .btn')].map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), Math.round(r.right)]; })")
    r.check(len({tuple(x) for x in btns}) == 1, f"os Restaurar do mesmo tamanho e alinhados ({sorted({tuple(x) for x in btns})})")
    # 1.44: os botões de Dados no padrão da família (o do GerencIA): na largura do cartão no celular, da mesma altura
    acoes = await pg.evaluate("[...document.querySelectorAll('#mp .sec-acao > .btn, #p-export .oa > .btn')].map(b => { const r = b.getBoundingClientRect(), c = b.closest('section').getBoundingClientRect(); return [Math.round(r.height), Math.round(r.width), Math.round(c.width - r.width), innerWidth]; })")
    r.check(len(acoes) >= 7 and all(h == 50 and (w == 250 if tela >= 1000 else sobra <= 60) for h, w, sobra, tela in acoes),
            f"Dados: 250 px no computador (na largura do cartão no celular), todos com 50 px de altura ({acoes[:2]})")
    await r.shot(pg, "lista", full_page=True)
    # 1.45.1: o Restaurar ao lado do texto, como no ResolvIA (antes ficava embaixo, com 280 px): do tamanho do texto, com
    # 50 px de altura, alinhado pela direita com o Criar backup, no computador e no celular; o nome comprido cortado com …
    MEDE = """() => { const m = (e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), Math.round(r.width), Math.round(r.height), Math.round(r.top)]; };
      const c = document.querySelector('[data-act="backup-create"]');
      return { criar: m(c), lista: m(document.querySelector('#p-backup .bk-lista')), linhas: [...document.querySelectorAll('#p-backup .bk-lista li')].map(li => ({ ot: m(li.querySelector('.ot')), bt: m(li.querySelector('.btn')),
        corta: (s => s.scrollWidth > s.clientWidth)(li.querySelector('.ot span')) })) }; }"""
    for tam in ("pc", "cel", "estreito"):
        c2, p2 = (None, pg) if tam == "pc" else await r.page(b, tam, "dark")
        if c2:
            await r.open(p2, "#/config/dados", ".more-tabs")
            await p2.wait_for_selector('[data-act="backup-restore"]', timeout=10000)
        t = await p2.evaluate(MEDE)
        bts = [x["bt"] for x in t["linhas"]]
        # no celular, o Criar backup é da largura do cartão: os Restaurar ficam alinhados com ele pela direita (e o texto, pela esquerda)
        r.check(len({(x[1], x[2], x[3]) for x in bts}) == 1 and bts[0][1] == t["lista"][1] and bts[0][3] == 50 and bts[0][2] < 160
                and (tam == "pc" or (bts[0][1] == t["criar"][1] and t["linhas"][0]["ot"][0] == t["criar"][0])),
                f"[{tam}] os Restaurar do tamanho do texto, com 50 px, alinhados pela direita ({t['criar']}, {t['lista']}, {bts[0]})")
        r.check(all(x["bt"][0] > x["ot"][1] and abs(x["bt"][4] - x["ot"][4]) < 20 for x in t["linhas"]), f"[{tam}] ao lado do texto, não embaixo")
        if tam != "pc":
            r.check(any(x["corta"] for x in t["linhas"]), f"[{tam}] o nome comprido cortado com … (inteiro no title)")
            if tam == "cel":
                await r.shot(p2, "lista-celular")
            await c2.close()

    # -- restaurar um antigo: pergunta; Cancelar não muda nada
    rev = r.data()["rev"]
    btn = f'[data-act="backup-restore"][data-name="{old_name}"]'
    await pg.click(btn)
    ask = pg.locator('dialog[aria-label="Restaurar este backup?"]')
    await ask.wait_for(timeout=4000)
    r.eq(" ".join((await ask.locator(".dlg-b").text_content()).split()), f"O inventário atual vira o de {old_name}. Antes, o app guarda uma cópia do atual.",
         "Restaurar pergunta antes, com o nome do backup")
    await r.shot(pg, "restaurar-pergunta")
    await ask.locator('[data-r="0"]').click()
    await pg.wait_for_timeout(300)
    r.eq(r.data()["rev"], rev, "Cancelar: nada muda")
    await pg.click(btn)
    await ask.locator('[data-r="1"]').click()
    await pg.locator(".toast", has_text="Backup restaurado").wait_for(timeout=15000)
    d = r.data()
    r.check(len(d["items"]) == len(old["items"]) and r.item_named("Item do backup antigo") is not None, f"Restaurar: o inventário é o do backup antigo ({len(d['items'])} itens)")
    n_photos = len({f for i in old["items"] for f in i["photos"]} | {f["file"] for x in old["rooms"] for f in x["photos"]})
    r.eq((await pg.text_content(".page-sub")).replace("\xa0", " "), f"{len(old['items'])} itens e {n_photos} fotos no inventário", "a tela já mostra o restaurado")
    await pg.wait_for_function("(e => e && e.title.startsWith('antes-de-restaurar-'))(document.querySelector('#p-backup .opts li:nth-child(1) .ot span'))", timeout=8000)
    r.check(True, "a cópia de antes de restaurar aparece em primeiro na lista")
    hist = r.api("GET", "api/history")["history"]
    r.check(hist and hist[0]["reason"] == "restore" and hist[0]["items"] == 38, "e uma versão de antes de restaurar, com os 38 itens")

    # -- criar um backup agora (um segundo depois da cópia de antes de restaurar: a lista ordena pela hora, em segundos)
    await pg.wait_for_timeout(1100)
    await pg.click('[data-act="backup-create"]')
    t = pg.locator(".toast", has_text="Backup salvo: inventario-")
    await t.wait_for(timeout=15000)
    created = (await t.text_content()).split("Backup salvo: ", 1)[1].strip()
    await pg.wait_for_function(f"(e => e && e.title === {json.dumps(created)})(document.querySelector('#p-backup .opts li:nth-child(1) .ot span'))", timeout=8000)
    r.check(True, f"Criar backup: o novo aparece em primeiro ({created})")
    with zipfile.ZipFile(os.path.join(share, created)) as z:
        names = z.namelist()
        inside = json.loads(z.read("inventario.json"))
    r.check(len(inside["items"]) == len(old["items"]) and {"inventario.csv", "LEIA-ME.txt"} <= set(names), "com o inventário de agora, a planilha e o LEIA-ME")
    await ctx.close()

    # -- celular estreito: o nome comprido quebra sem passar da tela
    ctx, pg = await r.page(b, "estreito", "dark", accent="verde")
    await r.open(pg, "#/config/dados", ".more-tabs")
    await pg.wait_for_selector(f'[data-name="{LONG}"]', timeout=10000)
    r.check(await pg.evaluate(OVERFLOW), "celular de 320 px: nome comprido sem rolagem para o lado")
    await pg.locator(f'[data-name="{LONG}"]').scroll_into_view_if_needed()
    await r.shot(pg, "estreito-nome-comprido")
    await ctx.close()

    # -- pasta share indisponível: a pasta /share não está montada (o caminho até ela não leva a lugar nenhum)
    tmp = tempfile.mkdtemp(prefix="sem-share-", dir=TMP)
    os.symlink(os.path.join(tmp, "nao-montada"), os.path.join(tmp, "share"))
    app = AppServer(seed=True, env={"INV_SHARE": os.path.join(tmp, "share", "inventario")})
    try:
        ctx, pg = await r.page(b, "cel", "light", accent="azul")
        await pg.goto(app.base + "#/config/dados")
        await pg.wait_for_selector('[data-act="backup-create"]', timeout=10000)
        r.eq(" ".join((await pg.text_content("#p-backup .help")).split()), "A pasta share não está disponível.", "sem a pasta share: diz isso")
        r.check(await pg.is_disabled('[data-act="backup-create"]'), "e Criar backup fica desligado")
        r.eq(await pg.locator('[data-act="backup-restore"]').count(), 0, "sem backups na lista")
        st, _, out = app.post("api/backups")
        r.eq((st, out.get("error")), (500, "A pasta share não está disponível para o app."), "o servidor também recusa criar backup")
        await r.shot(pg, "sem-share")
        # importar continua: a cópia de antes fica nas versões
        js = os.path.join(tmp, "inventario.json")
        helpers.write_file(js, json.dumps(old, ensure_ascii=False))
        async with pg.expect_file_chooser() as fc:
            await pg.click('[data-act="import-file"]')
        await (await fc.value).set_files(js)
        await pg.wait_for_selector('dialog[aria-label="Trocar o inventário atual?"] [data-r="1"]', timeout=15000)
        await pg.click('dialog[aria-label="Trocar o inventário atual?"] [data-r="1"]')
        await pg.locator(".toast", has_text="Inventário importado").wait_for(timeout=15000)
        hist = app.ok("GET", "api/history")["history"]
        r.check(len(app.data()["items"]) == len(old["items"]) and hist and hist[0]["reason"] == "import", "sem a pasta share, importar continua (a cópia fica nas versões)")
        await ctx.close()
    finally:
        app.stop()

    # -- share/inventario é um arquivo (e não uma pasta)
    helpers.write_file(os.path.join(tmp, "inventario"), "não é pasta")
    app = AppServer(seed=True, env={"INV_SHARE": os.path.join(tmp, "inventario")})
    try:
        ctx, pg = await r.page(b, "cel", "light")
        await pg.goto(app.base + "#/config/dados")
        await pg.wait_for_function("(e => e && !e.textContent.includes('Carregando'))(document.querySelector('[data-slot=backups]'))", timeout=10000)
        txt = " ".join((await pg.text_content('[data-slot="backups"]')).split())
        await r.shot(pg, "share-arquivo")
        r.check("Erro interno" not in txt, f"share/inventario sendo um arquivo: um aviso, sem Erro interno ({txt[:60]})")
        await ctx.close()
    finally:
        app.stop()
        shutil.rmtree(tmp, ignore_errors=True)
    await b.close()


main("backups", body)
