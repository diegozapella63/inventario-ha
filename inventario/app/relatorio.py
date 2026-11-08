"""Relatório para seguro em PDF (Mais > Relatório > Baixar PDF): o app do Home Assistant no Android não imprime a página,
então o arquivo é feito aqui e baixado. O mesmo relatório da tela: o cabeçalho dos relatórios dos apps (o do ResolvIA e do
GerencIA), os números, os gráficos da tela Gráficos (cômodos, categorias, faixas de valor, os mais valiosos e os bens) e um
cômodo depois do outro, com a foto, o código, o item, a zona (com as zonas ligadas), a quantidade e o valor; no pé de cada
página, a marca da CorrerIA Code (como no Mais > Sobre) e o número da página. Sempre claro, A4 em pé.

dados() só monta os números (sem tocar em arquivo); gerar_pdf() desenha, lendo as miniaturas pela função que recebe."""
import math
import re
from datetime import datetime

import pdf

BANDS = [(0, 100, "até 100"), (100, 500, "100–500"), (500, 1000, "500–1 mil"), (1000, 5000, "1–5 mil"), (5000, math.inf, "5 mil+")]
BENS_GROUPS = [("imoveis", "Imóveis"), ("veiculos", "Veículos"), ("", "Outros")]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
TOP = 10  # os mais valiosos, como na tela Gráficos
# o raio da CorrerIA Code (o zap do Lucide, numa caixa de 24), o mesmo do Mais > Sobre
RAIO = [(13, 2), (3, 14), (12, 14), (11, 22), (21, 10), (12, 10)]


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _milhar(n):
    return f"{n:,}".replace(",", ".")


def brl(v, centavos=True):
    """R$ 1.234 (inteiro) ou R$ 1.234,50; centavos=False arredonda (os gráficos)."""
    v = _num(v)
    if not centavos or float(v).is_integer():
        return "R$ " + _milhar(int(round(v)))
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl_k(v):
    """Nas colunas: R$ 900, R$ 1,2 mil, R$ 12 mil, R$ 1,2 mi."""
    v = round(_num(v))
    um = lambda x: f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")  # noqa: E731
    if v >= 1e6:
        return f"R$ {um(v / 1e6)} mi"
    if v >= 1e4:
        return f"R$ {_milhar(round(v / 1000))} mil"
    if v >= 1000:
        return f"R$ {um(v / 1000)} mil"
    return f"R$ {_milhar(int(v))}"


def parte(v, t):
    """A parte do total como na tela: 37%, 4,5%, <1% não (uma casa decimal abaixo de 10)."""
    p = (v / t * 100) if t > 0 else 0
    if p >= 10 or p == 0:
        return f"{round(p)}%"
    return f"{p:.1f}".rstrip("0").rstrip(".").replace(".", ",") + "%"


def plural(n, um, varios):
    return f"{_milhar(n)} {um if n == 1 else varios}"


def qtd(q):
    return re.sub(r"^~\s*", "", str(q if q is not None else "1")).strip() or "1"


def dados(rooms, items, cats, zonas=False, fotos=True, agora=None):
    """Os números do relatório. rooms e items: os que contam (sem os bens com Usar bens desligado); cats: {id: nome}.
    Devolve o cabeçalho, os números, os gráficos e as seções (os cômodos na ordem da casa; os bens por último)."""
    agora = agora or datetime.now()
    ordem = sorted(rooms, key=lambda r: r.get("order") or 0)
    area = next((r for r in ordem if r.get("kind") == "bens"), None)
    comodos = [r for r in ordem if r is not area]
    por = {r["id"]: [] for r in ordem}
    for it in items:
        por.setdefault(it.get("room"), []).append(it)
    for lista in por.values():
        lista.sort(key=lambda i: i.get("seq") or 0)
    tot = {rid: sum(_num(i.get("value")) for i in lista) for rid, lista in por.items()}
    code = {r["id"]: r.get("code") or "ITM" for r in ordem}
    bens = por.get(area["id"], []) if area else []
    bens_total = tot.get(area["id"], 0) if area else 0
    casa = [i for i in items if not (area and i.get("room") == area["id"])]
    casa_total = sum(_num(i.get("value")) for i in casa)

    # os gráficos, como na tela Gráficos
    g_comodos = sorted(({"nome": r["name"], "tag": r.get("code") or "", "sub": plural(len(por.get(r["id"], [])), "item", "itens"),
                         "v": tot.get(r["id"], 0), "n": len(por.get(r["id"], []))} for r in comodos if por.get(r["id"])),
                       key=lambda x: (-x["v"], -x["n"]))
    ct = {}
    for i in casa:
        k = i.get("cat") if i.get("cat") in cats else "outros"
        t = ct.setdefault(k, [0.0, 0])
        t[0] += _num(i.get("value"))
        t[1] += 1
    g_cats = sorted(({"nome": cats.get(k, "Outros"), "sub": plural(n, "item", "itens"), "v": v, "n": n} for k, (v, n) in ct.items()),
                    key=lambda x: (-x["v"], -x["n"]))
    valor = sorted(casa, key=lambda i: -_num(i.get("value")))
    com_valor = [i for i in valor if _num(i.get("value")) > 0]
    faixas = [{"rotulo": rot, "n": len(fx), "v": sum(_num(i.get("value")) for i in fx)}
              for lo, hi, rot in BANDS for fx in [[i for i in com_valor if lo <= _num(i.get("value")) < hi]]]
    nomes = {r["id"]: r["name"] for r in ordem}
    g_top = [{"nome": i.get("name", ""), "sub": nomes.get(i.get("room"), ""), "v": _num(i.get("value"))} for i in com_valor[:TOP]]
    g_bens = [{"nome": i.get("name", ""), "sub": {"imoveis": "Imóvel", "veiculos": "Veículo"}.get(i.get("cat")) or cats.get(i.get("cat")) or "Outro",
               "v": _num(i.get("value"))} for i in sorted(bens, key=lambda i: -_num(i.get("value")))[:TOP]]

    secoes = []
    for r in comodos + ([area] if area and bens else []):
        lista = por.get(r["id"], [])
        if not lista:
            continue
        eh_bens = r is area
        secoes.append({
            "codigo": r.get("code") or "", "nome": r["name"], "bens": eh_bens, "zonas": zonas and not eh_bens, "total": tot.get(r["id"], 0),
            "resumo": (f"{plural(len(lista), 'bem', 'bens')} fora de casa" if eh_bens else plural(len(lista), "item", "itens")) + f", {brl(tot.get(r['id'], 0))}",
            "itens": [{"codigo": f"{code.get(i.get('room'), 'ITM')}-{int(i.get('seq') or 0):03d}", "nome": i.get("name", ""),
                       "detalhes": (i.get("details") or "").strip(), "zona": i.get("zone") or "", "qtd": qtd(i.get("qty")),
                       "valor": _num(i.get("value")), "foto": ((i.get("photos") or [None])[0] if fotos else None)} for i in lista],
        })
    return {
        "quando": f"{agora.day:02d}/{agora.month:02d}/{agora.year} às {agora.hour:02d}:{agora.minute:02d}",
        "dia": agora.strftime("%Y-%m-%d"),
        "contagem": f"{plural(len(casa), 'item', 'itens')} em {plural(len(comodos), 'cômodo', 'cômodos')}",
        "numeros": [("Na casa" if bens else "Patrimônio", brl(casa_total, False)), ("Itens", _milhar(len(casa))),
                    ("Cômodos", _milhar(len(comodos)))] + ([("Bens", brl(bens_total, False))] if bens else []),
        "casa_total": casa_total, "bens_total": bens_total, "fotos": fotos,
        "graficos": [g for g in [
            {"titulo": "Cômodos", "linhas": g_comodos, "total": casa_total} if g_comodos else None,
            {"titulo": "Categorias", "linhas": g_cats, "total": casa_total} if g_cats else None,
            {"titulo": "Faixas de valor", "faixas": faixas, "sem_valor": len(casa) - len(com_valor)} if com_valor else None,
            {"titulo": "Itens mais valiosos", "linhas": g_top, "total": casa_total} if g_top else None,
            {"titulo": "Bens", "linhas": g_bens, "total": bens_total} if g_bens else None,
        ] if g],
        "secoes": secoes,
    }


def nome_arquivo(d):
    return f"inventario-{d['dia']}.pdf"


def _tom(cor, k):
    """A cor misturada com o branco (k = quanto da cor fica)."""
    return tuple(1 - (1 - c) * k for c in cor)


def gerar_pdf(d, cor="#f5c400", tinta=None, ler_foto=lambda nome: None):
    """O PDF do relatório. cor: a cor do app (#rrggbb); tinta: a cor do texto em destaque (a cor do app escurecida, que
    se lê no branco); ler_foto(nome): os bytes da miniatura (JPG) ou None."""
    A = pdf.cor_rgb(cor if re.fullmatch(r"#[0-9a-fA-F]{6}", cor or "") else "#f5c400")
    T = pdf.cor_rgb(tinta) if re.fullmatch(r"#[0-9a-fA-F]{6}", tinta or "") else tuple(c * 0.62 for c in A)
    FG, MUT, LIN, LIN2, CARD = pdf.cor_rgb("#141a22"), pdf.cor_rgb("#5b6573"), pdf.cor_rgb("#e3e7ec"), pdf.cor_rgb("#eef1f4"), pdf.cor_rgb("#f6f7f9")
    doc = pdf.Documento("Relatório para seguro · InventarIA", "InventarIA")
    M = 40
    W = doc.largura_pagina - 2 * M
    FIM = doc.altura_pagina - 64  # o pé: uma linha e a marca da CorrerIA Code
    y = [M]

    def icone(x, top, s):
        """O ícone do app: a etiqueta com R$, na cor do app (em pé: o texto do PDF não gira)."""
        u = s / 32

        def P(px, py):
            return (x + px * u, top + py * u)
        doc.poligono([P(10, 8), P(28, 8), P(30.5, 10.5), P(30.5, 23.5), P(28, 26), P(10, 26), P(3, 19), P(3, 15)], A)
        doc.poligono([P(7 + 2.3 * math.cos(t / 10 * math.tau), 17 + 2.3 * math.sin(t / 10 * math.tau)) for t in range(10)], (1, 1, 1))
        rx, ry = P(20.5, 21.2)
        doc.texto(rx, ry, "R$", 10.5 * u * 0.92, True, FG, "centro")

    def novo():
        doc.nova_pagina()
        y[0] = M
        doc.texto(M, y[0] + 10, "Relatório para seguro · InventarIA", 9, False, MUT)
        y[0] += 26

    def cabe(h):
        if y[0] + h > FIM:
            novo()

    # o cabeçalho dos relatórios dos apps: a faixa na cor do app, o ícone, o app, o título, a contagem e quando
    h = 88
    doc.retangulo(M, y[0], W, h, borda=LIN, fundo=CARD, raio=10)
    doc.retangulo(M, y[0], 5, h, fundo=A)
    icone(M + 18, y[0] + 18, 52)
    tx = M + 84
    w1 = pdf.largura("Inventar", 15, True)
    doc.texto(tx, y[0] + 24, "Inventar", 15, True, FG)
    doc.texto(tx + w1, y[0] + 24, "IA", 15, True, T)
    doc.texto(tx + w1 + pdf.largura("IA", 15, True) + 6, y[0] + 24, "· inventário da casa", 10, False, MUT)
    doc.texto(tx, y[0] + 52, "Relatório para seguro", 22, True, FG)
    doc.texto(tx, y[0] + 72, f"{d['contagem']} · {d['quando']}", 10, False, MUT)
    y[0] += h + 14

    # os números
    n = len(d["numeros"])
    gap = 10
    tw = (W - gap * (n - 1)) / n
    for k, (rot, val) in enumerate(d["numeros"]):
        x = M + k * (tw + gap)
        doc.retangulo(x, y[0], tw, 50, borda=LIN, raio=8)
        doc.texto(x + 12, y[0] + 18, rot, 9, False, MUT)
        doc.texto(x + 12, y[0] + 40, pdf.cortar(val, tw - 24, 17, True), 17, True, FG)
    y[0] += 64

    # os gráficos, dois a dois, cada um num cartão (como na tela Gráficos)
    LIN_G = 24

    def altura(g):
        if "faixas" in g:
            return 34 + 104 + (14 if g["sem_valor"] else 0) + 6
        return 34 + len(g["linhas"]) * LIN_G + 4

    def grafico(g, x, top, w, h):
        doc.retangulo(x, top, w, h, borda=LIN, raio=8)
        ix, iw = x + 12, w - 24
        doc.texto(ix, top + 20, g["titulo"], 12.5, True, FG)
        cy = top + 32
        if "faixas" in g:
            fx = g["faixas"]
            mx = max([f["n"] for f in fx] + [1])
            cw = iw / len(fx)
            base = cy + 70
            for k, f in enumerate(fx):
                bx = ix + k * cw + cw * 0.2
                bw = cw * 0.6
                bh = (f["n"] / mx) * 56 if f["n"] else 0
                doc.retangulo(bx, cy + 14, bw, 56, fundo=LIN2, raio=3)
                if bh:
                    doc.retangulo(bx, base - bh, bw, bh, fundo=A, raio=3)
                doc.texto(bx + bw / 2, cy + 9, _milhar(f["n"]), 9.5, True, FG, "centro")
                doc.texto(bx + bw / 2, base + 12, f["rotulo"], 7.5, False, MUT, "centro")
                doc.texto(bx + bw / 2, base + 23, brl_k(f["v"]) if f["n"] else "–", 7.5, True, FG, "centro")
            if g["sem_valor"]:
                doc.texto(ix, base + 38, f"{plural(g['sem_valor'], 'item está', 'itens estão')} sem valor.", 8.5, False, MUT)
            return
        mx = max([l["v"] for l in g["linhas"]] + [1])
        for l in g["linhas"]:
            val = brl(l["v"], False)
            pv = parte(l["v"], g["total"])
            vw = max(pdf.largura(val, 10, True), pdf.largura(pv, 7.5)) + 10
            nome = (l.get("tag") + "  " if l.get("tag") else "") + l["nome"]
            nome = pdf.cortar(nome, iw - vw - 4, 9.5, True)
            doc.texto(ix, cy + 9, nome, 9.5, True, FG)
            if l.get("sub"):
                sx = ix + pdf.largura(nome, 9.5, True) + 6
                if sx + pdf.largura(l["sub"], 8) < ix + iw - vw:
                    doc.texto(sx, cy + 9, l["sub"], 8, False, MUT)
            doc.texto(ix + iw, cy + 9, val, 10, True, FG, "direita")
            doc.texto(ix + iw, cy + 18.5, pv, 7, False, MUT, "direita")
            bw = iw - vw
            doc.retangulo(ix, cy + 13.5, bw, 4, fundo=LIN2, raio=2)
            doc.retangulo(ix, cy + 13.5, max(2, bw * l["v"] / mx), 4, fundo=A, raio=2)
            cy += LIN_G

    gs = d["graficos"]
    cw = (W - 12) / 2
    for k in range(0, len(gs), 2):
        par = gs[k:k + 2]
        h = max(altura(g) for g in par)
        cabe(h)
        for j, g in enumerate(par):
            grafico(g, M + j * (cw + 12), y[0], cw, h)
        y[0] += h + 12
    if gs:
        y[0] += 6

    # os cômodos, um depois do outro
    FOTO = 30
    for s in d["secoes"]:
        cabe(80)

        def cabeca(cont=False):
            cw_ = pdf.largura(s["codigo"], 9, True) + 10
            doc.retangulo(M, y[0] + 2, cw_, 15, borda=LIN, fundo=CARD, raio=3)
            doc.texto(M + 5, y[0] + 13, s["codigo"], 9, True, MUT)
            doc.texto(M + cw_ + 7, y[0] + 14, s["nome"] + (" (continuação)" if cont else ""), 14, True, FG)
            doc.texto(M + W, y[0] + 14, s["resumo"], 9, False, MUT, "direita")
            doc.linha(M, y[0] + 22, M + W, y[0] + 22, A, 1.5)
            y[0] += 30
            # os títulos das colunas
            for xx, t, al in ([(x_cod, "CÓDIGO", "esquerda"), (x_nome, "ITEM", "esquerda")] + ([(x_zona, "ZONA", "esquerda")] if s["zonas"] else [])
                              + [(x_qtd, "QTD.", "direita"), (x_val, "VALOR", "direita")]):
                doc.texto(xx, y[0] + 6, t, 7, True, MUT, al, espaco=0.6)
            y[0] += 10
        com_foto = d["fotos"]
        x_cod = M + (FOTO + 10 if com_foto else 0)
        x_nome = x_cod + 56
        x_val = M + W
        x_qtd = x_val - 92
        x_zona = x_qtd - 86
        larg_nome = (x_zona if s["zonas"] else x_qtd) - x_nome - 22
        cabeca()
        for k, it in enumerate(s["itens"]):
            linhas = pdf.quebrar(it["nome"], larg_nome, 10.5)[:3]
            det = pdf.quebrar(it["detalhes"], larg_nome, 8.5)[:2] if it["detalhes"] else []
            h = max(FOTO + 8 if com_foto else 0, 8 + len(linhas) * 13 + len(det) * 10.5 + 6)
            if y[0] + h > FIM:
                novo()
                cabeca(True)
            if com_foto:
                jpg = ler_foto(it["foto"]) if it["foto"] else None
                if not (jpg and doc.imagem(M, y[0] + 4, FOTO, FOTO, jpg, raio=4)):
                    doc.retangulo(M, y[0] + 4, FOTO, FOTO, fundo=LIN2, raio=4)
            doc.texto(x_cod, y[0] + 15, it["codigo"], 8.5, True, MUT)
            for j, t in enumerate(linhas):
                doc.texto(x_nome, y[0] + 15 + j * 13, t, 10.5, False, FG)
            for j, t in enumerate(det):
                doc.texto(x_nome, y[0] + 13 + len(linhas) * 13 + j * 10.5, t, 8.5, False, MUT)
            if s["zonas"]:
                doc.texto(x_zona, y[0] + 15, pdf.cortar(it["zona"], 80, 9), 9, False, FG)
            doc.texto(x_qtd, y[0] + 15, it["qtd"], 9.5, False, FG, "direita")
            doc.texto(x_val, y[0] + 15, brl(it["valor"]), 10, True, FG, "direita")
            y[0] += h
            doc.linha(x_cod if com_foto else M, y[0], M + W, y[0], LIN2, 0.6)
        cabe(26)
        doc.texto(M, y[0] + 16, "Total dos bens" if s["bens"] else "Subtotal", 10, True, FG)
        doc.texto(M + W, y[0] + 16, brl(s["total"]), 10.5, True, FG, "direita")
        y[0] += 36
    if not d["secoes"]:
        doc.texto(M, y[0] + 12, "Nenhum item cadastrado.", 11, False, MUT)

    # no pé de cada página: a marca da CorrerIA Code (como no Mais > Sobre) e, com mais de uma, o número da página
    n = len(doc.paginas)
    oque = "DESENVOLVIMENTO DE SOFTWARES"
    nome_w = pdf.largura("CorrerIA Code", 10.5, True)
    bloco = 16 + 8 + max(nome_w, pdf.largura(oque, 6, True) + 0.9 * (len(oque) - 1))
    ang = math.radians(-8)
    for k in range(n):
        doc.ir_para(k)
        fy = doc.altura_pagina - 34
        doc.linha(M, fy - 16, M + W, fy - 16, LIN, 0.8)
        bx = doc.largura_pagina / 2 - bloco / 2
        cx, cy = bx + 8, fy + 1

        def gira(px, py):
            return (cx + px * math.cos(ang) - py * math.sin(ang), cy + px * math.sin(ang) + py * math.cos(ang))
        quad = []
        for ox, oy, ini in ((4, 4, 0), (-4, 4, 90), (-4, -4, 180), (4, -4, 270)):
            for j in range(7):
                t = math.radians(ini + j * 15)
                quad.append(gira(ox + 4 * math.cos(t), oy + 4 * math.sin(t)))
        doc.poligono(quad, A)
        doc.poligono([gira((px - 12) * 0.46, (py - 12) * 0.46) for px, py in RAIO], pdf.cor_rgb("#1a1210"))
        tx = bx + 24
        doc.texto(tx, fy, "Correr", 10.5, True, FG)
        doc.texto(tx + pdf.largura("Correr", 10.5, True), fy, "IA", 10.5, True, T)
        doc.texto(tx + pdf.largura("CorrerIA", 10.5, True), fy, " Code", 10.5, True, FG)
        doc.texto(tx, fy + 9, oque, 6, True, MUT, espaco=0.9)
        if n > 1:
            doc.texto(M + W, fy + 4, f"página {k + 1} de {n}", 8, False, MUT, "direita")
    return doc.bytes()
