# Instruções para quem for mexer neste repositório (pessoas ou IAs)

InventarIA é um app (add-on) do Home Assistant para o inventário da casa: cômodos (com zonas), itens com fotos, valores e categorias, relatório em PDF, leitura de fotos por IA, fotos da internet, novidades dos produtos, Conversar (chat com a IA) e Falar. Faz parte de uma família de apps do mesmo dono, que conversam entre si pelo Home Assistant:

| App | Repositório | O que é |
|---|---|---|
| InventarIA | `diegozapella63/inventario-ha` (este) | inventário da casa: cômodos e itens com valor |
| ResolvIA | `diegozapella63/resolvia-ha` | listas de tarefas; liga uma tarefa a um cômodo ou a um item daqui |
| CronologIA | `diegozapella63/cronologia-ha` | calendário, rotinas, remédios, placar (recebe cômodos e itens pelo ResolvIA) |
| GerencIA | `diegozapella63/gerencia-ha` | finanças; soma os itens daqui no patrimônio ("Bens da casa"), depreciados por categoria |

O Home Assistant instala direto do GitHub (`repository.yaml` + `inventario/config.yaml`), a partir da branch `main`: o que está em `main` é o que os usuários recebem.

## Estrutura

```
inventario/config.yaml        versão e opções do app
inventario/CHANGELOG.md       o que mudou em cada versão (o HA mostra ao atualizar)
inventario/DOCS.md            manual do usuário (aba Documentação no HA)
inventario/app/server.py      servidor HTTP (Python, só biblioteca padrão): dados, fotos, IA, backups, integração
inventario/app/web/           a tela: index.html, app.js (JavaScript puro, sem build), style.css, fontes
inventario/app/relatorio.py   o Relatório do inventário em PDF (Baixar PDF): os números, os gráficos e os cômodos
inventario/app/ferramentas.py as ferramentas do CorrerIA (WhatsApp, Claude e Gemini): a lista e as regras; grava pelo Store do server.py
inventario/app/pdf.py         PDF feito à mão (Helvetica, A4, fotos JPG): o mesmo arquivo do GerencIA; ao mudar, copie para lá
inventario/app/web/selectsheet.js  as caixas de seleção no visual do app: arquivo igual em todos os apps (no ResolvIA e
                              no CronologIA, frontend/src/selectsheet.js); ao mudar, copie para os outros
inventario/seed/              ponto de partida vazio (LEIA-ME); nunca coloque dados reais aqui
tests/                        testes unitários, de integração e visuais (veja tests/README.md)
tests/fixtures/casa/          a casa de teste, inventada: usada pelos testes, pela prévia e pelo dev/run.sh
dev/run.sh                    sobe o app no computador com a casa de teste e a IA simulada
preview/preview.js            o servidor imitado em memória da prévia (mesma tela, sem servidor)
tools/build_preview.py        monta a prévia numa página só (casa de teste, ou outra pasta)
tools/demo.py, shots_readme.py  casa de exemplo e as capturas do README (docs/)
tools/make_logo.py            desenha icon.png e logo.png
.github/workflows/testes.yml  roda os testes a cada push (aba Actions)
docs/                         capturas de tela do README (de uma casa de exemplo)
```

Os dados ficam em `/data` (JSON e as fotos em JPG), backups em `/share/inventario` e versões automáticas a cada 10 minutos de uso.

## Rodar no computador

```
dev/run.sh              # http://127.0.0.1:8099, casa de teste, IA simulada
dev/run.sh --vazio      # como numa instalação nova
dev/run.sh --limpar     # volta ao começo
```

À mão: `cd inventario/app` e `INV_DEV=1 INV_DATA=/tmp/i/data INV_SEED=../../tests/fixtures/casa INV_WEB=./web INV_SHARE=/tmp/i/share INV_MEDIA=/tmp/i/media INV_AI_MOCK=1 python3 server.py`. `INV_PORT` muda a porta; `INV_URL_INTERNA` é o endereço que os outros apps usam. Outras variáveis (para testes): `INV_HA_API`/`INV_HA_WS`/`SUPERVISOR_TOKEN` apontam para outro Home Assistant (o `tests/fake_ha.py`), `INV_MOCK_SEARCH` é um JSON com a resposta da busca na internet, `INV_WEB_ALLOW_LOCAL=1` deixa baixar fotos de 127.0.0.1, `INV_ALLOW` libera IPs fora do Ingress, `INV_HOJE` (AAAA-MM-DD) fixa o "hoje" das novidades (os testes usam 2026-11-04, para as datas de exemplo não envelhecerem), `INV_MOCK_NEWS` é um JSON com a resposta das novidades e `INV_NEWS_TICK` (segundos; 1800 de início) é de quanto em quanto tempo o servidor olha se está na hora de conferir as novidades sozinho.

## Testes

```
tests/run.sh                        # unitários e integração (só Python, ~40 s)
tests/e2e/run.sh                    # visuais (pip install playwright; python -m playwright install chromium)
E2E_JOBS=4 tests/e2e/run.sh e2e_itens e2e_telas   # só alguns, quatro de cada vez
E2E_JOBS=4 tools/cobertura.py       # tudo, com a cobertura do server.py e do app.js (e o que falta)
```

Tudo roda no GitHub a cada push (workflow **Testes**; as capturas ficam no artefato da execução). Detalhes e a lista do que cada teste cobre: `tests/README.md`. Mudou o comportamento, ajuste ou crie o teste; achou um erro, escreva o teste que o pega antes de corrigir; tela ou janela nova entra em `tests/e2e/e2e_telas.py` (confere 320 px a computador, claro e escuro).

## Checklist de toda mudança

1. `git pull --rebase` antes de começar: outras sessões (pessoas ou IAs) também publicam aqui.
2. Implementar. Servidor: só biblioteca padrão do Python (roda em `python:3.12-alpine`). Tela: `inventario/app/web/app.js`, sem build. A prévia usa a mesma tela: se a mudança depende do servidor, imite em `preview/preview.js`.
3. Testar: `tests/run.sh` e os visuais que tocam a parte mudada (ou todos). Olhar as capturas no celular de 390 px e no computador, no tema claro e no escuro. Se mexer nas rotas `/api/integracao/*`, rode os testes do GerencIA e do ResolvIA que usam o InventarIA (`tests/e2e/run.sh bens_e2e bens_graf cats_inv` no `gerencia-ha`; `npm test` no `resolvia-ha`).
4. Subir a versão num lugar só: `inventario/config.yaml` (`version:`). O `server.py` lê de lá (`VERSION`; na imagem, o Dockerfile copia o config.yaml para /app), e a prévia também. Correção = patch (1.18.0 → 1.18.1); novidade = minor (1.18.x → 1.19.0).
5. `inventario/CHANGELOG.md`: nova seção no topo, em português, do ponto de vista de quem usa.
6. `inventario/DOCS.md` quando muda o comportamento ou aparece algo novo; `README.md` quando muda a lista do que o app tem.
7. Antes de publicar, olhe o diff procurando dados pessoais (veja **Dados do dono**).
8. Commit em `main` com mensagem em português ("InventarIA 1.19.0: ..."), `git pull --rebase` e push. Confira na aba Actions que os testes passaram.

O `config.yaml` tem o `url` do repositório. O `panel_admin` fica no padrão do Home Assistant (o painel só para administradores): o inventário tem os valores da casa, backups, importar (que troca tudo) e Começar do zero; abrir para todos é decisão do dono.

## Dados do dono

Este repositório é público e tem **só código**. O inventário real (itens, valores, fotos, cômodos da casa do dono) nunca entra aqui: nem em testes, nem em exemplos, nem em capturas, nem em mensagens de commit. Exemplos e capturas usam a casa inventada (`tests/fixtures/casa`, `tools/demo.py`). Nunca guarde IMEI, número de série ou telefone em nenhum lugar. Valores que o dono informou para os itens dele são dele: nada (script, migração, IA) muda um valor que já está gravado sem ele pedir. Antes de cada push, `git diff --cached` e uma busca por nomes, valores e números que não sejam da casa de teste.

## Arquivos iguais em todos os apps

A lista dos arquivos que são iguais nos apps da família fica em `tools/iguais.py` (ele também é igual em todos):
`python3 tools/iguais.py` confere os daqui com os dos apps ao lado (`../resolvia-ha`, ...), e o GitHub confere a cada
push (job **Arquivos iguais aos dos outros apps**, que baixa os outros apps). Mudou um arquivo da lista? Copie para os
outros apps do grupo e publique todos. Um arquivo que passa a ser igual entra em `GRUPOS`, aqui e nas cópias.

`share/<app>/integracao.json` começa igual em todos os apps: `app` (o id, como no `correria.json`), `nome`, `versao` e
`gravado_em` (ISO 8601 com o fuso), depois os campos de cada app. O ResolvIA e o CronologIA ainda gravam o nome em
`app` (as versões de antes conferem por ele) e quem lê aceita os dois; o id entra numa próxima versão.

## Como os apps conversam

- Este app grava `share/inventario/integracao.json` (`url`, `ip_url`, `chave`) e responde, só para leitura e com `Authorization: Bearer <chave>`:
  - `GET /api/integracao/comodos` → `{versao, comodos: [{id, nome, codigo, itens, tipo?}]}` (`tipo: "bens"` na área Bens, sempre a última)
  - `GET /api/integracao/itens` → `{versao, itens: [{id, nome, comodo, zona, categoria, valor, valor_em}], categorias: {id: nome}}` (até 2000 itens)
- Quem lê: o **ResolvIA** (cômodos e equipamentos das tarefas) e o **GerencIA** (bens da casa, pelo `valor` e pela data `valor_em`, que muda quando o valor muda). Mudar esse formato exige mudar os outros apps junto.
- **CorrerIA → InventarIA** (o contrato é o mesmo para todos os apps da família; ver o AGENTS.md do CorrerIA): com **Mais > Configurações > Integrações > CorrerIA** ligado (`settings.correria`, desligado de início, sem depender do Usar IA), este app grava `share/inventario/correria.json` (`app: "inventario"`, `nome`, `assunto`, `url`, `ip_url`, `chave`, `versao`, `ferramentas`, `gravado_em`; 600, atômico; chave própria em `/data/correria.key`, separada da de `integracao.json`); desligado, o arquivo some e a rota responde 401 (`{"erro"}`; chave comparada em tempo constante). `GET /api/integracao/ferramentas` → `{versao, instrucoes, ferramentas: [{nome, titulo, descricao, entrada (JSON Schema), grava, apaga}]}`; `POST` `{nome, argumentos, pessoa, cliente}` → `{texto}` (400 `{erro}` dizendo o que vale; 404 ferramenta desconhecida). As ferramentas (`ferramentas.py`): `resumo`, `buscar_itens`, `ver_item` (pelo id ou pelo código, SAL-003), `cadastrar_itens`, `editar_item`, `mover_itens`, `apagar_item`, `novo_comodo`; gravam pelo `Store` (o número do item, `valueAt`, versões automáticas, `createdBy`/`updatedBy` = a pessoa), com `source: "correria"` (a ficha diz **Pelo CorrerIA**), e respeitam Usar zonas e Usar bens (`visible_data()`). Nada de fotos, backups ou configurações. O último uso (`{app: o cliente, em, nome}`) fica em `/data/correria_uso.json` e vai para a tela em `/api/data` e `/api/rev` (`correria_uso`). Testes: `tests/unit/test_u_ferramentas.py`, `tests/integration/test_correria.py` e `tests/e2e/e2e_correria.py`.

## Como o dono gosta (interface)

- Tudo em português do Brasil, sem palavras em inglês na tela.
- **Menos é mais**: textos curtos, sem explicar o óbvio, sem "porquês" desnecessários, sem avisos repetidos. Um texto que diz onde fica algo que já está à vista sai.
- Botões lado a lado com o mesmo tamanho e alinhados; nada torto nem cortado. Em Configurações (e nas telas de Mais), os botões e as seleções das linhas têm 280 × 44 e ficam alinhados pela direita.
- **Mais** é um menu (`#/mais`), não uma tela de ajustes: cada coisa que não cabe na barra de baixo tem a sua linha e a sua tela (Bens `#/bens`, Gráficos `#/graficos`, Novidades `#/novidades`, Categorias `#/categorias`, Relatório `#/relatorio`), **Configurações** (`#/config`, em abas: Integrações, Dados, Aparência, Opções) e, por último, **Sobre** (`#/sobre`: CorrerIA Code, os apps da família e o GitHub; a mesma página do `about.js` do CronologIA, só muda o app marcado). Nada de misturar uma função do app com as configurações.
- O que depende da IA respeita a chave **Usar IA** (Mais > Configurações > Integrações): desligada, os botões de IA somem, o servidor recusa as rotas de IA (409) e nada chama a IA; uma busca que começou com a IA ligada e terminou com ela desligada não entrega o resultado. O **Falar** some junto (o servidor recusa `/api/voice`); com a IA ligada mas sem uma IA no Home Assistant que responda, o app separa os itens sozinho (`splitSpoken` no app.js). As **Novidades** também têm a sua chave (Mais > Configurações > Opções).
- **Bens** (`#/bens`, primeira linha do Mais) é o que fica fora de casa (casa, terreno, carro): um "cômodo" do sistema com `kind: "bens"` (código BEN), criado com o primeiro bem (`POST /api/rooms {kind: "bens"}`, que também acrescenta Imóveis e Veículos numa lista de categorias editada), sempre depois dos cômodos. Na tela, `D.rooms` são só os cômodos, `D.bens`/`D.bensItems` a área, `D.items` os itens que contam; `D.total` (patrimônio) soma tudo e `D.houseTotal` só a casa (o relatório e a parte de cada cômodo). **Usar bens** (Opções, `settings.bens`, ligado de início) desligado esconde a área e os bens de tudo, da tela (`derive`) aos outros apps e à IA (`visible_data()` no server.py), sem apagar.
- Valores livres: o app não sugere "valor de mercado"; o valor é o que a pessoa quiser.
- Em http (sem https) não há câmera nem microfone: explicar e oferecer escolher a foto. No app do Home Assistant no Android, a câmera é a do próprio app (tela cheia); no navegador do celular, a do aparelho.
- Avisos vão para **pessoas** do Home Assistant, nunca para um aparelho escolhido aqui, como nos outros apps: os celulares de uma pessoa são os do app Home Assistant entre os rastreadores dela (`news_people`/`tracker_devices`/`tracker_phones` no server.py, a mesma regra do `avisos.py` do GerencIA e do `lib/phones.js` do ResolvIA e da CronologIA; o `avisos.py` não foi copiado igual porque tem partes só do GerencIA, os textos dos avisos e o `endereco_app` que só reconhece o `-gerencia`). O aviso das novidades é o componente da família (o modelo é o do GerencIA): **Conferir sozinho** (`news_every`: 0, 7, 15 ou 30), **Horário** (`news_hora`, de meia em meia hora, sem AM/PM) e **A cada** lado a lado, **Avisar no celular** (`news_aviso`), **Quem recebe** (`news_para`, uma lista de `person.*`, um botão por pessoa) e **Testar no meu celular** (`{who: "eu"}`) na largura toda, embaixo. O jeito antigo (`news_notify`: `todos` ou uma pessoa) ainda vale para quem não mudou nada.
- Avisos no celular (`notify.mobile_app_*`) abrem o app pelo link `/app/<app>/<caminho>`: o painel do Home Assistant (2026.2 ou mais novo) carrega a tela no começo e passa o caminho por mensagem (`home-assistant/subscribe-properties` e `home-assistant/properties`, no fim do app.js), e a tela vai para a rota. Hoje só `/novidades`.
- Celular primeiro (390 px; nada pode passar da largura nem em 320 px); tema claro e escuro; as 12 cores da família (veja **Padrão da família**).
- Quando o dono pede "igual ao ResolvIA" ou "como no CronologIA", abra o código do outro app (repositórios acima) e siga o mesmo jeito: textos, botões, câmera, Falar, uso da IA, menu Mais e abas de Configurações.
- Relatórios (a página e o PDF, iguais em todos os apps): o cabeçalho dos apps (cartão com a faixa na cor do app, o ícone, Inventar**IA** · o que é o app, o título, a contagem e quando; a hora só ali, sem o nome da casa), os números, os gráficos da tela Gráficos e, no fim, a marca da CorrerIA Code como no **Sobre** (o raio no quadrado inclinado na cor do app, Correr**IA** Code e DESENVOLVIMENTO DE SOFTWARES); no PDF, a marca e o número da página no pé de cada página. O app do Home Assistant no Android não imprime: o PDF é feito pelo servidor e baixado (**Baixar PDF**).
- **Inativos no fim, recolhidos**: o que está inativo, cancelado, encerrado, arquivado ou ignorado de propósito (por uma opção, como Nunca considerar) fica numa seção no fim da lista, recolhida por padrão, com o nome e a contagem (ex.: **Arquivados (3)**); abre num toque. Vale para todos os apps da família. Aqui: **Deixados de fora pela IA (N)** em Mais › Novidades (`<details class="news-out">` no fim da lista, no `renderNews`; aberto, fica aberto enquanto a tela está aberta).
- **Caixas de seleção no visual do app**: nenhuma janela nativa do celular. Toda caixa de seleção abre pelo selectsheet.js; sugestões de texto (no lugar do `<datalist>`) e horários (sem AM/PM) também no visual do app; a caixa fechada igual aos outros campos (altura, cantos, seta), no claro e no escuro. Aqui: `data-sug="<id do datalist>"` no campo (a lista `.sug-box` logo abaixo dele, como no GerencIA), nunca `list=`; a caixa fechada é `.select` (44 px, os cantos do `.input`, a seta `--sel-arrow` na cor do `--muted` de cada tema).
- Exemplos e capturas sempre de uma casa inventada: nunca itens, fotos ou valores reais do dono.

**Padrão da família (igual em todos os apps)**
- Barra de baixo: o botão do meio é **Adicionar** (no EconomIA, a ação principal dele); **Buscar**, quando houver, é a 2ª aba; **Mais** é a última, com o ícone de três pontos.
- **Mais** é um menu: as funções do app, depois **Configurações** e por último **Sobre**. Os relatórios se chamam **Relatório de/do …**.
- **Configurações** em 4 abas, nesta ordem: **Integrações › Dados › Aparência › Opções**; abre em Integrações. Nenhuma função do app vira aba.
- **Integrações**, nesta ordem: os outros apps da família › CorrerIA › **IA do Home Assistant** (o Usar IA) › Falar › Uso da IA › Sensores.
- IA: as entradas se chamam **Colar mensagem**, **Escolher fotos** (ou **Escolher fotos ou PDF**, onde PDF vale) e **Digitalizar com IA**; a conversa recomeça em **Nova conversa**; o Voltar do celular fecha a Conversa.
- Palavras: **Apagar** (nunca Excluir); **Testar no meu celular**; **Home Assistant Cloud** (não Nabu Casa); recolhidos como **Nome (n)**; o CHANGELOG começa com "# Mudanças".
- **Dados**: Exportar › Backup na pasta share › Importar › Versões anteriores › Onde ficam os dados › Começar do zero.
- **Aparência**: o tema vale no aparelho (começa em Automático); a cor do app vale para a casa toda; uma paleta só, de 12 cores (Vermelho, Coral, Laranja, Ouro, Verde, Menta, Turquesa, Azul, Índigo, Lilás, Rosa, Grafite); a Cor do dia é a mesma em todos os apps (as 11 sem o Grafite, pelo número do dia).

Aqui: Configurações em `ALL_TABS` (o `#/config` é Integrações; os Dados em `#/config/dados`); a cor do app em `settings.accent` e `settings.accent_daily` no servidor (`ACCENTS` no app.js e no server.py; o aparelho guarda só a cópia que o index.html pinta antes de carregar; uma cor de antes da paleta vira a mais próxima, `nearestAccent`); **Começar do zero** é `POST /api/erase {confirm: true}` (uma versão antes, "antes de apagar tudo"; as categorias, as opções e as fotos no disco ficam); o Testar no meu celular manda `{who: "eu"}` (a pessoa cujo `user_id` é o `X-Remote-User-Id` do Ingress). O InventarIA não tem Colar mensagem nem integração a ligar com os outros apps (a do ResolvIA e do GerencIA é automática).

## Conversa com o dono

Respostas curtas, em português. Ao terminar uma mudança: o que mudou, a versão e se está publicado, e o caminho para atualizar no Home Assistant: **Configurações > Aplicativos > Loja de aplicativos > ⋮ > Verificar atualizações > InventarIA > Atualizar**.
