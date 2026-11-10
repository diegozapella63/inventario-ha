"""Todas as telas e janelas no tablet, em pé (820 × 1100) e deitado (1100 × 820): nada passa da largura, os botões do
alto aparecem inteiros e alinhados, a barra de abas embaixo em pé e a barra lateral deitado, as abas de Mais com os
ícones, e cada janela no lugar dela (centralizada, a ficha à direita, o visualizador com o painel ao lado ou embaixo)."""
from e2e_lib import SIZES, main

SIZES.setdefault("tablet-deitado", (1100, 820, True))  # só neste teste; o e2e_lib já tem o tablet em pé ("tablet")

PAGES = ["#/", "#/buscar", "#/comodos", "#/c/sala", "#/relatorio", "#/mais", "#/graficos", "#/novidades", "#/categorias", "#/config", "#/config/dados", "#/config/aparencia", "#/config/opcoes", "#/sobre"]
# (nome, endereço, como abrir, o que aparece, tipo da janela)
DIALOGS = [
    ("item-novo", "#/c/escritorio", '.rhead-actions [data-act="item-new"]', "#f-name", "modal"),
    ("ficha", "#/i/sal-001", None, "dialog.sheet h1", "sheet"),
    ("catalogar", "#/c/quarto", '.rhead-actions [data-act="catalog"]', '[data-ct="upload"]', "wide"),
    ("falar", "#/", ".mic-top", ".voice", "wide"),
    ("versoes", "#/config/dados", '[data-act="versions"]', "dialog .dlg-b", "narrow"),
    ("mover", "#/i/sal-002", 'dialog.sheet [data-act="item-move"]', "#mv-room", "narrow"),
    ("foto-comodo", "#/c/sala", ".strip .ph", "dialog.viewer", "viewer"),
    ("adicionar", "#/", ".tabbar .plus", "[data-go]", "narrow"),  # só em pé: deitado não tem a barra de abas
]

PAGE_CHECK = """(mode) => {
  const bad = [], vis = (e) => !!e && getComputedStyle(e).display !== 'none' && e.getClientRects().length > 0, box = (e) => e.getBoundingClientRect();
  if (innerWidth > screen.width + 1 || document.documentElement.scrollWidth > innerWidth + 1) bad.push('rolagem para o lado');
  const top = [...document.querySelectorAll(location.hash.startsWith('#/c/') ? '.rhead-actions .btn' : '.top-actions .btn')];
  if (top.length < 2 || !top.every(vis)) bad.push('botões do alto escondidos (' + top.length + ')');
  if (new Set(top.map(b => Math.round(box(b).height))).size > 1 || new Set(top.map(b => Math.round(box(b).top))).size > 1) bad.push('botões do alto desalinhados');
  for (const b of top) {
    if (b.scrollWidth > b.clientWidth + 2) bad.push('texto cortado: ' + b.textContent.trim());
    if (box(b).right > innerWidth + 1) bad.push('botão do alto fora da tela');
  }
  for (let i = 1; i < top.length; i++) if (box(top[i]).left < box(top[i - 1]).right - 1) bad.push('botões do alto um sobre o outro');
  const tab = document.querySelector('.tabbar'), side = document.querySelector('.side');
  if (mode === 'em pé') {
    if (!vis(tab) || Math.abs(box(tab).bottom - innerHeight) > 1 || tab.querySelectorAll('a, button').length !== 5) bad.push('barra de abas fora do lugar');
    if (vis(side)) bad.push('barra lateral em pé');
  } else {
    if (vis(tab)) bad.push('barra de abas deitado');
    if (!vis(side) || side.querySelectorAll('.side-room').length < 6) bad.push('sem a barra lateral com os cômodos');
  }
  const mt = [...document.querySelectorAll('.more-tabs [role=tab]')];
  if (mt.length) {
    const bar = box(document.querySelector('.more-tabs'));
    if (mt.length < 4 || mt.some(t => box(t).right > bar.right + 1 || box(t).left < bar.left - 1 || t.scrollWidth > t.clientWidth + 2)) bad.push('abas de Mais não cabem');
    if (mt.some(t => !vis(t.querySelector('.ic')))) bad.push('abas de Mais sem os ícones');
    if (new Set(mt.map(t => Math.round(box(t).height))).size > 1) bad.push('abas de Mais de alturas diferentes');
  }
  return bad;
}"""

DIALOG_CHECK = """(kind) => {
  const bad = [], box = (e) => e.getBoundingClientRect();
  if (innerWidth > screen.width + 1 || document.documentElement.scrollWidth > innerWidth + 1) bad.push('rolagem para o lado');
  const d = [...document.querySelectorAll('dialog[open]')].pop(), r = box(d);
  if (r.left < -1 || r.right > innerWidth + 1 || r.top < -1 || r.bottom > innerHeight + 1) bad.push('janela fora da tela');
  const f = d.querySelector('.dlg-f');
  if (f && box(f).bottom > innerHeight + 1) bad.push('botões de baixo fora da tela');
  const want = { modal: 660, narrow: 460, wide: Math.min(980, innerWidth - 32) }[kind];
  if (want) {
    if (Math.abs(r.left - (innerWidth - r.right)) > 2) bad.push('janela não centralizada');
    if (Math.abs(r.width - want) > 1) bad.push('largura ' + Math.round(r.width) + ' em vez de ' + want);
  }
  if (kind === 'sheet' && (Math.abs(r.right - innerWidth) > 1 || Math.abs(r.width - 560) > 1 || Math.abs(r.height - innerHeight) > 1)) bad.push('ficha fora da direita');
  if (kind === 'viewer') {
    const s = box(d.querySelector('.vside')), im = box(d.querySelector('.vimg'));
    const ok = innerWidth >= 900 ? s.left >= im.right - 1 && Math.abs(s.width - 340) <= 1 : s.top >= im.bottom - 1 && Math.abs(s.width - innerWidth) <= 1;
    if (!ok) bad.push('painel do visualizador fora do lugar');
  }
  const btns = [...d.querySelectorAll('.btn, button')].filter(b => b.offsetParent && !b.closest('.strip, .wgrid, .seg'));
  for (const b of btns) if (getComputedStyle(b).overflow === 'visible' && b.scrollWidth > b.clientWidth + 2) bad.push('texto do botão cortado: ' + b.textContent.trim().slice(0, 30));
  for (let i = 0; i < btns.length; i++) for (let j = i + 1; j < btns.length; j++) {
    const a = box(btns[i]), c = box(btns[j]);
    if (btns[i].contains(btns[j]) || btns[j].contains(btns[i])) continue;
    if (Math.min(a.right, c.right) - Math.max(a.left, c.left) > 2 && Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top) > 2) bad.push('botões um sobre o outro');
  }
  return bad;
}"""


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p, camera=True, mic=True)
    for size, mode, scheme, accent in (("tablet", "em pé", "light", "verde"), ("tablet-deitado", "deitado", "dark", "lilas")):
        ctx, pg = await r.page(b, size, scheme, accent=accent, perms=["microphone", "camera"])
        for h in PAGES:
            await r.open(pg, h)
            bad = await pg.evaluate(PAGE_CHECK, mode)
            r.check(not bad, f"[{mode}] {h}: sem rolagem para o lado, botões do alto inteiros e alinhados, abas no lugar" + (f": {bad[:3]}" if bad else ""))
            if h in ("#/", "#/c/sala", "#/mais", "#/config", "#/config/dados"):
                await r.shot(pg, f"{size}-{h.strip('#/').replace('/', '-') or 'inicio'}")
        for name, h, opener, wait, kind in DIALOGS:
            if name == "adicionar" and mode == "deitado":
                continue
            await r.open(pg, h, ".tag, .rooms, .more-tabs, .rhead, dialog[open]")
            if opener:
                await pg.locator(opener).first.click()
            await pg.wait_for_selector(wait, timeout=8000)
            await pg.wait_for_timeout(350)
            bad = await pg.evaluate(DIALOG_CHECK, kind)
            r.check(not bad, f"[{mode}] janela {name} ({kind}): cabe, no lugar, botões inteiros" + (f": {bad[:3]}" if bad else ""))
            if name in ("ficha", "catalogar", "foto-comodo", "item-novo"):
                await r.shot(pg, f"{size}-janela-{name}")
        await ctx.close()
    await b.close()


main("tablet", body)
