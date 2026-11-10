/* InventarIA: interface do app de inventário da casa para o Home Assistant.
   JavaScript puro, sem dependências nem etapa de build. Fala com o servidor em api/... (URLs relativas, por causa do Ingress). */
(() => {
  "use strict";

  // ------------------------------------------------------------------ constantes
  // categorias: a lista padrão até a casa editar (Mais > Categorias); a lista da casa vem com os dados
  const DEFAULT_CATS = [
    ["eletronicos", "Eletrônicos"], ["moveis", "Móveis"], ["decoracao", "Decoração e arte"],
    ["colecao", "Colecionáveis"], ["cozinha", "Cozinha e bar"], ["texteis", "Tapetes e têxteis"],
    ["plantas", "Plantas"], ["livros", "Livros e jogos"], ["pets", "Pets"], ["saude", "Saúde"],
    ["vestuario", "Roupas e calçados"], ["utilidades", "Utilidades"], ["imoveis", "Imóveis"], ["veiculos", "Veículos"], ["outros", "Outros"],
  ];
  let CATS = DEFAULT_CATS, CAT = Object.fromEntries(CATS);
  function applyCats(list) {
    CATS = Array.isArray(list) && list.length ? list.map((c) => [c.id, c.name]) : DEFAULT_CATS;
    CAT = Object.fromEntries(CATS);
  }
  const SOURCES = { foto: "Catalogado por foto", informado: "Valor informado", ia: "Leitura por IA", voz: "Cadastro por voz", manual: "Cadastro manual", correria: "Pelo CorrerIA" };
  const ORDERS = [["rel", "Mais relevantes"], ["val", "Maior valor"], ["valasc", "Menor valor"], ["az", "Nome, de A a Z"], ["new", "Mais recentes"], ["code", "Código"]];
  const PREVIEW = !!window.INV_PREVIEW;
  const COARSE = window.matchMedia("(pointer: coarse)").matches;
  // Dentro do app do Home Assistant no Android (WebView), o botão de câmera abre a galeria
  // e a seleção de vários arquivos pode não voltar para a página: lá usamos um arquivo por vez.
  const UA = navigator.userAgent || "";
  const ANDROID_APP = /Android/i.test(UA) && (/Home ?Assistant\//i.test(UA) || /; wv\)/.test(UA));
  const CAMERA_DIRECT = COARSE && !ANDROID_APP;
  // o app do Home Assistant no Android ignora o "capture" e abre a galeria: lá a câmera é a do próprio app (como no ResolvIA)
  const CAMERA = CAMERA_DIRECT || ANDROID_APP;
  const MULTI_PICK = !ANDROID_APP;
  // O ícone do app (o mesmo desenho do ícone do app no Home Assistant: a etiqueta com R$ e o fio), na cor
  // escolhida em Mais > Configurações > Aparência. O fio fica na cor do texto, para aparecer no tema escuro.
  const APP_ICON = `<svg class="app-ic" viewBox="0 0 32 32" aria-hidden="true"><g transform="rotate(-12 17 19)"><path d="M10 10h18a2.5 2.5 0 0 1 2.5 2.5v13a2.5 2.5 0 0 1-2.5 2.5H10l-7-7v-4z" style="fill:var(--tag);stroke:var(--tag-edge)" stroke-width="1"/><path d="M12.6 12.6v12.8" style="stroke:var(--tag-ink)" stroke-opacity=".32" stroke-width="1.1" stroke-dasharray="1.7 1.5"/><circle cx="8" cy="19" r="2.3" style="fill:var(--paper);stroke:var(--tag-ring)" stroke-width="1.3"/><text x="21.8" y="23.3" text-anchor="middle" style="font:700 10.5px var(--font-c);fill:var(--tag-ink)">R$</text></g><path d="M8.2 20.9C6.6 15 5.7 8.6 7 2.6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>`;
  const BRAND = APP_ICON;

  // ------------------------------------------------------------------ utilidades
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const nf2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nf1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
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
  // a data e a hora de um backup, curta como no ResolvIA: "09/11/2026 às 21:17"
  const shortDateTime = (s) => {
    const t = parseDate(s), d = new Date(t), p = (n) => String(n).padStart(2, "0");
    return t ? `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} às ${p(d.getHours())}:${p(d.getMinutes())}` : "";
  };
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
  // Cor do app (as cores ficam no style.css, em [data-accent]): a paleta da família, as mesmas 12 cores do CronologIA, com o
  // preenchimento de cada uma (a conta da mais próxima usa ele). Vale para a casa toda (gravada no servidor, em settings.accent
  // e settings.accent_daily); o aparelho guarda uma cópia só para pintar a tela antes de carregar (o index.html).
  const ACCENTS = [["vermelho", "Vermelho", "#ff5a4f"], ["coral", "Coral", "#ff8a65"], ["laranja", "Laranja", "#ffa23e"], ["ouro", "Ouro", "#f2c14e"],
    ["verde", "Verde", "#8bd45f"], ["menta", "Menta", "#4ed3a6"], ["turquesa", "Turquesa", "#3ccbda"], ["azul", "Azul", "#62b5ff"],
    ["indigo", "Índigo", "#8f9bff"], ["lilas", "Lilás", "#b99bff"], ["rosa", "Rosa", "#ff77a9"], ["grafite", "Grafite", "#b5b9c2"]];
  const ACCENT0 = "ouro"; // a cor do app quando ninguém escolheu (a etiqueta do ícone)
  // as cores de antes da paleta da família (até a 1.41): uma gravada vira a mais próxima
  const OLD_ACCENTS = { amarelo: "#f5c400", kraft: "#caa377", cinza: "#acb2b9" };
  function nearestAccent(a) {
    if (ACCENTS.some(([k]) => k === a)) return a;
    const hex = OLD_ACCENTS[a] || (/^#[0-9a-f]{6}$/i.test(a || "") ? a : null);
    if (!hex) return ACCENT0;
    const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    const c = rgb(hex);
    const dist = (h) => { const [r, g, b] = rgb(h), m = (r + c[0]) / 2; return (2 + m / 256) * (r - c[0]) ** 2 + 4 * (g - c[1]) ** 2 + (2 + (255 - m) / 256) * (b - c[2]) ** 2; };
    return ACCENTS.reduce((best, x) => (dist(x[2]) < dist(best[2]) ? x : best))[0];
  }
  // a da casa (depois de carregar: settings.accent e accent_daily) ou a cópia do aparelho
  let HOUSE_LOOK = {};
  const houseSet = (k) => HOUSE_LOOK[k] != null;
  const pickedAccent = () => nearestAccent(houseSet("accent") ? HOUSE_LOOK.accent : LS.get("accent", ACCENT0));
  // Cor do dia (Mais > Configurações > Aparência): ligada até a pessoa desligar ou escolher uma cor. Uma cor por dia, pela data
  // local, a mesma em todos os apps da família: as 11 cores da paleta sem o Grafite, na ordem, pelo número do dia desde
  // 01/01/1970 (Date.UTC do dia local). O index.html faz a mesma conta antes de pintar a tela.
  const DAY_ACCENTS = ACCENTS.map(([k]) => k).filter((k) => k !== "grafite");
  function colorOfDay(d = new Date()) {
    const day = Math.floor(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86400000), n = DAY_ACCENTS.length;
    return DAY_ACCENTS[((day % n) + n) % n];
  }
  const accentDaily = () => (houseSet("accent_daily") ? HOUSE_LOOK.accent_daily !== false : LS.get("accentDaily", true) !== false);
  const accentOf = () => (accentDaily() ? colorOfDay() : pickedAccent());
  // Mais é um menu (#/mais): Novidades (#/novidades), Categorias (#/categorias), Relatório, Configurações e, por último, Sobre (#/sobre). Configurações em abas,
  // na ordem da família (Integrações › Dados › Aparência › Opções), abrindo em Integrações: #/config (Integrações), #/config/dados (com Exportar no
  // alto), #/config/aparencia e #/config/opcoes.
  const ALL_TABS = [["integracoes", "Integrações", "plug"], ["dados", "Dados", "archive"], ["aparencia", "Aparência", "palette"], ["opcoes", "Opções", "toggle"]];
  const moreTabs = () => ALL_TABS;
  const moreTab = (t) => (ALL_TABS.some(([k]) => k === t) ? t : ALL_TABS[0][0]);
  const IN_MORE = ["menu", "bens", "charts", "news", "cats", "data", "report", "about"]; // telas que ficam embaixo de Mais
  function applyAccent(a) {
    if (a === ACCENT0) delete document.documentElement.dataset.accent;
    else document.documentElement.dataset.accent = a;
    // Aparência aberta: a cor que está valendo fica marcada
    document.querySelectorAll('[data-input="accent"]').forEach((r) => { r.checked = r.value === a; });
  }
  applyAccent(accentOf());
  // passou da meia-noite com o app aberto: a cor do dia novo, sem recarregar
  const refreshAccent = () => { if (accentDaily()) applyAccent(colorOfDay()); };
  setInterval(refreshAccent, 60000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshAccent(); });
  window.addEventListener("focus", refreshAccent);
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
  // Opções da casa (Mais), iguais em todos os aparelhos: a IA vem ligada; as zonas, desligadas.
  // Desligar só esconde: nada do que já foi gravado se perde.
  const aiOn = () => S.settings.ai !== false;
  const zonesOn = () => S.settings.zones === true;
  const newsOn = () => aiOn() && S.settings.news !== false; // Novidades: precisa da IA e pode ser desligada em Opções
  const sensorsOn = () => S.settings.ha_sensors === true; // sensores no Home Assistant: só com a opção ligada
  let D = null;
  const roomFilter = {};
  let searchLimit = 120;
  let firstHome = true;
  let focusSearch = false;

  // Bens: o que tem valor e fica fora de casa (casa, terreno, carro). Uma área do sistema (kind "bens"), fora da lista
  // de cômodos: conta no patrimônio, nos gráficos e na busca; o relatório mostra à parte.
  const BENS_NEW = "@bens"; // a área ainda não existe: é criada ao gravar o primeiro bem
  const BENS_GROUPS = [["imoveis", "Imóveis"], ["veiculos", "Veículos"], ["", "Outros"]];
  const bensGroup = (it) => (it.cat === "imoveis" || it.cat === "veiculos" ? it.cat : "");
  const bensOn = () => S.settings.bens !== false; // Mais > Configurações > Opções > Usar bens (desligar não apaga)
  const correriaOn = () => S.settings.correria === true; // Mais > Configurações > Integrações > CorrerIA (desligado de início)
  // Valor de hoje (Mais > Configurações > Integrações > GerencIA, desligado de início): com a depreciação que o GerencIA
  // publica (a perda por ano, em %, de cada categoria; negativa: valoriza), o valor perde a taxa por ano, composta, desde
  // a data do valor (valueAt). A mesma conta do bens.valor_hoje do GerencIA e do valor_hoje do server.py. Só na tela: o
  // valor gravado (e o da ficha, ao editar) não muda.
  const deprecOn = () => S.settings.deprec === true && !!(S.gerencia && S.gerencia.taxas);
  const taxaDe = (it) => { const t = (S.gerencia && S.gerencia.taxas) || {}, c = it.cat || "outros"; return c in t ? +t[c] : 10; };
  const diaLocal = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || "")); return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null; };
  function valorHoje(it, hoje = new Date()) {
    const v = +it.value || 0, d0 = diaLocal(it.valueAt || it.createdAt);
    if (!v || !deprecOn() || !d0) return v;
    const h = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
    return v * (1 - taxaDe(it) / 100) ** (Math.max(0, Math.round((h - d0) / 864e5)) / 365.25);
  }
  const taxaTxt = (t) => (t > 0 ? `−${String(+t).replace(".", ",")}%` : t < 0 ? `+${String(-t).replace(".", ",")}%` : "0%");
  const dataCurta = (s) => { const d = diaLocal(s); return d ? `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}` : ""; };
  const vl = (it) => (D && D.vh && D.vh.has(it.id) ? D.vh.get(it.id) : valorHoje(it));
  function derive() {
    const sorted = [...S.rooms].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    const area = sorted.find((r) => r.kind === "bens") || null, bens = bensOn() ? area : null;
    const rooms = sorted.filter((r) => r !== area), all = bens ? sorted : rooms;
    const items = area && !bens ? S.items.filter((i) => i.room !== area.id) : S.items; // os itens que contam (sem os bens, se desligados)
    const roomById = new Map(all.map((r) => [r.id, r]));
    const byRoom = new Map(all.map((r) => [r.id, []]));
    const photoItems = new Map();
    const catTotals = new Map();
    const vh = new Map(S.items.map((it) => [it.id, valorHoje(it)]));
    let total = 0;
    for (const it of items) {
      if (!byRoom.has(it.room)) byRoom.set(it.room, []);
      byRoom.get(it.room).push(it);
      const v = vh.get(it.id) || 0;
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
      roomTotals.set(rid, list.reduce((s, i) => s + (vh.get(i.id) || 0), 0));
    }
    const files = new Set();
    for (const it of items) for (const p of it.photos || []) files.add(p);
    for (const r of rooms) for (const p of r.photos || []) files.add(p.file);
    const bensItems = bens ? byRoom.get(bens.id) || [] : [], bensTotal = bens ? roomTotals.get(bens.id) || 0 : 0;
    D = { vh, rooms, allRooms: all, bens, bensItems, bensTotal, houseTotal: total - bensTotal, houseCount: items.length - bensItems.length, items,
      roomById, byRoom, roomTotals, catTotals, photoItems, total, photoCount: files.size, itemById: new Map(items.map((i) => [i.id, i])) };
  }
  const isBens = (rid) => rid === BENS_NEW || (!!D.bens && rid === D.bens.id);
  // as opções de cômodo de um item: os cômodos e, no fim, Bens
  const roomOptions = (sel) => [...D.rooms, ...(bensOn() ? [D.bens || { id: BENS_NEW, name: "Bens" }] : [])]
    .map((r) => `<option value="${esc(r.id)}"${r.id === sel ? " selected" : ""}>${esc(r.name)}</option>`).join("");
  async function realRoom(rid) { // "@bens": cria a área Bens (uma vez) e devolve o id dela
    if (rid !== BENS_NEW) return rid;
    const res = await API.post("api/rooms", { kind: "bens" });
    setRev(res.rev); S.rooms = res.rooms; if (res.cats) { S.cats = res.cats; applyCats(res.cats); } derive();
    return res.room.id;
  }
  const tagOf = (it) => `${D.roomById.get(it.room)?.code || "ITM"}-${String(it.seq || 0).padStart(3, "0")}`;
  const zonesOf = (rid) => [...new Set((D.byRoom.get(rid) || []).map((i) => i.zone).filter(Boolean))];
  const lastRoom = () => { const r = LS.get("lastRoom", null); return D.rooms.some((x) => x.id === r) ? r : D.rooms[0]?.id || ""; };
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
      correriaUso: d.correria_uso || null, gerencia: d.gerencia || null, resolvia: d.resolvia === true, atalho: d.atalho || null,
    });
    applyCats(d.cats);
    derive();
    syncLook();
  }

  // ------------------------------------------------------------------ avisos
  function toastBox() {
    let box = document.getElementById("toasts");
    if (!box) {
      box = document.createElement("div");
      box.className = "toasts"; box.id = "toasts";
      box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite");
      document.body.append(box);
    }
    return box;
  }
  function toast(msg, opts = {}) {
    const box = toastBox();
    const el = document.createElement("div");
    el.className = "toast" + (opts.error ? " err" : "");
    el.innerHTML = `<span class="tmsg">${esc(msg)}</span>${opts.action ? `<button type="button">${esc(opts.action)}</button>` : ""}`;
    let done = false;
    const close = () => { if (!done) { done = true; el.remove(); } };
    if (opts.action) el.querySelector("button").addEventListener("click", () => { close(); opts.onAction && opts.onAction(); });
    box.append(el);
    while (box.children.length > 3) box.firstElementChild.remove();
    showToasts();
    setTimeout(close, opts.ms || (opts.action ? 8000 : 3800));
    return close;
  }
  const fail = (e) => toast(e?.message || String(e), { error: true, ms: 7000 });
  function showToasts() {
    // Janelas abertas ficam numa camada acima da página; os avisos vão para dentro da janela de cima
    // para aparecer (e o botão "Desfazer" funcionar) mesmo com o editor aberto.
    const box = toastBox();
    const host = (stack.length && stack[stack.length - 1].dlg) || document.body;
    if (box.parentElement !== host) host.append(box);
  }

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
      const box = $("#toasts");
      if (box && dlg.contains(box)) ((stack.length && stack[stack.length - 1].dlg) || document.body).append(box);
      dlg.remove();
      entry.onClose && entry.onClose();
      if (entry.routed) { entry.onRouteClose && entry.onRouteClose(); }
      else if (entry.pushed && !entry.awaitingPop && history.state && history.state.invModal) { ignorePops++; history.back(); }
    });
    dlg.addEventListener("pointerdown", (e) => { entry.downOnBackdrop = e.target === dlg; });
    dlg.addEventListener("click", (e) => { if (e.target === dlg && entry.downOnBackdrop) requestClose(entry); });
    entry.opener = document.activeElement && document.activeElement !== document.body ? document.activeElement : null; // antes de abrir: depois, o foco já está na janela
    entry.openerKey = openerKey(entry.opener);
    dlg.showModal();
    showToasts(); // os avisos (com o Desfazer) vão para a janela nova, à mão
    return entry;
  }
  // a janela fecha depois de a tela ser redesenhada: o foco volta para o botão equivalente, não para o começo da página
  function openerKey(el) {
    if (!el || !el.dataset || !el.dataset.act) return "";
    const q = (k) => (el.dataset[k] ? `[data-${k}="${CSS.escape(el.dataset[k])}"]` : "");
    return `[data-act="${CSS.escape(el.dataset.act)}"]${q("room")}${q("id")}`;
  }
  function focusBack(entry) {
    setTimeout(() => {
      if (stack.length) return;
      const a = document.activeElement;
      if (a && a !== document.body && a.isConnected) return;
      const el = entry.opener && entry.opener.isConnected ? entry.opener : entry.openerKey ? $(entry.openerKey) : null;
      if (el) try { el.focus({ preventScroll: true }); } catch { /* ok */ }
    }, 0);
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
    const box = $("#toasts");
    if (box && entry.dlg.contains(box)) ((stack.length && stack[stack.length - 1].dlg) || document.body).append(box);
    try { entry.dlg.close(); } catch { /* já fechado */ }
    entry.dlg.remove();
    entry.onClose && entry.onClose();
    focusBack(entry);
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

  // ------------------------------------------------------------------ sugestões no visual do app
  // No lugar da lista do celular (<datalist>, que no Android abre fora do padrão), como no GerencIA: o campo com
  // data-sug="<id do datalist>" mostra logo abaixo, dentro da janela, até 6 sugestões que combinam com o que foi
  // digitado (sem acento); ao entrar num campo que já tem uma delas, as outras. Tocar numa preenche o campo (com os
  // eventos input e change de sempre); sair do campo, Esc ou escolher fecha. No teclado, as setas marcam uma e o Enter escolhe.
  let SUG = null; // {inp, box, at, press}
  function sugClose() { if (SUG) { SUG.box.remove(); SUG = null; } }
  function sugShow(inp, entering = false) {
    const dl = document.getElementById(inp.dataset.sug), cur = norm(inp.value.trim());
    const all = dl ? [...new Set([...dl.options].map((o) => o.value))].filter(Boolean) : [];
    const q = entering && all.some((v) => norm(v) === cur) ? "" : cur;
    const ops = all.filter((v) => norm(v) !== cur && (!q || norm(v).includes(q))).slice(0, 6);
    if (!ops.length) { sugClose(); return; }
    const fresh = !SUG || SUG.inp !== inp || !SUG.box.isConnected;
    if (fresh) {
      sugClose();
      const box = document.createElement("div");
      box.className = "sug-box";
      box.setAttribute("role", "listbox");
      if (inp.id) box.id = `${inp.id}-sug`;
      // embaixo do campo (ou da linha dele, quando o campo divide a linha com outros, como no Catalogar)
      (inp.closest(".frow2") || inp).insertAdjacentElement("afterend", box);
      SUG = { inp, box, at: -1, press: false };
    }
    SUG.at = -1;
    SUG.box.innerHTML = ops.map((v) => `<button type="button" class="sug-op" role="option" tabindex="-1" data-sugv="${esc(v)}">${esc(v)}</button>`).join("");
    if (fresh) requestAnimationFrame(() => { if (SUG && SUG.box.isConnected) SUG.box.scrollIntoView({ block: "nearest" }); });
  }
  function sugPick(b) {
    if (!SUG) return;
    const inp = SUG.inp;
    inp.value = b.dataset.sugv;
    sugClose();
    inp.dispatchEvent(new Event("input", { bubbles: true }));
    inp.dispatchEvent(new Event("change", { bubbles: true }));
    sugClose(); // o input acima mostraria as que ainda combinam: escolher fecha
  }
  const isSug = (t) => t && t.matches && t.matches("input[data-sug]");
  document.addEventListener("focusin", (e) => { if (isSug(e.target)) sugShow(e.target, true); });
  document.addEventListener("input", (e) => { if (isSug(e.target) && document.activeElement === e.target) sugShow(e.target); });
  document.addEventListener("focusout", (e) => {
    if (!SUG || e.target !== SUG.inp) return;
    setTimeout(() => { if (SUG && !SUG.press && document.activeElement !== SUG.inp) sugClose(); }, 150);
  });
  // o toque na sugestão não tira o foco do campo (o teclado do celular fica); arrastar para rolar não escolhe
  document.addEventListener("pointerdown", (e) => {
    const b = e.target.closest && e.target.closest(".sug-op");
    if (!b || !SUG) return;
    e.preventDefault();
    SUG.press = true;
  }, true);
  document.addEventListener("mousedown", (e) => { if (e.target.closest && e.target.closest(".sug-op")) e.preventDefault(); }, true);
  const sugRelease = () => { if (SUG) { SUG.press = false; if (document.activeElement !== SUG.inp) sugClose(); } };
  document.addEventListener("pointercancel", sugRelease, true);
  document.addEventListener("pointerup", () => { if (SUG && SUG.press) setTimeout(sugRelease, 300); }, true); // depois do clique
  document.addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest(".sug-op");
    if (!b || !SUG || !SUG.box.contains(b)) return;
    e.preventDefault();
    e.stopPropagation();
    sugPick(b);
  }, true);
  document.addEventListener("keydown", (e) => {
    if (!SUG || e.target !== SUG.inp) return;
    const ops = [...SUG.box.querySelectorAll(".sug-op")];
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); sugClose(); return; } // só a lista, não a janela
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      SUG.at = Math.max(-1, Math.min(ops.length - 1, SUG.at + (e.key === "ArrowDown" ? 1 : -1)));
      ops.forEach((o, i) => { o.classList.toggle("on", i === SUG.at); o.setAttribute("aria-selected", i === SUG.at ? "true" : "false"); });
      if (ops[SUG.at]) ops[SUG.at].scrollIntoView({ block: "nearest" });
      return;
    }
    if (e.key === "Enter" && ops[SUG.at] && !e.isComposing) { e.preventDefault(); e.stopPropagation(); sugPick(ops[SUG.at]); }
    else if (e.key === "Tab") sugClose();
  }, true);

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
      case "c": return D && D.bens && parts[1] === D.bens.id ? { name: "bens", q } : { name: "room", id: parts[1], q };
      case "bens": return bensOn() ? { name: "bens", q } : { name: "menu" }; // bens desligados: o menu Mais
      case "i": return { name: "item", id: parts[1], q };
      case "buscar": return { name: "search", q };
      case "relatorio": return { name: "report", q };
      case "comodos": return { name: "rooms", q };
      case "mais": // #/mais é o menu; #/mais/<aba> é o endereço antigo de Configurações (e de Novidades)
        if (!parts[1]) return { name: "menu", q };
        if (parts[1] === "novidades") return { name: newsOn() ? "news" : "menu", q };
        if (parts[1] === "sobre") return { name: "about", q }; // como no CronologIA (#/mais/sobre)
        return { name: "data", tab: moreTab(parts[1]), q };
      case "config": return { name: "data", tab: moreTab(parts[1]), q };
      case "dados": return { name: "data", tab: "dados", q }; // o endereço antigo dos Dados
      case "novidades": return { name: newsOn() ? "news" : "menu", q }; // Novidades usa a IA e pode ser desligada: fica o menu
      case "categorias": return { name: "cats", q };
      case "graficos": return { name: "charts", q };
      case "sobre": return { name: "about", q };
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
      case "rooms": return "#/comodos";
      case "menu": return "#/mais";
      case "news": return "#/novidades";
      case "cats": return "#/categorias";
      case "charts": return "#/graficos";
      case "bens": return "#/bens";
      case "about": return "#/sobre";
      case "data": { const t = moreTab(r.tab); return t === ALL_TABS[0][0] ? "#/config" : `#/config/${t}`; }
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
      if (!rendered) { base = isBens(it.room) ? { name: "bens", q: {} } : { name: "room", id: it.room, q: {} }; renderView(true); }
      showItemSheet(it);
      return;
    }
    if (IN_MORE.includes(r.name) && location.hash.split("?")[0] !== hashOf(r)) { // endereço antigo: troca pelo de agora
      try { history.replaceState(history.state, "", hashOf(r)); } catch { /* ok */ }
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
      <a class="brand" href="#/">${BRAND}<span class="brand-name">InventarIA</span></a>
      <nav class="nav" aria-label="Seções">
        <a href="#/"${cr("home")}>${ic("home")}Início</a>
        <a href="#/buscar"${cr("search")}>${ic("search")}Buscar<kbd>/</kbd></a>
        <a href="#/comodos"${cr("rooms")}>${ic("rooms")}Cômodos</a>
        <a href="#/relatorio"${cr("report")}>${ic("report")}Relatório</a>
        <a href="#/mais"${IN_MORE.includes(cur.name) && cur.name !== "report" ? ' aria-current="page"' : ""}>${ic("menu")}Mais</a>
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
    return { home: "Início", search: "Buscar", rooms: "Cômodos", report: "Relatório", menu: "Mais", bens: "Bens", charts: "Gráficos", news: "Novidades", cats: "Categorias", data: "Configurações", about: "Sobre" }[r.name] || "InventarIA";
  }
  // Topo de cada tela, igual nos apps da família (EconomIA, ResolvIA): nome do app com "IA" na cor
  // do app, saudação ao usuário do Home Assistant e o título grande da tela.
  const TAB_OF = { home: "home", search: "search", rooms: "rooms", room: "rooms", menu: "data", bens: "data", charts: "data", news: "data", cats: "data", data: "data", report: "data", about: "data" };
  function renderTop() {
    const el = $("#topbar");
    const r = base;
    const first = (S.user || "").trim().split(/\s+/)[0];
    const up = r.name === "room" ? ["#/comodos", "Cômodos"] : IN_MORE.includes(r.name) && r.name !== "menu" ? ["#/mais", "Mais"] : null;
    const title = r.name === "room" || r.name === "report" ? "" : viewTitle(r);
    const sub = r.name === "rooms" && D.rooms.length
      ? `${plural(D.rooms.length, "cômodo", "cômodos")}, ${plural(D.houseCount, "item", "itens")}, ${money(D.houseTotal)}`
      : r.name === "bens" && D.bensItems.length ? `${plural(D.bensItems.length, "bem", "bens")}, ${money(D.bensTotal)}`
      : r.name === "data" ? `${plural(S.items.length, "item", "itens")} e ${plural(D.photoCount, "foto", "fotos")} no inventário` : "";
    el.innerHTML = `
      <div class="mh-row">
        <p class="eyebrow"><span class="brand-word">${APP_ICON}Inventar<span>IA</span></span>${first ? `<span class="hello"><span class="sep"> · </span>Olá, ${esc(first)}</span>` : ""}</p>
        ${aiOn() ? `<button type="button" class="chat-top" data-act="chat" aria-label="Conversar com a IA" title="Conversar">${ic("chat")}</button>` : ""}
        ${voiceReady() ? `<button type="button" class="mic-top" data-act="voice" aria-label="Falar: adicionar itens falando" title="Falar">${ic("mic")}</button>` : ""}
        ${r.name !== "room" ? `<div class="top-actions">
          ${aiOn() ? `<button type="button" class="btn wide" data-act="catalog">${ic("scan")}Catalogar itens com IA</button>` : ""}
          <button type="button" class="btn primary wide" data-act="item-new">${ic("plus")}Adicionar item</button></div>` : ""}
      </div>
      ${up ? `<a class="uplink" href="${up[0]}">${ic("back", "sm")}${up[1]}</a>` : ""}
      ${title ? `<h1 class="page-title">${esc(title)}</h1>` : ""}
      ${sub ? `<p class="page-sub">${sub}</p>` : ""}`;
    $$(".tabbar [data-tab]").forEach((a) => {
      if (a.dataset.tab === TAB_OF[r.name]) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }

  // ------------------------------------------------------------------ renderização das telas
  function renderView(navigated) {
    const view = $("#view");
    const key = hashOf(base);
    const focus = navigated ? null : captureFocus();
    const y = window.scrollY;
    let html;
    if (navigated) roomsOrganize = false;
    try {
      if (base.name !== "search") SEL = null;
      switch (base.name) {
        case "room": html = viewRoom(base.id); break;
        case "search": html = viewSearch(base.q); break;
        case "report": html = viewReport(); break;
        case "rooms": html = viewRooms(); break;
        case "menu": html = viewMenu(); break;
        case "news": html = `<div class="mscreen">${moreNews()}</div>`; break;
        case "cats": html = `<div class="mscreen">${viewCats()}</div>`; break;
        case "charts": html = viewCharts(); break;
        case "bens": html = viewBens(); break;
        case "data": html = viewData(); break;
        case "about": html = viewAbout(); break;
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
    document.title = base.name === "home" ? "InventarIA" : `InventarIA – ${viewTitle(base)}`;
    if (navigated) {
      const memo = scrollMemo.get(key);
      window.scrollTo(0, memo || 0);
    } else {
      window.scrollTo(0, y);
      restoreFocus(focus);
    }
    if (navigated) navCount++;
    afterRender(navigated);
  }
  // No computador, abrir pelo menu uma tela que tem busca já deixa o cursor nela, pronto para digitar
  // (Buscar, a busca do Início e o filtro do cômodo). A primeira tela, ao abrir o app, não puxa o cursor.
  let navCount = 0;
  const focusFree = () => { const a = document.activeElement; return !a || a === document.body || !!a.closest("#side, #tabbar"); };
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
  function afterRender(navigated = false) {
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
      if (inp && (focusSearch || (!COARSE && focusFree()))) {
        inp.focus({ preventScroll: true });
        try { inp.setSelectionRange(inp.value.length, inp.value.length); } catch { /* ok */ }
      }
      focusSearch = false;
    } else if (navigated && navCount > 1 && !COARSE && focusFree() && !document.querySelector("dialog[open]")) {
      const box = base.name === "home" ? $('#view [data-input="home-q"]') : base.name === "room" ? $('#view [data-input="room-filter"]') : null;
      box?.focus({ preventScroll: true });
    }
    if (base.name === "data") loadDataPanels();
    if (base.name === "news") loadNews();
    if (base.name === "charts") drawArea();
    if (navigated && slideFrom) { // a tela nova entra pelo lado para onde o dedo foi
      const dir = slideFrom;
      slideFrom = 0;
      if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && $("#view").animate) {
        $("#view").animate([{ opacity: 0, transform: `translateX(${dir > 0 ? 40 : -40}px)` }, { opacity: 1, transform: "none" }], { duration: 280, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" });
      }
    }
  }

  // -- linhas reutilizáveis
  function itemRow(it, { toks = [], mode = "global", pick = null } = {}) {
    const ph = it.photos && it.photos[0];
    const room = D.roomById.get(it.room);
    let where;
    if (mode === "room") where = it.details ? hl(snippet(it.details), toks) : "";
    else if (mode === "bens") where = esc(CAT[it.cat] || "Outros");
    else where = hl([room?.name, zonesOn() ? it.zone : ""].filter(Boolean).join(", "), toks);
    const qty = qtyClean(it.qty);
    const thumb = ph ? `<img class="thumb" src="${esc(src(ph))}" alt="" loading="lazy" decoding="async" width="56" height="56">` : `<span class="thumb">${ic("tag")}</span>`;
    const inner = `${pick === null ? thumb : `<span class="tw">${thumb}<span class="pk" aria-hidden="true">${ic("check", "sm")}</span></span>`}
      <span class="ib"><span class="nm">${hl(it.name, toks)}</span>
        <span class="meta"><span class="mt soft">${esc(tagOf(it))}</span>${where ? `<span class="z">${where}</span>` : ""}</span></span>
      <span class="iv"><span class="val">${money(vl(it))}</span>${qty !== "1" ? `<span class="qty">${esc(qtyShort(it.qty))}</span>` : ""}</span>`;
    if (pick !== null) return `<li><button type="button" class="irow selr" data-act="sel-toggle" data-id="${esc(it.id)}" aria-pressed="${pick === true}"${pick === "off" ? " disabled" : ""}>${inner}</button></li>`;
    return `<li><a class="irow" href="#/i/${encodeURIComponent(it.id)}">${inner}</a></li>`;
  }
  function roomRow(r, max) {
    const v = D.roomTotals.get(r.id) || 0;
    const n = (D.byRoom.get(r.id) || []).length;
    return `<li><a class="rrow" href="#/c/${encodeURIComponent(r.id)}">
      <span class="mt">${esc(r.code)}</span>
      <span class="rn">${esc(r.name)}<small>${plural(n, "item", "itens")}</small></span>
      <span class="rv">${moneyR(v)}</span>
      <span class="bar"><i style="width:${max > 0 ? ((v / max) * 100).toFixed(2) : 0}%"></i></span>
      <span class="pct">${pctFmt(pct(v, D.houseTotal))}</span></a></li>`;
  }

  // -- início
  const secIc = (name) => `<span class="sec-ic" aria-hidden="true">${ic(name)}</span>`;
  function viewHome() {
    if (!D.rooms.length) {
      return `<section class="hero welcome">
        <div class="tagwrap">
          <div class="tagswing">
            <svg class="string" viewBox="0 0 120 140" aria-hidden="true"><path d="M36 132 C 35 104, 28 50, 25 0"/></svg>
            <div class="tag" role="img" aria-label="Bem-vindo ao InventarIA">
              <div class="tag-body"><p class="tag-label">Bem-vindo ao</p><p class="tag-value">InventarIA</p><p class="tag-sub">Cômodos, itens, fotos e valores</p></div>
            </div>
          </div>
        </div>
        <div class="welcome-text">
          <h1>Vamos começar</h1>
          <p>Importe um backup (.zip) ou crie o primeiro cômodo.</p>
          <div class="acts"><button type="button" class="btn primary" data-act="import-file">${ic("upload")}Importar backup</button>
            <button type="button" class="btn" data-act="room-new">${ic("plus")}Criar o primeiro cômodo</button></div>
          <p class="muted" style="font-size:14px;margin:0">${MULTI_PICK ? "Backup em partes: escolha todas de uma vez." : "Backup em partes: uma de cada vez, começando pela parte 1."}</p>
        </div>
      </section>`;
    }
    const n = D.items.length;
    const byValue = [...D.items].sort((a, b) => vl(b) - vl(a));
    const recent = [...D.items].sort((a, b) => parseDate(b.createdAt) - parseDate(a.createdAt)).slice(0, 6);
    const maxRoom = Math.max(0, ...D.rooms.map((r) => D.roomTotals.get(r.id) || 0));
    const bigRoom = D.rooms.find((r) => (D.roomTotals.get(r.id) || 0) === maxRoom);
    const top = byValue[0], last = recent[0];
    return `
    <section class="hero">
      <div class="tagwrap">
        <div class="tagswing">
          <svg class="string" viewBox="0 0 120 140" aria-hidden="true"><path d="M36 132 C 35 104, 28 50, 25 0"/></svg>
          <div class="tag" role="img" aria-label="Patrimônio: ${esc(money(D.total))} em ${esc(plural(n, "item", "itens"))}">
            <div class="tag-body">
              <p class="tag-label">${deprecOn() ? "Patrimônio hoje" : "Patrimônio"}</p>
              <p class="tag-value"><span class="cur">R$</span>${numTxt(Math.round(D.total))}</p>
              <p class="tag-sub">${plural(D.houseCount, "item", "itens")} em ${plural(D.rooms.length, "cômodo", "cômodos")}${D.bensItems.length ? ` e ${plural(D.bensItems.length, "bem", "bens")}` : ""}</p>
            </div>
          </div>
        </div>
      </div>
      <div class="hero-side">
      <form class="homesearch" data-form="homesearch" role="search">
        ${ic("search")}<input class="input" type="search" name="q" data-input="home-q" placeholder="Buscar entre ${esc(plural(n, "item", "itens"))}" aria-label="Buscar itens" autocomplete="off" enterkeyhint="search"><kbd>/</kbd>
      </form>
      <dl class="facts">
        ${top ? `<div><dt>${secIc("gem")}Mais valioso</dt><dd><a href="#/i/${encodeURIComponent(top.id)}">${esc(top.name)}</a></dd><dd class="fv">${money(vl(top))}</dd></div>` : ""}
        ${bigRoom ? `<div><dt>${secIc("pie")}Maior cômodo</dt><dd><a href="#/c/${encodeURIComponent(bigRoom.id)}">${esc(bigRoom.name)}</a></dd><dd class="fv">${pctFmt(pct(maxRoom, D.houseTotal))}</dd></div>` : ""}
        ${last ? `<div><dt>${secIc("clock")}Último cadastro</dt><dd><a href="#/i/${encodeURIComponent(last.id)}">${esc(last.name)}</a></dd><dd class="fv muted">${esc(ago(last.createdAt))}</dd></div>` : ""}
        <div><dt>${secIc("images")}Fotos</dt><dd>${plural(D.photoCount, "foto guardada", "fotos guardadas")}</dd><dd class="fv"></dd></div>
      </dl>
      </div>
    </section>
    <section class="sec">
      <div class="sec-h"><h2>${secIc("rooms")}Cômodos</h2><button type="button" class="btn ghost sm" data-act="room-new">${ic("plus", "sm")}Novo cômodo</button></div>
      <ul class="rows">${D.rooms.map((r) => roomRow(r, maxRoom)).join("")}</ul>
    </section>
    ${D.bensItems.length ? `<section class="sec" id="home-bens">
      <div class="sec-h"><h2>${secIc("home")}Bens</h2><a class="aside" href="#/bens">Ver todos</a></div>
      <ul class="ilist">${[...D.bensItems].sort((a, b) => vl(b) - vl(a)).slice(0, 5).map((it) => itemRow(it, { mode: "bens" })).join("")}</ul>
    </section>` : ""}
    <section class="sec">
      <div class="sec-h"><h2>${secIc("clock")}Cadastrados recentemente</h2><a class="aside" href="#/buscar?ord=new">Ver todos</a></div>
      <ul class="ilist">${recent.map((it) => itemRow(it)).join("")}</ul>
    </section>`;
  }
  const emptyMark = () => '<svg class="empty-mark" viewBox="0 0 74 50" aria-hidden="true"><path d="M18 2h52a2 2 0 0 1 2 2v42a2 2 0 0 1-2 2H18L2 33V17z" fill="none" stroke="currentColor" stroke-width="2.5"/><circle cx="17" cy="25" r="5" fill="none" stroke="currentColor" stroke-width="2.5"/></svg>';

  // -- cômodo
  function viewRoom(id) {
    const r = D.roomById.get(id);
    if (!r) return `<div class="empty">${emptyMark()}<h2>Cômodo não encontrado</h2><p>Ele pode ter sido apagado ou renomeado.</p><div class="acts"><a class="btn" href="#/comodos">Ver os cômodos</a></div></div>`;
    const list = D.byRoom.get(id) || [];
    const total = D.roomTotals.get(id) || 0;
    const photos = r.photos || [];
    const zones = new Set(list.map((i) => i.zone || "Sem zona"));
    return `
    <section class="rhead">
      <div class="rhead-top">
        <div class="rhead-name"><span class="mt lg">${esc(r.code)}</span><h1>${esc(r.name)}</h1>
          <div class="stats"><span><b>${int(list.length)}</b> ${list.length === 1 ? "item" : "itens"}</span>${zonesOn() ? `<span><b>${int(zones.size)}</b> ${zones.size === 1 ? "zona" : "zonas"}</span>` : ""}<span><b>${int(photos.length)}</b> ${photos.length === 1 ? "foto" : "fotos"}</span></div>
        </div>
        <div class="rhead-val"><div class="big">${moneyR(total)}</div><div class="small">${pctFmt(pct(total, D.houseTotal))} ${D.bensItems.length ? "da casa" : "do patrimônio"}</div></div>
      </div>
      <div class="rhead-actions">
        <button type="button" class="btn primary" data-act="item-new" data-room="${esc(id)}" aria-label="Adicionar item">${ic("plus")}<span>Adicionar<span class="lbl-x"> item</span></span></button>
        ${aiOn() ? `<button type="button" class="btn" data-act="catalog" data-room="${esc(id)}" aria-label="Catalogar itens com IA">${ic("scan")}<span class="lbl">Catalogar itens com IA</span><span class="lbl-short">Catalogar</span></button>` : ""}
        <button type="button" class="btn ghost" data-act="room-edit" data-room="${esc(id)}" aria-label="Editar cômodo">${ic("edit")}<span class="lbl">Editar cômodo</span></button>
      </div>
    </section>
    <div class="strip" role="list" aria-label="Fotos do cômodo">
      ${photos.map((p, i) => {
        const n = (D.photoItems.get(p.file) || []).length;
        return `<div class="phi" role="listitem" aria-label="${esc(p.label || `Foto ${i + 1}`)}"><button type="button" class="ph" data-act="viewer-room" data-room="${esc(id)}" data-i="${i}" aria-label="${esc(p.label || `Foto ${i + 1}`)}">
          <img src="${esc(src(p.file))}" alt="" loading="lazy" decoding="async">${n ? `<span class="cnt">${plural(n, "item", "itens")}</span>` : ""}</button></div>`;
      }).join("")}
      <div class="phi" role="listitem"><button type="button" class="ph add" data-act="room-photo-add" data-room="${esc(id)}">${ic("plus")}Foto do cômodo</button></div>
    </div>
    ${list.length > 6 ? `<div class="filterbar"><label class="search">${ic("search")}<span class="sr">Filtrar itens deste cômodo</span>
      <input class="input" type="search" data-input="room-filter" data-room="${esc(id)}" placeholder="Filtrar neste cômodo" value="${esc(roomFilter[id] || "")}" autocomplete="off"></label></div>` : ""}
    <div id="zones">${zonesHtml(id)}</div>`;
  }
  function zonesHtml(id) {
    const all = D.byRoom.get(id) || [];
    if (!all.length) {
      return `<div class="empty">${emptyMark()}<h2>Nenhum item aqui ainda</h2>
        <div class="acts"><button class="btn primary" data-act="item-new" data-room="${esc(id)}">${ic("plus")}Adicionar item</button>
        ${aiOn() ? `<button class="btn" data-act="catalog" data-room="${esc(id)}">${ic("scan")}Catalogar itens com IA</button>` : ""}</div></div>`;
    }
    const toks = tokens(roomFilter[id] || "");
    const list = toks.length ? all.filter((it) => matches(it, toks)) : all;
    if (!list.length) return `<div class="empty"><h2>Nada com “${esc(roomFilter[id])}”</h2></div>`;
    if (!zonesOn()) return `<section class="zone"><ul class="ilist">${list.map((it) => itemRow(it, { toks, mode: "room" })).join("")}</ul></section>`;
    const groups = new Map();
    for (const it of list) {
      const z = it.zone || "Sem zona";
      if (!groups.has(z)) groups.set(z, []);
      groups.get(z).push(it);
    }
    const ordered = [...groups.entries()].sort((a, b) => Math.min(...a[1].map((i) => i.seq || 0)) - Math.min(...b[1].map((i) => i.seq || 0)));
    return ordered.map(([z, its]) => `<section class="zone">
      <div class="zone-h"><h3>${hl(z, toks)}</h3><span class="zs">${plural(its.length, "item", "itens")}<b>${moneyR(its.reduce((s, i) => s + vl(i), 0))}</b></span></div>
      <ul class="ilist">${its.map((it) => itemRow(it, { toks, mode: "room" })).join("")}</ul></section>`).join("");
  }
  // -- Bens (Mais > Bens): Imóveis, Veículos e Outros, cada grupo com o total
  function viewBens() { // com bens, adicionar é o + de baixo (ou o Adicionar do alto, no computador): sem botão repetido
    const rid = D.bens ? D.bens.id : BENS_NEW;
    const add = `<button type="button" class="btn primary" data-act="item-new" data-room="${esc(rid)}">${ic("plus")}Adicionar bem</button>`;
    if (!D.bensItems.length) {
      return `<div class="mscreen"><div class="empty">${emptyMark()}<h2>Nenhum bem ainda</h2>
        <p>Casa, apartamento, terreno, carro, moto: o que tem valor e fica fora de casa.</p><div class="acts">${add}</div></div></div>`;
    }
    const groups = BENS_GROUPS.map(([k, name]) => [name, D.bensItems.filter((it) => bensGroup(it) === k).sort((a, b) => vl(b) - vl(a))])
      .filter(([, its]) => its.length);
    return `<div class="mscreen bens">
      ${groups.map(([name, its]) => `<section class="zone">
        <div class="zone-h"><h3>${esc(name)}</h3><span class="zs">${plural(its.length, "bem", "bens")}<b>${moneyR(its.reduce((t, i) => t + vl(i), 0))}</b></span></div>
        <ul class="ilist">${its.map((it) => itemRow(it, { mode: name === "Outros" ? "bens" : "room" })).join("")}</ul></section>`).join("")}
    </div>`;
  }
  function matches(it, toks) {
    const room = D.roomById.get(it.room);
    const hay = norm(`${it.name} ${it.details} ${zonesOn() ? it.zone : ""} ${room?.name || ""} ${tagOf(it)} ${CAT[it.cat] || ""}`);
    return toks.every((t) => hay.includes(t));
  }

  // -- busca
  // o tipo, na busca (só quando há bens): os itens da casa ou um grupo de Mais > Bens; num tipo de bem, sem cômodo e categoria
  const TIPOS = [["", "Todos os tipos"], ["casa", "Itens da casa"], ["imoveis", "Imóveis"], ["veiculos", "Veículos"], ["outros", "Outros bens"]];
  const tipoBens = (t) => t === "imoveis" || t === "veiculos" || t === "outros";
  function viewSearch(q) {
    const ord = q.ord || (q.q ? "rel" : "val");
    const tipo = D.bensItems.length && TIPOS.some(([k]) => k === q.tipo) ? q.tipo || "" : "", house = !tipoBens(tipo);
    const n = (D.bensItems.length ? 1 : 0) + (house ? 2 : 0) + 1;
    return `
    <section class="sbar">
      <form class="q" data-form="search" role="search">${ic("search")}
        <input class="input" type="search" name="q" data-input="search-q" value="${esc(q.q || "")}" placeholder="${zonesOn() ? "Nome, marca, detalhe ou zona" : "Nome, marca ou detalhe"}" aria-label="Buscar itens" autocomplete="off" enterkeyhint="search">
        <button type="button" class="btn ghost icon sm clear" data-act="search-clear" aria-label="Limpar busca"${q.q ? "" : " hidden"}>${ic("close", "sm")}</button>
      </form>
      <div class="sfilters n${n}">
        ${D.bensItems.length ? `<select class="select" data-input="search-tipo" aria-label="Tipo">
          ${TIPOS.map(([k, v]) => `<option value="${k}"${k === tipo ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>` : ""}
        ${house ? `<select class="select" data-input="search-room" aria-label="Cômodo"><option value="">Todos os cômodos</option>
          ${D.rooms.map((r) => `<option value="${esc(r.id)}"${r.id === q.room ? " selected" : ""}>${esc(r.name)}</option>`).join("")}</select>
        <select class="select" data-input="search-cat" aria-label="Categoria"><option value="">Todas as categorias</option>
          ${CATS.map(([k, v]) => `<option value="${k}"${k === q.cat ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>` : ""}
        <select class="select ord" data-input="search-ord" aria-label="Ordenar">
          ${ORDERS.map(([k, v]) => `<option value="${k}"${k === ord ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
      </div>
    </section>
    <div id="results">${resultsHtml(q)}</div>`;
  }
  function searchItems(q) {
    const toks = tokens(q.q || "");
    let list = D.items;
    const tipo = D.bensItems.length ? q.tipo : "";
    if (tipo === "casa") list = list.filter((i) => !isBens(i.room));
    else if (tipoBens(tipo)) list = list.filter((i) => isBens(i.room) && (bensGroup(i) || "outros") === tipo);
    if (!tipoBens(tipo)) {
      if (q.room && D.rooms.some((r) => r.id === q.room)) list = list.filter((i) => i.room === q.room); // cômodo de um link antigo: vale Todos, como diz a seleção
      if (q.cat && CAT[q.cat]) list = list.filter((i) => (CAT[i.cat] ? i.cat : "outros") === q.cat);
    }
    if (toks.length) list = list.filter((i) => matches(i, toks));
    const ord = q.ord || (toks.length ? "rel" : "val");
    const score = (it) => {
      const n = norm(it.name);
      let s = 0;
      for (const t of toks) { if (n.startsWith(t) || n.includes(" " + t)) s += 3; else if (n.includes(t)) s += 2; else s += 0.5; }
      return s;
    };
    const cmp = {
      rel: (a, b) => score(b) - score(a) || vl(b) - vl(a),
      val: (a, b) => vl(b) - vl(a),
      valasc: (a, b) => vl(a) - vl(b),
      az: (a, b) => a.name.localeCompare(b.name, "pt-BR"),
      new: (a, b) => parseDate(b.createdAt) - parseDate(a.createdAt),
      code: (a, b) => (D.roomById.get(a.room)?.order ?? 99) - (D.roomById.get(b.room)?.order ?? 99) || (a.seq || 0) - (b.seq || 0),
    }[ord] || ((a, b) => vl(b) - vl(a));
    return { list: [...list].sort(cmp), toks };
  }
  function resultsHtml(q) {
    const { list, toks } = searchItems(q);
    const sum = list.reduce((s, i) => s + vl(i), 0);
    if (!list.length) {
      const filtered = q.room || q.cat;
      return `<div class="empty">${emptyMark()}<h2>${q.q ? `Nada encontrado para “${esc(q.q)}”` : "Nenhum item com esses filtros"}</h2>
        <p>${filtered ? "Tente limpar os filtros de cômodo e categoria." : "Tente outra palavra, como a marca ou o tipo do objeto."}</p>
        ${filtered ? `<div class="acts"><button class="btn" data-act="search-reset">Limpar filtros</button></div>` : ""}</div>`;
    }
    const shown = list.slice(0, searchLimit);
    const pickable = list.filter((i) => !isBens(i.room)); // os bens não têm cômodo nem categoria: ficam de fora
    if (SEL) { const ok = new Set(pickable.map((i) => i.id)); for (const id of [...SEL]) if (!ok.has(id)) SEL.delete(id); } // só o que está na lista
    const more = list.length > shown.length ? `<div class="more"><button class="btn" data-act="more-results">Mostrar mais ${int(Math.min(120, list.length - shown.length))}</button></div>` : "";
    if (!SEL) {
      return `<div class="ssum"><span>${plural(list.length, "item", "itens")}</span>${pickable.length ? `<button type="button" class="btn ghost sm sel-go" data-act="sel-start">${ic("checks", "sm")}Selecionar</button>` : ""}<b>${moneyR(sum)}</b></div>
      <ul class="ilist">${shown.map((it) => itemRow(it, { toks })).join("")}</ul>${more}`;
    }
    const n = SEL.size, all = n > 0 && n === pickable.length;
    const selSum = pickable.reduce((s, i) => s + (SEL.has(i.id) ? vl(i) : 0), 0);
    return `<div class="ssum sel"><button type="button" class="btn ghost icon sm" data-act="sel-end" aria-label="Cancelar seleção">${ic("close")}</button>
        <span class="sel-n">${n ? plural(n, "selecionado", "selecionados") : "Selecionar"}</span>${n ? `<b>${moneyR(selSum)}</b>` : ""}
        <button type="button" class="btn ghost sm" data-act="sel-all">${all ? "Nenhum" : "Todos"}</button></div>
      <ul class="ilist">${shown.map((it) => itemRow(it, { toks, pick: isBens(it.room) ? "off" : SEL.has(it.id) })).join("")}</ul>${more}
      <div class="selbar"><button type="button" class="btn primary" data-act="sel-change"${n ? "" : " disabled"}>${ic("edit")}${n ? `Alterar ${plural(n, "item", "itens")}` : "Alterar"}</button></div>`;
  }
  // Buscar › Selecionar: marcar vários itens e alterar de uma vez o cômodo, a categoria e a zona (com Desfazer), como no
  // ResolvIA. A seleção vale só para o que está na lista (mudou o filtro, sai o que sumiu); o Voltar do celular sai.
  let SEL = null;
  function selRender() {
    const el = $("#results");
    if (el && base.name === "search") el.innerHTML = resultsHtml(base.q);
  }
  function selStart(first = null) {
    SEL = new Set(first ? [first] : []);
    try { history.pushState({ ...(history.state || {}), invSel: 1 }, ""); } catch { /* sem histórico */ }
    selRender();
  }
  // segurar o dedo num item do Buscar começa o Selecionar com ele marcado, como no ResolvIA (no celular, segurar é o
  // contextmenu; o menu do link não abre)
  document.addEventListener("contextmenu", (e) => {
    if (base.name !== "search") return;
    const row = e.target.closest && e.target.closest("#results .irow");
    if (!row) return;
    const id = row.dataset.id || decodeURIComponent((row.getAttribute("href") || "").split("/").pop());
    const it = D.itemById.get(id);
    if (!it || isBens(it.room)) return;
    e.preventDefault();
    try { navigator.vibrate && navigator.vibrate(12); } catch { /* sem vibração */ }
    if (!SEL) selStart(id); // já selecionando, o toque marca e desmarca
  });
  function selEnd() {
    if (history.state && history.state.invSel) { history.back(); return; } // o popstate abaixo sai
    SEL = null; selRender();
  }
  window.addEventListener("popstate", () => { if (SEL && !(history.state && history.state.invSel) && !stack.length) { SEL = null; selRender(); } });
  // Alterar N itens: cada campo começa em Manter (nada muda até escolher outra coisa), como no ResolvIA; dá para mudar o
  // cômodo, a categoria e a zona juntos. Em outro cômodo, o item ganha um código novo e fica sem zona (ou na zona escolhida).
  const KEEP = "__manter__", OTHER = "__outra__";
  function selEdit() {
    const its = [...SEL].map((id) => D.itemById.get(id)).filter((i) => i && !isBens(i.room));
    if (!its.length) return;
    const n = plural(its.length, "item", "itens"), zOn = zonesOn();
    const chip = (name, value, label, on = false) => `<label class="chip"><input type="radio" name="${name}" value="${esc(value)}"${on ? " checked" : ""}>${label}</label>`;
    const zoneChips = (rid) => {
      const zl = (rid ? zonesOf(rid) : [...new Set(its.flatMap((i) => zonesOf(i.room)))]).sort((a, b) => a.localeCompare(b, "pt-BR"));
      return chip("bk-zone", KEEP, "Manter", true) + chip("bk-zone", "", "Sem zona") + zl.map((z) => chip("bk-zone", z, esc(z))).join("") + chip("bk-zone", OTHER, "Outra");
    };
    const entry = openDialog({
      cls: "modal narrow", label: `Alterar ${n}`,
      html: `<div class="dlg"><div class="dlg-h"><h2>Alterar ${n}</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b" data-bk><div class="form">
          <div class="field" data-f="room"><span class="lbl" id="bk-l-room">Cômodo</span>
            <div class="chips" role="radiogroup" aria-labelledby="bk-l-room">${chip("bk-room", KEEP, "Manter", true)}${D.rooms.map((r) => chip("bk-room", r.id, esc(r.name))).join("")}</div>
            <p class="help" id="bk-help" hidden>Em outro cômodo, o item ganha um código novo${zOn ? " e fica sem zona, se não escolher uma" : ""}.</p></div>
          <div class="field" data-f="cat"><span class="lbl" id="bk-l-cat">Categoria</span>
            <div class="chips" role="radiogroup" aria-labelledby="bk-l-cat">${chip("bk-cat", KEEP, "Manter", true)}${CATS.map(([k, v]) => chip("bk-cat", k, esc(v))).join("")}</div></div>
          ${zOn ? `<div class="field" data-f="zone"><span class="lbl" id="bk-l-zone">Zona</span>
            <div class="chips" id="bk-zones" role="radiogroup" aria-labelledby="bk-l-zone">${zoneChips("")}</div>
            <input id="bk-zone-new" class="input" placeholder="Nome da zona" maxlength="120" autocomplete="off" aria-label="Nome da zona" hidden></div>` : ""}
        </div></form>
        <div class="dlg-f"><span class="grow"></span><button class="btn ghost" data-x>Cancelar</button><button class="btn primary" data-ok disabled>Aplicar</button></div></div>`,
    });
    const dlg = entry.dlg;
    const val = (name) => { const r = $(`input[name="${name}"]:checked`, dlg); return r ? r.value : KEEP; };
    const zoneOf = () => { const z = zOn ? val("bk-zone") : KEEP; return z === OTHER ? $("#bk-zone-new", dlg).value.trim() : z; };
    const sync = () => {
      const room = val("bk-room"), z = zOn ? val("bk-zone") : KEEP;
      $("#bk-help", dlg).hidden = room === KEEP;
      if (zOn) $("#bk-zone-new", dlg).hidden = z !== OTHER;
      $("[data-ok]", dlg).disabled = (room === KEEP && val("bk-cat") === KEEP && z === KEEP) || (z === OTHER && !zoneOf());
    };
    dlg.addEventListener("change", (e) => {
      if (zOn && e.target.name === "bk-room") $("#bk-zones", dlg).innerHTML = zoneChips(e.target.value === KEEP ? "" : e.target.value); // as zonas do cômodo novo
      if (e.target.value === OTHER) setTimeout(() => $("#bk-zone-new", dlg).focus(), 0);
      sync();
    });
    dlg.addEventListener("input", sync);
    let busy = false;
    const go = async () => {
      if (busy || $("[data-ok]", dlg).disabled) return;
      busy = true;
      try {
        const room = val("bk-room"), cat = val("bk-cat"), zone = zoneOf();
        const todo = [];
        for (const i of its) {
          const c = {};
          if (room !== KEEP && room !== i.room) { c.room = room; c.zone = zone !== KEEP ? zone : ""; }
          else if (zone !== KEEP && zone !== (i.zone || "")) c.zone = zone;
          if (cat !== KEEP && cat !== i.cat) c.cat = cat;
          if (Object.keys(c).length) todo.push({ id: i.id, ...c });
        }
        if (!todo.length) { requestClose(entry, { force: true }); toast("Nada mudou."); return; }
        const before = todo.map((t) => { const i = D.itemById.get(t.id); return { id: i.id, room: i.room, seq: i.seq, zone: i.zone || "", cat: i.cat }; });
        const res = await API.post("api/items/bulk", { items: todo });
        setRev(res.rev); res.items.forEach(upsertItem); derive(); requestClose(entry, { force: true }); refreshAll();
        toast(plural(res.items.length, "item alterado", "itens alterados"), { action: "Desfazer", onAction: async () => {
          try { const back = await API.post("api/items/bulk", { items: before }); setRev(back.rev); back.items.forEach(upsertItem); derive(); refreshAll(); }
          catch (er) { fail(er); }
        } });
      } catch (e) { fail(e); }
      finally { busy = false; }
    };
    $("[data-bk]", dlg).addEventListener("submit", (e) => { e.preventDefault(); go(); });
    dlg.addEventListener("click", (e) => { if (e.target.closest("[data-x]")) requestClose(entry, { force: true }); if (e.target.closest("[data-ok]")) go(); });
  }

  function updateSearch(patch) {
    base.q = { ...base.q, ...patch };
    if (!base.q.q && base.q.ord === "rel") delete base.q.ord;
    try { history.replaceState(history.state, "", hashOf(base)); } catch { /* sem histórico */ }
    rendered = hashOf(base);
    searchLimit = 120;
    selRender();
    const ordSel = $('#view [data-input="search-ord"]');
    if (ordSel) ordSel.value = base.q.ord || (base.q.q ? "rel" : "val"); // digitar passa para Mais relevantes: a seleção diz o mesmo
    const clear = $('#view [data-act="search-clear"]');
    if (clear) clear.hidden = !base.q.q;
  }

  // -- relatório: o padrão dos relatórios dos apps (o do ResolvIA e do GerencIA): o cabeçalho (a faixa na cor do app, o
  // ícone, o app, o título, a contagem e quando), os números, os gráficos da tela Gráficos, um cômodo depois do outro e, no
  // fim, a marca da CorrerIA Code (como no Mais > Sobre). Baixar PDF: o servidor faz o mesmo relatório como arquivo (o
  // app do Home Assistant no Android não imprime a página).
  const RAIO = "M13 2L3 14L12 14L11 22L21 10L12 10Z";
  const MARCA = `<footer class="marca"><span class="raio" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="${RAIO}"/></svg></span><span><b class="nome">Correr<i>IA</i> Code</b><small>desenvolvimento de softwares</small></span></footer>`;
  function reportPdfHref(withPhotos) {
    const cs = getComputedStyle(document.documentElement);
    const hex = (v) => (/^#[0-9a-f]{6}$/i.test((v || "").trim()) ? v.trim() : "");
    const q = new URLSearchParams({ fotos: withPhotos ? "1" : "0" });
    if (hex(cs.getPropertyValue("--a"))) q.set("cor", hex(cs.getPropertyValue("--a")));
    if (hex(cs.getPropertyValue("--a-text"))) q.set("tinta", hex(cs.getPropertyValue("--a-text")));
    return `api/relatorio.pdf?${q}`;
  }
  function viewReport() {
    const withPhotos = LS.get("reportPhotos", true);
    const nb = D.bensItems.length > 0; // os bens (fora de casa) vêm numa seção à parte, com o total deles
    const now = new Date();
    const p2 = (n) => String(n).padStart(2, "0");
    const when = `${p2(now.getDate())}/${p2(now.getMonth() + 1)}/${now.getFullYear()} às ${p2(now.getHours())}:${p2(now.getMinutes())}`;
    const day = `${now.getFullYear()}-${p2(now.getMonth() + 1)}-${p2(now.getDate())}`;
    // os gráficos da tela Gráficos: cômodos, categorias, faixas de valor, os mais valiosos e os bens
    const c = D.items.length ? chartData() : null, T = D.houseTotal;
    const bmax = c ? Math.max(...c.bands.map((b) => b.n), 1) : 1;
    const graf = (id, icon, title, body) => `<section class="rep-g" id="rg-${id}"><h2>${secIc(icon)}${title}</h2>${body}</section>`;
    const charts = c ? [
      c.rooms.length && graf("rooms", "rooms", "Cômodos", hbars(c.rooms.map((x) => ({ href: `#/c/${encodeURIComponent(x.r.id)}`, tag: `<span class="mt soft">${esc(x.r.code)}</span>`, name: x.r.name, sub: plural(x.n, "item", "itens"), v: x.v, share: pctTxt(x.v, T) })))),
      c.cats.length && graf("cats", "grid", "Categorias", hbars(c.cats.map((x) => ({ href: `#/buscar?cat=${encodeURIComponent(x.k)}&ord=val`, name: x.name, sub: plural(x.n, "item", "itens"), v: x.v, share: pctTxt(x.v, T) })))),
      c.valued.length && graf("bands", "bars", "Faixas de valor", `<div class="bands" role="list" aria-label="Itens por faixa de valor, em reais">
        ${c.bands.map((b) => `<div class="band" role="listitem" aria-label="${esc(`${b.label} reais: ${plural(b.n, "item", "itens")}, ${moneyR(b.v)} no total`)}">
          <span class="bd-bar"><span class="bd-n">${int(b.n)}</span><i style="height:${b.n ? Math.max(3, (b.n / bmax) * 100).toFixed(1) : 0}%"></i></span>
          <span class="bd-l">${esc(b.label)}</span><span class="bd-v">${b.n ? moneyK(b.v) : "–"}</span></div>`).join("")}</div>
        ${c.items.length - c.valued.length ? `<p class="muted bands-cap">${plural(c.items.length - c.valued.length, "item está", "itens estão")} sem valor.</p>` : ""}`),
      c.valued.length && graf("top", "gem", "Itens mais valiosos", hbars(c.valued.slice(0, 10).map((i) => ({ href: `#/i/${encodeURIComponent(i.id)}`, name: i.name, sub: D.roomById.get(i.room)?.name || "", v: vl(i), share: pctTxt(vl(i), T) })))),
      nb && graf("bens", "home", "Bens", hbars(c.bens.slice(0, 10).map((i) => ({ href: `#/i/${encodeURIComponent(i.id)}`, name: i.name, sub: { imoveis: "Imóvel", veiculos: "Veículo" }[i.cat] || CAT[i.cat] || "Outro", v: vl(i), share: pctTxt(vl(i), D.bensTotal) })))),
    ].filter(Boolean) : [];
    return `
    <div class="rep-tools no-print">
      <label class="btn rep-fotos"><input type="checkbox" role="switch" data-input="rep-photos"${withPhotos ? " checked" : ""}><span>Mostrar fotos</span></label>
      <a class="btn primary" data-act="rep-pdf" href="${esc(reportPdfHref(withPhotos))}" download="inventario-${day}.pdf">${ic("download")}Baixar PDF</a>
    </div>
    <article class="report">
      <header class="rcab">${APP_ICON}<div><div class="rapp"><span class="wm">Inventar<b>IA</b></span> · inventário da casa</div>
        <h1>Relatório do inventário</h1><p class="rmeta">${plural(D.houseCount, "item", "itens")} em ${plural(D.rooms.length, "cômodo", "cômodos")}${deprecOn() ? " · valor de hoje" : ""} · ${when}</p></div></header>
      <div class="rtotal">
        <div><span>${nb ? "Na casa" : "Patrimônio"}</span><b>${moneyR(D.houseTotal)}</b></div>
        <div><span>Itens</span><b>${int(D.houseCount)}</b></div>
        <div><span>Cômodos</span><b>${int(D.rooms.length)}</b></div>
        ${nb ? `<div><span>Bens</span><b>${moneyR(D.bensTotal)}</b></div>` : ""}
      </div>
      ${charts.length ? `<div class="rep-graf">${charts.join("")}</div>` : ""}
      ${[...D.rooms, ...(nb ? [D.bens] : [])].filter((r) => (D.byRoom.get(r.id) || []).length).map((r) => {
        const its = D.byRoom.get(r.id) || [];
        const bens = r === D.bens, zc = zonesOn() && !bens;
        return `<section class="rep-room${bens ? " rep-bens" : ""}"><h2><span class="mt">${esc(r.code)}</span>${esc(r.name)}</h2>
          <p class="rs">${bens ? `${plural(its.length, "bem", "bens")} fora de casa` : plural(its.length, "item", "itens")}, ${money(D.roomTotals.get(r.id) || 0)}</p>
          <table class="rtable"><thead><tr>${withPhotos ? '<th class="t"><span class="sr">Foto</span></th>' : ""}<th>Código</th><th>Item</th>${zc ? "<th>Zona</th>" : ""}<th class="r">Qtd.</th><th class="r">Valor</th></tr></thead><tbody>
          ${its.map((it) => `<tr>${withPhotos ? `<td class="t">${it.photos && it.photos[0] ? `<img src="${esc(src(it.photos[0]))}" alt="" width="44" height="44">` : ""}</td>` : ""}
            <td class="c">${esc(tagOf(it))}</td><td>${esc(it.name)}${it.details ? `<span class="d">${esc(snippet(it.details, 140))}</span>` : ""}${withPhotos && it.photos && it.photos[0] && (it.photoSrc || {})[it.photos[0]] ? `<span class="d">Foto ilustrativa, de ${esc(siteOf(it.photoSrc[it.photos[0]]))}</span>` : ""}</td>
            ${zc ? `<td>${esc(it.zone || "")}</td>` : ""}<td class="r">${esc(qtyClean(it.qty))}</td><td class="r">${money(vl(it))}</td></tr>`).join("")}
          </tbody><tfoot><tr>${withPhotos ? "<td></td>" : ""}<td colspan="${zc ? 4 : 3}">${bens ? "Total dos bens" : "Subtotal"}</td><td class="r">${money(D.roomTotals.get(r.id) || 0)}</td></tr></tfoot></table></section>`;
      }).join("")}
      ${D.items.length ? "" : `<p class="muted">Nenhum item cadastrado.</p>`}
      ${MARCA}
    </article>`;
  }

  // -- cômodos (aba própria): lista para abrir cada cômodo; em "Organizar", setas e edição
  let roomsOrganize = false;
  function roomThumb(r) {
    const ps = r.photos || [];
    const p = ps.length ? ps[Math.min(Math.max(r.cover || 0, 0), ps.length - 1)] : null;
    return p ? `<img class="thumb" src="${esc(src(p.file))}" alt="" loading="lazy" decoding="async" width="56" height="56">` : `<span class="thumb">${ic("rooms")}</span>`;
  }
  function viewRooms() {
    if (!D.rooms.length) {
      return `<div class="empty">${emptyMark()}<h2>Nenhum cômodo ainda</h2>
        <div class="acts"><button type="button" class="btn primary" data-act="room-new">${ic("plus")}Novo cômodo</button></div></div>`;
    }
    const org = roomsOrganize, last = D.rooms.length - 1;
    const rows = D.rooms.map((r, i) => {
      const n = (D.byRoom.get(r.id) || []).length, nph = (r.photos || []).length;
      const id = esc(r.id), name = esc(r.name);
      const body = `<span class="ib"><span class="nm">${name}</span><span class="meta"><span class="mt soft">${esc(r.code)}</span>${org ? "" : `<span class="rc">${plural(n, "item", "itens")}, ${plural(nph, "foto", "fotos")}</span>`}</span></span>`;
      if (!org) {
        return `<li><a class="irow croom" href="#/c/${encodeURIComponent(r.id)}" data-room-row="${id}">${roomThumb(r)}${body}
          <span class="iv"><span class="val">${moneyR(D.roomTotals.get(r.id) || 0)}</span></span></a></li>`;
      }
      return `<li><div class="irow croom org" data-room-row="${id}">${roomThumb(r)}${body}<span class="ra">
        <button type="button" class="btn sm icon" data-act="room-up" data-room="${id}" aria-label="Subir ${name}"${i === 0 ? " disabled" : ""}>${ic("up", "sm")}</button>
        <button type="button" class="btn sm icon" data-act="room-down" data-room="${id}" aria-label="Descer ${name}"${i === last ? " disabled" : ""}>${ic("down", "sm")}</button>
        <button type="button" class="btn sm icon" data-act="room-edit" data-room="${id}" aria-label="Editar ${name}">${ic("edit", "sm")}</button></span></div></li>`;
    }).join("");
    return `
    <div class="rooms-bar">
      <button type="button" class="btn primary" data-act="room-new">${ic("plus")}Novo cômodo</button>
      <button type="button" class="btn${org ? " dark" : ""}" data-act="rooms-organize">${ic(org ? "check" : "sort")}${org ? "Concluir" : "Organizar"}</button>
    </div>
    ${org ? `<p class="rooms-hint">A ordem vale também para o relatório.</p>` : ""}
    <ul class="ilist rooms">${rows}</ul>`;
  }

  // -- dados e ajustes
  const SW_TAG = "M8 0h20a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H8L0 13V7z";
  const SWATCH = `<svg viewBox="-5 -5 40 30" aria-hidden="true"><path class="sw-ring" d="${SW_TAG}"/><path class="sw-gap" d="${SW_TAG}"/><path class="sw-fill" d="${SW_TAG}M9.7 10a2.7 2.7 0 1 0-5.4 0a2.7 2.7 0 1 0 5.4 0z"/><path class="sw-check" d="m14.6 10.3 3.2 3.2 6.5-6.9"/></svg>`;
  // -- Mais: um menu com o que não cabe na barra (Novidades, Relatório), Configurações e, por último, Sobre
  function viewMenu() {
    const rows = [
      bensOn() && ["#/bens", "home", "Bens", "Casa, terreno, carro: o que fica fora de casa."],
      ["#/graficos", "bars", "Gráficos", "Cômodos, categorias e itens que mais valem."],
      newsOn() && ["#/novidades", "spark", "Novidades", "Atualizações, lançamentos e recalls dos eletrônicos."],
      ["#/categorias", "grid", "Categorias", "Criar, renomear e apagar."],
      ["#/relatorio", "report", "Relatório do inventário", `Por cômodo, com ${LS.get("reportPhotos", true) ? "fotos e " : ""}gráficos. Baixa em PDF.`], // sem Mostrar fotos, não promete fotos
      ["#/config", "gear", "Configurações", "Integrações, dados e backup, aparência e opções."],
      ["#/sobre", "info", "Sobre", "CorrerIA Code, os apps e o GitHub."],
    ].filter(Boolean);
    return `<nav aria-label="Mais"><ul class="menu-list">${rows.map(([h, i, t, d]) => `<li><a class="menu-row" href="${h}">${secIc(i)}
        <span class="mb"><b>${t}</b><span>${d}</span></span>${ic("chev", "sm")}</a></li>`).join("")}</ul></nav>
    <p class="foot"><b>InventarIA</b><br>${PREVIEW ? "Prévia do app do Home Assistant: as alterações ficam só nesta tela." : `v${esc(S.version)}, com os dados em arquivos abertos (JSON e JPG) dentro do Home Assistant.`}</p>`;
  }
  // -- Sobre: quem faz o app (CorrerIA Code), os apps da família, cada um com uma linha e o link para o GitHub, e Meu GitHub.
  // A mesma página em todos os apps da família (o about.js do CronologIA): aqui o InventarIA fica marcado, com a versão.
  const GITHUB = "https://github.com/diegozapella63";
  const PRODUCTS = [ // [nome, repositório, ícone, a linha sobre ele], nesta ordem
    ["CronologIA", "cronologia-ha", "calendar", "Agenda da família, remédios, rotinas e placar."],
    ["ResolvIA", "resolvia-ha", "checks", "Listas de tarefas com prazos, pontos e repetição."],
    ["GerencIA", "gerencia-ha", "wallet", "Finanças da casa: caixa, cartões e investimentos."],
    ["InventarIA", "inventario-ha", "package", "Inventário da casa: cômodos, itens e valores."],
    ["EconomIA", "economia-ha", "receipt", "Lista de compras com o melhor preço perto de casa."],
    ["MemorIA", "memoria-ha", "book", "Cadernos de anotação que abrem na hora certa."],
    ["CorrerIA", "correria-ha", "chat", "Pergunte e peça a qualquer app, no chat ou no WhatsApp."],
  ];
  const wordmark = (n) => `<span class="ab-wm">${esc(n.slice(0, -2))}<span>${esc(n.slice(-2))}</span></span>`; // o "IA" na cor do app, sem quebrar o nome
  const outLink = (href, body, cls) => `<a class="${cls}" href="${href}" target="_blank" rel="noopener">${body}</a>`;
  function viewAbout() {
    return `<div class="mscreen about">
    <div class="about-hero">
      <span class="ab-mark" aria-hidden="true">${ic("flash")}</span>
      <h2 class="ab-name">Correr<span>IA</span> Code</h2>
      <p class="ab-what">desenvolvimento de softwares</p>
      <p class="ab-tag">Feito na correria, rodado pela IA.</p>
    </div>
    <section class="panel about-why">
      <h2>${secIc("hourglass")}Por que CorrerIA?</h2>
      <p>Porque eu sou um programador sem tempo: vivo na correria. Então eu uso a IA para rodar tudo isso aqui. Ela escreve, testa e publica; eu dou as ideias e reclamo dos botões tortos.</p>
    </section>
    <section class="panel">
      <h2>${secIc("layers")}Os apps</h2>
      <ul class="about-apps" aria-label="Os apps">${PRODUCTS.map(([n, repo, i, line]) => {
        const here = n === "InventarIA";
        return `<li>${outLink(`${GITHUB}/${repo}`, `${secIc(i)}
          <span class="mb"><b>${wordmark(n)}${here ? `<em class="ab-here">Este app · v${esc(S.version)}</em>` : ""}</b><span>${line}</span></span>${ic("external", "sm")}`,
          `ab-row${here ? " here" : ""}`)}</li>`;
      }).join("")}</ul>
    </section>
    ${outLink(GITHUB, `${ic("external")}Meu GitHub`, "btn primary ab-github")}
    </div>`;
  }
  // -- Gráficos: onde está o valor da casa. Barras de uma cor só (a do app), da maior para a menor, com o valor
  // escrito (o gráfico não depende do toque); faixas de valor em colunas e o patrimônio mês a mês.
  const MES_C = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const moneyK = (v) => { // eixo e colunas: R$ 900, R$ 12 mil, R$ 1,2 mi
    v = Math.round(+v || 0);
    if (v >= 1e6) return `R$ ${nf1.format(v / 1e6)} mi`;
    if (v >= 1e4) return `R$ ${int(Math.round(v / 1000))} mil`;
    if (v >= 1000) return `R$ ${nf1.format(v / 1000)} mil`;
    return `R$ ${int(v)}`;
  };
  const pctTxt = (v, t) => { const p = pct(v, t); return `${p >= 10 || p === 0 ? int(Math.round(p)) : nf1.format(p)}%`; };
  const BANDS = [[0, 100, "até 100"], [100, 500, "100–500"], [500, 1000, "500–1 mil"], [1000, 5000, "1–5 mil"], [5000, Infinity, "5 mil+"]];
  // os gráficos da casa (cômodos, categorias, faixas, mais valiosos) são só dos itens da casa; os bens (fora de casa) têm
  // o gráfico deles. O patrimônio (o número do alto e o mês a mês) soma tudo.
  function chartData() {
    const total = D.houseTotal;
    const house = D.items.filter((i) => !isBens(i.room));
    const rooms = D.rooms.map((r) => ({ r, v: D.roomTotals.get(r.id) || 0, n: (D.byRoom.get(r.id) || []).length })).filter((x) => x.n).sort((a, b) => b.v - a.v || b.n - a.n);
    const ct = new Map();
    for (const i of house) { const k = CAT[i.cat] ? i.cat : "outros", t = ct.get(k) || { value: 0, count: 0 }; t.value += vl(i); t.count++; ct.set(k, t); }
    const cats = [...ct].map(([k, t]) => ({ k, name: CAT[k] || "Outros", v: t.value, n: t.count })).sort((a, b) => b.v - a.v || b.n - a.n);
    const items = [...house].sort((a, b) => vl(b) - vl(a));
    const valued = items.filter((i) => vl(i) > 0);
    const bands = BANDS.map(([lo, hi, label]) => {
      const list = valued.filter((i) => vl(i) >= lo && vl(i) < hi);
      return { label, n: list.length, v: list.reduce((s, i) => s + vl(i), 0) };
    });
    const top10 = items.slice(0, 10).reduce((s, i) => s + vl(i), 0);
    let acc = 0, half = 0; // quantos cômodos somam metade
    for (const x of rooms) { if (acc * 2 >= total) break; acc += x.v; half++; }
    // patrimônio mês a mês, pela data de cadastro, do primeiro mês até hoje
    const ym = (d) => String(d || "").slice(0, 7);
    const months = [...new Set(D.items.map((i) => ym(i.createdAt)).filter(Boolean))].sort();
    let series = [];
    if (months.length >= 2) {
      const now = new Date(), last = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
      const add = new Map();
      for (const i of D.items) { const m = ym(i.createdAt) || months[0]; add.set(m, (add.get(m) || 0) + vl(i)); }
      let [y, mo] = months[0].split("-").map(Number), sum = 0;
      for (let k = 0; k < 120; k++) { // até 10 anos
        const key = `${y}-${String(mo).padStart(2, "0")}`;
        sum += add.get(key) || 0;
        series.push({ key, label: `${MES_C[mo - 1]}/${String(y).slice(2)}`, v: sum, add: add.get(key) || 0 });
        if (key >= last && key >= months[months.length - 1]) break;
        mo++; if (mo > 12) { mo = 1; y++; }
      }
    }
    const bens = [...D.bensItems].sort((a, b) => vl(b) - vl(a));
    const groups = BENS_GROUPS.map(([k, name]) => ({ k, name, v: bens.filter((i) => bensGroup(i) === k).reduce((s, i) => s + vl(i), 0) })).filter((g) => g.v > 0).sort((a, b) => b.v - a.v);
    return { total, rooms, cats, items, valued, bands, top10, half, series, bens, groups, photos: house.filter((i) => (i.photos || []).length).length };
  }
  function hbars(rows) { // barras de uma cor, da maior para a menor; cada linha leva a algum lugar
    const max = Math.max(...rows.map((x) => x.v), 1);
    return `<ul class="hbars">${rows.map((x) => `<li><a class="hbar" href="${x.href}">
        <span class="hb-t">${x.tag || ""}<b>${esc(x.name)}</b><span class="hb-s">${esc(x.sub)}</span></span>
        <span class="hb-v"><b>${moneyR(x.v)}</b><span>${esc(x.share)}</span></span>
        <span class="hb-bar" aria-hidden="true"><i style="width:${Math.max(0.6, (x.v / max) * 100).toFixed(2)}%"></i></span></a></li>`).join("")}</ul>`;
  }
  function viewCharts() {
    if (!D.items.length) return `<div class="empty"><h2>Nada para mostrar ainda</h2><p>Cadastre itens para ver os gráficos.</p><div class="acts"><button class="btn primary" data-act="item-new">${ic("plus")}Adicionar item</button></div></div>`;
    const c = chartData(), T = c.total;
    const stat = (label, value, sub = "") => `<div class="kpi"><span>${label}</span><b>${value}</b>${sub ? `<small>${sub}</small>` : ""}</div>`;
    const bmax = Math.max(...c.bands.map((b) => b.n), 1);
    const zero = c.items.length - c.valued.length;
    const nb = c.bens.length, of = nb ? "do que há em casa" : "do patrimônio";
    const roomRows = c.rooms.map((x) => ({ href: `#/c/${encodeURIComponent(x.r.id)}`, tag: `<span class="mt soft">${esc(x.r.code)}</span>`, name: x.r.name,
      sub: plural(x.n, "item", "itens"), v: x.v, share: pctTxt(x.v, T) }));
    const bensRows = c.bens.slice(0, 10).map((i) => ({ href: `#/i/${encodeURIComponent(i.id)}`, name: i.name, sub: { imoveis: "Imóvel", veiculos: "Veículo" }[i.cat] || CAT[i.cat] || "Outro", v: vl(i), share: pctTxt(vl(i), D.bensTotal) }));
    const catRows = c.cats.map((x) => ({ href: `#/buscar?cat=${encodeURIComponent(x.k)}&ord=val`, name: x.name, sub: plural(x.n, "item", "itens"), v: x.v, share: pctTxt(x.v, T) }));
    const topRows = c.items.slice(0, 10).filter((i) => vl(i) > 0).map((i) => ({ href: `#/i/${encodeURIComponent(i.id)}`, name: i.name, sub: D.roomById.get(i.room)?.name || "", v: vl(i), share: pctTxt(vl(i), T) }));
    const lead = (t) => `<p class="lead">${t}</p>`;
    return `<div class="mscreen charts">
    <div class="kpis">
      ${stat("Patrimônio", moneyR(D.total), nb ? `${moneyR(D.bensTotal)} em bens` : "")}
      ${stat("Itens", int(c.items.length), plural(D.rooms.length, "cômodo", "cômodos"))}
      ${stat("Valor médio", moneyR(c.valued.length ? T / c.valued.length : 0), "por item com valor")}
      ${stat("Com foto", pctTxt(c.photos, c.items.length), `${int(c.photos)} de ${int(c.items.length)}`)}
    </div>
    <div class="chart-pair">
    <section class="panel" id="g-rooms">
      <h2>${secIc("rooms")}Cômodos</h2>
      ${c.rooms.length > 1 ? lead(c.half === 1 ? `${esc(c.rooms[0].r.name)} tem ${pctTxt(c.rooms[0].v, T)} ${of}.` : `${int(c.half)} cômodos somam metade ${of}.`) : ""}
      ${hbars(roomRows)}
    </section>
    <section class="panel" id="g-cats">
      <h2>${secIc("grid")}Categorias</h2>
      ${c.cats.length > 1 ? lead(`${esc(c.cats[0].name)} vale ${pctTxt(c.cats[0].v, T)} do total.`) : ""}
      ${hbars(catRows)}
    </section>
    </div>
    ${nb ? `<section class="panel" id="g-bens">
      <h2>${secIc("home")}Bens</h2>
      ${lead(c.groups.length > 1 ? `${esc(c.groups[0].name)} são ${pctTxt(c.groups[0].v, D.bensTotal)} dos bens.` : `${plural(nb, "bem", "bens")} fora de casa, ${moneyR(D.bensTotal)}.`)}
      ${hbars(bensRows)}
    </section>` : ""}
    <div class="chart-pair">
    <section class="panel" id="g-bands">
      <h2>${secIc("bars")}Faixas de valor</h2>
      ${c.items.length >= 10 ? lead(`Os 10 itens mais caros somam ${pctTxt(c.top10, T)} ${of}.`) : ""}
      <div class="bands" role="list" aria-label="Itens por faixa de valor, em reais">
        ${c.bands.map((b) => `<button type="button" class="band" role="listitem" aria-label="${esc(`${b.label} reais: ${plural(b.n, "item", "itens")}, ${moneyR(b.v)} no total`)}">
          <span class="bd-bar"><span class="bd-n">${int(b.n)}</span><i style="height:${b.n ? Math.max(3, (b.n / bmax) * 100).toFixed(1) : 0}%"></i></span>
          <span class="bd-l">${esc(b.label)}</span><span class="bd-v">${b.n ? moneyK(b.v) : "–"}</span></button>`).join("")}
      </div>
      <p class="muted bands-cap">Quantos itens em cada faixa, em reais, e quanto somam.${zero ? ` ${plural(zero, "item está", "itens estão")} sem valor.` : ""}</p>
    </section>
    <section class="panel" id="g-top">
      <h2>${secIc("gem")}Itens mais valiosos</h2>
      ${hbars(topRows)}
    </section>
    </div>
    ${c.series.length >= 2 ? `<section class="panel" id="g-time">
      <h2>${secIc("history")}Patrimônio mês a mês</h2>
      ${lead(`Pela data de cadastro: ${moneyR(c.series[c.series.length - 1].v)} em ${esc(c.series[c.series.length - 1].label)}.`)}
      <div class="area" data-slot="area" role="img" aria-label="${esc(`Patrimônio cadastrado mês a mês, de ${c.series[0].label} a ${c.series[c.series.length - 1].label}: de ${moneyR(c.series[0].v)} a ${moneyR(c.series[c.series.length - 1].v)}`)}"></div>
      <details class="area-tab"><summary>${ic("chev", "sm")}Ver mês a mês</summary>
        <table><thead><tr><th>Mês</th><th>Cadastrado</th><th>Total</th></tr></thead><tbody>
        ${c.series.map((x) => `<tr><td>${esc(x.label)}</td><td>${moneyR(x.add)}</td><td>${moneyR(x.v)}</td></tr>`).join("")}</tbody></table></details>
    </section>` : ""}
    </div>`;
  }
  // a área do patrimônio: desenhada depois, com a largura de verdade; a linha vertical segue o dedo ou o mouse
  function drawArea() {
    const box = $('#view [data-slot="area"]');
    if (!box) return;
    const series = chartData().series;
    const W = Math.max(240, Math.round(box.clientWidth)), H = 190, L = 62, R = 8, Tp = 14, B = 26;
    const max = Math.max(...series.map((x) => x.v), 1);
    const nice = (() => { const e = 10 ** Math.floor(Math.log10(max)), f = max / e; return (f <= 2 ? 2 : f <= 5 ? 5 : 10) * e; })();
    const x = (i) => L + (i / (series.length - 1)) * (W - L - R), y = (v) => Tp + (1 - v / nice) * (H - Tp - B);
    const pts = series.map((s, i) => [x(i), y(s.v)]);
    const line = pts.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)} ${b.toFixed(1)}`).join("");
    const grid = [0.5, 1].map((f) => `<line class="g" x1="${L}" x2="${W - R}" y1="${y(nice * f).toFixed(1)}" y2="${y(nice * f).toFixed(1)}"/><text class="gt" x="${L - 8}" y="${(y(nice * f) + 4).toFixed(1)}" text-anchor="end">${esc(moneyK(nice * f))}</text>`).join("");
    const every = Math.ceil(series.length / Math.max(2, Math.floor((W - L - R) / 56)));
    const ticks = series.map((s, i) => (i % every === 0 || i === series.length - 1) && !(i !== series.length - 1 && series.length - 1 - i < every / 2)
      ? `<text class="xt" x="${x(i).toFixed(1)}" y="${H - 8}" text-anchor="${i === 0 ? "start" : i === series.length - 1 ? "end" : "middle"}">${esc(s.label)}</text>` : "").join("");
    const [ex, ey] = pts[pts.length - 1];
    box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true">
      ${grid}<line class="base" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/>
      <path class="fill" d="${line}L${(W - R).toFixed(1)} ${y(0)}L${L} ${y(0)}Z"/><path class="ln" d="${line}"/>
      <circle class="end" cx="${ex.toFixed(1)}" cy="${ey.toFixed(1)}" r="4.5"/>${ticks}
      <line class="cross" x1="0" x2="0" y1="${Tp}" y2="${y(0)}" visibility="hidden"/><circle class="dot" r="4.5" visibility="hidden"/></svg>
      <div class="ctip" hidden></div>`;
    const svg = $("svg", box), tip = $(".ctip", box), cross = $(".cross", svg), dot = $(".dot", svg);
    const show = (clientX) => {
      const rx = clientX - svg.getBoundingClientRect().left;
      const i = Math.max(0, Math.min(series.length - 1, Math.round(((rx - L) / (W - L - R)) * (series.length - 1))));
      const [px, py] = pts[i];
      cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("visibility", "visible");
      dot.setAttribute("cx", px); dot.setAttribute("cy", py); dot.setAttribute("visibility", "visible");
      tip.hidden = false;
      tip.replaceChildren();
      const b = document.createElement("b"); b.textContent = moneyR(series[i].v);
      const sp = document.createElement("span"); sp.textContent = `${series[i].label} · +${moneyR(series[i].add)}`;
      tip.append(b, sp);
      tip.style.left = `${Math.max(0, Math.min(W - tip.offsetWidth, px - tip.offsetWidth / 2))}px`;
    };
    const hide = () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); };
    svg.addEventListener("pointermove", (e) => show(e.clientX));
    svg.addEventListener("pointerdown", (e) => show(e.clientX));
    svg.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") hide(); }); // no toque, o valor fica até tocar fora
  }
  let areaTimer = null;
  window.addEventListener("resize", () => { clearTimeout(areaTimer); areaTimer = setTimeout(() => { if (base.name === "charts") drawArea(); }, 150); });
  function viewData() {
    const tab = moreTab(base.tab);
    const label = ALL_TABS.find(([k]) => k === tab)[1];
    const bodies = { dados: () => moreExport() + moreData(), integracoes: moreIntegrations, aparencia: moreLook, opcoes: moreOptions };
    return `<div class="more-anchor" aria-hidden="true"></div>
    <div class="more-tabs" role="tablist" aria-label="Seções de Configurações">
      ${moreTabs().map(([k, l, i]) => `<button type="button" role="tab" id="mt-${k}" aria-controls="mp" aria-selected="${k === tab}" tabindex="${k === tab ? 0 : -1}" data-act="more-tab" data-tab="${k}">${ic(i, "sm")}<span>${l}</span></button>`).join("")}
    </div>
    <div class="more-panel" id="mp" role="tabpanel" aria-labelledby="mt-${tab}" aria-label="${label}">${bodies[tab]()}</div>
    <p class="foot"><b>InventarIA</b><br>${PREVIEW ? "Prévia do app do Home Assistant: as alterações ficam só nesta tela." : `v${esc(S.version)}, com os dados em arquivos abertos (JSON e JPG) dentro do Home Assistant.`}</p>`;
  }
  function moreExport() {
    return `
    <section class="panel" id="p-export">
      <h2>${secIc("download")}Exportar</h2>
      <ul class="opts">
        <li><div class="ot"><b>Planilha (CSV)</b><span>Abre no Excel e no Google Planilhas.</span></div><div class="oa"><button class="btn" data-act="export" data-kind="csv">${ic("download")}Baixar CSV</button></div></li>
        <li><div class="ot"><b>Dados completos (JSON)</b><span>Todos os campos.</span></div><div class="oa"><button class="btn" data-act="export" data-kind="json">${ic("download")}Baixar JSON</button></div></li>
        <li><div class="ot"><b>Tudo com fotos (ZIP)</b><span>JSON, CSV e fotos.</span></div><div class="oa"><button class="btn" data-act="export" data-kind="zip">${ic("download")}Baixar ZIP</button></div></li>
      </ul>
    </section>`;
  }
  // -- novidades de todos os equipamentos: a IA escolhe, nas categorias marcadas, o que faz sentido conferir
  function moreNews() {
    return `
    <section class="panel" id="p-news">
      <p class="lead">Atualizações, lançamentos, modelo novo, recalls e fim de suporte dos eletrônicos.</p>
      <ul class="opts"><li><div class="ot"><b>Conferir todos</b><span>A IA escolhe, entre os eletrônicos, os que vale conferir.</span></div>
        <div class="oa"><button type="button" class="btn primary" data-act="news-all">${ic("spark")}Conferir novidades</button></div></li>
        <li><div class="ot"><b>Limpar</b><span>Apaga as novidades encontradas e as escolhas da IA.</span></div>
        <div class="oa"><button type="button" class="btn" data-act="news-clear">${ic("trash")}Limpar novidades</button></div></li></ul>
      <div data-slot="news-job"></div>
    </section>
    <section class="panel" id="p-news-list">
      <h2>${secIc("tag")}Equipamentos</h2>
      <div data-slot="news-list"><p class="muted">Carregando…</p></div>
    </section>`;
  }
  let newsOv = null, newsJob = null, newsTimer = null;
  async function loadNews() {
    try { newsOv = await API.get("api/news"); }
    catch (e) { const sl = $('#view [data-slot="news-list"]'); if (sl) sl.innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
    renderNews();
    if (newsOv.job && !newsJob) { newsJob = newsOv.job.id; pollNewsAll(); }
  }
  const newsCount = (r) => ((r && r.news && r.news.novidades) || []).length;
  const newsRecall = (r) => ((r && r.news && r.news.novidades) || []).some((x) => x.tipo === "recall");
  // uma linha por equipamento: o mesmo em vários cômodos (ou no plural) fica junto, com o nome mais curto
  function newsRow(g) {
    const { it, r, items, open } = g;
    const rooms = [...new Set(items.map((x) => x.room))];
    const where = rooms.length > 1 ? plural(rooms.length, "cômodo", "cômodos") : (D.roomById.get(rooms[0])?.name || "");
    const n = newsCount(r);
    const st = !r ? "Ainda não conferido" : `${n ? plural(n, "novidade", "novidades") : "Nada novo"} · ${whenShort(r.at)}`;
    return `<li><button type="button" class="nrow" data-act="news-open" data-id="${esc(open.id)}">
        <span class="nb"><b>${esc(it.name)}</b><span class="nm">${esc(where)} · ${esc(st)}</span></span>
        ${newsRecall(r) ? `<span class="pill warn">Recall</span>` : n ? `<span class="pill">${int(n)}</span>` : ""}${ic("chev", "sm")}</button></li>`;
  }
  function newsGroups(list, ov) {
    const res = ov.itens || {}, grp = ov.grupos || {}, by = new Map();
    for (const it of list) {
      const k = grp[it.id] || it.id;
      if (!by.has(k)) by.set(k, []);
      by.get(k).push(it);
    }
    return [...by.values()].map((items) => {
      const it = [...items].sort((a, b) => a.name.length - b.name.length || a.name.localeCompare(b.name, "pt-BR"))[0];
      const r = items.map((x) => res[x.id]).filter(Boolean).sort((a, b) => String(b.at).localeCompare(String(a.at)))[0];
      return { it, r, items, open: items.find((x) => r && res[x.id] === r) || it }; // abre o que tem o resultado mais novo
    });
  }
  function renderNews() {
    const ov = newsOv;
    const ls = $('#view [data-slot="news-list"]');
    if (!ov || !ls) return;
    const res = ov.itens || {}, tri = ov.triagem || {};
    const rank = (g) => (newsRecall(g.r) ? 0 : newsCount(g.r) ? 1 : !g.r ? 2 : 3);
    const sortG = (a, b) => rank(a) - rank(b) || newsCount(b.r) - newsCount(a.r) || a.it.name.localeCompare(b.it.name, "pt-BR");
    // na lista: os que a IA escolheu e os já conferidos (um deixado de fora conferido sai de lá); embaixo, os deixados de fora
    const chosen = newsGroups(D.items.filter((it) => ov.cats.includes(it.cat) && (tri[it.id] === true || res[it.id])), ov).sort(sortG);
    const out = newsGroups(D.items.filter((it) => tri[it.id] === false && !res[it.id] && ov.cats.includes(it.cat)), ov).sort(sortG);
    // os deixados de fora no fim, recolhidos (o padrão dos apps para o que fica de fora): abertos, ficam abertos
    // enquanto a tela está aberta (conferir um por um não fecha a lista); ao voltar à tela, recolhidos de novo
    const wasOpen = !!$(".news-out[open]", ls);
    ls.innerHTML = `${chosen.length ? `<ul class="nlist">${chosen.map(newsRow).join("")}</ul>`
        : `<p class="muted">${ov.pendentes ? "Toque em Conferir novidades: a IA escolhe os equipamentos." : "Nenhum item em Eletrônicos."}</p>`}
      ${out.length ? `<details class="news-out"${wasOpen ? " open" : ""}><summary>${ic("chev", "sm")}Deixados de fora pela IA (${int(out.length)})</summary><ul class="nlist">${out.map(newsRow).join("")}</ul></details>` : ""}`;
    if (!newsJob) renderNewsJob(null);
  }
  function renderNewsJob(st) {
    const js = $('#view [data-slot="news-job"]');
    if (!js) return;
    const btn = $('#view [data-act="news-all"]');
    if (btn) btn.disabled = !!(st && st.stage === "busy");
    if (st && st.stage === "busy") {
      const p = st.progress || {}, pct = p.total ? Math.round((p.feitos / p.total) * 100) : 0;
      js.innerHTML = `<div class="njob" aria-live="polite"><p><span class="spin"></span><span>${esc(st.msg || "Conferindo…")}</span></p>
        <div class="prog" role="progressbar" aria-label="Progresso" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"><i style="width:${pct}%"></i></div>
        <button type="button" class="btn sm" data-act="news-cancel">Parar</button></div>`;
      return;
    }
    if (st && st.stage === "error") { js.innerHTML = `<p class="formerr njob">${esc(st.msg)}</p>`; return; }
    const u = newsOv && newsOv.ultima;
    js.innerHTML = u ? `<p class="muted njob">Conferido ${esc(whenShort(u.at))}: ${u.conferidos ? `${int(u.com_novidades)} de ${int(u.conferidos)} com novidades` : "nada para conferir agora"}.</p>` : "";
  }
  async function startNewsAll() {
    try { const r = await API.post("api/news/all", {}); newsJob = r.id; renderNewsJob({ stage: "busy", msg: "Começando…" }); pollNewsAll(); }
    catch (e) { fail(e); }
  }
  async function pollNewsAll() {
    clearTimeout(newsTimer);
    if (!newsJob) return;
    let st;
    try { st = await API.get(`api/news/${newsJob}`); }
    catch (e) { newsJob = null; renderNewsJob({ stage: "error", msg: e.message }); return; }
    if (st.stage === "busy") {
      renderNewsJob(st);
      if ($('#view [data-slot="news-job"]')) newsTimer = setTimeout(pollNewsAll, 1500); else newsJob = null; // saiu da aba: segue no servidor
      return;
    }
    API.del(`api/news/${newsJob}`).catch(() => {});
    newsJob = null;
    const sm = st.summary || {};
    if (st.stage === "done") toast(sm.conferidos ? `Conferidos ${int(sm.conferidos)}: ${int(sm.com_novidades || 0)} com novidades.` : "Tudo conferido nos últimos 7 dias.");
    await loadNews();
    if (st.stage === "error") renderNewsJob(st);
  }
  async function clearNews() {
    const ok = await confirmBox({ title: "Limpar as novidades?", body: "O inventário não muda.", ok: "Limpar", danger: true });
    if (!ok) return;
    try {
      newsOv = await API.del("api/news");
      newsJob = null;
      clearTimeout(newsTimer);
      renderNews();
      renderNewsJob(null);
      toast("Novidades limpas.");
    } catch (e) { fail(e); }
  }
  async function cancelNewsAll() {
    if (!newsJob) return;
    const j = newsJob;
    newsJob = null;
    clearTimeout(newsTimer);
    await API.del(`api/news/${j}`).catch(() => {});
    toast("Conferência parada. O que já foi conferido ficou salvo.");
    loadNews();
  }

  // chave liga/desliga (um checkbox com papel de switch), rotulada pelo título da linha
  const switchHtml = (key, on, labelledby) => `<label class="switch"><input type="checkbox" role="switch" data-input="${key}" aria-labelledby="${labelledby}"${on ? " checked" : ""}><span class="track" aria-hidden="true"></span></label>`;
  function moreIntegrations() {
    const on = aiOn();
    // na ordem da família: os outros apps (o GerencIA, quando publica a depreciação) › CorrerIA › IA do Home Assistant ›
    // Falar › Uso da IA › Sensores
    return `
    ${S.gerencia && S.gerencia.taxas ? `<section class="panel" id="p-gerencia">
      <h2>${secIc("wallet")}GerencIA</h2>
      <ul class="opts"><li><div class="ot"><b id="deprec-h">Valor de hoje</b><span>${deprecOn()
        ? "Ligado: os valores perdem, por ano, a taxa de cada categoria do GerencIA."
        : "Os valores com a depreciação de cada categoria, a do GerencIA."}</span></div>
        <div class="oa">${switchHtml("deprec-on", deprecOn(), "deprec-h")}</div></li></ul>
    </section>` : ""}
    <section class="panel" id="p-correria">
      <h2>${secIc("flash")}CorrerIA</h2>
      <ul class="opts"><li><div class="ot"><b id="correria-h">Usar com o CorrerIA</b><span>${correriaOn()
        ? "Ligado: pelo WhatsApp, o Claude e o Gemini leem e mudam o inventário."
        : "Para o WhatsApp, o Claude e o Gemini lerem e mudarem o inventário."}</span></div>
        <div class="oa">${switchHtml("correria-on", correriaOn(), "correria-h")}</div></li></ul>
      ${correriaOn() ? `<p class="help" data-slot="correria-uso">${esc(correriaUsoTxt())}</p>` : ""}
    </section>
    <section class="panel" id="p-ai">
      <h2>${secIc("scan")}IA do Home Assistant</h2>
      <p class="lead">A IA configurada no Home Assistant: Claude, OpenAI, Gemini ou Ollama.</p>
      <ul class="opts"><li><div class="ot"><b id="ai-on-h">Usar IA</b><span>${on ? "Ler fotos, catalogar e buscar na internet." : "Os botões de IA e o Falar ficam escondidos."}</span></div>
        <div class="oa">${switchHtml("ai-on", on, "ai-on-h")}</div></li></ul>
      ${on ? `<div data-slot="ai-panel"><p class="muted">Verificando…</p></div>` : ""}
    </section>
    ${on ? `<section class="panel" id="p-voice">
      <h2>${secIc("mic")}Falar</h2>
      <p class="lead" data-slot="voice-lead">${voiceLead(aiCache.data)}</p>
      <div data-slot="voice-panel"><p class="muted">Verificando…</p></div>
    </section>
    <section class="panel" id="p-usage">
      <h2>${secIc("bars")}Uso da IA</h2>
      <p class="lead">O Home Assistant não informa tokens nem custo: o app conta as chamadas e estima os tokens.</p>
      <div data-slot="usage"><p class="muted">Carregando…</p></div>
    </section>
    <section class="panel" id="p-sensors">
      <h2>${secIc("gauge")}Sensores no Home Assistant</h2>
      <ul class="opts"><li><div class="ot"><b id="sensors-h">Criar os sensores</b><span>${sensorsOn()
        ? '<span class="codepath">sensor.inventaria_ia_hoje</span>, com as chamadas de IA de hoje.'
        : "As chamadas de IA de hoje, para painéis e automações."}</span></div>
        <div class="oa">${switchHtml("sensors-on", sensorsOn(), "sensors-h")}</div></li></ul>
    </section>` : ""}
`;
  }
  // CorrerIA (o contato no WhatsApp e o servidor MCP do Claude e do Gemini) usa as ferramentas do servidor (ferramentas.py),
  // sem a IA daqui: não depende do Usar IA. A linha diz quem usou por último (o cliente do último pedido) e quando.
  function correriaUsoTxt() {
    const u = S.correriaUso, d = u && u.em ? new Date(u.em) : null;
    if (!d || Number.isNaN(d.getTime())) return "Ainda não foi usado. Conecte no app CorrerIA.";
    const k = ymd(d), dia = k === ymd(new Date()) ? "hoje" : k === ymd(new Date(Date.now() - 864e5)) ? "ontem" : `em ${ddmm(k)}`;
    return `${u.app || "CorrerIA"} usou ${dia} às ${d.toLocaleTimeString("pt-BR", { hour: "numeric", minute: "2-digit" })}.`;
  }

  // -- uso da IA (igual ao do EconomIA): hoje, 7 dias e o mês, gráfico por dia e as últimas chamadas
  let usageData = null, usageSel = null;
  const USAGE_KIND = { foto: "Digitalizar com IA", catalogo: "Catalogar itens", busca: "Buscar foto na internet", fala: "Falar", novidades: "Novidades", triagem: "Escolher equipamentos", chat: "Conversar" };
  const USAGE_RES = { ok: "", cota: "cota excedida", formato: "fora do formato", sem_busca: "sem busca na web", erro: "erro" };
  const WEEKDAY = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
  const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const weekday = (day) => WEEKDAY[new Date(`${day}T12:00:00`).getDay()];
  const ddmm = (day) => `${day.slice(8, 10)}/${day.slice(5, 7)}`;
  const milTokens = (n) => { n = +n || 0; return n >= 1e6 ? `${(n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi` : n >= 1000 ? `${Math.round(n / 1000)} mil` : String(Math.round(n)); };
  function whenShort(iso) {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const hm = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    const k = ymd(d), today = ymd(new Date()), yest = ymd(new Date(Date.now() - 864e5));
    return k === today ? `hoje ${hm}` : k === yest ? `ontem ${hm}` : `${ddmm(k)} ${hm}`;
  }
  function aiName(id) {
    if (!id || id === "padrão do Home Assistant") return "Padrão do Home Assistant";
    const all = [...(aiCache.data?.entities || []), ...(aiCache.data?.agents || [])];
    const x = all.find((e) => e.id === id);
    return x ? x.name : id === "ai_task.simulado" ? "IA simulada (teste)" : id.replace(/^[a-z_]+\./, "").replace(/_/g, " ");
  }
  function aiProvider(words) {
    const j = norm(words.join(" "));
    if (/google|gemini/.test(j)) return "google";
    if (/openai|chatgpt|gpt/.test(j)) return "openai";
    if (/anthropic|claude/.test(j)) return "anthropic";
    return "";
  }
  function usageExample() {
    const day = (i) => ymd(new Date(Date.now() - (6 - i) * 864e5));
    const recent = [["catalogo", "ok", 8.4, 2100, 1], ["foto", "ok", 5.1, 1300, 1], ["busca", "ok", 31.0, 1900, 0], ["foto", "cota", 1.2, 900, 1]]
      .map(([kind, result, seconds, tokens, images], i) => ({ at: new Date(Date.now() - (i * 9 + 4) * 60000).toISOString(), kind, entity: "ai_task.google_ai_task", result, seconds, tokens, images }));
    return { today: { calls: 4, errors: 0, quota: 1, tokens: 6200, images: 3, kinds: { foto: 2, catalogo: 1, busca: 1 }, entities: {} },
      week: { calls: 19, errors: 1, quota: 1, tokens: 31000, images: 14, kinds: { foto: 9, catalogo: 6, busca: 4 }, entities: { "ai_task.google_ai_task": 19 } },
      month: { calls: 47, errors: 2, quota: 1, tokens: 78000, images: 36, kinds: {}, entities: {} },
      days: [2, 0, 5, 3, 0, 5, 4].map((calls, i) => ({ day: day(i), calls, errors: i === 2 ? 1 : 0, quota: i === 6 ? 1 : 0 })), recent, sensor: "sensor.inventaria_ia_hoje" };
  }
  function renderUsage(slot) {
    const u = usageData;
    if (!u || !u.today || !(u.days || []).length) { slot.innerHTML = `<p class="muted">Sem dados de uso ainda.</p>`; return; }
    const today = u.days[u.days.length - 1].day;
    if (!usageSel || !u.days.some((d) => d.day === usageSel)) usageSel = today;
    const dayLong = (day) => (day === today ? "Hoje" : `${weekday(day).replace(/^./, (c) => c.toUpperCase())}, ${ddmm(day)}`);
    const sub = (t) => (t.quota ? `<span class="s alerta">${int(t.quota)} ${t.quota > 1 ? "vezes" : "vez"} sem cota</span>`
      : t.errors ? `<span class="s alerta">${int(t.errors)} com erro</span>` : `<span class="s">≈ ${milTokens(t.tokens)} tokens</span>`);
    const tile = (k, t) => `<div class="uso-tile"><span class="k">${k}</span><span class="v">${int(t.calls || 0)}</span>${sub(t)}</div>`;
    const max = Math.max(1, ...u.days.map((d) => d.calls || 0));
    const bars = u.days.map((d) => {
      const h = d.calls ? Math.max(4, Math.round((d.calls / max) * 100)) : 0;
      const lab = `${dayLong(d.day)}: ${plural(d.calls || 0, "chamada", "chamadas")}${d.errors ? `, ${d.errors} com erro` : ""}${d.quota ? `, ${d.quota} sem cota` : ""}`;
      return `<button type="button" class="uso-bar" data-usage-day="${esc(d.day)}" aria-pressed="${d.day === usageSel}" aria-label="${esc(lab)}" title="${esc(lab)}"><i style="height:${h}%"></i></button>`;
    }).join("");
    const sel = u.days.find((d) => d.day === usageSel);
    const kinds = Object.entries(u.week.kinds || {}).sort((a, b) => b[1] - a[1]);
    const recent = (u.recent || []).map((c) => {
      const res = USAGE_RES[c.result] ?? c.result;
      return `<li><b>${esc(USAGE_KIND[c.kind] || c.kind)}</b><span>${esc(aiName(c.entity))}</span>${res ? `<span class="r-erro">${esc(res)}</span>` : ""}
        <span class="t">${esc(String(c.seconds).replace(".", ","))} s · ≈ ${milTokens(c.tokens)} tokens${c.images ? ` · ${plural(c.images, "imagem", "imagens")}` : ""} · ${esc(whenShort(c.at))}</span></li>`;
    }).join("");
    const ids = [...Object.keys(u.month.entities || {}), ...Object.keys(u.week.entities || {}), S.settings.ai_entity || "", S.settings.ai_search || ""];
    let prov = aiProvider([...ids, ...ids.filter(Boolean).map(aiName)]);
    if (!prov) {
      const ps = new Set([...(aiCache.data?.entities || []), ...(aiCache.data?.agents || [])].map((e) => aiProvider([e.id, e.name])).filter(Boolean));
      if (ps.size === 1) prov = [...ps][0];
    }
    const link = (href, txt) => `<a href="${href}" target="_blank" rel="noopener noreferrer">${txt}</a>`;
    const provTxt = prov === "google" ? `Consumo exato do Gemini: ${link("https://console.cloud.google.com/apis/dashboard", "Google Cloud Console")}, em Generative Language API. A cota grátis volta de madrugada (4h ou 5h).`
      : prov === "openai" ? `Consumo exato e custo da OpenAI: ${link("https://platform.openai.com/usage", "platform.openai.com/usage")}.`
      : prov === "anthropic" ? `Consumo exato e custo da Anthropic: ${link("https://platform.claude.com/usage", "Claude Console, Usage")}.`
      : "Consumo exato e custo: no painel do provedor da sua IA.";
    slot.innerHTML = `<div class="uso-tiles">${tile("Hoje", u.today)}${tile("7 dias", u.week)}${tile("Este mês", u.month)}</div>
      <div class="uso-chart" role="group" aria-label="Chamadas de IA nos últimos 7 dias">${bars}</div>
      <div class="uso-dias" aria-hidden="true">${u.days.map((d) => `<span>${d.day === today ? "hoje" : weekday(d.day)}</span>`).join("")}</div>
      <p class="uso-cap" aria-live="polite">${dayLong(sel.day)}: <b>${plural(sel.calls || 0, "chamada", "chamadas")}</b>${sel.errors ? `, ${int(sel.errors)} com erro` : ""}${sel.quota ? `, ${int(sel.quota)} sem cota` : ""}.</p>
      ${kinds.length ? `<ul class="uso-tipos" aria-label="Nos últimos 7 dias">${kinds.map(([k, n]) => `<li>${esc(USAGE_KIND[k] || k)} <b>${int(n)}</b></li>`).join("")}</ul>` : ""}
      <details class="uso-ult"><summary>${ic("chev", "sm")}Últimas chamadas</summary><ul>${recent || "<li>Nenhuma chamada ainda.</li>"}</ul></details>
      <p class="help">${provTxt} A estimativa conta só o texto.</p>`;
  }
  function moreData() {
    return `
    <section class="panel" id="p-backup">
      <h2>${secIc("archive")}Backup na pasta share</h2>
      <p class="lead">Cópia completa, com fotos, em <span class="codepath">share/inventario</span>. Os backups do Home Assistant também incluem o inventário.</p>
      <div data-slot="backups"><p class="muted">Carregando backups…</p></div>
    </section>
    <section class="panel" id="p-import">
      <h2>${secIc("upload")}Importar</h2>
      <p class="lead">Backup .zip, com fotos, ou .json do app. Antes, o app guarda uma cópia do atual.</p>
      <div class="sec-acao"><button class="btn" data-act="import-file">${ic("upload")}Escolher arquivo</button></div>
      <p class="help">${MULTI_PICK ? "Backup em partes: escolha todas de uma vez." : "Backup em partes: uma de cada vez, começando pela parte 1."}</p>
    </section>
    <section class="panel" id="p-history">
      <h2>${secIc("history")}Versões anteriores</h2>
      <p class="lead">Uma cópia a cada 10 minutos de uso e antes de importar, restaurar ou apagar tudo. Ficam as 3 mais recentes.</p>
      <div class="sec-acao"><button class="btn" data-act="versions">${ic("history")}Ver versões</button></div>
    </section>
    <section class="panel" id="p-where">
      <h2>${secIc("folder")}Onde ficam os dados</h2>
      <p class="lead">Itens em <span class="codepath">inventario.json</span> e fotos em JPG, dentro do app. Entram nos backups do Home Assistant.</p>
    </section>
    <section class="panel" id="p-zero">
      <h2>${secIc("trash")}Começar do zero</h2>
      <p class="lead">Apaga os cômodos, os bens e os itens. As categorias e as opções continuam, e uma cópia fica em Versões anteriores.</p>
      <div class="sec-acao"><button type="button" class="btn danger" data-act="erase-all"${S.items.length || S.rooms.length ? "" : " disabled"}>${ic("trash")}Apagar tudo</button></div>
    </section>`;
  }
  function moreLook() {
    const theme = LS.get("theme", "auto");
    const accent = accentOf();
    return `
    <section class="panel" id="p-look">
      <h2>${secIc("contrast")}Tema</h2>
      <p class="lead">Cada aparelho guarda a sua escolha.</p>
      <div class="seg themes" role="group" aria-label="Tema">
        ${[["auto", "Sistema", "phone"], ["light", "Claro", "sun"], ["dark", "Escuro", "moon"]].map(([k, v, i]) => `<button type="button" data-act="theme" data-theme="${k}" aria-pressed="${theme === k}">${ic(i)}<span>${v}</span></button>`).join("")}
      </div>
    </section>
    <section class="panel" id="p-accent">
      <h2 id="accent-h">${secIc("palette")}Cor do app</h2>
      <p class="lead">Vale para todos os aparelhos.</p>
      <ul class="opts"><li><div class="ot"><b id="daily-h">Cor do dia</b><span>Muda a cor do app todo dia.</span></div>
        <div class="oa">${switchHtml("accent-daily", accentDaily(), "daily-h")}</div></li></ul>
      <div class="swatches" role="radiogroup" aria-labelledby="accent-h">${ACCENTS.map(([k, v]) => `<label class="sw" data-accent="${k}"><input type="radio" name="accent" value="${k}" data-input="accent"${k === accent ? " checked" : ""}>${SWATCH}<span>${v}</span></label>`).join("")}</div>
    </section>`;
  }
  // Opções: o que muda o jeito de cadastrar e de ver o inventário, para a casa toda
  // Novidades › o aviso no celular, o mesmo componente dos apps da família (o modelo é o do GerencIA): Conferir sozinho,
  // o Horário (uma caixa do app, de meia em meia hora, sem o AM/PM do celular) e A cada, lado a lado; Avisar no celular;
  // Quem recebe (um botão por pessoa da casa, do mesmo tamanho, lado a lado; nunca um aparelho: os celulares de cada
  // pessoa são os ligados a ela no Home Assistant) e Testar no meu celular, na largura toda, embaixo.
  const NEWS_EVERY = [[7, "7 dias"], [15, "15 dias"], [30, "30 dias"]];
  const NEWS_HORAS = Array.from({ length: 48 }, (_, k) => `${String(k >> 1).padStart(2, "0")}:${k % 2 ? "30" : "00"}`);
  let newsPeople = null;
  const joinE = (l) => (l.length > 1 ? `${l.slice(0, -1).join(", ")} e ${l[l.length - 1]}` : l[0] || "");
  // quem recebe; do jeito antigo (até a 1.42), "todos" marca todas as pessoas com celular
  function newsPara() {
    const p = S.settings.news_para || [];
    return p.includes("todos") ? (newsPeople || []).filter((x) => x.phone).map((x) => x.id) : p;
  }
  function moreNewsOptions() {
    if (!aiOn()) return "";
    const on = newsOn(), every = +S.settings.news_every || 0, aviso = !!S.settings.news_aviso;
    const hora = S.settings.news_hora || "10:00", horas = NEWS_HORAS.includes(hora) ? NEWS_HORAS : [...NEWS_HORAS, hora].sort();
    const opt = (v, label, cur) => `<option value="${esc(v)}"${String(v) === String(cur) ? " selected" : ""}>${esc(label)}</option>`;
    return `
    <section class="panel" id="p-news-opts">
      <h2>${secIc("spark")}Novidades</h2>
      <ul class="opts"><li><div class="ot"><b id="news-h">Usar novidades</b><span>Atualizações e recalls dos eletrônicos.</span></div>
        <div class="oa">${switchHtml("news-on", on, "news-h")}</div></li>
      ${on ? `<li><div class="ot"><b id="news-auto-h">Conferir sozinho</b><span>A IA confere os eletrônicos de tempos em tempos.</span></div>
        <div class="oa">${switchHtml("news-auto", !!every, "news-auto-h")}</div></li>` : ""}
      ${on && every ? `<li class="aviso-quando">
          <div class="field"><label for="news-hora">Horário</label><select id="news-hora" class="select" data-input="news-hora">${horas.map((x) => opt(x, x, hora)).join("")}</select></div>
          <div class="field"><label for="news-every">A cada</label><select id="news-every" class="select" data-input="news-every">${NEWS_EVERY.map(([k, v]) => opt(k, v, every)).join("")}</select></div></li>
        <li><div class="ot"><b id="news-aviso-h">Avisar no celular</b><span>Quando a conferência sozinha achar novidade.</span></div>
          <div class="oa">${switchHtml("news-aviso", aviso, "news-aviso-h")}</div></li>
        ${aviso ? `<li class="aviso-quem" data-slot="news-quem">${quemRecebe()}</li>` : ""}` : ""}
      </ul>
    </section>`;
  }
  // Testar no meu celular: o aviso vai para o celular de quem está na tela (como nos outros apps); sem celular, fica inativo
  function newsTestWhy() {
    if (!newsPeople) return "";
    const me = newsPeople.find((x) => x.eu);
    return !me ? "Você não está entre as pessoas do Home Assistant." : me.phone ? "" : "Sem celular ligado a você no Home Assistant.";
  }
  function quemRecebe() {
    const P = newsPeople, para = new Set(newsPara());
    let h = `<div class="field"><span class="lbl" id="quem-l">Quem recebe</span>`;
    if (!P) h += `<p class="help">Procurando as pessoas da casa…</p>`;
    else if (!P.length) h += `<p class="help">Nenhuma pessoa da casa no Home Assistant.</p>`;
    else {
      h += `<div class="quem" role="group" aria-labelledby="quem-l">${P.map((p) => `<button type="button" class="quem-p${para.has(p.id) ? " on" : ""}${p.phone ? "" : " sem"}" data-act="news-pessoa" data-id="${esc(p.id)}" aria-pressed="${para.has(p.id)}">${ic("user", "sm")}<b>${esc(p.name)}</b>${p.phone ? "" : "<span>sem celular</span>"}</button>`).join("")}</div>`;
      const sem = P.filter((p) => para.has(p.id) && !p.phone).map((p) => p.name);
      if (sem.length) h += `<p class="help">Sem celular para ${esc(joinE(sem))}: ligue o celular à pessoa no Home Assistant (Configurações > Pessoas).</p>`;
      else if (!para.size) h += `<p class="help">Escolha quem recebe.</p>`;
    }
    const why = newsTestWhy();
    return `${h}</div><button type="button" class="btn block aviso-testar" data-act="news-notify-test"${why ? " disabled" : ""}>${ic("send")}Testar no meu celular</button>${why ? `<p class="help">${esc(why)}</p>` : ""}`;
  }
  async function loadNewsTargets() {
    if (newsPeople || !newsOn()) return;
    try { newsPeople = (await API.get("api/news/people")).people || []; } catch { newsPeople = []; }
    const slot = $('#view [data-slot="news-quem"]');
    if (slot) slot.innerHTML = quemRecebe();
  }
  async function saveNews(patch, msg) {
    try {
      const out = await API.put("api/settings", patch);
      Object.assign(S.settings, patch);
      if (out && Array.isArray(out.news_para)) S.settings.news_para = out.news_para;
      renderView(false);
      if (msg) toast(msg);
      return true;
    } catch (er) { fail(er); renderView(false); return false; }
  }
  function toggleNewsPessoa(id) {
    const para = new Set(newsPara());
    if (para.has(id)) para.delete(id); else para.add(id);
    const p = (newsPeople || []).find((x) => x.id === id);
    saveNews({ news_para: [...para] }, `${p ? p.name : "A pessoa"} ${para.has(id) ? "recebe" : "não recebe"} o aviso`);
  }
  function moreOptions() {
    return `${moreNewsOptions()}
    <section class="panel" id="p-bens">
      <h2>${secIc("home")}Bens</h2>
      <p class="lead">Casa, terreno, carro: o que fica fora de casa.</p>
      <ul class="opts"><li><div class="ot"><b id="bens-h">Usar bens</b><span>Desligar não apaga os bens.</span></div>
        <div class="oa">${switchHtml("bens-on", bensOn(), "bens-h")}</div></li></ul>
    </section>
    <section class="panel" id="p-zones">
      <h2>${secIc("pin")}Zonas</h2>
      <p class="lead">Partes de um cômodo, como Estante ou Rack da TV.</p>
      <ul class="opts"><li><div class="ot"><b id="zones-h">Usar zonas</b><span>Desligar não apaga as zonas.</span></div>
        <div class="oa">${switchHtml("zones-on", zonesOn(), "zones-h")}</div></li></ul>
    </section>
    ${moreShortcut()}`;
  }
  // Atalho no celular (igual em todos os apps da família): o caminho do app no Home Assistant, para um ícone na tela inicial
  // que abre o app direto (Atalho fixado do app do Home Assistant no Android). Fora do Home Assistant, não aparece.
  function moreShortcut() {
    if (!S.atalho) return "";
    return `<section class="panel" id="p-atalho">
      <h2>${secIc("phone")}Atalho no celular</h2>
      <p class="lead">Um ícone na tela inicial do celular que abre o InventarIA direto.</p>
      <ol class="steps"><li>No app do Home Assistant: <b>Configurações › Aplicativo complementar › Gerenciar atalhos</b>.</li><li>Em <b>Atalho fixado</b>, escolha o tipo <b>Painel</b> e cole o <b>Caminho</b> abaixo.</li></ol>
      <div class="field atalho-f"><label for="atalho-c">Caminho</label><div class="copy-row"><input id="atalho-c" class="input" readonly value="${esc(S.atalho)}">
        <button type="button" class="btn" data-act="copy-field" data-target="atalho-c">${ic("copy")}Copiar</button></div></div>
    </section>`;
  }
  // Copiar: em http o navegador não deixa (sem área de transferência): o texto fica selecionado e o aviso explica
  async function copyField(id) {
    const inp = document.getElementById(id);
    if (!inp) return;
    inp.focus(); inp.select();
    try {
      if (!navigator.clipboard) throw new Error("sem área de transferência");
      await navigator.clipboard.writeText(inp.value);
      toast("Copiado");
    } catch { toast("Toque e segure no texto para copiar"); }
  }
  // -- Categorias: uma tela própria, no menu Mais
  function viewCats() {
    return `
    <section class="panel" id="p-cats">
      <ul class="opts cats">
        <li><div class="ot"><b>${plural(CATS.length, "categoria", "categorias")}</b></div>
          <div class="oa"><button type="button" class="btn" data-act="cat-new">${ic("plus")}Nova categoria</button></div></li>
        ${CATS.map(([k, v]) => {
          const n = D.catTotals.get(k)?.count || 0;
          // Eletrônicos é a categoria das novidades: fica sempre, com o mesmo nome (sem Renomear nem Apagar)
          if (k === "eletronicos") return `<li><div class="ot"><b>${esc(v)}</b><span>${plural(n, "item", "itens")}</span></div></li>`;
          return `<li><div class="ot"><b>${esc(v)}</b><span>${plural(n, "item", "itens")}</span></div>
            <div class="oa"><button type="button" class="btn icon" data-act="cat-edit" data-cat="${esc(k)}" aria-label="Renomear ${esc(v)}">${ic("edit")}</button>
              ${k === "outros" ? `<span class="cat-keep" aria-hidden="true"></span>` : `<button type="button" class="btn icon danger" data-act="cat-del" data-cat="${esc(k)}" aria-label="Apagar ${esc(v)}">${ic("trash")}</button>`}</div></li>`;
        }).join("")}
      </ul>
    </section>`;
  }
  // criar ou renomear uma categoria
  function openCatName(id = null) {
    const old = id ? CAT[id] : "";
    const entry = openDialog({
      cls: "modal narrow", label: id ? "Renomear categoria" : "Nova categoria",
      html: `<div class="dlg"><div class="dlg-h"><h2>${id ? "Renomear categoria" : "Nova categoria"}</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b" data-cn><div class="form">
          <div class="field"><label for="cn-name">Nome</label><input id="cn-name" class="input" name="name" maxlength="60" value="${esc(old)}" placeholder="Ex.: Ferramentas" autocomplete="off"></div>
          <div class="formerr" data-err hidden></div>
        </div></form>
        <div class="dlg-f"><span class="grow"></span><button class="btn ghost" data-x>Cancelar</button><button class="btn primary" data-ok>${id ? "Salvar" : "Criar categoria"}</button></div></div>`,
    });
    const form = $("[data-cn]", entry.dlg), err = $("[data-err]", entry.dlg);
    setTimeout(() => { form.name.focus(); form.name.select(); }, 50);
    const go = async () => {
      const name = form.name.value.trim();
      if (!name) { err.hidden = false; err.textContent = "Dê um nome à categoria."; form.name.focus(); return; }
      if (id && name === old) { requestClose(entry, { force: true }); return; }
      try {
        const res = id ? await API.put(`api/cats/${encodeURIComponent(id)}`, { name }) : await API.post("api/cats", { name });
        setRev(res.rev); applyCats(res.cats); derive();
        finalizeThen(entry, () => { refreshAll(); toast(id ? "Categoria renomeada" : `${res.cat.name} criada`); });
      } catch (e) { err.hidden = false; err.textContent = e.message; }
    };
    form.addEventListener("submit", (e) => { e.preventDefault(); go(); });
    entry.dlg.addEventListener("click", (e) => { if (e.target.closest("[data-x]")) requestClose(entry, { force: true }); if (e.target.closest("[data-ok]")) go(); });
  }
  async function deleteCat(id) {
    const name = CAT[id], n = D.catTotals.get(id)?.count || 0;
    if (!name) return;
    const ok = await confirmBox({ title: `Apagar ${name}?`, body: n ? `${plural(n, "item vai", "itens vão")} para ${esc(CAT.outros || "Outros")}.` : "", ok: "Apagar categoria", danger: true });
    if (!ok) return;
    try {
      await API.del(`api/cats/${encodeURIComponent(id)}`);
      await loadData(); refreshAll();
      toast(`${name} apagada`);
    } catch (e) { fail(e); }
  }
  // Trocar de aba substitui o endereço (não enche o histórico: Voltar sai de Mais) e mantém as abas no alto.
  function setMoreTab(k) {
    k = moreTab(k);
    if (base.name !== "data" || moreTab(base.tab) === k) return;
    const y = window.scrollY;
    const anchor = $("#view .more-anchor"), tabs = $("#view .more-tabs");
    const natural = anchor && tabs ? anchor.getBoundingClientRect().top + window.scrollY + (parseFloat(getComputedStyle(tabs).marginTop) || 0) : 0;
    base = { ...base, tab: k };
    try { history.replaceState(history.state, "", hashOf(base)); } catch { /* ok */ }
    renderView(false);
    window.scrollTo(0, Math.min(y, natural));
    $(`#mt-${k}`)?.focus({ preventScroll: true });
    showMoreTab();
  }
  // a barra de abas rola para o lado no celular estreito: a aba escolhida fica à vista
  function showMoreTab() {
    const bar = $("#view .more-tabs"), on = bar && $('[aria-selected="true"]', bar);
    if (!on) return;
    const l = on.offsetLeft, r = l + on.offsetWidth;
    if (l < bar.scrollLeft) bar.scrollLeft = l - 8;
    else if (r > bar.scrollLeft + bar.clientWidth) bar.scrollLeft = r - bar.clientWidth + 8;
  }

  async function loadDataPanels() {
    const tab = moreTab(base.tab);
    if (tab === "opcoes") loadNewsTargets();
    const bslot = tab === "dados" ? $('#view [data-slot="backups"]') : null;
    const aslot = tab === "integracoes" ? $('#view [data-slot="ai-panel"]') : null;
    if (bslot) try {
      const b = await API.get("api/backups");
      if (document.contains(bslot)) {
        bslot.innerHTML = `<div class="sec-acao"><button class="btn primary" data-act="backup-create"${b.available === false ? " disabled" : ""}>${ic("archive")}Criar backup</button></div>
          ${b.available === false ? '<p class="help">A pasta share não está disponível.</p>' : ""}
          <ul class="opts bk-lista">
          ${(b.backups || []).slice(0, 12).map((x) => `<li><div class="ot"><b>${esc(shortDateTime(x.date))}</b><span title="${esc(x.name)}">${esc(fmtSize(x.size))} · ${esc(x.name)}</span></div>
            <div class="oa"><button class="btn" data-act="backup-restore" data-name="${esc(x.name)}">${ic("history")}Restaurar</button></div></li>`).join("")}
        </ul>`;
      }
    } catch (e) { bslot.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
    if (aslot) { const st = await aiStatus(true); if (document.contains(aslot)) { renderAiPanel(aslot, st); paintVoiceLead(); } }
    showMoreTab();
    const vslot = tab === "integracoes" ? $('#view [data-slot="voice-panel"]') : null;
    if (vslot) { renderVoicePanel(vslot); }
    const uslot = tab === "integracoes" ? $('#view [data-slot="usage"]') : null;
    if (uslot) {
      try { usageData = PREVIEW ? usageExample() : await API.get("api/ai/usage"); if (document.contains(uslot)) renderUsage(uslot); }
      catch (e) { if (document.contains(uslot)) uslot.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
    }
  }
  const fmtSize = (n) => (n > 1048576 ? `${(n / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

  // ------------------------------------------------------------------ IA
  let aiCache = { at: 0, data: null };
  async function aiStatus(force = false) {
    if (!force && aiCache.data && Date.now() - aiCache.at < 60000) return aiCache.data;
    try { aiCache = { at: Date.now(), data: await API.get("api/ai/status") }; } catch (e) { aiCache = { at: Date.now(), data: { ready: false, reason: "error", message: e.message, entities: [] } }; }
    return aiCache.data;
  }
  // Falar: quem separa os itens é a IA, se houver uma pronta (como no openCatalog); sem ela, o app, pelas vírgulas
  const voiceSplit = (st) => (st && !st.ready ? "o app separa pelas vírgulas" : "a IA separa os itens");
  const voiceLead = (st) => `Fale os itens e quanto valem.${st ? ` O Home Assistant transcreve e ${voiceSplit(st)}.` : ""}`; // antes de saber, não diz quem separa
  function paintVoiceLead() { const el = $('#view [data-slot="voice-lead"]'); if (el) el.textContent = voiceLead(aiCache.data); }
  function aiReasonText(st) {
    switch (st.reason) {
      case "no_api": return "O app não tem acesso à API do Home Assistant.";
      case "no_entity": return "Nenhuma integração de IA encontrada no Home Assistant.";
      case "no_vision": return st.selected ? "A IA escolhida não aceita fotos. Escolha outra." : "As IAs configuradas não aceitam fotos.";
      case "error": return st.message || "Não deu para consultar o Home Assistant.";
      case "preview": return "Na prévia, a leitura é simulada.";
      default: { const e = (st.entities || []).find((x) => x.id === st.selected); return (e ? `Usando ${e.name}.` : "Usando a IA preferida do Home Assistant.") + (st.missing ? " A escolhida saiu do Home Assistant." : ""); }
    }
  }
  const AI_STEPS = `<ol class="steps">
    <li>No Home Assistant, abra Configurações, Dispositivos e serviços, Adicionar integração.</li>
    <li>Escolha Anthropic, OpenAI, Google Gemini ou Ollama (local, grátis) e cole a chave de API.</li>
    <li>Na integração, adicione uma tarefa de IA (AI Task) com um modelo que leia imagens.</li>
    <li>Escolha essa IA aqui, em Mais > Configurações > Integrações.</li></ol>`;
  function renderAiPanel(slot, st) {
    if (st.preview) {
      slot.innerHTML = `<ul class="opts"><li><div class="ot"><b><span class="status warn"><i></i>Exemplo simulado na prévia</span></b><span>Na prévia, a leitura é simulada.</span></div></li></ul><div style="margin-top:12px"><b>Como configurar no Home Assistant</b>${AI_STEPS}</div>`;
      return;
    }
    const ents = st.entities || [], agents = st.agents || [];
    const cls = st.ready ? "ok" : st.reason === "no_vision" ? "warn" : "bad";
    const opt = (e, sel) => `<option value="${esc(e.id)}"${e.id === sel ? " selected" : ""}>${esc(e.name)}</option>`;
    slot.innerHTML = `<ul class="opts">
      <li><div class="ot"><b><span class="status ${cls}"><i></i>${st.ready ? "Pronta para ler fotos" : "Não configurada"}</span></b><span>${esc(aiReasonText(st))}</span></div>
        <div class="oa"><button class="btn" data-act="ai-refresh">${ic("refresh")}Verificar de novo</button></div></li>
      ${ents.length ? `<li><div class="ot"><b>IA para ler fotos</b><span>Padrão do Home Assistant usa a IA preferida definida lá.</span></div>
        <div class="oa"><select class="select" data-input="ai-entity" aria-label="IA para ler fotos">
          <option value="">Padrão do Home Assistant</option>
          ${ents.map((e) => `<option value="${esc(e.id)}"${e.id === st.selected ? " selected" : ""}${e.attachments ? "" : " disabled"}>${esc(e.name)}${e.attachments ? "" : " (não lê fotos)"}</option>`).join("")}
        </select></div></li>` : ""}
      ${ents.length || agents.length ? `<li><div class="ot"><b>IA para buscar fotos na internet</b><span>Padrão do Home Assistant usa a IA preferida definida lá. Precisa da busca na web: na Anthropic, "Enable web search"; no Gemini, um assistente de conversa com "Enable Google Search tool".</span></div>
        <div class="oa"><select class="select" data-input="ai-search" aria-label="IA para buscar fotos na internet">
          <option value="">Padrão do Home Assistant</option>
          ${ents.length ? `<optgroup label="Tarefas de IA">${ents.map((e) => opt(e, st.search)).join("")}</optgroup>` : ""}
          ${agents.length ? `<optgroup label="Assistentes de conversa">${agents.map((e) => opt(e, st.search)).join("")}</optgroup>` : ""}
        </select></div></li>` : ""}
    </ul>${st.ready ? "" : `<div style="margin-top:12px"><b>Como configurar</b>${AI_STEPS}</div>`}`;
  }
  async function needAi() {
    const st = await aiStatus();
    if (st.ready) return true;
    if (st.reason === "error") { toast(aiReasonText(st), { error: true }); return false; } // a IA está configurada, o Home Assistant só não respondeu
    const entry = openDialog({
      cls: "modal narrow", label: "Leitura por IA",
      html: `<div class="dlg"><div class="dlg-h"><h2>Leitura por IA</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b"><p style="margin-top:0"><span class="status ${st.reason === "no_vision" ? "warn" : "bad"}"><i></i>${esc(aiReasonText(st))}</span></p>
        <p>Configure no Home Assistant:</p>${AI_STEPS}</div>
        <div class="dlg-f"><a class="btn" href="#/config/integracoes" data-x>Abrir Integrações</a><button class="btn primary" data-x>Entendi</button></div></div>`,
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
    catch {
      url = URL.createObjectURL(file);
      try { img = await loadImg(url); }
      catch (e) {
        if (/hei[cf]/i.test(file.type || "") || /\.hei[cf]$/i.test(file.name || "")) {
          throw new Error("Foto em HEIC, que o navegador não abre. Escolha outra ou desligue o HEIF nas configurações da câmera.");
        }
        throw e;
      }
    }
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
    inp.multiple = multiple && !camera && MULTI_PICK;
    inp.value = "";
    inp.click();
  }
  // Tirar foto: no celular, a câmera do aparelho; no app do Home Assistant (Android), a câmera do próprio app
  function camera(cb, { max = 1, title = "Tirar foto" } = {}) {
    if (!ANDROID_APP) { pickFiles(cb, { camera: true }); return; }
    takePhotos({ max, title }).then((r) => {
      if (r === "pick") pickFiles(cb, { multiple: max > 1 });
      else if (r.length) cb(r);
    });
  }
  // Câmera em tela cheia: fotografa até `max` fotos e devolve os arquivos (ou "pick" para escolher da galeria)
  function takePhotos({ max = 1, title = "Tirar foto" } = {}) {
    return new Promise((resolve) => {
      let stream = null, track = null, torch = false, out = [], shots = [];
      const stop = () => { if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; };
      const entry = openDialog({
        cls: "camera", label: title,
        html: `<div class="cam">
          <video playsinline muted autoplay></video>
          <div class="cam-top"><button type="button" class="cam-btn" data-cam="close" aria-label="Fechar">${ic("close")}</button>
            <span class="cam-title">${esc(title)}</span><button type="button" class="cam-btn" data-cam="torch" aria-label="Lanterna" aria-pressed="false" hidden>${ic("flash")}</button></div>
          <div class="cam-mid"><p class="cam-hint" data-cam-hint>Abrindo a câmera…</p></div>
          <div class="cam-bottom"><div class="cam-shots" data-cam-shots></div>
            <button type="button" class="cam-shutter" data-cam="shoot" aria-label="Fotografar" disabled><span></span></button>
            ${max > 1 ? `<button type="button" class="cam-done" data-cam="done" disabled>Pronto</button>` : `<span></span>`}</div>
        </div>`,
        onClose: () => { stop(); shots.forEach((u) => URL.revokeObjectURL(u)); resolve(out); },
      });
      const dlg = entry.dlg, video = $("video", dlg), hint = $("[data-cam-hint]", dlg), shoot = $('[data-cam="shoot"]', dlg), done = $('[data-cam="done"]', dlg);
      const finish = (r) => { out = r; requestClose(entry, { force: true }); };
      const fail = (msg) => {
        stop();
        $(".cam-mid", dlg).innerHTML = `<div class="cam-msg">${ic("camera", "lg")}<p>${esc(msg)}</p><button type="button" class="btn primary" data-cam="pick">${ic("image")}Escolher fotos</button></div>`;
        shoot.disabled = true;
      };
      const md = navigator.mediaDevices;
      if (!md || !md.getUserMedia) {
        fail(window.isSecureContext === false ? "A câmera só abre com o Home Assistant num endereço seguro (https), como o do Home Assistant Cloud." : "Este aparelho não deixa o app usar a câmera.");
      } else {
        md.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1440 } } }).then((st) => {
          if (!document.contains(dlg)) { st.getTracks().forEach((t) => t.stop()); return; }
          stream = st; track = st.getVideoTracks()[0];
          video.srcObject = st; video.play().catch(() => {});
          const caps = track && track.getCapabilities ? track.getCapabilities() : {};
          $('[data-cam="torch"]', dlg).hidden = !caps.torch;
          hint.textContent = ""; shoot.disabled = false;
        }).catch((err) => {
          if (!document.contains(dlg)) return;
          const n = (err && err.name) || "";
          fail(n === "NotAllowedError" || n === "SecurityError" ? "Sem permissão para a câmera. Libere a câmera para o app do Home Assistant nas configurações do celular." : n === "NotReadableError" ? "A câmera está sendo usada por outro app." : "Não consegui abrir a câmera.");
        });
      }
      async function snap() {
        if (!video.videoWidth || shoot.disabled) return;
        shoot.disabled = true;
        const scale = Math.min(1, 2000 / Math.max(video.videoWidth, video.videoHeight));
        const c = document.createElement("canvas");
        c.width = Math.round(video.videoWidth * scale); c.height = Math.round(video.videoHeight * scale);
        c.getContext("2d").drawImage(video, 0, 0, c.width, c.height);
        const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
        if (!blob || !document.contains(dlg)) return;
        try { navigator.vibrate && navigator.vibrate(12); } catch { /* sem vibração */ }
        const file = new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" });
        if (max <= 1) { finish([file]); return; }
        out.push(file);
        const url = URL.createObjectURL(blob); shots.push(url);
        const flash = document.createElement("div"); flash.className = "cam-flash"; $(".cam", dlg).append(flash); setTimeout(() => flash.remove(), 400);
        const n = out.length;
        $("[data-cam-shots]", dlg).innerHTML = shots.slice(-3).map((u) => `<img src="${u}" alt="">`).join("") + (n > 3 ? `<span>+${n - 3}</span>` : "");
        done.disabled = false; done.textContent = `Pronto (${n})`;
        shoot.disabled = n >= max;
        hint.textContent = n >= max ? "Limite de fotos deste item." : "";
      }
      dlg.addEventListener("click", async (e) => {
        const b = e.target.closest("[data-cam]");
        if (!b) return;
        const a = b.dataset.cam;
        if (a === "close") { out = []; requestClose(entry, { force: true }); }
        else if (a === "shoot") snap();
        else if (a === "done") finish(out);
        else if (a === "pick") finish("pick");
        else if (a === "torch" && track) {
          try { await track.applyConstraints({ advanced: [{ torch: !torch }] }); torch = !torch; b.setAttribute("aria-pressed", String(torch)); }
          catch { b.hidden = true; }
        }
      });
    });
  }
  ["#pick-files", "#pick-camera"].forEach((s) => $(s).addEventListener("change", (e) => {
    const files = [...e.target.files];
    e.target.value = "";
    if (files.length && pickCb) pickCb(files);
  }));
  // Alguns seletores do Android devolvem a foto sem tipo: aceita e deixa a leitura da imagem decidir.
  const IMG_EXT = /\.(jpe?g|png|webp|gif|bmp|heic|heif|avif)$/i;
  function imageFiles(list) { return [...(list || [])].filter((f) => /^image\//.test(f.type || "") || (!f.type && (IMG_EXT.test(f.name || "") || !/\.[a-z0-9]{2,5}$/i.test(f.name || "")))); }
  function wireDrop(entry, el, onFiles) {
    entry.onFiles = onFiles;
    el.addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); el.classList.add("over"); } });
    el.addEventListener("dragleave", (e) => { if (!el.contains(e.relatedTarget)) el.classList.remove("over"); });
    el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("over"); const f = [...(e.dataTransfer.files || [])]; if (f.length) onFiles(f); });
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
          <div class="dlg-b">${photos.length ? `<div class="pick">${photos.map((p, k) => `<label><input type="checkbox" value="${esc(p.file)}" aria-label="${esc(p.label || `Foto ${k + 1}`)}"><img src="${esc(src(p.file))}" alt="" loading="lazy">${p.label ? `<span>${esc(p.label)}</span>` : ""}</label>`).join("")}</div>`
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

  // ------------------------------------------------------------------ fotos da internet
  // A IA do Home Assistant (com a busca na web) acha páginas do produto e o servidor separa as fotos.
  // Na mesma chamada, a IA devolve os dados do produto (nome, detalhes, categoria e valor): `fills(produto)` diz
  // o que dá para preencher no item, e a janela mostra isso para a pessoa decidir, sem outra chamada de IA.
  // Devolve { file, src, product } (product só se ela quiser preencher; file null se ela usar só os dados) ou null.
  const siteOf = (u) => { try { return new URL(u).hostname.replace(/^(www\d?|m)\./, ""); } catch { return ""; } };
  const WEB_FIELDS = { name: "Nome", details: "Detalhes", cat: "Categoria", value: "Valor" };
  // o que os dados da IA preenchem: só campos vazios (e o nome, num item novo, que ainda é o que a pessoa buscou)
  function webFills(cur, p, withName) {
    const out = {};
    if (!p) return out;
    if (withName && p.name && p.name.trim().toLowerCase() !== String(cur.name || "").trim().toLowerCase()) out.name = p.name;
    if (p.details && !String(cur.details || "").trim()) out.details = p.details;
    if (p.cat && CAT[p.cat] && (!cur.cat || (cur.cat === "outros" && p.cat !== "outros"))) out.cat = p.cat;
    if (p.value > 0 && !(+cur.value > 0)) out.value = p.value;
    return out;
  }
  const webImg = (job, n) => (window.INV_WEB_IMG ? window.INV_WEB_IMG(job, n) : `api/web-photos/${job}/${n}`);
  function webPhotoSearch({ name, details = "", qty = "1", fills = null }) {
    if (!aiOn()) { toast("A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações."); return Promise.resolve(null); }
    return new Promise((resolve) => {
      let job = null, timer = null, chosen = null, results = [], got = null, gen = 0, product = null;
      const entry = openDialog({
        cls: "modal", label: "Buscar foto na internet",
        html: `<div class="dlg"><div class="dlg-h"><h2>Buscar foto na internet</h2><button type="button" class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
          <div class="dlg-b"><form class="wq" data-wq><label class="sr" for="wq">O que buscar</label>
            <input id="wq" class="input" name="q" value="${esc(name)}" maxlength="200" autocomplete="off" enterkeyhint="search">
            <button type="submit" class="btn" data-go>${ic("search")}<span class="lbl">Buscar</span></button></form>
            <div data-slot="web" aria-live="polite"></div></div>
          <div class="dlg-f"><span class="grow"></span><button type="button" class="btn ghost" data-x>Cancelar</button>
            <button type="button" class="btn primary" data-ok disabled>Usar foto</button></div></div>`,
        onClose: () => { gen++; clearTimeout(timer); if (job) API.del(`api/web-photos/${job}`).catch(() => {}); resolve(got); },
      });
      const dlg = entry.dlg, form = $("[data-wq]", dlg), slot = $('[data-slot="web"]', dlg), ok = $("[data-ok]", dlg);
      const show = (html) => { slot.innerHTML = html; };
      const busy = (msg) => show(`<div class="wbusy"><span class="spin lg"></span><p><b>${esc(msg)}</b><span>Pode levar até um minuto.</span></p></div>`);
      async function start() {
        const q = form.q.value.trim();
        if (!q) { form.q.focus(); return; }
        const my = ++gen;
        clearTimeout(timer);
        if (job) { API.del(`api/web-photos/${job}`).catch(() => {}); job = null; }
        chosen = null; results = []; product = null; ok.disabled = true;
        busy("Procurando o produto na internet…");
        try {
          const r = await API.post("api/web-photos", { name: q, details: q === name ? details : "", qty });
          if (my !== gen) return;
          job = r.id;
          poll(my);
        } catch (e) { if (my === gen) show(`<p class="formerr">${esc(e.message)}</p>`); }
      }
      async function poll(my) {
        let st;
        try { st = await API.get(`api/web-photos/${job}`); }
        catch (e) { if (my === gen) show(`<p class="formerr">${esc(e.message)}</p>`); return; }
        if (my !== gen) return;
        if (st.stage === "busy") { busy(st.msg); timer = setTimeout(() => poll(my), 1200); return; }
        product = st.product || null;
        if (st.stage === "error") {
          // sem fotos, os dados que a IA achou ainda servem
          show(`<p class="formerr">${esc(st.msg)}</p>${prodCard(false)}`);
          return;
        }
        results = st.results || [];
        show(`${prodCard(true)}<p class="wsum">${results.length === 1 ? "1 foto encontrada" : `${results.length} fotos encontradas`}.</p>
          <div class="wgrid" role="radiogroup" aria-label="Fotos encontradas">${results.map((x) => `<button type="button" class="wimg" role="radio" aria-checked="false" data-n="${x.n}">
            <img src="${esc(webImg(job, x.n))}" alt="Foto de ${esc(x.site)}" loading="lazy"><span>${esc(x.site)}</span></button>`).join("")}</div>
          <p class="muted wtip">${st.example ? "Exemplo simulado da prévia, com fotos do próprio inventário. " : ""}A foto fica marcada como ilustrativa, com o site de origem.</p>`);
      }
      // o que a IA achou do produto, com o que vai para o item; com foto, dá para desmarcar
      function prodCard(withPhotos) {
        const f = fills ? fills(product) : {};
        const keys = Object.keys(f);
        if (!keys.length) return "";
        const what = keys.map((k) => WEB_FIELDS[k].toLowerCase());
        const list = what.length > 1 ? `${what.slice(0, -1).join(", ")} e ${what[what.length - 1]}` : what[0];
        return `<div class="wprod">
            ${withPhotos ? `<label class="check"><input type="checkbox" data-fill checked> Preencher também ${esc(list)}</label>` : `<p class="wprod-h">A IA achou estes dados do produto</p>`}
            <dl>${keys.map((k) => `<div><dt>${WEB_FIELDS[k]}</dt><dd>${esc(k === "cat" ? CAT[f[k]] : k === "value" ? money(f[k]) : f[k])}</dd></div>`).join("")}</dl>
            <button type="button" class="btn sm" data-only>${withPhotos ? "Usar só os dados, sem foto" : "Usar estes dados"}</button></div>`;
      }
      const wantsFill = () => { const c = $("[data-fill]", dlg); return !!product && (!c || c.checked); };
      async function use() {
        const r = results.find((x) => x.n === chosen);
        if (!r || !job) return;
        ok.disabled = true; ok.innerHTML = `<span class="spin"></span>Salvando`;
        try {
          const res = await fetch(webImg(job, r.n), { cache: "no-store", credentials: "same-origin" });
          if (!res.ok) throw new Error("Esta busca terminou. Busque de novo.");
          const blob = await res.blob();
          const file = await uploadPhoto(new File([blob], `internet.${(blob.type.split("/")[1] || "jpg")}`, { type: blob.type || "image/jpeg" }));
          got = { file, src: r.page || r.image, product: wantsFill() ? product : null };
          requestClose(entry, { force: true });
        } catch (e) { fail(e); ok.disabled = false; ok.textContent = "Usar foto"; }
      }
      form.addEventListener("submit", (e) => { e.preventDefault(); start(); });
      dlg.addEventListener("click", (e) => {
        if (e.target.closest("[data-x]")) { requestClose(entry, { force: true }); return; }
        if (e.target.closest("[data-ok]")) { use(); return; }
        if (e.target.closest("[data-only]") && product) { got = { file: null, src: null, product }; requestClose(entry, { force: true }); return; }
        const t = e.target.closest(".wimg");
        if (t) {
          chosen = +t.dataset.n;
          $$(".wimg", dlg).forEach((b) => b.setAttribute("aria-checked", String(b === t)));
          ok.disabled = false;
        }
      });
      dlg.addEventListener("dblclick", (e) => { if (e.target.closest(".wimg")) use(); });
      start();
    });
  }
  // Novidades do produto: a IA com busca na web traz as 3 mais recentes (atualizações, lançamentos, modelo novo, recalls e
  // fim de suporte), cada uma com a fonte. O resultado fica guardado no servidor: a ficha mostra direto, sem chamar a IA.
  const NEWS_KIND = { atualizacao: "Atualização", lancamento: "Lançamento", sucessor: "Modelo novo", recall: "Recall", suporte: "Fim de suporte", outro: "Novidade" };
  const MES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."];
  const newsDate = (d) => {
    const [y, m, day] = String(d || "").split("-");
    if (!y) return "";
    return day ? `${+day} ${MES[+m - 1]} ${y}` : m ? `${MES[+m - 1]} ${y}` : y;
  };
  function newsListHtml(r, it) {
    const list = (r.news && r.news.novidades) || [], prod = (r.news && r.news.produto) || "";
    return `${list.length ? `<ul class="news">${list.map((x) => `<li>
        <div class="news-meta"><span class="pill${x.tipo === "recall" ? " warn" : ""}">${esc(NEWS_KIND[x.tipo] || "Novidade")}</span>${x.boato ? `<span class="pill">Boato</span>` : ""}${x.data ? `<span class="news-date">${esc(newsDate(x.data))}</span>` : ""}</div>
        <b>${esc(x.titulo)}</b>${x.resumo ? `<p>${esc(x.resumo)}</p>` : ""}
        <a href="${esc(x.fonte)}" target="_blank" rel="noopener noreferrer">${esc(x.site || siteOf(x.fonte))}</a></li>`).join("")}</ul>`
      : `<p class="muted news-none">Nada novo nos últimos 12 meses.</p>`}
      <p class="muted news-foot">${r.example ? "Exemplo simulado da prévia. " : ""}Buscado ${esc(whenShort(r.at))}${prod && norm(prod) !== norm(it.name) ? `, como ${esc(prod)}` : ""}.</p>`;
  }
  // na ficha: o que já foi conferido aparece direto; Novidades (ou Buscar de novo) procura ali mesmo. A busca segue no
  // servidor se a ficha fechar, e o resultado fica guardado.
  const INEWS = { id: null, st: null, gen: 0, timer: null };
  function itemNewsHtml(it) {
    const st = INEWS.id === it.id ? INEWS.st : null;
    const btn = (icon, label) => `<button type="button" class="btn" data-act="item-news" data-id="${esc(it.id)}">${ic(icon)}${label}</button>`;
    if (!st) return btn("spark", "Novidades");
    if (st.busy) return `<div class="wbusy"><span class="spin"></span><p><b>Procurando novidades…</b><span>Pode levar até um minuto.</span></p></div>`;
    return `<h3 class="inews-h">${ic("spark")}Novidades</h3>${st.error ? `<p class="formerr">${esc(st.error)}</p>` : newsListHtml(st.r, it)}${btn("refresh", "Buscar de novo")}`;
  }
  function paintItemNews() {
    const slot = sheet && sheet.itemId === INEWS.id && $('[data-slot="item-news"]', sheet.dlg);
    const it = INEWS.id && D.itemById.get(INEWS.id);
    if (slot && it) slot.innerHTML = itemNewsHtml(it);
  }
  function stopItemNews() { INEWS.gen++; clearTimeout(INEWS.timer); }
  function loadItemNews(it) {
    if (INEWS.id === it.id) { paintItemNews(); return; } // a ficha foi redesenhada: fica como estava
    stopItemNews();
    const my = INEWS.gen;
    const saved = newsOv && newsOv.itens && newsOv.itens[it.id];
    Object.assign(INEWS, { id: it.id, st: saved ? { r: saved } : null });
    paintItemNews();
    API.get(`api/news?item=${encodeURIComponent(it.id)}`).then((r) => {
      if (my !== INEWS.gen) return;
      INEWS.st = r && r.news ? { r } : null;
      paintItemNews();
    }).catch(() => {});
  }
  async function searchItemNews(it) {
    if (!aiOn()) { toast("A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações."); return; }
    stopItemNews();
    const my = INEWS.gen;
    Object.assign(INEWS, { id: it.id, st: { busy: true } });
    paintItemNews();
    const done = (st) => { if (my === INEWS.gen) { INEWS.st = st; paintItemNews(); } };
    let id;
    try { id = (await API.post("api/news", { item: it.id })).id; }
    catch (e) { done({ error: e.message }); return; }
    const poll = async () => {
      if (my !== INEWS.gen) return;
      let st;
      try { st = await API.get(`api/news/${id}`); }
      catch (e) { done({ error: e.message }); return; }
      if (st.stage === "busy") { if (my === INEWS.gen) INEWS.timer = setTimeout(poll, 1200); return; }
      API.del(`api/news/${id}`).catch(() => {});
      if (st.stage === "error") { done({ error: st.msg }); return; }
      const r = { news: st.news, at: new Date().toISOString(), example: !!st.example };
      if (newsOv) { newsOv.itens = { ...(newsOv.itens || {}), [it.id]: r }; renderNews(); }
      done({ r });
    };
    poll();
  }
  function openNews(it) {
    if (!aiOn()) { toast("A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações."); return; }
    let job = null, timer = null, gen = 0;
    const entry = openDialog({
      cls: "modal", label: "Novidades",
      html: `<div class="dlg"><div class="dlg-h"><h2>Novidades</h2><button type="button" class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b"><p class="news-of">${esc(it.name)}</p><div data-slot="news" aria-live="polite"></div></div>
        <div class="dlg-f"><button type="button" class="btn" data-again hidden>${ic("refresh")}Buscar de novo</button><span class="grow"></span>
          <button type="button" class="btn primary" data-item>Ver item</button></div></div>`,
      onClose: () => { gen++; clearTimeout(timer); if (job) API.del(`api/news/${job}`).catch(() => {}); job = null; },
    });
    const dlg = entry.dlg, slot = $('[data-slot="news"]', dlg), again = $("[data-again]", dlg);
    const show = (html, done) => { slot.innerHTML = html; again.hidden = !done; };
    const error = (m) => show(`<p class="formerr">${esc(m)}</p>`, true);
    const render = (r) => show(newsListHtml(r, it), true);
    async function poll(my) {
      let st;
      try { st = await API.get(`api/news/${job}`); }
      catch (e) { if (my === gen) error(e.message); return; }
      if (my !== gen) return;
      if (st.stage === "busy") { timer = setTimeout(() => poll(my), 1200); return; }
      API.del(`api/news/${job}`).catch(() => {});
      job = null;
      if (st.stage === "error") { error(st.msg); return; }
      const r = { news: st.news, at: new Date().toISOString(), example: !!st.example };
      if (newsOv) { newsOv.itens = { ...(newsOv.itens || {}), [it.id]: r }; renderNews(); }
      render(r);
    }
    async function start() {
      const my = ++gen;
      clearTimeout(timer);
      if (job) { API.del(`api/news/${job}`).catch(() => {}); job = null; }
      show(`<div class="wbusy"><span class="spin lg"></span><p><b>Procurando novidades…</b><span>Pode levar até um minuto.</span></p></div>`, false);
      try {
        const r = await API.post("api/news", { item: it.id });
        if (my !== gen) return;
        job = r.id;
        poll(my);
      } catch (e) { if (my === gen) error(e.message); }
    }
    dlg.addEventListener("click", (e) => {
      if (e.target.closest("[data-x]")) { requestClose(entry, { force: true }); return; }
      if (e.target.closest("[data-item]")) { finalizeThen(entry, () => nav(`#/i/${encodeURIComponent(it.id)}`)); return; } // a ficha do item; o Voltar volta para as Novidades
      if (e.target.closest("[data-again]")) start();
    });
    const my0 = gen;
    // o que já foi conferido fica guardado no servidor: abre na hora, sem chamar a IA
    const saved = newsOv && newsOv.itens && newsOv.itens[it.id];
    if (saved) render(saved);
    else API.get("api/news").then((ov) => { newsOv = ov; const r = (ov.itens || {})[it.id]; if (my0 === gen) { if (r) render(r); else start(); } }).catch(() => { if (my0 === gen) start(); });
  }
  async function addWebPhoto(it) {
    // na ficha, o item já existe: os dados da IA só completam o que está vazio (nunca o nome nem um valor já dado)
    const got = await webPhotoSearch({ name: it.name, details: it.details, qty: it.qty, fills: (p) => webFills(D.itemById.get(it.id) || it, p, false) });
    const cur = got && D.itemById.get(it.id);
    if (!cur) return;
    const add = webFills(cur, got.product, false);
    const keys = Object.keys(add);
    if (!got.file && !keys.length) return;
    const before = { photos: [...(cur.photos || [])], photoSrc: { ...(cur.photoSrc || {}) } };
    keys.forEach((k) => { before[k] = cur[k]; });
    const body = { ...add };
    if (got.file) Object.assign(body, { photos: [...before.photos, got.file], photoSrc: { ...before.photoSrc, [got.file]: got.src } });
    try {
      const res = await API.put(`api/items/${encodeURIComponent(cur.id)}`, { ...body, _base: cur.updatedAt });
      setRev(res.rev); upsertItem(res.item); derive(); refreshAll();
      const msg = got.file ? `Foto de ${siteOf(got.src)} adicionada${keys.length ? ", com os dados do produto" : ""}` : "Dados do produto preenchidos";
      toast(msg, { action: "Desfazer", onAction: async () => {
        try {
          const now = D.itemById.get(cur.id);
          const back = await API.put(`api/items/${encodeURIComponent(cur.id)}`, { ...before, _base: now?.updatedAt });
          setRev(back.rev); upsertItem(back.item); derive(); refreshAll();
        } catch (e) { fail(e); }
      } });
    } catch (e) { fail(e); }
  }

  // ------------------------------------------------------------------ detalhe do item
  function showItemSheet(it) {
    const html = itemSheetHtml(it);
    if (sheet) {
      const box = sheet.dlg.querySelector("#toasts");
      sheet.dlg.innerHTML = html;
      if (box) sheet.dlg.append(box);
      sheet.dlg.setAttribute("aria-label", it.name); sheet.itemId = it.id; sheet.closing = false;
    } else {
      sheet = openDialog({ cls: "sheet", html, routed: true, label: it.name });
      sheet.itemId = it.id;
      sheet.onRouteClose = leaveItem;
      sheet.onClose = () => { sheet = null; stopItemNews(); INEWS.id = null; };
    }
    if (newsOn() && it.cat === "eletronicos") loadItemNews(it); // as novidades são só dos eletrônicos
    if (S.resolvia) loadTarefas(it);
  }
  // -- Tarefas no ResolvIA (com Usar equipamentos ligado lá): as abertas ligadas ao item e a Nova tarefa, que entra numa
  // lista do Home Assistant e fica ligada ao item (e ao cômodo) no ResolvIA. O servidor faz as duas coisas.
  const TAREFAS = { id: null, st: null }; // st: {lista: [...]} | {erro} | null (carregando)
  const prazoCurto = (d) => { const x = diaLocal(d); if (!x) return ""; const h = new Date(); h.setHours(0, 0, 0, 0);
    const n = Math.round((x - h) / 864e5); return n === 0 ? "hoje" : n === 1 ? "amanhã" : n < 0 ? `atrasada desde ${dataCurta(d).slice(0, 5)}` : `até ${dataCurta(d).slice(0, 5)}`; };
  function tarefasHtml(it) {
    const st = TAREFAS.id === it.id ? TAREFAS.st : null;
    if (!st) return `<p class="muted">Carregando…</p>`;
    if (st.erro) return `<p class="muted">${esc(st.erro)}</p>`;
    if (!st.lista.length) return `<p class="muted">Nenhuma tarefa aberta.</p>`;
    return `<ul class="tlist">${st.lista.map((t) => `<li><b>${esc(t.tarefa)}</b><span>${esc(t.nome_lista)}${t.prazo ? ` · ${esc(prazoCurto(t.prazo))}` : ""}${t.iguais > 1 ? ` · ${int(t.iguais)} iguais na lista` : ""}</span></li>`).join("")}</ul>`;
  }
  function paintTarefas(it) {
    const el = sheet && sheet.itemId === it.id ? $('[data-slot="tarefas-lista"]', sheet.dlg) : null;
    if (el) el.innerHTML = tarefasHtml(it);
  }
  function loadTarefas(it, again = false) {
    if (TAREFAS.id === it.id && TAREFAS.st && !again) { paintTarefas(it); return; }
    Object.assign(TAREFAS, { id: it.id, st: again ? TAREFAS.st : null });
    paintTarefas(it);
    API.get(`api/resolvia/tarefas?item=${encodeURIComponent(it.id)}`)
      .then((r) => { if (TAREFAS.id === it.id) { TAREFAS.st = { lista: r.tarefas || [] }; paintTarefas(it); } })
      .catch((e) => { if (TAREFAS.id === it.id) { TAREFAS.st = { erro: e.message }; paintTarefas(it); } });
  }
  const PRAZOS = [["", "Sem prazo"], [0, "Hoje"], [1, "Amanhã"], [7, "Em 7 dias"], [30, "Em 30 dias"]];
  const diaMais = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
  function openTarefaNova(it) {
    const entry = openDialog({
      cls: "modal narrow", label: "Nova tarefa no ResolvIA",
      html: `<div class="dlg"><div class="dlg-h"><h2>Nova tarefa</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b" data-tn><div class="form">
          <p class="muted" style="margin:0">${esc(it.name)}</p>
          <div class="field"><label for="tn-nome">Tarefa</label><input id="tn-nome" class="input" name="tarefa" maxlength="255" placeholder="Ex.: Trocar o filtro" autocomplete="off"></div>
          <div class="field"><span class="lbl" id="tn-l-lista">Lista</span>
            <div class="chips grid" role="radiogroup" aria-labelledby="tn-l-lista" data-slot="tn-listas"><p class="muted">Carregando…</p></div></div>
          <div class="field" data-tn-prazo hidden><span class="lbl" id="tn-l-prazo">Prazo</span>
            <div class="chips grid" role="radiogroup" aria-labelledby="tn-l-prazo">${PRAZOS.map(([v, t], k) => `<label class="chip"><input type="radio" name="prazo" value="${v}"${k === 0 ? " checked" : ""}>${t}</label>`).join("")}</div></div>
          <div class="formerr" data-err hidden></div>
        </div></form>
        <div class="dlg-f"><span class="grow"></span><button class="btn ghost" data-x>Cancelar</button><button class="btn primary" data-ok disabled>Criar tarefa</button></div></div>`,
    });
    const form = $("[data-tn]", entry.dlg), err = $("[data-err]", entry.dlg), ok = $("[data-ok]", entry.dlg);
    // as listas como no Nova tarefa do ResolvIA: todas à vista, cada uma com a cor de lá; o prazo só numa lista que aceita
    // prazo, com Controlar prazos ligado lá (o servidor já diz isso em "prazo")
    let listas = [];
    const slot = $('[data-slot="tn-listas"]', entry.dlg);
    const escolhida = () => (form.querySelector('input[name="lista"]:checked') || {}).value || "";
    const prazoOk = () => { const l = listas.find((x) => x.id === escolhida()); $("[data-tn-prazo]", entry.dlg).hidden = !(l && l.prazo); };
    API.get("api/resolvia/listas").then((r) => {
      listas = r.listas || [];
      if (!listas.length) { err.hidden = false; err.textContent = "Nenhuma lista do ResolvIA aceita tarefa nova."; slot.innerHTML = ""; return; }
      const last = listas.some((l) => l.id === LS.get("resolviaLista", "")) ? LS.get("resolviaLista", "") : listas[0].id;
      slot.innerHTML = listas.map((l) => `<label class="chip lchip"${l.cor ? ` style="--c:${esc(l.cor)}"` : ""}><input type="radio" name="lista" value="${esc(l.id)}"${l.id === last ? " checked" : ""}><span class="dot"></span><span>${esc(l.nome)}</span></label>`).join("");
      ok.disabled = false; prazoOk();
    }).catch((e) => { err.hidden = false; err.textContent = e.message; slot.innerHTML = ""; });
    slot.addEventListener("change", prazoOk);
    form.tarefa.addEventListener("input", () => { err.hidden = true; });
    setTimeout(() => form.tarefa.focus(), 50);
    const go = async () => {
      const tarefa = form.tarefa.value.trim();
      if (!tarefa) { err.hidden = false; err.textContent = "Dê um nome à tarefa."; form.tarefa.focus(); return; }
      if (ok.disabled) return;
      const pv = (form.querySelector('input[name="prazo"]:checked') || {}).value || "";
      const lista = escolhida(), l = listas.find((x) => x.id === lista);
      ok.disabled = true;
      try {
        const r = await API.post("api/resolvia/tarefa", { item: it.id, lista, tarefa, prazo: pv !== "" && l && l.prazo ? diaMais(+pv) : "" });
        LS.set("resolviaLista", lista);
        const msg = r.ja_existia ? `${r.tarefa} já estava em ${r.nome_lista}: ${r.ligada === false ? "não consegui ligar a este item" : "agora ligada a este item também"}`
          : r.ligada === false ? `Tarefa criada em ${r.nome_lista}, sem a ligação com o item` : `Tarefa criada em ${r.nome_lista}`;
        finalizeThen(entry, () => { toast(msg); loadTarefas(it, true); });
      } catch (e) { err.hidden = false; err.textContent = e.message; ok.disabled = false; }
    };
    form.addEventListener("submit", (e) => { e.preventDefault(); go(); });
    form.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("input[type=text], input:not([type])") && !e.isComposing) { e.preventDefault(); go(); } });
    entry.dlg.addEventListener("click", (e) => { if (e.target.closest("[data-x]")) requestClose(entry, { force: true }); if (e.target.closest("[data-ok]")) go(); });
  }
  function leaveItem() {
    if (inAppNavs > 0) history.back();
    else location.replace(hashOf(base));
  }
  function galleryHtml(it, i = 0) {
    const ph = it.photos || [];
    const web = (it.photoSrc || {})[ph[i]];
    return `<div class="gal"><button type="button" class="gal-main" data-act="viewer-item" data-id="${esc(it.id)}" data-i="${i}" aria-label="Ampliar foto">
        <img src="${esc(src(ph[i], "photos"))}" alt="Foto de ${esc(it.name)}" decoding="async"></button></div>
      ${web ? `<p class="gal-src">${ic("info", "sm")}<span>Foto ilustrativa de <a href="${esc(web)}" target="_blank" rel="noopener noreferrer">${esc(siteOf(web))}</a></span></p>` : ""}
      ${ph.length > 1 ? `<div class="gal-thumbs">${ph.map((p, k) => `<button type="button" data-act="gal" data-id="${esc(it.id)}" data-i="${k}" aria-current="${k === i}" aria-label="Foto ${k + 1}"><img src="${esc(src(p))}" alt=""></button>`).join("")}</div>` : ""}`;
  }
  function itemSheetHtml(it) {
    const room = D.roomById.get(it.room) || { id: it.room, code: "?", name: it.room };
    const n = qtyNum(it.qty);
    const by = (who) => (who ? ` <span class="by">por ${esc(who)}</span>` : "");
    const lbl = (icon, text) => `${ic(icon)}<span class="lbl">${text}</span>`;
    return `<div class="dlg">
      <div class="dlg-h"><span class="mt">${esc(tagOf(it))}</span><h2 class="sr">${esc(it.name)}</h2><span style="flex:1"></span>
        ${aiOn() ? `<button type="button" class="btn ghost icon" data-act="chat" aria-label="Conversar sobre este item" title="Conversar">${ic("chat")}</button>` : ""}
        <button type="button" class="btn ghost icon" data-act="sheet-close" aria-label="Fechar">${ic("close")}</button></div>
      <div class="dlg-b">
        <div data-slot="gallery">${(it.photos || []).length ? galleryHtml(it, 0)
          : `<div class="gal"><div class="gal-none">${ic("image", "lg")}<span>Sem foto</span><div class="gal-acts">
              <button type="button" class="btn sm" data-act="item-edit" data-id="${esc(it.id)}">${ic("plus", "sm")}Adicionar foto</button>
              ${aiOn() ? `<button type="button" class="btn sm" data-act="web-photo" data-id="${esc(it.id)}">${ic("search", "sm")}Buscar na internet</button>` : ""}</div></div></div>`}</div>
        <div class="ihead"><h1>${esc(it.name)}</h1>
          <div class="ival"><span class="big">${money(vl(it))}</span>${n && n > 1 ? `<span class="unit">${int(n)} unidades, ${money(vl(it) / n)} cada</span>` : qtyClean(it.qty) !== "1" ? `<span class="unit">${esc(qtyLabel(it.qty))}</span>` : ""}
            ${deprecOn() && +it.value && Math.abs(vl(it) - it.value) >= 0.005 ? `<span class="unit" data-slot="valor-gravado">${esc(`${money(+it.value)} em ${dataCurta(it.valueAt || it.createdAt)}, ${taxaTxt(taxaDe(it))} ao ano`)}</span>` : ""}</div></div>
        ${it.details ? `<p class="idet">${esc(it.details)}</p>` : ""}
        ${it.flag ? `<p class="inote">${ic("info")}<span>${esc(it.flag)}</span></p>` : ""}
        <dl class="props">
          <dt>${room.kind === "bens" ? "Onde" : "Cômodo"}</dt><dd><a href="${room.kind === "bens" ? "#/bens" : `#/c/${encodeURIComponent(room.id)}`}"><span class="mt soft">${esc(room.code)}</span><span class="rnm">${esc(room.name)}</span></a></dd>
          ${zonesOn() ? `<dt>Zona</dt><dd>${esc(it.zone || "Sem zona")}</dd>` : ""}
          <dt>Categoria</dt><dd><a href="#/buscar?cat=${esc(CAT[it.cat] ? it.cat : "outros")}&amp;ord=val"><span class="rnm">${esc(CAT[it.cat] || "Outros")}</span></a></dd>
          <dt>Quantidade</dt><dd>${esc(qtyLabel(it.qty))}</dd>
          <dt>Origem</dt><dd>${esc(SOURCES[it.source] || "Cadastro manual")}</dd>
          ${it.createdAt ? `<dt>Cadastrado</dt><dd>${esc(dateTime(it.createdAt))}${by(it.createdBy)}</dd>` : ""}
          ${it.updatedAt && it.updatedAt !== it.createdAt ? `<dt>Alterado</dt><dd>${esc(dateTime(it.updatedAt))}${by(it.updatedBy)}</dd>` : ""}
        </dl>
        ${S.resolvia ? `<div class="inews itasks" data-slot="item-tarefas">
          <h3 class="inews-h">${ic("checks")}Tarefas no ResolvIA</h3>
          <div data-slot="tarefas-lista" aria-live="polite">${tarefasHtml(it)}</div>
          <button type="button" class="btn" data-act="tarefa-nova" data-id="${esc(it.id)}">${ic("plus")}Nova tarefa</button></div>` : ""}
        ${newsOn() && it.cat === "eletronicos" ? `<div class="inews" data-slot="item-news" aria-live="polite">${itemNewsHtml(it)}</div>` : ""}
      </div>
      <div class="dlg-f">
        <button type="button" class="btn danger" data-act="item-delete" data-id="${esc(it.id)}" aria-label="Apagar">${lbl("trash", "Apagar")}</button>
        <span class="grow"></span>
        <button type="button" class="btn" data-act="item-move" data-id="${esc(it.id)}" aria-label="Mover">${lbl("move", "Mover")}</button>
        <button type="button" class="btn" data-act="item-dup" data-id="${esc(it.id)}" aria-label="Duplicar">${lbl("copy", "Duplicar")}</button>
        <button type="button" class="btn primary" data-act="item-edit" data-id="${esc(it.id)}">${ic("edit")}Editar</button>
      </div></div>`;
  }

  async function deleteItem(it) {
    const ok = await confirmBox({ title: "Apagar este item?", body: `<b>${esc(it.name)}</b> sai do inventário. Dá para desfazer logo em seguida.`, ok: "Apagar", danger: true });
    if (!ok) return;
    try {
      const res = await API.del(`api/items/${encodeURIComponent(it.id)}`);
      setRev(res.rev);
      removeItem(it.id);
      derive();
      if (sheet && sheet.itemId === it.id) requestClose(sheet, { force: true });
      refreshAll();
      toast("Item apagado", {
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
    const zones = zonesOn();
    const zonesFor = (rid) => zonesOf(rid).map((z) => `<option value="${esc(z)}">`).join("");
    const entry = openDialog({
      cls: "modal narrow", label: "Mover item",
      html: `<div class="dlg"><div class="dlg-h"><h2>Mover item</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b" data-mv><div class="form">
          <p class="muted" style="margin:0">${esc(it.name)}</p>
          <div class="field"><label for="mv-room">Para o cômodo</label><select id="mv-room" class="select" name="room">${roomOptions(it.room)}</select>
            ${zones ? "" : `<p class="help">Em outro cômodo, o item ganha um código novo.</p>`}</div>
          ${zones ? `<div class="field"><label for="mv-zone">Zona</label><input id="mv-zone" class="input" name="zone" data-sug="mv-zones" value="${esc(it.zone || "")}" autocomplete="off"><datalist id="mv-zones">${zonesFor(it.room)}</datalist>
            <p class="help">Em outro cômodo, o item ganha um código novo.</p></div>` : ""}
        </div></form>
        <div class="dlg-f"><span class="grow"></span><button class="btn ghost" data-x>Cancelar</button><button class="btn primary" data-ok>${ic("move")}Mover</button></div></div>`,
    });
    const form = $("[data-mv]", entry.dlg);
    if (zones) form.room.addEventListener("change", () => { $("#mv-zones", entry.dlg).innerHTML = zonesFor(form.room.value); if (form.room.value !== it.room) form.zone.value = ""; });
    const go = async () => {
      const moved = form.room.value !== it.room;
      if (!zones && !moved) { requestClose(entry, { force: true }); toast(`O item já está em ${D.roomById.get(it.room)?.name || "este cômodo"}.`); return; }
      // sem zonas, a zona do cômodo antigo não vai junto (ela não faria sentido no cômodo novo)
      const zone = zones ? form.zone.value : "";
      try {
        const res = await API.put(`api/items/${encodeURIComponent(it.id)}`, { room: await realRoom(form.room.value), zone, _base: it.updatedAt });
        setRev(res.rev); upsertItem(res.item); derive(); requestClose(entry, { force: true }); refreshAll();
        const before = { room: it.room, zone: it.zone || "", seq: it.seq };
        toast(res.item.room !== it.room ? `Movido para ${D.roomById.get(res.item.room)?.name}` : "Zona atualizada", { action: "Desfazer", onAction: async () => {
          try {
            const back = await API.put(`api/items/${encodeURIComponent(it.id)}`, { ...before, _base: res.item.updatedAt });
            setRev(back.rev); upsertItem(back.item); derive(); refreshAll();
          } catch (er) { fail(er); }
        } });
      } catch (e) { fail(e); }
    };
    form.addEventListener("submit", (e) => { e.preventDefault(); go(); });
    entry.dlg.addEventListener("click", (e) => { if (e.target.closest("[data-x]")) requestClose(entry, { force: true }); if (e.target.closest("[data-ok]")) go(); });
  }

  // ------------------------------------------------------------------ editor de item
  function openEditor({ item = null, dup = null, room = null, zone = null, photos = null } = {}) {
    if (!D.rooms.length) { toast("Crie um cômodo antes de adicionar itens."); openRoomNew(); return; }
    const from = item || dup || {};
    const rid = from.room || (room && (D.roomById.has(room) || room === BENS_NEW) ? room : lastRoom());
    const F = {
      id: item ? item.id : null, base: item ? item.updatedAt : null,
      name: from.name || "", details: from.details || "", room: rid,
      // sem zonas, item novo nasce sem zona; um item existente guarda a dele, escondida
      zone: item ? item.zone || "" : !zonesOn() ? "" : from.zone != null ? from.zone : zone != null ? zone : LS.get("lastZone:" + rid, "") || "",
      cat: from.cat || "", qty: from.qty ? qtyClean(from.qty) : "1", value: from.value ? moneyInput(from.value) : "",
      flag: from.flag || "", photos: [...(from.photos || photos || [])], photoSrc: { ...(from.photoSrc || {}) },
      source: item ? item.source || "manual" : dup ? dup.source || "manual" : "manual",
      dirty: !!(dup || (photos && photos.length)), busy: false, uploading: 0, aiBusy: false, hint: "",
    };
    // um bem (casa, terreno, carro) não tem cômodo, zona nem a lista de categorias da casa: só o tipo (Imóvel, Veículo
    // ou Outro, os grupos de Mais > Bens). Para levar um bem a um cômodo, Mover.
    const bem = isBens(rid), what = bem ? "bem" : "item";
    const title = item ? `Editar ${what}` : dup ? `Duplicar ${what}` : `Novo ${what}`;
    const saveLbl = F.id ? "Salvar alterações" : `Salvar ${what}`;
    const otherCat = BENS_GROUPS.some(([k]) => k && k === F.cat) ? "outros" : F.cat || "outros"; // Outro guarda a categoria de um item que veio de um cômodo
    const tipoBtns = () => BENS_GROUPS.map(([k, name]) => { const on = (k || "") === bensGroup(F); return `<button type="button" data-ed="tipo" data-v="${k}" aria-pressed="${on}">${{ imoveis: "Imóvel", veiculos: "Veículo" }[k] || "Outro"}</button>`; }).join("");
    const roomField = `<div class="field"><label for="f-room">Cômodo</label><select id="f-room" class="select" name="room">${roomOptions(F.room)}</select></div>`;
    const zoneField = `<div class="field"><label for="f-zone">Zona</label><input id="f-zone" class="input" name="zone" data-sug="f-zones" maxlength="120" autocomplete="off" value="${esc(F.zone)}" placeholder="Ex.: Estante, Bancada"><datalist id="f-zones"></datalist></div>`;
    const entry = openDialog({
      cls: "modal", label: title,
      html: `<div class="dlg">
        <div class="dlg-h"><h2>${title}</h2><button type="button" class="btn ghost icon" data-ed="cancel" aria-label="Fechar">${ic("close")}</button></div>
        <form class="dlg-b drop" data-ed-form novalidate autocomplete="off">
          <div class="form">
            <div class="field"><span class="lbl">Fotos</span><div class="phs" data-slot="photos"></div>
              ${COARSE ? "" : `<p class="help">Também dá para arrastar ou colar (Ctrl+V).</p>`}</div>
            ${aiOn() ? `<div class="aibox" data-slot="ai"></div>` : ""}
            <div class="field"><label for="f-name">Nome</label><input id="f-name" class="input" name="name" maxlength="200" value="${esc(F.name)}" placeholder="${bem ? "Ex.: Apartamento na praia" : "Ex.: Cafeteira Nespresso Inissia"}" enterkeyhint="next">
              <p class="err" data-err="name" hidden></p></div>
            <div class="field"><label for="f-details">Detalhes</label><textarea id="f-details" class="textarea" name="details" rows="3" maxlength="4000" placeholder="${bem ? "Endereço, modelo, ano e estado" : "Marca, modelo, cor, tamanho e estado"}">${esc(F.details)}</textarea></div>
            ${bem ? `<div class="field"><span class="lbl" id="f-tipo-l">Tipo</span><div class="seg tipo" role="group" aria-labelledby="f-tipo-l" data-slot="tipo">${tipoBtns()}</div></div>`
              : `${zonesOn() ? `<div class="row2">${roomField}${zoneField}</div>` : roomField}
            <div class="field"><label for="f-cat">Categoria</label><select id="f-cat" class="select" name="cat"><option value="">Escolha a categoria</option>${CATS.map(([k, v]) => `<option value="${k}"${k === F.cat ? " selected" : ""}>${esc(v)}</option>`).join("")}</select></div>`}
            <div class="row3">
              <div class="field"><label for="f-qty">Quantidade</label><input id="f-qty" class="input" name="qty" maxlength="30" value="${esc(F.qty)}" inputmode="text"></div>
              <div class="field"><label for="f-value">Valor total</label><div class="money"><input id="f-value" class="input" name="value" inputmode="decimal" value="${esc(F.value)}" placeholder="0"></div>
                <p class="unit-hint" data-slot="unit"></p><p class="err" data-err="value" hidden></p></div>
            </div>
            <details class="more-fields"${F.flag ? " open" : ""}><summary>${ic("chev", "sm")}Observação</summary>
              <div class="form"><div class="field"><label for="f-flag" class="sr">Observação</label><input id="f-flag" class="input" name="flag" maxlength="200" value="${esc(F.flag)}" placeholder="Algo para lembrar sobre este item"></div></div></details>
            <div class="formerr" data-slot="formerr" hidden></div>
          </div>
        </form>
        <div class="dlg-f">
          ${F.id ? "" : `<button type="button" class="btn" data-ed="again">Salvar e adicionar outro</button>`}
          <span class="grow"></span>
          <button type="button" class="btn ghost hide-narrow" data-ed="cancel">Cancelar</button>
          <button type="button" class="btn primary" data-ed="save">${saveLbl}</button>
        </div></div>`,
      guard: async () => !F.dirty || confirmBox({ title: "Descartar o que foi preenchido?", ok: "Descartar", cancel: "Continuar editando", danger: true }),
    });
    const dlg = entry.dlg;
    const form = $("[data-ed-form]", dlg);
    const slot = (n) => $(`[data-slot="${n}"]`, dlg);
    entry.onSubmit = () => save(false);

    const renderZones = () => { const dl = $("#f-zones", dlg); if (dl) dl.innerHTML = zonesOf(F.room).map((z) => `<option value="${esc(z)}">`).join(""); };
    const renderUnit = () => {
      const n = qtyNum(F.qty), v = parseMoney(F.value);
      slot("unit").textContent = n && n > 1 && v > 0 ? `${money(v / n)} cada` : "";
    };
    const renderPhotos = () => {
      const hasRoomPhotos = (D.roomById.get(F.room)?.photos || []).some((p) => !F.photos.includes(p.file));
      slot("photos").innerHTML = F.photos.map((f, i) => `<div class="ph"><img src="${esc(src(f))}" alt="Foto ${i + 1}">
          ${F.photoSrc[f] ? `<span class="web" title="Foto ilustrativa de ${esc(siteOf(F.photoSrc[f]))}">Internet</span>` : ""}
          ${i === 0 ? `<span class="cover">Capa</span>` : `<button type="button" class="mkcover" data-ed="cover" data-i="${i}">Usar como capa</button>`}
          <button type="button" class="x" data-ed="rmphoto" data-i="${i}" aria-label="Remover foto ${i + 1}">${ic("close")}</button></div>`).join("")
        + Array.from({ length: F.uploading }, () => `<div class="ph loading"><span class="spin lg"></span></div>`).join("")
        + (CAMERA ? `<button type="button" class="add" data-ed="camera">${ic("camera")}Tirar foto</button>` : "")
        + `<button type="button" class="add" data-ed="upload">${ic(COARSE ? "image" : "upload")}Escolher fotos</button>`
        + (hasRoomPhotos ? `<button type="button" class="add" data-ed="roomphotos">${ic("images")}Fotos do cômodo</button>` : "")
        + (F.photos.length < 12 && aiOn() ? `<button type="button" class="add" data-ed="web">${ic("search")}Buscar na internet</button>` : "");
      renderAi();
    };
    const renderAi = async () => {
      const box = slot("ai");
      if (!box) return;
      if (F.aiBusy) {
        box.innerHTML = `<div class="aih"><p><b>Lendo a foto…</b> Pode levar até um minuto.</p><button type="button" class="btn" disabled><span class="spin"></span>Lendo</button></div>`;
        return;
      }
      if (!F.photos.length) {
        box.innerHTML = `<div class="aih"><p>${ic("scan", "sm")} Com uma foto, a IA preenche os campos.</p></div>`;
        return;
      }
      box.innerHTML = `<div class="aih"><p>A IA lê a primeira foto e preenche os campos.</p>
          <button type="button" class="btn" data-ed="ai">${ic("scan")}Digitalizar com IA</button></div>
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
      b.innerHTML = on ? `<span class="spin"></span>Salvando` : saveLbl;
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
      if (e.target.name === "room") {
        F.room = e.target.value;
        if (form.zone && !item) { F.zone = LS.get("lastZone:" + F.room, "") || ""; form.zone.value = F.zone; } // a zona lembrada é a deste cômodo
        renderZones(); renderPhotos();
      }
      if (e.target.name === "value" && !Number.isNaN(parseMoney(F.value))) { F.value = moneyInput(parseMoney(F.value)); e.target.value = F.value; }
    });
    form.addEventListener("submit", (e) => { e.preventDefault(); save(false); });
    form.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("[data-ed-hint]")) { e.preventDefault(); runAi(); } });

    const addFiles = async (files) => {
      const all = [...(files || [])], imgs = imageFiles(all);
      if (imgs.length < all.length) toast(all.length - imgs.length === 1 && all.length === 1 ? "Escolha um arquivo de imagem (JPG ou PNG)." : `${plural(all.length - imgs.length, "arquivo não é imagem e ficou", "arquivos não são imagens e ficaram")} de fora.`, { error: true });
      const room = 12 - F.photos.length - F.uploading;
      if (imgs.length > room) toast(room > 0 ? `Até 12 fotos por item: ${plural(imgs.length - room, "ficou de fora", "ficaram de fora")}.` : "O item já tem 12 fotos, o máximo.", { error: true });
      files = imgs.slice(0, Math.max(0, room));
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
        const emptyVal = !String(F.value || "").trim() || parseMoney(F.value) === 0;
        Object.assign(F, { name: r.name || F.name, details: F.details.trim() ? F.details : r.details || "", cat: F.cat && F.cat !== "outros" ? F.cat : r.cat || F.cat,
          qty: qtyClean(F.qty) !== "1" ? F.qty : r.qty || F.qty, value: emptyVal && r.value ? moneyInput(r.value) : F.value, zone: zonesOn() ? F.zone || r.zone || "" : F.zone, source: "ia", dirty: true });
        fill();
        toast(res.example ? "Exemplo simulado da prévia: no Home Assistant, a IA lê a foto de verdade." : "Campos preenchidos pela IA. Confira antes de salvar.", { action: "Desfazer", onAction: () => { Object.assign(F, prev); if (document.contains(dlg)) fill(); } });
      } catch (e) { fail(e); }
      finally { F.aiBusy = false; if (document.contains(dlg)) renderAi(); }
    }
    function fill() {
      form.name.value = F.name; form.details.value = F.details;
      if (form.cat) form.cat.value = CAT[F.cat] ? F.cat : "";
      if (bem) slot("tipo").innerHTML = tipoBtns();
      form.qty.value = F.qty; form.value.value = F.value; form.flag.value = F.flag;
      if (form.zone) form.zone.value = F.zone;
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
      // sem zonas, a zona escondida só fica se o item continuar no mesmo cômodo
      const zone = zonesOn() ? F.zone.trim() : item && F.room === item.room ? item.zone || "" : "";
      const body = { name, details: F.details.trim(), room: F.room, zone, cat: F.cat || "outros", qty: F.qty.trim() || "1", value, photos: F.photos, photoSrc: F.photoSrc, flag: F.flag.trim(), source: F.source };
      setBusy(true);
      try {
        body.room = F.room = await realRoom(F.room); // o primeiro bem cria a área Bens
        const res = F.id
          ? await API.put(`api/items/${encodeURIComponent(F.id)}`, { ...body, _base: F.base })
          : await API.post("api/items", body);
        setRev(res.rev); upsertItem(res.item); derive();
        LS.set("lastRoom", res.item.room); if (zonesOn()) LS.set("lastZone:" + res.item.room, res.item.zone || "");
        refreshAll();
        if (again) {
          Object.assign(F, { name: "", details: "", qty: "1", value: "", flag: "", photos: [], photoSrc: {}, source: "manual", hint: "", dirty: false });
          fill(); renderPhotos();
          form.name.focus();
          toast(`${res.item.name} adicionado`);
        } else {
          F.dirty = false;
          requestClose(entry, { force: true });
          if (F.id) toast("Alterações salvas");
          else toast(isBens(res.item.room) ? "Bem adicionado" : "Item adicionado", { action: "Ver", onAction: () => nav(`#/i/${encodeURIComponent(res.item.id)}`) });
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
      else if (act === "tipo") { F.cat = b.dataset.v || otherCat; F.dirty = true; slot("tipo").innerHTML = tipoBtns(); }
      else if (act === "save") save(false);
      else if (act === "again") save(true);
      else if (act === "upload") pickFiles(addFiles);
      else if (act === "camera") camera(addFiles, { max: 12 - F.photos.length, title: "Fotos do item" });
      else if (act === "roomphotos") { const chosen = await roomPhotoPicker(F.room, F.photos); if (chosen.length) { F.photos.push(...chosen.slice(0, 12 - F.photos.length)); F.dirty = true; renderPhotos(); } }
      else if (act === "web") {
        const q = F.name.trim();
        if (!q) { fieldErr("name", "Escreva o nome do item para buscar a foto."); form.name.focus(); return; }
        // num item novo, o nome também vem da IA (com marca e modelo); o resto, só o que está vazio
        const cur = () => ({ name: F.name, details: F.details, cat: F.cat, value: parseMoney(F.value) || 0 });
        const got = await webPhotoSearch({ name: q, details: F.details.trim(), qty: F.qty.trim() || "1", fills: (p) => webFills(cur(), p, !F.id) });
        if (!got || !document.contains(dlg)) return;
        if (got.file && F.photos.length < 12) { F.photos.push(got.file); F.photoSrc = { ...F.photoSrc, [got.file]: got.src }; F.dirty = true; renderPhotos(); }
        const add = webFills(cur(), got.product, !F.id);
        if (Object.keys(add).length) {
          const prev = { name: F.name, details: F.details, cat: F.cat, value: F.value, source: F.source };
          Object.assign(F, add, add.value ? { value: moneyInput(add.value), source: "ia" } : {}, { dirty: true });
          fill();
          toast(got.file ? "Foto e dados do produto preenchidos. Confira antes de salvar." : "Dados do produto preenchidos. Confira antes de salvar.",
            { action: "Desfazer", onAction: () => { Object.assign(F, prev); if (document.contains(dlg)) fill(); } });
        }
      }
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

  // ------------------------------------------------------------------ Falar (como no ResolvIA e no CronologIA)
  // Grava o microfone como PCM cru, 16 kHz, 16 bits, mono (o que a fala para texto do Home Assistant recebe,
  // igual ao Assist), com o volume para a tela. O servidor manda para a fala para texto e a IA separa os itens.
  const VOICE_RATE = 16000, VOICE_MAX_S = 120;
  class Recorder {
    constructor(onLevel) { this.onLevel = onLevel; this.chunks = []; this.length = 0; this.rate = VOICE_RATE; }
    async start() {
      const md = navigator.mediaDevices;
      if (!md || !md.getUserMedia) throw Object.assign(new Error("no_api"), { name: "NoApi" });
      this.stream = await md.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      const AC = window.AudioContext || window.webkitAudioContext;
      try { this.ctx = new AC({ sampleRate: VOICE_RATE }); } catch { this.ctx = new AC(); } // alguns só gravam na taxa deles: ajusta no fim
      if (this.ctx.state === "suspended") await this.ctx.resume().catch(() => {});
      this.rate = this.ctx.sampleRate;
      this.src = this.ctx.createMediaStreamSource(this.stream);
      this.node = this.ctx.createScriptProcessor(4096, 1, 1);
      this.node.onaudioprocess = (e) => {
        const data = e.inputBuffer.getChannelData(0);
        this.chunks.push(new Float32Array(data));
        this.length += data.length;
        let sum = 0;
        for (let i = 0; i < data.length; i += 4) sum += data[i] * data[i];
        if (this.onLevel) this.onLevel(Math.min(1, Math.sqrt(sum / (data.length / 4)) * 5));
      };
      this.src.connect(this.node);
      this.node.connect(this.ctx.destination); // a saída fica muda; só mantém o nó rodando
    }
    seconds() { return this.length / this.rate; }
    stop() { // para e devolve o áudio: PCM Int16 a 16 kHz
      this.close();
      const all = new Float32Array(this.length);
      let o = 0;
      for (const c of this.chunks) { all.set(c, o); o += c.length; }
      this.chunks = [];
      const ratio = this.rate / VOICE_RATE, n = Math.floor(all.length / ratio), out = new Int16Array(n);
      for (let i = 0; i < n; i++) { // média de cada janela: um filtro simples quando o navegador gravou a 44,1/48 kHz
        const a = Math.floor(i * ratio), b = Math.max(a + 1, Math.min(all.length, Math.floor((i + 1) * ratio)));
        let sum = 0;
        for (let j = a; j < b; j++) sum += all[j];
        const v = Math.max(-1, Math.min(1, sum / (b - a)));
        out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
      }
      return out;
    }
    cancel() { this.close(); this.chunks = []; this.length = 0; }
    close() {
      try { if (this.node) this.node.onaudioprocess = null; if (this.src) this.src.disconnect(); if (this.node) this.node.disconnect(); } catch { /* já fechado */ }
      if (this.stream) for (const t of this.stream.getTracks()) t.stop();
      if (this.ctx && this.ctx.state !== "closed") this.ctx.close().catch(() => {});
      this.stream = null; this.node = null; this.src = null;
    }
  }
  function micError(err) {
    const n = (err && err.name) || "";
    if (n === "NotAllowedError" || n === "SecurityError") return "O microfone está bloqueado. Permita o microfone para o Home Assistant (no navegador, no cadeado ao lado do endereço; no app do celular, nas permissões do app Home Assistant) e tente de novo.";
    if (n === "NotFoundError" || n === "OverconstrainedError") return "Não achei um microfone neste aparelho.";
    if (n === "NotReadableError") return "O microfone está sendo usado por outro app. Feche o outro e tente de novo.";
    if (n === "NoApi") return "Este navegador não deixa usar o microfone aqui. Abra o Home Assistant pelo endereço com https (como o do Home Assistant Cloud) ou pelo app.";
    return `Não consegui abrir o microfone (${(err && err.message) || n || "erro"}).`;
  }
  async function loadVoice(fresh = false) {
    try { S.voice = await API.get(`api/voice/status${fresh ? "?fresh=1" : ""}`); } catch (e) { S.voice = { ready: false, reason: e.message }; }
    renderTop();
    const slot = $('#view [data-slot="voice-panel"]'); // Integrações aberta antes da resposta: não fica em "Verificando…"
    if (slot) renderVoicePanel(slot);
  }
  function renderVoicePanel(slot) {
    const v = S.voice, engines = (v && v.engines) || [], sel = (v && v.selected) || "";
    // quem transcreve é a fala para texto; o assistente de voz só diz qual é o padrão (o nome dele não é quem transcreve)
    const using = v && v.ready ? `Transcreve com ${esc(v.name || v.engine)} (${esc(v.language || "pt-BR")})${!sel && v.assistant ? `, do assistente ${esc(v.assistant)}` : ""}.` : "";
    slot.innerHTML = `<ul class="opts"><li><div class="ot"><b><span class="status ${v && v.ready ? "ok" : "bad"}"><i></i>${v && v.ready ? "Pronto para ouvir" : v ? "Sem fala para texto" : "Verificando…"}</span></b>
        <span>${v && v.ready ? `${using}${v.missing ? " A escolhida saiu do Home Assistant: usando o padrão." : ""}` : esc((v && v.reason) || "")}</span></div>
      <div class="oa"><button class="btn" data-act="voice-refresh">${ic("refresh")}Verificar de novo</button></div></li>
      ${engines.length ? `<li><div class="ot"><b id="voice-stt-l">Fala para texto</b><span>Padrão do Home Assistant usa a do assistente de voz preferido.</span></div>
        <div class="oa"><select class="select" data-input="voice-stt" aria-labelledby="voice-stt-l">
          <option value="">Padrão do Home Assistant</option>
          ${engines.map((e) => `<option value="${esc(e.id)}"${e.id === sel ? " selected" : ""}>${esc(e.name)}</option>`).join("")}
        </select></div></li>` : ""}</ul>`;
  }
  const voiceReady = () => aiOn() && !!(S.voice && S.voice.ready); // com Usar IA desligada, o Falar some junto
  const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  // sem uma IA que responda (ligada, mas sem entidade): separa o que foi dito pelas vírgulas, pontos e "e". Um pedaço que é só valor ("2.000 reais", "500")
  // vira o valor do item anterior; "TV Samsung R$ 3.000" fica TV Samsung com 3.000. Valor por extenso
  // ("dois mil reais", "três mil", "mil e duzentos reais") vira número antes; "duas luminárias" fica como está.
  const VALUE_WORDS = new Set(("uns umas um uma cerca de por vale valor custou paguei mais ou menos aproximadamente uns e r$ reais real mil centavos " +
    "dois duas três tres quatro cinco seis sete oito nove dez onze doze treze quatorze catorze quinze dezesseis dezessete dezoito dezenove vinte trinta " +
    "quarenta cinquenta sessenta setenta oitenta noventa cem cento duzentos duzentas trezentos trezentas quatrocentos quinhentos seiscentos setecentos oitocentos novecentos").split(" "));
  const isValueBit = (x) => /\d|\b(?:reais|real|mil)\b/i.test(x) && x.toLowerCase().replace(/r\$/g, " r$ ").split(/\s+/).filter(Boolean).every((w) => /^[\d.,]+$/.test(w) || VALUE_WORDS.has(w));
  const TAIL_VALUE = /\s*(?:r\$\s*\d[\d.]*(?:,\d+)?(?:\s*mil)?|\d[\d.]*(?:,\d+)?(?:\s*mil)?\s*(?:reais|real))\s*$/i;
  const NUM_WORDS = { um: 1, uma: 1, dois: 2, duas: 2, "três": 3, tres: 3, quatro: 4, cinco: 5, seis: 6, sete: 7, oito: 8, nove: 9, dez: 10, onze: 11, doze: 12,
    treze: 13, quatorze: 14, catorze: 14, quinze: 15, dezesseis: 16, dezessete: 17, dezoito: 18, dezenove: 19, vinte: 20, trinta: 30, quarenta: 40,
    cinquenta: 50, sessenta: 60, setenta: 70, oitenta: 80, noventa: 90, cem: 100, cento: 100, duzentos: 200, duzentas: 200, trezentos: 300,
    trezentas: 300, quatrocentos: 400, quatrocentas: 400, quinhentos: 500, quinhentas: 500, seiscentos: 600, seiscentas: 600, setecentos: 700,
    setecentas: 700, oitocentos: 800, oitocentas: 800, novecentos: 900, novecentas: 900, mil: 1000 };
  const NUM_W = Object.keys(NUM_WORDS).sort((a, b) => b.length - a.length).join("|");
  const NUM_RUN = new RegExp(`(?<!\\p{L})(?<!\\d[.,]?\\s*)(?:${NUM_W})(?:\\s+(?:e\\s+)?(?:${NUM_W}))*(?!\\p{L})(?=(\\s*(?:reais|real)(?!\\p{L}))?)`, "giu");
  const wordsToNumbers = (t) => String(t).replace(NUM_RUN, (run, money) => {
    const toks = run.split(/\s+/);
    let end = toks.length; // "três mil e duas luminárias": o "e duas" já é outro item
    if (!money) for (let i = 1; i < toks.length - 1; i++) if (toks[i].toLowerCase() === "e" && NUM_WORDS[toks[i + 1].toLowerCase()] < 10) { end = i; break; }
    const ws = toks.slice(0, end).map((w) => w.toLowerCase()).filter((w) => w !== "e");
    if (!money && !ws.some((w) => NUM_WORDS[w] >= 100)) return run; // "duas luminárias", "um sofá": quantidade, não valor
    let total = 0, cur = 0;
    for (const w of ws) { if (w === "mil") { total += (cur || 1) * 1000; cur = 0; } else cur += NUM_WORDS[w]; }
    return [String(total + cur), ...toks.slice(end)].join(" ");
  });
  const valueOf = (t) => {
    const m = String(t).match(/\d[\d.]*(?:,\d+)?/);
    if (!m) return 0;
    let v = parseFloat(m[0].replace(/\.(?=\d{3}\b)/g, "").replace(",", ".")) || 0;
    if (/\bmil\b/i.test(t) && v < 1000) v *= 1000;
    return v;
  };
  function splitSpoken(t) {
    const out = [];
    for (const raw of wordsToNumbers(t || "").split(/\s*(?:[;\n]|(?<!\d),|,(?!\d)|\.(?:\s|$)|\s+e\s+)\s*/i)) { // a vírgula do "2.499,90" fica
      let x = raw.trim().replace(/\.$/, "").replace(/^e\s+/i, "").trim();
      if (x.length < 2) continue;
      const prev = out[out.length - 1];
      if (prev && isValueBit(x)) {
        const v = valueOf(x);
        if (v) prev.value = v; else prev.details = prev.details ? `${prev.details}; ${x}` : x;
        continue;
      }
      let value = 0;
      const tail = x.match(TAIL_VALUE);
      if (tail && tail.index > 0) {
        value = valueOf(tail[0]);
        // "cafeteira por 499 reais", "tapete de uns 300 reais": a ligação antes do valor não faz parte do nome
        x = x.slice(0, tail.index).trim().replace(/(?:\s+(?:que|por|de|uns|umas|um|uma|cerca|vale|valor|custou|paguei|mais ou menos|aproximadamente))+$/i, "").trim();
      }
      if (out.length < 25) out.push({ name: x.charAt(0).toUpperCase() + x.slice(1), details: "", cat: "outros", qty: "1", value, zone: "", existing: "", confidence: "media", on: true });
    }
    return out;
  }

  // ------------------------------------------------------------------ conversar com a IA (ao lado do microfone, em qualquer tela)
  // A conversa fica até fechar o app. Cada pergunta leva onde a pessoa está (o item, o cômodo, a busca) e o servidor junta os dados.
  const CHAT = { msgs: [], busy: false };
  function chatScreen() {
    const sc = { view: base.name };
    if (sheet && sheet.itemId && D.itemById.has(sheet.itemId)) { sc.view = "item"; sc.item = sheet.itemId; }
    else if (base.name === "room") sc.room = base.id;
    else if (base.name === "search") sc.q = (base.q && base.q.q) || "";
    else if (base.name === "data") sc.tab = moreTab(base.tab);
    return sc;
  }
  function chatAbout(sc) {
    if (sc.item) return D.itemById.get(sc.item)?.name || "este item";
    if (sc.room) return D.roomById.get(sc.room)?.name || "este cômodo";
    if (sc.view === "search") return sc.q ? `a busca “${sc.q}”` : "a busca";
    if (sc.view === "news") return "as novidades dos eletrônicos";
    return { home: "o inventário", rooms: "os cômodos", report: "o relatório", data: "o inventário", menu: "o inventário" }[sc.view] || "o inventário";
  }
  function chatIdeas(sc) {
    if (sc.item) return ["Vale a pena pôr no seguro?", "Como conservar melhor?", "Quanto vale hoje, mais ou menos?"];
    if (sc.room) return ["Qual o item mais caro daqui?", "O que falta cadastrar num cômodo assim?"];
    if (sc.view === "news") return ["Alguma novidade importante?", "Tem algum recall?"];
    return ["Quais cômodos valem mais?", "O que eu devia pôr no seguro?", "Quantos eletrônicos eu tenho?"];
  }
  function chatHtml(t) { // texto simples da IA: negrito, listas, links e quebras de linha
    return esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(https?:\/\/[^\s<]+[^\s<.,;:)!?])/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
      .split(/\n/).map((l) => (/^\s*[-*•]\s+/.test(l) ? `<span class="li">${l.replace(/^\s*[-*•]\s+/, "")}</span>` : l)).join("<br>").replace(/<br>(<span class="li">)/g, "$1").replace(/(<\/span>)<br>/g, "$1");
  }
  function openChat() {
    if (!aiOn()) return;
    const sc = chatScreen();
    let rec = null;
    const entry = openDialog({
      cls: "sheet chat", label: "Conversar",
      html: `<div class="dlg"><div class="dlg-h"><h2>Conversar</h2>
          <button type="button" class="btn ghost sm" data-new${CHAT.msgs.length ? "" : " hidden"}>Nova conversa</button>
          <button type="button" class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b chat-b" data-slot="msgs" aria-live="polite"></div>
        <form class="chat-f" data-chat>
          <p class="chat-ctx">Sobre ${esc(chatAbout(sc))}</p>
          <div class="chat-in"><textarea class="input" name="t" rows="1" maxlength="2000" placeholder="Pergunte o que quiser" aria-label="Mensagem" enterkeyhint="send"></textarea>
            ${voiceReady() ? `<button type="button" class="btn icon" data-mic aria-label="Falar a pergunta">${ic("mic")}</button>` : ""}
            <button type="submit" class="btn primary icon" aria-label="Enviar">${ic("send")}</button></div>
        </form></div>`,
      onClose: () => { if (rec) { rec.cancel(); rec = null; } },
    });
    const dlg = entry.dlg, box = $('[data-slot="msgs"]', dlg), form = $("[data-chat]", dlg), ta = form.t, mic = $("[data-mic]", dlg);
    const render = () => {
      box.innerHTML = CHAT.msgs.length ? CHAT.msgs.map((m) => `<div class="msg ${m.role === "user" ? "me" : m.error ? "ai err" : "ai"}">${m.role === "user" ? esc(m.text) : chatHtml(m.text)}${m.error ? `<button type="button" class="btn sm" data-retry>${ic("refresh", "sm")}Tentar de novo</button>` : ""}</div>`).join("")
          + (CHAT.busy ? `<div class="msg ai typing" aria-label="A IA está escrevendo"><i></i><i></i><i></i></div>` : "")
        : `<div class="chat-empty"><div class="chat-ideas">${chatIdeas(sc).map((t) => `<button type="button" class="chip" data-idea>${esc(t)}</button>`).join("")}</div></div>`;
      $("[data-new]", dlg).hidden = !CHAT.msgs.length;
      box.scrollTop = box.scrollHeight;
    };
    const grow = () => { ta.style.height = "auto"; ta.style.height = `${Math.min(140, ta.scrollHeight + 2)}px`; };
    async function ask() {
      CHAT.busy = true; render();
      try {
        const res = await API.post("api/chat", { messages: CHAT.msgs.filter((m) => !m.error).slice(-12).map(({ role, text }) => ({ role, text })), screen: sc });
        CHAT.msgs.push({ role: "assistant", text: res.reply || "" });
      } catch (e) { CHAT.msgs.push({ role: "assistant", text: e.message, error: true }); }
      CHAT.busy = false;
      if (document.contains(dlg)) { render(); ta.focus(); }
    }
    function send(text) {
      const t = String(text || "").trim();
      if (!t || CHAT.busy) return;
      CHAT.msgs = CHAT.msgs.filter((m) => !m.error);
      CHAT.msgs.push({ role: "user", text: t });
      ta.value = ""; grow();
      ask();
    }
    async function dictate() {
      if (rec) { // segunda vez: para, transcreve e manda
        const r = rec; rec = null;
        const pcm = r.stop();
        mic.classList.remove("on"); mic.innerHTML = ic("mic");
        if (pcm.length < VOICE_RATE * 0.4) { toast("Não ouvi nada. Toque no microfone e fale."); return; }
        mic.disabled = true;
        try { const res = await API.raw("POST", "api/voice", pcm); send(res.text || ""); }
        catch (e) { fail(e); }
        finally { mic.disabled = false; }
        return;
      }
      const r = new (window.INV_RECORDER || Recorder)(() => {});
      try { await r.start(); } catch (err) { r.cancel(); toast(micError(err), { error: true }); return; }
      rec = r;
      mic.classList.add("on"); mic.innerHTML = ic("check"); mic.setAttribute("aria-label", "Pronto: enviar o que falei");
    }
    form.addEventListener("submit", (e) => { e.preventDefault(); send(ta.value); });
    ta.addEventListener("input", grow);
    ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(ta.value); } });
    dlg.addEventListener("click", (e) => {
      if (e.target.closest("[data-x]")) { requestClose(entry, { force: true }); return; }
      if (e.target.closest("[data-new]")) { CHAT.msgs = []; render(); ta.focus(); return; }
      const idea = e.target.closest("[data-idea]");
      if (idea) { send(idea.textContent); return; }
      if (e.target.closest("[data-retry]")) { CHAT.msgs = CHAT.msgs.filter((m) => !m.error); render(); ask(); return; }
      if (e.target.closest("[data-mic]")) dictate();
    });
    render();
    if (!COARSE) setTimeout(() => ta.focus(), 60);
  }

  // ------------------------------------------------------------------ catalogar foto com IA (vários itens); também a revisão do Falar
  async function openCatalog({ room = null, file = null, voice = false } = {}) {
    if (!D.rooms.length) { toast("Crie um cômodo antes."); openRoomNew(); return; }
    if (!aiOn()) { toast("A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações."); return; }
    if (!voice && !(await needAi())) return;
    const zonesUse = zonesOn();
    const useAi = voice ? !!(await aiStatus()).ready : true; // IA ligada mas sem entidade que responda: o app separa sozinho
    const house = (rid) => D.rooms.some((r) => r.id === rid); // a área Bens não é cômodo
    // o cômodo de onde abriu; sem ele, a IA escolhe (e, se não souber, a pessoa escolhe na revisão)
    const C = { step: voice ? "voice" : file ? "ready" : "photo", room: room && house(room) ? room : "", zone: "", hint: "", file, uploading: false, results: [], keep: true, entity: "", error: null, raw: "", busy: false, token: 0,
      voice, heard: "", rec: "off", secs: 0, level: 0, note: "" };
    let rec = null, recTimer = null;
    const stopRec = () => { clearInterval(recTimer); if (rec) rec.cancel(); rec = null; };
    const title = voice ? "Falar" : "Catalogar itens com IA";
    const entry = openDialog({
      cls: "modal wide", label: title,
      html: `<div class="dlg"><div class="dlg-h"><h2>${title}</h2><button type="button" class="btn ghost icon" data-ct="cancel" aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b drop" data-slot="body"></div><div class="dlg-f" data-slot="foot"></div></div>`,
      guard: async () => C.step !== "review" || !C.results.some((r) => r.on) || confirmBox({ title: "Descartar os itens encontrados?", body: voice ? "Os itens do que você falou ainda não foram adicionados." : "Os itens lidos pela IA ainda não foram adicionados.", ok: "Descartar", cancel: "Voltar", danger: true }),
      onClose: () => { C.token++; stopRec(); },
    });
    const dlg = entry.dlg;
    const body = $('[data-slot="body"]', dlg), foot = $('[data-slot="foot"]', dlg);
    const roomName = (rid = C.room) => D.roomById.get(rid)?.name || "";
    const roomOpts = (sel, first) => (first ? `<option value="${first[0]}"${sel === first[0] ? " selected" : ""}>${first[1]}</option>` : "")
      + D.rooms.map((r) => `<option value="${esc(r.id)}"${r.id === sel ? " selected" : ""}>${esc(r.name)}</option>`).join("");
    // na revisão, o cômodo de todos (com "Cada item no seu" quando a IA pôs em cômodos diferentes)
    const shared = () => { const set = new Set(C.results.map((r) => r.room || "")); return set.size === 1 ? [...set][0] : "*"; };
    const reviewRoom = () => {
      const sel = shared();
      return `<div class="field"><label for="c-room">Cômodo</label><select id="c-room" class="select${sel === "" ? " need" : ""}" data-ct-in="room">${roomOpts(sel, sel === "*" ? ["*", "Cada item no seu"] : sel === "" ? ["", "Escolha o cômodo"] : null)}</select></div>`;
    };
    const perItem = () => C.voice && C.results.length > 1; // quem fala pode citar um cômodo para cada item
    const heardBox = () => (C.heard ? `<p class="heard">${ic("mic", "sm")}<span>“${esc(C.heard)}”</span></p>` : "");

    function render() {
      if (C.step === "voice") {
        const on = C.rec === "on";
        body.innerHTML = `<div class="voice${on ? " on" : ""}">
            <button type="button" class="voice-mic" data-ct="mic" style="--lvl:${on ? C.level.toFixed(2) : 0}" aria-label="${on ? "Pronto: enviar o que falei" : "Começar a falar"}"><span class="voice-ring"></span>${ic(on ? "check" : "mic")}</button>
            <div class="voice-state" aria-live="polite">${on ? `<b>Ouvindo…</b> <span class="voice-time">${clock(C.secs)}</span>` : C.rec === "starting" ? "Abrindo o microfone…" : "Toque no microfone e fale"}</div>
            <p class="voice-hint">${on ? "Toque de novo quando terminar." : "Ex.: “Sofá cinza, dois mil reais. TV Samsung de 55 polegadas, três mil.”"}</p>
          </div>
          ${C.error ? `<div class="formerr" style="margin-top:14px">${esc(C.error)}</div>` : ""}
          <p class="voice-note">${useAi ? "" : "Sem IA, o app separa pelas vírgulas. "}Até 2 minutos.${PREVIEW ? " Na prévia, o microfone não grava: entra um exemplo." : ""}</p>`;
        foot.innerHTML = `<span class="grow"></span><button type="button" class="btn ghost" data-ct="cancel">Cancelar</button>
          <button type="button" class="btn primary" data-ct="done"${on ? "" : " disabled"}>${ic("check")}Pronto</button>`;
      } else if (C.step === "transcribing") {
        body.innerHTML = `<div class="ai-wait voice-wait"><span class="spin lg"></span><b>Transcrevendo…</b></div>`;
        foot.innerHTML = `<span class="grow"></span><button type="button" class="btn ghost" data-ct="stop">Cancelar</button>`;
      } else if (C.step === "photo" || C.step === "ready") {
        const hasRoomPhotos = (D.roomById.get(C.room)?.photos || []).length > 0;
        body.innerHTML = `<div class="form">
          <p class="muted" style="margin:0">A IA lista os objetos da foto.</p>
          ${C.file ? `<div class="cat-photo"><img src="${esc(src(C.file, "photos"))}" alt="Foto escolhida"></div>
              <div style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" class="btn sm" data-ct="change">${ic("image", "sm")}Trocar foto</button></div>`
            : `<div class="phs" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">
                ${C.uploading ? `<div class="ph loading" style="aspect-ratio:4/3"><span class="spin lg"></span></div>` : `
                ${CAMERA ? `<button type="button" class="add" style="aspect-ratio:4/3" data-ct="camera">${ic("camera", "lg")}Tirar foto</button>` : ""}
                <button type="button" class="add" style="aspect-ratio:4/3" data-ct="upload">${ic(COARSE ? "image" : "upload", "lg")}Escolher fotos</button>
                ${hasRoomPhotos ? `<button type="button" class="add" style="aspect-ratio:4/3" data-ct="roomphoto">${ic("images", "lg")}Foto do cômodo</button>` : ""}`}
              </div>${COARSE ? "" : `<p class="help" style="margin:0">Também dá para arrastar ou colar (Ctrl+V).</p>`}`}
          <div class="${zonesUse ? "row2" : ""}">
            <div class="field"><label for="c-room">Cômodo</label><select id="c-room" class="select" data-ct-in="room">${roomOpts(C.room, ["", "A IA escolhe"])}</select></div>
            ${zonesUse ? `<div class="field"><label for="c-zone">Zona (opcional)</label><input id="c-zone" class="input" data-ct-in="zone" data-sug="c-zones" value="${esc(C.zone)}" placeholder="Deixe vazio para a IA sugerir" autocomplete="off">
              <datalist id="c-zones">${zonesOf(C.room).map((z) => `<option value="${esc(z)}">`).join("")}</datalist></div>` : ""}
          </div>
          <div class="field"><label for="c-hint">Dica para a IA (opcional)</label><input id="c-hint" class="input" data-ct-in="hint" value="${esc(C.hint)}" maxlength="300" placeholder="Ex.: são taças de cristal; o vaso é de cerâmica" autocomplete="off"></div>
        </div>`;
        foot.innerHTML = `<span class="grow"></span><button type="button" class="btn ghost" data-ct="cancel">Cancelar</button>
          <button type="button" class="btn primary" data-ct="read"${C.file ? "" : " disabled"}>${ic("scan")}Digitalizar com IA</button>`;
      } else if (C.step === "reading") {
        body.innerHTML = C.voice ? `${heardBox()}<div class="ai-wait voice-wait"><span class="spin lg"></span><b>Separando os itens…</b></div>`
          : `<div class="cat-photo"><img src="${esc(src(C.file, "photos"))}" alt=""><div class="scan"></div></div>
          <div class="ai-wait"><b>Lendo a foto…</b><span>Pode levar até um minuto.</span></div>`;
        foot.innerHTML = `<span class="grow"></span><button type="button" class="btn ghost" data-ct="stop">${C.voice ? "Cancelar" : "Cancelar leitura"}</button>`;
      } else if (C.step === "error") {
        body.innerHTML = `${C.voice ? heardBox() : `<div class="cat-photo"><img src="${esc(src(C.file, "thumbs"))}" alt="" style="max-height:220px"></div>`}
          <div class="formerr" style="margin-top:14px">${esc(C.error)}</div>
          ${C.raw ? `<details style="margin-top:10px"><summary class="muted">Ver resposta da IA</summary><pre style="white-space:pre-wrap;font-size:13px">${esc(C.raw)}</pre></details>` : ""}`;
        foot.innerHTML = `<button type="button" class="btn" data-ct="back">${ic(C.voice ? "mic" : "back", "sm")}${C.voice ? "Falar de novo" : "Voltar"}</button><span class="grow"></span><button type="button" class="btn primary" data-ct="read">${ic("refresh")}Tentar de novo</button>`;
      } else if (C.step === "review") {
        const on = C.results.filter((r) => r.on).length;
        const all = shared(), each = perItem();
        const zl = [...new Set(C.results.map((r) => r.room).filter(Boolean))]; // uma lista de zonas para cada cômodo
        body.innerHTML = `${C.voice ? heardBox() : ""}<div style="display:flex;gap:14px;align-items:center;margin-bottom:16px">
            ${C.file ? `<img src="${esc(src(C.file))}" alt="" style="width:72px;height:72px;object-fit:cover;border-radius:8px;flex:none">` : ""}
            <b style="font:600 21px/1.2 var(--font-c)">${C.results.length ? plural(C.results.length, "item encontrado", "itens encontrados") : "Nenhum item encontrado"}</b></div>
          ${C.results.length ? `<div class="form" style="margin:0 0 14px">${reviewRoom()}</div>` : ""}
          ${C.note ? `<p class="inote" style="margin:0 0 14px">${ic("info")}<span>${esc(C.note)}</span></p>` : ""}
          ${C.example ? `<p class="inote" style="margin:0 0 14px">${ic("info")}<span>Exemplo simulado da prévia.</span></p>` : ""}
          ${C.results.length ? `${zonesUse ? zl.map((rid, k) => `<datalist id="cr-zones-${k}">${zonesOf(rid).map((z) => `<option value="${esc(z)}">`).join("")}</datalist>`).join("") : ""}<ul class="found">${C.results.map((r, i) => `<li class="${r.on ? "" : "off"}">
            <input type="checkbox" class="fcheck" data-ri="${i}" data-rf="on"${r.on ? " checked" : ""} aria-label="Adicionar ${esc(r.name)}">
            <div class="fbody">
              <div class="frow"><input class="input fname" data-ri="${i}" data-rf="name" value="${esc(r.name)}" aria-label="Nome">
                <input class="input" data-ri="${i}" data-rf="qty" value="${esc(r.qty)}" aria-label="Quantidade">
                <div class="money"><input class="input" data-ri="${i}" data-rf="value" value="${esc(moneyInput(r.value))}" inputmode="decimal" aria-label="Valor total"></div></div>
              <div class="frow2">${each ? `<select class="select${r.room ? "" : " need"}" data-ri="${i}" data-rf="room" aria-label="Cômodo">${roomOpts(r.room || "", r.room ? null : ["", "Qual cômodo?"])}</select>` : ""}
                <select class="select" data-ri="${i}" data-rf="cat" aria-label="Categoria">${CATS.map(([k, v]) => `<option value="${k}"${k === r.cat ? " selected" : ""}>${esc(v)}</option>`).join("")}</select>
                ${zonesUse ? `<input class="input" data-ri="${i}" data-rf="zone" value="${esc(r.zone)}"${r.room ? ` data-sug="cr-zones-${zl.indexOf(r.room)}"` : ""} placeholder="Zona" aria-label="Zona" autocomplete="off">` : ""}</div>
              ${r.details ? `<p class="fdet">${esc(r.details)}</p>` : ""}
              ${r.existing || r.confidence === "baixa" ? `<div class="fflag">${r.existing ? `<span class="pill warn">Parece já cadastrado: ${esc(r.existing)}</span>` : ""}${r.confidence === "baixa" ? `<span class="pill">IA pouco segura, confira</span>` : ""}</div>` : ""}
            </div></li>`).join("")}</ul>
          ${!C.file || !house(all) || (D.roomById.get(all)?.photos || []).some((p) => p.file === C.file) ? "" : `<label class="check" style="margin-top:16px"><input type="checkbox" data-ct-in="keep"${C.keep ? " checked" : ""}> Guardar esta foto nas fotos de ${esc(roomName(all))}</label>`}`
          : `<p class="muted">${C.voice ? "Não achei itens no que você falou." : "Nenhum objeto encontrado. Tente uma foto mais próxima ou uma dica."}</p>`}`;
        foot.innerHTML = `<button type="button" class="btn" data-ct="back">${ic(C.voice ? "mic" : "back", "sm")}${C.voice ? "Falar de novo" : "Outra foto"}</button><span class="grow"></span>
          <button type="button" class="btn ghost" data-ct="cancel">Cancelar</button>
          <button type="button" class="btn primary" data-ct="add"${on ? "" : " disabled"}>${ic("plus")}${on > 1 ? `Adicionar ${on} itens` : on === 1 ? "Adicionar 1 item" : "Adicionar"}</button>`;
      }
    }
    const setFile = async (files) => {
      const f = imageFiles(files)[0];
      if (!f) { if ((files || []).length) toast("Escolha um arquivo de imagem (JPG ou PNG).", { error: true }); return; }
      C.uploading = true; C.file = null; C.step = "photo"; render();
      try { C.file = await uploadPhoto(f); C.step = "ready"; } catch (e) { fail(e); }
      finally { C.uploading = false; if (document.contains(dlg)) render(); }
    };
    if (!voice) wireDrop(entry, body, setFile);
    async function startRec() {
      if (rec) return;
      C.error = null; C.rec = "starting"; C.secs = 0; C.level = 0; render();
      const r = new (window.INV_RECORDER || Recorder)((lvl) => { C.level = lvl; });
      rec = r;
      try { await r.start(); }
      catch (err) { r.cancel(); if (rec === r) rec = null; C.rec = "off"; C.error = micError(err); if (document.contains(dlg)) render(); return; }
      if (rec !== r || !document.contains(dlg) || C.step !== "voice") { r.cancel(); return; }
      C.rec = "on"; render();
      clearInterval(recTimer);
      recTimer = setInterval(() => { // só o anel e o relógio mudam: a tela não é redesenhada a cada volta
        if (rec !== r) { clearInterval(recTimer); return; }
        C.secs = r.seconds();
        $(".voice-mic", dlg)?.style.setProperty("--lvl", C.level.toFixed(2));
        const t = $(".voice-time", dlg);
        if (t) t.textContent = clock(C.secs);
        if (C.secs >= VOICE_MAX_S) finishRec();
      }, 120);
    }
    async function finishRec() {
      const r = rec;
      if (!r) return;
      clearInterval(recTimer); rec = null;
      const pcm = r.stop();
      C.rec = "off";
      if (pcm.length < VOICE_RATE * 0.4) { C.error = "Não ouvi nada. Toque no microfone e fale."; render(); return; }
      const my = ++C.token;
      C.step = "transcribing"; C.error = null; render();
      try {
        const res = await API.raw("POST", "api/voice", pcm);
        if (my !== C.token) return;
        C.heard = res.text || "";
        await readSpoken(my);
      } catch (e) {
        if (my !== C.token) return;
        C.step = "voice"; C.error = e.message;
        if (document.contains(dlg)) render();
      }
    }
    const pickRoom = (r, res) => [r.room, res.room, C.room].find((x) => x && house(x)) || "";
    async function readSpoken(my = ++C.token) {
      C.note = "";
      if (!useAi) {
        C.results = splitSpoken(C.heard).map((r) => ({ ...r, room: C.room }));
        C.note = "Sem IA: separado pelas vírgulas. Confira nomes e valores.";
        C.step = "review"; render();
        return;
      }
      C.step = "reading"; C.error = null; C.raw = ""; render();
      try {
        const res = await API.post("api/ai/text", { text: C.heard, room: C.room });
        if (my !== C.token) return;
        C.results = (res.items || []).map((r) => ({ ...r, room: pickRoom(r, res), zone: zonesUse ? r.zone || "" : "", on: !r.existing }));
        C.step = "review";
      } catch (e) {
        if (my !== C.token) return;
        C.step = "error"; C.error = e.message; C.raw = (e.data && e.data.raw) || "";
      }
      if (document.contains(dlg)) render();
    }
    async function read() {
      if (C.voice) { if (C.heard) readSpoken(); return; }
      if (!C.file) return;
      const my = ++C.token;
      C.step = "reading"; C.error = null; C.raw = ""; render();
      try {
        const res = await API.post("api/ai/identify", { file: C.file, mode: "multi", room: C.room, hint: C.hint });
        if (my !== C.token) return;
        C.entity = res.entity || "";
        C.example = !!res.example;
        C.results = (res.items || []).map((r) => ({ ...r, room: pickRoom(r, res), zone: zonesUse ? C.zone || r.zone || "" : "", on: !r.existing }));
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
      const lost = chosen.find((r) => !house(r.room));
      if (lost) {
        toast(perItem() ? `Escolha o cômodo de ${String(lost.name).trim()}.` : "Escolha o cômodo.", { error: true });
        $(perItem() ? `[data-ri="${C.results.indexOf(lost)}"][data-rf="room"]` : "#c-room", dlg)?.focus();
        return;
      }
      const one = new Set(chosen.map((r) => r.room)).size === 1 ? chosen[0].room : "";
      C.busy = true;
      const btn = $('[data-ct="add"]', dlg);
      btn.disabled = true; btn.innerHTML = `<span class="spin"></span>Adicionando`;
      try {
        const res = await API.post("api/items/batch", {
          items: chosen.map((r) => ({ room: r.room, zone: zonesUse ? (r.zone || C.zone || "").trim() : "", name: String(r.name).trim(), details: r.details || "", cat: r.cat, qty: String(r.qty || "1").trim() || "1", value: parseMoney(r.value), photos: C.file ? [C.file] : [], source: C.voice ? "voz" : "ia" })),
          roomPhoto: C.file && C.keep && one ? { room: one, file: C.file, label: (C.hint || chosen.slice(0, 3).map((r) => String(r.name).trim()).join(", ")).slice(0, 160) } : null,
        });
        setRev(res.rev);
        res.items.forEach(upsertItem);
        if (res.rooms) S.rooms = res.rooms;
        derive();
        C.results = [];
        requestClose(entry, { force: true });
        refreshAll();
        const n = plural(res.items.length, "item adicionado", "itens adicionados");
        if (one) toast(`${n} em ${roomName(one)}`, { action: "Ver", onAction: () => nav(`#/c/${encodeURIComponent(one)}`) });
        else toast(`${n} em ${new Set(chosen.map((r) => r.room)).size} cômodos`);
      } catch (e) { fail(e); C.busy = false; if (document.contains(dlg)) render(); }
    }
    dlg.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-ct]");
      if (!b) return;
      const act = b.dataset.ct;
      if (act === "cancel") requestClose(entry);
      else if (act === "mic") { if (C.rec === "on") finishRec(); else if (C.rec === "off") startRec(); }
      else if (act === "done") finishRec();
      else if (act === "upload") pickFiles(setFile, { multiple: false });
      else if (act === "camera") camera(setFile, { title: "Catalogar itens" });
      else if (act === "change") { C.file = null; C.step = "photo"; render(); }
      else if (act === "roomphoto") { const [f] = await roomPhotoPicker(C.room); if (f) { C.file = f; C.keep = false; C.step = "ready"; render(); } }
      else if (act === "read") read();
      else if (act === "stop" || act === "back") {
        C.token++;
        if (C.voice) { stopRec(); C.step = "voice"; C.rec = "off"; C.results = []; C.error = null; render(); if (act === "back") startRec(); }
        else { C.step = C.file ? "ready" : "photo"; render(); }
      }
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
      if (t.dataset.ctIn === "room") {
        if (C.step === "review") { if (house(t.value)) C.results.forEach((r) => { r.room = t.value; }); } // o de todos
        else C.room = t.value;
        render();
      }
      else if (t.dataset.rf === "room") { C.results[+t.dataset.ri].room = t.value; render(); }
      else if (t.dataset.ctIn === "keep") C.keep = t.checked;
      else if (t.dataset.rf === "on") { C.results[+t.dataset.ri].on = t.checked; render(); }
      else if (t.dataset.rf === "cat") C.results[+t.dataset.ri].cat = t.value;
    });
    dlg.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.dataset.ctIn === "hint" && C.file) { e.preventDefault(); read(); } });
    render();
    if (voice) startRec();
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
            ${its.length ? `<ul class="vlist">${its.map((it) => `<li><a href="#/i/${encodeURIComponent(it.id)}" data-v="item"><span>${esc(it.name)}</span><span class="v">${money(vl(it))}</span></a></li>`).join("")}</ul>` : ""}</div>
          ${room ? `<div class="vacts">
            <button type="button" class="btn primary" data-v="additem">${ic("plus")}Adicionar item com esta foto</button>
            ${aiOn() ? `<button type="button" class="btn" data-v="catalog">${ic("scan")}Catalogar esta foto com IA</button>` : ""}
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
        const ok = await confirmBox({ title: "Tirar a foto do cômodo?", body: "Os itens que usam esta foto continuam com ela.", ok: "Tirar do cômodo", danger: true });
        if (!ok) return;
        const room = D.roomById.get(roomId);
        const list = (room.photos || []).filter((_, k) => k !== i);
        const cover = room.cover || 0;
        const r = await saveRoomPhotos({ photos: list, cover: Math.min(i < cover ? cover - 1 : i === cover ? 0 : cover, Math.max(0, list.length - 1)) });
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
    form.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("input") && !e.isComposing) { e.preventDefault(); go(); } }); // Enter cria, em qualquer campo
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
        <div class="dlg-f"><button type="button" class="btn danger" data-re="delete"${count ? ` title="Mova ou apague os ${count} itens antes"` : ""}>${ic("trash")}<span class="lbl">Apagar cômodo</span></button><span class="grow"></span>
          <button type="button" class="btn ghost" data-re="cancel">Cancelar</button><button type="button" class="btn primary" data-re="save">Salvar</button></div></div>`,
      guard: async () => !R.dirty || confirmBox({ title: "Descartar as alterações?", ok: "Descartar", cancel: "Continuar editando", danger: true }),
    });
    const dlg = entry.dlg;
    const form = $("[data-re-form]", dlg);
    const renderPhotos = () => {
      $('[data-slot="rphotos"]', dlg).innerHTML = `<ul class="opts">${R.photos.map((p, i) => `<li class="rph">
          <img src="${esc(src(p.file))}" alt="">
          <input class="input" data-re-label="${i}" value="${esc(p.label || "")}" placeholder="Legenda" aria-label="Legenda da foto">
          <button type="button" class="btn sm${R.cover === i ? " primary" : ""}" data-re="cover" data-i="${i}" aria-pressed="${R.cover === i}">${R.cover === i ? "Capa" : "Usar como capa"}</button>
          <button type="button" class="btn sm icon" data-re="up" data-i="${i}" aria-label="Subir foto"${i === 0 ? " disabled" : ""}>${ic("up", "sm")}</button>
          <button type="button" class="btn sm icon" data-re="rm" data-i="${i}" aria-label="Apagar foto">${ic("trash", "sm")}</button></li>`).join("")}</ul>
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
          ${R.uploading ? `<span class="muted"><span class="spin sm"></span> Enviando ${R.uploading} foto(s)…</span>` : ""}
          ${CAMERA ? `<button type="button" class="btn sm" data-re="camera">${ic("camera", "sm")}Tirar foto</button>` : ""}
          <button type="button" class="btn sm" data-re="upload">${ic(COARSE ? "image" : "upload", "sm")}Escolher fotos</button></div>`;
    };
    const addFiles = async (files) => {
      const all = [...(files || [])];
      files = imageFiles(all);
      if (files.length < all.length) toast(all.length === 1 ? "Escolha um arquivo de imagem (JPG ou PNG)." : `${plural(all.length - files.length, "arquivo não é imagem e ficou", "arquivos não são imagens e ficaram")} de fora.`, { error: true });
      if (!files.length) return;
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
      else if (act === "camera") camera(addFiles, { max: 12, title: "Fotos do cômodo" });
      else if (act === "cover") { R.cover = i; R.dirty = true; renderPhotos(); }
      else if (act === "up" && i > 0) { const [p] = R.photos.splice(i, 1); R.photos.splice(i - 1, 0, p); if (R.cover === i) R.cover = i - 1; else if (R.cover === i - 1) R.cover = i; R.dirty = true; renderPhotos(); }
      else if (act === "rm") { R.photos.splice(i, 1); if (R.cover >= R.photos.length) R.cover = 0; else if (R.cover > i) R.cover -= 1; R.dirty = true; renderPhotos(); }
      else if (act === "delete") {
        if (count) { toast(`Mova ou apague os ${count} itens de ${r.name} antes de apagar o cômodo.`, { error: true }); return; }
        const ok = await confirmBox({ title: `Apagar ${r.name}?`, ok: "Apagar cômodo", danger: true });
        if (!ok) return;
        try {
          const res = await API.del(`api/rooms/${encodeURIComponent(id)}`);
          setRev(res.rev); S.rooms = res.rooms; derive(); R.dirty = false;
          finalizeThen(entry, () => { nav("#/comodos"); toast("Cômodo apagado"); });
        } catch (er) { fail(er); }
      }
    });
  }

  // Um movimento por vez (toques seguidos entram na fila), e a linha movida fica sob o dedo
  // para dar para subir o mesmo cômodo várias posições seguidas.
  let roomMoves = Promise.resolve();
  function moveRoom(id, d) { roomMoves = roomMoves.then(() => moveRoomNow(id, d)); return roomMoves; }
  async function moveRoomNow(id, d) {
    const ids = D.rooms.map((r) => r.id);
    const i = ids.indexOf(id), j = i + d;
    if (i < 0 || j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    const rowOf = () => $(`#view [data-room-row="${CSS.escape(id)}"]`);
    const before = rowOf()?.getBoundingClientRect().top;
    try {
      const res = await API.post("api/rooms/order", { ids }); setRev(res.rev); S.rooms = res.rooms; derive(); refreshAll();
      const row = rowOf();
      if (!row) return;
      if (before != null) window.scrollBy(0, row.getBoundingClientRect().top - before);
      row.classList.add("moved");
      const btn = $(`[data-act="${d < 0 ? "room-up" : "room-down"}"]:not([disabled])`, row) || $(`[data-act="${d < 0 ? "room-down" : "room-up"}"]`, row);
      btn?.focus({ preventScroll: true });
    } catch (e) { fail(e); }
  }

  let addMenuOpening = false;
  async function openAddMenu() {
    const rid = base.name === "room" ? base.id : null;
    if (base.name === "bens") { openEditor({ room: D.bens?.id || BENS_NEW }); return; } // em Bens, Adicionar é um bem (sem foto do cômodo nem Falar)
    if (addMenuOpening) return;
    // com o Falar, a linha diz quem separa os itens: a IA, se houver uma pronta, ou o app (o mesmo teste do openCatalog)
    let st = null;
    if (voiceReady()) { addMenuOpening = true; try { st = await aiStatus(); } finally { addMenuOpening = false; } }
    // Novo cômodo fica na aba Cômodos; aqui só o que entra no inventário
    const opts = [
      ["item", "plus", "Adicionar item", "Com foto e valor, preenchendo os campos"],
      aiOn() && ["catalog", "scan", "Catalogar itens com IA", "A IA lista vários itens de uma foto"],
      voiceReady() && ["voice", "mic", "Falar os itens", `Diga o que tem e quanto vale; ${voiceSplit(st)}`],
      bensOn() && base.name !== "rooms" && !rid && ["bem", "home", "Adicionar bem", "Casa, terreno, carro: o que fica fora de casa"], // por último: o único que é bem, não item; nos cômodos, só itens
    ].filter(Boolean);
    if (opts.length === 1) { openEditor({ room: rid }); return; } // sem IA e sem Falar: direto no item, sem um menu de uma linha só
    const entry = openDialog({
      cls: "modal narrow", label: "Adicionar",
      html: `<div class="dlg"><div class="dlg-h"><h2>Adicionar</h2><button class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b" style="padding:8px 12px 16px"><ul class="opts" style="border-top:0">
          ${opts.map(([go, icon, title, sub], i) => `<li style="padding:0;border:0"><button class="rrow nocode" data-go="${go}" style="grid-template-columns:auto 1fr;padding:14px 8px${i === opts.length - 1 ? ";border-bottom:0" : ""}">${ic(icon, "lg")}<span class="rn">${title}<small style="display:block;margin:2px 0 0">${sub}</small></span></button></li>`).join("")}
        </ul></div></div>`,
    });
    entry.dlg.addEventListener("click", (e) => {
      if (e.target.closest("[data-x]")) { requestClose(entry, { force: true }); return; }
      const b = e.target.closest("[data-go]");
      if (!b) return;
      const go = b.dataset.go;
      finalizeThen(entry, () => { if (go === "item") openEditor({ room: rid }); else if (go === "bem") openEditor({ room: D.bens?.id || BENS_NEW }); else if (go === "catalog") openCatalog({ room: rid }); else if (go === "voice") openCatalog({ room: rid, voice: true }); });
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
    const ok = await confirmBox({ title: "Restaurar este backup?", body: `O inventário atual vira o de <b>${esc(name)}</b>. Antes, o app guarda uma cópia do atual.`, ok: "Restaurar", danger: true });
    if (!ok) return;
    try { await API.post("api/backups/restore", { name }); await loadData(); refreshAll(); toast("Backup restaurado"); }
    catch (e) { fail(e); }
  }
  const VERSION_WHY = { auto: "automática", restore: "antes de restaurar", import: "antes de importar", erase: "antes de apagar tudo" };
  async function restoreHistory(v) {
    const ok = await confirmBox({ title: "Restaurar esta versão?", body: `O inventário volta a ser o de <b>${esc(dateTime(v.date))}</b>${v.items != null ? `, com ${esc(plural(v.items, "item", "itens"))} em ${esc(plural(v.rooms || 0, "cômodo", "cômodos"))}` : ""}. Antes, o app guarda uma cópia do atual.`, ok: "Restaurar", danger: true });
    if (!ok) return false;
    try { await API.post("api/history/restore", { name: v.name }); await loadData(); refreshAll(); toast("Versão restaurada"); return true; }
    catch (e) { fail(e); return false; }
  }
  // Versões anteriores, como no ResolvIA: o botão abre a lista, e cada versão tem o Restaurar
  async function openVersions() {
    const entry = openDialog({
      cls: "modal narrow", label: "Versões anteriores",
      html: `<div class="dlg"><div class="dlg-h"><h2>Versões anteriores</h2><button type="button" class="btn ghost icon" data-x aria-label="Fechar">${ic("close")}</button></div>
        <div class="dlg-b" data-slot="versions"><p class="muted" style="margin:0">Carregando…</p></div></div>`,
    });
    const slot = $('[data-slot="versions"]', entry.dlg);
    let list = [];
    try {
      list = (await API.get("api/history")).history || [];
      slot.innerHTML = list.length ? `<ul class="opts versions">${list.map((v, i) => `<li><div class="ot"><b>${esc(dateTime(v.date))}</b>
          <span>${esc(ago(v.date))}${v.items != null ? ` · ${esc(plural(v.items, "item", "itens"))}` : ""} · ${esc(VERSION_WHY[v.reason] || "automática")}</span></div>
          <div class="oa"><button type="button" class="btn sm" data-ver="${i}">${ic("history", "sm")}Restaurar</button></div></li>`).join("")}</ul>`
        : `<p class="muted" style="margin:0">Ainda não há versões anteriores.</p>`;
    } catch (e) { slot.innerHTML = `<p class="muted" style="margin:0">${esc(e.message)}</p>`; }
    entry.dlg.addEventListener("click", async (e) => {
      if (e.target.closest("[data-x]")) { requestClose(entry, { force: true }); return; }
      const b = e.target.closest("[data-ver]");
      if (b && list[+b.dataset.ver] && (await restoreHistory(list[+b.dataset.ver]))) requestClose(entry, { force: true });
    });
  }
  $("#pick-import").addEventListener("change", (e) => {
    const files = [...e.target.files];
    e.target.value = "";
    if (files.length) importFiles(files);
  });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const mb = (n) => (n / 1048576).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  // Importa um backup (.zip ou .json). Aceita vários arquivos de uma vez: um backup dividido em partes,
  // em que só uma parte tem o inventario.json e as outras trazem fotos.
  async function importFiles(files) {
    files = files.filter(Boolean).sort((a, b) => (a.name || "").localeCompare(b.name || "", "pt-BR", { numeric: true }));
    const bad = files.find((f) => !(/\.(zip|json)$/i.test(f.name || "") || /zip|json/.test(f.type || "")));
    if (bad) { fail(new Error(`${bad.name || "Um dos arquivos"} não é um backup .zip nem um .json exportado pelo app.`)); return; }
    const many = files.length > 1;
    const total = files.reduce((n, f) => n + f.size, 0) || 1;
    let cancelled = false, done = false, uid = null, lock = null;
    let confirmed = !(S.items.length || S.rooms.length);
    const result = { replaced: false, items: 0, rooms: 0, photos: 0 };
    const stop = () => Object.assign(new Error("cancelado"), { cancelled: true });
    const entry = openDialog({
      cls: "modal narrow", label: "Importando inventário",
      html: `<div class="dlg"><div class="dlg-h"><h2>Importando inventário</h2></div>
        <div class="dlg-b"><p style="margin:0 0 12px;overflow-wrap:anywhere"><b data-name>${esc(many ? plural(files.length, "arquivo", "arquivos") : files[0].name)}</b></p>
          <div class="prog" role="progressbar" aria-label="Progresso do envio" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i></i></div>
          <p class="muted" data-st style="margin:10px 0 0">Preparando o envio…</p>
          <p class="muted" style="margin:6px 0 0;font-size:14px">Deixe esta tela aberta até terminar.</p></div>
        <div class="dlg-f"><span class="grow"></span><button type="button" class="btn ghost" data-x>Cancelar</button></div></div>`,
      guard: async () => {
        if (done) return true;
        const ok = await confirmBox({
          title: "Cancelar a importação?",
          body: many ? "O envio para no ponto em que está. Os arquivos que já terminaram continuam importados." : "O envio para no ponto em que está e nada muda no inventário.",
          ok: "Cancelar importação", cancel: "Continuar", danger: true,
        });
        if (ok) cancelled = true;
        return ok;
      },
    });
    const dlg = entry.dlg;
    const st = $("[data-st]", dlg), bar = $(".prog", dlg), xbtn = $("[data-x]", dlg), nameEl = $("[data-name]", dlg);
    const setProg = (p) => { bar.firstElementChild.style.width = `${Math.min(100, p * 100).toFixed(1)}%`; bar.setAttribute("aria-valuenow", String(Math.round(p * 100))); };
    xbtn.addEventListener("click", () => requestClose(entry));
    try { lock = navigator.wakeLock ? await navigator.wakeLock.request("screen") : null; } catch { lock = null; }
    try {
      let sent = 0;
      for (const [k, file] of files.entries()) {
        const label = many ? `Arquivo ${k + 1} de ${files.length}: ` : "";
        nameEl.textContent = file.name;
        const start = await API.post("api/upload", { name: file.name, size: file.size });
        uid = start.id;
        let off = 0;
        while (off < file.size) {
          if (cancelled) throw stop();
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
          setProg((sent + off) / total);
          st.textContent = `${label}enviando ${mb(off)} de ${mb(file.size)} MB`;
        }
        sent += file.size;
        if (cancelled) throw stop();
        const info = await API.get(`api/upload/${uid}`);
        if (info.hasData && !confirmed) {
          const ok = await confirmBox({
            title: "Trocar o inventário atual?",
            body: `O inventário de agora (${plural(S.items.length, "item", "itens")}) vira o de <b>${esc(file.name)}</b> (${plural(info.items, "item", "itens")} em ${plural(info.rooms, "cômodo", "cômodos")}). Antes, o app guarda uma cópia do atual.`,
            ok: "Trocar inventário", cancel: "Cancelar", danger: true,
          });
          if (!ok) { cancelled = true; throw stop(); }
          confirmed = true;
        }
        st.textContent = `${label}${info.hasData ? "restaurando itens e fotos…" : "guardando as fotos…"}`;
        xbtn.disabled = true;
        const res = await API.post(`api/upload/${uid}/restore`);
        uid = null;
        xbtn.disabled = false;
        result.photos += res.photosAdded || 0;
        if (res.replaced) result.replaced = true;
        result.items = res.items;
        result.rooms = res.rooms;
      }
      done = true;
      await loadData();
      // fecha e só depois vai para o Início: o voltar do histórico da janela desfazia a ida
      finalizeThen(entry, () => { if (base.name !== "home") nav("#/"); else refreshAll(); });
      if (result.replaced) toast(`Inventário importado: ${plural(result.items, "item", "itens")} em ${plural(result.rooms, "cômodo", "cômodos")}${result.photos ? `, ${plural(result.photos, "foto", "fotos")}` : ""}`);
      else toast(result.photos ? `${plural(result.photos, "foto adicionada", "fotos adicionadas")} ao inventário` : "As fotos desse arquivo já estavam no inventário.");
    } catch (e) {
      done = true;
      if (uid) API.del(`api/upload/${uid}`).catch(() => {});
      if (stack.includes(entry)) requestClose(entry, { force: true });
      const partial = result.replaced || result.photos > 0;
      if (partial) { try { await loadData(); refreshAll(); } catch { /* ok */ } }
      if (e.cancelled || cancelled) toast(partial ? "Importação interrompida. O que já tinha chegado ficou salvo." : "Importação cancelada. Nada mudou no inventário.");
      else fail(e);
    } finally {
      try { if (lock) await lock.release(); } catch { /* ok */ }
    }
  }
  // Configurações > Dados > Começar do zero: apaga os cômodos, os bens e os itens, só depois de confirmar; o servidor guarda
  // antes uma versão (Versões anteriores). As categorias e as opções continuam.
  async function eraseAll() {
    // tudo o que está gravado, inclusive os bens com Usar bens desligado
    const bensIds = new Set(S.rooms.filter((r) => r.kind === "bens").map((r) => r.id));
    const nb = S.items.filter((i) => bensIds.has(i.room)).length, ni = S.items.length - nb, nr = S.rooms.length - bensIds.size;
    const parts = [nr && plural(nr, "cômodo", "cômodos"), ni && plural(ni, "item", "itens"), nb && plural(nb, "bem", "bens")].filter(Boolean);
    const ok = await confirmBox({ title: "Apagar tudo?",
      body: `${parts.length ? `Saem ${parts.length > 1 ? `${parts.slice(0, -1).join(", ")} e ${parts[parts.length - 1]}` : parts[0]}. ` : ""}As categorias e as opções continuam, e uma cópia fica em Versões anteriores.`,
      ok: "Apagar tudo", danger: true });
    if (!ok) return;
    try {
      const r = await API.post("api/erase", { confirm: true });
      setRev(r.rev);
      await loadData();
      refreshAll();
      toast("Tudo apagado. Uma cópia ficou em Versões anteriores.");
    } catch (e) { fail(e); }
  }
  function setTheme(t) {
    LS.set("theme", t);
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
    $$('[data-act="theme"]').forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.theme === t)));
  }
  // a cor do app vale para a casa toda: grava no servidor e guarda a cópia do aparelho (para pintar antes de carregar)
  function keepLook() {
    LS.set("accent", pickedAccent());
    LS.set("accentDaily", accentDaily());
  }
  async function saveLook(patch) {
    const before = { ...HOUSE_LOOK };
    HOUSE_LOOK = { ...HOUSE_LOOK, ...patch };
    Object.assign(S.settings, patch);
    keepLook();
    const sw = $('[data-input="accent-daily"]');
    if (sw) sw.checked = accentDaily();
    applyAccent(accentOf());
    try { await API.put("api/settings", patch); }
    catch (e) { HOUSE_LOOK = before; Object.assign(S.settings, before); keepLook(); if (sw) sw.checked = accentDaily(); applyAccent(accentOf()); fail(e); }
  }
  // escolher uma cor desliga a Cor do dia e fica com ela
  const setAccent = (a) => saveLook({ accent: nearestAccent(a), accent_daily: false });
  // ligada, a cor do dia; desligada, a última cor escolhida (ou o Ouro)
  const setAccentDaily = (on) => saveLook({ accent_daily: !!on, accent: pickedAccent() });
  // depois de carregar: vale a da casa. Na primeira vez (a casa ainda sem cor), a escolhida neste aparelho passa para a casa.
  function syncLook() {
    const st = S.settings || {};
    HOUSE_LOOK = { accent: st.accent ?? null, accent_daily: st.accent_daily ?? null };
    if (HOUSE_LOOK.accent == null && HOUSE_LOOK.accent_daily == null && !PREVIEW) {
      const a = LS.get("accent", null), d = LS.get("accentDaily", null);
      if (a != null || d != null) {
        const patch = { accent: nearestAccent(a || ACCENT0), accent_daily: d !== false };
        HOUSE_LOOK = patch;
        Object.assign(S.settings, patch);
        API.put("api/settings", patch).catch(() => {});
      }
    }
    if (houseSet("accent") || houseSet("accent_daily")) keepLook();
    applyAccent(accentOf());
  }

  // ------------------------------------------------------------------ eventos globais
  document.addEventListener("click", async (e) => {
    const a = e.target.closest("a[href^='#']");
    if (a && !e.defaultPrevented && !e.metaKey && !e.ctrlKey) inAppNavs++;
    const bar = e.target.closest("[data-usage-day]");
    if (bar) {
      usageSel = bar.dataset.usageDay;
      const slot = bar.closest('[data-slot="usage"]');
      if (slot) { renderUsage(slot); $(`[data-usage-day="${usageSel}"]`, slot)?.focus({ preventScroll: true }); }
      return;
    }
    const b = e.target.closest("[data-act]");
    if (!b) return;
    const act = b.dataset.act;
    const item = b.dataset.id ? D.itemById.get(b.dataset.id) : null;
    switch (act) {
      case "add-menu": openAddMenu(); break;
      case "item-new": openEditor({ room: b.dataset.room || (base.name === "room" ? base.id : base.name === "bens" ? D.bens?.id || BENS_NEW : null) }); break;
      case "catalog": openCatalog({ room: b.dataset.room || (base.name === "room" ? base.id : null) }); break;
      case "room-new": openRoomNew(); break;
      case "cat-new": openCatName(); break;
      case "cat-edit": openCatName(b.dataset.cat); break;
      case "cat-del": deleteCat(b.dataset.cat); break;
      case "room-edit": openRoomEdit(b.dataset.room); break;
      case "room-up": moveRoom(b.dataset.room, -1); break;
      case "room-down": moveRoom(b.dataset.room, 1); break;
      case "rooms-organize": roomsOrganize = !roomsOrganize; renderView(false); $('#view [data-act="rooms-organize"]')?.focus({ preventScroll: true }); break;
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
      case "web-photo": if (item) addWebPhoto(item); break;
      case "item-news": if (item) searchItemNews(item); break;
      case "item-dup": if (item) openEditor({ dup: item }); break;
      case "tarefa-nova": if (item) openTarefaNova(item); break;
      case "copy-field": copyField(b.dataset.target); break;
      case "item-move": if (item) moveItem(item); break;
      case "item-delete": if (item) deleteItem(item); break;
      case "sheet-close": if (sheet) requestClose(sheet); break;
      case "search-clear": { const inp = $('#view [data-input="search-q"]'); if (inp) { inp.value = ""; inp.focus(); } updateSearch({ q: "" }); break; }
      case "search-reset": base.q = { q: base.q.q || "" }; renderView(false); try { history.replaceState(history.state, "", hashOf(base)); } catch { /* ok */ } break;
      case "more-results": searchLimit += 120; selRender(); break;
      case "sel-start": selStart(); break;
      case "sel-end": selEnd(); break;
      case "sel-toggle": { const id = b.dataset.id; if (SEL) { if (SEL.has(id)) SEL.delete(id); else SEL.add(id); selRender(); } break; }
      case "sel-change": if (SEL && SEL.size) selEdit(); break;
      case "sel-all": if (SEL) { // todos os da lista (os que já apareceram e os que vêm com Mostrar mais), ou nenhum
        const ids = searchItems(base.q).list.filter((i) => !isBens(i.room)).map((i) => i.id);
        SEL = new Set(ids.length && ids.every((id) => SEL.has(id)) ? [] : ids); selRender();
      } break;
      case "export": download(b.dataset.kind); break;
      case "backup-create": createBackup(b); break;
      case "backup-restore": restoreBackup(b.dataset.name); break;
      case "versions": openVersions(); break;
      case "news-all": startNewsAll(); break;
      case "news-cancel": cancelNewsAll(); break;
      case "news-clear": clearNews(); break;
      case "erase-all": eraseAll(); break;
      case "news-pessoa": toggleNewsPessoa(b.dataset.id); break;
      case "news-notify-test":
        b.disabled = true;
        API.post("api/news/notify-test", { who: "eu" }).then((r) => toast(r.sent > 1 ? `Aviso enviado para ${r.sent} celulares` : "Aviso enviado"), fail).finally(() => { b.disabled = !!newsTestWhy(); });
        break;
      case "news-open": { const it = D.itemById.get(b.dataset.id); if (it) openNews(it); break; }
      case "import-file": { const inp = $("#pick-import"); inp.multiple = MULTI_PICK; inp.click(); break; }
      case "ai-refresh": { const slot = $('#view [data-slot="ai-panel"]'); if (slot) { slot.innerHTML = `<p class="muted">Verificando…</p>`; renderAiPanel(slot, await aiStatus(true)); paintVoiceLead(); } break; }
      case "theme": setTheme(b.dataset.theme); break;
      case "more-tab": setMoreTab(b.dataset.tab); break;
      case "voice": openCatalog({ room: base.name === "room" ? base.id : null, voice: true }); break;
      case "chat": openChat(); break;
      case "voice-refresh": { const slot = $('#view [data-slot="voice-panel"]'); if (slot) slot.innerHTML = `<p class="muted">Verificando…</p>`; await loadVoice(true); if (slot && document.contains(slot)) renderVoicePanel(slot); break; }
      case "print": if (window.INV_PRINT) toast(window.INV_PRINT); else window.print(); break;
      case "rep-pdf": {
        if (window.INV_PRINT) { e.preventDefault(); toast(window.INV_PRINT); break; }
        // a tela fica num quadro da página do Home Assistant, e o app do Home Assistant no Android só baixa o que a página
        // de cima pede: o link vai para lá e é clicado, como o Home Assistant faz com os backups (mesma origem, pelo
        // ingress); sem isso (outra origem), o link baixa sozinho
        try {
          const d = window.top.document, a = d.createElement("a");
          a.href = b.href; a.download = b.getAttribute("download") || ""; a.target = "_blank"; a.style.display = "none";
          d.body.appendChild(a); a.dispatchEvent(new MouseEvent("click")); d.body.removeChild(a);
          e.preventDefault();
          toast("Baixando o PDF…");
        } catch { /* outra origem */ }
        break;
      }
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
    if (k === "search-tipo") { // num tipo de bem, cômodo e categoria saem (e as seleções somem)
      base.q = { ...base.q, tipo: t.value, ...(tipoBens(t.value) ? { room: "", cat: "" } : {}) };
      try { history.replaceState(history.state, "", hashOf(base)); } catch { /* sem histórico */ }
      searchLimit = 120; renderView(false);
    }
    else if (k === "search-room") updateSearch({ room: t.value });
    else if (k === "search-cat") updateSearch({ cat: t.value });
    else if (k === "search-ord") updateSearch({ ord: t.value });
    else if (k === "rep-photos") { LS.set("reportPhotos", t.checked); renderView(false); }
    else if (k === "accent" && t.checked) setAccent(t.value);
    else if (k === "accent-daily") setAccentDaily(t.checked);
    else if (k === "ai-entity") {
      try { await API.put("api/settings", { ai_entity: t.value }); S.settings.ai_entity = t.value; const slot = $('#view [data-slot="ai-panel"]'); if (slot) { renderAiPanel(slot, await aiStatus(true)); paintVoiceLead(); } toast("IA para ler fotos atualizada"); }
      catch (er) { fail(er); }
    }
    else if (k === "voice-stt") {
      t.disabled = true;
      try {
        await API.put("api/settings", { voice_stt: t.value });
        await loadVoice(true);
        const slot = $('#view [data-slot="voice-panel"]');
        if (slot) renderVoicePanel(slot);
        toast(S.voice && S.voice.ready ? `Falar agora transcreve com ${S.voice.name || S.voice.engine}` : "Fala para texto atualizada");
      } catch (er) { fail(er); t.disabled = false; }
    }
    else if (k === "ai-search") {
      try { await API.put("api/settings", { ai_search: t.value }); S.settings.ai_search = t.value; aiCache.at = 0; toast("IA para buscar fotos atualizada"); }
      catch (er) { fail(er); }
    }
    else if (k === "news-every") saveNews({ news_every: +t.value }, `Conferir a cada ${+t.value} dias`);
    else if (k === "news-hora") saveNews({ news_hora: t.value }, `Conferir às ${t.value}`);
    else if (k === "news-auto") saveNews({ news_every: t.checked ? 7 : 0 }, t.checked ? `Conferir sozinho: a cada 7 dias, às ${S.settings.news_hora || "10:00"}` : "Conferir sozinho desligado");
    else if (k === "news-aviso") {
      // ligou o aviso sem ninguém escolhido: começa com quem está usando o app (como no GerencIA)
      const me = (newsPeople || []).find((x) => x.eu), patch = { news_aviso: t.checked };
      if (t.checked && !newsPara().length && me) patch.news_para = [me.id];
      saveNews(patch, t.checked ? "Aviso no celular ligado" : "Aviso no celular desligado");
    }
    else if (k === "ai-on" || k === "zones-on" || k === "sensors-on" || k === "news-on" || k === "bens-on" || k === "correria-on" || k === "deprec-on") {
      const key = { "ai-on": "ai", "zones-on": "zones", "news-on": "news", "bens-on": "bens", "correria-on": "correria", "deprec-on": "deprec" }[k] || "ha_sensors", on = t.checked;
      t.disabled = true;
      try {
        await API.put("api/settings", { [key]: on });
        S.settings[key] = on;
        aiCache.at = 0;
        if (key === "bens" || key === "deprec") derive(); // os bens (ou o valor de hoje) entram ou saem de tudo (patrimônio, busca, gráficos, relatório)
        renderView(false);
        toast(key === "ai" ? (on ? "IA ligada" : "IA desligada: os botões de IA ficaram escondidos")
          : key === "ha_sensors" ? (on ? "Sensor criado no Home Assistant" : "Sensores desligados: o sensor saiu do Home Assistant")
          : key === "news" ? (on ? "Novidades ligadas" : "Novidades desligadas")
          : key === "bens" ? (on ? "Bens ligados" : "Bens desligados: os bens gravados continuam guardados")
          : key === "correria" ? (on ? "CorrerIA ligado" : "CorrerIA desligado")
          : key === "deprec" ? (on ? "Valor de hoje ligado" : "Valor de hoje desligado")
          : on ? "Zonas ligadas" : "Zonas desligadas: as zonas gravadas continuam guardadas");
      } catch (er) { t.checked = !on; fail(er); }
      finally { t.disabled = false; }
    }
  });
  document.addEventListener("keydown", (e) => {
    const tabBtn = e.target.closest && e.target.closest('.more-tabs [role="tab"]');
    if (tabBtn && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
      e.preventDefault();
      const keys = moreTabs().map(([k]) => k), i = keys.indexOf(tabBtn.dataset.tab);
      const j = e.key === "Home" ? 0 : e.key === "End" ? keys.length - 1 : (i + (e.key === "ArrowRight" ? 1 : -1) + keys.length) % keys.length;
      setMoreTab(keys[j]);
      return;
    }
    if (stack.length) {
      const top = topEntry();
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && top.onSubmit) { e.preventDefault(); top.onSubmit(); }
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    // a busca do Início pode estar com o cursor: "/" nela vazia continua sendo o atalho do Buscar
    if (e.key === "/" && e.target.matches && e.target.matches('[data-input="home-q"]') && !e.target.value) { e.preventDefault(); focusSearch = true; nav("#/buscar"); return; }
    if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable]")) return;
    if (e.key === "/") {
      e.preventDefault();
      if (base.name === "search") $('#view [data-input="search-q"]')?.focus();
      else { focusSearch = true; nav("#/buscar"); }
    } else if (e.key === "n" || e.key === "N") { e.preventDefault(); openEditor({ room: base.name === "room" ? base.id : null }); }
  });
  // Arrastar para o lado troca de aba no celular, como no ResolvIA e no CronologIA: Início ⇄ Buscar ⇄ Cômodos ⇄ Mais.
  // Dentro de um cômodo, arrastar para a direita volta para Cômodos; no relatório, para Mais. Não vale começando na
  // borda da tela (é o Voltar do celular), num campo, numa fileira que rola para o lado ou com uma janela aberta.
  const SWIPE_TABS = [["home", "#/"], ["search", "#/buscar"], ["rooms", "#/comodos"], ["menu", "#/mais"]];
  let swipe = null, slideFrom = 0;
  document.addEventListener("touchstart", (e) => {
    swipe = null;
    if (!e.touches || e.touches.length !== 1 || window.matchMedia("(min-width: 1000px)").matches || document.querySelector("dialog[open]")) return;
    const t = e.touches[0];
    if (t.clientX < 24 || t.clientX > window.innerWidth - 24) return;
    for (let el = e.target instanceof Element ? e.target : e.target.parentElement; el && el !== document.body; el = el.parentElement) {
      if (el.matches("input, textarea, select, [contenteditable], [data-noswipe], .tabbar, .side")) return;
      const st = getComputedStyle(el);
      if ((st.overflowX === "auto" || st.overflowX === "scroll") && el.scrollWidth > el.clientWidth + 2) return;
    }
    swipe = { x: t.clientX, y: t.clientY, at: Date.now() };
  }, { passive: true });
  document.addEventListener("touchend", (e) => {
    const s = swipe;
    swipe = null;
    if (!s || !e.changedTouches || !e.changedTouches.length || document.querySelector("dialog[open]")) return;
    const t = e.changedTouches[0], dx = t.clientX - s.x, dy = t.clientY - s.y;
    if (Math.abs(dx) < 70 || Math.abs(dx) < Math.abs(dy) * 2 || Date.now() - s.at > 800) return;
    const d = dx < 0 ? 1 : -1; // dedo para a esquerda: a próxima aba
    let to = null;
    if (base.name === "room") to = d < 0 ? "#/comodos" : null;
    else if (IN_MORE.includes(base.name) && base.name !== "menu") to = d < 0 ? "#/mais" : null; // Relatório, Novidades, Configurações, Sobre: volta ao menu
    else {
      const i = SWIPE_TABS.findIndex(([n]) => n === base.name), j = i + d;
      if (i >= 0 && j >= 0 && j < SWIPE_TABS.length) to = SWIPE_TABS[j][1];
    }
    if (!to) return;
    slideFrom = d;
    nav(to);
  }, { passive: true });
  document.addEventListener("touchcancel", () => { swipe = null; }, { passive: true });
  window.addEventListener("hashchange", () => { onRoute(); });
  // No Home Assistant, o painel do app (/app/<app>/novidades, o link do aviso) passa o resto do endereço por mensagem:
  // o aviso das novidades abre direto nelas. Cada endereço conta uma vez (a mesma mensagem volta quando a largura muda).
  if (window.parent !== window && !PREVIEW) {
    let haPath = null;
    window.addEventListener("message", (e) => {
      if (e.source !== window.parent || !e.data || e.data.type !== "home-assistant/properties") return;
      const p = String((e.data.route && e.data.route.path) || "").replace(/\/+$/, "");
      if (p === haPath) return;
      haPath = p;
      if (p === "/novidades") nav("#/novidades");
    });
    try { window.parent.postMessage({ type: "home-assistant/subscribe-properties" }, "*"); } catch { /* fora do Home Assistant */ }
  }

  // atualização quando outro aparelho mexer no inventário
  async function checkRev() {
    if (document.hidden || !S.loaded || PREVIEW) return;
    try {
      const r = await API.get("api/rev");
      if (r && "correria_uso" in r) { // o CorrerIA leu algo (uma leitura não muda a rev): a linha de Integrações diz quando
        S.correriaUso = r.correria_uso || null;
        const el = $('#view [data-slot="correria-uso"]');
        if (el) el.textContent = correriaUsoTxt();
      }
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
    loadVoice();
  }
  // os testes da tela (tests/e2e) pedem as funções puras para conferir as contas e as regras
  if (typeof window.INV_TEST === "function") {
    window.INV_TEST({ esc, norm, numTxt, money, moneyR, plural, pct, pctFmt, ago, parseMoney, moneyInput, qtyClean, qtyNum, qtyLabel, qtyShort,
      splitSpoken, wordsToNumbers, newsDate, moneyK, pctTxt, chatHtml, webFills, siteOf, suggestCode, hl, applyCats, cats: () => CATS,
      colorOfDay, nearestAccent, dayAccents: () => DAY_ACCENTS, accents: () => ACCENTS.map(([k]) => k) });
  }
  if (!PREVIEW || window.INV_BACKEND) boot();
  else window.INV_BOOT = boot;
})();
