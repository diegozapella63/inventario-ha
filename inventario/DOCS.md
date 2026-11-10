# InventarIA

O InventarIA é o inventário da casa dentro do Home Assistant: cômodos, itens com fotos e valores, busca, gráficos, relatório em PDF e, se você quiser, leitura de fotos por IA e zonas dentro dos cômodos.

O app abre pela barra lateral (Ingress). Quem já está logado no Home Assistant usa direto, sem outra senha.

## Primeiro uso

Na primeira vez, o app abre vazio e oferece duas opções:

- **Importar backup**: escolha o arquivo `.zip` de um backup do app (com itens, fotos e valores). Funciona pelo celular: o arquivo é enviado em partes, com barra de progresso. Deixe a tela aberta até terminar.
- **Criar o primeiro cômodo**: comece pelo primeiro cômodo e vá cadastrando os itens.

Depois disso, tudo o que você muda fica salvo no app. Atualizar ou reiniciar o app não apaga nada.

## Como usar

- **Início**: a etiqueta do patrimônio, a busca logo abaixo, os destaques (mais valioso, maior cômodo, último cadastro e fotos), os cômodos (com a parte de cada um no total) e os cadastrados recentemente. As categorias e os itens mais valiosos ficam em **Mais > Gráficos**.
- **Cômodos** (aba ao lado de Adicionar): todos os cômodos com foto, número de itens e valor. Toque num cômodo para abrir. Em **Organizar**, as setas mudam a ordem (que vale para o app todo e para o relatório) e o lápis edita nome, código e fotos.
- **Cômodo**: fotos do cômodo e a lista dos itens, na ordem dos códigos (com mais de 6 itens, aparece **Filtrar neste cômodo**). Com as zonas ligadas, os itens aparecem separados por zona, com o subtotal de cada uma. Toque numa foto para ver os itens que estão nela, mudar a legenda, usar como capa, adicionar um item com ela, catalogar com IA ou tirá-la do cômodo.
- **Adicionar item**: nome, detalhes, cômodo, categoria, quantidade e valor total (e a zona, se estiver ligada). Dá para tirar foto pelo celular, **Escolher fotos** da galeria, usar uma das **Fotos do cômodo**, arrastar uma foto ou colar com Ctrl+V; a primeira é a capa. No app do Home Assistant para Android, **Tirar foto** abre a câmera do próprio InventarIA, como no ResolvIA (na primeira vez, o celular pede permissão). Com uma foto, **Digitalizar com IA** lê a primeira e preenche nome, detalhes, categoria e valor, com **Desfazer** no aviso; o que você já escreveu nos detalhes, na quantidade e no valor fica, e dá para dar uma dica à IA ("é uma cafeteira Oster"). **Observação** guarda um lembrete sobre o item. "Salvar e adicionar outro" mantém o cômodo para cadastrar em sequência.
- **Ficha do item**: toque num item para ver as fotos (toque para ampliar), o valor (e o de cada unidade), os detalhes, o cômodo, a categoria, a origem, quem cadastrou e quando, e as novidades. Embaixo ficam **Editar**, **Duplicar**, **Mover** (para outro cômodo ou zona; em outro cômodo, o item ganha um código novo) e **Apagar**. Mover e Apagar têm **Desfazer** no aviso.
- **Catalogar itens com IA**: tire uma foto de uma prateleira ou de um canto da casa (ou use uma foto do cômodo); a IA lista os objetos com nome, categoria, quantidade e uma sugestão de valor. Você confere, ajusta e escolhe o que entra. O que parece já cadastrado e o que a IA não tem certeza vêm marcados. Dentro de um cômodo, os itens vão para ele; fora, o **Cômodo** vem em **A IA escolhe**: ela conhece os cômodos da casa e reconhece o da foto. Se não souber, você escolhe na hora de conferir.
- **Falar**: o microfone no alto da tela. Fale os itens e quanto valem, e o app separa cada um para você conferir. Veja [Falar](#falar).
- **Novidades**: na ficha de um eletrônico, a IA procura na web atualizações, lançamentos, modelo novo, recalls e fim de suporte do produto; em **Mais > Novidades**, de todos os eletrônicos de uma vez. Veja [Novidades do produto](#novidades-do-produto).
- **Conversar**: o balão ao lado do microfone abre uma conversa com a IA, a qualquer momento, sobre o que está na tela ou qualquer outro assunto. Veja [Conversar](#conversar).
- **Buscar na internet**: num item sem foto (ou no editor do item), a IA procura o produto no fabricante e nas lojas e o app mostra as fotos encontradas para você escolher. Na mesma busca, a IA traz nome, detalhes, categoria e valor do produto para preencher o item. Veja [Fotos da internet](#fotos-da-internet).
- **Buscar**: por nome, marca ou detalhe, sem se preocupar com acentos. Filtre por cômodo e categoria e ordene por valor, nome, data ou código. Com bens cadastrados, o filtro **Tipo** vem antes: Itens da casa, Imóveis, Veículos ou Outros bens (num tipo de bem, os filtros de cômodo e categoria saem).
  - **Selecionar**, ao lado de quantos itens a busca achou (ou segure o dedo num item, que já vem marcado), muda vários itens de uma vez, como no ResolvIA: toque nos itens (ou em **Todos**, que vale para a lista inteira) e, embaixo, em **Alterar**. A janela tem **Cômodo**, **Categoria** e **Zona** (com as zonas ligadas), cada um começando em **Manter**: mude um ou mais e toque em **Aplicar**. Em outro cômodo, cada item ganha um código novo e fica sem zona, se não escolher uma. O aviso tem **Desfazer**. Os bens ficam de fora. O Voltar do celular ou o **X** saem do Selecionar.
- **Mais** é um menu: **Bens**, **Gráficos**, **Novidades** (com a IA ligada), **Categorias**, **Relatório do inventário**, **Configurações** e **Sobre**. Cada um abre a sua tela, com **‹ Mais** no alto para voltar.
- **Bens** (Mais > Bens) guarda o que tem valor e fica fora de casa: casa, apartamento, terreno, carro, moto.
  - **Adicionar bem** (na tela Bens ou no **+ Adicionar** de baixo, fora dos cômodos) abre o cadastro sem **Cômodo** e sem **Categoria**: só o **Tipo** (Imóvel, Veículo ou Outro). O código dos bens é BEN (BEN-001, BEN-002…).
  - A lista separa **Imóveis**, **Veículos** e **Outros**, cada um com o total. As categorias Imóveis e Veículos entram na lista de categorias com o primeiro bem.
  - Um item da casa também pode ir para Bens pelo **Mover**, e um bem pode voltar para um cômodo do mesmo jeito.
  - Os bens contam no patrimônio do Início (a etiqueta diz quantos), na busca (filtro **Tipo**) e na conversa com a IA, mas ficam fora da lista de cômodos. Em **Gráficos**, têm um gráfico só deles; os da casa (cômodos, categorias, faixas e mais valiosos) ficam sem eles.
  - Na lista de Bens, o **+ Adicionar** de baixo adiciona um bem.
  - No relatório, vêm numa seção à parte, no fim, com o total deles; o total da casa não muda.
- **Gráficos** (Mais > Gráficos): o patrimônio, quantos itens, o valor médio e quantos têm foto; os cômodos e as categorias que mais valem, do maior para o menor, com o valor e a parte do total; quantos itens há em cada faixa de valor; os 10 itens mais valiosos; e, quando há itens de mais de um mês, o patrimônio mês a mês pela data de cadastro (toque no gráfico para ver o valor de cada mês, ou **Ver mês a mês** para a tabela). Tocar numa linha abre o cômodo, a busca da categoria ou a ficha do item.
- **Categorias** (Mais > Categorias): renomeie, crie ou apague categorias; cada uma mostra quantos itens tem. Os itens de uma categoria apagada vão para Outros, que não pode ser apagada. **Eletrônicos** é a categoria das novidades: fica sempre, com esse nome. As categorias ficam no inventário: entram no backup, na exportação e nas versões, valem para todos os aparelhos, e a IA passa a usar as novas.
- **Relatório do inventário** (Mais > Relatório do inventário; no computador, também na barra lateral): no alto, o app, o título, quantos itens e cômodos e quando; o patrimônio, os gráficos da tela Gráficos (cômodos, categorias, faixas de valor, os mais valiosos e os bens) e os itens de cada cômodo, com código, foto, quantidade e valor; no fim, a marca da CorrerIA Code. **Baixar PDF** baixa o mesmo relatório como arquivo, na cor do app (o celular abre, e de lá dá para imprimir ou mandar para a seguradora). **Mostrar fotos** desmarcado deixa o relatório, e o PDF, só com o texto.
- **Configurações** (Mais > Configurações), em abas na ordem dos outros apps, abrindo em **Integrações**: **Integrações** (o [CorrerIA](#correria), ligar ou desligar a IA e escolher qual IA do Home Assistant usar, Falar, Uso da IA e sensores), **Dados** (exportar planilha, JSON e ZIP com fotos; backup na pasta share; importar; versões anteriores; onde ficam os dados; e **Começar do zero**, que apaga os cômodos, os bens e os itens depois de confirmar, com uma cópia em Versões anteriores; as categorias e as opções continuam), **Aparência** (tema claro, escuro ou automático e a cor do app, com as 12 cores da família: vermelho, coral, laranja, ouro, verde, menta, turquesa, azul, índigo, lilás, rosa e grafite; com a **Cor do dia**, ligada de início, a cor muda todo dia, a mesma o dia todo e em todos os apps da família, sem o grafite; escolher uma cor desliga a Cor do dia) e **Opções** (as novidades, os bens e as zonas). O tema fica em cada aparelho (começa em Sistema); a cor do app, a IA, as novidades e as zonas valem para a casa toda.
- **Sobre** (Mais > Sobre), por último: quem faz o app (**CorrerIA Code**), os apps da família, cada um com uma linha e o link para o GitHub (o InventarIA com a versão instalada), e **Meu GitHub**.
- No celular, **arrastar para o lado** troca de aba (Início, Buscar, Cômodos e Mais); dentro de um cômodo, arrastar para a direita volta para Cômodos, e em Gráficos, Novidades, Categorias, Relatório, Configurações ou Sobre, volta para o menu Mais.
- No computador (tela de 1000 pixels ou mais), a barra de baixo vira uma **barra lateral**: Início, Buscar, Cômodos, Relatório e Mais, e embaixo os cômodos, com o valor de cada um, e **Novo cômodo**. **Catalogar itens com IA** e **Adicionar item** ficam no alto da tela.
- Atalhos no computador: `/` abre a busca, `N` cria um item, `Ctrl+Enter` salva o formulário.
- As **caixas de seleção** (como o cômodo de um item ou os filtros da busca) abrem uma janela de baixo para cima com as opções; a atual vem marcada. O Voltar do celular, o **X** ou tocar fora fecham sem mudar nada. No computador, a janela abre no meio da tela, e dá para escolher com as setas e Enter.
- O campo **Zona** (no cadastro, no **Mover** e no **Catalogar**) mostra logo abaixo as zonas do cômodo que combinam com o que você digita, até 6; ao tocar num campo que já tem uma zona, aparecem as outras. Tocar numa preenche o campo; sair do campo ou Esc fecha a lista. No computador, as setas e o Enter também escolhem.

O valor de cada item é o que você quiser registrar, somando todas as unidades.

## Opções da casa

- **Usar IA** (Mais > Configurações > Integrações), ligada de início: desligada, o app esconde tudo o que usa IA (Catalogar itens com IA, Digitalizar com IA, Buscar na internet, Novidades, Conversar e Falar) e não chama a IA.
- **Usar bens** (Mais > Configurações > Opções), ligado de início: desligado, os bens somem de tudo, do menu Mais, do Início, da busca, dos gráficos, do relatório, da conversa com a IA e dos outros apps (ResolvIA, CronologIA e o patrimônio do GerencIA). Desligar não apaga os bens: ligado de novo, voltam como estavam.
- **Usar zonas** (Mais > Configurações > Opções), desligada de início: as zonas dividem um cômodo em partes, como Estante, Bancada ou Rack da TV. Ligadas, aparecem o campo Zona no cadastro, a zona na ficha do item, na busca e no relatório, e os itens de cada cômodo ficam separados por zona.

Desligar uma opção só esconde: nada do que já foi gravado se perde, e ligar de novo traz tudo de volta.

## Leitura de fotos por IA

O app não tem IA própria e não guarda chave de API. Ele usa a ação `ai_task.generate_data` do Home Assistant, então funciona com a integração de IA que você configurar lá, e dá para trocar quando quiser:

| Integração | Observação |
|---|---|
| Anthropic (Claude) | Precisa de chave da API da Anthropic. |
| OpenAI | Precisa de chave da API da OpenAI. |
| Google Gemini | Costuma ter uma cota gratuita. |
| Ollama | Roda um modelo local na sua rede, sem custo e sem mandar fotos para fora. Use um modelo que entenda imagens (por exemplo `qwen2.5vl` ou `gemma3`). |

Para configurar:

1. Em **Configurações > Dispositivos e serviços > Adicionar integração**, escolha a integração e siga os passos.
2. Na página da integração, adicione uma **tarefa de IA** (AI Task) e escolha um modelo que leia imagens.
3. No app, abra **Mais > Configurações > Integrações** e escolha essa IA em **IA para ler fotos**. "Padrão do Home Assistant" usa a IA preferida definida em **Configurações > Sistema > Geral**.

Na hora da leitura, o app copia a foto por alguns segundos para `media/inventario/ia-temp`, chama a IA pelo Home Assistant e apaga a cópia em seguida. A IA não recebe número de série, IMEI ou dados pessoais: as instruções pedem só descrição do objeto.

Sem IA configurada, todo o resto funciona normalmente. Se não for usar IA, desligue **Usar IA** em **Mais > Configurações > Integrações** e os botões de IA somem.

## Falar

O **microfone** fica no alto da tela, à direita (e também em **Adicionar > Falar os itens**). Toque, fale os itens e toque de novo, por exemplo: "Sofá cinza de três lugares, 2 mil reais. Televisão Samsung de 55 polegadas, 3 mil". O Home Assistant transcreve com a **fala para texto do Assist** (Configurações > Assistentes de voz; com o Home Assistant Cloud ela já vem pronta, em português), e a IA separa os itens com nome, categoria, quantidade e valor. O valor que você falar vale mais que a estimativa da IA. Você confere, ajusta e escolhe o que entra.

- O Falar não pergunta o cômodo: a IA conhece os cômodos da casa e põe cada item no seu, pelo que você falou ("na sala", "e na cozinha a batedeira") ou pelo objeto (a geladeira vai para a cozinha). O que ela não souber fica com **Qual cômodo?** para você escolher antes de adicionar; o **Cômodo** do alto muda todos de uma vez. Dentro de um cômodo, o que você não disser onde fica vai para ele.
- Sem IA (Usar IA desligada ou sem integração de IA), o app separa o que foi dito pelas vírgulas e pelo "e", e o valor ("2.000 reais", "R$ 500", "dois mil reais", "três mil") vai para o item anterior.
- Até 2 minutos por vez. Na primeira vez, o navegador ou o app do celular pede permissão para o microfone.
- O microfone só aparece quando o Home Assistant tem fala para texto. Em **Mais > Configurações > Integrações > Falar** você vê qual transcreve e escolhe outra em **Fala para texto**, como na escolha da IA: **Padrão do Home Assistant** usa a fala para texto do assistente de voz preferido (Configurações > Assistentes de voz), e embaixo vêm as que o Home Assistant tem, como Home Assistant Cloud, Google AI ou Whisper.
- Com **Usar IA** desligada, o Falar some junto. Com a IA ligada mas sem uma IA no Home Assistant que responda, o app separa os itens sozinho, pelas vírgulas. Para não usar nada do Gemini, escolha uma fala para texto que não seja a do Google AI.
- O microfone precisa do Home Assistant aberto com https (como o endereço do Home Assistant Cloud) ou pelo app do celular; pelo endereço http da rede de casa, o navegador não deixa usar.

## Uso da IA

Em **Mais > Configurações > Integrações > Uso da IA** ficam as chamadas de hoje, dos últimos 7 dias e do mês, um gráfico por dia (toque numa barra para ver o dia), o tipo de uso (Digitalizar com IA, Catalogar itens, Buscar foto na internet, Falar, Novidades, Escolher equipamentos e Conversar) e as últimas chamadas, com a IA usada, o tempo e o resultado (cota excedida, resposta fora do formato, IA sem busca na web ou erro).

O Home Assistant não informa tokens nem custo, então o app conta as chamadas e estima os tokens pelo tamanho do texto (uns 4 caracteres por token). As imagens e a busca na web gastam mais do que essa estimativa. O consumo exato e o custo ficam no painel do provedor: Google Cloud Console para o Gemini, platform.openai.com/usage para a OpenAI e Claude Console para a Anthropic.

Com **Sensores no Home Assistant** ligado (em **Mais > Configurações > Integrações**; vem desligado), o app cria no Home Assistant o sensor `sensor.inventaria_ia_hoje`, com as chamadas de hoje no estado e os detalhes nos atributos (`erros`, `cota_excedida`, `tokens_texto_estimados`, `imagens`, `por_tipo`, `ultimos_7_dias`, `este_mes` e `ultima_chamada`). Dá para pôr num painel ou numa automação, por exemplo para avisar quando passar de 50 chamadas no dia. O sensor zera na virada do dia; se o Home Assistant reiniciar, ele volta em alguns minutos. Desligando a opção, o sensor sai do Home Assistant na hora.

## Fotos da internet

Para itens sem foto, **Buscar na internet** pede à IA do Home Assistant que procure o produto na web, no site do fabricante e em lojas grandes. O app abre as páginas que a IA encontrou, pega a foto principal de cada uma, descarta o que não é foto ou é pequeno demais e mostra as opções. A foto escolhida entra no item como **foto ilustrativa**, com o site de onde veio, na ficha do item e no relatório. Para o seguro, uma foto sua do item continua valendo mais.

Na mesma chamada, a IA também descreve o produto que achou: nome com marca e modelo, detalhes, categoria e um valor estimado. A janela mostra o que vai para o item, já marcado em **Preencher também**, e dá para desmarcar. Os dados só preenchem o que está vazio: num item novo, o nome também vem da IA; num item que já existe, o nome e um valor já dado não mudam. **Usar só os dados, sem foto** preenche sem escolher foto, e serve também quando a busca não acha fotos. No editor, o aviso tem **Desfazer**.

A IA precisa ter a **busca na web** ligada:

- **Anthropic**: nas opções da tarefa de IA, ligue **Enable web search**.
- **Google Gemini**: a Pesquisa Google só funciona num assistente de conversa. Ligue **Enable Google Search tool** nele e escolha esse assistente.
- **OpenAI**: nas opções da tarefa de IA, ligue **Enable web search** (precisa do gpt-4o ou de um modelo mais novo).

Escolha a IA em **Mais > Configurações > Integrações > IA para buscar fotos na internet**. Como na leitura de fotos, "Padrão do Home Assistant" usa a tarefa de IA preferida definida no Home Assistant; para o Gemini, escolha o assistente de conversa na lista.

A IA recebe só o nome, o começo dos detalhes e a quantidade do item. O app baixa as fotos apenas de endereços públicos da internet (nunca da rede da casa) e guarda só a foto que você escolher; as outras são apagadas em até 30 minutos. Cada busca usa a busca na web da sua IA, que pode ter custo à parte.

## Novidades do produto

Na ficha de um eletrônico, **Novidades** pede à IA de busca (a mesma da busca de fotos, em Mais > Configurações > Integrações) o que saiu nos últimos 12 meses e o que já foi anunciado para os próximos meses sobre o produto: atualizações de firmware ou software, modelo novo, lançamentos da mesma linha, recalls e fim de suporte.

- A busca começa pela página de suporte do fabricante, nos downloads (os arquivos de firmware e de atualização do sistema, com a data), e olha também a do mesmo modelo em outro país, que costuma ter um código um pouco diferente. Se ainda assim não achar, cole o endereço da página de suporte nos **Detalhes** do item: a IA abre essa página primeiro.
- Vêm só as 3 novidades mais recentes, dos últimos 12 meses. Cada uma vem com o tipo, a data quando se sabe e o site da fonte, que abre fora do app. Sem fonte, não entra. Rumor aparece marcado como **Boato**; recall fica em destaque, mas só quando o produto é chamado de volta (troca, conserto ou reembolso); falha de segurança corrigida por atualização aparece como Atualização.
- A IA só acha o que já foi publicado: lançamento que ainda não foi anunciado não aparece.
- As novidades aparecem na própria ficha e ficam guardadas: ao abrir a ficha de novo, já estão lá, sem chamar a IA. **Buscar de novo** pergunta outra vez; fechar a ficha no meio da busca não perde o resultado. Cada busca conta em Uso da IA.
- **Mais > Novidades** confere todos os itens da categoria Eletrônicos de uma vez: toque em **Conferir novidades**. A IA escolhe, entre os eletrônicos, os que vale conferir e o app confere um por um, mostrando o andamento; **Parar** guarda o que já foi conferido. O que foi conferido nos últimos 7 dias fica para a próxima. A lista mostra recall primeiro, depois os com novidades; tocar num item abre o que foi achado, com **Ver item** para ir à ficha dele (o Voltar volta para as Novidades). Os que a IA deixou de fora ficam no fim, recolhidos em **Deixados de fora pela IA**, com quantos são; um toque abre (e fica aberto enquanto você estiver na tela), e dá para conferir cada um sozinho: conferido, ele sobe para a lista e entra nas próximas conferências. Itens de outras categorias não entram, nem na lista; dá para conferir um deles pela ficha. O mesmo equipamento em vários cômodos (ou escrito no plural, como "Lâmpadas …", com a cor no nome ou com as palavras em outra ordem, como "Echo Spot (2024) preto" e "Echo Spot 2024") é uma linha só e uma busca só, e o resultado aparece na ficha de cada um.
- **Limpar novidades** (com confirmação) apaga o que foi encontrado e as escolhas da IA, e para a conferência em andamento. O inventário não muda.
- Em **Mais > Configurações > Opções > Novidades**:
  - **Usar novidades** liga e desliga tudo: desligadas, somem do menu Mais e da ficha, e nada é conferido.
  - **Conferir sozinho** faz o app conferir os eletrônicos sozinho, do mesmo jeito do botão **Conferir novidades**, no **Horário** escolhido (de meia em meia hora; 10:00 de início) e **A cada** 7, 15 ou 30 dias, contados da última conferência. Quando a conferência dá erro, como cota da IA esgotada, o app tenta de novo em 6 horas.
  - **Avisar no celular** (aparece com **Conferir sozinho** ligado) manda um aviso quando essa conferência acha algo novo. Em **Quem recebe**, toque nas pessoas da casa (uma ou várias); ligar o aviso sem ninguém escolhido começa com você. O aviso vai para os celulares ligados a cada pessoa no Home Assistant (**Configurações > Pessoas**), como nos outros apps da família; quem não tem celular ligado aparece como "sem celular". O aviso diz "Novidades em 3 itens. Toque para abrir." e, ao tocar, abre o InventarIA em Novidades. **Testar no meu celular** manda um aviso na hora para o celular de quem está usando o app.
- Quanto mais o nome do item tiver marca e modelo, como na nota fiscal, melhor a busca. O app mostra como a IA identificou o produto.

## Conversar

O balão ao lado do microfone, no alto da tela (e na ficha do item), abre uma conversa com a IA. Pergunte sobre o que está na tela ("qual o item mais caro daqui?", "vale pôr no seguro?") ou sobre qualquer outro assunto. A IA recebe o resumo da casa e o que está na tela: o item, o cômodo com os itens, a busca ou as novidades. Ela responde, mas não muda o inventário.

- Responde a IA de buscar fotos na internet (Mais > Configurações > Integrações); sem ela, a de ler fotos. Um assistente de conversa com a Pesquisa Google ligada responde também o que é de fora da casa.
- Com o microfone da conversa, dá para falar a pergunta.
- A conversa fica até fechar o app; **Nova conversa** começa outra. Cada pergunta conta em Uso da IA.

## Seus dados

Tudo fica em arquivos abertos, dentro da pasta de dados do app:

- `inventario.json`: cômodos e itens (texto legível, abre em qualquer editor).
- `photos/` e `thumbs/`: fotos em JPG (tamanho cheio e miniatura).
- `history/`: cópias automáticas do inventário, uma a cada 10 minutos de uso (só as 3 mais recentes).

Formas de guardar uma cópia:

- **Backups do Home Assistant**: incluem o app e os dados dele.
- **Mais > Configurações > Dados > Backup na pasta share**: cria um `.zip` completo (JSON, CSV e fotos) em `share/inventario`, que você acessa pela rede (por exemplo `\\homeassistant.local\share\inventario` com o app Samba).
- **Mais > Configurações > Dados > Exportar**: CSV (abre no Excel), JSON ou ZIP com fotos, direto para o seu computador ou celular.

Para restaurar, use **Mais > Configurações > Dados**: escolha um backup da pasta share, volte para uma versão anterior (**Versões anteriores > Ver versões**, com a data, quantos itens cada uma tem e por que foi guardada) ou importe um arquivo (`.zip` de backup ou `.json`) do computador ou do celular. Antes de restaurar ou importar, o app guarda uma cópia do que existe naquele momento.

## Cômodos e itens nos outros apps

A ligação é automática, sem nada para configurar aqui: o InventarIA grava `share/inventario/integracao.json` com o endereço dele na rede interna dos apps e uma chave, e responde só a lista de cômodos e de itens (nome, cômodo, zona, categoria, valor e a data do valor) para quem tem essa chave. Os outros apps só leem; nada muda aqui. A tela do InventarIA continua abrindo só pelo Home Assistant.

- **ResolvIA** (2.28.0 ou mais novo): liga uma tarefa a um cômodo daqui e, a partir da 2.29.0, a um ou mais itens (um equipamento, um móvel…). Ligue lá, em **Mais > Configurações > Integrações > InventarIA** (**Usar cômodos** e **Usar equipamentos**, desligados de início).
- **CronologIA**: recebe os cômodos e os itens pelo ResolvIA. As tarefas mostram o cômodo e o equipamento, e o **Novo > Tarefa** pede os dois.
- **Bens** aparece para os outros apps ao lado dos cômodos, com os bens como itens: no ResolvIA e na CronologIA, uma tarefa pode ser ligada ao carro ou à casa da praia.
- **Tarefas no ResolvIA**: com **Usar equipamentos** ligado lá, a ficha de cada item daqui tem **Tarefas no ResolvIA**: as tarefas abertas ligadas ao item (com a lista e o prazo) e **Nova tarefa**. Escreva o que fazer, escolha a lista do Home Assistant e o prazo (**Sem prazo**, **Hoje**, **Amanhã**, **Em 7 dias** ou **Em 30 dias**; numa lista que não aceita prazo, ele some) e toque em **Criar tarefa**. A tarefa entra na lista e fica ligada ao item e ao cômodo no ResolvIA, como se tivesse sido criada lá.
- **GerencIA** (1.19.0 ou mais novo): soma os valores dos itens e dos bens no patrimônio, como **Bens da casa** (imóveis não perdem valor; veículos perdem 15% ao ano, e dá para mudar lá). Lê o valor e a data em que ele mudou e deprecia por categoria (eletrônicos perdem mais rápido que móveis, por exemplo). Dá para desligar lá, em **Mais > Integrações > Bens no InventarIA**.

## Valor de hoje (GerencIA)

Com o **GerencIA** (1.55.0 ou mais novo) no mesmo Home Assistant, aparece em **Mais > Configurações > Integrações** o cartão **GerencIA**, com **Valor de hoje** (vem desligado). Ligado:

- cada valor perde, por ano, a taxa da categoria dele que está no GerencIA (em **Mais › Invest › Valor dos bens por ano**, lá), composta, desde a data em que o valor mudou aqui. Uma taxa negativa valoriza (um imóvel, por exemplo); uma categoria que o GerencIA não tem perde 10%;
- o Início mostra **Patrimônio hoje**, e os cômodos, a busca, os gráficos e o relatório (também o PDF, que diz "valor de hoje") usam o valor de hoje;
- a ficha do item mostra o valor de hoje e, embaixo, o valor que você informou, a data e a taxa ("R$ 1.800 em 02/10/2026, −20% ao ano").

O valor gravado não muda: ao editar, você vê e muda o valor que informou, e os outros apps continuam recebendo esse valor. Desligar volta tudo para o valor gravado.

## CorrerIA

O **CorrerIA** é o app da família que liga o inventário ao WhatsApp, ao Claude e ao Gemini. Pelo WhatsApp ou numa conversa com o Claude ou o Gemini, dá para perguntar "quanto vale o que tem na sala?", "onde está a bicicleta?" ou pedir "cadastra uma rede de R$ 150 na varanda".

1. Aqui, em **Mais > Configurações > Integrações > CorrerIA**, ligue **Usar com o CorrerIA** (vem desligada). Não precisa da IA do InventarIA: quem pensa é a IA do CorrerIA, o Claude ou o Gemini.
2. No app **CorrerIA**, conecte o WhatsApp, o Claude ou o Gemini. O InventarIA aparece lá sozinho.

O que dá para fazer: ver o resumo da casa (o total, os cômodos, os bens e as categorias), buscar itens (por nome, cômodo, zona, categoria ou valor), ver um item, cadastrar um ou vários itens num cômodo (ou em Bens), editar (nome, valor, quantidade, categoria, zona, detalhes e observação), mover para outro cômodo e apagar, e criar um cômodo. As mudanças seguem as mesmas regras da tela: o item ganha o próximo código do cômodo, a data do valor muda quando o valor muda, e as versões automáticas continuam valendo. Pelo WhatsApp, o CorrerIA pede para você confirmar antes de gravar.

Fotos, backups e configurações não passam pelo CorrerIA. O item cadastrado assim mostra na ficha a origem **Pelo CorrerIA** e quem cadastrou. Embaixo da chave, o app mostra quem usou por último e quando ("Claude usou hoje às 9:41"). Desligar a chave corta a ligação na hora.

## Atualizar o app

Quando sai uma versão nova, o Home Assistant mostra **Atualizar** na página do app e em **Configurações > Atualizações**. Para procurar na hora, abra **Configurações > Aplicativos > Loja de aplicativos**, toque no menu **⋮** e escolha **Verificar atualizações**. Os dados não são apagados.

## Problemas comuns

- **"A sessão do Home Assistant expirou"**: recarregue a página do Home Assistant.
- **A IA aparece como não configurada**: confira se a integração de IA tem uma tarefa de IA criada e se o modelo lê imagens; depois toque em "Verificar de novo".
- **A IA demora**: modelos locais podem levar mais de um minuto por foto. Modelos na nuvem costumam responder em 5 a 20 segundos.
- **Ver o que está acontecendo**: aba **Registro** do app.
