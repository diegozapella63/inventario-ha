# Instruções para quem for mexer neste repositório (pessoas ou IAs)

InventarIA é um app (add-on) do Home Assistant para o inventário da casa: cômodos (com zonas), itens com fotos, valores e categorias, relatório para seguro, leitura de fotos por IA, fotos da internet, novidades dos produtos, Conversar (chat com a IA) e Falar. Faz parte de uma família de apps do mesmo dono, que conversam entre si pelo Home Assistant:

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

À mão: `cd inventario/app` e `INV_DEV=1 INV_DATA=/tmp/i/data INV_SEED=../../tests/fixtures/casa INV_WEB=./web INV_SHARE=/tmp/i/share INV_MEDIA=/tmp/i/media INV_AI_MOCK=1 python3 server.py`. `INV_PORT` muda a porta; `INV_URL_INTERNA` é o endereço que os outros apps usam. Outras variáveis (para testes): `INV_HA_API`/`INV_HA_WS`/`SUPERVISOR_TOKEN` apontam para outro Home Assistant (o `tests/fake_ha.py`), `INV_MOCK_SEARCH` é um JSON com a resposta da busca na internet, `INV_WEB_ALLOW_LOCAL=1` deixa baixar fotos de 127.0.0.1, `INV_ALLOW` libera IPs fora do Ingress.

## Testes

```
tests/run.sh                        # unitários e integração (só Python, ~40 s)
tests/e2e/run.sh                    # visuais (pip install playwright; python -m playwright install chromium)
E2E_JOBS=4 tests/e2e/run.sh e2e_itens e2e_telas   # só alguns, quatro de cada vez
```

Tudo roda no GitHub a cada push (workflow **Testes**; as capturas ficam no artefato da execução). Detalhes e a lista do que cada teste cobre: `tests/README.md`. Mudou o comportamento, ajuste ou crie o teste; achou um erro, escreva o teste que o pega antes de corrigir; tela ou janela nova entra em `tests/e2e/e2e_telas.py` (confere 320 px a computador, claro e escuro).

## Checklist de toda mudança

1. `git pull --rebase` antes de começar: outras sessões (pessoas ou IAs) também publicam aqui.
2. Implementar. Servidor: só biblioteca padrão do Python (roda em `python:3.12-alpine`). Tela: `inventario/app/web/app.js`, sem build. A prévia usa a mesma tela: se a mudança depende do servidor, imite em `preview/preview.js`.
3. Testar: `tests/run.sh` e os visuais que tocam a parte mudada (ou todos). Olhar as capturas no celular de 390 px e no computador, no tema claro e no escuro. Se mexer nas rotas `/api/integracao/*`, rode os testes do GerencIA e do ResolvIA que usam o InventarIA (`tests/e2e/run.sh bens_e2e bens_graf cats_inv` no `gerencia-ha`; `npm test` no `resolvia-ha`).
4. Subir a versão nos dois lugares (iguais): `inventario/config.yaml` (`version:`) e `inventario/app/server.py` (`VERSION`). Correção = patch (1.18.0 → 1.18.1); novidade = minor (1.18.x → 1.19.0).
5. `inventario/CHANGELOG.md`: nova seção no topo, em português, do ponto de vista de quem usa.
6. `inventario/DOCS.md` quando muda o comportamento ou aparece algo novo; `README.md` quando muda a lista do que o app tem.
7. Antes de publicar, olhe o diff procurando dados pessoais (veja **Dados do dono**).
8. Commit em `main` com mensagem em português ("InventarIA 1.19.0: ..."), `git pull --rebase` e push. Confira na aba Actions que os testes passaram.

## Dados do dono

Este repositório é público e tem **só código**. O inventário real (itens, valores, fotos, cômodos da casa do dono) nunca entra aqui: nem em testes, nem em exemplos, nem em capturas, nem em mensagens de commit. Exemplos e capturas usam a casa inventada (`tests/fixtures/casa`, `tools/demo.py`). Nunca guarde IMEI, número de série ou telefone em nenhum lugar. Valores que o dono informou para os itens dele são dele: nada (script, migração, IA) muda um valor que já está gravado sem ele pedir. Antes de cada push, `git diff --cached` e uma busca por nomes, valores e números que não sejam da casa de teste.

## Como os apps conversam

- Este app grava `share/inventario/integracao.json` (`url`, `ip_url`, `chave`) e responde, só para leitura e com `Authorization: Bearer <chave>`:
  - `GET /api/integracao/comodos` → `{versao, comodos: [{id, nome, codigo, itens}]}`
  - `GET /api/integracao/itens` → `{versao, itens: [{id, nome, comodo, zona, categoria, valor, valor_em}], categorias: {id: nome}}` (até 2000 itens)
- Quem lê: o **ResolvIA** (cômodos e equipamentos das tarefas) e o **GerencIA** (bens da casa, pelo `valor` e pela data `valor_em`, que muda quando o valor muda). Mudar esse formato exige mudar os outros apps junto.

## Como o dono gosta (interface)

- Tudo em português do Brasil, sem palavras em inglês na tela.
- **Menos é mais**: textos curtos, sem explicar o óbvio, sem "porquês" desnecessários, sem avisos repetidos. Um texto que diz onde fica algo que já está à vista sai.
- Botões lado a lado com o mesmo tamanho e alinhados; nada torto nem cortado. Em Mais, os botões e as seleções das linhas têm 280 × 44 e ficam alinhados pela direita.
- O que depende da IA respeita a chave **Usar IA** (Mais > Integrações): desligada, os botões de IA somem, o servidor recusa as rotas de IA (409) e nada chama a IA; uma busca que começou com a IA ligada e terminou com ela desligada não entrega o resultado. O **Falar** continua sem IA: o Home Assistant transcreve e o app separa os itens (`splitSpoken` no app.js).
- Valores livres: o app não sugere "valor de mercado"; o valor é o que a pessoa quiser.
- Em http (sem https) não há câmera nem microfone: explicar e oferecer escolher a foto. No app do Home Assistant no Android, a câmera é a do próprio app (tela cheia); no navegador do celular, a do aparelho.
- Celular primeiro (390 px; nada pode passar da largura nem em 320 px); tema claro e escuro; as 10 cores do app.
- Quando o dono pede "igual ao ResolvIA" ou "como no CronologIA", abra o código do outro app (repositórios acima) e siga o mesmo jeito: textos, botões, câmera, Falar, uso da IA, abas de Mais.
- Exemplos e capturas sempre de uma casa inventada: nunca itens, fotos ou valores reais do dono.

## Conversa com o dono

Respostas curtas, em português. Ao terminar uma mudança: o que mudou, a versão e se está publicado, e o caminho para atualizar no Home Assistant: **Configurações > Aplicativos > Loja de aplicativos > ⋮ > Verificar atualizações > InventarIA > Atualizar**.
