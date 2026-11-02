#!/usr/bin/env python3
"""Tira as 4 imagens do README (docs/*.png) com a casa de exemplo de demo.py.

Uso: shots_readme.py <url-do-servidor-de-exemplo> <ia.json> <pasta-de-saida>
Celular 390x844 em 2x, tema escuro, cor padrão (amarelo), usuário "Diego".
"""
import asyncio
import json
import os
import sys

from playwright.async_api import async_playwright

BASE, IA, OUT = sys.argv[1].rstrip("/") + "/", sys.argv[2], sys.argv[3]


async def main():
    os.makedirs(OUT, exist_ok=True)
    ia = json.load(open(IA, encoding="utf-8"))
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="dark",
                                  is_mobile=True, has_touch=True, reduced_motion="reduce",
                                  extra_http_headers={"X-Remote-User-Display-Name": "Diego"})
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))

        async def shot(name):
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=os.path.join(OUT, name))

        await pg.goto(BASE + "#/")
        await pg.wait_for_selector(".tag")
        await pg.evaluate("document.fonts.ready")
        await shot("inicio.png")

        await pg.click('.tabbar [data-tab="rooms"]')
        await pg.wait_for_selector(".rooms")
        await shot("comodos.png")

        await pg.click('.rooms a[href="#/c/sala"]')
        await pg.wait_for_selector(".rhead")
        await shot("comodo.png")

        # leitura por IA: foto da estante do escritório; a resposta vem de ia.json
        async def fake_ai(route):
            await asyncio.sleep(0.3)
            await route.fulfill(json={"items": ia["items"], "entity": "ai_task.google_ai_task"})
        await pg.route("**/api/ai/identify", fake_ai)
        await pg.goto(BASE + "#/c/escritorio")
        await pg.wait_for_selector(".rhead")
        await pg.click('.rhead-actions [data-act="catalog"]')
        await pg.wait_for_selector('[data-ct="roomphoto"]')
        await pg.click('[data-ct="roomphoto"]')
        await pg.wait_for_selector(".pick label")
        await pg.click(".pick label:nth-child(2)")
        await pg.click("[data-ok]")
        await pg.wait_for_selector('[data-ct="read"]:not([disabled])')
        await pg.click('[data-ct="read"]')
        await pg.wait_for_selector(".found")
        await shot("ia.png")

        await b.close()
    print("imagens em", OUT, "| erros:", errors or "nenhum")


asyncio.run(main())
