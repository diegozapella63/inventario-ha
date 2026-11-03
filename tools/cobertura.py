#!/usr/bin/env python3
"""Cobertura dos testes, só com a biblioteca padrão (Python 3.12+).

  tools/cobertura.py                 roda unitários, integração e visuais e mostra a cobertura
  tools/cobertura.py --sem-visuais   só unitários e integração (sem o app.js)
  tools/cobertura.py --pasta DIR     só mostra o relatório do que já está gravado em DIR

Servidor (server.py): linhas com comandos executadas por camada e no total (sys.monitoring, tests/cobertura/sitecustomize.py).
Tela (app.js): o Chromium conta o que rodou nos testes visuais (E2E_COV em tests/e2e/e2e_lib.py); a conta é por linha
e por função com nome. As linhas que faltam vão para DIR/faltam-server.txt e DIR/faltam-app.txt.
"""
from __future__ import annotations

import ast
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "inventario", "app")
SERVER = os.path.join(APP, "server.py")
APPJS = os.path.join(APP, "web", "app.js")
LAYERS = (("py-unit", "unitários"), ("py-int", "integração"), ("py-e2e", "visuais"))


# ---------------------------------------------------------------------------- servidor
def py_statements(path: str) -> dict[int, str]:
    """Linhas onde começa um comando que vira código ({linha: nome da função})."""
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    with_code = set()

    def walk(co):
        for _, _, ln in co.co_lines():
            if ln:
                with_code.add(ln)
        for c in co.co_consts:
            if hasattr(c, "co_lines"):
                walk(c)
    walk(compile(src, path, "exec"))
    out = {}

    def visit(node, fn):
        body = getattr(node, "body", None)
        doc = None
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            doc = body[0]
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, ast.stmt) and ch is not doc and not isinstance(ch, (ast.Global, ast.Nonlocal)) and ch.lineno in with_code:
                out.setdefault(ch.lineno, fn)
            visit(ch, ch.name if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn)
    visit(tree, "(módulo)")
    return out


def py_hits(folder: str) -> set[int]:
    hits = set()
    for f in glob.glob(os.path.join(folder, "*.json")):
        try:
            data = json.load(open(f))
        except ValueError:
            continue
        for path, lines in data.items():
            if os.path.samefile(path, SERVER) if os.path.exists(path) else False:
                hits.update(lines)
    return hits


def py_functions(path: str):
    """(nome, primeira linha, linhas de comando do corpo) de cada função."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = {n.lineno for n in ast.walk(node) if isinstance(n, ast.stmt) and n is not node}
            out.append((node.name, node.lineno, inner))
    return out


# ---------------------------------------------------------------------------- tela
def js_map(src: str):
    """Posição em UTF-16 (a do V8) -> linha; e quais posições são código (não espaço)."""
    line_of, code = [], []
    ln = 1
    for ch in src:
        n = 2 if ord(ch) > 0xFFFF else 1
        line_of.extend([ln] * n)
        code.extend([not ch.isspace()] * n)
        if ch == "\n":
            ln += 1
    return line_of, code


def js_covered(folder: str, size: int) -> bytearray | None:
    files = glob.glob(os.path.join(folder, "js-*.json"))
    if not files:
        return None
    total = bytearray(size)
    one, zero = b"\x01", b"\x00"
    for f in files:
        for take in json.load(open(f)):
            arr = bytearray(size)
            for fn in take:  # o V8 manda de fora para dentro: o de dentro vale mais
                for s, e, c in fn:
                    e = min(e, size)
                    if s < e:
                        arr[s:e] = (one if c else zero) * (e - s)
            total = _or(total, arr)
    return total


def _or(a: bytearray, b: bytearray) -> bytearray:
    return bytearray((int.from_bytes(a, "little") | int.from_bytes(b, "little")).to_bytes(len(a), "little"))


SKIP_LINE = re.compile(r"^\s*(?://.*|/\*.*|\*.*|[\]\)\}\s;,]*)$")
JS_FN = re.compile(r"\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(|\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?=(?:\([^()]*\)|[A-Za-z_$][\w$]*)\s*=>)")


def js_report(folder: str):
    src = open(APPJS, encoding="utf-8").read()
    line_of, code = js_map(src)
    cov = js_covered(folder, len(line_of))
    if cov is None:
        return None
    lines = src.split("\n")
    exe, hit = set(), set()
    for i, c in enumerate(code):
        if c:
            ln = line_of[i]
            if SKIP_LINE.match(lines[ln - 1]):
                continue
            exe.add(ln)
            if cov[i]:
                hit.add(ln)
    # posição UTF-16 de cada caractere do texto (para as funções)
    u16, pos = [], 0
    for ch in src:
        u16.append(pos)
        pos += 2 if ord(ch) > 0xFFFF else 1
    fns, miss_fn = 0, []
    for m in JS_FN.finditer(src):
        name = m.group(1) or m.group(2)
        at = m.start() if m.group(1) else m.end()
        fns += 1
        if not cov[u16[at]]:
            miss_fn.append((src.count("\n", 0, at) + 1, name))
    chars = sum(1 for i, c in enumerate(code) if c and line_of[i] in exe)
    chars_hit = sum(1 for i, c in enumerate(code) if c and cov[i] and line_of[i] in exe)
    return {"linhas": len(exe), "linhas_ok": len(hit), "faltam": sorted(exe - hit), "funcoes": fns, "funcoes_faltam": miss_fn,
            "codigo": chars, "codigo_ok": chars_hit}


# ---------------------------------------------------------------------------- relatório
def pct(a, b):
    return f"{100 * a / b:5.1f}%" if b else "   — "


def ranges(nums):
    out, start, prev = [], None, None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}-{prev}" if prev != start else str(start))
            start = prev = n
    if start is not None:
        out.append(f"{start}-{prev}" if prev != start else str(start))
    return out


def report(folder: str):
    stm = py_statements(SERVER)
    total = set(stm)
    print(f"Servidor (server.py): {len(total)} linhas com comandos")
    all_hits = set()
    for sub, label in LAYERS:
        d = os.path.join(folder, sub)
        if not os.path.isdir(d):
            continue
        h = py_hits(d) & total
        all_hits |= h
        print(f"  {label:<12} {pct(len(h), len(total))}  ({len(h)})")
    print(f"  {'tudo junto':<12} {pct(len(all_hits), len(total))}  ({len(all_hits)}; faltam {len(total - all_hits)})")
    fns = py_functions(SERVER)
    never = [(ln, n) for n, ln, inner in fns if inner & total and not (inner & all_hits)]
    print(f"  funções       {pct(len(fns) - len(never), len(fns))}  ({len(fns) - len(never)} de {len(fns)} rodaram)")
    miss = sorted(total - all_hits)
    by_fn = {}
    for ln in miss:
        by_fn.setdefault(stm[ln], []).append(ln)
    with open(os.path.join(folder, "faltam-server.txt"), "w", encoding="utf-8") as f:
        f.write("Funções que nenhum teste chama:\n" + "".join(f"  {ln}: {n}\n" for ln, n in sorted(never)))
        f.write("\nLinhas sem teste, por função (mais linhas primeiro):\n")
        for fn, lns in sorted(by_fn.items(), key=lambda kv: -len(kv[1])):
            f.write(f"  {fn}: {len(lns)} — {', '.join(ranges(lns))}\n")
    js = js_report(folder)
    if js:
        print(f"Tela (app.js), pelos testes visuais: {js['linhas']} linhas com código")
        print(f"  linhas       {pct(js['linhas_ok'], js['linhas'])}  ({js['linhas_ok']}; faltam {len(js['faltam'])})")
        print(f"  código       {pct(js['codigo_ok'], js['codigo'])}  (caracteres que rodaram)")
        print(f"  funções      {pct(js['funcoes'] - len(js['funcoes_faltam']), js['funcoes'])}  ({js['funcoes'] - len(js['funcoes_faltam'])} de {js['funcoes']} com nome rodaram)")
        with open(os.path.join(folder, "faltam-app.txt"), "w", encoding="utf-8") as f:
            f.write("Funções com nome que nenhum teste visual chama:\n" + "".join(f"  {ln}: {n}\n" for ln, n in js["funcoes_faltam"]))
            f.write("\nLinhas sem teste: " + ", ".join(ranges(js["faltam"])) + "\n")
    print(f"O que falta: {folder}/faltam-server.txt" + (f" e faltam-app.txt" if js else ""))


def run(folder: str, visuais: bool):
    py = os.environ.get("PYTHON") or ("python3.12" if subprocess.call(["sh", "-c", "command -v python3.12 >/dev/null"]) == 0 else sys.executable)
    base = dict(os.environ, INV_COV_SRC=APP, PYTHONPATH=os.pathsep.join(filter(None, [os.path.join(ROOT, "tests", "cobertura"), os.environ.get("PYTHONPATH")])))
    code = 0
    for sub, what in (("py-unit", "unit"), ("py-int", "integration")):
        print(f"== {what}", flush=True)
        code |= subprocess.call([os.path.join(ROOT, "tests", "run.sh"), what], env=dict(base, INV_COV_DIR=os.path.join(folder, sub), PYTHON=py))
    if visuais:
        print("== visuais", flush=True)
        code |= subprocess.call([os.path.join(ROOT, "tests", "e2e", "run.sh")],
                                env=dict(base, INV_COV_DIR=os.path.join(folder, "py-e2e"), E2E_COV=folder, E2E_TMP=os.path.join(folder, "e2e")))
    print()
    if code:
        print("Atenção: algum teste falhou; a cobertura abaixo vale para o que rodou.\n")
    return code


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--pasta" in args:
        report(args[args.index("--pasta") + 1])
        sys.exit(0)
    folder = tempfile.mkdtemp(prefix="cobertura-")
    code = run(folder, "--sem-visuais" not in args)
    report(folder)
    sys.exit(code)
