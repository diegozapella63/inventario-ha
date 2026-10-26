# Changelog

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
