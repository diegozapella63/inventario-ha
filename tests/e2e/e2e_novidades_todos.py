"""Novidades (no menu Mais): só Eletrônicos, sem escolher categorias; conferir todos (a IA escolhe, entre os eletrônicos, o que vale conferir),
progresso e Parar, a lista com recall primeiro, abrir um item, os deixados de fora, item de outra categoria fora da lista,
Limpar novidades com confirmação e a aba some com a IA desligada."""
from e2e_lib import OVERFLOW, main

ROWS = "[...document.querySelectorAll('#p-news-list > div > .nlist .nrow')].map(b => [b.querySelector('b').textContent, b.querySelector('.nm').textContent, [...b.querySelectorAll('.pill')].map(p => p.textContent)])"


async def body(r, p):
    r.start(search=False)
    for room, name in (("quarto", "Lâmpada inteligente Wi-Fi LX10"), ("sala", "Lâmpadas inteligentes Wi-Fi LX10")):  # o mesmo equipamento em 2 cômodos
        r.api("POST", "api/items", {"room": room, "name": name, "cat": "eletronicos", "value": 90})
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="laranja")
    await r.open(pg, "#/novidades", "#p-news")
    await pg.wait_for_selector('[data-slot="news-list"] p, #p-news-list .nlist', timeout=8000)
    r.eq((await pg.text_content(".page-title")).strip(), "Novidades", "Novidades numa tela própria, aberta pelo endereço")
    r.eq(await pg.locator("#view .more-tabs").count(), 0, "sem as abas de configurações")
    r.eq(await pg.locator("#view .chip, #p-news-cats").count(), 0, "sem escolher categorias")
    r.check("dos eletrônicos" in await pg.text_content("#p-news .lead"), "diz que é dos eletrônicos")
    r.check("Toque em Conferir novidades" in await pg.text_content('[data-slot="news-list"]'), "antes da primeira vez, diz o que fazer")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "antes", full_page=True)

    # conferir todos
    await pg.click('[data-act="news-all"]')
    await pg.wait_for_selector(".njob .prog", timeout=8000)
    r.check(await pg.is_disabled('[data-act="news-all"]'), "enquanto confere, o botão fica desligado")
    await pg.wait_for_function("document.querySelector('.njob span:nth-child(2)') && /Conferindo \\d+ de \\d+/.test(document.querySelector('.njob').textContent)", timeout=10000)
    r.check(True, "mostra quantos já foram e qual está sendo conferido")
    await r.shot(pg, "conferindo")
    await pg.wait_for_selector("#p-news-list .nlist .nrow", timeout=60000)
    await pg.locator(".toast", has_text="Conferidos").wait_for(timeout=10000)
    rows = await pg.evaluate(ROWS)
    nomes = [x[0] for x in rows]
    r.check("Smart TV 55 polegadas" in nomes and "Notebook 14 polegadas" in nomes, f"a IA escolheu os aparelhos ({len(nomes)})")
    r.check(not any(n in nomes for n in ("Geladeira frost free inox", "Fruteira de madeira", "Sofá de 3 lugares cinza-azulado")),
            "só eletrônicos: sem geladeira, fruteira nem sofá")
    r.check(all("novidades" in x[1] and "hoje" in x[1] for x in rows), "cada um com quantas novidades e quando")
    lx = [x for x in rows if "LX10" in x[0]]
    r.eq([x[0] for x in lx], ["Lâmpada inteligente Wi-Fi LX10"], "o mesmo equipamento em dois cômodos é uma linha só, com o nome no singular")
    r.check(lx and lx[0][1].startswith("2 cômodos · "), f"e diz em quantos cômodos está ({lx[0][1] if lx else ''})")
    r.eq(r.api("GET", "api/ai/usage")["today"]["kinds"].get("novidades"), len(rows), "uma busca por equipamento, não por item")
    lx_ids = [i["id"] for i in r.data()["items"] if "LX10" in i["name"]]
    r.check(all(r.api("GET", f"api/news?item={i}").get("news") for i in lx_ids), "e o resultado vale para os dois itens")
    r.check(all(x[2] == ["3"] for x in rows), f"o número de novidades ao lado ({rows[0][2]})")
    fora = await pg.text_content(".news-out summary")
    r.check(fora.startswith("Deixados de fora pela IA ("), f"os que a IA deixou de fora ficam recolhidos ({fora.strip()})")
    foot = await pg.text_content('[data-slot="news-job"]')
    r.check("Conferido hoje" in foot and "com novidades" in foot, f"resumo da última conferência ({foot.strip()})")
    r.check(await pg.is_enabled('[data-act="news-all"]'), "o botão volta")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "depois", full_page=True)

    # abrir um da lista: o que já foi conferido, sem chamar a IA
    sent = []
    pg.on("request", lambda q: sent.append(q.url) if q.method == "POST" and "/api/news" in q.url else None)
    await pg.locator(".nrow", has_text="Smart TV 55 polegadas").first.click()
    await pg.wait_for_selector("dialog.modal .news li", timeout=4000)
    r.eq(sent, [], "abrir um item mostra o resultado guardado, sem chamar a IA")
    r.check("Buscado hoje" in await pg.text_content(".news-foot"), "com a data")
    await pg.click("dialog.modal .dlg-h [data-x]")
    await pg.wait_for_timeout(300)

    # os deixados de fora: dá para conferir um por um
    await pg.click(".news-out summary")
    out_rows = pg.locator(".news-out .nrow")
    r.check(await out_rows.count() >= 1, "abre a lista dos deixados de fora")
    nome = (await out_rows.first.locator("b").text_content()).strip()
    r.check("Ainda não conferido" in await out_rows.first.text_content(), "ainda não conferido")
    await out_rows.first.click()
    await pg.wait_for_selector("dialog.modal .news li", timeout=10000)
    r.check(len(sent) == 1, f"um deixado de fora pode ser conferido sozinho ({nome})")
    await pg.click("dialog.modal .dlg-h [data-x]")
    await pg.wait_for_timeout(500)
    r.check("novidades" in await pg.locator(".news-out .nrow", has_text=nome).first.text_content(), "e a lista já mostra o resultado")

    # de novo na mesma semana: nada a conferir
    await pg.click('[data-act="news-all"]')
    await pg.locator(".toast", has_text="Tudo conferido nos últimos 7 dias").wait_for(timeout=15000)
    r.check(True, "conferir de novo na mesma semana não gasta a IA")

    # um item de outra categoria conferido pela ficha não entra na lista (só eletrônicos)
    jid = r.api("POST", "api/news", {"item": "coz-004"})["id"]
    for _ in range(50):
        if r.api("GET", f"api/news/{jid}")["stage"] != "busy":
            break
        await pg.wait_for_timeout(200)
    r.check("coz-004" in r.api("GET", "api/news")["itens"], "a geladeira foi conferida pela ficha")
    await r.open(pg, "#/novidades", "#p-news-list .nlist")
    todos = await pg.evaluate("[...document.querySelectorAll('#p-news-list .nrow b')].map(b => b.textContent)")
    r.check("Geladeira frost free inox" not in todos and "Smart TV 55 polegadas" in todos, "mas não entra na lista: só eletrônicos")
    r.eq(await pg.locator("#view .chip").count(), 0, "e continua sem escolher categorias")

    # Limpar novidades, com confirmação
    await pg.wait_for_selector("#p-news-list .nlist .nrow", timeout=8000)
    clear = pg.locator('[data-act="news-clear"]')
    r.eq((await clear.text_content()).strip(), "Limpar novidades", "o botão Limpar novidades")
    w = await pg.evaluate("[...document.querySelectorAll('#p-news .oa .btn')].map(b => Math.round(b.getBoundingClientRect().width))")
    r.check(len(set(w)) == 1, f"os dois botões com a mesma largura ({w})")
    await clear.click()
    await pg.wait_for_selector("dialog.modal [data-r]", timeout=4000)
    r.eq((await pg.text_content("dialog.modal h2")).strip(), "Limpar as novidades?", "pede confirmação")
    await r.shot(pg, "limpar")
    await pg.click('dialog.modal [data-r="0"]')
    await pg.wait_for_timeout(400)
    r.check(len(r.api("GET", "api/news")["itens"]) > 0 and await pg.locator("#p-news-list .nlist .nrow").count() > 0, "Cancelar não apaga nada")
    rev = r.api("GET", "api/rev")["rev"]
    await clear.click()
    await pg.wait_for_selector("dialog.modal [data-r]", timeout=4000)
    await pg.click('dialog.modal [data-r="1"]')
    await pg.locator(".toast", has_text="Novidades limpas").wait_for(timeout=5000)
    ov = r.api("GET", "api/news")
    r.check(ov["itens"] == {} and ov["triagem"] == {} and ov["ultima"] is None, "Limpar apaga as novidades e as escolhas da IA")
    r.eq(r.api("GET", "api/rev")["rev"], rev, "o inventário não muda")
    r.check("Toque em Conferir novidades" in await pg.text_content('[data-slot="news-list"]'), "a lista volta ao começo")
    r.eq((await pg.text_content('[data-slot="news-job"]')).strip(), "", "sem o resumo da última conferência")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "limpo", full_page=True)
    await ctx.close()

    # Parar no meio: o que já foi conferido fica
    app2 = r.app
    r.app = None
    r.start(search=False)
    ctx, pg = await r.page(b, "estreito", "light", accent="verde")
    await r.open(pg, "#/novidades", '[data-act="news-all"]')
    r.check(await pg.evaluate(OVERFLOW), "no celular estreito, nada passa da largura")
    await pg.click('[data-act="news-all"]')
    await pg.wait_for_function("/Conferindo [2-9] de/.test(document.querySelector('.njob')?.textContent || '')", timeout=20000)
    await pg.click('[data-act="news-cancel"]')
    await pg.locator(".toast", has_text="Conferência parada").wait_for(timeout=5000)
    await pg.wait_for_timeout(1200)
    n = len(r.api("GET", "api/news")["itens"])
    r.check(n >= 1, f"Parar: o que já foi conferido ficou ({n})")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await r.shot(pg, "parado", full_page=True)
    await ctx.close()

    # IA desligada: a aba some e o endereço volta para Dados
    r.api("PUT", "api/settings", {"ai": False})
    ctx, pg = await r.page(b, "cel", "light")
    await r.open(pg, "#/novidades", ".menu-list")
    r.check(pg.url.endswith("#/mais"), "IA desligada: o endereço de Novidades abre o menu Mais")
    r.check("Novidades" not in await pg.evaluate("[...document.querySelectorAll('.menu-row b')].map(b => b.textContent)"), "e o menu fica sem Novidades")
    await ctx.close()
    await b.close()
    app2.stop()


main("novidades_todos", body)
