#!/usr/bin/env python3
"""Evolog U14 — mac bildirimi gonderici.

Senkronizasyondan hemen sonra calisir. Iki tur bildirim uretir:

  * hatirlatma — kendi macimizin baslamasina 4 saatten az kaldiysa
  * sonuc      — mac oynanmis olarak isaretlendiginde, skorla birlikte

Ayni olay icin bir kez gonderilir; gonderilenler notified.json'da tutulur.
Artik gecerli olmayan abonelikler (404/410) listeden dusurulur.

Kullanim:
    python3 server/evolog_push.py              # olaylari bul ve gonder
    python3 server/evolog_push.py --dry-run    # ne gonderilecegini yaz
    python3 server/evolog_push.py --keys       # VAPID anahtarlarini uret/goster
    python3 server/evolog_push.py --test       # abonelere deneme bildirimi
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import sys

STATE_DIR = pathlib.Path(os.environ.get("EVOLOG_STATE_DIR", "/var/lib/evolog"))
LEAGUE_PATH = pathlib.Path(os.environ.get("EVOLOG_LEAGUE",
                                          "/var/www/evolog/data/league.json"))
SUBS = STATE_DIR / "subs.json"
NOTIFIED = STATE_DIR / "notified.json"
VAPID_JSON = STATE_DIR / "vapid.json"
VAPID_PEM = STATE_DIR / "vapid_private.pem"

CONTACT = os.environ.get("EVOLOG_PUSH_CONTACT", "mailto:monspro34@gmail.com")
APP_URL = os.environ.get("EVOLOG_APP_URL", "https://evolog.213-159-6-115.sslip.io/evolog/")
REMINDER_HOURS = float(os.environ.get("EVOLOG_REMINDER_HOURS", "4"))
TZ = dt.timezone(dt.timedelta(hours=3))


def read_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


# -------------------------------------------------------------------- VAPID
def ensure_keys() -> dict:
    """VAPID anahtar cifti yoksa uretir. Public anahtar tarayiciya gider."""
    keys = read_json(VAPID_JSON, {})
    if keys.get("publicKey") and VAPID_PEM.exists():
        return keys

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private = ec.generate_private_key(ec.SECP256R1())
    VAPID_PEM.parent.mkdir(parents=True, exist_ok=True)
    VAPID_PEM.write_bytes(private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    VAPID_PEM.chmod(0o600)

    raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    keys = {"publicKey": base64.urlsafe_b64encode(raw).rstrip(b"=").decode()}
    write_json(VAPID_JSON, keys)
    VAPID_JSON.chmod(0o644)      # public anahtar; servis okuyup yayinliyor
    return keys


# ------------------------------------------------------------------ olaylar
def our_side(fixture: dict, our_key: str):
    """Maçta bizim taraf ev sahibi mi? (skorlari dogru yorumlamak icin)"""
    home = (fixture.get("home") or "").lower()
    return our_key in home


def build_events(league: dict) -> list[dict]:
    our_key = (league.get("ourTeamKey") or "evolog").lower()
    now = dt.datetime.now(TZ)
    events = []

    for f in league.get("fixtures") or []:
        if not f.get("isOurs"):
            continue
        mid = f.get("matchId")
        if not mid:
            continue

        home, away = f.get("home") or "", f.get("away") or ""
        we_home = our_side(f, our_key)
        opp = away if we_home else home

        if f.get("played") and f.get("homeScore") is not None:
            ours = f["homeScore"] if we_home else f["awayScore"]
            theirs = f["awayScore"] if we_home else f["homeScore"]
            if ours > theirs:
                title = f"Kazandık! {ours}-{theirs}"
            elif ours < theirs:
                title = f"Maç bitti: {ours}-{theirs}"
            else:
                title = f"Maç berabere: {ours}-{theirs}"
            events.append({
                "id": f"result-{mid}",
                "title": title,
                "body": f"{home} {f['homeScore']} - {f['awayScore']} {away}",
                "tag": f"mac-{mid}",
            })
            continue

        # Oynanmamis mac: baslamasina REMINDER_HOURS'tan az kaldiysa hatirlat.
        if not f.get("date"):
            continue
        try:
            clock = f.get("time") or "00:00"
            start = dt.datetime.strptime(f"{f['date']} {clock}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        except ValueError:
            continue
        hours_left = (start - now).total_seconds() / 3600
        if 0 < hours_left <= REMINDER_HOURS:
            when = start.strftime("%H:%M")
            where = f.get("venue") or ""
            events.append({
                "id": f"reminder-{mid}",
                "title": f"Bugün {when} · {opp}",
                "body": ("Maça yaklaşık " + str(int(round(hours_left))) + " saat kaldı"
                         + (f" · {where}" if where else "")),
                "tag": f"mac-{mid}",
            })

    return events


# ---------------------------------------------------------------- gonderim
def send_all(events: list[dict], dry: bool) -> int:
    subs = read_json(SUBS, [])
    if not subs:
        print("Abone yok, gonderilecek bir sey yok.")
        return 0
    if dry:
        for e in events:
            print(f"  [deneme] {e['title']} — {e['body']}  ({len(subs)} abone)")
        return 0

    from pywebpush import WebPushException, webpush

    keys = ensure_keys()
    del keys
    private_pem = VAPID_PEM.read_text()
    alive, sent = [], 0

    for sub in subs:
        drop = False
        for e in events:
            payload = json.dumps({
                "title": e["title"], "body": e["body"],
                "tag": e["tag"], "url": APP_URL,
            }, ensure_ascii=False)
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": sub.get("keys") or {}},
                    data=payload,
                    vapid_private_key=private_pem,
                    vapid_claims={"sub": CONTACT},
                    timeout=20,
                )
                sent += 1
            except WebPushException as exc:
                code = getattr(exc.response, "status_code", None)
                if code in (404, 410):
                    drop = True          # abonelik artik gecersiz
                    break
                print(f"  uyari: gonderilemedi ({code}): {exc}")
            except Exception as exc:
                print(f"  uyari: {type(exc).__name__}: {exc}")
        if not drop:
            alive.append(sub)

    if len(alive) != len(subs):
        write_json(SUBS, alive)
        print(f"  {len(subs) - len(alive)} gecersiz abonelik dusuruldu")
    return sent


def main() -> int:
    ap = argparse.ArgumentParser(description="Evolog mac bildirimleri")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keys", action="store_true", help="VAPID anahtarlarini uret/goster")
    ap.add_argument("--test", action="store_true", help="abonelere deneme bildirimi gonder")
    args = ap.parse_args()

    keys = ensure_keys()
    if args.keys:
        print("VAPID public key:", keys["publicKey"])
        return 0

    if args.test:
        send_all([{
            "id": "test", "tag": "test",
            "title": "Evolog U14 Kız Siyah",
            "body": "Bildirimler çalışıyor. Maç öncesi ve sonrası haber vereceğiz.",
        }], args.dry_run)
        return 0

    league = read_json(LEAGUE_PATH, {})
    if not league:
        print("league.json okunamadi.")
        return 1

    done = read_json(NOTIFIED, {})
    events = [e for e in build_events(league) if e["id"] not in done]
    if not events:
        print("Yeni bildirim yok.")
        return 0

    sent = send_all(events, args.dry_run)
    if not args.dry_run:
        stamp = dt.datetime.now(TZ).isoformat(timespec="seconds")
        for e in events:
            done[e["id"]] = stamp
        write_json(NOTIFIED, done)
    print(f"{len(events)} olay, {sent} gonderim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
