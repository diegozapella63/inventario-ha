# Changelog

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
