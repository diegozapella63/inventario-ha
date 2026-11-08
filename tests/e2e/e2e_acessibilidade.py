"""Acessibilidade: botões só de ícone com nome, campos com rótulo e imagens com alt em todas as telas e janelas;
lang="pt-BR"; aria-current nas abas e no menu; janelas com nome; abas de Mais (tablist, tab, tabpanel); chaves com role=switch;
avisos lidos pelo leitor de tela; um título h1 por tela."""
from e2e_lib import main

# o que o leitor de tela não teria como dizer: botão ou link sem nome, imagem sem alt, campo sem rótulo
AUDIT = r"""(sel) => {
  const scope = sel ? [...document.querySelectorAll(sel)].pop() : document;
  if (!scope) return ['nada para conferir: ' + sel];
  const vis = (e) => e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden';
  const txt = (e) => (e.textContent || '').replace(/\s+/g, ' ').trim();
  const ids = (v) => (v || '').split(/\s+/).map((i) => document.getElementById(i)).filter(Boolean).map(txt).join(' ').trim();
  const own = (e) => (e.getAttribute('aria-label') || '').trim() || ids(e.getAttribute('aria-labelledby')) || (e.getAttribute('title') || '').trim();
  const bad = [];
  for (const e of scope.querySelectorAll('button, a[href], [role=button], [role=tab]')) {
    if (!vis(e)) continue;
    const name = own(e) || txt(e) || [...e.querySelectorAll('img[alt]')].map((i) => i.alt).join(' ').trim();
    if (!name) bad.push('sem nome: ' + e.outerHTML.slice(0, 90));
  }
  for (const e of scope.querySelectorAll('img')) if (!e.hasAttribute('alt')) bad.push('imagem sem alt: ' + e.getAttribute('src'));
  for (const e of scope.querySelectorAll('input, select, textarea')) {
    if (e.type === 'hidden' || e.type === 'file' || !vis(e)) continue;
    const lab = own(e) || [...(e.labels || [])].map(txt).join(' ').trim() || (e.getAttribute('placeholder') || '').trim();
    if (!lab) bad.push('campo sem rótulo: ' + (e.id || e.name || e.dataset.input || e.outerHTML.slice(0, 70)));
  }
  return bad;
}"""
DIALOG_NAMES = """[...document.querySelectorAll('dialog[open]')].map(d => (d.getAttribute('aria-label') || '').trim()
  || (d.getAttribute('aria-labelledby') && (document.getElementById(d.getAttribute('aria-labelledby')) || {}).textContent) || '')"""
H1 = "[...document.querySelectorAll('h1')].filter(h => h.getClientRects().length && !h.closest('dialog')).length"


async def body(r, p):
    r.start(search=False)
    r.api("POST", "api/rooms", {"name": "Garagem", "code": "GAR"})
    r.api("PUT", "api/rooms/garagem", {"photos": [{"file": "varanda-1.jpg", "label": ""}]})
    b = await r.browser(p)
    ctx, pg = await r.page(b, "cel", "dark", accent="azul")

    # -- a página
    await r.open(pg, "#/", ".tag")
    r.eq(await pg.get_attribute("html", "lang"), "pt-BR", 'a página diz que está em português do Brasil (lang="pt-BR")')
    r.check(await pg.get_attribute("#toasts", "role") == "status" and await pg.get_attribute("#toasts", "aria-live") == "polite",
            "os avisos ficam numa região que o leitor de tela lê sozinho (role=status, aria-live)")
    tag = await pg.get_attribute(".hero .tag", "aria-label")
    r.check(tag.startswith("Patrimônio: R$") and "38 itens" in tag, f"a etiqueta do total é lida como uma frase ({tag})")

    # -- telas: nada sem nome, um h1 por tela, a aba certa marcada
    screens = [("#/", "home"), ("#/buscar?q=mesa", "search"), ("#/comodos", "rooms"), ("#/c/sala", "rooms"), ("#/relatorio", "data"),
               ("#/mais", "data"), ("#/graficos", "data"), ("#/novidades", "data"), ("#/categorias", "data"), ("#/config", "data"), ("#/config/integracoes", "data"), ("#/config/aparencia", "data"), ("#/config/opcoes", "data"), ("#/sobre", "data")]
    for h, tab in screens:
        await r.open(pg, h)
        await pg.wait_for_timeout(300)
        bad = await pg.evaluate(AUDIT, None)
        cur = await pg.evaluate("[...document.querySelectorAll('.tabbar [aria-current=page]')].map(a => a.dataset.tab)")
        h1 = await pg.evaluate(H1)
        r.check(not bad and cur == [tab] and h1 == 1, f"{h}: tudo com nome, um título h1 e a aba {tab} marcada" + (f" ({bad[:3]}, {cur}, h1={h1})" if bad or cur != [tab] or h1 != 1 else ""))

    # -- nomes que o navegador calcula para os botões só de ícone
    await r.open(pg, "#/buscar?q=mesa", ".sbar")
    r.eq(await pg.get_by_role("button", name="Limpar busca", exact=True).count(), 1, "o X da busca se chama Limpar busca")
    await r.open(pg, "#/c/sala", ".rhead")
    r.check(await pg.get_by_role("button", name="Editar cômodo", exact=True).is_visible(), "no celular, o lápis (só o ícone) se chama Editar cômodo")
    r.check(await pg.get_by_role("list", name="Fotos do cômodo").count() == 1 and await pg.get_by_role("listitem", name="Rack com a TV").count() == 1,
            "a fileira de fotos é uma lista com nome, e cada foto diz o que mostra")
    photo_buttons = await pg.get_by_role("button", name="Rack com a TV").count()
    r.eq(photo_buttons, 1, "e cada foto continua sendo um botão para o leitor de tela")

    # -- janelas: todas com nome, e nada sem nome dentro
    dialogs = [
        ("ficha", "#/i/sal-002", None, "dialog.sheet h1", "Almofadas decorativas"),
        ("foto grande", "#/i/sal-002", "dialog.sheet .gal-main", "dialog.viewer", "Foto"),
        ("cadastro", "#/c/garagem", '.rhead-actions [data-act="item-new"]', "#f-name", "Novo item"),
        ("fotos do cômodo", None, '[data-ed="roomphotos"]', "dialog .pick", "Fotos do cômodo"),
        ("mover", "#/i/sal-002", 'dialog.sheet [data-act="item-move"]', "#mv-room", "Mover item"),
        ("excluir", "#/i/sal-002", 'dialog.sheet [data-act="item-delete"]', '[data-r="1"]', "Excluir este item?"),
        ("adicionar", "#/", ".tabbar .plus", "[data-go]", "Adicionar"),
        ("catalogar", "#/c/quarto", '.rhead-actions [data-act="catalog"]', '[data-ct="upload"]', "Catalogar itens com IA"),
        ("editar cômodo", "#/c/sala", '.rhead-actions [data-act="room-edit"]', "#re-name", "Editar cômodo"),
        ("nova categoria", "#/categorias", '[data-act="cat-new"]', "#cn-name", "Nova categoria"),
        ("versões", "#/config", '[data-act="versions"]', "dialog .dlg-b", "Versões anteriores"),
    ]
    for name, h, opener, wait, label in dialogs:
        if h:
            await r.open(pg, h, ".tag, .sbar, .rooms, .more-tabs, .rhead, #p-cats, dialog[open]")
        if opener:
            await pg.locator(opener).first.click()
        await pg.wait_for_selector(wait, timeout=8000)
        await pg.wait_for_timeout(300)
        names = await pg.evaluate(DIALOG_NAMES)
        bad = await pg.evaluate(AUDIT, "dialog[open]")
        if name == "fotos do cômodo":
            unnamed = [x for x in bad if "campo sem rótulo" in x]
            bad = [x for x in bad if x not in unnamed]
            r.check(not unnamed, "Fotos do cômodo: cada foto tem um nome, mesmo sem legenda")
            await r.shot(pg, "fotos-do-comodo")
        r.check(names[-1] == label and not bad, f"janela {name}: chamada {label!r}, nada sem nome dentro" + (f" ({names[-1]!r}, {bad[:3]})" if names[-1] != label or bad else ""))
    await ctx.close()

    # -- computador: menu lateral com aria-current, abas de Mais e chaves
    ctx, pg = await r.page(b, "pc", "light", accent="azul")
    await r.open(pg, "#/c/escritorio", ".rhead")
    cur = await pg.evaluate("[...document.querySelectorAll('.side [aria-current=page]')].map(a => a.textContent.trim())")
    r.check(len(cur) == 1 and "Escritório" in cur[0], f"menu lateral: só o cômodo aberto marcado ({cur})")
    r.eq(await pg.get_attribute(".side nav", "aria-label"), "Seções", "o menu lateral tem nome")
    await r.open(pg, "#/relatorio", ".report")
    r.eq(await pg.evaluate("[...document.querySelectorAll('.side nav [aria-current=page]')].map(a => a.textContent.trim())"), ["Relatório"], "no relatório, Relatório marcado")

    await r.open(pg, "#/config/opcoes", ".more-tabs")
    tabs = await pg.evaluate("""(() => { const l = document.querySelector('.more-tabs'); return { role: l.getAttribute('role'), label: l.getAttribute('aria-label'),
      tabs: [...l.children].map(t => [t.getAttribute('role'), t.getAttribute('aria-selected'), t.getAttribute('aria-controls')]) }; })()""")
    r.check(tabs["role"] == "tablist" and tabs["label"] and all(t[0] == "tab" and t[2] == "mp" for t in tabs["tabs"])
            and [t[1] for t in tabs["tabs"]].count("true") == 1 and tabs["tabs"][-1][1] == "true",
            f"abas de Mais: uma lista de abas com nome, cada aba com role=tab, só Opções selecionada ({[t[1] for t in tabs['tabs']]})")
    panel = await pg.evaluate("(p => [p.getAttribute('role'), p.getAttribute('aria-labelledby')])(document.getElementById('mp'))")
    r.eq(panel, ["tabpanel", "mt-opcoes"], "o conteúdo é o painel da aba, ligado a ela")
    sw = await pg.evaluate("""[...document.querySelectorAll('input[type=checkbox][data-input$=-on]')].map(i => [i.dataset.input, i.getAttribute('role'),
      (document.getElementById(i.getAttribute('aria-labelledby')) || {}).textContent, i.checked])""")
    r.eq(sw, [["news-on", "switch", "Usar novidades", True], ["bens-on", "switch", "Usar bens", True], ["zones-on", "switch", "Usar zonas", False]],
         "Usar novidades, Usar bens e Usar zonas são chaves (role=switch) com nome; novidades e bens ligados, zonas desligadas")
    await pg.click('label.switch:has([data-input="zones-on"])')
    await pg.locator(".toast", has_text="Zonas ligadas").wait_for(timeout=5000)
    r.check(await pg.get_by_role("switch", name="Usar zonas").is_checked(), "ligada, o leitor de tela ouve que está ligada")
    await r.open(pg, "#/config/integracoes", ".more-tabs")
    await pg.wait_for_timeout(500)
    names = await pg.evaluate("[...document.querySelectorAll('[role=switch]')].map(i => (document.getElementById(i.getAttribute('aria-labelledby')) || {}).textContent)")
    r.eq(names, ["Usar IA", "Criar os sensores", "Usar com o CorrerIA"], "Integrações: Usar IA, Criar os sensores e Usar com o CorrerIA são chaves com nome")
    await r.open(pg, "#/config/aparencia", ".more-tabs")
    look = await pg.evaluate("""[document.querySelector('.seg.themes').getAttribute('role'), [...document.querySelectorAll('[data-act=theme]')].map(b => b.getAttribute('aria-pressed')),
      document.querySelector('.swatches').getAttribute('role'), document.getElementById(document.querySelector('.swatches').getAttribute('aria-labelledby')).textContent.trim()]""")
    r.check(look[0] == "group" and look[1].count("true") == 1 and look[2] == "radiogroup" and look[3] == "Cor do app",
            f"Aparência: o tema é um grupo de botões marcáveis e a cor, um grupo de opções com nome ({look})")
    await r.open(pg, "#/i/sal-001", "dialog.sheet h1")
    r.check(await pg.get_by_role("button", name="Ampliar foto").count() == 1 and await pg.get_by_role("button", name="Fechar").count() == 1,
            "ficha: a foto se chama Ampliar foto e o X, Fechar")
    await r.shot(pg, "ficha-pc")
    await ctx.close()
    await b.close()


main("acessibilidade", body)
