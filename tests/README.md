# Testes do InventarIA

Três camadas, todas rodando a cada push no GitHub (aba Actions, workflow **Testes**):

| Camada | Onde | Como rodar | O que confere |
|---|---|---|---|
| Unitários | `tests/unit/test_*.py` | `tests/run.sh unit` | cada parte do servidor (`inventario/app/server.py`) importada direto, sem Home Assistant: valores, quantidades, códigos, itens e cômodos, categorias, armazenamento, fotos, backups e versões, importar e exportar, IA (prompts, respostas, uso, sensor, configurações; o cômodo que a IA escolhe em `test_u_ia_comodo.py`), Falar, fotos da internet, novidades, Conversar, integração com os outros apps, as ferramentas do CorrerIA (`test_u_ferramentas.py`: cada leitura e gravação, os erros, zonas e bens, a chave e o arquivo próprios) |
| Integração | `tests/integration/test_*.py` | `tests/run.sh integration` | o servidor de verdade (processo próprio, portas livres) pelo HTTP: todas as rotas, segurança (Ingress, chave da integração, chave do CorrerIA e `/api/integracao/ferramentas` em `test_correria.py`), envios cortados e em partes, concorrência, e a conversa com um Home Assistant de mentira (`fake_ha.py`: estados, `ai_task`, `conversation`, fala para texto, avisos no celular, WebSocket do Assist) e uma loja de mentira (`fixtures/site`) |
| Visuais | `tests/e2e/e2e_*.py` | `tests/e2e/run.sh` | as telas no Chromium (Playwright), como celular de 320 e 384 px, tablet e computador, claro e escuro: clica, digita, confere o que aparece e grava capturas de tela |

`tests/run.sh` roda as duas primeiras (só Python 3.12 ou mais novo, sem instalar nada; uns 2 minutos). Os visuais precisam de `pip install playwright && python -m playwright install chromium`; `E2E_JOBS=4 tests/e2e/run.sh` roda quatro de cada vez (uns 10 minutos). As capturas ficam em `$E2E_TMP/shots` e a saída de cada teste em `$E2E_TMP/logs`; no GitHub, no artefato **capturas-e-saidas** de cada execução.

## Cobertura

`tools/cobertura.py` roda as três camadas e mostra quanto do `server.py` (por camada e no total) e do `app.js` (pelos visuais) os testes executam; `--sem-visuais` pula os visuais. Só biblioteca padrão: o servidor é medido com `sys.monitoring` (`cobertura/sitecustomize.py`, Python 3.12+) e a tela com a contagem do próprio Chromium (`E2E_COV` em `e2e/e2e_lib.py`). As linhas que nenhum teste roda ficam em `faltam-server.txt` e `faltam-app.txt`, na pasta que ele mostra no fim.

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
| `e2e_funcoes` | as contas puras da tela (valores, quantidades, Falar sem IA, dados da internet, categorias, datas das novidades, a Cor do dia) |
| `e2e_inicio_busca` | Início em 4 tamanhos, busca sem acento, filtros, ordem, endereço da busca |
| `e2e_busca` | zonas na busca, mais resultados, limpar, Voltar, ordem por relevância, filtros pelo endereço |
| `e2e_itens` | ficha, cadastro com foto, salvar e adicionar outro, editar, mover, duplicar, excluir e desfazer, conflito, rascunho, atalhos |
| `e2e_editor` | cada campo do cadastro: avisos, quantidades, valores, valor por unidade, detalhes longos, categoria nova, Cancelar |
| `e2e_fotos_item` | várias fotos, limite de 12, capa, tirar, colar, arrastar, arquivo que não é imagem, fotos do cômodo no cadastro |
| `e2e_ficha` | galeria, foto grande e setas, link do cômodo, foto da internet com o site, sem foto, celular e computador |
| `e2e_comodos` | lista, Organizar, novo, editar (nome, código, foto), excluir, zonas, barra lateral |
| `e2e_fotos_comodo` | fotos do cômodo: adicionar, legenda, capa, subir, tirar; os itens de cada foto no visualizador |
| `e2e_organizar` | setas nas pontas, ordem gravada, Início, barra lateral, relatório e outro aparelho |
| `e2e_zonas` | zonas ligadas do começo ao fim: sugestões, a última zona do cômodo, subtotais, relatório, desligar |
| `e2e_desfazer` | Desfazer em excluir, mover, foto e dados da internet; avisos empilhados e com janela aberta |
| `e2e_catalogar_falar` | Catalogar itens com IA de ponta a ponta (sem cômodo, a IA escolhe o da foto); Falar com microfone de mentira (cada item no seu cômodo; sem cômodo, nada é gravado); Adicionar nos cômodos sem Adicionar bem; IA desligada: sem Falar e Adicionar direto no item; microfone bloqueado |
| `e2e_preencher_ia` | Preencher com IA no cadastro: o que preenche, o que fica, sem foto, IA desligada |
| `e2e_ia_falhas` | a IA falhando (cota, fora do formato, erro, nada) no Catalogar, no Preencher e na busca; Home Assistant fora do ar |
| `e2e_falar_ha` | Falar com o Home Assistant de mentira: fala para texto escolhida, erros, áudio curto, idioma; sem uma IA que responda, o app separa (e o Adicionar e o painel Falar dizem isso); IA desligada, o Falar some e o servidor recusa |
| `e2e_camera` | câmera dentro do app no Android, várias fotos, Voltar, sem câmera, navegador do celular, computador |
| `e2e_internet` | Buscar na internet: fotos e dados do produto na ficha e no editor, Desfazer, sem fotos, sem busca, IA desligada |
| `e2e_novidades` | Novidades na própria ficha: só as 3 mais recentes, tipos, datas, fontes, boato, guardadas ao abrir de novo, Buscar de novo, fechar no meio, erro, IA desligada |
| `e2e_novidades_todos` | Novidades (no menu Mais): o mesmo equipamento em vários cômodos numa linha só, só Eletrônicos, sem escolher categorias, item de outra categoria fora da lista, conferir todos com a IA escolhendo, andamento, Parar, deixados de fora, Limpar com confirmação, aba some sem IA |
| `e2e_novidades_ajustes` | Opções > Novidades: Usar novidades, Conferir sozinho, Avisar (uma pessoa da casa ou Todos, pelos celulares ligados a ela) e Testar o aviso, os dois só com Conferir sozinho ligado, seleções 280×44 alinhadas; desligadas, somem do menu e da ficha; IA desligada, o painel some; o link do aviso abre o app em Novidades (mensagem do painel do Home Assistant) |
| `e2e_bens` | Mais > Bens: vazio, o primeiro bem cria a área (BEN, no fim), cadastro de um bem só com o Tipo (sem Cômodo nem Categoria), o filtro Tipo da busca, o gráfico só dos bens (os da casa sem eles), Adicionar bem no menu do +, Usar bens desligado (somem de tudo, sem apagar) e ligado de novo, Imóveis/Veículos/Outros com totais, patrimônio do Início, fora de Cômodos, ficha, busca, Mover e Desfazer, relatório à parte, gráficos, 320 px e computador |
| `e2e_conversar` | Conversar: botão ao lado do microfone, ideias, Enter, resposta formatada, da ficha, erro, ditar, computador, IA desligada |
| `e2e_graficos` | Mais > Gráficos: números do alto, cômodos e categorias do maior para o menor, faixas de valor, itens mais valiosos, mês a mês (tocar mostra o valor), cada linha abre a sua tela, 320 px e computador |
| `e2e_mais` | o menu Mais (Bens, Gráficos, Novidades, Categorias, Relatório, Configurações, Sobre), Voltar, endereços antigos; Configurações: abas, botões 280×44 alinhados, exportar CSV/JSON/ZIP, backup e restaurar, versões, importar |
| `e2e_sobre` | Mais > Sobre, a última linha do menu: CorrerIA Code, por que CorrerIA, os seis apps (cada um para o seu GitHub, com o IA em destaque e uma linha; o InventarIA com "Este app" e a versão), Meu GitHub, os 7 links abrindo fora, Voltar e ‹ Mais de volta ao menu, 320 e 390 px e computador, claro e escuro |
| `e2e_selecao` | as caixas de seleção (`web/selectsheet.js`, igual nos outros apps): tocar abre a janela do app (não a do celular), título, opções, a atual marcada, cores do app no claro e no escuro; escolher filtra a busca e grava a IA; Voltar, X e tocar fora fecham só ela; numa tela de Configurações, o Voltar seguinte é o do app; no computador, no meio e pelo teclado |
| `e2e_backups` | lista de backups, restaurar um antigo, pasta share indisponível |
| `e2e_versoes` | versões anteriores: nenhuma, várias, os motivos, restaurar cada uma |
| `e2e_importar_partes` | backup em partes, só fotos, cancelar no meio, progresso |
| `e2e_correria` | Integrações > CorrerIA em 390 px e no computador, claro e escuro: desligado de início, sem depender do Usar IA, ligar grava `share/inventario/correria.json` e desligar apaga (e a rota responde 401), a chave alinhada com as outras, a linha do último uso ("Claude usou hoje às 9:41") que muda sozinha, e um item cadastrado pelo CorrerIA que aparece na busca sem recarregar, com a origem Pelo CorrerIA e quem cadastrou |
| `e2e_ajustes` | Integrações com o Home Assistant de mentira (IA, Falar, uso, sensor, Usar IA), Aparência (tema, as 10 cores e a Cor do dia: ligada de início, a cor de cada dia, a virada da meia-noite, escolher uma cor desliga), Opções (zonas), Categorias (tela própria) |
| `e2e_uso_ia` | painel Uso da IA: dias, barras, tipos, últimas chamadas, links do provedor |
| `e2e_relatorio` | o padrão dos relatórios dos apps: o cabeçalho (o app, o título, a contagem e quando), os números, os gráficos da tela Gráficos (as partes somam 100%), os cômodos na ordem da casa, as fotos liga/desliga (e o menu Mais só diz "com fotos" com elas ligadas), Baixar PDF (o arquivo do servidor, com as fotos ou sem, na cor do app; não abre a impressão), Mostrar fotos e Baixar PDF do mesmo tamanho, a marca da CorrerIA Code no fim, zonas e a impressão do navegador |
| `e2e_navegacao` | abas, arrastar para o lado, Voltar, endereços que não existem, atualização vinda de outro aparelho |
| `e2e_teclado` | N, /, Esc, Ctrl+Enter, setas, Tab preso na janela, foco de volta, Enter nos formulários |
| `e2e_acessibilidade` | nomes dos botões de ícone, aria-current, janelas com nome, imagens com alt, abas e chaves |
| `e2e_erros` | servidor fora do ar ao abrir, erro ao gravar sem perder o digitado, resposta lenta |
| `e2e_boasvindas` | primeiro uso: começar do zero e importar backup |
| `e2e_tablet` | todas as telas no tablet, retrato e paisagem |
| `e2e_computador` | layout do computador em 1280 e 1920: barra lateral, botões do alto, janelas |
| `e2e_telas` | todas as telas e janelas em todos os tamanhos e temas: nada passa da largura, janelas cabem, botões não se sobrepõem nem cortam |
| `e2e_previa` | a prévia montada por `tools/build_preview.py` |

## Ao mudar o app

- Mudou o comportamento: ajuste o teste que confere aquilo, ou crie um. Achou um erro: escreva o teste que pega o erro antes de corrigir.
- Tela nova ou janela nova: inclua em `e2e_telas.py`.
- Conferências em português, dizendo o que se espera ("Desfazer volta tudo"), para a saída ler como uma lista do que o app faz.
