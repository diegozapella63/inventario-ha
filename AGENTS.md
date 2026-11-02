# Instruções para quem for mexer neste repositório (pessoas ou IAs)

InventarIA é um app (add-on) do Home Assistant para o inventário da casa: cômodos (com zonas), itens com fotos, valores e categorias, relatório para seguro, leitura de fotos por IA, fotos da internet e Falar. Faz parte de uma família de apps do mesmo dono, que conversam entre si pelo Home Assistant:

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
inventario/seed/              ponto de partida vazio (LEIA-ME)
docs/                         capturas de tela do README (de uma casa de exemplo)
```

Os dados ficam em `/data` (JSON e as fotos em JPG), backups em `/share/inventario` e versões automáticas a cada 10 minutos de uso.

## Rodar no computador

```
cd inventario/app
INV_DEV=1 INV_DATA=/tmp/i/data INV_SEED=../seed INV_WEB=./web INV_SHARE=/tmp/i/share INV_MEDIA=/tmp/i/media INV_AI_MOCK=1 python3 server.py
```

Abra `http://localhost:8099` (`INV_PORT` muda a porta; `INV_URL_INTERNA` é o endereço que os outros apps usam).

## Checklist de toda mudança

1. Implementar. Servidor: só biblioteca padrão do Python. Tela: `inventario/app/web/app.js`.
2. Testar no navegador (celular de 390 px e computador), no tema claro e no escuro. Se mexer nas rotas `/api/integracao/*`, rode os testes do GerencIA e do ResolvIA que usam o InventarIA (`tests/e2e/run.sh bens_e2e bens_graf cats_inv` no `gerencia-ha`; `npm test` no `resolvia-ha`).
3. Subir a versão nos dois lugares (iguais): `inventario/config.yaml` (`version:`) e `inventario/app/server.py` (`VERSION`). Correção = patch (1.18.0 → 1.18.1); novidade = minor (1.18.x → 1.19.0).
4. `inventario/CHANGELOG.md`: nova seção no topo, em português, do ponto de vista de quem usa.
5. `inventario/DOCS.md` quando muda o comportamento ou aparece algo novo.
6. Commit em `main` com mensagem em português ("InventarIA 1.19.0: ..."), `git pull --rebase` e push.

## Como os apps conversam

- Este app grava `share/inventario/integracao.json` (`url`, `ip_url`, `chave`) e responde, só para leitura e com `Authorization: Bearer <chave>`:
  - `GET /api/integracao/comodos` → `{versao, comodos: [{id, nome, codigo, itens}]}`
  - `GET /api/integracao/itens` → `{versao, itens: [{id, nome, comodo, zona, categoria, valor, valor_em}], categorias: {id: nome}}` (até 2000 itens)
- Quem lê: o **ResolvIA** (cômodos e equipamentos das tarefas) e o **GerencIA** (bens da casa, pelo `valor` e pela data `valor_em`, que muda quando o valor muda). Mudar esse formato exige mudar os outros apps junto.

## Como o dono gosta (interface)

- Tudo em português do Brasil, sem palavras em inglês na tela.
- **Menos é mais**: textos curtos, sem explicar o óbvio, sem avisos repetidos.
- Botões lado a lado com o mesmo tamanho e alinhados; nada torto nem cortado.
- O que depende da IA respeita a chave da IA (desligada, os botões somem).
- Em http (sem https) não há câmera nem microfone: explicar e oferecer escolher a foto.
- Celular primeiro (390 px); tema claro e escuro.
- Exemplos e capturas sempre de uma casa inventada: nunca itens, fotos ou valores reais do dono.

## Conversa com o dono

Respostas curtas, em português. Ao terminar uma mudança: o que mudou, a versão e se está publicado.
