"""Ferramentas do InventarIA para o CorrerIA (o WhatsApp e o servidor MCP do Claude e do Gemini): ler o inventário e gravar
(cadastrar, editar, mover e apagar itens; criar cômodo). O CorrerIA lista (GET /api/integracao/ferramentas) e chama uma
(POST {nome, argumentos, pessoa, cliente}); aqui ficam a lista e as regras, e as gravações passam pelas mesmas funções da
tela (o Store do server.py: o número do item no cômodo, a data do valor, as versões automáticas). A tela vê a mudança pelo
/api/rev, como quando outro aparelho muda algo. Nada de fotos, backups, configurações ou chaves. Só biblioteca padrão.

Cada ferramenta: {nome, titulo, descricao, entrada (JSON Schema), grava, apaga}. chamar() recebe o próprio server.py
(srv), para não importar o servidor daqui, e devolve o texto para a IA; um argumento ruim levanta ErroFerramenta (400)."""
from __future__ import annotations

import os
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
# 1.82.0: um consumível não tem quantidade nem valor: tem a duração estimada
_DURACAO = {"type": "integer", "minimum": 0, "maximum": 3650,
            "description": "Só num consumível: quantos dias uma embalagem costuma durar (os atalhos da tela: 7, 15, 30, 90, 180, 365). 0 tira."}
_ZONA = {"type": "string", "description": "Parte do cômodo, como Estante ou Rack da TV (só com as zonas ligadas)."}
_DETALHES = {"type": "string", "description": "Marca, modelo, cor, tamanho e estado."}
_OBS = {"type": "string", "description": "Algo para lembrar sobre o item (até 200 caracteres)."}
_USADO = {"type": "string", "description": "Só num consumível, com Consumíveis por cômodo ligado (opcoes.consumiveis_por_comodo no resumo): "
                                           "o id ou o nome do cômodo onde é usado; mais de um, separados por ponto e vírgula (Cozinha; Lavanderia). Vazio tira."}

FERRAMENTAS = [
    {"nome": "resumo", "titulo": "Resumo do inventário", "grava": False,
     "descricao": "Visão geral: o total, os cômodos (id, código, quantos itens e quanto valem; com as zonas ligadas, as zonas), "
                  "os bens (casa, terreno, carro), os consumíveis (o que se gasta: pasta térmica, creme de massagem; sem quantidade e sem valor, com a duração "
                  "estimada e as categorias deles, categorias_consumiveis), as categorias (id e "
                  "nome), os itens mais valiosos e os últimos cadastrados. "
                  "Comece por aqui: os ids servem nas outras ferramentas.",
     "entrada": _obj({})},
    {"nome": "buscar_itens", "titulo": "Buscar itens", "grava": False,
     "descricao": "Busca itens por texto (todas as palavras, sem ligar para acentos, no nome, nos detalhes, na observação, no "
                  "código, no cômodo, na categoria e na zona), cômodo, zona, categoria e faixa de valor. Devolve quantos achou, a soma dos valores e os itens (id, código, nome, cômodo, "
                  "zona, categoria, quantidade, valor; num consumível, no lugar da quantidade e do valor, quanto dura e para que serve). Sem filtros, todos. Para achar pelo uso "
                  "(o que temos para massagem?), busque só o começo da palavra do uso (massag acha massagem e massageador): ele vale no "
                  "nome e nos detalhes, onde fica o que é e para que serve.",
     "entrada": _obj({"texto": {"type": "string", "description": "Palavras ou o código (ex.: SAL-003)."},
                      "comodo": _COMODO, "zona": {"type": "string"}, "categoria": {"type": "string", "description": "O id ou o nome da categoria."},
                      "usado_em": {"type": "string", "description": "Só os consumíveis usados neste cômodo (o id ou o nome; com Consumíveis por cômodo ligado)."},
                      "valor_min": {"type": "number", "minimum": 0}, "valor_max": {"type": "number", "minimum": 0},
                      "sem_foto": {"type": "boolean", "description": "true: só os itens que ainda não têm foto (1.99.0)."},
                      "ordem": {"type": "string", "enum": ["codigo", "valor", "nome", "recentes"],
                                "description": "codigo: na ordem dos cômodos (padrão); valor: do maior para o menor; recentes: os últimos cadastrados primeiro."},
                      "limite": {"type": "integer", "minimum": 1, "maximum": MAX_LISTA, "description": f"Padrão: {PADRAO_LISTA}."}})},
    # 1.98.0 (o dono: "pode criar ferramenta… o que precisar para melhorarmos o processo"; a Ronda da casa do CorrerIA 1.33.0
    # pergunta pelas novidades): só lê o que o app já conferiu e guardou; não procura na internet nem chama a IA
    {"nome": "novidades", "titulo": "Novidades dos equipamentos", "grava": False,
     "descricao": "As novidades já conferidas dos equipamentos da casa (atualização, lançamento, modelo novo, recall, fim de suporte), "
                  "cada uma com o item, o cômodo, o título, o resumo, a data e a fonte. Só lê o que o app já conferiu e guardou: não "
                  "procura na internet. Filtros: comodo e so_novas (as que apareceram na última conferência). conferido_em diz de "
                  "quando são. Só com as Novidades ligadas (opcoes.novidades no resumo).",
     "entrada": _obj({"comodo": _COMODO,
                      "so_novas": {"type": "boolean", "description": "true: só as que apareceram na última conferência."},
                      "limite": {"type": "integer", "minimum": 1, "maximum": 30, "description": "Quantas no máximo (padrão 12)."}})},
    {"nome": "ver_item", "titulo": "Ver item", "grava": False,
     "descricao": "Tudo de um item: nome, código, cômodo, zona, categoria, quantidade, valor (e o de cada unidade), detalhes, "
                  "observação, quantas fotos tem, de onde veio, quando e por quem foi cadastrado e alterado, e desde quando vale "
                  "o valor.",
     "entrada": _obj({"id": _ID}, ["id"])},
    # 1.93.0: o Digitalizar com IA de várias coisas numa foto, pelo CorrerIA (leitura: fica com as outras leituras)
    {"nome": "ler_arquivo", "titulo": "Ler a foto", "grava": False, "anexo": ["image/jpeg"],
     "descricao": "Lê com a IA do InventarIA a foto que a pessoa acabou de mandar na conversa e devolve as coisas que há nela "
                  "(uma estante, uma bancada, um cômodo: o nome, a categoria e o que é cada uma). Não cadastra nada: depois, "
                  "cadastre com inventario_cadastrar_itens os que a pessoa quiser. Para cadastrar UMA coisa com a foto no item, "
                  "use inventario_cadastrar_por_foto.",
     "entrada": _obj({"comodo": {"type": "string", "description": "O cômodo da foto, se a pessoa disse (ajuda a IA)."},
                      "consumiveis": {"type": "boolean", "description": "true quando a foto é de consumíveis (cremes, produtos de limpeza, "
                                      "comida: o que se gasta e se compra de novo): a leitura traz só eles, com a duração estimada, e diz os que já estão cadastrados."},
                      "dica": {"type": "string", "description": "O que a pessoa disse sobre a foto, se disse."}})},
    # 1.103.0 (o dono: "botão para avaliar com a IA… um parecer do consumível, qualidade, etc."): o Avaliar com IA da ficha
    {"nome": "avaliar", "titulo": "Avaliar consumível com IA", "grava": False,
     "descricao": "O parecer da IA do InventarIA sobre um consumível, pelas avaliações na web: a nota de 1 a 5, se vale a pena, os "
                  "pontos fortes e fracos, dicas para render mais, outras opções e o preço de hoje. Devolve o parecer guardado; sem "
                  "ele (ou com nova), avalia agora (demora até um minuto).",
     "entrada": _obj({"id": _ID, "nova": {"type": "boolean", "description": "Avaliar de novo, mesmo com um parecer guardado."}}, ["id"])},
    {"nome": "pareceres", "titulo": "Pareceres dos consumíveis", "grava": False,
     "descricao": "Os consumíveis com o parecer guardado do Avaliar com IA (a nota de 1 a 5, o resumo e quando foi avaliado) e os que "
                  "ainda não têm, como a tela Pesquisas da IA › Pareceres. Só lê o que já foi avaliado: para avaliar um, use avaliar. "
                  "Filtro: so_sem (só os que não têm parecer).",
     "entrada": _obj({"so_sem": {"type": "boolean", "description": "true: só os consumíveis sem parecer."}})},
    {"nome": "cadastrar_itens", "titulo": "Cadastrar itens", "grava": True,
     "descricao": "Cadastra um ou mais itens num cômodo (ou em Bens: casa, terreno, carro; ou em Consumíveis: o que se gasta "
                  "e se compra de novo, como pasta térmica e creme de massagem). Cada item ganha o próximo código "
                  "do cômodo (ex.: SAL-013). Valor: o de todas as unidades juntas; sem valor, fica 0. Um consumível não tem valor nem "
                  "quantidade: mande duracao_dias (quanto costuma durar), a categoria dos consumíveis (categorias_consumiveis do "
                  "resumo) e, em detalhes, o que é e para que serve. Com uma foto que a pessoa mandou na conversa, use cadastrar_por_foto.",
     "entrada": _obj({"comodo": _COMODO,
                      "zona": {"type": "string", "description": "A zona de todos (só com as zonas ligadas; cada item pode ter a sua)."},
                      "itens": {"type": "array", "minItems": 1, "maxItems": MAX_LOTE,
                                "items": _obj({"nome": {"type": "string", "description": "Curto, como a pessoa diria."},
                                               "valor": _VALOR, "quantidade": _QTD, "categoria": _CATEGORIA, "duracao_dias": _DURACAO,
                                               "usado_em": _USADO, "detalhes": _DETALHES, "observacao": _OBS, "zona": _ZONA}, ["nome"])}},
                     ["comodo", "itens"])},
    {"nome": "editar_item", "titulo": "Editar item", "grava": True,
     "descricao": "Muda um item (só o que vier): nome, valor, quantidade, categoria, zona, detalhes ou observação; num consumível, "
                  "duracao_dias no lugar do valor e da quantidade. Texto vazio "
                  "apaga a zona, os detalhes ou a observação. Para levar a outro cômodo, use inventario_mover_itens.",
     "entrada": _obj({"id": _ID, "nome": {"type": "string"}, "valor": _VALOR, "quantidade": _QTD, "categoria": _CATEGORIA,
                      "duracao_dias": _DURACAO, "usado_em": _USADO, "zona": _ZONA, "detalhes": _DETALHES, "observacao": _OBS}, ["id"])},
    {"nome": "mover_itens", "titulo": "Mover itens", "grava": True,
     "descricao": "Leva um ou mais itens para outro cômodo (ou para Bens ou Consumíveis), ou muda a zona deles. Num cômodo novo, o item ganha "
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
    # 1.101.0 (o dono, à lista do que a IA não fazia: "todas")
    {"nome": "comprei", "titulo": "Comprei (consumível)", "grava": True,
     "descricao": "Anota que um consumível foi comprado de novo (ou reposto): o Dura até volta a contar de hoje. Com duracao_dias, "
                  "a duração estimada muda também.",
     "entrada": _obj({"id": _ID, "duracao_dias": _DURACAO}, ["id"])},
    {"nome": "editar_comodo", "titulo": "Renomear ou apagar cômodo", "grava": True, "apaga": True,
     "descricao": "Muda o nome ou o código de um cômodo (o código novo muda o código dos itens dele), ou apaga um cômodo vazio "
                  "(com itens, mova ou apague os itens antes). Bens e Consumíveis não mudam por aqui.",
     "entrada": _obj({"comodo": _COMODO, "nome": {"type": "string"}, "codigo": {"type": "string", "description": "De 1 a 4 letras ou números."},
                      "apagar": {"type": "boolean"}}, ["comodo"])},
    {"nome": "categoria", "titulo": "Criar, mudar ou apagar categoria", "grava": True, "apaga": True,
     "descricao": "As categorias da casa (ou, com consumiveis, as dos consumíveis), como em Mais › Categorias: nova (nome e, se "
                  "quiser, cor), mudar (o nome com novo_nome e/ou a cor) ou apagar (os itens dela vão para Outros). Eletrônicos, "
                  "Utilidades e Veículos mudam só a cor; Outros não se apaga.",
     "entrada": _obj({"acao": {"type": "string", "enum": ["nova", "mudar", "apagar"]}, "nome": {"type": "string", "description": "O nome (ou o id) da categoria."},
                      "novo_nome": {"type": "string"}, "cor": {"type": "string", "enum": ["vermelho", "coral", "laranja", "ouro", "verde", "menta", "turquesa", "azul", "indigo", "lilas", "rosa", "grafite"]},
                      "consumiveis": {"type": "boolean"}}, ["acao", "nome"])},
    # 1.92.0 (o dono, numa ronda: mandou a foto de um consumível com "coloca 6 meses" e a foto foi para o GerencIA): a foto que a
    # pessoa mandou na conversa vira um item. `anexo` diz ao CorrerIA que esta ferramenta recebe o arquivo (ele manda em
    # `anexo`, fora dos argumentos). Sem o nome, a IA daqui lê a foto, como o Digitalizar com IA da tela.
    {"nome": "cadastrar_por_foto", "titulo": "Cadastrar pela foto", "grava": True, "anexo": ["image/jpeg"],
     "descricao": "Cadastra UM item a partir da foto que a pessoa mandou na conversa: a foto fica no item e, se você não "
                  "souber o nome, não mande nome: a IA do InventarIA lê a foto (o nome, o que é, a categoria). Use sempre "
                  "que a pessoa manda uma foto e pede para cadastrar, adicionar ou pôr no inventário ou nos consumíveis. "
                  "Num consumível, comodo \"Consumíveis\" com duracao_dias (6 meses = 180) e, se for de um cômodo, usado_em.",
     "entrada": _obj({"comodo": _COMODO, "nome": {"type": "string", "description": "Só se a pessoa disse o nome; sem ele, a IA lê a foto."},
                      "valor": _VALOR, "categoria": _CATEGORIA, "duracao_dias": _DURACAO, "usado_em": _USADO, "detalhes": _DETALHES,
                      "zona": _ZONA}, ["comodo"])},
    # 1.93.0 (o dono: "todos os apps que tenham as funções de PDF ou imagem ou foto funcionem no correria/rondas"): as outras
    # duas funções de foto da tela: a foto num item que já existe e o Digitalizar com IA de várias coisas numa foto só
    {"nome": "anexar_foto", "titulo": "Pôr a foto no item", "grava": True, "anexo": ["image/jpeg"],
     "descricao": "Guarda num item que já existe a foto que a pessoa acabou de mandar na conversa (a nota, o estado, a "
                  "etiqueta). Ache o item antes, com inventario_buscar_itens. Só serve logo depois de a pessoa mandar a foto.",
     "entrada": _obj({"id": {"type": "string", "description": "O id ou o código do item (SAL-003)."}}, ["id"])},
    {"nome": "apagar_pesquisa", "titulo": "Apagar o que a IA buscou", "grava": True, "apaga": True,
     "descricao": "Apaga de um item o que a IA buscou na internet, como o Apagar da ficha: as novidades (não voltam nas próximas "
                  "conferências), os recursos (de um eletrônico; também nos outros cômodos com o mesmo equipamento) ou o parecer (de "
                  "um consumível). O item não muda, e dá para buscar de novo. Com todos: true (sem id), os recursos de todos os "
                  "eletrônicos ou os pareceres de todos os consumíveis, como o Limpar das Pesquisas da IA.",
     "entrada": _obj({"id": _ID, "o_que": {"type": "string", "enum": ["novidades", "recursos", "parecer"], "description": "O que apagar."},
                      "todos": {"type": "boolean", "description": "Os recursos ou os pareceres de todos (sem id). As novidades de todos se limpam na tela."}}, ["o_que"])},
]
POR_NOME = {f["nome"]: f for f in FERRAMENTAS}


def lista():
    return [dict(f, apaga=bool(f.get("apaga"))) for f in FERRAMENTAS]


def instrucoes(srv) -> str:
    """Para a IA: o que é o app e por onde começar (com o que está ligado nesta casa)."""
    extras = [x for x, on in (("zonas (partes de um cômodo)", srv.zones_enabled() and srv.itens_enabled()), ("os bens (casa, terreno, carro)", srv.bens_enabled()),
                              ("os consumíveis (o que se gasta e se compra de novo, fora do patrimônio; os detalhes dizem o que é e para que serve)", srv.consumiveis_enabled())) if on]
    return ("InventarIA: o inventário da casa: " + ("cômodos, itens com valor, quantidade e categoria" if srv.itens_enabled() else "sem os itens da casa (desligados)")
            + (", " + " e ".join(extras) if extras else "")
            + (". Um consumível não tem quantidade nem valor: tem a categoria dos consumíveis e a duração estimada (duracao_dias)" if srv.consumiveis_enabled() else "")
            + (" e, com Consumíveis por cômodo ligado, o cômodo onde é usado (usado_em)" if srv.cons_comodo_enabled() else "")
            + ". Valores em reais, como número; o valor de um item é o de todas "
            "as unidades juntas. Comece por inventario_resumo: os ids dos cômodos e das categorias servem nas outras ferramentas; "
            "um item se acha com inventario_buscar_itens, pelo id (sal-003) ou pelo código (SAL-003). Antes de gravar, diga à "
            "pessoa o que vai ser feito, e não mude um valor que ela não pediu."
            + (" Valor de hoje ligado: o valor de cada item, as somas e os filtros são os de hoje, como na tela (o valor "
               "gravado perde a depreciação do GerencIA desde valor_desde); valor_gravado é o que a pessoa informou, e é o "
               "que inventario_editar_item muda." if _taxas(srv) else ""))


def _taxas(srv):
    """1.75.0: com o Valor de hoje ligado (a depreciação do GerencIA), as taxas de cada categoria; senão, None."""
    return srv.gerencia_taxas() if srv.deprec_enabled() else None


def _v(srv, it, taxas) -> float:
    """O valor do item como a tela mostra: o de hoje, com o Valor de hoje ligado; senão, o gravado."""
    return round(_bruto(srv, it, taxas), 2)


def _bruto(srv, it, taxas) -> float:
    """O mesmo, sem arredondar: as somas (do cômodo, da categoria, da busca) somam assim, como a tela (que soma os valores
    e arredonda só o total; antes, somar os já arredondados dava alguns centavos de diferença)."""
    if taxas:
        return srv.item_hoje(it, taxas)
    try:
        return float(it.get("value") or 0)
    except (TypeError, ValueError):
        return 0.0


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
    if srv.consumiveis_enabled() and not any(r.get("kind") == "consumiveis" for r in rooms):
        nomes.append("Consumíveis (o que se gasta)")
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
    if not r and f in ("consumiveis", "consumivel", "consumo"):  # 1.78.0: a área do que se gasta
        if not srv.consumiveis_enabled():
            raise ErroFerramenta("Os consumíveis estão desligados no InventarIA (Mais › Configurações › Opções › Usar consumíveis).")
        r = srv.STORE.consumiveis_room()
        if not r and criar_bens:
            return "@consumiveis"
    if not r:
        raise ErroFerramenta(f"Cômodo não encontrado: {s}. Os cômodos: {_nomes_comodos(srv, rooms)}.")
    return r


def _eh_cons(srv, it) -> bool:
    return (srv.STORE.room(it.get("room")) or {}).get("kind") == "consumiveis"


def _duracao(srv, v) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or v > 3650 or int(v) != v:
        raise ErroFerramenta("duracao_dias: um número inteiro de dias, de 0 a 3650 (7, 15, 30, 90, 180 ou 365 são os atalhos da tela; qualquer outro número vale).")
    return int(v)


def _sem_valor(x, n=""):
    """1.82.0: um consumível não tem valor nem quantidade (a IA lê o porquê e manda de novo, com a duração)."""
    v, q = x.get("valor"), str(x.get("quantidade") or "").strip()
    if (isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0) or q not in ("", "1"):
        raise ErroFerramenta(f"{n}Um consumível não tem valor nem quantidade: mande duracao_dias (quanto costuma durar), sem valor e sem quantidade.")


def _achar_categoria(srv, v, cons: bool = False, solta: bool = False) -> str:
    cats = srv.STORE.cons_cats() if cons else srv.STORE.cats()
    s = str(v if v is not None and not isinstance(v, (dict, list, bool)) else "").strip()
    if not s:
        return srv.CONS_OUTROS if cons else "outros"
    f = srv.fold(s)
    c = next((c for c in cats if c["id"] == s), None) or next((c for c in cats if srv.fold(c["name"]) == f), None)
    if not c:
        parte = [c for c in cats if f and (f in srv.fold(c["name"]) or f in c["id"])]
        c = parte[0] if len(parte) == 1 else None
    if not c and solta:
        # 1.94.0 (o dono, depois do Sim: "Não deu: Categoria não encontrada: Consumíveis", "toda hora isso de não achar"): uma
        # categoria que não existe não trava o cadastro: o item fica em Outros, como na tela quando ninguém escolhe
        return srv.CONS_OUTROS if cons else "outros"
    if not c:
        todas = ", ".join(f"{c['name']} ({c['id']})" for c in cats)
        raise ErroFerramenta(f"Categoria não encontrada: {s}. As categorias{' dos consumíveis' if cons else ''}: {todas}.")
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


def _area(room) -> str:
    """"bens" ou "consumiveis" se o cômodo é uma área do sistema (ou o pedido de criar uma: "@bens"); senão ""."""
    if isinstance(room, str):
        return room[1:] if room.startswith("@") else ""
    return (room or {}).get("kind") or ""


def _criar_area(srv, room):
    return srv.STORE.create_room({"kind": room[1:]}) if isinstance(room, str) else room


def _zona_ok(srv, room, zona_dada: bool):
    if not zona_dada:
        return
    if not srv.zones_enabled():
        raise ErroFerramenta("As zonas estão desligadas no InventarIA (Mais › Configurações › Opções › Usar zonas). Mande sem a zona.")
    if _area(room):
        raise ErroFerramenta(("Um bem" if _area(room) == "bens" else "Um consumível") + " não tem zona. Mande sem a zona.")


def _linha(srv, it, cats=None, taxas=None) -> dict:
    """Um item numa lista: o que a IA precisa para falar dele e achá-lo de novo."""
    cats = cats if cats is not None else srv.STORE.cat_map()
    out = {"id": it["id"], "codigo": srv.STORE.tag(it), "nome": it.get("name") or "", "comodo": _nome_comodo(srv, it.get("room"))}
    if srv.zones_enabled() and it.get("zone"):
        out["zona"] = it["zone"]
    if _eh_cons(srv, it):  # 1.78.0: o que é e para que serve, para achar pelo uso; 1.82.0: a duração, sem quantidade e sem valor
        out["categoria"] = srv.STORE.cat_of(it)
        out["tipo"] = "consumível"
        if srv.used_in(it):  # 1.88.0: Consumíveis por cômodo
            out["usado_em"] = srv.used_in_text(it)
        if srv.clean_dur(it.get("dur")):
            out["duracao"], out["duracao_dias"] = srv.dur_text(it.get("dur")), srv.clean_dur(it.get("dur"))
            if srv.dur_until(it):  # 1.83.0: até quando dura
                out["dura_ate"] = srv.dur_until(it)
        d = " ".join(str(it.get("details") or "").split())
        if d:
            out["para_que_serve"] = d[:240]
        return out
    out["categoria"] = cats.get(it.get("cat"), cats.get("outros", "Outros"))
    if str(it.get("qty") or "1") != "1":
        out["quantidade"] = it.get("qty")
    out["valor"] = _v(srv, it, taxas)
    if taxas:
        out["valor_gravado"] = _num(it.get("value"))
    return out


def _frase(srv, it) -> str:
    """Uma linha para a resposta de uma gravação: Abajur (SAL-013, Sala de estar, R$ 120, id sal-013)."""
    bits = [srv.STORE.tag(it), _nome_comodo(srv, it.get("room"))]
    if srv.zones_enabled() and it.get("zone"):
        bits.append(f"zona {it['zone']}")
    if _eh_cons(srv, it):  # 1.82.0: a duração, sem quantidade e sem valor
        if srv.clean_dur(it.get("dur")):
            bits.append(f"dura {srv.dur_text(it.get('dur'))}" + (f", até {srv.dia_br(srv.dur_until(it))}" if srv.dur_until(it) else ""))
        bits.append(f"id {it['id']}")
        return f"{it.get('name') or ''} ({', '.join(bits)})"
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
    rooms, items = srv.visible_data(consumiveis=False)  # o patrimônio; os consumíveis vêm à parte, no fim
    consumiveis = [i for i in srv.visible_data()[1] if (srv.STORE.room(i.get("room")) or {}).get("kind") == "consumiveis"]
    cats = srv.STORE.cat_map()
    taxas = _taxas(srv)
    val = lambda i: _bruto(srv, i, taxas)  # noqa: E731
    zonas = srv.zones_enabled()
    por_comodo = {}
    for it in items:
        por_comodo.setdefault(it.get("room"), []).append(it)
    comodos, bens = [], None
    for r in sorted(rooms, key=lambda r: r.get("order", 0)):
        its = por_comodo.get(r["id"], [])
        c = {"id": r["id"], "codigo": r.get("code") or "", "nome": r.get("name") or r["id"], "itens": len(its),
             "valor": round(sum(val(i) for i in its), 2)}
        if r.get("kind") == "bens":
            grupos = {}
            for i in its:
                g = cats.get(i.get("cat")) if i.get("cat") in ("imoveis", "veiculos") else "Outros"
                grupos[g] = round(grupos.get(g, 0) + val(i), 2)
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
    total = round(sum(val(i) for i in items), 2)
    out = {"total": total, "itens": len(items)}
    if taxas:
        out["valores"] = "de hoje, como na tela (Valor de hoje ligado: a depreciação do GerencIA)"
    if bens is not None:
        out["dentro_de_casa"] = round(sum(val(i) for i in items if i.get("room") != bens["id"]), 2)
    out["comodos"] = comodos
    if srv.bens_enabled():
        out["bens"] = bens or {"itens": 0, "valor": 0, "obs": "Ainda sem bens: o primeiro cadastrado com comodo Bens cria a área."}
    conta = {}
    for i in items:
        k = i.get("cat") if i.get("cat") in cats else "outros"
        n, v = conta.get(k, (0, 0.0))
        conta[k] = (n + 1, v + val(i))
    out["categorias"] = [{"id": k, "nome": v, "itens": conta.get(k, (0, 0))[0], "valor": round(conta.get(k, (0, 0.0))[1], 2)} for k, v in cats.items()]
    out["mais_valiosos"] = [_linha(srv, i, cats, taxas) for i in sorted(items, key=lambda i: -val(i))[:MAX_RESUMO]]
    out["ultimos_cadastrados"] = [dict(_linha(srv, i, cats, taxas), cadastrado_em=str(i.get("createdAt") or "")[:10])
                                  for i in sorted(items, key=lambda i: str(i.get("createdAt") or ""), reverse=True)[:MAX_RESUMO]]
    if srv.consumiveis_enabled():
        out["categorias_consumiveis"] = [{"id": c["id"], "nome": c["name"]} for c in srv.STORE.cons_cats()]
        out["consumiveis"] = {"itens": len(consumiveis), "obs": "O que se gasta e se compra de novo; fora do total, sem quantidade e sem valor: "
                                                                 "com a duração estimada (duracao_dias). Cadastre com comodo Consumíveis.",
                              "lista": [_linha(srv, i, cats, taxas) for i in sorted(consumiveis, key=lambda i: i.get("seq") or 0)[:MAX_RESUMO * 3]]}
    out["opcoes"] = {"zonas": zonas, "itens_da_casa": srv.itens_enabled(), "bens": srv.bens_enabled(), "consumiveis": srv.consumiveis_enabled(),
                     "consumiveis_por_comodo": srv.cons_comodo_enabled(), "novidades": srv.news_enabled()}
    return _json(out)


def _usado_em(srv, v):
    """1.88.0: os ids dos cômodos onde o consumível é usado ([] tira). Só com Consumíveis por cômodo ligado.
    1.91.0: mais de um, separados por ponto e vírgula («Cozinha; Lavanderia») ou numa lista."""
    if not srv.cons_comodo_enabled():
        raise ErroFerramenta("usado_em: os Consumíveis por cômodo estão desligados no InventarIA (Mais › Configurações › Opções). Mande sem usado_em.")
    nomes = v if isinstance(v, list) else str(v or "").split(";")
    ids = []
    for nome in (str(x).strip() for x in nomes):
        if not nome:
            continue
        room = _achar_comodo(srv, nome)
        if isinstance(room, str) or _area(room):
            raise ErroFerramenta("usado_em: um cômodo da casa (não Bens nem Consumíveis).")
        if room["id"] not in ids:
            ids.append(room["id"])
    return ids


def _buscar(srv, a) -> str:
    rooms, items = srv.visible_data()
    cats = srv.STORE.cat_map()
    room = _achar_comodo(srv, a["comodo"], criar_bens=True) if a.get("comodo") not in (None, "") else None
    if isinstance(room, str):  # a área (Bens ou Consumíveis) ainda não existe: nenhum
        room = {"id": None}
    cat = None
    if a.get("categoria") not in (None, ""):
        try:
            cat = _achar_categoria(srv, a["categoria"])
        except ErroFerramenta:
            if not srv.consumiveis_enabled():
                raise
            cat = _achar_categoria(srv, a["categoria"], cons=True)  # 1.82.0: uma categoria dos consumíveis
    vmin = _valor(srv, a["valor_min"]) if a.get("valor_min") not in (None, "") else None
    vmax = _valor(srv, a["valor_max"]) if a.get("valor_max") not in (None, "") else None
    sem_foto = a.get("sem_foto")
    if sem_foto not in (None, "", True, False):
        raise ErroFerramenta("sem_foto é true ou false.")
    if vmin is not None and vmax is not None and vmax < vmin:
        raise ErroFerramenta("valor_max é menor que valor_min.")
    zonas = srv.zones_enabled()
    zona = srv.fold(" ".join(str(a.get("zona") or "").split())) if a.get("zona") not in (None, "") else None
    if zona is not None and not zonas:
        raise ErroFerramenta("As zonas estão desligadas no InventarIA. Busque sem a zona.")
    palavras = [srv.fold(w) for w in str(a.get("texto") or "").split()][:12]
    usado = (_usado_em(srv, a["usado_em"]) or None) if a.get("usado_em") not in (None, "") else None
    ordem = a.get("ordem") or "codigo"
    if ordem not in ("codigo", "valor", "nome", "recentes"):
        raise ErroFerramenta("ordem: codigo, valor, nome ou recentes.")
    lim = a.get("limite", PADRAO_LISTA)
    if isinstance(lim, bool) or not isinstance(lim, (int, float)) or not 1 <= int(lim) <= MAX_LISTA:
        raise ErroFerramenta(f"limite: de 1 a {MAX_LISTA}.")
    taxas = _taxas(srv)
    achados = []
    for it in items:
        if room and it.get("room") != room["id"]:
            continue
        if usado and not (_eh_cons(srv, it) and set(usado) & set(srv.STORE.home_rooms(it.get("usedIn")))):
            continue
        if cat and (cat.startswith("c-") != _eh_cons(srv, it) or
                    ((it.get("cat") if it.get("cat") in srv.STORE.cons_cat_map() else srv.CONS_OUTROS) if _eh_cons(srv, it)
                     else (it.get("cat") if it.get("cat") in cats else "outros")) != cat):
            continue
        v = _v(srv, it, taxas)
        if (vmin is not None and v < vmin) or (vmax is not None and v > vmax):
            continue
        if sem_foto and (it.get("photos") or []):
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
        achados.sort(key=lambda i: -_v(srv, i, taxas))
    elif ordem == "nome":
        achados.sort(key=lambda i: srv.fold(i.get("name") or ""))
    elif ordem == "recentes":
        achados.sort(key=lambda i: str(i.get("createdAt") or ""), reverse=True)
    else:
        achados.sort(key=lambda i: (order.get(i.get("room"), 999), i.get("seq") or 0))
    mostrar = achados[:int(lim)]
    fora = {r["id"] for r in rooms if r.get("kind") == "consumiveis"}  # os consumíveis não entram na soma (fora do patrimônio)
    return _json({"encontrados": len(achados), "mostrando": len(mostrar), "valor_total": round(sum(_bruto(srv, i, taxas) for i in achados if i.get("room") not in fora), 2),
                  "itens": [_linha(srv, i, cats, taxas) for i in mostrar]})


ORIGENS = {"foto": "catalogado por foto", "informado": "valor informado", "ia": "leitura por IA", "voz": "cadastro por voz",
           "manual": "cadastro manual", "correria": "pelo CorrerIA"}


NOVIDADE_TIPO = {"atualizacao": "atualização", "lancamento": "lançamento", "sucessor": "modelo novo", "recall": "recall",
                 "suporte": "fim de suporte", "outro": "outro"}


def _novidades(srv, a) -> str:
    """1.98.0: as novidades guardadas (o que a tela Novidades mostra), sem as que a pessoa apagou nem as de um item que não
    aparece (um tipo desligado). Não confere nada: lê o arquivo."""
    if not srv.news_enabled():
        raise ErroFerramenta("As Novidades estão desligadas no InventarIA (Mais › Configurações › Opções › Novidades).")
    rooms, items = srv.visible_data(consumiveis=False)
    room = _achar_comodo(srv, a["comodo"]) if a.get("comodo") not in (None, "") else None
    if isinstance(room, str):
        room = {"id": None}
    limite = a.get("limite")
    if limite in (None, ""):
        limite = 12
    if not isinstance(limite, int) or isinstance(limite, bool) or not 1 <= limite <= 30:
        raise ErroFerramenta("limite vai de 1 a 30.")
    so_novas = a.get("so_novas")
    if so_novas not in (None, "", True, False):
        raise ErroFerramenta("so_novas é true ou false.")
    d = srv.news_read()
    nomes = {r["id"]: r["name"] for r in rooms}
    saida, conferidos, quando = [], 0, ""
    for it in items:
        if room and it.get("room") != room["id"]:
            continue
        v = d["itens"].get(it["id"])
        news = v.get("news") if isinstance(v, dict) else None
        if not isinstance(news, dict):
            continue
        conferidos += 1
        quando = max(quando, str(v.get("at") or ""))
        fora = srv.news_fora(srv.news_group_ids(it["id"]))
        for n in news.get("novidades") or []:
            if not isinstance(n, dict) or fora.intersection(srv.news_keys(n)) or (so_novas and not n.get("nova")):
                continue
            saida.append({"item": it["name"], "id": it["id"], "comodo": nomes.get(it.get("room"), ""), "tipo": NOVIDADE_TIPO.get(n.get("tipo"), "outro"),
                          "titulo": n.get("titulo") or "", "resumo": n.get("resumo") or "", "data": n.get("data") or "", "fonte": n.get("fonte") or "",
                          **({"boato": True} if n.get("boato") else {}), **({"nova": True} if n.get("nova") else {})})
    saida.sort(key=lambda x: (not x.get("nova"), -int("".join(c for c in (x["data"] + "0000-00-00")[:10] if c.isdigit()) or 0), x["item"]))
    out = {"total": len(saida), "itens_conferidos": conferidos, "novidades": saida[:limite]}
    if quando:
        out["conferido_em"] = quando[:10]
    if not conferidos:
        out["aviso"] = "Nenhum equipamento teve as novidades conferidas ainda (na tela: Mais › Novidades › Conferir)."
    return _json(out)


def _ver(srv, a) -> str:
    it = _achar_item(srv, a.get("id"))
    cats = srv.STORE.cat_map()
    room = srv.STORE.room(it.get("room")) or {}
    out = {"id": it["id"], "codigo": srv.STORE.tag(it), "nome": it.get("name") or "",
           "comodo": {"id": room.get("id") or it.get("room"), "codigo": room.get("code") or "", "nome": room.get("name") or it.get("room")}}
    if room.get("kind") == "bens":
        out["comodo"]["obs"] = "Bens: o que fica fora de casa"
    if room.get("kind") == "consumiveis":
        out["comodo"]["obs"] = "Consumíveis: o que se gasta e se compra de novo; fora do patrimônio"
    if srv.zones_enabled():
        out["zona"] = it.get("zone") or ""
    if room.get("kind") == "consumiveis":  # 1.82.0: a categoria dos consumíveis e a duração; sem quantidade e sem valor
        ccats = srv.STORE.cons_cat_map()
        cid = it.get("cat") if it.get("cat") in ccats else srv.CONS_OUTROS
        out["categoria"] = {"id": cid, "nome": ccats.get(cid, "Outros")}
        out["duracao_dias"], out["duracao"] = srv.clean_dur(it.get("dur")), srv.dur_text(it.get("dur")) or "sem duração"
        if srv.used_in(it):  # 1.88.0
            out["usado_em"] = srv.used_in_text(it)
        if srv.dur_until(it):
            out["dura_ate"] = srv.dur_until(it)
        p = srv.par_of(it["id"])
        if p:  # 1.103.0: o parecer guardado do Avaliar com IA
            out["parecer"] = {"nota": p.get("nota"), "resumo": p.get("resumo"), "em": (p.get("at") or "")[:10]}
    else:
        cid = it.get("cat") if it.get("cat") in cats else "outros"
        out["categoria"] = {"id": cid, "nome": cats.get(cid, "Outros")}
        out["quantidade"] = str(it.get("qty") or "1")
        taxas = _taxas(srv)
        out["valor"] = _v(srv, it, taxas)
        if taxas:
            out["valor_gravado"] = _num(it.get("value"))
        m = re.match(r"\s*(\d+)", out["quantidade"])
        n = int(m.group(1)) if m else 1
        if n > 1:
            out["valor_de_cada"] = round(out["valor"] / n, 2)
        out["valor_desde"] = str(it.get("valueAt") or it.get("createdAt") or "")[:10]
    rec = srv.rec_of(it["id"]) if srv.ai_enabled() else {}
    if rec.get("recursos"):  # 1.107.0: os recursos guardados (os de Pesquisas da IA › Recursos)
        out["recursos"] = [r.get("nome") for r in rec["recursos"] if r.get("nome")]
    out["detalhes"] = it.get("details") or ""
    out["observacao"] = it.get("flag") or ""
    out["fotos"] = len(it.get("photos") or [])
    out["origem"] = ORIGENS.get(it.get("source"), "cadastro manual")
    out["cadastrado"] = {"em": str(it.get("createdAt") or "")[:16].replace("T", " "), "por": it.get("createdBy") or ""}
    if it.get("updatedAt") and it.get("updatedAt") != it.get("createdAt"):
        out["alterado"] = {"em": str(it["updatedAt"])[:16].replace("T", " "), "por": it.get("updatedBy") or ""}
    return _json(out)


# ---------------------------------------------------------------- gravação

def _cadastrar(srv, a, quem, fotos=None) -> str:
    lote = a.get("itens")
    if not isinstance(lote, list) or not lote:
        raise ErroFerramenta("Mande os itens numa lista: itens: [{nome, valor, quantidade, categoria}].")
    if len(lote) > MAX_LOTE:
        raise ErroFerramenta(f"No máximo {MAX_LOTE} itens de cada vez.")
    room = _achar_comodo(srv, a.get("comodo"), criar_bens=True)
    # 1.91.0 (o dono, numa ronda: "Não deu: duracao_dias só vale num consumível". "Entendi nada"): itens com duracao_dias ou
    # usado_em são consumíveis, mesmo com o comodo de um cômodo da casa (a IA manda o cômodo da ronda): vão para os
    # Consumíveis e, com Consumíveis por cômodo, esse cômodo vira o usado_em de quem não disse outro.
    de_cons = lambda x: isinstance(x, dict) and (x.get("duracao_dias") not in (None, 0) or x.get("usado_em") not in (None, ""))
    if not _area(room) and srv.consumiveis_enabled() and all(de_cons(x) for x in lote):
        if srv.cons_comodo_enabled():
            lote = [dict(x, usado_em=x.get("usado_em") or room.get("name")) for x in lote]
        room = _achar_comodo(srv, "Consumíveis", criar_bens=True)
    bem = bool(_area(room))
    cons = _area(room) == "consumiveis"
    zona_geral = _texto(srv, a.get("zona"), 120, "zona") if a.get("zona") not in (None, "") else ""
    _zona_ok(srv, room, bool(zona_geral))
    corpos = []
    for n, x in enumerate(lote, 1):
        if not isinstance(x, dict):
            raise ErroFerramenta(f"Item {n}: mande um objeto, como {{\"nome\": \"Abajur\", \"valor\": 120}}.")
        sobra = sorted(set(x) - set(POR_NOME["cadastrar_itens"]["entrada"]["properties"]["itens"]["items"]["properties"]))
        if sobra:
            raise ErroFerramenta(f"Item {n}: campo desconhecido: {', '.join(sobra)}. Valem: nome, valor, quantidade, categoria, duracao_dias, usado_em, detalhes, observacao, zona.")
        try:
            if cons:
                _sem_valor(x)
            elif x.get("duracao_dias") not in (None, 0):
                raise ErroFerramenta("A duração só vale num consumível: mande comodo \"Consumíveis\" (com Usar consumíveis ligado no InventarIA).")
            if x.get("usado_em") not in (None, "") and not cons:
                raise ErroFerramenta("O cômodo onde é usado só vale num consumível: mande comodo \"Consumíveis\" (com Usar consumíveis ligado no InventarIA).")
            zona = _texto(srv, x.get("zona"), 120, "zona") if x.get("zona") not in (None, "") else zona_geral
            _zona_ok(srv, room, x.get("zona") not in (None, ""))
            corpos.append({"name": _texto(srv, x.get("nome"), 200, "nome", obrig=True), "value": _valor(srv, x.get("valor")),
                           "qty": _qtd(srv, x.get("quantidade")), "cat": _achar_categoria(srv, x.get("categoria"), cons=cons, solta=True),
                           **({"dur": _duracao(srv, x["duracao_dias"])} if cons and x.get("duracao_dias") is not None else {}),
                           **({"usedIn": _usado_em(srv, x["usado_em"])} if cons and x.get("usado_em") not in (None, "") else {}),
                           "details": _texto(srv, x.get("detalhes"), 4000, "detalhes", linhas=True), "flag": _texto(srv, x.get("observacao"), 200, "observação"),
                           "zone": "" if bem else zona, "source": "correria"})
        except (ErroFerramenta, srv.ApiError) as e:
            raise ErroFerramenta(f"Item {n}: {getattr(e, 'msg', None) or e}") from None
    room = _criar_area(srv, room)  # o primeiro bem (ou consumível) cria a área, como na tela
    for c in corpos:
        c["room"] = room["id"]
    if fotos and len(corpos) == 1:  # 1.92.0: a foto da conversa (cadastrar_por_foto)
        corpos[0]["photos"] = list(fotos)
    _, items = srv.visible_data()
    iguais = {srv.fold(i.get("name") or ""): i for i in items if i.get("room") == room["id"]}
    novos = srv.STORE.create_items(corpos, quem)
    txt = (f"Cadastrado em {room.get('name')}: " if len(novos) == 1 else f"Cadastrados {len(novos)} itens em {room.get('name')}: ")
    txt += "; ".join(_frase(srv, it) for it in novos) + "."
    if len(novos) > 1 and not cons:
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
    cons = room.get("kind") == "consumiveis"
    if cons:  # 1.82.0
        _sem_valor(a)
        a = {k: v for k, v in a.items() if k not in ("valor", "quantidade")}
        if "duracao_dias" in a:
            novo["dur"] = _duracao(srv, a["duracao_dias"])
        if "usado_em" in a:
            novo["usedIn"] = _usado_em(srv, a["usado_em"])
    elif "duracao_dias" in a:
        raise ErroFerramenta("duracao_dias só vale num consumível.")
    elif "usado_em" in a:
        raise ErroFerramenta("usado_em só vale num consumível.")
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
        novo["cat"] = _achar_categoria(srv, a["categoria"], cons=cons)
    if "zona" in a:
        z = _texto(srv, a["zona"], 120, "zona")
        _zona_ok(srv, room, True)
        novo["zone"] = z
    if "detalhes" in a:
        novo["details"] = _texto(srv, a["detalhes"], 4000, "detalhes", linhas=True)
    if "observacao" in a:
        novo["flag"] = _texto(srv, a["observacao"], 200, "observação") or None
    if not novo:
        raise ErroFerramenta("Diga o que muda: nome, categoria, duracao_dias, detalhes ou observacao." if cons
                             else "Diga o que muda: nome, valor, quantidade, categoria, zona, detalhes ou observacao.")
    rotulo = {"usedIn": "usado em", "name": "nome", "value": "valor", "qty": "quantidade", "cat": "categoria", "zone": "zona", "details": "detalhes", "flag": "observação",
              "dur": "duração"}
    cats = srv.STORE.cons_cat_map() if cons else srv.STORE.cat_map()

    def mostra(k, v):
        if k == "value":
            return srv._money(v)
        if k == "cat":
            return cats.get(v, "Outros")
        if k == "dur":
            return srv.dur_text(v) or "(sem)"
        if k == "usedIn":
            return ", ".join(srv.STORE.room(r)["name"] for r in srv.STORE.home_rooms(v)) or "(nenhum)"
        if k == "details":
            v = " ".join(str(v or "").split())
            return f"\"{v[:80]}{'…' if len(v) > 80 else ''}\"" if v else "(vazio)"
        return f"\"{v}\"" if v not in (None, "") else "(vazio)"

    antes = {k: (it.get(k) if k != "cat" else (it.get("cat") if it.get("cat") in cats else (srv.CONS_OUTROS if cons else "outros"))) for k in novo}
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
    room = _criar_area(srv, room)
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
    if srv.fold(nome) in ("consumiveis", "consumivel"):
        raise ErroFerramenta("Consumíveis é a área do que se gasta: cadastre com inventario_cadastrar_itens e comodo Consumíveis.")
    if not srv.itens_enabled():
        raise ErroFerramenta("Os itens da casa estão desligados no InventarIA (Mais › Configurações › Opções › Usar itens da casa).")
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


# ---------------------------------------------------------------- comprei, cômodos e categorias (1.101.0)

def _avaliar(srv, a) -> str:
    """1.103.0: o parecer da IA sobre um consumível (o guardado, ou um novo pela busca na web), fora da trava do Store."""
    with srv.STORE.lock:
        it = _achar_item(srv, a.get("id"))
    if not _eh_cons(srv, it):
        raise ErroFerramenta(f"{it.get('name')} não é um consumível: o Avaliar com IA é dos consumíveis.")
    if not srv.ai_enabled():
        raise ErroFerramenta("A IA do InventarIA está desligada (Mais › Configurações › Integrações › Usar IA). Diga isso à pessoa.")
    p = {} if a.get("nova") is True else srv.par_of(it["id"])
    novo = not p
    if novo:
        p = srv.avaliar(it["id"])
    out = {"item": it.get("name"), "id": it["id"], "avaliado_em": (p.get("at") or "")[:10], "novo": novo,
           **{k: p.get(k) for k in ("produto", "nota", "resumo", "fortes", "fracos", "dicas", "alternativas", "preco") if p.get(k) not in (None, "", [])}}
    if p.get("fontes"):
        out["fontes"] = [f["url"] for f in p["fontes"]]
    return json.dumps(out, ensure_ascii=False)


def _pareceres(srv, a) -> str:
    """1.107.0: os pareceres guardados dos consumíveis (o que a tela Pesquisas da IA › Pareceres mostra), sem chamar a IA."""
    if not srv.ai_enabled():
        raise ErroFerramenta("A IA do InventarIA está desligada (Mais › Configurações › Integrações › Usar IA). Diga isso à pessoa.")
    if not srv.consumiveis_enabled():
        raise ErroFerramenta("Os consumíveis estão desligados (Mais › Configurações › Opções › Usar consumíveis). Diga isso à pessoa.")
    com, sem = [], []
    for it in srv.STORE.sorted_items():
        if not _eh_cons(srv, it):
            continue
        p = srv.par_of(it["id"])
        if p and (p.get("resumo") or p.get("fortes")):
            com.append({"id": it["id"], "item": it.get("name"), "nota": p.get("nota"), "resumo": p.get("resumo"), "avaliado_em": (p.get("at") or "")[:10]})
        else:
            sem.append({"id": it["id"], "item": it.get("name")})
    out = {"sem_parecer": sem} if a.get("so_sem") is True else {"com_parecer": sorted(com, key=lambda x: -(x["nota"] or 0)), "sem_parecer": sem}
    return json.dumps(out, ensure_ascii=False)


def _apagar_pesquisa(srv, a) -> str:
    """1.107.0: Apagar as novidades, os recursos ou o parecer de um item (o Apagar da ficha), fora da trava do Store."""
    o_que = a.get("o_que")
    if o_que not in ("novidades", "recursos", "parecer"):
        raise ErroFerramenta("o_que: novidades, recursos ou parecer.")
    if a.get("todos") is True:  # 1.109.0: os de todos, como o Limpar da tela
        if o_que == "novidades":
            raise ErroFerramenta("As novidades de todos se limpam em Mais › Pesquisas da IA › Novidades › Limpar. Aqui, com todos, recursos ou parecer.")
        (srv.rec_clear if o_que == "recursos" else srv.par_clear)()
        return json.dumps({"apagado": o_que, "todos": True}, ensure_ascii=False)
    if not a.get("id"):
        raise ErroFerramenta("Diga o id do item (ou todos: true para os recursos ou os pareceres de todos).")
    with srv.STORE.lock:
        it = _achar_item(srv, a.get("id"))
    if o_que == "novidades":
        r = srv.news_of(it["id"])
        if not ((r.get("news") or {}).get("novidades")):
            raise ErroFerramenta(f"{it.get('name')} não tem novidades para apagar.")
        srv.news_dismiss(it["id"])
    elif o_que == "recursos":
        if not srv.rec_of(it["id"]):
            raise ErroFerramenta(f"{it.get('name')} não tem recursos guardados.")
        srv.rec_dismiss(it["id"])
    else:
        if not _eh_cons(srv, it):
            raise ErroFerramenta(f"{it.get('name')} não é um consumível: o parecer é dos consumíveis.")
        if not srv.par_of(it["id"]):
            raise ErroFerramenta(f"{it.get('name')} não tem parecer para apagar.")
        srv.par_dismiss(it["id"])
    return json.dumps({"item": it.get("name"), "id": it["id"], "apagado": o_que}, ensure_ascii=False)


def _comprei(srv, a, quem) -> str:
    it = _achar_item(srv, a.get("id"))
    if not _eh_cons(srv, it):
        raise ErroFerramenta(f"{it.get('name')} não é um consumível: o Comprei é dos consumíveis.")
    mud = {"_comprado": True}
    if a.get("duracao_dias") is not None:
        dias = _duracao(srv, a["duracao_dias"])
        if not dias:
            raise ErroFerramenta("duracao_dias: de 1 a 3650 dias.")
        mud["dur"] = dias
    elif not srv.clean_dur(it.get("dur")):
        raise ErroFerramenta(f"{it.get('name')} não tem duração estimada: mande duracao_dias (quanto costuma durar).")
    novo = srv.STORE.update_item(it["id"], mud, quem)
    return (f"Comprei anotado: {novo.get('name')} dura {srv.dur_text(novo.get('dur'))}, até {srv.dur_until(novo)}"
            if srv.dur_until(novo) else f"Comprei anotado: {novo.get('name')}") + "."


def _editar_comodo(srv, a, quem) -> str:
    room = _achar_comodo(srv, a.get("comodo"))
    if room.get("kind"):
        raise ErroFerramenta(f"{room.get('name')} é uma área do app: não se renomeia nem se apaga.")
    if a.get("apagar") is True:
        n = sum(1 for i in srv.STORE.data["items"] if i.get("room") == room["id"])
        if n:
            raise ErroFerramenta(f"{room['name']} tem {n} {'item' if n == 1 else 'itens'}: mova (inventario_mover_itens) ou apague antes.")
        srv.STORE.delete_room(room["id"])
        return f"Cômodo apagado: {room['name']}."
    mud = {}
    if a.get("nome") not in (None, ""):
        nome = _texto(srv, a.get("nome"), 60, "nome do cômodo", obrig=True)
        if any(srv.fold(r.get("name") or "") == srv.fold(nome) and r["id"] != room["id"] for r in srv.STORE.data["rooms"]):
            raise ErroFerramenta(f"Já existe o cômodo {nome}.")
        mud["name"] = nome
    if a.get("codigo") not in (None, ""):
        mud["code"] = _texto(srv, a.get("codigo"), 4, "código")
    if not mud:
        raise ErroFerramenta("Diga o que muda: nome ou codigo (ou apagar).")
    antes = dict(room)
    r = srv.STORE.update_room(room["id"], mud)
    partes = ([f"nome {antes['name']} → {r['name']}"] if r["name"] != antes["name"] else []) + \
             ([f"código {antes['code']} → {r['code']} (os itens viram {r['code']}-001…)"] if r["code"] != antes["code"] else [])
    return "Cômodo mudado: " + ("; ".join(partes) or "nada mudou") + "."


def _categoria(srv, a, quem) -> str:
    cons = a.get("consumiveis") is True
    if cons and not srv.consumiveis_enabled():
        raise ErroFerramenta("Os consumíveis estão desligados no InventarIA (Mais › Configurações › Opções › Usar consumíveis).")
    acao, de = a.get("acao"), " dos consumíveis" if cons else ""
    if acao == "nova":
        corpo = {"name": a.get("nome"), **({"kind": "consumiveis"} if cons else {}), **({"cor": a["cor"]} if a.get("cor") else {})}
        c = srv.STORE.create_cat(corpo)
        return f"Categoria{de} criada: {c['name']} ({c.get('cor')}). id {c['id']}"
    cid = _achar_categoria(srv, a.get("nome"), cons)
    velho = (srv.STORE.cons_cat_map() if cons else srv.STORE.cat_map()).get(cid, cid)
    if acao == "apagar":
        n = srv.STORE.delete_cat(cid)
        return f"Categoria apagada: {velho}." + (f" {n} {'item foi' if n == 1 else 'itens foram'} para Outros." if n else "")
    corpo = {**({"name": a["novo_nome"]} if str(a.get("novo_nome") or "").strip() else {}), **({"cor": a["cor"]} if a.get("cor") else {})}
    if not corpo:
        raise ErroFerramenta("Diga o que muda: novo_nome e/ou cor.")
    c = srv.STORE.update_cat(cid, corpo)
    return f"Categoria mudada: {velho}" + (f" → {c['name']}" if c["name"] != velho else "") + f" ({c.get('cor')})."


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


def _por_foto(srv, a, quem, anexo) -> str:
    """A foto da conversa vira um item: guarda a foto, lê com a IA daqui se faltar o nome (fora da trava do Store: a
    leitura demora) e cadastra pelas regras do cadastrar_itens, com a foto no item."""
    cons = a.get("duracao_dias") not in (None, 0) or a.get("usado_em") not in (None, "") or srv.fold(str(a.get("comodo") or "")) in ("consumiveis", "consumivel")
    item = {k: a[k] for k in ("nome", "valor", "categoria", "duracao_dias", "usado_em", "detalhes", "zona") if a.get(k) not in (None, "")}
    arquivo = _foto_do_anexo(srv, anexo)
    if not item.get("nome"):
        if not srv.ai_enabled():
            raise ErroFerramenta("A foto chegou, mas a IA do InventarIA está desligada e não dá para ler o que é. Pergunte o nome do item e chame de novo com nome.")
        try:
            lidos = srv.ai_identify({"file": arquivo, "mode": "single", "consumivel": cons}).get("items") or []
        except srv.ApiError as e:
            raise ErroFerramenta(f"Não consegui ler a foto ({e.msg}) Pergunte o nome do item e chame de novo com nome.") from None
        if not lidos:
            raise ErroFerramenta("Não reconheci nada na foto. Pergunte o nome do item e chame de novo com nome.")
        item["nome"] = lidos[0]["name"]
        item.setdefault("detalhes", lidos[0].get("details") or "")
        if lidos[0].get("cat"):
            item.setdefault("categoria", lidos[0]["cat"])
    with srv.STORE.lock:
        return _cadastrar(srv, {"comodo": a.get("comodo"), "itens": [item]}, quem, fotos=[arquivo])


def _foto_do_anexo(srv, anexo) -> str:
    """Guarda a foto que veio do CorrerIA e devolve o nome do arquivo."""
    b64 = anexo.get("b64") if isinstance(anexo, dict) and isinstance(anexo.get("b64"), str) else ""
    b64 = b64.split(",", 1)[1] if b64.startswith("data:") and "," in b64 else b64
    if not b64:
        raise ErroFerramenta("Não chegou nenhuma foto. Peça para a pessoa mandar a foto de novo, com o pedido junto.")
    return srv.save_photo({"full": b64})["file"]


def _anexar_foto(srv, a, quem, anexo) -> str:
    """1.93.0: a foto da conversa num item que já existe (como o Adicionar foto da ficha)."""
    with srv.STORE.lock:
        it = _achar_item(srv, a.get("id"))
        arquivo = _foto_do_anexo(srv, anexo)
        fotos = list(it.get("photos") or []) + [arquivo]
        srv.STORE.update_item(it["id"], {"photos": fotos}, quem)
        return f"Foto guardada em {it.get('name')} ({srv.STORE.tag(it)}): agora {'tem 1 foto' if len(fotos) == 1 else f'tem {len(fotos)} fotos'}."


def _ler_arquivo(srv, a, anexo) -> str:
    """1.93.0: o Digitalizar com IA de várias coisas numa foto, pelo CorrerIA: a IA daqui lê e devolve o que há; nada é
    cadastrado e a foto não fica guardada."""
    if not srv.ai_enabled():
        raise ErroFerramenta("A IA do InventarIA está desligada (Mais › Configurações › Integrações › Usar IA): não dá para ler a foto. Diga isso à pessoa.")
    arquivo = _foto_do_anexo(srv, anexo)
    try:
        corpo = {"file": arquivo, "mode": "multi", "hint": " ".join(str(a.get("dica") or "").split())[:300]}
        cons = a.get("consumiveis") is True or srv.fold(str(a.get("comodo") or "")) in ("consumiveis", "consumivel")
        if cons and not srv.consumiveis_enabled():
            raise ErroFerramenta("Os consumíveis estão desligados no InventarIA (Mais › Configurações › Opções › Usar consumíveis). Diga isso à pessoa.")
        if cons:
            corpo["consumivel"] = True
        elif a.get("comodo") not in (None, ""):
            room = _achar_comodo(srv, a.get("comodo"))
            if not isinstance(room, str) and not _area(room):
                corpo["room"] = room["id"]
        try:
            lidos = srv.ai_identify(corpo).get("items") or []
        except srv.ApiError as e:
            raise ErroFerramenta(f"O InventarIA não conseguiu ler a foto ({e.msg}) Diga isso à pessoa, sem inventar o que há nela.") from None
    finally:
        for pasta in (srv.PHOTOS_DIR, srv.THUMBS_DIR):
            try:
                os.unlink(os.path.join(pasta, arquivo))
            except OSError:
                pass
    if not lidos:
        return "A IA do InventarIA leu a foto e não reconheceu nenhum item nela. Diga isso à pessoa e pergunte o que ela quer fazer."
    if cons:  # 1.94.0: só os consumíveis, com a duração estimada e os que já existem (pelo nome, sem acento nem maiúsculas)
        ccats = srv.STORE.cons_cat_map()
        with srv.STORE.lock:
            area = next((r["id"] for r in srv.STORE.data["rooms"] if r.get("kind") == "consumiveis"), None)
            tem = {srv.fold(i["name"]): i["name"] for i in srv.STORE.data["items"] if area and i["room"] == area}
        linhas = []
        for it in lidos:
            extra = "; ".join(x for x in (ccats.get(it.get("cat")), " ".join(str(it.get("details") or "").split())[:160],
                                          f"duração estimada: {it['dur']} dias" if it.get("dur") else "") if x)
            ja = tem.get(srv.fold(it["name"]))
            linhas.append(f"- {it['name']}" + (f" ({extra})" if extra else "") + (f" [já está nos consumíveis: {ja}]" if ja else ""))
        return (f"Na foto (lida pela IA do InventarIA) {'há 1 consumível' if len(lidos) == 1 else f'há {len(lidos)} consumíveis'}:\n" + "\n".join(linhas)
                + "\nNada foi cadastrado. São todos consumíveis: não pergunte se são bens nem peça valor. Mostre a lista à pessoa e proponha "
                  "cadastrar com inventario_cadastrar_itens, no cômodo «Consumíveis», os que ainda não estão cadastrados, com duracao_dias "
                  "(a que a pessoa disse; sem ela, a estimada, dizendo que é estimada), a categoria e os detalhes daqui.")
    cats = srv.STORE.cat_map()
    linhas = []
    for it in lidos:
        extra = "; ".join(x for x in (cats.get(it.get("cat")), " ".join(str(it.get("details") or "").split())[:160]) if x)
        linhas.append(f"- {it['name']}" + (f" ({extra})" if extra else "") + (f" [parece já estar cadastrado: {it['existing']}]" if it.get("existing") else ""))
    return (f"Na foto (lida pela IA do InventarIA) {'há 1 item' if len(lidos) == 1 else f'há {len(lidos)} itens'}:\n" + "\n".join(linhas)
            + "\nNada foi cadastrado. Mostre à pessoa e cadastre com inventario_cadastrar_itens os que ela quiser (o valor é ela quem diz).")


def chamar(srv, nome, argumentos, pessoa=None, cliente=None, anexo=None) -> str:
    """Roda a ferramenta (as de gravar mudam o inventário pelo Store, que grava, sobe a rev e faz a versão automática)."""
    a = conferir_argumentos(nome, argumentos)
    quem = _quem(pessoa, cliente)
    if nome == "avaliar":  # 1.103.0: a IA pesquisa na web, fora da trava do Store
        try:
            return _avaliar(srv, a)
        except srv.ApiError as e:
            raise ErroFerramenta(e.msg) from None
    if nome in ("pareceres", "apagar_pesquisa"):  # 1.107.0: cada arquivo tem a trava dele
        try:
            return _pareceres(srv, a) if nome == "pareceres" else _apagar_pesquisa(srv, a)
        except srv.ApiError as e:
            raise ErroFerramenta(e.msg) from None
    if nome in ("cadastrar_por_foto", "anexar_foto", "ler_arquivo"):  # as que recebem a foto (a leitura por IA fica fora da trava do Store)
        try:
            return _por_foto(srv, a, quem, anexo) if nome == "cadastrar_por_foto" else _anexar_foto(srv, a, quem, anexo) if nome == "anexar_foto" else _ler_arquivo(srv, a, anexo)
        except srv.ApiError as e:
            raise ErroFerramenta(e.msg) from None
    try:
        with srv.STORE.lock:
            if nome == "resumo":
                return _resumo(srv)
            if nome == "buscar_itens":
                return _buscar(srv, a)
            if nome == "ver_item":
                return _ver(srv, a)
            if nome == "novidades":
                return _novidades(srv, a)
            faz = {"cadastrar_itens": _cadastrar, "editar_item": _editar, "mover_itens": _mover, "apagar_item": _apagar,
                   "novo_comodo": _novo_comodo, "comprei": _comprei, "editar_comodo": _editar_comodo, "categoria": _categoria}[nome]
            return faz(srv, a, quem)
    except srv.ApiError as e:  # as regras do Store (nome obrigatório, valor, cômodo que não existe…) viram 400 para a IA
        raise ErroFerramenta(e.msg) from None
