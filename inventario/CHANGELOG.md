# Mudanças

## 1.48.1

- **Tarefas no ResolvIA**: uma tarefa ligada a vários equipamentos aparecia repetida na ficha. Agora aparece uma vez só (com **n iguais na lista** quando a lista do Home Assistant tem mais de uma com o mesmo nome).
- **Nova tarefa** com o nome de uma que já está aberta na lista: não cria outra igual, liga este item a ela, junto dos equipamentos que já estavam. Antes, a nova tirava os equipamentos da que já existia.

## 1.48.0

- **Atalho no celular**, em **Mais › Configurações › Opções**: o caminho do InventarIA no Home Assistant, com **Copiar**, e como criar um ícone na tela inicial do celular que abre o app direto (no app do Home Assistant: Configurações › Aplicativo complementar › Gerenciar atalhos). O mesmo vale em todos os apps da família.
- **Tarefas no ResolvIA**, na ficha do item: fica acima das **Novidades**, e os botões das duas têm o mesmo tamanho.
- **Nova tarefa**: as listas aparecem todas na tela, em botões, como no ResolvIA (os mesmos nomes e cores, sem as desmarcadas lá; com o ResolvIA 2.57.0 ou mais novo). O prazo só aparece com **Controlar prazos** ligado no ResolvIA e numa lista que aceita prazo.

## 1.47.1

- **Avisos no celular**: o título fica "InventarIA · 🆕 Novidades" e o ícone pequeno é o do app. Como todos os apps chegam como Home Assistant, agora dá para ver de qual app é cada aviso. Vale para todos os apps da família.

## 1.47.0

- **Tarefas no ResolvIA**, na ficha de cada item: com **Usar equipamentos** ligado no ResolvIA (Mais › Configurações › Integrações › InventarIA, lá), a ficha mostra as tarefas abertas ligadas ao item e o botão **Nova tarefa**. Escreva o que fazer ("Trocar o filtro"), escolha a lista e o prazo (sem prazo, hoje, amanhã, em 7 ou em 30 dias) e toque em **Criar tarefa**. A tarefa entra na lista e já fica ligada ao item e ao cômodo no ResolvIA (e aparece também na CronologIA). A última lista escolhida fica lembrada.

## 1.46.0

- **Valor de hoje, com a depreciação do GerencIA**: em **Mais > Configurações > Integrações > GerencIA**, ligue **Valor de hoje** (vem desligado; o cartão aparece quando o GerencIA 1.55.0 ou mais novo está instalado). Os valores perdem, por ano, a taxa de cada categoria que está no GerencIA (eletrônicos 20%, móveis 10%, imóveis 0%…), desde a data em que o valor mudou. O Início mostra **Patrimônio hoje**, e os cômodos, a busca, os gráficos e o relatório (também o PDF) usam o valor de hoje. Na ficha, embaixo do valor de hoje, fica o valor que você informou, a data e a taxa. O valor gravado não muda.

## 1.45.1

- **Tema**: **Automático** agora se chama **Sistema** (segue o claro ou escuro do Home Assistant, como antes). O nome cabe ao lado do ícone e é o mesmo em todos os apps da família.
- **Backup na pasta share**: cada backup mostra a data e a hora em destaque e, embaixo, o tamanho e o nome do arquivo; o **Restaurar** fica ao lado, como no ResolvIA.

## 1.45.0

- **Uma altura só**: botões, campos, caixas de seleção, botões de escolha (as abas de Configurações, o Tema, o Tipo do bem) e as escolhas em botões têm a mesma altura, a mesma de todos os apps da família. O Tema ficou com o ícone ao lado do nome.

## 1.44.0

- **Mais › Configurações › Dados**: os botões no padrão dos outros apps da família: na largura do cartão no celular, da mesma altura, sem a linha com o título repetido em cima de cada um. **Apagar tudo** fica vermelho.

## 1.43.0

- **Opções › Novidades**: o aviso no celular igual ao dos outros apps da família. **Conferir sozinho** liga e desliga, com o **Horário** (sem AM/PM) e **A cada** 7, 15 ou 30 dias lado a lado; **Avisar no celular** liga o aviso; em **Quem recebe**, um botão para cada pessoa da casa (dá para escolher várias); **Testar no meu celular** fica embaixo, na largura toda. Quem já recebia o aviso continua recebendo.

## 1.42.0

O padrão da família de apps:

- **Configurações** abre em **Integrações**, com as abas na ordem Integrações › Dados › Aparência › Opções. Em Integrações, o **CorrerIA** vem primeiro, antes da IA do Home Assistant.
- **Dados › Começar do zero** (novo, no fim): apaga os cômodos, os bens e os itens depois de confirmar. Antes, o app guarda uma cópia em **Versões anteriores**; as categorias e as opções continuam. Na casa vazia, o botão que criava o primeiro cômodo agora se chama **Criar o primeiro cômodo**.
- **Aparência**: a **cor do app** vale para a casa toda (antes, só para o aparelho); na primeira vez, fica a que este aparelho já usava. As cores são as 12 da família: Vermelho, Coral, Laranja, Ouro, Verde, Menta, Turquesa, Azul, Índigo, Lilás, Rosa e Grafite. Uma cor que saiu vira a mais parecida (Amarelo: Ouro; Kraft: Coral; Cinza: Grafite). A **Cor do dia** é a mesma em todos os apps. O tema continua em cada aparelho.
- **Apagar** no lugar de Excluir (item, cômodo e categoria); **Escolher fotos** no lugar de Galeria e Enviar foto; **Digitalizar com IA** no lugar de Ler foto e Preencher com IA; **Criar backup** no lugar de Criar backup agora; **Apagar foto** no botão da lixeira das fotos do cômodo (antes dizia Tirar foto, o mesmo nome da câmera).
- **Opções › Novidades › Testar no meu celular**: o aviso de teste vai para o celular de quem está usando o app.

## 1.41.0

- **Zona** (no cadastro, no **Mover** e no **Catalogar itens com IA**): as sugestões das zonas do cômodo aparecem logo abaixo do campo, no visual do app, em vez da lista do celular. Até 6, as que combinam com o que você digita (sem precisar de acento); num campo que já tem uma zona, as outras. Tocar numa preenche o campo, e o teclado não fecha.
- As caixas de seleção fechadas ficam iguais aos outros campos: os filtros do **Buscar** com a mesma altura, e a seta na cor certa no tema escuro.
- **Mais › Novidades**: **Deixados de fora pela IA** continua aberto depois de conferir um deles, para conferir o próximo. Ao voltar à tela, começa recolhido.

## 1.40.0

- **Buscar › Selecionar** como no ResolvIA: embaixo, um botão só, **Alterar N itens**, abre uma janela com **Cômodo**, **Categoria** e **Zona** (com as zonas ligadas). Cada um começa em **Manter**; dá para mudar o cômodo e a categoria juntos. Na zona, as zonas do cômodo aparecem como opções, além de **Sem zona** e **Outra**. No alto, o **X** sai do Selecionar e **Todos** marca a lista inteira (de novo, **Nenhum**). O aviso diz quantos itens foram alterados e tem **Desfazer**.

## 1.39.4

- **Novidades**: a busca começa pela página de suporte do fabricante, nos downloads, onde ficam os arquivos de firmware e de atualização do sistema com a data, e procura também a página do mesmo modelo em outro país quando a do Brasil não mostra os arquivos. Se a busca ainda não achar, cole o endereço da página de suporte nos **Detalhes** do item: ela é aberta primeiro.

## 1.39.3

- **Mais › Novidades**: um item dos **Deixados de fora pela IA** que você conferiu sobe para a lista, com o que foi achado, e passa a entrar nas próximas conferências. Antes ele ficava embaixo, como se não tivesse sido conferido.

## 1.39.2

- **Mais › Novidades**: o mesmo eletrônico escrito de jeitos um pouco diferentes vira uma linha só e uma busca só, como "Amazon Echo Spot (2024) preto" e "Amazon Echo Spot 2024". A cor, os parênteses, palavras como "de" e "com" e a ordem das palavras não separam mais. O ano, a marca e o tamanho continuam separando.

## 1.39.1

- **Buscar**: segurar o dedo num item começa o **Selecionar** com ele marcado, como no ResolvIA.

## 1.39.0

- **Buscar › Selecionar**: muda vários itens de uma vez. Toque nos itens, ou em **Selecionar todos** para a lista inteira, e embaixo em **Cômodo**, **Categoria** ou **Zona** (com as zonas ligadas). O aviso tem **Desfazer**. Em outro cômodo, cada item ganha um código novo e fica sem zona. Os bens ficam de fora. O Voltar do celular ou **Cancelar** saem do Selecionar.
- **Mais › Novidades**: um item que deixa de ser eletrônico sai da lista na hora.

## 1.38.4

- Corrigido: no **Editar item** e no **Mover**, o **Cômodo** e a **Categoria** não mudavam. A janela das opções abria atrás da janela do item e não recebia o toque. Agora abre por cima, e o Voltar do celular fecha só ela.

## 1.38.3

- **Mais › Sobre**: a CorrerIA agora é descrita como o chat com todos os apps (pergunte e peça, também pelo WhatsApp).

## 1.38.2

- **Mais › Novidades**: a janela das novidades de um item ganha **Ver item**, que abre a ficha dele. O Voltar do celular volta para as Novidades. O **Fechar** saiu: o X no alto e o Voltar fecham.

## 1.38.1

- **Mais › Sobre**: a **CorrerIA** (o contato no WhatsApp) entra na lista dos apps.

## 1.38.0

- **Falar** não pergunta mais o cômodo: a IA conhece os cômodos da casa e põe cada item no seu, pelo que você falou ("na sala", "e na cozinha a batedeira") ou pelo objeto (a geladeira vai para a cozinha). Na hora de conferir, cada item mostra o cômodo; o que a IA não souber vem com **Qual cômodo?** para você escolher. O **Cômodo** do alto muda todos de uma vez.
- **Catalogar itens com IA**: fora de um cômodo, o **Cômodo** vem em **A IA escolhe**, e a IA reconhece o cômodo pela foto. Se não souber, você escolhe na hora de conferir.
- **+ Adicionar** na aba **Cômodos** e dentro de um cômodo mostra só o que é item: **Adicionar bem** fica no Início e nas outras telas.

## 1.37.0

- **Mais > Configurações > Integrações > CorrerIA**: nova chave **Usar com o CorrerIA**, desligada de início. Ligada, o InventarIA aparece no app **CorrerIA**, e o WhatsApp, o Claude e o Gemini passam a ler e mudar o inventário: o resumo da casa, buscar e ver itens, cadastrar, editar, mover e apagar itens e criar cômodos. Não depende do **Usar IA**, porque quem pensa é a IA de lá.
- Embaixo da chave aparece quem usou por último e quando, como "Claude usou hoje às 9:41".
- O que muda pelo CorrerIA aparece na tela sozinho. Na ficha, o item cadastrado assim mostra a origem **Pelo CorrerIA** e quem cadastrou.
- Nada de fotos, backups ou configurações pelo CorrerIA. As fotos continuam pela tela do app.

## 1.36.3

- **+ Adicionar**: **Adicionar bem** passa para o fim, porque é a única opção que mexe com bens. **Catalogar foto com IA** passa a se chamar **Catalogar itens com IA**, aqui, nos cômodos e no Uso da IA. Fica claro o que é item e o que é bem.
- Saíram textos que não precisavam estar ali: "Usada nas novidades" em Eletrônicos e "Vale para todos os aparelhos" em Categorias, Usar IA, Usar bens e Usar zonas.

## 1.36.2

- **Relatório › Baixar PDF** funciona no app do Home Assistant no celular: o PDF vai para a pasta Downloads (aparece nas notificações), com o aviso **Baixando o PDF…**.

## 1.36.1

- O **Relatório para seguro** passa a se chamar **Relatório do inventário**: no menu Mais, na tela e no PDF.

## 1.36.0

- **Relatório para seguro** no padrão dos relatórios dos apps (como o do ResolvIA e o do GerencIA): no alto, um cabeçalho com o ícone, o app, o título, quantos itens e cômodos e quando; depois os números, os gráficos da tela **Gráficos** (cômodos, categorias, faixas de valor, os itens mais valiosos e, com bens, os bens) e um cômodo depois do outro. No fim, a marca da **CorrerIA Code**, como no **Mais > Sobre**.
- **Baixar PDF** no lugar do Imprimir: o app do Home Assistant no celular não imprimia a página. O PDF é feito pelo app, com o mesmo relatório (com as fotos, ou sem elas com **Mostrar fotos** desmarcado), na cor do app e com o número de cada página.

## 1.35.0

- **Caixas de seleção** (os filtros da busca, cômodo e categoria do item, Mover, a IA usada, Fala para texto, Conferir sozinho, Avisar) abrem uma janela no visual do app, de baixo para cima, com as opções em linhas e a atual marcada na cor do app, no tema claro ou escuro, e não mais a janela padrão do celular, como nos outros apps da família. O Voltar do celular, o X ou tocar fora fecham só ela.

## 1.34.0

- **+ Adicionar**: nova opção **Adicionar bem**, logo depois de Adicionar item.
- **Mais > Configurações > Opções > Usar bens**: desligado, os bens somem de tudo:
  - do menu Mais, do Início, da busca, dos gráficos, do relatório e da conversa com a IA;
  - do ResolvIA, da CronologIA e do patrimônio do GerencIA.

  Desligar não apaga os bens. Ao ligar de novo, eles voltam como estavam.

## 1.33.1

- **Buscar**: os filtros não cortam mais o texto, como em "Todas as categorias". Em celulares estreitos a letra fica um pouco menor e, nos bem estreitos, vem um filtro por linha.

## 1.33.0

- **Buscar**: com bens cadastrados, o filtro **Tipo** vem antes do de cômodos: Itens da casa, Imóveis, Veículos ou Outros bens. Num tipo de bem, os filtros de cômodo e categoria saem, e **Bens** sai da lista de cômodos.
- **Mais > Bens**: sai o botão Adicionar bem do alto da lista. O **+ Adicionar** de baixo já adiciona um bem nessa tela.
- O botão **Novidades** da ficha só aparece nos **Eletrônicos**, como a lista de Novidades.
- **Mais > Gráficos**: os bens saem de Cômodos, Categorias, Faixas de valor e Itens mais valiosos, que agora mostram só o que está dentro de casa. Os bens ganham um gráfico só deles. O patrimônio do alto continua somando tudo e diz quanto está em bens.
- **Mais > Categorias**: **Eletrônicos** não se renomeia nem se exclui, porque é a categoria das novidades. Se tiver sido excluída antes, ela volta.

## 1.32.1

- **Novo bem** e **Editar bem**: sem **Cômodo** e sem **Categoria**. No lugar, só o **Tipo**: Imóvel, Veículo ou Outro. Um item que veio de um cômodo pelo **Mover** fica em Outro e guarda a categoria que tinha. O botão diz **Salvar bem**.

## 1.32.0

- **Opções > Novidades > Avisar**: agora você escolhe a **pessoa** (ou **Todos**), não o aparelho, como no ResolvIA e na CronologIA. O aviso vai para os celulares ligados a ela no Home Assistant (**Configurações > Pessoas**). Quem não tem celular ligado aparece como "sem celular". Saiu a opção Notificação do Home Assistant.

## 1.31.2

- **Falar** sem uma IA pronta no Home Assistant: **Adicionar > Falar os itens** e o painel **Falar** (Integrações) dizem que o app separa pelas vírgulas, em vez de "a IA separa os itens".

## 1.31.1

- **Opções > Novidades**: **Avisar** e **Testar** só aparecem com **Conferir sozinho** ligado. Com "Não", nada avisaria.
- **Mais**: o Relatório para seguro só diz "com fotos" quando **Mostrar fotos** está marcado.

## 1.31.0

- **Mais > Bens**: casa, apartamento, terreno, carro, moto, tudo o que tem valor e fica fora de casa.
  - **Adicionar bem** abre o cadastro de sempre.
  - A lista separa **Imóveis**, **Veículos** e **Outros**, cada um com o total. As categorias Imóveis e Veículos são novas.
  - Os bens entram no patrimônio do Início, que ganha uma lista **Bens**, nos gráficos e na busca. Ficam fora da lista de cômodos.
  - No **relatório para seguro**, os bens vêm numa seção à parte, no fim, com o total deles. O total da casa não muda.
  - **Mover** leva um item para Bens, e Desfazer traz de volta.
- No ResolvIA e na CronologIA, **Bens** aparece ao lado dos cômodos, e uma tarefa pode ser ligada a um bem. O GerencIA soma os bens no patrimônio: imóveis não perdem valor e veículos perdem 15% ao ano.
- No Início e em Cômodos, a parte de cada cômodo é a do que está dentro de casa.

## 1.30.0

- **Mais > Configurações > Opções > Novidades**:
  - **Usar novidades** liga e desliga o recurso. Desligadas, as novidades somem do menu Mais e da ficha do item.
  - **Conferir sozinho**: toda semana, a cada 15 dias ou todo mês, o app confere os eletrônicos sem você pedir.
  - **Avisar**: quando essa conferência acha algo novo, chega um aviso no celular escolhido (ou na notificação do Home Assistant): "Novidades em 3 itens. Toque para abrir." Tocar abre o InventarIA direto em Novidades. **Testar** manda um aviso na hora.
- Com **Usar IA** desligada, o **Falar** também some: o microfone no alto e "Falar os itens" em Adicionar. Sem IA e sem Falar, **Adicionar** abre direto o item novo.

## 1.29.0

- **Mais > Sobre**, a última linha do menu: quem faz o app (**CorrerIA Code**, desenvolvimento de softwares, e por que esse nome), os apps da família (CronologIA, ResolvIA, GerencIA, InventarIA, EconomIA e MemorIA), cada um com uma linha e o link para o GitHub, e o botão **Meu GitHub**. O InventarIA aparece marcado com a versão instalada.

## 1.28.1

- **Início** mais curto: Categorias e Mais valiosos saíram, porque já estão em Mais > Gráficos. Ficam a etiqueta do patrimônio, a busca, os destaques, os cômodos e os cadastrados recentemente.

## 1.28.0

- **Mais > Gráficos**: o patrimônio, os itens, o valor médio e quantos têm foto no alto; os cômodos e as categorias que mais valem, do maior para o menor, com o valor e a parte do total; as faixas de valor; os 10 itens mais valiosos; e o patrimônio mês a mês. Tocar numa linha abre o cômodo, a categoria ou o item. No computador, os gráficos ficam lado a lado.

## 1.27.0

- **Novidades**: o mesmo equipamento em vários cômodos (ou escrito no plural) agora é uma linha só, com uma busca só. O resultado aparece na ficha de cada um.
- **Recall** só quando o produto é chamado de volta (troca, conserto ou reembolso). Falha de segurança corrigida por atualização aparece como Atualização. Vale também para o que já estava guardado.
- Novidades com mais de 12 meses saem, também das já guardadas.

## 1.26.0

- **Mais** agora é um menu: **Novidades**, **Categorias**, **Relatório para seguro** e **Configurações**, cada um na sua tela, com o caminho de volta para Mais no alto.
- **Configurações** fica com as abas Dados, Integrações, Aparência e Opções (as zonas). Novidades e Categorias saíram de lá, e o Relatório saiu de Dados.
- Os endereços antigos (como Mais > Integrações) levam para o lugar novo.

## 1.25.0

- **Novidades na ficha do item**: o que já foi conferido aparece direto na ficha, embaixo dos dados, sem abrir outra janela e sem chamar a IA. **Novidades** (ou **Buscar de novo**) procura ali mesmo; fechar a ficha no meio da busca não perde o resultado.

## 1.24.0

- **Mais > Novidades**: só Eletrônicos, sem escolher categorias. A lista de categorias saiu; itens de outras categorias não entram, nem na lista (pela ficha, dá para conferir qualquer item).

## 1.23.0

- **Cor do dia**, em Mais > Aparência: a cor do app muda todo dia (a mesma o dia todo, em todos os aparelhos), sem o cinza. Vem ligada. Escolher uma cor desliga; ligar de novo volta à cor do dia.
- No celular estreito, as chaves de Mais ficam à direita, na linha do nome.

## 1.22.0

- **Novidades**: vêm só as 3 mais recentes de cada equipamento. As já guardadas também passam a mostrar só as 3.
- Recall só quando é oficial (do fabricante ou de um órgão como o Procon), para não marcar recall à toa.
- **Mais > Novidades**: de início, só Eletrônicos. A lista mostra só os itens das categorias marcadas.
- **Limpar novidades** (com confirmação): apaga o que foi encontrado e as escolhas da IA, para começar do zero.

## 1.21.1

- Um pedido torto (de um programa que não é o navegador) recebe a resposta de erro completa.

## 1.21.0

- **Conversar**: o balão ao lado do microfone abre uma conversa com a IA, em qualquer tela, sobre o que está nela ou outro assunto. A IA vê o item, o cômodo, a busca ou as novidades da tela e o resumo da casa, mas não muda o inventário. Dá para falar a pergunta.
- **Mais > Novidades**: confere as novidades de todos os equipamentos de uma vez. A IA escolhe, nas categorias marcadas, o que faz sentido (sem móveis, panelas, cestos), e o app confere um por um, com o andamento e Parar. O resultado fica guardado; o que já foi conferido na semana fica para a próxima.
- Cota da IA acabada e Home Assistant sem resposta: avisos em português, sem mandar configurar a IA de novo.
- Preencher com IA não troca mais os detalhes, o valor e a quantidade que você já escreveu.
- Tirar uma foto do cômodo que vem antes da capa não troca mais a capa.
- No Editar cômodo, as legendas das fotos ficam alinhadas.
- Abas de Mais com o nome inteiro; no celular estreito, a barra rola para o lado.
- Com uma janela aberta no computador, o fundo escurece inteiro, sem a faixa clara da barra de rolagem.
- Desfazer depois de excluir volta o item com as datas de antes (o GerencIA não recomeça a depreciação). Renomear ou mover um item também não muda a data do valor.
- O número de um item excluído não volta para outro item (o ResolvIA liga tarefas pelo número).
- O app abre mesmo com o inventário, uma versão anterior ou as configurações corrompidos (volta à última versão boa e guarda o arquivo estragado).
- Backups com espaço ou parênteses no nome (como "inventario (1).zip") aparecem na lista; backup com foto estragada dá aviso claro.
- Nome de usuário com acento aparece certo.
- **Mover** agora tem Desfazer: volta o cômodo, a zona e o código.
- Arquivo que não é foto e a 13ª foto de um item avisam, em vez de sumir calados.
- Busca: ao digitar, a ordem mostrada passa para Mais relevantes, como a lista; um link com cômodo que não existe mostra todos.
- Cadastro: trocar o cômodo não leva a zona do cômodo anterior.
- Detalhes compridos (um endereço, por exemplo) quebram a linha na ficha.
- Teclado: Enter cria o cômodo; depois de salvar, o foco volta para Adicionar item. Melhor leitura de tela nas fotos do cômodo.
- Vários erros raros que davam "Erro interno" agora dão um aviso claro.

## 1.20.0

- **Novidades** na ficha do item: a IA de busca procura o que saiu nos últimos 12 meses e o que já foi anunciado sobre o produto (atualizações de firmware ou software, modelo novo, lançamentos, recalls e fim de suporte), cada um com a data e o site da fonte. Boato vem marcado; recall fica em destaque. Com a IA desligada, o botão some.

## 1.19.1

- Relatório no celular estreito (320 px): a tabela cabe na tela, sem a página encolher.

## 1.19.0

- **Falar sem IA** entende valor por extenso: "dois mil reais", "três mil", "mil e duzentos reais" viram o valor do item. Quantidade por extenso ("duas luminárias") continua no nome. "Cafeteira por 499 reais" e "abajur que custou 2 mil" ficam só Cafeteira e Abajur.
- Valor digitado como "1.200" é mil e duzentos, como na tela (antes podia virar 1,2).
- Celular estreito (320 px): no cômodo, os botões Adicionar, Catalogar e Editar cabem sem a página encolher; no Editar cômodo, os botões de cada foto descem para baixo da legenda.
- Importar em Mais: ao terminar, abre o Início.
- Mais > Integrações aberta direto: o Falar não fica mais em "Verificando…".
- Adicionar vários itens de uma vez (Catalogar, Falar) e salvar Integrações: se algo está errado, nada fica pela metade.
- Testes automáticos de tudo (servidor, integração com o Home Assistant e as telas), rodando a cada mudança no GitHub.

## 1.18.1

- Catalogar foto com IA: o aviso "Parece já cadastrado" com um nome comprido quebra em duas linhas dentro do selo, em vez de passar por cima da borda.

## 1.18.0

- **Tirar foto** no app do Home Assistant para Android, como no ResolvIA: abre a câmera do próprio InventarIA, em tela cheia, com lanterna quando o celular tem. No cadastro do item e nas fotos do cômodo dá para tirar várias e tocar em Pronto; no Catalogar foto com IA, uma foto já volta para a leitura. No navegador do celular, continua a câmera do aparelho.
- Saiu o aviso "As fotos vêm da galeria: tire antes com a câmera".

## 1.17.0

- **Categorias** em Mais > Opções: renomeie, crie ou exclua as categorias da casa. Cada uma mostra quantos itens tem. Ao excluir, os itens vão para Outros, que não pode ser excluída.
- As categorias ficam no inventário: entram no backup, na exportação (JSON e planilha) e nas versões, valem para todos os aparelhos, e a IA passa a usar as novas ao ler fotos, ouvir e buscar na internet. O GerencIA e o ResolvIA recebem os nomes da casa.

## 1.16.0

- **Valores para o GerencIA**: a lista de itens para os outros apps (`/api/integracao/itens`, com a chave de `share/inventario`) agora traz também o valor de cada item e a data desse valor, e os nomes das categorias. O GerencIA soma os bens no patrimônio e deprecia por categoria a partir dessa data.
- O app guarda quando o valor de um item mudou (antes, só quando o item mudou).

## 1.15.0

- **Itens para os outros apps**: além dos cômodos, o ResolvIA (2.29.0 ou mais novo) pode ligar uma tarefa a um item daqui (um equipamento, um móvel…). A leitura é só da lista de itens (nome, cômodo, zona e categoria), em `/api/integracao/itens`, com a mesma chave de `share/inventario`.

## 1.14.0

- **Cômodos para os outros apps da família**: o ResolvIA pode ligar uma pendência a um cômodo daqui. O InventarIA grava `share/inventario/integracao.json` com o endereço dele na rede interna dos apps e uma chave (como o GerencIA), e responde só a leitura dos cômodos em `/api/integracao/comodos`, com essa chave. Nada mais fica aberto: a tela continua só pelo Home Assistant.

## 1.13.5

- Em Mais, os botões e as listas de escolha têm o mesmo tamanho e ficam alinhados: à esquerda no celular, à direita no computador.

## 1.13.4

- Menos texto: saíram as explicações do óbvio e os porquês que sobravam pelo app, como "o microfone aparece no alto de todas as telas", "toque na que mais parece com o seu item" e "você confere antes de salvar". Ficou só o que ajuda a decidir ou a resolver um problema.
- Os botões de Mais têm todos o mesmo tamanho, inclusive Verificar de novo, em Integrações, e Restaurar, nos backups.

## 1.13.3

- A busca do Início subiu para cima de Mais valioso: no celular, logo abaixo da etiqueta; no computador, no alto da coluna ao lado da etiqueta, com a largura da lista.

## 1.13.2

- Com **Usar IA** desligada, o painel do Falar mostra **Pronto para ouvir, sem IA** e explica que o próprio app separa os itens pelas vírgulas, sem chamar a IA. A descrição de Usar IA também diz que o Falar continua sem IA.

## 1.13.1

- Os botões das seções de Mais têm todos a mesma largura: Baixar CSV, Baixar JSON, Baixar ZIP, Abrir relatório, Criar backup, Escolher arquivo e Ver versões.

## 1.13.0

- **Falar** com escolha da fala para texto, como a escolha da IA para ler fotos: em Mais > Integrações > Falar, **Fala para texto** começa em **Padrão do Home Assistant** (a do assistente de voz preferido) e lista as que o Home Assistant tem (Home Assistant Cloud, Google AI, Whisper e outras). O app usa o português que cada uma aceita.
- O painel do Falar agora diz quem transcreve de fato. Antes mostrava o nome do assistente de voz (por exemplo, "Gemini"), o que parecia que o Falar estava preso a ele.
- Se a fala para texto escolhida sair do Home Assistant, o app volta para o padrão e avisa no painel.

## 1.12.1

- Com **Usar IA** desligada, nada do Buscar na internet passa: se a IA for desligada no meio de uma busca, as fotos e os dados do produto que ela achou não chegam ao item. O resto já respeitava a opção: sem IA, o botão Buscar na internet some da ficha e do editor, o app não chama a IA, e o Falar separa os itens pelas vírgulas.

## 1.12.0

- **Buscar na internet** traz também os dados do produto, na mesma chamada da IA (sem gastar outra): nome com marca e modelo, detalhes, categoria e valor estimado. A janela mostra o que vai para o item, já marcado em **Preencher também**; dá para desmarcar e ficar só com a foto.
- Os dados só preenchem o que está vazio. Num item novo, o nome também vem da IA (com Desfazer no aviso); num item que já existe, o nome e um valor já dado não mudam.
- **Usar só os dados, sem foto**, para quando nenhuma foto serve. Se a busca não acha fotos, os dados aparecem do mesmo jeito.
- A busca considera a quantidade do item para o valor.

## 1.11.0

- **Arrastar para o lado** troca de aba no celular, como no ResolvIA e no CronologIA: Início ⇄ Buscar ⇄ Cômodos ⇄ Mais, com a tela nova entrando pelo lado. Dentro de um cômodo, arrastar para a direita volta para Cômodos; no relatório, volta para Mais. Não vale começando na borda da tela (é o Voltar do celular), num campo, na fileira de fotos que rola para o lado ou com uma janela aberta.

## 1.10.2

- O **ícone do app** ao lado do nome, no alto da tela e na barra lateral do computador, como no ResolvIA e no CronologIA: a etiqueta com R$ e o fio, na cor escolhida em Aparência.

## 1.10.1

- **Sensores no Home Assistant**, em Mais > Integrações, agora são uma opção e vêm **desligados**. Ligada, o app cria o `sensor.inventaria_ia_hoje` (chamadas de IA de hoje). Desligada, o app não cria sensores e tira na hora o que já existia, inclusive o que as versões 1.9 e 1.10 criaram sem perguntar.

## 1.10.0

- **Falar**, como no ResolvIA e no CronologIA: o microfone no alto da tela, à direita (e em **Adicionar > Falar os itens**). Fale os itens e quanto valem; o Home Assistant transcreve com a fala para texto do Assist (Configurações > Assistentes de voz; com o Home Assistant Cloud já vem pronta) e a IA separa os itens com nome, categoria, quantidade e valor, para você conferir e adicionar. O valor que você falar vale mais que a estimativa. Dentro de um cômodo, os itens vão para ele. Sem IA, o app separa pelas vírgulas e pelo "e". Até 2 minutos por vez.
- **Mais > Integrações > Falar** mostra se o microfone está pronto e qual fala para texto ele usa. O Uso da IA conta também o Falar.
- **Versões anteriores**, como no ResolvIA: o botão **Ver versões** abre a lista, com a data, quantos itens cada versão tem e por que ela foi guardada (automática, antes de importar ou antes de restaurar), e o **Restaurar** de cada uma.
- O **Adicionar** não tem mais **Novo cômodo**: ele fica na aba Cômodos.

## 1.9.1

- No computador, abrir pelo menu uma tela que tem busca já deixa o cursor nela, pronto para digitar: Buscar, a busca do Início e o filtro do cômodo. No Início, é só começar a digitar para buscar. Ao abrir o app e no celular, nada muda.
- Com o cursor na busca vazia do Início, "/" continua abrindo o Buscar.

## 1.9.0

- **Uso da IA**, em Mais > Integrações, como no EconomIA: chamadas de hoje, dos últimos 7 dias e do mês, com tokens estimados; gráfico dos 7 dias (toque numa barra para ver o dia); tipo de uso (Preencher com IA, Catalogar foto, Buscar foto na internet); erros e cota excedida; e as últimas chamadas, com a IA, o tempo e os tokens.
- Sensor **sensor.inventaria_ia_hoje** no Home Assistant, com as chamadas de hoje e os detalhes nos atributos, para painel e automação.
- Atalho para o painel de consumo do provedor (Google Cloud Console, OpenAI ou Claude Console).

## 1.8.1

- Nova aba **Opções** em Mais, com **Usar zonas** (que saiu de Aparência). Aparência fica só com o tema e a cor do app.
- As abas de Mais acompanham o tamanho do nome, e em celular estreito a letra diminui um pouco para as quatro caberem inteiras.
- Versões anteriores: o app fica só com as 3 cópias automáticas mais recentes (antes eram 60). As mais antigas são apagadas quando o app inicia.

## 1.8.0

- **Usar IA**, em Mais > Integrações: desligada, o app esconde tudo o que usa IA (Catalogar foto com IA, Preencher com IA e Buscar na internet). Vem ligada.
- **Zonas** agora são opcionais e vêm desligadas. Ligue em Mais > Aparência para ter o campo Zona no cadastro, a zona na ficha, na busca e no relatório, e os itens de cada cômodo separados por zona. Desligadas, o cômodo mostra a lista na ordem dos códigos, e as zonas já gravadas continuam guardadas.
- Aparência com ícones nos títulos (Tema, Cor do app e Zonas) e nos botões do tema (Automático, Claro e Escuro).
- O valor do item é o que você quiser: saíram os textos de "valor de mercado de usado" do cadastro, do relatório e do Catalogar foto com IA.
- Visualizador de fotos: a foto não cobre mais o nome e o valor dos itens logo abaixo, e uma foto grande não empurra mais os botões de baixar e fechar para fora da tela.

## 1.7.4

- Ícones também nas quatro linhas abaixo da etiqueta do Início: Mais valioso, Maior cômodo, Último cadastro e Fotos, no mesmo quadradinho dos títulos.

## 1.7.3

- Ícones também nos títulos de Mais: Exportar, Backup na pasta share, Importar, Versões anteriores, Onde ficam os dados e IA do Home Assistant.
- A IA para buscar fotos na internet segue o mesmo padrão da IA para ler fotos: começa em **Padrão do Home Assistant** (a IA preferida definida lá), seguida das tarefas de IA e dos assistentes de conversa. A opção "A mesma de ler fotos" saiu.

## 1.7.2

- Ícones nos títulos do Início (Cômodos, Categorias, Mais valiosos e Cadastrados recentemente), num quadradinho no tom da cor do app.

## 1.7.1

- Exportar foi para dentro da aba Dados, como no CronologIA e no ResolvIA. Mais fica com três abas: Dados (abre primeiro, com Exportar no alto), Integrações e Aparência.

## 1.7.0

- Mais organizado em abas, como no CronologIA e no ResolvIA: **Exportar**, **Integrações**, **Dados** e **Aparência**. As abas ficam presas no alto ao rolar a página, e trocar de aba não enche o histórico: Voltar sai de Mais.
- A página "Dados e ajustes" passou a se chamar Mais, como a aba do celular, e a versão do app fica no rodapé.
- No tema escuro, a opção marcada (do tema e das abas) fica mais clara que o fundo, para dar para ver qual está ligada.

## 1.6.0

- Buscar foto na internet: num item sem foto, ou no editor do item, a IA do Home Assistant (com a busca na web ligada) procura o produto no fabricante e nas lojas, e o app mostra as fotos encontradas para você escolher. A foto fica marcada como ilustrativa, com o site de onde veio, na ficha do item e no relatório.
- Em Dados e ajustes, a seção agora se chama IA do Home Assistant e tem a escolha da IA para buscar fotos na internet (tarefa de IA ou assistente de conversa).
- O botão Adicionar fica inteiro dentro da barra de baixo.

## 1.5.0

- Nova aba **Cômodos** na barra de baixo, ao lado de Adicionar: todos os cômodos com foto, número de itens e valor. Toque num cômodo para abrir. Em **Organizar**, as setas mudam a ordem e o lápis edita nome, código e fotos. A lista de cômodos saiu de Dados e ajustes.
- Topo das telas como nos outros apps da casa: o nome InventarIA, com "IA" na cor do app, "Olá" com o nome do usuário do Home Assistant e o título grande da tela.
- Barra de baixo com 5 abas e o Adicionar no meio; o ícone da aba aberta fica na cor do app.
- Dentro de um cômodo, "Cômodos" no topo volta para a lista.
- O fio da etiqueta da tela inicial balança preso ao ilhós.

## 1.4.0

- Cor do app: em **Dados e ajustes > Aparência** (aba **Mais** no celular), escolha entre amarelo (o padrão), laranja, coral, rosa, lilás, azul, turquesa, verde, kraft e cinza. A cor muda a etiqueta, os botões principais e os destaques, e o texto continua legível em todas elas. Cada aparelho guarda a sua escolha.
- Os avisos continuam amarelos, qualquer que seja a cor escolhida.

## 1.3.0

- Importar backup dividido em partes (para celulares que não baixam arquivos grandes): no navegador dá para escolher todas as partes de uma vez; no app do Home Assistant, uma de cada vez. Partes só com fotos acrescentam as fotos sem mexer nos itens.
- Enquanto a foto grande não chega, o app mostra a miniatura.
- No app do Home Assistant para Android: a escolha de fotos pela galeria voltou a funcionar (um arquivo por vez) e o botão "Tirar foto", que lá abria a galeria, deu lugar a "Escolher foto".
- Fotos em HEIC mostram uma mensagem explicando como resolver, em vez de não fazer nada.
- Avisos e erros agora aparecem também com uma janela aberta (antes ficavam escondidos atrás do editor).
- Corrige o alinhamento dos campos Quantidade e Valor no editor.

## 1.2.0

- Novo nome: InventarIA.
- Corrige a leitura do texto da etiqueta amarela na tela de boas-vindas no modo escuro (o texto ficava claro sobre o amarelo).

## 1.1.0

- Importar backup `.zip` (com fotos) ou `.json` direto pelo app, inclusive pelo celular: o arquivo vai em partes, com barra de progresso, e dá para cancelar.
- Tela de boas-vindas quando o inventário está vazio, com "Importar backup" e "Começar do zero".
- A restauração encontra o `inventario.json` em qualquer pasta do `.zip`.
- Antes de importar, o app guarda uma cópia do inventário atual (quando existe um).

## 1.0.0

- Primeira versão: cômodos, zonas e itens com fotos e valores.
- Início com patrimônio total, cômodos, categorias, itens mais valiosos e cadastros recentes.
- Busca com filtros por cômodo e categoria e ordenação.
- Cadastro e edição de itens com várias fotos (câmera, galeria, arrastar ou colar).
- Leitura de fotos por IA pela ação `ai_task.generate_data` do Home Assistant: preencher um item ou catalogar vários itens de uma foto.
- Relatório para seguro (imprimir ou salvar em PDF).
- Exportação em CSV, JSON e ZIP com fotos; backup e restauração na pasta `share/inventario`; versões automáticas.
- Tema claro e escuro.
