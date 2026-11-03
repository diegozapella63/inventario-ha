"""As contas e regras puras da tela (valores, quantidades, separar o que foi falado, dados da internet, códigos), no navegador."""
from e2e_lib import main

HOOK = "window.INV_TEST = (f) => { window.__f = f; };"


async def body(r, p):
    r.start(search=False)
    b = await r.browser(p)
    ctx, pg = await r.page(b, "pc", init=HOOK)
    await r.open(pg)
    ev = lambda js, *a: pg.evaluate(js, *a)  # noqa: E731

    # valores como a pessoa digita
    casos = {"1200": 1200, "1.200": 1200, "1.200,50": 1200.5, "R$ 2.000": 2000, "0,99": 0.99, "": 0, " 300 ": 300, "3.5": 3.5, "1.234.567,89": 1234567.89}
    got = await ev("(c) => Object.fromEntries(Object.keys(c).map(k => [k, __f.parseMoney(k)]))", casos)
    r.eq(got, casos, "parseMoney entende os formatos brasileiros")
    r.check(await ev("() => [__f.parseMoney('abc'), __f.parseMoney('-5')].every(Number.isNaN)"), "parseMoney recusa texto e negativo")
    r.eq(await ev("() => [__f.money(1200), __f.money(1200.5), __f.moneyR(99.6), __f.moneyInput(0), __f.moneyInput(1500)]"),
         ["R$ 1.200", "R$ 1.200,50", "R$ 100", "", "1.500"], "dinheiro formatado")
    r.eq(await ev("() => [__f.qtyNum('2'), __f.qtyNum('~3'), __f.qtyNum('1 par'), __f.qtyClean(''), __f.qtyLabel('1'), __f.qtyLabel('4'), __f.qtyLabel('1 par'), __f.qtyShort('2')]"),
         [2, 3, None, "1", "1 unidade", "4 unidades", "1 par", "2 un."], "quantidades")
    r.eq(await ev("() => [__f.plural(1, 'item', 'itens'), __f.plural(2, 'item', 'itens'), __f.plural(1500, 'item', 'itens')]"),
         ["1 item", "2 itens", "1.500 itens"], "plural com milhar")
    r.eq(await ev("() => [__f.pctFmt(0), __f.pctFmt(0.4), __f.pctFmt(37.6), __f.pct(1, 4), __f.pct(1, 0)]"), ["0%", "<1%", "38%", 25, 0], "porcentagens")
    r.eq(await ev("() => [__f.norm('Ação Ótima'), __f.suggestCode('Área de serviço'), __f.suggestCode('Sala')]"), ["acao otima", "ARE", "SAL"], "acentos e código sugerido")
    r.eq(await ev("() => __f.esc('<img src=x onerror=alert(1)>&\"')"), "&lt;img src=x onerror=alert(1)&gt;&amp;&quot;", "texto escapado (sem HTML de fora)")
    r.eq(await ev("() => __f.siteOf('https://www.loja.exemplo/p?x=1')"), "loja.exemplo", "site de uma foto da internet")

    # Cor do dia: uma cor da paleta por dia, pela data local; o cinza fica de fora; depois da última, a primeira
    r.eq(await ev("() => [__f.accents().length, __f.dayAccents()]"),
         [10, ["amarelo", "laranja", "coral", "rosa", "lilas", "azul", "turquesa", "verde", "kraft"]], "Cor do dia: as 10 cores menos o Cinza")
    dias = await ev("() => [[2026, 10, 3], [2026, 10, 4], [2026, 10, 5], [2026, 10, 6], [2026, 11, 31], [2027, 0, 1], [2024, 1, 29], [1970, 0, 1]].map(([y, m, d]) => __f.colorOfDay(new Date(y, m, d, 12)))")
    r.eq(dias, ["turquesa", "verde", "kraft", "amarelo", "laranja", "coral", "amarelo", "amarelo"], "Cor do dia em datas fixas (de Kraft volta a Amarelo; virada do ano; 29 de fevereiro)")
    r.eq(await ev("() => [0, 1, 12, 23].map(h => __f.colorOfDay(new Date(2026, 10, 3, h, h ? 59 : 0, h ? 59 : 0)))"), ["turquesa"] * 4, "a mesma cor o dia todo, da meia-noite às 23h59")
    seq = await ev("() => Array.from({ length: 18 }, (_, i) => __f.colorOfDay(new Date(2026, 10, 3 + i)))")
    r.check(len(set(seq[:9])) == 9 and seq[9:] == seq[:9], f"9 dias seguidos, 9 cores diferentes, e de novo ({seq})")
    r.check(await ev("() => Array.from({ length: 3700 }, (_, i) => __f.colorOfDay(new Date(2026, 0, 1 + i))).every(c => c !== 'cinza')"), "em 10 anos, nenhum dia Cinza")

    # Falar sem IA: separa pelas vírgulas, pontos e "e"; valor falado vai para o item
    split = await ev("(t) => __f.splitSpoken(t).map(i => [i.name, i.value])",
                     "Sofá cinza, 2.000 reais. Mesa de jantar e quatro cadeiras, TV Samsung R$ 3.000, cafeteira por 499,90 reais")
    r.eq(split[0], ["Sofá cinza", 2000], "Falar sem IA: valor dito depois do item")
    r.check(any(n.startswith("TV Samsung") and v == 3000 for n, v in split), f"Falar sem IA: valor no fim do item ({split})")
    r.check(any(n.startswith("Mesa de jantar") for n, _ in split) and any(n.lower().startswith("quatro cadeiras") for n, _ in split), "Falar sem IA: separa pelo 'e'")
    r.check(["Cafeteira", 499.9] in [[n, round(v, 2)] for n, v in split], "Falar sem IA: vírgula decimal não separa itens, e o 'por' sai do nome")
    more = await ev("(t) => __f.splitSpoken(t).map(i => [i.name, i.value])", "tapete de uns 300 reais; abajur que custou 2 mil reais")
    r.eq(more, [["Tapete", 300], ["Abajur", 2000]], "'de uns' e 'que custou' antes do valor saem do nome")
    # valor por extenso vira número; quantidade por extenso fica
    w2n = await ev("(l) => l.map(__f.wordsToNumbers)", ["dois mil reais", "três mil", "mil e duzentos reais", "duzentos e cinquenta", "vinte e cinco reais",
                                                           "cem mil reais", "duas luminárias", "um sofá de mil reais", "três mil e duas luminárias", "Três Mil"])
    r.eq(w2n, ["2000 reais", "3000", "1200 reais", "250", "25 reais", "100000 reais", "duas luminárias", "um sofá de 1000 reais", "3000 e duas luminárias", "3000"],
         "números por extenso")
    falado = await ev("(t) => __f.splitSpoken(t).map(i => [i.name, i.value])",
                      "Sofá cinza de três lugares, uns dois mil reais. Televisão Samsung de 55 polegadas, três mil. E duas luminárias de chão. Mesa de mil e duzentos reais")
    r.eq(falado, [["Sofá cinza de três lugares", 2000], ["Televisão Samsung de 55 polegadas", 3000], ["Duas luminárias de chão", 0], ["Mesa", 1200]],
         "Falar sem IA com valores por extenso")

    # Buscar na internet: o que os dados do produto preenchem
    wf = "(a) => __f.webFills(a[0], a[1], a[2])"
    p = {"name": "Cafeteira X", "details": "inox", "cat": "cozinha", "value": 450}
    r.eq(await ev(wf, [{"name": "cafeteira", "details": "", "cat": "", "value": 0}, p, True]), p, "item novo: preenche tudo, até o nome")
    r.eq(await ev(wf, [{"name": "cafeteira", "details": "minha", "cat": "moveis", "value": 300}, p, True]), {"name": "Cafeteira X"}, "não troca o que a pessoa escreveu")
    r.eq(await ev(wf, [{"name": "cafeteira", "details": "", "cat": "outros", "value": 0}, p, False]), {"details": "inox", "cat": "cozinha", "value": 450}, "item existente: nunca o nome")
    r.eq(await ev(wf, [{"name": "Cafeteira X", "details": "", "cat": "", "value": 0}, None, True]), {}, "sem dados, nada")

    # data das novidades do produto
    r.eq(await ev("() => ['2026-09-12', '2026-01', '2026', '', null].map(__f.newsDate)"), ["12 set. 2026", "jan. 2026", "2026", "", ""], "data das novidades")

    # categorias da casa
    r.eq(await ev("() => { __f.applyCats([{id: 'a', name: 'A'}, {id: 'outros', name: 'Outros'}]); const c = __f.cats(); __f.applyCats(null); return [c, __f.cats().length]; }"),
         [[["a", "A"], ["outros", "Outros"]], 13], "categorias da casa e volta para a padrão")
    await ctx.close()
    await b.close()


main("funcoes", body)
