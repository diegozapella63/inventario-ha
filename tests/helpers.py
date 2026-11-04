"""O que os testes do InventarIA usam em comum: caminhos, a casa de teste e o servidor de verdade num processo à parte.

A casa de teste (tests/fixtures/casa) é fictícia: 6 cômodos, 38 itens e 9 fotos ilustradas, as mesmas das imagens do README.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(ROOT, "inventario", "app")
WEB = os.path.join(APP, "web")
FIXTURE = os.path.join(HERE, "fixtures", "casa")
SITE = os.path.join(HERE, "fixtures", "site")

if HERE not in sys.path:
    sys.path.insert(0, HERE)
from fake_ha import FakeHA, free_port  # noqa: E402,F401


def fixture_data() -> dict:
    with open(os.path.join(FIXTURE, "inventario.json"), encoding="utf-8") as f:
        return json.load(f)


def fixture_photo(name="sala-1.jpg") -> bytes:
    with open(os.path.join(FIXTURE, "photos", name), "rb") as f:
        return f.read()


def write_file(path: str, data: bytes | str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as f:
        f.write(data)
    return path


def jpeg(w=64, h=48) -> bytes:
    """Um JPEG pequeno de verdade (uma das fotos da casa de teste serve)."""
    return fixture_photo("cozinha-1.jpg")


def zip_bytes(files: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


# ---------------------------------------------------------------------------- servidor em processo à parte

class AppServer:
    """O server.py de verdade num processo, com uma pasta de dados nova.

    seed=True começa com a casa de teste; seed=False, vazio (a tela de boas-vindas).
    dev=True aceita qualquer endereço (como o modo dev); dev=False só aceita o do Supervisor (INV_ALLOW).
    """

    def __init__(self, env: dict | None = None, seed: bool = True, dev: bool = True, mock_ai: bool = False, ha: FakeHA | None = None,
                 port: int | None = None, root: str | None = None):
        self.root = root or tempfile.mkdtemp(prefix="inventaria-")
        for d in ("data", "share", "media", "empty-seed"):
            os.makedirs(os.path.join(self.root, d), exist_ok=True)
        self.port = port or free_port()
        self.base = f"http://127.0.0.1:{self.port}/"
        e = dict(os.environ)
        for k in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN", "INV_AI_MOCK", "INV_DEV", "INV_ALLOW", "INV_HA_API", "INV_HA_WS", "INV_MOCK_SEARCH", "INV_WEB_ALLOW_LOCAL"):
            e.pop(k, None)
        e.setdefault("INV_HOJE", "2026-11-04")  # as novidades de exemplo são de 2026: os testes não envelhecem
        e.update({
            "INV_PORT": str(self.port), "INV_DATA": self.path("data"), "INV_SHARE": self.path("share"), "INV_MEDIA": self.path("media"),
            "INV_SEED": FIXTURE if seed else self.path("empty-seed"), "INV_WEB": WEB, "PYTHONUNBUFFERED": "1", "TZ": e.get("TZ", "America/Sao_Paulo"),
        })
        if dev:
            e["INV_DEV"] = "1"
        if mock_ai:
            e["INV_AI_MOCK"] = "1"
        if ha:
            e.update(ha.env())
        e.update(env or {})
        self.env = e
        self.log = open(self.path("server.log"), "w")
        self.proc = subprocess.Popen([sys.executable, os.path.join(APP, "server.py")], env=e, stdout=self.log, stderr=subprocess.STDOUT)
        self.wait()

    def path(self, *p) -> str:
        return os.path.join(self.root, *p)

    def wait(self, timeout=15.0):
        end = time.time() + timeout
        while time.time() < end:
            if self.proc.poll() is not None:
                raise RuntimeError("o servidor parou:\n" + open(self.path("server.log")).read()[-3000:])
            try:
                with urllib.request.urlopen(self.base + "api/health", timeout=1) as r:
                    if r.status in (200, 403):
                        return
            except urllib.error.HTTPError as err:
                if err.code == 403:
                    return
            except OSError:
                pass
            time.sleep(0.1)
        raise RuntimeError("o servidor não respondeu")

    def request(self, method: str, path: str, body=None, raw: bytes | None = None, headers: dict | None = None, timeout=30):
        """(status, cabeçalhos, resposta): a resposta vem em JSON quando é JSON, senão em bytes."""
        h = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(self.base + path.lstrip("/"), data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, hdrs, out = r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as err:
            status, hdrs, out = err.code, dict(err.headers), err.read()
        if "json" in (hdrs.get("Content-Type") or ""):
            out = json.loads(out or b"null")
        return status, hdrs, out

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body if body is not None or "raw" in kw else {}, **kw)

    def put(self, path, body=None, **kw):
        return self.request("PUT", path, body if body is not None else {}, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)

    def ok(self, method, path, body=None, expect=(200, 201, 202), **kw):
        st, _, out = self.request(method, path, body, **kw)
        if st not in expect:
            raise AssertionError(f"{method} {path}: {st} {out}")
        return out

    def data(self) -> dict:
        return self.ok("GET", "api/data")

    def stored(self) -> dict:
        with open(self.path("data", "inventario.json"), encoding="utf-8") as f:
            return json.load(f)

    def logtext(self) -> str:
        self.log.flush()
        with open(self.path("server.log"), encoding="utf-8", errors="replace") as f:
            return f.read()

    def stop(self, clean=True):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.log.close()
        if clean:
            shutil.rmtree(self.root, ignore_errors=True)


# ---------------------------------------------------------------------------- site de lojas de mentira (fotos da internet)

class FakeSite:
    """Serve tests/fixtures/site numa porta livre: páginas de produto com og:image, JSON-LD, redirecionamento e gzip."""

    def __init__(self):
        import gzip
        import threading
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

        class H(SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=SITE, **k)

            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/produto-c.html":
                    self.send_response(302)
                    self.send_header("Location", "/produto-c2.html")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if self.path == "/produto-d.html":
                    with open(os.path.join(SITE, "produto-d.html"), "rb") as f:
                        body = gzip.compress(f.read())
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                return super().do_GET()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}/"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def search_answer(site: FakeSite, product=True, extra_pages=True) -> dict:
    """A resposta que uma IA com busca na web daria para a cafeteira do site de mentira."""
    pages = [{"url": site.base + "produto-a.html", "titulo": "Loja A"}, {"url": site.base + "produto-b.html"}]
    if extra_pages:
        pages += [{"url": site.base + "produto-c.html"}, {"url": site.base + "produto-d.html"}, {"url": site.base + "pequena.html"},
                  {"url": site.base + "semfoto.html"}, {"url": site.base + "nao-existe.html"}, {"url": "javascript:alert(1)"}]
    out = {"paginas": pages, "imagens": [site.base + "img/e.jpg", site.base + "img/not-image.txt"]}
    if product:
        out["produto"] = {"nome": "Cafeteira Espresso Exemplo CX-20", "detalhes": "Cafeteira espresso de 15 bar, inox, reservatório de 1,2 L.",
                          "categoria": "cozinha", "valor": "450,00"}
    return out
