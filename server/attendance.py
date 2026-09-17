#!/usr/bin/env python3
"""Yoklama kaydi — antrenman seansi basina bir kayit.

Veri, git agacinin disinda `/var/lib/evolog/attendance-<yas>.json` icinde durur
(senkronizasyon `git reset --hard` yapiyor, depoda duran her sey silinir).

Bicim:

    {
      "sessions": {
        "2026-09-18T19:30": {
          "date": "2026-09-18", "start": "19:30",
          "title": "Basketbol", "venue": "tev",
          "takenAt": "2026-09-18T21:05:00+03:00",
          "players": { "750529": "geldi", "750530": "izinli" }
        }
      }
    }

Oyuncu anahtari TBF oyuncu numarasidir (`tbfPlayerId`); isim degisse de kayit
bozulmaz. Numarasi olmayan oyuncu icin ad kullanilir.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

TZ = dt.timezone(dt.timedelta(hours=3))

# Antrenor bir dokunusla isaretliyor; dordu de tek satira sigsin diye kisa.
DURUMLAR = ("geldi", "gec", "gelmedi", "izinli")
# Devam yuzdesi hesabinda "izinli" pay disi kalir: mazeretli devamsizlik
# sporcuyu cezalandirmamali.
SAYILAN = ("geldi", "gec", "gelmedi")
GELMIS = ("geldi", "gec")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def path(state_dir: pathlib.Path, age: str) -> pathlib.Path:
    return pathlib.Path(state_dir) / f"attendance-{age}.json"


def load(state_dir: pathlib.Path, age: str) -> dict:
    try:
        data = json.loads(path(state_dir, age).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sessions": {}}
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
        return {"sessions": {}}
    return data


def session_key(date: str, start: str) -> str:
    return f"{date}T{start}"


def player_key(player: dict) -> str:
    """Oyuncunun kalici anahtari: TBF numarasi, yoksa adi."""
    pid = player.get("tbfPlayerId")
    if pid:
        return str(pid)
    return (player.get("name") or "").strip().lower()


def validate(payload) -> dict:
    """Gelen yoklama kaydini temizler. Hatali ise ValueError firlatir."""
    if not isinstance(payload, dict):
        raise ValueError("Beklenen bicim: nesne")

    date = str(payload.get("date") or "").strip()
    start = str(payload.get("start") or "").strip()
    if not DATE_RE.match(date):
        raise ValueError("Tarih gecersiz (YYYY-AA-GG)")
    if not TIME_RE.match(start):
        raise ValueError("Saat gecersiz (SS:DD)")

    gelen = payload.get("players")
    if not isinstance(gelen, dict) or not gelen:
        raise ValueError("En az bir oyuncu isaretlenmeli")

    players = {}
    for key, durum in list(gelen.items())[:60]:
        key = str(key).strip()[:60]
        durum = str(durum).strip().lower()
        if key and durum in DURUMLAR:
            players[key] = durum
    if not players:
        raise ValueError("En az bir oyuncu isaretlenmeli")

    return {
        "date": date,
        "start": start,
        "title": (str(payload.get("title") or "").strip() or "Antrenman")[:80],
        "venue": (str(payload.get("venue") or "").strip() or None),
        "takenAt": dt.datetime.now(TZ).isoformat(timespec="seconds"),
        "players": players,
    }


def save(state_dir: pathlib.Path, age: str, record: dict) -> dict:
    """Kaydi dosyaya yazar (ayni seans tekrar alinirsa uzerine yazar)."""
    data = load(state_dir, age)
    data["sessions"][session_key(record["date"], record["start"])] = record
    target = path(state_dir, age)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(target)
    return data


def get(state_dir: pathlib.Path, age: str, date: str, start: str) -> dict:
    return load(state_dir, age)["sessions"].get(session_key(date, start)) or {}


def summary(state_dir: pathlib.Path, age: str, players: list, limit: int = 0) -> dict:
    """Oyuncu bazli devam ozeti; en son seanstan geriye dogru `limit` antrenman.

    limit=0 -> tum kayitlar. Doner:
        {"sessions": [{date,start,title,gelen,toplam}...],
         "players": [{key,no,name,geldi,gec,gelmedi,izinli,oran}...]}
    """
    data = load(state_dir, age)
    kayitlar = sorted(data["sessions"].values(), key=lambda r: session_key(r["date"], r["start"]))
    if limit:
        kayitlar = kayitlar[-limit:]

    sayac = {}
    for p in players:
        sayac[player_key(p)] = {
            "key": player_key(p), "no": p.get("no"), "name": p.get("name") or "",
            "geldi": 0, "gec": 0, "gelmedi": 0, "izinli": 0,
        }

    seanslar = []
    for r in kayitlar:
        gelen = 0
        for key, durum in (r.get("players") or {}).items():
            hedef = sayac.get(key)
            if hedef is None:      # kadrodan ayrilmis oyuncu: ozette gosterilmez
                continue
            hedef[durum] = hedef.get(durum, 0) + 1
            if durum in GELMIS:
                gelen += 1
        seanslar.append({"date": r["date"], "start": r["start"],
                         "title": r.get("title") or "Antrenman",
                         "gelen": gelen, "toplam": len(r.get("players") or {})})

    satirlar = []
    for row in sayac.values():
        sayilan = sum(row[d] for d in SAYILAN)
        gelmis = sum(row[d] for d in GELMIS)
        row["oran"] = round(100 * gelmis / sayilan) if sayilan else None
        satirlar.append(row)
    satirlar.sort(key=lambda r: (r["oran"] is None, r["oran"], r["name"]))

    return {"sessions": seanslar, "players": satirlar}
