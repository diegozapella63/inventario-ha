/* Inventário da casa: interface do app do Home Assistant.
   JavaScript puro, sem dependências nem etapa de build. Fala com o servidor em api/... (URLs relativas, por causa do Ingress). */
(() => {
  "use strict";

  // ------------------------------------------------------------------ constantes
  const CATS = [
    ["eletronicos", "Eletrônicos"], ["moveis", "Móveis"], ["decoracao", "Decoração e arte"],
    ["colecao", "Colecionáveis"], ["cozinha", "Cozinha e bar"], ["texteis", "Tapetes e têxteis"],
    ["plantas", "Plantas"], ["livros", "Livros e jogos"], ["pets", "Pets"], ["saude", "Saúde"],
    ["vestuario", "Roupas e calçados"], ["utilidades", "Utilidades"], ["outros", "Outros"],
  ];
  const CAT = Object.fromEntries(CATS);
  const SOURCES = { foto: "Catalogado por foto", informado: "Valor informado", ia: "Leitura por IA", manual: "Cadastro manual" };
  const ORDERS = [["rel", "Mais relevantes"], ["val", "Maior valor"], ["valasc", "Menor valor"], ["az", "Nome, de A a Z"], ["new", "Mais recentes"], ["code", "Código"]];
  const PREVIEW = !!window.INV_PREVIEW;
  const COARSE = window.matchMedia("(pointer: coarse)").matches;
  const BRAND = '<svg class="brand-mark" viewBox="0 0 30 20" aria-hidden="true"><path d="M8 0h20a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H8L0 13V7z" style="fill:var(--tag)"/><circle cx="7" cy="10" r="2.7" style="fill:var(--paper)"/></svg>';

  // ------------------------------------------------------------------ utilidades
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const nf2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const numTxt = (v) => { v = +v || 0; return Number.isInteger(v) ? nf0.format(v) : nf2.format(v); };
  const money = (v) => "R$ " + numTxt(v);
  const moneyR = (v) => money(Math.round(+v || 0));
  const int = (n) => nf0.format(n || 0);
  const plural = (n, one, many) => `${int(n)} ${n === 1 ? one : many}`;
  const pct = (v, t) => (t > 0 ? (v / t) * 100 : 0);
  const pctFmt = (p) => (p === 0 ? "0%" : p < 1 ? "<1%" : `${Math.round(p)}%`);
  const ic = (n, cls = "") => `<svg class="ic ${cls}" aria-hidden="true"><use href="#i-${n}"/></svg>`;
  const src = (f, kind = "thumbs") => (window.INV_PHOTO_URL && window.INV_PHOTO_URL(f, kind)) || `${kind}/${encodeURIComponent(f)}`;
  const parseDate = (s) => { const t = Date.parse(s || ""); return Number.isNaN(t) ? 0 : t; };
  const dfDate = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "short", year: "numeric" });
  const dfDateTime = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  const dfLong = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "long", year: "numeric" });
  const rtf = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });
  const dateTime = (s) => (parseDate(s) ? dfDateTime.format(parseDate(s)) : "");
  function ago(s) {
    const t = parseDate(s);
    if (!t) return "";
    const d = (t - Date.now()) / 1000, a = Math.abs(d);
    if (a < 60) return "agora";
    if (a < 3600) return rtf.format(Math.round(d / 60), "minute");
    if (a < 86400) return rtf.format(Math.round(d / 3600), "hour");
    if (a < 86400 * 7) return rtf.format(Math.round(d / 86400), "day");
    return dfDate.format(t);
  }
  const qtyClean = (q) => String(q ?? "1").replace(/^~\s*/, "").trim() || "1";
  const qtyNum = (q) => (/^\d+$/.test(qtyClean(q)) ? parseInt(qtyClean(q), 10) : null);
  const qtyLabel = (q) => { const n = qtyNum(q); return n != null ? `${int(n)} ${n === 1 ? "unidade" : "unidades"}` : qtyClean(q); };
  const qtyShort = (q) => { const n = qtyNum(q); return n != null ? `${int(n)} un.` : qtyClean(q); };
  function parseMoney(s) {
    if (typeof s === "number") return s;
    s = String(s ?? "").trim().replace(/R\$|\s| /g, "");
    if (!s) return 0;
    if (s.includes(",")) s = s.replace(/\./g, "").replace(",", ".");
    else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, "");
    const v = Number(s);
    return Number.isFinite(v) && v >= 0 ? Math.round(v * 100) / 100 : NaN;
  }
  const moneyInput = (v) => (+v ? numTxt(v) : "");
  const LS = {
    get(k, d) { try { const v = localStorage.getItem("inv:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("inv:" + k, JSON.stringify(v)); } catch { /* sem armazenamento */ } },
  };
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  const tokens = (q) => norm(q).split(/\s+/).filter(Boolean);
  function hl(text, toks) {
    text = String(text ?? "");
    if (!toks || !toks.length) return esc(text);
    let ns = "";
    const map = [];
    for (let i = 0; i < text.length; i++) for (const ch of norm(text[i])) { ns += ch; map.push(i); }
    const marks = new Uint8Array(text.length);
    for (const t of toks) {
      let p = 0;
      while ((p = ns.indexOf(t, p)) !== -1) { for (let k = p; k < p + t.length; k++) marks[map[k]] = 1; p += t.length; }
    }
    let out = "", open = false;
    for (let i = 0; i < text.length; i++) {
      if (marks[i] && !open) { out += "<mark>"; open = true; } else if (!marks[i] && open) { out += "</mark>"; open = false; }
      out += esc(text[i]);
    }
    return open ? out + "</mark>" : out;
  }
  const snippet = (s, n = 90) => { s = String(s || "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s; };

  // ------------------------------------------------------------------ estado
  const S = { rooms: [], items: [], rev: 0, updatedAt: null, user: null, version: "", features: {}, settings: {}, loaded: false, error: null, stale: false };
  let D = null;
  const roomFilter = {};
  let searchLimit = 120;
  let firstHome = true;
  let focusSearch = false;

  function derive() {
    const rooms = [...S.rooms].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    const roomById = new Map(rooms.map((r) => [r.id, r]));
    const byRoom = new Map(rooms.map((r) => [r.id, []]));
    const photoItems = new Map();
    const catTotals = new Map();
    let total = 0;
    for (const it of S.items) {
      if (!byRoom.has(it.room)) byRoom.set(it.room, []);
      byRoom.get(it.room).push(it);
      const v = +it.value || 0;
      total += v;
      const c = CAT[it.cat] ? it.cat : "outros";
      const ct = catTotals.get(c) || { value: 0, count: 0 };
      ct.value += v; ct.count += 1;
      catTotals.set(c, ct);
      for (const p of it.photos || []) { if (!photoItems.has(p)) photoItems.set(p, []); photoItems.get(p).push(it); }
    }
    const roomTotals = new Map();
    for (const [rid, list] of byRoom) {
      list.sort((a, b) => (a.seq || 0) - (b.seq || 0));
      roomTotals.set(rid, list.reduce((s, i) => s + (+i.value || 0), 0));
    }
    const files = new Set();
    for (const it of S.items) for (const p of it.photos || []) files.add(p);
    for (const r of rooms) for (const p of r.photos || []) files.add(p.file);
    D = { rooms, roomById, byRoom, roomTotals, catTotals, photoItems, total, photoCount: files.size, itemById: new Map(S.items.map((i) => [i.id, i])) };
  }
  const tagOf = (it) => `${D.roomById.get(it.room)?.code || "ITM"}-${String(it.seq || 0).padStart(3, "0")}`;
  const zonesOf = (rid) => [...new Set((D.byRoom.get(rid) || []).map((i) => i.zone).filter(Boolean))];
  const lastRoom = () => { const r = LS.get("lastRoom", null); return D.roomById.has(r) ? r : D.rooms[0]?.id || ""; };
  function upsertItem(it) { const i = S.items.findIndex((x) => x.id === it.id); if (i >= 0) S.items[i] = it; else S.items.push(it); }
  function removeItem(id) { S.items = S.items.filter((x) => x.id !== id); }
  function upsertRoom(r) { const i = S.rooms.findIndex((x) => x.id === r.id); if (i >= 0) S.rooms[i] = r; else S.rooms.push(r); }
  const setRev = (rev) => { if (rev) S.rev = rev; };

  // ------------------------------------------------------------------ API
  const API = {
    async req(method, path, body) {
      if (window.INV_BACKEND) return window.INV_BACKEND(method, path, body);
      let res;
      try {
        res = await fetch(path, {
          method, cache: "no-store", credentials: "same-origin",
          headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
          body: body !== undefined ? JSON.stringify(body) : undefined,
        });
      } catch {
        throw Object.assign(new Error("Sem conexão com o Home Assistant. Confira a rede e tente de novo."), { status: 0 });
      }
      let data = null;
      if ((res.headers.get("content-type") || "").includes("json")) { try { data = await res.json(); } catch { data = null; } }
      if (!res.ok) {
        const msg = data?.error || (res.status === 401 || res.status === 403
          ? "A sessão do Home Assistant expirou. Recarregue a página."
          : res.status === 502 || res.status === 503 ? "O app está reiniciando. Tente de novo em alguns segundos." : `Erro ${res.status} no servidor.`);
        throw Object.assign(new Error(msg), { status: res.status, data });
      }
      return data;
    },
    async raw(method, path, blob) {
      if (window.INV_BACKEND) return window.INV_BACKEND(method, path, blob);
      let res;
      try {
        res = await fetch(path, { method, body: blob, cache: "no-store", credentials: "same-origin", headers: { "Content-Type": "application/octet-stream" } });
      } catch {
        throw Object.assign(new Error("A conexão caiu durante o envio."), { status: 0 });
      }
      let data = null;
      try { data = await res.json(); } catch { data = null; }
      if (!res.ok) throw Object.assign(new Error(data?.error || `Erro ${res.status} no envio.`), { status: res.status, data });
      return data;
    },
    get: (p) => API.req("GET", p),
    post: (p, b = {}) => API.req("POST", p, b),
    put: (p, b = {}) => API.req("PUT", p, b),
    del: (p) => API.req("DELETE", p),
  };

  async function loadData() {
    const d = await API.get("api/data");
    Object.assign(S, {
      rooms: d.rooms || [], items: d.items || [], rev: d.rev || 0, updatedAt: d.updatedAt, user: d.user || null,
      version: d.version || "", features: d.features || {}, settings: d.settings || {}, loaded: true, error: null, stale: false,
    });
    derive();
  }

  // ------------------------------------------------------------------ avisos
  function toast(msg, opts = {}) {
    const box = $("#toasts");
    const el = document.createElement("div");
    el.className = "toast" + (opts.error ? " err" : "");
    el.innerHTML = `<span class="tmsg">${esc(msg)}</span>${opts.action ? `<button type="button">${esc(opts.action)}</button>` : ""}`;
    let done = false;
    const close = () => { if (!done) { done = true; el.remove(); } };
    if (opts.action) el.querySelector("button").addEventListener("click", () => { close(); opts.onAction && opts.onAction(); });
    box.append(el);
    while (box.children.length > 3) box.firstElementChild.remove();
    setTimeout(close, opts.ms || (opts.action ? 8000 : 3800));
    return close;
  }
  const fail = (e) => toast(e?.message || String(e), { error: true, ms: 7000 });

  // ------------------------------------------------------------------ janelas (dialog) com botão voltar do celular
  const stack = [];
  function openDialog({ cls = "modal", html, routed = false, guard = null, onClose = null, label = "" }) {
    const dlg = document.createElement("dialog");
    dlg.className = cls;
    if (label) dlg.setAttribute("aria-label", label);
    dlg.innerHTML = html;
    document.body.append(dlg);
    const entry = { dlg, routed, guard, onClose, closing: false, awaitingPop: false };
    stack.push(entry);
    if (!routed) { try { history.pushState({ invModal: stack.length }, ""); entry.pushed = true; } catch { entry.pushed = false; } }
    dlg.addEventListener("cancel", (e) => { e.preventDefault(); requestClose(entry); });
    dlg.addEventListener("close", () => {
      // fechada pelo navegador (ex.: Esc duas vezes seguidas no Chrome): limpa o que ficou para trás
      if (!stack.includes(entry)) return;
      stack.splice(stack.indexOf(entry), 1);
      dlg.remove();
      entry.onClose && entry.onClose();
      if (entry.routed) { entry.onRouteClose && entry.onRouteClose(); }
      else if (entry.pushed && !entry.awaitingPop && history.state && history.state.invModal) { ignorePops++; history.back(); }
    });
    dlg.addEventListener("pointerdown", (e) => { entry.downOnBackdrop = e.target === dlg; });
    dlg.addEventListener("click", (e) => { if (e.target === dlg && entry.downOnBackdrop) requestClose(entry); });
    dlg.showModal();
    return entry;
  }
  async function requestClose(entry, { force = false } = {}) {
    if (entry.closing || !stack.includes(entry)) return;
    if (!force && entry.guard) {
      entry.closing = true;
      let ok = false;
      try { ok = await entry.guard(); } finally { entry.closing = false; }
      if (!ok) return;
    }
    entry.closing = true;
    if (entry.routed) { entry.onRouteClose && entry.onRouteClose(); return; }
    if (entry.pushed && history.state && history.state.invModal) {
      entry.awaitingPop = true;
      history.back();
      // se o navegador não devolver o "voltar" (navegação concorrente), fecha mesmo assim
      setTimeout(() => { if (stack.includes(entry)) finalize(entry); }, 700);
    } else finalize(entry);
  }
  function finalize(entry) {
    const i = stack.indexOf(entry);
    if (i >= 0) stack.splice(i, 1);
    try { entry.dlg.close(); } catch { /* já fechado */ }
    entry.dlg.remove();
    entry.onClose && entry.onClose();
  }
  let ignorePops = 0;
  window.addEventListener("popstate", () => {
    if (ignorePops > 0) { ignorePops--; return; }
    const top = stack[stack.length - 1];
    if (!top || top.routed) return;
    if (top.awaitingPop) { finalize(top); return; }
    if (top.guard) { try { history.pushState({ invModal: stack.length }, ""); } catch { top.pushed = false; } requestClose(top); return; }
    finalize(top);
  });
  const topEntry = () => stack[stack.length - 1];

  function confirmBox({ title, body = "", ok = "Confirmar", cancel = "Cancelar", danger = false }) {
    return new Promise((resolve) => {
      let answer = false;
      const entry = openDialog({
        cls: "modal narrow", label: title,
        html: `<div class="dlg"><div class="dlg-h"><h2>${esc(title)}</h2></div>
          ${body ? `<div class="dlg-b"><p style="margin:0">${body}</p></div>` : ""}
          <div class="dlg-f"><span class="grow"></span><button type="button" class="btn ghost" data-r="0">${esc(cancel)}</button>
          <button type="button" class="btn ${danger ? "danger" : "primary"}" data-r="1">${esc(ok)}</button></div></div>`,
        onClose: () => resolve(answer),
      });
      entry.dlg.addEventListener("click", (e) => {
        const b = e.target.closest("[data-r]");
        if (!b) return;
        answer = b.dataset.r === "1";
        requestClose(entry, { force: true });
      });
      setTimeout(() => $(`[data-r="${danger ? 0 : 1}"]`, entry.dlg)?.focus(), 30);
    });
  }

  // ------------------------------------------------------------------ rotas
  function parseHash(h = location.hash) {
    const raw = h.replace(/^#\/?/, "");
    const [path, qs = ""] = raw.split("?");
    const parts = path.split("/").filter(Boolean).map((p) => { try { return decodeURIComponent(p); } catch { return p; } });
    const q = Object.fromEntries(new URLSearchParams(qs));
    switch (parts[0]) {
      case "c": return { name: "room", id: parts[1], q };
      case "i": return { name: "item", id: parts[1], q };
      case "buscar": return { name: "search", q };
      case "relatorio": return { name: "report", q };
      case "dados": return { name: "data", q };
      default: return { name: "home", q };
    }
  }
  function hashOf(r) {
    switch (r.name) {
      case "room": return `#/c/${encodeURIComponent(r.id)}`;
      case "item": return `#/i/${encodeURIComponent(r.id)}`;
      case "search": {
        const q = Object.fromEntries(Object.entries(r.q || {}).filter(([, v]) => v));
        const qs = new URLSearchParams(q).toString();
        return "#/buscar" + (qs ? "?" + qs : "");
      }
      case "report": return "#/relatorio";
      case "data": return "#/dados";
      default: return "#/";
    }
  }
  let base = { name: "home", q: {} };
  let rendered = null;
  let inAppNavs = 0;
  let sheet = null;
  const scrollMemo = new Map();

  function onRoute() {
    if (!S.loaded) return;
    const r = parseHash();
    if (r.name === "item") {
      const it = D.itemById.get(r.id);
      if (!it) {
        if (sheet) finalize(sheet);
        toast("Este item não existe mais.");
        location.replace(rendered ? hashOf(base) : "#/");
        return;
      }
      if (!rendered) { base = { name: "room", id: it.room, q: {} }; renderView(true); }
      showItemSheet(it);
      return;
    }
    const hadSheet = !!sheet;
    if (sheet) finalize(sheet);
    if (rendered && rendered === hashOf(r) && (hadSheet || r.name === "search")) { base = r; return; }
    if (rendered) scrollMemo.set(rendered, window.scrollY);
    base = r;
    if (r.name === "search") searchLimit = 120;
    renderView(true);
  }
  function nav(hash) { inAppNavs++; location.hash = hash; }

  // ------------------------------------------------------------------ moldura: lateral, topo, abas
  function renderSide() {
    const el = $("#side");
    const cur = base;
    const cr = (name) => (cur.name === name ? ' aria-current="page"' : "");
    el.innerHTML = `
      <a class="brand" href="#/">${BRAND}<span class="brand-name">Inventário</span></a>
      <nav class="nav" aria-label="Seções">
        <a href="#/"${cr("home")}>${ic("home")}Início</a>
        <a href="#/buscar"${cr("search")}>${ic("search")}Buscar<kbd>/</kbd></a>
        <a href="#/relatorio"${cr("report")}>${ic("report")}Relatório</a>
        <a href="#/dados"${cr("data")}>${ic("gear")}Dados e ajustes</a>
      </nav>
      <div class="side-h"><h2>Cômodos</h2><span>${int(D.rooms.length)}</span></div>
      <div class="side-rooms">
        ${D.rooms.map((r) => `<a class="side-room" href="#/c/${encodeURIComponent(r.id)}"${cur.name === "room" && cur.id === r.id ? ' aria-current="page"' : ""}>
          <span class="mt soft">${esc(r.code)}</span><span class="rn">${esc(r.name)}</span><span class="rv">${numTxt(Math.round(D.roomTotals.get(r.id) || 0))}</span></a>`).join("")}
        <button type="button" class="side-room" data-act="room-new">${ic("plus", "sm")}<span class="rn">Novo cômodo</span></button>
      </div>
      <div class="side-foot">${PREVIEW ? "Prévia do app do Home Assistant" : `Versão ${esc(S.version)}`}</div>`;
  }

  function viewTitle(r) {
    if (r.name === "room") return D.roomById.get(r.id)?.name || "Cômodo";
    return { home: "Início", search: "Buscar", report: "Relatório", data: "Dados e ajustes" }[r.name] || "Inventário";
  }
  function renderTop() {
    const el = $("#topbar");
    const r = base;
    const crumbs = r.name === "home"
      ? `<span class="top-title">Início</span>`
      : `<a class="btn ghost icon only-narrow" href="#/" aria-label="Voltar ao início">${ic("back")}</a>
         <a class="crumb only-wide" href="#/">Início</a><span class="sep only-wide" aria-hidden="true">/</span>
         <span class="top-title sub">${esc(viewTitle(r))}</span>`;
    el.innerHTML = `
      <div class="crumbs">${crumbs}</div>
      <div class="top-actions">
        ${r.name !== "search" ? `<a class="btn ghost icon narrow" href="#/buscar" aria-label="Buscar">${ic("search")}</a>` : ""}
        ${r.name !== "room" ? `<button type="button" class="btn wide" data-act="catalog">${ic("scan")}Catalogar foto com IA</button>
        <button type="button" class="btn primary wide" data-act="item-new">${ic("plus")}Adicionar item</button>` : ""}
      </div>`;
    $$(".tabbar [data-tab]").forEach((a) => {
      const on = a.dataset.tab === r.name || (a.dataset.tab === "data" && r.name === "report") || (a.dataset.tab === "home" && r.name === "room");
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }

  // ------------------------------------------------------------------ renderização das telas
  function renderView(navigated) {
    const view = $("#view");
    const key = hashOf(base);
    const focus = navigated ? null : captureFocus();
    const y = window.scrollY;
    let html;
    try {
      switch (base.name) {
        case "room": html = viewRoom(base.id); break;
        case "search": html = viewSearch(base.q); break;
        case "report": html = viewReport(); break;
        case "data": html = viewData(); break;
        default: html = viewHome();
      }
    } catch (e) {
      console.error(e);
      html = `<div class="empty"><h2>Algo deu errado nesta tela</h2><p>${esc(e.message)}</p><div class="acts"><a class="btn" href="#/">Voltar ao início</a></div></div>`;
    }
    view.innerHTML = html;
    rendered = key;
    renderSide();
    renderTop();
    document.title = base.name === "home" ? "Inventário" : `Inventário – ${viewTitle(base)}`;
    if (navigated) {
      const memo = scrollMemo.get(key);
      window.scrollTo(0, memo || 0);
    } else {
      window.scrollTo(0, y);
      restoreFocus(focus);
    }
    afterRender();
  }
  function refreshAll() { if (S.loaded) renderView(false); if (sheet) { const it = D.itemById.get(parseHash().id); if (it) showItemSheet(it); } }
  function captureFocus() {
    const a = document.activeElement;
    if (!a || !a.dataset || !a.dataset.input || !$("#view").contains(a)) return null;
    return { key: a.dataset.input, start: a.selectionStart, end: a.selectionEnd };
  }
  function restoreFocus(f) {
    if (!f) return;
    const el = $(`#view [data-input="${f.key}"]`);
    if (!el) return;
    el.focus({ preventScroll: true });
    try { el.setSelectionRange(f.start, f.end); } catch { /* select */ }
  }
  function afterRender() {
    if (base.name === "home" && firstHome) {
      firstHome = false;
      const t = $(".tagswing");
      if (t && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        t.classList.add("go");
        t.addEventListener("animationend", () => t.classList.remove("go"), { once: true });
      }
    }
    if (base.name === "search") {
      const inp = $('#view [data-input="search-q"]');
      if (inp && (focusSearch || (!COARSE && document.activeElement === document.body))) {
        inp.focus({ preventScroll: true });
        try { inp.setSelectionRange(inp.value.length, inp.value.length); } catch { /* ok */ }
      }
      focusSearch = false;
    }
    if (base.name === "data") loadDataPanels();
  }

  // -- linhas reutilizáveis
  function itemRow(it, { toks = [], mode = "global" } = {}) {
    const ph = it.photos && it.photos[0];
    const room = D.roomById.get(it.room);
    let where;
    if (mode === "room") where = it.details ? hl(snippet(it.details), toks) : "";
    else where = hl([room?.name, it.zone].filter(Boolean).join(", "), toks);
    const qty = qtyClean(it.qty);
    return `<li><a class="irow" href="#/i/${encodeURIComponent(it.id)}">
      ${ph ? `<img class="thumb" src="${esc(src(ph))}" alt="" loading="lazy" decoding="async" width="56" height="56">` : `<span class="thumb">${ic("tag")}</span>`}
      <span class="ib"><span class="nm">${hl(it.name, toks)}</span>
        <span class="meta"><span class="mt soft">${esc(tagOf(it))}</span>${where ? `<span class="z">${where}</span>` : ""}</span></span>
      <span class="iv"><span class="val">${money(it.value)}</span>${qty !== "1" ? `<span class="qty">${esc(qtyShort(it.qty))}</span>` : ""}</span>
    </a></li>`;
  }
  function roomRow(r, max) {
    const v = D.roomTotals.get(r.id) || 0;
    const n = (D.byRoom.get(r.id) || []).length;
    return `<li><a class="rrow" href="#/c/${encodeURIComponent(r.id)}">
      <span class="mt">${esc(r.code)}</span>
      <span class="rn">${esc(r.name)}<small>${plural(n, "item", "itens")}</small></span>
      <span class="rv">${moneyR(v)}</span>
      <span class="bar"><i style="width:${max > 0 ? ((v / max) * 100).toFixed(2) : 0}%"></i></span>
      <span class="pct">${pctFmt(pct(v, D.total))}</span></a></li>`;
  }

  // -- início
  function viewHome() {
    if (!D.rooms.length) {
      return `<section class="hero welcome">
        <div class="tagwrap">
          <div class="tagswing">
            <svg class="string" viewBox="0 0 120 140" aria-hidden="true"><path d="M36 132 C 35 104, 27 62, 22 -60"/></svg>
            <div class="tag" role="img" aria-label="Inventário">
              <div class="tag-body"><p class="tag-label">Bem-vindo</p><p class="tag-value">Inventário</p><p class="tag-sub">Cômodos, itens, fotos e valores</p></div>
            </div>
          </div>
        </div>
        <div class="welcome-text">
          <h1>Vamos começar</h1>
          <p>Já tem um inventário salvo? Importe o arquivo de backup (.zip) e tudo volta, com fotos e valores. Se preferir, comece do zero criando o primeiro cômodo.</p>
          <div class="acts"><button type="button" class="btn primary" data-act="import-file">${ic("upload")}Importar backup</button>
            <button type="button" class="btn" data-act="room-new">${ic("plus")}Começar do zero</button></div>
          <p class="muted" style="font-size:14px;margin:0">O backup é o arquivo .zip criado em Dados e ajustes, ou o que você recebeu junto com o app.</p>
        </div>
      </section>`;
    }
    const n = S.items.length;
    const byValue = [...S.items].sort((a, b) => (b.value || 0) - (a.value || 0));
    const recent = [...S.items].sort((a, b) => parseDate(b.createdAt) - parseDate(a.createdAt)).slice(0, 6);
    const maxRoom = Math.max(0, ...D.rooms.map((r) => D.roomTotals.get(r.id) || 0));
    const bigRoom = D.rooms.find((r) => (D.roomTotals.get(r.id) || 0) === maxRoom);
    const cats = [...D.catTotals.entries()].sort((a, b) => b[1].value - a[1].value);
    const maxCat = cats.length ? cats[0][1].value : 0;
    const top = byValue[0], last = recent[0];
    return `
    <section class="hero">
      <div class="tagwrap">
        <div class="tagswing">
          <svg class="string" viewBox="0 0 120 140" aria-hidden="true"><path d="M36 132 C 35 104, 27 62, 22 -60"/></svg>
          <div class="tag" role="img" aria-label="Patrimônio: ${esc(money(D.total))} em ${esc(plural(n, "item", "itens"))}">
            <div class="tag-body">
              <p class="tag-label">Patrimônio</p>
              <p class="tag-value"><span class="cur">R$</span>${numTxt(Math.round(D.total))}</p>
              <p class="tag-sub">${plural(n, "item", "itens")} em ${plural(D.rooms.length, "cômodo", "cômodos")}</p>
            </div>
          </div>
        </div>
      </div>
      <dl class="facts">
        ${top ? `<div><dt>Mais valioso</dt><dd><a href="#/i/${encodeURIComponent(top.id)}">${esc(top.name)}</a></dd><dd class="fv">${money(top.value)}</dd></div>` : ""}
        ${bigRoom ? `<div><dt>Maior cômodo</dt><dd><a href="#/c/${encodeURIComponent(bigRoom.id)}">${esc(bigRoom.name)}</a></dd><dd class="fv">${pctFmt(pct(maxRoom, D.total))}</dd></div>` : ""}
        ${last ? `<div><dt>Último cadastro</dt><dd><a href="#/i/${encodeURIComponent(last.id)}">${esc(last.name)}</a></dd><dd class="fv muted">${esc(ago(last.createdAt))}</dd></div>` : ""}
        <div><dt>Fotos</dt><dd>${plural(D.photoCount, "foto guardada", "fotos guardadas")}</dd><dd class="fv"></dd></div>
      </dl>
    </section>
    <form class="homesearch" data-form="homesearch" role="search">
      ${ic("search")}<input class="input" type="search" name="q" data-input="home-q" placeholder="Buscar entre ${esc(plural(n, "item", "itens"))}" aria-label="Buscar itens" autocomplete="off" enterkeyhint="search"><kbd>/</kbd>
    </form>
    <section class="sec">
      <div class="sec-h"><h2>Cômodos</h2><button type="button" class="btn ghost sm" data-act="room-new">${ic("plus", "sm")}Novo cômodo</button></div>
      <ul class="rows">${D.rooms.map((r) => roomRow(r, maxRoom)).join("")}</ul>
    </section>
    <div class="cols">
      <section class="sec">
        <div class="sec-h"><h2>Categorias</h2><span class="aside">${plural(cats.length, "categoria", "categorias")}</span></div>
        <ul class="rows">${cats.map(([c, t]) => `<li><a class="rrow nocode" href="#/buscar?cat=${c}&amp;ord=val">
          <span class="rn">${esc(CAT[c])}<small>${plural(t.count, "item", "itens")}</small></span><span class="rv">${moneyR(t.value)}</span>
          <span class="bar"><i style="width:${maxCat ? ((t.value / maxCat) * 100).toFixed(2) : 0}%"></i></span><span class="pct">${pctFmt(pct(t.value, D.total))}</span></a></li>`).join("")}</ul>
      </section>
      <section class="sec">
        <div class="sec-h"><h2>Mais valiosos</h2><a class="aside" href="#/buscar?ord=val">Ver todos</a></div>
        <ul class="ilist">${byValue.slice(0, 7).map((it) => itemRow(it)).join("")}</ul>
      </section>
    </div>
    <section class="sec">
      <div class="sec-h"><h2>Cadastrados recentemente</h2><a class="aside" href="#/buscar?ord=new">Ver todos</a></div>
      <ul class="ilist">${recent.map((it) => itemRow(it)).join("")}</ul>
    </section>`;
  }
  const emptyMark = () => '<svg class="empty-mark" viewBox="0 0 74 50" aria-hidden="true"><path d="M18 2h52a2 2 0 0 1 2 2v42a2 2 0 0 1-2 2H18L2 33V17z" fill="none" stroke="currentColor" stroke-width="2.5"/><circle cx="17" cy="25" r="5" fill="none" stroke="currentColor" stroke-width="2.5"/></svg>';

  // -- cômodo
  function viewRoom(id) {
    const r = D.roomById.get(id);
    if (!r) return `<div class="empty">${emptyMark()}<h2>Cômodo não encontrado</h2><p>Ele pode ter sido excluído ou renomeado.</p><div class="acts"><a class="btn" href="#/">Voltar ao início</a></div></div>`;
    const list = D.byRoom.get(id) || [];
    const total = D.roomTotals.get(id) || 0;
    const photos = r.photos || [];
    const zones = new Set(list.map((i) => i.zone || "Sem zona"));
    return `
    <section class="rhead">
      <div class="rhead-top">
        <div class="rhead-name"><span class="mt lg">${esc(r.code)}</span><h1>${esc(r.name)}</h1>
          <div class="stats"><span><b>${int(list.length)}</b> ${list.length === 1 ? "item" : "itens"}</span><span><b>${int(zones.size)}</b> ${zones.size === 1 ? "zona" : "zonas"}</span><span><b>${int(photos.length)}</b> ${photos.length === 1 ? "foto" : "fotos"}</span></div>
        </div>
        <div class="rhead-val"><div class="big">${moneyR(total)}</div><div class="small">${pctFmt(pct(total, D.total))} do patrimônio</div></div>
      </div>
      <div class="rhead-actions">
        <button type="button" class="btn primary" data-act="item-new" data-room="${esc(id)}">${ic("plus")}Adicionar item</button>
        <button type="button" class="btn" data-act="catalog" data-room="${esc(id)}" aria-label="Catalogar foto com IA">${ic("scan")}<span class="lbl">Catalogar foto com IA</span><span class="lbl-short">Catalogar</span></button>
        <button type="button" class="btn ghost" data-act="room-edit" data-room="${esc(id)}" aria-label="Editar cômodo">${ic("edit")}<span class="lbl">Editar cômodo</span></button>
      </div>
    </section>
    <div class="strip" role="list" aria-label="Fotos do cômodo">
      ${photos.map((p, i) => {
        const n = (D.photoItems.get(p.file) || []).length;
        return `<button type="button" class="ph" role="listitem" data-act="viewer-room" data-room="${esc(id)}" data-i="${i}" aria-label="${esc(p.label || `Foto ${i + 1}`)}">
          <img src="${esc(src(p.file))}" alt="" loading="lazy" decoding="async">${n ? `<span class="cnt">${plural(n, "item", "itens")}</span>` : ""}</button>`;
      }).join("")}
      <button type="button" class="ph add" data-act="room-photo-add" data-room="${esc(id)}">${ic("plus")}Foto do cômodo</button>
    </div>
    ${list.length > 6 ? `<div class="filterbar"><label class="search">${ic("search")}<span class="sr">Filtrar itens deste cômodo</span>
      <input class="input" type="search" data-input="room-filter" data-room="${esc(id)}" placeholder="Filtrar neste cômodo" value="${esc(roomFilter[id] || "")}" autocomplete="off"></label></div>` : ""}
    <div id="zones">${zonesHtml(id)}</div>`;
  }
  function zonesHtml(id) {
    const all = D.byRoom.get(id) || [];
    if (!all.length) {
      return `<div class="empty">${emptyMark()}<h2>Nenhum item aqui ainda</h2><p>Adicione o primeiro item ou tire uma foto e deixe a IA listar o que aparece nela.</p>
        <div class="acts"><button class="btn primary" data-act="item-new" data-room="${esc(id)}">${ic("plus")}Adicionar item</button>
        <button class="btn" data-act="catalog" data-room="${esc(id)}">${ic("scan")}Catalogar foto com IA</button></div></div>`;
    }
    const toks = tokens(roomFilter[id] || "");
    const list = toks.length ? all.filter((it) => matches(it, toks)) : all;
    if (!list.length) return `<div class="empty"><h2>Nada com “${esc(roomFilter[id])}”</h2><p>Tente outra palavra ou limpe o filtro.</p></div>`;
    const groups = new Map();
    for (const it of list) {
      const z = it.zone || "Sem zona";
      if (!groups.has(z)) groups.set(z, []);
      groups.get(z).push(it);
    }
    const ordered = [...groups.entries()].sort((a, b) => Math.min(...a[1].map((i) => i.seq || 0)) - Math.min(...b[1].map((i) => i.seq || 0)));
    return ordered.map(([z, its]) => `<section class="zone">
      <div class="zone-h"><h3>${hl(z, toks)}</h3><span class="zs">${plural(its.length, "item", "itens")}<b>${moneyR(its.reduce((s, i) => s + (+i.value || 0), 0))}</b></span></div>
      <ul class="ilist">${its.map((it) => itemRow(it, { toks, mode: "room" })).join("")}</ul></section>`).join("");
  }
  function matches(it, toks) {
    const room = D.roomById.get(it.room);
    const hay = norm(`${it.name} ${it.details} ${it.zone} ${room?.name || ""} ${tagOf(it)} ${CAT[it.cat] || ""}`);
    return toks.every((t) => hay.includes(t));
  }

  // -- busca
  function viewSearch(q) {
    const ord = q.ord || (q.q ? "rel" : "val");
    return `
    <section class="sbar">
      <form class="q" data-form="search" role="search">${ic("search")}
        <input class="input" type="search" name="q" data-input="search-q" value="${esc(q.q || "")}" placeholder="Nome, marca, detalhe ou zona" aria-label="Buscar itens" autocomplete="off" enterkeyhint="search">
        <button type="button" class="btn ghost icon sm clear" data-act="search-clear" aria-label="Limpar busca"${q.q ? "" : " hidden"}>${ic("close", "sm")}</button>
      </form>
      <div class="sfilters">
        <select class="select" data-input="search-room" aria-label="Cômodo"><option value="">Todos os cômodos</option>
          ${D.rooms.map((r) => `<option value="${esc(r.id)}"${r.id === q.room ? " selected" : ""}>${esc(r.name)}</option>`).join("")}</select>
        <select class="select" data-input="search-cat" aria-label="Categoria"><option value="">Todas as categorias</option>
          ${CATS.map(([k, v]) => `<option value="${k}"${k === q.cat ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
        <select class="select ord" data-input="search-ord" aria-label="Ordenar">
          ${ORDERS.map(([k, v]) => `<option value="${k}"${k === ord ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
      </div>
    </section>
    <div id="results">${resultsHtml(q)}</div>`;
  }
  function searchItems(q) {
    const toks = tokens(q.q || "");
    let list = S.items;
    if (q.room) list = list.filter((i) => i.room === q.room);
    if (q.cat) list = list.filter((i) => (CAT[i.cat] ? i.cat : "outros") === q.cat);
    if (toks.length) list = list.filter((i) => matches(i, toks));
    const ord = q.ord || (toks.length ? "rel" : "val");
    const score = (it) => {
      const n = norm(it.name);
      let s = 0;
      for (const t of toks) { if (n.startsWith(t) || n.includes(" " + t)) s += 3; else if (n.includes(t)) s += 2; else s += 0.5; }
      return s;
    };
    const cmp = {
      rel: (a, b) => score(b) - score(a) || (b.value || 0) - (a.value || 0),
      val: (a, b) => (b.value || 0) - (a.value || 0),
      valasc: (a, b) => (a.value || 0) - (b.value || 0),
      az: (a, b) => a.name.localeCompare(b.name, "pt-BR"),
      new: (a, b) => parseDate(b.createdAt) - parseDate(a.createdAt),
      code: (a, b) => (D.roomById.get(a.room)?.order ?? 99) - (D.roomById.get(b.room)?.order ?? 99) || (a.seq || 0) - (b.seq || 0),
    }[ord] || ((a, b) => (b.value || 0) - (a.value || 0));
    return { list: [...list].sort(cmp), toks };
  }
  function resultsHtml(q) {
    const { list, toks } = searchItems(q);
    const sum = list.reduce((s, i) => s + (+i.value || 0), 0);
    if (!list.length) {
      const filtered = q.room || q.cat;
      return `<div class="empty">${emptyMark()}<h2>${q.q ? `Nada encontrado para “${esc(q.q)}”` : "Nenhum item com esses filtros"}</h2>
        <p>${filtered ? "Tente limpar os filtros de cômodo e categoria." : "Tente outra palavra, como a marca ou o tipo do objeto."}</p>
        ${filtered ? `<div class="acts"><button class="btn" data-act="search-reset">Limpar filtros</button></div>` : ""}</div>`;
    }
    const shown = list.slice(0, searchLimit);
    return `<div class="ssum"><span>${plural(list.length, "item", "itens")}</span><b>${moneyR(sum)}</b></div>
      <ul class="ilist">${shown.map((it) => itemRow(it, { toks })).join("")}</ul>
      ${list.length > shown.length ? `<div class="more"><button class="btn" data-act="more-results">Mostrar mais ${int(Math.min(120, list.length - shown.length))}</button></div>` : ""}`;
  }
  function updateSearch(patch) {
    base.q = { ...base.q, ...patch };
    if (!base.q.q && base.q.ord === "rel") delete base.q.ord;
    try { history.replaceState(history.state, "", hashOf(base)); } catch { /* sem histórico */ }
    rendered = hashOf(base);
    searchLimit = 120;
    $("#results").innerHTML = resultsHtml(base.q);
    const clear = $('#view [data-act="search-clear"]');
    if (clear) clear.hidden = !base.q.q;
  }

  // -- relatório
  function viewReport() {
    const withPhotos = LS.get("reportPhotos", true);
    const now = new Date();
    return `
    <div class="rep-tools no-print">
      <label class="check"><input type="checkbox" data-input="rep-photos"${withPhotos ? " checked" : ""}> Mostrar fotos</label>
      <button type="button" class="btn primary" data-act="print">${ic("printer")}Imprimir ou salvar PDF</button>
    </div>
    <article class="report">
      <h1>Inventário da casa</h1>
      <p class="rmeta">Gerado em ${esc(dfLong.format(now))}. Valores estimados de mercado de usados, em reais.</p>
      <div class="rtotal">
        <div><span>Patrimônio</span><b>${money(D.total)}</b></div>
        <div><span>Itens</span><b>${int(S.items.length)}</b></div>
        <div><span>Cômodos</span><b>${int(D.rooms.length)}</b></div>
      </div>
      <table class="rtable"><thead><tr><th>Cômodo</th><th class="r">Itens</th><th class="r">Valor</th><th class="r">Parte</th></tr></thead>
        <tbody>${D.rooms.map((r) => { const v = D.roomTotals.get(r.id) || 0; return `<tr><td><span class="c">${esc(r.code)}</span> ${esc(r.name)}</td><td class="r">${int((D.byRoom.get(r.id) || []).length)}</td><td class="r">${money(v)}</td><td class="r">${pctFmt(pct(v, D.total))}</td></tr>`; }).join("")}</tbody>
        <tfoot><tr><td>Total</td><td class="r">${int(S.items.length)}</td><td class="r">${money(D.total)}</td><td class="r">100%</td></tr></tfoot></table>
      ${D.rooms.filter((r) => (D.byRoom.get(r.id) || []).length).map((r) => {
        const its = D.byRoom.get(r.id) || [];
        return `<section class="rep-room"><h2><span class="mt">${esc(r.code)}</span>${esc(r.name)}</h2>
          <p class="rs">${plural(its.length, "item", "itens")}, ${money(D.roomTotals.get(r.id) || 0)}</p>
          <table class="rtable"><thead><tr>${withPhotos ? '<th class="t"><span class="sr">Foto</span></th>' : ""}<th>Código</th><th>Item</th><th>Zona</th><th class="r">Qtd.</th><th class="r">Valor</th></tr></thead><tbody>
          ${its.map((it) => `<tr>${withPhotos ? `<td class="t">${it.photos && it.photos[0] ? `<img src="${esc(src(it.photos[0]))}" alt="" width="44" height="44">` : ""}</td>` : ""}
            <td class="c">${esc(tagOf(it))}</td><td>${esc(it.name)}${it.details ? `<span class="d">${esc(snippet(it.details, 140))}</span>` : ""}</td>
            <td>${esc(it.zone || "")}</td><td class="r">${esc(qtyClean(it.qty))}</td><td class="r">${money(it.value)}</td></tr>`).join("")}
          </tbody><tfoot><tr>${withPhotos ? "<td></td>" : ""}<td colspan="4">Subtotal</td><td class="r">${money(D.roomTotals.get(r.id) || 0)}</td></tr></tfoot></table></section>`;
      }).join("")}
      <p class="rep-foot">Inventário mantido no app Inventário do Home Assistant. Dados em arquivos abertos (JSON e JPG).</p>
    </article>`;
  }

  // -- dados e ajustes
  function viewData() {
    const theme = LS.get("theme", "auto");
    return `
    <section class="panel" id="p-export" style="margin-top:14px">
      <h2>Exportar</h2>
      <p class="lead">Baixe o inventário para abrir no Excel, guardar ou levar para outro programa. Os arquivos são abertos e legíveis.</p>
      <ul class="opts">
        <li><div class="ot"><b>Planilha (CSV)</b><span>Abre no Excel e no Google Planilhas, com um item por linha.</span></div><div class="oa"><button class="btn" data-act="export" data-kind="csv">${ic("download")}Baixar CSV</button></div></li>
        <li><div class="ot"><b>Dados completos (JSON)</b><span>Todos os campos, para backup ou para outro sistema.</span></div><div class="oa"><button class="btn" data-act="export" data-kind="json">${ic("download")}Baixar JSON</button></div></li>
        <li><div class="ot"><b>Tudo com fotos (ZIP)</b><span>JSON, CSV e todas as fotos num arquivo só.</span></div><div class="oa"><button class="btn" data-act="export" data-kind="zip">${ic("download")}Baixar ZIP</button></div></li>
        <li><div class="ot"><b>Relatório para seguro</b><span>Lista por cômodo com fotos, pronta para imprimir ou salvar em PDF.</span></div><div class="oa"><a class="btn" href="#/relatorio">${ic("report")}Abrir relatório</a></div></li>
      </ul>
    </section>
    <section class="panel" id="p-backup">
      <h2>Backup na pasta share</h2>
      <p class="lead">Cria uma cópia completa (com fotos) em <span class="codepath">share/inventario</span>, que você acessa pela rede do Home Assistant. Os backups do próprio Home Assistant também incluem o inventário.</p>
      <div data-slot="backups"><p class="muted">Carregando backups…</p></div>
    </section>
    <section class="panel" id="p-ai">
      <h2>Leitura de fotos por IA</h2>
      <p class="lead">O app usa a integração de IA que estiver configurada no Home Assistant (Anthropic Claude, OpenAI, Google Gemini ou um modelo local pelo Ollama). Dá para trocar de IA quando quiser, sem mexer no inventário.</p>
      <div data-slot="ai"><p class="muted">Verificando…</p></div>
    </section>
    <section class="panel" id="p-rooms">
      <h2>Cômodos</h2>
      <p class="lead">Mude nomes, códigos e a ordem em que os cômodos aparecem.</p>
      <ul class="opts">${D.rooms.map((r, i) => `<li><div class="ot"><b><span class="mt soft">${esc(r.code)}</span> ${esc(r.name)}</b><span>${plural((D.byRoom.get(r.id) || []).length, "item", "itens")}, ${plural((r.photos || []).length, "foto", "fotos")}</span></div>
        <div class="oa"><button class="btn sm icon" data-act="room-up" data-room="${esc(r.id)}" aria-label="Subir ${esc(r.name)}"${i === 0 ? " disabled" : ""}>${ic("up", "sm")}</button>
        <button class="btn sm icon" data-act="room-down" data-room="${esc(r.id)}" aria-label="Descer ${esc(r.name)}"${i === D.rooms.length - 1 ? " disabled" : ""}>${ic("down", "sm")}</button>
        <button class="btn sm" data-act="room-edit" data-room="${esc(r.id)}">${ic("edit", "sm")}Editar</button></div></li>`).join("")}
        <li><div class="ot"><b>Novo cômodo</b><span>Uma área nova da casa, como depósito ou garagem.</span></div><div class="oa"><button class="btn" data-act="room-new">${ic("plus")}Novo cômodo</button></div></li>
      </ul>
    </section>
    <section class="panel" id="p-history">
      <h2>Versões anteriores</h2>
      <p class="lead">O app guarda sozinho uma cópia do inventário a cada 10 minutos de uso. Se algo sair errado, volte para uma versão anterior.</p>
      <div data-slot="history"><p class="muted">Carregando…</p></div>
    </section>
    <section class="panel" id="p-import">
      <h2>Importar</h2>
      <p class="lead">Traz um inventário de um arquivo: o backup .zip, com as fotos, ou um .json exportado pelo app. Antes de importar, o app guarda uma cópia do que existe hoje.</p>
      <ul class="opts"><li><div class="ot"><b>Importar backup ou JSON</b><span>Funciona pelo celular: escolha o arquivo nos seus downloads.</span></div><div class="oa"><button class="btn" data-act="import-file">${ic("upload")}Escolher arquivo</button></div></li></ul>
    </section>
    <section class="panel" id="p-look">
      <h2>Aparência</h2>
      <ul class="opts"><li><div class="ot"><b>Tema</b><span>Automático segue o modo claro ou escuro do aparelho.</span></div>
        <div class="oa"><div class="seg" role="group" aria-label="Tema">
          ${[["auto", "Automático"], ["light", "Claro"], ["dark", "Escuro"]].map(([k, v]) => `<button type="button" data-act="theme" data-theme="${k}" aria-pressed="${theme === k}">${v}</button>`).join("")}
        </div></div></li></ul>
    </section>
    <section class="panel">
      <h2>Sobre</h2>
      <p class="lead">${PREVIEW ? "Esta é uma prévia do app do Home Assistant. Aqui as alterações ficam só nesta tela." : `Inventário ${esc(S.version)}. Os dados ficam em <span class="codepath">inventario.json</span> e as fotos em JPG, dentro do app. Funciona sem internet; só a leitura por IA usa a integração de IA do Home Assistant.`}</p>
    </section>`;
  }

  async function loadDataPanels() {
    const bslot = $('[data-slot="backups"]');
    const hslot = $('[data-slot="history"]');
    const aslot = $('[data-slot="ai"]');
    try {
      const b = await API.get("api/backups");
      if (bslot && document.contains(bslot)) {
        bslot.innerHTML = `<ul class="opts">
          <li><div class="ot"><b>Criar backup agora</b><span>${b.available === false ? "A pasta share não está disponível." : "Salva um arquivo .zip com dados e fotos."}</span></div>
            <div class="oa"><button class="btn primary" data-act="backup-create"${b.available === false ? " disabled" : ""}>${ic("archive")}Criar backup</button></div></li>
          ${(b.backups || []).slice(0, 12).map((x) => `<li><div class="ot"><b>${esc(x.name)}</b><span>${esc(dateTime(x.date))}, ${esc(fmtSize(x.size))}</span></div>
            <div class="oa"><button class="btn sm" data-act="backup-restore" data-name="${esc(x.name)}">${ic("history", "sm")}Restaurar</button></div></li>`).join("")}
        </ul>`;
      }
    } catch (e) { if (bslot) bslot.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
    try {
      const h = await API.get("api/history");
      if (hslot && document.contains(hslot)) {
        const list = h.history || [];
        hslot.innerHTML = list.length ? `<ul class="opts">${list.slice(0, 10).map((x) => `<li><div class="ot"><b>${esc(dateTime(x.date))}</b><span>${esc(ago(x.date))}</span></div>
          <div class="oa"><button class="btn sm" data-act="history-restore" data-name="${esc(x.name)}">${ic("history", "sm")}Voltar para esta versão</button></div></li>`).join("")}</ul>`
          : `<p class="muted">Ainda não há versões anteriores. Elas aparecem depois das primeiras alterações.</p>`;
      }
    } catch (e) { if (hslot) hslot.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
    if (aslot) renderAiPanel(aslot, await aiStatus(true));
  }
  const fmtSize = (n) => (n > 1048576 ? `${(n / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

  // ------------------------------------------------------------------ IA
  let aiCache = { at: 0, data: null };
  async function aiStatus(force = false) {
    if (!force && aiCache.data && Date.now() - aiCache.at < 60000) return aiCache.data;
    try { aiCache = { at: Date.now(), data: await API.get("api/ai/status") }; } catch (e) { aiCache = { at: Date.now(), data: { ready: false, reason: "error", message: e.message, entities: [] } }; }
    return aiCache.data;
  }
  function aiReasonText(st) {
    switch (st.reason) {
      case "no_api": return "O app não tem acesso à API do Home Assistant.";
      case "no_entity": return "Nenhuma integração de IA encontrada no Home Assistant.";
      case "no_vision": return st.selected ? "A IA escolhida não aceita fotos. Escolha outra." : "As IAs configuradas não aceitam fotos.";
      case "error": return st.message || "Não deu para consultar o Home Assistant.";
      case "preview": return "Na prévia, a IA não lê as fotos de verdade. No Home Assistant, ela usa a integração de IA configurada lá.";
      default: { const e = (st.entities || []).find((x) => x.id === st.selected); return e ? `Usando ${e.name}.` : "Usando a IA preferida do Home Assistant."; }
    }
  }
  const AI_STEPS = `<ol class="steps">
    <li>No Home Assistant, abra Configurações, Dispositivos e serviços, Adicionar integração.</li>
    <li>Escolha a IA: Anthropic (Claude), OpenAI, Google Gemini ou Ollama (modelo local, de graça). Cole a chave de API quando pedir.</li>
    <li>Na integração, adicione uma tarefa de IA (AI Task) e use um modelo que entenda imagens.</li>
    <li>Volte aqui em Dados e ajustes e escolha essa IA na lista.</li></ol>`;
  function renderAiPanel(slot, st) {
    if (st.preview) {
      slot.innerHTML = `<ul class="opts"><li><div class="ot"><b><span class="status warn"><i></i>Exemplo simulado na prévia</span></b><span>Aqui a IA não lê as fotos de verdade: os botões mostram como fica a revisão. No Home Assistant, a leitura usa a integração de IA que você configurar.</span></div></li></ul><div style="margin-top:12px"><b>Como configurar no Home Assistant</b>${AI_STEPS}</div>`;
      return;
    }
    const ents = st.entities || [];
    const cls = st.ready ? "ok" : st.reason === "no_vision" ? "warn" : "bad";
    slot.innerHTML = `<ul class="opts">
      <li><div class="ot"><b><span class="status ${cls}"><i></i>${st.ready ? "Pronta para ler fotos" : "Não configurada"}</span></b><span>${esc(aiReasonText(st))}</span></div>
        <div class="oa"><button class="btn sm" data-act="ai-refresh">${ic("refresh", "sm")}Verificar de novo</button></div></li>
      ${ents.length ? `<li><div class="ot"><b>IA usada pelo app</b><span>Padrão do Home Assistant usa a IA preferida definida lá.</span></div>
        <div class="oa"><select class="select" data-input="ai-entity" aria-label="IA usada pelo app" style="min-width:240px">
          <option value="">Padrão do Home Assistant</option>
          ${ents.map((e) => `<option value="${esc(e.id)}"${e.id === st.selected ? " selected" : ""}${e.attachments ? "" : " disabled"}>${esc(e.name)}${e.attachments ? "" : " (não lê fotos)"}</option>`).join("")}
        </select></div></li>` : ""}
    </ul>${st.ready ? "" : `<div style="margin-top:12px"><b>Como configurar</b>${AI_STEPS}</div>`}`;
  }
  async function needAi() {
    const st = await aiStatus();
    if (st.ready) return true;
    const entry = openDialog({
      cls: "modal narrow", label: "Leitura por IA",
      html: `<div class="dlg"><div class="dlg-h"><h2>Leitura por IA</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b"><p style="margin-top:0"><span class="status ${st.reason === "no_vision" ? "warn" : "bad"}"><i></i>${esc(aiReasonText(st))}</span></p>
        <p>Para a IA ler as fotos, o Home Assistant precisa de uma integração de IA com tarefa de IA (AI Task):</p>${AI_STEPS}
        <p class="muted" style="margin-bottom:0">Enquanto isso, você pode cadastrar os itens à mão normalmente.</p></div>
        <div class="dlg-f"><a class="btn" href="#/dados" data-x>Abrir Dados e ajustes</a><button class="btn primary" data-x>Entendi</button></div></div>`,
    });
    entry.dlg.addEventListener("click", (e) => { if (e.target.closest("[data-x]")) requestClose(entry, { force: true }); });
    return false;
  }

  // ------------------------------------------------------------------ fotos: processamento e envio
  function loadImg(url) {
    return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = () => rej(new Error("Não deu para abrir esta imagem. Use JPG ou PNG.")); im.src = url; });
  }
  function toJpeg(img, max, q) {
    const w0 = img.width || img.naturalWidth, h0 = img.height || img.naturalHeight;
    const k = Math.min(1, max / Math.max(w0, h0));
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w0 * k)); c.height = Math.max(1, Math.round(h0 * k));
    const g = c.getContext("2d");
    g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);
    g.imageSmoothingQuality = "high";
    g.drawImage(img, 0, 0, c.width, c.height);
    return new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error("Não deu para processar a foto."))), "image/jpeg", q));
  }
  const b64 = (blob) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(",")[1]); r.onerror = () => rej(r.error); r.readAsDataURL(blob); });
  async function uploadPhoto(file) {
    if (!file || !/^image\//.test(file.type || "image/")) throw new Error("Escolha um arquivo de imagem (JPG ou PNG).");
    let img, url;
    try { img = await createImageBitmap(file, { imageOrientation: "from-image" }); }
    catch { url = URL.createObjectURL(file); img = await loadImg(url); }
    try {
      const full = await toJpeg(img, 1600, 0.85);
      const thumb = await toJpeg(img, 480, 0.78);
      const res = await API.post("api/photos", { full: await b64(full), thumb: await b64(thumb) });
      if (window.INV_PHOTO_STORE) window.INV_PHOTO_STORE(res.file, full, thumb);
      return res.file;
    } finally { if (url) URL.revokeObjectURL(url); if (img && img.close) img.close(); }
  }
  let pickCb = null;
  function pickFiles(cb, { camera = false, multiple = true } = {}) {
    pickCb = cb;
    const inp = camera ? $("#pick-camera") : $("#pick-files");
    inp.multiple = multiple && !camera;
    inp.value = "";
    inp.click();
  }
  ["#pick-files", "#pick-camera"].forEach((s) => $(s).addEventListener("change", (e) => {
    const files = [...e.target.files];
    e.target.value = "";
    if (files.length && pickCb) pickCb(files);
  }));
  function imageFiles(list) { return [...(list || [])].filter((f) => /^image\//.test(f.type)); }
  function wireDrop(entry, el, onFiles) {
    entry.onFiles = onFiles;
    el.addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); el.classList.add("over"); } });
    el.addEventListener("dragleave", (e) => { if (!el.contains(e.relatedTarget)) el.classList.remove("over"); });
    el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("over"); const f = imageFiles(e.dataTransfer.files); if (f.length) onFiles(f); });
  }
  document.addEventListener("paste", (e) => {
    const top = topEntry();
    if (!top || !top.onFiles) return;
    const f = imageFiles(e.clipboardData && e.clipboardData.files);
    if (f.length) { e.preventDefault(); top.onFiles(f); }
  });

  function roomPhotoPicker(roomId, already = []) {
    const r = D.roomById.get(roomId);
    const photos = (r?.photos || []).filter((p) => !already.includes(p.file));
    return new Promise((resolve) => {
      let chosen = [];
      const entry = openDialog({
        cls: "modal wide", label: "Fotos do cômodo",
        html: `<div class="dlg"><div class="dlg-h"><h2>Fotos de ${esc(r?.name || "cômodo")}</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
          <div class="dlg-b">${photos.length ? `<div class="pick">${photos.map((p) => `<label><input type="checkbox" value="${esc(p.file)}"><img src="${esc(src(p.file))}" alt="" loading="lazy">${p.label ? `<span>${esc(p.label)}</span>` : ""}</label>`).join("")}</div>`
            : `<p class="muted" style="margin:0">Este cômodo ainda não tem outras fotos.</p>`}</div>
          <div class="dlg-f"><span class="grow"></span><button class="btn ghost" data-x>Cancelar</button><button class="btn primary" data-ok disabled>Usar fotos</button></div></div>`,
        onClose: () => resolve(chosen),
      });
      const okBtn = $("[data-ok]", entry.dlg);
      entry.dlg.addEventListener("change", () => {
        const n = $$("input:checked", entry.dlg).length;
        okBtn.disabled = !n;
        okBtn.textContent = n > 1 ? `Usar ${n} fotos` : "Usar foto";
      });
      entry.dlg.addEventListener("click", (e) => {
        if (e.target.closest("[data-x]")) requestClose(entry, { force: true });
        if (e.target.closest("[data-ok]")) { chosen = $$("input:checked", entry.dlg).map((i) => i.value); requestClose(entry, { force: true }); }
      });
    });
  }

  // ------------------------------------------------------------------ detalhe do item
  function showItemSheet(it) {
    const html = itemSheetHtml(it);
    if (sheet) { sheet.dlg.innerHTML = html; sheet.dlg.setAttribute("aria-label", it.name); sheet.itemId = it.id; sheet.closing = false; return; }
    sheet = openDialog({ cls: "sheet", html, routed: true, label: it.name });
    sheet.itemId = it.id;
    sheet.onRouteClose = leaveItem;
    sheet.onClose = () => { sheet = null; };
  }
  function leaveItem() {
    if (inAppNavs > 0) history.back();
    else location.replace(hashOf(base));
  }
  function galleryHtml(it, i = 0) {
    const ph = it.photos || [];
    return `<div class="gal"><button type="button" class="gal-main" data-act="viewer-item" data-id="${esc(it.id)}" data-i="${i}" aria-label="Ampliar foto">
        <img src="${esc(src(ph[i], "photos"))}" alt="Foto de ${esc(it.name)}" decoding="async"></button></div>
      ${ph.length > 1 ? `<div class="gal-thumbs">${ph.map((p, k) => `<button type="button" data-act="gal" data-id="${esc(it.id)}" data-i="${k}" aria-current="${k === i}" aria-label="Foto ${k + 1}"><img src="${esc(src(p))}" alt=""></button>`).join("")}</div>` : ""}`;
  }
  function itemSheetHtml(it) {
    const room = D.roomById.get(it.room) || { id: it.room, code: "?", name: it.room };
    const n = qtyNum(it.qty);
    const by = (who) => (who ? ` <span class="by">por ${esc(who)}</span>` : "");
    const lbl = (icon, text) => `${ic(icon)}<span class="lbl">${text}</span>`;
    return `<div class="dlg">
      <div class="dlg-h"><span class="mt">${esc(tagOf(it))}</span><h2 class="sr">${esc(it.name)}</h2><span style="flex:1"></span>
        <button type="button" class="btn ghost icon" data-act="sheet-close" aria-label="Fechar">${ic("close")}</button></div>
      <div class="dlg-b">
        <div data-slot="gallery">${(it.photos || []).length ? galleryHtml(it, 0)
          : `<div class="gal"><div class="gal-none">${ic("image", "lg")}<span>Sem foto</span><button type="button" class="btn sm" data-act="item-edit" data-id="${esc(it.id)}">Adicionar foto</button></div></div>`}</div>
        <div class="ihead"><h1>${esc(it.name)}</h1>
          <div class="ival"><span class="big">${money(it.value)}</span>${n && n > 1 ? `<span class="unit">${int(n)} unidades, ${money((+it.value || 0) / n)} cada</span>` : qtyClean(it.qty) !== "1" ? `<span class="unit">${esc(qtyLabel(it.qty))}</span>` : ""}</div></div>
        ${it.details ? `<p class="idet">${esc(it.details)}</p>` : ""}
        ${it.flag ? `<p class="inote">${ic("info")}<span>${esc(it.flag)}</span></p>` : ""}
        <dl class="props">
          <dt>Cômodo</dt><dd><a href="#/c/${encodeURIComponent(room.id)}"><span class="mt soft">${esc(room.code)}</span><span class="rnm">${esc(room.name)}</span></a></dd>
          <dt>Zona</dt><dd>${esc(it.zone || "Sem zona")}</dd>
          <dt>Categoria</dt><dd><a href="#/buscar?cat=${esc(CAT[it.cat] ? it.cat : "outros")}&amp;ord=val"><span class="rnm">${esc(CAT[it.cat] || "Outros")}</span></a></dd>
          <dt>Quantidade</dt><dd>${esc(qtyLabel(it.qty))}</dd>
          <dt>Origem</dt><dd>${esc(SOURCES[it.source] || "Cadastro manual")}</dd>
          ${it.createdAt ? `<dt>Cadastrado</dt><dd>${esc(dateTime(it.createdAt))}${by(it.createdBy)}</dd>` : ""}
          ${it.updatedAt && it.updatedAt !== it.createdAt ? `<dt>Alterado</dt><dd>${esc(dateTime(it.updatedAt))}${by(it.updatedBy)}</dd>` : ""}
        </dl>
      </div>
      <div class="dlg-f">
        <button type="button" class="btn danger" data-act="item-delete" data-id="${esc(it.id)}" aria-label="Excluir">${lbl("trash", "Excluir")}</button>
        <span class="grow"></span>
        <button type="button" class="btn" data-act="item-move" data-id="${esc(it.id)}" aria-label="Mover">${lbl("move", "Mover")}</button>
        <button type="button" class="btn" data-act="item-dup" data-id="${esc(it.id)}" aria-label="Duplicar">${lbl("copy", "Duplicar")}</button>
        <button type="button" class="btn primary" data-act="item-edit" data-id="${esc(it.id)}">${ic("edit")}Editar</button>
      </div></div>`;
  }

  async function deleteItem(it) {
    const ok = await confirmBox({ title: "Excluir este item?", body: `<b>${esc(it.name)}</b> sai do inventário. Dá para desfazer logo em seguida.`, ok: "Excluir", danger: true });
    if (!ok) return;
    try {
      const res = await API.del(`api/items/${encodeURIComponent(it.id)}`);
      setRev(res.rev);
      removeItem(it.id);
      derive();
      if (sheet && sheet.itemId === it.id) requestClose(sheet, { force: true });
      refreshAll();
      toast("Item excluído", {
        action: "Desfazer",
        onAction: async () => {
          try {
            const r = await API.post("api/items", { ...res.item, _restore: true });
            setRev(r.rev); upsertItem(r.item); derive(); refreshAll();
            toast("Item restaurado");
          } catch (e) { fail(e); }
        },
      });
    } catch (e) { fail(e); }
  }

  function moveItem(it) {
    const zonesFor = (rid) => zonesOf(rid).map((z) => `<option value="${esc(z)}">`).join("");
    const entry = openDialog({
      cls: "modal narrow", label: "Mover item",
      html: `<div class="dlg"><div class="dlg-h"><h2>Mover item</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b" data-mv><div class="form">
          <p class="muted" style="margin:0">${esc(it.name)}</p>
          <div class="field"><label for="mv-room">Para o cômodo</label><select id="mv-room" class="select" name="room">${D.rooms.map((r) => `<option value="${esc(r.id)}"${r.id === it.room ? " selected" : ""}>${esc(r.name)}</option>`).join("")}</select></div>
          <div class="field"><label for="mv-zone">Zona</label><input id="mv-zone" class="input" name="zone" list="mv-zones" value="${esc(it.zone || "")}" autocomplete="off"><datalist id="mv-zones">${zonesFor(it.room)}</datalist>
            <p class="help">Ao mudar de cômodo, o item ganha um código novo no fim da lista.</p></div>
        </div></form>
        <div class="dlg-f"><span class="grow"></span><button class="btn ghost" data-x>Cancelar</button><button class="btn primary" data-ok>${ic("move")}Mover</button></div></div>`,
    });
    const form = $("[data-mv]", entry.dlg);
    form.room.addEventListener("change", () => { $("#mv-zones", entry.dlg).innerHTML = zonesFor(form.room.value); if (form.room.value !== it.room) form.zone.value = ""; });
    const go = async () => {
      try {
        const res = await API.put(`api/items/${encodeURIComponent(it.id)}`, { room: form.room.value, zone: form.zone.value, _base: it.updatedAt });
        setRev(res.rev); upsertItem(res.item); derive(); requestClose(entry, { force: true }); refreshAll();
        toast(res.item.room !== it.room ? `Movido para ${D.roomById.get(res.item.room)?.name}` : "Zona atualizada");
      } catch (e) { fail(e); }
    };
    form.addEventListener("submit", (e) => { e.preventDefault(); go(); });
    entry.dlg.addEventListener("click", (e) => { if (e.target.closest("[data-x]")) requestClose(entry, { force: true }); if (e.target.closest("[data-ok]")) go(); });
  }

  // ------------------------------------------------------------------ editor de item
  function openEditor({ item = null, dup = null, room = null, zone = null, photos = null } = {}) {
    if (!D.rooms.length) { toast("Crie um cômodo antes de adicionar itens."); openRoomNew(); return; }
    const from = item || dup || {};
    const rid = from.room || (room && D.roomById.has(room) ? room : lastRoom());
    const F = {
      id: item ? item.id : null, base: item ? item.updatedAt : null,
      name: from.name || "", details: from.details || "", room: rid,
      zone: from.zone != null ? from.zone : zone != null ? zone : LS.get("lastZone:" + rid, "") || "",
      cat: from.cat || "", qty: from.qty ? qtyClean(from.qty) : "1", value: from.value ? moneyInput(from.value) : "",
      flag: from.flag || "", photos: [...(from.photos || photos || [])], source: item ? item.source || "manual" : dup ? dup.source || "manual" : "manual",
      dirty: !!(dup || (photos && photos.length)), busy: false, uploading: 0, aiBusy: false, hint: "",
    };
    const title = item ? "Editar item" : dup ? "Duplicar item" : "Novo item";
    const entry = openDialog({
      cls: "modal", label: title,
      html: `<div class="dlg">
        <div class="dlg-h"><h2>${title}</h2><button type="button" class="btn ghost icon" data-ed="cancel" aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b drop" data-ed-form novalidate autocomplete="off">
          <div class="form">
            <div class="field"><span class="lbl">Fotos</span><div class="phs" data-slot="photos"></div>
              <p class="help">${COARSE ? "Tire uma foto ou escolha da galeria." : "Arraste fotos para cá ou cole uma imagem com Ctrl+V."}</p></div>
            <div class="aibox" data-slot="ai"></div>
            <div class="field"><label for="f-name">Nome</label><input id="f-name" class="input" name="name" maxlength="200" value="${esc(F.name)}" placeholder="Ex.: Cafeteira Nespresso Inissia" enterkeyhint="next">
              <p class="err" data-err="name" hidden></p></div>
            <div class="field"><label for="f-details">Detalhes</label><textarea id="f-details" class="textarea" name="details" rows="3" maxlength="4000" placeholder="Marca, modelo, cor, tamanho e estado">${esc(F.details)}</textarea></div>
            <div class="row2">
              <div class="field"><label for="f-room">Cômodo</label><select id="f-room" class="select" name="room">${D.rooms.map((r) => `<option value="${esc(r.id)}"${r.id === F.room ? " selected" : ""}>${esc(r.name)}</option>`).join("")}</select></div>
              <div class="field"><label for="f-zone">Zona</label><input id="f-zone" class="input" name="zone" list="f-zones" maxlength="120" value="${esc(F.zone)}" placeholder="Ex.: Estante, Bancada"><datalist id="f-zones"></datalist></div>
            </div>
            <div class="field"><label for="f-cat">Categoria</label><select id="f-cat" class="select" name="cat"><option value="">Escolha a categoria</option>${CATS.map(([k, v]) => `<option value="${k}"${k === F.cat ? " selected" : ""}>${esc(v)}</option>`).join("")}</select></div>
            <div class="row3">
              <div class="field"><label for="f-qty">Quantidade</label><input id="f-qty" class="input" name="qty" maxlength="30" value="${esc(F.qty)}" inputmode="text"></div>
              <div class="field"><label for="f-value">Valor total</label><div class="money"><input id="f-value" class="input" name="value" inputmode="decimal" value="${esc(F.value)}" placeholder="0"></div>
                <p class="unit-hint" data-slot="unit"></p><p class="err" data-err="value" hidden></p></div>
            </div>
            <p class="help" style="margin-top:-8px">Valor de mercado de usado, somando todas as unidades.</p>
            <details class="more-fields"${F.flag ? " open" : ""}><summary>${ic("chev", "sm")}Observação</summary>
              <div class="form"><div class="field"><label for="f-flag" class="sr">Observação</label><input id="f-flag" class="input" name="flag" maxlength="200" value="${esc(F.flag)}" placeholder="Algo para lembrar sobre este item"></div></div></details>
            <div class="formerr" data-slot="formerr" hidden></div>
          </div>
        </form>
        <div class="dlg-f">
          ${F.id ? "" : `<button type="button" class="btn" data-ed="again">Salvar e adicionar outro</button>`}
          <span class="grow"></span>
          <button type="button" class="btn ghost hide-narrow" data-ed="cancel">Cancelar</button>
          <button type="button" class="btn primary" data-ed="save">${F.id ? "Salvar alterações" : "Salvar item"}</button>
        </div></div>`,
      guard: async () => !F.dirty || confirmBox({ title: "Descartar o que foi preenchido?", body: "As alterações deste item ainda não foram salvas.", ok: "Descartar", cancel: "Continuar editando", danger: true }),
    });
    const dlg = entry.dlg;
    const form = $("[data-ed-form]", dlg);
    const slot = (n) => $(`[data-slot="${n}"]`, dlg);
    entry.onSubmit = () => save(false);

    const renderZones = () => { $("#f-zones", dlg).innerHTML = zonesOf(F.room).map((z) => `<option value="${esc(z)}">`).join(""); };
    const renderUnit = () => {
      const n = qtyNum(F.qty), v = parseMoney(F.value);
      slot("unit").textContent = n && n > 1 && v > 0 ? `${money(v / n)} cada` : "";
    };
    const renderPhotos = () => {
      const hasRoomPhotos = (D.roomById.get(F.room)?.photos || []).some((p) => !F.photos.includes(p.file));
      slot("photos").innerHTML = F.photos.map((f, i) => `<div class="ph"><img src="${esc(src(f))}" alt="Foto ${i + 1}">
          ${i === 0 ? `<span class="cover">Capa</span>` : `<button type="button" class="mkcover" data-ed="cover" data-i="${i}">Usar como capa</button>`}
          <button type="button" class="x" data-ed="rmphoto" data-i="${i}" aria-label="Remover foto ${i + 1}">${ic("close")}</button></div>`).join("")
        + Array.from({ length: F.uploading }, () => `<div class="ph loading"><span class="spin lg"></span></div>`).join("")
        + (COARSE ? `<button type="button" class="add" data-ed="camera">${ic("camera")}Tirar foto</button>` : "")
        + `<button type="button" class="add" data-ed="upload">${ic(COARSE ? "image" : "upload")}${COARSE ? "Galeria" : "Enviar foto"}</button>`
        + (hasRoomPhotos ? `<button type="button" class="add" data-ed="roomphotos">${ic("images")}Fotos do cômodo</button>` : "");
      renderAi();
    };
    const renderAi = async () => {
      const box = slot("ai");
      if (F.aiBusy) {
        box.innerHTML = `<div class="aih"><p><b>Lendo a foto…</b> Pode levar até um minuto.</p><button type="button" class="btn" disabled><span class="spin"></span>Lendo</button></div>`;
        return;
      }
      if (!F.photos.length) {
        box.innerHTML = `<div class="aih"><p>${ic("scan", "sm")} Com uma foto, a IA preenche nome, detalhes, categoria e valor. Você confere antes de salvar.</p></div>`;
        return;
      }
      box.innerHTML = `<div class="aih"><p>A IA lê a primeira foto e preenche os campos. Você confere antes de salvar.</p>
          <button type="button" class="btn" data-ed="ai">${ic("scan")}Preencher com IA</button></div>
        <input class="input" data-ed-hint placeholder="Dica para a IA (opcional), ex.: é uma cafeteira Oster" value="${esc(F.hint)}" maxlength="300" style="height:40px">`;
    };
    const showErr = (msg) => { const el = slot("formerr"); el.hidden = !msg; el.innerHTML = msg || ""; if (msg) el.scrollIntoView({ block: "nearest", behavior: "smooth" }); };
    const fieldErr = (name, msg) => {
      const p = $(`[data-err="${name}"]`, dlg), inp = form[name];
      p.hidden = !msg; p.textContent = msg || "";
      if (inp) inp.setAttribute("aria-invalid", msg ? "true" : "false");
    };
    const setBusy = (on) => {
      F.busy = on;
      $$('[data-ed="save"], [data-ed="again"]', dlg).forEach((b) => { b.disabled = on; });
      const b = $('[data-ed="save"]', dlg);
      b.innerHTML = on ? `<span class="spin"></span>Salvando` : F.id ? "Salvar alterações" : "Salvar item";
    };

    renderZones(); renderPhotos(); renderUnit();
    setTimeout(() => { if (!COARSE && !F.photos.length) form.name.focus(); }, 60);

    form.addEventListener("input", (e) => {
      const t = e.target;
      if (t.matches("[data-ed-hint]")) { F.hint = t.value; return; }
      if (!t.name) return;
      F[t.name] = t.value;
      F.dirty = true;
      if (t.name === "qty" || t.name === "value") renderUnit();
      if (t.name === "name" && t.value.trim()) fieldErr("name", "");
      if (t.name === "value") fieldErr("value", "");
    });
    form.addEventListener("change", (e) => {
      if (e.target.name === "room") { F.room = e.target.value; renderZones(); renderPhotos(); }
      if (e.target.name === "value" && !Number.isNaN(parseMoney(F.value))) { F.value = moneyInput(parseMoney(F.value)); e.target.value = F.value; }
    });
    form.addEventListener("submit", (e) => { e.preventDefault(); save(false); });
    form.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("[data-ed-hint]")) { e.preventDefault(); runAi(); } });

    const addFiles = async (files) => {
      files = imageFiles(files).slice(0, 12 - F.photos.length);
      if (!files.length) return;
      F.uploading += files.length; F.dirty = true; renderPhotos();
      for (const file of files) {
        try { const name = await uploadPhoto(file); F.photos.push(name); }
        catch (e) { fail(e); }
        finally { F.uploading -= 1; if (document.contains(dlg)) renderPhotos(); }
      }
    };
    wireDrop(entry, form, addFiles);

    async function runAi() {
      if (!F.photos.length || F.aiBusy) return;
      if (!(await needAi())) return;
      F.aiBusy = true; renderAi();
      try {
        const res = await API.post("api/ai/identify", { file: F.photos[0], mode: "single", room: F.room, hint: F.hint });
        const r = (res.items || [])[0];
        if (!r) throw new Error("A IA não reconheceu um item nesta foto. Tente outra foto ou escreva uma dica.");
        const prev = { name: F.name, details: F.details, cat: F.cat, qty: F.qty, value: F.value, zone: F.zone, source: F.source };
        Object.assign(F, { name: r.name, details: r.details || F.details, cat: r.cat || F.cat, qty: r.qty || F.qty, value: r.value ? moneyInput(r.value) : F.value, zone: F.zone || r.zone || "", source: "ia", dirty: true });
        fill();
        toast(res.example ? "Exemplo simulado da prévia: no Home Assistant, a IA lê a foto de verdade." : "Campos preenchidos pela IA. Confira antes de salvar.", { action: "Desfazer", onAction: () => { Object.assign(F, prev); if (document.contains(dlg)) fill(); } });
      } catch (e) { fail(e); }
      finally { F.aiBusy = false; if (document.contains(dlg)) renderAi(); }
    }
    function fill() {
      form.name.value = F.name; form.details.value = F.details; form.cat.value = CAT[F.cat] ? F.cat : "";
      form.qty.value = F.qty; form.value.value = F.value; form.zone.value = F.zone; form.flag.value = F.flag;
      renderUnit(); fieldErr("name", ""); fieldErr("value", "");
    }

    async function save(again) {
      if (F.busy) return;
      if (F.uploading) { toast("Espere as fotos terminarem de enviar."); return; }
      showErr("");
      const name = F.name.trim();
      const value = parseMoney(F.value);
      let bad = false;
      if (!name) { fieldErr("name", "Dê um nome ao item."); bad = true; }
      if (Number.isNaN(value)) { fieldErr("value", "Use só números, como 1200 ou 1.200,50."); bad = true; }
      if (bad) { (name ? form.value : form.name).focus(); return; }
      const body = { name, details: F.details.trim(), room: F.room, zone: F.zone.trim(), cat: F.cat || "outros", qty: F.qty.trim() || "1", value, photos: F.photos, flag: F.flag.trim(), source: F.source };
      setBusy(true);
      try {
        const res = F.id
          ? await API.put(`api/items/${encodeURIComponent(F.id)}`, { ...body, _base: F.base })
          : await API.post("api/items", body);
        setRev(res.rev); upsertItem(res.item); derive();
        LS.set("lastRoom", res.item.room); LS.set("lastZone:" + res.item.room, res.item.zone || "");
        refreshAll();
        if (again) {
          Object.assign(F, { name: "", details: "", qty: "1", value: "", flag: "", photos: [], source: "manual", hint: "", dirty: false });
          fill(); renderPhotos();
          form.name.focus();
          toast(`${res.item.name} adicionado. Pode cadastrar o próximo.`);
        } else {
          F.dirty = false;
          requestClose(entry, { force: true });
          if (F.id) toast("Alterações salvas");
          else toast("Item adicionado", { action: "Ver", onAction: () => nav(`#/i/${encodeURIComponent(res.item.id)}`) });
        }
      } catch (e) {
        if (e.status === 409 && e.data && e.data.item) {
          const cur = e.data.item;
          showErr(`${esc(e.message)}<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
            <button type="button" class="btn sm" data-ed="theirs">Carregar a versão atual</button>
            <button type="button" class="btn sm" data-ed="mine">Salvar a minha mesmo assim</button></div>`);
          entry.conflict = cur;
        } else showErr(esc(e.message));
      } finally { if (document.contains(dlg)) setBusy(false); }
    }

    dlg.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-ed]");
      if (!b) return;
      const act = b.dataset.ed;
      if (act === "cancel") requestClose(entry);
      else if (act === "save") save(false);
      else if (act === "again") save(true);
      else if (act === "upload") pickFiles(addFiles);
      else if (act === "camera") pickFiles(addFiles, { camera: true });
      else if (act === "roomphotos") { const chosen = await roomPhotoPicker(F.room, F.photos); if (chosen.length) { F.photos.push(...chosen.slice(0, 12 - F.photos.length)); F.dirty = true; renderPhotos(); } }
      else if (act === "rmphoto") { F.photos.splice(+b.dataset.i, 1); F.dirty = true; renderPhotos(); }
      else if (act === "cover") { const [p] = F.photos.splice(+b.dataset.i, 1); F.photos.unshift(p); F.dirty = true; renderPhotos(); }
      else if (act === "ai") runAi();
      else if (act === "theirs" && entry.conflict) {
        const c = entry.conflict;
        Object.assign(F, { base: c.updatedAt, name: c.name, details: c.details || "", room: c.room, zone: c.zone || "", cat: c.cat, qty: qtyClean(c.qty), value: moneyInput(c.value), flag: c.flag || "", photos: [...(c.photos || [])], dirty: false });
        form.room.value = F.room; fill(); renderPhotos(); renderZones(); showErr("");
      } else if (act === "mine" && entry.conflict) { F.base = entry.conflict.updatedAt; showErr(""); save(false); }
    });
  }

  // ------------------------------------------------------------------ catalogar foto com IA (vários itens)
  async function openCatalog({ room = null, file = null } = {}) {
    if (!D.rooms.length) { toast("Crie um cômodo antes."); openRoomNew(); return; }
    if (!(await needAi())) return;
    const C = { step: file ? "ready" : "photo", room: room && D.roomById.has(room) ? room : lastRoom(), zone: "", hint: "", file, uploading: false, results: [], keep: true, entity: "", error: null, raw: "", busy: false, token: 0 };
    const entry = openDialog({
      cls: "modal wide", label: "Catalogar foto com IA",
      html: `<div class="dlg"><div class="dlg-h"><h2>Catalogar foto com IA</h2><button type="button" class="btn ghost icon" data-ct="cancel" aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b drop" data-slot="body"></div><div class="dlg-f" data-slot="foot"></div></div>`,
      guard: async () => C.step !== "review" || !C.results.some((r) => r.on) || confirmBox({ title: "Descartar os itens encontrados?", body: "Os itens lidos pela IA ainda não foram adicionados.", ok: "Descartar", cancel: "Voltar", danger: true }),
    });
    const dlg = entry.dlg;
    const body = $('[data-slot="body"]', dlg), foot = $('[data-slot="foot"]', dlg);
    const roomName = () => D.roomById.get(C.room)?.name || "";

    function render() {
      if (C.step === "photo" || C.step === "ready") {
        const hasRoomPhotos = (D.roomById.get(C.room)?.photos || []).length > 0;
        body.innerHTML = `<div class="form">
          <p class="muted" style="margin:0">A IA lista os objetos da foto com nome, categoria, quantidade e um valor estimado de usado. Você revisa tudo antes de adicionar.</p>
          ${C.file ? `<div class="cat-photo"><img src="${esc(src(C.file, "photos"))}" alt="Foto escolhida"></div>
              <div style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="btn sm" data-ct="change">${ic("image", "sm")}Trocar foto</button></div>`
            : `<div class="phs" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">
                ${C.uploading ? `<div class="ph loading" style="aspect-ratio:4/3"><span class="spin lg"></span></div>` : `
                ${COARSE ? `<button type="button" class="add" style="aspect-ratio:4/3" data-ct="camera">${ic("camera", "lg")}Tirar foto</button>` : ""}
                <button type="button" class="add" style="aspect-ratio:4/3" data-ct="upload">${ic(COARSE ? "image" : "upload", "lg")}${COARSE ? "Galeria" : "Enviar foto"}</button>
                ${hasRoomPhotos ? `<button type="button" class="add" style="aspect-ratio:4/3" data-ct="roomphoto">${ic("images", "lg")}Foto do cômodo</button>` : ""}`}
              </div>${COARSE ? "" : `<p class="help" style="margin:0">Você também pode arrastar a foto para cá ou colar com Ctrl+V.</p>`}`}
          <div class="row2">
            <div class="field"><label for="c-room">Cômodo</label><select id="c-room" class="select" data-ct-in="room">${D.rooms.map((r) => `<option value="${esc(r.id)}"${r.id === C.room ? " selected" : ""}>${esc(r.name)}</option>`).join("")}</select></div>
            <div class="field"><label for="c-zone">Zona (opcional)</label><input id="c-zone" class="input" data-ct-in="zone" list="c-zones" value="${esc(C.zone)}" placeholder="Deixe vazio para a IA sugerir" autocomplete="off">
              <datalist id="c-zones">${zonesOf(C.room).map((z) => `<option value="${esc(z)}">`).join("")}</datalist></div>
          </div>
          <div class="field"><label for="c-hint">Dica para a IA (opcional)</label><input id="c-hint" class="input" data-ct-in="hint" value="${esc(C.hint)}" maxlength="300" placeholder="Ex.: são taças de cristal; o vaso é de cerâmica" autocomplete="off"></div>
        </div>`;
        foot.innerHTML = `<span class="grow"></span><button type="button" class="btn ghost" data-ct="cancel">Cancelar</button>
          <button type="button" class="btn primary" data-ct="read"${C.file ? "" : " disabled"}>${ic("scan")}Ler foto</button>`;
      } else if (C.step === "reading") {
        body.innerHTML = `<div class="cat-photo"><img src="${esc(src(C.file, "photos"))}" alt=""><div class="scan"></div></div>
          <div class="ai-wait"><b>Lendo a foto…</b><span>A IA está listando os objetos. Pode levar até um minuto.</span></div>`;
        foot.innerHTML = `<span class="grow"></span><button type="button" class="btn ghost" data-ct="stop">Cancelar leitura</button>`;
      } else if (C.step === "error") {
        body.innerHTML = `<div class="cat-photo"><img src="${esc(src(C.file, "thumbs"))}" alt="" style="max-height:220px"></div>
          <div class="formerr" style="margin-top:14px">${esc(C.error)}</div>
          ${C.raw ? `<details style="margin-top:10px"><summary class="muted">Ver resposta da IA</summary><pre style="white-space:pre-wrap;font-size:13px">${esc(C.raw)}</pre></details>` : ""}`;
        foot.innerHTML = `<button type="button" class="btn" data-ct="back">${ic("back", "sm")}Voltar</button><span class="grow"></span><button type="button" class="btn primary" data-ct="read">${ic("refresh")}Tentar de novo</button>`;
      } else if (C.step === "review") {
        const on = C.results.filter((r) => r.on).length;
        const zones = zonesOf(C.room);
        body.innerHTML = `<div style="display:flex;gap:14px;align-items:center;margin-bottom:16px">
            <img src="${esc(src(C.file))}" alt="" style="width:72px;height:72px;object-fit:cover;border-radius:8px;flex:none">
            <div><b style="font:600 21px/1.2 var(--font-c)">${C.results.length ? plural(C.results.length, "item encontrado", "itens encontrados") : "Nenhum item encontrado"}</b>
            <div class="muted" style="font-size:14px">Em ${esc(roomName())}. Confira nomes e valores antes de adicionar.</div></div></div>
          ${C.example ? `<p class="inote" style="margin:0 0 14px">${ic("info")}<span>Exemplo simulado da prévia: aqui a IA não lê a foto. No Home Assistant, a lista vem da sua integração de IA.</span></p>` : ""}
          ${C.results.length ? `<datalist id="cr-zones">${zones.map((z) => `<option value="${esc(z)}">`).join("")}</datalist><ul class="found">${C.results.map((r, i) => `<li class="${r.on ? "" : "off"}">
            <input type="checkbox" class="fcheck" data-ri="${i}" data-rf="on"${r.on ? " checked" : ""} aria-label="Adicionar ${esc(r.name)}">
            <div class="fbody">
              <div class="frow"><input class="input fname" data-ri="${i}" data-rf="name" value="${esc(r.name)}" aria-label="Nome">
                <input class="input" data-ri="${i}" data-rf="qty" value="${esc(r.qty)}" aria-label="Quantidade">
                <div class="money"><input class="input" data-ri="${i}" data-rf="value" value="${esc(moneyInput(r.value))}" inputmode="decimal" aria-label="Valor total"></div></div>
              <div class="frow2"><select class="select" data-ri="${i}" data-rf="cat" aria-label="Categoria">${CATS.map(([k, v]) => `<option value="${k}"${k === r.cat ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
                <input class="input" data-ri="${i}" data-rf="zone" value="${esc(r.zone)}" list="cr-zones" placeholder="Zona" aria-label="Zona"></div>
              ${r.details ? `<p class="fdet">${esc(r.details)}</p>` : ""}
              ${r.existing || r.confidence === "baixa" ? `<div class="fflag">${r.existing ? `<span class="pill warn">Parece já cadastrado: ${esc(r.existing)}</span>` : ""}${r.confidence === "baixa" ? `<span class="pill">IA pouco segura, confira</span>` : ""}</div>` : ""}
            </div></li>`).join("")}</ul>
          ${(D.roomById.get(C.room)?.photos || []).some((p) => p.file === C.file) ? "" : `<label class="check" style="margin-top:16px"><input type="checkbox" data-ct-in="keep"${C.keep ? " checked" : ""}> Guardar esta foto nas fotos de ${esc(roomName())}</label>`}`
          : `<p class="muted">A IA não encontrou objetos para catalogar. Tente uma foto mais próxima ou escreva uma dica.</p>`}`;
        foot.innerHTML = `<button type="button" class="btn" data-ct="back">${ic("back", "sm")}Outra foto</button><span class="grow"></span>
          <button type="button" class="btn ghost" data-ct="cancel">Cancelar</button>
          <button type="button" class="btn primary" data-ct="add"${on ? "" : " disabled"}>${ic("plus")}${on > 1 ? `Adicionar ${on} itens` : on === 1 ? "Adicionar 1 item" : "Adicionar"}</button>`;
      }
    }
    const setFile = async (files) => {
      const f = imageFiles(files)[0];
      if (!f) return;
      C.uploading = true; C.file = null; C.step = "photo"; render();
      try { C.file = await uploadPhoto(f); C.step = "ready"; } catch (e) { fail(e); }
      finally { C.uploading = false; if (document.contains(dlg)) render(); }
    };
    wireDrop(entry, body, setFile);
    async function read() {
      if (!C.file) return;
      const my = ++C.token;
      C.step = "reading"; C.error = null; C.raw = ""; render();
      try {
        const res = await API.post("api/ai/identify", { file: C.file, mode: "multi", room: C.room, hint: C.hint });
        if (my !== C.token) return;
        C.entity = res.entity || "";
        C.example = !!res.example;
        C.results = (res.items || []).map((r) => ({ ...r, zone: C.zone || r.zone || "", on: !r.existing }));
        C.step = "review";
      } catch (e) {
        if (my !== C.token) return;
        C.step = "error"; C.error = e.message; C.raw = (e.data && e.data.raw) || "";
      }
      if (document.contains(dlg)) render();
    }
    async function add() {
      const chosen = C.results.filter((r) => r.on);
      if (!chosen.length || C.busy) return;
      const bad = chosen.find((r) => !String(r.name).trim() || Number.isNaN(parseMoney(r.value)));
      if (bad) { toast(!String(bad.name).trim() ? "Um dos itens está sem nome." : `Valor inválido em ${bad.name}.`, { error: true }); return; }
      C.busy = true;
      const btn = $('[data-ct="add"]', dlg);
      btn.disabled = true; btn.innerHTML = `<span class="spin"></span>Adicionando`;
      try {
        const res = await API.post("api/items/batch", {
          items: chosen.map((r) => ({ room: C.room, zone: (r.zone || C.zone || "").trim(), name: String(r.name).trim(), details: r.details || "", cat: r.cat, qty: String(r.qty || "1").trim() || "1", value: parseMoney(r.value), photos: [C.file], source: "ia" })),
          roomPhoto: C.keep ? { room: C.room, file: C.file, label: (C.hint || chosen.slice(0, 3).map((r) => String(r.name).trim()).join(", ")).slice(0, 160) } : null,
        });
        setRev(res.rev);
        res.items.forEach(upsertItem);
        if (res.rooms) S.rooms = res.rooms;
        derive();
        C.results = [];
        requestClose(entry, { force: true });
        refreshAll();
        const rid = C.room;
        toast(`${plural(res.items.length, "item adicionado", "itens adicionados")} em ${D.roomById.get(rid)?.name}`, { action: "Ver", onAction: () => nav(`#/c/${encodeURIComponent(rid)}`) });
      } catch (e) { fail(e); C.busy = false; if (document.contains(dlg)) render(); }
    }
    dlg.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-ct]");
      if (!b) return;
      const act = b.dataset.ct;
      if (act === "cancel") requestClose(entry);
      else if (act === "upload") pickFiles(setFile, { multiple: false });
      else if (act === "camera") pickFiles(setFile, { camera: true });
      else if (act === "change") { C.file = null; C.step = "photo"; render(); }
      else if (act === "roomphoto") { const [f] = await roomPhotoPicker(C.room); if (f) { C.file = f; C.keep = false; C.step = "ready"; render(); } }
      else if (act === "read") read();
      else if (act === "stop" || act === "back") { C.token++; C.step = C.file ? "ready" : "photo"; render(); }
      else if (act === "add") add();
    });
    dlg.addEventListener("input", (e) => {
      const t = e.target;
      if (t.dataset.ctIn === "zone") C.zone = t.value;
      else if (t.dataset.ctIn === "hint") C.hint = t.value;
      else if (t.dataset.ri != null && t.dataset.rf !== "on") C.results[+t.dataset.ri][t.dataset.rf] = t.value;
    });
    dlg.addEventListener("change", (e) => {
      const t = e.target;
      if (t.dataset.ctIn === "room") { C.room = t.value; render(); }
      else if (t.dataset.ctIn === "keep") C.keep = t.checked;
      else if (t.dataset.rf === "on") { C.results[+t.dataset.ri].on = t.checked; render(); }
      else if (t.dataset.rf === "cat") C.results[+t.dataset.ri].cat = t.value;
    });
    dlg.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.dataset.ctIn === "hint" && C.file) { e.preventDefault(); read(); } });
    render();
  }

  // ------------------------------------------------------------------ visualizador de fotos
  function openViewer({ photos, index = 0, roomId = null }) {
    let i = Math.max(0, Math.min(index, photos.length - 1));
    const entry = openDialog({ cls: "viewer", label: "Foto", html: `<div class="vwrap"></div>` });
    const wrap = $(".vwrap", entry.dlg);
    const render = () => {
      const p = photos[i];
      const its = D.photoItems.get(p.file) || [];
      const room = roomId ? D.roomById.get(roomId) : null;
      const isCover = room && (room.cover || 0) === i;
      wrap.innerHTML = `
        <div class="vtop"><span class="cap">${esc(p.label || (room ? room.name : "Foto"))}</span>${photos.length > 1 ? `<span class="pos">${i + 1} de ${photos.length}</span>` : ""}
          ${PREVIEW ? "" : `<a class="btn icon" href="${esc(src(p.file, "photos"))}" target="_blank" rel="noopener" aria-label="Abrir em tamanho original">${ic("download")}</a>`}
          <button type="button" class="btn icon" data-v="close" aria-label="Fechar">${ic("close")}</button></div>
        <div class="vimg"><img src="${esc(src(p.file, "photos"))}" alt="${esc(p.label || "")}" draggable="false">
          ${photos.length > 1 ? `<button type="button" class="btn icon vnav prev" data-v="prev" aria-label="Foto anterior">${ic("back")}</button><button type="button" class="btn icon vnav next" data-v="next" aria-label="Próxima foto">${ic("chev")}</button>` : ""}</div>
        <div class="vside">
          ${room ? `<div class="field"><label for="v-label" style="color:#c9cfd5">Legenda</label><input id="v-label" class="input" data-v-label value="${esc(p.label || "")}" placeholder="Ex.: Estante do lado da janela" style="background:#0f1113;color:#eef0f2;border-color:#3e464e"></div>` : ""}
          <div><h3>${its.length ? plural(its.length, "item nesta foto", "itens nesta foto") : "Nenhum item usa esta foto"}</h3>
            ${its.length ? `<ul class="vlist">${its.map((it) => `<li><a href="#/i/${encodeURIComponent(it.id)}" data-v="item"><span>${esc(it.name)}</span><span class="v">${money(it.value)}</span></a></li>`).join("")}</ul>` : ""}</div>
          ${room ? `<div class="vacts">
            <button type="button" class="btn primary" data-v="additem">${ic("plus")}Adicionar item com esta foto</button>
            <button type="button" class="btn" data-v="catalog">${ic("scan")}Catalogar esta foto com IA</button>
            <button type="button" class="btn" data-v="cover"${isCover ? " disabled" : ""}>${ic("image")}${isCover ? "Capa do cômodo" : "Usar como capa do cômodo"}</button>
            <button type="button" class="btn" data-v="remove">${ic("trash")}Tirar do cômodo</button></div>` : ""}
        </div>`;
    };
    const step = (d) => { if (photos.length > 1) { i = (i + d + photos.length) % photos.length; render(); } };
    const saveRoomPhotos = async (patch) => {
      try { const res = await API.put(`api/rooms/${encodeURIComponent(roomId)}`, patch); setRev(res.rev); upsertRoom(res.room); derive(); refreshAll(); return res.room; }
      catch (e) { fail(e); return null; }
    };
    entry.dlg.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-v]");
      if (!b) return;
      const act = b.dataset.v;
      const p = photos[i];
      if (act === "close") requestClose(entry, { force: true });
      else if (act === "prev") step(-1);
      else if (act === "next") step(1);
      else if (act === "item") { e.preventDefault(); const href = b.getAttribute("href"); finalizeThen(entry, () => nav(href)); }
      else if (act === "additem") finalizeThen(entry, () => openEditor({ room: roomId, photos: [p.file] }));
      else if (act === "catalog") finalizeThen(entry, () => openCatalog({ room: roomId, file: p.file }));
      else if (act === "cover") { const r = await saveRoomPhotos({ cover: i }); if (r) { render(); toast("Capa do cômodo atualizada"); } }
      else if (act === "remove") {
        const ok = await confirmBox({ title: "Tirar a foto do cômodo?", body: "A foto sai da lista do cômodo. Os itens que usam esta foto continuam com ela.", ok: "Tirar do cômodo", danger: true });
        if (!ok) return;
        const room = D.roomById.get(roomId);
        const list = (room.photos || []).filter((_, k) => k !== i);
        const r = await saveRoomPhotos({ photos: list, cover: Math.min(room.cover || 0, Math.max(0, list.length - 1)) });
        if (r) { photos = r.photos; if (!photos.length) { requestClose(entry, { force: true }); return; } i = Math.min(i, photos.length - 1); render(); toast("Foto retirada do cômodo"); }
      }
    });
    entry.dlg.addEventListener("change", async (e) => {
      if (!e.target.matches("[data-v-label]")) return;
      const room = D.roomById.get(roomId);
      const list = (room.photos || []).map((p, k) => (k === i ? { ...p, label: e.target.value.trim() } : p));
      const r = await saveRoomPhotos({ photos: list });
      if (r) { photos = r.photos; toast("Legenda salva"); }
    });
    entry.dlg.addEventListener("keydown", (e) => {
      if (e.target.matches("input")) return;
      if (e.key === "ArrowLeft") step(-1);
      if (e.key === "ArrowRight") step(1);
    });
    let sx = null;
    entry.dlg.addEventListener("pointerdown", (e) => { if (e.target.closest(".vimg")) sx = e.clientX; });
    entry.dlg.addEventListener("pointerup", (e) => { if (sx != null) { const dx = e.clientX - sx; if (Math.abs(dx) > 50) step(dx < 0 ? 1 : -1); sx = null; } });
    render();
  }
  function finalizeThen(entry, fn) {
    // fecha a janela já (sem esperar o voltar do histórico) e segue
    entry.closing = true;
    if (entry.pushed && history.state && history.state.invModal) {
      entry.awaitingPop = true;
      let ran = false;
      const done = () => { if (ran) return; ran = true; window.removeEventListener("popstate", done); setTimeout(fn, 0); };
      window.addEventListener("popstate", done);
      history.back();
      setTimeout(() => { if (stack.includes(entry)) finalize(entry); done(); }, 700);
    } else { finalize(entry); fn(); }
  }

  // ------------------------------------------------------------------ cômodos
  const suggestCode = (name) => norm(name).replace(/[^a-z0-9]/g, "").slice(0, 3).toUpperCase();
  function openRoomNew() {
    const entry = openDialog({
      cls: "modal narrow", label: "Novo cômodo",
      html: `<div class="dlg"><div class="dlg-h"><h2>Novo cômodo</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b" data-rn><div class="form">
          <div class="field"><label for="rn-name">Nome</label><input id="rn-name" class="input" name="name" maxlength="60" placeholder="Ex.: Garagem" autocomplete="off"></div>
          <div class="field"><label for="rn-code">Código</label><input id="rn-code" class="input" name="code" maxlength="4" style="text-transform:uppercase;max-width:140px" autocomplete="off">
            <p class="help">De 1 a 4 letras. Vira o começo do código dos itens, como GAR-001.</p></div>
          <div class="formerr" data-err hidden></div>
        </div></form>
        <div class="dlg-f"><span class="grow"></span><button class="btn ghost" data-x>Cancelar</button><button class="btn primary" data-ok>Criar cômodo</button></div></div>`,
    });
    const form = $("[data-rn]", entry.dlg);
    let touched = false;
    form.name.addEventListener("input", () => { if (!touched) form.code.value = suggestCode(form.name.value); });
    form.code.addEventListener("input", () => { touched = true; });
    setTimeout(() => form.name.focus(), 50);
    const go = async () => {
      const name = form.name.value.trim();
      const err = $("[data-err]", entry.dlg);
      if (!name) { err.hidden = false; err.textContent = "Dê um nome ao cômodo."; form.name.focus(); return; }
      try {
        const res = await API.post("api/rooms", { name, code: form.code.value.trim() || suggestCode(name) });
        setRev(res.rev); S.rooms = res.rooms; derive();
        finalizeThen(entry, () => { nav(`#/c/${encodeURIComponent(res.room.id)}`); toast(`${res.room.name} criado`); });
      } catch (e) { err.hidden = false; err.textContent = e.message; }
    };
    form.addEventListener("submit", (e) => { e.preventDefault(); go(); });
    entry.dlg.addEventListener("click", (e) => { if (e.target.closest("[data-x]")) requestClose(entry, { force: true }); if (e.target.closest("[data-ok]")) go(); });
  }

  function openRoomEdit(id) {
    const r = D.roomById.get(id);
    if (!r) return;
    const R = { name: r.name, code: r.code, photos: (r.photos || []).map((p) => ({ ...p })), cover: r.cover || 0, dirty: false, uploading: 0 };
    const count = (D.byRoom.get(id) || []).length;
    const entry = openDialog({
      cls: "modal", label: "Editar cômodo",
      html: `<div class="dlg"><div class="dlg-h"><h2>Editar cômodo</h2><button class="btn ghost icon" data-re="cancel" aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b drop" data-re-form><div class="form">
          <div class="row2" style="grid-template-columns:1fr 120px">
            <div class="field"><label for="re-name">Nome</label><input id="re-name" class="input" name="name" maxlength="60" value="${esc(R.name)}"></div>
            <div class="field"><label for="re-code">Código</label><input id="re-code" class="input" name="code" maxlength="4" value="${esc(R.code)}" style="text-transform:uppercase"></div>
          </div>
          <div class="field"><span class="lbl">Fotos do cômodo</span><div data-slot="rphotos"></div></div>
          <div class="formerr" data-err hidden></div>
        </div></form>
        <div class="dlg-f"><button type="button" class="btn danger" data-re="delete"${count ? ` title="Mova ou exclua os ${count} itens antes"` : ""}>${ic("trash")}<span class="lbl">Excluir cômodo</span></button><span class="grow"></span>
          <button type="button" class="btn ghost" data-re="cancel">Cancelar</button><button type="button" class="btn primary" data-re="save">Salvar</button></div></div>`,
      guard: async () => !R.dirty || confirmBox({ title: "Descartar as alterações?", body: "As mudanças neste cômodo ainda não foram salvas.", ok: "Descartar", cancel: "Continuar editando", danger: true }),
    });
    const dlg = entry.dlg;
    const form = $("[data-re-form]", dlg);
    const renderPhotos = () => {
      $('[data-slot="rphotos"]', dlg).innerHTML = `<ul class="opts">${R.photos.map((p, i) => `<li style="flex-wrap:nowrap">
          <img src="${esc(src(p.file))}" alt="" style="width:64px;height:48px;object-fit:cover;border-radius:6px;flex:none">
          <input class="input" data-re-label="${i}" value="${esc(p.label || "")}" placeholder="Legenda" style="height:38px;flex:1;min-width:0">
          <button type="button" class="btn sm${R.cover === i ? " primary" : ""}" data-re="cover" data-i="${i}" aria-pressed="${R.cover === i}">${R.cover === i ? "Capa" : "Usar como capa"}</button>
          <button type="button" class="btn sm icon" data-re="up" data-i="${i}" aria-label="Subir foto"${i === 0 ? " disabled" : ""}>${ic("up", "sm")}</button>
          <button type="button" class="btn sm icon" data-re="rm" data-i="${i}" aria-label="Tirar foto">${ic("trash", "sm")}</button></li>`).join("")}</ul>
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
          ${R.uploading ? `<span class="muted"><span class="spin sm"></span> Enviando ${R.uploading} foto(s)…</span>` : ""}
          ${COARSE ? `<button type="button" class="btn sm" data-re="camera">${ic("camera", "sm")}Tirar foto</button>` : ""}
          <button type="button" class="btn sm" data-re="upload">${ic("upload", "sm")}Enviar fotos</button></div>`;
    };
    const addFiles = async (files) => {
      files = imageFiles(files);
      R.uploading += files.length; R.dirty = true; renderPhotos();
      for (const f of files) {
        try { R.photos.push({ file: await uploadPhoto(f), label: "" }); } catch (e) { fail(e); }
        finally { R.uploading -= 1; if (document.contains(dlg)) renderPhotos(); }
      }
    };
    wireDrop(entry, form, addFiles);
    renderPhotos();
    form.addEventListener("input", (e) => {
      R.dirty = true;
      if (e.target.dataset.reLabel != null) R.photos[+e.target.dataset.reLabel].label = e.target.value;
      else if (e.target.name) R[e.target.name] = e.target.value;
    });
    const save = async () => {
      const err = $("[data-err]", dlg);
      if (!R.name.trim()) { err.hidden = false; err.textContent = "Dê um nome ao cômodo."; return; }
      if (R.uploading) { toast("Espere as fotos terminarem de enviar."); return; }
      try {
        const res = await API.put(`api/rooms/${encodeURIComponent(id)}`, { name: R.name.trim(), code: R.code.trim().toUpperCase(), photos: R.photos, cover: R.cover });
        setRev(res.rev); upsertRoom(res.room); derive(); R.dirty = false;
        requestClose(entry, { force: true }); refreshAll(); toast("Cômodo salvo");
      } catch (e) { err.hidden = false; err.textContent = e.message; }
    };
    form.addEventListener("submit", (e) => { e.preventDefault(); save(); });
    dlg.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-re]");
      if (!b) return;
      const act = b.dataset.re, i = +b.dataset.i;
      if (act === "cancel") requestClose(entry);
      else if (act === "save") save();
      else if (act === "upload") pickFiles(addFiles);
      else if (act === "camera") pickFiles(addFiles, { camera: true });
      else if (act === "cover") { R.cover = i; R.dirty = true; renderPhotos(); }
      else if (act === "up" && i > 0) { const [p] = R.photos.splice(i, 1); R.photos.splice(i - 1, 0, p); if (R.cover === i) R.cover = i - 1; else if (R.cover === i - 1) R.cover = i; R.dirty = true; renderPhotos(); }
      else if (act === "rm") { R.photos.splice(i, 1); if (R.cover >= R.photos.length) R.cover = 0; else if (R.cover > i) R.cover -= 1; R.dirty = true; renderPhotos(); }
      else if (act === "delete") {
        if (count) { toast(`Mova ou exclua os ${count} itens de ${r.name} antes de excluir o cômodo.`, { error: true }); return; }
        const ok = await confirmBox({ title: `Excluir ${r.name}?`, body: "O cômodo está vazio e sai da lista.", ok: "Excluir cômodo", danger: true });
        if (!ok) return;
        try {
          const res = await API.del(`api/rooms/${encodeURIComponent(id)}`);
          setRev(res.rev); S.rooms = res.rooms; derive(); R.dirty = false;
          finalizeThen(entry, () => { nav("#/"); toast("Cômodo excluído"); });
        } catch (er) { fail(er); }
      }
    });
  }

  async function moveRoom(id, d) {
    const ids = D.rooms.map((r) => r.id);
    const i = ids.indexOf(id), j = i + d;
    if (i < 0 || j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    try { const res = await API.post("api/rooms/order", { ids }); setRev(res.rev); S.rooms = res.rooms; derive(); refreshAll(); }
    catch (e) { fail(e); }
  }

  function openAddMenu() {
    const rid = base.name === "room" ? base.id : null;
    const entry = openDialog({
      cls: "modal narrow", label: "Adicionar",
      html: `<div class="dlg"><div class="dlg-h"><h2>Adicionar</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b" style="padding:8px 12px 16px"><ul class="opts" style="border-top:0">
          <li style="padding:0;border:0"><button class="rrow nocode" data-go="item" style="grid-template-columns:auto 1fr;padding:14px 8px">${ic("plus", "lg")}<span class="rn">Adicionar item<small style="display:block;margin:2px 0 0">Com foto e valor, preenchendo os campos</small></span></button></li>
          <li style="padding:0;border:0"><button class="rrow nocode" data-go="catalog" style="grid-template-columns:auto 1fr;padding:14px 8px">${ic("scan", "lg")}<span class="rn">Catalogar foto com IA<small style="display:block;margin:2px 0 0">A IA lista vários itens de uma foto</small></span></button></li>
          <li style="padding:0;border:0"><button class="rrow nocode" data-go="room" style="grid-template-columns:auto 1fr;padding:14px 8px;border-bottom:0">${ic("door", "lg")}<span class="rn">Novo cômodo<small style="display:block;margin:2px 0 0">Uma área nova da casa</small></span></button></li>
        </ul></div></div>`,
    });
    entry.dlg.addEventListener("click", (e) => {
      if (e.target.closest("[data-x]")) { requestClose(entry, { force: true }); return; }
      const b = e.target.closest("[data-go]");
      if (!b) return;
      const go = b.dataset.go;
      finalizeThen(entry, () => { if (go === "item") openEditor({ room: rid }); else if (go === "catalog") openCatalog({ room: rid }); else openRoomNew(); });
    });
  }

  // ------------------------------------------------------------------ exportar, backup, histórico, importar
  function download(kind) {
    if (window.INV_EXPORT) { toast(window.INV_EXPORT(kind)); return; }
    const a = document.createElement("a");
    a.href = `api/export.${kind}`;
    a.download = "";
    document.body.append(a);
    a.click();
    a.remove();
    toast(kind === "zip" ? "Preparando o ZIP com as fotos. O download começa em instantes." : "Download iniciado");
  }
  async function createBackup(btn) {
    btn.disabled = true; btn.innerHTML = `<span class="spin"></span>Criando`;
    try { const res = await API.post("api/backups"); toast(`Backup salvo: ${res.backup.name}`); loadDataPanels(); }
    catch (e) { fail(e); btn.disabled = false; btn.innerHTML = `${ic("archive")}Criar backup`; }
  }
  async function restoreBackup(name) {
    const ok = await confirmBox({ title: "Restaurar este backup?", body: `O inventário atual vai ser trocado pelo conteúdo de <b>${esc(name)}</b>. Antes, o app salva uma cópia do que existe hoje na mesma pasta.`, ok: "Restaurar", danger: true });
    if (!ok) return;
    try { await API.post("api/backups/restore", { name }); await loadData(); refreshAll(); toast("Backup restaurado"); }
    catch (e) { fail(e); }
  }
  async function restoreHistory(name, label) {
    const ok = await confirmBox({ title: "Voltar para esta versão?", body: `O inventário volta a ficar como estava em <b>${esc(label)}</b>. A versão atual também fica guardada nesta lista.`, ok: "Voltar para esta versão", danger: true });
    if (!ok) return;
    try { await API.post("api/history/restore", { name }); await loadData(); refreshAll(); toast("Versão restaurada"); }
    catch (e) { fail(e); }
  }
  $("#pick-import").addEventListener("change", (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    if (f) importFile(f);
  });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const mb = (n) => (n / 1048576).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  async function importFile(file) {
    const name = file.name || "arquivo";
    const isZip = /\.zip$/i.test(name) || /zip/.test(file.type || "");
    const isJson = /\.json$/i.test(name) || /json/.test(file.type || "");
    if (!isZip && !isJson) { fail(new Error("Escolha o backup .zip ou um .json exportado pelo app.")); return; }
    if (S.items.length || S.rooms.length) {
      const ok = await confirmBox({ title: "Trocar o inventário atual?", body: `O inventário de agora (${plural(S.items.length, "item", "itens")}) vai ser trocado pelo conteúdo de <b>${esc(name)}</b>. Antes, o app guarda uma cópia do que existe hoje.`, ok: "Importar", danger: true });
      if (!ok) return;
    }
    let cancelled = false, done = false, uid = null, lock = null;
    const entry = openDialog({
      cls: "modal narrow", label: "Importando inventário",
      html: `<div class="dlg"><div class="dlg-h"><h2>Importando inventário</h2></div>
        <div class="dlg-b"><p style="margin:0 0 12px;overflow-wrap:anywhere"><b>${esc(name)}</b></p>
          <div class="prog" role="progressbar" aria-label="Progresso do envio" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i></i></div>
          <p class="muted" data-st style="margin:10px 0 0">Preparando o envio…</p>
          <p class="muted" style="margin:6px 0 0;font-size:14px">Deixe esta tela aberta até terminar.</p></div>
        <div class="dlg-f"><span class="grow"></span><button type="button" class="btn ghost" data-x>Cancelar</button></div></div>`,
      guard: async () => {
        if (done) return true;
        const ok = await confirmBox({ title: "Cancelar a importação?", body: "O envio para no ponto em que está e nada muda no inventário.", ok: "Cancelar importação", cancel: "Continuar", danger: true });
        if (ok) cancelled = true;
        return ok;
      },
    });
    const dlg = entry.dlg;
    const st = $("[data-st]", dlg), bar = $(".prog", dlg), xbtn = $("[data-x]", dlg);
    const setProg = (p) => { bar.firstElementChild.style.width = `${(p * 100).toFixed(1)}%`; bar.setAttribute("aria-valuenow", String(Math.round(p * 100))); };
    xbtn.addEventListener("click", () => requestClose(entry));
    try { lock = navigator.wakeLock ? await navigator.wakeLock.request("screen") : null; } catch { lock = null; }
    try {
      const start = await API.post("api/upload", { name, size: file.size });
      uid = start.id;
      let off = 0;
      while (off < file.size) {
        if (cancelled) throw Object.assign(new Error("cancelado"), { cancelled: true });
        const part = file.slice(off, Math.min(file.size, off + start.chunk));
        for (let tries = 0; ; tries++) {
          try { const r = await API.raw("PUT", `api/upload/${uid}?offset=${off}`, part); off = r.received; break; }
          catch (e) {
            if (e.status === 409 && e.data && e.data.received != null) { off = e.data.received; break; }
            if (tries >= 3 || (e.status >= 400 && e.status < 500)) throw e;
            st.textContent = "A conexão oscilou. Tentando de novo…";
            await sleep(1500 * (tries + 1));
          }
        }
        setProg(off / file.size);
        st.textContent = `Enviando ${mb(off)} de ${mb(file.size)} MB`;
      }
      if (cancelled) throw Object.assign(new Error("cancelado"), { cancelled: true });
      st.textContent = "Restaurando itens e fotos…";
      xbtn.disabled = true;
      const res = await API.post(`api/upload/${uid}/restore`);
      done = true;
      await loadData();
      requestClose(entry, { force: true });
      if (base.name !== "home") nav("#/"); else refreshAll();
      toast(`Inventário importado: ${plural(res.items, "item", "itens")} em ${plural(res.rooms, "cômodo", "cômodos")}`);
    } catch (e) {
      done = true;
      if (uid) API.del(`api/upload/${uid}`).catch(() => {});
      if (stack.includes(entry)) requestClose(entry, { force: true });
      if (e.cancelled || cancelled) toast("Importação cancelada. Nada mudou no inventário.");
      else fail(e);
    } finally {
      try { if (lock) await lock.release(); } catch { /* ok */ }
    }
  }
  function setTheme(t) {
    LS.set("theme", t);
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
    $$('[data-act="theme"]').forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.theme === t)));
  }

  // ------------------------------------------------------------------ eventos globais
  document.addEventListener("click", async (e) => {
    const a = e.target.closest("a[href^='#']");
    if (a && !e.defaultPrevented && !e.metaKey && !e.ctrlKey) inAppNavs++;
    const b = e.target.closest("[data-act]");
    if (!b) return;
    const act = b.dataset.act;
    const item = b.dataset.id ? D.itemById.get(b.dataset.id) : null;
    switch (act) {
      case "add-menu": openAddMenu(); break;
      case "item-new": openEditor({ room: b.dataset.room || (base.name === "room" ? base.id : null) }); break;
      case "catalog": openCatalog({ room: b.dataset.room || (base.name === "room" ? base.id : null) }); break;
      case "room-new": openRoomNew(); break;
      case "room-edit": openRoomEdit(b.dataset.room); break;
      case "room-up": moveRoom(b.dataset.room, -1); break;
      case "room-down": moveRoom(b.dataset.room, 1); break;
      case "room-photo-add": {
        const rid = b.dataset.room;
        pickFiles(async (files) => {
          let n = 0;
          for (const f of imageFiles(files)) {
            try {
              const file = await uploadPhoto(f);
              const res = await API.post(`api/rooms/${encodeURIComponent(rid)}/photos`, { file, label: "" });
              setRev(res.rev); upsertRoom(res.room); n++;
            } catch (er) { fail(er); }
          }
          if (n) { derive(); refreshAll(); toast(n > 1 ? `${n} fotos adicionadas` : "Foto adicionada"); }
        }, { camera: false });
        break;
      }
      case "viewer-room": { const r = D.roomById.get(b.dataset.room); if (r) openViewer({ photos: r.photos, index: +b.dataset.i, roomId: r.id }); break; }
      case "viewer-item": if (item) openViewer({ photos: item.photos.map((f) => ({ file: f, label: item.name })), index: +b.dataset.i }); break;
      case "gal": if (item) { const g = $('[data-slot="gallery"]', sheet ? sheet.dlg : document); if (g) g.innerHTML = galleryHtml(item, +b.dataset.i); } break;
      case "item-edit": if (item) openEditor({ item }); break;
      case "item-dup": if (item) openEditor({ dup: item }); break;
      case "item-move": if (item) moveItem(item); break;
      case "item-delete": if (item) deleteItem(item); break;
      case "sheet-close": if (sheet) requestClose(sheet); break;
      case "search-clear": { const inp = $('#view [data-input="search-q"]'); if (inp) { inp.value = ""; inp.focus(); } updateSearch({ q: "" }); break; }
      case "search-reset": base.q = { q: base.q.q || "" }; renderView(false); try { history.replaceState(history.state, "", hashOf(base)); } catch { /* ok */ } break;
      case "more-results": searchLimit += 120; $("#results").innerHTML = resultsHtml(base.q); break;
      case "export": download(b.dataset.kind); break;
      case "backup-create": createBackup(b); break;
      case "backup-restore": restoreBackup(b.dataset.name); break;
      case "history-restore": restoreHistory(b.dataset.name, b.closest("li")?.querySelector("b")?.textContent || ""); break;
      case "import-file": $("#pick-import").click(); break;
      case "ai-refresh": { const slot = $('[data-slot="ai"]'); if (slot) { slot.innerHTML = `<p class="muted">Verificando…</p>`; renderAiPanel(slot, await aiStatus(true)); } break; }
      case "theme": setTheme(b.dataset.theme); break;
      case "print": if (window.INV_PRINT) toast(window.INV_PRINT); else window.print(); break;
      case "retry": boot(); break;
      default: break;
    }
  });
  document.addEventListener("submit", (e) => {
    const f = e.target.closest("[data-form]");
    if (!f) return;
    e.preventDefault();
    if (f.dataset.form === "homesearch") { const q = f.q.value.trim(); focusSearch = true; nav(hashOf({ name: "search", q: q ? { q } : {} })); }
    if (f.dataset.form === "search") { const inp = f.q; if (COARSE) inp.blur(); }
  });
  const onSearchInput = debounce((v) => updateSearch({ q: v }), 120);
  const onRoomFilter = debounce((rid, v) => { roomFilter[rid] = v; const z = $("#zones"); if (z) z.innerHTML = zonesHtml(rid); }, 100);
  document.addEventListener("input", (e) => {
    const t = e.target;
    const k = t.dataset && t.dataset.input;
    if (!k) return;
    if (k === "search-q") { onSearchInput(t.value); const c = $('#view [data-act="search-clear"]'); if (c) c.hidden = !t.value; }
    else if (k === "room-filter") onRoomFilter(t.dataset.room, t.value);
    else if (k === "home-q" && t.value.trim()) {
      focusSearch = true;
      nav(hashOf({ name: "search", q: { q: t.value } }));
      onRoute(); // já troca de tela aqui, para o teclado do celular continuar aberto
    }
  });
  document.addEventListener("change", async (e) => {
    const t = e.target;
    const k = t.dataset && t.dataset.input;
    if (!k) return;
    if (k === "search-room") updateSearch({ room: t.value });
    else if (k === "search-cat") updateSearch({ cat: t.value });
    else if (k === "search-ord") updateSearch({ ord: t.value });
    else if (k === "rep-photos") { LS.set("reportPhotos", t.checked); renderView(false); }
    else if (k === "ai-entity") {
      try { await API.put("api/settings", { ai_entity: t.value }); S.settings.ai_entity = t.value; const slot = $('[data-slot="ai"]'); if (slot) renderAiPanel(slot, await aiStatus(true)); toast("IA do app atualizada"); }
      catch (er) { fail(er); }
    }
  });
  document.addEventListener("keydown", (e) => {
    if (stack.length) {
      const top = topEntry();
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && top.onSubmit) { e.preventDefault(); top.onSubmit(); }
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable]")) return;
    if (e.key === "/") {
      e.preventDefault();
      if (base.name === "search") $('#view [data-input="search-q"]')?.focus();
      else { focusSearch = true; nav("#/buscar"); }
    } else if (e.key === "n" || e.key === "N") { e.preventDefault(); openEditor({ room: base.name === "room" ? base.id : null }); }
  });
  window.addEventListener("hashchange", () => { onRoute(); });
  window.addEventListener("scroll", () => { $("#topbar").classList.toggle("scrolled", window.scrollY > 4); }, { passive: true });

  // atualização quando outro aparelho mexer no inventário
  async function checkRev() {
    if (document.hidden || !S.loaded || PREVIEW) return;
    try {
      const r = await API.get("api/rev");
      if (r && r.rev !== S.rev) {
        if (stack.some((m) => !m.routed)) { S.stale = true; return; }
        await loadData();
        refreshAll();
      }
    } catch { /* tenta de novo depois */ }
  }
  setInterval(checkRev, 30000);
  document.addEventListener("visibilitychange", checkRev);

  // ------------------------------------------------------------------ início
  async function boot() {
    const view = $("#view");
    try {
      await loadData();
    } catch (e) {
      view.innerHTML = `<div class="empty">${emptyMark()}<h2>Não deu para abrir o inventário</h2><p>${esc(e.message)}</p><div class="acts"><button class="btn primary" data-act="retry">${ic("refresh")}Tentar de novo</button></div></div>`;
      return;
    }
    onRoute();
  }
  if (!PREVIEW || window.INV_BACKEND) boot();
  else window.INV_BOOT = boot;
})();
