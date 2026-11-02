#!/usr/bin/env python3
"""Desenha o ícone (icon.png) e o logo (logo.png) do InventarIA a partir de SVG, com Chromium.

Uso: tools/make_logo.py [pasta-de-saida]   (padrão: inventario/, ao lado de config.yaml)

Os dois têm fundo transparente e funcionam no tema claro e no escuro (do GitHub e do Home Assistant):
a etiqueta tem cor própria, o fio é cinza médio e o nome usa dourado com o "IA" no amarelo do app.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "inventario")
FONT = os.path.join(ROOT, "inventario", "app", "web", "fonts", "barlowc-700.woff")

AMARELO, BORDA, SOMBRA, ANEL, TINTA, FIO = "#f5c400", "#d4a800", "#c29700", "#fbe27a", "#1d2125", "#8b939c"
OURO = "#e5a100"

# etiqueta de preço desenhada em 256x256: corpo com ponta, espessura embaixo, picote, ilhós vazado, R$ e fio
CORPO = "M78 70H222a16 16 0 0 1 16 16V196a16 16 0 0 1-16 16H78L30 168V114Z"
FURO = "M66.5 141a8.5 8.5 0 1 0-17 0a8.5 8.5 0 1 0 17 0Z"
ANEL_D = "M75 141a17 17 0 1 0-34 0a17 17 0 1 0 34 0Z" + FURO


def icon_svg(px):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 256 256">
  <g transform="rotate(-12 134 141)">
    <path d="{CORPO}{FURO}" transform="translate(0 8)" fill="{SOMBRA}" fill-rule="evenodd"/>
    <path d="{CORPO}{FURO}" fill="{AMARELO}" fill-rule="evenodd"/>
    <path d="{CORPO}" fill="none" stroke="{BORDA}" stroke-width="3" stroke-linejoin="round"/>
    <line x1="98" y1="88" x2="98" y2="194" stroke="{TINTA}" stroke-opacity=".3" stroke-width="4" stroke-dasharray="9 8" stroke-linecap="round"/>
    <path d="{ANEL_D}" fill="{ANEL}" fill-rule="evenodd" stroke="{BORDA}" stroke-width="2"/>
    <text x="168" y="174" text-anchor="middle" font-family="BC" font-weight="700" font-size="104" fill="{TINTA}">R$</text>
    <path d="M58 141C56 112 44 74 52 8" fill="none" stroke="{FIO}" stroke-width="6.5" stroke-linecap="round"/>
  </g>
</svg>"""


PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: BC; src: url("file://{font}") format("woff"); font-weight: 700; }}
html, body {{ margin: 0; background: transparent; }}
#icon {{ width: 256px; height: 256px; }}
#logo {{ display: inline-flex; align-items: center; gap: 34px; padding: 14px 40px 22px 6px; }}
#logo svg {{ width: 430px; height: 430px; flex: none; margin: -40px -28px -40px 0; }}
.wm {{ font: 700 262px/1 BC; letter-spacing: -3px; white-space: nowrap; }}
.wm span {{ color: {ouro}; }}
.wm span + span {{ color: {amarelo}; }}
</style></head><body>
<div id="icon">{icon256}</div>
<div id="logo">{icon430}<span class="wm"><span>Inventar</span><span>IA</span></span></div>
</body></html>"""


async def main():
    html = PAGE.format(font=FONT, ouro=OURO, amarelo=AMARELO, icon256=icon_svg(256), icon430=icon_svg(430))
    path = os.path.join(os.path.dirname(os.path.abspath(OUT + "/x")), ".logo.html")
    tmp = "/tmp/inventaria-logo.html"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 2400, "height": 900}, device_scale_factor=1)
        await pg.goto("file://" + tmp)
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(200)
        await pg.locator("#icon").screenshot(path=os.path.join(OUT, "icon.png"), omit_background=True)
        await pg.locator("#logo").screenshot(path=os.path.join(OUT, "logo.png"), omit_background=True)
        await b.close()
    os.remove(tmp)
    print("icon.png e logo.png em", OUT)


asyncio.run(main())
