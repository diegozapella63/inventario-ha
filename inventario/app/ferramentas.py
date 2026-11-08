"""Ferramentas do InventarIA para o CorrerIA (o WhatsApp e o servidor MCP do Claude e do Gemini): ler o inventário e gravar
(cadastrar, editar, mover e apagar itens; criar cômodo). O CorrerIA lista (GET /api/integracao/ferramentas) e chama uma
(POST {nome, argumentos, pessoa, cliente}); aqui ficam a lista e as regras, e as gravações passam pelas mesmas funções da
tela (o Store do server.py: o número do item no cômodo, a data do valor, as versões automáticas). A tela vê a mudança pelo
/api/rev, como quando outro aparelho muda algo. Nada de fotos, backups, configurações ou chaves. Só biblioteca padrão.

Cada ferramenta: {nome, titulo, descricao, entrada (JSON Schema), grava, apaga}. chamar() recebe o próprio server.py
(srv), para não importar o servidor daqui, e devolve o texto para a IA; um argumento ruim levanta ErroFerramenta (400)."""
from __future__ import annotations

import json
import re

MAX_LISTA = 200   # itens numa busca
PADRAO_LISTA = 50
MAX_LOTE = 30     # itens num cadastro
MAX_MOVER = 60    # itens numa mudança de cômodo
MAX_RESUMO = 10   # os mais valiosos e os últimos cadastrados no resumo


class ErroFerramenta(ValueError):
    pass


# ---------------------------------------------------------------- a lista

def _obj(props, obrig=()):
    return {"type": "object", "properties": props, "required": list(obrig), "additionalProperties": False}


_ID = {"type": "string", "description": "O id do item (ex.: sal-003) ou o código que aparece na tela (ex.: SAL-003)."}
_COMODO = {"type": "string", "description": "O id, o código (ex.: SAL) ou o nome do cômodo; Bens para o que fica fora de casa."}
_CATEGORIA = {"type": "string", "description": "O id ou o nome da categoria (veja inventario_resumo). Padrão: Outros."}
_VALOR = {"type": "number", "minimum": 0, "description": "Em reais: o valor de todas as unidades juntas."}
_QTD = {"type": "string", "description": "Ex.: 1, 2 ou 3 pares. Padrão: 1."}
_ZONA = {"type": "string", "description": "Parte do cômodo, como Estante ou Rack da TV (só com as zonas ligadas)."}
_DETALHES = {"type": "string", "description": "Marca, modelo, cor, tamanho e estado."}
_OBS = {"type": "string", "description": "Algo para lembrar sobre o item (até 200 caracteres)."}

FERRAMENTAS = [
    {"nome": "resumo", "titulo": "Resumo do inventário", "grava": False,
     "descricao": "Visão geral: o total, os cômodos (id, código, quantos itens e quanto valem; com as zonas ligadas, as zonas), "
                  "os bens (casa, terreno, carro), as categorias (id e nome), os itens mais valiosos e os últimos cadastrados. "
                  "Comece por aqui: os ids servem nas outras ferramentas.",
     "entrada": _obj({})},
    {"nome": "buscar_itens", "titulo": "Buscar itens", "grava": False,
     "descricao": "Busca itens por texto (todas as palavras, sem ligar para acentos, no nome, nos detalhes, na observação, no "
                  "código, no cômodo, na categoria e na zona), cômodo, zona, categoria e faixa de valor. Devolve quantos achou, a soma dos valores e os itens (id, código, nome, cômodo, "
                  "zona, categoria, quantidade, valor). Sem filtros, todos.",
     "entrada": _obj({"texto": {"type": "string", "description": "Palavras ou o código (ex.: SAL-003)."},
                      "comodo": _COMODO, "zona": {"type": "string"}, "categoria": {"type": "string", "description": "O id ou o nome da categoria."},
                      "valor_min": {"type": "number", "minimum": 0}, "valor_max": {"type": "number", "minimum": 0},
                      "ordem": {"type": "string", "enum": ["codigo", "valor", "nome", "recentes"],
                                "description": "codigo: na ordem dos cômodos (padrão); valor: do maior para o menor; recentes: os últimos cadastrados primeiro."},
                      "limite": {"type": "integer", "minimum": 1, "maximum": MAX_LISTA, "description": f"Padrão: {PADRAO_LISTA}."}})},
    {"nome": "ver_item", "titulo": "Ver item", "grava": False,
     "descricao": "Tudo de um item: nome, código, cômodo, zona, categoria, quantidade, valor (e o de cada unidade), detalhes, "
                  "observação, quantas fotos tem, de onde veio, quando e por quem foi cadastrado e alterado, e desde quando vale "
                  "o valor.",
     "entrada": _obj({"id": _ID}, ["id"])},
    {"nome": "cadastrar_itens", "titulo": "Cadastrar itens", "grava": True,
     "descricao": "Cadastra um ou mais itens num cômodo (ou em Bens: casa, terreno, carro). Cada item ganha o próximo código "
                  "do cômodo (ex.: SAL-013). Valor: o de todas as unidades juntas; sem valor, fica 0. As fotos se põem pela tela "
                  "do app.",
     "entrada": _obj({"comodo": _COMODO,
                      "zona": {"type": "string", "description": "A zona de todos (só com as zonas ligadas; cada item pode ter a sua)."},
                      "itens": {"type": "array", "minItems": 1, "maxItems": MAX_LOTE,
                                "items": _obj({"nome": {"type": "string", "description": "Curto, como a pessoa diria."},
                                               "valor": _VALOR, "quantidade": _QTD, "categoria": _CATEGORIA,
                                               "detalhes": _DETALHES, "observacao": _OBS, "zona": _ZONA}, ["nome"])}},
                     ["comodo", "itens"])},
    {"nome": "editar_item", "titulo": "Editar item", "grava": True,
     "descricao": "Muda um item (só o que vier): nome, valor, quantidade, categoria, zona, detalhes ou observação. Texto vazio "
                  "apaga a zona, os detalhes ou a observação. Para levar a outro cômodo, use inventario_mover_itens.",
     "entrada": _obj({"id": _ID, "nome": {"type": "string"}, "valor": _VALOR, "quantidade": _QTD, "categoria": _CATEGORIA,
                      "zona": _ZONA, "detalhes": _DETALHES, "observacao": _OBS}, ["id"])},
    {"nome": "mover_itens", "titulo": "Mover itens", "grava": True,
     "descricao": "Leva um ou mais itens para outro cômodo (ou para Bens), ou muda a zona deles. Num cômodo novo, o item ganha "
                  "um código novo (o id continua o mesmo) e fica sem zona, se ela não vier.",
     "entrada": _obj({"ids": {"type": "array", "minItems": 1, "maxItems": MAX_MOVER, "items": _ID}, "comodo": _COMODO, "zona": _ZONA},
                     ["ids", "comodo"])},
    {"nome": "apagar_item", "titulo": "Apagar item", "grava": True, "apaga": True,
     "descricao": "Tira um item do inventário. Devolve os dados dele, para cadastrar de novo se foi engano (as fotos não voltam).",
     "entrada": _obj({"id": _ID}, ["id"])},
    {"nome": "novo_comodo", "titulo": "Novo cômodo", "grava": True,
     "descricao": "Cria um cômodo, no fim da lista. codigo: de 1 a 4 letras ou números, o começo do código dos itens (ex.: GAR, "
                  "para GAR-001); sem ele, as 3 primeiras letras do nome.",
     "entrada": _obj({"nome": {"type": "string"}, "codigo": {"type": "string"}}, ["nome"])},
]
POR_NOME = {f["nome"]: f for f in FERRAMENTAS}


def lista():
    return [dict(f, apaga=bool(f.get("apaga"))) for f in FERRAMENTAS]


def instrucoes(srv) -> str:
    """Para a IA: o que é o app e por onde começar (com o que está ligado nesta casa)."""
    extras = [x for x, on in (("zonas (partes de um cômodo)", srv.zones_enabled()), ("os bens (casa, terreno, carro)", srv.bens_enabled())) if on]
    return ("InventarIA: o inventário da casa: cômodos, itens com valor, quantidade e categoria"
            + (", " + " e ".join(extras) if extras else "") + ". Valores em reais, como número; o valor de um item é o de todas "
            "as unidades juntas. Comece por inventario_resumo: os ids dos cômodos e das categorias servem nas outras ferramentas; "
            "um item se acha com inventario_buscar_itens, pelo id (sal-003) ou pelo código (SAL-003). Antes de gravar, diga à "
            "pessoa o que vai ser feito, e não mude um valor que ela não pediu.")


# ---------------------------------------------------------------- ajudantes

def _json(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _num(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _texto(srv, v, limite, campo, obrig=False, linhas=False) -> str:
    """Um texto pelas regras da tela (srv.text: obrigatório e tamanho); só os detalhes guardam as quebras de linha."""
    if isinstance(v, bool) or (v is not None and not isinstance(v, (str, int, float))):
        raise ErroFerramenta(f"{campo.capitalize()} precisa ser um texto.")
    t = srv.text(v, limite, campo, required=obrig)
    return t if linhas else " ".join(t.split())


def _valor(srv, v):
    if isinstance(v, bool):
        raise ErroFerramenta("Valor inválido: use um número, como 1200 ou 1200.50.")
    return srv.parse_value(v)


def _qtd(srv, v) -> str:
    if isinstance(v, bool):
        raise ErroFerramenta("Quantidade inválida: use um número ou um texto curto, como 2 ou 3 pares.")
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return _texto(srv, v, 30, "quantidade") or "1"


def _nomes_comodos(srv, rooms) -> str:
    nomes = [f"{r.get('name') or r['id']} ({r.get('code') or r['id']})" for r in sorted(rooms, key=lambda r: r.get("order", 0))]
    if srv.bens_enabled() and not any(r.get("kind") == "bens" for r in rooms):
        nomes.append("Bens (casa, terreno, carro)")
    return ", ".join(nomes) or "nenhum (crie um com inventario_novo_comodo)"


def _achar_comodo(srv, v, criar_bens=False):
    """Pelo id, pelo código ou pelo nome (inteiro ou só um pedaço, se for um só). "Bens" é a área do que fica fora de casa:
    com criar_bens, é criada como na tela (o primeiro bem cria a área)."""
    rooms, _ = srv.visible_data()
    s = str(v if v is not None and not isinstance(v, (dict, list)) else "").strip()
    if not s:
        raise ErroFerramenta(f"Falta o cômodo. Os cômodos: {_nomes_comodos(srv, rooms)}.")
    f = srv.fold(s)
    r = (next((r for r in rooms if r["id"] == s), None) or next((r for r in rooms if srv.fold(r.get("code") or "") == f), None)
         or next((r for r in rooms if srv.fold(r.get("name") or "") == f), None))
    if not r:
        parte = [r for r in rooms if f and f in srv.fold(r.get("name") or "")]
        r = parte[0] if len(parte) == 1 else None
    if not r and f in ("bens", "bem", "fora de casa"):
        if not srv.bens_enabled():
            raise ErroFerramenta("Os bens estão desligados no InventarIA (Mais › Configurações › Opções › Usar bens).")
        r = srv.STORE.bens_room()
        if not r and criar_bens:
            return "@bens"  # quem grava cria a área depois de conferir o resto
    if not r:
        raise ErroFerramenta(f"Cômodo não encontrado: {s}. Os cômodos: {_nomes_comodos(srv, rooms)}.")
    return r


def _achar_categoria(srv, v) -> str:
    cats = srv.STORE.cats()
    s = str(v if v is not None and not isinstance(v, (dict, list, bool)) else "").strip()
    if not s:
        return "outros"
    f = srv.fold(s)
    c = next((c for c in cats if c["id"] == s), None) or next((c for c in cats if srv.fold(c["name"]) == f), None)
    if not c:
        parte = [c for c in cats if f and (f in srv.fold(c["name"]) or f in c["id"])]
        c = parte[0] if len(parte) == 1 else None
    if not c:
        todas = ", ".join(f"{c['name']} ({c['id']})" for c in cats)
        raise ErroFerramenta(f"Categoria não encontrada: {s}. As categorias: {todas}.")
    return c["id"]


def _achar_item(srv, v):
    s = str(v if v is not None and not isinstance(v, (dict, list, bool)) else "").strip()
    if not s:
        raise ErroFerramenta("Falta o id do item.")
    _, items = srv.visible_data()
    low = s.lower()
    it = (next((i for i in items if i.get("id") == s), None) or next((i for i in items if str(i.get("id") or "").lower() == low), None)
          or next((i for i in items if srv.STORE.tag(i).lower() == low), None))
    if not it:
        raise ErroFerramenta(f"Item não encontrado: {s}. Busque o id com inventario_buscar_itens.")
    return it


def _nome_comodo(srv, rid) -> str:
    return (srv.STORE.room(rid) or {}).get("name") or rid or ""


def _zona_ok(srv, room, zona_dada: bool):
    if not zona_dada:
        return
    if not srv.zones_enabled():
        raise ErroFerramenta("As zonas estão desligadas no InventarIA (Mais › Configurações › Opções › Usar zonas). Mande sem a zona.")
    if room == "@bens" or (isinstance(room, dict) and room.get("kind") == "bens"):
        raise ErroFerramenta("Um bem não tem zona. Mande sem a zona.")


def _linha(srv, it, cats=None) -> dict:
    """Um item numa lista: o que a IA precisa para falar dele e achá-lo de novo."""
    cats = cats if cats is not None else srv.STORE.cat_map()
    out = {"id": it["id"], "codigo": srv.STORE.tag(it), "nome": it.get("name") or "", "comodo": _nome_comodo(srv, it.get("room"))}
    if srv.zones_enabled() and it.get("zone"):
        out["zona"] = it["zone"]
    out["categoria"] = cats.get(it.get("cat"), cats.get("outros", "Outros"))
    if str(it.get("qty") or "1") != "1":
        out["quantidade"] = it.get("qty")
    out["valor"] = _num(it.get("value"))
    return out


def _frase(srv, it) -> str:
    """Uma linha para a resposta de uma gravação: Abajur (SAL-013, Sala de estar, R$ 120, id sal-013)."""
    bits = [srv.STORE.tag(it), _nome_comodo(srv, it.get("room"))]
    if srv.zones_enabled() and it.get("zone"):
        bits.append(f"zona {it['zone']}")
    if str(it.get("qty") or "1") != "1":
        bits.append(f"quantidade {it['qty']}")
    bits += [srv._money(it.get("value")), f"id {it['id']}"]
    return f"{it.get('name') or ''} ({', '.join(bits)})"


def _quem(pessoa, cliente) -> str | None:
    """Quem fez, como a tela guarda (Cadastrado por, Alterado por): a pessoa que conectou o Claude, ou o cliente."""
    nome = pessoa.get("nome") if isinstance(pessoa, dict) else None
    nome = " ".join(str(nome or "").split()) or " ".join(str(cliente or "").split())
    return nome[:60] or None


# ---------------------------------------------------------------- leitura

def _resumo(srv) -> str:
    rooms, items = srv.visible_data()
    cats = srv.STORE.cat_map()
    zonas = srv.zones_enabled()
    por_comodo = {}
    for it in items:
        por_comodo.setdefault(it.get("room"), []).append(it)
    comodos, bens = [], None
    for r in sorted(rooms, key=lambda r: r.get("order", 0)):
        its = por_comodo.get(r["id"], [])
        c = {"id": r["id"], "codigo": r.get("code") or "", "nome": r.get("name") or r["id"], "itens": len(its),
             "valor": round(sum(_num(i.get("value")) for i in its), 2)}
        if r.get("kind") == "bens":
            grupos = {}
            for i in its:
                g = cats.get(i.get("cat")) if i.get("cat") in ("imoveis", "veiculos") else "Outros"
                grupos[g] = round(grupos.get(g, 0) + _num(i.get("value")), 2)
            bens = dict(c, por_tipo=grupos)
            continue
        if zonas:
            zs = []
            for i in sorted(its, key=lambda i: i.get("seq") or 0):
                z = " ".join(str(i.get("zone") or "").split())
                if z and z not in zs:
                    zs.append(z)
            c["zonas"] = zs
        comodos.append(c)
    total = round(sum(_num(i.get("value")) for i in items), 2)
    out = {"total": total, "itens": len(items)}
    if bens is not None:
        out["dentro_de_casa"] = round(total - bens["valor"], 2)
    out["comodos"] = comodos
    if srv.bens_enabled():
        out["bens"] = bens or {"itens": 0, "valor": 0, "obs": "Ainda sem bens: o primeiro cadastrado com comodo Bens cria a área."}
    conta = {}
    for i in items:
        k = i.get("cat") if i.get("cat") in cats else "outros"
        n, v = conta.get(k, (0, 0.0))
        conta[k] = (n + 1, v + _num(i.get("value")))
    out["categorias"] = [{"id": k, "nome": v, "itens": conta.get(k, (0, 0))[0], "valor": round(conta.get(k, (0, 0.0))[1], 2)} for k, v in cats.items()]
    out["mais_valiosos"] = [_linha(srv, i, cats) for i in sorted(items, key=lambda i: -_num(i.get("value")))[:MAX_RESUMO]]
    out["ultimos_cadastrados"] = [dict(_linha(srv, i, cats), cadastrado_em=str(i.get("createdAt") or "")[:10])
                                  for i in sorted(items, key=lambda i: str(i.get("createdAt") or ""), reverse=True)[:MAX_RESUMO]]
    out["opcoes"] = {"zonas": zonas, "bens": srv.bens_enabled()}
    return _json(out)


def _buscar(srv, a) -> str:
    rooms, items = srv.visible_data()
    cats = srv.STORE.cat_map()
    room = _achar_comodo(srv, a["comodo"], criar_bens=True) if a.get("comodo") not in (None, "") else None
    if room == "@bens":  # a área Bens ainda não existe: nenhum bem
        room = {"id": None}
    cat = _achar_categoria(srv, a["categoria"]) if a.get("categoria") not in (None, "") else None
    vmin = _valor(srv, a["valor_min"]) if a.get("valor_min") not in (None, "") else None
    vmax = _valor(srv, a["valor_max"]) if a.get("valor_max") not in (None, "") else None
    if vmin is not None and vmax is not None and vmax < vmin:
        raise ErroFerramenta("valor_max é menor que valor_min.")
    zonas = srv.zones_enabled()
    zona = srv.fold(" ".join(str(a.get("zona") or "").split())) if a.get("zona") not in (None, "") else None
    if zona is not None and not zonas:
        raise ErroFerramenta("As zonas estão desligadas no InventarIA. Busque sem a zona.")
    palavras = [srv.fold(w) for w in str(a.get("texto") or "").split()][:12]
    ordem = a.get("ordem") or "codigo"
    if ordem not in ("codigo", "valor", "nome", "recentes"):
        raise ErroFerramenta("ordem: codigo, valor, nome ou recentes.")
    lim = a.get("limite", PADRAO_LISTA)
    if isinstance(lim, bool) or not isinstance(lim, (int, float)) or not 1 <= int(lim) <= MAX_LISTA:
        raise ErroFerramenta(f"limite: de 1 a {MAX_LISTA}.")
    achados = []
    for it in items:
        if room and it.get("room") != room["id"]:
            continue
        if cat and (it.get("cat") if it.get("cat") in cats else "outros") != cat:
            continue
        v = _num(it.get("value"))
        if (vmin is not None and v < vmin) or (vmax is not None and v > vmax):
            continue
        if zona is not None and zona not in srv.fold(it.get("zone") or ""):
            continue
        if palavras:  # como a busca da tela (matches no app.js), mais a observação
            onde = srv.fold(" ".join(str(x or "") for x in (it.get("name"), it.get("details"), it.get("zone") if zonas else "", it.get("flag"),
                                                            _nome_comodo(srv, it.get("room")), srv.STORE.tag(it), cats.get(it.get("cat"), ""))))
            if not all(w in onde for w in palavras):
                continue
        achados.append(it)
    order = {r["id"]: r.get("order", 0) for r in rooms}
    if ordem == "valor":
        achados.sort(key=lambda i: -_num(i.get("value")))
    elif ordem == "nome":
        achados.sort(key=lambda i: srv.fold(i.get("name") or ""))
    elif ordem == "recentes":
        achados.sort(key=lambda i: str(i.get("createdAt") or ""), reverse=True)
    else:
        achados.sort(key=lambda i: (order.get(i.get("room"), 999), i.get("seq") or 0))
    mostrar = achados[:int(lim)]
    return _json({"encontrados": len(achados), "mostrando": len(mostrar), "valor_total": round(sum(_num(i.get("value")) for i in achados), 2),
                  "itens": [_linha(srv, i, cats) for i in mostrar]})


ORIGENS = {"foto": "catalogado por foto", "informado": "valor informado", "ia": "leitura por IA", "voz": "cadastro por voz",
           "manual": "cadastro manual", "correria": "pelo CorrerIA"}


def _ver(srv, a) -> str:
    it = _achar_item(srv, a.get("id"))
    cats = srv.STORE.cat_map()
    room = srv.STORE.room(it.get("room")) or {}
    out = {"id": it["id"], "codigo": srv.STORE.tag(it), "nome": it.get("name") or "",
           "comodo": {"id": room.get("id") or it.get("room"), "codigo": room.get("code") or "", "nome": room.get("name") or it.get("room")}}
    if room.get("kind") == "bens":
        out["comodo"]["obs"] = "Bens: o que fica fora de casa"
    if srv.zones_enabled():
        out["zona"] = it.get("zone") or ""
    cid = it.get("cat") if it.get("cat") in cats else "outros"
    out["categoria"] = {"id": cid, "nome": cats.get(cid, "Outros")}
    out["quantidade"] = str(it.get("qty") or "1")
    out["valor"] = _num(it.get("value"))
    m = re.match(r"\s*(\d+)", out["quantidade"])
    n = int(m.group(1)) if m else 1
    if n > 1:
        out["valor_de_cada"] = round(out["valor"] / n, 2)
    out["valor_desde"] = str(it.get("valueAt") or it.get("createdAt") or "")[:10]
    out["detalhes"] = it.get("details") or ""
    out["observacao"] = it.get("flag") or ""
    out["fotos"] = len(it.get("photos") or [])
    out["origem"] = ORIGENS.get(it.get("source"), "cadastro manual")
    out["cadastrado"] = {"em": str(it.get("createdAt") or "")[:16].replace("T", " "), "por": it.get("createdBy") or ""}
    if it.get("updatedAt") and it.get("updatedAt") != it.get("createdAt"):
        out["alterado"] = {"em": str(it["updatedAt"])[:16].replace("T", " "), "por": it.get("updatedBy") or ""}
    return _json(out)


# ---------------------------------------------------------------- gravação

def _cadastrar(srv, a, quem) -> str:
    lote = a.get("itens")
    if not isinstance(lote, list) or not lote:
        raise ErroFerramenta("Mande os itens numa lista: itens: [{nome, valor, quantidade, categoria}].")
    if len(lote) > MAX_LOTE:
        raise ErroFerramenta(f"No máximo {MAX_LOTE} itens de cada vez.")
    room = _achar_comodo(srv, a.get("comodo"), criar_bens=True)
    bem = room == "@bens" or room.get("kind") == "bens"
    zona_geral = _texto(srv, a.get("zona"), 120, "zona") if a.get("zona") not in (None, "") else ""
    _zona_ok(srv, room, bool(zona_geral))
    corpos = []
    for n, x in enumerate(lote, 1):
        if not isinstance(x, dict):
            raise ErroFerramenta(f"Item {n}: mande um objeto, como {{\"nome\": \"Abajur\", \"valor\": 120}}.")
        sobra = sorted(set(x) - set(POR_NOME["cadastrar_itens"]["entrada"]["properties"]["itens"]["items"]["properties"]))
        if sobra:
            raise ErroFerramenta(f"Item {n}: campo desconhecido: {', '.join(sobra)}. Valem: nome, valor, quantidade, categoria, detalhes, observacao, zona.")
        try:
            zona = _texto(srv, x.get("zona"), 120, "zona") if x.get("zona") not in (None, "") else zona_geral
            _zona_ok(srv, room, x.get("zona") not in (None, ""))
            corpos.append({"name": _texto(srv, x.get("nome"), 200, "nome", obrig=True), "value": _valor(srv, x.get("valor")),
                           "qty": _qtd(srv, x.get("quantidade")), "cat": _achar_categoria(srv, x.get("categoria")),
                           "details": _texto(srv, x.get("detalhes"), 4000, "detalhes", linhas=True), "flag": _texto(srv, x.get("observacao"), 200, "observação"),
                           "zone": "" if bem else zona, "source": "correria"})
        except (ErroFerramenta, srv.ApiError) as e:
            raise ErroFerramenta(f"Item {n}: {getattr(e, 'msg', None) or e}") from None
    if room == "@bens":  # o primeiro bem cria a área Bens, como na tela
        room = srv.STORE.create_room({"kind": "bens"})
    for c in corpos:
        c["room"] = room["id"]
    _, items = srv.visible_data()
    iguais = {srv.fold(i.get("name") or ""): i for i in items if i.get("room") == room["id"]}
    novos = srv.STORE.create_items(corpos, quem)
    txt = (f"Cadastrado em {room.get('name')}: " if len(novos) == 1 else f"Cadastrados {len(novos)} itens em {room.get('name')}: ")
    txt += "; ".join(_frase(srv, it) for it in novos) + "."
    if len(novos) > 1:
        txt += f" Total: {srv._money(sum(_num(i.get('value')) for i in novos))}."
    repetidos = [(it, iguais[srv.fold(it['name'])]) for it in novos if srv.fold(it["name"]) in iguais]
    if repetidos:
        txt += "\nAtenção: já havia " + "; ".join(f"{velho.get('name')} ({srv.STORE.tag(velho)}, id {velho['id']})" for _, velho in repetidos) \
               + f" em {room.get('name')}. Se foi engano, apague um deles."
    return txt


def _editar(srv, a, quem) -> str:
    it = _achar_item(srv, a.get("id"))
    room = srv.STORE.room(it.get("room")) or {}
    novo = {}
    if "nome" in a:
        novo["name"] = _texto(srv, a["nome"], 200, "nome", obrig=True)
    if "valor" in a:
        if a["valor"] is None or a["valor"] == "":
            raise ErroFerramenta("Valor vazio: mande 0 para tirar o valor.")
        novo["value"] = _valor(srv, a["valor"])
    if "quantidade" in a:
        novo["qty"] = _qtd(srv, a["quantidade"])
    if "categoria" in a:
        if a["categoria"] in (None, ""):
            raise ErroFerramenta("Categoria vazia: mande Outros para tirar a categoria.")
        novo["cat"] = _achar_categoria(srv, a["categoria"])
    if "zona" in a:
        z = _texto(srv, a["zona"], 120, "zona")
        _zona_ok(srv, room, True)
        novo["zone"] = z
    if "detalhes" in a:
        novo["details"] = _texto(srv, a["detalhes"], 4000, "detalhes", linhas=True)
    if "observacao" in a:
        novo["flag"] = _texto(srv, a["observacao"], 200, "observação") or None
    if not novo:
        raise ErroFerramenta("Diga o que muda: nome, valor, quantidade, categoria, zona, detalhes ou observacao.")
    rotulo = {"name": "nome", "value": "valor", "qty": "quantidade", "cat": "categoria", "zone": "zona", "details": "detalhes", "flag": "observação"}
    cats = srv.STORE.cat_map()

    def mostra(k, v):
        if k == "value":
            return srv._money(v)
        if k == "cat":
            return cats.get(v, "Outros")
        if k == "details":
            v = " ".join(str(v or "").split())
            return f"\"{v[:80]}{'…' if len(v) > 80 else ''}\"" if v else "(vazio)"
        return f"\"{v}\"" if v not in (None, "") else "(vazio)"

    antes = {k: (it.get(k) if k != "cat" else (it.get("cat") if it.get("cat") in cats else "outros")) for k in novo}
    mudou = [k for k in novo if (antes[k] or None) != (novo[k] or None) and not (k == "value" and _num(antes[k]) == _num(novo[k]))]
    if not mudou:
        return f"Nada mudou: {_frase(srv, it)} já estava assim."
    feito = srv.STORE.update_item(it["id"], {k: novo[k] for k in mudou}, quem)
    partes = [f"{rotulo[k]}: {mostra(k, antes[k])} → {mostra(k, feito.get(k))}" for k in mudou]
    return f"Alterado: {_frase(srv, feito)}. " + "; ".join(partes) + "."


def _mover(srv, a, quem) -> str:
    ids = a.get("ids")
    if isinstance(ids, str):
        ids = [ids]
    if not isinstance(ids, list) or not ids:
        raise ErroFerramenta("Mande os ids numa lista: ids: [\"sal-003\"].")
    if len(ids) > MAX_MOVER:
        raise ErroFerramenta(f"No máximo {MAX_MOVER} itens de cada vez.")
    itens, vistos = [], set()
    for v in ids:
        it = _achar_item(srv, v)
        if it["id"] not in vistos:
            vistos.add(it["id"])
            itens.append(it)
    room = _achar_comodo(srv, a.get("comodo"), criar_bens=True)
    zona_dada = a.get("zona") not in (None, "")
    zona = _texto(srv, a.get("zona"), 120, "zona") if zona_dada else ""
    _zona_ok(srv, room, zona_dada)
    if room == "@bens":
        room = srv.STORE.create_room({"kind": "bens"})
    feitos, ficaram = [], []
    for it in itens:
        if it["room"] == room["id"] and (not zona_dada or (it.get("zone") or "") == zona):
            ficaram.append(it)
            continue
        de = srv.STORE.tag(it)
        # como o Mover da tela: num cômodo novo a zona antiga não vai junto (sem zonas, ou sem dizer a zona)
        corpo = {"room": room["id"], "zone": zona} if it["room"] != room["id"] else {"zone": zona}
        feito = srv.STORE.update_item(it["id"], corpo, quem)
        feitos.append((de, feito))
    partes = []
    if feitos:
        partes.append((f"Movido para {room.get('name')}: " if len(feitos) == 1 else f"Movidos {len(feitos)} itens para {room.get('name')}: ")
                      + "; ".join(f"{f.get('name')} ({de} → {srv.STORE.tag(f)}{', zona ' + f['zone'] if srv.zones_enabled() and f.get('zone') else ''}, id {f['id']})"
                                  for de, f in feitos) + ".")
    if ficaram:
        partes.append(f"Já estava{'m' if len(ficaram) > 1 else ''} lá: " + "; ".join(_frase(srv, it) for it in ficaram) + ".")
    return " ".join(partes)


def _apagar(srv, a, quem) -> str:
    it = _achar_item(srv, a.get("id"))
    frase = _frase(srv, it)
    dados = {"nome": it.get("name") or "", "comodo": _nome_comodo(srv, it.get("room")), "valor": _num(it.get("value")),
             "quantidade": str(it.get("qty") or "1"), "categoria": srv.STORE.cat_map().get(it.get("cat"), "Outros")}
    if srv.zones_enabled() and it.get("zone"):
        dados["zona"] = it["zone"]
    for k, campo in (("details", "detalhes"), ("flag", "observacao")):
        if it.get(k):
            dados[campo] = it[k]
    srv.STORE.delete_item(it["id"])
    return f"Apagado: {frase}. Para cadastrar de novo: {_json(dados)}"


def _novo_comodo(srv, a, quem) -> str:
    nome = _texto(srv, a.get("nome"), 60, "nome do cômodo", obrig=True)
    if srv.fold(nome) == "bens":
        raise ErroFerramenta("Bens é a área do que fica fora de casa: cadastre o bem com inventario_cadastrar_itens e comodo Bens.")
    rooms, _ = srv.visible_data()
    igual = next((r for r in rooms if srv.fold(r.get("name") or "") == srv.fold(nome)), None)
    if igual:
        raise ErroFerramenta(f"Já existe o cômodo {igual.get('name')} ({igual.get('code')}, id {igual['id']}).")
    codigo = a.get("codigo")
    if codigo not in (None, ""):
        codigo = _texto(srv, codigo, 4, "código")
        if not srv.room_code(codigo):
            raise ErroFerramenta("O código precisa ter de 1 a 4 letras ou números.")
    else:  # como a tela sugere (suggestCode no app.js): as 3 primeiras letras do nome
        codigo = re.sub(r"[^a-z0-9]", "", srv.fold(nome))[:3].upper()
    r = srv.STORE.create_room({"name": nome, "code": codigo})
    pedido = srv.room_code(codigo)
    aviso = f" ({pedido} já era de outro cômodo)" if pedido and r["code"] != pedido else ""
    return f"Cômodo criado: {r['name']}, código {r['code']}{aviso}. Os itens vão ser {r['code']}-001, {r['code']}-002… id {r['id']}"


# ---------------------------------------------------------------- chamar

def conferir_argumentos(nome, argumentos) -> dict:
    """Os argumentos de uma ferramenta: um objeto só com os campos dela (a IA lê o erro e tenta de novo)."""
    f = POR_NOME.get(str(nome or ""))
    if not f:
        raise LookupError(f"Ferramenta desconhecida: {nome}.")
    if argumentos is None:
        argumentos = {}
    if not isinstance(argumentos, dict):
        raise ErroFerramenta("argumentos precisa ser um objeto, como {\"id\": \"sal-003\"}.")
    campos = f["entrada"]["properties"]
    sobra = sorted(set(argumentos) - set(campos))
    if sobra:
        raise ErroFerramenta(f"Argumento desconhecido: {', '.join(sobra)}. Valem: {', '.join(campos) or 'nenhum'}.")
    falta = [k for k in f["entrada"]["required"] if argumentos.get(k) in (None, "", [])]
    if falta:
        raise ErroFerramenta(f"Falta: {', '.join(falta)}.")
    return argumentos


def chamar(srv, nome, argumentos, pessoa=None, cliente=None) -> str:
    """Roda a ferramenta (as de gravar mudam o inventário pelo Store, que grava, sobe a rev e faz a versão automática)."""
    a = conferir_argumentos(nome, argumentos)
    quem = _quem(pessoa, cliente)
    try:
        with srv.STORE.lock:
            if nome == "resumo":
                return _resumo(srv)
            if nome == "buscar_itens":
                return _buscar(srv, a)
            if nome == "ver_item":
                return _ver(srv, a)
            faz = {"cadastrar_itens": _cadastrar, "editar_item": _editar, "mover_itens": _mover, "apagar_item": _apagar,
                   "novo_comodo": _novo_comodo}[nome]
            return faz(srv, a, quem)
    except srv.ApiError as e:  # as regras do Store (nome obrigatório, valor, cômodo que não existe…) viram 400 para a IA
        raise ErroFerramenta(e.msg) from None
