#!/usr/bin/env python3
"""Monta a prévia do app (uma página só, para abrir no navegador ou publicar): a mesma interface, com o
servidor imitado em memória (preview/preview.js), os dados e as fotos de uma casa.

Uso: tools/build_preview.py <pasta-de-saida> [pasta-da-casa]
A casa padrão é a de teste (tests/fixtures/casa, inventada). Para ver a sua, passe uma pasta com
inventario.json, photos/ e thumbs/ (um backup .zip descompactado), e não publique o resultado.
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = f"{ROOT}/inventario/app/web"
SEED = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else f"{ROOT}/tests/fixtures/casa"
OUT = sys.argv[1]

html = open(f"{WEB}/index.html", encoding="utf-8").read()
css = open(f"{WEB}/style.css", encoding="utf-8").read()
app = open(f"{WEB}/app.js", encoding="utf-8").read()
# as caixas de seleção no visual do app (o mesmo arquivo dos outros apps), antes do app: o Voltar dela vem primeiro
caixas = open(f"{WEB}/selectsheet.js", encoding="utf-8").read()
prev = open(f"{ROOT}/preview/preview.js", encoding="utf-8").read()
version = re.search(r'VERSION = "([^"]+)"', open(f"{ROOT}/inventario/app/server.py", encoding="utf-8").read()).group(1)

# fontes: na prévia vêm do Google Fonts (mesma família Barlow)
css = re.sub(r"@font-face \{[^}]*\}\n", "", css)
css += """
/* aviso da prévia */
.pv-note { display: flex; gap: 10px; align-items: center; justify-content: center; flex-wrap: wrap; padding-block: 8px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  background: var(--tag-soft); color: var(--ink); font-size: 14px; text-align: center; border-bottom: 1px solid var(--line); }
.pv-note a { font-weight: 600; }
"""

body = html[html.index("<svg width=\"0\""):html.index("<script src=\"selectsheet.js")]
body = body.replace('<div class="app">', '<div class="pv-note" role="note">Prévia do app do Home Assistant: dá para clicar em tudo, mas as alterações ficam só nesta tela.</div>\n<div class="app">', 1)
theme = re.search(r"<script>try\{.*?</script>", html).group(0)

page = f"""<meta charset="utf-8">
<title>Prévia do Inventário</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&amp;family=Barlow+Condensed:wght@500;600;700&amp;display=swap">
<style>
{css}
</style>
{theme}
{body}
<script>
{caixas}
</script>
<script>
{prev}
</script>
<script>
{app}
</script>
"""
page = page.replace("%%V%%", version)
os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/index.html", "w", encoding="utf-8") as f:
    f.write(page)
shutil.copyfile(f"{SEED}/inventario.json", f"{OUT}/data.json")
for sub in ("photos", "thumbs"):
    os.makedirs(f"{OUT}/{sub}", exist_ok=True)
    for n in os.listdir(f"{SEED}/{sub}"):
        dst = f"{OUT}/{sub}/{n}"
        if not os.path.exists(dst):
            shutil.copyfile(f"{SEED}/{sub}/{n}", dst)
print("page", len(page.encode()), "bytes")
