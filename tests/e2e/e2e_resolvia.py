"""Tarefas no ResolvIA (1.47.0), na ficha do item: só aparece com Usar equipamentos ligado no ResolvIA (o arquivo dele na
pasta share); mostra as tarefas abertas ligadas ao item e a Nova tarefa (nome, lista, prazo em botões, sem a janela do
celular). Criar põe a tarefa na lista e manda o evento resolvia_comodo com o item e o cômodo; a lista escolhida fica
lembrada; uma lista sem prazo esconde o prazo. 1.48.0: as tarefas acima das Novidades, os botões do mesmo tamanho; as
listas como o ResolvIA mostra (as que ele publica, com os nomes e as cores de lá, todas à vista em botões) e o prazo só
com Controlar prazos ligado lá. Listas, tarefas e itens inventados."""
import json
import os
from datetime import date, timedelta

import e2e_lib
from e2e_lib import OVERFLOW, TMP, FakeHA, main

e2e_lib.SIZES.setdefault("cel390", (390, 844, True))
LISTAS = [{"entity_id": "todo.casa", "state": "0", "attributes": {"friendly_name": "Casa", "supported_features": 1 | 16}},
          {"entity_id": "todo.mercado", "state": "0", "attributes": {"friendly_name": "Mercado", "supported_features": 1}},
          {"entity_id": "todo.guardada", "state": "0", "attributes": {"friendly_name": "Guardada", "supported_features": 1 | 16}}]
# o que o ResolvIA publica: a Guardada está desmarcada lá (fica de fora); o nome e a cor de cada uma são os de lá
PUBLICADAS = [{"id": "todo.casa", "nome": "Minha casa", "cor": "#4ED3A6", "prazo": True},
              {"id": "todo.mercado", "nome": "Mercado", "cor": "#FF5A4F", "prazo": False}]


async def body(r, p):
    arq = os.path.join(TMP, "resolvia-e2e.json")
    ha = FakeHA()
    ha.states += [dict(x) for x in LISTAS]
    r.start(search=False, ha=ha, env={"INV_RESOLVIA": arq})
    it = next(i for i in r.data()["items"] if i.get("room") and i.get("cat") == "eletronicos")

    def resolvia(**mais):
        with open(arq, "w", encoding="utf-8") as f:
            json.dump({"app": "ResolvIA", "nome": "ResolvIA", "prazos": True, "listas": PUBLICADAS,
                       "equipamentos": {"lista": [], "tarefas": {"todo.casa": {"limpar o filtro": it["id"]}}}, **mais}, f)

    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel390", "dark")
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    r.eq(await pg.locator('[data-slot="item-tarefas"]').count(), 0, "sem o ResolvIA: nada de tarefas")
    # o ResolvIA com Usar equipamentos: uma tarefa aberta já ligada ao item
    # (1.48.1: duas iguais na lista são uma tarefa só no ResolvIA: aparece uma vez)
    ha.todo_items = {"todo.casa": [{"summary": "Limpar o filtro", "uid": "a", "status": "needs_action", "due": (date.today() + timedelta(days=1)).isoformat()},
                                   {"summary": "Limpar o filtro", "uid": "b", "status": "needs_action"}]}
    resolvia()
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    sec = pg.locator('[data-slot="item-tarefas"]')
    await sec.locator(".tlist li").first.wait_for(timeout=8000)
    r.eq(" ".join((await sec.locator(".tlist").inner_text()).split()), "Limpar o filtro Minha casa · amanhã · 2 iguais na lista",
         "a tarefa aberta do item, uma vez só, a lista (o nome do ResolvIA) e o prazo")
    # as tarefas acima das Novidades, e os botões das duas do mesmo tamanho
    blocos = await pg.locator(".dlg-b > .inews").evaluate_all("es => es.map(e => e.dataset.slot)")
    r.eq(blocos, ["item-tarefas", "item-news"], "Tarefas no ResolvIA acima das Novidades")
    await pg.locator('[data-slot="item-news"] .btn').first.wait_for(timeout=8000)
    tam = await pg.locator(".dlg-b > .inews > .btn").evaluate_all("es => es.map(e => { const b = e.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)]; })")
    r.check(len(tam) == 2 and tam[0] == tam[1], f"Nova tarefa e Novidades do mesmo tamanho ({tam})")
    await sec.scroll_into_view_if_needed()
    await r.shot(pg, "ficha")
    # Nova tarefa: as listas do ResolvIA, todas à vista, com a cor de lá
    await sec.locator('[data-act="tarefa-nova"]').click()
    dlg = pg.locator("dialog.modal", has_text="Nova tarefa")
    chips = dlg.locator('[data-slot="tn-listas"] .chip')
    await chips.first.wait_for(timeout=8000)
    r.eq([t.strip() for t in await chips.all_inner_texts()], ["Minha casa", "Mercado"], "as listas do ResolvIA, sem a desmarcada lá")
    r.eq(await dlg.locator("select").count(), 0, "sem caixa de seleção: as listas direto na tela")
    cores = await chips.locator(".dot").evaluate_all("es => es.map(e => getComputedStyle(e).backgroundColor)")
    r.eq(cores, ["rgb(78, 211, 166)", "rgb(255, 90, 79)"], "a bolinha na cor de cada lista no ResolvIA")
    r.eq(await dlg.locator('input[name="lista"]:checked').input_value(), "todo.casa", "a primeira já escolhida")
    r.eq([t.strip() for t in await dlg.locator("[data-tn-prazo] .chip").all_text_contents()], ["Sem prazo", "Hoje", "Amanhã", "Em 7 dias", "Em 30 dias", "Outra data"],
         "o prazo em botões, sem a janela do celular")
    hs = await dlg.locator('#tn-nome, [data-slot="tn-listas"] .chip, [data-tn-prazo] .chip, .dlg-f .btn').evaluate_all("es => es.map(e => Math.round(e.getBoundingClientRect().height))")
    r.check(all(h == 50 for h in hs), f"tudo com 50 px ({hs})")
    ws = await chips.evaluate_all("es => es.map(e => Math.round(e.getBoundingClientRect().width))")
    r.check(len(set(ws)) == 1, f"as listas do mesmo tamanho, lado a lado ({ws})")
    await dlg.locator("[data-ok]").click()
    r.eq((await dlg.locator("[data-err]").text_content()).strip(), "Dê um nome à tarefa.", "sem nome, pede o nome")
    await dlg.locator("#tn-nome").fill("Trocar o filtro")
    r.check(await dlg.locator("[data-err]").is_hidden(), "ao escrever, o aviso some")
    await dlg.locator("[data-tn-prazo] .chip", has_text="Em 7 dias").click()
    await r.shot(pg, "nova")
    r.check(await pg.evaluate(OVERFLOW), "nada passa da largura")
    await dlg.locator("[data-ok]").click()
    await pg.locator(".toast", has_text="Tarefa criada em Minha casa").wait_for(timeout=8000)
    r.eq(ha.todo_items["todo.casa"][-1], {"summary": "Trocar o filtro", "uid": "u3", "status": "needs_action", "due": (date.today() + timedelta(days=7)).isoformat()},
         "a tarefa na lista, com o prazo")
    r.eq(ha.events[-1], ("resolvia_comodo", {"entity_id": "todo.casa", "tarefa": "Trocar o filtro", "equipamento": it["id"], "origem": "InventarIA", "comodo": it["room"]}),
         "o evento liga a tarefa ao item e ao cômodo no ResolvIA")
    # a lista lembrada; o Mercado não aceita prazo
    await sec.locator('[data-act="tarefa-nova"]').click()
    await chips.first.wait_for(timeout=8000)
    r.eq(await dlg.locator('input[name="lista"]:checked').input_value(), "todo.casa", "a última lista fica escolhida")
    await chips.filter(has_text="Mercado").click()
    r.check(await dlg.locator("[data-tn-prazo]").is_hidden(), "lista sem prazo: o prazo some")
    await dlg.locator("#tn-nome").fill("Comprar pilhas")
    await dlg.locator("#tn-nome").press("Enter")
    await pg.locator(".toast", has_text="Tarefa criada em Mercado").wait_for(timeout=8000)
    r.eq(ha.todo_items["todo.mercado"][-1].get("due"), None, "sem prazo")
    # 1.48.1: o mesmo nome de uma aberta na lista: não cria outra igual, liga este item a ela junto dos que já estavam
    n = len(ha.todo_items["todo.casa"])
    await sec.locator('[data-act="tarefa-nova"]').click()
    await chips.first.wait_for(timeout=8000)
    await chips.filter(has_text="Minha casa").click()
    await dlg.locator("#tn-nome").fill("limpar o filtro")
    await dlg.locator("[data-ok]").click()
    await pg.locator(".toast", has_text="Limpar o filtro já estava em Minha casa: agora ligada a este item também").wait_for(timeout=8000)
    r.eq(len(ha.todo_items["todo.casa"]), n, "nada de tarefa repetida")
    r.eq(ha.events[-1][1]["equipamento"], it["id"], "o item, que já estava ligado, uma vez só")
    # 1.49.1: Outra data, no visual do app: o mês, com hoje marcado; escolhido o dia, ele fica no botão e o mês fecha
    await sec.locator('[data-act="tarefa-nova"]').click()
    await chips.first.wait_for(timeout=8000)
    await chips.filter(has_text="Minha casa").click()
    r.eq(await dlg.locator('input[type="date"]').count(), 0, "nada da janela de data do celular")
    await dlg.locator("[data-outra]").click()
    cal = dlg.locator("[data-tn-cal]")
    r.check(await cal.is_visible() and await cal.locator(".tcal-d.hoje").count() == 1, "Outra data: o mês, com hoje marcado")
    hs = await cal.locator(".tcal-d").evaluate_all("es => es.map(e => Math.round(e.getBoundingClientRect().height))")
    r.check(min(hs) >= 40, f"os dias fáceis de tocar ({min(hs)} px)")
    await dlg.locator("#tn-nome").fill("Limpar as grades")
    await dlg.locator("[data-ok]").click()
    r.eq((await dlg.locator("[data-err]").text_content()).strip(), "Escolha a data.", "sem o dia, pede o dia")
    await cal.locator('[data-cal="1"]').click()
    await r.shot(pg, "outra-data-mes")
    alvo = (date.today().replace(day=1) + timedelta(days=40)).replace(day=15)
    await cal.locator(f'[data-day="{alvo.isoformat()}"]').click()
    r.check(await cal.is_hidden() and (await dlg.locator("[data-outra-l]").inner_text()).strip() == alvo.strftime("%d/%m/%Y"), "o dia escolhido no botão, o mês fecha")
    r.check(await dlg.locator("[data-err]").is_hidden(), "e o aviso some")
    await r.shot(pg, "outra-data")
    await dlg.locator("[data-ok]").click()
    await pg.locator(".toast", has_text="Tarefa criada em Minha casa").wait_for(timeout=8000)
    r.eq(ha.todo_items["todo.casa"][-1].get("due"), alvo.isoformat(), "o prazo é o dia escolhido")
    # 1.49.0: uma lista sem data com o prazo guardado no ResolvIA 2.59.0: o prazo aparece, com o aviso, e vai no evento
    resolvia(listas=[PUBLICADAS[0], {**PUBLICADAS[1], "prazo_app": True}])
    await sec.locator('[data-act="tarefa-nova"]').click()
    await chips.first.wait_for(timeout=8000)
    await chips.filter(has_text="Mercado").click()
    r.check(await dlg.locator("[data-tn-prazo]").is_visible() and await dlg.locator("[data-tn-app]").is_visible(), "Mercado: o prazo, guardado no ResolvIA")
    await chips.filter(has_text="Minha casa").click()
    r.check(await dlg.locator("[data-tn-app]").is_hidden(), "Minha casa: o prazo vai para a lista, sem o aviso")
    await chips.filter(has_text="Mercado").click()
    await dlg.locator("[data-tn-prazo] .chip", has_text="Amanhã").click()
    await dlg.locator("#tn-nome").fill("Comprar pilhas AA")
    await dlg.locator("[data-ok]").click()
    await pg.locator(".toast", has_text="Tarefa criada em Mercado").wait_for(timeout=8000)
    r.eq(ha.todo_items["todo.mercado"][-1].get("due"), None, "sem data no Home Assistant")
    r.eq(ha.events[-1][1].get("prazo"), (date.today() + timedelta(days=1)).isoformat(), "o prazo vai para o ResolvIA no evento")
    # Controlar prazos desligado no ResolvIA: nenhuma lista pede prazo
    resolvia(prazos=False, listas=[{**x, "prazo": False} for x in PUBLICADAS])
    await sec.locator('[data-act="tarefa-nova"]').click()
    await chips.first.wait_for(timeout=8000)
    await chips.filter(has_text="Minha casa").click()
    r.check(await dlg.locator("[data-tn-prazo]").is_hidden(), "Controlar prazos desligado no ResolvIA: sem prazo")
    await dlg.locator("[data-x]").first.click()
    await ctx.close()
    ctx, pg = await r.page(b, "estreito", "light")
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    await pg.locator('[data-slot="item-tarefas"] .tlist li').first.wait_for(timeout=8000)
    await pg.locator('[data-act="tarefa-nova"]').click()
    await pg.locator('[data-slot="tn-listas"] .chip').first.wait_for(timeout=8000)
    r.check(await pg.evaluate(OVERFLOW), "320 px, claro: nada passa da largura")
    await r.shot(pg, "nova-320")
    await b.close()


if __name__ == "__main__":
    main("e2e_resolvia", body)
