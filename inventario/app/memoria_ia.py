"""A Memória da IA: o que a casa pediu para a IA lembrar em toda conversa. Uma lista só, da casa, compartilhada por todos
os apps da família: fica na pasta share do Home Assistant (share/familia/memoria_ia.json), e não dentro de um app. Cada app
tem o cartão Memória da IA (Configurações › Integrações), que lê e escreve aqui, e põe as frases na frente das instruções
da IA dele. Funciona com um app só instalado.

Arquivo igual nos apps em Python (tools/iguais.py); nos apps em Node, lib/memoria-ia.js faz o mesmo. Só biblioteca padrão.

O arquivo: {versao: 1, gravado_em, lista: [{id, texto, em, app, quem?}]} (até 60 frases de 240 letras; só do dono).
"""
import contextlib
import json
import os
import secrets
import threading
import time

ARQUIVO = os.environ.get("MEMORIA_IA_ARQ", "/share/familia/memoria_ia.json")
MAX_FRASES, MAX_LETRAS = 60, 240
TITULO = "O que a casa pediu para lembrar (preferências da casa; use quando tiver a ver com o que você está fazendo):"
VALE_SEG = 30   # a lista lida fica guardada este tempo (outro app pode ter escrito)
_TRAVA = threading.Lock()
_GUARDADO = {}  # arquivo -> (quando, lista)


class ErroMemoria(ValueError):
    """O que dizer à pessoa."""


ESPERA_SEG, VELHA_SEG = 3.0, 10.0   # quanto esperar a vez de gravar; uma trava mais velha que isto ficou de um app que caiu


@contextlib.contextmanager
def _vez(arquivo):
    """A vez de gravar entre os apps: uma pasta ao lado do arquivo (criar a pasta é um passo só, também entre os apps que
    dividem a pasta share). Sem ela, dois apps gravando no mesmo instante liam a mesma lista e um apagava a frase do outro.
    Se a vez não vem (a pasta share não deixa criar, ou outro app demora), grava assim mesmo: melhor que não guardar."""
    trava, tenho, fim = arquivo + ".trava", False, time.monotonic() + ESPERA_SEG
    while True:
        try:
            os.makedirs(os.path.dirname(arquivo), exist_ok=True)
            os.mkdir(trava)
            tenho = True
            break
        except FileExistsError:
            try:
                if time.time() - os.stat(trava).st_mtime > VELHA_SEG:
                    os.rmdir(trava)
                    continue
            except OSError:
                pass   # sumiu agora, ou o caminho não é uma pasta: tenta de novo, até o prazo
        except OSError:
            break
        if time.monotonic() >= fim:
            break
        time.sleep(0.01 + secrets.randbelow(20) / 1000)
    try:
        yield
    finally:
        if tenho:
            with contextlib.suppress(OSError):
                os.rmdir(trava)


def _agora_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _limpa(lista):
    out, vistos = [], set()
    for x in lista if isinstance(lista, list) else []:
        if not isinstance(x, dict):
            continue
        texto = " ".join(str(x.get("texto") or "").split())[:MAX_LETRAS]
        if len(texto) < 3 or texto.lower() in vistos:
            continue
        vistos.add(texto.lower())
        out.append({"id": str(x.get("id") or secrets.token_hex(4))[:16], "texto": texto, "em": str(x.get("em") or "")[:40],
                    "app": str(x.get("app") or "")[:30], **({"quem": str(x["quem"])[:60]} if x.get("quem") else {})})
    return out[:MAX_FRASES]


def ler(arquivo=None, agora=None, fresco=False):
    """A lista de agora: [{id, texto, em, app, quem?}]. Sem o arquivo, ou com ele estragado, []."""
    arquivo = arquivo or ARQUIVO
    agora = time.time() if agora is None else agora
    g = _GUARDADO.get(arquivo)
    if g and not fresco and 0 <= agora - g[0] < VALE_SEG:
        return [dict(x) for x in g[1]]
    try:
        with open(arquivo, encoding="utf-8") as f:
            v = json.load(f)
        lista = _limpa(v.get("lista") if isinstance(v, dict) else None)
    except (OSError, ValueError):
        lista = []
    _GUARDADO[arquivo] = (agora, lista)
    return [dict(x) for x in lista]


def _gravar(arquivo, lista):
    try:
        os.makedirs(os.path.dirname(arquivo), exist_ok=True)
        tmp = f"{arquivo}.{os.getpid()}.{secrets.token_hex(3)}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"versao": 1, "gravado_em": _agora_iso(), "lista": lista}, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, arquivo)
    except OSError as e:
        raise ErroMemoria(f"Não consegui gravar a memória na pasta share ({e.strerror or e}).") from None
    _GUARDADO[arquivo] = (time.time(), lista)


def lembrar(texto, app, quem="", arquivo=None):
    """Guarda uma frase (a mesma não entra duas vezes). Devolve a lista. ErroMemoria diz o que vale."""
    arquivo = arquivo or ARQUIVO
    t = " ".join(str(texto or "").split())[:MAX_LETRAS]
    if len(t) < 3:
        raise ErroMemoria("Escreva o que é para lembrar.")
    with _TRAVA, _vez(arquivo):
        lista = ler(arquivo, fresco=True)   # lê de novo: outro app pode ter escrito
        if not any(x["texto"].lower() == t.lower() for x in lista):
            if len(lista) >= MAX_FRASES:
                raise ErroMemoria(f"A memória já tem {MAX_FRASES} frases. Apague alguma.")
            lista.append({"id": secrets.token_hex(4), "texto": t, "em": _agora_iso(), "app": str(app or ""), **({"quem": str(quem)[:60]} if quem else {})})
            _gravar(arquivo, lista)
    return lista


def esquecer(fid, arquivo=None):
    """Tira uma frase pelo id. Devolve a lista."""
    arquivo = arquivo or ARQUIVO
    with _TRAVA, _vez(arquivo):
        lista = ler(arquivo, fresco=True)
        fica = [x for x in lista if x["id"] != str(fid or "")]
        if len(fica) != len(lista):
            _gravar(arquivo, fica)
    return fica


def juntar(textos, app, arquivo=None):
    """Põe várias frases de uma vez (as que um app guardava antes de a memória ser de todos). Devolve quantas entraram."""
    arquivo = arquivo or ARQUIVO
    with _TRAVA, _vez(arquivo):
        lista = ler(arquivo, fresco=True)
        antes = len(lista)
        junta = _limpa(lista + [{"texto": t.get("texto") if isinstance(t, dict) else t, "em": (t.get("em") if isinstance(t, dict) else "") or _agora_iso(),
                                 "app": app, "quem": t.get("quem") if isinstance(t, dict) else ""} for t in textos or []])
        if len(junta) != antes:
            _gravar(arquivo, junta)
    return len(junta) - antes


def para_a_ia(arquivo=None, agora=None):
    """O bloco que vai na frente das instruções da IA ("" sem nada na memória)."""
    lista = ler(arquivo, agora)
    return TITULO + "\n" + "\n".join(f"- {x['texto']}" for x in lista) if lista else ""
