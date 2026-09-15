#!/usr/bin/env python3
"""Evolog U14 — kucuk kayit servisi.

Statik uygulamanin yazmaya ihtiyac duydugu tek seyler icin:
  * antrenman programi (WhatsApp metninden cozumlenip kaydedilir)
  * mac bildirimi abonelikleri (web push)

Veriler /var/lib/evolog altinda tutulur — git agacinin disinda, boylece
10 dakikada bir calisan "git reset --hard" senkronu bunlari silmez.

Yalnizca Python standart kutuphanesi kullanir.

Ortam degiskenleri:
  EVOLOG_STATE_DIR   varsayilan /var/lib/evolog
  EVOLOG_ADMIN_PASS  yonetim sifresi (zorunlu)
  EVOLOG_PORT        varsayilan 8106
"""

from __future__ import annotations

import hmac
import json
import os
import pathlib
import re
import threading
import urllib.parse
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE_DIR = pathlib.Path(os.environ.get("EVOLOG_STATE_DIR", "/var/lib/evolog"))
ADMIN_PASS = os.environ.get("EVOLOG_ADMIN_PASS", "")
PORT = int(os.environ.get("EVOLOG_PORT", "8106"))
MAX_BODY = 512 * 1024

SUBS = STATE_DIR / "subs.json"
VAPID = STATE_DIR / "vapid.json"

# Yas gruplari: her birinin kendi antrenman programi var. Listeyi ortam
# degiskeniyle genisletebilirsiniz (yeni yas acilinca tek satir).
AGES = tuple(a.strip() for a in os.environ.get("EVOLOG_AGES", "u14,u16,u18").split(",") if a.strip())
DEFAULT_AGE = AGES[0] if AGES else "u14"


def age_of(handler) -> str:
    """Sorgudaki ?age=... degerini dogrular. Bilinmeyen/eksikse varsayilan."""
    query = urllib.parse.urlparse(handler.path).query
    value = (urllib.parse.parse_qs(query).get("age") or [""])[0].strip().lower()
    return value if value in AGES else DEFAULT_AGE


def training_path(age: str) -> pathlib.Path:
    return STATE_DIR / f"training-{age}.json"


def clean_ages(value) -> list:
    """Bildirim icin secilen yas listesi; bilinmeyenler atilir."""
    if not isinstance(value, list):
        return []
    out = [str(v).strip().lower() for v in value[:10]]
    return [a for a in dict.fromkeys(out) if a in AGES]

_lock = threading.Lock()
_fails: dict[str, list] = {}


def read_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


# ------------------------------------------------------------------ dogrulama
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_str(value, limit=120):
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] or None


def validate_training(payload):
    """Gelen antrenman programini temizler. Hatali ise ValueError firlatir."""
    if not isinstance(payload, dict):
        raise ValueError("Beklenen bicim: nesne")

    venues = []
    for v in (payload.get("venues") or [])[:30]:
        if not isinstance(v, dict):
            continue
        vid = clean_str(v.get("id"), 40)
        name = clean_str(v.get("name"), 120)
        if not vid or not name:
            continue
        maps = clean_str(v.get("maps"), 400)
        if maps and not maps.startswith(("https://", "http://")):
            maps = None
        color = clean_str(v.get("color"), 9)
        if color and not re.match(r"^#[0-9a-fA-F]{6}$", color):
            color = None
        venues.append({"id": vid, "name": name,
                       "address": clean_str(v.get("address"), 200),
                       "maps": maps, "color": color})

    sessions = []
    for s in (payload.get("sessions") or [])[:40]:
        if not isinstance(s, dict):
            continue
        try:
            day = int(s.get("day"))
        except (TypeError, ValueError):
            continue
        start = clean_str(s.get("start"), 5)
        if not (1 <= day <= 7) or not start or not TIME_RE.match(start):
            continue
        end = clean_str(s.get("end"), 5)
        if end and not TIME_RE.match(end):
            end = None
        sessions.append({"day": day, "start": start, "end": end,
                         "venue": clean_str(s.get("venue"), 40),
                         "title": clean_str(s.get("title"), 80) or "Antrenman",
                         "coach": clean_str(s.get("coach"), 80)})
    if not sessions:
        raise ValueError("En az bir gecerli antrenman gerekli")

    exceptions = []
    for e in (payload.get("exceptions") or [])[:60]:
        if not isinstance(e, dict):
            continue
        date = clean_str(e.get("date"), 10)
        if not date or not DATE_RE.match(date):
            continue
        exceptions.append({"date": date,
                           "type": clean_str(e.get("type"), 40) or "iptal",
                           "reason": clean_str(e.get("reason"), 160)})

    return {
        "note": "Antrenman programi uygulamadaki yonetim ekranindan kaydedilir. day 1=Pazartesi ... 7=Pazar.",
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S+03:00", time.localtime()),
        "venues": venues,
        "sessions": sessions,
        "exceptions": exceptions,
    }


def authorized(handler) -> bool:
    """Sabit zamanli sifre kontrolu + kaba kuvvete karsi basit yavaslatma."""
    if not ADMIN_PASS:
        return False
    ip = handler.client_address[0]
    now = time.time()
    recent = [t for t in _fails.get(ip, []) if now - t < 300]
    _fails[ip] = recent
    if len(recent) >= 8:
        return False
    header = handler.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else ""
    if hmac.compare_digest(token, ADMIN_PASS):
        _fails[ip] = []
        return True
    _fails[ip] = recent + [now]
    return False


# -------------------------------------------------------------------- sunucu
class Handler(BaseHTTPRequestHandler):
    server_version = "evolog/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # nginx zaten kaydediyor
        pass

    def send_json(self, code: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            raise ValueError("Gecersiz govde boyutu")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    # --------------------------------------------------------------- GET
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            return self.send_json(200, {"ok": True, "hasPass": bool(ADMIN_PASS)})
        if path == "/api/training":
            return self.send_json(200, read_json(training_path(age_of(self)), None) or {})
        if path == "/api/push/key":
            keys = read_json(VAPID, {})
            return self.send_json(200, {"publicKey": keys.get("publicKey")})
        return self.send_json(404, {"error": "yok"})

    # --------------------------------------------------------------- POST
    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/auth":
                # Yonetim ekrani girisi: sifreyi kaydetmeden once dogrular.
                if not authorized(self):
                    return self.send_json(401, {"error": "Sifre hatali"})
                return self.send_json(200, {"ok": True})

            if path == "/api/training":
                if not authorized(self):
                    return self.send_json(401, {"error": "Sifre hatali"})
                age = age_of(self)
                data = validate_training(self.body_json())
                with _lock:
                    write_json(training_path(age), data)
                return self.send_json(200, {"ok": True, "age": age,
                                            "sessions": len(data["sessions"])})

            if path == "/api/push/subscribe":
                sub = self.body_json()
                endpoint = (sub or {}).get("endpoint")
                if not endpoint or not str(endpoint).startswith("https://"):
                    return self.send_json(400, {"error": "Gecersiz abonelik"})
                ages = clean_ages(sub.get("ages")) or [DEFAULT_AGE]
                with _lock:
                    subs = read_json(SUBS, [])
                    subs = [s for s in subs if s.get("endpoint") != endpoint]
                    subs.append({"endpoint": endpoint, "keys": sub.get("keys") or {},
                                 "ages": ages,
                                 "addedAt": time.strftime("%Y-%m-%dT%H:%M:%S")})
                    write_json(SUBS, subs[-500:])
                return self.send_json(200, {"ok": True, "ages": ages})

            if path == "/api/push/unsubscribe":
                endpoint = (self.body_json() or {}).get("endpoint")
                with _lock:
                    subs = [s for s in read_json(SUBS, []) if s.get("endpoint") != endpoint]
                    write_json(SUBS, subs)
                return self.send_json(200, {"ok": True})

        except ValueError as exc:
            return self.send_json(400, {"error": str(exc)})
        except Exception:
            return self.send_json(500, {"error": "Sunucu hatasi"})

        return self.send_json(404, {"error": "yok"})


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
