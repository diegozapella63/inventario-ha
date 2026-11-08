"""Falar, sem servidor: a conversa com o Home Assistant pelo WebSocket (ha_ws, com o FakeHA e com um roteiro para ping,
mensagens em partes e conexão fechada), as falas para texto (stt_entities, stt_language), qual delas usar (voice_engine,
voice_status, a guarda de um minuto e o ?fresh), o áudio para texto (voice_text) e os itens do que foi dito (ai_from_speech)."""
import copy
import json
import re
import socket
import struct
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from _boot import UnitBase, helpers, server as S

PCM = b"\x01\x00" * 16000  # 1 segundo de "áudio"
LISTA = {"type": "assist_pipeline/pipeline/list"}


class Resposta:
    """Faz o papel do Handler nas funções r_*: guarda o que seria enviado."""

    def __init__(self, corpo=None):
        self.corpo = corpo
        self.enviado = []

    def read_body(self):
        return self.corpo

    def send_json(self, obj, status=200):
        self.enviado.append((status, obj))


class RoteiroWS:
    """Um servidor de WebSocket de uma conexão só que segue um roteiro: o que o FakeHA não faz (ping, partes, fechar)."""

    ACEITA = b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: x\r\n\r\n"

    def __init__(self, roteiro):
        self.roteiro = roteiro
        self.pedido = b""
        self.recebidos = []  # (fin, op, mascarado, dados) de cada quadro que o app mandou
        self.cliente_fechou = False
        self.erro = None
        self.liberar = threading.Event()
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.srv.settimeout(5)
        self.url = f"ws://127.0.0.1:{self.srv.getsockname()[1]}/api/websocket"
        self.thread = threading.Thread(target=self._rodar, daemon=True)
        self.thread.start()

    def _rodar(self):
        try:
            conn, _ = self.srv.accept()
        except OSError as e:
            self.erro = e
            return
        conn.settimeout(5)
        with conn, conn.makefile("rb") as f:
            try:
                while True:
                    linha = f.readline()
                    self.pedido += linha
                    if linha in (b"\r\n", b"\n", b""):
                        break
                conn.sendall(self.ACEITA)
                self.roteiro(self, conn, f)
                self.cliente_fechou = f.read(1) == b""
            except Exception as e:  # noqa: BLE001  o teste confere
                self.erro = e

    @staticmethod
    def quadro(conn, op, dados, fin=True, mascara=None):
        if isinstance(dados, (dict, list)):
            dados = json.dumps(dados).encode()
        n = len(dados)
        b0 = (0x80 if fin else 0) | op
        m = 0x80 if mascara else 0
        head = bytes([b0, m | n]) if n < 126 else (bytes([b0, m | 126]) + struct.pack(">H", n) if n < 65536 else bytes([b0, m | 127]) + struct.pack(">Q", n))
        if mascara:
            head += mascara
            dados = bytes(b ^ mascara[i % 4] for i, b in enumerate(dados))
        conn.sendall(head + dados)

    def ler(self, f):
        h = f.read(2)
        if len(h) < 2:
            raise EOFError("o app fechou")
        n = h[1] & 0x7F
        if n == 126:
            n = struct.unpack(">H", f.read(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", f.read(8))[0]
        mask = f.read(4) if h[1] & 0x80 else b"\0\0\0\0"
        dados = bytes(b ^ mask[i % 4] for i, b in enumerate(f.read(n)))
        self.recebidos.append((bool(h[0] & 0x80), h[0] & 0x0F, bool(h[1] & 0x80), dados))
        return dados

    def ler_json(self, f):
        return json.loads(self.ler(f))

    def entrar(self, conn, f):
        """auth_required, auth, auth_ok; devolve o comando que o app mandou."""
        self.quadro(conn, 1, {"type": "auth_required"})
        self.ler_json(f)
        self.quadro(conn, 1, {"type": "auth_ok"})
        return self.ler_json(f)

    def parar(self):
        self.liberar.set()
        self.thread.join(6)
        self.srv.close()


class SttFalso:
    """Uma fala para texto que responde sempre o mesmo (status e corpo), para o que o FakeHA não faz."""

    def __init__(self, status, corpo: bytes, tipo="text/plain"):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self.send_response(status)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.api = f"http://127.0.0.1:{self.httpd.server_address[1]}/core/api"
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


CAMPOS_DO_HA = ("token", "states", "pipelines", "stt_text", "stt_status", "stt_result", "ai_reply", "ai_error", "conversation_reply", "ws_fail")


class Base(UnitBase):
    @classmethod
    def tearDownClass(cls):
        ha = cls.__dict__.get("_ha")
        if ha:
            ha.stop()
            cls._ha = None
        super().tearDownClass()

    def fake_ha(self):
        """O Home Assistant de mentira, um por classe (parar um custa meio segundo), zerado a cada teste."""
        cls = type(self)
        if cls.__dict__.get("_ha") is None:
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

    def roteiro(self, fn) -> RoteiroWS:
        ws = RoteiroWS(fn)
        self.addCleanup(ws.parar)
        for p in (mock.patch.object(S, "HA_WS", ws.url), mock.patch.object(S, "SUPERVISOR_TOKEN", "token-do-roteiro")):
            p.start()
            self.addCleanup(p.stop)
        return ws

    def stt_falso(self, status, corpo, **kw) -> SttFalso:
        stt = SttFalso(status, corpo, **kw)
        self.addCleanup(stt.stop)
        S._voice_cache.update(at=time.time(), value={"engine": "stt.teste", "language": "pt-BR", "name": "Fala de teste", "assistant": ""})
        for p in (mock.patch.object(S, "HA_API", stt.api), mock.patch.object(S, "SUPERVISOR_TOKEN", "token-de-teste")):
            p.start()
            self.addCleanup(p.stop)
        return stt


# ---------------------------------------------------------------------------- ha_ws com o Home Assistant de mentira

class WebSocketComOHomeAssistant(Base):
    def test_devolve_o_resultado_do_comando(self):
        ha = self.fake_ha()
        self.assertEqual(S.ha_ws(LISTA), ha.pipelines)

    def test_manda_o_comando_com_id_1(self):
        ha = self.fake_ha()
        S.ha_ws(LISTA)
        cmd = [r for r in ha.calls("WS") if r["path"] == "command"][-1]["body"]
        self.assertEqual(cmd, {"id": 1, "type": "assist_pipeline/pipeline/list"})

    def test_chave_recusada(self):
        ha = self.fake_ha()
        ha.token = "outra-chave"
        e = self.assertApiError(502, S.ha_ws, LISTA)
        self.assertIn("não aceitou a conexão do app", e.msg)
        self.assertFalse([r for r in ha.calls("WS") if r["path"] == "command"], "não manda o comando sem entrar")

    def test_falha_do_comando_traz_a_mensagem(self):
        ha = self.fake_ha()
        ha.ws_fail = True
        self.assertApiError(502, S.ha_ws, LISTA, msg_part="falhou")

    def test_comando_desconhecido_traz_a_mensagem_do_home_assistant(self):
        self.fake_ha()
        self.assertApiError(502, S.ha_ws, {"type": "nao/existe"}, msg_part="Unknown command.")

    def test_resposta_de_mais_de_64_kb_chega_inteira(self):
        ha = self.fake_ha()
        ha.pipelines = {"preferred_pipeline": None, "pipelines": [{"id": f"p{n}", "name": "Assistente de teste " * 4, "stt_engine": None}
                                                                  for n in range(1500)]}
        self.assertGreater(len(json.dumps(ha.pipelines)), 65536)
        self.assertEqual(S.ha_ws(LISTA), ha.pipelines)

    def test_endereco_que_nao_e_websocket(self):
        ha = self.fake_ha()
        with mock.patch.object(S, "HA_WS", ha.api.replace("http://", "ws://") + "/states"):
            self.assertApiError(502, S.ha_ws, LISTA, msg_part="recusou a conexão de WebSocket")

    def test_sem_servidor_da_erro_de_conexao(self):
        with mock.patch.object(S, "HA_WS", f"ws://127.0.0.1:{helpers.free_port()}/api/websocket"), mock.patch.object(S, "SUPERVISOR_TOKEN", "x"):
            with self.assertRaises(OSError):
                S.ha_ws(LISTA, timeout=2)


# ---------------------------------------------------------------------------- ha_ws com um roteiro

class WebSocketPeloRoteiro(Base):
    @staticmethod
    def resultado(conn, cmd, res, ws=RoteiroWS):
        ws.quadro(conn, 1, {"id": cmd["id"], "type": "result", "success": True, "result": res})

    def test_pedido_de_conexao_como_o_protocolo_pede(self):
        def roteiro(ws, conn, f):
            self.resultado(conn, ws.entrar(conn, f), {})
        ws = self.roteiro(roteiro)
        S.ha_ws(LISTA)
        ws.parar()
        pedido = ws.pedido.decode()
        port = ws.url.split(":")[2].split("/")[0]
        self.assertTrue(pedido.startswith("GET /api/websocket HTTP/1.1\r\n"), pedido)
        for linha in (f"Host: 127.0.0.1:{port}", "Upgrade: websocket", "Connection: Upgrade", "Sec-WebSocket-Version: 13"):
            self.assertIn(linha + "\r\n", pedido)
        self.assertRegex(pedido, r"Sec-WebSocket-Key: [A-Za-z0-9+/]{22}==\r\n", "16 bytes ao acaso, em base64")

    def test_quadros_do_app_vao_mascarados_com_a_chave(self):
        def roteiro(ws, conn, f):
            self.resultado(conn, ws.entrar(conn, f), {})
        ws = self.roteiro(roteiro)
        S.ha_ws(LISTA)
        ws.parar()
        self.assertIsNone(ws.erro)
        self.assertEqual([(fin, op, masc) for fin, op, masc, _ in ws.recebidos], [(True, 1, True), (True, 1, True)])
        self.assertEqual(json.loads(ws.recebidos[0][3]), {"type": "auth", "access_token": "token-do-roteiro"})

    def test_responde_ping_com_pong(self):
        def roteiro(ws, conn, f):
            ws.quadro(conn, 9, b"oi")
            ws.ler(f)
            self.resultado(conn, ws.entrar(conn, f), {"ok": 1})
        ws = self.roteiro(roteiro)
        self.assertEqual(S.ha_ws(LISTA), {"ok": 1})
        ws.parar()
        self.assertEqual(ws.recebidos[0][:2] + (ws.recebidos[0][3],), (True, 10, b"oi"), "o pong devolve os mesmos dados")

    def test_ignora_pong_eventos_e_respostas_de_outro_pedido(self):
        def roteiro(ws, conn, f):
            cmd = ws.entrar(conn, f)
            ws.quadro(conn, 10, b"")
            ws.quadro(conn, 1, {"id": 1, "type": "event", "event": {"x": 1}})
            ws.quadro(conn, 1, {"id": 2, "type": "result", "success": True, "result": "de outro pedido"})
            self.resultado(conn, cmd, {"certo": True})
        self.roteiro(roteiro)
        self.assertEqual(S.ha_ws(LISTA), {"certo": True})

    def test_junta_mensagem_em_partes(self):
        def roteiro(ws, conn, f):
            ws.entrar(conn, f)
            d = json.dumps({"id": 1, "type": "result", "success": True, "result": {"pipelines": ["a", "b"]}}).encode()
            ws.quadro(conn, 1, d[:10], fin=False)
            ws.quadro(conn, 0, d[10:30], fin=False)
            ws.quadro(conn, 0, d[30:])
        self.roteiro(roteiro)
        self.assertEqual(S.ha_ws(LISTA), {"pipelines": ["a", "b"]})

    def test_ping_no_meio_das_partes_nao_perde_o_comeco(self):
        def roteiro(ws, conn, f):
            ws.entrar(conn, f)
            d = json.dumps({"id": 1, "type": "result", "success": True, "result": "inteiro"}).encode()
            ws.quadro(conn, 1, d[:15], fin=False)
            ws.quadro(conn, 9, b"p")
            ws.quadro(conn, 0, d[15:])
            ws.ler(f)  # o pong
        ws = self.roteiro(roteiro)
        self.assertEqual(S.ha_ws(LISTA), "inteiro")
        ws.parar()
        self.assertEqual(ws.recebidos[-1][1], 10)

    def test_aceita_quadro_mascarado_do_servidor(self):
        def roteiro(ws, conn, f):
            cmd = ws.entrar(conn, f)
            ws.quadro(conn, 1, {"id": cmd["id"], "type": "result", "success": True, "result": [1, 2]}, mascara=b"\x11\x22\x33\x44")
        self.roteiro(roteiro)
        self.assertEqual(S.ha_ws(LISTA), [1, 2])

    def test_sem_pedido_de_autenticacao_vai_direto_ao_comando(self):
        def roteiro(ws, conn, f):
            ws.quadro(conn, 1, {"type": "auth_ok"})
            self.resultado(conn, ws.ler_json(f), "ok")
        ws = self.roteiro(roteiro)
        self.assertEqual(S.ha_ws(LISTA), "ok")
        ws.parar()
        self.assertEqual(len(ws.recebidos), 1)
        self.assertEqual(json.loads(ws.recebidos[0][3])["type"], "assist_pipeline/pipeline/list", "não manda a chave sem ser pedida")

    def test_home_assistant_fecha_a_conexao(self):
        def roteiro(ws, conn, f):
            ws.quadro(conn, 8, b"\x03\xe8")
        self.roteiro(roteiro)
        self.assertApiError(502, S.ha_ws, LISTA, msg_part="fechou a conexão")

    def test_conexao_cortada_no_meio(self):
        def roteiro(ws, conn, f):
            ws.quadro(conn, 1, {"type": "auth_required"})
            ws.ler(f)
            conn.sendall(b"\x81")  # metade de um quadro
            conn.shutdown(socket.SHUT_WR)
        self.roteiro(roteiro)
        self.assertApiError(502, S.ha_ws, LISTA, msg_part="fechou a conexão")

    def test_falha_sem_mensagem_usa_o_texto_padrao(self):
        def roteiro(ws, conn, f):
            ws.entrar(conn, f)
            ws.quadro(conn, 1, {"id": 1, "type": "result", "success": False, "error": {}})
        self.roteiro(roteiro)
        e = self.assertApiError(502, S.ha_ws, LISTA)
        self.assertEqual(e.msg, "O Home Assistant recusou o pedido.")

    def test_sem_resposta_esgota_o_tempo(self):
        def roteiro(ws, conn, f):
            ws.entrar(conn, f)
            ws.liberar.wait(5)
        self.roteiro(roteiro)
        t0 = time.time()
        with self.assertRaises(OSError):
            S.ha_ws(LISTA, timeout=0.3)
        self.assertLess(time.time() - t0, 3)

    def test_fecha_a_conexao_depois_da_resposta(self):
        def roteiro(ws, conn, f):
            self.resultado(conn, ws.entrar(conn, f), {})
        ws = self.roteiro(roteiro)
        S.ha_ws(LISTA)
        ws.parar()
        self.assertIsNone(ws.erro)
        self.assertTrue(ws.cliente_fechou)


# ---------------------------------------------------------------------------- falas para texto e idiomas

class FalasParaTexto(Base):
    def test_so_entidades_stt_em_ordem_de_nome(self):
        ha = self.fake_ha()
        ha.states.append({"entity_id": "stt.alfa", "state": "unknown", "attributes": {"friendly_name": "alfa local"}})
        self.assertEqual([e["id"] for e in S.stt_entities()], ["stt.alfa", "stt.faster_whisper", "stt.home_assistant_cloud"],
                         "sem diferença de maiúsculas; sem luz, IA nem assistente de conversa")
        self.assertEqual(S.stt_entities()[0], {"id": "stt.alfa", "name": "alfa local"})

    def test_sem_nome_amigavel_usa_o_id(self):
        ha = self.fake_ha()
        ha.states = [{"entity_id": "stt.sem_nome", "state": "unknown", "attributes": {}},
                     {"entity_id": "stt.sem_atributos", "state": "unknown", "attributes": None}]
        self.assertEqual(S.stt_entities(), [{"id": "stt.sem_atributos", "name": "stt.sem_atributos"}, {"id": "stt.sem_nome", "name": "stt.sem_nome"}])

    def test_ignora_estados_estranhos(self):
        ha = self.fake_ha()
        ha.states = ["lixo", 5, None, {"state": "on"}, {"entity_id": "stt.boa", "attributes": {"friendly_name": "Boa"}}]
        self.assertEqual(S.stt_entities(), [{"id": "stt.boa", "name": "Boa"}])

    def test_resposta_que_nao_e_lista(self):
        ha = self.fake_ha()
        ha.states = {"message": "algo diferente"}
        self.assertEqual(S.stt_entities(), [])

    def test_sem_acesso_ao_home_assistant(self):
        self.assertApiError(503, S.stt_entities)


class IdiomaDaFala(Base):
    def idioma(self, langs, reserva="reserva"):
        with mock.patch.object(S, "ha_request", return_value=langs if not isinstance(langs, list) else {"languages": langs}):
            return S.stt_language("stt.teste", reserva)

    def test_pt_br_e_o_preferido(self):
        self.assertEqual(self.idioma(["en-US", "pt-PT", "pt-BR"]), "pt-BR")

    def test_pt_br_escrito_de_outros_jeitos(self):
        for langs, esperado in ((["en", "pt_BR"], "pt_BR"), (["pt-br", "es"], "pt-br"), (["pt-PT", "pt_BR"], "pt_BR")):
            with self.subTest(langs=langs):
                self.assertEqual(self.idioma(langs), esperado)

    def test_outro_portugues_quando_nao_tem_o_do_brasil(self):
        for langs, esperado in ((["en", "pt-PT"], "pt-PT"), (["de", "PT"], "PT"), (["en", "pt"], "pt")):
            with self.subTest(langs=langs):
                self.assertEqual(self.idioma(langs), esperado)

    def test_sem_portugues_usa_o_reserva(self):
        self.assertEqual(self.idioma(["en-US", "es-ES"], "pt-BR"), "pt-BR")

    def test_resposta_sem_lista_de_idiomas_usa_o_reserva(self):
        for resp in (None, {}, {"languages": None}, ["en"], "texto"):
            with self.subTest(resp=resp):
                with mock.patch.object(S, "ha_request", return_value=resp):
                    self.assertEqual(S.stt_language("stt.teste", "pt-BR"), "pt-BR")

    def test_erro_do_home_assistant_usa_o_reserva(self):
        with mock.patch.object(S, "ha_request", side_effect=S.ApiError(502, "O Home Assistant recusou o pedido: x")):
            self.assertEqual(S.stt_language("stt.teste", "pt"), "pt")

    def test_pergunta_os_idiomas_da_entidade_certa(self):
        ha = self.fake_ha()
        self.assertEqual(S.stt_language("stt.faster_whisper", "x"), "pt")
        self.assertEqual(ha.calls("GET", "/core/api/stt/")[-1]["path"], "/core/api/stt/stt.faster_whisper")


# ---------------------------------------------------------------------------- qual fala usar

class QualFalaUsar(Base):
    def test_preferido_sem_fala_usa_o_primeiro_assistente_com_fala(self):
        ha = self.fake_ha()
        ha.pipelines["preferred_pipeline"] = "sem-fala"
        e = S.voice_engine()
        self.assertEqual((e["engine"], e["assistant"]), ("stt.home_assistant_cloud", "Home Assistant"))

    def test_idioma_do_assistente(self):
        ha = self.fake_ha()
        for pipe, esperado in (({"stt_engine": "stt.faster_whisper", "language": "pt"}, "pt"), ({"stt_engine": "stt.faster_whisper"}, "pt-BR")):
            with self.subTest(pipe=pipe):
                ha.pipelines = {"preferred_pipeline": "a", "pipelines": [{"id": "a", "name": "A", **pipe}]}
                S._voice_cache["at"] = 0
                self.assertEqual(S.voice_engine()["language"], esperado)

    def test_provedor_antigo_tem_nome_legivel(self):
        ha = self.fake_ha()
        ha.pipelines = {"preferred_pipeline": "velho", "pipelines": [{"id": "velho", "name": "Antigo", "stt_engine": "cloud", "stt_language": "pt-BR"}]}
        e = S.voice_engine()
        self.assertEqual((e["engine"], e["name"]), ("cloud", "Home Assistant Cloud"))

    def test_fala_desconhecida_usa_o_id_como_nome(self):
        ha = self.fake_ha()
        ha.pipelines = {"preferred_pipeline": "a", "pipelines": [{"id": "a", "name": "A", "stt_engine": "stt.de_outro_lugar"}]}
        self.assertEqual(S.voice_engine()["name"], "stt.de_outro_lugar")

    def test_escolhida_igual_a_do_assistente_usa_o_idioma_dele(self):
        ha = self.fake_ha()
        self.store.settings["voice_stt"] = "stt.home_assistant_cloud"
        e = S.voice_engine()
        self.assertEqual(e, {"engine": "stt.home_assistant_cloud", "language": "pt-BR", "name": "Home Assistant Cloud", "assistant": ""})
        self.assertEqual(ha.calls("GET", "/core/api/stt/"), [], "não precisa perguntar os idiomas")

    def test_lista_de_falas_falhou_e_a_escolhida_vale(self):
        self.fake_ha()
        self.store.settings["voice_stt"] = "stt.faster_whisper"
        with mock.patch.object(S, "stt_entities", side_effect=S.ApiError(502, "O Home Assistant recusou o pedido: x")):
            e = S.voice_engine()
        self.assertEqual(e, {"engine": "stt.faster_whisper", "language": "pt", "name": "stt.faster_whisper", "assistant": ""})
        self.assertFalse(S._voice_cache["missing"], "sem a lista, não dá para dizer que sumiu")

    def test_websocket_fora_do_ar_usa_a_primeira_fala(self):
        self.fake_ha()
        with mock.patch.object(S, "HA_WS", f"ws://127.0.0.1:{helpers.free_port()}/core/websocket"):
            e = S.voice_engine()
        self.assertEqual((e["engine"], e["assistant"], e["language"]), ("stt.faster_whisper", "", "pt"))

    def test_assistentes_sem_resposta_usa_a_primeira_fala(self):
        self.fake_ha()
        with mock.patch.object(S, "ha_ws", return_value=None):
            self.assertEqual(S.voice_engine()["engine"], "stt.faster_whisper")

    def test_sem_acesso_ao_home_assistant_nao_tem_fala(self):
        with mock.patch.object(S, "ha_ws") as ws, mock.patch.object(S, "ha_request") as req:
            self.assertIsNone(S.voice_engine())
        ws.assert_not_called()
        req.assert_not_called()
        st = S.voice_status()
        self.assertEqual((st["ready"], st["engines"], st["missing"]), (False, [], False))

    def test_nada_configurado_tambem_fica_guardado(self):
        ha = self.fake_ha()
        ha.pipelines = {"preferred_pipeline": None, "pipelines": []}
        ha.states = [s for s in ha.states if not s["entity_id"].startswith("stt.")]
        self.assertFalse(S.voice_status()["ready"])
        n = len(ha.requests)
        self.assertFalse(S.voice_status()["ready"])
        self.assertEqual(len(ha.requests), n, "não pergunta de novo a cada toque no microfone")

    def test_fresh_confere_de_novo(self):
        ha = self.fake_ha()
        S.voice_status()
        n = len(ha.calls("WS"))
        h = Resposta()
        S.r_voice_status(h, {})
        self.assertEqual(len(ha.calls("WS")), n, "sem ?fresh, usa o que guardou")
        S.r_voice_status(h, {"fresh": "1"})
        self.assertGreater(len(ha.calls("WS")), n)
        self.assertEqual([(st, obj["ready"]) for st, obj in h.enviado], [(200, True), (200, True)])

    def test_trocar_a_fala_escolhida_confere_de_novo(self):
        self.fake_ha()
        self.assertEqual(S.voice_status()["engine"], "stt.home_assistant_cloud")
        S.r_settings_put(Resposta({"voice_stt": "stt.faster_whisper"}), {})
        st = S.voice_status()
        self.assertEqual((st["engine"], st["selected"]), ("stt.faster_whisper", "stt.faster_whisper"))


class SituacaoDaFala(Base):
    def test_pronto_tem_todos_os_campos(self):
        self.fake_ha()
        st = S.voice_status()
        self.assertEqual(set(st), {"ready", "engine", "language", "name", "assistant", "engines", "selected", "missing"})
        self.assertEqual((st["selected"], st["missing"]), ("", False))

    def test_sem_fala_tem_o_motivo(self):
        ha = self.fake_ha()
        ha.pipelines = {"preferred_pipeline": None, "pipelines": []}
        ha.states = [s for s in ha.states if not s["entity_id"].startswith("stt.")]
        st = S.voice_status()
        self.assertEqual(st, {"ready": False, "reason": S.VOICE_HOWTO, "engines": [], "selected": "", "missing": False})

    def test_escolhida_sem_nenhuma_fala_nao_acusa_que_sumiu(self):
        ha = self.fake_ha()
        ha.pipelines = {"preferred_pipeline": None, "pipelines": []}
        ha.states = [s for s in ha.states if not s["entity_id"].startswith("stt.")]
        self.store.settings["voice_stt"] = "stt.qualquer"
        st = S.voice_status()
        self.assertEqual((st["ready"], st["selected"], st["missing"]), (False, "stt.qualquer", False))


# ---------------------------------------------------------------------------- áudio para texto

class AudioParaTexto(Base):
    def test_exatamente_o_minimo_passa(self):
        ha = self.fake_ha()
        self.assertEqual(S.voice_text(b"\0" * S.VOICE_MIN)["text"], ha.stt_text)

    def test_exatamente_o_maximo_passa(self):
        ha = self.fake_ha()
        self.assertEqual(S.voice_text(b"\0" * S.VOICE_MAX)["text"], ha.stt_text)
        self.assertEqual(ha.calls("POST", "/core/api/stt/")[-1]["body"]["bytes"], S.VOICE_MAX)

    def test_idioma_do_cabecalho_e_o_da_fala_escolhida(self):
        ha = self.fake_ha()
        self.store.settings["voice_stt"] = "stt.faster_whisper"
        res = S.voice_text(PCM)
        call = ha.calls("POST", "/core/api/stt/")[-1]
        self.assertEqual(call["path"], "/core/api/stt/stt.faster_whisper")
        self.assertTrue(call["body"]["speech"].endswith("; language=pt"))
        self.assertEqual((res["engine"], res["name"]), ("stt.faster_whisper", "faster-whisper"))

    def test_manda_a_chave_e_o_tipo_do_audio(self):
        ha = self.fake_ha()
        S.voice_text(PCM)
        nomes = ha.calls("POST", "/core/api/stt/")[-1]["headers"]
        for nome in ("Authorization", "Content-Type", "Content-Length", "X-Speech-Content"):
            self.assertIn(nome, nomes)

    def test_chave_recusada_pela_fala_para_texto(self):
        self.stt_falso(401, b'{"message": "401: Unauthorized"}', tipo="application/json")
        self.assertApiError(502, S.voice_text, PCM, msg_part="falhou (401: ")
        self.assertEqual(S._voice_cache["at"], 0.0, "confere de novo qual fala usar")

    def test_texto_so_com_espacos_e_nao_entendi(self):
        ha = self.fake_ha()
        ha.stt_text = "   "
        self.assertApiError(422, S.voice_text, PCM, msg_part="Não entendi")

    def test_texto_volta_sem_espacos_nas_pontas(self):
        ha = self.fake_ha()
        ha.stt_text = "  sofá cinza, dois mil  "
        self.assertEqual(S.voice_text(PCM), {"text": "sofá cinza, dois mil", "engine": "stt.home_assistant_cloud", "name": "Home Assistant Cloud"})

    def test_resposta_que_nao_e_json_e_nao_entendi(self):
        self.stt_falso(200, b"<html>ok</html>", tipo="text/html")
        self.assertApiError(422, S.voice_text, PCM, msg_part="Não entendi")

    def test_sucesso_sem_texto_e_nao_entendi(self):
        self.stt_falso(200, b'{"result": "success"}', tipo="application/json")
        self.assertApiError(422, S.voice_text, PCM, msg_part="Não entendi")

    def test_detalhe_do_erro_vai_encurtado_e_em_uma_linha(self):
        self.stt_falso(500, ("erro   muito\n\ncomprido " * 60).encode())
        e = self.assertApiError(502, S.voice_text, PCM)
        detalhe = re.search(r"\(500: (.*)\)\.$", e.msg).group(1)
        self.assertEqual(len(detalhe), 200)
        self.assertNotIn("\n", detalhe)
        self.assertNotIn("  ", detalhe)

    def test_erro_sem_detalhe_mostra_o_numero(self):
        self.stt_falso(400, b"")
        e = self.assertApiError(502, S.voice_text, PCM)
        self.assertEqual(e.msg, "A fala para texto não aceitou o áudio (400).")

    def test_fala_para_texto_fora_do_ar(self):
        S._voice_cache.update(at=time.time(), value={"engine": "stt.teste", "language": "pt-BR", "name": "Teste", "assistant": ""})
        with mock.patch.object(S, "HA_API", f"http://127.0.0.1:{helpers.free_port()}/core/api"), mock.patch.object(S, "SUPERVISOR_TOKEN", "x"):
            self.assertApiError(504, S.voice_text, PCM, msg_part="Sem resposta da fala para texto")


# ---------------------------------------------------------------------------- itens do que foi dito

class ItensFalados(Base):
    def setUp(self):
        super().setUp()
        self.ha = self.fake_ha()
        self.ha.ai_reply = lambda kind, payload: '{"room": "", "items": [{"name": "Sofá", "value": 2000}]}'

    def instrucoes(self):
        return self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["instructions"]

    def test_sem_texto_pede_para_preencher(self):
        for body in ({}, {"text": None}):
            with self.subTest(body=body):
                self.assertApiError(400, S.ai_from_speech, body, msg_part="Preencha o campo texto")

    def test_texto_longo_demais(self):
        self.assertApiError(400, S.ai_from_speech, {"text": "a" * 4001}, msg_part="limite de 4000")
        self.assertEqual(self.ha.calls("POST"), [])

    def test_ia_desligada_nao_chama_o_home_assistant(self):
        self.store.settings["ai"] = False
        self.assertApiError(409, S.ai_from_speech, {"text": "um sofá"})
        self.assertEqual(self.ha.calls("POST"), [])

    def test_o_que_foi_dito_vai_nas_instrucoes(self):
        S.ai_from_speech({"text": "  sofá cinza de dois mil  "})
        instr = self.instrucoes()
        self.assertTrue(instr.endswith("O que a pessoa falou:\nsofá cinza de dois mil"))
        self.assertIn("Cômodos da casa (id = nome):\n- sala = Sala de estar.", instr)
        self.assertEqual(self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["task_name"], "InventarIA: itens falados")

    def test_comodo_escolhido_vai_nas_instrucoes(self):
        S.ai_from_speech({"text": "uma batedeira", "room": "cozinha"})
        instr = self.instrucoes()
        self.assertIn("Cômodo: Cozinha.", instr)
        self.assertIn("Itens já cadastrados neste cômodo: Geladeira frost free inox; Mesa de jantar com 4 cadeiras;", instr, "do mais caro para o mais barato")

    def test_comodo_que_nao_existe_e_ignorado(self):
        res = S.ai_from_speech({"text": "uma pá", "room": "garagem"})
        self.assertNotIn("Cômodo:", self.instrucoes())
        self.assertEqual(res["room"], "")

    def test_item_ja_cadastrado_no_comodo_que_a_ia_entendeu(self):
        self.ha.ai_reply = lambda k, p: json.dumps({"room": "cozinha", "items": [
            {"name": "Geladeira", "existing": "Geladeira frost free inox"}, {"name": "Sofá", "existing": "Sofá de 3 lugares cinza-azulado"}]})
        res = S.ai_from_speech({"text": "na cozinha tem a geladeira e o sofá"})
        self.assertEqual(res["room"], "cozinha")
        self.assertEqual([i["existing"] for i in res["items"]], ["Geladeira frost free inox", ""], "o sofá é da sala, não da cozinha")

    def test_ia_escolhida_recebe_o_pedido(self):
        self.store.settings["ai_entity"] = "ai_task.google_ai_task"
        S.ai_from_speech({"text": "um sofá"})
        self.assertEqual(self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"]["entity_id"], "ai_task.google_ai_task")
        self.assertEqual(S.usage_summary()["recent"][0]["entity"], "ai_task.google_ai_task")

    def test_sem_ia_escolhida_usa_a_preferida_do_home_assistant(self):
        S.ai_from_speech({"text": "um sofá"})
        self.assertNotIn("entity_id", self.ha.calls("POST", "/core/api/services/ai_task")[-1]["body"])

    def test_ia_sem_resposta(self):
        self.ha.ai_reply = lambda k, p: None
        self.assertApiError(502, S.ai_from_speech, {"text": "um sofá"}, msg_part="não devolveu resposta")
        self.assertEqual(S.usage_summary()["recent"][0]["result"], "formato")

    def test_ia_responde_fora_do_formato(self):
        self.ha.ai_reply = lambda k, p: "Desculpe, não entendi o que foi dito."
        e = self.assertApiError(502, S.ai_from_speech, {"text": "um sofá"})
        self.assertIn("raw", e.extra, "a tela mostra o que a IA respondeu")
        self.assertEqual(S.usage_summary()["recent"][0]["result"], "formato")

    def test_uso_registrado_como_fala(self):
        S.ai_from_speech({"text": "um sofá"})
        r = S.usage_summary()["recent"][0]
        self.assertEqual((r["kind"], r["result"], r["entity"]), ("fala", "ok", "padrão do Home Assistant"))

    def test_simulado_devolve_os_itens_de_exemplo(self):
        with mock.patch.object(S, "AI_MOCK", True), mock.patch.object(S.time, "sleep"):
            res = S.ai_from_speech({"text": "qualquer coisa"})
        self.assertEqual(([i["name"] for i in res["items"]], res["room"]), ([i["name"] for i in S.MOCK_VOICE_RESULT["items"]], ""))
        self.assertEqual(self.ha.calls("POST"), [], "simulado não chama o Home Assistant")


if __name__ == "__main__":
    unittest.main()
