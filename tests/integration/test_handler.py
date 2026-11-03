"""O que o Handler do servidor faz em todo pedido, pelo HTTP de verdade: os arquivos da tela (página, app.js, style.css,
fontes e ícones) com o tipo e o cache certos, HEAD, método que não existe, rota desconhecida, caminhos estranhos, o usuário
do Home Assistant (X-Remote-User-Display-Name) nos itens, o acesso de fora do Ingress, a chave dos outros apps, erros
sempre em JSON e conexões cortadas ou lentas que não derrubam o servidor."""
import http.client
import json
import os
import re
import socket
import time
import unittest

from _boot import AppServer, ServerCase, helpers

JSON = {"Content-Type": "application/json"}
FORA = "Abra o InventarIA pelo Home Assistant."


def troca(app, pedido: bytes, timeout=10) -> tuple[int | None, dict, bytes]:
    """Manda um pedido HTTP escrito à mão e lê até o servidor fechar: (status, cabeçalhos, corpo); status None se nada voltou."""
    buf = b""
    with socket.create_connection(("127.0.0.1", app.port), timeout=timeout) as s:
        s.sendall(pedido)
        try:
            while True:
                d = s.recv(65536)
                if not d:
                    break
                buf += d
        except (ConnectionResetError, socket.timeout):
            pass
    if not buf:
        return None, {}, b""
    head, _, body = buf.partition(b"\r\n\r\n")
    linhas = head.decode("iso-8859-1").split("\r\n")
    hdrs = dict(ln.split(": ", 1) for ln in linhas[1:] if ": " in ln)
    return int(linhas[0].split(" ", 2)[1]), hdrs, body


def conexao(app) -> http.client.HTTPConnection:
    return http.client.HTTPConnection("127.0.0.1", app.port, timeout=10)


def pedir(conn, method, path, body=None, headers=None):
    conn.request(method, path, body=body, headers=headers or {})
    r = conn.getresponse()
    return r.status, dict(r.getheaders()), r.read()


class HandlerCase(ServerCase):
    def vivo(self, app=None):
        self.assertEqual((app or self.app).get("api/health")[0], 200, "o servidor continua respondendo")

    def erro_json(self, st, h, out, status, msg=None):
        self.assertEqual(st, status)
        self.assertEqual(h.get("Content-Type"), "application/json; charset=utf-8")
        self.assertIsInstance(out, dict)
        self.assertIsInstance(out.get("error"), str)
        if msg:
            self.assertEqual(out["error"], msg)


class Tela(HandlerCase):
    def disco(self, *p):
        with open(os.path.join(helpers.WEB, *p), "rb") as f:
            return f.read()

    def test_raiz_e_index_html_iguais_com_a_versao_no_lugar(self):
        a, b = self.app.get("/"), self.app.get("index.html")
        self.assertEqual((a[0], b[0], a[2]), (200, 200, b[2]))
        self.assertEqual((a[1]["Content-Type"], a[1]["Cache-Control"]), ("text/html; charset=utf-8", "no-cache"))
        versao = self.app.ok("GET", "api/health")["version"]
        self.assertEqual(a[2], self.disco("index.html").replace(b"%%V%%", versao.encode()))
        self.assertIn(f'style.css?v={versao}'.encode(), a[2])

    def test_app_js_e_style_css_com_tipo_e_sem_cache_guardado(self):
        for nome, tipo in (("app.js", "text/javascript; charset=utf-8"), ("style.css", "text/css; charset=utf-8")):
            with self.subTest(arquivo=nome):
                st, h, body = self.app.get(nome)
                self.assertEqual((st, h["Content-Type"], h["Cache-Control"]), (200, tipo, "no-cache"))
                self.assertEqual(body, self.disco(nome))
                self.assertEqual(int(h["Content-Length"]), len(body))

    def test_cabecalhos_de_seguranca_em_todas_as_respostas(self):
        for path in ("/", "app.js", "api/data", "photos/sala-1.jpg", "fonts/barlow-400.woff", "api/nao-existe", "nao-existe.js", "api/export.csv"):
            with self.subTest(path=path):
                _, h, _ = self.app.get(path)
                self.assertEqual((h.get("X-Content-Type-Options"), h.get("Referrer-Policy")), ("nosniff", "same-origin"))

    def test_versao_na_query_nao_atrapalha(self):
        for path in ("style.css?v=1.0.0", "app.js?v=x&y=2", "?tab=mais", "index.html?x"):
            with self.subTest(path=path):
                self.assertEqual(self.app.get(path)[0], 200)

    def test_fontes_guardadas_por_um_ano(self):
        fontes = sorted(n for n in os.listdir(os.path.join(helpers.WEB, "fonts")) if n.endswith((".woff", ".woff2")))
        self.assertGreaterEqual(len(fontes), 6)
        for nome in fontes:
            with self.subTest(fonte=nome):
                st, h, body = self.app.get(f"fonts/{nome}")
                self.assertEqual((st, h["Cache-Control"], body), (200, "public, max-age=31536000, immutable", self.disco("fonts", nome)))

    def test_fontes_da_folha_de_estilo_existem(self):
        css = self.app.get("style.css")[2].decode()
        usadas = re.findall(r'url\("(fonts/[^"]+)"\)', css)
        self.assertTrue(usadas)
        for path in usadas:
            with self.subTest(fonte=path):
                self.assertEqual(self.app.get(path)[0], 200)

    def test_fontes_com_tipo_de_fonte(self):
        self.assertEqual(self.app.get("fonts/barlow-400.woff")[1]["Content-Type"], "font/woff")

    def test_icones_usados_na_tela_existem_na_pagina(self):
        js, html = self.app.get("app.js")[2].decode(), self.app.get("/")[2].decode()
        nomes = set(re.findall(r'\b(?:ic|lbl|secIc)\(\s*"([a-z0-9-]+)"', js))
        nomes |= {n for par in re.findall(r'\bic\([^()"]*\?\s*"([a-z0-9-]+)"\s*:\s*"([a-z0-9-]+)"', js) for n in par}
        nomes |= set(re.findall(r'\["[a-z]+", "[^"]+", "([a-z0-9-]+)"\]', js))  # abas de Mais e temas: [chave, texto, ícone]
        self.assertGreater(len(nomes), 30)
        definidos = set(re.findall(r'<symbol id="i-([a-z0-9-]+)"', html))
        self.assertEqual(nomes - definidos, set(), "todo ícone que a tela usa está no index.html")

    def test_sem_favicon_responde_404_em_json(self):
        st, h, out = self.app.get("favicon.ico")
        self.erro_json(st, h, out, 404, "Arquivo não encontrado.")


class Metodos(HandlerCase):
    def test_head_da_pagina_sem_corpo_com_o_tamanho(self):
        conn = conexao(self.app)
        self.addCleanup(conn.close)
        st, h, body = pedir(conn, "HEAD", "/")
        st2, h2, body2 = pedir(conn, "GET", "/")
        self.assertEqual((st, body, h["Content-Type"]), (200, b"", "text/html; charset=utf-8"))
        self.assertEqual(int(h["Content-Length"]), len(body2), "o tamanho é o do GET")

    def test_head_da_api_e_da_foto_sem_corpo(self):
        conn = conexao(self.app)
        self.addCleanup(conn.close)
        for path in ("/api/health", "/api/data", "/photos/sala-1.jpg", "/api/export.csv", "/api/nao-existe"):
            with self.subTest(path=path):
                st, h, body = pedir(conn, "HEAD", path)
                self.assertEqual(body, b"")
                self.assertGreater(int(h["Content-Length"]), 0)

    def test_head_do_zip_sem_corpo(self):
        st, h, body = troca(self.app, b"HEAD /api/export.zip HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
        self.assertEqual((st, h.get("Content-Type"), body), (200, "application/zip", b""))

    def test_metodo_desconhecido_nao_derruba(self):
        for method in ("PATCH", "OPTIONS", "TRACE", "PROPFIND"):
            with self.subTest(method=method):
                st, _, _ = self.app.request(method, "api/data")
                self.assertEqual(st, 501)
        self.vivo()

    def test_metodo_desconhecido_responde_em_json(self):
        st, h, out = self.app.request("PATCH", "api/items/sal-001", {"name": "x"})
        self.erro_json(st, h, out, st)
        self.assertIn(st, (405, 501))

    def test_escrever_em_rota_de_leitura_404_em_json(self):
        for method, path in (("POST", "api/data"), ("PUT", "api/health"), ("DELETE", "api/rev"), ("POST", "api/export.csv"), ("POST", "/"),
                             ("PUT", "api/history"), ("DELETE", "api/settings"), ("POST", "api/ai/status")):
            with self.subTest(method=method, path=path):
                st, h, out = self.app.request(method, path, {"x": 1})
                self.erro_json(st, h, out, 404, "Endereço não encontrado.")

    def test_ler_rota_de_escrita_procura_arquivo_da_tela(self):
        for path in ("api/items", "api/rooms/order", "api/import", "api/backups/restore", "api/photos", "api/voice", "api/history/restore"):
            with self.subTest(path=path):
                st, h, out = self.app.get(path)
                self.erro_json(st, h, out, 404, "Arquivo não encontrado.")


class Caminhos(HandlerCase):
    def test_query_e_codificacao_por_cento(self):
        self.assertEqual(self.app.get("api/data?x=1&y")[0], 200)
        self.assertEqual(self.app.get("api/%64ata")[0], 200, "o caminho é decodificado antes de achar a rota")
        self.assertEqual(self.app.get("photos/sala%2D1.jpg")[0], 200)

    def test_caminhos_que_saem_da_pasta_da_tela_ficam_em_404(self):
        for path in (b"/../server.py", b"//etc/passwd", b"/fonts/../../server.py", b"/fonts/..%2f..%2fserver.py", b"/%2Fetc%2Fpasswd",
                     b"/..%5cserver.py", b"/web/app.js", b"/../../../etc/hostname", b"/photos/..%2f..%2finventario.json",
                     b"/thumbs/%2e%2e%2finventario.json", b"/api/../../server.py"):
            with self.subTest(path=path):
                st, h, body = troca(self.app, b"GET " + path + b" HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
                self.assertEqual(st, 404, body[:200])
                self.assertEqual(h.get("Content-Type"), "application/json; charset=utf-8")
                self.assertNotIn(b"import ", body)

    def test_ponto_barra_fica_dentro_da_pasta(self):
        st, _, body = troca(self.app, b"GET /./app.js HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
        self.assertEqual((st, body), (200, self.app.get("app.js")[2]))

    def test_pastas_nao_sao_servidas(self):
        for path in ("fonts", "fonts/", "photos/", "thumbs/", "api/", "api"):
            with self.subTest(path=path):
                st, h, out = self.app.get(path)
                self.erro_json(st, h, out, 404)

    def test_byte_nulo_no_caminho_404(self):
        for path in ("app.js%00.png", "fonts/barlow-400.woff%00", "photos/sala-1.jpg%00"):
            with self.subTest(path=path):
                self.assertEqual(self.app.get(path)[0], 404)

    def test_caminho_longo_demais_nao_derruba(self):
        linha = b"GET /" + b"a" * 70000
        st, _, _ = troca(self.app, linha[:65537])  # o http.server lê no máximo 65537 bytes da primeira linha
        self.assertEqual(st, 414)
        self.vivo()

    def test_pedido_mal_formado_nao_derruba(self):
        for pedido in (b"ISTO NAO E HTTP\r\n\r\n", b"GET\r\n\r\n", b"\x16\x03\x01\x02\x00\x01\x00\x01\xfc\x03\x03\r\n\r\n"):
            with self.subTest(pedido=pedido[:12]):
                st, _, _ = troca(self.app, pedido)
                self.assertIn(st, (400, None))
        self.vivo()


class Usuario(HandlerCase):
    def criar(self, headers):
        st, _, out = self.app.post("api/items", {"room": "varanda", "name": "Com autor"}, headers=headers)
        self.assertEqual(st, 201, out)
        self.addCleanup(self.app.delete, f"api/items/{out['item']['id']}")
        return out["item"]

    def test_nome_de_exibicao_vale_mais_que_o_usuario(self):
        it = self.criar({"X-Remote-User-Display-Name": "Diego Exemplo", "X-Remote-User-Name": "diego"})
        self.assertEqual((it["createdBy"], it["updatedBy"]), ("Diego Exemplo", "Diego Exemplo"))
        self.assertEqual(self.app.ok("GET", "api/data", headers={"X-Remote-User-Display-Name": "Diego Exemplo", "X-Remote-User-Name": "diego"})["user"],
                         "Diego Exemplo")

    def test_nome_cortado_em_60(self):
        self.assertEqual(self.criar({"X-Remote-User-Display-Name": "N" * 80})["createdBy"], "N" * 60)

    def test_nome_so_com_espacos_nao_conta(self):
        it = self.criar({"X-Remote-User-Display-Name": "   ", "X-Remote-User-Name": ""})
        self.assertNotIn("createdBy", it)
        self.assertIsNone(self.app.ok("GET", "api/data", headers={"X-Remote-User-Display-Name": "   "})["user"])

    def test_nome_aparado(self):
        self.assertEqual(self.app.ok("GET", "api/data", headers={"X-Remote-User-Name": "  ana  "})["user"], "ana")

    def test_nome_com_acento_como_o_ingress_manda(self):
        body = json.dumps({"room": "varanda", "name": "Com acento"}).encode()
        conn = conexao(self.app)
        self.addCleanup(conn.close)
        conn.putrequest("POST", "/api/items")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(body)))
        conn.putheader("X-Remote-User-Display-Name", "José Conceição".encode("utf-8"))
        conn.endheaders()
        conn.send(body)
        r = conn.getresponse()
        out = json.loads(r.read())
        self.addCleanup(self.app.delete, f"api/items/{out['item']['id']}")
        self.assertEqual(out["item"]["createdBy"], "José Conceição")


class ForaDoIngress(HandlerCase):
    """Sem INV_DEV, só o endereço do Supervisor (INV_ALLOW, 172.30.32.2 por padrão) abre o app."""
    server_kw = {"dev": False}

    def test_tudo_recusado_em_json_com_a_mensagem(self):
        for method, path, body in (("GET", "app.js", None), ("GET", "fonts/barlow-400.woff", None), ("GET", "thumbs/sala-1.jpg", None),
                                   ("GET", "api/ai/status", None), ("PUT", "api/settings", {"zones": True}), ("DELETE", "api/items/sal-001", None),
                                   ("POST", "api/upload", {"size": 10}), ("GET", "api/export.zip", None), ("GET", "nao-existe", None)):
            with self.subTest(method=method, path=path):
                st, h, out = self.app.request(method, path, body)
                self.erro_json(st, h, out, 403, FORA)

    def test_recusado_nao_muda_nada(self):
        self.app.delete("api/items/sal-001")
        self.app.put("api/settings", {"zones": True})
        self.app.post("api/cats", {"name": "Invasora"})
        self.assertIn("sal-001", [i["id"] for i in self.app.stored()["items"]])
        self.assertNotIn("cats", self.app.stored())
        self.assertFalse(os.path.exists(self.app.path("data", "settings.json")))

    def test_head_recusado_sem_corpo(self):
        conn = conexao(self.app)
        self.addCleanup(conn.close)
        st, _, body = pedir(conn, "HEAD", "/")
        self.assertEqual((st, body), (403, b""))

    def test_corpo_recusado_e_lido_e_a_conexao_continua(self):
        conn = conexao(self.app)
        self.addCleanup(conn.close)
        st, _, _ = pedir(conn, "POST", "/api/items", body=b'{"room": "sala", "name": "' + b"x" * 1_000_000 + b'"}', headers=JSON)
        self.assertEqual(st, 403)
        st, _, out = pedir(conn, "GET", "/api/health")
        self.assertEqual((st, json.loads(out)["error"]), (403, FORA), "o próximo pedido na mesma conexão é lido certo")

    def test_lista_de_enderecos_com_espacos(self):
        app = self.fresh(dev=False, env={"INV_ALLOW": "10.9.8.7, 127.0.0.1 ,"})
        self.assertEqual(app.get("api/data")[0], 200)

    def test_outro_endereco_continua_bloqueado(self):
        app = self.fresh(dev=False, env={"INV_ALLOW": "10.9.8.7,172.30.32.2"})
        st, h, out = app.get("api/data")
        self.erro_json(st, h, out, 403, FORA)


class Integracao(HandlerCase):
    """A chave de share/inventario/integracao.json abre só /api/integracao, também no modo dev."""

    def chave(self):
        with open(self.app.path("share", "integracao.json"), encoding="utf-8") as f:
            return json.load(f)["chave"]

    def ler(self, path, chave=None):
        return self.app.get(path, headers={"Authorization": f"Bearer {chave or self.chave()}"})

    def test_modo_dev_nao_dispensa_a_chave(self):
        for path in ("api/integracao/comodos", "api/integracao/itens"):
            with self.subTest(path=path):
                st, h, out = self.app.get(path)
                self.erro_json(st, h, out, 401, "Chave inválida.")

    def test_chave_com_espacos_em_volta_aceita(self):
        st, _, _ = self.app.get("api/integracao/comodos", headers={"Authorization": f"Bearer   {self.chave()}  "})
        self.assertEqual(st, 200)

    def test_outro_esquema_ou_sem_bearer_recusado(self):
        for valor in (f"bearer {self.chave()}", f"Token {self.chave()}", self.chave(), f"Basic {self.chave()}", "Bearer "):
            with self.subTest(valor=valor[:12]):
                self.assertEqual(self.app.get("api/integracao/itens", headers={"Authorization": valor})[0], 401)

    def test_rota_desconhecida_da_integracao_tambem_pede_a_chave(self):
        self.assertEqual(self.app.get("api/integracao/nada")[0], 401)
        st, h, out = self.ler("api/integracao/nada")
        self.erro_json(st, h, out, 404, "Arquivo não encontrado.")

    def test_contagem_de_itens_por_comodo_acompanha(self):
        antes = {c["id"]: c["itens"] for c in self.ler("api/integracao/comodos")[2]["comodos"]}
        it = self.app.ok("POST", "api/items", {"room": "varanda", "name": "Regador"})["item"]
        self.addCleanup(self.app.delete, f"api/items/{it['id']}")
        depois = {c["id"]: c["itens"] for c in self.ler("api/integracao/comodos")[2]["comodos"]}
        self.assertEqual(depois["varanda"], antes["varanda"] + 1)
        self.assertEqual(self.ler("api/integracao/comodos")[2]["versao"], self.app.ok("GET", "api/health")["version"])

    def test_valor_em_muda_quando_o_valor_muda(self):
        it = self.app.ok("POST", "api/items", {"room": "varanda", "name": "Cadeira de praia", "value": 80})["item"]
        self.addCleanup(self.app.delete, f"api/items/{it['id']}")
        novo = self.app.ok("PUT", f"api/items/{it['id']}", {"value": 60})["item"]
        x = next(i for i in self.ler("api/integracao/itens")[2]["itens"] if i["id"] == it["id"])
        self.assertEqual((x["valor"], x["valor_em"]), (60.0, novo["valueAt"][:10]))

    def test_item_novo_sem_zona_nem_categoria(self):
        it = self.app.ok("POST", "api/items", {"room": "varanda", "name": "Balde"})["item"]
        self.addCleanup(self.app.delete, f"api/items/{it['id']}")
        x = next(i for i in self.ler("api/integracao/itens")[2]["itens"] if i["id"] == it["id"])
        self.assertEqual({k: x[k] for k in ("nome", "comodo", "zona", "categoria", "valor")},
                         {"nome": "Balde", "comodo": "varanda", "zona": "", "categoria": "outros", "valor": 0.0})
        self.assertEqual(x["valor_em"], it["createdAt"][:10])

    def test_respostas_sem_cache(self):
        for path in ("api/integracao/comodos", "api/integracao/itens"):
            with self.subTest(path=path):
                st, h, _ = self.ler(path)
                self.assertEqual((st, h["Cache-Control"], h["Content-Type"]), (200, "no-store", "application/json; charset=utf-8"))


class RespostasEmJson(HandlerCase):
    def test_erros_sempre_em_json_com_a_mensagem_e_sem_cache(self):
        casos = [("GET", "api/nao-existe", None, None, 404), ("POST", "api/items", None, b"{quebrado", 400), ("PUT", "api/items/nao-existe", {"name": "x"}, None, 404),
                 ("PUT", "api/items/sal-001", {"name": "x", "_base": "2000"}, None, 409), ("GET", "photos/nao-existe.jpg", None, None, 404),
                 ("GET", "api/integracao/itens", None, None, 401), ("POST", "api/rooms", {"name": ""}, None, 400),
                 ("DELETE", "api/cats/outros", None, None, 400), ("POST", "api/upload", {"size": 0}, None, 400),
                 ("POST", "api/voice", None, b"\0", 422), ("GET", "api/web-photos/0123456789abcdef", None, None, 404)]
        for method, path, body, raw, status in casos:
            with self.subTest(method=method, path=path):
                st, h, out = self.app.request(method, path, body, raw=raw, headers=JSON if raw else None)
                self.erro_json(st, h, out, status)
                self.assertEqual(h["Cache-Control"], "no-store")

    def test_json_em_utf8_sem_escapes_e_compacto(self):
        conn = conexao(self.app)
        self.addCleanup(conn.close)
        raw = pedir(conn, "GET", "/api/data")[2]
        self.assertIn("Móveis".encode("utf-8"), raw)
        self.assertNotIn(b"\\u00f3", raw)
        versao = self.app.ok("GET", "api/health")["version"]
        self.assertEqual(pedir(conn, "GET", "/api/health")[2], b'{"ok":true,"version":"' + versao.encode() + b'"}')


    def test_corpo_json_que_nao_e_objeto_recusado_com_400(self):
        for method, path, raw in (("POST", "api/items", b"[1, 2]"), ("POST", "api/items", b'"sofa"'), ("PUT", "api/items/sal-001", b"[1]"),
                                  ("POST", "api/items/batch", b"[1]"), ("POST", "api/items/batch", b'{"items": [{"room": "sala", "name": "A"}], "roomPhoto": "x.jpg"}'),
                                  ("POST", "api/rooms", b"[1]"), ("PUT", "api/rooms/sala", b"[1]"), ("POST", "api/rooms/sala/photos", b"[1]"),
                                  ("POST", "api/rooms/order", b"[1]"), ("POST", "api/cats", b"[1]"), ("PUT", "api/cats/moveis", b"[1]"),
                                  ("POST", "api/import", b"[1]"), ("POST", "api/upload", b"[1]"), ("POST", "api/backups/restore", b"[1]"),
                                  ("POST", "api/history/restore", b"[1]"), ("POST", "api/photos", b"[1]"), ("POST", "api/ai/identify", b"[1]"),
                                  ("POST", "api/web-photos", b"[1]")):
            with self.subTest(method=method, path=path, corpo=raw[:20]):
                st, _, out = self.app.request(method, path, raw=raw, headers=JSON)
                self.assertEqual(st, 400, out)


class Robustez(HandlerCase):
    def test_varios_pedidos_na_mesma_conexao_mesmo_com_erros(self):
        conn = conexao(self.app)
        self.addCleanup(conn.close)
        seq = [("POST", "/api/nada", b'{"a": 1}', 404), ("GET", "/api/health", None, 200), ("POST", "/api/items", b"{quebrado", 400),
               ("GET", "/api/rev", None, 200), ("PUT", "/api/items/nao-existe", b'{"name": "x"}', 404), ("POST", "/api/rooms", b'{"name": ""}', 400),
               ("GET", "/photos/nao-existe.jpg", None, 404), ("GET", "/", None, 200)]
        for method, path, body, status in seq:
            with self.subTest(method=method, path=path):
                st, _, _ = pedir(conn, method, path, body, JSON if body else None)
                self.assertEqual(st, status)

    def test_corpo_em_partes_cortado_no_meio_nao_derruba(self):
        n = len(self.app.stored()["items"])
        with socket.create_connection(("127.0.0.1", self.app.port), timeout=5) as s:
            s.sendall(b"POST /api/items HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n40\r\n{\"room\": \"sala\"")
        time.sleep(0.2)
        self.vivo()
        self.assertEqual(len(self.app.stored()["items"]), n)

    def test_download_do_zip_interrompido_nao_derruba_nem_deixa_temporario(self):
        with socket.create_connection(("127.0.0.1", self.app.port), timeout=5) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            s.sendall(b"GET /api/export.zip HTTP/1.1\r\nHost: x\r\n\r\n")
            s.recv(100)
        fim = time.time() + 5
        while time.time() < fim and [n for n in os.listdir(self.app.path("data", "tmp")) if n.endswith(".zip")]:
            time.sleep(0.05)
        self.assertEqual([n for n in os.listdir(self.app.path("data", "tmp")) if n.endswith(".zip")], [])
        self.vivo()

    def test_tamanho_de_corpo_que_nao_e_numero_nao_derruba(self):
        troca(self.app, b"POST /api/items HTTP/1.1\r\nHost: x\r\nContent-Length: abc\r\nConnection: close\r\n\r\n{}", timeout=3)
        self.vivo()

    def test_tamanho_de_corpo_que_nao_e_numero_responde_400(self):
        st, h, body = troca(self.app, b"POST /api/items HTTP/1.1\r\nHost: x\r\nContent-Length: abc\r\nConnection: close\r\n\r\n{}", timeout=3)
        self.assertEqual(st, 400)
        self.assertIn("error", json.loads(body))

    def test_tamanho_negativo_nao_trava_os_outros(self):
        with socket.create_connection(("127.0.0.1", self.app.port), timeout=5) as s:
            s.sendall(b"POST /api/items HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: -1\r\n\r\n{}")
            time.sleep(0.1)
            self.vivo()
            self.assertEqual(self.app.post("api/items", {"room": "x"})[0], 400)

    def test_cliente_lento_nao_trava_os_outros(self):
        with socket.create_connection(("127.0.0.1", self.app.port), timeout=5) as lento:
            lento.sendall(b"POST /api/items HTTP/1.1\r\nHost: x\r\nContent-Le")
            for _ in range(3):
                self.vivo()
            self.assertEqual(self.app.get("/")[0], 200)

    def test_excluir_categoria_com_corpo_nao_estraga_a_conexao(self):
        self.app.ok("POST", "api/cats", {"name": "Conexão"})
        conn = conexao(self.app)
        self.addCleanup(conn.close)
        st, _, _ = pedir(conn, "DELETE", "/api/cats/conexao", b'{"confirmar": true}', JSON)
        self.assertEqual(st, 200)
        st, _, _ = pedir(conn, "GET", "/api/health")
        self.assertEqual(st, 200)


if __name__ == "__main__":
    unittest.main()
