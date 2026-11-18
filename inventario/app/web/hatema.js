/* O tema do Home Assistant nos apps da família: o fundo e o cartão de cada app são os do tema escolhido no Home
   Assistant, para todos os apps terem o mesmo fundo (claro ou escuro, como cada app já escolhe). Arquivo igual em todos
   os apps (ver tools/iguais.py): ao mudar, copie para os outros.

   Publica no <html> deste app quatro cores, que o CSS de cada app usa no fundo e nos cartões (e mistura com a cor do
   texto para os cinzas: as linhas, os campos):
     --ha-bg-light, --ha-card-light   o fundo e o cartão do tema claro
     --ha-bg-dark,  --ha-card-dark    os do tema escuro
   As do modo em que o Home Assistant está agora vêm dele (--primary-background-color e --card-background-color, como ele
   pinta a tela, inclusive de um tema da pessoa); as do outro modo, e fora do Home Assistant (a prévia, os testes), são
   as do tema padrão dele. Quando o tema ou o modo do Home Assistant muda, as cores mudam junto.

   window.__haTema: { aplicar(), cores, doHA } (cores: o que está publicado; doHA: o modo lido do Home Assistant, ou
   null). Sem dependências: vai como <script> antes do app (ou importado pelo build dos apps em Lit). */
(function () {
  if (window.__haTema) return;
  var PADRAO = { light: { bg: "#fafafa", card: "#ffffff" }, dark: { bg: "#111111", card: "#1c1c1c" } };
  var api = { cores: { light: PADRAO.light, dark: PADRAO.dark }, doHA: null, aplicar: aplicar };
  window.__haTema = api;

  /* a janela do Home Assistant: a de cima (o painel do app) ou a do alto (um app dentro de outro, como o CronologIA
     na Tela cheia do CorrerIA); só a da mesma origem, onde está o <home-assistant> */
  function ha() {
    var ws = [];
    try { if (window.parent && window.parent !== window) ws.push(window.parent); } catch (e) { /* outra origem */ }
    try { if (window.top && window.top !== window && ws.indexOf(window.top) < 0) ws.push(window.top); } catch (e) { /* outra origem */ }
    for (var i = 0; i < ws.length; i++) {
      try {
        var d = ws[i].document, el = d && d.querySelector("home-assistant");
        if (el) return { win: ws[i], doc: d, el: el };
      } catch (e) { /* outra origem */ }
    }
    return null;
  }

  // a cor escura? (pela luz da cor, quando o Home Assistant não diz o modo)
  function escura(cor) {
    var c = document.createElement("canvas").getContext("2d");
    if (!c) return false;
    c.fillStyle = "#000";
    c.fillStyle = cor;
    var m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i.exec(c.fillStyle);
    var r = m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : (c.fillStyle.match(/\d+(\.\d+)?/g) || [0, 0, 0]).map(Number);
    return (0.2126 * r[0] + 0.7152 * r[1] + 0.0722 * r[2]) / 255 < 0.5;
  }

  function lerHA() {
    var h = ha();
    if (!h) return null;
    try {
      var cs = h.win.getComputedStyle(h.doc.documentElement);
      var bg = cs.getPropertyValue("--primary-background-color").trim();
      var card = cs.getPropertyValue("--ha-card-background").trim() || cs.getPropertyValue("--card-background-color").trim();
      if (!bg) return null;
      var t = h.el.hass && h.el.hass.themes;
      var dark = t && typeof t.darkMode === "boolean" ? t.darkMode : escura(bg);
      return { modo: dark ? "dark" : "light", bg: bg, card: card || PADRAO[dark ? "dark" : "light"].card };
    } catch (e) {
      return null;
    }
  }

  function aplicar() {
    var lido = lerHA(), s = document.documentElement.style;
    api.doHA = lido ? lido.modo : null;
    ["light", "dark"].forEach(function (m) {
      var v = lido && lido.modo === m ? { bg: lido.bg, card: lido.card } : PADRAO[m];
      api.cores[m] = v;
      if (s.getPropertyValue("--ha-bg-" + m) !== v.bg) s.setProperty("--ha-bg-" + m, v.bg);
      if (s.getPropertyValue("--ha-card-" + m) !== v.card) s.setProperty("--ha-card-" + m, v.card);
    });
    vigiar();
  }

  // o Home Assistant pinta o tema no <html> dele: quando muda (outro tema, claro e escuro), lê de novo
  var vigiado = null, pendente = 0;
  function depois() {
    if (pendente) return;
    pendente = setTimeout(function () { pendente = 0; aplicar(); }, 60);
  }
  function vigiar() {
    var h = ha();
    if (!h || vigiado === h.doc.documentElement || typeof MutationObserver !== "function") return;
    try {
      new MutationObserver(depois).observe(h.doc.documentElement, { attributes: true, attributeFilter: ["style", "class"] });
      vigiado = h.doc.documentElement;
    } catch (e) { /* sem como vigiar: fica o que foi lido */ }
  }

  aplicar();
  try {
    var mq = window.matchMedia && matchMedia("(prefers-color-scheme: dark)");
    if (mq && mq.addEventListener) mq.addEventListener("change", depois);
  } catch (e) { /* antigo */ }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) depois(); });
  // o Home Assistant pode ainda estar montando o tema quando este app abre
  setTimeout(aplicar, 400);
  setTimeout(aplicar, 2000);
})();
