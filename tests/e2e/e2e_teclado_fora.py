"""1.83.2: o teclado do celular não deixa a página em volta do app (a do Home Assistant) rolada.

Ao abrir uma janela, o campo recebe o foco enquanto ela ainda sobe e o navegador rola as páginas em volta para mostrar o
campo. Aqui o app fica dentro de um quadro, numa página rolada (como dentro do Home Assistant), e um campo de texto
recebe o foco: a página de fora volta para o começo; um botão não mexe em nada.
"""
from e2e_lib import main

QUADRO = """async (alvo) => {
  const f = document.createElement('iframe');
  f.src = location.href; f.style.cssText = 'display:block;width:320px;height:320px';
  const alto = document.createElement('div'); alto.style.height = '3000px';
  document.documentElement.style.cssText = 'height:auto;overflow:visible';
  document.body.style.cssText = 'height:auto;overflow:visible;display:block';
  document.body.append(f, alto);
  await new Promise((r) => (f.onload = r));
  await new Promise((r) => setTimeout(r, 400));
  window.scrollTo(0, 80);
  const antes = window.scrollY;
  const d = f.contentDocument, el = d.createElement(alvo);
  d.body.appendChild(el);
  el.dispatchEvent(new f.contentWindow.FocusEvent('focusin', { bubbles: true, composed: true }));
  await new Promise((r) => setTimeout(r, 200));
  const depois = window.scrollY;
  f.remove(); alto.remove();
  return [antes, depois, !!f.contentWindow || true];
}"""


async def body(r, p):
    r.start()
    b = await r.browser(p)
    ctx, pg = await r.page(b)
    await r.open(pg)
    antes, depois, _ = await pg.evaluate(QUADRO, "button")
    r.check(antes == 80 and depois == 80, f"o foco num botão não mexe na página de fora ({antes} → {depois})")
    antes, depois, _ = await pg.evaluate(QUADRO, "textarea")
    r.check(antes == 80 and depois == 0, f"o foco num campo de texto põe a página de fora no começo ({antes} → {depois})")
    r.check(await pg.evaluate("window.__tecladoCalmo === true"), "o app liga a guarda do teclado")
    await b.close()


main("teclado_fora", body)
