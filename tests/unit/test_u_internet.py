"""Buscar na internet, sem servidor: só endereços públicos (_public_ip), o download (web_get, com o FakeSite e uma loja de
mentira com os casos difíceis), as fotos que a página declara (_PageImages, _ld_images, _fix_url, page_images), tipo e
tamanho das fotos (image_kind, image_size, fetch_image), site_of, as instruções e os dados do produto (web_prompt,
web_product), a resposta da IA (ai_find_pages) e o ciclo de uma busca (web_job_start, _web_job_run, web_job, cancelar,
web_jobs_cleanup, IA desligada no meio)."""
import copy
import gzip
import json
import os
import re
import socket
import struct
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from _boot import UnitBase, helpers, server as S

IMG = os.path.join(helpers.SITE, "img")


def arquivo(nome) -> bytes:
    with open(os.path.join(IMG, nome), "rb") as f:
        return f.read()


A1 = arquivo("a1.jpg")


def png(w, h, tamanho=0) -> bytes:
    b = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", w, h) + b"\x08\x02\0\0\0"
    return b + b"\0" * max(0, tamanho - len(b))


def jpeg_sof(w, h, marcador=0xC0, antes=b"") -> bytes:
    sof = bytes([0xFF, marcador]) + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", h, w) + b"\x03" + b"\0" * 9
    return b"\xff\xd8" + antes + sof + b"\xff\xd9"


def webp(chunk: bytes, dados: bytes) -> bytes:
    return b"RIFF" + struct.pack("<I", 4 + 8 + len(dados)) + b"WEBP" + chunk + struct.pack("<I", len(dados)) + dados


def gai(*ips):
    """O que socket.getaddrinfo devolveria para esses endereços."""
    return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 80, 0, 0) if ":" in ip else (ip, 80)) for ip in ips]


class Resposta:
    """Faz o papel do Handler nas funções r_*: guarda o que seria enviado."""

    def __init__(self):
        self.enviado = []
        self.arquivos = []

    def send_json(self, obj, status=200):
        self.enviado.append((status, obj))

    def send_file(self, path, ctype=None, cache="no-cache", download_name=None):
        self.arquivos.append((path, ctype, cache))


class Loja:
    """Uma loja de mentira para o que o FakeSite não tem: laço de redirecionamento, gzip que cresce, sem tamanho, eco do pedido."""

    def __init__(self):
        self.rotas: dict[str, tuple] = {}
        self.pedidos: list[tuple[str, dict]] = []
        loja = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                loja.pedidos.append((self.path, dict(self.headers)))
                status, cab, corpo = loja.rotas.get(self.path.split("?", 1)[0]) or (404, {"Content-Type": "text/plain"}, b"nao existe")
                cab = dict(cab)
                sem_tamanho = cab.pop("_sem_tamanho", False)
                self.send_response(status)
                for k, v in cab.items():
                    self.send_header(k, v)
                if not sem_tamanho:
                    self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                try:
                    self.wfile.write(corpo)
                except OSError:
                    pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def pagina(self, path, html, tipo="text/html; charset=utf-8"):
        self.rotas[path] = (200, {"Content-Type": tipo}, html if isinstance(html, bytes) else html.encode())

    def foto(self, path, corpo, tipo="image/jpeg"):
        self.rotas[path] = (200, {"Content-Type": tipo}, corpo)

    def redireciona(self, path, destino, status=302):
        self.rotas[path] = (status, {"Location": destino}, b"")

    def vezes(self, prefixo):
        return sum(1 for p, _ in self.pedidos if p.startswith(prefixo))

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


CAMPOS_DO_HA = ("token", "states", "pipelines", "stt_text", "stt_status", "stt_result", "ai_reply", "ai_error", "conversation_reply", "ws_fail")


class Base(UnitBase):
    """Uma loja, o site de mentira e o Home Assistant de mentira por classe (parar cada um custa meio segundo); WEB_ALLOW_LOCAL ligado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loja = Loja()
        cls.site = helpers.FakeSite()
        cls._ha = None

    @classmethod
    def tearDownClass(cls):
        cls.loja.stop()
        cls.site.stop()
        if cls._ha:
            cls._ha.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.loja.rotas.clear()
        self.loja.pedidos.clear()
        p = mock.patch.object(S, "WEB_ALLOW_LOCAL", True)
        p.start()
        self.addCleanup(p.stop)

    def fake_ha(self):
        cls = type(self)
        if cls._ha is None:
            cls._ha = helpers.FakeHA(media_root=S.MEDIA_ROOT)
            cls._padrao = {k: copy.deepcopy(getattr(cls._ha, k)) for k in CAMPOS_DO_HA}
        ha = cls._ha
        for k in CAMPOS_DO_HA:
            setattr(ha, k, copy.deepcopy(cls._padrao[k]))
        with ha.lock:
            ha.requests.clear()
        for p in (mock.patch.object(S, "SUPERVISOR_TOKEN", ha.token), mock.patch.object(S, "HA_API", ha.api), mock.patch.object(S, "HA_WS", ha.ws)):
            p.start()
            self.addCleanup(p.stop)
        return ha


# ---------------------------------------------------------------------------- só a internet pública

class SoEnderecosPublicos(UnitBase):
    def resolve(self, *ips):
        return mock.patch.object(S.socket, "getaddrinfo", return_value=gai(*ips))

    def test_a_propria_maquina_e_recusada_antes_de_conectar(self):
        with mock.patch.object(S.socket, "create_connection", side_effect=AssertionError("não devia conectar")):
            for url in ("http://127.0.0.1/admin", "https://localhost/", "http://192.168.0.1/"):
                with self.subTest(url=url):
                    with self.assertRaises(S.WebError) as cm:
                        S.web_get(url, 1000, "*/*")
                    self.assertEqual(str(cm.exception), "endereço fora da internet")

    def test_ipv4_publico_e_aceito(self):
        self.assertEqual(S._public_ip("8.8.8.8", 443), "8.8.8.8")

    def test_ipv6_publico_e_aceito(self):
        with self.resolve("2606:4700:4700::1111"):
            self.assertEqual(S._public_ip("loja.exemplo", 443), "2606:4700:4700::1111")

    def test_ipv6_link_local_com_zona_e_recusado(self):
        with self.resolve("fe80::1%eth0"):
            with self.assertRaises(S.WebError) as cm:
                S._public_ip("loja.exemplo", 80)
        self.assertEqual(str(cm.exception), "endereço fora da internet")

    def test_ipv6_da_rede_de_casa_e_recusado(self):
        for ip in ("fd12:3456::1", "fc00::1", "::", "::ffff:192.168.1.1"):
            with self.subTest(ip=ip), self.resolve(ip):
                with self.assertRaises(S.WebError):
                    S._public_ip("loja.exemplo", 80)

    def test_faixas_especiais_do_ipv4_sao_recusadas(self):
        for ip in ("100.64.0.1", "192.0.2.1", "198.18.0.1", "0.0.0.0", "255.255.255.255"):
            with self.subTest(ip=ip), self.resolve(ip):
                with self.assertRaises(S.WebError):
                    S._public_ip("loja.exemplo", 80)

    def test_um_endereco_de_casa_entre_os_publicos_recusa_tudo(self):
        with self.resolve("93.184.216.34", "10.0.0.1"):
            with self.assertRaises(S.WebError):
                S._public_ip("loja.exemplo", 80)

    def test_devolve_o_primeiro_endereco(self):
        with self.resolve("93.184.216.34", "93.184.216.35"):
            self.assertEqual(S._public_ip("loja.exemplo", 80), "93.184.216.34")

    def test_pergunta_o_nome_com_a_porta(self):
        with self.resolve("93.184.216.34") as gai_:
            S._public_ip("loja.exemplo", 443)
        gai_.assert_called_once_with("loja.exemplo", 443, type=socket.SOCK_STREAM)

    def test_nome_que_nao_existe(self):
        for erro in (socket.gaierror(-2, "Name or service not known"), UnicodeError("label too long")):
            with self.subTest(erro=erro), mock.patch.object(S.socket, "getaddrinfo", side_effect=erro):
                with self.assertRaises(S.WebError) as cm:
                    S._public_ip("nao-existe.exemplo", 80)
                self.assertEqual(str(cm.exception), "site não encontrado")

    def test_nome_sem_nenhum_endereco(self):
        with mock.patch.object(S.socket, "getaddrinfo", return_value=[]):
            with self.assertRaises(S.WebError) as cm:
                S._public_ip("vazio.exemplo", 80)
        self.assertEqual(str(cm.exception), "site não encontrado")

    def test_rede_local_liberada_so_nos_testes(self):
        with mock.patch.object(S, "WEB_ALLOW_LOCAL", True), self.resolve("192.168.1.10"):
            self.assertEqual(S._public_ip("nas.local", 80), "192.168.1.10")


# ---------------------------------------------------------------------------- download

class Baixar(Base):
    def erro(self, url, max_bytes=100000, accept="*/*"):
        with self.assertRaises(S.WebError) as cm:
            S.web_get(url, max_bytes, accept)
        return str(cm.exception)

    def test_pagina_com_tipo_e_conteudo(self):
        url, tipo, corpo = S.web_get(self.site.base + "produto-a.html", 100000, "text/html")
        self.assertEqual((url, tipo), (self.site.base + "produto-a.html", "text/html"))
        self.assertIn(b'og:image" content="/img/a2.png"', corpo)

    def test_redirecionamento_relativo(self):
        self.loja.redireciona("/antigo/p1", "../novo/p1")
        self.loja.pagina("/novo/p1", "<html></html>")
        url, _, _ = S.web_get(self.loja.base + "antigo/p1", 1000, "*/*")
        self.assertEqual(url, self.loja.base + "novo/p1")

    def test_todos_os_tipos_de_redirecionamento(self):
        self.loja.pagina("/fim", "ok")
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.loja.redireciona(f"/r{status}", "/fim", status)
                self.assertEqual(S.web_get(self.loja.base + f"r{status}", 1000, "*/*")[0], self.loja.base + "fim")

    def test_redirecionamentos_demais(self):
        self.loja.redireciona("/laco", "/laco")
        self.assertEqual(self.erro(self.loja.base + "laco"), "redirecionamentos demais")
        self.assertEqual(self.loja.vezes("/laco"), 6, "o primeiro e mais 5")

    def test_redirecionamento_sem_destino(self):
        self.loja.rotas["/vazio"] = (302, {}, b"")
        self.assertEqual(self.erro(self.loja.base + "vazio"), "redirecionamento sem destino")

    def test_redirecionamento_para_arquivo_local_e_recusado(self):
        self.loja.redireciona("/arquivo", "file:///etc/passwd")
        self.assertEqual(self.erro(self.loja.base + "arquivo"), "endereço inválido")

    def test_cada_salto_do_redirecionamento_e_conferido(self):
        self.loja.redireciona("/para-casa", "http://roteador.exemplo/painel")
        vistos = []

        def conferir(host, port):
            vistos.append((host, port))
            if host == "127.0.0.1":
                return "127.0.0.1"
            raise S.WebError("endereço fora da internet")
        with mock.patch.object(S, "_public_ip", side_effect=conferir):
            self.assertEqual(self.erro(self.loja.base + "para-casa"), "endereço fora da internet")
        self.assertEqual(vistos[-1], ("roteador.exemplo", 80))

    def test_tamanho_declarado_acima_do_limite(self):
        self.assertEqual(self.erro(self.site.base + "img/a1.jpg", max_bytes=1000), "arquivo grande demais")

    def test_exatamente_o_limite_passa(self):
        _, tipo, corpo = S.web_get(self.site.base + "img/a1.jpg", len(A1), "image/*")
        self.assertEqual((tipo, corpo), ("image/jpeg", A1))

    def test_sem_tamanho_declarado_e_acima_do_limite(self):
        self.loja.rotas["/sem-tamanho"] = (200, {"Content-Type": "text/html", "_sem_tamanho": True}, b"x" * 5000)
        self.assertEqual(self.erro(self.loja.base + "sem-tamanho", max_bytes=1000), "arquivo grande demais")

    def test_gzip_e_descompactado(self):
        _, tipo, corpo = S.web_get(self.site.base + "produto-d.html", 100000, "text/html")
        self.assertTrue(corpo.startswith(b"<html>"), corpo[:20])
        self.assertIn(b"/img/d.jpg", corpo)

    def test_gzip_que_cresce_alem_do_limite(self):
        bomba = gzip.compress(b"\0" * 200000)
        self.assertLess(len(bomba), 10000)
        self.loja.rotas["/bomba"] = (200, {"Content-Type": "text/html", "Content-Encoding": "gzip"}, bomba)
        self.assertEqual(self.erro(self.loja.base + "bomba", max_bytes=10000), "arquivo grande demais")

    def test_gzip_quebrado(self):
        self.loja.rotas["/quebrado"] = (200, {"Content-Type": "text/html", "Content-Encoding": "gzip"}, b"isto nao e gzip")
        self.assertEqual(self.erro(self.loja.base + "quebrado"), "sem resposta do site (error)")

    def test_site_responde_erro(self):
        self.assertEqual(self.erro(self.site.base + "nao-existe.html"), "o site respondeu 404")
        self.loja.rotas["/falhou"] = (500, {}, b"erro")
        self.assertEqual(self.erro(self.loja.base + "falhou"), "o site respondeu 500")

    def test_sem_tipo_de_conteudo(self):
        self.loja.rotas["/sem-tipo"] = (200, {}, b"algo")
        self.assertEqual(S.web_get(self.loja.base + "sem-tipo", 1000, "*/*")[1], "")

    def test_tipo_em_minusculas_e_sem_parametros(self):
        self.loja.pagina("/tipo", "x", tipo="Image/JPEG; q=1")
        self.assertEqual(S.web_get(self.loja.base + "tipo", 1000, "*/*")[1], "image/jpeg")

    def test_cabecalhos_do_pedido(self):
        self.loja.pagina("/eco", "ok")
        S.web_get(self.loja.base + "eco", 1000, "image/webp,*/*;q=0.5")
        _, cab = self.loja.pedidos[-1]
        self.assertTrue(cab["User-Agent"].startswith(f"Mozilla/5.0 (compatible; InventarIA/{S.VERSION};"))
        self.assertEqual((cab["Accept"], cab["Accept-Encoding"]), ("image/webp,*/*;q=0.5", "gzip"))
        self.assertTrue(cab["Accept-Language"].startswith("pt-BR"))

    def test_consulta_vai_junto_e_caminho_vazio_vira_barra(self):
        self.loja.pagina("/eco", "ok")
        self.loja.pagina("/", "inicio")
        S.web_get(self.loja.base + "eco?cor=preta&tam=2", 1000, "*/*")
        self.assertEqual(self.loja.pedidos[-1][0], "/eco?cor=preta&tam=2")
        S.web_get(self.loja.base.rstrip("/"), 1000, "*/*")
        self.assertEqual(self.loja.pedidos[-1][0], "/")

    def test_esquema_em_maiusculas(self):
        url = self.site.base.replace("http://", "HTTP://") + "produto-b.html"
        self.assertIn(b"b.webp", S.web_get(url, 100000, "*/*")[2])

    def test_site_fora_do_ar(self):
        self.assertEqual(self.erro(f"http://127.0.0.1:{helpers.free_port()}/x"), "sem resposta do site (ConnectionRefusedError)")

    def test_enderecos_que_nao_sao_http_sao_recusados(self):
        for url in ("javascript:alert(1)", "data:text/html,oi", "mailto:loja@exemplo", "//loja.exemplo/x", "loja.exemplo/x", ""):
            with self.subTest(url=url):
                self.assertEqual(self.erro(url), "endereço inválido")

    def test_nome_com_acento_vai_em_idna(self):
        with mock.patch.object(S, "_public_ip", side_effect=S.WebError("site não encontrado")) as conferir:
            self.erro("http://café.exemplo/x")
        conferir.assert_called_once_with("xn--caf-dma.exemplo", 80)


# ---------------------------------------------------------------------------- fotos que a página declara

class LerPagina(UnitBase):
    def ler(self, html):
        p = S._PageImages()
        p.feed(html)
        p.close()
        return p

    def test_variantes_do_og_image_e_do_twitter(self):
        p = self.ler('<meta property="og:image:secure_url" content="/s.jpg"><meta property="og:image:url" content="/u.jpg">'
                     '<meta name="twitter:image:src" content="/t.jpg">')
        self.assertEqual(p.metas, [(1, "/s.jpg"), (1, "/u.jpg"), (2, "/t.jpg")])

    def test_meta_sem_conteudo_e_outras_metas_sao_ignoradas(self):
        p = self.ler('<meta property="og:image"><meta property="og:image" content=""><meta property="og:title" content="X">'
                     '<meta name="description" content="/d.jpg"><link rel="image_src">')
        self.assertEqual(p.metas, [])

    def test_chaves_sem_diferenca_de_maiusculas(self):
        p = self.ler('<META PROPERTY="OG:IMAGE" CONTENT="/a.jpg"><link REL="IMAGE_SRC" HREF="/b.jpg"><meta ItemProp="Image" content="/c.jpg">')
        self.assertEqual(sorted(p.metas), [(1, "/a.jpg"), (3, "/c.jpg"), (4, "/b.jpg")])

    def test_so_o_primeiro_titulo_encurtado(self):
        p = self.ler(f"<title>{'Cafeteira ' * 40}</title><svg><title>Ícone</title></svg>")
        self.assertEqual(len(p.title), 200)
        self.assertTrue(p.title.startswith("Cafeteira Cafeteira"))

    def test_varios_json_ld_e_script_comum_de_fora(self):
        p = self.ler('<script type="application/ld+json; charset=utf-8">{"a": 1}</script><script>var x = {"image": "/x.jpg"}</script>'
                     '<script type="application/LD+JSON">{"b": 2}</script>')
        self.assertEqual([json.loads(x) for x in p.ld], [{"a": 1}, {"b": 2}])

    def test_json_ld_numa_lista_de_itens(self):
        raw = json.dumps({"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "item": {"@type": "Product", "image": "/1.jpg"}},
                                                                    {"@type": "ListItem", "item": {"@type": "Product", "image": ["/2.jpg"]}}]})
        self.assertEqual(S._ld_images(raw), ["/1.jpg", "/2.jpg"])

    def test_json_ld_para_de_procurar_com_8_fotos(self):
        graph = [{"@type": "Product", "image": [f"/{p}-{n}.jpg" for n in range(5)]} for p in range(3)]
        fotos = S._ld_images(json.dumps({"@graph": graph}))
        self.assertEqual(fotos, [f"/{p}-{n}.jpg" for p in range(2) for n in range(5)], "o terceiro produto nem é lido")

    def test_json_ld_outros_tipos_de_produto(self):
        for tipo in ("IndividualProduct", "ProductModel", "product", ["Thing", "Product"]):
            with self.subTest(tipo=tipo):
                self.assertEqual(S._ld_images(json.dumps({"@type": tipo, "image": "/p.jpg"})), ["/p.jpg"])

    def test_json_ld_ignora_valores_estranhos(self):
        raw = json.dumps({"@type": "Product", "image": [1, None, {"name": "sem endereço"}, {"contentUrl": "/a.jpg", "url": "/b.jpg"}, "/c.jpg"]})
        self.assertEqual(S._ld_images(raw), ["/a.jpg", "/c.jpg"], "contentUrl vale mais que url")

    def test_json_ld_lista_no_topo_e_com_espacos(self):
        raw = "\n  " + json.dumps([{"@type": "Organization", "logo": "/logo.png"}, {"@type": "Product", "image": {"url": "/p.jpg"}}]) + "  \n"
        self.assertEqual(S._ld_images(raw), ["/p.jpg"])


class ArrumarEndereco(UnitBase):
    def test_entidades_html_sao_decodificadas(self):
        self.assertEqual(S._fix_url("https://l.exemplo/a&#x2F;b.jpg"), "https://l.exemplo/a/b.jpg")

    def test_relativo_sem_base_e_recusado(self):
        for u in ("/a.jpg", "img/a.jpg", "a.jpg"):
            with self.subTest(u=u):
                self.assertIsNone(S._fix_url(u))

    def test_espacos_nas_pontas_saem(self):
        self.assertEqual(S._fix_url("  https://l.exemplo/a.jpg \n"), "https://l.exemplo/a.jpg")

    def test_protocolo_relativo_vira_https_mesmo_em_pagina_http(self):
        self.assertEqual(S._fix_url("//cdn.exemplo/a.jpg", "http://l.exemplo/p"), "https://cdn.exemplo/a.jpg")

    def test_http_e_aceito(self):
        self.assertEqual(S._fix_url("http://l.exemplo/a.jpg"), "http://l.exemplo/a.jpg")

    def test_ate_1000_caracteres(self):
        base = "https://l.exemplo/"
        self.assertIsNotNone(S._fix_url(base + "a" * (1000 - len(base))))
        self.assertIsNone(S._fix_url(base + "a" * (1001 - len(base))))


class FotosDaPagina(Base):
    def test_no_maximo_4_fotos(self):
        self.loja.pagina("/muitas.html", "".join(f'<meta property="og:image" content="/f{n}.jpg">' for n in range(6)))
        _, fotos = S.page_images(self.loja.base + "muitas.html")
        self.assertEqual(fotos, [self.loja.base + f"f{n}.jpg" for n in range(4)])

    def test_ordem_json_ld_e_depois_metas_por_prioridade(self):
        self.loja.pagina("/ordem.html", '<link rel="image_src" href="/5.jpg"><meta itemprop="image" content="/4.jpg">'
                                        '<meta name="twitter:image" content="/3.jpg"><meta property="og:image" content="/2.jpg">'
                                        '<script type="application/ld+json">{"@type": "Product", "image": "/1.jpg"}</script>')
        _, fotos = S.page_images(self.loja.base + "ordem.html")
        self.assertEqual(fotos, [self.loja.base + f"{n}.jpg" for n in (1, 2, 3, 4)])

    def test_mesma_foto_escrita_de_jeitos_diferentes_entra_uma_vez(self):
        self.loja.pagina("/p/repetida.html", f'<meta property="og:image" content="{self.loja.base}p/a.jpg"><meta name="twitter:image" content="a.jpg">'
                                             '<script type="application/ld+json">{"@type": "Product", "image": "/p/a.jpg"}</script>')
        self.assertEqual(S.page_images(self.loja.base + "p/repetida.html")[1], [self.loja.base + "p/a.jpg"])

    def test_enderecos_ruins_da_pagina_ficam_de_fora(self):
        self.loja.pagina("/ruins.html", '<meta property="og:image" content="javascript:alert(1)"><meta name="twitter:image" content="data:image/png;base64,xx">'
                                        '<meta itemprop="image" content="/boa.jpg"><link rel="image_src" href="ftp://l.exemplo/x.jpg">')
        self.assertEqual(S.page_images(self.loja.base + "ruins.html")[1], [self.loja.base + "boa.jpg"])

    def test_pagina_sem_foto(self):
        self.assertEqual(S.page_images(self.site.base + "semfoto.html"), (self.site.base + "semfoto.html", []))

    def test_html_quebrado_e_bytes_estranhos_nao_derrubam(self):
        self.loja.pagina("/quebrada.html", b'<html><head>\xff\xfe<meta property="og:image" content="/q.jpg"><<<>>><script type="application/ld+json">{quebrado'
                                           b"</script></head")
        self.assertEqual(S.page_images(self.loja.base + "quebrada.html")[1], [self.loja.base + "q.jpg"])

    def test_foto_pequena_ainda_e_listada(self):
        self.assertEqual(S.page_images(self.site.base + "pequena.html")[1], [self.site.base + "img/tiny.png"], "quem descarta é a conferência da foto")


# ---------------------------------------------------------------------------- tipo e tamanho das fotos

class TipoETamanho(UnitBase):
    def test_webp_simples(self):
        b = webp(b"VP8 ", b"\0\0\0" + b"\x9d\x01\x2a" + struct.pack("<HH", 640 | 0x4000, 480 | 0x8000))
        self.assertEqual(S.image_kind(b), "webp")
        self.assertEqual(S.image_size(b, "webp"), (640, 480), "sem os bits de escala")

    def test_webp_sem_perdas(self):
        v = (1024 - 1) | ((768 - 1) << 14)
        self.assertEqual(S.image_size(webp(b"VP8L", b"\x2f" + v.to_bytes(4, "little")), "webp"), (1024, 768))

    def test_webp_estendido(self):
        b = webp(b"VP8X", b"\0\0\0\0" + (1920 - 1).to_bytes(3, "little") + (1080 - 1).to_bytes(3, "little"))
        self.assertEqual(S.image_size(b, "webp"), (1920, 1080))

    def test_jpeg_progressivo(self):
        self.assertEqual(S.image_size(jpeg_sof(1200, 900, marcador=0xC2), "jpeg"), (1200, 900))

    def test_jpeg_pula_as_tabelas_antes_do_tamanho(self):
        dht = b"\xff\xc4" + struct.pack(">H", 8) + struct.pack(">HH", 9999, 8888) + b"\0\0"
        dac = b"\xff\xcc" + struct.pack(">H", 8) + struct.pack(">HH", 7777, 6666) + b"\0\0"
        self.assertEqual(S.image_size(jpeg_sof(640, 480, antes=dht + dac), "jpeg"), (640, 480))

    def test_jpeg_com_bytes_de_preenchimento_e_marcadores_soltos(self):
        self.assertEqual(S.image_size(jpeg_sof(300, 200, antes=b"\xff\xff\xff\x01\xff\xd0"), "jpeg"), (300, 200))

    def test_avif_variante_avis(self):
        b = b"\0\0\0\x1cftypavis" + b"\0" * 20 + b"ispe" + b"\0" * 4 + struct.pack(">II", 800, 600)
        self.assertEqual((S.image_kind(b), S.image_size(b, "avif")), ("avif", (800, 600)))

    def test_lixo_nao_e_foto(self):
        for b in (b"", b"RIFF\0\0\0\0WAVEfmt ", b"<html><body>", b"\x89PNX\r\n\x1a\n", b"%PDF-1.7", b"\0\0\0\x1cftypmp42"):
            with self.subTest(b=b):
                self.assertIsNone(S.image_kind(b))

    def test_png_cortado_fica_sem_tamanho(self):
        self.assertIsNone(S.image_size(b"\x89PNG\r\n\x1a\n", "png"))

    def test_sem_tamanho_quando_nao_da_para_ler(self):
        self.assertIsNone(S.image_size(webp(b"ALPH", b"\0" * 20), "webp"), "pedaço de WebP desconhecido")
        self.assertIsNone(S.image_size(b"\0\0\0\x1cftypavif" + b"\0" * 30, "avif"), "AVIF sem ispe")
        self.assertIsNone(S.image_size(b"GIF89a" + b"\0" * 20, "gif"), "tipo que o app não lê")
        self.assertIsNone(S.image_size(b"\xff\xd8" + b"\0" * 100, "jpeg"), "JPEG sem o pedaço do tamanho")

    def test_foto_pequena_do_site(self):
        b = arquivo("tiny.png")
        self.assertEqual((S.image_kind(b), S.image_size(b, "png")), ("png", (60, 60)))


class ConferirFoto(Base):
    def erro(self, url):
        with self.assertRaises(S.WebError) as cm:
            S.fetch_image(url)
        return str(cm.exception)

    def test_arquivo_que_nao_e_foto(self):
        self.assertEqual(self.erro(self.site.base + "img/not-image.txt"), "não é uma foto")

    def test_foto_pequena(self):
        self.assertEqual(self.erro(self.site.base + "img/tiny.png"), "foto pequena demais")

    def test_arquivo_pequeno_mesmo_dizendo_ser_grande(self):
        self.loja.foto("/mentirosa.png", png(1000, 1000, 500), "image/png")
        self.assertEqual(self.erro(self.loja.base + "mentirosa.png"), "foto pequena demais")

    def test_lado_menor_que_200_e_pequena(self):
        self.loja.foto("/faixa.png", png(1000, 150, 5000), "image/png")
        self.assertEqual(self.erro(self.loja.base + "faixa.png"), "foto pequena demais")

    def test_200_de_lado_passa(self):
        self.loja.foto("/quadrada.png", png(200, 200, 5000), "image/png")
        self.assertEqual(S.fetch_image(self.loja.base + "quadrada.png")[1:3], ("png", (200, 200)))

    def test_foto_sem_tamanho_legivel_e_aceita(self):
        corpo = b"\xff\xd8\xff\xe0" + struct.pack(">H", 16) + b"JFIF\0" + b"\x01\x01\0\0\x01\0\x01\0\0" + b"\0" * 5000
        self.loja.foto("/sem-tamanho.jpg", corpo)
        _, tipo, tam, _ = S.fetch_image(self.loja.base + "sem-tamanho.jpg")
        self.assertEqual((tipo, tam), ("jpeg", None))

    def test_foto_acima_do_limite(self):
        with mock.patch.object(S, "WEB_IMG_MAX", 10000):
            self.assertEqual(self.erro(self.site.base + "img/a1.jpg"), "arquivo grande demais")

    def test_devolve_o_endereco_final_e_o_conteudo(self):
        self.loja.redireciona("/foto-antiga.jpg", "/foto-nova.jpg", 301)
        self.loja.foto("/foto-nova.jpg", A1)
        final, tipo, tam, corpo = S.fetch_image(self.loja.base + "foto-antiga.jpg")
        self.assertEqual((final, tipo, tam, corpo), (self.loja.base + "foto-nova.jpg", "jpeg", (800, 800), A1))

    def test_tipo_vem_do_conteudo_e_nao_do_cabecalho(self):
        self.loja.foto("/disfarce.txt", A1, "text/plain")
        self.assertEqual(S.fetch_image(self.loja.base + "disfarce.txt")[1], "jpeg")


class SiteDaFoto(UnitBase):
    def test_tira_www2_e_fica_em_minusculas(self):
        self.assertEqual(S.site_of("https://WWW2.Loja.Exemplo/x"), "loja.exemplo")
        self.assertEqual(S.site_of("https://www.loja.exemplo:8443/x"), "loja.exemplo")

    def test_so_tira_um_prefixo_do_comeco(self):
        for url, site in (("https://mobile.loja.exemplo/", "mobile.loja.exemplo"), ("https://www.m.loja.exemplo/", "m.loja.exemplo"),
                          ("https://loja.m.exemplo/", "loja.m.exemplo"), ("https://mm.loja.exemplo/", "mm.loja.exemplo")):
            with self.subTest(url=url):
                self.assertEqual(S.site_of(url), site)

    def test_endereco_sem_nome(self):
        for url in ("", "nada", "/so/caminho"):
            with self.subTest(url=url):
                self.assertEqual(S.site_of(url), "")


# ---------------------------------------------------------------------------- instruções e dados do produto

class InstrucoesEProduto(UnitBase):
    def test_instrucoes_tem_o_produto_e_os_detalhes(self):
        p = S.web_prompt("Cafeteira Exemplo CX-20", "inox, 15 bar")
        self.assertIn("\nProduto: Cafeteira Exemplo CX-20\nDetalhes: inox, 15 bar\n", p)

    def test_sem_detalhes_nao_tem_a_linha(self):
        self.assertNotIn("Detalhes:", S.web_prompt("Cafeteira", ""))

    def test_quantidade_vazia_nao_entra(self):
        self.assertNotIn("Quantidade", S.web_prompt("Cafeteira", "", ""))

    def test_pede_sem_dados_pessoais_e_o_aviso_sem_busca(self):
        p = S.web_prompt("Cafeteira", "")
        self.assertIn("Nunca inclua número de série, IMEI, telefone, nome de pessoa ou endereço.", p)
        self.assertIn('Se não conseguir usar a busca na web, responda apenas {"erro": "sem_busca"}.', p)
        self.assertIn("Use só endereços que apareceram na busca: não invente.", p)

    def test_categorias_sao_as_da_casa(self):
        self.store.delete_cat("pets")
        self.store.update_cat("moveis", {"name": "Mobília"})
        p = S.web_prompt("Cafeteira", "")
        self.assertNotIn("pets (Pets)", p)
        self.assertIn("moveis (Mobília)", p)

    def test_valor_em_reais_com_centavos(self):
        self.assertEqual(S.web_product({"produto": {"nome": "X", "valor": "R$ 1.234,56"}})["value"], 1234.56)

    def test_valor_em_numero(self):
        for v, esperado in ((899.9, 899.9), (450, 450), (0, 0), (None, 0)):
            with self.subTest(v=v):
                self.assertEqual(S.web_product({"produto": {"nome": "X", "valor": v}})["value"], esperado)

    def test_sem_valor_fica_zero(self):
        self.assertEqual(S.web_product({"produto": {"nome": "X"}})["value"], 0)

    def test_valor_estranho_fica_zero(self):
        for v in (-50, True, "2e12", [100]):
            with self.subTest(v=v):
                self.assertEqual(S.web_product({"produto": {"nome": "X", "valor": v}})["value"], 0)

    def test_nome_e_detalhes_arrumados_e_encurtados(self):
        p = S.web_product({"produto": {"nome": "  Cafeteira   Espresso\n CX-20 " + "x" * 300, "detalhes": "  inox " + "d" * 1500}})
        self.assertTrue(p["name"].startswith("Cafeteira Espresso CX-20 x"))
        self.assertEqual((len(p["name"]), len(p["details"])), (200, 1000))
        self.assertTrue(p["details"].startswith("inox "))

    def test_so_com_detalhes_vale(self):
        self.assertEqual(S.web_product({"produto": {"detalhes": "Cafeteira de inox."}}), {"name": "", "details": "Cafeteira de inox.", "cat": "", "value": 0})

    def test_produto_que_nao_e_objeto(self):
        for p in ("Cafeteira", ["Cafeteira"], 5):
            with self.subTest(p=p):
                self.assertIsNone(S.web_product({"produto": p}))

    def test_categoria_criada_na_casa_vale(self):
        nova = self.store.create_cat({"name": "Ferramentas"})
        self.assertEqual(S.web_product({"produto": {"nome": "Furadeira", "categoria": nova["id"]}})["cat"], nova["id"])

    def test_categoria_que_nao_e_texto_fica_vazia(self):
        for cat in (["cozinha"], {"id": "cozinha"}, 5):
            with self.subTest(cat=cat):
                self.assertEqual(S.web_product({"produto": {"nome": "Cafeteira", "categoria": cat}})["cat"], "", "e a busca segue")

    def test_categoria_excluida_fica_vazia(self):
        self.store.delete_cat("pets")
        self.assertEqual(S.web_product({"produto": {"nome": "Arranhador", "categoria": "pets"}})["cat"], "")

    def test_portugues_vale_mais_que_ingles(self):
        p = S.web_product({"produto": {"nome": "Cafeteira"}, "product": {"name": "Coffee maker"}})
        self.assertEqual(p["name"], "Cafeteira")


# ---------------------------------------------------------------------------- resposta da IA

class RespostaDaIA(Base):
    def setUp(self):
        super().setUp()
        self.ha = self.fake_ha()

    def responde(self, data):
        self.ha.ai_reply = lambda kind, payload: data if isinstance(data, str) or data is None else json.dumps(data)

    def test_paginas_e_imagens_limpas(self):
        self.responde({"paginas": [{"url": "https://loja.exemplo/p/1", "titulo": "A"}, "https://outra.exemplo/p/2", {"url": "https://loja.exemplo/p/1"},
                                   {"url": "javascript:alert(1)"}, {"url": "/relativo"}, {"titulo": "sem url"}, 5],
                       "imagens": [{"url": "https://cdn.exemplo/a.jpg"}, "https://cdn.exemplo/a.jpg", "//cdn.exemplo/b.jpg", "data:image/png;base64,xx"]})
        r = S.ai_find_pages("Cafeteira", "", "")
        self.assertEqual(r["pages"], ["https://loja.exemplo/p/1", "https://outra.exemplo/p/2"])
        self.assertEqual(r["images"], ["https://cdn.exemplo/a.jpg", "https://cdn.exemplo/b.jpg"])

    def test_no_maximo_8_paginas_e_6_imagens(self):
        self.responde({"paginas": [f"https://l{n}.exemplo/p" for n in range(12)], "imagens": [f"https://cdn.exemplo/{n}.jpg" for n in range(10)]})
        r = S.ai_find_pages("Cafeteira", "", "")
        self.assertEqual((len(r["pages"]), len(r["images"])), (8, 6))
        self.assertEqual(r["pages"][0], "https://l0.exemplo/p", "na ordem em que a IA trouxe")

    def test_chaves_em_ingles(self):
        self.responde({"pages": [{"url": "https://loja.exemplo/p"}], "images": ["https://cdn.exemplo/a.jpg"], "product": {"name": "Coffee maker"}})
        r = S.ai_find_pages("Cafeteira", "", "")
        self.assertEqual((r["pages"], r["images"], r["product"]["name"]), (["https://loja.exemplo/p"], ["https://cdn.exemplo/a.jpg"], "Coffee maker"))

    def test_so_imagens_sem_paginas_vale(self):
        self.responde({"imagens": ["https://cdn.exemplo/a.jpg"]})
        self.assertEqual(S.ai_find_pages("Cafeteira", "", "")["pages"], [])

    def test_erro_mesmo_com_paginas(self):
        self.responde({"erro": "sem_busca", "paginas": ["https://loja.exemplo/p"]})
        self.assertApiError(502, S.ai_find_pages, "Cafeteira", "", "", msg_part="não usou a busca na web")
        self.assertEqual(S.usage_summary()["recent"][0]["result"], "sem_busca")

    def test_resposta_em_bloco_de_codigo(self):
        corpo = json.dumps({"paginas": ["https://loja.exemplo/p"]})
        for resp in (f"```json\n{corpo}\n```", f"Aqui está o que achei:\n```json\n{corpo}\n```"):
            with self.subTest(resp=resp[:12]):
                self.responde(resp)
                self.assertEqual(S.ai_find_pages("Cafeteira", "", "")["pages"], ["https://loja.exemplo/p"])

    def test_ia_sem_resposta(self):
        self.responde(None)
        self.assertApiError(502, S.ai_find_pages, "Cafeteira", "", "", msg_part="respondeu sem usar a busca na web")
        self.assertEqual(S.usage_summary()["recent"][0]["result"], "sem_busca")

    def test_pedido_vai_para_a_ia_escolhida(self):
        self.responde({"paginas": ["https://loja.exemplo/p"]})
        S.ai_find_pages("Cafeteira", "", "ai_task.google_ai_task")
        body = self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]
        self.assertEqual((body["entity_id"], body["task_name"]), ("ai_task.google_ai_task", "InventarIA: buscar foto"))
        r = S.usage_summary()["recent"][0]
        self.assertEqual((r["kind"], r["entity"], r["result"]), ("busca", "ai_task.google_ai_task", "ok"))

    def test_sem_ia_escolhida_usa_a_preferida(self):
        self.responde({"paginas": ["https://loja.exemplo/p"]})
        S.ai_find_pages("Cafeteira", "", "")
        self.assertNotIn("entity_id", self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"])
        self.assertEqual(S.usage_summary()["recent"][0]["entity"], "padrão do Home Assistant")

    def test_sem_produto_vem_vazio(self):
        self.responde({"paginas": ["https://loja.exemplo/p"]})
        self.assertIsNone(S.ai_find_pages("Cafeteira", "", "")["product"])

    def test_simulado_le_o_arquivo_de_busca(self):
        arq = helpers.write_file(os.path.join(S.DATA_DIR, "busca.json"), json.dumps({"paginas": ["https://loja.exemplo/simulada"]}))
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep"), mock.patch.dict(os.environ, {"INV_MOCK_SEARCH": arq}):
            self.assertEqual(S.ai_find_pages("Cafeteira", "", "")["pages"], ["https://loja.exemplo/simulada"])
        self.assertEqual(self.ha.calls("POST"), [])

    def test_simulado_sem_arquivo_e_sem_busca(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep"), mock.patch.dict(os.environ):
            os.environ.pop("INV_MOCK_SEARCH", None)
            self.assertApiError(502, S.ai_find_pages, "Cafeteira", "", "", msg_part="não usou a busca na web")


# ---------------------------------------------------------------------------- o ciclo de uma busca

class CicloDaBusca(Base):
    def setUp(self):
        super().setUp()
        self.ha = self.fake_ha()

    def rodar(self, resposta, nome="Cafeteira"):
        """Roda a busca aqui mesmo (sem a linha de execução à parte) e devolve (id, busca)."""
        self.ha.ai_reply = lambda k, p: json.dumps(resposta)
        jid = "c0ffee" + "0" * 10
        S.WEB_JOBS[jid] = {"stage": "busy", "msg": "", "results": [], "at": time.time()}
        S._web_job_run(jid, nome, "", "", "1")
        return jid, S.WEB_JOBS[jid]

    def arquivos(self, jid):
        return sorted(n for n in os.listdir(S.TMP_DIR) if n.startswith(f"web-{jid}-"))

    def test_comecar_sem_acesso_ao_home_assistant(self):
        with mock.patch.object(S, "SUPERVISOR_TOKEN", None):
            self.assertApiError(503, S.web_job_start, {"name": "Cafeteira"}, msg_part="não tem acesso")
        self.assertEqual(S.WEB_JOBS, {})

    def test_comecar_devolve_id_e_fica_procurando(self):
        with mock.patch.object(S, "_web_job_run"):
            jid = S.web_job_start({"name": "Cafeteira"})["id"]
        self.assertRegex(jid, r"^[a-f0-9]{16}$")
        job = S.WEB_JOBS[jid]
        self.assertEqual((job["stage"], job["msg"], job["results"]), ("busy", "Procurando o produto na internet…", []))

    def test_comecar_arruma_os_campos(self):
        chamado, args = threading.Event(), []

        def falso(*a):
            args.append(a)
            chamado.set()
        self.store.settings["ai_search"] = "conversation.google_generative_ai"
        with mock.patch.object(S, "_web_job_run", falso):
            jid = S.web_job_start({"name": "  Cafeteira  ", "details": "inox\n\n  " + "x" * 400, "qty": "  2   un "})["id"]
            self.assertTrue(chamado.wait(5))
        self.assertEqual(args[0][:2], (jid, "Cafeteira"))
        self.assertEqual(args[0][2], ("inox " + "x" * 400)[:300])
        self.assertEqual(args[0][3:], ("conversation.google_generative_ai", "2 un"))

    def test_quantidade_vazia_vira_1(self):
        for qty in ("", None, "   "):
            with self.subTest(qty=qty):
                chamado, args = threading.Event(), []
                with mock.patch.object(S, "_web_job_run", lambda *a: (args.append(a), chamado.set())):
                    S.web_job_start({"name": "Cafeteira", "qty": qty})
                    self.assertTrue(chamado.wait(5))
                self.assertEqual(args[0][4], "1")

    def test_comecar_limpa_buscas_velhas(self):
        velha = "b" * 16
        S.WEB_JOBS[velha] = {"stage": "done", "msg": "", "results": [], "at": time.time() - S.WEB_JOB_TTL - 5}
        with mock.patch.object(S, "_web_job_run"):
            S.web_job_start({"name": "Cafeteira"})
        self.assertNotIn(velha, S.WEB_JOBS)

    def test_nome_ou_detalhes_longos_demais(self):
        self.assertApiError(400, S.web_job_start, {"name": "n" * 201}, msg_part="limite de 200")
        self.assertApiError(400, S.web_job_start, {"name": "Cafeteira", "details": "d" * 4001}, msg_part="limite de 4000")
        self.assertEqual(S.WEB_JOBS, {})

    def test_falha_da_ia_vira_erro_da_busca(self):
        self.ha.ai_error = (500, "Erro interno da IA")
        _, job = self.rodar({})
        self.assertEqual(job["stage"], "error")
        self.assertIn("recusou o pedido: Erro interno da IA", job["msg"])

    def test_erro_inesperado_vira_mensagem_generica(self):
        with mock.patch.object(S, "page_images", side_effect=RuntimeError("defeito")):
            _, job = self.rodar({"paginas": [self.site.base + "produto-a.html"]})
        self.assertEqual((job["stage"], job["msg"]), ("error", "Não deu para buscar agora. Tente de novo em instantes."))

    def test_cancelada_antes_das_fotos_nao_baixa_nada(self):
        jid = "d" * 16

        def achou(*a):
            S.WEB_JOBS[jid]["cancelled"] = True
            return {"pages": [self.site.base + "produto-a.html"], "images": [], "product": {"name": "Cafeteira"}}
        S.WEB_JOBS[jid] = {"stage": "busy", "msg": "", "results": [], "at": time.time()}
        with mock.patch.object(S, "ai_find_pages", achou), mock.patch.object(S, "page_images") as pagina:
            S._web_job_run(jid, "Cafeteira", "", "", "1")
        pagina.assert_not_called()
        self.assertEqual((S.WEB_JOBS[jid]["stage"], S.WEB_JOBS[jid]["product"]), ("busy", {"name": "Cafeteira"}))

    def test_cancelada_durante_as_fotos_apaga_os_arquivos(self):
        real = S.site_of
        jid = "c0ffee" + "0" * 10

        def site_e_cancela(url):
            S.WEB_JOBS[jid]["cancelled"] = True  # logo depois de gravar a primeira foto
            return real(url)
        with mock.patch.object(S, "site_of", site_e_cancela):
            _, job = self.rodar({"paginas": [self.site.base + "produto-a.html", self.site.base + "produto-b.html"]})
        self.assertTrue(job["cancelled"], "cancelou depois de gravar a primeira foto")
        self.assertEqual(job["stage"], "busy", "cancelada não vira pronta")
        self.assertEqual(len(job.get("results") or []), 0)
        self.assertEqual(self.arquivos(jid), [], "a foto que já tinha baixado é apagada")

    def test_no_maximo_8_fotos_de_14_candidatas(self):
        for n in range(22):
            self.loja.foto(f"/foto/{n}.jpg", A1 + bytes([n]) * (n + 1))
        for n in range(8):
            self.loja.pagina(f"/p{n}.html", f'<meta property="og:image" content="/foto/{2 * n}.jpg"><meta name="twitter:image" content="/foto/{2 * n + 1}.jpg">')
        jid, job = self.rodar({"paginas": [self.loja.base + f"p{n}.html" for n in range(8)],
                               "imagens": [self.loja.base + f"foto/{n}.jpg" for n in range(16, 22)]})
        self.assertEqual(job["stage"], "done", job["msg"])
        self.assertEqual(self.loja.vezes("/foto/"), 14, "confere só as 14 primeiras")
        self.assertEqual([r["image"] for r in job["results"]], [self.loja.base + f"foto/{n}.jpg" for n in range(8)])
        self.assertEqual([r["n"] for r in job["results"]], list(range(8)))
        self.assertEqual(len(self.arquivos(jid)), 8)

    def test_duas_fotos_por_pagina(self):
        for n in range(4):
            self.loja.foto(f"/foto/{n}.jpg", A1 + bytes([n]) * (n + 1))
        self.loja.pagina("/quatro.html", '<meta property="og:image" content="/foto/0.jpg"><meta name="twitter:image" content="/foto/1.jpg">'
                                         '<meta itemprop="image" content="/foto/2.jpg"><link rel="image_src" href="/foto/3.jpg">')
        _, job = self.rodar({"paginas": [self.loja.base + "quatro.html"]})
        self.assertEqual([r["image"] for r in job["results"]], [self.loja.base + "foto/0.jpg", self.loja.base + "foto/1.jpg"])
        self.assertEqual(self.loja.vezes("/foto/2.jpg") + self.loja.vezes("/foto/3.jpg"), 0)

    def test_campos_de_cada_foto_e_os_arquivos(self):
        jid, job = self.rodar({"paginas": [self.site.base + "produto-b.html"], "imagens": [self.site.base + "img/e.jpg"]})
        self.assertEqual(job["results"], [
            {"n": 0, "kind": "webp", "image": self.site.base + "img/b.webp", "page": self.site.base + "produto-b.html", "site": "127.0.0.1", "w": 700, "h": 700},
            {"n": 1, "kind": "jpeg", "image": self.site.base + "img/e.jpg", "page": "", "site": "127.0.0.1", "w": 900, "h": 700}])
        self.assertEqual(self.arquivos(jid), [f"web-{jid}-0.webp", f"web-{jid}-1.jpg"])
        with open(os.path.join(S.TMP_DIR, f"web-{jid}-1.jpg"), "rb") as f:
            self.assertEqual(f.read(), arquivo("e.jpg"))

    def test_estado_da_busca_pela_rota(self):
        jid, _ = self.rodar({"paginas": [self.site.base + "produto-b.html"], "produto": {"nome": "Cafeteira"}})
        h = Resposta()
        S.r_web_status(h, jid, {})
        status, obj = h.enviado[0]
        self.assertEqual((status, set(obj)), (200, {"stage", "msg", "results", "product"}))
        self.assertEqual((obj["stage"], obj["product"]["name"], len(obj["results"])), ("done", "Cafeteira", 1))

    def test_foto_da_busca_pela_rota(self):
        jid, _ = self.rodar({"paginas": [self.site.base + "produto-b.html"]})
        h = Resposta()
        S.r_web_image(h, jid, "0", {})
        self.assertEqual(h.arquivos, [(os.path.join(S.TMP_DIR, f"web-{jid}-0.webp"), "image/webp", "no-store")])
        self.assertApiError(404, S.r_web_image, h, jid, "5", {}, msg_part="Foto não encontrada")

    def test_cancelar_busca_terminada_apaga_tudo(self):
        jid, _ = self.rodar({"paginas": [self.site.base + "produto-b.html"]})
        h = Resposta()
        S.r_web_cancel(h, jid, {})
        self.assertEqual(h.enviado, [(200, {"ok": True})])
        self.assertNotIn(jid, S.WEB_JOBS)
        self.assertEqual(self.arquivos(jid), [])

    def test_cancelar_busca_em_andamento_so_marca(self):
        jid = "e" * 16
        S.WEB_JOBS[jid] = {"stage": "busy", "msg": "", "results": [], "at": time.time()}
        S.r_web_cancel(Resposta(), jid, {})
        self.assertTrue(S.WEB_JOBS[jid]["cancelled"], "quem apaga é a própria busca, ao parar")

    def test_cancelar_busca_que_nao_existe(self):
        h = Resposta()
        S.r_web_cancel(h, "f" * 16, {})
        self.assertEqual(h.enviado, [(200, {"ok": True})])

    def test_limpeza_mantem_as_recentes(self):
        jid, _ = self.rodar({"paginas": [self.site.base + "produto-b.html"]})
        S.web_jobs_cleanup()
        self.assertIn(jid, S.WEB_JOBS)
        self.assertEqual(len(self.arquivos(jid)), 1)

    def test_limpeza_apaga_so_arquivos_velhos_da_busca(self):
        velho = time.time() - S.WEB_JOB_TTL - 60
        caminhos = {n: helpers.write_file(os.path.join(S.TMP_DIR, n), b"x") for n in ("web-aaaa-0.jpg", "web-bbbb-0.jpg", "outro.jpg")}
        for n in ("web-aaaa-0.jpg", "outro.jpg"):
            os.utime(caminhos[n], (velho, velho))
        S.web_jobs_cleanup()
        self.assertEqual(sorted(os.listdir(S.TMP_DIR)), ["outro.jpg", "web-bbbb-0.jpg"])

    def test_limpeza_sem_pasta_temporaria_nao_quebra(self):
        S.WEB_JOBS["a" * 16] = {"stage": "done", "msg": "", "results": [], "at": 0}
        os.rmdir(S.TMP_DIR)
        S.web_jobs_cleanup()
        self.assertEqual(S.WEB_JOBS, {})
        self.assertEqual(S._web_job_files("a" * 16), [])

    def test_ia_desligada_no_meio_da_busca(self):
        resposta = json.dumps({"paginas": [self.site.base + "produto-b.html"], "produto": {"nome": "Cafeteira"}})

        def desliga_e_responde(kind, payload):
            self.store.settings["ai"] = False
            return resposta
        self.ha.ai_reply = desliga_e_responde
        jid = "c0ffee" + "1" * 10
        S.WEB_JOBS[jid] = {"stage": "busy", "msg": "", "results": [], "at": time.time()}
        S._web_job_run(jid, "Cafeteira", "", "", "1")
        self.assertEqual(S.WEB_JOBS[jid]["stage"], "done")
        for fn, args in ((S.web_job, (jid,)), (S.r_web_status, (Resposta(), jid, {})), (S.r_web_image, (Resposta(), jid, "0", {}))):
            with self.subTest(fn=fn.__name__):
                self.assertApiError(409, fn, *args, msg_part="IA está desligada")


if __name__ == "__main__":
    unittest.main()
