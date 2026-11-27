# Padrões da família de apps

O que vale em todos os apps do Diego (pessoas ou IAs). Este arquivo é **igual nos 8 repositórios** (o `tools/iguais.py`
confere a cada push); o `AGENTS.md` de cada app diz como cada regra é feita ali (os nomes das funções e dos arquivos).

Uma regra nova que o dono pede para todos ("igual aos outros apps", "vale em todos", "isso era nosso padrão") entra aqui,
é feita em todos os apps e este arquivo é copiado para os outros 7. Quando o dono pede "igual ao ResolvIA" ou "como no
OdisseIA", abra o código desse app e faça do mesmo jeito: os textos, os botões, a ordem, o comportamento.

## A família

| App | Pasta e repositório (`diegozapella63/…`) | O que é | Feito com |
|---|---|---|---|
| ResolvIA | `resolvia-ha` | listas de tarefas, pontos, repetição | Lit (`frontend/src`) e Node |
| CronologIA | `cronologia-ha` | calendário, rotinas, remédios, placar | Lit e Node |
| MemorIA | `memoria-ha` | blocos de anotação | Lit e Node |
| GerencIA | `gerencia-ha` | finanças | JavaScript puro e Python |
| InventarIA | `inventario-ha` | inventário da casa | JavaScript puro e Python |
| EconomIA | `economia-ha` | lista de compras e preços | uma página (`pagina/painel.html`, montada) e Python |
| OdisseIA | `odisseia` (no GitHub, `OdisseIA`) | filmes, séries e jogos | JavaScript puro e Python |
| CorrerIA | `correria-ha` (no GitHub, `CorrerIA-ha`) | os apps no WhatsApp, no Claude e no Gemini | JavaScript puro e Python |

O Home Assistant instala direto da branch `main`: o que está lá é o que a casa recebe.

## Conversa com o dono

- Em português, curto. Ao terminar: o que mudou, a versão, se está publicado e o caminho para atualizar:
  **Configurações › Aplicativos › Loja de aplicativos › ⋮ › Verificar atualizações › <app> › Atualizar**.
- Ele usa o app do Home Assistant no Android: pense no Voltar do celular, no teclado e na câmera.
- Toda mudança é pensada também para a IA e o CorrerIA: o que a tela faz, uma ferramenta faz. Quando ele pergunta quais
  ferramentas adicionar, diga quais (os nomes e o que cada uma faz), não só que dá.
- "Faz tudo", "pode fazer": tudo o que foi oferecido. Pode publicar antes de os testes do GitHub terminarem; depois, confira.
- Os prints que ele manda têm dados de verdade: nunca vão para teste, exemplo, captura ou commit.

## Toda mudança

1. `git pull --rebase` antes de começar: outras sessões também publicam.
2. Servidor só com o que já vem: biblioteca padrão do Python ou módulos do Node (o Lit fica em `frontend/vendor`).
3. Teste para toda mudança e todo erro corrigido (o teste que pegaria o erro); a cobertura fica acima de 95% das linhas.
4. Versão num lugar só, o `config.yaml` (no GerencIA, o `tools/versao.py` escreve os três lugares). Correção = patch
   (1.2.3 → 1.2.4); novidade = minor (1.2.x → 1.3.0).
5. `CHANGELOG.md`: começa com `# Mudanças`; a seção nova no topo, em português, do ponto de vista de quem usa.
6. `DOCS.md` quando muda o comportamento; `README.md` (e as capturas, pelo `tools/` do app, com uma casa inventada)
   quando muda a lista do que o app tem; no `AGENTS.md`, uma linha da versão com o pedido do dono entre aspas e os nomes.
7. Commit em `main`, em português ("ResolvIA 2.94.0: …"), `git pull --rebase` e push. O GitHub roda todos os testes.
8. Arquivos iguais (abaixo): mudou um, copie para os outros do grupo e publique todos.

## Dados e segredos

- Exemplos, testes e capturas sempre inventados (Ana, Beto, itens e valores fictícios): nunca dados do dono.
- Tokens, chaves e senhas só em `/data`, com permissão 600; nunca voltam para a tela (só o fim, ••••1234) nem vão ao GitHub.
- **Dados**, nesta ordem: Exportar › Backup na pasta share (os últimos 10) › Importar › Versões anteriores (cópias
  automáticas, também antes de importar, restaurar ou começar do zero) › Onde ficam os dados › Começar do zero. Restaurar,
  importar e começar do zero pedem confirmação.
- O que um app guarda para outros (a Memória da IA, o `integracao.json`) fica fora do Exportar e do Começar do zero.

## A tela

**Navegação**
- Barra de baixo: **Agora** primeiro (onde o app abre, ícone do relógio; nunca Início), **Buscar** em 2º quando houver,
  **Adicionar** no meio, só o ícone (o nome no `aria-label`; no EconomIA, a ação principal dele), **Mais** por último
  (três pontos). O CorrerIA não tem barra: abre na Conversa e os três pontos levam ao Mais.
- Celular primeiro: 390 px de referência e nada passa da largura em 320 px. Com 1000 px ou mais (fora da Tela cheia), a
  barra lateral da família no lugar da de baixo e as janelas no meio. Tema claro e escuro.
- **Mais** é um menu: as funções do app (cada uma com a sua tela), depois **Configurações** e por último **Sobre** (o
  mesmo em todos: CorrerIA Code, os 8 apps e o GitHub). Os relatórios se chamam **Relatório de/do …**.
- O Voltar do celular fecha o que abriu por último (a janela, a Conversa, o menu do clipe, a seleção, uma confirmação,
  o outro horário espiado) e nunca sai do app sem querer: cada coisa aberta ocupa uma entrada no histórico. Uma janela
  aberta de dentro de outra volta para ela no Voltar, no X e no Cancelar. O ‹ Mais e arrastar para a direita voltam ao
  menu. Uma página do servidor (o Relatório) volta para a tela de onde saiu.
- Abrir uma aba não põe o foco num campo (o Buscar abre sem o teclado).
- Os links `/app/<slug>/<caminho>` (dos avisos e das rondas do CorrerIA) chegam pelo painel do Home Assistant
  (`home-assistant/properties`) e abrem a tela do caminho, também com o app já aberto.

**Configurações**: 4 abas, nesta ordem, **Integrações › Dados › Aparência › Opções**; abre em Integrações; nenhuma função
do app vira aba (o CorrerIA tem também WhatsApp e MCP).
- **Integrações**, nesta ordem: os outros apps da família › CorrerIA › **IA** › **Memória da IA** › **Falar** › **Uso da
  IA** › as integrações próprias do app › **Sensores**. O que depende de uma integração só aparece com ela ligada; o que
  depende da IA, com o Usar IA ligado.
- **Aparência**: o Tema vale no aparelho (começa em Sistema); a cor do app vale para a casa toda, numa paleta só de 12
  (Vermelho, Coral, Laranja, Ouro, Verde, Menta, Turquesa, Azul, Índigo, Lilás, Rosa, Grafite); a **Cor do dia** é a
  mesma em todos os apps (as 11 sem o Grafite, pelo número do dia). O fundo e os cartões são os do tema do Home Assistant
  (`hatema.js`); os cinzas (linhas, campos) saem do cartão misturado com o texto (`color-mix`), nunca uma cor fixa.

**Seções e ícones**
- Cada seção principal é um cartão (fundo, borda, cantos arredondados), sem linha no fim. Entre as linhas de opções não
  há linha; nas listas de dados, a linha fina entre as entradas, sem a do fim.
- Toda seção começa com o cabeçalho: o ícone e o título. O título de cada tela, grupo e janela (e a lista de uma caixa de
  seleção) também tem o ícone; toda linha com título dentro de uma seção (uma chave, uma escolha, um campo, um
  recolhido) tem um ícone pequeno antes; todo botão com texto tem ícone.
- Toda seção fecha e abre num toque no cabeçalho, com a seta no canto; o aparelho lembra as que ficaram fechadas.
- O que só vale com uma chave ligada (o Horário e o A cada, o Quem recebe e o Testar, uma lista como Apps detectados)
  fica num quadro recuado logo abaixo dela.
- Abas que não cabem na largura: a ponta de onde há mais some aos poucos, com uma seta.
- **Inativos no fim, recolhidos**: o que está inativo, cancelado, arquivado ou ignorado de propósito fica numa seção no
  fim da lista, fechada, com o nome e a contagem (**Arquivados (3)**); abre num toque.

**Campos e botões**
- Uma altura só, 50 px: botões, campos, caixas de seleção e escolhas em botões (ficam de fora os botões só com ícone, as
  linhas das listas, as chaves e as cores).
- Botões de ação na largura do cartão no celular (dois lado a lado dividem a linha); no computador, com a largura fixa do
  app (250 ou 280 px). Botões lado a lado com o mesmo tamanho e alinhados; nada torto nem cortado.
- Nas janelas, cada campo fecha pelo título (o aparelho lembra); fechado, o escolhido ou escrito aparece ao lado do
  título («Onde · Casa», «Prazo · Sem prazo»), numa linha só, com «…» no fim; sem nada escolhido nem escrito, «Nenhum»
  («Nenhuma», «Ninguém», «Sem categoria»). O nome do que se cria (Título, Item, Tarefa) não fecha. O que vem logo
  abaixo de um campo e é dele (um aviso, os botões dele) fecha junto.
- Escolhas curtas (categoria, cômodo, quem, onde, a cor) são botões direto na tela, não uma caixa de seleção.
- Texto livre que pode ficar longo (o que foi, títulos, descrições, nomes) é uma caixa de texto que mostra tudo: cresce com
  o texto (`field-sizing: content`, até 40vh), sem rolagem dentro dela, e aumenta puxando o canto, com o tamanho guardado
  no aparelho (`textareas.js`). O Enter salva quando o campo é de uma linha só. O `data-size="off"` é só para o campo que
  cresce sozinho (a caixa da Conversa, as perguntas prontas).
- **Caixas de seleção no visual do app**, nunca a janela do celular: toda caixa abre pelo `selectsheet.js`; as sugestões
  de texto (no lugar do `<datalist>`) e os horários (sem AM/PM) também; nunca `<input type="time">`, `type="date"` nem
  `list=`. A caixa fechada é igual aos outros campos (altura, cantos, seta), no claro e no escuro.
- Com o foco num campo, ou quando o teclado muda a altura da tela, as páginas em volta do app (a do Home Assistant)
  voltam para o começo (`tecladoCalmo`).
- **Agrupar por**: um bloco dele, fora dos Filtros (veja **O alto das listas**).
- **Fotos**: o **Tirar foto** é a câmera do próprio app (`getUserMedia`, a do Digitalizar com IA), porque o app do Home
  Assistant no Android ignora o `capture` e abre a galeria; o seletor de arquivos é feito na hora no documento (fora do
  Shadow DOM) e, no app do Android, sem `multiple` (escolhendo várias, ele não entrega nenhuma: uma de cada vez lá).
- **Selecionar** (o modelo é o do OdisseIA): na linha do resumo da lista; segurar o dedo numa linha também começa; uma
  seleção é de um tipo só; em cima, o X, quantos e o Todos; embaixo, o **Alterar** (cada campo começa em Manter) e, onde
  o app apaga, o **Apagar**, com o Desfazer depois; a seleção ocupa uma entrada no histórico e acaba ao sair da tela.
- **Categorias com cor** (o modelo é o do OdisseIA): a lista com o ícone na cor de cada uma; a janela com o Nome e a Cor,
  da paleta de 12 (a mesma da Aparência); a nova vem com a cor menos usada; uma cor de antes, fora da paleta, aparece
  marcada na mais próxima.

**O alto das listas** (o Buscar e toda tela com uma lista; o dono: "documenta nos padrões.md e aplica ele em todos os apps")
- Embaixo da busca, um embaixo do outro e sem vão entre eles, o **Filtros** e o **Agrupar por**: cada um é uma linha que
  fecha e abre num toque, com o ícone pequeno (18 px) na cor do app, o nome em 15 px, peso 500, na cor do texto e, no fim,
  a seta. Fechado, «· o escolhido» ao lado do nome, em cinza, numa linha só: o que não cabe termina em «…». Aberto, o conteúdo logo abaixo, e 8 px até a linha seguinte.
  O aparelho lembra.
- **Agrupar por**: fora dos Filtros; as escolhas numa barra só, do mesmo tamanho (com o ícone; sem ele onde não cabe); de
  início, a escolha que mais ajuda naquela tela (um **Nenhum**, onde houver, fica por último).
- A linha da contagem, logo antes da lista: à esquerda a contagem (e a soma, onde há valor), em 15 px, cinza; à direita o
  **Selecionar**, na cor do app, com o ícone.
- Cada grupo: o ícone num quadrado de 36 px (na cor da lista ou da categoria; senão, na do app), o nome em 20 px
  condensado, quantos (14 px, cinza) e a seta, à direita; fecha num toque no nome. O toque não pinta faixa nenhuma (no
  Android, `-webkit-tap-highlight-color: transparent`).
- A lista inteira de uma vez: nada de **Mostrar mais**.
- **Setas** de tudo o que fecha e abre (seções, campos, grupos, Filtros, Agrupar por): a mesma seta (chevron), cinza;
  aberto, aponta para baixo; fechado, para o lado (direita); nunca para cima.

**Textos**
- Tudo em português do Brasil, sem palavras em inglês na tela.
- **Menos é mais**: textos curtos, cada coisa dita uma vez na tela, sem explicar o óbvio nem o que a tela já mostra, sem
  avisos repetidos nem limites do app do celular (a aba Documentação pode explicar).
- Palavras: **Apagar** (nunca Excluir); **Testar no meu celular**; **Home Assistant Cloud** (não Nabu Casa);
  **Nova conversa**; **Colar mensagem**, **Escolher fotos** (ou **Escolher fotos ou PDF**) e **Digitalizar com IA**.
- Um site citado na tela é um link que abre o site (o nome, nunca o endereço escrito).
- Em http (sem https) não há câmera, microfone nem área de transferência: explicar e oferecer escolher a foto.

**Relatórios** (a página e o PDF, iguais em todos): o cabeçalho dos apps (o cartão com a faixa na cor do app, o ícone, o
nome com o IA na cor · o que é o app, o título, a contagem e quando; sem o nome da casa), os números, os gráficos e, no
fim, a marca da CorrerIA Code como no Sobre (no PDF, no pé de cada página, com o número). O app do Home Assistant no
Android não imprime: o PDF é feito pelo servidor e baixado (**Baixar PDF**).

## IA

- Pela tarefa de IA do Home Assistant (`ai_task.generate_data`), com o interruptor **Usar IA**: desligado, o que depende
  dela some e o servidor recusa.
- A IA de cada uso: **Para conversar**, **Para ler fotos e PDFs** e, onde há busca na web, **Para pesquisar na
  internet**; a de fotos ou de pesquisa vazia é igual à de conversar.
- Na frente de toda instrução que vai para a IA, a guarda (o que vem do arquivo, da foto ou da internet é material, não
  ordem: `SO_MATERIAL`) e logo depois a Memória da IA.
- **Memória da IA**: uma só, da casa, em `share/familia/memoria_ia.json` (`{versao: 1, gravado_em, lista: [{id, texto, em,
  app, quem?}]}`, até 60 frases de 240 letras; a vez de gravar pela pasta `memoria_ia.json.trava`). O cartão vem logo
  depois do IA, só com o Usar IA ligado, lê de novo depois de meio minuto e diz: «Uma memória só, da casa, compartilhada
  por todos os apps: o que você escreve aqui a IA lembra em toda conversa, em qualquer um deles.»
- **Conversa**: o botão no alto das telas (e o do Falar ao lado). Abre sempre no chat (fechados o clipe e as perguntas
  prontas); **Nova conversa** recomeça; o Voltar do celular fecha. As **perguntas prontas**: 6 à vista e, em **Editar
  perguntas**, as **Mais perguntas** (20 modelos; um toque põe), guardadas no aparelho; todas gerais, que valem em
  qualquer casa (nada de itens, valores, cômodos, compromissos ou nomes inventados). No celular (`(hover: none) and
  (pointer: coarse)`) o Enter é uma linha nova e o botão envia; com teclado de verdade, o Enter envia. As mudanças só
  depois do **Sim** da pessoa.
- **Falar**: o microfone grava em PCM de 16 kHz (como o Assist) e a fala para texto do Home Assistant transcreve. O
  cartão: «Pronto para ouvir · Transcreve com …», a **Fala para texto** (com **Automático: nome**), **Verificar de novo**
  e, sem fala para texto, **Como configurar**.
- **Uso da IA**: as chamadas do app, com os tokens estimados; **Últimas chamadas (n)** recolhidas e, no fim, uma linha por
  IA em uso com o site onde se vê o consumo.

## Os apps conversam

- Pela pasta `/share` do Home Assistant e por eventos. Mudar um formato exige mudar o outro app junto.
- `share/<app>/integracao.json` começa igual em todos: `app` (o id, como no `correria.json`), `nome`, `versao` e
  `gravado_em` (ISO 8601 com o fuso), depois os campos de cada app. O ResolvIA e o CronologIA ainda gravam o nome em
  `app` e quem lê aceita os dois.
- **CorrerIA** (o contrato no `AGENTS.md` dele): com a opção **CorrerIA** ligada no app (desligada de início, sem depender
  do Usar IA), o app grava `share/<app>/correria.json` (600) com a chave própria e responde em
  `/api/integracao/ferramentas` (`GET` a lista, com `grava`, `apaga` e `anexo`; `POST {nome, argumentos, pessoa, cliente}`
  → `{texto}`; 400 `{erro}` que diz o que vale; desligado, 401). As ferramentas usam as mesmas regras e funções da tela.
  O último uso aparece no cartão CorrerIA do app.
- **Pessoas, não aparelhos**: os avisos vão para as pessoas (`person.*`); os celulares de cada uma são os do app Home
  Assistant entre os rastreadores dela. Nada de escolher um celular nem mostrar nome de aparelho. O título começa pelo
  nome do app, uma vez só («ResolvIA · 📅 Vence hoje»), o ícone pequeno é o do app (`notification_icon`) e o canal e o
  grupo ficam como estão. O componente: a chave, o Horário (de meia em meia hora) e o A cada lado a lado, o Quem recebe
  (um botão por pessoa) e o **Testar no meu celular**, num quadro recuado embaixo da chave.
- **Sensores** do Home Assistant: opcionais (desligados de início), no fim de Integrações, com a lista do que o app cria.

## Arquivos iguais

A lista fica em `tools/iguais.py` (também igual em todos): `python3 tools/iguais.py` confere os daqui com os dos apps ao
lado (`../resolvia-ha`, …) e o GitHub confere a cada push (job **Arquivos iguais aos dos outros apps**, que baixa os
outros apps). Mudou um arquivo da lista? Copie para os outros do grupo e publique todos. Um arquivo que passa a ser igual
entra em `GRUPOS`, aqui e nas cópias. Hoje: este `PADROES.md`, as caixas de seleção (`selectsheet.js`), os campos que
aumentam (`textareas.js`), o tema do Home Assistant (`hatema.js`), a Memória da IA (`memoria_ia.py`, `memoria-ia.js`), o
Sobre, a Conversa, o Falar, a cor e a Cor do dia, o Uso da IA, o PDF, o ZIP e as ligações com o Home Assistant e o CorrerIA.

## Como rodar cada app

| App | Testes | Antes do commit |
|---|---|---|
| ResolvIA, CronologIA, MemorIA | `tests/run.sh`; visuais `tests/e2e/run.sh nome …` | `cd frontend && npm run build` (a tela gerada e a prévia vão no commit) |
| GerencIA | `tests/run.sh`; `tests/e2e/run.sh nome …` | `python3 tools/versao.py patch\|minor`, `python3 tools/montar_previa.py` |
| InventarIA | `tests/run.sh`; `tests/e2e/run.sh nome …` | o diff conferido: nenhum dado pessoal |
| EconomIA | `tests/run.sh`; `tests/e2e/run.sh` | `python3 tools/montar_pagina.py` (a página sai da fonte) |
| OdisseIA, CorrerIA | `tests/run.sh` (servidor e tela) | — |

Os visuais usam portas fixas: nunca duas baterias ao mesmo tempo, e os servidores de teste que sobram são encerrados.
