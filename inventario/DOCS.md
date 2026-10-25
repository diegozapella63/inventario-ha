# InventarIA

O InventarIA é o inventário da casa dentro do Home Assistant: cômodos, zonas, itens com fotos e valores, busca, relatório para seguro e leitura de fotos por IA.

O app abre pela barra lateral (Ingress). Quem já está logado no Home Assistant usa direto, sem outra senha.

## Primeiro uso

Na primeira vez, o app abre vazio e oferece duas opções:

- **Importar backup**: escolha o arquivo `.zip` de um backup do app (com itens, fotos e valores). Funciona pelo celular: o arquivo é enviado em partes, com barra de progresso. Deixe a tela aberta até terminar.
- **Começar do zero**: crie o primeiro cômodo e vá cadastrando os itens.

Depois disso, tudo o que você muda fica salvo no app. Atualizar ou reiniciar o app não apaga nada.

## Como usar

- **Início**: patrimônio total, cômodos (com a parte de cada um no total), categorias, itens mais valiosos e últimos cadastros.
- **Cômodos** (aba ao lado de Adicionar): todos os cômodos com foto, número de itens e valor. Toque num cômodo para abrir. Em **Organizar**, as setas mudam a ordem (que vale para o app todo e para o relatório) e o lápis edita nome, código e fotos.
- **Cômodo**: fotos do cômodo, itens agrupados por zona (estante, bancada, eletrônicos...) com subtotal de cada zona.
- **Adicionar item**: nome, detalhes, cômodo, zona, categoria, quantidade e valor total. Dá para tirar foto pelo celular, enviar da galeria, arrastar uma foto ou colar com Ctrl+V. "Salvar e adicionar outro" mantém o cômodo e a zona para cadastrar em sequência.
- **Catalogar foto com IA**: tire uma foto de uma prateleira ou de um canto da casa; a IA lista os objetos com nome, categoria, quantidade e valor estimado. Você confere, ajusta e escolhe o que entra.
- **Buscar na internet**: num item sem foto (ou no editor do item), a IA procura o produto no fabricante e nas lojas e o app mostra as fotos encontradas para você escolher. Veja [Fotos da internet](#fotos-da-internet).
- **Buscar**: por nome, marca, detalhe ou zona, sem se preocupar com acentos. Filtre por cômodo e categoria e ordene por valor, nome ou data.
- **Relatório**: lista por cômodo com fotos e valores, pronta para imprimir ou salvar em PDF (útil para seguro).
- **Mais**, em abas como nos outros apps: **Exportar** (planilha, JSON, ZIP com fotos e o relatório), **Integrações** (a IA do Home Assistant), **Dados** (backup, importar, versões anteriores) e **Aparência** (tema claro, escuro ou automático e a cor do app: amarelo, laranja, coral, rosa, lilás, azul, turquesa, verde, kraft ou cinza; cada aparelho guarda a sua escolha).
- Atalhos no computador: `/` abre a busca, `N` cria um item, `Ctrl+Enter` salva o formulário.

Os valores são de mercado de usados (o que o item vale hoje), somando todas as unidades.

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
3. No app, abra **Mais > Integrações** e escolha essa IA em **IA para ler fotos**. "Padrão do Home Assistant" usa a IA preferida definida em **Configurações > Sistema > Geral**.

Na hora da leitura, o app copia a foto por alguns segundos para `media/inventario/ia-temp`, chama a IA pelo Home Assistant e apaga a cópia em seguida. A IA não recebe número de série, IMEI ou dados pessoais: as instruções pedem só descrição do objeto.

Sem IA configurada, todo o resto funciona normalmente.

## Fotos da internet

Para itens sem foto, **Buscar na internet** pede à IA do Home Assistant que procure o produto na web, no site do fabricante e em lojas grandes. O app abre as páginas que a IA encontrou, pega a foto principal de cada uma, descarta o que não é foto ou é pequeno demais e mostra as opções. A foto escolhida entra no item como **foto ilustrativa**, com o site de onde veio, na ficha do item e no relatório. Para o seguro, uma foto sua do item continua valendo mais.

A IA precisa ter a **busca na web** ligada:

- **Anthropic**: nas opções da tarefa de IA, ligue **Enable web search**.
- **Google Gemini**: a Pesquisa Google só funciona num assistente de conversa. Ligue **Enable Google Search tool** nele e escolha esse assistente.
- **OpenAI**: nas opções da tarefa de IA, ligue **Enable web search** (precisa do gpt-4o ou de um modelo mais novo).

Escolha a IA em **Mais > Integrações > IA para buscar fotos na internet**. "A mesma de ler fotos" usa a IA da leitura de fotos.

A IA recebe só o nome e o começo dos detalhes do item. O app baixa as fotos apenas de endereços públicos da internet (nunca da rede da casa) e guarda só a foto que você escolher; as outras são apagadas em até 30 minutos. Cada busca usa a busca na web da sua IA, que pode ter custo à parte.

## Seus dados

Tudo fica em arquivos abertos, dentro da pasta de dados do app:

- `inventario.json`: cômodos e itens (texto legível, abre em qualquer editor).
- `photos/` e `thumbs/`: fotos em JPG (tamanho cheio e miniatura).
- `history/`: cópias automáticas do inventário, uma a cada 10 minutos de uso (as 60 mais recentes).

Formas de guardar uma cópia:

- **Backups do Home Assistant**: incluem o app e os dados dele.
- **Mais > Dados > Backup na pasta share**: cria um `.zip` completo (JSON, CSV e fotos) em `share/inventario`, que você acessa pela rede (por exemplo `\\homeassistant.local\share\inventario` com o app Samba).
- **Mais > Exportar**: CSV (abre no Excel), JSON ou ZIP com fotos, direto para o seu computador ou celular.

Para restaurar, use **Mais > Dados**: escolha um backup da pasta share, volte para uma versão anterior ou importe um arquivo (`.zip` de backup ou `.json`) do computador ou do celular. Antes de restaurar ou importar, o app guarda uma cópia do que existe naquele momento.

## Atualizar o app

Quando sai uma versão nova, o Home Assistant mostra **Atualizar** na página do app e em **Configurações > Atualizações**. Para procurar na hora, abra **Configurações > Apps > Loja de apps**, toque no menu e escolha **Verificar atualizações**. Os dados não são apagados.

## Problemas comuns

- **"A sessão do Home Assistant expirou"**: recarregue a página do Home Assistant.
- **A IA aparece como não configurada**: confira se a integração de IA tem uma tarefa de IA criada e se o modelo lê imagens; depois toque em "Verificar de novo".
- **A IA demora**: modelos locais podem levar mais de um minuto por foto. Modelos na nuvem costumam responder em 5 a 20 segundos.
- **Ver o que está acontecendo**: aba **Registro** do app.
