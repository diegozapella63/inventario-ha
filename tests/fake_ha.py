"""Home Assistant de mentira para os testes: a API do Supervisor (/core/api) e o WebSocket (/core/websocket).

Responde o que o InventarIA usa do Home Assistant, e guarda cada pedido para os testes conferirem:

- GET  /core/api/states                       entidades (tarefas de IA, assistentes de conversa, falas para texto, pessoas)
- GET/POST/DELETE /core/api/states/<entidade> o sensor de uso da IA
- POST /core/api/services/ai_task/generate_data?return_response
- POST /core/api/services/conversation/process?return_response
- GET  /core/api/services                     serviços (os celulares em notify.mobile_app_*)
- POST /core/api/services/notify/<celular>    aviso no celular
- GET  /core/api/stt/<entidade>               idiomas da fala para texto
- POST /core/api/stt/<entidade>               áudio para texto (exige o cabeçalho escrito "X-Speech-Content", como o Supervisor)
- WS   /core/websocket                        auth + assist_pipeline/pipeline/list, config/entity_registry/list_for_display,
                                              config/device_registry/list (os aparelhos dos rastreadores das pessoas)

Uso:
    ha = FakeHA(media_root="/tmp/media")   # sobe numa porta livre
    ha.ai_reply = lambda kind, payload: '{"items": [...]}'
    ...
    ha.stop()
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

TOKEN = "token-de-teste"

DEFAULT_STATES = [
    {"entity_id": "ai_task.google_ai_task", "state": "unknown", "attributes": {"friendly_name": "Google AI Task", "supported_features": 3}},
    {"entity_id": "ai_task.texto_apenas", "state": "unknown", "attributes": {"friendly_name": "IA só de texto", "supported_features": 1}},
    {"entity_id": "conversation.home_assistant", "state": "on", "attributes": {"friendly_name": "Home Assistant"}},
    {"entity_id": "conversation.google_generative_ai", "state": "on", "attributes": {"friendly_name": "Google Generative AI"}},
    {"entity_id": "stt.home_assistant_cloud", "state": "unknown", "attributes": {"friendly_name": "Home Assistant Cloud"}},
    {"entity_id": "stt.faster_whisper", "state": "unknown", "attributes": {"friendly_name": "faster-whisper"}},
    {"entity_id": "light.sala", "state": "off", "attributes": {"friendly_name": "Luz da sala"}},
    # pessoas (inventadas): a Ana com o celular dela (o aparelho do app Home Assistant tem outro nome que o rastreador),
    # o Beto só com o roteador (sem celular) e a Carla com um rastreador fora dos registros (pelo nome: mobile_app_tablet_da_sala)
    {"entity_id": "person.ana", "state": "home", "attributes": {"friendly_name": "Ana", "user_id": "u-ana", "device_trackers": ["device_tracker.pixel_ana"]}},
    {"entity_id": "person.beto", "state": "home", "attributes": {"friendly_name": "Beto", "user_id": "u-beto", "device_trackers": ["device_tracker.roteador_beto"]}},
    {"entity_id": "person.carla", "state": "not_home", "attributes": {"friendly_name": "Carla", "device_trackers": ["device_tracker.tablet_da_sala"]}},
]
DEFAULT_DEVICES = [
    {"id": "d-ana", "name": "Celular da Ana", "identifiers": [["mobile_app", "abc123"]]},
    {"id": "d-rot", "name": "Roteador", "identifiers": [["ping", "192.0.2.1"]]},
]
DEFAULT_TRACKERS = [{"ei": "device_tracker.pixel_ana", "di": "d-ana"}, {"ei": "device_tracker.roteador_beto", "di": "d-rot"}]

DEFAULT_PIPELINES = {"preferred_pipeline": "gemini", "pipelines": [
    {"id": "cloud", "name": "Home Assistant", "stt_engine": "stt.home_assistant_cloud", "stt_language": "pt-BR"},
    {"id": "gemini", "name": "Gemini", "stt_engine": "stt.home_assistant_cloud", "stt_language": "pt-BR"},
    {"id": "sem-fala", "name": "Só texto", "stt_engine": None},
]}

STT_LANGS = {"stt.home_assistant_cloud": ["en-US", "pt-BR"], "stt.faster_whisper": ["en", "pt"]}


def ai_kind(instructions: str) -> str:
    """De que pedido do InventarIA se trata, pelo texto das instruções."""
    if "Use a busca na web" in instructions:
        return "busca"
    if "O texto no fim é o que a pessoa falou" in instructions:
        return "fala"
    if "exatamente 1 item" in instructions:
        return "foto"
    return "catalogo"


class FakeHA:
    def __init__(self, media_root: str | None = None, token: str = TOKEN):
        self.token = token
        self.media_root = media_root
        self.states = [dict(s) for s in DEFAULT_STATES]
        self.phones = ["mobile_app_celular_da_ana", "mobile_app_tablet_da_sala", "mobile_app_celular_velho"]  # notify.mobile_app_* (inventados)
        self.devices = json.loads(json.dumps(DEFAULT_DEVICES))  # config/device_registry/list
        self.trackers = json.loads(json.dumps(DEFAULT_TRACKERS))  # config/entity_registry/list_for_display (os rastreadores)
        self.notify_status = 200
        self.todo_items = {}  # todo.x -> [{summary, uid, status, due?}] (todo.add_item e todo.get_items)
        self.events = []  # [(tipo, dados)] dos eventos disparados (POST /api/events/<tipo>)
        self.events_status = 200
        self.pipelines = json.loads(json.dumps(DEFAULT_PIPELINES))
        self.stt_text = "Sofá cinza, dois mil reais. Televisão de 50 polegadas, mil e quinhentos reais."
        self.stt_status = 200
        self.stt_result = "success"
        self.ai_reply = lambda kind, payload: json.dumps({"items": []})  # (tipo, pedido) -> texto ou dict
        self.ai_error: tuple[int, str] | None = None  # (status, mensagem) para a IA falhar
        self.conversation_reply = lambda payload: '{"erro": "sem_busca"}'
        self.ws_fail = False
        self.requests: list[dict] = []  # tudo o que chegou, na ordem
        self.lock = threading.Lock()
        fake = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _send(self, status, obj=None, raw: bytes | None = None, ctype="application/json"):
                body = raw if raw is not None else (json.dumps(obj).encode() if obj is not None else b"")
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _auth(self):
                if self.headers.get("Authorization") != f"Bearer {fake.token}":
                    self._send(401, {"message": "401: Unauthorized"})
                    return False
                return True

            def _body(self) -> bytes:
                n = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(n) if n else b""

            def _log(self, method, path, body=None, raw_headers=None):
                with fake.lock:
                    fake.requests.append({"method": method, "path": path, "body": body, "headers": raw_headers or []})

            def do_GET(self):
                path = urlparse(self.path).path
                if path in ("/core/websocket", "/websocket") and self.headers.get("Upgrade", "").lower() == "websocket":
                    return fake._websocket(self)
                if not self._auth():
                    return
                self._log("GET", self.path)
                if path == "/core/api/states":
                    return self._send(200, fake.states)
                if path.startswith("/core/api/states/"):
                    eid = unquote(path.rsplit("/", 1)[1])
                    st = next((s for s in fake.states if s["entity_id"] == eid), None)
                    return self._send(200, st) if st else self._send(404, {"message": "Entity not found."})
                if path == "/core/api/services":
                    return self._send(200, [{"domain": "notify", "services": {**{p: {} for p in fake.phones}, "notify": {}, "persistent_notification": {}}},
                                            {"domain": "light", "services": {"turn_on": {}}}])
                if path.startswith("/core/api/stt/"):
                    eid = unquote(path.rsplit("/", 1)[1])
                    return self._send(200, {"languages": STT_LANGS.get(eid, ["pt-BR"]), "formats": ["wav"], "codecs": ["pcm"],
                                            "sample_rates": [16000], "bit_rates": [16], "channels": [1]})
                return self._send(404, {"message": "Not found"})

            def do_DELETE(self):
                if not self._auth():
                    return
                path = urlparse(self.path).path
                self._log("DELETE", self.path)
                if path.startswith("/core/api/states/"):
                    eid = unquote(path.rsplit("/", 1)[1])
                    before = len(fake.states)
                    fake.states = [s for s in fake.states if s["entity_id"] != eid]
                    return self._send(200, {}) if len(fake.states) < before else self._send(404, {"message": "Entity not found."})
                return self._send(404, {"message": "Not found"})

            def do_POST(self):
                if not self._auth():
                    return
                url = urlparse(self.path)
                path = url.path
                raw = self._body()
                names = list(self.headers.keys())
                if path.startswith("/core/api/stt/"):
                    self._log("POST", self.path, {"bytes": len(raw), "speech": self.headers.get("X-Speech-Content")}, names)
                    if "X-Speech-Content" not in names:
                        return self._send(400, raw=b"Missing X-Speech-Content header", ctype="text/plain")
                    if fake.stt_status != 200:
                        return self._send(fake.stt_status, raw=b"falhou", ctype="text/plain")
                    return self._send(200, {"result": fake.stt_result, "text": fake.stt_text})
                try:
                    body = json.loads(raw or b"null")
                except ValueError:
                    return self._send(400, {"message": "JSON inválido"})
                self._log("POST", self.path, body, names)
                if path.startswith("/core/api/states/"):
                    eid = unquote(path.rsplit("/", 1)[1])
                    st = {"entity_id": eid, "state": str(body.get("state")), "attributes": body.get("attributes") or {}}
                    fake.states = [s for s in fake.states if s["entity_id"] != eid] + [st]
                    return self._send(201, st)
                if path == "/core/api/services/ai_task/generate_data":
                    if fake.ai_error:
                        return self._send(fake.ai_error[0], {"message": fake.ai_error[1]})
                    kind = ai_kind(body.get("instructions") or "")
                    seen = []
                    for a in body.get("attachments") or []:  # a foto precisa existir em /media enquanto a IA lê
                        cid = a.get("media_content_id", "")
                        rel = cid.split("media-source://media_source/local/", 1)[-1]
                        seen.append(bool(fake.media_root) and os.path.exists(os.path.join(fake.media_root, rel)))
                    with fake.lock:
                        fake.requests[-1]["attachments_present"] = seen
                    data = fake.ai_reply(kind, body)
                    return self._send(200, {"changed_states": [], "service_response": {"data": data}})
                if path == "/core/api/services/todo/add_item":
                    t = {"summary": body.get("item"), "uid": f"u{sum(len(v) for v in fake.todo_items.values()) + 1}", "status": "needs_action"}
                    if body.get("due_date"):
                        t["due"] = body["due_date"]
                    fake.todo_items.setdefault(body.get("entity_id"), []).append(t)
                    return self._send(200, [])
                if path == "/core/api/services/todo/get_items":
                    eid, quer = body.get("entity_id"), body.get("status") or ["needs_action", "completed"]
                    return self._send(200, {"changed_states": [], "service_response": {eid: {"items": [t for t in fake.todo_items.get(eid, []) if t["status"] in quer]}}})
                if path.startswith("/core/api/events/"):
                    if fake.events_status != 200:
                        return self._send(fake.events_status, {"message": "falhou"})
                    fake.events.append((path.rsplit("/", 1)[1], body))
                    return self._send(200, {"message": "Event fired."})
                if path.startswith("/core/api/services/notify/"):
                    return self._send(fake.notify_status, [] if fake.notify_status == 200 else {"message": "falhou"})
                if path == "/core/api/services/conversation/process":
                    if fake.ai_error:
                        return self._send(fake.ai_error[0], {"message": fake.ai_error[1]})
                    speech = fake.conversation_reply(body)
                    rtype = "error" if isinstance(speech, str) and speech.startswith("ERRO:") else "action_done"
                    return self._send(200, {"changed_states": [], "service_response": {"response": {
                        "response_type": rtype, "speech": {"plain": {"speech": speech[5:] if rtype == "error" else speech}}}}})
                return self._send(404, {"message": "Not found"})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    # -- endereços para o InventarIA
    @property
    def api(self) -> str:
        return f"http://127.0.0.1:{self.port}/core/api"

    @property
    def ws(self) -> str:
        return f"ws://127.0.0.1:{self.port}/core/websocket"

    def env(self) -> dict:
        return {"INV_HA_API": self.api, "INV_HA_WS": self.ws, "SUPERVISOR_TOKEN": self.token}

    def calls(self, method=None, prefix="") -> list[dict]:
        with self.lock:
            return [r for r in self.requests if (method is None or r["method"] == method) and r["path"].startswith(prefix)]

    def state(self, eid):
        return next((s for s in self.states if s["entity_id"] == eid), None)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    # -- WebSocket (só o necessário: auth e um comando)
    def _websocket(self, h: BaseHTTPRequestHandler):
        key = h.headers.get("Sec-WebSocket-Key", "")
        acc = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        h.wfile.write(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {acc}\r\n\r\n".encode())
        h.wfile.flush()
        rf, wf = h.rfile, h.wfile

        def send(obj):
            d = json.dumps(obj).encode()
            n = len(d)
            head = bytes([0x81, n]) if n < 126 else (bytes([0x81, 126]) + struct.pack(">H", n) if n < 65536 else bytes([0x81, 127]) + struct.pack(">Q", n))
            wf.write(head + d)
            wf.flush()

        def recv():
            b1, b2 = rf.read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", rf.read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", rf.read(8))[0]
            mask = rf.read(4) if b2 & 0x80 else b"\0\0\0\0"
            data = rf.read(n)
            return json.loads(bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

        try:
            send({"type": "auth_required", "ha_version": "2026.10.0"})
            auth = recv()
            self._log_ws("auth", auth)
            if auth.get("access_token") != self.token:
                send({"type": "auth_invalid", "message": "Invalid access token"})
                return
            send({"type": "auth_ok", "ha_version": "2026.10.0"})
            cmd = recv()
            self._log_ws("command", cmd)
            if self.ws_fail:
                send({"id": cmd.get("id"), "type": "result", "success": False, "error": {"code": "unknown", "message": "falhou"}})
            elif cmd.get("type") == "assist_pipeline/pipeline/list":
                send({"id": cmd.get("id"), "type": "result", "success": True, "result": self.pipelines})
            elif cmd.get("type") == "config/entity_registry/list_for_display":
                send({"id": cmd.get("id"), "type": "result", "success": True, "result": {"entity_categories": {}, "entities": self.trackers}})
            elif cmd.get("type") == "config/device_registry/list":
                send({"id": cmd.get("id"), "type": "result", "success": True, "result": self.devices})
            else:
                send({"id": cmd.get("id"), "type": "result", "success": False, "error": {"code": "unknown_command", "message": "Unknown command."}})
        except (OSError, ValueError, struct.error):
            pass
        finally:
            h.close_connection = True

    def _log_ws(self, what, msg):
        with self.lock:
            self.requests.append({"method": "WS", "path": what, "body": msg, "headers": []})


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
