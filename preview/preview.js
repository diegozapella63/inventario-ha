/* Prévia do app: imita o servidor do Home Assistant em memória, com os dados reais (data.json).
   Nada é salvo; recarregar a página volta ao inventário original. */
(() => {
  "use strict";
  window.INV_PREVIEW = true;
  const DEF_CATS = [["eletronicos", "Eletrônicos"], ["moveis", "Móveis"], ["decoracao", "Decoração e arte"], ["colecao", "Colecionáveis"], ["cozinha", "Cozinha e bar"],
    ["texteis", "Tapetes e têxteis"], ["plantas", "Plantas"], ["livros", "Livros e jogos"], ["pets", "Pets"], ["saude", "Saúde"], ["vestuario", "Roupas e calçados"],
    ["utilidades", "Utilidades"], ["imoveis", "Imóveis"], ["veiculos", "Veículos"], ["outros", "Outros"]].map(([id, name]) => ({ id, name }));
  const catsOf = (d) => { if (!Array.isArray(d.cats) || !d.cats.length) d.cats = clone(DEF_CATS); return d.cats; };
  const CATS = { has: (k) => ST.data && catsOf(ST.data).some((c) => c.id === k) };
  // 1.82.0: as categorias dos consumíveis (à parte) e a duração estimada, como no server.py
  const DEF_CCATS = [["c-limpeza", "Limpeza"], ["c-higiene", "Higiene e cuidados"], ["c-despensa", "Cozinha e despensa"], ["c-farmacia", "Farmácia"], ["c-pets", "Pets"],
    ["c-papelaria", "Escritório e papelaria"], ["c-manutencao", "Manutenção e reparos"], ["c-eletronicos", "Pilhas e eletrônicos"], ["c-carro", "Carro"], ["c-jardim", "Jardim"],
    ["c-outros", "Outros"]].map(([id, name]) => ({ id, name }));
  const ccatsOf = (d) => { if (!Array.isArray(d.consCats) || !d.consCats.length) d.consCats = clone(DEF_CCATS); return d.consCats; };
  const isCons = (d, rid) => (d.rooms.find((r) => r.id === rid) || {}).kind === "consumiveis";
  // 1.91.0: os cômodos onde um consumível é usado: um id (o jeito de antes) ou uma lista; só os cômodos da casa
  const usados = (d, v) => [...new Set([].concat(v || []))].filter((id) => d.rooms.some((x) => x.id === id && !x.kind)).slice(0, 40);
  const consCat = (d, k) => (ccatsOf(d).some((c) => c.id === k) ? k : "c-outros");
  const dur = (v) => { const n = Math.trunc(+v); return n > 0 && n <= 3650 ? n : 0; };
  const foldName = (t) => String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  const kindRank = (r) => ({ bens: 1, consumiveis: 2 })[r.kind] || 0; // as áreas do sistema depois dos cômodos: Bens, Consumíveis
  const ST = { data: null, rev: 1, blobs: new Map(), jobs: new Map(), settings: { ai_entity: "", ai_search: "", ai_chat: "", ai: true, zones: false, ha_sensors: false, voice_stt: "", news: true, news_every: 0, news_notify: "", bens: true, itens: true, consumiveis: false, correria: false },
    news: { itens: {}, triagem: {}, ultima: null, apps: {}, apps_triagem: {}, apagadas: {} } };
  const now = () => new Date().toISOString();
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const fail = (msg, status = 400, extra = {}) => { throw Object.assign(new Error(msg), { status, data: { error: msg, ...extra } }); };
  const OFF = "Na prévia isso fica desligado. No Home Assistant, ";

  async function data() {
    if (!ST.data) {
      const r = await fetch("data.json", { cache: "no-store" });
      if (!r.ok) fail("Não deu para carregar os dados da prévia.", 500);
      ST.data = await r.json();
    }
    return ST.data;
  }
  function money(v) {
    if (v === "" || v == null) return 0;
    if (typeof v === "number") return Math.round(v * 100) / 100;
    let s = String(v).replace(/R\$|\s| /g, "");
    if (s.includes(",")) s = s.replace(/\./g, "").replace(",", ".");
    else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, "");
    const n = Number(s);
    if (!Number.isFinite(n) || n < 0) fail("Valor inválido. Use só números, como 1200 ou 1.200,50.");
    return Math.round(n * 100) / 100;
  }
  const nextSeq = (d, rid) => Math.max(0, ...d.items.filter((i) => i.room === rid).map((i) => i.seq || 0)) + 1;
  const room = (d, id) => d.rooms.find((r) => r.id === id);
  function build(d, b, restore) {
    const r = room(d, b.room);
    if (!r) fail("Escolha um cômodo que exista.");
    const name = String(b.name || "").trim();
    if (!name) fail("Preencha o campo nome.");
    const t = now();
    const seqs = new Set(d.items.filter((i) => i.room === r.id).map((i) => i.seq));
    const seq = restore && b.seq && !seqs.has(b.seq) ? b.seq : nextSeq(d, r.id);
    const ids = new Set(d.items.map((i) => i.id));
    let id = restore && b.id && !ids.has(b.id) ? b.id : `${r.code.toLowerCase()}-${String(seq).padStart(3, "0")}`;
    if (ids.has(id)) id += "-" + Math.random().toString(16).slice(2, 6);
    return {
      id, room: r.id, seq, zone: String(b.zone || "").trim(), name, details: String(b.details || "").trim(),
      ...(r.kind === "consumiveis" ? { cat: consCat(d, b.cat), qty: "1", value: 0, dur: dur(b.dur), ...(dur(b.dur) ? { durAt: restore && b.durAt ? b.durAt : t } : {}), ...(usados(d, b.usedIn).length ? { usedIn: usados(d, b.usedIn) } : {}) }
        : { cat: CATS.has(b.cat) ? b.cat : "outros", qty: String(b.qty || "1").trim() || "1", value: money(b.value) }),
      photos: Array.isArray(b.photos) ? [...b.photos] : [], ...(b.photoSrc && Object.keys(b.photoSrc).length ? { photoSrc: { ...b.photoSrc } } : {}),
      checked: !!b.checked, flag: (b.flag || "").trim() || null,
      approx: true, source: b.source || "manual", createdAt: restore && b.createdAt ? b.createdAt : t, updatedAt: t,
    };
  }
  const bump = () => { ST.rev += 1; return ST.rev; };

  // fotos enviadas na prévia ficam só na memória do navegador
  window.INV_PHOTO_STORE = (name, full, thumb) => { ST.blobs.set(name, { photos: URL.createObjectURL(full), thumbs: URL.createObjectURL(thumb) }); };
  window.INV_PHOTO_URL = (f, kind) => { const b = ST.blobs.get(f); return b ? b[kind] || b.photos : null; };
  window.INV_EXPORT = () => OFF + "este botão baixa o arquivo para o seu computador.";
  window.INV_PRINT = OFF + "este botão baixa o relatório em PDF.";

  // Falar na prévia: sem microfone, um "gravador" de mentira e um exemplo do que alguém falou
  const SPEECH = "Cafeteira Nespresso vermelha, uns quinhentos reais. Liquidificador Philips Walita, duzentos reais. E duas almofadas cinzas de veludo.";
  const SPOKEN = [
    { name: "Cafeteira Nespresso vermelha", details: "Cafeteira de cápsulas Nespresso, vermelha.", cat: "cozinha", qty: "1", value: 500, zone: "", existing: "", confidence: "alta" },
    { name: "Liquidificador Philips Walita", details: "Liquidificador Philips Walita com jarra de plástico.", cat: "cozinha", qty: "1", value: 200, zone: "", existing: "", confidence: "alta" },
    { name: "Almofadas cinzas de veludo", details: "Duas almofadas decorativas de veludo cinza.", cat: "texteis", qty: "2", value: 80, zone: "", existing: "", confidence: "media" },
  ];
  window.INV_RECORDER = class {
    constructor(onLevel) { this.onLevel = onLevel; this.t0 = 0; this.timer = null; }
    async start() { await wait(250); this.t0 = Date.now(); this.timer = setInterval(() => { if (this.onLevel) this.onLevel(0.2 + Math.random() * 0.6); }, 120); }
    seconds() { return this.t0 ? (Date.now() - this.t0) / 1000 : 0; }
    stop() { const n = Math.max(16000, Math.round(this.seconds() * 16000)); this.cancel(); return new Int16Array(n); }
    cancel() { clearInterval(this.timer); this.timer = null; }
  };
  const STT = [{ id: "stt.exemplo", name: "Fala simulada da prévia" }, { id: "stt.home_assistant_cloud", name: "Home Assistant Cloud" }];

  // Buscar na internet na prévia: as "lojas" são o próprio inventário (itens com foto parecidos com o que foi buscado)
  const norm = (t) => String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  function webFind(d, q) {
    const words = norm(q).split(/[^a-z0-9]+/).filter((w) => w.length >= 3);
    const withPh = d.items.filter((i) => (i.photos || []).length && !(i.photoSrc || {})[i.photos[0]]);
    const score = (i) => words.filter((w) => norm(`${i.name} ${i.details}`).includes(w)).length;
    let hits = withPh.map((i) => [score(i), i]).filter((x) => x[0] > 0).sort((a, b) => b[0] - a[0]).map((x) => x[1]);
    const best = hits[0] || null;
    if (hits.length < 8) hits = hits.concat(withPh.filter((i) => !hits.includes(i) && (!best || i.cat === best.cat)).slice(0, 12));
    const seen = new Set();
    hits = hits.filter((i) => !seen.has(i.photos[0]) && seen.add(i.photos[0])); // a mesma foto de cômodo vale para vários itens
    const results = hits.slice(0, 6).map((i, n) => ({ n, kind: "jpeg", file: i.photos[0], image: "", page: `https://previa.inventaria/produto/${encodeURIComponent(i.id)}`, site: "exemplo da prévia", w: null, h: null }));
    const product = best ? { name: best.name, details: best.details || "", cat: best.cat || "", value: best.value || 0 } : null;
    return { results, product };
  }
  window.INV_WEB_IMG = (job, n) => { const j = ST.jobs.get(job); const r = j && j.results.find((x) => x.n === +n); return r ? `photos/${r.file}` : ""; };

  const EXAMPLES = [
    { name: "Luminária de mesa articulada preta", details: "Luminária de braço articulado em metal preto com cúpula cônica.", cat: "decoracao", qty: "1", value: 90, zone: "", existing: "", confidence: "alta" },
    { name: "Caneca de cerâmica branca", details: "Caneca lisa de cerâmica branca, cerca de 300 ml.", cat: "cozinha", qty: "2", value: 30, zone: "", existing: "", confidence: "media" },
    { name: "Fone de ouvido Bluetooth", details: "Fone over-ear preto dobrável.", cat: "eletronicos", qty: "1", value: 180, zone: "Eletrônicos", existing: "", confidence: "baixa" },
  ];

  async function handle(method, path, body = {}) {
    const d = await data();
    let m;
    if (method === "GET" && path === "api/data") {
      const st = ST.settings;
      return { ...clone(d), rev: ST.rev, version: "%%V%%", user: null, features: { ai: true, share: false },
        settings: { ai_entity: st.ai_entity, ai_search: st.ai_search, ai_chat: st.ai_chat || "", voice_stt: st.voice_stt, ai: st.ai !== false, zones: st.zones === true, ha_sensors: st.ha_sensors === true, news: st.news !== false, news_every: st.news_every || 0, news_notify: st.news_notify || "", bens: st.bens !== false, itens: st.itens !== false, consumiveis: st.consumiveis === true, cons_comodo: st.cons_comodo === true, correria: st.correria === true, accent: st.accent ?? null, accent_daily: st.accent_daily ?? null, news_hora: st.news_hora || "10:00", news_aviso: st.news_aviso === true, news_para: st.news_para || [], news_apps: st.news_apps === true }, correria_uso: null };
    }
    if (method === "GET" && path === "api/rev") return { rev: ST.rev, correria_uso: null };
    if (method === "POST" && path === "api/items") {
      const restore = !!body._restore;
      const it = build(d, body, restore);
      d.items.push(it);
      return { item: clone(it), rev: bump() };
    }
    if (method === "POST" && path === "api/items/batch") {
      const created = (body.items || []).map((b) => { const it = build(d, b, false); d.items.push(it); return it; });
      const rp = body.roomPhoto;
      if (rp && room(d, rp.room) && !room(d, rp.room).photos.some((p) => p.file === rp.file)) room(d, rp.room).photos.push({ file: rp.file, label: rp.label || "" });
      return { items: clone(created), rooms: clone(d.rooms), rev: bump() };
    }
    if (method === "POST" && path === "api/items/bulk") { // Buscar › Selecionar: vários de uma vez, tudo ou nada
      const plan = (body.items || []).map((ch) => {
        const it = d.items.find((i) => i.id === ch.id);
        if (!it) fail("Um dos itens não existe mais. Atualize a página.", 404);
        if ("room" in ch && ch.room !== it.room && !room(d, ch.room)) fail("Escolha um cômodo que exista.");
        if ("cat" in ch && !CATS.has(ch.cat) && !ccatsOf(d).some((c) => (c.id || c[0]) === ch.cat)) fail("Escolha uma categoria que exista.");
        return [it, ch];
      });
      if (!plan.length) fail("Escolha os itens.");
      const t = now();
      for (const [it, ch] of plan) {
        if ("room" in ch && ch.room !== it.room) {
          const used = new Set(d.items.filter((i) => i.room === ch.room).map((i) => i.seq));
          it.seq = ch.seq && !used.has(ch.seq) ? ch.seq : nextSeq(d, ch.room);
          it.room = ch.room;
        }
        if ("cat" in ch) it.cat = ch.cat;
        if ("zone" in ch) it.zone = String(ch.zone || "").trim();
        if ("usedIn" in ch) { if (usados(d, ch.usedIn).length) it.usedIn = usados(d, ch.usedIn); else delete it.usedIn; }
        it.updatedAt = t;
      }
      return { items: clone(plan.map(([it]) => it)), rev: bump() };
    }
    if ((m = path.match(/^api\/items\/([^/]+)$/))) {
      const it = d.items.find((i) => i.id === decodeURIComponent(m[1]));
      if (!it) fail("Este item não existe mais.", 404);
      if (method === "DELETE") { d.items.splice(d.items.indexOf(it), 1); return { item: clone(it), rev: bump() }; }
      if (method === "PUT") {
        if (body._base && body._base !== it.updatedAt) fail("Este item foi alterado em outro aparelho.", 409, { item: clone(it) });
        if (body.room && body.room !== it.room) { if (!room(d, body.room)) fail("Escolha um cômodo que exista."); it.room = body.room; it.seq = nextSeq(d, body.room); }
        for (const k of ["zone", "details", "flag", "source"]) if (k in body) it[k] = typeof body[k] === "string" ? body[k].trim() : body[k];
        if ("name" in body) { const n = String(body.name || "").trim(); if (!n) fail("Preencha o campo nome."); it.name = n; }
        if (isCons(d, it.room)) { it.cat = consCat(d, "cat" in body ? body.cat : it.cat); if ("dur" in body) { if (dur(body.dur) !== dur(it.dur)) it.durAt = now(); it.dur = dur(body.dur); }
          if ("usedIn" in body) { if (usados(d, body.usedIn).length) it.usedIn = usados(d, body.usedIn); else delete it.usedIn; } }
        else {
          it.cat = CATS.has("cat" in body ? body.cat : it.cat) ? ("cat" in body ? body.cat : it.cat) : "outros";
          if ("qty" in body) it.qty = String(body.qty || "1").trim() || "1";
          if ("value" in body) it.value = money(body.value);
        }
        if ("photos" in body) it.photos = [...(body.photos || [])];
        if ("photos" in body || "photoSrc" in body) {
          const src = Object.fromEntries(Object.entries(body.photoSrc || it.photoSrc || {}).filter(([f]) => it.photos.includes(f)));
          if (Object.keys(src).length) it.photoSrc = src; else delete it.photoSrc;
        }
        it.updatedAt = now();
        return { item: clone(it), rev: bump() };
      }
    }
    if (method === "POST" && path === "api/cats" && body.kind === "consumiveis") {
      const cats = ccatsOf(d), name = String(body.name || "").trim().replace(/\s+/g, " ");
      if (!name) fail("Preencha o campo nome da categoria.");
      if (cats.some((c) => foldName(c.name) === foldName(name))) fail(`Já existe a categoria ${name}.`);
      const base = "c-" + (foldName(name).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 34) || "categoria");
      let id = base, n = 2;
      while (cats.some((c) => c.id === id)) id = `${base}-${n++}`;
      const cat = { id, name };
      const at = cats.findIndex((c) => c.id === "c-outros");
      cats.splice(at < 0 ? cats.length : at, 0, cat);
      return { cat: clone(cat), cats: clone(catsOf(d)), consCats: clone(cats), rev: bump() };
    }
    if ((m = path.match(/^api\/cats\/(c-[a-z0-9_-]+)$/)) && ccatsOf(d).some((c) => c.id === m[1])) {
      const cats = ccatsOf(d), cat = cats.find((c) => c.id === m[1]);
      if (method === "PUT") {
        const name = String(body.name || "").trim().replace(/\s+/g, " ");
        if (!name) fail("Preencha o campo nome da categoria.");
        if (cats.some((c) => c.id !== cat.id && foldName(c.name) === foldName(name))) fail(`Já existe a categoria ${name}.`);
        cat.name = name;
        return { cat: clone(cat), cats: clone(catsOf(d)), consCats: clone(cats), rev: bump() };
      }
      if (method === "DELETE") {
        if (cat.id === "c-outros") fail("A categoria Outros não pode ser apagada.");
        let moved = 0;
        d.items.forEach((i) => { if (i.cat === cat.id) { i.cat = "c-outros"; moved++; } });
        cats.splice(cats.indexOf(cat), 1);
        return { moved, cats: clone(catsOf(d)), consCats: clone(cats), rev: bump() };
      }
    }
    if (method === "POST" && path === "api/cats") {
      const cats = catsOf(d), name = String(body.name || "").trim().replace(/\s+/g, " ");
      if (!name) fail("Preencha o campo nome da categoria.");
      if (cats.some((c) => foldName(c.name) === foldName(name))) fail(`Já existe a categoria ${name}.`);
      const base = foldName(name).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 36) || "categoria";
      let id = base, n = 2;
      while (cats.some((c) => c.id === id)) id = `${base}-${n++}`;
      const cat = { id, name };
      const at = cats.findIndex((c) => c.id === "outros");
      cats.splice(at < 0 ? cats.length : at, 0, cat);
      return { cat: clone(cat), cats: clone(cats), rev: bump() };
    }
    if ((m = path.match(/^api\/cats\/([a-z0-9_-]+)$/))) {
      const cats = catsOf(d), cat = cats.find((c) => c.id === m[1]);
      if (!cat) fail("Esta categoria não existe mais.", 404);
      if (["eletronicos", "utilidades", "veiculos"].includes(cat.id)) fail(`${cat.name} é uma categoria fixa (as novidades e os recursos): não dá para ${method === "PUT" ? "renomear" : "apagar"}.`);
      if (method === "PUT") {
        const name = String(body.name || "").trim().replace(/\s+/g, " ");
        if (!name) fail("Preencha o campo nome da categoria.");
        if (cats.some((c) => c.id !== cat.id && foldName(c.name) === foldName(name))) fail(`Já existe a categoria ${name}.`);
        cat.name = name;
        return { cat: clone(cat), cats: clone(cats), rev: bump() };
      }
      if (method === "DELETE") {
        if (cat.id === "outros") fail("A categoria Outros não pode ser apagada.");
        let moved = 0;
        d.items.forEach((i) => { if (i.cat === cat.id) { i.cat = "outros"; moved++; } });
        cats.splice(cats.indexOf(cat), 1);
        return { moved, cats: clone(cats), rev: bump() };
      }
    }
    if (method === "POST" && path === "api/rooms" && body.kind === "bens") { // a área Bens (fora de casa): criada uma vez
      if (ST.settings.bens === false) fail("Os bens estão desligados. Para usar, ligue em Mais > Configurações > Opções.", 409);
      let r = d.rooms.find((x) => x.kind === "bens");
      if (!r) {
        r = { id: room(d, "bens") ? "bens-2" : "bens", code: d.rooms.some((x) => x.code === "BEN") ? "BEN2" : "BEN", name: "Bens", kind: "bens", order: d.rooms.length, cover: 0, photos: [], updatedAt: now() };
        d.rooms.push(r);
        const cats = catsOf(d), at = cats.findIndex((c) => c.id === "outros");
        for (const [id, name] of [["imoveis", "Imóveis"], ["veiculos", "Veículos"]]) if (!cats.some((c) => c.id === id)) cats.splice(at < 0 ? cats.length : at, 0, { id, name });
      }
      return { room: clone(r), rooms: clone(d.rooms), cats: clone(catsOf(d)), rev: bump() };
    }
    if (method === "POST" && path === "api/rooms" && body.kind === "consumiveis") { // 1.78.0: a área Consumíveis (o que se gasta): criada uma vez
      if (ST.settings.consumiveis !== true) fail("Os consumíveis estão desligados. Para usar, ligue em Mais > Configurações > Opções.", 409);
      let r = d.rooms.find((x) => x.kind === "consumiveis");
      if (!r) {
        r = { id: room(d, "consumiveis") ? "consumiveis-2" : "consumiveis", code: d.rooms.some((x) => x.code === "CON") ? "CON2" : "CON", name: "Consumíveis", kind: "consumiveis", order: d.rooms.length, cover: 0, photos: [], updatedAt: now() };
        d.rooms.push(r);
        d.rooms.sort((a, b) => kindRank(a) - kindRank(b) || a.order - b.order).forEach((x, i) => { x.order = i; });
      }
      return { room: clone(r), rooms: clone(d.rooms), cats: clone(catsOf(d)), rev: bump() };
    }
    if (method === "POST" && path === "api/rooms") {
      const name = String(body.name || "").trim();
      if (!name) fail("Dê um nome ao cômodo.");
      let id = name.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "comodo";
      while (room(d, id)) id += "-2";
      let code = String(body.code || name).normalize("NFD").replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 4) || "CMD";
      if (d.rooms.some((r) => r.code === code)) code = code.slice(0, 3) + "2";
      const geral = room(d, "geral");
      const r = { id, code, name, order: geral ? geral.order - 0.5 : d.rooms.length, cover: 0, photos: [], updatedAt: now() };
      d.rooms.push(r);
      d.rooms.sort((a, b) => kindRank(a) - kindRank(b) || a.order - b.order).forEach((x, i) => { x.order = i; });
      return { room: clone(r), rooms: clone(d.rooms), rev: bump() };
    }
    if (method === "POST" && path === "api/rooms/order") {
      const pos = new Map((body.ids || []).map((id, i) => [id, i]));
      d.rooms.forEach((r) => { r.order = pos.has(r.id) ? pos.get(r.id) : 999; });
      d.rooms.sort((a, b) => kindRank(a) - kindRank(b) || a.order - b.order).forEach((x, i) => { x.order = i; });
      return { rooms: clone(d.rooms), rev: bump() };
    }
    if ((m = path.match(/^api\/rooms\/([^/]+)\/photos$/)) && method === "POST") {
      const r = room(d, decodeURIComponent(m[1]));
      if (!r) fail("Este cômodo não existe mais.", 404);
      if (!r.photos.some((p) => p.file === body.file)) r.photos.push({ file: body.file, label: body.label || "" });
      return { room: clone(r), rev: bump() };
    }
    if ((m = path.match(/^api\/rooms\/([^/]+)$/))) {
      const r = room(d, decodeURIComponent(m[1]));
      if (!r) fail("Este cômodo não existe mais.", 404);
      if (method === "DELETE") {
        if (d.items.some((i) => i.room === r.id)) fail("Mova ou apague os itens deste cômodo antes de apagá-lo.");
        d.rooms.splice(d.rooms.indexOf(r), 1);
        return { room: clone(r), rooms: clone(d.rooms), rev: bump() };
      }
      if (method === "PUT") {
        if ("name" in body) { const n = String(body.name || "").trim(); if (!n) fail("Dê um nome ao cômodo."); r.name = n; }
        if ("code" in body) {
          const c = String(body.code || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 4);
          if (!c) fail("O código precisa ter de 1 a 4 letras ou números.");
          if (d.rooms.some((x) => x.code === c && x.id !== r.id)) fail(`O código ${c} já é usado por outro cômodo.`);
          r.code = c;
        }
        if ("photos" in body) r.photos = clone(body.photos || []);
        if ("cover" in body) r.cover = Number.isInteger(body.cover) && body.cover < Math.max(1, r.photos.length) ? body.cover : 0;
        if (r.cover >= Math.max(1, r.photos.length)) r.cover = 0;
        r.updatedAt = now();
        return { room: clone(r), rev: bump() };
      }
    }
    if (method === "POST" && path === "api/photos") {
      return { file: `previa-${Date.now()}-${Math.random().toString(16).slice(2, 8)}.jpg` };
    }
    if (method === "GET" && path === "api/ai/status") {
      return { ready: true, preview: true, reason: null, entities: [{ id: "ai_task.exemplo", name: "Exemplo simulado", attachments: true }],
        agents: [{ id: "conversation.exemplo", name: "Assistente de exemplo" }], selected: ST.settings.ai_entity || "", chat: ST.settings.ai_chat || "", search: ST.settings.ai_search || "" };
    }
    const aiOff = () => { if (ST.settings.ai === false) fail("A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações.", 409); };
    if (method === "GET" && path.startsWith("api/voice/status")) {
      const sel = STT.find((e) => e.id === ST.settings.voice_stt);
      return { ready: true, engine: (sel || STT[0]).id, language: "pt-BR", name: (sel || STT[0]).name, assistant: sel ? "" : "Assistente de exemplo",
        engines: clone(STT), selected: ST.settings.voice_stt || "", missing: false };
    }
    if (method === "POST" && path === "api/voice") { aiOff(); await wait(900); return { text: SPEECH, engine: "stt.exemplo", name: STT[0].name }; }
    // a IA escolhe o cômodo de cada item pelo nome dos cômodos da casa (o que não der para saber fica para a pessoa)
    const guessRoom = (re) => { const r = d.rooms.find((x) => !x.kind && re.test(x.name.normalize("NFD").replace(/[\u0300-\u036f]/g, ""))); return r ? r.id : ""; };
    const fixedRoom = () => (d.rooms.some((x) => x.id === body.room && !x.kind) ? body.room : "");
    if (method === "POST" && path === "api/ai/text") {
      aiOff(); await wait(1600);
      const items = clone(SPOKEN).map((it, i) => ({ ...it, room: (i < 2 ? guessRoom(/cozinha/i) : "") || fixedRoom() }));
      const one = new Set(items.map((it) => it.room)).size === 1 ? items[0].room : "";
      return { items, room: one, example: true };
    }
    if (method === "POST" && path === "api/web-photos") {
      aiOff();
      const id = Math.random().toString(16).slice(2, 10).padEnd(8, "0") + Math.random().toString(16).slice(2, 10).padEnd(8, "0");
      ST.jobs.set(id, { at: Date.now(), ...webFind(d, body.name) });
      return { id };
    }
    if ((m = path.match(/^api\/web-photos\/([a-f0-9]+)$/))) {
      const j = ST.jobs.get(m[1]);
      if (method === "DELETE") { ST.jobs.delete(m[1]); return { ok: true }; }
      if (!j) fail("Esta busca terminou. Busque de novo.", 404);
      aiOff();
      const t = Date.now() - j.at;
      if (t < 1600) return { stage: "busy", msg: t < 800 ? "Procurando o produto na internet…" : "Conferindo as fotos das páginas…", results: [] };
      if (!j.results.length) return { stage: "error", msg: "Não achei fotos desse produto nas páginas que a IA encontrou. Tente buscar só pela marca e o modelo.", results: [], product: j.product };
      return { stage: "done", msg: "", results: j.results.map(({ file, ...r }) => r), product: j.product, example: true };
    }
    // Novidades de todos: a "IA" da prévia escolhe os eletrônicos e aparelhos, e cada um ganha as novidades de exemplo
    const newsCats = () => ["eletronicos"].filter((c) => CATS.has(c)); // só Eletrônicos, como o servidor
    const PICK = /\b(tv|televis|notebook|computador|celular|tablet|geladeira|micro-?ondas|maquina|lavadora|lampada|fone|soundbar|cafeteira|ar.condicionado|aspirador|roteador|impressora|monitor|console|camera|forno)/i;
    const plain = (t) => String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const exampleNews = (name) => {
      const y = new Date().getFullYear();
      return { produto: name, novidades: [
        { tipo: "atualizacao", titulo: "Atualização de software com correções", resumo: "O fabricante liberou uma versão nova, com correções de estabilidade.", data: `${y}-09`, fonte: "https://exemplo.com/atualizacao", site: "exemplo.com", boato: false },
        { tipo: "sucessor", titulo: "Modelo novo da mesma linha anunciado", resumo: "A geração seguinte chega com melhorias de consumo e conexão.", data: `${y}-10`, fonte: "https://exemplo.com/lancamento", site: "exemplo.com", boato: false },
        { tipo: "lancamento", titulo: "Versão nova pode chegar no próximo ano", resumo: "Sites de tecnologia falam de uma versão nova; o fabricante não confirmou.", data: "", fonte: "https://exemplo.com/rumor", site: "exemplo.com", boato: true },
      ].sort((a, b) => (b.data || "0").localeCompare(a.data || "0")).slice(0, 3) }; // só as 3 mais recentes, como o servidor
    };
    // o mesmo equipamento em vários cômodos (no plural, noutra cor ou noutra ordem) é um só (como news_group_key do servidor)
    const NOISE = new Set(("de da do das dos com sem e em para pra a o as os na no nas nos and with the of cor preto preta branco branca cinza prata " +
      "prateado prateada dourado dourada azul azui vermelho vermelha verde rosa roxo roxa lila amarelo amarela laranja bege marrom grafite chumbo " +
      "vinho creme nude champagne titanio black white silver gray grey gold blue red green pink purple graphite").split(" "));
    const groupKey = (it) => {
      const words = (plain(it.name).match(/[a-z0-9]+(?:-[a-z0-9]+)*/g) || []).map((w) => (w.length > 3 && w.endsWith("s") && !/\d/.test(w) ? w.slice(0, -1) : w));
      const codes = [...new Set(words.filter((w) => w.length >= 3 && /\d/.test(w) && /[a-z]/.test(w)))].sort();
      if (codes.length && words.length) return `${words[0]}|${codes.join(" ")}`;
      return [...new Set(words.filter((w) => !NOISE.has(w)))].sort().join(" ") || words.join(" ");
    };
    const sameGroup = (it) => d.items.filter((x) => groupKey(x) === groupKey(it));
    const newsJobOf = () => [...ST.jobs.entries()].find(([, j]) => j.lote && !j.done);
    // Apps do celular (1.56.0): os apps de exemplo de dois celulares (no Home Assistant, vêm do sensor Último app usado)
    const APPS = [["com.exemplo.casaconectada", "Casa Conectada", ["Ana"]], ["com.exemplo.musicaja", "Música Já", ["Ana", "Beto"]],
      ["com.exemplo.mercadinho", "Mercadinho", ["Beto"]], ["com.android.launcher3", "Tela inicial", ["Ana", "Beto"]]];
    const appsOn = () => ST.settings.news_apps === true && ST.settings.news !== false;
    const exampleAppNews = (name) => ({ produto: name, novidades: [
      { tipo: "atualizacao", titulo: "Novo modo de economia de bateria", resumo: "Exemplo da prévia: no Home Assistant, a IA busca as novidades deste app.", data: `${new Date().getFullYear()}-10`, fonte: "https://exemplo.com/blog", site: "exemplo.com", boato: false }] });
    // 1.62.0: a que não estava na conferência anterior ganha nova: true (como news_mark do servidor)
    const markNews = (before, found, fora = []) => {
      const tira = new Set(fora), todas = found.novidades;
      found = { ...found, novidades: todas.filter((x) => !tira.has(x.fonte) && !tira.has(plain(x.titulo))) };
      found.apagadas = todas.length - found.novidades.length;
      const prev = new Set(((before && before.novidades) || []).flatMap((x) => [x.fonte, plain(x.titulo)]));
      const at = new Date().toISOString();
      return { ...found, novidades: found.novidades.map((x) => {
        const old = ((before && before.novidades) || []).find((o) => o.fonte === x.fonte || plain(o.titulo) === plain(x.titulo));
        return prev.has(x.fonte) || prev.has(plain(x.titulo)) ? (old && old.desde ? { ...x, desde: old.desde } : { ...x }) : { ...x, desde: at, nova: true };
      }) };
    };
    // 1.66.0: Renomear (apps_nomes); 1.68.0: Apagar (apps_fora)
    const appsList = () => ({ sensores: 2, celulares: ["Ana", "Beto"], lista: APPS.filter(([pacote]) => !(ST.news.apps_fora || []).includes(pacote)).map(([pacote, nome, pessoas]) => {
      const t = ST.news.apps_triagem[pacote], novo = (ST.news.apps_nomes || {})[pacote];
      return { pacote, nome: novo || nome, ...(novo ? { renomeado: true } : {}), pessoas, ultimo: new Date().toISOString(), conferir: t ? t.conferir : null, manual: !!(t && t.manual), res: ST.news.apps[pacote] || null };
    }) });
    const newsTick = (j) => { // a conferência anda com o relógio: um item a cada 0,7 s
      const n = Math.min(j.todo.length, Math.floor((Date.now() - j.at) / 700));
      for (const it of j.todo.slice(j.saved, n)) {
        if (it.rec) { // 1.68.0: Só eletrônicos (e Todas): os recursos dos que ainda não têm
          for (const x of sameGroup(it)) if (!(ST.rec || {})[x.id]) ST.rec = { ...(ST.rec || {}), [x.id]: { recursos: [{ nome: "Wi-Fi", detalhe: "Exemplo da prévia: no Home Assistant, a IA diz os recursos deste modelo." }, { nome: "Timer", detalhe: "Programa a hora de ligar e desligar." }], fonte: "", at: new Date().toISOString() } };
          j.recs = (j.recs || 0) + 1;
          continue;
        }
        const news = it.app ? markNews((ST.news.apps[it.app] || {}).news, exampleAppNews(it.name), (ST.news.apps_apagadas || {})[it.app]) : markNews((ST.news.itens[it.id] || {}).news, exampleNews(it.name), (ST.news.apagadas || {})[it.id]);
        if (news.novidades.some((x) => x.nova)) j.novos = (j.novos || 0) + 1;
        if (it.app) ST.news.apps[it.app] = { at: new Date().toISOString(), news };
        else for (const x of sameGroup(it)) ST.news.itens[x.id] = { at: new Date().toISOString(), news };
      }
      j.saved = n;
      if (n >= j.todo.length && !j.done) {
        j.done = true;
        const conf = n - (j.recs || 0);
        j.summary = { conferidos: conf, com_novidades: conf, novos: j.novos || 0, selecionados: conf, em_dia: 0, erros: 0, recursos: j.recs || 0 };
        if (j.so !== "recursos") ST.news.ultima = { at: new Date().toISOString(), ...j.summary };
      }
      return n;
    };
    if (method === "GET" && path.startsWith("api/news?item=")) {
      aiOff();
      return ST.news.itens[decodeURIComponent(path.slice("api/news?item=".length))] || {};
    }
    if (method === "GET" && path === "api/news") {
      aiOff();
      const cats = newsCats(), tri = ST.news.triagem;
      const live = newsJobOf();
      if (live) newsTick(live[1]);
      const lj = newsJobOf();
      const grupos = Object.fromEntries(d.items.filter((i) => cats.includes(i.cat) || i.id in ST.news.itens).map((i) => [i.id, groupKey(i)]));
      return { cats, triagem: { ...tri }, grupos, pendentes: d.items.filter((i) => cats.includes(i.cat) && !(i.id in tri)).length,
        itens: { ...ST.news.itens }, ultima: ST.news.ultima, job: lj ? { id: lj[0], stage: "busy", msg: "Conferindo…", progress: null, summary: null } : null,
        apps: appsOn() ? appsList() : null };
    }
    if (method === "DELETE" && path.startsWith("api/news?item=")) { // 1.63.0: Apagar as de um equipamento (e dos outros cômodos com o mesmo)
      const it = d.items.find((i) => i.id === decodeURIComponent(path.slice("api/news?item=".length)));
      if (!it) fail("Item não encontrado.", 404);
      ST.news.apagadas = ST.news.apagadas || {};
      for (const x of sameGroup(it)) {
        const v = ST.news.itens[x.id];
        if (!v) continue;
        ST.news.apagadas[x.id] = [...(ST.news.apagadas[x.id] || []), ...v.news.novidades.flatMap((n) => [n.fonte, plain(n.titulo)])];
        v.news = { ...v.news, novidades: [], apagadas: v.news.novidades.length + (v.news.apagadas || 0) };
      }
      return ST.news.itens[it.id] || {};
    }
    if (method === "DELETE" && path.startsWith("api/news?pacote=")) { // 1.70.0: Apagar as de um app
      const pkg = decodeURIComponent(path.slice("api/news?pacote=".length));
      const v = ST.news.apps[pkg];
      if (!v || !v.news) fail("Este app não tem novidades.", 404);
      ST.news.apps_apagadas = ST.news.apps_apagadas || {};
      ST.news.apps_apagadas[pkg] = [...(ST.news.apps_apagadas[pkg] || []), ...v.news.novidades.flatMap((n) => [n.fonte, plain(n.titulo)])];
      v.news = { ...v.news, novidades: [], apagadas: v.news.novidades.length + (v.news.apagadas || 0) };
      return v;
    }
    if (method === "DELETE" && path === "api/news") {
      for (const [id, j] of ST.jobs) if (j.lote) { j.done = true; ST.jobs.delete(id); }
      const manual = Object.fromEntries(Object.entries(ST.news.apps_triagem).filter(([, v]) => v.manual)); // a escolha da pessoa fica
      ST.news = { itens: {}, triagem: {}, ultima: null, apps: {}, apps_triagem: manual, apagadas: {} };
      return handle("GET", "api/news", {});
    }
    if (method === "PUT" && path === "api/news/app/nome") {
      aiOff();
      const nome = String(body.nome || "").split(/\s+/).filter(Boolean).join(" ");
      ST.news.apps_nomes = { ...(ST.news.apps_nomes || {}) };
      if (nome) ST.news.apps_nomes[body.pacote] = nome; else delete ST.news.apps_nomes[body.pacote];
      return handle("GET", "api/news", {});
    }
    if (method === "DELETE" && path.startsWith("api/news/app?pacote=")) {
      aiOff();
      const p = decodeURIComponent(path.slice("api/news/app?pacote=".length));
      ST.news.apps_fora = [...(ST.news.apps_fora || []), p];
      delete ST.news.apps[p]; delete ST.news.apps_triagem[p];
      return handle("GET", "api/news", {});
    }
    if (method === "POST" && path === "api/news/visto") { // 1.68.0: abriu: deixam de ser novas
      aiOff();
      const alvos = body.item ? sameGroup(d.items.find((i) => i.id === body.item) || { name: "" }).map((x) => ST.news.itens[x.id]) : [ST.news.apps[body.pacote]];
      let n = 0;
      for (const v of alvos) for (const x of ((v && v.news && v.news.novidades) || [])) if (x.nova) { delete x.nova; n++; }
      return { vistas: n };
    }
    if (method === "PUT" && path === "api/news/app") {
      const a = APPS.find((x) => x[0] === body.pacote);
      if (!a) fail("App não encontrado.", 404);
      ST.news.apps_triagem[a[0]] = { conferir: body.acompanhar === true, manual: true };
      if (body.acompanhar !== true) delete ST.news.apps[a[0]];
      return handle("GET", "api/news", {});
    }
    // Encontrar apps com IA (1.59.0): na prévia, a "IA" acha sempre os mesmos apps
    if (method === "POST" && path === "api/news/apps/ler") {
      aiOff();
      if (!(body.fotos || []).length && !String(body.texto || "").trim()) fail("Escolha os prints ou cole os nomes dos apps.");
      const ja = new Set(APPS.map((x) => x[1]));
      return { apps: [["com.exemplo.casaconectada", "Casa Conectada", false], ["com.exemplo.bancolua", "Banco Lua", false], ["", "Mapa Fácil", false], ["com.android.settings", "Configurações", true]]
        .map(([pacote, nome, sistema]) => ({ id: pacote || "ia." + plain(nome).replace(/[^a-z0-9]+/g, "_"), nome, pacote, sistema, ja: ja.has(nome) })) };
    }
    if (method === "POST" && path === "api/news/apps/adicionar") {
      let n = 0;
      for (const x of body.apps || []) {
        const id = x.pacote || x.id;
        if (APPS.some((a) => a[0] === id || a[1] === x.nome)) continue;
        APPS.push([id, x.nome, ["Ana"]]); ST.news.apps_triagem[id] = { conferir: true, manual: true }; n++;
      }
      return { ...handle("GET", "api/news", {}), adicionados: n };
    }
    if (method === "POST" && path === "api/news/app") {
      aiOff();
      const a = APPS.find((x) => x[0] === body.pacote);
      if (!a) fail("App não encontrado.", 404);
      const id = Math.random().toString(16).slice(2, 10).padEnd(8, "0") + Math.random().toString(16).slice(2, 10).padEnd(8, "0");
      ST.jobs.set(id, { at: Date.now(), news: true, name: a[1], app: a[0] });
      return { id };
    }
    if (method === "POST" && path === "api/news/all") {
      aiOff();
      const live = newsJobOf();
      if (live) return { id: live[0] };
      const so = (body && body.so) || ""; // Todas as novidades, Só equipamentos (itens), Só apps (apps) ou Só eletrônicos (recursos)
      const cats = so === "apps" || so === "recursos" ? [] : newsCats();
      for (const i of d.items) if (cats.includes(i.cat) && !(i.id in ST.news.triagem)) ST.news.triagem[i.id] = PICK.test(plain(i.name));
      const week = Date.now() - 7 * 864e5;
      const seen = new Set();
      const todo = d.items.filter((i) => cats.includes(i.cat) && (ST.news.triagem[i.id] || ST.news.itens[i.id]) && !(ST.news.itens[i.id] && Date.parse(ST.news.itens[i.id].at) > week))
        .filter((i) => !seen.has(groupKey(i)) && seen.add(groupKey(i))); // uma busca por equipamento
      if (appsOn() && (so === "" || so === "apps")) { // e os apps: a "IA" deixa a tela inicial de fora
        for (const [p] of APPS) if (!ST.news.apps_triagem[p]) ST.news.apps_triagem[p] = { conferir: !/launcher/.test(p) };
        for (const [p, name] of APPS) if ((ST.news.apps_triagem[p].conferir || ST.news.apps[p]) && !(ST.news.apps[p] && Date.parse(ST.news.apps[p].at) > week)) todo.push({ name, app: p });
      }
      const id = Math.random().toString(16).slice(2, 10).padEnd(8, "0") + Math.random().toString(16).slice(2, 10).padEnd(8, "0");
      if (so === "" || so === "recursos") { // os recursos dos eletrônicos que ainda não têm, um por equipamento
        const vistos = new Set();
        for (const i of d.items.filter((x) => x.cat === "eletronicos")) {
          if (vistos.has(groupKey(i))) continue;
          vistos.add(groupKey(i));
          if (!sameGroup(i).some((x) => (ST.rec || {})[x.id])) todo.push({ rec: true, id: i.id, name: i.name });
        }
      }
      ST.jobs.set(id, { lote: true, so, at: Date.now(), todo, saved: 0, done: false });
      return { id };
    }
    if ((m = path.match(/^api\/news\/([a-f0-9]+)$/)) && ST.jobs.get(m[1]) && ST.jobs.get(m[1]).lote) {
      const j = ST.jobs.get(m[1]);
      if (method === "DELETE") { j.done = true; ST.jobs.delete(m[1]); return { ok: true }; }
      aiOff();
      const n = newsTick(j);
      if (!j.done) return { stage: "busy", msg: `Conferindo ${n + 1} de ${j.todo.length}: ${j.todo[n].name}`, progress: { feitos: n, total: j.todo.length, atual: j.todo[n].name } };
      return { stage: "done", msg: "", summary: { ...(j.summary || ST.news.ultima) }, example: true };
    }
    if (method === "POST" && path === "api/chat") {
      aiOff();
      await wait(900);
      const last = [...(body.messages || [])].reverse().find((m) => m.role === "user");
      if ((body.anexos || []).length) return { reply: `Exemplo da prévia: no Home Assistant, a IA olha ${body.anexos.length > 1 ? `os ${body.anexos.length} arquivos` : "o arquivo"} e responde de verdade.`, entity: "ai_task.exemplo" };
      return { reply: `Exemplo da prévia: no Home Assistant, a IA responde de verdade, com os dados desta tela.\n- Você perguntou: “${String(last ? last.text : "").slice(0, 120)}”`, entity: "ai_task.exemplo" };
    }
    // Recursos (1.54.0): o que o equipamento tem, ditos pela IA (aqui, um exemplo)
    if (method === "GET" && path.startsWith("api/recursos?item=")) {
      aiOff();
      return (ST.rec || {})[decodeURIComponent(path.slice("api/recursos?item=".length))] || {};
    }
    // Novidades › Eletrônicos (1.65.0): os recursos de todos os eletrônicos; a busca de todos completa os que faltam
    const recDe = (id) => { const r = (ST.rec || {})[id]; return r ? { n: r.recursos.length, at: r.at } : null; };
    if (method === "GET" && path === "api/recursos/todos") {
      aiOff();
      const els = d.items.filter((i) => i.cat === "eletronicos");
      return { itens: Object.fromEntries(els.map((i) => [i.id, recDe(i.id)])), grupos: Object.fromEntries(els.map((i) => [i.id, groupKey(i)])) };
    }
    if (method === "POST" && path === "api/recursos") {
      aiOff();
      const it = d.items.find((i) => i.id === body.item);
      if (!it) fail("Item não encontrado.", 404);
      const id = Math.random().toString(16).slice(2, 10).padEnd(8, "0") + Math.random().toString(16).slice(2, 10).padEnd(8, "0");
      ST.jobs.set(id, { at: Date.now(), rec: true, item: it.id });
      return { id };
    }
    if ((m = path.match(/^api\/recursos\/([a-f0-9]+)$/))) {
      const j = ST.jobs.get(m[1]);
      if (method === "DELETE") { ST.jobs.delete(m[1]); return { ok: true }; }
      if (!j) fail("Esta busca terminou. Veja de novo.", 404);
      if (Date.now() - j.at < 1200) return { stage: "busy", msg: "Procurando os recursos…" };
      const rec = { recursos: [{ nome: "Wi-Fi", detalhe: "Exemplo da prévia: no Home Assistant, a IA diz os recursos deste modelo." }, { nome: "Timer", detalhe: "Programa a hora de ligar e desligar." }], fonte: "", at: new Date().toISOString() };
      ST.rec = { ...(ST.rec || {}), [j.item]: rec };
      return { stage: "done", msg: "", rec };
    }
    if (method === "POST" && path === "api/news") {
      aiOff();
      const it = d.items.find((i) => i.id === body.item);
      if (!it) fail("Item não encontrado.", 404);
      const id = Math.random().toString(16).slice(2, 10).padEnd(8, "0") + Math.random().toString(16).slice(2, 10).padEnd(8, "0");
      ST.jobs.set(id, { at: Date.now(), news: true, name: it.name, item: it.id });
      return { id };
    }
    if ((m = path.match(/^api\/news\/([a-f0-9]+)$/))) {
      const j = ST.jobs.get(m[1]);
      if (method === "DELETE") { ST.jobs.delete(m[1]); return { ok: true }; }
      if (!j) fail("Esta busca terminou. Busque de novo.", 404);
      aiOff();
      if (Date.now() - j.at < 1600) return { stage: "busy", msg: "Procurando novidades…" };
      if (j.app) { const news = markNews((ST.news.apps[j.app] || {}).news, exampleAppNews(j.name), (ST.news.apps_apagadas || {})[j.app]); ST.news.apps[j.app] = { at: new Date().toISOString(), news }; return { stage: "done", msg: "", example: true, news }; }
      const news = markNews((ST.news.itens[j.item] || {}).news, exampleNews(j.name), (ST.news.apagadas || {})[j.item]);
      const it = d.items.find((i) => i.id === j.item);
      for (const x of it ? sameGroup(it) : [{ id: j.item }]) ST.news.itens[x.id] = { at: new Date().toISOString(), news };
      return { stage: "done", msg: "", example: true, news };
    }
    if (method === "POST" && path === "api/ai/identify") {
      await wait(2400);
      const linked = d.items.filter((i) => (i.photos || []).includes(body.file));
      let items;
      if (linked.length) {
        items = linked.slice(0, 25).map((i) => ({ name: i.name, details: i.details, cat: i.cat, qty: String(i.qty).replace(/^~/, ""), value: i.value, zone: i.zone, existing: i.name, confidence: "alta" }));
        if (body.mode === "single") items = [{ ...items[0], existing: "" }];
      } else {
        items = body.mode === "single" ? EXAMPLES.slice(0, 1) : clone(EXAMPLES);
        if (body.mode === "single" && body.consumivel) items = [{ name: "Pasta térmica", details: "Pasta que vai entre o processador e o cooler, para o calor passar. Seringa de 4 g.", cat: "c-manutencao", qty: "1", value: 0, dur: 365, zone: "", existing: "", confidence: "alta" }];
      }
      const room = fixedRoom() || (linked.length ? linked[0].room : guessRoom(/escrit|quarto/i));
      items = items.map((it) => ({ ...it, room }));
      return { items, room, entity: "ai_task.exemplo", example: true };
    }
    if (method === "GET" && path === "api/news/people") return { people: [{ id: "person.ana", name: "Ana", phone: true, eu: true }, { id: "person.beto", name: "Beto", phone: true, eu: false }] };
    if (method === "POST" && path === "api/news/notify-test") return { ok: true, sent: body.who === "todos" ? 2 : 1, example: true };
    if (path === "api/settings") {
      if (method === "PUT") {
        const t = { itens: ST.settings.itens !== false, bens: ST.settings.bens !== false, consumiveis: ST.settings.consumiveis === true, ...body };
        if (!t.itens && !t.bens && !t.consumiveis) fail("Pelo menos um fica ligado: itens da casa, bens ou consumíveis.", 409);
        Object.assign(ST.settings, body);
      }
      return { ...ST.settings };
    }
    if (path === "api/backups") fail(OFF + "os backups vão para a pasta share/inventario.");
    if (path === "api/history") {
      const t = Date.now(), n = d.items.length, at = (min) => new Date(t - min * 60000).toISOString();
      return { history: [{ name: "a", date: at(12), items: n, rooms: d.rooms.length, reason: "auto" },
        { name: "b", date: at(190), items: Math.max(0, n - 3), rooms: d.rooms.length, reason: "import" },
        { name: "c", date: at(1500), items: Math.max(0, n - 7), rooms: d.rooms.length, reason: "auto" }] };
    }
    if (method === "POST" && path === "api/erase") { d.rooms = []; d.items = []; return { ok: true, rev: bump() }; } // Começar do zero
    if (path === "api/history/restore") fail(OFF + "a versão escolhida volta, e o app guarda antes uma cópia do que existe hoje.");
    if (path === "api/upload" || path.startsWith("api/upload/")) fail(OFF + "a importação traz o backup com fotos para dentro do app.");
    if (method === "POST" && path === "api/import") {
      if (!body.data || !Array.isArray(body.data.rooms) || !Array.isArray(body.data.items)) fail("Arquivo inválido: não parece um inventário.");
      ST.data = clone(body.data);
      return { ok: true, rev: bump() };
    }
    fail(OFF + "esta função funciona normalmente.");
  }

  window.INV_BACKEND = async (method, path, body) => {
    await wait(40);
    return handle(method, path, body);
  };
})();
