#!/usr/bin/env python3
"""Evolog — veli bildirimi gonderici (mac + antrenman).

Senkronizasyondan hemen sonra calisir. Iki tur bildirim uretir:

  * hatirlatma — kendi macimizin baslamasina 4 saatten az kaldiysa
  * sonuc      — mac oynanmis olarak isaretlendiginde, skorla birlikte
  * degisiklik — macin gun/saati degistiginde
  * antrenman  — haftalik antrenman programi degistiginde

Ayni olay icin bir kez gonderilir; gonderilenler notified.json'da tutulur.
Artik gecerli olmayan abonelikler (404/410) listeden dusurulur.

Kullanim:
    python3 server/evolog_push.py              # tum yas gruplarini tara ve gonder
    python3 server/evolog_push.py --dry-run    # ne gonderilecegini yaz
    python3 server/evolog_push.py --keys       # VAPID anahtarlarini uret/goster
    python3 server/evolog_push.py --test       # abonelere deneme bildirimi
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys

STATE_DIR = pathlib.Path(os.environ.get("EVOLOG_STATE_DIR", "/var/lib/evolog"))
DATA_DIR = pathlib.Path(os.environ.get("EVOLOG_DATA_DIR", "/var/www/evolog/data"))
AGES = tuple(a.strip() for a in os.environ.get("EVOLOG_AGES", "u14").split(",") if a.strip())
DEFAULT_AGE = AGES[0] if AGES else "u14"
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


def load_leagues() -> list[tuple[str, dict]]:
    """Her yas grubunun league.json dosyasini okur. Eksik olan atlanir."""
    out = []
    for age in AGES:
        league = read_json(DATA_DIR / age / "league.json", {})
        if league:
            out.append((age, league))
        else:
            print(f"  uyari: {age} league.json okunamadi, atlandi.")
    return out


GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def fmt_gun(date_str: str, time_str: str | None) -> str:
    """2026-09-23, 20:00 -> '23 Eylül Çarşamba 20:00'"""
    try:
        d = dt.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return date_str or "?"
    out = f"{d.day} {AYLAR[d.month - 1]} {GUNLER[d.weekday()]}"
    return f"{out} {time_str}" if time_str else out


# --------------------------------------------------------------- antrenman
def training_path(age: str) -> pathlib.Path:
    return STATE_DIR / f"training-{age}.json"


def training_seen_path(age: str) -> pathlib.Path:
    """En son bildirilen program; degisikligi bununla karsilastiriyoruz."""
    return STATE_DIR / f"training-seen-{age}.json"


def training_by_day(program: dict) -> dict:
    """{gun: ["19:30 Basketbol (Tev)", ...]} — karsilastirma ve metin icin."""
    isim = {v.get("id"): v.get("name") for v in (program.get("venues") or []) if isinstance(v, dict)}
    gunler: dict = {}
    for s_ in (program.get("sessions") or []):
        if not isinstance(s_, dict):
            continue
        try:
            day = int(s_.get("day"))
        except (TypeError, ValueError):
            continue
        salon = isim.get(s_.get("venue")) or ""
        satir = f"{s_.get('start') or ''} {s_.get('title') or 'Antrenman'}".strip()
        if salon:
            satir += f" ({salon})"
        gunler.setdefault(day, []).append(satir)
    for day in gunler:
        gunler[day].sort()
    return gunler


# Ayni duyurunun tekrar gonderilmemesi icin pencere. Sonsuza dek engellemek
# YANLIS olur: kocun ayni hatirlatmayi gelecek hafta tekrar gondermesi mesru.
DUYURU_TEKRAR_DK = 10


def duyuru_tekrar_mi(done: dict, olay_id: str, simdi: float | None = None,
                     pencere_dk: int = DUYURU_TEKRAR_DK) -> bool:
    """Ayni duyuru pencere icinde zaten gitti mi?

    Kodda "ayni metin iki kez gonderilmez" yorumu vardi ama kontrol HIC
    yapilmiyordu: `done` okunuyor, gonderimden SONRA yaziliyor, ama gondermeden
    once bakilmiyordu (kiyas: fikstur yolunda `e["id"] not in done` var).
    Sonuc: ayni metin her cagrida yeniden gidiyordu. CP kopru ucu zaman
    asiminda tekrar denerse veliler cift bildirim alirdi.
    """
    kayit = done.get(olay_id)
    if not kayit:
        return False
    try:
        gonderildi = dt.datetime.fromisoformat(kayit)
    except (ValueError, TypeError):
        return False          # okunamayan kayit mesru duyuruyu bloklamasin
    simdi_dt = (dt.datetime.fromtimestamp(simdi, TZ) if simdi is not None
                else dt.datetime.now(TZ))
    return (simdi_dt - gonderildi).total_seconds() < pencere_dk * 60


def bildirim_govdesi(metin: str, sinir: int = 180) -> str:
    """Bildirime giden ozet.

    Telefon zaten kesiyor (Android kapali bildirimde ~2 satir). Kesmeyi
    isletim sistemine birakmak yerine KASITLI kisaltiyoruz: boylece kesik
    yerde kelime ortadan bolunmez ve ucnokta veliye "devami var" der.
    Tam metin veritabaninda durur, uygulamadaki Duyurular ekraninda okunur.
    """
    metin = " ".join((metin or "").split())
    if len(metin) <= sinir:
        return metin
    kirp = metin[:sinir]
    bosluk = kirp.rfind(" ")
    if bosluk > sinir * 0.6:          # kelimeyi ortadan bolme
        kirp = kirp[:bosluk]
    return kirp.rstrip(" ,.;:-") + "…"


def training_summary(onceki: dict, yeni: dict) -> list[str]:
    """Bildirim metni: programin KALAN gunleri, veli diliyle.

    WhatsApp'tan gelen duyuru da boyle okunuyor ("Cuma 19:30 ... Cumartesi OFF"),
    velinin kafasinda soru birakmiyor. Gecmis gunler yazilmaz; antrenmani
    kaldirilan gun "antrenman yok" diye gorunur.
    """
    a, b = training_by_day(onceki), training_by_day(yeni)

    # Program bu haftaya aitse bugunden itibaren yaz; gelecek haftaninsa tumu.
    bugun = dt.datetime.now(TZ).date()
    bu_pazartesi = (bugun - dt.timedelta(days=bugun.weekday())).isoformat()
    ilk_gun = bugun.weekday() + 1 if (yeni.get("weekStart") or bu_pazartesi) == bu_pazartesi else 1

    # Bugunun antrenmani baslamissa artik onu duyurmanin anlami yok.
    if ilk_gun == bugun.weekday() + 1:
        saatler = [x.split(" ")[0] for x in (a.get(ilk_gun) or []) + (b.get(ilk_gun) or [])]
        if saatler and max(saatler) <= dt.datetime.now(TZ).strftime("%H:%M"):
            ilk_gun += 1

    satirlar = []
    for day in range(ilk_gun, 8):
        simdiki, eskisi = b.get(day) or [], a.get(day) or []
        ad = GUNLER[day - 1]
        if simdiki:
            satirlar.append(f"{ad} {', '.join(simdiki)}")
        elif eskisi:
            satirlar.append(f"{ad} antrenman yok")
    return satirlar


def build_training_events(age: str) -> tuple[list[dict], dict | None]:
    """Antrenman programi degistiyse tek bir bildirim uretir.

    Doner: (olaylar, yeni program). Program ilk kez goruluyorsa bildirim
    uretilmez - yalnizca kaydedilir, yoksa ilk kurulumda gereksiz bildirim gider.
    """
    program = read_json(training_path(age), None)
    if not program or not (program.get("sessions") or []):
        return [], None

    onceki = read_json(training_seen_path(age), None)
    if not onceki:
        return [], program

    if training_by_day(onceki) == training_by_day(program):
        return [], None                 # program ayni; salon adi/hafta degismis olabilir
    satirlar = training_summary(onceki, program)
    if not satirlar:
        return [], program              # yalnizca gecmis gunler degismis: sessizce kaydet

    label = age.upper()
    imza = hashlib.sha1(
        json.dumps(training_by_day(program), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:8]
    govde = " · ".join(satirlar)
    if len(govde) > 240:
        govde = govde[:237] + "..."
    return ([{
        "id": f"training-{age}-{imza}",
        "age": age,
        "title": f"{label} · Antrenman programı güncellendi",
        "body": govde,
        "tag": f"antrenman-{age}",
    }], program)


def build_events(league: dict, age: str = DEFAULT_AGE) -> list[dict]:
    our_key = (league.get("ourTeamKey") or "evolog").lower()
    label = league.get("label") or age.upper()
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
                "age": age,
                "title": f"{label} · {title}",
                "body": f"{home} {f['homeScore']} - {f['awayScore']} {away}",
                "tag": f"mac-{mid}",
            })
            continue

        if not f.get("date"):
            continue

        # Gun/saat degisikligi: velilerin hemen ogrenmesi gereken tek sey bu.
        # Olay kimligi yeni tarih+saati icerir, boylece her degisiklik bir kez
        # gider; ayni degisiklik tekrar tekrar bildirilmez.
        if f.get("changedAt") and f.get("previousDate"):
            eski = fmt_gun(f.get("previousDate"), f.get("previousTime"))
            yeni = fmt_gun(f.get("date"), f.get("time"))
            if eski != yeni:
                events.append({
                    "id": f"change-{mid}-{f.get('date')}-{f.get('time')}",
                    "age": age,
                    "title": f"{label} · Maç saati değişti",
                    "body": (f"{opp} maçı {yeni} oynanacak (önceki: {eski})"
                             + (f" · {f.get('venue')}" if f.get("venue") else "")),
                    "tag": f"mac-{mid}",
                })

        # Oynanmamis mac: baslamasina REMINDER_HOURS'tan az kaldiysa hatirlat.
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
                "age": age,
                "title": f"{label} · Bugün {when} · {opp}",
                "body": ("Maça yaklaşık " + str(int(round(hours_left))) + " saat kaldı"
                         + (f" · {where}" if where else "")),
                "tag": f"mac-{mid}",
            })

    return events


# ---------------------------------------------------------------- gonderim
def send_all(events: list[dict], dry: bool) -> tuple[int, set]:
    """Bildirimleri gonderir. Doner: (gonderim sayisi, en az bir aboneye ulasan olay id'leri)"""
    subs = read_json(SUBS, [])
    if not subs:
        print("Abone yok, gonderilecek bir sey yok.")
        # Kimseye gidemeyen olay birikmesin; sonradan abone olan veli eski
        # maclarin bildirimlerini topluca almasin.
        return 0, {e["id"] for e in events}
    if dry:
        for e in events:
            want = [s for s in subs if e.get("age", DEFAULT_AGE) in (s.get("ages") or [DEFAULT_AGE])]
            print(f"  [deneme] {e['title']} — {e['body']}  ({len(want)}/{len(subs)} abone)")
        return 0, set()

    from pywebpush import WebPushException, webpush

    keys = ensure_keys()
    del keys
    # DIKKAT: anahtari METIN olarak vermeyin. py_vapid metni ham DER sanip
    # "Could not deserialize key data" ile cokuyor; dosya yolu verilince
    # PEM'i dogru okuyor. Bildirimlerin hic gitmemesinin sebebi buydu.
    vapid_key = str(VAPID_PEM)
    alive, sent = [], 0
    delivered: set = set()

    for sub in subs:
        drop = False
        # Abone yalnizca actigi yas gruplarinin macini alir; eski kayitlarda
        # alan yoksa varsayilan yas kabul edilir.
        wanted = sub.get("ages") or [DEFAULT_AGE]
        for e in events:
            if e.get("age", DEFAULT_AGE) not in wanted:
                continue
            payload = json.dumps({
                "title": e["title"], "body": e["body"],
                "tag": e["tag"], "url": APP_URL + "?age=" + e.get("age", DEFAULT_AGE),
            }, ensure_ascii=False)
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": sub.get("keys") or {}},
                    data=payload,
                    vapid_private_key=vapid_key,
                    vapid_claims={"sub": CONTACT},
                    timeout=20,
                )
                sent += 1
                delivered.add(e["id"])
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
    return sent, delivered


def status() -> int:
    """Kurulum dogru mu, kac abone var, hangi bildirimler bekliyor."""
    print(f"Durum dizini : {STATE_DIR}  ({'var' if STATE_DIR.exists() else 'YOK'})")
    print(f"Veri dizini  : {DATA_DIR}  ({'var' if DATA_DIR.exists() else 'YOK'})")

    try:
        import pywebpush  # noqa: F401
        print("pywebpush    : kurulu")
    except ImportError:
        print("pywebpush    : KURULU DEGIL  ->  pip3 install pywebpush")

    print(f"VAPID anahtar: {'var' if VAPID_PEM.exists() else 'YOK (ilk calismada uretilir)'}")

    subs = read_json(SUBS, [])
    print(f"Abone        : {len(subs)}")
    yas = {}
    for s_ in subs:
        for a in (s_.get("ages") or [DEFAULT_AGE]):
            yas[a] = yas.get(a, 0) + 1
    if yas:
        print("               " + ", ".join(f"{k}: {v}" for k, v in sorted(yas.items())))

    leagues = load_leagues()
    if not leagues:
        print("Lig verisi   : OKUNAMADI")
        return 1
    print(f"Lig verisi   : {len(leagues)} yas grubu")

    done = read_json(NOTIFIED, {})
    bekleyen, gonderilmis = [], 0
    olaylar = []
    for age, league in leagues:
        olaylar += build_events(league, age)
    for age in AGES:
        olaylar += build_training_events(age)[0]
    for e in olaylar:
        if e["id"] in done:
            gonderilmis += 1
        else:
            bekleyen.append(e)

    print(f"Gonderilmis  : {gonderilmis} olay")
    print(f"Bekleyen     : {len(bekleyen)} olay")
    for e in bekleyen:
        print(f"   - {e['title']} | {e['body']}")
    if bekleyen and not subs:
        print("\nUYARI: Gonderilecek bildirim var ama hic abone yok.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Evolog mac bildirimleri")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keys", action="store_true", help="VAPID anahtarlarini uret/goster")
    ap.add_argument("--test", action="store_true", help="abonelere deneme bildirimi gonder")
    ap.add_argument("--duyuru", metavar="METIN",
                    help="antrenorden velilere serbest metin bildirimi gonder")
    ap.add_argument("--baslik", metavar="METIN", default="Antrenörden duyuru",
                    help="--duyuru ile gonderilecek bildirimin basligi")
    ap.add_argument("--status", action="store_true",
                    help="abone sayisi, bekleyen olaylar ve kurulum durumunu yaz")
    args = ap.parse_args()

    if args.status:
        return status()

    keys = ensure_keys()
    if args.keys:
        print("VAPID public key:", keys["publicKey"])
        return 0

    if args.duyuru:
        # Antrenor panelinden gelen duyuru. Olay kimligi metnin ozetinden
        # uretilir: ayni metin iki kez gonderilmez, farkli metin engellenmez.
        metin = args.duyuru.strip()[:1000]
        if not metin:
            print("Bos duyuru gonderilmedi.")
            return 1
        imza = hashlib.sha1(metin.encode("utf-8")).hexdigest()[:10]
        olay = {
            "id": "duyuru-" + imza,
            "age": DEFAULT_AGE,
            "title": (args.baslik or "Antrenörden duyuru").strip()[:80],
            # Bildirimde OZET; tam metin uygulamada. url, veliyi dogrudan
            # Duyurular ekranina goturur (app.js ?duyuru=1'i yakalar).
            "body": bildirim_govdesi(metin),
            "tag": "duyuru-" + imza,
            "url": "./?duyuru=1",
        }
        done = read_json(NOTIFIED, {})
        if duyuru_tekrar_mi(done, olay["id"]):
            print(f"TEKRAR: ayni metin son {DUYURU_TEKRAR_DK} dakikada gonderildi.")
            print("Duyuru: 0 gonderim.")
            return 0
        sent, delivered = send_all([olay], args.dry_run)
        if not args.dry_run and olay["id"] in delivered:
            done[olay["id"]] = dt.datetime.now(TZ).isoformat(timespec="seconds")
            write_json(NOTIFIED, done)
        # Abone yoksa bu bir hata degil, bilgi: panel "kimseye ulasmadi" yazar.
        print(f"Duyuru: {sent} gonderim.")
        return 0

    if args.test:
        send_all([{
            "id": "test", "tag": "test",
            "title": "Evolog Kız Basketbol",
            "body": "Bildirimler çalışıyor. Maç öncesi ve sonrası haber vereceğiz.",
        }], args.dry_run)
        return 0

    leagues = load_leagues()
    if not leagues:
        print("Hicbir league.json okunamadi.")
        return 1

    done = read_json(NOTIFIED, {})
    events = []
    for age, league in leagues:
        events += [e for e in build_events(league, age) if e["id"] not in done]

    # Antrenman programi degisikligi: gonderim basarili olunca program
    # "bildirildi" diye kaydedilir, boylece ayni degisiklik ikinci kez gitmez.
    programs = {}
    for age in AGES:
        tr_events, program = build_training_events(age)
        if program is not None:
            programs[age] = (program, [e["id"] for e in tr_events])
        events += [e for e in tr_events if e["id"] not in done]

    if not events:
        for age, (program, ids) in programs.items():
            if not ids:                      # ilk kayit: sessizce sakla
                write_json(training_seen_path(age), program)
        print("Yeni bildirim yok.")
        return 0

    sent, delivered = send_all(events, args.dry_run)
    if not args.dry_run:
        stamp = dt.datetime.now(TZ).isoformat(timespec="seconds")
        for e in events:
            # Gonderilemeyen olay isaretlenmez; sonraki calismada tekrar denenir.
            if e["id"] in delivered:
                done[e["id"]] = stamp
        write_json(NOTIFIED, done)
        for age, (program, ids) in programs.items():
            if all(i in delivered or i in done for i in ids):
                write_json(training_seen_path(age), program)
        kalan = [e for e in events if e["id"] not in delivered]
        if kalan:
            print(f"  {len(kalan)} olay gonderilemedi, sonraki calismada tekrar denenecek")
    print(f"{len(events)} olay, {sent} gonderim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
