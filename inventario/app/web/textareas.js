// Os campos de texto aberto (textarea) de todos os apps da família: dá para aumentar puxando o canto, e o tamanho fica
// guardado no aparelho, para cada campo: aberto de novo, o campo volta do tamanho que a pessoa deixou. Vale também dentro
// do Shadow DOM (as telas em Lit). Um campo que cresce sozinho (a conversa) fica de fora com data-size="off".
// Arquivo igual em todos os apps (tools/iguais.py): ao mudar, copie para os outros.
(() => {
  if (window.__textareas) return;
  // as telas de todos os apps abrem no mesmo endereço do Home Assistant (o mesmo localStorage): cada app com o seu nome
  const prefix = () => `textareas:${(document.title || "app").split(/[·|-]/)[0].trim()}:`;
  const keyOf = (ta) => ta.dataset.size || ta.id || ta.name || ta.getAttribute("aria-label") || ta.placeholder || "";
  const read = (k) => {
    try {
      return Number(localStorage.getItem(prefix() + k)) || 0;
    } catch (e) {
      return 0;
    }
  };
  const write = (k, h) => {
    try {
      localStorage.setItem(prefix() + k, String(Math.round(h)));
    } catch (e) {
      /* navegação privada: só não fica guardado */
    }
  };
  // a pessoa puxou o canto: o navegador põe a altura no style do campo; outra mudança de tamanho (a largura da tela, o
  // texto) não mexe nela e não conta
  const saving = new WeakMap();
  const ro = typeof ResizeObserver === "function" ? new ResizeObserver((list) => list.forEach(({ target: ta }) => {
    const h = parseFloat(ta.style.height);
    if (!h || h === ta.__tsSet) return;
    clearTimeout(saving.get(ta));
    saving.set(ta, setTimeout(() => {
      const k = keyOf(ta), now = parseFloat(ta.style.height);
      if (k && now) write(k, now);
      ta.__tsSet = now;
    }, 400));
  })) : null;
  const fit = (ta) => {
    if (!(ta instanceof HTMLTextAreaElement) || ta.dataset.size === "off" || ta.__tsDone) return;
    ta.__tsDone = true;
    ta.style.resize = "vertical";
    const k = keyOf(ta);
    const h = k && read(k);
    if (h) {
      ta.style.height = `${h}px`;
      ta.__tsSet = h;
    }
    if (ro) ro.observe(ta);
  };
  const watched = new WeakSet();
  const scan = (node) => {
    if (!node || node.nodeType !== 1) return;
    if (node.tagName === "TEXTAREA") fit(node);
    if (node.shadowRoot) watch(node.shadowRoot);
    if (node.querySelectorAll) {
      node.querySelectorAll("textarea").forEach(fit);
      node.querySelectorAll("*").forEach((el) => el.shadowRoot && watch(el.shadowRoot));
    }
  };
  function watch(root) {
    if (watched.has(root)) return;
    watched.add(root);
    new MutationObserver((list) => list.forEach((m) => m.addedNodes.forEach(scan))).observe(root, { childList: true, subtree: true });
    root.querySelectorAll("textarea").forEach(fit);
    root.querySelectorAll("*").forEach((el) => el.shadowRoot && watch(el.shadowRoot));
  }
  window.__textareas = { fit, keyOf };
  const start = () => watch(document.body || document.documentElement);
  if (document.body) start();
  else document.addEventListener("DOMContentLoaded", start);
})();
