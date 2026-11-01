# Changelog

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
