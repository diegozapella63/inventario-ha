"""Erros e lentidão: o servidor fora do ar ao abrir (tela de erro e Tentar de novo depois que ele volta), as mensagens de cada
erro (sem conexão, reiniciando, sessão expirada, erro 500), uma gravação que falha sem perder o que foi digitado (item, mover,
excluir, cômodo, categoria, foto) e o "carregando" quando a resposta demora."""
import asyncio
import os
import socket
import urllib.parse

from e2e_lib import AppServer, OVERFLOW, helpers, main

TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".woff2": "font/woff2", ".svg": "image/svg+xml", ".png": "image/png"}
FIELDS = "['f-name', 'f-details', 'f-cat', 'f-qty', 'f-value'].map(i => document.getElementById(i).value)"


def txt(s):
    return " ".join((s or "").replace("\xa0", " ").split())


async def static(route):
    """A tela (index.html, app.js, style.css, fontes) vem do disco; só a API vai para o servidor, esteja ele no ar ou não."""
    path = urllib.parse.urlparse(route.request.url).path.lstrip("/") or "index.html"
    full = os.path.join(helpers.WEB, path)
    if path.startswith(("api/", "photos/", "thumbs/")) or not os.path.isfile(full):
        await route.continue_()
        return
    with open(full, "rb") as f:
        data = f.read()
    if path == "index.html":
        data = data.replace(b"%%V%%", b"teste")
    await route.fulfill(status=200, body=data, content_type=TYPES.get(os.path.splitext(path)[1], "application/octet-stream"))


def fail_with(status=500, body="Internal Server Error", method=None, abort=False, delay=0.0):
    async def handler(route):
        if method and route.request.method != method:
            await route.continue_()
            return
        if delay:
            await asyncio.sleep(delay)
            await route.continue_()
            return
        if abort:
            await route.abort("connectionrefused")
            return
        await route.fulfill(status=status, body=body, content_type="text/plain")
    return handler


async def body(r, p):
    r.start(search=False)
    r.api("POST", "api/items", {"name": "Cofre pequeno", "room": "escritorio", "value": 600})
    b = await r.browser(p)

    # -- servidor fora do ar ao abrir
    ctx, pg = await r.page(b, "cel", "dark", accent="amarelo")
    await ctx.route(r.base + "**", static)
    root, port = r.app.root, r.app.port
    r.app.stop(clean=False)
    # segura a porta enquanto o servidor está fora (sem escutar: a conexão é recusada), para outro teste rodando junto não pegá-la
    hold = socket.socket()
    try:
        hold.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        hold.bind(("0.0.0.0", port))
        await r.open(pg, "#/", "#view .empty")
        r.eq(txt(await pg.text_content("#view .empty h2")), "Não deu para abrir o inventário", "servidor fora do ar: a tela diz que não abriu")
        r.eq(txt(await pg.text_content("#view .empty p")), "Sem conexão com o Home Assistant. Confira a rede e tente de novo.", "e diz o que fazer")
        retry = pg.locator('#view [data-act="retry"]')
        r.check(await retry.is_visible() and txt(await retry.text_content()) == "Tentar de novo" and await pg.locator("#view .skel").count() == 0,
                "com o botão Tentar de novo, sem o esqueleto de carregando")
        r.check(await pg.evaluate(OVERFLOW), "a tela de erro cabe no celular")
        await r.shot(pg, "fora-do-ar")
        await retry.click()
        await pg.wait_for_timeout(800)
        r.check(await pg.locator('#view [data-act="retry"]').count() == 1, "Tentar de novo com o servidor ainda fora: continua a tela de erro")
    finally:
        hold.close()
    r.app = AppServer(root=root, port=port, seed=True, mock_ai=True)
    await asyncio.sleep(0.3)
    if r.app.proc.poll() is not None:
        raise RuntimeError("o servidor não voltou na mesma porta: " + r.app.logtext()[-500:])
    await pg.click('#view [data-act="retry"]')
    await pg.wait_for_selector(".tag-sub", timeout=8000)
    r.eq(txt(await pg.text_content(".tag-sub")), "39 itens em 6 cômodos", "servidor de volta: Tentar de novo abre o Início, com o que foi gravado antes")
    await pg.click('.tabbar [data-tab="search"]')
    await pg.wait_for_selector(".ssum", timeout=4000)
    r.check(True, "e o app segue normal (abas funcionam)")
    await ctx.close()

    # -- a mensagem de cada erro ao abrir
    msgs = {}
    for status in (502, 401, 500):
        ctx, pg = await r.page(b, "cel", "light")
        await pg.route("**/api/data", fail_with(status))
        await r.open(pg, "#/", "#view .empty")
        msgs[status] = txt(await pg.text_content("#view .empty p"))
        await ctx.close()
    r.eq(msgs, {502: "O app está reiniciando. Tente de novo em alguns segundos.", 401: "A sessão do Home Assistant expirou. Recarregue a página.",
                500: "Erro 500 no servidor."}, "cada erro com a sua mensagem: reiniciando (502), sessão expirada (401), erro do servidor (500)")

    # -- gravação que falha: o que foi digitado fica
    ctx, pg = await r.page(b, "pc", "light", accent="verde")
    await r.open(pg, "#/c/lavanderia", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_function("document.activeElement && document.activeElement.id === 'f-name'", timeout=3000)  # o cursor vai sozinho para o nome
    await pg.fill("#f-name", "Varal de chão")
    await pg.fill("#f-details", "Dobrável, de alumínio")
    await pg.select_option("#f-cat", "utilidades")
    await pg.fill("#f-qty", "2")
    await pg.fill("#f-value", "1.234,50")
    typed = await pg.evaluate(FIELDS)
    h = fail_with(500, method="POST")
    await pg.route("**/api/items", h)
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector('[data-slot="formerr"]:not([hidden])', timeout=5000)
    r.eq(txt(await pg.text_content('[data-slot="formerr"]')), "Erro 500 no servidor.", "erro 500 ao salvar: o aviso aparece no cadastro")
    r.check(await pg.evaluate(FIELDS) == typed and await pg.locator("#f-name").count() == 1, "o cadastro continua aberto, com tudo o que foi digitado")
    r.check(txt(await pg.text_content('[data-ed="save"]')) == "Salvar item" and await pg.is_enabled('[data-ed="save"]') and await pg.is_enabled('[data-ed="again"]'),
            "os botões de salvar voltam a funcionar (não ficam em Salvando)")
    await pg.wait_for_timeout(800)
    seen = await pg.evaluate("""(() => { const e = document.querySelector('[data-slot=formerr]').getBoundingClientRect(),
      b = document.querySelector('dialog[open] .dlg-b').getBoundingClientRect(); return e.top >= b.top - 1 && e.bottom <= b.bottom + 1; })()""")
    r.check(seen and r.item_named("Varal de chão") is None, "o cadastro rola até o aviso, e nada foi gravado")
    await r.shot(pg, "erro-500-salvar")
    await pg.unroute("**/api/items", h)
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector("#f-name", state="detached", timeout=5000)
    it = r.item_named("Varal de chão")
    r.check(it and (it["details"], it["cat"], it["qty"], it["value"]) == ("Dobrável, de alumínio", "utilidades", "2", 1234.5), "tentar de novo grava tudo certo")

    # sem conexão ao editar; valor recusado pelo servidor; item excluído em outro aparelho
    await r.open(pg, f"#/i/{it['id']}", "dialog.sheet h1")
    await pg.click('dialog.sheet [data-act="item-edit"].primary')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-name", "Varal de chão grande")
    h = fail_with(abort=True, method="PUT")
    await pg.route("**/api/items/*", h)
    await pg.click('[data-ed="save"]')
    await pg.wait_for_selector('[data-slot="formerr"]:not([hidden])', timeout=5000)
    r.check(txt(await pg.text_content('[data-slot="formerr"]')) == "Sem conexão com o Home Assistant. Confira a rede e tente de novo."
            and await pg.input_value("#f-name") == "Varal de chão grande", "sem conexão ao salvar: avisa e o nome novo continua no campo")
    await pg.unroute("**/api/items/*", h)
    await pg.fill("#f-value", "2.000.000.000")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_function("document.querySelector('[data-slot=formerr]').textContent.includes('intervalo')", timeout=5000)
    r.check(txt(await pg.text_content('[data-slot="formerr"]')) == "Valor fora do intervalo permitido." and await pg.input_value("#f-value") == "2.000.000.000",
            "valor que o servidor recusa: a mensagem do servidor, e o valor fica para corrigir")
    await pg.fill("#f-value", "150")
    r.api("DELETE", f"api/items/{it['id']}")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_function("document.querySelector('[data-slot=formerr]').textContent.includes('não existe mais')", timeout=5000)
    r.check(await pg.input_value("#f-name") == "Varal de chão grande", "item excluído em outro aparelho: avisa que não existe mais, sem apagar o que foi digitado")
    await pg.click('[data-ed="cancel"] >> nth=0')
    await pg.click('[data-r="1"]')
    await pg.wait_for_timeout(500)

    # mover, excluir, cômodo, categoria e foto com erro
    await r.open(pg, "#/i/lav-002", "dialog.sheet h1")
    h = fail_with(500, method="PUT")
    await pg.route("**/api/items/lav-002", h)
    await pg.click('dialog.sheet [data-act="item-move"]')
    await pg.select_option("#mv-room", "varanda")
    await pg.click("dialog.modal [data-ok]")
    await pg.locator(".toast.err", has_text="Erro 500").wait_for(timeout=5000)
    r.check(await pg.input_value("#mv-room") == "varanda" and next(i for i in r.data()["items"] if i["id"] == "lav-002")["room"] == "lavanderia",
            "Mover com erro: aviso, a janela fica com a escolha, e o item não muda")
    await pg.click("dialog.modal [data-x] >> nth=0")
    await pg.unroute("**/api/items/lav-002", h)
    h = fail_with(500, method="DELETE")
    await pg.route("**/api/items/lav-002", h)
    n_err = await pg.locator(".toast.err").count()
    await pg.click('dialog.sheet [data-act="item-delete"]')
    await pg.click('[data-r="1"]')
    await pg.wait_for_function(f"document.querySelectorAll('.toast.err').length > {n_err}", timeout=5000)
    r.check(await pg.locator("dialog.sheet[open]").count() == 1 and any(i["id"] == "lav-002" for i in r.data()["items"]),
            "Excluir com erro: aviso, a ficha fica e o item também")
    await pg.unroute("**/api/items/lav-002", h)
    await r.open(pg, "#/comodos", ".ilist.rooms")
    h = fail_with(500, method="POST")
    await pg.route("**/api/rooms", h)
    await pg.click('#view [data-act="room-new"]')
    await pg.fill("#rn-name", "Garagem")
    await pg.click("dialog [data-ok]")
    await pg.wait_for_selector("dialog [data-err]:not([hidden])", timeout=5000)
    r.check(txt(await pg.text_content("dialog [data-err]")) == "Erro 500 no servidor." and await pg.input_value("#rn-name") == "Garagem",
            "Novo cômodo com erro: aviso na janela, com o nome digitado")
    await pg.unroute("**/api/rooms", h)
    await pg.click("dialog [data-ok]")
    await pg.wait_for_selector(".rhead h1", timeout=5000)
    r.eq(await pg.text_content(".rhead h1"), "Garagem", "e Criar cômodo de novo funciona")
    await r.open(pg, "#/mais/opcoes", ".more-tabs")
    h = fail_with(abort=True)
    await pg.route("**/api/cats", h)
    await pg.click('[data-act="cat-new"]')
    await pg.fill("#cn-name", "Ferramentas")
    await pg.click("dialog [data-ok]")
    await pg.wait_for_selector("dialog [data-err]:not([hidden])", timeout=5000)
    r.check("Sem conexão" in await pg.text_content("dialog [data-err]") and await pg.input_value("#cn-name") == "Ferramentas", "Nova categoria sem conexão: aviso, com o nome digitado")
    await pg.unroute("**/api/cats", h)
    await pg.click("dialog [data-x] >> nth=0")
    await r.open(pg, "#/c/garagem", ".rhead")
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    h = fail_with(500)
    await pg.route("**/api/photos", h)
    async with pg.expect_file_chooser() as fc:
        await pg.click('[data-ed="upload"]')
    await (await fc.value).set_files(os.path.join(helpers.FIXTURE, "photos", "sala-1.jpg"))
    await pg.locator(".toast.err", has_text="Erro 500").wait_for(timeout=8000)
    await pg.wait_for_function("!document.querySelector('[data-slot=photos] .ph.loading')", timeout=5000)
    r.eq(await pg.locator("[data-slot=photos] .ph img").count(), 0, "foto que não subiu: aviso, e o lugar dela some")
    await pg.unroute("**/api/photos", h)
    await ctx.close()

    # -- resposta lenta: o carregando
    ctx, pg = await r.page(b, "cel", "dark")
    await pg.route("**/api/data", fail_with(delay=2.0))
    await pg.goto(r.base + "#/")
    await pg.wait_for_timeout(600)
    r.check(await pg.locator("#view .skel").count() >= 3 and await pg.locator(".tag").count() == 0, "abrindo devagar: o esqueleto de carregando no lugar do Início")
    await pg.wait_for_selector(".tag", timeout=8000)
    r.eq(await pg.locator("#view .skel").count(), 0, "a resposta chega e o Início aparece")
    await pg.unroute("**/api/data")
    await r.open(pg, "#/c/sala", ".rhead")
    await pg.route("**/api/items", fail_with(delay=1.5, method="POST"))
    await pg.click('.rhead-actions [data-act="item-new"]')
    await pg.wait_for_selector("#f-name")
    await pg.fill("#f-name", "Abajur de leitura")
    await pg.click('[data-ed="save"]')
    await pg.wait_for_timeout(300)
    r.check(txt(await pg.text_content('[data-ed="save"]')) == "Salvando" and await pg.locator('[data-ed="save"] .spin').count() == 1
            and await pg.is_disabled('[data-ed="save"]') and await pg.is_disabled('[data-ed="again"]'), "salvando devagar: Salvando com o círculo, e os botões desligados")
    await pg.evaluate("document.querySelector('[data-ed=save]').click(); document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', ctrlKey: true}))")
    await pg.wait_for_selector("#f-name", state="detached", timeout=8000)
    await pg.wait_for_timeout(500)
    r.eq(sum(1 for i in r.data()["items"] if i["name"] == "Abajur de leitura"), 1, "tocar de novo ou Ctrl+Enter enquanto salva não grava duas vezes")
    await pg.unroute("**/api/items")
    await pg.route("**/api/backups", fail_with(delay=2.0))
    await r.open(pg, "#/mais", ".more-tabs")
    r.eq(txt(await pg.text_content('[data-slot="backups"]')), "Carregando backups…", "backups devagar: Carregando backups…")
    await pg.route("**/api/history", fail_with(delay=2.0))
    await pg.click('[data-act="versions"]')
    await pg.wait_for_selector('[data-slot="versions"]')
    r.eq(txt(await pg.text_content('[data-slot="versions"]')), "Carregando…", "versões devagar: Carregando…")
    await r.shot(pg, "carregando-versoes")
    await pg.wait_for_selector('[data-slot="versions"] .opts, [data-slot="versions"] p:not(:has-text("Carregando"))', timeout=8000)
    await ctx.close()
    await b.close()


main("erros", body)
