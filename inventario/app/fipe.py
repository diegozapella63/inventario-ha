"""Tabela FIPE pela BrasilAPI (1.114.0): o preço médio de um veículo pelo código FIPE (005340-6), um valor por ano-modelo.

Só biblioteca padrão, sem chave. A BrasilAPI é um serviço grátis mantido pela comunidade (sem garantia de estar no ar): quem
guarda o último valor é o server.py. A tabela muda uma vez por mês. O valor é uma referência: nada aqui muda o valor de um bem.
"""
import json
import os
import re
import urllib.error
import urllib.request

BASE = os.environ.get("INV_FIPE", "https://brasilapi.com.br/api/fipe/preco/v1")  # INV_FIPE: só para testes


class Erro(Exception):
    pass


def codigo(v):
    """O código como a FIPE escreve (005340-6); "" se não parece um."""
    d = re.sub(r"\D", "", str(v or ""))
    return f"{d[:6]}-{d[6]}" if len(d) == 7 else ""


def ano(v):
    """O ano-modelo (1950 a 2100; 32000 é o zero quilômetro da FIPE); 0 se não vale."""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return 0
    return n if 1950 <= n <= 2100 or n == 32000 else 0


def separar(texto):
    """«005340-6 2014» (como a pessoa escreve no campo) → ("005340-6", 2014); o que não vale vem vazio ou 0."""
    s = str(texto or "")
    m = re.search(r"(\d{6})\s*-?\s*(\d)(?!\d)", s)
    cod = f"{m[1]}-{m[2]}" if m else ""
    resto = s[m.end():] if m else s
    a = re.search(r"(?<!\d)(19[5-9]\d|20\d\d)(?!\d)", resto)
    return cod, int(a[1]) if a else 0


def _valor(v):
    if isinstance(v, bool):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v) if 0 < v < 1e9 else 0.0
    t = re.sub(r"[^0-9,]", "", str(v or "")).replace(",", ".")
    try:
        n = float(t)
    except ValueError:
        return 0.0
    return n if 0 < n < 1e9 else 0.0


def da_resposta(d):
    """As linhas que valem de uma resposta: [{ano, combustivel, valor, marca, modelo, mes}], o ano mais novo primeiro."""
    out = []
    for x in d if isinstance(d, list) else []:
        if not isinstance(x, dict):
            continue
        a, v = ano(x.get("anoModelo")), _valor(x.get("valor"))
        if a and v:
            out.append({"ano": a, "combustivel": str(x.get("combustivel") or "")[:30], "valor": round(v, 2), "marca": str(x.get("marca") or "")[:60],
                        "modelo": str(x.get("modelo") or "")[:120], "mes": str(x.get("mesReferencia") or "").strip()[:30]})
    out.sort(key=lambda x: (-x["ano"], x["combustivel"]))
    return out


def consultar(cod, timeout=15, base=None):
    """As linhas do código na tabela de agora. Erro diz o que houve."""
    c = codigo(cod)
    if not c:
        raise Erro("O código FIPE tem 7 números, como 005340-6.")
    req = urllib.request.Request(f"{base or BASE}/{c}", headers={"Accept": "application/json", "User-Agent": "InventarIA (Home Assistant)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read(400000).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            raise Erro(f"O código {c} não está na Tabela FIPE.") from None
        raise Erro("A consulta da Tabela FIPE não respondeu agora.") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise Erro("A consulta da Tabela FIPE não respondeu agora.") from None
    linhas = da_resposta(d)
    if not linhas:
        raise Erro(f"O código {c} não está na Tabela FIPE.")
    return linhas


def do_ano(linhas, a):
    """A linha do ano-modelo (a de maior valor, se houver mais de um combustível); sem o ano, None."""
    do = [x for x in linhas if x["ano"] == a]
    return max(do, key=lambda x: x["valor"]) if do else None
