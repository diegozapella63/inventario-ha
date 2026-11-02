# Testes do InventarIA

Três camadas, todas rodando a cada push no GitHub (aba Actions, workflow **Testes**):

| Camada | Onde | Como rodar | O que confere |
|---|---|---|---|
| Unitários | `tests/unit/test_*.py` | `tests/run.sh unit` | cada parte do servidor (`inventario/app/server.py`) importada direto, sem Home Assistant: valores, quantidades, códigos, itens e cômodos, categorias, backups e versões, importar e exportar, IA (prompts, respostas, uso, sensor), Falar, fotos da internet, integração com os outros apps |
| Integração | `tests/integration/test_*.py` | `tests/run.sh integration` | o servidor de verdade (processo próprio, portas livres) pelo HTTP: todas as rotas, segurança (Ingress, chave da integração), envios cortados e em partes, concorrência, e a conversa com um Home Assistant de mentira (`fake_ha.py`: estados, `ai_task`, `conversation`, fala para texto, WebSocket do Assist) e uma loja de mentira (`fixtures/site`) |
| Visuais | `tests/e2e/e2e_*.py` | `tests/e2e/run.sh` | as telas no Chromium (Playwright), como celular de 320 e 384 px, tablet e computador, claro e escuro: clica, digita, confere o que aparece e grava capturas de tela |

`tests/run.sh` roda as duas primeiras (só Python 3.12 ou mais novo, sem instalar nada; uns 40 segundos). Os visuais precisam de `pip install playwright && python -m playwright install chromium`; `E2E_JOBS=4 tests/e2e/run.sh` roda quatro de cada vez (uns 5 minutos). As capturas ficam em `$E2E_TMP/shots` e a saída de cada teste em `$E2E_TMP/logs`; no GitHub, no artefato **capturas-e-saidas** de cada execução.

## A casa de teste

`fixtures/casa/` é uma casa **inventada** (6 cômodos, 38 itens, 9 fotos ilustradas): é a casa de todos os testes, da prévia (`tools/build_preview.py`) e do `dev/run.sh`. Nunca use dados, fotos ou valores reais do dono aqui.

`fixtures/site/` é uma loja de mentira para a busca de fotos na internet: páginas com JSON-LD, `og:image`, `twitter:image`, redirecionamento, gzip, imagem pequena demais e página sem foto.

## Peças

- `helpers.py`: `AppServer` (sobe o `server.py` num diretório temporário, com ou sem a casa de teste, com a IA simulada ou um `FakeHA`), `FakeSite`, `search_answer()` e utilidades.
- `fake_ha.py`: o Home Assistant de mentira (API do Supervisor e WebSocket); guarda cada pedido para os testes conferirem.
- `unit/_boot.py`: importa o servidor uma vez, com pastas temporárias, e zera o estado entre os testes.
- `integration/_boot.py`: um servidor por classe de teste.
- `e2e/e2e_lib.py`: `Run` (conferências, capturas, app no ar, páginas como celular ou computador) e `main()`. Se um teste para no meio, grava `<nome>-parou-N.png` de cada página aberta.

## Os testes visuais

| Arquivo | O que cobre |
|---|---|
| `e2e_funcoes` | as contas puras da tela (valores, quantidades, Falar sem IA, dados da internet, categorias) |
| `e2e_inicio_busca` | Início em 4 tamanhos, busca sem acento, filtros, ordem, endereço da busca |
| `e2e_itens` | ficha, cadastro com foto, salvar e adicionar outro, editar, mover, duplicar, excluir e desfazer, conflito, rascunho, atalhos |
| `e2e_comodos` | lista, Organizar, novo, editar (nome, código, foto), excluir, zonas, barra lateral |
| `e2e_catalogar_falar` | Catalogar foto com IA de ponta a ponta; Falar com microfone de mentira, com e sem IA; microfone bloqueado |
| `e2e_camera` | câmera dentro do app no Android, várias fotos, Voltar, sem câmera, navegador do celular, computador |
| `e2e_internet` | Buscar na internet: fotos e dados do produto na ficha e no editor, Desfazer, sem fotos, sem busca, IA desligada |
| `e2e_mais` | abas, botões 280×44 alinhados, exportar CSV/JSON/ZIP, backup e restaurar, versões, importar |
| `e2e_ajustes` | Integrações com o Home Assistant de mentira (IA, Falar, uso, sensor, Usar IA), Aparência (tema e as 10 cores), Opções (zonas e categorias) |
| `e2e_relatorio` | totais, ordem, fotos, zonas, impressão e PDF |
| `e2e_navegacao` | abas, arrastar para o lado, Voltar, endereços que não existem, atualização vinda de outro aparelho |
| `e2e_boasvindas` | primeiro uso: começar do zero e importar backup |
| `e2e_telas` | todas as telas e janelas em todos os tamanhos e temas: nada passa da largura, janelas cabem, botões não se sobrepõem nem cortam |
| `e2e_previa` | a prévia montada por `tools/build_preview.py` |

## Ao mudar o app

- Mudou o comportamento: ajuste o teste que confere aquilo, ou crie um. Achou um erro: escreva o teste que pega o erro antes de corrigir.
- Tela nova ou janela nova: inclua em `e2e_telas.py`.
- Conferências em português, dizendo o que se espera ("Desfazer volta tudo"), para a saída ler como uma lista do que o app faz.
