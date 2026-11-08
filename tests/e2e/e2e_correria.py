"""Mais > Configurações > Integrações > CorrerIA: o cartão no celular de 390 px e no computador, claro e escuro; desligado de
início e sem depender do Usar IA; ligar grava share/inventario/correria.json e desligar apaga (e a rota passa a responder
401); a linha diz quem usou e quando, e muda sozinha quando o Claude lê algo; uma gravação pelo CorrerIA aparece na tela
sem recarregar, com a origem Pelo CorrerIA e quem cadastrou."""
import json
import os
import re

import e2e_lib
from e2e_lib import OVERFLOW, main

e2e_lib.SIZES.setdefault("cel390", (390, 844, True))
ANA = {"id": "person.ana", "nome": "Ana"}


async def body(r, p):
    r.start(search=False)
    share = r.app.path("share", "correria.json")

    def chave():
        with open(share, encoding="utf-8") as f:
            return {"Authorization": "Bearer " + json.load(f)["chave"], "X-App": "CorrerIA"}

    def usar(nome, args=None, cliente="Claude"):
        return r.app.ok("POST", "api/integracao/ferramentas", {"nome": nome, "argumentos": args or {}, "pessoa": ANA, "cliente": cliente}, headers=chave())

    async def acordar(pg):  # a tela confere o /api/rev ao voltar para ela (e a cada 30 s)
        await pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        await pg.wait_for_timeout(600)

    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel390", "light", accent="laranja")
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    card = pg.locator("#p-correria")
    r.eq(await card.count(), 1, "Integrações tem o cartão CorrerIA")
    r.eq(" ".join((await card.locator("h2").text_content()).split()), "CorrerIA", "com o título CorrerIA")
    sw = pg.get_by_role("switch", name="Usar com o CorrerIA")
    r.check(not await sw.is_checked(), "desligado de início")
    r.eq(" ".join((await card.locator(".ot span").text_content()).split()), "Para o WhatsApp, o Claude e o Gemini lerem e mudarem o inventário.",
         "desligado: o que ele faz, numa linha")
    r.eq(await card.locator('[data-slot="correria-uso"]').count(), 0, "desligado: sem a linha do último uso")
    r.check(not os.path.exists(share), "desligado: sem share/inventario/correria.json")
    await card.scroll_into_view_if_needed()
    await r.shot(pg, "desligado-claro")

    # não depende do Usar IA: com a IA desligada, o cartão fica e liga
    await pg.click('label.switch:has([data-input="ai-on"])')
    await pg.locator(".toast", has_text="IA desligada").wait_for(timeout=8000)
    r.eq(await pg.locator("#p-usage").count(), 0, "IA desligada: o Uso da IA some")
    r.eq(await card.count(), 1, "mas o CorrerIA fica (quem pensa é a IA do CorrerIA, o Claude ou o Gemini)")
    await pg.click('label.switch:has([data-input="correria-on"])')
    await pg.locator(".toast", has_text="CorrerIA ligado").wait_for(timeout=8000)
    r.check(r.data()["settings"]["correria"] is True, "ligado fica gravado")
    r.check(os.path.exists(share), "ligar grava share/inventario/correria.json, mesmo com a IA desligada")
    with open(share, encoding="utf-8") as f:
        info = json.load(f)
    r.eq((info["app"], info["ferramentas"]), ("inventario", "/api/integracao/ferramentas"), "o arquivo do contrato do CorrerIA")
    r.eq(" ".join((await card.locator(".ot span").text_content()).split()), "Ligado: pelo WhatsApp, o Claude e o Gemini leem e mudam o inventário.",
         "ligado: diz que está ligado")
    uso = card.locator('[data-slot="correria-uso"]')
    r.eq((await uso.text_content()).strip(), "Ainda não foi usado. Conecte no app CorrerIA.", "antes do primeiro uso, diz onde conectar")
    await pg.click('label.switch:has([data-input="ai-on"])')
    await pg.locator(".toast", has_text="IA ligada").wait_for(timeout=8000)
    r.check(await sw.is_checked(), "religar a IA não mexe no CorrerIA")

    # alinhado como as outras chaves; nada passa da largura
    await pg.wait_for_selector("#p-sensors")
    xs = await pg.evaluate("""['ai-on', 'sensors-on', 'correria-on'].map(k => {
        const r = document.querySelector(`label.switch:has([data-input="${k}"])`).getBoundingClientRect(); return [Math.round(r.right), Math.round(r.width), Math.round(r.height)]; })""")
    r.check(len({tuple(x) for x in xs}) == 1, f"a chave do CorrerIA do mesmo tamanho e alinhada com Usar IA e Criar os sensores ({xs})")
    r.check(await pg.evaluate(OVERFLOW), "nada passa da largura em 390 px")

    # o Claude leu (sem mudar nada): a linha muda sozinha
    rev = r.data()["rev"]
    usar("resumo")
    await acordar(pg)
    txt = (await uso.text_content()).strip()
    r.check(re.fullmatch(r"Claude usou hoje às \d{1,2}:\d{2}\.", txt) is not None, f"a linha diz quem usou e quando ({txt})")
    r.eq(r.data()["rev"], rev, "uma leitura não muda o inventário")
    await pg.wait_for_timeout(3500)  # os avisos de baixo somem
    await card.scroll_into_view_if_needed()
    await r.shot(pg, "ligado-claro")

    # uma gravação pelo CorrerIA aparece na tela sem recarregar
    out = usar("cadastrar_itens", {"comodo": "Varanda", "itens": [{"nome": "Rede de descanso", "valor": 150, "categoria": "Utilidades"}]}, cliente="Gemini")
    iid = re.search(r"id (var-\d+)", out["texto"]).group(1)
    await acordar(pg)
    r.eq((await uso.text_content()).strip()[:12], "Gemini usou ", "a linha passa para quem usou por último")
    await pg.evaluate("location.hash = '#/buscar?q=rede'")
    await pg.wait_for_selector("#results")
    await pg.wait_for_timeout(400)
    r.check("Rede de descanso" in await pg.text_content("#results"), "o item cadastrado pelo CorrerIA aparece na busca, sem recarregar")
    await pg.evaluate(f"location.hash = '#/i/{iid}'")
    await pg.wait_for_selector("dialog.sheet h1")
    props = dict(await pg.evaluate("[...document.querySelectorAll('dialog.sheet .props dt')].map(dt => [dt.textContent.trim(), dt.nextElementSibling.textContent.replace(/\\s+/g, ' ').trim()])"))
    r.eq(props.get("Origem"), "Pelo CorrerIA", "a ficha diz de onde veio")
    r.check(props.get("Cadastrado", "").endswith("por Ana"), f"e quem cadastrou: a pessoa que conectou ({props.get('Cadastrado')})")
    await r.shot(pg, "ficha-pelo-correria")
    await ctx.close()

    # escuro, celular e computador
    for size, scheme in (("cel390", "dark"), ("pc", "dark"), ("pc", "light")):
        ctx, pg = await r.page(b, size, scheme, accent="laranja")
        await r.open(pg, "#/config/integracoes", ".more-tabs")
        card = pg.locator("#p-correria")
        await card.scroll_into_view_if_needed()
        r.check(await pg.get_by_role("switch", name="Usar com o CorrerIA").is_checked(), f"{size} {scheme}: ligado")
        r.check((await card.locator('[data-slot="correria-uso"]').text_content()).startswith("Gemini usou "), f"{size} {scheme}: com o último uso")
        r.check(await pg.evaluate(OVERFLOW), f"{size} {scheme}: nada passa da largura")
        await pg.wait_for_timeout(200)
        await r.shot(pg, f"ligado-{size}-{'escuro' if scheme == 'dark' else 'claro'}")
        if (size, scheme) != ("pc", "light"):
            await ctx.close()
    # desligar apaga o arquivo e fecha a rota
    h = chave()
    await pg.click('label.switch:has([data-input="correria-on"])')
    await pg.locator(".toast", has_text="CorrerIA desligado").wait_for(timeout=8000)
    r.check(not os.path.exists(share), "desligar apaga share/inventario/correria.json")
    r.eq(await pg.locator('#p-correria [data-slot="correria-uso"]').count(), 0, "desligado: a linha do último uso some")
    st, _, _ = r.app.get("api/integracao/ferramentas", headers=h)
    r.eq(st, 401, "desligado: a rota das ferramentas responde 401")
    await ctx.close()
    await b.close()


if __name__ == "__main__":
    main("e2e_correria", body)
