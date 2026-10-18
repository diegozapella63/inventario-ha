# InventarIA

O InventarIA é um app do Home Assistant para manter o inventário da casa: cômodos, itens, fotos e valores, com busca, relatório para seguro e leitura de fotos por IA (pela integração de IA que você já usa no Home Assistant).

[![Adicionar o repositório ao Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fdiegozapella63%2Finventario-ha)

## Instalação

1. Toque no botão acima. Se preferir, no Home Assistant abra **Configurações > Apps > Loja de apps**, toque no menu, escolha **Repositórios** e cole `https://github.com/diegozapella63/inventario-ha`.
2. Na loja de apps, abra **InventarIA** e toque em **Instalar**. A primeira instalação leva alguns minutos.
3. Toque em **Iniciar** e ligue **Mostrar na barra lateral**.
4. Abra o InventarIA e importe o seu backup (`.zip`) ou comece do zero.

Atualizações aparecem sozinhas no Home Assistant, com o botão **Atualizar**.

## Seus dados

Os itens e as fotos ficam só no seu Home Assistant, em arquivos abertos (JSON e JPG), e entram nos backups do Home Assistant. Este repositório tem apenas o código do app.

Veja [DOCS.md](inventario/DOCS.md) para uso, IA, backups e exportação.
