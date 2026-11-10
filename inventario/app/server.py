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
import hashlib
import hmac
import html
import http.client
import io
import ipaddress
import json
import logging
import os
import re
import secrets
import shutil
import socket
import ssl
import struct
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from html.parser import HTMLParser

import ferramentas
import relatorio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

VERSION = "1.41.0"
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
USAGE_FILE = os.path.join(DATA_DIR, "uso_ia.json")
NEWS_FILE = os.path.join(DATA_DIR, "novidades.json")  # novidades conferidas e a escolha da IA (não entra no inventário)
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
THUMBS_DIR = os.path.join(DATA_DIR, "thumbs")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
TMP_DIR = os.path.join(DATA_DIR, "tmp")
AI_TMP_REL = "inventario/ia-temp"  # relativo a /media (fonte de mídia "local" do HA)

MAX_BODY = 30 * 1024 * 1024
HISTORY_KEEP = 3  # versões anteriores: só as 3 mais recentes
HISTORY_EVERY = 10 * 60  # no máximo uma cópia automática a cada 10 minutos

CATS = {
    "eletronicos": "Eletrônicos", "moveis": "Móveis", "decoracao": "Decoração e arte",
    "colecao": "Colecionáveis", "cozinha": "Cozinha e bar", "texteis": "Tapetes e têxteis",
    "plantas": "Plantas", "livros": "Livros e jogos", "pets": "Pets", "saude": "Saúde",
    "vestuario": "Roupas e calçados", "utilidades": "Utilidades", "imoveis": "Imóveis", "veiculos": "Veículos", "outros": "Outros",
}
BENS_CATS = ("imoveis", "veiculos")  # os bens fora de casa (casa, terreno, carro); o resto vai em Outros
SAFE_CAT = re.compile(r"[a-z0-9][a-z0-9_-]{0,40}")
SAFE_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(?:jpe?g|png|webp)")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}")
BACKUP_NAME = re.compile(r"[^/\\\x00-\x1f.][^/\\\x00-\x1f]{0,150}\.zip", re.I)  # "inventario (1).zip", "- Cópia.zip"; sem barra nem ponto no começo
HISTORY_NAME = re.compile(r"inventario-\d{8}-\d{6}\.json")
HISTORY_REASONS = "motivos.json"  # dentro de history/: por que cada cópia foi feita (antes de importar, antes de restaurar)

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


def room_code(wanted) -> str:
    """Código do cômodo: letras sem acento e números, de 1 a 4."""
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", str(wanted or "")).encode("ascii", "ignore").decode().upper())[:4]


def free_code(wanted, used: set) -> str:
    """Um código que ainda não é usado, nunca maior que 4: SAL, SAL2… SA10."""
    base = room_code(wanted) or "CMD"
    if base not in used:
        return base
    for n in range(2, 1000):
        c = f"{base[:4 - len(str(n))]}{n}"
        if c not in used:
            return c
    return secrets.token_hex(2).upper()


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def read_json_ok(path, default=None):
    """Como read_json, mas um arquivo ilegível vale o padrão (para arquivos de apoio, que se refazem sozinhos)."""
    try:
        return read_json(path, default)
    except (ValueError, OSError):
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


def default_cats() -> list[dict]:
    return [{"id": k, "name": v} for k, v in CATS.items()]


def clean_cats(raw) -> list[dict] | None:
    """Categorias da casa (editáveis em Mais > Categorias), na ordem. "outros" sempre existe: é para onde vão os itens."""
    out, seen = [], set()
    for c in raw if isinstance(raw, list) else []:
        if isinstance(c, dict):
            cid, name = str(c.get("id") or ""), " ".join(str(c.get("name") or "").split())[:60]
            if SAFE_CAT.fullmatch(cid) and name and cid not in seen:
                out.append({"id": cid, "name": name})
                seen.add(cid)
    if not out:
        return None
    if "outros" not in seen:
        out.append({"id": "outros", "name": "Outros"})
    return out


def fold(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower().strip()


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
            elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):  # "1.200" é mil e duzentos, como na tela (não 1,2)
                s = s.replace(".", "")
            x = float(s)
    except OverflowError:
        raise ApiError(400, "Valor fora do intervalo permitido.")
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


def clean_photo_src(v, photos: list[str]) -> dict:
    """De onde veio cada foto tirada da internet: {foto: endereço da página}. Só fotos que o item ainda tem."""
    if not isinstance(v, dict):
        return {}
    return {k: u for k, u in v.items()
            if k in photos and isinstance(u, str) and u.startswith(("https://", "http://")) and len(u) <= 1000}


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
        try:
            self.data = read_json(DATA_FILE) or {}
            if not isinstance(self.data, dict):
                raise ValueError("não é um inventário")
        except (ValueError, OSError) as e:
            self.data = self.recover(e)
        self.data.setdefault("format", "inventario-casa")
        self.data.setdefault("schema", 1)
        self.data.setdefault("rev", 1)
        self.data.setdefault("rooms", [])
        self.data.setdefault("items", [])
        try:
            self.settings = read_json(SETTINGS_FILE, {}) or {}
            if not isinstance(self.settings, dict):
                raise ValueError
        except (ValueError, OSError):
            log.warning("settings.json ilegível: valem as opções padrão")
            self.settings = {}
        self.prune_history()  # quem vinha de uma versão que guardava mais cópias fica só com as últimas
        snaps = self.history_list()
        if snaps:
            self.last_snapshot = os.path.getmtime(os.path.join(HISTORY_DIR, snaps[0]["name"]))
        log.info("InventarIA: inventário carregado com %d cômodos e %d itens", len(self.data["rooms"]), len(self.data["items"]))

    def recover(self, err) -> dict:
        """inventario.json ilegível (disco cheio, desligou no meio): guarda o arquivo e volta para a última versão anterior boa."""
        keep = f"{DATA_FILE}.corrompido-{stamp()}"
        try:
            os.replace(DATA_FILE, keep)
        except OSError:
            keep = ""
        log.error("inventario.json ilegível (%s); guardado em %s", err, keep or "(não deu para guardar)")
        for snap in self.history_list(details=False):
            try:
                data = read_json(os.path.join(HISTORY_DIR, snap["name"]))
            except (ValueError, OSError):
                continue
            if isinstance(data, dict) and isinstance(data.get("rooms"), list) and isinstance(data.get("items"), list):
                log.warning("inventário de volta à versão %s", snap["name"])
                write_json_atomic(DATA_FILE, data)
                return data
        return {}

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
    def snapshot_if_due(self, force=False, reason="auto"):
        if not os.path.exists(DATA_FILE):
            return
        now = time.time()
        if not force and now - self.last_snapshot < HISTORY_EVERY:
            return
        if force and now - self.last_snapshot < 5 and os.path.getmtime(DATA_FILE) <= self.last_snapshot:
            return  # a cópia de agora há pouco já tem tudo (ex.: o backup de segurança logo antes de importar)
        name = f"inventario-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        tmp = os.path.join(HISTORY_DIR, f".{name}.tmp")
        shutil.copyfile(DATA_FILE, tmp)  # copia e só depois dá o nome: desligar no meio não deixa uma versão cortada
        os.replace(tmp, os.path.join(HISTORY_DIR, name))
        self.last_snapshot = now
        if reason != "auto":
            reasons = read_json(os.path.join(HISTORY_DIR, HISTORY_REASONS), {}) or {}
            reasons[name] = reason
            write_json_atomic(os.path.join(HISTORY_DIR, HISTORY_REASONS), reasons)
        self.prune_history()

    def prune_history(self):
        for old in self.history_list(details=False)[HISTORY_KEEP:]:
            try:
                os.unlink(os.path.join(HISTORY_DIR, old["name"]))
            except OSError:
                pass
        path = os.path.join(HISTORY_DIR, HISTORY_REASONS)
        reasons = read_json_ok(path, {}) or {}
        keep = {k: v for k, v in reasons.items() if os.path.exists(os.path.join(HISTORY_DIR, k))}
        if keep != reasons:
            write_json_atomic(path, keep)

    def history_list(self, details=True):
        try:
            names = [n for n in os.listdir(HISTORY_DIR) if HISTORY_NAME.fullmatch(n)]
        except FileNotFoundError:
            return []
        reasons = (read_json_ok(os.path.join(HISTORY_DIR, HISTORY_REASONS), {}) or {}) if details else {}
        out = []
        for n in sorted(names, reverse=True):
            p = os.path.join(HISTORY_DIR, n)
            info = {"name": n, "size": os.path.getsize(p), "date": datetime.fromtimestamp(os.path.getmtime(p)).astimezone().isoformat(timespec="seconds")}
            if details:  # só as 3 últimas existem: dá para abrir cada uma e contar
                try:
                    snap = read_json(p, {}) or {}
                except (ValueError, OSError):
                    snap = None  # cópia cortada: aparece na lista, sem a contagem
                ok = isinstance(snap, dict)
                info.update(items=len(snap.get("items") or []) if ok else None, rooms=len(snap.get("rooms") or []) if ok else None,
                            reason=reasons.get(n, "auto"))
            out.append(info)
        return out

    # -- consultas
    def room(self, rid):
        return next((r for r in self.data["rooms"] if r["id"] == rid), None)

    def item(self, iid):
        return next((i for i in self.data["items"] if i["id"] == iid), None)

    def next_seq(self, rid):
        """O próximo número do cômodo. Um número que já foi usado não volta (o ResolvIA liga tarefas pelo id do item)."""
        room = self.room(rid) or {}
        return max([i.get("seq") or 0 for i in self.data["items"] if i["room"] == rid] + [int(room.get("lastSeq") or 0)]) + 1

    def _retire_seq(self, it):
        room = self.room(it.get("room"))
        if room and isinstance(it.get("seq"), int):
            room["lastSeq"] = max(int(room.get("lastSeq") or 0), it["seq"])

    def sorted_items(self):
        order = {r["id"]: r.get("order", 99) for r in self.data["rooms"]}
        return sorted(self.data["items"], key=lambda i: (order.get(i["room"], 99), i.get("seq") or 0))

    def tag(self, it):
        r = self.room(it["room"])
        return f"{(r or {}).get('code') or 'ITM'}-{int(it.get('seq') or 0):03d}"

    def public(self):
        return {
            "rev": self.data["rev"], "updatedAt": self.data.get("updatedAt"),
            "rooms": self.data["rooms"], "items": self.data["items"], "cats": self.cats(),
        }

    # -- categorias: a lista padrão até alguém editar; editada, fica no inventário (entra no backup e nas versões)
    def cats(self) -> list[dict]:
        cs = clean_cats(self.data.get("cats")) or default_cats()
        if not any(c["id"] == "eletronicos" for c in cs):  # a das novidades sempre existe (uma lista antiga pode não ter)
            cs.insert(0, {"id": "eletronicos", "name": CATS["eletronicos"]})
        return cs

    def cat_map(self) -> dict:
        return {c["id"]: c["name"] for c in self.cats()}

    def _cat_name(self, body: dict, skip: str = "") -> str:
        name = " ".join(text(body.get("name"), 60, "nome da categoria", required=True).split())
        if any(fold(c["name"]) == fold(name) and c["id"] != skip for c in self.cats()):
            raise ApiError(400, f"Já existe a categoria {name}.")
        return name

    def create_cat(self, body: dict) -> dict:
        with self.lock:
            name = self._cat_name(body)
            cats = self.cats()
            base = re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")[:36] or "categoria"
            cid, n = base, 2
            while any(c["id"] == cid for c in cats):
                cid, n = f"{base}-{n}", n + 1
            cat = {"id": cid, "name": name}
            cats.insert(next((i for i, c in enumerate(cats) if c["id"] == "outros"), len(cats)), cat)  # Outros fica no fim
            self.data["cats"] = cats
            self.save()
            return cat

    def update_cat(self, cid: str, body: dict) -> dict:
        with self.lock:
            if cid == "eletronicos":
                raise ApiError(400, "Eletrônicos é a categoria das novidades: não dá para renomear.")
            cats = self.cats()
            cat = next((c for c in cats if c["id"] == cid), None)
            if not cat:
                raise ApiError(404, "Esta categoria não existe mais.")
            cat["name"] = self._cat_name(body, skip=cid)
            self.data["cats"] = cats
            self.save()
            return cat

    def delete_cat(self, cid: str) -> int:
        """Exclui a categoria; os itens dela vão para Outros. Devolve quantos itens mudaram."""
        with self.lock:
            if cid == "outros":
                raise ApiError(400, "A categoria Outros não pode ser excluída.")
            if cid == "eletronicos":
                raise ApiError(400, "Eletrônicos é a categoria das novidades: não dá para excluir.")
            cats = self.cats()
            if not any(c["id"] == cid for c in cats):
                raise ApiError(404, "Esta categoria não existe mais.")
            moved, t = 0, now_iso()
            for it in self.data["items"]:
                if it.get("cat") == cid:
                    it["cat"], it["updatedAt"] = "outros", t
                    moved += 1
            self.data["cats"] = [c for c in cats if c["id"] != cid]
            self.save()
            return moved

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
            "cat": body.get("cat") if body.get("cat") in self.cat_map() else "outros",
            "qty": text(body.get("qty") or "1", 30, "quantidade") or "1",
            "value": parse_value(body.get("value")),
            "photos": clean_photos(body.get("photos")),
            "checked": bool(body.get("checked")), "flag": text(body.get("flag"), 200, "observação") or None,
            "approx": True, "source": text(body.get("source") or "manual", 40, "origem"),
            "createdAt": ts, "updatedAt": ts, "valueAt": ts,
        }
        src = clean_photo_src(body.get("photoSrc"), it["photos"])
        if src:
            it["photoSrc"] = src
        if user:
            it["createdBy"] = it["updatedBy"] = user
        want_id = body.get("id") if restore else None
        want_seq = body.get("seq") if restore else None
        if restore:
            for k in ("createdAt", "createdBy", "updatedAt", "updatedBy", "valueAt", "approx", "checkedAt"):  # Desfazer volta o item como era
                if body.get(k) is not None:
                    it[k] = body[k]
            if not body.get("valueAt"):
                it["valueAt"] = it["createdAt"]  # item de antes da data do valor: vale a de criação, como para os outros apps
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
            try:
                for b in bodies:
                    if not isinstance(b, dict):
                        raise ApiError(400, "Item inválido.")
                    it = self.build_item(b, user, restore=restore)
                    self.data["items"].append(it)  # já na lista: o próximo do lote não repete o número
                    created.append(it)
                if room_photo:
                    self._add_room_photo(room_photo.get("room"), room_photo.get("file"), room_photo.get("label"))
            except Exception:
                for it in created:  # um item ruim (ou a foto do cômodo) desfaz o lote inteiro, também na memória
                    self.data["items"].remove(it)
                raise
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
                want = body.get("seq")  # Desfazer o Mover: volta com o número de antes, se ninguém o usa
                used = {i.get("seq") for i in self.data["items"] if i["room"] == room["id"]}
                new["seq"] = want if isinstance(want, int) and not isinstance(want, bool) and want > 0 and want not in used else self.next_seq(room["id"])
            if "zone" in body:
                new["zone"] = text(body["zone"], 120, "zona")
            if "name" in body:
                new["name"] = text(body["name"], 200, "nome", required=True)
            if "details" in body:
                new["details"] = text(body["details"], 4000, "detalhes")
            if "cat" in body:
                new["cat"] = body["cat"] if body["cat"] in self.cat_map() else "outros"
            if "qty" in body:
                new["qty"] = text(body["qty"] or "1", 30, "quantidade") or "1"
            if "value" in body:
                new["value"] = parse_value(body["value"])
                if new["value"] != it.get("value"):
                    new["valueAt"] = now_iso()  # quando o valor mudou (o GerencIA deprecia a partir daqui)
            if "photos" in body:
                new["photos"] = clean_photos(body["photos"])
            if "photos" in body or "photoSrc" in body:
                src = clean_photo_src(body.get("photoSrc", it.get("photoSrc")), new["photos"])
                if src:
                    new["photoSrc"] = src
                else:
                    new.pop("photoSrc", None)
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
            if new["room"] != it["room"]:
                self._retire_seq(it)
            it.clear()
            it.update(new)
            self.save()
            return it

    def update_items(self, changes, user) -> list[dict]:
        """Vários itens de uma vez (Buscar › Selecionar: o cômodo, a categoria ou a zona, e o Desfazer): [{id, room?, seq?,
        zone?, cat?}], cada um com o que muda. Tudo ou nada, gravado uma vez. Em outro cômodo, o item ganha o próximo
        número de lá (ou o seq pedido, no Desfazer, se estiver livre), como no Mover."""
        if not isinstance(changes, list) or not changes:
            raise ApiError(400, "Escolha os itens.")
        if len(changes) > 2000:
            raise ApiError(400, "No máximo 2000 itens de uma vez.")
        with self.lock:
            cats, plan, seen = self.cat_map(), [], set()
            for ch in changes:
                if not isinstance(ch, dict):
                    raise ApiError(400, "Item inválido.")
                it = self.item(ch.get("id"))
                if not it:
                    raise ApiError(404, "Um dos itens não existe mais. Atualize a página.")
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                new = {}
                if "room" in ch and ch["room"] != it["room"]:
                    room = self.room(ch["room"])
                    if not room:
                        raise ApiError(400, "Escolha um cômodo que exista.")
                    new["room"] = room["id"]
                if "cat" in ch:
                    if ch["cat"] not in cats:
                        raise ApiError(400, "Escolha uma categoria que exista.")
                    new["cat"] = ch["cat"]
                if "zone" in ch:
                    new["zone"] = text(ch["zone"], 120, "zona")
                plan.append((it, new, ch.get("seq")))
            t, out = now_iso(), []
            for it, new, want in plan:
                if "room" in new:
                    used = {i.get("seq") for i in self.data["items"] if i["room"] == new["room"]}
                    seq = want if isinstance(want, int) and not isinstance(want, bool) and want > 0 and want not in used else self.next_seq(new["room"])
                    self._retire_seq(it)
                    it["room"], it["seq"] = new["room"], seq
                for k in ("cat", "zone"):
                    if k in new:
                        it[k] = new[k]
                if new:
                    it["updatedAt"] = t
                    if user:
                        it["updatedBy"] = user
                out.append(it)
            self.save()
            return out

    def delete_item(self, iid: str) -> dict:
        with self.lock:
            it = self.item(iid)
            if not it:
                raise ApiError(404, "Este item não existe mais.")
            self.data["items"].remove(it)
            self._retire_seq(it)
            self.save()
            return it

    # -- cômodos
    def _unique_code(self, wanted: str, skip_id=None) -> str:
        return free_code(wanted, {r["code"] for r in self.data["rooms"] if r["id"] != skip_id})

    def bens_room(self) -> dict | None:
        """A área Bens: o que não fica dentro de casa (casa, terreno, carro). É um "cômodo" do sistema, fora da lista de cômodos."""
        return next((r for r in self.data["rooms"] if r.get("kind") == "bens"), None)

    def _ensure_bens(self) -> dict:
        room = self.bens_room()
        if room:
            return room
        ids = {r["id"] for r in self.data["rooms"]}
        rid, n = "bens", 2
        while rid in ids:
            rid, n = f"bens-{n}", n + 1
        room = {"id": rid, "code": self._unique_code("BEN"), "name": "Bens", "kind": "bens",
                "order": max([r.get("order", 0) for r in self.data["rooms"]] or [0]) + 1, "cover": 0, "photos": [], "updatedAt": now_iso()}
        self.data["rooms"].append(room)
        # Imóveis e Veículos na lista de categorias da casa (a lista editada não tinha): só acrescenta, nada muda nos itens
        cats = self.cats()
        missing = [{"id": c, "name": CATS[c]} for c in BENS_CATS if not any(x["id"] == c for x in cats)]
        if missing and self.data.get("cats"):
            at = next((i for i, c in enumerate(cats) if c["id"] == "outros"), len(cats))
            self.data["cats"] = cats[:at] + missing + cats[at:]
        self._normalize_order()
        self.save()
        return room

    def create_room(self, body: dict) -> dict:
        with self.lock:
            if body.get("kind") == "bens":  # a área Bens: criada na primeira vez, depois devolve a mesma
                if not bens_enabled():
                    raise ApiError(409, "Os bens estão desligados. Para usar, ligue em Mais > Configurações > Opções.")
                return self._ensure_bens()
            if body.get("kind"):
                raise ApiError(400, "Tipo de cômodo inválido.")
            name = text(body.get("name"), 60, "nome do cômodo", required=True)
            rid = slug(name)
            ids = {r["id"] for r in self.data["rooms"]}
            n = 2
            while rid in ids:
                rid = f"{slug(name)}-{n}"
                n += 1
            code_in = text(body.get("code"), 4, "código") or name
            geral = self.room("geral")
            house = [r.get("order", 0) for r in self.data["rooms"] if r.get("kind") != "bens"]
            room = {
                "id": rid, "code": self._unique_code(code_in), "name": name,
                # novos cômodos entram no fim da lista, antes de "Geral" (e a área Bens fica sempre depois de todos)
                "order": (geral.get("order", 0) - 0.5) if geral else max(house or [0]) + 1,
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
            upd = {}  # confere tudo antes: um pedido recusado não muda nada
            if "name" in body:
                upd["name"] = text(body["name"], 60, "nome do cômodo", required=True)
            if "code" in body:
                code = room_code(body["code"])
                if not code:
                    raise ApiError(400, "O código precisa ter de 1 a 4 letras ou números.")
                if code != room["code"] and any(r["code"] == code for r in self.data["rooms"] if r["id"] != rid):
                    raise ApiError(400, f"O código {code} já é usado por outro cômodo.")
                upd["code"] = code
            if "photos" in body:
                photos = []
                for p in body["photos"] or []:
                    if not isinstance(p, dict) or not photo_exists(p.get("file", "")):
                        raise ApiError(400, "Uma das fotos do cômodo não foi encontrada.")
                    photos.append({"file": p["file"], "label": text(p.get("label"), 160, "legenda")})
                upd["photos"] = photos
            room.update(upd)
            if "cover" in body:
                c = body["cover"]
                room["cover"] = c if isinstance(c, int) and not isinstance(c, bool) and 0 <= c < max(1, len(room["photos"])) else 0
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
        self.data["rooms"].sort(key=lambda r: (r.get("kind") == "bens", r.get("order", 0)))
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
            if not r.get("code"):
                r["code"] = free_code(str(r["id"])[:3], {x.get("code") for x in data["rooms"] if isinstance(x, dict) and x.get("code")})
            r.setdefault("photos", [])
            r.setdefault("cover", 0)
            r["photos"] = [p if isinstance(p, dict) else {"file": p, "label": ""} for p in r["photos"]]
            room_ids.add(r["id"])
        for i in data["items"]:
            if not isinstance(i, dict) or not i.get("id") or i.get("room") not in room_ids:
                raise ApiError(400, "Arquivo inválido: item sem id ou com cômodo desconhecido.")
            i.setdefault("photos", [i["photo"]] if i.get("photo") else [])
            i.pop("photo", None)
            try:
                i["value"] = parse_value(i.get("value"))  # "1.200,50" num .json feito à mão vira número (planilha e backup contam)
            except ApiError:
                i["value"] = 0
        cats = clean_cats(data.get("cats"))
        if cats:
            data["cats"] = cats
        else:
            data.pop("cats", None)
        return data

    def has_data(self):
        return bool(self.data.get("items") or self.data.get("rooms"))

    def replace_all(self, data: dict, reason="restore"):
        data = self.check_inventory(data)
        with self.lock:
            self.snapshot_if_due(force=True, reason=reason)
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
        cats = STORE.cat_map()
        for it in STORE.sorted_items():
            room = STORE.room(it["room"]) or {}
            try:
                v = float(it.get("value") or 0)
            except (TypeError, ValueError):
                v = 0.0
            w.writerow([
                STORE.tag(it), room.get("name", it["room"]), it.get("zone", ""), it.get("name", ""),
                it.get("details", ""), cats.get(it.get("cat"), cats.get("outros", "Outros")), it.get("qty", "1"),
                f"{v:.2f}".replace(".", ","), ", ".join(it.get("photos") or []),
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
        used = sorted(p for p in {p for i in STORE.data["items"] for p in i.get("photos") or []} |
                      {p.get("file") for r in STORE.data["rooms"] for p in r.get("photos") or [] if isinstance(p, dict)}
                      if isinstance(p, str) and SAFE_FILE.fullmatch(p))  # nada de fora de photos/ (nome vindo de um .json importado)
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
        names = [n for n in os.listdir(SHARE_DIR) if BACKUP_NAME.fullmatch(n) and os.path.isfile(os.path.join(SHARE_DIR, n))]
    except OSError:  # não existe, ou o caminho é um arquivo: sem backups
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
    try:
        with open(tmp, "wb") as f:
            write_zip(f)
        os.replace(tmp, os.path.join(SHARE_DIR, name))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return next(b for b in backups_list() if b["name"] == name)


def share_available() -> bool:
    return os.path.isdir(os.path.dirname(SHARE_DIR.rstrip("/"))) and (not os.path.lexists(SHARE_DIR) or os.path.isdir(SHARE_DIR))


def safety_backup(prefix):
    """Antes de trocar o inventário, guarda uma cópia do atual (se houver o que guardar)."""
    with STORE.lock:
        STORE.snapshot_if_due(force=True, reason="import" if "importar" in prefix else "restore")
        has = STORE.has_data()
    if has and share_available():
        return create_backup(prefix)
    return None


def _media_entries(z: zipfile.ZipFile):
    """Fotos e miniaturas dentro do zip (pastas photos/ e thumbs/, em qualquer nível)."""
    for info in z.infolist():
        if info.is_dir() or "__MACOSX" in info.filename:
            continue
        parts = info.filename.split("/")
        if len(parts) >= 2 and parts[-2] in ("photos", "thumbs") and SAFE_FILE.fullmatch(parts[-1]):
            yield info, parts[-2], parts[-1]


def _zip_inventory(z: zipfile.ZipFile):
    cands = sorted((n for n in z.namelist() if n.split("/")[-1] == "inventario.json" and "__MACOSX" not in n),
                   key=lambda n: n.count("/"))
    if not cands:
        return None
    try:
        return STORE.check_inventory(json.loads(z.read(cands[0]).decode("utf-8-sig")))
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "O inventario.json de dentro do .zip está corrompido.")


def _extract_media(z: zipfile.ZipFile) -> int:
    added, total = 0, 0
    for info, kind, name in _media_entries(z):
        if info.file_size > 60 * 1024 * 1024:
            continue
        total += info.file_size
        if total > 8 * 1024 ** 3:
            raise ApiError(400, "O .zip é grande demais para restaurar.")
        dst = os.path.join(DATA_DIR, kind, name)
        if not os.path.exists(dst):
            try:
                with z.open(info) as src, open(dst + ".tmp", "wb") as out:
                    shutil.copyfileobj(src, out)
            except (zipfile.BadZipFile, zlib.error, EOFError):
                try:
                    os.unlink(dst + ".tmp")
                except OSError:
                    pass
                raise ApiError(400, f"O backup está corrompido: a foto {name} não abre.") from None
            os.replace(dst + ".tmp", dst)
            if kind == "photos":
                added += 1
    return added


def _open_zip(path):
    try:
        return zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ApiError(400, "O arquivo não é um .zip válido.")


def inspect_file(path: str) -> dict:
    """O que tem no arquivo enviado: inventário completo, só fotos (parte de um backup) ou JSON."""
    if zipfile.is_zipfile(path):
        with _open_zip(path) as z:
            data = _zip_inventory(z)
            media = list(_media_entries(z))
            photos = sum(1 for _, kind, _ in media if kind == "photos")
            if data is not None:
                return {"kind": "backup", "hasData": True, "items": len(data["items"]), "rooms": len(data["rooms"]), "photos": photos}
            if media:
                return {"kind": "photos", "hasData": False, "items": 0, "rooms": 0, "photos": photos}
        raise ApiError(400, "Este .zip não tem inventário nem fotos do InventarIA.")
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = STORE.check_inventory(json.load(f))
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "Use um backup .zip ou um .json exportado pelo app.")
    return {"kind": "json", "hasData": True, "items": len(data["items"]), "rooms": len(data["rooms"]), "photos": 0}


def restore_zip(path: str, prefix: str):
    """Restaura um .zip: com inventario.json troca o inventário e traz as fotos; sem ele (parte só de fotos)
    apenas acrescenta as fotos, sem mexer nos itens. Devolve (backup de segurança, fotos novas, trocou dados)."""
    with _open_zip(path) as z:
        data = _zip_inventory(z)
        if data is None:
            if not any(True for _ in _media_entries(z)):
                raise ApiError(400, "Este .zip não tem inventário nem fotos do InventarIA.")
            return None, _extract_media(z), False
        safety = safety_backup(prefix)
        added = _extract_media(z)
    STORE.replace_all(data, "import" if "importar" in prefix else "restore")
    return safety, added, True


def restore_backup(name: str):
    if not BACKUP_NAME.fullmatch(name or ""):
        raise ApiError(400, "Nome de backup inválido.")
    path = os.path.join(SHARE_DIR, name)
    if not os.path.isfile(path):
        raise ApiError(404, "Backup não encontrado na pasta share/inventario.")
    return restore_zip(path, "antes-de-restaurar")[0]


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
        if e.code == 429 or is_quota(detail):
            log.info("cota da IA: %s", " ".join(str(detail).split())[:300])
            raise ApiError(502, QUOTA_MSG)
        raise ApiError(502, f"O Home Assistant recusou o pedido: {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log.info("sem resposta do Home Assistant: %s", e)
        raise ApiError(504, "O Home Assistant não respondeu. Tente de novo em instantes.")


def ai_entities():
    """Tarefas de IA (ai_task.*) e assistentes de conversa (conversation.*) do Home Assistant."""
    if AI_MOCK:
        return ([{"id": "ai_task.simulado", "name": "IA simulada (teste)", "attachments": True}],
                [{"id": "conversation.simulado", "name": "Assistente simulado (teste)"}])
    states = ha_request("GET", "/states") or []
    tasks, agents = [], []
    for s in states:
        eid = s.get("entity_id", "")
        attrs = s.get("attributes") or {}
        if eid.startswith("ai_task."):
            feats = int(attrs.get("supported_features") or 0)
            tasks.append({"id": eid, "name": attrs.get("friendly_name") or eid,
                          "attachments": bool(feats & 2), "state": s.get("state")})
        elif eid.startswith("conversation.") and eid != "conversation.home_assistant":
            agents.append({"id": eid, "name": attrs.get("friendly_name") or eid})
    return (sorted(tasks, key=lambda e: (not e["attachments"], e["name"].lower())),
            sorted(agents, key=lambda e: e["name"].lower()))


# Opções da casa (valem para todos os aparelhos): a IA vem ligada; as zonas, desligadas.
def ai_enabled() -> bool:
    return STORE.settings.get("ai") is not False


def zones_enabled() -> bool:
    return STORE.settings.get("zones") is True


def bens_enabled() -> bool:
    """Bens (o que fica fora de casa): vem ligado. Desligado, os bens somem do app, dos outros apps e da IA, sem apagar."""
    return STORE.settings.get("bens") is not False


def visible_data() -> tuple[list, list]:
    """Os cômodos e os itens que contam: sem a área Bens e os bens dela quando Usar bens está desligado."""
    rooms, items = STORE.data.get("rooms") or [], STORE.data.get("items") or []
    if bens_enabled():
        return rooms, items
    hid = {r["id"] for r in rooms if r.get("kind") == "bens"}
    return [r for r in rooms if r["id"] not in hid], [i for i in items if i.get("room") not in hid]


def sensors_enabled() -> bool:
    """Sensores no Home Assistant: só com a opção ligada (Mais > Configurações > Integrações); vem desligada."""
    return STORE.settings.get("ha_sensors") is True


def need_ai_on():
    if not ai_enabled():
        raise ApiError(409, "A IA está desligada. Para usar, ligue em Mais > Configurações > Integrações.")


# -- Novidades nas Configurações (Opções): ligar e desligar, conferir sozinho de tempos em tempos e avisar no celular
NEWS_EVERY = (0, 7, 15, 30)  # dias; 0 = só quando a pessoa pede
NOTIFY_RE = re.compile(r"mobile_app_[a-z0-9_]+")  # o serviço de um celular (notify.mobile_app_*)
WHO_RE = re.compile(r"todos|person\.[a-z0-9_]+")  # quem recebe o aviso: todos ou uma pessoa do Home Assistant
NEWS_TICK = max(1, int(os.environ.get("INV_NEWS_TICK") or 1800))  # de quanto em quanto tempo o app olha se está na hora (s)


def news_enabled() -> bool:
    return STORE.settings.get("news") is not False


def need_news_on():
    need_ai_on()
    if not news_enabled():
        raise ApiError(409, "As novidades estão desligadas. Para usar, ligue em Mais > Configurações > Opções.")


def news_every() -> int:
    v = STORE.settings.get("news_every")
    return v if v in NEWS_EVERY and not isinstance(v, bool) else 0


def news_notify_target() -> str:
    """Quem recebe o aviso das novidades: "todos", "person.<pessoa>" ou "" (não avisar)."""
    t = str(STORE.settings.get("news_notify") or "")
    return t if WHO_RE.fullmatch(t) else ""


# -- uso da IA: o Home Assistant não devolve tokens nem custo, então o app conta as chamadas (como no EconomIA)
USAGE_LOCK = threading.Lock()
USAGE_DAYS = 120
USAGE_SENSOR = "sensor.inventaria_ia_hoje"
USAGE_KINDS = ("foto", "catalogo", "busca", "fala")  # Preencher com IA, Catalogar itens, Buscar foto na internet, Falar
_usage_sensor = {"day": None, "checked": 0.0}


def usage_day(ts=None) -> str:
    t = time.time() if ts is None else ts
    if os.environ.get("TZ"):
        return time.strftime("%Y-%m-%d", time.localtime(t))
    return time.strftime("%Y-%m-%d", time.gmtime(t - 3 * 3600))  # sem fuso no ambiente: horário de Brasília


QUOTA_MSG = "A cota da IA acabou por agora. Tente de novo mais tarde (a cota grátis do Gemini volta de madrugada)."


def is_quota(msg) -> bool:
    t = str(msg or "").lower()
    return "429" in t or "quota" in t or "resource_exhausted" in t or "rate limit" in t or "cota da ia acabou" in t


def record_usage(kind: str, entity: str, chars_in: int, chars_out: int, images: int, seconds: float, result: str):
    tokens = round((chars_in + chars_out) / 4)  # estimativa: uns 4 caracteres por token, só o texto
    day = usage_day()
    with USAGE_LOCK:
        u = read_json(USAGE_FILE, {}) or {}
        days = u.setdefault("days", {})
        d = days.setdefault(day, {})
        for k, v in (("calls", 1), ("tokens", tokens), ("images", images), ("seconds", round(seconds, 1)),
                     ("errors", 0 if result in ("ok", "cota") else 1), ("quota", 1 if result == "cota" else 0)):
            d[k] = round(d.get(k, 0) + v, 1)
        name = entity or "padrão do Home Assistant"
        for group, key in (("kinds", kind), ("entities", name)):
            g = d.setdefault(group, {})
            g[key] = g.get(key, 0) + 1
        for old in sorted(days)[:-USAGE_DAYS]:
            del days[old]
        recent = u.setdefault("recent", [])
        recent.insert(0, {"at": now_iso(), "kind": kind, "entity": name, "result": result,
                          "seconds": round(seconds, 1), "tokens": tokens, "images": images})
        del recent[40:]
        write_json_atomic(USAGE_FILE, u)
    threading.Thread(target=publish_usage_sensor, daemon=True).start()


class AiCall:
    """Mede uma chamada à IA e registra no uso, com o resultado: ok, cota, formato, sem_busca ou erro."""

    def __init__(self, kind: str, entity: str, prompt: str, images: int = 0):
        self.kind, self.entity, self.chars_in, self.images = kind, entity, len(prompt or ""), images
        self.out, self.result = 0, None

    def answer(self, raw):
        try:
            self.out = len(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
        except (TypeError, ValueError):
            self.out = 0

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, et, ev, tb):
        result = self.result or ("ok" if et is None else "cota" if is_quota(getattr(ev, "msg", ev)) else "erro")
        try:
            record_usage(self.kind, self.entity, self.chars_in, self.out, self.images, time.time() - self.t0, result)
        except Exception:  # noqa: BLE001
            log.exception("uso da IA")
        return False


def usage_summary() -> dict:
    with USAGE_LOCK:
        u = read_json(USAGE_FILE, {}) or {}
    days = u.get("days") or {}
    today = usage_day()
    week = [usage_day(time.time() - i * 86400) for i in range(6, -1, -1)]

    def total(keys):
        t = {"calls": 0, "errors": 0, "quota": 0, "tokens": 0, "images": 0, "seconds": 0, "kinds": {}, "entities": {}}
        for k in keys:
            d = days.get(k) or {}
            for c in ("calls", "errors", "quota", "tokens", "images", "seconds"):
                t[c] = round(t[c] + (d.get(c) or 0), 1)
            for group in ("kinds", "entities"):
                for name, n in (d.get(group) or {}).items():
                    t[group][name] = t[group].get(name, 0) + n
        return t

    return {"today": total([today]), "week": total(week), "month": total([k for k in days if k[:7] == today[:7]]),
            "days": [{"day": k, **{c: (days.get(k) or {}).get(c, 0) for c in ("calls", "errors", "quota")}} for k in week],
            "recent": (u.get("recent") or [])[:12], "since": min(days) if days else None, "sensor": USAGE_SENSOR}


def publish_usage_sensor():
    """Sensor no Home Assistant com as chamadas de hoje, para painel e automação (só com Sensores ligado)."""
    if not SUPERVISOR_TOKEN or AI_MOCK or not sensors_enabled() or not ai_enabled():
        return
    try:
        r = usage_summary()
        h = r["today"]
        ha_request("POST", "/states/" + USAGE_SENSOR, {"state": int(h["calls"]), "attributes": {
            "friendly_name": "InventarIA: chamadas de IA hoje", "icon": "mdi:robot-outline",
            "unit_of_measurement": "chamadas", "state_class": "total_increasing",
            "erros": int(h["errors"]), "cota_excedida": int(h["quota"]), "tokens_texto_estimados": int(h["tokens"]),
            "imagens": int(h["images"]), "por_tipo": h["kinds"], "ultimos_7_dias": int(r["week"]["calls"]),
            "este_mes": int(r["month"]["calls"]), "ultima_chamada": r["recent"][0]["at"] if r["recent"] else None}}, timeout=10)
        _usage_sensor["day"] = usage_day()
    except Exception as e:  # noqa: BLE001
        if _usage_sensor["day"] != usage_day():
            log.info("sensor de uso da IA: %s", getattr(e, "msg", e))
        _usage_sensor["day"] = usage_day()


def remove_usage_sensor():
    """Tira o sensor do Home Assistant (quando a opção é desligada, ou o que uma versão antiga deixou)."""
    if not SUPERVISOR_TOKEN or AI_MOCK:
        return
    try:
        ha_request("DELETE", "/states/" + USAGE_SENSOR, timeout=10)
        log.info("sensor de uso da IA retirado do Home Assistant")
    except ApiError:
        pass  # já não existia
    _usage_sensor["day"] = None


def usage_sensor_loop():
    """Zera o sensor na virada do dia e o devolve quando o Home Assistant reinicia (estados da API não ficam salvos lá)."""
    cleaned = False
    while True:
        time.sleep(60)
        if not SUPERVISOR_TOKEN or AI_MOCK:
            continue
        if not sensors_enabled() or not ai_enabled():
            if not cleaned:  # as versões 1.9 e 1.10 criavam o sensor sem perguntar: tira uma vez
                cleaned = True
                remove_usage_sensor()
            continue
        cleaned = False
        try:
            if _usage_sensor["day"] != usage_day():
                publish_usage_sensor()
            elif time.time() - _usage_sensor["checked"] > 300:
                _usage_sensor["checked"] = time.time()
                try:
                    ha_request("GET", "/states/" + USAGE_SENSOR, timeout=10)
                except ApiError as e:
                    if "404" in e.msg or "not found" in e.msg.lower() or "Entity not found" in e.msg:
                        publish_usage_sensor()
        except Exception:  # noqa: BLE001
            log.exception("sensor de uso da IA")


def ai_status():
    search = STORE.settings.get("ai_search") or ""
    if not SUPERVISOR_TOKEN and not AI_MOCK:
        return {"ready": False, "reason": "no_api", "entities": [], "agents": [], "selected": "", "search": search}
    try:
        ents, agents = ai_entities()
    except ApiError as e:
        return {"ready": False, "reason": "error", "message": e.msg, "entities": [], "agents": [], "selected": "", "search": search}
    sel, missing = STORE.settings.get("ai_entity") or "", ""
    if sel and not any(e["id"] == sel for e in ents):
        missing, sel = sel, ""  # a escolhida saiu do Home Assistant: vale a preferida de lá, como no Falar
    usable = [e for e in ents if e["attachments"]]
    ready = bool(usable) if not sel else any(e["id"] == sel and e["attachments"] for e in ents)
    return {"ready": ready, "reason": None if ready else ("no_entity" if not ents else "no_vision"),
            "entities": ents, "agents": agents, "selected": sel, "missing": missing, "search": search}


def photo_entity() -> str:
    """A IA escolhida para ler fotos e textos; se ela saiu do Home Assistant, vazio (a preferida de lá)."""
    sel = STORE.settings.get("ai_entity") or ""
    if not sel or AI_MOCK or not SUPERVISOR_TOKEN:
        return sel
    try:
        ents, agents = ai_entities()
    except ApiError:
        return sel
    return sel if any(e["id"] == sel for e in ents + agents) else ""


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


def ai_house() -> list[tuple[dict, list[dict]]]:
    """Os cômodos da casa (sem a área Bens, que não é cômodo) e os itens de cada um, do mais caro para o mais barato."""
    with STORE.lock:
        rooms = [r for r in STORE.data["rooms"] if r.get("kind") != "bens"]
        its = list(STORE.data["items"])
    return [(r, sorted((i for i in its if i["room"] == r["id"]), key=lambda i: -(i.get("value") or 0))) for r in rooms]


def ai_room_id(v) -> str:
    """O cômodo que a IA respondeu (o id ou o nome) se for um cômodo da casa, ou "" (a pessoa escolhe na revisão)."""
    v = v.strip() if isinstance(v, str) else ""
    if not v:
        return ""
    with STORE.lock:
        rooms = [r for r in STORE.data["rooms"] if r.get("kind") != "bens"]
    r = next((r for r in rooms if r["id"] == v), None) or next((r for r in rooms if r["name"].casefold() == v.casefold()), None)
    return r["id"] if r else ""


def ai_prompt(mode: str, room: dict | None, hint: str, spoken: str = "") -> str:
    cats = ", ".join(f"{k} ({v})" for k, v in STORE.cat_map().items())
    parts = ["Você ajuda a catalogar o inventário de uma casa no Brasil, para controle de patrimônio e seguro."]
    if mode == "single":
        parts.append("A foto mostra um item para cadastrar. Identifique só o objeto principal (o mais em destaque) e devolva exatamente 1 item.")
    elif mode == "voice":
        parts.append("O texto no fim é o que a pessoa falou, transcrito automaticamente (pode ter palavras trocadas pelo reconhecimento de voz). "
                     "Liste cada objeto que ela citou para cadastrar, até 25, na ordem em que falou. Junte objetos iguais num item só, com a quantidade. "
                     "Corrija nomes, marcas e modelos que a transcrição claramente trocou.")
        parts.append("Valor: se a pessoa disse quanto o item vale ou quanto pagou, use exatamente esse valor (somando as unidades). "
                     "Só estime, como explicado abaixo, quando ela não disse.")
    else:
        parts.append("Liste cada objeto da foto que valha a pena catalogar, até 25. Ignore paredes, piso, tomadas, interruptores, "
                     "embalagens vazias, objetos cortados na borda que não dê para identificar e coisas sem valor de revenda. "
                     "Junte objetos iguais num item só, com a quantidade.")
    rules = AI_RULES.format(cats=cats)
    use_zones = zones_enabled()
    if not use_zones:  # zonas desligadas: a IA nem pergunta onde fica o item
        rules = "\n".join(ln for ln in rules.splitlines() if not ln.startswith('- "zone"')).replace('"zone":"",', "")
    # o cômodo: quem fala pode citar um cômodo para cada item; sem cômodo escolhido, a IA escolhe (a da foto, pelo que ela mostra);
    # se não der para saber, "" e a pessoa escolhe na revisão
    house = ai_house() if mode != "single" else []
    if mode == "voice" and house:
        guess = ('o cômodo onde esse objeto claramente fica (ex.: geladeira na cozinha); "" se não der para saber com segurança' if not room
                 else '""')
        rules = rules.replace('- "existing"', '- "room": o id do cômodo onde o item fica, da lista de cômodos abaixo: o que a pessoa disse '
                              f'para ele (ou para todos); se ela não disse, {guess}.\n- "existing"', 1).replace('"existing":""', '"room":"","existing":""')
    elif mode != "single" and house and not room:
        rules += ('\nResponda também "room", ao lado de "items": o id do cômodo que a foto mostra, da lista de cômodos abaixo, '
                  'se der para reconhecer com segurança pelos móveis e objetos; senão "".')
        rules = rules.replace('{"items":[', '{"room":"","items":[')
    parts.append(rules)
    if room:
        if mode == "voice" and house:
            parts.append("Cômodos da casa (id = nome): " + "; ".join(f"{r['id']} = {r['name']}" for r, _ in house) + ".")
        with STORE.lock:
            its = [i for i in STORE.data["items"] if i["room"] == room["id"]]
            zones = sorted({i.get("zone") for i in its if i.get("zone")})
            names = [i["name"] for i in sorted(its, key=lambda i: -(i.get("value") or 0))][:150]
        parts.append(f"Cômodo: {room['name']}.")
        if zones and use_zones:
            parts.append("Zonas já usadas neste cômodo (prefira uma delas): " + "; ".join(zones) + ".")
        if names and mode != "single":
            parts.append("Itens já cadastrados neste cômodo: " + "; ".join(names) + ".")
    elif house:
        lines = []
        for r, its in house:
            ln = f"- {r['id']} = {r['name']}."
            zones = sorted({i.get("zone") for i in its if i.get("zone")})
            if zones and use_zones:
                ln += " Zonas: " + "; ".join(zones) + "."
            if its:
                ln += " Itens já cadastrados: " + "; ".join(i["name"] for i in its[:60]) + "."
            lines.append(ln)
        parts.append("Cômodos da casa (id = nome):\n" + "\n".join(lines))
    if hint:
        parts.append(f"Dica de quem está cadastrando: {hint}")
    if spoken:
        parts.append(f"O que a pessoa falou:\n{spoken}")
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


def clean_ai_items(parsed, room: dict | None, per_item: bool = False) -> list[dict]:
    """Os itens que a IA devolveu, limpos. "room": o cômodo escolhido; sem ele, o que a IA disse (na fala, um para cada item;
    na foto, o da foto); "" se ninguém soube (a pessoa escolhe na revisão)."""
    items = parsed.get("items") if isinstance(parsed, dict) else parsed
    if isinstance(parsed, dict) and items is None and parsed.get("name"):
        items = [parsed]
    if not isinstance(items, list):
        raise ApiError(502, "A IA não devolveu itens. Tente de novo.")
    fixed = room["id"] if room else ""
    top = ai_room_id(parsed.get("room")) if isinstance(parsed, dict) else ""
    names: dict[str, set] = {}
    with STORE.lock:
        bens = {r["id"] for r in STORE.data["rooms"] if r.get("kind") == "bens"}
        for i in STORE.data["items"]:
            if i["room"] not in bens:
                names.setdefault(i["room"], set()).add(i["name"])
    house = set().union(*names.values()) if names else set()
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
        rid = (ai_room_id(raw.get("room")) or top or fixed) if per_item else (fixed or top)
        out.append({
            "name": name, "details": str(raw.get("details") or "").strip()[:1000],
            "cat": raw.get("cat") if isinstance(raw.get("cat"), str) and raw.get("cat") in STORE.cat_map() else "outros",
            "qty": str(raw.get("qty") or "1").strip()[:30] or "1", "value": value,
            "zone": str(raw.get("zone") or "").strip()[:120], "room": rid,
            "existing": existing if existing in (names.get(rid, set()) if rid else house) else "",
            "confidence": conf if conf in ("alta", "media", "baixa") else "media",
        })
    return out


def common_room(items: list[dict]) -> str:
    """O cômodo de todos os itens, se for um só; senão ""."""
    rooms = {i.get("room") or "" for i in items}
    return rooms.pop() if len(rooms) == 1 else ""


MOCK_RESULT = {"room": "escritorio", "items": [
    {"name": "Luminária de mesa articulada preta", "details": "Luminária de braço articulado em metal preto com cúpula cônica.",
     "cat": "decoracao", "qty": "1", "value": 90, "zone": "Mesa", "existing": "", "confidence": "alta"},
    {"name": "Caneca de cerâmica branca", "details": "Caneca lisa de cerâmica branca, cerca de 300 ml.",
     "cat": "cozinha", "qty": "2", "value": 30, "zone": "", "existing": "", "confidence": "media"},
    {"name": "Fone de ouvido Bluetooth", "details": "Fone over-ear preto dobrável.",
     "cat": "eletronicos", "qty": "1", "value": 180, "zone": "Eletrônicos", "existing": "", "confidence": "baixa"},
]}


def ai_fixed_room(body: dict) -> dict | None:
    """O cômodo que a pessoa escolheu (ou de onde abriu), se for um cômodo da casa; sem ele, a IA escolhe."""
    r = STORE.room(body.get("room")) if isinstance(body.get("room"), str) and body.get("room") else None
    return r if r and r.get("kind") != "bens" else None


def ai_identify(body: dict) -> dict:
    need_ai_on()
    file = body.get("file") or ""
    if not photo_exists(file):
        raise ApiError(400, "Envie uma foto antes de pedir a leitura por IA.")
    mode = "single" if body.get("mode") == "single" else "multi"
    room = ai_fixed_room(body)
    hint = text(body.get("hint"), 300, "dica")
    prompt = ai_prompt(mode, room, hint)
    entity = photo_entity()
    kind = "foto" if mode == "single" else "catalogo"
    if AI_MOCK:
        with AiCall(kind, "ai_task.simulado", prompt, images=1) as call:
            time.sleep(1.2)
            res = dict(MOCK_RESULT)
            if mode == "single":
                res = {"items": MOCK_RESULT["items"][:1]}
            call.answer(res)
        items = clean_ai_items(res, room)
        return {"items": items, "room": common_room(items), "entity": "ai_task.simulado"}
    tmp_dir = os.path.join(MEDIA_ROOT, AI_TMP_REL)
    if not os.path.isdir(MEDIA_ROOT):
        raise ApiError(500, "A pasta media não está disponível para o app.")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_name = f"{secrets.token_hex(8)}.jpg"
    tmp_path = os.path.join(tmp_dir, tmp_name)
    shutil.copyfile(os.path.join(PHOTOS_DIR, file), tmp_path)
    with AiCall(kind, entity, prompt, images=1) as call:
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
            call.result = "formato"
            raise ApiError(502, "A IA não devolveu resposta.")
        call.answer(data)
        try:
            parsed = extract_json(data)
        except ApiError:
            call.result = "formato"
            raise
    items = clean_ai_items(parsed, room)
    return {"items": items, "room": common_room(items), "entity": entity or "padrão do Home Assistant"}


# ---------------------------------------------------------------------------
# Falar (como no ResolvIA e no CronologIA): o áudio do microfone vai para a fala para texto do Home
# Assistant, a do assistente de voz preferido (Configurações > Assistentes de voz; com o Home Assistant
# Cloud já vem pronta), no idioma dele; sem assistente, a primeira entidade stt.*. Depois a IA separa
# os itens do que foi dito. O áudio chega do app como PCM cru, 16 kHz, 16 bits, mono (o mesmo do Assist).

VOICE_RATE = 16000
VOICE_MIN = int(VOICE_RATE * 2 * 0.4)  # menos de 0,4 s: não falou nada
VOICE_MAX = VOICE_RATE * 2 * 125  # pouco mais de 2 minutos
HA_WS = os.environ.get("INV_HA_WS") or re.sub(r"^http", "ws", HA_API).rsplit("/api", 1)[0] + "/websocket"
VOICE_HOWTO = ("Para falar, o Home Assistant precisa de um assistente de voz com fala para texto "
               "(Configurações > Assistentes de voz; com o Home Assistant Cloud ele já vem pronto).")
_voice_cache = {"at": 0.0, "value": None}
MOCK_SPEECH = "Sofá cinza de três lugares, uns dois mil reais. Televisão Samsung de 55 polegadas, três mil. E duas luminárias de chão."
MOCK_VOICE_RESULT = {"room": "", "items": [
    {"name": "Sofá cinza de três lugares", "details": "Sofá de tecido cinza, três lugares.", "cat": "moveis", "qty": "1", "value": 2000,
     "zone": "", "room": "sala", "existing": "", "confidence": "alta"},
    {"name": "Televisão Samsung 55 polegadas", "details": "Smart TV Samsung de 55 polegadas.", "cat": "eletronicos", "qty": "1", "value": 3000,
     "zone": "Eletrônicos", "room": "sala", "existing": "", "confidence": "alta"},
    {"name": "Luminária de chão", "details": "", "cat": "decoracao", "qty": "2", "value": 300, "zone": "", "room": "", "existing": "", "confidence": "media"},
]}


def ha_ws(command: dict, timeout=10.0):
    """Um comando pela API de WebSocket do Home Assistant (a lista dos assistentes de voz só existe por ela)."""
    u = urllib.parse.urlsplit(HA_WS)
    sock = socket.create_connection((u.hostname, u.port or (443 if u.scheme == "wss" else 80)), timeout=timeout)
    try:
        if u.scheme == "wss":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=u.hostname)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall((f"GET {u.path or '/'} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        f = sock.makefile("rb")
        if b" 101" not in f.readline():
            raise ApiError(502, "O Home Assistant recusou a conexão de WebSocket.")
        while f.readline() not in (b"\r\n", b"\n", b""):
            pass

        def send_frame(op: int, data: bytes):
            n, head = len(data), bytearray([0x80 | op])
            if n < 126:
                head.append(0x80 | n)
            elif n < 65536:
                head += bytes([0x80 | 126]) + struct.pack(">H", n)
            else:
                head += bytes([0x80 | 127]) + struct.pack(">Q", n)
            mask = os.urandom(4)
            sock.sendall(bytes(head) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

        def read(n: int) -> bytes:
            data = f.read(n)
            if len(data) < n:
                raise ApiError(502, "O Home Assistant fechou a conexão.")
            return data

        def recv():
            buf = b""
            while True:
                h = read(2)
                op, n = h[0] & 0x0F, h[1] & 0x7F
                if n == 126:
                    n = struct.unpack(">H", read(2))[0]
                elif n == 127:
                    n = struct.unpack(">Q", read(8))[0]
                mask = read(4) if h[1] & 0x80 else None
                data = read(n) if n else b""
                if mask:
                    data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
                if op == 8:
                    raise ApiError(502, "O Home Assistant fechou a conexão.")
                if op == 9:
                    send_frame(10, data)
                    continue
                if op == 10:
                    continue
                buf += data
                if h[0] & 0x80:
                    return json.loads(buf.decode("utf-8"))

        msg = recv()
        if msg.get("type") == "auth_required":
            send_frame(1, json.dumps({"type": "auth", "access_token": SUPERVISOR_TOKEN}).encode())
            msg = recv()
        if msg.get("type") != "auth_ok":
            raise ApiError(502, "O Home Assistant não aceitou a conexão do app.")
        send_frame(1, json.dumps({"id": 1, **command}).encode())
        while True:
            msg = recv()
            if msg.get("id") == 1 and msg.get("type") == "result":
                if not msg.get("success"):
                    raise ApiError(502, ((msg.get("error") or {}).get("message")) or "O Home Assistant recusou o pedido.")
                return msg.get("result")
    finally:
        try:
            sock.close()
        except OSError:
            pass


STT_LEGACY = {"cloud": "Home Assistant Cloud", "stt.home_assistant_cloud": "Home Assistant Cloud"}  # assistentes antigos guardam o provedor, não a entidade


def stt_entities() -> list[dict]:
    """As falas para texto do Home Assistant (entidades stt.*), para escolher em Mais > Configurações > Integrações > Falar."""
    out, states = [], ha_request("GET", "/states")
    for st in states if isinstance(states, list) else []:
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id", ""))
        if eid.startswith("stt."):
            out.append({"id": eid, "name": (st.get("attributes") or {}).get("friendly_name") or eid})
    return sorted(out, key=lambda e: e["name"].lower())


def stt_language(engine: str, fallback: str) -> str:
    """O português que essa fala para texto aceita (pt-BR de preferência), pelo que ela informa ao Home Assistant."""
    try:
        meta = ha_request("GET", f"/stt/{engine}")
        langs = [str(x) for x in (meta.get("languages") if isinstance(meta, dict) else None) or []]
    except ApiError:
        return fallback
    for want in ("pt-BR", "pt_BR", "pt-br"):
        if want in langs:
            return want
    return next((x for x in langs if x.lower().startswith("pt")), fallback)


def voice_engine():
    """{engine, language, name, assistant} da fala para texto a usar, ou None. Fica guardado por um minuto.
    Sem escolha (o padrão), é a do assistente de voz preferido do Home Assistant; com escolha, a entidade stt escolhida."""
    now = time.time()
    if now - _voice_cache["at"] < 60:
        return _voice_cache["value"]
    sel = STORE.settings.get("voice_stt") or ""
    pipe, engines = None, []
    if AI_MOCK:
        pipe = {"engine": "stt.simulado", "language": "pt-BR", "assistant": "Assistente simulado"}
        engines = [{"id": "stt.outra", "name": "Outra fala (teste)"}, {"id": "stt.simulado", "name": "Fala simulada (teste)"}]
    elif SUPERVISOR_TOKEN:
        try:
            r = ha_ws({"type": "assist_pipeline/pipeline/list"}) or {}
            pipes = r.get("pipelines") or []
            p = (next((x for x in pipes if x.get("id") == r.get("preferred_pipeline") and x.get("stt_engine")), None)
                 or next((x for x in pipes if x.get("stt_engine")), None))
            if p:
                pipe = {"engine": p["stt_engine"], "language": p.get("stt_language") or p.get("language") or "pt-BR", "assistant": p.get("name") or ""}
        except (ApiError, OSError, ValueError) as e:
            log.info("assistentes de voz: %s", getattr(e, "msg", e))
        try:
            engines = stt_entities()
        except ApiError as e:
            log.info("fala para texto: %s", e.msg)
    names = {e["id"]: e["name"] for e in engines}
    missing = bool(sel and engines and sel not in names)
    value = None
    if sel and not missing and (engines or pipe):
        lang = pipe["language"] if pipe and pipe["engine"] == sel else stt_language(sel, (pipe or {}).get("language") or "pt-BR")
        value = {"engine": sel, "language": lang, "name": names.get(sel, sel), "assistant": ""}
    elif pipe:
        value = {"engine": pipe["engine"], "language": pipe["language"], "assistant": pipe["assistant"],
                 "name": names.get(pipe["engine"]) or STT_LEGACY.get(pipe["engine"]) or pipe["engine"]}
    elif engines:
        value = {"engine": engines[0]["id"], "language": stt_language(engines[0]["id"], "pt-BR"), "name": engines[0]["name"], "assistant": ""}
    _voice_cache.update(at=now, value=value, engines=engines, missing=missing)
    return value


def voice_status() -> dict:
    e = voice_engine()
    extra = {"engines": _voice_cache.get("engines") or [], "selected": STORE.settings.get("voice_stt") or "",
             "missing": bool(_voice_cache.get("missing"))}
    if not e:
        return {"ready": False, "reason": VOICE_HOWTO, **extra}
    return {"ready": True, "engine": e["engine"], "language": e["language"], "name": e["name"], "assistant": e.get("assistant") or "", **extra}


def voice_text(pcm: bytes) -> dict:
    """PCM cru (16 kHz, 16 bits, mono) para texto, pela fala para texto do Home Assistant."""
    if len(pcm) < VOICE_MIN:
        raise ApiError(422, "Não ouvi nada. Toque no microfone e fale.")
    if len(pcm) > VOICE_MAX:
        raise ApiError(413, "Fale até 2 minutos de cada vez.")
    e = voice_engine()
    if not e:
        raise ApiError(409, VOICE_HOWTO)
    if AI_MOCK:
        time.sleep(0.6)
        return {"text": MOCK_SPEECH, "engine": e["engine"], "name": e["name"]}
    u = urllib.parse.urlsplit(HA_API)
    conn = (http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection)(u.hostname, u.port, timeout=90)
    try:
        # http.client manda o nome do cabeçalho do jeito que está escrito: o proxy do Supervisor só repassa
        # "X-Speech-Content" assim (urllib e fetch() mudam as letras e o Home Assistant responde "Missing X-Speech-Content header")
        conn.putrequest("POST", u.path.rstrip("/") + "/stt/" + urllib.parse.quote(e["engine"]))
        conn.putheader("Authorization", f"Bearer {SUPERVISOR_TOKEN}")
        conn.putheader("Content-Type", "application/octet-stream")
        conn.putheader("X-Speech-Content", f"format=wav; codec=pcm; sample_rate={VOICE_RATE}; bit_rate=16; channel=1; language={e['language']}")
        conn.putheader("Content-Length", str(len(pcm)))
        conn.endheaders()
        conn.send(pcm)
        r = conn.getresponse()
        status, raw = r.status, r.read().decode("utf-8", "replace")
    except (OSError, http.client.HTTPException) as err:
        raise ApiError(504, f"Sem resposta da fala para texto do Home Assistant ({err}).") from None
    finally:
        conn.close()
    if not 200 <= status < 300:
        _voice_cache["at"] = 0.0
        detail = " ".join(raw.split())[:200]
        log.info("fala para texto (%s): %s %s", e["engine"], status, detail)
        raise ApiError(502, f"A fala para texto não aceitou o áudio ({detail or status})." if status in (400, 415)
                       else f"A fala para texto do Home Assistant falhou ({status}{': ' + detail if detail else ''}).")
    try:
        j = json.loads(raw)
    except ValueError:
        j = {}
    said = str(j.get("text") or "").strip()
    if j.get("result") != "success" or not said:
        raise ApiError(422, "Não entendi. Tente de novo, mais perto do microfone.")
    return {"text": said, "engine": e["engine"], "name": e["name"]}


def ai_from_speech(body: dict) -> dict:
    """O que foi dito vira itens: a IA separa nome, detalhes, categoria, quantidade e valor (o dito vale mais que a estimativa)."""
    need_ai_on()
    spoken = text(body.get("text"), 4000, "texto", required=True)
    room = ai_fixed_room(body)
    prompt = ai_prompt("voice", room, "", spoken)
    entity = photo_entity()
    with AiCall("fala", "ai_task.simulado" if AI_MOCK else entity, prompt) as call:
        if AI_MOCK:
            time.sleep(0.8)
            res = MOCK_VOICE_RESULT
        else:
            res = ai_call_text("InventarIA: itens falados", prompt, entity, timeout=180)
            if res is None:
                call.result = "formato"
                raise ApiError(502, "A IA não devolveu resposta.")
        call.answer(res)
        try:
            parsed = extract_json(res)
        except ApiError:
            call.result = "formato"
            raise
    items = clean_ai_items(parsed, room, per_item=True)
    return {"items": items, "room": common_room(items)}


# ---------------------------------------------------------------------------
# Fotos da internet: a IA, com a busca na web, acha páginas do produto (fabricante e lojas); o app lê a
# foto principal de cada página (JSON-LD de produto, og:image), confere se é uma imagem de verdade e de
# bom tamanho e mostra as opções. Só busca em endereços públicos da internet (nada da rede de casa).

WEB_UA = f"Mozilla/5.0 (compatible; InventarIA/{VERSION}; +https://github.com/diegozapella63/inventario-ha)"
WEB_ALLOW_LOCAL = DEV and os.environ.get("INV_WEB_ALLOW_LOCAL") == "1"  # só nos testes locais
WEB_PAGE_MAX = 3 * 1024 * 1024
WEB_IMG_MAX = 8 * 1024 * 1024
WEB_JOB_TTL = 30 * 60
WEB_JOB_ID = re.compile(r"[a-f0-9]{16}")
WEB_JOBS: dict[str, dict] = {}
WEB_LOCK = threading.Lock()
WEB_KINDS = {"jpeg": ("jpg", "image/jpeg"), "png": ("png", "image/png"), "webp": ("webp", "image/webp"), "avif": ("avif", "image/avif")}
SEARCH_HOWTO = ("Na Anthropic, ligue \"Enable web search\" nas opções da tarefa de IA. No Google Gemini, a Pesquisa Google só "
                "funciona num assistente de conversa: ligue \"Enable Google Search tool\" nele e escolha esse assistente em "
                "Mais, Configurações, Integrações, IA para buscar fotos na internet.")


class WebError(Exception):
    pass


class _PinnedHTTP(http.client.HTTPConnection):
    """Conecta no IP já conferido (evita que o nome aponte para outro lugar entre a conferência e a conexão)."""

    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _public_ip(host: str, port: int) -> str:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as e:
        raise WebError("site não encontrado") from e
    addrs = []
    for *_, sa in infos:
        ip = ipaddress.ip_address(str(sa[0]).split("%")[0])
        if not ip.is_global and not WEB_ALLOW_LOCAL:
            raise WebError("endereço fora da internet")
        addrs.append(str(sa[0]))
    if not addrs:
        raise WebError("site não encontrado")
    return addrs[0]


def web_get(url: str, max_bytes: int, accept: str, timeout=12, hops=5):
    """GET de um endereço público, seguindo até 5 redirecionamentos. Devolve (url final, tipo, conteúdo)."""
    for _ in range(hops + 1):
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
            raise WebError("endereço inválido")
        try:
            host = u.hostname.encode("idna").decode("ascii")
            port = u.port or (443 if u.scheme == "https" else 80)
        except (UnicodeError, ValueError) as e:
            raise WebError("endereço inválido") from e
        if port not in (80, 443) and not WEB_ALLOW_LOCAL:
            raise WebError("porta não permitida")
        ip = _public_ip(host, port)
        conn = (_PinnedHTTPS if u.scheme == "https" else _PinnedHTTP)(host, port, ip, timeout)
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        try:
            conn.request("GET", path, headers={"User-Agent": WEB_UA, "Accept": accept, "Accept-Encoding": "gzip",
                                               "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5"})
            r = conn.getresponse()
            if r.status in (301, 302, 303, 307, 308):
                loc = (r.getheader("Location") or "").strip()
                if not loc:
                    raise WebError("redirecionamento sem destino")
                url = urllib.parse.urljoin(url, loc)
                continue
            if r.status != 200:
                raise WebError(f"o site respondeu {r.status}")
            size = r.getheader("Content-Length") or ""
            if size.isdigit() and int(size) > max_bytes:
                raise WebError("arquivo grande demais")
            body = r.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise WebError("arquivo grande demais")
            if (r.getheader("Content-Encoding") or "").lower() == "gzip":
                d = zlib.decompressobj(16 + zlib.MAX_WBITS)
                body = d.decompress(body, max_bytes + 1)
                if len(body) > max_bytes or d.unconsumed_tail:
                    raise WebError("arquivo grande demais")
            ctype = (r.getheader("Content-Type") or "").split(";")[0].strip().lower()
            return url, ctype, body
        except (OSError, http.client.HTTPException, zlib.error) as e:
            raise WebError(f"sem resposta do site ({e.__class__.__name__})") from e
        finally:
            conn.close()
    raise WebError("redirecionamentos demais")


class _PageImages(HTMLParser):
    """Lê as fotos que a página declara: JSON-LD de produto, og:image, twitter:image e image_src."""
    META = {"og:image:secure_url": 1, "og:image": 1, "og:image:url": 1, "twitter:image": 2, "twitter:image:src": 2, "image": 3}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas: list[tuple[int, str]] = []
        self.ld: list[str] = []
        self.title = ""
        self._mode = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key in self.META and a.get("content"):
                self.metas.append((self.META[key], a["content"]))
        elif tag == "link" and "image_src" in a.get("rel", "").lower() and a.get("href"):
            self.metas.append((4, a["href"]))
        elif tag == "script" and "ld+json" in a.get("type", "").lower():
            self._mode, self._buf = "ld", []
        elif tag == "title" and not self.title:
            self._mode, self._buf = "title", []

    def handle_data(self, data):
        if self._mode:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if self._mode == "ld" and tag == "script":
            self.ld.append("".join(self._buf))
            self._mode = None
        elif self._mode == "title" and tag == "title":
            self.title = " ".join("".join(self._buf).split())[:200]
            self._mode = None


def _ld_images(raw: str) -> list[str]:
    try:
        data = json.loads(raw.strip())
    except ValueError:
        return []
    out: list[str] = []

    def walk(o, depth=0):
        if depth > 8 or len(out) >= 8:
            return
        if isinstance(o, list):
            for x in o:
                walk(x, depth + 1)
            return
        if not isinstance(o, dict):
            return
        types = o.get("@type") if isinstance(o.get("@type"), list) else [o.get("@type")]
        if any(str(t).lower() in ("product", "productgroup", "individualproduct", "productmodel") for t in types):
            img = o.get("image")
            for v in img if isinstance(img, list) else [img]:
                if isinstance(v, dict):
                    v = v.get("contentUrl") or v.get("url")
                if isinstance(v, str):
                    out.append(v)
        for k in ("@graph", "mainEntity", "hasVariant", "itemListElement", "item"):
            if k in o:
                walk(o[k], depth + 1)
    walk(data)
    return out


def _fix_url(u, base="") -> str | None:
    if not isinstance(u, str):
        return None
    u = html.unescape(u.strip())
    if u.startswith("//"):
        u = "https:" + u
    if base:
        u = urllib.parse.urljoin(base, u)
    return u if u.startswith(("https://", "http://")) and len(u) <= 1000 and " " not in u else None


def page_images(url: str):
    """Fotos declaradas pela página do produto. Devolve (url final, [fotos])."""
    final, ctype, body = web_get(url, WEB_PAGE_MAX, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5")
    if ctype.startswith("image/"):
        return final, [final]
    p = _PageImages()
    try:
        p.feed(body.decode("utf-8", "replace"))
        p.close()
    except Exception:  # noqa: BLE001  HTML quebrado: fica com o que já leu
        pass
    found = [u for raw in p.ld for u in _ld_images(raw)] + [u for _, u in sorted(p.metas, key=lambda m: m[0])]
    out = []
    for raw in found:
        u = _fix_url(raw, final)
        if u and u not in out:
            out.append(u)
    return final, out[:4]


def image_kind(b: bytes) -> str | None:
    if b[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    if b[4:8] == b"ftyp" and b[8:12] in (b"avif", b"avis"):
        return "avif"
    return None


def image_size(b: bytes, kind: str):
    """Largura e altura lendo só o cabeçalho (JPEG, PNG, WebP e AVIF); None se não der."""
    try:
        if kind == "png":
            return struct.unpack(">II", b[16:24])
        if kind == "webp":
            chunk = b[12:16]
            if chunk == b"VP8 ":
                w, h = struct.unpack("<HH", b[26:30])
                return w & 0x3FFF, h & 0x3FFF
            if chunk == b"VP8L":
                v = int.from_bytes(b[21:25], "little")
                return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
            if chunk == b"VP8X":
                return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
        if kind == "avif":
            i = b.find(b"ispe")
            if i > 0:
                return struct.unpack(">II", b[i + 8:i + 16])
        if kind == "jpeg":
            i = 2
            while i + 9 < len(b):
                if b[i] != 0xFF:
                    i += 1
                    continue
                marker = b[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
                    i += 1 if marker == 0xFF else 2
                    continue
                seg = struct.unpack(">H", b[i + 2:i + 4])[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", b[i + 5:i + 9])
                    return w, h
                i += 2 + seg
    except struct.error:
        pass
    return None


def fetch_image(url: str):
    final, _, body = web_get(url, WEB_IMG_MAX, "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8")
    kind = image_kind(body)
    if not kind:
        raise WebError("não é uma foto")
    size = image_size(body, kind)
    if len(body) < 3000 or (size and min(size) < 200):
        raise WebError("foto pequena demais")
    return final, kind, size, body


def site_of(url: str) -> str:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return re.sub(r"^(www\d?|m)\.", "", host)


def ai_call_text(task_name: str, instructions: str, entity: str, timeout=300):
    """Pergunta à IA escolhida: uma tarefa de IA (ai_task) ou um assistente de conversa (conversation)."""
    if entity.startswith("conversation."):
        res = ha_request("POST", "/services/conversation/process?return_response",
                         {"text": instructions, "agent_id": entity}, timeout=timeout)
        resp = ((res or {}).get("service_response") or {}).get("response") or {}
        speech = (((resp.get("speech") or {}).get("plain") or {}).get("speech")) or ""
        if resp.get("response_type") == "error":
            raise ApiError(502, "O assistente de conversa respondeu com erro: " + " ".join(speech.split())[:160])
        return speech
    payload = {"task_name": task_name, "instructions": instructions}
    if entity:
        payload["entity_id"] = entity
    res = ha_request("POST", "/services/ai_task/generate_data?return_response", payload, timeout=timeout)
    return ((res or {}).get("service_response") or {}).get("data")


def web_prompt(name: str, details: str, qty: str = "1") -> str:
    cats = ", ".join(f"{k} ({v})" for k, v in STORE.cat_map().items())
    return "\n".join(filter(None, [
        "Você ajuda a montar o inventário de uma casa no Brasil e precisa de fotos e dos dados de um item.",
        f"Produto: {name}",
        f"Detalhes: {details}" if details else "",
        f"Quantidade: {qty}" if qty and qty != "1" else "",
        "",
        "Use a busca na web agora. Procure este produto, de preferência o mesmo modelo, no site do fabricante e em lojas grandes "
        "do Brasil (como Mercado Livre, Amazon, Magazine Luiza, Kabum, Casas Bahia, Americanas, Fast Shop e Leroy Merlin). "
        "Se for um item comum, sem marca, procure um produto bem parecido.",
        "Com o que você achou, descreva também o produto para o cadastro:",
        '- "nome": nome curto em português, com marca e modelo (ex.: "Liquidificador Philips Walita 1400 W").',
        '- "detalhes": 1 ou 2 frases objetivas sobre o que é, cor, material, tamanho ou capacidade. Sem preço. '
        "Nunca inclua número de série, IMEI, telefone, nome de pessoa ou endereço.",
        f'- "categoria": uma destas chaves: {cats}.',
        '- "valor": valor TOTAL estimado em reais (número, sem símbolo), pensando no mercado de usados no Brasil (anúncios da OLX), '
        "um pouco abaixo da mediana dos anúncios de usados. Se a quantidade for maior que 1, some todas as unidades.",
        "Responda somente com um objeto JSON, sem texto antes ou depois:",
        '{"produto": {"nome": "", "detalhes": "", "categoria": "", "valor": 0}, '
        '"paginas": [{"url": "endereço da página do produto", "titulo": "título da página"}], '
        '"imagens": ["endereço direto de uma foto do produto (.jpg, .png ou .webp), se você viu algum"]}',
        "Traga de 3 a 6 páginas, de sites diferentes. Use só endereços que apareceram na busca: não invente.",
        'Se não conseguir usar a busca na web, responda apenas {"erro": "sem_busca"}.',
    ]))


def web_product(data: dict) -> dict | None:
    """Os dados do produto que a IA achou na mesma busca das fotos (nome, detalhes, categoria e valor)."""
    p = data.get("produto") or data.get("product")
    if not isinstance(p, dict):
        return None
    name = " ".join(str(p.get("nome") or p.get("name") or "").split())[:200]
    details = str(p.get("detalhes") or p.get("details") or "").strip()[:1000]
    cat = p.get("categoria") or p.get("cat") or ""
    try:
        value = parse_value(p.get("valor", p.get("value")))
    except ApiError:
        value = 0
    if not (name or details):
        return None
    return {"name": name, "details": details, "cat": cat if isinstance(cat, str) and cat in STORE.cat_map() else "", "value": value}


def ai_find_pages(name: str, details: str, entity: str, qty: str = "1") -> dict:
    prompt = web_prompt(name, details, qty)
    with AiCall("busca", "ai_task.simulado" if AI_MOCK else entity, prompt) as call:
        if AI_MOCK:
            time.sleep(0.4)
            data = read_json(os.environ.get("INV_MOCK_SEARCH") or "", {}) or {}
            call.answer(data)
        else:
            raw = ai_call_text("InventarIA: buscar foto", prompt, entity)
            call.answer(str(raw or ""))
            try:
                data = extract_json(raw)
            except ApiError:
                call.result = "sem_busca"
                log.info("busca de fotos: resposta da IA fora do formato: %s", " ".join(str(raw or "").split())[:400])
                raise ApiError(502, "A IA respondeu sem usar a busca na web. " + SEARCH_HOWTO) from None
        if not isinstance(data, dict):
            data = {}
        pages, images = [], []
        for p in data.get("paginas") or data.get("pages") or []:
            u = _fix_url(p.get("url") if isinstance(p, dict) else p)
            if u and u not in pages:
                pages.append(u)
        for p in data.get("imagens") or data.get("images") or []:
            u = _fix_url(p.get("url") if isinstance(p, dict) else p)
            if u and u not in images:
                images.append(u)
        if data.get("erro") or not (pages or images):
            call.result = "sem_busca"
            raise ApiError(502, "A IA não usou a busca na web. " + SEARCH_HOWTO)
    return {"pages": pages[:8], "images": images[:6], "product": web_product(data)}


def search_entity() -> str:
    """IA da busca de fotos; vazio = a tarefa de IA preferida do Home Assistant, como na leitura de fotos."""
    return STORE.settings.get("ai_search") or ""


def _web_job_files(jid: str):
    try:
        return [os.path.join(TMP_DIR, n) for n in os.listdir(TMP_DIR) if n.startswith(f"web-{jid}-")]
    except OSError:
        return []


def web_jobs_cleanup(max_age=WEB_JOB_TTL):
    now = time.time()
    with WEB_LOCK:
        for jid in [j for j, v in WEB_JOBS.items() if now - v["at"] > max_age]:
            WEB_JOBS.pop(jid, None)
    try:
        names = [n for n in os.listdir(TMP_DIR) if n.startswith("web-")]
    except OSError:
        names = []
    for n in names:
        p = os.path.join(TMP_DIR, n)
        try:
            if now - os.path.getmtime(p) > max_age:
                os.unlink(p)
        except OSError:
            pass


def _web_job_run(jid: str, name: str, details: str, entity: str, qty: str = "1"):
    job = WEB_JOBS[jid]
    try:
        found = ai_find_pages(name, details, entity, qty)
        job["product"] = found.get("product")
        if job.get("cancelled"):
            return
        job["msg"] = "Conferindo as fotos das páginas…"
        cands: list[tuple[str, str]] = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = [(p, ex.submit(page_images, p)) for p in found["pages"]]
            for p, f in futs:
                try:
                    final, imgs = f.result()
                    cands += [(u, final) for u in imgs[:2]]
                except WebError as e:
                    log.info("busca de fotos: página %s: %s", site_of(p), e)
        cands += [(u, "") for u in found["images"]]
        seen, uniq = set(), []
        for u, page in cands:
            if u not in seen:
                seen.add(u)
                uniq.append((u, page))
        good, hashes = [], set()
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = [(u, page, ex.submit(fetch_image, u)) for u, page in uniq[:14]]
            for u, page, f in futs:
                try:
                    final, kind, size, body = f.result()
                except WebError as e:
                    log.info("busca de fotos: foto de %s: %s", site_of(u), e)
                    continue
                h = hashlib.sha1(body).hexdigest()
                if h in hashes or len(good) >= 8 or job.get("cancelled"):
                    continue
                hashes.add(h)
                n = len(good)
                with open(os.path.join(TMP_DIR, f"web-{jid}-{n}.{WEB_KINDS[kind][0]}"), "wb") as fh:
                    fh.write(body)
                good.append({"n": n, "kind": kind, "image": final, "page": page, "site": site_of(page or final),
                             "w": size[0] if size else None, "h": size[1] if size else None})
        if job.get("cancelled"):
            return
        if not good:
            raise ApiError(404, "Não achei fotos desse produto nas páginas que a IA encontrou. Tente buscar só pela marca e o modelo.")
        job.update(stage="done", msg="", results=good)
    except ApiError as e:
        job.update(stage="error", msg=e.msg)
    except Exception:  # noqa: BLE001
        log.exception("busca de fotos")
        job.update(stage="error", msg="Não deu para buscar agora. Tente de novo em instantes.")
    finally:
        if job.get("cancelled"):
            for p in _web_job_files(jid):
                try:
                    os.unlink(p)
                except OSError:
                    pass


def web_job_start(body: dict) -> dict:
    need_ai_on()
    name = text(body.get("name"), 200, "nome", required=True)
    details = " ".join(text(body.get("details"), 4000, "detalhes").split())[:300]
    qty = " ".join(str(body.get("qty") or "1").split())[:30] or "1"
    if not SUPERVISOR_TOKEN and not AI_MOCK:
        raise ApiError(503, "O app não tem acesso à API do Home Assistant.")
    web_jobs_cleanup()
    jid = secrets.token_hex(8)
    with WEB_LOCK:
        WEB_JOBS[jid] = {"stage": "busy", "msg": "Procurando o produto na internet…", "results": [], "at": time.time()}
    threading.Thread(target=_web_job_run, args=(jid, name, details, search_entity(), qty), daemon=True).start()
    return {"id": jid}


def web_job(jid: str) -> dict:
    need_ai_on()  # desligou a IA no meio da busca: o resultado (fotos e dados do produto) não chega
    job = WEB_JOBS.get(jid)
    if not job:
        raise ApiError(404, "Esta busca terminou. Busque de novo.")
    return job


# ---------------------------------------------------------------------------
# Novidades do produto: a IA com busca na web procura atualizações, lançamentos, modelo novo, recalls e fim de
# suporte de um item. Mesmo jeito da busca de fotos (um trabalho em segundo plano, com a mesma IA de busca).

NEWS_KINDS = ("atualizacao", "lancamento", "sucessor", "recall", "suporte", "outro")
NEWS_MAX = 3  # só as mais recentes
MOCK_NEWS = {"produto": "Produto de exemplo", "novidades": [
    {"tipo": "atualizacao", "titulo": "Atualização de firmware com correções de conexão", "resumo": "O fabricante liberou uma versão nova "
     "do firmware, que melhora a reconexão ao Wi-Fi.", "data": "2026-09-12", "fonte": "https://exemplo.com/firmware", "boato": False},
    {"tipo": "sucessor", "titulo": "Modelo novo da mesma linha anunciado", "resumo": "A nova geração chega com mais brilho e menor consumo.",
     "data": "2026-10", "fonte": "https://exemplo.com/lancamento", "boato": False},
    {"tipo": "lancamento", "titulo": "Versão com Matter pode chegar no próximo ano", "resumo": "Sites de tecnologia falam de uma versão "
     "compatível com Matter; o fabricante não confirmou.", "data": "", "fonte": "https://exemplo.com/rumor", "boato": True},
]}


def news_prompt(name: str, details: str) -> str:
    links = re.findall(r"https?://[^\s<>\"']+", details or "")
    return "\n".join(filter(None, [
        "Você acompanha os equipamentos e objetos de uma casa no Brasil.",
        f"Produto: {name}",
        f"Detalhes: {details}" if details else "",
        f"Hoje é {news_today().isoformat()}.",
        "",
        "Use a busca na web agora.",
        f"Abra primeiro a página indicada nos detalhes ({', '.join(links[:2])})." if links else "",
        # a busca comum não achava o firmware: ele fica na página de suporte do fabricante, nos downloads, e às vezes só na
        # do mesmo modelo em outro país (o código muda um pouco por região)
        "Comece pela página de suporte do fabricante para este modelo, na parte de downloads ou de software (manuais e downloads, "
        "firmware, atualização de software): cada arquivo de firmware ou de atualização do sistema com data nos últimos 12 meses "
        "é uma atualização (no título, a versão; a data é a do arquivo; a fonte é a página de suporte). O mesmo aparelho costuma "
        "ter um código um pouco diferente em cada país (mudam as letras do começo ou do fim): se a página do Brasil não mostrar "
        "os arquivos, procure a do mesmo modelo em outro país.",
        "Depois procure, no site do fabricante e em sites de tecnologia e de notícias confiáveis, "
        "o que saiu nos últimos 12 meses e o que já foi anunciado para os próximos meses sobre este produto:",
        "- atualizações de firmware, software ou aplicativo;",
        "- modelo novo ou sucessor;",
        "- lançamentos anunciados da mesma linha;",
        "- recall deste modelo: só quando o fabricante ou um órgão (como a Senacon) chama o produto de volta para troca, conserto ou reembolso. "
        "Falha de segurança corrigida por atualização é atualizacao, não recall;",
        "- fim de suporte ou de atualizações.",
        "Cada novidade precisa de uma fonte que apareceu na busca. Não invente: sem fonte, deixe de fora. "
        "Rumor ou vazamento só entra marcado como boato.",
        "Responda somente com um objeto JSON, sem texto antes ou depois:",
        '{"produto": "nome do produto que você identificou", "novidades": [{"tipo": "atualizacao, lancamento, sucessor, recall, suporte ou outro", '
        '"titulo": "frase curta em português", "resumo": "uma ou duas frases em português", "data": "AAAA-MM-DD, AAAA-MM ou vazio", '
        '"fonte": "endereço da página", "boato": false}]}',
        f"Só as {NEWS_MAX} novidades mais recentes, da mais nova para a mais antiga.",
        'Se não achar nada, responda {"produto": "...", "novidades": []}.',
        'Se não conseguir usar a busca na web, responda apenas {"erro": "sem_busca"}.',
    ]))


# "recall" só fica quando o texto fala de recall de verdade (chamar de volta, lote afetado, órgão do consumidor, risco);
# a IA marcava recall em atualização de segurança e em notícia comum. O resto vira atualização ou outro.
RECALL_WORDS = re.compile(r"recall|chamamento|convoca|recolhiment|recolher|senacon|cpsc|devolu|reembols|\blotes?\b|"
                          r"risco de (incendio|choque|queimadura|explosao|ferimento)|pegar fogo")
UPDATE_WORDS = re.compile(r"firmware|software|atualiza|patch|versao|aplicativo|corrig")  # falha só anunciada, sem correção: outro


def news_today():
    """Hoje (INV_HOJE fixa a data nos testes)."""
    try:
        return datetime.strptime(os.environ.get("INV_HOJE", ""), "%Y-%m-%d").date()
    except ValueError:
        return datetime.now().date()


def news_recent(date: str) -> bool:
    """Dos últimos 12 meses (ou sem data). "2023" e "2023-09" valem pelo fim do ano e do mês."""
    if not date:
        return True
    y, m, d = (date.split("-") + ["", ""])[:3]
    try:
        y = int(y)
        m = int(m) if m else 12
        end = datetime(y, m, int(d)).date() if d else (datetime(y + (m == 12), m % 12 + 1, 1).date() - timedelta(days=1))
    except ValueError:
        return True
    return end >= news_today() - timedelta(days=365)


def news_kind(kind, title: str = "", summary: str = "") -> str:
    kind = fold(str(kind or "")).strip()
    kind = kind if kind in NEWS_KINDS else "outro"
    if kind == "recall":
        txt = fold(f"{title or ''} {summary or ''}")
        if not RECALL_WORDS.search(txt):
            kind = "atualizacao" if UPDATE_WORDS.search(txt) else "outro"
    return kind


def news_clean(data) -> dict:
    """O que a IA achou, conferido: só com fonte (http ou https), tipo conhecido, data no formato certo, sem repetidas."""
    if not isinstance(data, dict):
        data = {}
    raw = data.get("novidades") or data.get("news") or []
    out, seen = [], set()
    for n in raw if isinstance(raw, list) else []:
        if not isinstance(n, dict):
            continue
        title = " ".join(str(n.get("titulo") or n.get("title") or "").split())[:160]
        url = _fix_url(n.get("fonte") or n.get("url") or n.get("source"))
        if not title or not url:
            continue
        key = (title.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        date = str(n.get("data") or n.get("date") or "").strip()[:10]
        if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", date):
            date = ""
        if not news_recent(date):  # a IA às vezes traz notícia de anos atrás
            continue
        summary = " ".join(str(n.get("resumo") or n.get("summary") or "").split())[:400]
        out.append({"tipo": news_kind(n.get("tipo") or n.get("type"), title, summary), "titulo": title, "resumo": summary,
                    "data": date, "fonte": url, "site": site_of(url), "boato": n.get("boato") is True or n.get("rumor") is True})
    out.sort(key=lambda x: x["data"] or "0000", reverse=True)
    return {"produto": " ".join(str(data.get("produto") or data.get("product") or "").split())[:200], "novidades": out[:NEWS_MAX]}


def ai_find_news(name: str, details: str, entity: str) -> dict:
    prompt = news_prompt(name, details)
    with AiCall("novidades", "ai_task.simulado" if AI_MOCK else entity, prompt) as call:
        if AI_MOCK:
            time.sleep(0.4)
            data = read_json(os.environ.get("INV_MOCK_NEWS") or "", None) or MOCK_NEWS
            call.answer(data)
        else:
            raw = ai_call_text("InventarIA: novidades", prompt, entity)
            call.answer(str(raw or ""))
            try:
                data = extract_json(raw)
            except ApiError:
                call.result = "sem_busca"
                log.info("novidades: resposta da IA fora do formato: %s", " ".join(str(raw or "").split())[:400])
                raise ApiError(502, "A IA respondeu sem usar a busca na web. " + SEARCH_HOWTO) from None
        if isinstance(data, dict) and data.get("erro"):
            call.result = "sem_busca"
            raise ApiError(502, "A IA não usou a busca na web. " + SEARCH_HOWTO)
    return news_clean(data)


def _news_job_run(jid: str, name: str, details: str, entity: str, iid: str = ""):
    job = WEB_JOBS[jid]
    try:
        found = ai_find_news(name, details, entity)
        if not job.get("cancelled"):
            for g in news_group_ids(iid) if iid else []:  # o mesmo equipamento nos outros cômodos ganha o mesmo resultado
                news_save_result(g, found)
            job.update(stage="done", msg="", news=found)
    except ApiError as e:
        job.update(stage="error", msg=e.msg)
    except Exception:  # noqa: BLE001
        log.exception("novidades")
        job.update(stage="error", msg="Não deu para buscar agora. Tente de novo em instantes.")


def news_job_start(body: dict) -> dict:
    need_news_on()
    it = STORE.item(str(body.get("item") or ""))
    if not it:
        raise ApiError(404, "Item não encontrado.")
    if it.get("cat") not in news_cats():
        raise ApiError(400, "As novidades são só dos eletrônicos.")
    if not SUPERVISOR_TOKEN and not AI_MOCK:
        raise ApiError(503, "O app não tem acesso à API do Home Assistant.")
    web_jobs_cleanup()
    jid = secrets.token_hex(8)
    details = " ".join(str(it.get("details") or "").split())[:300]
    with WEB_LOCK:
        WEB_JOBS[jid] = {"stage": "busy", "msg": "Procurando novidades…", "results": [], "news": None, "at": time.time(), "kind": "novidades"}
    threading.Thread(target=_news_job_run, args=(jid, it["name"], details, search_entity(), it["id"]), daemon=True).start()
    return {"id": jid}


# Novidades de todos: a IA escolhe, nas categorias marcadas, os itens em que faz sentido procurar novidades (uma
# pergunta só, sem busca na web; fica guardado até o item mudar) e o app confere um por um, guardando cada resultado.
NEWS_LOCK = threading.Lock()
NEWS_FRESH_DAYS = 7  # conferido há menos que isso fica para a próxima
NEWS_CATS = ("eletronicos",)  # só Eletrônicos: móveis, panelas e roupas não têm novidades
TRIAGE_CHUNK = 60
MOCK_TRIAGE = re.compile(r"\b(tv|televis|notebook|computador|celular|smartphone|tablet|geladeira|refrigerador|micro-?ondas|maquina|lavadora|"
                         r"lampada|fone|soundbar|cafeteira|ar.?condicionado|aspirador|roteador|impressora|monitor|console|camera|forno)", re.I)  # caixa de som passiva fica de fora


def news_cats() -> list[str]:
    """Categorias em que a IA procura equipamentos: só Eletrônicos (se a categoria não foi excluída)."""
    cats = STORE.cat_map()
    return [c for c in NEWS_CATS if c in cats]


# o que não muda o equipamento nas novidades: a cor e as palavras de ligação ("Echo Spot (2024) preto" = "Echo Spot 2024")
NEWS_NOISE = set("""de da do das dos com sem e em para pra a o as os na no nas nos and with the of cor
preto preta branco branca cinza prata prateado prateada dourado dourada azul azui vermelho vermelha verde rosa roxo roxa
lila amarelo amarela laranja bege marrom grafite chumbo vinho creme nude champagne titanio
black white silver gray grey gold blue red green pink purple graphite""".split())


def news_group_key(it: dict) -> str:
    """O mesmo equipamento em vários cômodos (ou no plural, ou noutra cor, ou com as palavras em outra ordem) é um só nas
    novidades: pelo código do modelo (LX20, K300) e a primeira palavra, no singular; sem código, pelas palavras do nome no
    singular, sem a cor nem as palavras de ligação, em ordem alfabética."""
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not re.search(r"\d", w) else w
             for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", fold(it.get("name") or ""))]
    codes = sorted({w for w in words if len(w) >= 3 and re.search(r"\d", w) and re.search(r"[a-z]", w)})
    if codes and words:
        return f"{words[0]}|{' '.join(codes)}"
    return " ".join(sorted({w for w in words if w not in NEWS_NOISE})) or " ".join(words)


def news_group_ids(iid: str) -> list[str]:
    """Os itens do mesmo grupo do item (ele primeiro)."""
    it = STORE.item(iid)
    if not it:
        return [iid]
    key = news_group_key(it)
    return [iid] + [i["id"] for i in STORE.data["items"] if i["id"] != iid and news_group_key(i) == key]


def item_sig(it: dict) -> str:
    return fold(f"{it.get('name') or ''} | {' '.join(str(it.get('details') or '').split())[:200]}")


def news_read() -> dict:
    d = read_json_ok(NEWS_FILE, {}) or {}
    if not isinstance(d, dict):
        d = {}
    for k in ("itens", "triagem"):
        if not isinstance(d.get(k), dict):
            d[k] = {}
    for v in d["itens"].values():  # guardadas antes do limite: ficam só as mais recentes
        news = v.get("news") if isinstance(v, dict) else None
        if isinstance(news, dict) and isinstance(news.get("novidades"), list):  # guardadas antes: as mesmas regras de agora
            news["novidades"] = [n for n in news["novidades"] if isinstance(n, dict) and news_recent(str(n.get("data") or ""))][:NEWS_MAX]
            for n in news["novidades"]:
                n["tipo"] = news_kind(n.get("tipo"), n.get("titulo"), n.get("resumo"))
    return d


def news_of(iid: str) -> dict:
    """O que já foi conferido de um item ({at, news}), para a ficha; vazio se nunca foi."""
    v = news_read()["itens"].get(iid)
    if not isinstance(v, dict) or not isinstance(v.get("news"), dict) or not STORE.item(iid):
        return {}
    return {"at": v.get("at"), "news": v["news"]}


def news_clear() -> dict:
    """Apaga as novidades guardadas, as escolhas da IA e a última conferência; para a conferência em andamento."""
    for jid, job in list(WEB_JOBS.items()):
        if job.get("kind") == "lote":
            job.update(cancelled=True, cleared=True)
            WEB_JOBS.pop(jid, None)
    with NEWS_LOCK:
        write_json_atomic(NEWS_FILE, {"itens": {}, "triagem": {}})
    return news_overview()


def news_save_result(iid: str, found: dict):
    with NEWS_LOCK:
        d = news_read()
        it = STORE.item(iid)
        d["itens"][iid] = {"at": now_iso(), "sig": item_sig(it) if it else "", "news": found}
        write_json_atomic(NEWS_FILE, d)


def news_overview() -> dict:
    """O que a aba Novidades mostra: as categorias, quem a IA escolheu, o que já foi conferido e a conferência em andamento."""
    d = news_read()
    ids = {i["id"]: i for i in STORE.data["items"]}
    cats = news_cats()
    tri = {k: v for k, v in d["triagem"].items() if k in ids and isinstance(v, dict) and v.get("sig") == item_sig(ids[k])}
    job = next((dict(id=j, stage=v["stage"], msg=v["msg"], progress=v.get("progress"), summary=v.get("summary"))
                for j, v in WEB_JOBS.items() if v.get("kind") == "lote" and v["stage"] == "busy"), None)
    grupos = {i["id"]: news_group_key(i) for i in STORE.data["items"] if i.get("cat") in cats or i["id"] in d["itens"]}
    return {"cats": cats, "triagem": {k: bool(v.get("conferir")) for k, v in tri.items()}, "grupos": grupos,
            "pendentes": sum(1 for i in STORE.data["items"] if i.get("cat") in cats and i["id"] not in tri),
            "itens": {k: {"at": v.get("at"), "news": v.get("news")} for k, v in d["itens"].items() if k in ids and isinstance(v, dict)},
            "ultima": d.get("ultima"), "job": job}


def triage_prompt(items: list[dict]) -> str:
    cats = STORE.cat_map()
    lines = [f"{i['id']}: {i['name']}" + (f" — {' '.join(str(i.get('details') or '').split())[:160]}" if i.get("details") else "")
             + f" [{cats.get(i.get('cat'), 'Outros')}]" for i in items]
    return "\n".join([
        "Você ajuda a acompanhar as novidades dos equipamentos de uma casa no Brasil.",
        "Para cada item abaixo, diga se vale procurar novidades na internet: atualizações de firmware ou software, modelo novo, "
        "lançamentos, recalls ou fim de suporte.",
        "Vale para eletrônicos, eletrodomésticos, aparelhos conectados, ferramentas elétricas, veículos e equipamentos com marca ou modelo.",
        "Não vale para móveis (cama, mesa, cadeira, sofá, armário, estante), decoração, quadros, tapetes, roupa de cama, toalhas, "
        "utensílios simples (panelas, pratos, talheres), plantas, livros, roupas e coisas sem marca nem modelo.",
        "",
        "Itens (id: nome — detalhes [categoria]):",
        *lines,
        "",
        'Responda somente com um objeto JSON, sem texto antes ou depois: {"conferir": ["id", "id"]}, só com os ids em que vale procurar.',
    ])


def ai_triage(items: list[dict]) -> set[str]:
    """Os ids em que vale procurar novidades, numa pergunta à IA (sem busca na web) para cada bloco de itens."""
    chosen: set[str] = set()
    entity = photo_entity()
    for k in range(0, len(items), TRIAGE_CHUNK):
        part = items[k:k + TRIAGE_CHUNK]
        prompt = triage_prompt(part)
        with AiCall("triagem", "ai_task.simulado" if AI_MOCK else entity, prompt) as call:
            if AI_MOCK:
                data = {"conferir": [i["id"] for i in part if MOCK_TRIAGE.search(fold(i["name"]))]}
                call.answer(data)
            else:
                raw = ai_call_text("InventarIA: escolher equipamentos", prompt, entity, timeout=180)
                if raw is None:
                    call.result = "formato"
                    raise ApiError(502, "A IA não devolveu resposta.")
                call.answer(raw)
                try:
                    data = extract_json(raw)
                except ApiError:
                    call.result = "formato"
                    raise
        got = data.get("conferir") if isinstance(data, dict) else data
        ids = {i["id"] for i in part}
        chosen |= {str(x) for x in (got if isinstance(got, list) else []) if str(x) in ids}
    return chosen


def _news_batch_run(jid: str):
    job = WEB_JOBS[jid]
    done = found = errors = 0
    novos = []  # equipamentos com alguma novidade que não estava guardada (para o aviso)
    try:
        cats = news_cats()
        cands = [i for i in STORE.sorted_items() if i.get("cat") in cats]
        d = news_read()
        todo_tri = [i for i in cands if (d["triagem"].get(i["id"]) or {}).get("sig") != item_sig(i)]
        if todo_tri:
            job["msg"] = "A IA está escolhendo os equipamentos…"
            chosen = ai_triage(todo_tri)
            if job.get("cleared"):
                return
            with NEWS_LOCK:
                d = news_read()
                for i in todo_tri:
                    d["triagem"][i["id"]] = {"sig": item_sig(i), "conferir": i["id"] in chosen}
                write_json_atomic(NEWS_FILE, d)
        # sozinho, de tempos em tempos: confere de novo o que tem mais tempo que o intervalo (menos um dia de folga)
        fresh = time.time() - (max(1, news_every() - 1) if job.get("auto") else NEWS_FRESH_DAYS) * 86400
        # os que a IA escolheu e os que a pessoa conferiu (um deixado de fora conferido pela ficha passa a ser conferido também)
        sel = [i for i in cands if (d["triagem"].get(i["id"]) or {}).get("conferir") or i["id"] in d["itens"]]

        def checked_at(i):
            at = (d["itens"].get(i["id"]) or {}).get("at")
            try:
                return datetime.fromisoformat(at).timestamp() if at else 0.0
            except (TypeError, ValueError):
                return 0.0
        groups = {}  # o mesmo equipamento em vários cômodos: uma busca só
        for i in sel:
            groups.setdefault(news_group_key(i), []).append(i)
        todo = []
        for members in groups.values():
            best = max(members, key=checked_at)
            if checked_at(best) < fresh:
                todo.append(members)
                continue
            late = [m for m in members if checked_at(m) < fresh]  # um já conferido na semana: os outros ganham o mesmo resultado
            if late:
                with NEWS_LOCK:
                    d2 = news_read()
                    src = d2["itens"].get(best["id"])
                    for m in late:
                        if src:
                            d2["itens"][m["id"]] = {**src, "sig": item_sig(m)}
                    write_json_atomic(NEWS_FILE, d2)
        todo.sort(key=lambda ms: max(checked_at(m) for m in ms))
        job["progress"] = {"feitos": 0, "total": len(todo), "atual": ""}
        entity = search_entity()
        for n, members in enumerate(todo):
            if job.get("cancelled"):
                break
            need_ai_on()
            it = min(members, key=lambda m: (len(m["name"]), m["name"]))  # o nome mais curto: "Lâmpada", não "Lâmpadas"
            job["progress"] = {"feitos": n, "total": len(todo), "atual": it["name"]}
            job["msg"] = f"Conferindo {n + 1} de {len(todo)}: {it['name']}"
            try:
                res = ai_find_news(it["name"], " ".join(str(it.get("details") or "").split())[:300], entity)
            except ApiError as e:
                if is_quota(e.msg) or "busca na web" in e.msg or e.status == 409:
                    raise  # a cota acabou, a IA não busca na web ou a IA foi desligada: as próximas também não vão
                errors += 1
                continue
            if job.get("cleared"):  # Limpar novidades no meio: nada mais é gravado
                return
            if news_new_entries((news_read()["itens"].get(it["id"]) or {}).get("news"), res):
                novos.append(it["name"])
            for m in members:
                news_save_result(m["id"], res)
            done += 1
            found += 1 if res["novidades"] else 0
        summary = {"selecionados": len(groups), "conferidos": done, "com_novidades": found, "em_dia": len(groups) - len(todo), "erros": errors,
                   "novos": len(novos)}
        if job.get("cleared"):
            return
        with NEWS_LOCK:
            d = news_read()
            d["ultima"] = {"at": now_iso(), **summary}
            write_json_atomic(NEWS_FILE, d)
        job.update(stage="done", msg="", summary=summary, progress={"feitos": done, "total": len(todo), "atual": ""})
        if job.get("auto") and novos and news_notify_target():
            try:
                send_news_notice(len(novos))
            except ApiError as e:
                log.warning("aviso das novidades: %s", e.msg)
    except ApiError as e:
        msg = e.msg
        if done:
            msg += f" O que já foi conferido ({done}) ficou salvo."
        job.update(stage="error", msg=msg, summary={"conferidos": done, "com_novidades": found})
    except Exception:  # noqa: BLE001
        log.exception("novidades de todos")
        job.update(stage="error", msg="Não deu para conferir agora. Tente de novo em instantes.")


def news_new_entries(before, after) -> list[dict]:
    """As novidades de agora que não estavam na busca anterior (pela fonte ou pelo título)."""
    seen = set()
    for n in ((before or {}).get("novidades") or []) if isinstance(before, dict) else []:
        if isinstance(n, dict):
            seen.add(str(n.get("fonte") or "")); seen.add(fold(str(n.get("titulo") or "")))
    return [n for n in (after or {}).get("novidades") or [] if n.get("fonte") not in seen and fold(n.get("titulo") or "") not in seen]


def ingress_path() -> str | None:
    """O endereço do app dentro do Home Assistant (/app/<slug>, desde o 2026.2), pelo nome da máquina ("a1b2c3d4-inventario")."""
    h = socket.gethostname()
    return f"/app/{h.replace('-', '_', 1)}" if re.fullmatch(r"[a-z0-9]+-inventario", h) else None


def news_notice(n: int, test: bool = False) -> dict:
    """O aviso: "Novidades em 3 itens. Toque para abrir.", que abre o InventarIA em Novidades (o Home Assistant passa o
    "/novidades" para a tela por mensagem, e a tela vai para #/novidades)."""
    link = f"{ingress_path()}/novidades" if ingress_path() else None
    msg = f"Novidades em {n} {'item' if n == 1 else 'itens'}. Toque para abrir."
    return {"title": "InventarIA" + (" (teste)" if test else ""), "message": msg, "link": link}


def send_news_notice(n: int, who: str | None = None, test: bool = False) -> int:
    """Manda o aviso para os celulares de quem foi escolhido (todos ou uma pessoa). Devolve quantos celulares receberam."""
    who = who or news_notify_target()
    if not WHO_RE.fullmatch(who or ""):
        raise ApiError(400, "Escolha quem avisar.")
    phones = news_phones(who)
    note = news_notice(n, test)
    if AI_MOCK and not SUPERVISOR_TOKEN:
        log.info("aviso simulado para %s: %s", ", ".join(phones), note["message"])  # dev/run.sh: sem Home Assistant
        return len(phones)
    data = {"tag": "inventaria-novidades", "group": "inventaria", "channel": "Novidades"}
    if note["link"]:
        data.update(url=note["link"], clickAction=note["link"])
    sent, err = 0, None
    for ph in phones:
        try:
            ha_request("POST", f"/services/notify/{ph}", {"title": note["title"], "message": note["message"], "data": data}, timeout=15)
            sent += 1
        except ApiError as e:
            log.warning("aviso das novidades para %s: %s", ph, e.msg)
            err = e
    if not sent and err:
        raise err
    return sent


# -- as pessoas que recebem avisos: o app olha para a pessoa, nunca para um aparelho (como no ResolvIA e na CronologIA,
# lib/phones.js). Os celulares de uma pessoa são os do app Home Assistant entre os rastreadores dela (Configurações > Pessoas).
_people_cache = {"at": 0.0, "value": None}


def ha_slug(v: str) -> str:
    """Como o Home Assistant dá nome às coisas: "Celular da Ana" → "celular_da_ana"."""
    v = unicodedata.normalize("NFD", str(v or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", v).strip("_")


def tracker_devices() -> dict | None:
    """O aparelho de cada rastreador, pelos registros do Home Assistant: {entity_id: {"name", "mobile"} ou None};
    None quando não deu para ler os registros. O serviço de aviso tem o nome do aparelho, não do rastreador."""
    try:
        ents = ha_ws({"type": "config/entity_registry/list_for_display"}) or {}
        devs = ha_ws({"type": "config/device_registry/list"}) or []
        if not isinstance(ents, dict) or not isinstance(ents.get("entities"), list) or not isinstance(devs, list):
            return None
    except (ApiError, OSError, ValueError):
        return None
    by_id = {d.get("id"): d for d in devs if isinstance(d, dict)}
    out = {}
    for e in ents["entities"]:
        if isinstance(e, dict) and str(e.get("ei") or "").startswith("device_tracker."):
            d = by_id.get(e.get("di"))
            out[e["ei"]] = {"name": d.get("name") or "", "mobile": any(isinstance(i, list) and i[:1] == ["mobile_app"] for i in d.get("identifiers") or [])} if d else None
    return out


def tracker_phones(trackers, notify: set, devices: dict | None) -> list[str]:
    """Os celulares (notify.mobile_app_*) desses rastreadores: pelo nome do aparelho do app Home Assistant; outro tipo
    de rastreador (o roteador) não é celular. Sem os registros, pelo nome do rastreador (device_tracker.x → mobile_app_x)."""
    out = []
    for t in trackers if isinstance(trackers, list) else []:
        tid = str(t)
        by_id = "mobile_app_" + re.sub(r"^device_tracker\.", "", tid)
        cands = [by_id]
        if devices is not None and tid in devices:
            d = devices[tid]
            cands = [f"mobile_app_{ha_slug(d['name'])}", by_id] if d and d["mobile"] else []
        hit = next((c for c in cands if c in notify), None)
        if hit and hit not in out:
            out.append(hit)
    return out


def news_people() -> list[dict]:
    """As pessoas da casa no Home Assistant e os celulares de cada uma: [{id, name, phones}], por nome (cache de 60 s)."""
    if AI_MOCK and not SUPERVISOR_TOKEN:
        return [{"id": "person.pessoa_de_teste", "name": "Pessoa de Teste", "phones": ["mobile_app_celular_de_teste"]}]
    if not SUPERVISOR_TOKEN:
        return []
    if _people_cache["value"] is not None and time.time() - _people_cache["at"] < 60:
        return _people_cache["value"]
    states = ha_request("GET", "/states", timeout=15) or []
    notify = {svc for dom in ha_request("GET", "/services", timeout=15) or [] if isinstance(dom, dict) and dom.get("domain") == "notify"
              for svc in (dom.get("services") or {}) if NOTIFY_RE.fullmatch(svc)}
    devices = tracker_devices()
    out = []
    for st in states if isinstance(states, list) else []:
        eid = str((st or {}).get("entity_id") or "")
        if re.fullmatch(r"person\.[a-z0-9_]+", eid):
            a = st.get("attributes") or {}
            out.append({"id": eid, "name": str(a.get("friendly_name") or eid[7:]), "phones": tracker_phones(a.get("device_trackers"), notify, devices)})
    out.sort(key=lambda p: fold(p["name"]))
    _people_cache.update(at=time.time(), value=out)
    return out


def news_phones(who: str) -> list[str]:
    """Os celulares de quem recebe: de todas as pessoas ou de uma."""
    people = news_people()
    if who == "todos":
        phones = list(dict.fromkeys(ph for p in people for ph in p["phones"]))
        if not phones:
            raise ApiError(400, "Ninguém da casa tem celular ligado no Home Assistant (Configurações > Pessoas).")
        return phones
    p = next((x for x in people if x["id"] == who), None)
    if not p:
        raise ApiError(400, "Essa pessoa não está mais no Home Assistant. Escolha outra em Avisar.")
    if not p["phones"]:
        raise ApiError(400, f"Sem celular ligado a {p['name']} no Home Assistant (Configurações > Pessoas).")
    return p["phones"]


def news_auto_due(now: float) -> bool:
    """Está na hora de conferir sozinho? Pela última conferência que terminou; depois de uma tentativa que deu erro,
    espera 6 horas para não gastar a IA à toa."""
    every = news_every()
    if not every or not news_enabled() or not ai_enabled():
        return False
    d = news_read()

    def ts(v):
        try:
            return datetime.fromisoformat(v).timestamp() if v else 0.0
        except (TypeError, ValueError):
            return 0.0
    return now - ts((d.get("ultima") or {}).get("at")) >= every * 86400 - 3600 and now - ts(d.get("auto_tentativa")) >= 6 * 3600


def news_auto_loop():
    while True:
        time.sleep(NEWS_TICK)
        try:
            if (SUPERVISOR_TOKEN or AI_MOCK) and news_auto_due(time.time()):
                with NEWS_LOCK:
                    d = news_read()
                    d["auto_tentativa"] = now_iso()
                    write_json_atomic(NEWS_FILE, d)
                news_batch_start(auto=True)
        except ApiError as e:
            log.info("novidades sozinho: %s", e.msg)
        except Exception:  # noqa: BLE001
            log.exception("novidades sozinho")


def news_batch_start(auto: bool = False) -> dict:
    need_news_on()
    if not SUPERVISOR_TOKEN and not AI_MOCK:
        raise ApiError(503, "O app não tem acesso à API do Home Assistant.")
    with WEB_LOCK:
        for j, v in WEB_JOBS.items():
            if v.get("kind") == "lote" and v["stage"] == "busy" and not v.get("cancelled"):
                return {"id": j}  # já tem uma conferência andando: acompanha a mesma
    web_jobs_cleanup()
    jid = secrets.token_hex(8)
    with WEB_LOCK:
        WEB_JOBS[jid] = {"stage": "busy", "msg": "Começando…", "results": [], "at": time.time(), "kind": "lote", "auto": auto,
                         "progress": {"feitos": 0, "total": 0, "atual": ""}}
    threading.Thread(target=_news_batch_run, args=(jid,), daemon=True).start()
    return {"id": jid}


# ---------------------------------------------------------------------------
# Conversar: um chat com a IA do Home Assistant a qualquer momento, sobre o que está na tela ou outro assunto.
# Sem memória no servidor: a tela manda as últimas mensagens e onde a pessoa está; o app junta os dados do inventário.

CHAT_TURNS = 12
CHAT_MAX_CHARS = 2000
MOCK_CHAT = "Exemplo da IA simulada: no Home Assistant, a IA responde de verdade, com os dados desta tela."


def _money(v) -> str:
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        x = 0.0
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + (s[:-3] if s.endswith(",00") else s)


def _item_line(it: dict, cats: dict) -> str:
    room = STORE.room(it.get("room")) or {}
    bits = [f"{STORE.tag(it)} {it.get('name', '')}", room.get("name", ""), cats.get(it.get("cat"), "Outros"),
            f"qtd {it.get('qty') or '1'}", _money(it.get("value"))]
    if it.get("zone") and zones_enabled():
        bits.insert(2, f"zona {it['zone']}")
    return " | ".join(b for b in bits if b)


def chat_context(screen: dict) -> str:
    """O que a IA precisa saber: o resumo da casa e o que está na tela (um item, um cômodo, uma busca, Novidades…)."""
    screen = screen if isinstance(screen, dict) else {}
    cats = STORE.cat_map()
    rooms, items = visible_data()  # com Usar bens desligado, a IA não vê os bens
    total = sum(float(i.get("value") or 0) for i in items)
    lines = [f"Inventário: {len(items)} itens em {len(rooms)} cômodos, total {_money(total)}."]
    by_room = []
    for r in sorted(rooms, key=lambda r: r.get("order", 0)):
        its = [i for i in items if i["room"] == r["id"]]
        by_room.append(f"{r['code']} {r['name']}: {len(its)} itens, {_money(sum(float(i.get('value') or 0) for i in its))}")
    lines.append("Cômodos: " + "; ".join(by_room) + ".")
    top = sorted(items, key=lambda i: -float(i.get("value") or 0))[:10]
    if top:
        lines.append("Mais valiosos: " + "; ".join(f"{i.get('name')} ({_money(i.get('value'))})" for i in top) + ".")
    view = str(screen.get("view") or "")
    where = {"home": "Início", "search": "Buscar", "rooms": "Cômodos", "room": "um cômodo", "item": "a ficha de um item",
             "report": "Relatório do inventário", "data": "Mais"}.get(view, "o app")
    lines.append(f"A pessoa está em: {where}.")
    it = STORE.item(str(screen.get("item") or "")) if screen.get("item") else None
    room = STORE.room(str(screen.get("room") or "")) if screen.get("room") else None
    if it:
        lines.append("Item na tela: " + _item_line(it, cats) + ".")
        if it.get("details"):
            lines.append("Detalhes: " + " ".join(str(it["details"]).split())[:600])
        lines.append(f"Fotos: {len(it.get('photos') or [])}. Cadastrado em {str(it.get('createdAt') or '')[:10]}.")
        saved = (news_read()["itens"].get(it["id"]) or {}).get("news") or {}
        for n in (saved.get("novidades") or [])[:5]:
            lines.append(f"Novidade conferida: [{n.get('tipo')}] {n.get('titulo')} ({n.get('data') or 'sem data'}, {n.get('site') or ''}).")
    elif room:
        its = [i for i in STORE.sorted_items() if i["room"] == room["id"]]
        lines.append(f"Cômodo na tela: {room['code']} {room['name']}, {len(its)} itens:")
        lines += ["- " + _item_line(i, cats) for i in its[:80]]
    elif view == "search":
        q = " ".join(str(screen.get("q") or "").split())[:100]
        if q:
            lines.append(f"Busca na tela: \"{q}\".")
            words = [fold(w) for w in q.split()]
            hits = [i for i in items if all(w in fold(f"{i.get('name')} {i.get('details')} {i.get('zone')}") for w in words)][:40]
            lines += ["- " + _item_line(i, cats) for i in hits] or ["(nenhum item encontrado)"]
    elif view == "news" or (view == "data" and screen.get("tab") == "novidades"):  # a tela Novidades (antes, uma aba de Mais)
        d = news_read()
        com, seen = [], set()
        for k, v in d["itens"].items():
            it = STORE.item(k)
            if it and (v.get("news") or {}).get("novidades") and news_group_key(it) not in seen:  # o mesmo equipamento uma vez só
                seen.add(news_group_key(it))
                com.append((it, v))
        lines.append(f"Tela Novidades: {len(com)} eletrônicos com novidades conferidas.")
        for i, v in com[:20]:
            ns = v["news"]["novidades"]
            lines.append(f"- {i['name']}: " + "; ".join(f"[{n.get('tipo')}] {n.get('titulo')}" for n in ns[:3]))
    return "\n".join(lines)


def chat_prompt(messages: list[dict], screen: dict, user: str | None) -> str:
    conv = []
    for m in messages[-CHAT_TURNS:]:
        who = "Pessoa" if m["role"] == "user" else "Assistente"
        conv.append(f"{who}: {m['text']}")
    return "\n".join([
        f"Você é o assistente do InventarIA, o app de inventário da casa{f' de {user}' if user else ''}, dentro do Home Assistant.",
        "Responda em português do Brasil, curto e direto, em texto simples (no máximo uma lista curta).",
        "Pode responder sobre o que está na tela, sobre o inventário ou sobre qualquer outro assunto.",
        "Use só os dados do inventário abaixo; não invente itens nem valores. Você não muda o inventário: se pedirem, diga como fazer no app.",
        "",
        "Dados do inventário:",
        chat_context(screen),
        "",
        "Conversa até agora:",
        *conv,
        "",
        "Responda à última mensagem da Pessoa. Só o texto da resposta.",
    ])


def chat_entity() -> str:
    """A IA da conversa: a de buscar na internet (um assistente com busca responde também o que é de fora), senão a de ler fotos."""
    return search_entity() or photo_entity()


def ai_chat(body: dict, user: str | None) -> dict:
    need_ai_on()
    raw = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(raw, list) or not raw:
        raise ApiError(400, "Escreva uma mensagem.")
    msgs = []
    for m in raw[-CHAT_TURNS:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            raise ApiError(400, "Conversa inválida.")
        t = " ".join(str(m.get("text") or "").split()) if m["role"] == "user" else str(m.get("text") or "").strip()
        if not t:
            continue
        msgs.append({"role": m["role"], "text": t[:CHAT_MAX_CHARS]})
    if not msgs or msgs[-1]["role"] != "user":
        raise ApiError(400, "Escreva uma mensagem.")
    if not SUPERVISOR_TOKEN and not AI_MOCK:
        raise ApiError(503, "O app não tem acesso à API do Home Assistant.")
    prompt = chat_prompt(msgs, body.get("screen") or {}, user)
    entity = chat_entity()
    with AiCall("chat", "ai_task.simulado" if AI_MOCK else entity, prompt) as call:
        if AI_MOCK:
            time.sleep(0.4)
            reply = MOCK_CHAT
        else:
            res = ai_call_text("InventarIA: conversa", prompt, entity, timeout=120)
            if isinstance(res, dict):  # tarefa de IA às vezes devolve um objeto
                res = res.get("text") or res.get("resposta") or json.dumps(res, ensure_ascii=False)
            reply = str(res or "").strip()
            if not reply:
                call.result = "formato"
                raise ApiError(502, "A IA não devolveu resposta.")
        call.answer(reply)
    return {"reply": reply[:6000], "entity": entity or "padrão do Home Assistant"}


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
        ".woff2": "font/woff2", ".woff": "font/woff", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
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
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError, ValueError):  # ValueError: byte nulo no caminho
            return self.send_json({"error": "Arquivo não encontrado."}, 404)
        headers = {"Cache-Control": cache}
        if download_name:
            headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        self.send_bytes(200, body, ctype or MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream"), headers)

    # -- entrada
    def user(self):
        v = (self.headers.get("X-Remote-User-Display-Name") or self.headers.get("X-Remote-User-Name") or "").strip()
        try:
            v = v.encode("latin-1").decode("utf-8")  # o http.server lê os cabeçalhos como latin-1; o Ingress manda UTF-8
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return v[:60] or None

    def content_length(self) -> int:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0:
            self.close_connection = True
            self._body_read = True
            raise ApiError(400, "Pedido inválido.")
        return n

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
        length = self.content_length()
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
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ApiError(400, "Pedido inválido (JSON).")
        if not isinstance(body, dict):
            raise ApiError(400, "Pedido inválido.")
        return body

    def send_error(self, code, message=None, explain=None):
        if getattr(self, "request_version", "") == "HTTP/0.9":
            self.request_version = "HTTP/1.0"  # pedido torto: no Python 3.12 a resposta saía sem a linha de status
        if code != 501:
            return super().send_error(code, message, explain)
        body = json.dumps({"error": "Método não aceito."}, ensure_ascii=False).encode("utf-8")  # PATCH, OPTIONS…: em JSON, como os outros erros
        self.close_connection = True
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

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
        self._erro = "error"
        try:
            url = urlparse(self.path)
            path = unquote(url.path)
            if path == "/api/integracao/ferramentas":
                # o CorrerIA (WhatsApp, Claude e Gemini), com a chave de share/inventario/correria.json; os erros em {"erro"}
                self._erro = "erro"
                if not (correria_enabled() and CORRERIA.autorizado(self.headers, marcar=False)):
                    raise ApiError(401, "Chave inválida ou CorrerIA desligado no InventarIA.")
            elif path.startswith("/api/integracao/"):
                # outros apps do Home Assistant (ResolvIA) chegam pela rede interna, com a chave de share/inventario
                if not CONEXAO.autorizado(self.headers):
                    raise ApiError(401, "Chave inválida.")
            elif not DEV and self.client_address[0] not in ALLOWED_IPS:
                raise ApiError(403, "Abra o InventarIA pelo Home Assistant.")
            query = parse_qs(url.query)
            for m, rx, fn in ROUTES:
                if m == method:
                    match = rx.fullmatch(path)
                    if match:
                        fn(self, *match.groups(), query=query)
                        self.drain()  # corpo que a rota não leu não pode sobrar para o próximo pedido da mesma conexão
                        return None
            if method == "GET":
                return self.static(path)
            raise ApiError(404, "Endereço não encontrado.")
        except ApiError as e:
            self.drain()
            self.send_json({self._erro: e.msg, **e.extra}, e.status)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as e:  # noqa: BLE001
            log.exception("Erro em %s %s", method, self.path)
            self.drain()
            self.send_json({self._erro: f"Erro interno: {e}"}, 500)

    def drain(self):
        if not self._body_read and self.command in ("POST", "PUT", "DELETE"):
            if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
                self.close_connection = True
                self._body_read = True
                return
            try:
                length = self.content_length()
            except ApiError:
                length = 0
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
            if not os.path.isfile(p):
                # miniatura no lugar da foto grande (ou o contrário) enquanto a outra não chegou
                p = os.path.join(PHOTOS_DIR if m.group(1) == "thumbs" else THUMBS_DIR, name)
                if not os.path.isfile(p):
                    raise ApiError(404, "Foto não encontrada.")
                return self.send_file(p, cache="no-cache")
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
    out.update({"version": VERSION, "user": h.user(),
                "settings": {"ai_entity": STORE.settings.get("ai_entity") or "", "ai_search": STORE.settings.get("ai_search") or "",
                             "voice_stt": STORE.settings.get("voice_stt") or "", "ai": ai_enabled(), "zones": zones_enabled(), "bens": bens_enabled(), "ha_sensors": sensors_enabled(),
                             "news": news_enabled(), "news_every": news_every(), "news_notify": news_notify_target(), "correria": correria_enabled()},
                "correria_uso": correria_uso() if correria_enabled() else None,
                "features": {"ai": bool(SUPERVISOR_TOKEN) or AI_MOCK, "share": share_available()}})
    h.send_json(out)


def r_rev(h, query):
    # correria_uso: a tela mostra quando o CorrerIA usou as ferramentas por último (uma leitura não muda a rev)
    h.send_json({"rev": STORE.data.get("rev"), "correria_uso": correria_uso() if correria_enabled() else None})


def r_health(h, query):
    h.send_json({"ok": True, "version": VERSION})


def r_item_create(h, query):
    body = h.read_body()
    restore = bool(body.pop("_restore", False))
    it = STORE.create_items([body], h.user(), restore=restore)[0]
    h.send_json({"item": it, "rev": STORE.data["rev"]}, 201)


def r_items_bulk(h, query):
    items = STORE.update_items(h.read_body().get("items"), h.user())
    h.send_json({"items": items, "rev": STORE.data["rev"]})


def r_items_batch(h, query):
    body = h.read_body()
    bodies = body.get("items") or []
    if not isinstance(bodies, list) or not bodies or len(bodies) > 60:
        raise ApiError(400, "Envie de 1 a 60 itens.")
    rp = body.get("roomPhoto")
    if rp is not None and not isinstance(rp, dict):
        raise ApiError(400, "Foto do cômodo inválida.")
    created = STORE.create_items(bodies, h.user(), room_photo=rp)
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
    h.send_json({"room": room, "rooms": STORE.data["rooms"], "cats": STORE.cats(), "rev": STORE.data["rev"]}, 201)


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


def r_cat_create(h, query):
    cat = STORE.create_cat(h.read_body())
    h.send_json({"cat": cat, "cats": STORE.cats(), "rev": STORE.data["rev"]}, 201)


def r_cat_update(h, cid, query):
    cat = STORE.update_cat(cid, h.read_body())
    h.send_json({"cat": cat, "cats": STORE.cats(), "rev": STORE.data["rev"]})


def r_cat_delete(h, cid, query):
    moved = STORE.delete_cat(cid)
    h.send_json({"moved": moved, "cats": STORE.cats(), "rev": STORE.data["rev"]})


def r_rooms_order(h, query):
    rooms = STORE.reorder_rooms(h.read_body().get("ids") or [])
    h.send_json({"rooms": rooms, "rev": STORE.data["rev"]})


def r_photo(h, query):
    h.send_json(save_photo(h.read_body()), 201)


def r_ai_status(h, query):
    h.send_json(ai_status())


def r_voice_status(h, query):
    if query.get("fresh"):
        _voice_cache["at"] = 0.0
    h.send_json(voice_status())


def r_voice(h, query):
    pcm = h.read_raw(VOICE_MAX + 1024)
    need_ai_on()  # com Usar IA desligada, o Falar some junto
    h.send_json(voice_text(pcm))


def r_ai_text(h, query):
    h.send_json(ai_from_speech(h.read_body()))


def r_ai_usage(h, query):
    h.send_json(usage_summary())


def r_ai_identify(h, query):
    h.send_json(ai_identify(h.read_body()))


def r_web_start(h, query):
    h.send_json(web_job_start(h.read_body()), 202)


def r_web_status(h, jid, query):
    job = web_job(jid)
    h.send_json({"stage": job["stage"], "msg": job["msg"], "results": job["results"], "product": job.get("product")})


def r_web_image(h, jid, n, query):
    job = web_job(jid)
    r = next((x for x in job["results"] if x["n"] == int(n)), None)
    if not r:
        raise ApiError(404, "Foto não encontrada.")
    ext, ctype = WEB_KINDS[r["kind"]]
    h.send_file(os.path.join(TMP_DIR, f"web-{jid}-{r['n']}.{ext}"), ctype, cache="no-store")


def r_web_cancel(h, jid, query):
    job = WEB_JOBS.get(jid)
    if job:
        job["cancelled"] = True
        if job["stage"] != "busy":
            for p in _web_job_files(jid):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            WEB_JOBS.pop(jid, None)
    h.send_json({"ok": True})


def r_chat(h, query):
    h.send_json(ai_chat(h.read_body(), h.user()))


def r_news_start(h, query):
    h.send_json(news_job_start(h.read_body()), 202)


def r_news_status(h, jid, query):
    job = web_job(jid)
    h.send_json({"stage": job["stage"], "msg": job["msg"], "news": job.get("news"), "progress": job.get("progress"), "summary": job.get("summary")})


def r_news_overview(h, query):
    need_news_on()
    iid = (query.get("item") or [""])[0]
    h.send_json(news_of(iid) if iid else news_overview())


def r_news_clear(h, query):
    h.send_json(news_clear())


def r_news_all(h, query):
    h.read_body()
    h.send_json(news_batch_start(), 202)


def r_news_people(h, query):
    h.send_json({"people": [{"id": p["id"], "name": p["name"], "phone": bool(p["phones"])} for p in news_people()]})


def r_news_notify_test(h, query):
    body = h.read_body()
    who = str(body.get("who") or news_notify_target())
    if not WHO_RE.fullmatch(who):
        raise ApiError(400, "Escolha quem avisar.")
    h.send_json({"ok": True, "sent": send_news_notice(2, who, test=True)})


def r_news_cancel(h, jid, query):
    job = WEB_JOBS.get(jid)
    if job:
        job["cancelled"] = True
        WEB_JOBS.pop(jid, None)
    h.send_json({"ok": True})


def r_settings_get(h, query):
    h.send_json(STORE.settings)


def r_settings_put(h, query):
    body = h.read_body()
    if not isinstance(body, dict):
        raise ApiError(400, "Pedido inválido.")
    upd = {}  # confere tudo antes: um campo ruim não deixa os outros valendo pela metade
    for key, rx, msg in (("ai_entity", r"ai_task\.[a-z0-9_]+", "Entidade de IA inválida."),
                         ("ai_search", r"(ai_task|conversation)\.[a-z0-9_]+", "Entidade de IA inválida."),
                         ("voice_stt", r"stt\.[a-z0-9_]+", "Fala para texto inválida.")):
        if key in body:
            e = str(body.get(key) or "")
            if e and not re.fullmatch(rx, e):
                raise ApiError(400, msg)
            upd[key] = e
    for key in ("ai", "zones", "ha_sensors", "news", "bens", "correria"):
        if key in body:
            if not isinstance(body[key], bool):
                raise ApiError(400, "Use verdadeiro ou falso nesta opção.")
            upd[key] = body[key]
    if "news_every" in body:
        if isinstance(body["news_every"], bool) or body["news_every"] not in NEWS_EVERY:
            raise ApiError(400, "Escolha de quanto em quanto tempo conferir.")
        upd["news_every"] = int(body["news_every"])
    if "news_notify" in body:
        t = str(body.get("news_notify") or "")
        if t and not WHO_RE.fullmatch(t):
            raise ApiError(400, "Escolha quem avisar.")
        upd["news_notify"] = t
    with STORE.lock:
        STORE.settings.update(upd)
        STORE.save_settings()
    if "voice_stt" in upd:
        _voice_cache["at"] = 0.0
    if "correria" in upd:  # grava ou apaga share/inventario/correria.json na hora
        correria_publicar()
    if "ha_sensors" in upd or "ai" in upd:  # cria ou tira o sensor na hora
        threading.Thread(target=publish_usage_sensor if sensors_enabled() and ai_enabled() else remove_usage_sensor, daemon=True).start()
    h.send_json(STORE.settings)


def r_relatorio_pdf(h, query):
    """Mais > Relatório > Baixar PDF: o relatório do inventário como arquivo (o app do Home Assistant no Android não imprime
    a página). fotos=0 sem as fotos (o Mostrar fotos da tela); cor e tinta: a cor do app e a do texto em destaque."""
    um = lambda k, padrao="": (query.get(k) or [padrao])[0]  # noqa: E731
    fotos = um("fotos", "1") != "0"
    with STORE.lock:
        rooms, items = visible_data()
        d = relatorio.dados(json.loads(json.dumps(rooms)), json.loads(json.dumps(items)), STORE.cat_map(), zonas=zones_enabled(), fotos=fotos)

    def ler(nome):
        if not nome or not SAFE_FILE.fullmatch(nome):
            return None
        for pasta in (THUMBS_DIR, PHOTOS_DIR):
            p = os.path.join(pasta, nome)
            if os.path.isfile(p) and os.path.getsize(p) <= 8 * 1024 * 1024:
                with open(p, "rb") as f:
                    return f.read()
        return None
    body = relatorio.gerar_pdf(d, cor=um("cor"), tinta=um("tinta"), ler_foto=ler)
    return h.send_bytes(200, body, "application/pdf", {"Content-Disposition": f'attachment; filename="{relatorio.nome_arquivo(d)}"', "Cache-Control": "no-store"})


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
        if h.command != "HEAD":
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
    STORE.replace_all(data, "import")
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
    added, replaced = 0, True
    try:
        if zipfile.is_zipfile(part):
            safety, added, replaced = restore_zip(part, "antes-de-importar")
        else:
            try:
                with open(part, encoding="utf-8-sig") as f:
                    data = STORE.check_inventory(json.load(f))
            except (UnicodeDecodeError, ValueError):
                raise ApiError(400, "Use um backup .zip ou um .json exportado pelo app.")
            safety = safety_backup("antes-de-importar")
            STORE.replace_all(data, "import")
    finally:
        drop_upload(uid)
    with STORE.lock:
        h.send_json({"ok": True, "rev": STORE.data["rev"], "items": len(STORE.data["items"]),
                     "rooms": len(STORE.data["rooms"]), "safety": safety, "photosAdded": added, "replaced": replaced})


def r_upload_info(h, uid, query):
    part, _, m = upload_meta(uid)
    if os.path.getsize(part) != m["size"]:
        raise ApiError(400, "O envio do arquivo não terminou. Tente de novo.")
    h.send_json(inspect_file(part))


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
    try:
        data = read_json(os.path.join(HISTORY_DIR, name))
    except (ValueError, OSError):
        raise ApiError(400, "Esta versão está corrompida. Escolha outra.") from None
    if data is None:
        raise ApiError(404, "Versão não encontrada.")
    STORE.replace_all(data)
    h.send_json({"ok": True, "rev": STORE.data["rev"]})


# ---------------------------------------------------------------- outros apps

def write_private(path: str, text: str) -> None:
    """Um arquivo que só o dono lê (600) desde o primeiro byte: as chaves e os arquivos com a chave na pasta share."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, 0o600)  # se já existia com outra permissão


class Conexao:
    """Deixa os outros apps da família (ResolvIA) lerem os cômodos, como o GerencIA faz com as contas:
    share/inventario/integracao.json tem o endereço deste app na rede interna dos apps e uma chave;
    eles chamam /api/integracao/* com essa chave. Só leitura.
    nome separa as conexões, cada uma com a sua chave (integracao: os outros apps; correria: o CorrerIA, em
    share/inventario/correria.json); campos vai no começo do arquivo."""

    def __init__(self, nome="integracao", campos=None):
        self.arq_chave = os.path.join(DATA_DIR, f"{nome}.key")
        self.arq_share = os.path.join(SHARE_DIR, f"{nome}.json")
        self.campos = campos if campos is not None else {"app": "InventarIA"}
        self._chave = None
        self.ultimo = None

    def chave(self) -> str:
        if self._chave:
            return self._chave
        try:
            with open(self.arq_chave, encoding="utf-8") as f:
                self._chave = f.read().strip()
        except OSError:
            self._chave = ""
        if len(self._chave) < 32:
            self._chave = secrets.token_urlsafe(32)
            os.makedirs(os.path.dirname(self.arq_chave), exist_ok=True)
            write_private(self.arq_chave, self._chave)
        return self._chave

    def endereco(self):
        url = os.environ.get("INV_URL_INTERNA")
        if url:
            return url.rstrip("/"), None
        host = socket.gethostname()
        try:
            ip = socket.gethostbyname(host)
        except OSError:
            ip = None
        return f"http://{host}:{PORT}", ip

    def publicar(self, ligado=True):
        """Grava o arquivo que o outro app lê (atômico, só o dono lê) ou, desligado, apaga."""
        try:
            if not ligado:
                if os.path.exists(self.arq_share):
                    os.remove(self.arq_share)
                return
            url, ip = self.endereco()
            corpo = {**self.campos, "versao": VERSION, "url": url, "ip_url": f"http://{ip}:{PORT}" if ip else None,
                     "chave": self.chave(), "gravado_em": datetime.now().isoformat(timespec="seconds")}
            os.makedirs(SHARE_DIR, exist_ok=True)
            tmp = self.arq_share + ".tmp"
            write_private(tmp, json.dumps(corpo, ensure_ascii=False, indent=1))
            os.replace(tmp, self.arq_share)
        except OSError as e:
            log.warning("Conexão com outros apps: não consegui gravar %s (%s)", self.arq_share, e)

    def autorizado(self, headers, marcar=True) -> bool:
        h = headers.get("Authorization") or ""
        if not h.startswith("Bearer "):
            return False
        ok = hmac.compare_digest(h[7:].strip().encode(), self.chave().encode())
        if ok and marcar:
            self.ultimo = {"app": (headers.get("X-App") or "outro app")[:40], "em": now_iso()}
        return ok


CONEXAO = Conexao()


# O CorrerIA (o contato no WhatsApp e o servidor MCP do Claude e do Gemini) usa as ferramentas daqui (ferramentas.py): lê e
# grava o inventário. Só com Mais > Configurações > Integrações > CorrerIA ligado (desligado de início; não depende da IA,
# porque quem pensa é a IA do CorrerIA, o Claude ou o Gemini): grava share/inventario/correria.json com uma chave própria
# (/data/correria.key); desligado, o arquivo some e a rota responde 401.
CORRERIA_ASSUNTO = "inventário da casa: cômodos, itens com valor, categorias e os bens (casa, terreno, carro)"


def correria_conexao() -> Conexao:
    return Conexao("correria", {"app": "inventario", "nome": "InventarIA", "assunto": CORRERIA_ASSUNTO,
                                "ferramentas": "/api/integracao/ferramentas"})


CORRERIA = correria_conexao()


def correria_enabled() -> bool:
    return STORE.settings.get("correria") is True


def correria_uso() -> dict | None:
    """O último uso das ferramentas ({app: o cliente, como Claude, em, nome: a ferramenta}), para a tela mostrar quando foi.
    Fica num arquivo: continua valendo depois de reiniciar ou atualizar o app."""
    u = read_json_ok(os.path.join(DATA_DIR, "correria_uso.json"))
    return u if isinstance(u, dict) and u.get("em") else None


def correria_publicar():
    CORRERIA.publicar(correria_enabled())


def conexao_loop():
    # regravado a cada 15 minutos: um arquivo velho quer dizer que o InventarIA parou ou saiu
    while True:
        CONEXAO.publicar()
        correria_publicar()
        time.sleep(15 * 60)


def r_ferramentas_lista(h, query):
    h.send_json({"versao": VERSION, "instrucoes": ferramentas.instrucoes(sys.modules[__name__]), "ferramentas": ferramentas.lista()})


def r_ferramentas_usar(h, query):
    """Uma ferramenta chamada pelo CorrerIA: {nome, argumentos, pessoa, cliente} → {texto}. As de gravar passam pelo Store
    (a rev sobe, a versão automática, a tela atualiza sozinha). 400: argumento inválido (a IA lê e tenta de novo)."""
    corpo = h.read_body()
    nome = str(corpo.get("nome") or "")
    cliente = " ".join(str(corpo.get("cliente") or "").split())[:40] or "CorrerIA"
    pessoa = corpo.get("pessoa") if isinstance(corpo.get("pessoa"), dict) else {}
    try:
        write_json_atomic(os.path.join(DATA_DIR, "correria_uso.json"), {"app": cliente, "em": now_iso(), "nome": nome[:40]})
    except OSError:
        pass
    try:
        texto = ferramentas.chamar(sys.modules[__name__], nome, corpo.get("argumentos"), pessoa, cliente)
    except LookupError as e:
        raise ApiError(404, str(e)) from None
    except ferramentas.ErroFerramenta as e:
        raise ApiError(400, str(e)) from None
    if ferramentas.POR_NOME[nome]["grava"]:
        quem = " ".join(str(pessoa.get("nome") or "").split())[:40]
        log.info("CorrerIA: %s%s %s → %s", cliente, f" ({quem})" if quem else "", nome, texto.split("\n")[0][:160])
    h.send_json({"texto": texto})


def r_integracao_comodos(h, query):
    with STORE.lock:
        rooms, items = visible_data()  # com Usar bens desligado, a área Bens não vai para os outros apps
        rooms = sorted(rooms, key=lambda r: r.get("order", 0))
        conta = {}
        for it in items:
            conta[it.get("room")] = conta.get(it.get("room"), 0) + 1
        out = [{"id": r["id"], "nome": r.get("name") or r["id"], "codigo": r.get("code") or "", "itens": conta.get(r["id"], 0),
                **({"tipo": "bens"} if r.get("kind") == "bens" else {})} for r in rooms]  # Bens: o que fica fora de casa
    h.send_json({"versao": VERSION, "comodos": out})


def r_integracao_itens(h, query):
    """Os itens (equipamentos, móveis…), para os outros apps: o ResolvIA liga uma tarefa a um deles; o GerencIA soma os valores
    no patrimônio (com a data do valor, para depreciar)."""
    with STORE.lock:
        rooms, items = visible_data()  # com Usar bens desligado, os bens não entram no patrimônio do GerencIA
        order = {r["id"]: r.get("order", 0) for r in rooms}
        items = sorted(items, key=lambda it: (order.get(it.get("room"), 999), (it.get("name") or "").lower()))
        out = [{"id": it["id"], "nome": (it.get("name") or "")[:120], "comodo": it.get("room") or "", "zona": (it.get("zone") or "")[:60],
                "categoria": it.get("cat") or "outros", "valor": round(float(it.get("value") or 0), 2),
                "valor_em": str(it.get("valueAt") or it.get("createdAt") or "")[:10]} for it in items if it.get("id")]
        cats = STORE.cat_map()  # as categorias da casa (editáveis em Mais > Categorias)
    h.send_json({"versao": VERSION, "itens": out[:2000], "categorias": cats})


ROUTES = [(m, re.compile(p), fn) for m, p, fn in [
    ("GET", r"/api/data", r_data),
    ("GET", r"/api/rev", r_rev),
    ("GET", r"/api/health", r_health),
    ("GET", r"/api/integracao/comodos", r_integracao_comodos),
    ("GET", r"/api/integracao/itens", r_integracao_itens),
    ("GET", r"/api/integracao/ferramentas", r_ferramentas_lista),
    ("POST", r"/api/integracao/ferramentas", r_ferramentas_usar),
    ("POST", r"/api/items", r_item_create),
    ("POST", r"/api/items/batch", r_items_batch),
    ("POST", r"/api/items/bulk", r_items_bulk),
    ("PUT", r"/api/items/([A-Za-z0-9_-]+)", r_item_update),
    ("DELETE", r"/api/items/([A-Za-z0-9_-]+)", r_item_delete),
    ("POST", r"/api/cats", r_cat_create),
    ("PUT", r"/api/cats/([a-z0-9_-]+)", r_cat_update),
    ("DELETE", r"/api/cats/([a-z0-9_-]+)", r_cat_delete),
    ("POST", r"/api/rooms", r_room_create),
    ("POST", r"/api/rooms/order", r_rooms_order),
    ("PUT", r"/api/rooms/([A-Za-z0-9_-]+)", r_room_update),
    ("DELETE", r"/api/rooms/([A-Za-z0-9_-]+)", r_room_delete),
    ("POST", r"/api/rooms/([A-Za-z0-9_-]+)/photos", r_room_photo),
    ("POST", r"/api/photos", r_photo),
    ("GET", r"/api/ai/status", r_ai_status),
    ("POST", r"/api/ai/identify", r_ai_identify),
    ("GET", r"/api/ai/usage", r_ai_usage),
    ("POST", r"/api/ai/text", r_ai_text),
    ("GET", r"/api/voice/status", r_voice_status),
    ("POST", r"/api/voice", r_voice),
    ("POST", r"/api/web-photos", r_web_start),
    ("GET", r"/api/web-photos/([a-f0-9]{16})", r_web_status),
    ("GET", r"/api/web-photos/([a-f0-9]{16})/(\d)", r_web_image),
    ("DELETE", r"/api/web-photos/([a-f0-9]{16})", r_web_cancel),
    ("POST", r"/api/chat", r_chat),
    ("GET", r"/api/news", r_news_overview),
    ("POST", r"/api/news", r_news_start),
    ("DELETE", r"/api/news", r_news_clear),
    ("POST", r"/api/news/all", r_news_all),
    ("GET", r"/api/news/people", r_news_people),
    ("POST", r"/api/news/notify-test", r_news_notify_test),
    ("GET", r"/api/news/([a-f0-9]{16})", r_news_status),
    ("DELETE", r"/api/news/([a-f0-9]{16})", r_news_cancel),
    ("GET", r"/api/settings", r_settings_get),
    ("PUT", r"/api/settings", r_settings_put),
    ("GET", r"/api/export\.(csv|json|zip)", r_export),
    ("GET", r"/api/relatorio\.pdf", r_relatorio_pdf),
    ("GET", r"/api/backups", r_backups),
    ("POST", r"/api/backups", r_backup_create),
    ("POST", r"/api/backups/restore", r_backup_restore),
    ("POST", r"/api/import", r_import),
    ("POST", r"/api/upload", r_upload_start),
    ("PUT", r"/api/upload/([a-f0-9]{16})", r_upload_chunk),
    ("GET", r"/api/upload/([a-f0-9]{16})", r_upload_info),
    ("POST", r"/api/upload/([a-f0-9]{16})/restore", r_upload_restore),
    ("DELETE", r"/api/upload/([a-f0-9]{16})", r_upload_cancel),
    ("GET", r"/api/history", r_history),
    ("POST", r"/api/history/restore", r_history_restore),
]]


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    STORE.load()
    cleanup_uploads()
    web_jobs_cleanup(max_age=0)
    threading.Thread(target=usage_sensor_loop, daemon=True).start()
    threading.Thread(target=news_auto_loop, daemon=True).start()
    threading.Thread(target=conexao_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    log.info("InventarIA %s ouvindo na porta %d%s", VERSION, PORT, " (modo dev)" if DEV else "")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
