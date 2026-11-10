"""Tarefas no ResolvIA (1.47.0), na ficha do item: só aparece com Usar equipamentos ligado no ResolvIA (o arquivo dele na
pasta share); mostra as tarefas abertas ligadas ao item e a Nova tarefa (nome, lista do Home Assistant, prazo em botões,
sem a janela do celular). Criar põe a tarefa na lista e manda o evento resolvia_comodo com o item e o cômodo; a lista
escolhida fica lembrada; uma lista sem prazo esconde o prazo. Listas, tarefas e itens inventados."""
import json
import os
from datetime import date, timedelta

import e2e_lib
from e2e_lib import OVERFLOW, TMP, FakeHA, main

e2e_lib.SIZES.setdefault("cel390", (390, 844, True))
LISTAS = [{"entity_id": "todo.casa", "state": "0", "attributes": {"friendly_name": "Casa", "supported_features": 1 | 16}},
          {"entity_id": "todo.mercado", "state": "0", "attributes": {"friendly_name": "Mercado", "supported_features": 1}}]


async def body(r, p):
    arq = os.path.join(TMP, "resolvia-e2e.json")
    ha = FakeHA()
    ha.states += [dict(x) for x in LISTAS]
    r.start(search=False, mock_ai=False, ha=ha, env={"INV_RESOLVIA": arq})
    it = next(i for i in r.data()["items"] if i.get("room"))
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel390", "dark")
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    r.eq(await pg.locator('[data-slot="item-tarefas"]').count(), 0, "sem o ResolvIA: nada de tarefas")
    # o ResolvIA com Usar equipamentos: uma tarefa aberta já ligada ao item
    ha.todo_items = {"todo.casa": [{"summary": "Limpar o filtro", "uid": "a", "status": "needs_action", "due": (date.today() + timedelta(days=1)).isoformat()}]}
    with open(arq, "w", encoding="utf-8") as f:
        json.dump({"app": "ResolvIA", "nome": "ResolvIA", "equipamentos": {"lista": [], "tarefas": {"todo.casa": {"limpar o filtro": it["id"]}}}}, f)
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    sec = pg.locator('[data-slot="item-tarefas"]')
    await sec.locator(".tlist li").first.wait_for(timeout=8000)
    r.eq(" ".join((await sec.locator(".tlist").inner_text()).split()), "Limpar o filtro Casa · amanhã", "a tarefa aberta do item, a lista e o prazo")
    await sec.scroll_into_view_if_needed()
    await r.shot(pg, "ficha")
    # Nova tarefa
    await sec.locator('[data-act="tarefa-nova"]').click()
    dlg = pg.locator("dialog.modal", has_text="Nova tarefa")
    await dlg.locator("#tn-lista:not([disabled])").wait_for(timeout=8000)
    r.eq(await dlg.locator("#tn-lista option").all_text_contents(), ["Casa", "Mercado"], "as listas do Home Assistant que aceitam tarefa")
    r.eq([t.strip() for t in await dlg.locator("[data-tn-prazo] .chip").all_text_contents()], ["Sem prazo", "Hoje", "Amanhã", "Em 7 dias", "Em 30 dias"],
         "o prazo em botões, sem a janela do celular")
    hs = await dlg.locator("#tn-nome, #tn-lista, [data-tn-prazo] .chip, .dlg-f .btn").evaluate_all("es => es.map(e => Math.round(e.getBoundingClientRect().height))")
    r.check(all(h == 50 for h in hs), f"tudo com 50 px ({hs})")
    await dlg.locator("[data-ok]").click()
    r.eq((await dlg.locator("[data-err]").text_content()).strip(), "Dê um nome à tarefa.", "sem nome, pede o nome")
    await dlg.locator("#tn-nome").fill("Trocar o filtro")
    r.check(await dlg.locator("[data-err]").is_hidden(), "ao escrever, o aviso some")
    await dlg.locator("[data-tn-prazo] .chip", has_text="Em 7 dias").click()
    await r.shot(pg, "nova")
    r.check(await pg.evaluate(OVERFLOW), "nada passa da largura")
    await dlg.locator("[data-ok]").click()
    await pg.locator(".toast", has_text="Tarefa criada em Casa").wait_for(timeout=8000)
    r.eq(ha.todo_items["todo.casa"][-1], {"summary": "Trocar o filtro", "uid": "u2", "status": "needs_action", "due": (date.today() + timedelta(days=7)).isoformat()},
         "a tarefa na lista, com o prazo")
    r.eq(ha.events[-1], ("resolvia_comodo", {"entity_id": "todo.casa", "tarefa": "Trocar o filtro", "equipamento": it["id"], "origem": "InventarIA", "comodo": it["room"]}),
         "o evento liga a tarefa ao item e ao cômodo no ResolvIA")
    # a lista lembrada; o Mercado não aceita prazo
    await sec.locator('[data-act="tarefa-nova"]').click()
    await dlg.locator("#tn-lista:not([disabled])").wait_for(timeout=8000)
    r.eq(await dlg.locator("#tn-lista").input_value(), "todo.casa", "a última lista fica escolhida")
    await pg.select_option("#tn-lista", "todo.mercado")
    r.check(await dlg.locator("[data-tn-prazo]").is_hidden(), "lista sem prazo: o prazo some")
    await dlg.locator("#tn-nome").fill("Comprar pilhas")
    await dlg.locator("#tn-nome").press("Enter")
    await pg.locator(".toast", has_text="Tarefa criada em Mercado").wait_for(timeout=8000)
    r.eq(ha.todo_items["todo.mercado"][-1].get("due"), None, "sem prazo")
    await ctx.close()
    ctx, pg = await r.page(b, "estreito", "light")
    await r.open(pg, f"#/i/{it['id']}", ".ihead")
    await pg.locator('[data-slot="item-tarefas"] .tlist li').first.wait_for(timeout=8000)
    await pg.locator('[data-act="tarefa-nova"]').click()
    await pg.locator("#tn-lista:not([disabled])").wait_for(timeout=8000)
    r.check(await pg.evaluate(OVERFLOW), "320 px, claro: nada passa da largura")
    await r.shot(pg, "nova-320")
    await b.close()


if __name__ == "__main__":
    main("e2e_resolvia", body)
