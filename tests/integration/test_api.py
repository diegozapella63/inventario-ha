"""O servidor de verdade pelo HTTP: tela, dados, itens, cômodos, categorias, fotos, configurações e segurança."""
import json
import socket
import time
import unittest

from _boot import ServerCase, b64, helpers, AppServer


class Tela(ServerCase):
    def test_pagina_versao_e_arquivos(self):
        st, h, html = self.app.get("/")
        self.assertEqual(st, 200)
        self.assertIn("text/html", h["Content-Type"])
        self.assertNotIn(b"%%V%%", html, "a versão entra na página")
        for path, tipo in (("app.js", "javascript"), ("style.css", "text/css"), ("index.html", "text/html")):
            st, h, _ = self.app.get(path)
            self.assertEqual((st, tipo in h["Content-Type"]), (200, True), path)
            self.assertEqual(h.get("X-Content-Type-Options"), "nosniff")
        st, _, out = self.app.get("api/health")
        self.assertEqual((st, out["ok"]), (200, True))

    def test_nada_fora_da_pasta_da_tela(self):
        for path in ("../server.py", "..%2fserver.py", "%2e%2e/server.py", "/etc/passwd", "photos/../inventario.json", "photos/..%2finventario.json",
                     "thumbs/nao-existe.jpg", "nao-existe.js"):
            with self.subTest(path=path):
                st, _, out = self.app.get(path)
                self.assertEqual(st, 404)
        st, _, _ = self.app.request("GET", "api/nao-existe")
        self.assertEqual(st, 404)
        st, _, _ = self.app.request("PATCH" if False else "DELETE", "api/data")
        self.assertEqual(st, 404)

    def test_fotos_e_miniaturas(self):
        st, h, body = self.app.get("photos/sala-1.jpg")
        self.assertEqual((st, h["Content-Type"]), (200, "image/jpeg"))
        self.assertIn("immutable", h["Cache-Control"])
        self.assertEqual(body, helpers.fixture_photo("sala-1.jpg"))
        self.assertEqual(self.app.get("thumbs/sala-1.jpg")[0], 200)


class Dados(ServerCase):
    def test_tudo_o_que_a_tela_precisa(self):
        d = self.app.ok("GET", "api/data", headers={"X-Remote-User-Display-Name": "Diego"})
        self.assertEqual((len(d["rooms"]), len(d["items"]), len(d["cats"])), (6, 38, 13))
        self.assertEqual(d["user"], "Diego")
        self.assertEqual(d["settings"], {"ai_entity": "", "ai_search": "", "voice_stt": "", "ai": True, "zones": False, "ha_sensors": False})
        self.assertEqual(d["features"], {"ai": False, "share": True}, "sem Home Assistant, sem IA")
        self.assertRegex(d["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(self.app.ok("GET", "api/rev")["rev"], d["rev"])

    def test_revisao_sobe_a_cada_mudanca(self):
        r0 = self.app.ok("GET", "api/rev")["rev"]
        out = self.app.ok("POST", "api/items", {"room": "varanda", "name": "Rede"})
        self.assertEqual(out["rev"], r0 + 1)
        self.assertEqual(self.app.ok("GET", "api/rev")["rev"], r0 + 1)
        self.app.ok("DELETE", f"api/items/{out['item']['id']}")


class Itens(ServerCase):
    def test_ciclo_completo(self):
        foto = self.upload_photo()
        st, _, out = self.app.post("api/items", {"room": "quarto", "name": "Cômoda", "details": "branca", "cat": "moveis", "qty": "1",
                                                 "value": "1.200,00", "photos": [foto]}, headers={"X-Remote-User-Name": "dessa"})
        self.assertEqual(st, 201)
        it = out["item"]
        self.assertEqual((it["value"], it["photos"], it["createdBy"], it["room"]), (1200, [foto], "dessa", "quarto"))
        st, _, out = self.app.put(f"api/items/{it['id']}", {"name": "Cômoda de 4 gavetas", "_base": it["updatedAt"]})
        self.assertEqual((st, out["item"]["name"]), (200, "Cômoda de 4 gavetas"))
        time.sleep(1.05)
        self.app.put(f"api/items/{it['id']}", {"value": 900})
        st, _, out = self.app.put(f"api/items/{it['id']}", {"name": "Velha", "_base": it["updatedAt"]})
        self.assertEqual(st, 409, "editado em outro aparelho")
        self.assertEqual(out["item"]["value"], 900, "o conflito traz a versão atual")
        st, _, out = self.app.put(f"api/items/{it['id']}", {"room": "escritorio"})
        self.assertTrue(out["item"]["room"] == "escritorio")
        self.assertEqual(self.app.delete(f"api/items/{it['id']}")[0], 200)
        self.assertEqual(self.app.delete(f"api/items/{it['id']}")[0], 404)
        self.assertEqual(self.app.put(f"api/items/{it['id']}", {"name": "x"})[0], 404)

    def test_erros_de_cadastro(self):
        for body, parte in (({"room": "sala", "name": ""}, "nome"), ({"room": "x", "name": "A"}, "cômodo"), ({"room": "sala", "name": "A", "value": "caro"}, "Valor"),
                            ({"room": "sala", "name": "A", "photos": ["sumiu.jpg"]}, "foto")):
            with self.subTest(body=body):
                st, _, out = self.app.post("api/items", body)
                self.assertEqual(st, 400)
                self.assertIn(parte, out["error"])
        st, _, out = self.app.request("POST", "api/items", raw=b"{nao e json", headers={"Content-Type": "application/json"})
        self.assertEqual((st, out["error"]), (400, "Pedido inválido (JSON)."))

    def test_lote_do_catalogar_e_falar(self):
        st, _, out = self.app.post("api/items/batch", {"items": [{"room": "cozinha", "name": "A", "source": "foto"}, {"room": "cozinha", "name": "B", "source": "voz"}],
                                                        "roomPhoto": {"room": "cozinha", "file": "sala-3.jpg", "label": "Bancada"}})
        self.assertEqual(st, 201)
        self.assertEqual([i["source"] for i in out["items"]], ["foto", "voz"])
        self.assertTrue(any(p["file"] == "sala-3.jpg" for r in out["rooms"] if r["id"] == "cozinha" for p in r["photos"]))
        for body in ({"items": []}, {"items": "x"}, {"items": [{"room": "cozinha", "name": "x"}] * 61}):
            self.assertEqual(self.app.post("api/items/batch", body)[0], 400)
        n = len(self.app.data()["items"])
        st, _, _ = self.app.post("api/items/batch", {"items": [{"room": "cozinha", "name": "Bom"}, {"room": "cozinha", "name": ""}]})
        self.assertEqual(st, 400)
        self.assertEqual(len(self.app.data()["items"]), n, "o lote com um item ruim não entra pela metade")
        self.app.ok("PUT", "api/settings", {"zones": False})
        self.assertEqual(len(self.app.data()["items"]), n, "nem numa gravação seguinte")
        for it in out["items"]:
            self.app.delete(f"api/items/{it['id']}")


class Comodos(ServerCase):
    def test_ciclo_completo(self):
        st, _, out = self.app.post("api/rooms", {"name": "Garagem", "code": "gar"})
        self.assertEqual((st, out["room"]["code"]), (201, "GAR"))
        rid = out["room"]["id"]
        foto = self.upload_photo()
        out = self.app.ok("POST", f"api/rooms/{rid}/photos", {"file": foto, "label": "Prateleira"})
        self.assertEqual(out["room"]["photos"], [{"file": foto, "label": "Prateleira"}])
        out = self.app.ok("PUT", f"api/rooms/{rid}", {"name": "Garagem coberta", "code": "GA2", "cover": 0})
        self.assertEqual((out["room"]["name"], out["room"]["code"]), ("Garagem coberta", "GA2"))
        ids = [r["id"] for r in self.app.data()["rooms"]]
        out = self.app.ok("POST", "api/rooms/order", {"ids": [rid] + [i for i in ids if i != rid]})
        self.assertEqual(out["rooms"][0]["id"], rid)
        it = self.app.ok("POST", "api/items", {"room": rid, "name": "Furadeira"})["item"]
        st, _, err = self.app.delete(f"api/rooms/{rid}")
        self.assertEqual(st, 400)
        self.assertIn("Mova ou exclua", err["error"])
        self.app.delete(f"api/items/{it['id']}")
        self.assertEqual(self.app.delete(f"api/rooms/{rid}")[0], 200)
        self.assertEqual(self.app.put(f"api/rooms/{rid}", {"name": "x"})[0], 404)
        self.app.ok("POST", "api/rooms/order", {"ids": ids})


class Categorias(ServerCase):
    def test_ciclo_completo(self):
        st, _, out = self.app.post("api/cats", {"name": "Oficina"})
        self.assertEqual((st, out["cat"]["id"], out["cats"][-1]["id"]), (201, "oficina", "outros"))
        it = self.app.ok("POST", "api/items", {"room": "varanda", "name": "Serrote", "cat": "oficina"})["item"]
        self.assertEqual(it["cat"], "oficina")
        self.assertEqual(self.app.post("api/cats", {"name": "OFICINA"})[0], 400)
        self.assertEqual(self.app.ok("PUT", "api/cats/oficina", {"name": "Oficina e jardim"})["cat"]["name"], "Oficina e jardim")
        self.assertEqual(self.app.put("api/cats/Oficina", {"name": "x"})[0], 404, "ids de categoria são minúsculos")
        out = self.app.ok("DELETE", "api/cats/oficina")
        self.assertEqual(out["moved"], 1)
        self.assertEqual(next(i for i in self.app.data()["items"] if i["id"] == it["id"])["cat"], "outros")
        self.assertEqual(self.app.delete("api/cats/outros")[0], 400)
        self.app.delete(f"api/items/{it['id']}")


class Fotos(ServerCase):
    def test_enviar(self):
        jpg = helpers.jpeg()
        st, _, out = self.app.post("api/photos", {"full": b64(jpg), "thumb": b64(jpg)})
        self.assertEqual(st, 201)
        self.assertEqual(self.app.get(f"photos/{out['file']}")[2], jpg)
        self.assertEqual(self.app.post("api/photos", {"full": b64(b"GIF89a" + b"0" * 300)})[0], 400)

    def test_miniatura_no_lugar_da_foto_enquanto_ela_nao_chega(self):
        helpers.write_file(self.app.path("data", "thumbs", "so-mini.jpg"), helpers.jpeg())
        st, h, _ = self.app.get("photos/so-mini.jpg")
        self.assertEqual((st, h["Cache-Control"]), (200, "no-cache"), "a miniatura serve, sem guardar no cache")

    def test_pedido_grande_demais(self):
        st, _, out = self.app.request("POST", "api/photos", raw=b"{}", headers={"Content-Type": "application/json", "Content-Length": str(31 * 1024 * 1024)})
        self.assertEqual(st, 413)


class Configuracoes(ServerCase):
    def test_opcoes_da_casa(self):
        self.assertEqual(self.app.ok("GET", "api/settings"), {})
        out = self.app.ok("PUT", "api/settings", {"zones": True, "ai": False, "ai_entity": "ai_task.google", "ai_search": "conversation.gemini", "voice_stt": "stt.cloud"})
        self.assertEqual((out["zones"], out["ai"], out["ai_entity"], out["ai_search"], out["voice_stt"]), (True, False, "ai_task.google", "conversation.gemini", "stt.cloud"))
        d = self.app.data()["settings"]
        self.assertEqual((d["zones"], d["ai"]), (True, False))
        with open(self.app.path("data", "settings.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["zones"], True)
        self.app.ok("PUT", "api/settings", {"zones": False, "ai": True, "ai_entity": "", "ai_search": "", "voice_stt": ""})

    def test_valores_invalidos_nao_mudam_nada(self):
        antes = self.app.ok("GET", "api/settings")
        for body in ({"zones": "sim"}, {"ai": 1}, {"ai_entity": "conversation.x"}, {"ai_entity": "ai_task.X Y"}, {"ai_search": "light.sala"},
                     {"voice_stt": "ai_task.x"}, {"zones": True, "ai": "nao"}, {"ai_entity": "ai_task.ok", "voice_stt": "ruim"}):
            with self.subTest(body=body):
                self.assertEqual(self.app.put("api/settings", body)[0], 400)
                self.assertEqual(self.app.ok("GET", "api/settings"), antes, "nada vale pela metade")
        self.assertEqual(self.app.request("PUT", "api/settings", raw=b"[1]", headers={"Content-Type": "application/json"})[0], 400)


class Seguranca(unittest.TestCase):
    """Fora do modo dev, só o Supervisor (Ingress) abre o app; os outros apps só leem /api/integracao com a chave."""

    @classmethod
    def setUpClass(cls):
        cls.app = AppServer(dev=False)

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def test_so_pelo_home_assistant(self):
        for path in ("/", "api/data", "api/health", "photos/sala-1.jpg"):
            with self.subTest(path=path):
                st, _, out = self.app.get(path)
                self.assertEqual(st, 403)
        st, _, out = self.app.post("api/items", {"room": "sala", "name": "invasor"})
        self.assertEqual(st, 403)
        self.assertIn("Home Assistant", out["error"])
        self.assertEqual(len(self.app.stored()["items"]), 38)

    def test_endereco_do_supervisor_entra(self):
        app = AppServer(dev=False, env={"INV_ALLOW": "127.0.0.1"})
        try:
            self.assertEqual(app.get("api/data")[0], 200)
        finally:
            app.stop()

    def test_outros_apps_com_a_chave(self):
        with open(self.app.path("share", "integracao.json"), encoding="utf-8") as f:
            info = json.load(f)
        key = {"Authorization": f"Bearer {info['chave']}", "X-App": "ResolvIA"}
        st, _, out = self.app.get("api/integracao/comodos", headers=key)
        self.assertEqual(st, 200)
        self.assertEqual(out["comodos"][0], {"id": "sala", "nome": "Sala de estar", "codigo": "SAL", "itens": 12})
        st, _, out = self.app.get("api/integracao/itens", headers=key)
        self.assertEqual((st, len(out["itens"])), (200, 38))
        sofa = next(i for i in out["itens"] if i["id"] == "sal-001")
        self.assertEqual((sofa["comodo"], sofa["categoria"], sofa["valor"], sofa["valor_em"]), ("sala", "moveis", 1800.0, "2026-10-02"))
        self.assertEqual(out["categorias"]["moveis"], "Móveis")
        for h in ({}, {"Authorization": "Bearer errada"}):
            self.assertEqual(self.app.get("api/integracao/itens", headers=h)[0], 401)
        self.assertEqual(self.app.get("api/data", headers=key)[0], 403, "a chave só abre a integração")
        self.assertEqual(self.app.post("api/integracao/itens", {}, headers=key)[0], 404, "só leitura")


class Robustez(ServerCase):
    def test_conexao_cortada_no_meio_nao_derruba(self):
        s = socket.create_connection(("127.0.0.1", self.app.port))
        s.sendall(b"POST /api/items HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 500\r\n\r\n{\"room\":")
        s.close()
        time.sleep(0.3)
        self.assertEqual(self.app.get("api/health")[0], 200)

    def test_envio_em_partes_http(self):
        import http.client
        body = json.dumps({"room": "varanda", "name": "Vaso grande"}).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=10)
        conn.request("POST", "/api/items", body=iter([body[:10], body[10:]]), headers={"Content-Type": "application/json"}, encode_chunked=True)
        r = conn.getresponse()
        out = json.loads(r.read())
        conn.close()
        self.assertEqual(r.status, 201)
        self.assertEqual(out["item"]["name"], "Vaso grande")
        self.app.delete(f"api/items/{out['item']['id']}")

    def test_varios_ao_mesmo_tempo(self):
        import threading
        erros = []

        def cria(n):
            st, _, out = self.app.post("api/items", {"room": "lavanderia", "name": f"Pregador {n}"})
            if st != 201:
                erros.append(out)

        ts = [threading.Thread(target=cria, args=(n,)) for n in range(20)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(erros, [])
        novos = [i for i in self.app.data()["items"] if i["name"].startswith("Pregador")]
        self.assertEqual(len(novos), 20)
        self.assertEqual(len({i["id"] for i in novos}), 20, "cada um com seu código")
        self.assertEqual(len({i["seq"] for i in novos}), 20)
        self.assertEqual(len([i for i in self.app.stored()["items"] if i["name"].startswith("Pregador")]), 20, "e todos no arquivo")
        for i in novos:
            self.app.delete(f"api/items/{i['id']}")


if __name__ == "__main__":
    unittest.main()
