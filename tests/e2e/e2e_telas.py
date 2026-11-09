"""Todas as telas e janelas em todos os tamanhos (celular de 320 px até computador), claro e escuro:
nada passa da largura (o Chrome do celular encolheria a página), as janelas cabem na altura com os botões
de baixo visíveis, e nenhum texto de botão fica cortado."""
from e2e_lib import main

PAGES = ["#/", "#/buscar", "#/buscar?q=mesa", "#/comodos", "#/c/sala", "#/c/varanda", "#/relatorio", "#/mais", "#/bens", "#/graficos", "#/novidades", "#/categorias", "#/config", "#/config/integracoes", "#/config/aparencia", "#/config/opcoes", "#/sobre"]

# (nome, endereço, como abrir (um seletor ou vários, um depois do outro), seletor que aparece)
DIALOGS = [
    ("ficha", "#/i/sal-001", None, "dialog.sheet h1"),
    ("adicionar", "#/", ".tabbar .plus", "[data-go]"),
    ("item-novo", "#/c/escritorio", '.rhead-actions [data-act="item-new"]', "#f-name"),
    ("bem-novo", "#/bens", '.mscreen [data-act="item-new"]', "#f-name"),
    ("editar-item", "#/i/esc-001", 'dialog.sheet [data-act="item-edit"].primary', "#f-name"),
    ("catalogar", "#/c/quarto", '.rhead-actions [data-act="catalog"]', '[data-ct="upload"]'),
    ("falar", "#/", ".mic-top", ".voice"),
    ("novo-comodo", "#/comodos", '#view [data-act="room-new"]', "#rn-name"),
    ("editar-comodo", "#/c/sala", '.rhead-actions [data-act="room-edit"]', "#re-name"),
    ("mover", "#/i/sal-002", 'dialog.sheet [data-act="item-move"]', "#mv-room"),
    ("versoes", "#/config", '[data-act="versions"]', "dialog .dlg-b"),
    ("categoria", "#/categorias", '[data-act="cat-new"]', "#cn-name"),
    ("foto-comodo", "#/c/sala", ".strip .ph", "dialog.viewer"),
    ("excluir-item", "#/i/var-001", 'dialog.sheet [data-act="item-delete"]', '[data-r="1"]'),
    ("novidades", "#/i/sal-007", 'dialog.sheet [data-act="item-news"]', ".news li"),
    ("conversar", "#/c/sala", ".chat-top", "dialog.chat .chat-ideas"),
    ("selecionar", "#/buscar", ['[data-act="sel-start"]', '[data-act="sel-toggle"]'], ".selbar"),
    ("alterar-varios", "#/buscar", ['[data-act="sel-start"]', '[data-act="sel-toggle"]', '.selbar [data-act="sel-change"]'], "dialog.modal [data-bk]"),
]

CHECK = """() => {
  const bad = [];
  if (innerWidth > screen.width + 1) bad.push('a página ficou mais larga que a tela: ' + innerWidth);
  if (document.documentElement.scrollWidth > innerWidth + 1) bad.push('rolagem para o lado: ' + document.documentElement.scrollWidth);
  const vh = Math.min(innerHeight, screen.height);
  for (const d of document.querySelectorAll('dialog[open]')) {
    const r = d.getBoundingClientRect();
    if (r.left < -1 || r.right > innerWidth + 1) bad.push('janela passa da largura ' + Math.round(r.left) + '..' + Math.round(r.right));
    if (r.bottom > vh + 1) bad.push('janela passa da altura ' + Math.round(r.bottom) + ' > ' + vh);
    const f = d.querySelector('.dlg-f');
    if (f && f.getBoundingClientRect().bottom > vh + 1) bad.push('botões de baixo fora da tela');
  }
  const scope = document.querySelector('dialog[open]:last-of-type') || document;
  for (const b of scope.querySelectorAll('.btn, button')) {
    if (!b.offsetParent || b.closest('.tabbar, .strip, .wgrid, .more-tabs, .seg')) continue;
    const cs = getComputedStyle(b);
    if (cs.overflow === 'visible' && b.scrollWidth > b.clientWidth + 2 && b.clientWidth > 0) bad.push('texto do botão cortado: ' + b.textContent.trim().slice(0, 30));
    const br = b.getBoundingClientRect();
    if (br.width && (br.right > innerWidth + 1 || br.left < -1)) bad.push('botão fora da tela: ' + b.textContent.trim().slice(0, 30));
  }
  // só a parte visível: o que rola dentro da janela passa por baixo dos botões de baixo, e isso é normal
  const clip = (b) => { const r = b.getBoundingClientRect(), box = b.closest('.dlg-b'); if (!box) return r; const c = box.getBoundingClientRect();
    return { left: Math.max(r.left, c.left), right: Math.min(r.right, c.right), top: Math.max(r.top, c.top), bottom: Math.min(r.bottom, c.bottom) }; };
  const btns = [...scope.querySelectorAll('dialog[open] .btn, dialog[open] button')].filter(b => b.offsetParent).map(b => [b, clip(b)]).filter(([, r]) => r.right > r.left && r.bottom > r.top);
  for (let i = 0; i < btns.length; i++) for (let j = i + 1; j < btns.length; j++) {
    const [a, ra] = btns[i], [c, rc] = btns[j];
    if (a.contains(c) || c.contains(a)) continue;
    const ox = Math.min(ra.right, rc.right) - Math.max(ra.left, rc.left), oy = Math.min(ra.bottom, rc.bottom) - Math.max(ra.top, rc.top);
    if (ox > 2 && oy > 2) bad.push('botões um sobre o outro: ' + (a.textContent.trim() || a.getAttribute('aria-label')).slice(0, 20) + ' / ' + (c.textContent.trim() || c.getAttribute('aria-label')).slice(0, 20));
  }
  return bad;
}"""


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p, camera=True, mic=True)
    for size in ("estreito", "cel", "tablet", "pc"):
        for scheme in ("light", "dark"):
            ctx, pg = await r.page(b, size, scheme, accent="lilas" if scheme == "dark" else "verde", perms=["microphone", "camera"])
            for h in PAGES:
                await r.open(pg, h)
                bad = await pg.evaluate(CHECK)
                r.check(not bad, f"[{size} {scheme}] {h}" + (f": {bad[:3]}" if bad else ""))
                if scheme == "light" and size in ("estreito", "tablet"):
                    await r.shot(pg, f"{size}-{h.strip('#/').replace('/', '-').replace('?', '-') or 'inicio'}", full_page=True)
            for name, h, opener, wait in DIALOGS:
                if name in ("falar", "adicionar") and size == "pc":  # no computador: botões no alto, sem a barra de baixo
                    continue
                await r.open(pg, h, ".tag, .sbar, .rooms, .more-tabs, .report, .rhead, #p-cats, .mscreen, dialog[open]")
                for o in opener if isinstance(opener, list) else [opener] if opener else []:
                    await pg.locator(o).first.click()
                    await pg.wait_for_timeout(150)
                await pg.wait_for_selector(wait, timeout=8000)
                await pg.wait_for_timeout(350)
                bad = await pg.evaluate(CHECK)
                r.check(not bad, f"[{size} {scheme}] janela {name}" + (f": {bad[:3]}" if bad else ""))
                if scheme == "dark" and size in ("estreito", "pc"):
                    await r.shot(pg, f"{size}-janela-{name}")
            await ctx.close()
    await b.close()


main("telas", body)
