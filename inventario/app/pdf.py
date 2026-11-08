"""Um PDF simples, feito à mão (só biblioteca padrão): páginas A4 com texto (Helvetica e Helvetica-Bold, que todo leitor
de PDF tem), linhas, retângulos, figuras e fotos JPG. Serve para os relatórios (o de patrimônio do GerencIA, o para
seguro do InventarIA), que precisam ser um arquivo para baixar: o app do Home Assistant no Android não imprime nem salva
PDF pela página. O mesmo arquivo no GerencIA e no InventarIA: ao mudar um, copie para o outro.

Acentos do português entram pela codificação WinAnsi (cp1252); o que não couber nela vira "?"."""
import hashlib
import unicodedata
import zlib

A4 = (595.28, 841.89)

# larguras (em milésimos do tamanho da letra) dos caracteres de 32 a 126, das métricas oficiais da Adobe
_W = {
    False: [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
            556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
            667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556,
            556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584],
    True: [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
           556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
           667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611,
           611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584],
}
_EXTRA = {"·": 278, "…": 1000, "—": 1000, "–": 556, "º": 365, "ª": 370, "°": 400, "€": 556, "“": 333, "”": 333, "‘": 222, "’": 222}
# o que a WinAnsi não tem, trocado por um parecido (o sinal de menos e o "aproximadamente" dos rótulos do app)
_TROCAS = str.maketrans({"−": "–", "≈": "~"})


def largura(texto, tam, negrito=False):
    """Largura do texto em pontos."""
    t = 0
    for c in str(texto).translate(_TROCAS):
        o = ord(c)
        if 32 <= o <= 126:
            t += _W[negrito][o - 32]
        elif c in _EXTRA:
            t += _EXTRA[c]
        else:  # letra acentuada: a largura da letra sem acento
            b = unicodedata.normalize("NFD", c)[:1]
            t += _W[negrito][ord(b) - 32] if b and 32 <= ord(b) <= 126 else 556
    return t * tam / 1000


def cortar(texto, larg, tam, negrito=False):
    """O texto inteiro se couber; senão, cortado com "…"."""
    texto = str(texto)
    if largura(texto, tam, negrito) <= larg:
        return texto
    while texto and largura(texto + "…", tam, negrito) > larg:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def quebrar(texto, larg, tam, negrito=False):
    """O texto em linhas que cabem na largura (quebra nos espaços)."""
    linhas = []
    for par in str(texto).split("\n"):
        atual = ""
        for p in par.split(" "):
            tenta = (atual + " " + p).strip()
            if atual and largura(tenta, tam, negrito) > larg:
                linhas.append(atual)
                atual = p
            else:
                atual = tenta
        linhas.append(atual)
    return linhas


def jpeg_info(dados):
    """(largura, altura, componentes) de um JPG, ou None se não for um."""
    if not dados or dados[:2] != b"\xff\xd8":
        return None
    i, n = 2, len(dados)
    while i + 9 < n:
        if dados[i] != 0xFF:
            i += 1
            continue
        m = dados[i + 1]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7 or m == 0xFF:
            i += 1 if m == 0xFF else 2
            continue
        tam = int.from_bytes(dados[i + 2:i + 4], "big")
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            alt, larg, comp = int.from_bytes(dados[i + 5:i + 7], "big"), int.from_bytes(dados[i + 7:i + 9], "big"), dados[i + 9]
            return (larg, alt, comp) if larg and alt and comp in (1, 3, 4) else None
        i += 2 + tam
    return None


def cor_rgb(hexa):
    h = str(hexa or "").lstrip("#")
    if len(h) != 6:
        return (0, 0, 0)
    try:
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def _texto_pdf(s):
    b = str(s).translate(_TROCAS).encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class Documento:
    """Páginas A4 (em pé ou deitadas). As posições são em pontos, com y contado de cima para baixo (como numa tela)."""

    def __init__(self, titulo="", autor="GerencIA", deitada=False):
        self.titulo, self.autor = titulo, autor
        self.tamanho = (A4[1], A4[0]) if deitada else A4
        self.paginas = []
        self.imagens = []  # (bytes do JPG, (largura, altura, componentes)), na ordem: /Im1, /Im2...
        self._img_k = {}
        self.atual = 0  # a página em que se desenha
        self.nova_pagina()

    @property
    def largura_pagina(self):
        return self.tamanho[0]

    @property
    def altura_pagina(self):
        return self.tamanho[1]

    def nova_pagina(self):
        self.paginas.append([])
        self.atual = len(self.paginas) - 1

    def ir_para(self, k):
        """Volta a desenhar numa página já criada (k a partir de 0), para o rodapé com "Página k de n"."""
        self.atual = k

    def _op(self, s):
        self.paginas[self.atual].append(s if isinstance(s, bytes) else s.encode("ascii"))

    def texto(self, x, y, s, tam=10, negrito=False, cor=(0, 0, 0), alinhar="esquerda", espaco=0):
        """y é a linha de base do texto. alinhar: esquerda, direita (x é a ponta direita) ou centro. espaco: pontos entre
        as letras (como o letter-spacing)."""
        if s is None or str(s) == "":
            return
        w = largura(s, tam, negrito) + espaco * max(0, len(str(s)) - 1)
        if alinhar == "direita":
            x -= w
        elif alinhar == "centro":
            x -= w / 2
        r, g, b = cor
        tc = f"{espaco:.2f} Tc " if espaco else ""
        op = (f"BT /{'F2' if negrito else 'F1'} {tam:.2f} Tf {tc}{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {self.tamanho[1] - y:.2f} Td (".encode("ascii")
              + _texto_pdf(s) + b") Tj ET")
        # o espaço entre as letras fica no estado gráfico: q … Q o devolve para os próximos textos
        self._op(b"q " + op + b" Q" if espaco else op)

    def linha(self, x1, y1, x2, y2, cor=(0, 0, 0), esp=0.5):
        r, g, b = cor
        self._op(f"{r:.3f} {g:.3f} {b:.3f} RG {esp:.2f} w {x1:.2f} {self.tamanho[1] - y1:.2f} m {x2:.2f} {self.tamanho[1] - y2:.2f} l S")

    def retangulo(self, x, y, w, h, borda=None, fundo=None, esp=0.6, raio=0):
        """Retângulo com o canto de cima à esquerda em (x, y); raio arredonda os cantos."""
        ops = []
        if fundo:
            ops.append("{:.3f} {:.3f} {:.3f} rg".format(*fundo))
        if borda:
            ops.append("{:.3f} {:.3f} {:.3f} RG {:.2f} w".format(*borda, esp))
        b = self.tamanho[1] - y - h  # a base, contada de baixo (como o PDF conta)
        r = max(0, min(raio, w / 2, h / 2))
        if r:
            k = r * 0.5523  # o arco de um quarto de círculo em curva de Bézier
            ops.append(" ".join([
                f"{x + r:.2f} {b:.2f} m", f"{x + w - r:.2f} {b:.2f} l",
                f"{x + w - r + k:.2f} {b:.2f} {x + w:.2f} {b + r - k:.2f} {x + w:.2f} {b + r:.2f} c", f"{x + w:.2f} {b + h - r:.2f} l",
                f"{x + w:.2f} {b + h - r + k:.2f} {x + w - r + k:.2f} {b + h:.2f} {x + w - r:.2f} {b + h:.2f} c", f"{x + r:.2f} {b + h:.2f} l",
                f"{x + r - k:.2f} {b + h:.2f} {x:.2f} {b + h - r + k:.2f} {x:.2f} {b + h - r:.2f} c", f"{x:.2f} {b + r:.2f} l",
                f"{x:.2f} {b + r - k:.2f} {x + r - k:.2f} {b:.2f} {x + r:.2f} {b:.2f} c", "h"]))
        else:
            ops.append(f"{x:.2f} {b:.2f} {w:.2f} {h:.2f} re")
        ops.append("B" if fundo and borda else "f" if fundo else "S")
        self._op(" ".join(ops))

    def _caminho_ret(self, x, y, w, h, raio):
        b = self.tamanho[1] - y - h
        r = max(0, min(raio, w / 2, h / 2))
        if not r:
            return f"{x:.2f} {b:.2f} {w:.2f} {h:.2f} re"
        k = r * 0.5523
        return " ".join([
            f"{x + r:.2f} {b:.2f} m", f"{x + w - r:.2f} {b:.2f} l",
            f"{x + w - r + k:.2f} {b:.2f} {x + w:.2f} {b + r - k:.2f} {x + w:.2f} {b + r:.2f} c", f"{x + w:.2f} {b + h - r:.2f} l",
            f"{x + w:.2f} {b + h - r + k:.2f} {x + w - r + k:.2f} {b + h:.2f} {x + w - r:.2f} {b + h:.2f} c", f"{x + r:.2f} {b + h:.2f} l",
            f"{x + r - k:.2f} {b + h:.2f} {x:.2f} {b + h - r + k:.2f} {x:.2f} {b + h - r:.2f} c", f"{x:.2f} {b + r:.2f} l",
            f"{x:.2f} {b + r - k:.2f} {x + r - k:.2f} {b:.2f} {x + r:.2f} {b:.2f} c", "h"])

    def imagem(self, x, y, w, h, jpg, raio=0):
        """Uma foto JPG na caixa (x, y, w, h), cobrindo a caixa toda (cortada no meio, como object-fit: cover), com os
        cantos arredondados por raio. Devolve False se não for um JPG."""
        info = jpeg_info(jpg)
        if not info:
            return False
        chave = hashlib.sha1(jpg).hexdigest()
        if chave not in self._img_k:
            self.imagens.append((jpg, info))
            self._img_k[chave] = len(self.imagens)
        k = self._img_k[chave]
        iw, ih = info[0], info[1]
        esc = max(w / iw, h / ih)
        dw, dh = iw * esc, ih * esc
        dx, dy = x + (w - dw) / 2, y + (h - dh) / 2
        self._op(f"q {self._caminho_ret(x, y, w, h, raio)} W n {dw:.2f} 0 0 {dh:.2f} {dx:.2f} {self.tamanho[1] - dy - dh:.2f} cm /Im{k} Do Q")
        return True

    def poligono(self, pontos, fundo=(0, 0, 0)):
        """Uma figura cheia pelos pontos [(x, y), ...] (y de cima para baixo), como o raio da CorrerIA Code."""
        if len(pontos) < 3:
            return
        alt = self.tamanho[1]
        caminho = " ".join(f"{x:.2f} {alt - y:.2f} {'m' if k == 0 else 'l'}" for k, (x, y) in enumerate(pontos))
        self._op("{:.3f} {:.3f} {:.3f} rg ".format(*fundo) + caminho + " h f")

    def bytes(self):
        objs = []  # objetos na ordem: 1 catálogo, 2 páginas, 3 e 4 fontes, depois (página, conteúdo) de cada página

        def obj(conteudo):
            objs.append(conteudo)
            return len(objs)

        obj(b"<< /Type /Catalog /Pages 2 0 R >>")
        obj(b"")  # as páginas, preenchido depois
        f1 = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        imgs = []
        for jpg, (iw, ih, comp) in self.imagens:
            cs = {1: "/DeviceGray", 3: "/DeviceRGB", 4: "/DeviceCMYK /Decode [1 0 1 0 1 0 1 0]"}[comp]
            imgs.append(obj(("<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %s /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n"
                             % (iw, ih, cs, len(jpg))).encode("ascii") + jpg + b"\nendstream"))
        xobj = (" /XObject << " + " ".join(f"/Im{k + 1} {n} 0 R" for k, n in enumerate(imgs)) + " >>") if imgs else ""
        kids = []
        for ops in self.paginas:
            dados = zlib.compress(b"\n".join(ops))
            c = obj(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(dados) + dados + b"\nendstream")
            p = obj(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >>%s >> /Contents %d 0 R >>"
                     % (self.tamanho[0], self.tamanho[1], f1, f2, xobj, c)).encode("ascii"))
            kids.append(p)
        objs[1] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(f"{k} 0 R" for k in kids), len(kids))).encode("ascii")
        info = obj(b"<< /Title (" + _texto_pdf(self.titulo) + b") /Producer (" + _texto_pdf(self.autor) + b") >>")

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        pos = []
        for i, o in enumerate(objs, 1):
            pos.append(len(out))
            out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        out += b"".join(b"%010d 00000 n \n" % p for p in pos)
        out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, info, xref)
        return bytes(out)
