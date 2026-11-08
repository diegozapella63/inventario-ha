/*
 * Caixas de seleção no visual do app. Arquivo igual em todos os apps (ResolvIA, CronologIA, MemorIA, GerencIA,
 * InventarIA e EconomIA): ao mudar aqui, copie para os outros.
 *
 * Uma caixa de seleção (<select>) não abre mais a janela padrão do celular (a lista com bolinhas do Android): abre
 * uma janela que sobe de baixo (no computador, no meio da tela) com as opções em linhas e a atual marcada na cor
 * do app, no tema claro ou escuro. O Voltar do celular, o X, tocar fora e Esc fecham só ela. Os apps não mudam
 * nada nas caixas: a opção escolhida entra na própria <select>, com os eventos input e change de sempre.
 *
 * Para o toque não chegar à caixa (e o Android não abrir a janela dele), as caixas têm pointer-events: none: aqui
 * para as da página e, nos apps com Shadow DOM (Lit), na folha de estilo do app. Sem isso, o toque na caixa é
 * barrado aqui mesmo (mousedown e touchend).
 *
 * Um app pode dizer as cores: window.__selectSheet.theme = () => ({ dark, accent, bg, fg, muted }). Sem isso, elas vêm
 * das variáveis do app (--rv-accent/--a/--accent, --rv-surface/--surface/--card, --rv-text/--text/--fg/--ink,
 * --rv-muted/--muted/--mut) e o tema, do fundo atrás da caixa.
 */
(() => {
  if (typeof window === "undefined" || window.__selectSheet) return;
  const api = (window.__selectSheet = { theme: null, isOpen: () => !!cur });
  let cur = null; // {sel, wrap, pending, byBack}
  let lastTouch = 0;
  let touch0 = null;

  const STYLE = `
select:not([multiple]){pointer-events:none}
.ss-wrap{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:flex-end;justify-content:center;font-family:var(--ss-font);-webkit-tap-highlight-color:transparent}
dialog.ss-wrap{width:auto;height:auto;max-width:none;max-height:none;margin:0;padding:0;border:0;background:transparent;color:inherit;overflow:visible}
dialog.ss-wrap::backdrop{background:transparent}
.ss-back{position:absolute;inset:0;background:var(--ss-scrim);opacity:0;transition:opacity .18s}
.ss-sheet{position:relative;width:100%;max-width:560px;max-height:min(72vh,640px);display:flex;flex-direction:column;background:var(--ss-bg);color:var(--ss-fg);border-radius:28px 28px 0 0;box-shadow:0 -8px 32px rgba(0,0,0,.25);transform:translateY(100%);transition:transform .2s cubic-bezier(.2,.8,.2,1);padding-bottom:env(safe-area-inset-bottom)}
.ss-wrap.out{pointer-events:none}
.ss-wrap.in .ss-back{opacity:1}
.ss-wrap.in .ss-sheet{transform:none}
.ss-grab{width:40px;height:4px;border-radius:2px;background:var(--ss-line2);margin:10px auto 2px;flex:none}
.ss-head{display:flex;align-items:center;gap:8px;padding:6px 10px 8px 20px;flex:none}
.ss-head b{flex:1;font-size:17px;font-weight:600;line-height:1.25;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.ss-x{width:40px;height:40px;border-radius:50%;border:0;background:transparent;color:var(--ss-mut);display:grid;place-items:center;cursor:pointer;flex:none}
.ss-x:hover{background:var(--ss-soft2)}
.ss-x svg,.ss-opt svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.ss-list{overflow-y:auto;overscroll-behavior:contain;padding:0 10px 12px}
.ss-group{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--ss-mut);padding:12px 12px 4px}
.ss-opt{display:flex;align-items:center;gap:12px;width:100%;min-height:50px;padding:10px 12px;border:0;border-radius:14px;background:transparent;color:inherit;font:inherit;font-size:16px;line-height:1.3;text-align:left;cursor:pointer}
.ss-opt span{flex:1;min-width:0;overflow-wrap:anywhere}
.ss-opt:hover,.ss-opt:focus-visible{background:var(--ss-soft2);outline:none}
.ss-opt.on{background:var(--ss-soft);font-weight:600}
.ss-opt.on svg{color:var(--ss-a)}
.ss-opt:not(.on) svg{visibility:hidden}
.ss-opt:disabled{opacity:.45;cursor:default}
@media (min-width:700px){.ss-wrap{align-items:center}.ss-sheet{max-width:440px;border-radius:28px;transform:translateY(16px) scale(.98);opacity:0;transition:transform .16s,opacity .16s}.ss-wrap.in .ss-sheet{opacity:1}.ss-grab{display:none}.ss-head{padding-top:14px}}
@media (prefers-reduced-motion:reduce){.ss-back,.ss-sheet{transition:none}}
`;
  const ICON_X = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  const ICON_OK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';

  const addCss = () => {
    if (document.getElementById("ss-css")) return;
    const st = document.createElement("style");
    st.id = "ss-css";
    st.textContent = STYLE;
    (document.head || document.documentElement).appendChild(st);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", addCss);
  else addCss();

  // the parent of a node, through the shadow roots
  const up = (n) => (n.parentNode && n.parentNode.host && n.parentNode.nodeType === 11 ? n.parentNode.host : n.parentNode || (n.host ? n.host : null));
  const rgba = (c) => {
    const m = /rgba?\(([^)]+)\)/.exec(c || "");
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lum = ({ r, g, b }) => (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  const mix = (hex, a) => {
    const c = rgba(hex) || (/^#([0-9a-f]{6})$/i.test(hex) ? { r: parseInt(hex.slice(1, 3), 16), g: parseInt(hex.slice(3, 5), 16), b: parseInt(hex.slice(5, 7), 16) } : { r: 100, g: 160, b: 240 });
    return `rgba(${c.r},${c.g},${c.b},${a})`;
  };

  /** The look: from the app (window.__selectSheet.theme), from its variables, or from around the box. */
  function look(sel) {
    const cs = getComputedStyle(sel);
    const v = (names) => {
      for (const n of names) {
        const x = cs.getPropertyValue(n).trim();
        if (x) return x;
      }
      return "";
    };
    let dark = null;
    for (let n = sel; n && n.nodeType === 1; n = up(n)) {
      const c = rgba(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) {
        dark = lum(c) < 0.45;
        break;
      }
    }
    if (dark === null) dark = !!(window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches);
    const t = (api.theme && api.theme()) || {};
    dark = t.dark ?? dark;
    const accent = t.accent || v(["--rv-accent", "--a", "--accent", "--cor"]) || "#64b5f6";
    // the colors of the app's own windows, when it names them so
    const bg = t.bg || v(["--rv-surface", "--surface", "--card"]);
    const fg = t.fg || v(["--rv-text", "--text", "--fg", "--ink"]);
    const mut = t.muted || v(["--rv-muted", "--muted", "--mut"]);
    return {
      "--ss-bg": bg || (dark ? "#1b2229" : "#ffffff"),
      "--ss-fg": fg || (dark ? "#e8edf3" : "#141a22"),
      "--ss-mut": mut || (dark ? "#9aa6b4" : "#5b6573"),
      "--ss-line2": dark ? "rgba(255,255,255,.18)" : "rgba(0,0,0,.14)",
      "--ss-a": accent,
      "--ss-soft": mix(accent, dark ? 0.22 : 0.16),
      "--ss-soft2": dark ? "rgba(255,255,255,.06)" : "rgba(0,0,0,.05)",
      "--ss-scrim": v(["--rv-scrim", "--scrim"]) || "rgba(0,0,0,.45)",
      "--ss-font": cs.fontFamily || "system-ui, sans-serif",
    };
  }

  /** The name of the box: its aria-label (or aria-labelledby), its label, or the label of its field. */
  function titleOf(sel) {
    const a = sel.getAttribute("aria-label");
    if (a) return a;
    const root = sel.getRootNode();
    const by = sel.getAttribute("aria-labelledby");
    if (by && root.getElementById) {
      const t = by.split(/\s+/).map((id) => (root.getElementById(id) || {}).textContent || "").join(" ").trim();
      if (t) return t;
    }
    if (sel.id && root.querySelector) {
      const l = root.querySelector(`label[for="${CSS.escape(sel.id)}"]`);
      if (l) return l.textContent.trim();
    }
    const lab = sel.closest("label, .field");
    if (lab) {
      const f = lab.querySelector(".flabel, .label, legend, b, span");
      if (f && !f.contains(sel)) return f.textContent.trim();
    }
    return "";
  }

  // a box inside a modal window (<dialog> opened with showModal: on top of everything, the rest of the page inert)
  function inModal(sel) {
    const d = sel.closest ? sel.closest("dialog") : null;
    if (!d || !d.open) return false;
    try {
      return d.matches(":modal");
    } catch {
      return true;
    }
  }

  function open(sel) {
    if (cur || !sel || sel.disabled || sel.multiple) return;
    // in a modal window, the sheet is a modal window too: only then is it on top of it and gets the touches
    const modal = inModal(sel);
    const wrap = document.createElement(modal ? "dialog" : "div");
    wrap.className = "ss-wrap";
    for (const [k, v] of Object.entries(look(sel))) wrap.style.setProperty(k, v);
    const title = titleOf(sel);
    const sheet = document.createElement("div");
    sheet.className = "ss-sheet";
    sheet.setAttribute("role", "dialog");
    sheet.setAttribute("aria-modal", "true");
    if (title) sheet.setAttribute("aria-label", title);
    sheet.innerHTML = `<div class="ss-grab"></div><div class="ss-head"><b></b><button type="button" class="ss-x" aria-label="Fechar">${ICON_X}</button></div><div class="ss-list" role="listbox"></div>`;
    sheet.querySelector(".ss-head b").textContent = title;
    const list = sheet.querySelector(".ss-list");
    let selectedBtn = null;
    const addOpt = (o) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = `ss-opt${o.selected ? " on" : ""}`;
      b.setAttribute("role", "option");
      b.setAttribute("aria-selected", o.selected ? "true" : "false");
      b.disabled = o.disabled;
      b.innerHTML = `<span></span>${ICON_OK}`;
      b.firstChild.textContent = o.label || o.textContent;
      b.addEventListener("click", () => choose(o.value));
      if (o.selected) selectedBtn = b;
      list.appendChild(b);
    };
    for (const n of sel.children) {
      if (n.tagName === "OPTGROUP") {
        const g = document.createElement("div");
        g.className = "ss-group";
        g.textContent = n.label;
        list.appendChild(g);
        for (const o of n.children) if (o.tagName === "OPTION" && !o.hidden) addOpt(o);
      } else if (n.tagName === "OPTION" && !n.hidden) addOpt(n);
    }
    const back = document.createElement("div");
    back.className = "ss-back";
    wrap.append(back, sheet);
    document.body.appendChild(wrap);
    cur = { sel, wrap, pending: null, closing: false };
    if (modal) {
      try {
        wrap.showModal();
      } catch {}
      wrap.addEventListener("cancel", (e) => {
        e.preventDefault();
        close();
      });
    }
    back.addEventListener("click", () => close());
    sheet.querySelector(".ss-x").addEventListener("click", () => close());
    wrap.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation(); // only the sheet closes, not the window under it
        close();
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const opts = [...list.querySelectorAll(".ss-opt:not(:disabled)")];
        const i = opts.indexOf(document.activeElement);
        const next = opts[Math.max(0, Math.min(opts.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
        if (next) {
          e.preventDefault();
          next.focus();
        }
      }
    });
    // the Back of the phone closes only this
    try {
      history.pushState(history.state, "");
    } catch {}
    requestAnimationFrame(() => {
      wrap.classList.add("in");
      if (selectedBtn) {
        selectedBtn.scrollIntoView({ block: "center" });
        selectedBtn.focus({ preventScroll: true });
      } else sheet.querySelector(".ss-x").focus({ preventScroll: true });
    });
  }

  /** Closes; the value chosen enters the box after the history is back where it was (the app's Back intact). */
  function close(value = null) {
    if (!cur || cur.closing) return;
    cur.closing = true;
    cur.pending = value;
    const done = cur;
    const finish = () => {
      if (cur !== done) return;
      cur = null;
      if (done.wrap.open) done.wrap.close(); // out of the top layer: the box under it can take the focus again
      done.wrap.classList.remove("in");
      done.wrap.classList.add("out");
      setTimeout(() => done.wrap.remove(), 220);
      const sel = done.sel;
      if (done.pending !== null && sel.value !== done.pending) {
        sel.value = done.pending;
        sel.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
        sel.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
      }
      try {
        sel.focus({ preventScroll: true });
      } catch {}
    };
    done.finish = finish;
    if (done.byBack) return finish();
    history.back();
    // no popstate (an odd history): close anyway
    setTimeout(finish, 400);
  }
  const choose = (v) => close(v);

  // first of all the listeners of popstate: the Back that closes the sheet is not seen by the app
  window.addEventListener("popstate", (e) => {
    if (!cur) return;
    e.stopImmediatePropagation();
    if (cur.closing) return cur.finish && cur.finish();
    cur.byBack = true;
    close();
  });

  // the box under the finger: with pointer-events: none, the tap lands on what is under it (its label, the chip it
  // covers), so look for it among the nearest ancestors of what was touched
  function boxAt(e) {
    const path = e.composedPath ? e.composedPath() : [e.target];
    const t = path[0];
    if (t && t.tagName === "SELECT") return t;
    if (typeof e.clientX !== "number") return null;
    for (const n of path.slice(0, 6)) {
      if (!n || n.nodeType !== 1 || n === document.body || n === document.documentElement) break;
      for (const s of n.querySelectorAll("select")) {
        if (s.disabled || s.multiple) continue;
        const r = s.getBoundingClientRect();
        if (r.width && e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom && onTop(s, e.clientX, e.clientY)) return s;
      }
    }
    return null;
  }
  // the box is what the finger touched only when nothing covers it there (a bar stuck over a scrolled list, say)
  function onTop(s, x, y) {
    const before = s.style.getPropertyValue("pointer-events");
    s.style.setProperty("pointer-events", "auto", "important");
    let hit = null;
    try {
      const root = s.getRootNode();
      hit = (root.elementFromPoint ? root : document).elementFromPoint(x, y);
    } catch {}
    if (before) s.style.setProperty("pointer-events", before);
    else s.style.removeProperty("pointer-events");
    return hit === s;
  }
  const isBox = (e) => {
    const t = e.composedPath ? e.composedPath()[0] : e.target;
    return t && t.tagName === "SELECT" && !t.disabled && !t.multiple ? t : null;
  };

  window.addEventListener("touchstart", (e) => {
    const t = e.touches[0];
    touch0 = t ? { x: t.clientX, y: t.clientY } : null;
  }, { capture: true, passive: true });
  window.addEventListener("touchend", (e) => {
    const sel = isBox(e);
    if (!sel || cur) return;
    const t = e.changedTouches[0];
    if (touch0 && t && Math.hypot(t.clientX - touch0.x, t.clientY - touch0.y) > 10) return; // a scroll
    e.preventDefault();
    lastTouch = Date.now();
    open(sel);
  }, { capture: true, passive: false });
  window.addEventListener("mousedown", (e) => {
    if (isBox(e)) e.preventDefault();
  }, true);
  window.addEventListener("click", (e) => {
    if (cur) return;
    const sel = boxAt(e);
    if (!sel) return;
    e.preventDefault();
    e.stopPropagation();
    if (Date.now() - lastTouch > 600) open(sel);
  }, true);
  window.addEventListener("keydown", (e) => {
    const sel = isBox(e);
    if (!sel || cur) return;
    if (e.key === "Enter" || e.key === " " || e.key === "F4" || (e.altKey && (e.key === "ArrowDown" || e.key === "ArrowUp"))) {
      e.preventDefault();
      open(sel);
    }
  }, true);
  api.open = open;
  api.close = () => close();
})();
