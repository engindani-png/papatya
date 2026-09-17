#!/usr/bin/env python3
"""Yoklama — SQLite tabanli kayit, ozet ve devamsizlik dokumu.

Veritabani `/var/lib/evolog/evolog.db` (git agacinin disi; senkron
`git reset --hard` yapiyor, depoda duran her sey silinirdi). Ayni dosya
ileride uyelik sisteminin de yeri olacak (bkz. docs/superpowers/specs).

Tablolar:
    yoklama        (yas, tarih, saat) -> antrenmanin kendisi
    yoklama_kayit  (yas, tarih, saat, oyuncu) -> durum
    duyuru         antrenorun gonderdigi bildirimlerin kaydi

Oyuncu anahtari TBF oyuncu numarasidir (`tbfPlayerId`); isim degisse de kayit
bozulmaz. Numarasi olmayan oyuncu icin kucuk harfe indirilmis ad kullanilir.

Onceki surumde kayitlar `attendance-<yas>.json` dosyasindaydi; ilk acilista
otomatik olarak veritabanina tasinir (bkz. `_json_tasi`).
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sqlite3

TZ = dt.timezone(dt.timedelta(hours=3))

# Antrenor bir dokunusla isaretliyor; dordu de tek satira sigsin diye kisa.
DURUMLAR = ("geldi", "gec", "gelmedi", "izinli")
# Devam yuzdesi hesabinda "izinli" pay disi kalir: mazeretli devamsizlik
# sporcuyu cezalandirmamali.
SAYILAN = ("geldi", "gec", "gelmedi")
GELMIS = ("geldi", "gec")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

SEMA = """
CREATE TABLE IF NOT EXISTS yoklama (
  yas     TEXT NOT NULL,
  tarih   TEXT NOT NULL,
  saat    TEXT NOT NULL,
  baslik  TEXT,
  salon   TEXT,
  alindi  TEXT,
  PRIMARY KEY (yas, tarih, saat)
);
CREATE TABLE IF NOT EXISTS yoklama_kayit (
  yas     TEXT NOT NULL,
  tarih   TEXT NOT NULL,
  saat    TEXT NOT NULL,
  oyuncu  TEXT NOT NULL,
  durum   TEXT NOT NULL,
  PRIMARY KEY (yas, tarih, saat, oyuncu)
);
CREATE INDEX IF NOT EXISTS ix_kayit_oyuncu ON yoklama_kayit (yas, oyuncu);
CREATE TABLE IF NOT EXISTS duyuru (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  yas      TEXT,
  baslik   TEXT,
  metin    TEXT,
  gonderim INTEGER,
  zaman    TEXT
);
"""


def db_path(state_dir) -> pathlib.Path:
    return pathlib.Path(state_dir) / "evolog.db"


def baglan(state_dir) -> sqlite3.Connection:
    yol = db_path(state_dir)
    yol.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(yol), timeout=10)
    con.row_factory = sqlite3.Row
    con.executescript(SEMA)
    return con


def _json_tasi(state_dir, yas: str, con: sqlite3.Connection) -> int:
    """Eski attendance-<yas>.json dosyasini bir kez veritabanina tasir."""
    eski = pathlib.Path(state_dir) / f"attendance-{yas}.json"
    if not eski.exists():
        return 0
    try:
        veri = json.loads(eski.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    n = 0
    for kayit in (veri.get("sessions") or {}).values():
        try:
            kaydet(state_dir, yas, kayit, con=con, tasima=True)
            n += 1
        except ValueError:
            continue
    eski.rename(eski.with_suffix(".json.tasindi"))
    return n


def hazirla(state_dir, yas: str) -> sqlite3.Connection:
    con = baglan(state_dir)
    _json_tasi(state_dir, yas, con)
    return con


# --------------------------------------------------------------- dogrulama
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


# ------------------------------------------------------------------ yazma
def kaydet(state_dir, yas: str, record: dict, con: sqlite3.Connection | None = None,
           tasima: bool = False) -> dict:
    """Bir antrenmanin yoklamasini yazar (ayni seans tekrar alinirsa gunceller)."""
    kapat = con is None
    con = con or (baglan(state_dir) if tasima else hazirla(state_dir, yas))
    try:
        with con:
            con.execute(
                "INSERT INTO yoklama (yas, tarih, saat, baslik, salon, alindi) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(yas, tarih, saat) DO UPDATE SET "
                "baslik=excluded.baslik, salon=excluded.salon, alindi=excluded.alindi",
                (yas, record["date"], record["start"], record.get("title"),
                 record.get("venue"), record.get("takenAt")))
            con.execute("DELETE FROM yoklama_kayit WHERE yas=? AND tarih=? AND saat=?",
                        (yas, record["date"], record["start"]))
            con.executemany(
                "INSERT INTO yoklama_kayit (yas, tarih, saat, oyuncu, durum) VALUES (?,?,?,?,?)",
                [(yas, record["date"], record["start"], k, v)
                 for k, v in record["players"].items()])
    finally:
        if kapat:
            con.close()
    return record


def duyuru_kaydet(state_dir, yas: str, baslik: str, metin: str, gonderim: int) -> None:
    con = baglan(state_dir)
    try:
        with con:
            con.execute("INSERT INTO duyuru (yas, baslik, metin, gonderim, zaman) "
                        "VALUES (?,?,?,?,?)",
                        (yas, baslik, metin, gonderim,
                         dt.datetime.now(TZ).isoformat(timespec="seconds")))
    finally:
        con.close()


def duyurular(state_dir, yas: str, limit: int = 20) -> list:
    con = baglan(state_dir)
    try:
        return [dict(r) for r in con.execute(
            "SELECT baslik, metin, gonderim, zaman FROM duyuru WHERE yas=? "
            "ORDER BY id DESC LIMIT ?", (yas, limit))]
    finally:
        con.close()


# ------------------------------------------------------------------ okuma
def seanslar(state_dir, yas: str, con: sqlite3.Connection | None = None) -> list:
    """Yoklamasi alinmis antrenmanlar, eskiden yeniye."""
    kapat = con is None
    con = con or hazirla(state_dir, yas)
    try:
        satirlar = con.execute(
            "SELECT tarih, saat, baslik, salon, alindi FROM yoklama WHERE yas=? "
            "ORDER BY tarih, saat", (yas,)).fetchall()
        return [dict(r) for r in satirlar]
    finally:
        if kapat:
            con.close()


def get(state_dir, yas: str, date: str, start: str) -> dict:
    """Tek bir antrenmanin kaydi (uygulamadaki bicimde)."""
    con = hazirla(state_dir, yas)
    try:
        bas = con.execute("SELECT tarih, saat, baslik, salon, alindi FROM yoklama "
                          "WHERE yas=? AND tarih=? AND saat=?", (yas, date, start)).fetchone()
        if not bas:
            return {}
        kayitlar = con.execute("SELECT oyuncu, durum FROM yoklama_kayit "
                               "WHERE yas=? AND tarih=? AND saat=?",
                               (yas, date, start)).fetchall()
        return {"date": bas["tarih"], "start": bas["saat"], "title": bas["baslik"],
                "venue": bas["salon"], "takenAt": bas["alindi"],
                "players": {r["oyuncu"]: r["durum"] for r in kayitlar}}
    finally:
        con.close()


def player_key(player: dict) -> str:
    pid = player.get("tbfPlayerId")
    if pid:
        return str(pid)
    return (player.get("name") or "").strip().lower()


def summary(state_dir, yas: str, players: list, limit: int = 0) -> dict:
    """Oyuncu bazli devam ozeti; en son seanstan geriye dogru `limit` antrenman."""
    con = hazirla(state_dir, yas)
    try:
        hepsi = seanslar(state_dir, yas, con=con)
        if limit:
            hepsi = hepsi[-limit:]
        anahtarlar = {(s["tarih"], s["saat"]) for s in hepsi}

        sayac = {}
        for p in players:
            sayac[player_key(p)] = {
                "key": player_key(p), "no": p.get("no"), "name": p.get("name") or "",
                "geldi": 0, "gec": 0, "gelmedi": 0, "izinli": 0,
            }

        kayitlar = con.execute(
            "SELECT tarih, saat, oyuncu, durum FROM yoklama_kayit WHERE yas=?", (yas,)).fetchall()
        gelen_sayisi = {}
        for r in kayitlar:
            if (r["tarih"], r["saat"]) not in anahtarlar:
                continue
            hedef = sayac.get(r["oyuncu"])
            if hedef is None:          # kadrodan ayrilmis oyuncu: ozette gorunmez
                continue
            hedef[r["durum"]] = hedef.get(r["durum"], 0) + 1
            if r["durum"] in GELMIS:
                gelen_sayisi[(r["tarih"], r["saat"])] = gelen_sayisi.get((r["tarih"], r["saat"]), 0) + 1

        seans_listesi = []
        for s in hepsi:
            anahtar = (s["tarih"], s["saat"])
            toplam = con.execute("SELECT COUNT(*) FROM yoklama_kayit "
                                 "WHERE yas=? AND tarih=? AND saat=?",
                                 (yas, anahtar[0], anahtar[1])).fetchone()[0]
            seans_listesi.append({"date": s["tarih"], "start": s["saat"],
                                  "title": s["baslik"] or "Antrenman",
                                  "gelen": gelen_sayisi.get(anahtar, 0), "toplam": toplam})

        satirlar = []
        for row in sayac.values():
            sayilan = sum(row[d] for d in SAYILAN)
            gelmis = sum(row[d] for d in GELMIS)
            row["oran"] = round(100 * gelmis / sayilan) if sayilan else None
            satirlar.append(row)
        satirlar.sort(key=lambda r: (r["oran"] is None, r["oran"], r["name"]))

        return {"sessions": seans_listesi, "players": satirlar}
    finally:
        con.close()


def oyuncu_dokumu(state_dir, yas: str, anahtar: str, players: list | None = None) -> dict:
    """Tek oyuncunun devamsizlik dokumu.

    Antrenorun sordugu soru "kac gun gelmedi" degil, **nasil gelmedi**:
    ust uste mi, dagilmis mi, mazeretli mi. Doner:

        sessions  [{date, start, title, durum}]  yeniden eskiye
        streak    su an ust uste kacinci antrenmana gelmedi
        enUzun    gecmisteki en uzun ust uste gelmeme
        missed    gelmedigi antrenmanlarin listesi
    """
    con = hazirla(state_dir, yas)
    try:
        hepsi = seanslar(state_dir, yas, con=con)
        durumlar = {(r["tarih"], r["saat"]): r["durum"] for r in con.execute(
            "SELECT tarih, saat, durum FROM yoklama_kayit WHERE yas=? AND oyuncu=?",
            (yas, anahtar))}
    finally:
        con.close()

    ad, no = "", None
    for p in (players or []):
        if player_key(p) == anahtar:
            ad, no = p.get("name") or "", p.get("no")
            break

    liste = []
    for s in hepsi:
        durum = durumlar.get((s["tarih"], s["saat"]))
        if durum is None:
            continue                     # o gun isaretlenmemis: sayilmaz
        liste.append({"date": s["tarih"], "start": s["saat"],
                      "title": s["baslik"] or "Antrenman", "durum": durum})

    # Ust uste gelmeme: en son antrenmandan geriye dogru. "izinli" seriyi
    # bozar (mazeretli), "gec" gelmis sayilir.
    streak = 0
    for k in reversed(liste):
        if k["durum"] == "gelmedi":
            streak += 1
        else:
            break

    en_uzun, o_an = 0, 0
    for k in liste:
        if k["durum"] == "gelmedi":
            o_an += 1
            en_uzun = max(en_uzun, o_an)
        else:
            o_an = 0

    sayilar = {d: sum(1 for k in liste if k["durum"] == d) for d in DURUMLAR}
    sayilan = sum(sayilar[d] for d in SAYILAN)
    gelmis = sum(sayilar[d] for d in GELMIS)

    return {
        "key": anahtar, "name": ad, "no": no,
        "sessions": list(reversed(liste)),
        "missed": [k for k in reversed(liste) if k["durum"] == "gelmedi"],
        "counts": sayilar,
        "oran": round(100 * gelmis / sayilan) if sayilan else None,
        "streak": streak,
        "enUzun": en_uzun,
        "toplam": len(liste),
    }
