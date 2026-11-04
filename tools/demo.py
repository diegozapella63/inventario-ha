#!/usr/bin/env python3
"""Casa de exemplo para as imagens do README: cômodos, itens e fotos ilustradas (nada da casa real).

Uso: demo.py <pasta-de-saida>
Gera <saida>/seed/inventario.json, seed/photos/*.jpg e seed/thumbs/*.jpg, prontos para o servidor
usar como INV_SEED, e <saida>/ia.json com a resposta de exemplo da leitura por IA.
"""
import asyncio
import json
import os
import random
import sys

from PIL import Image
from playwright.async_api import async_playwright

OUT = sys.argv[1]
SEED = os.path.join(OUT, "seed")
FLOOR = 440


# ------------------------------------------------------------------ cores
def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ra, rb))


def dark(c, t):
    return mix(c, "#000000", t)


def light(c, t):
    return mix(c, "#ffffff", t)


INK = "#2b2f33"
WOOD = "#a9794e"
WOOD_L = "#c99c6e"
GREENS = ["#3f7d4e", "#4f9a5f", "#2f6b40", "#5aa86a"]
BOOKS = ["#c9644a", "#e0b13a", "#2f7f7a", "#5b6f7c", "#8a5a83", "#d98d5f", "#3d5a80", "#9aa66b", "#b84a5a", "#e8dcc4", "#45494e"]

DEFS = """<defs>
<linearGradient id="wl" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#000" stop-opacity=".07"/></linearGradient>
<linearGradient id="fs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".16"/></linearGradient>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9fcbe8"/><stop offset="1" stop-color="#e3f1f7"/></linearGradient>
<linearGradient id="steel" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#c9cfd4"/><stop offset=".5" stop-color="#e3e7ea"/><stop offset="1" stop-color="#c3c9ce"/></linearGradient>
<linearGradient id="screen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2a3138"/><stop offset=".55" stop-color="#14181c"/><stop offset="1" stop-color="#0d1013"/></linearGradient>
<radialGradient id="glow"><stop offset="0" stop-color="#ffe7b0" stop-opacity=".55"/><stop offset="1" stop-color="#ffe7b0" stop-opacity="0"/></radialGradient>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#a9c6d8"/><stop offset="1" stop-color="#5f7f94"/></linearGradient>
</defs>"""


# ------------------------------------------------------------------ cenário
def base(wall, floor, kind="wood"):
    s = [f'<rect width="800" height="600" fill="{wall}"/>', '<rect width="800" height="440" fill="url(#wl)"/>',
         f'<rect y="{FLOOR}" width="800" height="160" fill="{floor}"/>']
    if kind == "wood":
        for i, y in enumerate(range(FLOOR + 26, 600, 26)):
            s.append(f'<line x1="0" y1="{y}" x2="800" y2="{y}" stroke="{dark(floor, .13)}" stroke-width="2"/>')
        for i, y in enumerate(range(FLOOR, 600, 26)):
            off = (i * 137) % 230
            for x in range(off, 800, 230):
                s.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + 26}" stroke="{dark(floor, .13)}" stroke-width="2"/>')
    else:
        for y in range(FLOOR + 40, 600, 40):
            s.append(f'<line x1="0" y1="{y}" x2="800" y2="{y}" stroke="{dark(floor, .1)}" stroke-width="2"/>')
        for x in range(0, 800, 80):
            s.append(f'<line x1="{x}" y1="{FLOOR}" x2="{x}" y2="600" stroke="{dark(floor, .1)}" stroke-width="2"/>')
    s.append(f'<rect y="{FLOOR - 12}" width="800" height="12" fill="{light(wall, .4)}"/>')
    s.append(f'<rect y="{FLOOR}" width="800" height="3" fill="{dark(floor, .25)}"/>')
    s.append(f'<rect y="{FLOOR}" width="800" height="160" fill="url(#fs)"/>')
    return "".join(s)


def shadow(cx, w, y=FLOOR + 6, o=.16):
    return f'<ellipse cx="{cx}" cy="{y}" rx="{w / 2}" ry="11" fill="#000" opacity="{o}"/>'


def window(x, y, w, h, curtain="#e8dcc4"):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#f4f2ee"/>',
         f'<rect x="{x + 12}" y="{y + 12}" width="{w - 24}" height="{h - 24}" fill="url(#sky)"/>',
         f'<ellipse cx="{x + w * .3}" cy="{y + h - 12}" rx="{w * .32}" ry="34" fill="#8fbf8a"/>',
         f'<ellipse cx="{x + w * .75}" cy="{y + h - 12}" rx="{w * .3}" ry="26" fill="#7fb07c"/>',
         f'<rect x="{x + w / 2 - 4}" y="{y + 12}" width="8" height="{h - 24}" fill="#f4f2ee"/>',
         f'<rect x="{x - 10}" y="{y + h}" width="{w + 20}" height="12" rx="3" fill="#ebe7e0"/>']
    for cx0, side in ((x - 34, 1), (x + w - 22, -1)):
        s.append(f'<rect x="{cx0}" y="{y - 26}" width="56" height="{h + 70}" rx="8" fill="{curtain}"/>')
        for k in range(1, 4):
            s.append(f'<line x1="{cx0 + k * 14}" y1="{y - 20}" x2="{cx0 + k * 14}" y2="{y + h + 38}" stroke="{dark(curtain, .1)}" stroke-width="3"/>')
    s.append(f'<rect x="{x - 50}" y="{y - 32}" width="{w + 100}" height="7" rx="3" fill="{INK}"/>')
    return "".join(s)


def frame(x, y, w, h, scheme=("#e0b13a", "#5b6f7c", "#9aa66b")):
    sun, hill1, hill2 = scheme
    ix, iy, iw, ih = x + 24, y + 24, w - 48, h - 48
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{INK}"/>'
            f'<rect x="{x + 8}" y="{y + 8}" width="{w - 16}" height="{h - 16}" fill="#f6f3ee"/>'
            f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="#efe6d6"/>'
            f'<circle cx="{ix + iw * .68}" cy="{iy + ih * .36}" r="{min(iw, ih) * .16}" fill="{sun}"/>'
            f'<path d="M{ix} {iy + ih} L{ix} {iy + ih * .72} Q{ix + iw * .3} {iy + ih * .42} {ix + iw * .58} {iy + ih * .7} T{ix + iw} {iy + ih * .62} L{ix + iw} {iy + ih}Z" fill="{hill1}"/>'
            f'<path d="M{ix} {iy + ih} L{ix} {iy + ih * .86} Q{ix + iw * .45} {iy + ih * .68} {ix + iw} {iy + ih * .84} L{ix + iw} {iy + ih}Z" fill="{hill2}"/>')


def rug(cx, w, c1="#c96f4a", c2="#efe3cf"):
    top, bot = FLOOR + 24, FLOOR + 104
    pts = f"{cx - w / 2 + 50},{top} {cx + w / 2 - 50},{top} {cx + w / 2},{bot} {cx - w / 2},{bot}"
    s = [f'<polygon points="{pts}" fill="{c2}"/>']
    for k, t in enumerate((.25, .5, .75)):
        y = top + (bot - top) * t
        half = (w / 2 - 50) + 50 * t
        s.append(f'<line x1="{cx - half + 8}" y1="{y}" x2="{cx + half - 8}" y2="{y}" stroke="{c1}" stroke-width="7"/>')
    return "".join(s)


# ------------------------------------------------------------------ objetos
def sofa(x, w, c, pillows=("#e0b13a", "#c96f4a")):
    s = [shadow(x + w / 2, w + 30)]
    for lx in (x + 34, x + w - 44):
        s.append(f'<rect x="{lx}" y="{FLOOR - 24}" width="10" height="28" rx="2" fill="{dark(WOOD, .3)}"/>')
    s.append(f'<rect x="{x + 16}" y="262" width="{w - 32}" height="112" rx="26" fill="{dark(c, .12)}"/>')
    n, cw = 3, (w - 92) / 3
    for i in range(n):
        s.append(f'<rect x="{x + 46 + i * cw}" y="276" width="{cw - 8}" height="72" rx="18" fill="{light(c, .03)}"/>')
    s.append(f'<rect x="{x}" y="334" width="{w}" height="86" rx="20" fill="{c}"/>')
    for i in range(n):
        s.append(f'<rect x="{x + 46 + i * cw}" y="326" width="{cw - 8}" height="38" rx="14" fill="{light(c, .08)}"/>')
    for ax in (x - 6, x + w - 46):
        s.append(f'<rect x="{ax}" y="300" width="52" height="122" rx="22" fill="{dark(c, .05)}"/>')
    p1, p2 = pillows
    s.append(f'<rect x="{x + 54}" y="286" width="66" height="58" rx="14" fill="{p1}" transform="rotate(-8 {x + 87} 315)"/>')
    s.append(f'<rect x="{x + w - 122}" y="286" width="66" height="58" rx="14" fill="{p2}" transform="rotate(7 {x + w - 89} 315)"/>')
    return "".join(s)


def floor_lamp(x, shade="#f1e6cf"):
    return (f'<circle cx="{x}" cy="150" r="130" fill="url(#glow)"/>'
            f'<ellipse cx="{x}" cy="{FLOOR - 2}" rx="34" ry="7" fill="{INK}"/>'
            f'<line x1="{x}" y1="160" x2="{x}" y2="{FLOOR - 4}" stroke="{INK}" stroke-width="5"/>'
            f'<path d="M{x - 48} 176 L{x + 48} 176 L{x + 32} 102 L{x - 32} 102 Z" fill="{shade}"/>'
            f'<ellipse cx="{x}" cy="176" rx="48" ry="6" fill="{dark(shade, .12)}"/>')


def plant(x, scale=1.0, pot="#c96f4a", floor=True, base_y=FLOOR, trailing=False):
    k = scale
    py = base_y if floor else base_y
    s = []
    if floor:
        s.append(shadow(x, 90 * k, py + 4, .14))
    s.append(f'<path d="M{x - 40 * k} {py - 78 * k} L{x + 40 * k} {py - 78 * k} L{x + 30 * k} {py} L{x - 30 * k} {py} Z" fill="{pot}"/>')
    s.append(f'<rect x="{x - 44 * k}" y="{py - 86 * k}" width="{88 * k}" height="{14 * k}" rx="{4 * k}" fill="{dark(pot, .12)}"/>')
    rnd = random.Random(int(x * 7 + scale * 100))
    if trailing:
        # jiboia: ramos saem do vaso e caem pela frente da prateleira
        for i in range(7):
            side = -1 if i % 2 else 1
            sx, sy = x + (i - 3) * 6 * k, py - 84 * k
            ex = x + side * (18 + i * 9) * k
            ey = py + (20 + rnd.random() * 110) * k
            cx_, cy_ = ex + side * 18 * k, py - 96 * k
            s.append(f'<path d="M{sx} {sy} Q{cx_} {cy_} {ex} {ey}" fill="none" stroke="{GREENS[2]}" stroke-width="{2.6 * k}"/>')
            for j in range(1, 6):
                t = j / 5
                lx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx_ + t * t * ex
                ly = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy_ + t * t * ey
                s.append(f'<ellipse cx="{lx + side * 5 * k}" cy="{ly}" rx="{10 * k}" ry="{7 * k}" fill="{GREENS[(i + j) % 4]}" transform="rotate({side * 35} {lx + side * 5 * k} {ly})"/>')
        return "".join(s)
    leaves = [(-70, 1.0), (-40, 1.15), (-10, 1.25), (20, 1.15), (50, 1.0), (-55, .8), (35, .85)]
    for i, (ang, ln) in enumerate(leaves):
        L = 120 * k * ln
        import math
        r = math.radians(ang - 90)
        ex, ey = x + math.cos(r) * L, py - 86 * k + math.sin(r) * L
        s.append(f'<line x1="{x}" y1="{py - 86 * k}" x2="{ex}" y2="{ey}" stroke="{GREENS[2]}" stroke-width="{3 * k}"/>')
        s.append(f'<ellipse cx="{ex}" cy="{ey}" rx="{30 * k * ln}" ry="{19 * k * ln}" fill="{GREENS[i % 4]}" transform="rotate({ang} {ex} {ey})"/>')
    return "".join(s)


def rack(x, w, c=WOOD):
    s = [shadow(x + w / 2, w + 20)]
    for lx in (x + 16, x + w - 26):
        s.append(f'<rect x="{lx}" y="{FLOOR - 18}" width="10" height="22" fill="{INK}"/>')
    s.append(f'<rect x="{x}" y="{FLOOR - 92}" width="{w}" height="76" rx="6" fill="{c}"/>')
    s.append(f'<rect x="{x}" y="{FLOOR - 92}" width="{w}" height="8" rx="4" fill="{light(c, .15)}"/>')
    n = 3
    for i in range(1, n):
        xx = x + w * i / n
        s.append(f'<line x1="{xx}" y1="{FLOOR - 80}" x2="{xx}" y2="{FLOOR - 22}" stroke="{dark(c, .2)}" stroke-width="2"/>')
    for i in range(n):
        s.append(f'<rect x="{x + w * (i + .5) / n - 14}" y="{FLOOR - 56}" width="28" height="4" rx="2" fill="{dark(c, .35)}"/>')
    return "".join(s)


def tv(x, y, w):
    h = w * .56
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#111417"/>'
            f'<rect x="{x + 7}" y="{y + 7}" width="{w - 14}" height="{h - 14}" rx="4" fill="url(#screen)"/>'
            f'<path d="M{x + 7} {y + 7} L{x + w * .45} {y + 7} L{x + w * .22} {y + h - 7} L{x + 7} {y + h - 7}Z" fill="#fff" opacity=".05"/>'
            f'<rect x="{x + w / 2 - 50}" y="{y + h}" width="100" height="10" rx="4" fill="#1a1d20"/>')


def soundbar(x, y, w=210):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="22" rx="11" fill="#1f2326"/>'
            f'<rect x="{x + 12}" y="{y + 8}" width="{w - 24}" height="6" rx="3" fill="#33383d"/>')


def speaker(x, y, c="#2f7f7a"):
    return (f'<rect x="{x}" y="{y}" width="64" height="86" rx="16" fill="{c}"/>'
            f'<circle cx="{x + 32}" cy="{y + 50}" r="20" fill="{dark(c, .3)}"/><circle cx="{x + 32}" cy="{y + 50}" r="8" fill="{dark(c, .5)}"/>'
            f'<circle cx="{x + 32}" cy="{y + 16}" r="5" fill="{dark(c, .3)}"/>')


def camera(x, y, c="#9fc7d9"):
    return (f'<rect x="{x}" y="{y}" width="92" height="74" rx="14" fill="{c}"/>'
            f'<rect x="{x}" y="{y}" width="92" height="20" rx="10" fill="{light(c, .35)}"/>'
            f'<circle cx="{x + 46}" cy="{y + 44}" r="23" fill="#e9eef1"/><circle cx="{x + 46}" cy="{y + 44}" r="15" fill="#20262b"/>'
            f'<circle cx="{x + 41}" cy="{y + 39}" r="4" fill="#fff" opacity=".7"/>'
            f'<rect x="{x + 66}" y="{y + 6}" width="16" height="10" rx="2" fill="#20262b"/>')


def headphones(x, y, c="#45494e"):
    return (f'<path d="M{x} {y + 50} Q{x} {y} {x + 40} {y} Q{x + 80} {y} {x + 80} {y + 50}" fill="none" stroke="{c}" stroke-width="8" stroke-linecap="round"/>'
            f'<rect x="{x - 10}" y="{y + 40}" width="24" height="40" rx="10" fill="{c}"/><rect x="{x + 66}" y="{y + 40}" width="24" height="40" rx="10" fill="{c}"/>')


def books_row(x, y_bottom, width, max_h, rnd, lean_last=True):
    s, cx = [], x
    while cx < x + width - 14:
        bw = rnd.choice([12, 14, 16, 18, 20, 24])
        if cx + bw > x + width:
            break
        bh = max_h * rnd.uniform(.62, .95)
        col = rnd.choice(BOOKS)
        s.append(f'<rect x="{cx}" y="{y_bottom - bh}" width="{bw}" height="{bh}" rx="2" fill="{col}"/>')
        s.append(f'<rect x="{cx + 3}" y="{y_bottom - bh + 10}" width="{bw - 6}" height="3" fill="{light(col, .35)}" opacity=".8"/>')
        cx += bw + 1
    return "".join(s)


def bookshelf(x, y, w, h, shelves, fill_fn, c=WOOD_L):
    s = [shadow(x + w / 2, w + 20) if y + h >= FLOOR - 2 else "",
         f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{c}"/>',
         f'<rect x="{x + 10}" y="{y + 10}" width="{w - 20}" height="{h - 20}" fill="{dark(c, .22)}"/>']
    inner = (h - 20) / shelves
    for i in range(shelves):
        top = y + 10 + i * inner
        bottom = top + inner - 8
        s.append(fill_fn(i, x + 18, top + 6, w - 36, bottom))
        s.append(f'<rect x="{x + 10}" y="{bottom}" width="{w - 20}" height="8" fill="{c}"/>')
    return "".join(s)


def fridge(x, w=170):
    return (shadow(x + w / 2, w + 10)
            + f'<rect x="{x}" y="128" width="{w}" height="{FLOOR - 128}" rx="14" fill="url(#steel)"/>'
            + f'<line x1="{x}" y1="236" x2="{x + w}" y2="236" stroke="#9aa2a9" stroke-width="3"/>'
            + f'<rect x="{x + w - 26}" y="160" width="8" height="56" rx="4" fill="#8d959c"/>'
            + f'<rect x="{x + w - 26}" y="256" width="8" height="90" rx="4" fill="#8d959c"/>')


def counter(x, w, cab="#e9e5de", top="#4a4f55"):
    s = [f'<rect x="{x}" y="196" width="{w}" height="126" fill="#f3f1ec"/>']
    for ty in range(196, 322, 21):
        s.append(f'<line x1="{x}" y1="{ty}" x2="{x + w}" y2="{ty}" stroke="#dedad2" stroke-width="2"/>')
    for tx in range(x, x + w, 42):
        s.append(f'<line x1="{tx}" y1="196" x2="{tx}" y2="322" stroke="#dedad2" stroke-width="2"/>')
    s.append(f'<rect x="{x}" y="70" width="{w}" height="112" rx="4" fill="{cab}"/>')
    n = max(2, round(w / 110))
    for i in range(1, n):
        xx = x + w * i / n
        s.append(f'<line x1="{xx}" y1="74" x2="{xx}" y2="178" stroke="{dark(cab, .12)}" stroke-width="2"/>')
    for i in range(n):
        s.append(f'<rect x="{x + w * (i + 1) / n - 16}" y="150" width="6" height="22" rx="3" fill="#9aa2a9"/>')
    s.append(f'<rect x="{x}" y="334" width="{w}" height="{FLOOR - 334}" fill="{cab}"/>')
    for i in range(1, n):
        xx = x + w * i / n
        s.append(f'<line x1="{xx}" y1="340" x2="{xx}" y2="{FLOOR - 6}" stroke="{dark(cab, .12)}" stroke-width="2"/>')
    for i in range(n):
        s.append(f'<rect x="{x + w * i / n + 12}" y="350" width="22" height="6" rx="3" fill="#9aa2a9"/>')
    s.append(f'<rect x="{x - 6}" y="318" width="{w + 12}" height="18" rx="3" fill="{top}"/>')
    return "".join(s)


def coffee_maker(x, y_top=318):
    return (f'<rect x="{x}" y="{y_top - 108}" width="78" height="108" rx="10" fill="#26292d"/>'
            f'<rect x="{x + 10}" y="{y_top - 100}" width="58" height="22" rx="5" fill="#3a3f45"/>'
            f'<circle cx="{x + 56}" cy="{y_top - 89}" r="5" fill="#e0b13a"/>'
            f'<rect x="{x + 18}" y="{y_top - 66}" width="42" height="12" rx="3" fill="#3a3f45"/>'
            f'<path d="M{x + 22} {y_top - 40} h34 v30 a6 6 0 0 1 -6 6 h-22 a6 6 0 0 1 -6 -6z" fill="#f2efe9"/>'
            f'<rect x="{x + 6}" y="{y_top - 6}" width="66" height="6" rx="2" fill="#3a3f45"/>')


def kettle(x, y_top=318, c="#d0d5d9"):
    return (f'<path d="M{x} {y_top} L{x + 6} {y_top - 70} Q{x + 34} {y_top - 84} {x + 62} {y_top - 70} L{x + 68} {y_top} Z" fill="{c}"/>'
            f'<path d="M{x + 66} {y_top - 60} q22 6 20 34" fill="none" stroke="#2b2f33" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M{x + 4} {y_top - 50} l-20 -14" stroke="{dark(c, .1)}" stroke-width="9" stroke-linecap="round"/>'
            f'<rect x="{x + 24}" y="{y_top - 84}" width="20" height="8" rx="4" fill="#2b2f33"/>')


def fruit_bowl(x, y_top=318):
    return (f'<circle cx="{x + 18}" cy="{y_top - 30}" r="15" fill="#e8862e"/><circle cx="{x + 42}" cy="{y_top - 34}" r="16" fill="#c9443a"/>'
            f'<circle cx="{x + 64}" cy="{y_top - 28}" r="14" fill="#9fbf4a"/>'
            f'<path d="M{x} {y_top - 26} h86 a43 26 0 0 1 -86 0z" fill="{WOOD}"/>')


def bed(x, w, c="#8a9a8c", duvet="#f1efe9", blanket="#c96f4a"):
    s = [shadow(x + w / 2, w + 40, FLOOR + 6, .18),
         f'<rect x="{x}" y="206" width="{w}" height="170" rx="18" fill="{c}"/>']
    for k in range(1, 6):
        xx = x + w * k / 6
        s.append(f'<line x1="{xx}" y1="222" x2="{xx}" y2="360" stroke="{dark(c, .1)}" stroke-width="3"/>')
    s.append(f'<rect x="{x - 14}" y="330" width="{w + 28}" height="96" rx="16" fill="{duvet}"/>')
    s.append(f'<rect x="{x - 14}" y="330" width="{w + 28}" height="22" rx="10" fill="{dark(duvet, .05)}"/>')
    s.append(f'<rect x="{x + 28}" y="290" width="{w / 2 - 44}" height="54" rx="16" fill="#ffffff"/>')
    s.append(f'<rect x="{x + w / 2 + 16}" y="290" width="{w / 2 - 44}" height="54" rx="16" fill="#ffffff"/>')
    s.append(f'<rect x="{x - 14}" y="388" width="{w + 28}" height="30" rx="8" fill="{blanket}"/>')
    s.append(f'<rect x="{x - 14}" y="396" width="{w + 28}" height="5" fill="{light(blanket, .3)}"/>')
    return "".join(s)


def nightstand(x, lamp=True, c=WOOD_L):
    s = [shadow(x + 40, 90), f'<rect x="{x}" y="{FLOOR - 82}" width="80" height="78" rx="6" fill="{c}"/>',
         f'<line x1="{x + 6}" y1="{FLOOR - 46}" x2="{x + 74}" y2="{FLOOR - 46}" stroke="{dark(c, .2)}" stroke-width="2"/>',
         f'<circle cx="{x + 40}" cy="{FLOOR - 64}" r="4" fill="{dark(c, .4)}"/><circle cx="{x + 40}" cy="{FLOOR - 28}" r="4" fill="{dark(c, .4)}"/>']
    if lamp:
        s.append(f'<circle cx="{x + 40}" cy="{FLOOR - 150}" r="70" fill="url(#glow)"/>')
        s.append(f'<path d="M{x + 26} {FLOOR - 82} q14 -60 28 0z" fill="#e8dcc4"/>')
        s.append(f'<path d="M{x + 8} {FLOOR - 120} L{x + 72} {FLOOR - 120} L{x + 60} {FLOOR - 164} L{x + 20} {FLOOR - 164}Z" fill="#f4ecdc"/>')
    return "".join(s)


def desk(x, w, c=WOOD_L):
    return (shadow(x + w / 2, w + 20)
            + f'<rect x="{x + 16}" y="{FLOOR - 112}" width="8" height="112" fill="{INK}"/>'
            + f'<rect x="{x + w - 24}" y="{FLOOR - 112}" width="8" height="112" fill="{INK}"/>'
            + f'<rect x="{x}" y="{FLOOR - 124}" width="{w}" height="14" rx="3" fill="{c}"/>')


def monitor(x, y_top, w=230):
    h = w * .58
    return (f'<rect x="{x + w / 2 - 6}" y="{y_top - 54}" width="12" height="54" fill="#3a3f45"/>'
            f'<rect x="{x + w / 2 - 44}" y="{y_top - 6}" width="88" height="6" rx="3" fill="#3a3f45"/>'
            f'<rect x="{x}" y="{y_top - 54 - h}" width="{w}" height="{h}" rx="8" fill="#15181b"/>'
            f'<rect x="{x + 8}" y="{y_top - 46 - h}" width="{w - 16}" height="{h - 16}" rx="3" fill="#1e2a33"/>'
            f'<rect x="{x + 20}" y="{y_top - 34 - h}" width="{w * .42}" height="14" rx="3" fill="#e0b13a"/>'
            f'<rect x="{x + 20}" y="{y_top - 12 - h}" width="{w * .6}" height="8" rx="3" fill="#5b6f7c"/>'
            f'<rect x="{x + 20}" y="{y_top + 2 - h}" width="{w * .5}" height="8" rx="3" fill="#5b6f7c"/>'
            f'<rect x="{x + w * .62}" y="{y_top - 34 - h}" width="{w * .3}" height="{h * .55}" rx="4" fill="#2f7f7a"/>')


def laptop(x, y_top):
    return (f'<path d="M{x + 10} {y_top - 92} h130 a6 6 0 0 1 6 6 v80 h-142 v-80 a6 6 0 0 1 6 -6z" fill="#b9c0c6"/>'
            f'<rect x="{x + 16}" y="{y_top - 86}" width="118" height="74" rx="3" fill="#24313a"/>'
            f'<rect x="{x - 8}" y="{y_top - 8}" width="166" height="8" rx="3" fill="#cfd5da"/>')


def mug(x, y_top, c="#e8dcc4"):
    return (f'<rect x="{x}" y="{y_top - 40}" width="34" height="40" rx="6" fill="{c}"/>'
            f'<path d="M{x + 34} {y_top - 32} q16 2 0 20" fill="none" stroke="{c}" stroke-width="6"/>')


def office_chair(x, c="#3a3f45"):
    return (shadow(x + 50, 120, FLOOR + 6, .14)
            + f'<rect x="{x + 8}" y="{FLOOR - 220}" width="84" height="104" rx="22" fill="{c}"/>'
            + f'<rect x="{x - 4}" y="{FLOOR - 106}" width="108" height="26" rx="12" fill="{light(c, .08)}"/>'
            + f'<rect x="{x + 45}" y="{FLOOR - 82}" width="10" height="50" fill="#2a2d31"/>'
            + f'<path d="M{x + 2} {FLOOR - 26} L{x + 50} {FLOOR - 38} L{x + 98} {FLOOR - 26}" fill="none" stroke="#2a2d31" stroke-width="8" stroke-linecap="round"/>'
            + f'<circle cx="{x + 4}" cy="{FLOOR - 16}" r="8" fill="#2a2d31"/><circle cx="{x + 96}" cy="{FLOOR - 16}" r="8" fill="#2a2d31"/><circle cx="{x + 50}" cy="{FLOOR - 12}" r="8" fill="#2a2d31"/>')


def washer(x, w=170):
    cx, cy = x + w / 2, FLOOR - 82
    return (shadow(x + w / 2, w + 10)
            + f'<rect x="{x}" y="{FLOOR - 200}" width="{w}" height="198" rx="12" fill="#f4f5f6"/>'
            + f'<rect x="{x}" y="{FLOOR - 200}" width="{w}" height="38" rx="12" fill="#e2e6e9"/>'
            + f'<circle cx="{x + w - 30}" cy="{FLOOR - 181}" r="10" fill="#c3c9ce"/>'
            + f'<rect x="{x + 18}" y="{FLOOR - 188}" width="58" height="14" rx="3" fill="#2a3a46"/>'
            + f'<circle cx="{cx}" cy="{cy}" r="60" fill="#cfd5da"/><circle cx="{cx}" cy="{cy}" r="46" fill="url(#glass)"/>'
            + f'<path d="M{cx - 30} {cy + 18} q20 -26 56 -6 q-6 26 -36 30 q-16 -2 -20 -24z" fill="#c96f4a" opacity=".75"/>'
            + f'<path d="M{cx - 12} {cy - 22} q24 -6 34 14" fill="none" stroke="#fff" stroke-width="5" opacity=".5" stroke-linecap="round"/>')


def basket(x, c="#c8a46e"):
    return (shadow(x + 55, 120)
            + f'<path d="M{x} {FLOOR - 96} h110 l-10 94 h-90z" fill="{c}"/>'
            + "".join(f'<line x1="{x + 4}" y1="{FLOOR - 96 + k * 14}" x2="{x + 106}" y2="{FLOOR - 96 + k * 14}" stroke="{dark(c, .15)}" stroke-width="3"/>' for k in range(1, 7))
            + f'<path d="M{x + 6} {FLOOR - 96} q20 -30 50 -12 q30 -22 50 12z" fill="#5b6f7c"/>'
            + f'<path d="M{x + 30} {FLOOR - 100} q20 -22 46 -4z" fill="#e8dcc4"/>')


def wall_shelf(x, y, w, items, c=WOOD_L):
    return items + f'<rect x="{x}" y="{y}" width="{w}" height="12" rx="3" fill="{c}"/>' + \
        f'<rect x="{x + 20}" y="{y + 12}" width="8" height="18" fill="{dark(c, .3)}"/><rect x="{x + w - 28}" y="{y + 12}" width="8" height="18" fill="{dark(c, .3)}"/>'


def bottle(x, y_bottom, h, c):
    return (f'<rect x="{x}" y="{y_bottom - h}" width="42" height="{h}" rx="10" fill="{c}"/>'
            f'<rect x="{x + 12}" y="{y_bottom - h - 16}" width="18" height="18" rx="4" fill="{dark(c, .25)}"/>'
            f'<rect x="{x + 6}" y="{y_bottom - h * .62}" width="30" height="{h * .32}" rx="4" fill="#ffffff" opacity=".75"/>')


def towels(x, y_bottom):
    cols = ["#9fc7d9", "#e8dcc4", "#c96f4a"]
    return "".join(f'<rect x="{x}" y="{y_bottom - 22 * (k + 1)}" width="90" height="20" rx="8" fill="{c}"/>' for k, c in enumerate(cols))


def bicycle(x, y_ground=FLOOR + 70, frame_c="#2f7f7a"):
    r = 62
    a, b = (x, y_ground - r), (x + 190, y_ground - r)
    seat = (x + 70, y_ground - r - 92)
    bar = (x + 160, y_ground - r - 104)
    crank = (x + 92, y_ground - r)
    return (f'<ellipse cx="{x + 95}" cy="{y_ground + 2}" rx="140" ry="9" fill="#000" opacity=".15"/>'
            + "".join(f'<circle cx="{px}" cy="{py}" r="{r}" fill="none" stroke="{INK}" stroke-width="8"/><circle cx="{px}" cy="{py}" r="6" fill="{INK}"/>' for px, py in (a, b))
            + f'<path d="M{a[0]} {a[1]} L{seat[0] + 8} {seat[1] + 24} L{crank[0]} {crank[1]} Z M{seat[0] + 8} {seat[1] + 24} L{bar[0] - 6} {bar[1] + 30} L{crank[0]} {crank[1]} M{bar[0] - 6} {bar[1] + 30} L{b[0]} {b[1]}" fill="none" stroke="{frame_c}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>'
            + f'<line x1="{seat[0] + 8}" y1="{seat[1] + 24}" x2="{seat[0] + 4}" y2="{seat[1] + 6}" stroke="{INK}" stroke-width="6"/>'
            + f'<rect x="{seat[0] - 18}" y="{seat[1]}" width="44" height="10" rx="5" fill="{INK}"/>'
            + f'<line x1="{bar[0] - 6}" y1="{bar[1] + 30}" x2="{bar[0]}" y2="{bar[1]}" stroke="{INK}" stroke-width="6"/>'
            + f'<line x1="{bar[0] - 16}" y1="{bar[1]}" x2="{bar[0] + 22}" y2="{bar[1] - 4}" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'
            + f'<circle cx="{crank[0]}" cy="{crank[1]}" r="12" fill="{INK}"/>')


def bistro(x, c="#2b2f33"):
    s = [shadow(x + 120, 260)]
    for cx in (x, x + 200):
        s.append(f'<path d="M{cx} {FLOOR - 4} L{cx + 6} {FLOOR - 100} M{cx + 40} {FLOOR - 4} L{cx + 34} {FLOOR - 100}" stroke="{c}" stroke-width="5"/>')
        s.append(f'<rect x="{cx - 4}" y="{FLOOR - 104}" width="48" height="10" rx="4" fill="{c}"/>')
        s.append(f'<path d="M{cx + 2} {FLOOR - 104} q20 -80 38 0" fill="none" stroke="{c}" stroke-width="5"/>')
    s.append(f'<line x1="{x + 120}" y1="{FLOOR - 4}" x2="{x + 120}" y2="{FLOOR - 120}" stroke="{c}" stroke-width="7"/>')
    s.append(f'<ellipse cx="{x + 120}" cy="{FLOOR - 2}" rx="34" ry="6" fill="{c}"/>')
    s.append(f'<ellipse cx="{x + 120}" cy="{FLOOR - 124}" rx="70" ry="12" fill="#e8dcc4"/>')
    s.append(f'<rect x="{x + 104}" y="{FLOOR - 160}" width="24" height="34" rx="6" fill="#c96f4a"/>')
    s.append(f'<ellipse cx="{x + 116}" cy="{FLOOR - 166}" rx="18" ry="10" fill="{GREENS[1]}"/>')
    return "".join(s)


def railing(y_top=300):
    s = [f'<rect x="0" y="{y_top}" width="800" height="{FLOOR - y_top}" fill="#cfe3ea" opacity=".55"/>',
         f'<rect x="0" y="{y_top - 8}" width="800" height="10" rx="3" fill="{INK}"/>']
    for x in range(0, 800, 100):
        s.append(f'<rect x="{x}" y="{y_top}" width="6" height="{FLOOR - y_top}" fill="{INK}"/>')
    return "".join(s)


def outdoor_bg():
    return ('<rect width="800" height="600" fill="url(#sky)"/>'
            '<rect x="40" y="150" width="120" height="290" fill="#c6ccd2"/><rect x="180" y="210" width="90" height="230" fill="#b5bdc5"/>'
            '<rect x="560" y="170" width="140" height="270" fill="#c0c7ce"/><rect x="700" y="230" width="100" height="210" fill="#b0b8c0"/>'
            '<ellipse cx="330" cy="420" rx="120" ry="60" fill="#8fbf8a"/><ellipse cx="480" cy="430" rx="110" ry="50" fill="#7fb07c"/>'
            + "".join(f'<rect x="{x}" y="{y}" width="14" height="18" fill="#e6edf2"/>' for x in (60, 90, 120, 580, 620, 660) for y in (180, 220, 260, 300)))


# ------------------------------------------------------------------ cenas (800x600)
def scene(*parts):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">{DEFS}{"".join(parts)}</svg>'


def sala_1():
    return scene(base("#d9d3c8", "#b98a5e"), window(70, 70, 170, 230, "#efe6d6"), frame(420, 84, 180, 130),
                 rug(470, 520), plant(150, 1.0), sofa(300, 380, "#5f7383"), floor_lamp(735))


def sala_2():
    return scene(base("#d9d3c8", "#b98a5e"), frame(80, 70, 120, 160, ("#c96f4a", "#2f7f7a", "#e0b13a")),
                 rack(220, 400), tv(250, 150, 340), soundbar(315, FLOOR - 120), plant(705, .8, "#e8dcc4"),
                 speaker(560, FLOOR - 178, "#45494e"))


def sala_3():
    rnd = random.Random(3)

    def fill(i, x, top, w, bottom):
        if i == 0:
            return books_row(x, bottom, w * .55, bottom - top, rnd) + plant(x + w * .8, .42, "#e8dcc4", False, bottom)
        if i == 1:
            return frame(x + 8, bottom - 92, 76, 92, ("#e0b13a", "#5b6f7c", "#c96f4a")) + books_row(x + 100, bottom, w - 100, bottom - top, rnd)
        return books_row(x, bottom, w, bottom - top, rnd)
    return scene(base("#d9d3c8", "#b98a5e"), bookshelf(230, 80, 340, FLOOR - 80, 3, fill), plant(130, .9, "#5b6f7c"))


def cozinha_1():
    return scene(base("#cfdcd6", "#e6e1d8", "tile"), counter(40, 520), coffee_maker(110), kettle(240), fruit_bowl(360),
                 fridge(590))


def quarto_1():
    return scene(base("#d8d0e0", "#b98a5e"), frame(330, 70, 150, 110, ("#e8dcc4", "#8a5a83", "#9aa66b")),
                 nightstand(110), bed(210, 390), nightstand(630))


def escritorio_1():
    return scene(base("#cfd8e0", "#b98a5e"), window(580, 70, 160, 220, "#e8dcc4"),
                 desk(100, 450), monitor(120, FLOOR - 124, 200), mug(338, FLOOR - 124), laptop(400, FLOOR - 124),
                 office_chair(300), plant(52, .66, "#e8dcc4"))


def escritorio_2():
    rnd = random.Random(11)

    def fill(i, x, top, w, bottom):
        if i == 0:
            return speaker(x + 6, bottom - 86, "#2f7f7a") + camera(x + 92, bottom - 74) + books_row(x + 200, bottom, w * .38, bottom - top, rnd)
        if i == 1:
            return books_row(x, bottom, w * .6, bottom - top, rnd) + headphones(x + w * .72, bottom - 84)
        return books_row(x, bottom, w, bottom - top, rnd)
    shelf = bookshelf(180, 60, 440, FLOOR - 60, 3, fill)
    return scene(base("#cfd8e0", "#b98a5e"), shelf, plant(540, .62, "#e8dcc4", False, 60 + 10 + (FLOOR - 80) / 3 - 8, trailing=True))


def lavanderia_1():
    shelf_items = bottle(110, 150, 70, "#2f7f7a") + bottle(162, 150, 56, "#9fc7d9") + bottle(214, 150, 80, "#e0b13a") + towels(470, 150)
    return scene(base("#e2ddd2", "#e6e1d8", "tile"), wall_shelf(90, 150, 500, shelf_items),
                 washer(110), basket(330), plant(650, .8, "#c96f4a"))


def varanda_1():
    return scene(outdoor_bg(), railing(300), f'<rect y="{FLOOR}" width="800" height="160" fill="#c4b49c"/>',
                 '<rect y="440" width="800" height="160" fill="url(#fs)"/>',
                 bistro(80), bicycle(470), plant(760, .7, "#c96f4a"))


SCENES = {
    "sala-1.jpg": (sala_1, "Sofá, janela e luminária"),
    "sala-2.jpg": (sala_2, "Rack com a TV"),
    "sala-3.jpg": (sala_3, "Estante de livros"),
    "cozinha-1.jpg": (cozinha_1, "Bancada e geladeira"),
    "quarto-1.jpg": (quarto_1, "Cama e criados-mudos"),
    "escritorio-1.jpg": (escritorio_1, "Mesa de trabalho"),
    "escritorio-2.jpg": (escritorio_2, "Estante do escritório"),
    "lavanderia-1.jpg": (lavanderia_1, "Máquina e prateleira"),
    "varanda-1.jpg": (varanda_1, "Mesinha e bicicleta"),
}

ROOMS = [
    ("sala", "SAL", "Sala de estar", ["sala-1.jpg", "sala-2.jpg", "sala-3.jpg"]),
    ("cozinha", "COZ", "Cozinha", ["cozinha-1.jpg"]),
    ("quarto", "QUA", "Quarto", ["quarto-1.jpg"]),
    ("escritorio", "ESC", "Escritório", ["escritorio-1.jpg", "escritorio-2.jpg"]),
    ("lavanderia", "LAV", "Lavanderia", ["lavanderia-1.jpg"]),
    ("varanda", "VAR", "Varanda", ["varanda-1.jpg"]),
]

# (cômodo, zona, nome, detalhes, categoria, qtd, valor, foto, horas atrás)
ITEMS = [
    ("sala", "Sofá", "Sofá de 3 lugares cinza-azulado", "Tecido liso, almofadas de encosto soltas e pés de madeira.", "moveis", "1", 1800, "sala-1.jpg", 400),
    ("sala", "Sofá", "Almofadas decorativas", "Uma mostarda e uma terracota, com capa de linho.", "texteis", "2", 90, "sala-1.jpg", 400),
    ("sala", "Sofá", "Luminária de chão com cúpula de tecido", "Haste preta e cúpula creme, cerca de 1,6 m.", "decoracao", "1", 260, "sala-1.jpg", 399),
    ("sala", "Sofá", "Costela-de-adão em vaso de cerâmica", "Planta grande em vaso terracota.", "plantas", "1", 140, "sala-1.jpg", 399),
    ("sala", "Parede", "Quadro de paisagem com moldura preta", "Impressão com sol e colinas, 60 x 45 cm.", "decoracao", "1", 180, "sala-1.jpg", 398),
    ("sala", "Piso", "Tapete listrado", "Tapete bege com listras terracota, 2 x 1,4 m.", "texteis", "1", 350, "sala-1.jpg", 398),
    ("sala", "Rack", "Smart TV 55 polegadas", "TV 4K com controle remoto.", "eletronicos", "1", 2300, "sala-2.jpg", 380),
    ("sala", "Rack", "Rack de madeira com três portas", "Rack baixo com pés pretos, 1,8 m.", "moveis", "1", 480, "sala-2.jpg", 380),
    ("sala", "Rack", "Soundbar", "Barra de som preta com controle.", "eletronicos", "1", 650, "sala-2.jpg", 379),
    ("sala", "Rack", "Caixa de som de estante", "Caixa preta com alto-falante frontal.", "eletronicos", "1", 300, "sala-2.jpg", 379),
    ("sala", "Estante", "Estante de madeira com três prateleiras", "Madeira clara, 1,2 m de largura.", "moveis", "1", 520, "sala-3.jpg", 360),
    ("sala", "Estante", "Livros variados", "Romances, fotografia e culinária.", "livros", "28", 560, "sala-3.jpg", 360),
    ("cozinha", "Bancada", "Cafeteira espresso", "Cafeteira preta com reservatório de água.", "cozinha", "1", 650, "cozinha-1.jpg", 300),
    ("cozinha", "Bancada", "Chaleira elétrica de inox", "Chaleira de 1,7 L.", "cozinha", "1", 120, "cozinha-1.jpg", 300),
    ("cozinha", "Bancada", "Fruteira de madeira", "Fruteira redonda de madeira clara.", "cozinha", "1", 60, "cozinha-1.jpg", 299),
    ("cozinha", "Geladeira", "Geladeira frost free inox", "Duas portas, cerca de 450 L.", "cozinha", "1", 2600, "cozinha-1.jpg", 299),
    ("cozinha", "Armário", "Micro-ondas 30 L", "Micro-ondas branco.", "cozinha", "1", 380, "", 298),
    ("cozinha", "Armário", "Jogo de panelas antiaderentes (5 peças)", "Panelas com tampa de vidro.", "cozinha", "1", 420, "", 298),
    ("cozinha", "Mesa", "Mesa de jantar com 4 cadeiras", "Tampo de madeira e cadeiras estofadas.", "moveis", "1", 1200, "", 297),
    ("quarto", "Cama", "Cama queen com cabeceira estofada", "Cabeceira verde-acinzentada com gomos.", "moveis", "1", 1500, "quarto-1.jpg", 250),
    ("quarto", "Cama", "Jogo de cama e edredom", "Edredom branco e manta terracota.", "texteis", "1", 320, "quarto-1.jpg", 250),
    ("quarto", "Cabeceira", "Criado-mudo de madeira", "Duas gavetas, madeira clara.", "moveis", "2", 360, "quarto-1.jpg", 249),
    ("quarto", "Cabeceira", "Abajur com cúpula clara", "Base de cerâmica creme.", "decoracao", "2", 180, "quarto-1.jpg", 249),
    ("quarto", "Parede", "Ar-condicionado split 12.000 BTUs", "Inverter, com controle remoto.", "eletronicos", "1", 1900, "", 248),
    ("quarto", "Guarda-roupa", "Guarda-roupa de 6 portas", "Branco, com espelho.", "moveis", "1", 1100, "", 248),
    ("escritorio", "Mesa", "Notebook 14 polegadas", "Notebook prata com carregador.", "eletronicos", "1", 3800, "escritorio-1.jpg", 120),
    ("escritorio", "Mesa", "Monitor 27 polegadas", "Monitor com base ajustável.", "eletronicos", "1", 1100, "escritorio-1.jpg", 120),
    ("escritorio", "Mesa", "Cadeira de escritório ergonômica", "Encosto alto e rodízios.", "moveis", "1", 750, "escritorio-1.jpg", 119),
    ("escritorio", "Mesa", "Mesa de trabalho de madeira", "1,2 m com pés de metal preto.", "moveis", "1", 450, "escritorio-1.jpg", 119),
    ("escritorio", "Mesa", "Caneca de cerâmica", "Caneca creme.", "cozinha", "1", 35, "escritorio-1.jpg", 118),
    ("lavanderia", "Máquina", "Máquina de lavar 11 kg", "Abertura frontal, branca.", "utilidades", "1", 1600, "lavanderia-1.jpg", 60),
    ("lavanderia", "Máquina", "Cesto de roupas de vime", "Cesto com alças.", "utilidades", "1", 80, "lavanderia-1.jpg", 60),
    ("lavanderia", "Prateleira", "Prateleira de madeira", "Prateleira de parede com mãos-francesas.", "moveis", "1", 90, "lavanderia-1.jpg", 59),
    ("lavanderia", "Prateleira", "Toalhas de banho", "Azul, creme e terracota.", "texteis", "3", 120, "lavanderia-1.jpg", 59),
    ("lavanderia", "Armário", "Aspirador vertical sem fio", "Com base de carregamento.", "utilidades", "1", 480, "", 58),
    ("varanda", "Mesa", "Mesa bistrô com 2 cadeiras", "Metal preto e tampo claro.", "moveis", "1", 420, "varanda-1.jpg", 6),
    ("varanda", "Canto", "Bicicleta aro 29", "Quadro verde-petróleo.", "outros", "1", 1300, "varanda-1.jpg", 5),
    ("varanda", "Floreira", "Vasos com plantas", "Vasos de cerâmica com folhagens.", "plantas", "3", 150, "varanda-1.jpg", 2),
]

IA = {"items": [
    {"name": "Caixa de som Bluetooth portátil", "details": "Caixa verde-petróleo com alto-falante frontal.", "cat": "eletronicos", "qty": "1", "value": 280, "zone": "Estante", "existing": "", "confidence": "alta"},
    {"name": "Câmera instantânea azul", "details": "Câmera de filme instantâneo, azul-claro.", "cat": "eletronicos", "qty": "1", "value": 350, "zone": "Estante", "existing": "", "confidence": "alta"},
    {"name": "Fone de ouvido sem fio", "details": "Fone over-ear cinza-escuro.", "cat": "eletronicos", "qty": "1", "value": 220, "zone": "Estante", "existing": "", "confidence": "baixa"},
    {"name": "Livros variados", "details": "Cerca de 30 livros de capa colorida.", "cat": "livros", "qty": "30", "value": 450, "zone": "Estante", "existing": "", "confidence": "media"},
    {"name": "Jiboia em vaso de cerâmica", "details": "Planta pendente em vaso creme.", "cat": "plantas", "qty": "1", "value": 45, "zone": "Estante", "existing": "", "confidence": "alta"},
]}


async def render():
    os.makedirs(os.path.join(SEED, "photos"), exist_ok=True)
    os.makedirs(os.path.join(SEED, "thumbs"), exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 800, "height": 600})
        for name, (fn, _) in SCENES.items():
            await pg.set_content(f'<html><body style="margin:0">{fn()}</body></html>')
            path = os.path.join(SEED, "photos", name)
            await pg.screenshot(path=path, type="jpeg", quality=88, clip={"x": 0, "y": 0, "width": 800, "height": 600})
            im = Image.open(path)
            im.thumbnail((480, 480))
            im.save(os.path.join(SEED, "thumbs", name), "JPEG", quality=80)
        await b.close()


def data():
    from datetime import datetime, timedelta, timezone
    tz = timezone(timedelta(hours=-3))
    # as datas acompanham o dia em que as imagens são tiradas ("há 3 horas" no Início), e os cômodos foram cadastrados
    # ao longo de uns três meses, para Mais > Gráficos ter o patrimônio mês a mês
    now = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    weeks = {"sala": 10, "cozinha": 7, "quarto": 4, "escritorio": 2}
    rooms = []
    for i, (rid, code, name, photos) in enumerate(ROOMS):
        rooms.append({"id": rid, "code": code, "name": name, "order": i, "cover": 0,
                      "photos": [{"file": f, "label": SCENES[f][1]} for f in photos], "updatedAt": now.isoformat()})
    items, seq = [], {}
    for rid, zone, name, details, cat, qty, value, photo, hours in ITEMS:
        seq[rid] = seq.get(rid, 0) + 1
        code = next(r[1] for r in ROOMS if r[0] == rid)
        when = (now - timedelta(hours=hours, weeks=weeks.get(rid, 0))).isoformat()
        items.append({"id": f"{code.lower()}-{seq[rid]:03d}", "room": rid, "seq": seq[rid], "zone": zone, "name": name, "details": details,
                      "cat": cat, "qty": qty, "value": value, "photos": [photo] if photo else [], "checked": False, "flag": None,
                      "approx": True, "source": "foto" if photo else "manual", "createdAt": when, "updatedAt": when})
    doc = {"format": "inventario-casa", "schema": 1, "rev": 1, "updatedAt": now.isoformat(), "rooms": rooms, "items": items}
    with open(os.path.join(SEED, "inventario.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "ia.json"), "w", encoding="utf-8") as f:
        json.dump(IA, f, ensure_ascii=False, indent=1)
    total = sum(i["value"] for i in items)
    print(f"{len(rooms)} cômodos, {len(items)} itens, R$ {total}")


if __name__ == "__main__":
    asyncio.run(render())
    data()
