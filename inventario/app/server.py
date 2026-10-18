#!/usr/bin/env python3
"""InventarIA: servidor do app (add-on) de inventário da casa para o Home Assistant.

Só usa a biblioteca padrão do Python. Os dados ficam em arquivos abertos:
  /data/inventario.json   cômodos e itens (JSON legível, dá pra abrir em qualquer editor)
  /data/photos/*.jpg      fotos em tamanho cheio
  /data/thumbs/*.jpg      miniaturas
  /data/history/*.json    cópias automáticas do inventário (para desfazer erros)
A leitura de fotos por IA usa a ação ai_task.generate_data do Home Assistant, então
funciona com a integração de IA que estiver configurada lá (Anthropic, OpenAI,
Google Gemini, Ollama local...). Sem IA, o app funciona normalmente.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

VERSION = "1.2.0"
DEV = os.environ.get("INV_DEV") == "1"
DATA_DIR = os.environ.get("INV_DATA", "/data")
SEED_DIR = os.environ.get("INV_SEED", "/app/seed")
WEB_DIR = os.environ.get("INV_WEB", "/app/web")
SHARE_DIR = os.environ.get("INV_SHARE", "/share/inventario")
MEDIA_ROOT = os.environ.get("INV_MEDIA", "/media")
PORT = int(os.environ.get("INV_PORT", "8099"))
ALLOWED_IPS = {ip.strip() for ip in os.environ.get("INV_ALLOW", "172.30.32.2").split(",") if ip.strip()}
HA_API = os.environ.get("INV_HA_API", "http://supervisor/core/api")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN")
AI_MOCK = os.environ.get("INV_AI_MOCK") == "1"

DATA_FILE = os.path.join(DATA_DIR, "inventario.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
THUMBS_DIR = os.path.join(DATA_DIR, "thumbs")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
TMP_DIR = os.path.join(DATA_DIR, "tmp")
AI_TMP_REL = "inventario/ia-temp"  # relativo a /media (fonte de mídia "local" do HA)

MAX_BODY = 30 * 1024 * 1024
HISTORY_KEEP = 60
HISTORY_EVERY = 10 * 60  # no máximo uma cópia automática a cada 10 minutos

CATS = {
    "eletronicos": "Eletrônicos", "moveis": "Móveis", "decoracao": "Decoração e arte",
    "colecao": "Colecionáveis", "cozinha": "Cozinha e bar", "texteis": "Tapetes e têxteis",
    "plantas": "Plantas", "livros": "Livros e jogos", "pets": "Pets", "saude": "Saúde",
    "vestuario": "Roupas e calçados", "utilidades": "Utilidades", "outros": "Outros",
}
SAFE_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(?:jpe?g|png|webp)")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}")
BACKUP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.zip")
HISTORY_NAME = re.compile(r"inventario-\d{8}-\d{6}\.json")

log = logging.getLogger("inventario")


class ApiError(Exception):
    def __init__(self, status: int, msg: str, **extra):
        super().__init__(msg)
        self.status, self.msg, self.extra = status, msg, extra


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H%M")


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:40] or "comodo"


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json_atomic(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def parse_value(v) -> float | int:
    if v is None or v == "":
        return 0
    try:
        if isinstance(v, bool):
            raise ValueError
        if isinstance(v, (int, float)):
            x = float(v)
        else:
            s = str(v).strip().replace("R$", "").replace(" ", "").replace(" ", "")
            if "," in s:
                s = s.replace(".", "").replace(",", ".")
            x = float(s)
    except (TypeError, ValueError):
        raise ApiError(400, "Valor inválido. Use só números, como 1200 ou 1.200,50.")
    if x != x or x < 0 or x > 1e9:
        raise ApiError(400, "Valor fora do intervalo permitido.")
    x = round(x, 2)
    return int(x) if x.is_integer() else x


def text(v, limit: int, field: str, required=False) -> str:
    s = "" if v is None else str(v).strip()
    if required and not s:
        raise ApiError(400, f"Preencha o campo {field}.")
    if len(s) > limit:
        raise ApiError(400, f"O campo {field} passou do limite de {limit} caracteres.")
    return s


def photo_exists(name: str) -> bool:
    return bool(SAFE_FILE.fullmatch(name or "")) and os.path.isfile(os.path.join(PHOTOS_DIR, name))


def clean_photos(v) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list):
        raise ApiError(400, "Lista de fotos inválida.")
    out = []
    for name in v:
        if not isinstance(name, str) or not photo_exists(name):
            raise ApiError(400, "Uma das fotos não foi encontrada. Envie a foto de novo.")
        if name not in out:
            out.append(name)
    if len(out) > 12:
        raise ApiError(400, "Use no máximo 12 fotos por item.")
    return out


# ---------------------------------------------------------------------------
# Armazenamento


class Store:
    def __init__(self):
        self.lock = threading.RLock()
        self.data: dict = {}
        self.settings: dict = {}
        self.last_snapshot = 0.0

    # -- carga e gravação
    def load(self):
        for d in (DATA_DIR, PHOTOS_DIR, THUMBS_DIR, HISTORY_DIR, TMP_DIR):
            os.makedirs(d, exist_ok=True)
        if not os.path.exists(DATA_FILE):
            self.seed()
        self.data = read_json(DATA_FILE) or {}
        self.data.setdefault("format", "inventario-casa")
        self.data.setdefault("schema", 1)
        self.data.setdefault("rev", 1)
        self.data.setdefault("rooms", [])
        self.data.setdefault("items", [])
        self.settings = read_json(SETTINGS_FILE, {}) or {}
        snaps = self.history_list()
        if snaps:
            self.last_snapshot = os.path.getmtime(os.path.join(HISTORY_DIR, snaps[0]["name"]))
        log.info("InventarIA: inventário carregado com %d cômodos e %d itens", len(self.data["rooms"]), len(self.data["items"]))

    def seed(self):
        src = os.path.join(SEED_DIR, "inventario.json")
        if os.path.exists(src):
            log.info("Primeira execução: copiando inventário inicial")
            for sub in ("photos", "thumbs"):
                sdir = os.path.join(SEED_DIR, sub)
                if os.path.isdir(sdir):
                    for name in os.listdir(sdir):
                        dst = os.path.join(DATA_DIR, sub, name)
                        if not os.path.exists(dst):
                            shutil.copyfile(os.path.join(sdir, name), dst)
            data = read_json(src)
        else:
            data = {"format": "inventario-casa", "schema": 1, "rev": 1, "rooms": [], "items": []}
        data["updatedAt"] = now_iso()
        write_json_atomic(DATA_FILE, data)

    def save(self):
        self.snapshot_if_due()
        self.data["rev"] = int(self.data.get("rev", 0)) + 1
        self.data["updatedAt"] = now_iso()
        write_json_atomic(DATA_FILE, self.data)

    def save_settings(self):
        write_json_atomic(SETTINGS_FILE, self.settings)

    # -- histórico local
    def snapshot_if_due(self, force=False):
        if not os.path.exists(DATA_FILE):
            return
        if not force and time.time() - self.last_snapshot < HISTORY_EVERY:
            return
        name = f"inventario-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        shutil.copyfile(DATA_FILE, os.path.join(HISTORY_DIR, name))
        self.last_snapshot = time.time()
        for old in self.history_list()[HISTORY_KEEP:]:
            try:
                os.unlink(os.path.join(HISTORY_DIR, old["name"]))
            except OSError:
                pass

    def history_list(self):
        try:
            names = [n for n in os.listdir(HISTORY_DIR) if HISTORY_NAME.fullmatch(n)]
        except FileNotFoundError:
            return []
        out = []
        for n in sorted(names, reverse=True):
            p = os.path.join(HISTORY_DIR, n)
            info = {"name": n, "size": os.path.getsize(p), "date": datetime.fromtimestamp(os.path.getmtime(p)).astimezone().isoformat(timespec="seconds")}
            out.append(info)
        return out

    # -- consultas
    def room(self, rid):
        return next((r for r in self.data["rooms"] if r["id"] == rid), None)

    def item(self, iid):
        return next((i for i in self.data["items"] if i["id"] == iid), None)

    def next_seq(self, rid):
        return max([i.get("seq") or 0 for i in self.data["items"] if i["room"] == rid] or [0]) + 1

    def sorted_items(self):
        order = {r["id"]: r.get("order", 99) for r in self.data["rooms"]}
        return sorted(self.data["items"], key=lambda i: (order.get(i["room"], 99), i.get("seq") or 0))

    def tag(self, it):
        r = self.room(it["room"])
        return f"{(r or {}).get('code') or 'ITM'}-{int(it.get('seq') or 0):03d}"

    def public(self):
        return {
            "rev": self.data["rev"], "updatedAt": self.data.get("updatedAt"),
            "rooms": self.data["rooms"], "items": self.data["items"],
        }

    # -- itens
    def build_item(self, body: dict, user: str | None, restore=False) -> dict:
        room = self.room(body.get("room"))
        if not room:
            raise ApiError(400, "Escolha um cômodo que exista.")
        ts = now_iso()
        it = {
            "id": None, "room": room["id"], "seq": None,
            "zone": text(body.get("zone"), 120, "zona"),
            "name": text(body.get("name"), 200, "nome", required=True),
            "details": text(body.get("details"), 4000, "detalhes"),
            "cat": body.get("cat") if body.get("cat") in CATS else "outros",
            "qty": text(body.get("qty") or "1", 30, "quantidade") or "1",
            "value": parse_value(body.get("value")),
            "photos": clean_photos(body.get("photos")),
            "checked": bool(body.get("checked")), "flag": text(body.get("flag"), 200, "observação") or None,
            "approx": True, "source": text(body.get("source") or "manual", 40, "origem"),
            "createdAt": ts, "updatedAt": ts,
        }
        if user:
            it["createdBy"] = it["updatedBy"] = user
        want_id = body.get("id") if restore else None
        want_seq = body.get("seq") if restore else None
        if restore:
            for k in ("createdAt", "createdBy", "approx", "checkedAt"):
                if body.get(k) is not None:
                    it[k] = body[k]
        seqs = {i.get("seq") for i in self.data["items"] if i["room"] == room["id"]}
        it["seq"] = want_seq if isinstance(want_seq, int) and want_seq > 0 and want_seq not in seqs else self.next_seq(room["id"])
        ids = {i["id"] for i in self.data["items"]}
        if isinstance(want_id, str) and SAFE_ID.fullmatch(want_id) and want_id not in ids:
            it["id"] = want_id
        else:
            base = f"{room['code'].lower()}-{it['seq']:03d}"
            it["id"] = base if base not in ids else f"{base}-{secrets.token_hex(2)}"
        return it

    def create_items(self, bodies: list[dict], user, restore=False, room_photo=None):
        with self.lock:
            created = []
            for b in bodies:
                it = self.build_item(b, user, restore=restore)
                self.data["items"].append(it)
                created.append(it)
            if room_photo:
                self._add_room_photo(room_photo.get("room"), room_photo.get("file"), room_photo.get("label"))
            self.save()
            return created

    def update_item(self, iid: str, body: dict, user) -> dict:
        with self.lock:
            it = self.item(iid)
            if not it:
                raise ApiError(404, "Este item não existe mais. Atualize a página.")
            base = body.get("_base")
            if base and base != it.get("updatedAt"):
                raise ApiError(409, "Este item foi alterado em outro aparelho. Confira a versão atual antes de salvar.", item=it)
            new = dict(it)
            if "room" in body and body["room"] != it["room"]:
                room = self.room(body["room"])
                if not room:
                    raise ApiError(400, "Escolha um cômodo que exista.")
                new["room"] = room["id"]
                new["seq"] = self.next_seq(room["id"])
            if "zone" in body:
                new["zone"] = text(body["zone"], 120, "zona")
            if "name" in body:
                new["name"] = text(body["name"], 200, "nome", required=True)
            if "details" in body:
                new["details"] = text(body["details"], 4000, "detalhes")
            if "cat" in body:
                new["cat"] = body["cat"] if body["cat"] in CATS else "outros"
            if "qty" in body:
                new["qty"] = text(body["qty"] or "1", 30, "quantidade") or "1"
            if "value" in body:
                new["value"] = parse_value(body["value"])
            if "photos" in body:
                new["photos"] = clean_photos(body["photos"])
            if "flag" in body:
                new["flag"] = text(body["flag"], 200, "observação") or None
            if "checked" in body:
                new["checked"] = bool(body["checked"])
                if new["checked"] and not it.get("checked"):
                    new["checkedAt"] = now_iso()
                elif not new["checked"]:
                    new.pop("checkedAt", None)
            new["updatedAt"] = now_iso()
            if user:
                new["updatedBy"] = user
            it.clear()
            it.update(new)
            self.save()
            return it

    def delete_item(self, iid: str) -> dict:
        with self.lock:
            it = self.item(iid)
            if not it:
                raise ApiError(404, "Este item não existe mais.")
            self.data["items"].remove(it)
            self.save()
            return it

    # -- cômodos
    def _unique_code(self, wanted: str, skip_id=None) -> str:
        codes = {r["code"] for r in self.data["rooms"] if r["id"] != skip_id}
        base = re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", wanted).encode("ascii", "ignore").decode().upper())[:4] or "CMD"
        if base not in codes:
            return base
        for n in range(2, 100):
            c = f"{base[:3]}{n}"
            if c not in codes:
                return c
        return secrets.token_hex(2).upper()

    def create_room(self, body: dict) -> dict:
        with self.lock:
            name = text(body.get("name"), 60, "nome do cômodo", required=True)
            rid = slug(name)
            ids = {r["id"] for r in self.data["rooms"]}
            n = 2
            while rid in ids:
                rid = f"{slug(name)}-{n}"
                n += 1
            code_in = text(body.get("code"), 4, "código") or name
            geral = self.room("geral")
            room = {
                "id": rid, "code": self._unique_code(code_in), "name": name,
                # novos cômodos entram no fim da lista, antes de "Geral"
                "order": (geral.get("order", 0) - 0.5) if geral else max([r.get("order", 0) for r in self.data["rooms"]] or [0]) + 1,
                "cover": 0, "photos": [], "updatedAt": now_iso(),
            }
            self.data["rooms"].append(room)
            self._normalize_order()
            self.save()
            return room

    def update_room(self, rid: str, body: dict) -> dict:
        with self.lock:
            room = self.room(rid)
            if not room:
                raise ApiError(404, "Este cômodo não existe mais.")
            if "name" in body:
                room["name"] = text(body["name"], 60, "nome do cômodo", required=True)
            if "code" in body:
                code = re.sub(r"[^A-Z0-9]", "", str(body["code"]).upper())[:4]
                if not code:
                    raise ApiError(400, "O código precisa ter de 1 a 4 letras ou números.")
                if code != room["code"]:
                    if any(r["code"] == code for r in self.data["rooms"] if r["id"] != rid):
                        raise ApiError(400, f"O código {code} já é usado por outro cômodo.")
                    room["code"] = code
            if "photos" in body:
                photos = []
                for p in body["photos"] or []:
                    if not isinstance(p, dict) or not photo_exists(p.get("file", "")):
                        raise ApiError(400, "Uma das fotos do cômodo não foi encontrada.")
                    photos.append({"file": p["file"], "label": text(p.get("label"), 160, "legenda")})
                room["photos"] = photos
            if "cover" in body:
                c = body["cover"]
                room["cover"] = c if isinstance(c, int) and 0 <= c < max(1, len(room["photos"])) else 0
            if room.get("cover", 0) >= max(1, len(room["photos"])):
                room["cover"] = 0
            room["updatedAt"] = now_iso()
            self.save()
            return room

    def _add_room_photo(self, rid, file, label):
        room = self.room(rid)
        if not room or not photo_exists(file or ""):
            return
        if not any(p["file"] == file for p in room["photos"]):
            room["photos"].append({"file": file, "label": text(label, 160, "legenda")})
            room["updatedAt"] = now_iso()

    def add_room_photo(self, rid, body):
        with self.lock:
            if not self.room(rid):
                raise ApiError(404, "Este cômodo não existe mais.")
            if not photo_exists(body.get("file", "")):
                raise ApiError(400, "A foto não foi encontrada. Envie de novo.")
            self._add_room_photo(rid, body["file"], body.get("label"))
            self.save()
            return self.room(rid)

    def reorder_rooms(self, ids: list):
        with self.lock:
            pos = {rid: n for n, rid in enumerate(ids or [])}
            for r in self.data["rooms"]:
                r["order"] = pos.get(r["id"], len(pos) + r.get("order", 0))
            self._normalize_order()
            self.save()
            return self.data["rooms"]

    def _normalize_order(self):
        self.data["rooms"].sort(key=lambda r: r.get("order", 0))
        for n, r in enumerate(self.data["rooms"]):
            r["order"] = n

    def delete_room(self, rid):
        with self.lock:
            room = self.room(rid)
            if not room:
                raise ApiError(404, "Este cômodo não existe mais.")
            if any(i["room"] == rid for i in self.data["items"]):
                raise ApiError(400, "Mova ou exclua os itens deste cômodo antes de excluí-lo.")
            self.data["rooms"].remove(room)
            self._normalize_order()
            self.save()
            return room

    # -- substituição completa (restauração)
    @staticmethod
    def check_inventory(data):
        if not isinstance(data, dict) or not isinstance(data.get("rooms"), list) or not isinstance(data.get("items"), list):
            raise ApiError(400, "Arquivo inválido: não parece um inventário exportado pelo app.")
        room_ids = set()
        for r in data["rooms"]:
            if not isinstance(r, dict) or not r.get("id") or not r.get("name"):
                raise ApiError(400, "Arquivo inválido: cômodo sem id ou nome.")
            r.setdefault("code", str(r["id"])[:3].upper())
            r.setdefault("photos", [])
            r.setdefault("cover", 0)
            r["photos"] = [p if isinstance(p, dict) else {"file": p, "label": ""} for p in r["photos"]]
            room_ids.add(r["id"])
        for i in data["items"]:
            if not isinstance(i, dict) or not i.get("id") or i.get("room") not in room_ids:
                raise ApiError(400, "Arquivo inválido: item sem id ou com cômodo desconhecido.")
            i.setdefault("photos", [i["photo"]] if i.get("photo") else [])
            i.pop("photo", None)
        return data

    def has_data(self):
        return bool(self.data.get("items") or self.data.get("rooms"))

    def replace_all(self, data: dict):
        data = self.check_inventory(data)
        with self.lock:
            self.snapshot_if_due(force=True)
            rev = int(self.data.get("rev", 0))
            data["rev"] = max(rev, int(data.get("rev") or 0))
            data.setdefault("format", "inventario-casa")
            data.setdefault("schema", 1)
            self.data = data
            self._normalize_order()
            self.save()


STORE = Store()


# ---------------------------------------------------------------------------
# Exportação e backups


def export_csv_bytes() -> bytes:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(["Código", "Cômodo", "Zona", "Item", "Detalhes", "Categoria", "Quantidade", "Valor (R$)", "Fotos", "Criado em", "Atualizado em"])
    with STORE.lock:
        for it in STORE.sorted_items():
            room = STORE.room(it["room"]) or {}
            v = it.get("value") or 0
            w.writerow([
                STORE.tag(it), room.get("name", it["room"]), it.get("zone", ""), it.get("name", ""),
                it.get("details", ""), CATS.get(it.get("cat"), "Outros"), it.get("qty", "1"),
                f"{float(v):.2f}".replace(".", ","), ", ".join(it.get("photos") or []),
                it.get("createdAt") or "", it.get("updatedAt") or "",
            ])
    return ("﻿" + out.getvalue()).encode("utf-8")


README_ZIP = """InventarIA: cópia completa do inventário da casa
================================================

inventario.json  cômodos e itens (JSON). Cada item tem room (cômodo), zone (zona), name, details,
                 cat (categoria), qty (quantidade), value (valor total em reais) e photos (arquivos em photos/).
inventario.csv   a mesma lista em planilha (abre no Excel: separador ponto e vírgula, UTF-8).
photos/          fotos em tamanho cheio (JPG).
thumbs/          miniaturas (JPG).

Para restaurar no app do Home Assistant: copie este .zip para a pasta share/inventario
e use Dados e backup > Restaurar.
"""


def write_zip(fileobj) -> None:
    with STORE.lock:
        data = json.dumps(STORE.data, ensure_ascii=False, indent=1).encode("utf-8")
        used = sorted({p for i in STORE.data["items"] for p in i.get("photos") or []} |
                      {p["file"] for r in STORE.data["rooms"] for p in r.get("photos") or []})
    csv_bytes = export_csv_bytes()
    with zipfile.ZipFile(fileobj, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("inventario.json", data)
        z.writestr("inventario.csv", csv_bytes)
        z.writestr("LEIA-ME.txt", README_ZIP)
        for name in used:
            for sub, d in (("photos", PHOTOS_DIR), ("thumbs", THUMBS_DIR)):
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    z.write(p, f"{sub}/{name}", compress_type=zipfile.ZIP_STORED)


def backups_list():
    try:
        names = [n for n in os.listdir(SHARE_DIR) if BACKUP_NAME.fullmatch(n)]
    except FileNotFoundError:
        return []
    out = []
    for n in names:
        p = os.path.join(SHARE_DIR, n)
        out.append({"name": n, "size": os.path.getsize(p),
                    "date": datetime.fromtimestamp(os.path.getmtime(p)).astimezone().isoformat(timespec="seconds")})
    return sorted(out, key=lambda b: b["date"], reverse=True)


def create_backup(prefix="inventario") -> dict:
    if not share_available():
        raise ApiError(500, "A pasta share não está disponível para o app.")
    os.makedirs(SHARE_DIR, exist_ok=True)
    name = f"{prefix}-{stamp()}.zip"
    n = 2
    while os.path.exists(os.path.join(SHARE_DIR, name)):
        name = f"{prefix}-{stamp()}-{n}.zip"
        n += 1
    tmp = os.path.join(SHARE_DIR, f".{name}.tmp")
    with open(tmp, "wb") as f:
        write_zip(f)
    os.replace(tmp, os.path.join(SHARE_DIR, name))
    return next(b for b in backups_list() if b["name"] == name)


def share_available() -> bool:
    return os.path.isdir(os.path.dirname(SHARE_DIR.rstrip("/")))


def safety_backup(prefix):
    """Antes de trocar o inventário, guarda uma cópia do atual (se houver o que guardar)."""
    with STORE.lock:
        STORE.snapshot_if_due(force=True)
        has = STORE.has_data()
    if has and share_available():
        return create_backup(prefix)
    return None


def restore_zip(path: str, prefix: str):
    """Restaura um .zip de backup: inventario.json (em qualquer pasta do zip) + photos/ + thumbs/."""
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ApiError(400, "O arquivo não é um .zip válido.")
    with z:
        cands = sorted((n for n in z.namelist() if n.split("/")[-1] == "inventario.json" and "__MACOSX" not in n),
                       key=lambda n: n.count("/"))
        if not cands:
            raise ApiError(400, "O .zip não tem o arquivo inventario.json. Use um backup criado pelo app.")
        root = cands[0][: -len("inventario.json")]
        try:
            data = STORE.check_inventory(json.loads(z.read(cands[0]).decode("utf-8")))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "O inventario.json de dentro do .zip está corrompido.")
        safety = safety_backup(prefix)
        total = 0
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(root):
                continue
            parts = info.filename[len(root):].split("/")
            if len(parts) != 2 or parts[0] not in ("photos", "thumbs") or not SAFE_FILE.fullmatch(parts[1]):
                continue
            if info.file_size > 60 * 1024 * 1024:
                continue
            total += info.file_size
            if total > 8 * 1024 ** 3:
                raise ApiError(400, "O .zip é grande demais para restaurar.")
            dst = os.path.join(DATA_DIR, parts[0], parts[1])
            if not os.path.exists(dst):
                with z.open(info) as src, open(dst + ".tmp", "wb") as out:
                    shutil.copyfileobj(src, out)
                os.replace(dst + ".tmp", dst)
    STORE.replace_all(data)
    return safety


def restore_backup(name: str):
    if not BACKUP_NAME.fullmatch(name or ""):
        raise ApiError(400, "Nome de backup inválido.")
    path = os.path.join(SHARE_DIR, name)
    if not os.path.isfile(path):
        raise ApiError(404, "Backup não encontrado na pasta share/inventario.")
    return restore_zip(path, "antes-de-restaurar")


# -- envio de arquivos grandes em partes (o Ingress do Home Assistant limita cada pedido a 16 MB)
UPLOAD_ID = re.compile(r"[a-f0-9]{16}")
UPLOAD_CHUNK = 4 * 1024 * 1024
UPLOAD_MAX = 4 * 1024 ** 3


def upload_paths(uid: str):
    if not UPLOAD_ID.fullmatch(uid or ""):
        raise ApiError(404, "Envio não encontrado.")
    base = os.path.join(TMP_DIR, f"upload-{uid}")
    return base + ".part", base + ".json"


def upload_meta(uid: str):
    part, meta = upload_paths(uid)
    m = read_json(meta)
    if m is None or not os.path.exists(part):
        raise ApiError(404, "Este envio expirou. Comece de novo.")
    return part, meta, m


def cleanup_uploads(max_age=24 * 3600):
    try:
        for n in os.listdir(TMP_DIR):
            p = os.path.join(TMP_DIR, n)
            if n.startswith("upload-") and time.time() - os.path.getmtime(p) > max_age:
                os.unlink(p)
    except OSError:
        pass


def drop_upload(uid: str):
    for p in upload_paths(uid):
        try:
            os.unlink(p)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# IA (ação ai_task.generate_data do Home Assistant)


def ha_request(method: str, path: str, body=None, timeout=20):
    if not SUPERVISOR_TOKEN:
        raise ApiError(503, "O app não tem acesso à API do Home Assistant.")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(HA_API + path, data=data, method=method, headers={
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        try:
            detail = json.loads(detail).get("message", detail)
        except (ValueError, AttributeError):
            pass
        raise ApiError(502, f"O Home Assistant recusou o pedido: {detail}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise ApiError(504, f"Sem resposta do Home Assistant ({e}).")


def ai_entities():
    if AI_MOCK:
        return [{"id": "ai_task.simulado", "name": "IA simulada (teste)", "attachments": True}]
    states = ha_request("GET", "/states") or []
    out = []
    for s in states:
        eid = s.get("entity_id", "")
        if eid.startswith("ai_task."):
            attrs = s.get("attributes") or {}
            feats = int(attrs.get("supported_features") or 0)
            out.append({"id": eid, "name": attrs.get("friendly_name") or eid,
                        "attachments": bool(feats & 2), "state": s.get("state")})
    return sorted(out, key=lambda e: (not e["attachments"], e["name"].lower()))


def ai_status():
    if not SUPERVISOR_TOKEN and not AI_MOCK:
        return {"ready": False, "reason": "no_api", "entities": [], "selected": ""}
    try:
        ents = ai_entities()
    except ApiError as e:
        return {"ready": False, "reason": "error", "message": e.msg, "entities": [], "selected": ""}
    sel = STORE.settings.get("ai_entity") or ""
    usable = [e for e in ents if e["attachments"]]
    ready = bool(usable) if not sel else any(e["id"] == sel and e["attachments"] for e in ents)
    return {"ready": ready, "reason": None if ready else ("no_entity" if not ents else "no_vision"),
            "entities": ents, "selected": sel}


AI_RULES = """Para cada item, devolva:
- "name": nome curto em português, com marca e modelo quando estiverem legíveis ou forem claramente reconhecíveis (ex.: "Liquidificador Philips Walita 1400 W").
- "details": 1 ou 2 frases objetivas sobre o que é, cor, material, tamanho e estado. Sem preço. Nunca inclua número de série, IMEI, telefone, nome de pessoa ou endereço.
- "cat": uma destas chaves: {cats}.
- "qty": quantidade como texto ("1", "2", "1 par", "1 conj.").
- "value": valor TOTAL estimado em reais (número, sem símbolo), pensando no mercado de usados no Brasil (anúncios da OLX), um pouco abaixo da mediana dos anúncios de usados. Se a quantidade for maior que 1, some todas as unidades.
- "zone": onde o item fica dentro do cômodo, curto (ex.: "Estante", "Bancada", "Rack da TV"). Eletrônicos e aparelhos de saúde usam "Eletrônicos". Use "" se não der para saber.
- "existing": se o item já estiver na lista de itens cadastrados abaixo, o nome exato dele; senão "".
- "confidence": "alta", "media" ou "baixa".
Responda somente com JSON válido, sem markdown e sem texto antes ou depois, neste formato:
{{"items":[{{"name":"","details":"","cat":"","qty":"1","value":0,"zone":"","existing":"","confidence":"media"}}]}}"""


def ai_prompt(mode: str, room: dict | None, hint: str) -> str:
    cats = ", ".join(f"{k} ({v})" for k, v in CATS.items())
    parts = ["Você ajuda a catalogar o inventário de uma casa no Brasil, para controle de patrimônio e seguro."]
    if mode == "single":
        parts.append("A foto mostra um item para cadastrar. Identifique só o objeto principal (o mais em destaque) e devolva exatamente 1 item.")
    else:
        parts.append("Liste cada objeto da foto que valha a pena catalogar, até 25. Ignore paredes, piso, tomadas, interruptores, "
                     "embalagens vazias, objetos cortados na borda que não dê para identificar e coisas sem valor de revenda. "
                     "Junte objetos iguais num item só, com a quantidade.")
    parts.append(AI_RULES.format(cats=cats))
    if room:
        with STORE.lock:
            its = [i for i in STORE.data["items"] if i["room"] == room["id"]]
            zones = sorted({i.get("zone") for i in its if i.get("zone")})
            names = [i["name"] for i in sorted(its, key=lambda i: -(i.get("value") or 0))][:150]
        parts.append(f"Cômodo: {room['name']}.")
        if zones:
            parts.append("Zonas já usadas neste cômodo (prefira uma delas): " + "; ".join(zones) + ".")
        if names and mode != "single":
            parts.append("Itens já cadastrados neste cômodo: " + "; ".join(names) + ".")
    if hint:
        parts.append(f"Dica de quem está cadastrando: {hint}")
    return "\n\n".join(parts)


def extract_json(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    s = str(raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I | re.S).strip()
    try:
        return json.loads(s)
    except ValueError:
        pass
    start = min([p for p in (s.find("{"), s.find("[")) if p >= 0] or [-1])
    if start < 0:
        raise ApiError(502, "A IA respondeu sem uma lista de itens. Tente de novo ou use uma dica.", raw=s[:2000])
    for end in range(len(s), start, -1):
        if s[end - 1] in "}]":
            try:
                return json.loads(s[start:end])
            except ValueError:
                continue
    raise ApiError(502, "Não deu para entender a resposta da IA. Tente de novo.", raw=s[:2000])


def clean_ai_items(parsed, room: dict | None) -> list[dict]:
    items = parsed.get("items") if isinstance(parsed, dict) else parsed
    if isinstance(parsed, dict) and items is None and parsed.get("name"):
        items = [parsed]
    if not isinstance(items, list):
        raise ApiError(502, "A IA não devolveu itens. Tente de novo.")
    names = set()
    if room:
        with STORE.lock:
            names = {i["name"] for i in STORE.data["items"] if i["room"] == room["id"]}
    out = []
    for raw in items[:25]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()[:200]
        if not name:
            continue
        try:
            value = parse_value(raw.get("value"))
        except ApiError:
            value = 0
        conf = str(raw.get("confidence") or "").lower().replace("é", "e")
        existing = str(raw.get("existing") or "").strip()
        out.append({
            "name": name, "details": str(raw.get("details") or "").strip()[:1000],
            "cat": raw.get("cat") if raw.get("cat") in CATS else "outros",
            "qty": str(raw.get("qty") or "1").strip()[:30] or "1", "value": value,
            "zone": str(raw.get("zone") or "").strip()[:120],
            "existing": existing if existing in names else "",
            "confidence": conf if conf in ("alta", "media", "baixa") else "media",
        })
    return out


MOCK_RESULT = {"items": [
    {"name": "Luminária de mesa articulada preta", "details": "Luminária de braço articulado em metal preto com cúpula cônica.",
     "cat": "decoracao", "qty": "1", "value": 90, "zone": "Mesa", "existing": "", "confidence": "alta"},
    {"name": "Caneca de cerâmica branca", "details": "Caneca lisa de cerâmica branca, cerca de 300 ml.",
     "cat": "cozinha", "qty": "2", "value": 30, "zone": "", "existing": "", "confidence": "media"},
    {"name": "Fone de ouvido Bluetooth", "details": "Fone over-ear preto dobrável.",
     "cat": "eletronicos", "qty": "1", "value": 180, "zone": "Eletrônicos", "existing": "", "confidence": "baixa"},
]}


def ai_identify(body: dict) -> dict:
    file = body.get("file") or ""
    if not photo_exists(file):
        raise ApiError(400, "Envie uma foto antes de pedir a leitura por IA.")
    mode = "single" if body.get("mode") == "single" else "multi"
    room = STORE.room(body.get("room")) if body.get("room") else None
    hint = text(body.get("hint"), 300, "dica")
    prompt = ai_prompt(mode, room, hint)
    entity = STORE.settings.get("ai_entity") or ""
    if AI_MOCK:
        time.sleep(1.2)
        res = dict(MOCK_RESULT)
        if mode == "single":
            res = {"items": MOCK_RESULT["items"][:1]}
        return {"items": clean_ai_items(res, room), "entity": "ai_task.simulado"}
    tmp_dir = os.path.join(MEDIA_ROOT, AI_TMP_REL)
    if not os.path.isdir(MEDIA_ROOT):
        raise ApiError(500, "A pasta media não está disponível para o app.")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_name = f"{secrets.token_hex(8)}.jpg"
    tmp_path = os.path.join(tmp_dir, tmp_name)
    shutil.copyfile(os.path.join(PHOTOS_DIR, file), tmp_path)
    try:
        payload = {
            "task_name": "InventarIA: ler foto",
            "instructions": prompt,
            "attachments": [{"media_content_id": f"media-source://media_source/local/{AI_TMP_REL}/{tmp_name}",
                             "media_content_type": "image/jpeg"}],
        }
        if entity:
            payload["entity_id"] = entity
        res = ha_request("POST", "/services/ai_task/generate_data?return_response", payload, timeout=240)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    data = ((res or {}).get("service_response") or {}).get("data")
    if data is None:
        raise ApiError(502, "A IA não devolveu resposta.")
    return {"items": clean_ai_items(extract_json(data), room), "entity": entity or "padrão do Home Assistant"}


# ---------------------------------------------------------------------------
# HTTP


def save_photo(body: dict) -> dict:
    try:
        full = base64.b64decode(body.get("full") or "", validate=True)
        thumb = base64.b64decode(body.get("thumb") or "", validate=True) if body.get("thumb") else None
    except (ValueError, TypeError):
        raise ApiError(400, "Foto inválida.")
    if len(full) < 100 or full[:2] != b"\xff\xd8":
        raise ApiError(400, "Envie a foto em JPG.")
    if thumb is not None and thumb[:2] != b"\xff\xd8":
        thumb = None
    name = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}.jpg"
    for d, content in ((PHOTOS_DIR, full), (THUMBS_DIR, thumb or full)):
        with open(os.path.join(d, name + ".tmp"), "wb") as f:
            f.write(content)
        os.replace(os.path.join(d, name + ".tmp"), os.path.join(d, name))
    return {"file": name}


MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".woff2": "font/woff2", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".json": "application/json; charset=utf-8", ".ico": "image/x-icon", ".webmanifest": "application/manifest+json"}


class Handler(BaseHTTPRequestHandler):
    server_version = f"InventarIA/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if DEV:
            super().log_message(fmt, *args)

    # -- respostas
    def send_bytes(self, status, body: bytes, ctype: str, headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_bytes(status, body, "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    def send_file(self, path, ctype=None, cache="no-cache", download_name=None):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except (FileNotFoundError, IsADirectoryError):
            return self.send_json({"error": "Arquivo não encontrado."}, 404)
        headers = {"Cache-Control": cache}
        if download_name:
            headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        self.send_bytes(200, body, ctype or MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream"), headers)

    # -- entrada
    def user(self):
        return (self.headers.get("X-Remote-User-Display-Name") or self.headers.get("X-Remote-User-Name") or "").strip()[:60] or None

    def read_raw(self, limit=MAX_BODY) -> bytes:
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            out = bytearray()
            while True:
                line = self.rfile.readline(65537)
                try:
                    size = int(line.split(b";")[0].strip() or b"0", 16)
                except ValueError:
                    self.close_connection = True
                    raise ApiError(400, "Pedido inválido.")
                if size == 0:
                    while self.rfile.readline(65537) not in (b"\r\n", b"\n", b""):
                        pass
                    break
                if len(out) + size > limit:
                    self.close_connection = True
                    raise ApiError(413, "Arquivo grande demais.")
                out += self.rfile.read(size)
                self.rfile.readline(65537)
            self._body_read = True
            return bytes(out)
        length = int(self.headers.get("Content-Length") or 0)
        if length > limit:
            self.close_connection = True
            raise ApiError(413, "Arquivo grande demais.")
        raw = self.rfile.read(length) if length else b""
        self._body_read = True
        return raw

    def read_body(self):
        raw = self.read_raw(MAX_BODY)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "Pedido inválido (JSON).")

    def do_GET(self):
        self.dispatch("GET")

    def do_HEAD(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def dispatch(self, method):
        self._body_read = False
        try:
            if not DEV and self.client_address[0] not in ALLOWED_IPS:
                raise ApiError(403, "Abra o InventarIA pelo Home Assistant.")
            url = urlparse(self.path)
            path = unquote(url.path)
            query = parse_qs(url.query)
            for m, rx, fn in ROUTES:
                if m == method:
                    match = rx.fullmatch(path)
                    if match:
                        return fn(self, *match.groups(), query=query)
            if method == "GET":
                return self.static(path)
            raise ApiError(404, "Endereço não encontrado.")
        except ApiError as e:
            self.drain()
            self.send_json({"error": e.msg, **e.extra}, e.status)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as e:  # noqa: BLE001
            log.exception("Erro em %s %s", method, self.path)
            self.drain()
            self.send_json({"error": f"Erro interno: {e}"}, 500)

    def drain(self):
        if not self._body_read and self.command in ("POST", "PUT", "DELETE"):
            if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
                self.close_connection = True
                self._body_read = True
                return
            length = int(self.headers.get("Content-Length") or 0)
            if 0 < length <= MAX_BODY:
                self.rfile.read(length)
            elif length:
                self.close_connection = True
            self._body_read = True

    def static(self, path):
        if path in ("", "/", "/index.html"):
            try:
                with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as f:
                    html = f.read().replace("%%V%%", VERSION)
            except FileNotFoundError:
                raise ApiError(404, "Interface não encontrada.")
            return self.send_bytes(200, html.encode("utf-8"), MIME[".html"], {"Cache-Control": "no-cache"})
        m = re.fullmatch(r"/(photos|thumbs)/([^/]+)", path)
        if m:
            name = m.group(2)
            if not SAFE_FILE.fullmatch(name):
                raise ApiError(404, "Foto não encontrada.")
            p = os.path.join(DATA_DIR, m.group(1), name)
            if m.group(1) == "thumbs" and not os.path.isfile(p):
                p = os.path.join(PHOTOS_DIR, name)
            return self.send_file(p, cache="private, max-age=31536000, immutable")
        rel = os.path.normpath(path.lstrip("/"))
        if rel.startswith("..") or os.path.isabs(rel):
            raise ApiError(404, "Arquivo não encontrado.")
        full = os.path.join(WEB_DIR, rel)
        cache = "public, max-age=31536000, immutable" if rel.startswith("fonts/") else "no-cache"
        return self.send_file(full, cache=cache)


# -- rotas

def r_data(h, query):
    with STORE.lock:
        out = STORE.public()
    out.update({"version": VERSION, "user": h.user(), "settings": {"ai_entity": STORE.settings.get("ai_entity") or ""},
                "features": {"ai": bool(SUPERVISOR_TOKEN) or AI_MOCK, "share": share_available()}})
    h.send_json(out)


def r_rev(h, query):
    h.send_json({"rev": STORE.data.get("rev")})


def r_health(h, query):
    h.send_json({"ok": True, "version": VERSION})


def r_item_create(h, query):
    body = h.read_body()
    restore = bool(body.pop("_restore", False))
    it = STORE.create_items([body], h.user(), restore=restore)[0]
    h.send_json({"item": it, "rev": STORE.data["rev"]}, 201)


def r_items_batch(h, query):
    body = h.read_body()
    bodies = body.get("items") or []
    if not isinstance(bodies, list) or not bodies or len(bodies) > 60:
        raise ApiError(400, "Envie de 1 a 60 itens.")
    created = STORE.create_items(bodies, h.user(), room_photo=body.get("roomPhoto"))
    h.send_json({"items": created, "rev": STORE.data["rev"], "rooms": STORE.data["rooms"]}, 201)


def r_item_update(h, iid, query):
    it = STORE.update_item(iid, h.read_body(), h.user())
    h.send_json({"item": it, "rev": STORE.data["rev"]})


def r_item_delete(h, iid, query):
    h.read_body()
    it = STORE.delete_item(iid)
    h.send_json({"item": it, "rev": STORE.data["rev"]})


def r_room_create(h, query):
    room = STORE.create_room(h.read_body())
    h.send_json({"room": room, "rooms": STORE.data["rooms"], "rev": STORE.data["rev"]}, 201)


def r_room_update(h, rid, query):
    room = STORE.update_room(rid, h.read_body())
    h.send_json({"room": room, "rev": STORE.data["rev"]})


def r_room_delete(h, rid, query):
    h.read_body()
    room = STORE.delete_room(rid)
    h.send_json({"room": room, "rooms": STORE.data["rooms"], "rev": STORE.data["rev"]})


def r_room_photo(h, rid, query):
    room = STORE.add_room_photo(rid, h.read_body())
    h.send_json({"room": room, "rev": STORE.data["rev"]})


def r_rooms_order(h, query):
    rooms = STORE.reorder_rooms(h.read_body().get("ids") or [])
    h.send_json({"rooms": rooms, "rev": STORE.data["rev"]})


def r_photo(h, query):
    h.send_json(save_photo(h.read_body()), 201)


def r_ai_status(h, query):
    h.send_json(ai_status())


def r_ai_identify(h, query):
    h.send_json(ai_identify(h.read_body()))


def r_settings_get(h, query):
    h.send_json(STORE.settings)


def r_settings_put(h, query):
    body = h.read_body()
    with STORE.lock:
        if "ai_entity" in body:
            e = str(body.get("ai_entity") or "")
            if e and not re.fullmatch(r"ai_task\.[a-z0-9_]+", e):
                raise ApiError(400, "Entidade de IA inválida.")
            STORE.settings["ai_entity"] = e
        STORE.save_settings()
    h.send_json(STORE.settings)


def r_export(h, kind, query):
    day = datetime.now().strftime("%Y-%m-%d")
    if kind == "csv":
        body = export_csv_bytes()
        return h.send_bytes(200, body, "text/csv; charset=utf-8",
                            {"Content-Disposition": f'attachment; filename="inventario-{day}.csv"', "Cache-Control": "no-store"})
    if kind == "json":
        with STORE.lock:
            body = json.dumps(STORE.data, ensure_ascii=False, indent=1).encode("utf-8")
        return h.send_bytes(200, body, "application/json; charset=utf-8",
                            {"Content-Disposition": f'attachment; filename="inventario-{day}.json"', "Cache-Control": "no-store"})
    fd, tmp = tempfile.mkstemp(dir=TMP_DIR, suffix=".zip")
    try:
        with os.fdopen(fd, "wb") as f:
            write_zip(f)
        size = os.path.getsize(tmp)
        h.send_response(200)
        h.send_header("Content-Type", "application/zip")
        h.send_header("Content-Length", str(size))
        h.send_header("Content-Disposition", f'attachment; filename="inventario-{day}.zip"')
        h.send_header("Cache-Control", "no-store")
        h.end_headers()
        with open(tmp, "rb") as f:
            shutil.copyfileobj(f, h.wfile, 256 * 1024)
    finally:
        os.unlink(tmp)


def r_backups(h, query):
    h.send_json({"backups": backups_list(), "dir": "share/inventario", "available": share_available()})


def r_backup_create(h, query):
    h.read_body()
    h.send_json({"backup": create_backup(), "backups": backups_list()}, 201)


def r_backup_restore(h, query):
    body = h.read_body()
    safety = restore_backup(body.get("name"))
    h.send_json({"ok": True, "safety": safety, "rev": STORE.data["rev"]})


def r_import(h, query):
    body = h.read_body()
    data = STORE.check_inventory(body.get("data"))
    safety_backup("antes-de-importar")
    STORE.replace_all(data)
    h.send_json({"ok": True, "rev": STORE.data["rev"]})


def r_upload_start(h, query):
    body = h.read_body()
    try:
        size = int(body.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0 or size > UPLOAD_MAX:
        raise ApiError(400, "Tamanho de arquivo inválido.")
    cleanup_uploads()
    uid = secrets.token_hex(8)
    part, meta = upload_paths(uid)
    open(part, "wb").close()
    write_json_atomic(meta, {"name": str(body.get("name") or "")[:200], "size": size, "created": now_iso()})
    h.send_json({"id": uid, "chunk": UPLOAD_CHUNK}, 201)


def r_upload_chunk(h, uid, query):
    part, _, m = upload_meta(uid)
    try:
        offset = int((query.get("offset") or ["0"])[0])
    except ValueError:
        raise ApiError(400, "Posição inválida.")
    data = h.read_raw(UPLOAD_CHUNK * 4)
    cur = os.path.getsize(part)
    if offset < 0 or offset > cur:
        raise ApiError(409, "Parte fora de ordem.", received=cur)
    if offset + len(data) > m["size"]:
        raise ApiError(400, "O arquivo passou do tamanho informado.")
    with open(part, "r+b") as f:
        f.seek(offset)
        f.write(data)
        f.truncate(offset + len(data))
    h.send_json({"received": offset + len(data), "size": m["size"]})


def r_upload_restore(h, uid, query):
    h.read_body()
    part, _, m = upload_meta(uid)
    if os.path.getsize(part) != m["size"]:
        raise ApiError(400, "O envio do arquivo não terminou. Tente de novo.")
    try:
        if zipfile.is_zipfile(part):
            safety = restore_zip(part, "antes-de-importar")
        else:
            try:
                with open(part, encoding="utf-8-sig") as f:
                    data = STORE.check_inventory(json.load(f))
            except (UnicodeDecodeError, ValueError):
                raise ApiError(400, "Use um backup .zip ou um .json exportado pelo app.")
            safety = safety_backup("antes-de-importar")
            STORE.replace_all(data)
    finally:
        drop_upload(uid)
    with STORE.lock:
        h.send_json({"ok": True, "rev": STORE.data["rev"], "items": len(STORE.data["items"]),
                     "rooms": len(STORE.data["rooms"]), "safety": safety})


def r_upload_cancel(h, uid, query):
    h.read_body()
    upload_paths(uid)
    drop_upload(uid)
    h.send_json({"ok": True})


def r_history(h, query):
    h.send_json({"history": STORE.history_list()})


def r_history_restore(h, query):
    name = h.read_body().get("name") or ""
    if not HISTORY_NAME.fullmatch(name):
        raise ApiError(400, "Versão inválida.")
    data = read_json(os.path.join(HISTORY_DIR, name))
    if data is None:
        raise ApiError(404, "Versão não encontrada.")
    STORE.replace_all(data)
    h.send_json({"ok": True, "rev": STORE.data["rev"]})


ROUTES = [(m, re.compile(p), fn) for m, p, fn in [
    ("GET", r"/api/data", r_data),
    ("GET", r"/api/rev", r_rev),
    ("GET", r"/api/health", r_health),
    ("POST", r"/api/items", r_item_create),
    ("POST", r"/api/items/batch", r_items_batch),
    ("PUT", r"/api/items/([A-Za-z0-9_-]+)", r_item_update),
    ("DELETE", r"/api/items/([A-Za-z0-9_-]+)", r_item_delete),
    ("POST", r"/api/rooms", r_room_create),
    ("POST", r"/api/rooms/order", r_rooms_order),
    ("PUT", r"/api/rooms/([A-Za-z0-9_-]+)", r_room_update),
    ("DELETE", r"/api/rooms/([A-Za-z0-9_-]+)", r_room_delete),
    ("POST", r"/api/rooms/([A-Za-z0-9_-]+)/photos", r_room_photo),
    ("POST", r"/api/photos", r_photo),
    ("GET", r"/api/ai/status", r_ai_status),
    ("POST", r"/api/ai/identify", r_ai_identify),
    ("GET", r"/api/settings", r_settings_get),
    ("PUT", r"/api/settings", r_settings_put),
    ("GET", r"/api/export\.(csv|json|zip)", r_export),
    ("GET", r"/api/backups", r_backups),
    ("POST", r"/api/backups", r_backup_create),
    ("POST", r"/api/backups/restore", r_backup_restore),
    ("POST", r"/api/import", r_import),
    ("POST", r"/api/upload", r_upload_start),
    ("PUT", r"/api/upload/([a-f0-9]{16})", r_upload_chunk),
    ("POST", r"/api/upload/([a-f0-9]{16})/restore", r_upload_restore),
    ("DELETE", r"/api/upload/([a-f0-9]{16})", r_upload_cancel),
    ("GET", r"/api/history", r_history),
    ("POST", r"/api/history/restore", r_history_restore),
]]


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    STORE.load()
    cleanup_uploads()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    log.info("InventarIA %s ouvindo na porta %d%s", VERSION, PORT, " (modo dev)" if DEV else "")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
