"""Todas as telas e janelas em todos os tamanhos (celular de 320 px até computador), claro e escuro:
nada passa da largura (o Chrome do celular encolheria a página), as janelas cabem na altura com os botões
de baixo visíveis, e nenhum texto de botão fica cortado."""
from e2e_lib import main

PAGES = ["#/", "#/buscar", "#/buscar?q=mesa", "#/comodos", "#/c/sala", "#/c/varanda", "#/relatorio", "#/mais", "#/bens", "#/consumiveis", "#/graficos", "#/novidades", "#/pesquisas/recursos", "#/pesquisas/pareceres", "#/categorias", "#/config", "#/config/dados", "#/config/aparencia", "#/config/opcoes", "#/sobre"]

# (nome, endereço, como abrir (um seletor ou vários, um depois do outro), seletor que aparece)
DIALOGS = [
    ("ficha", "#/i/sal-001", None, "dialog.sheet h1"),
    ("adicionar", "#/", ".tabbar .plus", "[data-go]"),
    ("item-novo", "#/c/escritorio", '.rhead-actions [data-act="item-new"]', "#f-name"),
    ("bem-novo", "#/bens", '.mscreen [data-act="item-new"]', "#f-name"),
    ("consumivel-novo", "#/consumiveis", ".tabbar .plus:visible, .top-actions [data-act='item-new']:visible", "#f-name"),
    ("editar-item", "#/i/esc-001", 'dialog.sheet [data-act="item-edit"].primary', "#f-name"),
    ("catalogar", "#/c/quarto", '.rhead-actions [data-act="catalog"]', '[data-ct="upload"]'),
    ("falar", "#/", ".mic-top", ".voice"),
    ("novo-comodo", "#/comodos", '#view [data-act="room-new"]', "#rn-name"),
    ("editar-comodo", "#/c/sala", '.rhead-actions [data-act="room-edit"]', "#re-name"),
    ("mover", "#/i/sal-002", 'dialog.sheet [data-act="item-move"]', "#mv-room"),
    ("versoes", "#/config/dados", '[data-act="versions"]', "dialog .dlg-b"),
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
  // 1.59.0 (padrão da família): toda seção com o cabeçalho com ícone; toda linha com título com ícone; todo botão com texto
  // com ícone; sem linha entre as linhas de opções nem no fim das listas (a linha fica só no fim de cada seção principal)
  for (const sec of document.querySelectorAll('#view section.panel')) {
    if (!sec.offsetParent) continue;
    const h = sec.querySelector(':scope > h2');
    if (!h || !h.querySelector('.sec-ic')) bad.push('seção sem o cabeçalho com ícone: ' + (sec.id || sec.className));
  }
  for (const b of document.querySelectorAll('.opts:not(.cats):not(.bk-lista):not(.versions) > li > .ot > b')) {
    if (b.offsetParent && !b.querySelector('.ot-ic, .status')) bad.push('linha sem ícone: ' + b.textContent.trim().slice(0, 30));
  }
  for (const b of scope.querySelectorAll('.btn, button.chip, .toast button')) {
    if (!b.offsetParent || !b.textContent.trim() || b.querySelector('svg, .spin')) continue;
    bad.push('botão sem ícone: ' + b.textContent.trim().slice(0, 30));
  }
  for (const li of document.querySelectorAll('.opts:not(.cats):not(.bk-lista):not(.versions) > li')) {
    if (li.offsetParent && parseFloat(getComputedStyle(li).borderBottomWidth) > 0) { bad.push('linha entre as opções: ' + li.textContent.trim().slice(0, 30)); break; }
  }
  for (const l of document.querySelectorAll('.opts, .nlist')) {
    const last = l.lastElementChild, el = last && (last.querySelector(':scope > .nrow') || last);
    if (el && el.offsetParent && parseFloat(getComputedStyle(el).borderBottomWidth) > 0) { bad.push('linha no fim da lista: ' + (l.className)); break; }
  }
  // 1.59.1: o título da tela, os grupos (zonas, Imóveis, Veículos) e o título de cada janela com o ícone
  const pt = document.querySelector('#topbar .page-title');
  if (pt && pt.offsetParent && !pt.querySelector('.sec-ic')) bad.push('título da tela sem ícone: ' + pt.textContent.trim());
  for (const h of document.querySelectorAll('#view .zone-h h3')) if (h.offsetParent && !h.querySelector('.zone-ic')) bad.push('grupo sem ícone: ' + h.textContent.trim());
  for (const h of document.querySelectorAll('dialog[open] .dlg-h h2:not(.sr)')) if (!h.querySelector('.dlg-ic')) bad.push('janela sem ícone no título: ' + h.textContent.trim());
  // 1.60.0: as abas que não cabem mostram a seta do lado de onde há mais; as que cabem, nenhuma
  const tb = document.querySelector('#view .tabs-wrap > .more-tabs');
  if (tb && tb.offsetParent) {
    const w = tb.parentElement, mais = tb.scrollWidth > tb.clientWidth + 2;
    if (mais !== (w.classList.contains('tem-dir') || w.classList.contains('tem-esq'))) bad.push('abas: a seta não bate com o que cabe (' + w.className + ')');
  }
  // 1.60.0 (o padrão do GerencIA): cada seção principal num cartão, com a borda e os cantos arredondados
  for (const sec of document.querySelectorAll('#view .more-panel > section.panel, #view .mscreen > section.panel')) {
    if (!sec.offsetParent) continue;
    const st = getComputedStyle(sec);
    if (!(parseFloat(st.borderTopWidth) > 0 && parseFloat(st.borderBottomWidth) > 0 && parseFloat(st.borderTopLeftRadius) >= 12)) bad.push('seção fora do cartão: ' + (sec.id || sec.className));
  }
  return bad;
}"""


async def body(r, p):
    r.start(search=False)
    # 1.78.0: com os três tipos em uso (os quadros do Agora, a tela Consumíveis e as três chaves das Opções)
    r.api("PUT", "api/settings", {"consumiveis": True})
    con = r.api("POST", "api/rooms", {"kind": "consumiveis"})["room"]["id"]
    r.api("POST", "api/items", {"room": con, "name": "Creme de massagem relaxante de arnica", "details": "Creme para massagem nas costas e nas pernas.", "qty": "2 potes", "value": 1234})
    r.api("POST", "api/items", {"room": con, "name": "Pilhas AA", "cat": "utilidades", "qty": "8"})
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
