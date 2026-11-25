# InventarIA

O InventarIA é o inventário da casa dentro do Home Assistant: cômodos, itens com fotos e valores, busca, gráficos, relatório em PDF e, se você quiser, leitura de fotos por IA e zonas dentro dos cômodos.

O app abre pela barra lateral (Ingress). Quem já está logado no Home Assistant usa direto, sem outra senha.

## Primeiro uso

Na primeira vez, o app abre vazio e oferece duas opções:

- **Importar backup**: escolha o arquivo `.zip` de um backup do app (com itens, fotos e valores). Funciona pelo celular: o arquivo é enviado em partes, com barra de progresso. Deixe a tela aberta até terminar.
- **Criar o primeiro cômodo**: comece pelo primeiro cômodo e vá cadastrando os itens.

Depois disso, tudo o que você muda fica salvo no app. Atualizar ou reiniciar o app não apaga nada.

## Como usar

- **Agora** (a primeira aba; até a 1.52, Início): a etiqueta do patrimônio, a busca logo abaixo, os destaques (mais valioso, maior cômodo, último cadastro e fotos), os cômodos (com a parte de cada um no total) e os cadastrados recentemente. As categorias e os itens mais valiosos ficam em **Mais > Gráficos**.
- **Cômodos** (aba ao lado de Adicionar): todos os cômodos com foto, número de itens e valor. Toque num cômodo para abrir. Em **Organizar**, as setas mudam a ordem (que vale para o app todo e para o relatório) e o lápis edita nome, código e fotos.
- **Cômodo**: fotos do cômodo e a lista dos itens, na ordem dos códigos (com mais de 6 itens, aparece **Filtrar neste cômodo**). Com as zonas ligadas, os itens aparecem separados por zona, com o subtotal de cada uma. Toque numa foto para ver os itens que estão nela, mudar a legenda, usar como capa, adicionar um item com ela, catalogar com IA ou tirá-la do cômodo.
- **Adicionar item**: nome, detalhes, cômodo, categoria, quantidade e valor total (e a zona, se estiver ligada). Dá para tirar foto pelo celular, **Escolher fotos** da galeria, usar uma das **Fotos do cômodo**, arrastar uma foto ou colar com Ctrl+V; a primeira é a capa. No app do Home Assistant para Android, **Tirar foto** abre a câmera do próprio InventarIA, como no ResolvIA (na primeira vez, o celular pede permissão). Com uma foto, **Digitalizar com IA** lê a primeira e preenche nome, detalhes, categoria e valor, com **Desfazer** no aviso; o que você já escreveu nos detalhes, na quantidade e no valor fica, e dá para dar uma dica à IA ("é uma cafeteira Oster"). **Observação** guarda um lembrete sobre o item. "Salvar e adicionar outro" mantém o cômodo para cadastrar em sequência.
- **Ficha do item**: toque num item para ver as fotos (toque para ampliar), o valor (e o de cada unidade), os detalhes, o cômodo, a categoria, a origem, quem cadastrou e quando, e as novidades. Embaixo ficam **Editar**, **Duplicar**, **Mover** (para outro cômodo ou zona; em outro cômodo, o item ganha um código novo) e **Apagar**. Mover e Apagar têm **Desfazer** no aviso.
- **Catalogar itens com IA**: tire uma foto de uma prateleira ou de um canto da casa (ou use uma foto do cômodo); a IA lista os objetos com nome, categoria, quantidade e uma sugestão de valor. Você confere, ajusta e escolhe o que entra. O que parece já cadastrado e o que a IA não tem certeza vêm marcados. Dentro de um cômodo, os itens vão para ele; fora, o **Cômodo** vem em **A IA escolhe**: ela conhece os cômodos da casa e reconhece o da foto. Se não souber, você escolhe na hora de conferir.
- **Falar**: o microfone no alto da tela. Fale os itens e quanto valem, e o app separa cada um para você conferir. Veja [Falar](#falar).
- **Recursos**: na ficha de um eletrônico, de uma utilidade ou de um veículo (com a IA ligada), a seção **Recursos** (**Ver recursos**) pergunta à IA o que aquele equipamento tem: funções, modos, conexões e ajustes, cada um com uma frase de para que serve (pela busca na web, na página do fabricante, no manual ou na ficha técnica de hoje, e mostra a fonte; uma IA sem a busca na web não responde de memória: o app avisa como ligar). A lista fica guardada na ficha até o item mudar de nome ou de detalhes; **Ver de novo** pergunta outra vez. Por isso **Utilidades** e **Veículos** são fixas em Mais › Categorias, como Eletrônicos (o nome não muda e não se apagam; a cor, sim). Em **Mais › Novidades › Eletrônicos** ficam todos os eletrônicos, com quantos recursos cada um tem (o mesmo equipamento em vários cômodos numa linha só); **Conferir novidades › Só eletrônicos** busca os que ainda não têm (o mesmo equipamento noutro cômodo ganha os mesmos, sem perguntar de novo), com o andamento e **Parar**; **Todas as novidades** também busca os que faltam (o Conferir sozinho, não). Um toque abre os recursos, com **Ver de novo** e **Ver item**.
- **Novidades**: na ficha de um eletrônico, a IA procura na web atualizações, lançamentos, modelo novo, recalls e fim de suporte do produto; em **Mais > Novidades**, de todos os eletrônicos de uma vez e, se você ligar, dos apps que vocês usam no celular. Veja [Novidades do produto](#novidades-do-produto).
- **Conversar**: o balão ao lado do microfone abre uma conversa com a IA, a qualquer momento, sobre o que está na tela ou qualquer outro assunto. Veja [Conversar](#conversar).
- **Buscar na internet**: num item sem foto (ou no editor do item), a IA procura o produto no fabricante e nas lojas e o app mostra as fotos encontradas para você escolher. Na mesma busca, a IA traz nome, detalhes, categoria e valor do produto para preencher o item. Veja [Fotos da internet](#fotos-da-internet).
- **Buscar**: por nome, marca ou detalhe, sem se preocupar com acentos. Em **Filtros** (um toque no título fecha e abre, e o aparelho lembra), filtre por cômodo e categoria e ordene por valor, nome, data ou código. Com bens cadastrados, o filtro **Tipo** vem antes: Itens da casa, Imóveis, Veículos ou Outros bens (num tipo de bem, os filtros de cômodo e categoria saem).
  - **Selecionar**, ao lado de quantos itens a busca achou (ou segure o dedo num item, que já vem marcado), muda vários itens de uma vez, como no ResolvIA: toque nos itens (ou em **Todos**, que vale para a lista inteira) e, embaixo, em **Alterar**. A janela tem **Cômodo**, **Categoria** e **Zona** (com as zonas ligadas), cada um começando em **Manter**: mude um ou mais e toque em **Aplicar**. Em outro cômodo, cada item ganha um código novo e fica sem zona, se não escolher uma. O aviso tem **Desfazer**. Os bens ficam de fora. O Voltar do celular ou o **X** saem do Selecionar.
- **Mais** é um menu: **Bens**, **Gráficos**, **Novidades** (com a IA ligada), **Categorias**, **Relatório do inventário**, **Configurações** e **Sobre**. Cada um abre a sua tela, com **‹ Mais** no alto para voltar.
- **Bens** (Mais > Bens) guarda o que tem valor e fica fora de casa: casa, apartamento, terreno, carro, moto.
  - **Adicionar bem** (na tela Bens ou no **+ Adicionar** de baixo, fora dos cômodos) abre o cadastro sem **Cômodo** e sem **Categoria**: só o **Tipo** (Imóvel, Veículo ou Outro). O código dos bens é BEN (BEN-001, BEN-002…).
  - A lista separa **Imóveis**, **Veículos** e **Outros**, cada um com o total. As categorias Imóveis e Veículos entram na lista de categorias com o primeiro bem.
  - Um item da casa também pode ir para Bens pelo **Mover**, e um bem pode voltar para um cômodo do mesmo jeito.
  - Os bens contam no patrimônio da Agora (a etiqueta diz quantos), na busca (filtro **Tipo**) e na conversa com a IA, mas ficam fora da lista de cômodos. Em **Gráficos**, têm um gráfico só deles; os da casa (cômodos, categorias, faixas e mais valiosos) ficam sem eles.
  - Na lista de Bens, o **+ Adicionar** de baixo adiciona um bem.
  - No relatório, vêm numa seção à parte, no fim, com o total deles; o total da casa não muda.
- **Gráficos** (Mais > Gráficos): o patrimônio, quantos itens, o valor médio e quantos têm foto; os cômodos e as categorias que mais valem, do maior para o menor, com o valor e a parte do total; quantos itens há em cada faixa de valor; os 10 itens mais valiosos; e, quando há itens de mais de um mês, o patrimônio mês a mês pela data de cadastro (toque no gráfico para ver o valor de cada mês, ou **Ver mês a mês** para a tabela). Tocar numa linha abre o cômodo, a busca da categoria ou a ficha do item.
- **Categorias** (Mais > Categorias): uma linha por categoria, com o ícone na cor dela e quantos itens tem. Toque numa para mudar o **Nome** e a **Cor** (uma das 12 da paleta) ou **Apagar**; **Nova categoria**, no fim da lista, cria outra (começa na cor menos usada). A cor aparece também na escolha da categoria do item, num pontinho ao lado do nome. Os itens de uma categoria apagada vão para Outros (em Grafite), que não pode ser apagada. **Eletrônicos** é a categoria das novidades: fica sempre, com esse nome (muda só a cor). As categorias ficam no inventário: entram no backup, na exportação e nas versões, valem para todos os aparelhos, e a IA passa a usar as novas.
- **Relatório do inventário** (Mais > Relatório do inventário; no computador, também na barra lateral): no alto, o app, o título, quantos itens e cômodos e quando; o patrimônio, os gráficos da tela Gráficos (cômodos, categorias, faixas de valor, os mais valiosos e os bens) e os itens de cada cômodo, com código, foto, quantidade e valor; no fim, a marca da CorrerIA Code. **Baixar PDF** baixa o mesmo relatório como arquivo, na cor do app (o celular abre, e de lá dá para imprimir ou mandar para a seguradora). **Mostrar fotos** desmarcado deixa o relatório, e o PDF, só com o texto.
- **Configurações** (Mais > Configurações), em abas na ordem dos outros apps, abrindo em **Integrações**: **Integrações** (o [CorrerIA](#correria), ligar ou desligar a IA e escolher qual IA do Home Assistant usar, Falar, Uso da IA e sensores), **Dados** (exportar planilha, JSON e ZIP com fotos; backup na pasta share; importar; versões anteriores; onde ficam os dados; e **Começar do zero**, que apaga os cômodos, os bens e os itens depois de confirmar, com uma cópia em Versões anteriores; as categorias e as opções continuam), **Aparência** (tema claro, escuro ou automático e a cor do app, com as 12 cores da família: vermelho, coral, laranja, ouro, verde, menta, turquesa, azul, índigo, lilás, rosa e grafite; com a **Cor do dia**, ligada de início, a cor muda todo dia, a mesma o dia todo e em todos os apps da família, sem o grafite; escolher uma cor desliga a Cor do dia) e **Opções** (as novidades, os bens e as zonas). O tema fica em cada aparelho (começa em Sistema), com o fundo e os cartões do tema do Home Assistant, os mesmos dos outros apps; a cor do app, a IA, as novidades e as zonas valem para a casa toda.
- **Sobre** (Mais > Sobre), por último: quem faz o app (**CorrerIA Code**), os apps da família, cada um com uma linha e o link para o GitHub (o InventarIA com a versão instalada), e **Meu GitHub**.
- No celular, **arrastar para o lado** troca de aba (Agora, Buscar, Cômodos e Mais); dentro de um cômodo, arrastar para a direita volta para Cômodos, e em Gráficos, Novidades, Categorias, Relatório, Configurações ou Sobre, volta para o menu Mais.
- No computador (tela de 1000 pixels ou mais), a barra de baixo vira uma **barra lateral**: Agora, Buscar, Cômodos, Relatório e Mais, e embaixo os cômodos, com o valor de cada um, e **Novo cômodo**. **Catalogar itens com IA** e **Adicionar item** ficam no alto da tela.
- Atalhos no computador: `/` abre a busca, `N` cria um item, `Ctrl+Enter` salva o formulário.
- As **caixas de seleção** (como o cômodo de um item ou os filtros da busca) abrem uma janela de baixo para cima com as opções; a atual vem marcada. O Voltar do celular, o **X** ou tocar fora fecham sem mudar nada. No computador, a janela abre no meio da tela, e dá para escolher com as setas e Enter.
- O campo **Zona** (no cadastro, no **Mover** e no **Catalogar**) mostra logo abaixo as zonas do cômodo que combinam com o que você digita, até 6; ao tocar num campo que já tem uma zona, aparecem as outras. Tocar numa preenche o campo; sair do campo ou Esc fecha a lista. No computador, as setas e o Enter também escolhem.

O valor de cada item é o que você quiser registrar, somando todas as unidades.

## Opções da casa

- **Usar IA** (Mais > Configurações > Integrações), ligada de início: desligada, o app esconde tudo o que usa IA (Catalogar itens com IA, Digitalizar com IA, Buscar na internet, Novidades, Conversar e Falar) e não chama a IA.
- **Inventário** (Mais > Configurações > Opções): o app guarda três tipos, cada um com a sua chave: **Usar itens da casa** (os cômodos e o que há neles; ligado de início), **Usar bens** (ligado de início) e **Usar consumíveis** (desligado de início). Qualquer combinação vale, pelo menos um fica ligado, e desligar não apaga nada. Com mais de um em uso, a **Agora** mostra um quadro para cada, com a contagem e o total, e um toque abre o tipo.
  - **Sem os itens da casa**, somem os cômodos, os itens deles, as zonas, o Catalogar e o Falar; a aba **Cômodos** da barra vira **Bens** (ou **Consumíveis**), e os outros apps ficam só com os bens.
- **Consumíveis** (Mais > Consumíveis, com **Usar consumíveis** ligado): o que se gasta e se compra de novo, como pasta térmica, creme de massagem e pilhas.
- **Consumíveis por cômodo** (Mais > Configurações > Opções > Inventário, embaixo de Usar consumíveis; desligado de início): cada consumível pode dizer em que cômodos é usado (**Cômodos onde é usado**, ao editar: um, vários ou nenhum). A lista e a ficha mostram os cômodos, a tela dos Consumíveis ganha, no **Agrupar por**, o Cômodo (cada grupo fecha num toque no título), e o CorrerIA usa na Ronda da casa (os consumíveis de cada cômodo). Desligar não apaga o que foi escolhido. No **Buscar › Selecionar**, dá para marcar vários consumíveis e mudar de uma vez a categoria e o cômodo onde são usados.
  - **Adicionar consumível** (na tela ou no **+ Adicionar**) abre o cadastro sem **Cômodo** e sem **Zona**: o nome, **O que é e para que serve**, a categoria (das dos consumíveis) e a **Duração estimada**. O código começa com **CON** (CON-001).
  - **Agrupar por** (no alto da tela dos Consumíveis): **Categoria** ou **Vencimento**, pelo Dura até: **Já acabou**, **Esta semana** (até o domingo), **Este mês**, **Mês que vem**, **Depois** e **Sem duração**, com o que acaba primeiro no alto de cada grupo. Cada grupo fecha num toque no título, e o aparelho lembra.
  - Com uma foto, a IA preenche o nome e o que é e para que serve. É por esse texto que a busca, a Conversa e o CorrerIA acham o consumível pelo uso ("o que temos para massagem?").
  - A tela mostra os consumíveis por categoria, com a **Duração estimada** em destaque. Um consumível não tem quantidade nem valor: tem a duração (1 semana, 15 dias, 1 mês, 3 meses, 6 meses ou 1 ano).
  - A **Duração estimada** tem os atalhos e a **Outra** (o número e a unidade: dias, semanas, meses ou anos, até 10 anos). Com a duração, a ficha mostra **Dura até**: a duração contada do dia em que foi informada (mudou a duração, conta de novo). Em **Mais > Gráficos**, o cartão **Categorias dos consumíveis** mostra quantos há em cada categoria.
  - **Comprei hoje no EconomIA** (1.49.0 ou mais novo): o **Dura até** do consumível volta a contar do dia da compra, e a duração que você escolher lá vira a Duração estimada. Na lista dos consumíveis aparece até quando cada um dura; o que passou da data fica em vermelho.
  - **Compras no EconomIA**: com o EconomIA (1.47.0 ou mais novo) e **Consumíveis do InventarIA** ligado lá (Mais › Configurações › Opções › Reposição), a ficha do consumível mostra se ele está na lista de compras, a última compra e a Reposição, e os botões **Pôr na lista** e **Repor a cada** (a Duração estimada). Vale o nome igual ou parecido com o do item no EconomIA (a ficha mostra qual achou); com mais de uma lista pronta lá, o Pôr na lista pergunta em qual.
  - As categorias dos consumíveis são à parte das da casa e já vêm com sugestões (Limpeza, Higiene e cuidados, Cozinha e despensa, Farmácia, Pets…); em **Mais > Categorias**, na seção **Categorias dos consumíveis**, dá para criar, mudar o nome e a cor, e apagar.
  - Os consumíveis aparecem na Agora, na busca (filtro **Tipo**) e na Conversa, mas não contam no patrimônio, nos gráficos, no relatório nem nos outros apps (ResolvIA, CronologIA e GerencIA). O **EconomIA** pode escolher um consumível daqui para a **Reposição** dele (o que comprar de novo de tempos em tempos).
- **Usar bens** (Mais > Configurações > Opções), ligado de início: desligado, os bens somem de tudo, do menu Mais, da Agora, da busca, dos gráficos, do relatório, da conversa com a IA e dos outros apps (ResolvIA, CronologIA e o patrimônio do GerencIA). Desligar não apaga os bens: ligado de novo, voltam como estavam.
- **Usar zonas** (Mais > Configurações > Opções), desligada de início: as zonas dividem um cômodo em partes, como Estante, Bancada ou Rack da TV. Ligadas, aparecem o campo Zona no cadastro, a zona na ficha do item, na busca e no relatório, e os itens de cada cômodo ficam separados por zona.

Desligar uma opção só esconde: nada do que já foi gravado se perde, e ligar de novo traz tudo de volta.

**Atalho no celular** (Mais > Configurações > Opções, por último): para abrir o InventarIA direto da tela inicial do celular (Android), toque em **Copiar** embaixo do **Caminho** (algo como `/app/a1b2c3d4_inventario`). No app do Home Assistant, abra **Configurações › Aplicativo complementar › Gerenciar atalhos** e, em **Atalho fixado**, escolha o tipo **Painel**, cole o caminho e dê um nome. Fora do Home Assistant o cartão não aparece.

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
3. No app, abra **Mais > Configurações > Integrações > IA** e escolha a IA de cada uso: **Para conversar** (a Conversa e o Falar; "Padrão do Home Assistant" usa a IA preferida definida em **Configurações > Sistema > Geral**), **Para ler fotos e PDFs** (ler fotos, catalogar e a Conversa com uma foto ou um PDF) e **Para pesquisar na internet** (veja abaixo). A de fotos e a de pesquisar começam **Igual à de conversar**. Assim dá para usar uma IA mais barata para conversar, como o Claude Haiku ou o Gemini Flash-Lite, e uma mais caprichada para ler as fotos.

Na hora da leitura, o app copia a foto por alguns segundos para `media/inventario/ia-temp`, chama a IA pelo Home Assistant e apaga a cópia em seguida. A IA não recebe número de série, IMEI ou dados pessoais: as instruções pedem só descrição do objeto.

Sem IA configurada, todo o resto funciona normalmente. Se não for usar IA, desligue **Usar IA** em **Mais > Configurações > Integrações** e os botões de IA somem.

## Falar

O **microfone** fica no alto da tela, à direita (e também em **Adicionar > Falar os itens**). Toque, fale os itens e toque de novo, por exemplo: "Sofá cinza de três lugares, 2 mil reais. Televisão Samsung de 55 polegadas, 3 mil". O Home Assistant transcreve com a **fala para texto do Assist** (Configurações > Assistentes de voz; com o Home Assistant Cloud ela já vem pronta, em português), e a IA separa os itens com nome, categoria, quantidade e valor. O valor que você falar vale mais que a estimativa da IA. Você confere, ajusta e escolhe o que entra.

- O Falar não pergunta o cômodo: a IA conhece os cômodos da casa e põe cada item no seu, pelo que você falou ("na sala", "e na cozinha a batedeira") ou pelo objeto (a geladeira vai para a cozinha). O que ela não souber fica com **Qual cômodo?** para você escolher antes de adicionar; o **Cômodo** do alto muda todos de uma vez. Dentro de um cômodo, o que você não disser onde fica vai para ele.
- Sem IA (Usar IA desligada ou sem integração de IA), o app separa o que foi dito pelas vírgulas e pelo "e", e o valor ("2.000 reais", "R$ 500", "dois mil reais", "três mil") vai para o item anterior.
- Até 2 minutos por vez. Na primeira vez, o navegador ou o app do celular pede permissão para o microfone.
- O microfone só aparece quando o Home Assistant tem fala para texto. Em **Mais > Configurações > Integrações > Falar** você vê qual transcreve e escolhe outra em **Fala para texto**, como na escolha da IA: **Automático** (que diz qual é) usa a fala para texto do assistente de voz preferido (Configurações > Assistentes de voz), e embaixo vêm as que o Home Assistant tem, como Home Assistant Cloud, Google AI ou Whisper.
- Com **Usar IA** desligada, o Falar some junto. Com a IA ligada mas sem uma IA no Home Assistant que responda, o app separa os itens sozinho, pelas vírgulas. Para não usar nada do Gemini, escolha uma fala para texto que não seja a do Google AI.
- O microfone precisa do Home Assistant aberto com https (como o endereço do Home Assistant Cloud) ou pelo app do celular; pelo endereço http da rede de casa, o navegador não deixa usar.

## Uso da IA

Em **Mais > Configurações > Integrações > Uso da IA** ficam as chamadas de hoje, dos últimos 7 dias e do mês, um gráfico por dia (toque numa barra para ver o dia), o tipo de uso (Digitalizar com IA, Catalogar itens, Buscar foto na internet, Falar, Novidades, Escolher equipamentos e Conversar) e as últimas chamadas, com a IA usada, o tempo e o resultado (cota excedida, resposta fora do formato, IA sem busca na web ou erro).

O Home Assistant não informa tokens nem custo, então o app conta as chamadas e estima os tokens pelo tamanho do texto (uns 4 caracteres por token). As imagens e a busca na web gastam mais do que essa estimativa. O consumo exato e o custo ficam no painel do provedor, e o rodapé leva ao de cada IA em uso (a de conversar, a de ler fotos e a de pesquisar podem ser de provedores diferentes): o Google AI Studio para o Gemini (em Dashboard › Usage; o saldo dos créditos, em Billing), o Claude Console para o Claude (o saldo dos créditos, em Billing) e platform.openai.com/usage para a OpenAI.

Com **Sensores no Home Assistant** ligado (em **Mais > Configurações > Integrações**; vem desligado), o app cria no Home Assistant o sensor `sensor.inventaria_ia_hoje`, com as chamadas de hoje no estado e os detalhes nos atributos (`erros`, `cota_excedida`, `tokens_texto_estimados`, `imagens`, `por_tipo`, `ultimos_7_dias`, `este_mes` e `ultima_chamada`). Dá para pôr num painel ou numa automação, por exemplo para avisar quando passar de 50 chamadas no dia. O sensor zera na virada do dia; se o Home Assistant reiniciar, ele volta em alguns minutos. Desligando a opção, os sensores saem do Home Assistant na hora.

Com as **Novidades** ligadas, o app cria também o `binary_sensor.inventaria_recall`: ligado quando as Novidades acharam um **recall** de um item (os boatos ficam de fora), com `quantidade` e `itens` (o item, o cômodo, o título, a data e a fonte de cada um). Ele muda em até um minuto depois de uma conferência; se o Home Assistant reiniciar, volta em até 15 minutos. Exemplo de automação:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.inventaria_recall
    to: "on"
actions:
  - action: notify.mobile_app_celular_da_ana
    data:
      title: "Recall: {{ state_attr('binary_sensor.inventaria_recall', 'itens')[0].item }}"
      message: "{{ state_attr('binary_sensor.inventaria_recall', 'itens')[0].titulo }}"
```

## Fotos da internet

Para itens sem foto, **Buscar na internet** pede à IA do Home Assistant que procure o produto na web, no site do fabricante e em lojas grandes. O app abre as páginas que a IA encontrou, pega a foto principal de cada uma, descarta o que não é foto ou é pequeno demais e mostra as opções. A foto escolhida entra no item como **foto ilustrativa**, com o site de onde veio, na ficha do item e no relatório. Para o seguro, uma foto sua do item continua valendo mais. A mesma foto não aparece duas vezes (também em outro tamanho ou com outro nome de arquivo). Num consumível, a busca não traz valor e sugere uma categoria dos consumíveis.

Na mesma chamada, a IA também descreve o produto que achou: nome com marca e modelo, detalhes, categoria e um valor estimado. A janela mostra o que vai para o item, já marcado em **Preencher também**, e dá para desmarcar. Os dados só preenchem o que está vazio: num item novo, o nome também vem da IA; num item que já existe, o nome e um valor já dado não mudam. **Usar só os dados, sem foto** preenche sem escolher foto, e serve também quando a busca não acha fotos. No editor, o aviso tem **Desfazer**.

A IA precisa ter a **busca na web** ligada:

- **Anthropic**: nas opções da tarefa de IA, ligue **Enable web search**.
- **Google Gemini**: a Pesquisa Google só funciona num assistente de conversa. Ligue **Enable Google Search tool** nele e escolha esse assistente.
- **OpenAI**: nas opções da tarefa de IA, ligue **Enable web search** (precisa do gpt-4o ou de um modelo mais novo).

Escolha a IA em **Mais > Configurações > Integrações > IA > Para pesquisar na internet** (vale para as fotos da internet e para as novidades). "Igual à de conversar" usa a mesma da Conversa; para o Gemini, escolha o assistente de conversa na lista.

A IA recebe só o nome, o começo dos detalhes e a quantidade do item. O app baixa as fotos apenas de endereços públicos da internet (nunca da rede da casa) e guarda só a foto que você escolher; as outras são apagadas em até 30 minutos. Cada busca usa a busca na web da sua IA, que pode ter custo à parte.

## Novidades do produto

Na ficha de um eletrônico, a seção **Novidades** (**Buscar novidades**) pede à IA de busca (a mesma da busca de fotos, em Mais > Configurações > Integrações) o que saiu nos últimos 12 meses e o que já foi anunciado para os próximos meses sobre o produto: atualizações de firmware ou software, modelo novo, lançamentos da mesma linha, recalls e fim de suporte.

- A busca começa pela página de suporte do fabricante, nos downloads (os arquivos de firmware e de atualização do sistema, com a data), e olha também a do mesmo modelo em outro país, que costuma ter um código um pouco diferente. Se ainda assim não achar, cole o endereço da página de suporte nos **Detalhes** do item: a IA abre essa página primeiro.
- Vêm só as 3 novidades mais recentes, dos últimos 12 meses. Cada uma vem com o tipo, a data quando se sabe e o site da fonte, que abre fora do app. Sem fonte, não entra. Rumor aparece marcado como **Boato**; recall fica em destaque, mas só quando o produto é chamado de volta (troca, conserto ou reembolso); falha de segurança corrigida por atualização aparece como Atualização.
- A IA só acha o que já foi publicado: lançamento que ainda não foi anunciado não aparece.
- As novidades aparecem na própria ficha e ficam guardadas: ao abrir a ficha de novo, já estão lá, sem chamar a IA. **Buscar de novo** pergunta outra vez; fechar a ficha no meio da busca não perde o resultado. Cada busca conta em Uso da IA.
- **Mais > Novidades** confere todos os itens da categoria Eletrônicos de uma vez: toque em **Conferir novidades**. A IA escolhe, entre os eletrônicos, os que vale conferir e o app confere um por um, mostrando o andamento; **Parar** guarda o que já foi conferido. O que foi conferido nos últimos 7 dias fica para a próxima. Cada conferência compara com a anterior do mesmo item: o que não estava lá vem marcado **Nova** na janela do item, e na lista o equipamento diz quantas são novas (*2 novas de 3*, com o número na cor do app); os que só têm o que você já viu dizem *3 novidades*, com o número sem cor. Abrir as novidades de um equipamento ou de um app (a janela ou a ficha) mostra o **Nova** daquela vez; depois, elas contam como vistas. A lista mostra recall primeiro, depois os com novidades novas, depois os com novidades já vistas; o resumo (*Conferido hoje 21:52: 2 de 14 com novidades novas*) e o aviso no celular contam só os com novidades novas. Tocar num item abre o que foi achado, com **Ver item** para ir à ficha dele (o Voltar volta para as Novidades). Os que a IA deixou de fora ficam no fim, recolhidos em **Deixados de fora pela IA**, com quantos são; um toque abre (e fica aberto enquanto você estiver na tela), e dá para conferir cada um sozinho: conferido, ele sobe para a lista e entra nas próximas conferências. Itens de outras categorias não entram, nem na lista; dá para conferir um deles pela ficha. O mesmo equipamento em vários cômodos (ou escrito no plural, como "Lâmpadas …", com a cor no nome ou com as palavras em outra ordem, como "Echo Spot (2024) preto" e "Echo Spot 2024") é uma linha só e uma busca só, e o resultado aparece na ficha de cada um.
- Com mais de 6, **Equipamentos** e **Eletrônicos** (em **Mais > Novidades**) têm uma busca no alto, como a dos apps: **Buscar equipamento** e **Buscar eletrônico** filtram pelo nome, pelo código (SAL-003) ou pelo cômodo, sem acento; um deixado de fora pela IA que bate abre a lista dele.
- **Apagar**, na janela das novidades de um equipamento (ao lado do **Buscar de novo**) e na ficha do item, apaga as novidades daquele equipamento (e do mesmo equipamento nos outros cômodos), com confirmação. Elas não voltam nas próximas conferências; o que sair de novo aparece. Na lista, ele passa a dizer *Nada novo* e vai para o fim.
- **Limpar novidades** (com confirmação) apaga o que foi encontrado, as escolhas da IA e as novidades apagadas (elas podem voltar), e para a conferência em andamento. O inventário não muda, e o **Conferir sozinho** continua contando da última conferência. Com os apps do celular ligados, **Só equipamentos** e **Só apps** limpam só um lado; dos apps, o que você escolheu acompanhar ou deixar de fora continua.
- Em **Mais > Configurações > Opções > Novidades**:
  - **Usar novidades** liga e desliga tudo: desligadas, somem do menu Mais e da ficha, e nada é conferido.
  - **Conferir sozinho** faz o app conferir os eletrônicos sozinho, do mesmo jeito do botão **Conferir novidades**, no **Horário** escolhido (de meia em meia hora; 10:00 de início) e **A cada** 7, 15 ou 30 dias, contados da última conferência. Quando a conferência dá erro, como cota da IA esgotada, o app tenta de novo em 6 horas.
  - **Avisar no celular** (aparece com **Conferir sozinho** ligado) manda um aviso quando essa conferência acha algo novo. Em **Quem recebe**, toque nas pessoas da casa (uma ou várias); ligar o aviso sem ninguém escolhido começa com você. O aviso vai para os celulares ligados a cada pessoa no Home Assistant (**Configurações > Pessoas**), como nos outros apps da família; quem não tem celular ligado aparece como "sem celular". O aviso diz "Novidades em 3 itens. Toque para abrir." e, ao tocar, abre o InventarIA em Novidades. **Testar no meu celular** manda um aviso na hora para quem está usando o app, em todos os celulares ligados a essa pessoa no Home Assistant (um celular antigo, um tablet ou um relógio com o app Home Assistant também contam; tire os que não usa em **Configurações > Pessoas**), mesmo fora de **Quem recebe**.
- Quanto mais o nome do item tiver marca e modelo, como na nota fiscal, melhor a busca. O app mostra como a IA identificou o produto.

### Apps do celular

Com **Apps do celular** ligado (Mais > Configurações > Opções > Novidades, desligado de início), as Novidades acompanham também os apps que vocês usam no celular (Android):

- O InventarIA lê o sensor **Último app usado** do app Home Assistant de cada celular. Ligue o sensor em cada celular: no app Home Assistant, **Configurações > Aplicativo complementar > Gerenciar sensores > Último app usado** (o Android pede o acesso ao uso dos apps).
- O app junta os apps que apareceram no sensor, pelo histórico do Home Assistant (na primeira vez, os últimos 10 dias). Logo abaixo da opção, num quadro recuado (é parte dela), **Apps detectados (n)** (recolhido; um toque abre) mostra os celulares que têm o sensor ligado e cada app achado, com de quem é o celular e quando foi usado ("novo" quando a IA ainda não escolheu; "a IA deixou de fora" quando ela deixou). A chave de cada app diz se ele entra na pesquisa das novidades: desligue para desconsiderar um app, ligue para trazer de volta um que a IA deixou de fora (a sua escolha vale sobre a da IA). Os desligados ficam no fim, recolhidos em **Inativos (n)**. **Ver novidades** busca as novidades daquele app na hora, ou mostra o que já foi achado. **Renomear** (o lápis), ao lado, troca o nome do app (vale na lista, nas Novidades e na busca da IA); apagar o nome volta ao de antes. **Apagar** (a lixeira) tira o app da lista, com o que foi achado dele; ele volta se for usado de novo no celular. Com mais de 6 apps, **Buscar app** acha um pelo nome ou pelo pacote (um que está em Inativos abre a lista). **Encontrar apps com IA** (com a IA ligada) adiciona apps sem esperar o sensor: escolha prints da lista de apps do celular (a gaveta de apps, a tela inicial ou a Google Play) ou cole os nomes; a IA lê, os que já estão vêm desligados e os do sistema desmarcados, e você marca quais entram (acompanhados, com "pela IA"). Para um app entrar, basta abri-lo uma vez e deixar aberto por alguns minutos: o sensor é atualizado de tempos em tempos, e um app aberto só por alguns segundos pode não aparecer.
- Em **Mais > Novidades**, a seção **Apps do celular** mostra cada app com o nome da pessoa dona do celular (pelo rastreador do mesmo aparelho, em **Configurações > Pessoas**). Na conferência, a IA deixa de fora o que não vale acompanhar (tela inicial, configurações, teclado e outras partes do sistema): esses não aparecem aqui, só em **Apps detectados**, em Inativos. Com mais de 6 apps, **Buscar app** no alto da lista filtra pelo nome ou pelo pacote. Um app aparece uma vez só: dois pacotes com o mesmo nome (o que a IA achou num print e o que o celular usa) viram um, o do celular, com o nome dado, a escolha e as novidades do outro.
- A IA busca, para cada app, o que mudou nos últimos 12 meses e o que foi anunciado: recursos novos, mudanças, planos e preços (mesmo que saiam em outro app ou no site da mesma empresa) e fim de recurso. Fica de fora o que é só de outro país, só de teste fechado (beta, acesso antecipado) e o texto genérico de atualização da loja.
- Tocar num app mostra as novidades, com **Buscar de novo** e **Deixar de fora** (sai da lista e da conferência). **Apagar**, embaixo, apaga as novidades achadas daquele app, com confirmação: elas não voltam nas próximas conferências, e o que sair de novo aparece (o app continua acompanhado). Num deixado de fora (aberto pelo **Ver novidades** em Inativos), **Acompanhar** o traz de volta e busca na hora. A sua escolha vale sobre a da IA e fica mesmo depois de **Limpar novidades**.
- Com os apps, **Mais > Novidades** tem três botões: **Todas as novidades** (os equipamentos e os apps), **Só equipamentos** e **Só apps**. **Conferir sozinho** e **Avisar no celular** valem para os apps também: o aviso diz, por exemplo, "Novidades em 2 itens e 1 app".

## Seções que fecham

Em Mais e em Configurações, um toque no cabeçalho de uma seção fecha ou abre a seção. O aparelho lembra quais ficaram fechadas.

## Conversar

O balão ao lado do microfone, no alto da tela (e na ficha do item), abre uma conversa com a IA. Pergunte sobre o que está na tela ("qual o item mais caro daqui?", "vale pôr no seguro?") ou sobre qualquer outro assunto. A IA recebe o resumo da casa e o que está na tela: o item, o cômodo com os itens, a busca ou as novidades. Os valores são os mesmos da tela: com o **Valor de hoje** ligado, o de hoje; os **Bens** vão à parte, não como um cômodo. Ela responde, mas não muda o inventário.

- Responde a IA **Para conversar** (Mais > Configurações > Integrações > IA).
- Com o microfone da conversa (o botão redondo da direita, com a caixa vazia; escrevendo, ele vira o Enviar), dá para falar a pergunta. Ouvindo, o botão da direita vira o **Pronto** (manda o que foi dito) e o da esquerda, o **Cancelar** (para o microfone sem mandar nada).
- O **clipe**, à esquerda da caixa, manda junto uma foto ou um PDF: **Tirar foto**, **Escolher fotos** (a galeria, até 4) ou **Escolher arquivo** (uma foto ou um PDF, como o manual ou a nota fiscal). Com arquivo, responde a IA **Para ler fotos e PDFs**. Na conversa fica só o nome do arquivo.
- **Perguntas prontas**: na conversa vazia aparecem 6 perguntas da tela para tocar; o botão ✨ ao lado da caixa abre as mesmas a qualquer momento. Em **Editar perguntas**, toque numa pergunta para mudar o texto, o ✕ tira uma pergunta e **Adicionar** põe outra (aí valem em todas as telas); **Padrão** volta às de cada tela. Embaixo, **Mais perguntas (20)**: um toque põe a pergunta na lista. **Perguntas prontas** e **Mais perguntas** fecham e abrem num toque no título. Fica tudo guardado no aparelho.
- A IA vê todos os itens (o cômodo, a categoria, o valor, a observação e quem cadastrou) e o total de cada categoria, de qualquer tela.
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
- **Tarefas no ResolvIA**: com **Usar equipamentos** ligado lá, a ficha de cada item daqui tem **Tarefas no ResolvIA** (acima das Novidades): as tarefas abertas ligadas ao item (com a lista e o prazo) e **Nova tarefa**. Escreva o que fazer, toque na lista (todas à vista, com os nomes e as cores do ResolvIA, sem as desmarcadas lá; com o ResolvIA 2.57.0 ou mais novo) e escolha o prazo (**Sem prazo**, **Hoje**, **Amanhã**, **Em 7 dias**, **Em 30 dias** ou **Outra data**, que abre o mês para escolher o dia; ele só aparece com **Controlar prazos** ligado no ResolvIA e numa lista que aceita prazo) e toque em **Criar tarefa**. Se a lista já tem uma tarefa aberta com esse nome, o app não cria outra igual: liga este item a ela, junto dos que já estavam (no ResolvIA, tarefas de mesmo nome numa lista são uma só). Assim dá para ter uma tarefa para vários equipamentos: crie em um e repita o nome nos outros. Tarefas iguais repetidas na lista aparecem uma vez, com **n iguais na lista**. Nas listas que não aceitam data (as da Alexa), o prazo fica guardado no ResolvIA (2.59.0 ou mais novo), com o aviso "Guardado no ResolvIA: a lista não aceita data." A tarefa entra na lista e fica ligada ao item e ao cômodo no ResolvIA, como se tivesse sido criada lá.
- **GerencIA** (1.19.0 ou mais novo): soma os valores dos itens e dos bens no patrimônio, como **Bens da casa** (imóveis não perdem valor; veículos perdem 15% ao ano, e dá para mudar lá). Lê o valor e a data em que ele mudou e deprecia por categoria (eletrônicos perdem mais rápido que móveis, por exemplo). Dá para desligar lá, em **Mais > Integrações > Bens no InventarIA**.

## Valor de hoje (GerencIA)

Com o **GerencIA** (1.55.0 ou mais novo) no mesmo Home Assistant, aparece em **Mais > Configurações > Integrações** o cartão **GerencIA**, com **Valor de hoje** (vem desligado). Ligado:

- cada valor perde, por ano, a taxa da categoria dele que está no GerencIA (em **Mais › Invest › Valor dos bens por ano**, lá), composta, desde a data em que o valor mudou aqui. Uma taxa negativa valoriza (um imóvel, por exemplo); uma categoria que o GerencIA não tem perde 10%;
- a Agora mostra **Patrimônio hoje**, e os cômodos, a busca, os gráficos e o relatório (também o PDF, que diz "valor de hoje") usam o valor de hoje;
- a ficha do item mostra o valor de hoje e, embaixo, o valor que você informou, a data e a taxa ("R$ 1.800 em 02/10/2026, −20% ao ano").

O valor gravado não muda: ao editar, você vê e muda o valor que informou, e os outros apps continuam recebendo esse valor. Desligar volta tudo para o valor gravado.

## CorrerIA

O **CorrerIA** é o app da família que liga o inventário ao WhatsApp, ao Claude e ao Gemini. Pelo WhatsApp ou numa conversa com o Claude ou o Gemini, dá para perguntar "quanto vale o que tem na sala?", "onde está a bicicleta?" ou pedir "cadastra uma rede de R$ 150 na varanda".

1. Aqui, em **Mais > Configurações > Integrações > CorrerIA**, ligue **Usar com o CorrerIA** (vem desligada). Não precisa da IA do InventarIA: quem pensa é a IA do CorrerIA, o Claude ou o Gemini.
2. No app **CorrerIA**, conecte o WhatsApp, o Claude ou o Gemini. O InventarIA aparece lá sozinho.

O que dá para fazer: ver o resumo da casa (o total, os cômodos, os bens e as categorias), buscar itens (por nome, pelo uso, cômodo, zona, categoria ou valor), ver um item, cadastrar um ou vários itens num cômodo (ou em Bens, ou em Consumíveis), editar (nome, valor, quantidade, categoria, zona, detalhes e observação), mover para outro cômodo e apagar, criar, renomear e apagar um cômodo (vazio), anotar o **Comprei** de um consumível (o Dura até conta de hoje) e criar, mudar (nome e cor) e apagar categorias. As mudanças seguem as mesmas regras da tela: o item ganha o próximo código do cômodo, a data do valor muda quando o valor muda, e as versões automáticas continuam valendo. Pelo WhatsApp, o CorrerIA pede para você confirmar antes de gravar.

Fotos, backups e configurações não passam pelo CorrerIA. O item cadastrado assim mostra na ficha a origem **Pelo CorrerIA** e quem cadastrou. Embaixo da chave, o app mostra quem usou por último e quando ("Claude usou hoje às 9:41"). Desligar a chave corta a ligação na hora.

**Guardar a foto num item** e **ler várias coisas de uma foto** (1.93.0, com o CorrerIA 1.24.0): mande a foto e peça para guardar num item que já existe, ou para dizer o que há nela (você escolhe o que cadastrar).

**Cadastrar pela foto** (1.92.0, com o CorrerIA 1.23.0): mande a foto de um item ou de um consumível na conversa do CorrerIA e peça para cadastrar. A IA do InventarIA lê a foto (o nome, o que é, a categoria) e a foto fica no item; com a IA desligada aqui, diga o nome junto.

## Memória da IA

Em **Mais › Configurações › Integrações › Memória da IA** (com o Usar IA ligado) você escreve o que a IA deve lembrar em toda conversa: "o café é sempre o da marca azul", "a feira é no sábado". É **uma memória só, da casa, compartilhada por todos os apps** da família: o que você escreve aqui vale na Conversa e na leitura por IA dos outros apps, e o que foi escrito neles aparece aqui, com o nome do app. Cada frase tem o **Apagar**. São até 60 frases de 240 letras.

A memória fica na pasta share do Home Assistant (`share/familia/memoria_ia.json`), fora dos apps: funciona com um app só instalado, e não precisa do CorrerIA. Ela não entra no Exportar nem no Começar do zero de um app (é de todos); apague as frases pelo cartão.

## Atualizar o app

Quando sai uma versão nova, o Home Assistant mostra **Atualizar** na página do app e em **Configurações > Atualizações**. Para procurar na hora, abra **Configurações > Aplicativos > Loja de aplicativos**, toque no menu **⋮** e escolha **Verificar atualizações**. Os dados não são apagados.

## Problemas comuns

- **"A sessão do Home Assistant expirou"**: recarregue a página do Home Assistant.
- **A IA aparece como não configurada**: confira se a integração de IA tem uma tarefa de IA criada e se o modelo lê imagens; depois toque em "Verificar de novo".
- **A IA demora**: modelos locais podem levar mais de um minuto por foto. Modelos na nuvem costumam responder em 5 a 20 segundos.
- **Ver o que está acontecendo**: aba **Registro** do app.
