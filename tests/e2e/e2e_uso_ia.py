"""Mais > Configurações > Integrações > Uso da IA (Home Assistant de mentira): os números de hoje, 7 dias e do mês, as chamadas por dia
(tocar numa barra mostra o dia), os tipos, as últimas chamadas com erro e cota, e o link do consumo exato para
OpenAI, Anthropic e Google (ou o texto geral quando não dá para saber o provedor)."""
import json
import os
import time
from datetime import datetime

os.environ.setdefault("TZ", "America/Sao_Paulo")  # o servidor, este script e o Chromium no mesmo fuso
time.tzset()

from e2e_lib import OVERFLOW, FakeHA, main  # noqa: E402

WEEKDAY = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"]
CALLS = [3, 0, 5, 1, 0, 2, 4]  # do mais antigo até hoje
KINDS = [{"catalogo": 3}, {}, {"fala": 2, "foto": 3}, {"busca": 1}, {}, {"foto": 2}, {"busca": 2, "foto": 1, "catalogo": 1}]
OPENAI = {"entity_id": "ai_task.openai_ai_task", "state": "unknown", "attributes": {"friendly_name": "OpenAI AI Task", "supported_features": 3}}
CLAUDE = {"entity_id": "ai_task.claude_ai_task", "state": "unknown", "attributes": {"friendly_name": "Claude AI Task", "supported_features": 3}}


def day(i, now=None):
    return time.strftime("%Y-%m-%d", time.localtime((now or time.time()) - i * 86400))


def label(d):
    """Como a tela escreve um dia que não é hoje: "Qua, 28/10"."""
    wd = WEEKDAY[(datetime.strptime(d, "%Y-%m-%d").weekday() + 1) % 7]
    return f"{wd[0].upper()}{wd[1:]}, {d[8:10]}/{d[5:7]}"


def iso(t):
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def usage_file(entity):
    now = time.time()
    days = {}
    for k, (n, kinds) in enumerate(zip(CALLS, KINDS)):
        if not n:
            continue
        days[day(6 - k, now)] = {"calls": n, "tokens": n * 1200, "images": n, "seconds": n * 6.0, "errors": 1 if k == 2 else 0,
                                 "quota": 1 if k == 2 else 0, "kinds": kinds, "entities": {entity: n}}
    recent = [
        {"at": iso(now - 60), "kind": "foto", "entity": entity, "result": "ok", "seconds": 5.1, "tokens": 1300, "images": 1},
        {"at": iso(now - 86400), "kind": "catalogo", "entity": entity, "result": "cota", "seconds": 1.2, "tokens": 900, "images": 1},
        {"at": iso(now - 3 * 86400), "kind": "busca", "entity": entity, "result": "sem_busca", "seconds": 31.0, "tokens": 2600, "images": 0},
        {"at": iso(now - 4 * 86400), "kind": "fala", "entity": entity, "result": "formato", "seconds": 4.0, "tokens": 700, "images": 0},
        {"at": iso(now - 5 * 86400), "kind": "foto", "entity": entity, "result": "erro", "seconds": 2.0, "tokens": 400, "images": 1},
    ]
    return {"days": days, "recent": recent}, now


async def body(r, p):
    ha = FakeHA()
    r.start(search=False, mock_ai=False, ha=ha)
    ha.media_root = r.app.path("media")
    path = r.app.path("data", "uso_ia.json")

    def write(entity):
        data, now = usage_file(entity)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(path + ".tmp", path)
        return now

    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="turquesa")

    async def panel():
        await r.open(pg, "#/config/integracoes", ".more-tabs")
        await pg.wait_for_selector(".uso-tiles", timeout=10000)

    async def help_text():
        return " ".join((await pg.text_content("#p-usage .help")).split())

    # -- sem uso ainda
    await panel()
    r.eq(await pg.evaluate("[...document.querySelectorAll('.uso-tile .v')].map(e => e.textContent)"), ["0", "0", "0"], "sem uso: zero hoje, em 7 dias e no mês")
    r.eq(await pg.locator(".uso-tipos").count(), 0, "sem uso: sem a lista de tipos")
    await pg.click(".uso-ult summary")
    r.eq((await pg.text_content(".uso-ult li")).strip(), "Nenhuma chamada ainda.", "sem uso: Nenhuma chamada ainda")

    # -- uma semana de uso (OpenAI)
    ha.states = ha.states + [OPENAI]
    now = write("ai_task.openai_ai_task")
    await panel()
    tiles = await pg.evaluate("[...document.querySelectorAll('.uso-tile')].map(t => [t.querySelector('.k').textContent, t.querySelector('.v').textContent, t.querySelector('.s').textContent])")
    month = sum(n for k, n in enumerate(CALLS) if day(6 - k, now)[:7] == day(0, now)[:7])
    r.eq([t[:2] for t in tiles], [["Hoje", "4"], ["7 dias", "15"], ["Este mês", str(month)]], "chamadas de hoje, dos 7 dias e do mês")
    r.eq([tiles[0][2], tiles[1][2]], ["≈ 5 mil tokens", "1 vez sem cota"], "hoje: tokens estimados; 7 dias: a vez sem cota")
    heights = await pg.evaluate("[...document.querySelectorAll('.uso-bar i')].map(i => i.style.height)")
    r.eq(heights, ["60%", "0%", "100%", "20%", "0%", "40%", "80%"], "uma barra por dia, do tamanho das chamadas (o maior dia é a barra cheia)")
    r.eq(await pg.evaluate("[...document.querySelectorAll('.uso-dias span')].map(s => s.textContent)"),
         [WEEKDAY[(datetime.strptime(day(i, now), "%Y-%m-%d").weekday() + 1) % 7] for i in range(6, 0, -1)] + ["hoje"], "embaixo, o dia da semana; o último é hoje")
    r.eq(await pg.get_attribute(".uso-bar:last-child", "aria-pressed"), "true", "hoje vem escolhido")
    r.eq(" ".join((await pg.text_content(".uso-cap")).split()), "Hoje: 4 chamadas.", "e a legenda diz o de hoje")
    await pg.locator(".uso-bar").nth(2).click()
    r.eq(" ".join((await pg.text_content(".uso-cap")).split()), f"{label(day(4, now))}: 5 chamadas, 1 com erro, 1 sem cota.", "tocar num dia mostra as chamadas, o erro e a cota dele")
    r.eq(await pg.evaluate("[...document.querySelectorAll('.uso-bar')].map(b => b.getAttribute('aria-pressed'))"),
         ["false", "false", "true", "false", "false", "false", "false"], "e só ele fica marcado")
    await pg.locator(".uso-bar").nth(1).click()
    r.eq(" ".join((await pg.text_content(".uso-cap")).split()), f"{label(day(5, now))}: 0 chamadas.", "um dia sem uso: 0 chamadas")
    r.eq(await pg.evaluate("[...document.querySelectorAll('.uso-tipos li')].map(l => l.textContent.trim())"),
         ["Preencher com IA 6", "Catalogar itens 4", "Buscar foto na internet 3", "Falar 2"], "os tipos dos 7 dias, do mais usado ao menos")
    r.eq(await pg.evaluate("document.querySelector('.uso-ult').open"), False, "Últimas chamadas começa fechado")
    await pg.click(".uso-ult summary")
    rows = await pg.evaluate("[...document.querySelectorAll('.uso-ult li')].map(li => [li.querySelector('b').textContent, li.querySelector('span').textContent, (li.querySelector('.r-erro') || {}).textContent || '', li.querySelector('.t').textContent])")
    r.eq([x[:3] for x in rows], [["Preencher com IA", "OpenAI AI Task", ""], ["Catalogar itens", "OpenAI AI Task", "cota excedida"],
                                ["Buscar foto na internet", "OpenAI AI Task", "sem busca na web"], ["Falar", "OpenAI AI Task", "fora do formato"],
                                ["Preencher com IA", "OpenAI AI Task", "erro"]], "últimas chamadas: o tipo, a IA pelo nome e o que deu errado")
    hm = lambda t: time.strftime("%H:%M", time.localtime(t))  # noqa: E731
    r.eq(rows[0][3], f"5,1 s · ≈ 1 mil tokens · 1 imagem · hoje {hm(now - 60)}", "tempo, tokens, imagem e hora de hoje")
    r.eq(rows[1][3], f"1,2 s · ≈ 900 tokens · 1 imagem · ontem {hm(now - 86400)}", "a de ontem diz ontem")
    d3 = day(3, now)
    r.eq(rows[2][3], f"31 s · ≈ 3 mil tokens · {d3[8:10]}/{d3[5:7]} {hm(now - 3 * 86400)}", "a mais antiga diz o dia; sem imagem, não fala de imagem")
    t = await help_text()
    r.check(t.startswith("Consumo exato e custo da OpenAI: platform.openai.com/usage."), f"OpenAI: o link do consumo da OpenAI ({t[:60]})")
    a = await pg.evaluate("(a => [a.href, a.target, a.rel])(document.querySelector('#p-usage .help a'))")
    r.eq(a, ["https://platform.openai.com/usage", "_blank", "noopener noreferrer"], "o link abre fora do app")
    r.check(await pg.evaluate(OVERFLOW), "sem rolagem para o lado")
    await pg.evaluate("document.querySelector('#p-usage').scrollIntoView()")
    await r.shot(pg, "uso-openai")

    # -- Anthropic e Google, pela IA que foi usada
    ha.states = ha.states + [CLAUDE]
    write("ai_task.claude_ai_task")
    await panel()
    t = await help_text()
    r.check(t.startswith("Consumo exato e custo da Anthropic: Claude Console, Usage."), f"Anthropic: o link do Claude Console ({t[:60]})")
    r.eq(await pg.get_attribute("#p-usage .help a", "href"), "https://platform.claude.com/usage", "que leva ao uso da Anthropic")
    write("ai_task.google_ai_task")
    await panel()
    t = await help_text()
    r.check(t.startswith("Consumo exato do Gemini: Google Cloud Console") and "A cota grátis volta de madrugada" in t, f"Google: o Cloud Console e quando a cota volta ({t[:60]})")
    r.eq(await pg.get_attribute("#p-usage .help a", "href"), "https://console.cloud.google.com/apis/dashboard", "que leva ao painel do Google")

    # -- usou a IA padrão: o provedor vem das IAs do Home Assistant, se houver um só
    write("padrão do Home Assistant")
    await panel()
    t = await help_text()
    r.check(t.startswith("Consumo exato e custo: no painel do provedor da sua IA."), f"IAs de vários provedores: o texto geral, sem link ({t[:50]})")
    r.eq(await pg.locator("#p-usage .help a").count(), 0, "e nenhum link")
    ha.states = [s for s in ha.states if not s["entity_id"].startswith(("ai_task.", "conversation.google"))] + [CLAUDE]
    await panel()
    r.check((await help_text()).startswith("Consumo exato e custo da Anthropic"), "só a Anthropic no Home Assistant: o link dela")
    await ctx.close()

    # -- chamadas de verdade entram na hora: erro e cota
    ha.states = [s for s in ha.states if s["entity_id"] != CLAUDE["entity_id"]] + [{
        "entity_id": "ai_task.google_ai_task", "state": "unknown", "attributes": {"friendly_name": "Google AI Task", "supported_features": 3}}]
    photo = next(i["photos"][0] for i in r.data()["items"] if i["photos"])
    ctx, pg = await r.page(b, "pc", "light", accent="azul")
    ha.ai_error = (500, "Erro inesperado no modelo")
    r.app.post("api/ai/identify", {"file": photo, "mode": "single"})
    await panel()
    tile = await pg.evaluate("(t => [t.querySelector('.v').textContent, t.querySelector('.s').textContent])(document.querySelector('.uso-tile'))")
    r.eq(tile, ["5", "1 com erro"], "uma leitura que deu erro: 5 hoje, 1 com erro")
    ha.ai_error = (500, "429 RESOURCE_EXHAUSTED")
    r.app.post("api/ai/identify", {"file": photo, "mode": "multi"})
    await panel()
    tile = await pg.evaluate("(t => [t.querySelector('.v').textContent, t.querySelector('.s').textContent])(document.querySelector('.uso-tile'))")
    r.eq(tile, ["6", "1 vez sem cota"], "e uma sem cota: a cota aparece no lugar do erro")
    await pg.click(".uso-ult summary")
    first = await pg.evaluate("[...document.querySelector('.uso-ult li').children].map(e => e.textContent.trim()).slice(0, 3)")
    r.eq(first, ["Catalogar itens", "Padrão do Home Assistant", "cota excedida"], "a última chamada fica em primeiro, com a IA padrão")
    await pg.evaluate("document.querySelector('#p-usage').scrollIntoView()")
    await r.shot(pg, "uso-computador")
    await ctx.close()

    # celular estreito: o painel cabe
    ctx, pg = await r.page(b, "estreito", "light")
    await panel()
    await pg.click(".uso-ult summary")
    r.check(await pg.evaluate(OVERFLOW), "celular de 320 px: sem rolagem para o lado")
    await pg.evaluate("document.querySelector('#p-usage').scrollIntoView()")
    await r.shot(pg, "uso-estreito", full_page=False)
    await ctx.close()
    await b.close()
    ha.stop()


main("uso_ia", body)
