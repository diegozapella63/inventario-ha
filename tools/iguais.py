#!/usr/bin/env python3
"""Os arquivos que são iguais nos apps da família (as caixas de seleção, o Sobre, o Falar, a Conversa, o PDF...): a
lista fica aqui, e este arquivo também é igual em todos os repositórios (tools/iguais.py).

  python3 tools/iguais.py            confere os deste repositório com os dos outros, ao lado (../resolvia-ha, ...)
  python3 tools/iguais.py --exigir   o mesmo, mas falta de um repositório também é erro (o GitHub baixa todos)
  python3 tools/iguais.py --raiz DIR os repositórios estão em DIR

Mudou um arquivo da lista? Copie o mesmo arquivo para os outros apps do grupo e publique todos. Um arquivo novo que
passa a ser igual entra em GRUPOS (aqui e nas cópias deste arquivo nos outros apps). Só biblioteca padrão do Python."""
import hashlib
import os
import sys

# a pasta de cada repositório (o nome no GitHub é o mesmo, menos o do CorrerIA)
REPOS = ["gerencia-ha", "inventario-ha", "economia-ha", "correria-ha", "resolvia-ha", "cronologia-ha", "memoria-ha"]
GITHUB = {r: "diegozapella63/" + ("CorrerIA-ha" if r == "correria-ha" else r) for r in REPOS}
LIT = ("resolvia-ha", "cronologia-ha", "memoria-ha")  # os apps em Lit (frontend/src) com servidor em Node (lib/)
LIB = {"resolvia-ha": "resolvia/rootfs/app/lib", "cronologia-ha": "cronologia/rootfs/app/lib", "memoria-ha": "memoria/rootfs/app/lib"}


def _src(nome, apps=LIT):
    return [f"{r}/frontend/src/{nome}" for r in apps]


def _lib(nome, apps=LIT):
    return [f"{r}/{LIB[r]}/{nome}" for r in apps]


# cada grupo: (o que é, [repositório/caminho de cada cópia])
GRUPOS = [
    ("as caixas de seleção no visual do app", [
        "gerencia-ha/gerencia/app/www/selectsheet.js", "inventario-ha/inventario/app/web/selectsheet.js",
        "economia-ha/economia/pagina/selectsheet.js", *_src("selectsheet.js")]),
    ("Mais › Sobre", _src("about.js")),
    ("a janela da Conversa", _src("chat.js")),
    ("o Falar (microfone)", _src("voice.js")),
    ("a cor do app e a Cor do dia", _src("look.js")),
    ("arrastar para voltar", _src("swipe.js")),
    ("a escolha de equipamentos", _src("equip-picker.js", ("resolvia-ha", "cronologia-ha"))),
    ("o Uso da IA (a tela)", _src("usage-panel.js")),
    ("o Lit", [f"{r}/frontend/vendor/lit-all.min.js" for r in LIT]),
    ("a fala para texto do Home Assistant (Node)", _lib("voice.js")),
    ("o WebSocket do Home Assistant (Node)", _lib("ws.js")),
    ("o ZIP da exportação", _lib("zip.js")),
    ("a API do Home Assistant (Node)", _lib("ha.js")),
    ("o Uso da IA (o servidor)", _lib("usage.js")),
    ("os celulares de cada pessoa", _lib("phones.js", ("resolvia-ha", "cronologia-ha"))),
    ("a ligação com o CorrerIA e o integracao.json (Node)", _lib("correria.js")),
    ("o PDF do relatório (Node)", _lib("pdf.js", ("resolvia-ha", "memoria-ha"))),
    ("o PDF do relatório (Python)", ["gerencia-ha/gerencia/app/pdf.py", "inventario-ha/inventario/app/pdf.py"]),
    ("o Falar e o WebSocket do Home Assistant (Python)", ["gerencia-ha/gerencia/app/voz.py", "economia-ha/economia/app/voz.py"]),
    ("esta conferência", [f"{r}/tools/iguais.py" for r in REPOS]),
]


def _hash(caminho):
    with open(caminho, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def conferir(raiz, este, exigir=False):
    """(erros, avisos, conferidos): as cópias de cada grupo em que este repositório está, comparadas com a daqui."""
    erros, avisos, n = [], [], 0
    for oque, copias in GRUPOS:
        minhas = [c for c in copias if c.split("/", 1)[0] == este]
        if not minhas:
            continue
        base = minhas[0]
        caminho = os.path.join(raiz, base)
        if not os.path.isfile(caminho):
            erros.append(f"{base} ({oque}) não existe aqui.")
            continue
        h = _hash(caminho)
        for outra in copias:
            if outra == base:
                continue
            repo = outra.split("/", 1)[0]
            if not os.path.isdir(os.path.join(raiz, repo)):
                (erros if exigir else avisos).append(f"{repo} não está em {raiz}: {outra} ({oque}) não foi conferido.")
                continue
            p = os.path.join(raiz, outra)
            if not os.path.isfile(p):
                erros.append(f"{outra} ({oque}) não existe.")
            elif _hash(p) != h:
                erros.append(f"{base} e {outra} ({oque}) estão diferentes: copie o mais novo para o outro.")
            else:
                n += 1
    return erros, avisos, n


def main(args):
    aqui = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    este = os.path.basename(aqui)
    raiz = args[args.index("--raiz") + 1] if "--raiz" in args else os.path.dirname(aqui)
    if este not in REPOS:
        print(f"Este repositório ({este}) não está na lista REPOS de tools/iguais.py.")
        return 1
    erros, avisos, n = conferir(raiz, este, "--exigir" in args)
    for a in avisos:
        print("aviso:", a)
    for e in erros:
        print("ERRO:", e)
    print(f"{n} cópias iguais às daqui" + (f", {len(erros)} com problema." if erros else "."))
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
