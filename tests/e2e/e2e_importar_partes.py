"""Importar um backup em partes (Mais > Configurações > Dados > Importar): vários arquivos de uma vez no seletor, na ordem das partes,
com o progresso do envio; uma parte sem o inventário só traz fotos; cancelar no meio pergunta antes, e nada muda
(ou, em partes, o que já chegou fica)."""
import asyncio
import copy
import json
import os
import re
import shutil
import zipfile

from e2e_lib import OVERFLOW, TMP, helpers, main

DIR = os.path.join(TMP, "importar-partes")
IMPORT_DLG = 'dialog[aria-label="Importando inventário"]'
SAMPLE = """(d => d && [d.querySelector('[data-name]').textContent, d.querySelector('[data-st]').textContent,
  +d.querySelector('.prog').getAttribute('aria-valuenow')])(document.querySelector('dialog[aria-label="Importando inventário"]'))"""


def make_zip(name, files: dict, big: int = 0) -> str:
    """Um .zip com estes arquivos (e, se `big`, um enchimento de `big` MB que não comprime, para o envio ir em várias partes)."""
    path = os.path.join(DIR, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        for n, data in files.items():
            z.writestr(n, data)
        if big:
            z.writestr("thumbs/enchimento.jpg", os.urandom(big * 1024 * 1024))
    return path


def inventory(extra_items: list) -> bytes:
    d = copy.deepcopy(helpers.fixture_data())
    d["items"] += extra_items
    return json.dumps(d, ensure_ascii=False).encode()


def item(iid, room, seq, name, photos):
    return {"id": iid, "room": room, "seq": seq, "name": name, "details": "", "zone": "", "cat": "outros", "qty": "1", "value": 900,
            "photos": photos, "source": "manual", "createdAt": "2026-10-01T10:00:00-03:00", "updatedAt": "2026-10-01T10:00:00-03:00"}


async def body(r, p):
    os.makedirs(DIR, exist_ok=True)
    r.start(search=False)
    jpg = helpers.fixture_photo("varanda-1.jpg")
    # backup em 3 partes: só a 1 tem o inventário; a 2 é grande (vai em várias partes do envio)
    p1 = make_zip("inventario-parte1.zip", {"inventario.json": inventory([item("var-900", "varanda", 4, "Bicicleta ergométrica", ["parte2-bike.jpg"])]),
                                            "photos/sala-1.jpg": helpers.fixture_photo("sala-1.jpg"), "photos/parte1-a.jpg": jpg})
    p2 = make_zip("inventario-parte2.zip", {"photos/parte2-bike.jpg": jpg, "thumbs/parte2-bike.jpg": jpg}, big=9)
    p3 = make_zip("inventario-parte3.zip", {"photos/parte3-a.jpg": jpg})
    only_photos = make_zip("fotos-da-varanda.zip", {"photos/varanda-extra.jpg": jpg, "thumbs/varanda-extra.jpg": jpg})
    big_photos = make_zip("fotos-grandes.zip", {"photos/grande-a.jpg": jpg}, big=13)
    b1 = make_zip("outro-parte1.zip", {"inventario.json": inventory([item("var-901", "varanda", 4, "Rede de descanso", []), item("var-902", "varanda", 5, "Churrasqueira", [])])})
    b2 = make_zip("outro-parte2.zip", {"photos/outro-b.jpg": jpg}, big=13)

    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", "light", accent="coral")
    delay = {"s": 0.0}

    async def slow(route):
        if route.request.method == "PUT" and delay["s"]:
            await asyncio.sleep(delay["s"])
        await route.continue_()
    await pg.route(lambda u: "/api/upload/" in u, slow)
    starts = []
    pg.on("request", lambda q: starts.append(q.post_data_json.get("name")) if q.url.endswith("/api/upload") and q.method == "POST" else None)

    async def choose(*paths):
        await r.open(pg, "#/config/dados", ".more-tabs")
        async with pg.expect_file_chooser() as fc:
            await pg.click('[data-act="import-file"]')
        chooser = await fc.value
        if not starts:
            r.check(chooser.is_multiple(), "o seletor aceita vários arquivos de uma vez")
        await chooser.set_files(list(paths))
        await pg.wait_for_selector(IMPORT_DLG, timeout=8000)

    async def confirm_replace():
        await pg.wait_for_selector('dialog[aria-label="Trocar o inventário atual?"]', timeout=20000)
        return " ".join((await pg.text_content('dialog[aria-label="Trocar o inventário atual?"] .dlg-b')).split())

    # -- as 3 partes de uma vez, escolhidas fora de ordem
    delay["s"] = 0.5
    await choose(p3, p1, p2)
    txt = await confirm_replace()
    r.eq(txt, "O inventário de agora (38 itens) vira o de inventario-parte1.zip (39 itens em 6 cômodos). Antes, o app guarda uma cópia do atual.",
         "a parte com o inventário pergunta antes de trocar, com os números")
    await r.shot(pg, "partes-trocar")
    await pg.click('[data-r="1"]')
    seen = []
    while await pg.locator(IMPORT_DLG).count():
        try:
            s = await pg.evaluate(SAMPLE)
            if s and (not seen or s != seen[-1]):
                seen.append(s)
            if s and "parte2" in s[0] and "enviando 4,0" in s[1] and not os.path.exists(r.shot_path("partes-progresso")):
                await r.shot(pg, "partes-progresso")
        except Exception:  # noqa: BLE001  (a janela fechou no meio da leitura)
            pass
        await pg.wait_for_timeout(100)
    r.eq(starts[:3], ["inventario-parte1.zip", "inventario-parte2.zip", "inventario-parte3.zip"], "envia na ordem das partes, começando pela 1")
    st = [x[1] for x in seen]
    r.check(any(re.fullmatch(r"Arquivo 2 de 3: enviando [48],0 de 9,\d MB", x) for x in st), f"o progresso diz o arquivo e quanto já foi ({[x for x in st if 'Arquivo 2' in x][:3]})")
    r.check(any(x == "Arquivo 2 de 3: guardando as fotos…" for x in st) and any(x == "Arquivo 1 de 3: restaurando itens e fotos…" for x in st),
            "e o que está fazendo: restaurando a parte 1, guardando as fotos das outras")
    vals = [x[2] for x in seen]
    r.check(vals == sorted(vals) and vals[-1] >= 90 and len(set(vals)) >= 3, f"a barra só anda para a frente ({vals})")
    r.check({"inventario-parte1.zip", "inventario-parte2.zip", "inventario-parte3.zip"} <= {x[0] for x in seen}, "o nome de cada arquivo aparece enquanto vai")
    await pg.locator(".toast", has_text="Inventário importado").wait_for(timeout=8000)
    r.eq((await pg.text_content(".toast .tmsg")).strip(), "Inventário importado: 39 itens em 6 cômodos, 3 fotos", "no fim: itens, cômodos e as fotos novas")
    bike = r.item_named("Bicicleta ergométrica")
    st_code = r.app.get("thumbs/parte2-bike.jpg")[0]
    r.check(bike is not None and st_code == 200, f"o item da parte 1 tem a foto que veio na parte 2 ({st_code})")
    hist = r.api("GET", "api/history")["history"]
    r.check(any(v["reason"] == "import" and v["items"] == 38 for v in hist), "antes, uma versão de antes de importar, com os 38 itens")
    r.eq([n for n in os.listdir(r.app.path("data", "tmp")) if n.startswith("upload-")], [], "não sobra envio pela metade")
    delay["s"] = 0

    # -- uma parte sem o inventário: só fotos, sem perguntar
    n = len(r.data()["items"])
    await choose(only_photos)
    await pg.locator(".toast", has_text="ao inventário").wait_for(timeout=15000)
    r.eq(await pg.locator('dialog[aria-label="Trocar o inventário atual?"]').count(), 0, "só fotos: não pergunta nada")
    r.eq((await pg.text_content(".toast .tmsg")).strip(), "1 foto adicionada ao inventário", "e conta a foto nova")
    r.eq(len(r.data()["items"]), n, "os itens não mudam")
    await choose(only_photos)
    await pg.locator(".toast", has_text="já estavam").wait_for(timeout=15000)
    r.eq((await pg.text_content(".toast .tmsg")).strip(), "As fotos desse arquivo já estavam no inventário.", "a mesma parte de novo: as fotos já estavam")

    # -- Cancelar na pergunta de trocar: nada muda
    before = r.data()["rev"]
    await choose(b1)
    await confirm_replace()
    await pg.click('[data-r="0"]')
    await pg.locator(".toast", has_text="Importação cancelada").wait_for(timeout=8000)
    r.eq((await pg.text_content(".toast .tmsg")).strip(), "Importação cancelada. Nada mudou no inventário.", "Cancelar em Trocar o inventário: nada muda")
    r.eq((r.data()["rev"], r.item_named("Rede de descanso")), (before, None), "e o inventário é o mesmo")

    # -- cancelar no meio do envio de um arquivo grande: pergunta; Continuar segue; Cancelar importação para
    delay["s"] = 1.5
    await choose(big_photos)
    await pg.wait_for_function("(e => e && e.textContent.includes('enviando'))(document.querySelector('[data-st]'))", timeout=10000)
    await pg.click(f"{IMPORT_DLG} [data-x]")
    ask = pg.locator('dialog[aria-label="Cancelar a importação?"]')
    await ask.wait_for(timeout=4000)
    r.eq(" ".join((await ask.locator(".dlg-b").text_content()).split()), "O envio para no ponto em que está e nada muda no inventário.", "Cancelar no meio pergunta antes")
    r.eq([(await ask.locator('[data-r="0"]').text_content()).strip(), (await ask.locator('[data-r="1"]').text_content()).strip()], ["Continuar", "Cancelar importação"], "Continuar ou Cancelar importação")
    await r.shot(pg, "cancelar-pergunta")
    await ask.locator('[data-r="0"]').click()
    await pg.wait_for_timeout(300)
    r.eq(await pg.locator(IMPORT_DLG).count(), 1, "Continuar: o envio segue")
    await pg.click(f"{IMPORT_DLG} [data-x]")
    await ask.locator('[data-r="1"]').click()
    await pg.locator(".toast", has_text="Importação cancelada").wait_for(timeout=10000)
    r.check(not os.path.exists(r.app.path("data", "photos", "grande-a.jpg")), "Cancelar importação: a foto do arquivo não entra")
    await pg.wait_for_timeout(500)
    r.eq([n for n in os.listdir(r.app.path("data", "tmp")) if n.startswith("upload-")], [], "e o pedaço enviado é apagado")

    # -- em partes, cancelar na parte 2: a parte 1 já importada fica
    await choose(b2, b1)
    await confirm_replace()
    await pg.click('[data-r="1"]')
    await pg.wait_for_function("(e => e && e.textContent.startsWith('Arquivo 2 de 2: enviando'))(document.querySelector('[data-st]'))", timeout=20000)
    await pg.click(f"{IMPORT_DLG} [data-x]")
    await ask.wait_for(timeout=4000)
    r.eq(" ".join((await ask.locator(".dlg-b").text_content()).split()), "O envio para no ponto em que está. Os arquivos que já terminaram continuam importados.",
         "em partes: avisa que o que já terminou fica")
    await ask.locator('[data-r="1"]').click()
    await pg.locator(".toast", has_text="Importação interrompida").wait_for(timeout=10000)
    r.eq((await pg.text_content(".toast .tmsg")).strip(), "Importação interrompida. O que já tinha chegado ficou salvo.", "interrompida: o que chegou ficou")
    r.check(r.item_named("Rede de descanso") is not None and not os.path.exists(r.app.path("data", "photos", "outro-b.jpg")), "a parte 1 entrou; a 2, não")
    await r.open(pg, "#/", ".tag")
    r.check("40 itens" in await pg.text_content(".tag-sub"), "e a tela já mostra o inventário novo")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await ctx.close()
    await b.close()
    shutil.rmtree(DIR, ignore_errors=True)  # os arquivos grandes de teste


main("importar_partes", body)
