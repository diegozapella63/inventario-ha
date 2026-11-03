"""O que os testes visuais usam em comum.

Cada teste sobe o app (com a casa de teste fictícia e a IA simulada do próprio app), abre o Chromium (Playwright)
como celular, celular estreito, tablet ou computador, clica e confere o que aparece, e grava capturas de tela
em $E2E_TMP/shots. Saída: uma linha "PASS ..." ou "FAIL ..." por conferência e, no fim, o total.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.dirname(HERE)
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)
import helpers  # noqa: E402
from helpers import AppServer, FakeHA, FakeSite  # noqa: E402,F401

TMP = os.environ.get("E2E_TMP") or os.path.join(os.environ.get("TMPDIR", "/tmp"), "inventaria-e2e")
SHOTS = os.path.join(TMP, "shots")
os.makedirs(SHOTS, exist_ok=True)
COV = os.environ.get("E2E_COV")  # pasta: grava a cobertura do app.js (tools/cobertura.py)

ANDROID_APP_UA = ("Mozilla/5.0 (Linux; Android 14; SM-S921B Build/UP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                  "Chrome/130.0 Mobile Safari/537.36 Home Assistant/2026.10.1-full")
ANDROID_CHROME_UA = "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"

SIZES = {  # nome: (largura, altura, celular?)
    "cel": (384, 854, True), "estreito": (320, 700, True), "tablet": (820, 1100, True), "pc": (1280, 900, False),
}


class Run:
    """Um teste visual: conferências, capturas e o app no ar."""

    def __init__(self, name: str):
        self.name = name
        self.ok, self.failed, self.logs = 0, [], []
        self.app: AppServer | None = None
        self.site: FakeSite | None = None
        self.pages = []  # para a captura de tela quando o teste para no meio
        self.cov, self._cdp = [], {}

    # -- conferências
    def check(self, cond, label):
        print(("PASS " if cond else "FAIL ") + label, flush=True)
        if cond:
            self.ok += 1
        else:
            self.failed.append(label)
        return cond

    def eq(self, got, want, label):
        return self.check(got == want, f"{label} ({got!r})" if got == want else f"{label}: esperava {want!r}, veio {got!r}")

    def shot_path(self, label):
        return os.path.join(SHOTS, f"{self.name}-{label}.png")

    async def shot(self, pg, label, **kw):
        await pg.screenshot(path=self.shot_path(label), **kw)

    # -- app
    def start(self, seed=True, mock_ai=True, search=True, env=None, **kw) -> AppServer:
        e = dict(env or {})
        if search:
            self.site = FakeSite()
            path = os.path.join(TMP, f"busca-{self.name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(helpers.search_answer(self.site), f)
            e.update({"INV_MOCK_SEARCH": path, "INV_WEB_ALLOW_LOCAL": "1"})
        self.app = AppServer(seed=seed, mock_ai=mock_ai, env=e, **kw)
        self.base = self.app.base
        return self.app

    def set_search(self, answer: dict):
        with open(self.app.env["INV_MOCK_SEARCH"], "w", encoding="utf-8") as f:
            json.dump(answer, f)

    def api(self, method, path, body=None, **kw):
        return self.app.ok(method, path, body, **kw)

    def data(self):
        return self.app.data()

    def item_named(self, name):
        return next((i for i in self.data()["items"] if i["name"] == name), None)

    # -- navegador
    async def browser(self, p, camera=False, mic=False):
        args = []
        if camera or mic:
            args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
        b = await p.chromium.launch(args=args)
        if COV:
            close = b.close

            async def b_close(*a, **k):
                await self.cov_take_all()
                return await close(*a, **k)
            b.close = b_close
        return b

    async def page(self, b, size="cel", scheme="dark", accent="amarelo", ua=None, perms=None, init=None, user="Diego", motion="reduce"):
        w, h, mobile = SIZES[size]
        ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile,
                                  color_scheme=scheme, reduced_motion=motion, user_agent=ua, permissions=perms or [],
                                  extra_http_headers={"X-Remote-User-Display-Name": user} if user else {})
        if accent:  # None: fica a cor que a pessoa escolher na tela
            await ctx.add_init_script(f"try{{localStorage.setItem('inv:accent', JSON.stringify('{accent}'))}}catch(e){{}}")
        if init:
            await ctx.add_init_script(init)
        pg = await ctx.new_page()
        self.pages.append(pg)
        if COV:
            await self._cov_start(ctx, pg)
        pg.on("pageerror", lambda e: self.logs.append(f"[pageerror] {e}"))
        pg.on("console", lambda m: self.logs.append(f"[console] {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
        return ctx, pg

    # -- cobertura do app.js (E2E_COV): o Chromium perde a contagem ao recarregar, então ela é lida antes de cada goto/reload e ao fechar
    async def _cov_start(self, ctx, pg):
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send("Profiler.enable")
        await cdp.send("Profiler.startPreciseCoverage", {"callCount": False, "detailed": True})
        self._cdp[id(pg)] = cdp
        for name in ("goto", "reload", "close"):
            orig = getattr(pg, name)

            async def wrapped(*a, _orig=orig, **k):
                await self._cov_take(pg)
                return await _orig(*a, **k)
            setattr(pg, name, wrapped)
        close = ctx.close

        async def ctx_close(*a, **k):
            await self.cov_take_all()
            return await close(*a, **k)
        ctx.close = ctx_close

    async def _cov_take(self, pg):
        cdp = self._cdp.get(id(pg))
        if not cdp or pg.is_closed():
            return
        try:
            res = (await cdp.send("Profiler.takePreciseCoverage"))["result"]
        except Exception:  # noqa: BLE001
            return
        for sc in res:
            if sc["url"].split("?")[0].endswith("/app.js"):
                self.cov.append([[[r["startOffset"], r["endOffset"], r["count"]] for r in f["ranges"]] for f in sc["functions"]])

    async def cov_take_all(self):
        for pg in self.pages:
            await self._cov_take(pg)

    async def open(self, pg, hash_="#/", wait=".tag, .welcome, #view .empty, .sbar, .rooms, .more-tabs, .report, .rhead"):
        if pg.url.startswith(self.base):  # só o # mudaria: recarrega para ler o que a API gravou
            await pg.goto("about:blank")
        await pg.goto(self.base + hash_)
        await pg.wait_for_selector(wait, timeout=15000)
        await pg.wait_for_timeout(250)

    def finish(self):
        if COV and self.cov:
            os.makedirs(COV, exist_ok=True)
            with open(os.path.join(COV, f"js-{self.name}-{os.getpid()}.json"), "w") as f:
                json.dump(self.cov, f)
        if self.app:
            self.app.stop()
        if self.site:
            self.site.stop()
        errs = [l for l in self.logs if l.startswith("[pageerror]")]
        self.check(not errs, "nenhum erro de JavaScript na tela" + ("" if not errs else f": {errs[:3]}"))
        for l in self.logs:
            if not l.startswith("[pageerror]"):
                print("     " + l)
        print(f"{self.ok} conferências ok, {len(self.failed)} com falha", flush=True)
        sys.exit(1 if self.failed else 0)


def main(name: str, body):
    """Roda `body(run, playwright)` e encerra com o resumo."""
    from playwright.async_api import async_playwright

    run = Run(name)

    async def go():
        async with async_playwright() as p:
            try:
                await body(run, p)
                await run.cov_take_all()
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                run.check(False, f"o teste parou: {e.__class__.__name__}: {str(e)[:300]}")
                for i, pg in enumerate(x for x in run.pages if not x.is_closed()):
                    try:
                        await pg.screenshot(path=run.shot_path(f"parou-{i}"))
                    except Exception:  # noqa: BLE001
                        pass

    try:
        asyncio.run(go())
    finally:
        run.finish()


# -- trechos de JavaScript usados por vários testes
# nada mais largo que a tela: no celular, o Chrome encolhe a página inteira quando algo passa da largura (innerWidth cresce)
OVERFLOW = "innerWidth <= screen.width + 1 && document.documentElement.scrollWidth <= innerWidth + 1"
TEXTS = "(sel) => [...document.querySelectorAll(sel)].map(e => e.textContent.trim().replace(/\\s+/g, ' '))"
