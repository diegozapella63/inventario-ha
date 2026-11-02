"""Falar (fala para texto do Home Assistant) e Buscar na internet (páginas, fotos, segurança dos endereços)."""
import json
import os
import socket
import time
import unittest
from unittest import mock

from _boot import UnitBase, helpers, server as S

PCM = b"\x01\x00" * 16000  # 1 segundo de "áudio"


class FalaParaTexto(UnitBase):
    def test_padrao_e_a_do_assistente_preferido(self):
        ha = self.fake_ha()
        st = S.voice_status()
        self.assertTrue(st["ready"])
        self.assertEqual((st["engine"], st["name"], st["assistant"], st["language"]), ("stt.home_assistant_cloud", "Home Assistant Cloud", "Gemini", "pt-BR"))
        self.assertEqual([e["id"] for e in st["engines"]], ["stt.faster_whisper", "stt.home_assistant_cloud"])
        auth = [r for r in ha.calls("WS") if r["path"] == "auth"][-1]["body"]
        self.assertEqual(auth, {"type": "auth", "access_token": ha.token})

    def test_escolhida_e_idioma_que_ela_aceita(self):
        self.fake_ha()
        self.store.settings["voice_stt"] = "stt.faster_whisper"
        st = S.voice_status()
        self.assertEqual((st["engine"], st["language"], st["assistant"], st["selected"]), ("stt.faster_whisper", "pt", "", "stt.faster_whisper"))

    def test_escolhida_que_sumiu_volta_para_o_padrao(self):
        self.fake_ha()
        self.store.settings["voice_stt"] = "stt.sumiu"
        st = S.voice_status()
        self.assertEqual((st["engine"], st["missing"]), ("stt.home_assistant_cloud", True))

    def test_sem_assistente_usa_a_primeira_fala_para_texto(self):
        ha = self.fake_ha()
        ha.ws_fail = True
        st = S.voice_status()
        self.assertEqual(st["engine"], "stt.faster_whisper")

    def test_sem_nenhuma(self):
        ha = self.fake_ha()
        ha.pipelines = {"preferred_pipeline": None, "pipelines": []}
        ha.states = [s for s in ha.states if not s["entity_id"].startswith("stt.")]
        st = S.voice_status()
        self.assertFalse(st["ready"])
        self.assertIn("Assistentes de voz", st["reason"])
        self.assertApiError(409, S.voice_text, PCM)

    def test_guarda_por_um_minuto(self):
        ha = self.fake_ha()
        S.voice_status()
        n = len(ha.calls("WS"))
        S.voice_status()
        self.assertEqual(len(ha.calls("WS")), n)
        S._voice_cache["at"] = 0
        S.voice_status()
        self.assertGreater(len(ha.calls("WS")), n)

    def test_audio_para_texto_com_o_cabecalho_exato(self):
        ha = self.fake_ha()
        res = S.voice_text(PCM)
        self.assertEqual(res["text"], ha.stt_text)
        call = ha.calls("POST", "/core/api/stt/")[-1]
        self.assertIn("X-Speech-Content", call["headers"], "o Supervisor só repassa o cabeçalho escrito assim")
        self.assertEqual(call["body"]["speech"], "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1; language=pt-BR")
        self.assertEqual(call["body"]["bytes"], len(PCM))
        self.assertTrue(call["path"].endswith("/stt/stt.home_assistant_cloud"))

    def test_audio_curto_longo_e_falhas(self):
        ha = self.fake_ha()
        self.assertApiError(422, S.voice_text, b"\0" * 100, msg_part="Não ouvi")
        self.assertApiError(413, S.voice_text, b"\0" * (S.VOICE_MAX + 2), msg_part="2 minutos")
        ha.stt_result = "error"
        self.assertApiError(422, S.voice_text, PCM, msg_part="Não entendi")
        ha.stt_status = 415
        self.assertApiError(502, S.voice_text, PCM, msg_part="não aceitou o áudio")
        self.assertEqual(S._voice_cache["at"], 0.0, "uma falha faz conferir a fala para texto de novo")
        ha.stt_status = 500
        self.assertApiError(502, S.voice_text, PCM, msg_part="falhou (500")

    def test_simulado(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep"):
            self.assertEqual(S.voice_status()["engine"], "stt.simulado")
            self.assertEqual(S.voice_text(PCM)["text"], S.MOCK_SPEECH)


class PaginasDeProduto(UnitBase):
    def ler(self, html):
        p = S._PageImages()
        p.feed(html)
        p.close()
        return p

    def test_metas_json_ld_e_titulo(self):
        p = self.ler('<html><head><title> Produto   X </title><meta property="og:image" content="/a.jpg"><meta name="twitter:image" content="b.jpg">'
                     '<link rel="image_src" href="/c.jpg"><meta itemprop="image" content="/d.jpg">'
                     '<script type="application/ld+json">{"@graph": [{"@type": "Product", "image": ["/e.jpg", {"url": "/f.jpg"}]}]}</script></head></html>')
        self.assertEqual(p.title, "Produto X")
        self.assertEqual(sorted(p.metas), [(1, "/a.jpg"), (2, "b.jpg"), (3, "/d.jpg"), (4, "/c.jpg")])
        self.assertEqual(S._ld_images(p.ld[0]), ["/e.jpg", "/f.jpg"])

    def test_json_ld_de_varios_jeitos(self):
        self.assertEqual(S._ld_images('{"@type": ["Product"], "image": "/a.jpg"}'), ["/a.jpg"])
        self.assertEqual(S._ld_images('{"@type": "ProductGroup", "hasVariant": [{"@type": "Product", "image": {"contentUrl": "/v.jpg"}}]}'), ["/v.jpg"])
        self.assertEqual(S._ld_images('{"@type": "WebPage", "image": "/logo.png"}'), [], "imagem da página não é foto do produto")
        self.assertEqual(S._ld_images("{quebrado"), [])
        fundo = '{"@type": "Product", "image": "/x.jpg"}'
        for _ in range(12):
            fundo = '{"mainEntity": ' + fundo + "}"
        self.assertEqual(S._ld_images(fundo), [], "não desce para sempre")

    def test_enderecos(self):
        self.assertEqual(S._fix_url("/a.jpg", "https://loja.exemplo/p/1"), "https://loja.exemplo/a.jpg")
        self.assertEqual(S._fix_url("//cdn.exemplo/a.jpg"), "https://cdn.exemplo/a.jpg")
        self.assertEqual(S._fix_url("img.jpg?x=1&amp;y=2", "https://l.exemplo/p/"), "https://l.exemplo/p/img.jpg?x=1&y=2")
        for ruim in ("javascript:alert(1)", "data:image/png;base64,xx", "ftp://x/a.jpg", "a b.jpg", None, 5, "https://x/" + "a" * 1000):
            with self.subTest(ruim=ruim):
                self.assertIsNone(S._fix_url(ruim, "https://l.exemplo/"))
        self.assertEqual(S.site_of("https://www.loja.exemplo/x"), "loja.exemplo")
        self.assertEqual(S.site_of("http://m.loja.exemplo/x"), "loja.exemplo")

    def test_tipo_e_tamanho_das_fotos(self):
        d = os.path.join(helpers.SITE, "img")
        for nome, tipo, tam in (("a1.jpg", "jpeg", (800, 800)), ("a2.png", "png", (600, 600)), ("b.webp", "webp", (700, 700)), ("c.jpg", "jpeg", (640, 800))):
            with open(os.path.join(d, nome), "rb") as f:
                b = f.read()
            self.assertEqual(S.image_kind(b), tipo)
            self.assertEqual(S.image_size(b, tipo), tam)
        self.assertIsNone(S.image_kind(b"GIF89a....."))
        self.assertIsNone(S.image_size(b"\xff\xd8\xff", "jpeg"))
        avif = b"\0\0\0\x1cftypavif" + b"\0" * 20 + b"ispe" + b"\0\0\0\0" + (1200).to_bytes(4, "big") + (900).to_bytes(4, "big")
        self.assertEqual(S.image_kind(avif), "avif")
        self.assertEqual(S.image_size(avif, "avif"), (1200, 900))


class SegurancaDosEnderecos(UnitBase):
    def test_so_a_internet_publica(self):
        for host in ("127.0.0.1", "localhost", "10.0.0.5", "192.168.1.10", "172.30.32.2", "169.254.1.1", "::1", "homeassistant.local"):
            with self.subTest(host=host):
                with self.assertRaises(S.WebError):
                    S._public_ip(host, 80)

    def test_nome_que_aponta_para_a_rede_de_casa(self):
        with mock.patch.object(S.socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.0.2", 80))]):
            with self.assertRaises(S.WebError) as cm:
                S._public_ip("loja-falsa.exemplo", 80)
        self.assertIn("fora da internet", str(cm.exception))
        with mock.patch.object(S.socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]):
            self.assertEqual(S._public_ip("loja.exemplo", 80), "93.184.216.34")

    def test_enderecos_recusados_antes_de_conectar(self):
        for url in ("file:///etc/passwd", "ftp://loja.exemplo/a", "https://usuario:senha@loja.exemplo/", "https://loja.exemplo:8123/", "http:///x", "gopher://x"):
            with self.subTest(url=url):
                with self.assertRaises(S.WebError):
                    S.web_get(url, 1000, "*/*")


class BuscaNaInternet(UnitBase):
    def setUp(self):
        super().setUp()
        self.site = helpers.FakeSite()
        self.addCleanup(self.site.stop)
        for p in (mock.patch.object(S, "WEB_ALLOW_LOCAL", True),):
            p.start()
            self.addCleanup(p.stop)

    def test_instrucoes(self):
        p = S.web_prompt("cafeteira", "inox", "2")
        self.assertIn("Use a busca na web agora", p)
        self.assertIn("Quantidade: 2", p)
        self.assertIn('"produto"', p)
        self.assertNotIn("Quantidade", S.web_prompt("x", "", "1"))

    def test_dados_do_produto(self):
        self.assertEqual(S.web_product({"produto": {"nome": " Cafeteira  X ", "detalhes": "inox", "categoria": "cozinha", "valor": "1.200"}}),
                         {"name": "Cafeteira X", "details": "inox", "cat": "cozinha", "value": 1200})
        self.assertEqual(S.web_product({"product": {"name": "Y", "cat": "inventada", "value": "caro"}}), {"name": "Y", "details": "", "cat": "", "value": 0})
        self.assertIsNone(S.web_product({"produto": {"valor": 10}}))
        self.assertIsNone(S.web_product({}))

    def test_paginas_e_fotos_do_site(self):
        final, imgs = S.page_images(self.site.base + "produto-a.html")
        self.assertEqual(imgs, [self.site.base + "img/a1.jpg", self.site.base + "img/a2.png"], "JSON-LD antes do og:image")
        final, imgs = S.page_images(self.site.base + "produto-c.html")
        self.assertEqual(final, self.site.base + "produto-c2.html", "segue o redirecionamento")
        self.assertEqual(imgs, [self.site.base + "img/c.jpg"])
        self.assertEqual(S.page_images(self.site.base + "produto-d.html")[1], [self.site.base + "img/d.jpg"], "página com gzip")
        self.assertEqual(S.page_images(self.site.base + "img/e.jpg")[1], [self.site.base + "img/e.jpg"], "um endereço que já é foto")
        with self.assertRaises(S.WebError):
            S.page_images(self.site.base + "nao-existe.html")
        final, kind, size, body = S.fetch_image(self.site.base + "img/b.webp")
        self.assertEqual((kind, size), ("webp", (700, 700)))
        for ruim in ("img/tiny.png", "img/not-image.txt"):
            with self.assertRaises(S.WebError):
                S.fetch_image(self.site.base + ruim)

    def test_busca_completa_pela_ia(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda kind, payload: json.dumps(helpers.search_answer(self.site))
        job = S.web_job_start({"name": "Cafeteira", "details": "inox " * 200, "qty": "2"})["id"]
        for _ in range(100):
            if S.WEB_JOBS[job]["stage"] != "busy":
                break
            time.sleep(0.1)
        j = S.WEB_JOBS[job]
        self.assertEqual(j["stage"], "done", j["msg"])
        self.assertEqual(len(j["results"]), 5, "a1, a2, b, c e e; d é igual a a1; a pequena e o texto ficam de fora")
        self.assertEqual(j["product"]["value"], 450)
        instr = ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]
        self.assertIn("Quantidade: 2", instr)
        self.assertLess(instr.count("inox"), 70, "os detalhes vão encurtados")
        self.assertEqual(len([n for n in os.listdir(S.TMP_DIR) if n.startswith(f"web-{job}-")]), 5)
        S.web_jobs_cleanup(max_age=0)
        self.assertNotIn(job, S.WEB_JOBS)
        self.assertEqual([n for n in os.listdir(S.TMP_DIR) if n.startswith("web-")], [], "as fotos não escolhidas são apagadas")

    def test_ia_sem_busca_na_web(self):
        ha = self.fake_ha()
        for resposta in ('{"erro": "sem_busca"}', "Não tenho acesso à internet.", '{"paginas": []}'):
            ha.ai_reply = lambda k, p, r=resposta: r
            with self.subTest(resposta=resposta):
                e = self.assertApiError(502, S.ai_find_pages, "x", "", "")
                self.assertIn("Enable web search", e.msg)
        self.assertEqual({r["result"] for r in S.usage_summary()["recent"]}, {"sem_busca"})

    def test_assistente_de_conversa_para_buscar(self):
        ha = self.fake_ha()
        ha.conversation_reply = lambda body: json.dumps(helpers.search_answer(self.site, extra_pages=False))
        self.store.settings["ai_search"] = "conversation.google_generative_ai"
        found = S.ai_find_pages("Cafeteira", "", S.search_entity())
        self.assertEqual(len(found["pages"]), 2)
        self.assertEqual(found["product"]["name"], "Cafeteira Espresso Exemplo CX-20")
        self.assertEqual(ha.calls("POST", "/core/api/services/conversation")[-1]["body"]["agent_id"], "conversation.google_generative_ai")

    def test_nenhuma_foto_boa_mas_com_dados(self):
        ha = self.fake_ha()
        ha.ai_reply = lambda k, p: json.dumps({"paginas": [{"url": self.site.base + "semfoto.html"}], "produto": {"nome": "Coisa"}})
        job = S.web_job_start({"name": "Coisa"})["id"]
        for _ in range(100):
            if S.WEB_JOBS[job]["stage"] != "busy":
                break
            time.sleep(0.1)
        self.assertEqual(S.WEB_JOBS[job]["stage"], "error")
        self.assertIn("Não achei fotos", S.WEB_JOBS[job]["msg"])
        self.assertEqual(S.WEB_JOBS[job]["product"]["name"], "Coisa", "os dados ainda servem sem fotos")

    def test_validacao_e_ia_desligada_no_meio(self):
        self.fake_ha()
        self.assertApiError(400, S.web_job_start, {"name": ""})
        self.assertApiError(404, S.web_job, "0" * 16)
        S.WEB_JOBS["a" * 16] = {"stage": "done", "msg": "", "results": [], "at": time.time()}
        self.store.settings["ai"] = False
        self.assertApiError(409, S.web_job, "a" * 16)


if __name__ == "__main__":
    unittest.main()
